"""Teste externo limitado à VPS própria indicada; não imprime credenciais.

Copie privadamente .local/access.json e .local/tls/lab.crt da VPS para a pasta
indicada. Não transporte .env, chaves SSH ou a chave privada do certificado.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
from pathlib import Path
import socket
import ssl
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--private-dir', type=Path, required=True)
    args = parser.parse_args()
    access = json.loads((args.private_dir / 'access.json').read_text())
    ctx = ssl.create_default_context(cafile=str(args.private_dir / 'lab.crt'))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx))
    checks = []
    def probe(port):
        try:
            with socket.create_connection((args.host, port), timeout=5):
                state = 'CONNECTED'
        except OSError as error:
            state = 'TIMEOUT_OR_FILTERED' if isinstance(error, TimeoutError) else 'REFUSED_OR_UNREACHABLE'
        expected = port in [22, 80, 443]
        return {'check': 'TCP ' + str(port), 'result': state, 'status': 'PASS' if (state == 'CONNECTED') == expected else 'FAIL'}
    with ThreadPoolExecutor(max_workers=7) as pool:
        checks.extend(pool.map(probe, [22, 80, 443, 111, 5678, 5432, 19443]))
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    redirect = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        redirect.open('http://' + args.host + '/', timeout=8)
        checks.append({'check': 'Redirect externo HTTP para HTTPS', 'status': 'FAIL'})
    except urllib.error.HTTPError as error:
        ok = error.code == 301 and error.headers.get('Location') == 'https://' + args.host + '/'
        checks.append({'check': 'Redirect externo HTTP para HTTPS', 'status': 'PASS' if ok else 'FAIL', 'http_status': error.code})
    except OSError:
        checks.append({'check': 'Redirect externo HTTP para HTTPS', 'status': 'BLOCKED', 'reason': 'Sem conexão HTTP externa'})
    def http(name, path, expected, authenticated=False):
        headers = {}
        if authenticated:
            headers['Authorization'] = 'Basic ' + base64.b64encode((access['proxy_user'] + ':' + access['proxy_password']).encode()).decode()
        request = urllib.request.Request('https://' + args.host + path, headers=headers)
        try:
            with opener.open(request, timeout=8) as response:
                status = response.status
                response.read()
        except urllib.error.HTTPError as error:
            status = error.code
        except OSError:
            checks.append({'check': name, 'status': 'BLOCKED', 'reason': 'Sem conexão HTTPS externa ou TLS inválido'})
            return
        checks.append({'check': name, 'status': 'PASS' if status == expected else 'FAIL', 'http_status': status})
    http('TLS externo validado e painel exige BasicAuth', '/', 401)
    http('Painel externo com BasicAuth', '/', 200, authenticated=True)
    http('Login nativo necessário após BasicAuth', '/rest/workflows', 401, authenticated=True)
    output = {'executed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope': 'VPS própria de teste, cliente externo; endereço e credenciais omitidos',
        'ipv6': 'VPS sem endereço IPv6 global; não houve teste externo IPv6', 'checks': checks}
    (ROOT / 'evidence/verification-external.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'checks': len(checks), 'passed': sum(x['status'] == 'PASS' for x in checks), 'pending': [x['check'] for x in checks if x['status'] != 'PASS']}, ensure_ascii=False))
    return 0 if all(x['status'] == 'PASS' for x in checks) else 1

if __name__ == '__main__':
    raise SystemExit(main())
