"""Laboratório próprio reproduzível. Python 3.10+ e Docker Compose 2.24+.

Executado no host do laboratório; não publica em GitHub/Trello nem imprime segredos.
"""
import argparse
import base64
import copy
import datetime as dt
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local'
N8N_IMAGE = 'docker.n8n.io/n8nio/n8n:2.42.6@sha256:526daa38b68e923cc00c5280d18b4da5d489f115a73bdbf3b8e452b184197a9a'
WORKFLOW_ID = 'aresLabWorkflow01'


def run(args, *, data=None, timeout=180):
    result = subprocess.run(args, cwd=ROOT, input=data, text=True,
                            encoding='utf-8', errors='replace', capture_output=True,
                            timeout=timeout)
    if result.returncode:
        # Não reproduz stderr arbitrário: ele pode conter valores interpolados.
        raise RuntimeError(f'Comando {args[0]} {args[1]} falhou (exit {result.returncode}).')
    return result.stdout


def compose(*args, audit=False, timeout=240, data=None):
    file = 'compose.audit.yml' if audit else 'docker-compose.yml'
    return run(['docker', 'compose', '-f', file, *args], timeout=timeout, data=data)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8', newline='\n')
    if path.is_relative_to(LOCAL) or path == ROOT / '.env':
        path.chmod(0o600)


def json_write(path, obj):
    write(path, json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def read_env():
    result = {}
    for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            result[k] = v.strip("'\"")
    return result


def render_routes():
    env = read_env()
    host = env['N8N_HOST']
    if not re.fullmatch(r'[a-zA-Z0-9.-]+', host):
        raise ValueError('N8N_HOST deve ser um hostname, sem esquema nem porta.')
    template = (ROOT / 'traefik/routes.template.yml').read_text(encoding='utf-8')
    write(LOCAL / 'dynamic/routes.yml', template.replace('__HOST__', host)
          .replace('__TLS_PORT__', str(int(env['TLS_PORT']))))


def init(host='localhost', vps=False):
    if not re.fullmatch(r'[a-zA-Z0-9.-]+', host):
        raise ValueError('Host inválido; informe IP ou hostname sem esquema/porta.')
    if (ROOT / '.env').exists() or (LOCAL / 'access.json').exists():
        raise RuntimeError('Configuração já existe; init não sobrescreve chaves ou senhas.')
    openssl = shutil.which('openssl')
    if not openssl and os.name == 'nt':
        candidate = Path('C:/Program Files/Git/usr/bin/openssl.exe')
        if candidate.exists():
            openssl = str(candidate)
    if not openssl:
        raise RuntimeError('Instale OpenSSL antes de inicializar.')
    run(['docker', 'info', '--format', '{{.ServerVersion}}'])
    access = {'proxy_user': 'lab', 'proxy_password': secrets.token_urlsafe(24),
              'owner_email': 'owner@example.invalid',
              'owner_password': 'Aa1!' + secrets.token_urlsafe(24),
              'webhook_token': secrets.token_urlsafe(32)}
    js = "const fs=require('fs'); const b=require(require.resolve('bcryptjs',{paths:['/usr/local/lib/node_modules/n8n']})); const x=JSON.parse(fs.readFileSync(0,'utf8')); console.log(JSON.stringify(x.map(p=>b.hashSync(p,12))));"
    hashes = json.loads(run(['docker', 'run', '--rm', '-i', '--network', 'none',
                             '--entrypoint', 'node', N8N_IMAGE, '-e', js],
                            data=json.dumps([access['proxy_password'], access['owner_password']]), timeout=900))
    env = (ROOT / '.env.example').read_text(encoding='utf-8')
    if os.name == 'posix':
        env = env.replace('PROXY_UID=0', 'PROXY_UID=' + str(os.getuid()))
        env = env.replace('PROXY_GID=0', 'PROXY_GID=' + str(os.getgid()))
    if vps:
        env = env.replace('ADMIN_BIND=127.0.0.1', 'ADMIN_BIND=0.0.0.0')
        env = env.replace('WEB_PORT=18080', 'WEB_PORT=80').replace('TLS_PORT=18443', 'TLS_PORT=443')
        env = env.replace('N8N_HOST=localhost', 'N8N_HOST=' + host)
        env = env.replace('https://localhost:18443/', f'https://{host}/')
        env = env.replace('https://localhost:19443/', f'https://{host}:19443/')
    env = env.replace('POSTGRES_PASSWORD=GENERATE_WITH_LAB_INIT', 'POSTGRES_PASSWORD=' + secrets.token_hex(32))
    env = env.replace('POSTGRES_ADMIN_PASSWORD=GENERATE_WITH_LAB_INIT', 'POSTGRES_ADMIN_PASSWORD=' + secrets.token_hex(32))
    env = env.replace('N8N_ENCRYPTION_KEY=GENERATE_WITH_LAB_INIT', 'N8N_ENCRYPTION_KEY=' + secrets.token_hex(32))
    env = env.replace("OWNER_PASSWORD_HASH='GENERATE_WITH_LAB_INIT'", "OWNER_PASSWORD_HASH='" + hashes[1] + "'")
    env = env.replace('RUNNERS_AUTH_TOKEN=GENERATE_WITH_LAB_INIT', 'RUNNERS_AUTH_TOKEN=' + secrets.token_hex(32))
    write(ROOT / '.env', env)
    json_write(LOCAL / 'access.json', access)
    write(LOCAL / 'secrets/proxy.users', 'lab:' + hashes[0] + '\n')
    tls = LOCAL / 'tls'
    tls.mkdir(parents=True, exist_ok=True)
    san = 'DNS:localhost,IP:127.0.0.1'
    if host != 'localhost':
        try:
            ipaddress.ip_address(host)
            san += ',IP:' + host
        except ValueError:
            san += ',DNS:' + host
    run([openssl, 'req', '-x509', '-newkey', 'rsa:3072', '-sha256', '-nodes',
         '-keyout', str(tls / 'lab.key'), '-out', str(tls / 'lab.crt'),
         '-days', '30', '-subj', '/CN=' + host,
         '-addext', 'subjectAltName=' + san])
    (tls / 'lab.key').chmod(0o600)
    render_routes()
    baseline = json.loads((ROOT / 'workflows/baseline.json').read_text(encoding='utf-8'))
    hardened = copy.deepcopy(baseline)
    hardened[0]['nodes'] = hardened[0]['nodes'][:2]
    hardened[0]['nodes'][0]['parameters']['authentication'] = 'headerAuth'
    hardened[0]['nodes'][0]['credentials'] = {'httpHeaderAuth': {'id': 'aresLabHeader01', 'name': 'ARES header sintetico'}}
    json_write(LOCAL / 'fixtures/baseline.json', baseline)
    json_write(LOCAL / 'fixtures/hardened.json', hardened)
    json_write(LOCAL / 'fixtures/credentials.json', [{'id': 'aresLabHeader01',
        'name': 'ARES header sintetico', 'type': 'httpHeaderAuth',
        'data': {'name': 'X-Lab-Webhook-Token', 'value': access['webhook_token']}}])
    print('Inicializado: segredos locais em .local/access.json; nenhum segredo impresso.')


def extract_report(raw):
    decoder = json.JSONDecoder()
    for match in re.finditer(r'[\[{]', raw):
        try:
            obj, _ = decoder.raw_decode(raw[match.start():])
            if isinstance(obj, list) and obj and all(isinstance(x, dict) and 'risk' in x for x in obj):
                return obj
            if isinstance(obj, dict) and any('Risk Report' in k for k in obj):
                return obj
        except ValueError:
            pass
    if 'No security issues found' in raw:
        return []
    raise RuntimeError('Não foi possível extrair um relatório real de n8n audit.')


def cli(*args, audit=False):
    service = 'audit' if audit else 'n8n'
    return compose('run', '--rm', '--no-deps', '-T', service, *args, audit=audit)


def seed(audit=False, hardened=True):
    # O arquivo privado pertence ao usuário do host, que pode ter UID diferente
    # de 1000. Transportar por stdin evita torná-lo legível a outros usuários.
    def import_file(command, filename):
        js = "const fs=require('fs'),cp=require('child_process');const p='/tmp/ares-import.json';fs.writeFileSync(p,fs.readFileSync(0),{mode:0o600});const r=cp.spawnSync('n8n',[process.argv[1],'--input='+p],{stdio:'inherit'});fs.unlinkSync(p);if(r.error)throw r.error;process.exit(r.status??1);"
        data = (LOCAL / 'fixtures' / filename).read_text(encoding='utf-8')
        compose('run', '--rm', '--no-deps', '-T', '--entrypoint', 'node',
                'audit' if audit else 'n8n', '-e', js, command, audit=audit, data=data)
    if hardened:
        import_file('import:credentials', 'credentials.json')
    filename = 'hardened' if hardened else 'baseline'
    import_file('import:workflow', filename + '.json')
    cli('publish:workflow', '--id=' + WORKFLOW_ID, audit=audit)


def audit_before():
    print('Gerando auditoria baseline isolada, sem rede nem portas...')
    seed(audit=True, hardened=False)
    raw = cli('audit', audit=True)
    json_write(ROOT / 'evidence/audit-before.json', extract_report(raw))
    write(ROOT / 'evidence/audit-before.log', raw)
    print('Auditoria antes salva.')


def up():
    print('Iniciando PostgreSQL e preparando workflow autenticado...')
    compose('up', '-d', '--wait', 'postgres', timeout=600)
    # A CLI publica versões com a aplicação parada.
    compose('stop', 'n8n')
    seed()
    compose('up', '-d', '--wait', '--wait-timeout', '180', timeout=600)
    print('Laboratório pronto: ' + read_env()['EDITOR_URL'] + ' (credenciais em .local/access.json).')


def audit_after():
    print('Gerando auditoria da instância PostgreSQL endurecida...')
    raw = compose('exec', '-T', 'n8n', 'n8n', 'audit')
    json_write(ROOT / 'evidence/audit-after.json', extract_report(raw))
    write(ROOT / 'evidence/audit-after.log', raw)
    print('Auditoria depois salva.')


def verify(vps=False):
    env = read_env()
    if vps and (os.name != 'posix' or env['ADMIN_BIND'] != '0.0.0.0' or env['TLS_PORT'] != '443' or env['WEB_PORT'] != '80'):
        raise RuntimeError('verify --vps exige Linux e perfil VPS nas portas 80/443.')
    if (not vps and env['ADMIN_BIND'] != '127.0.0.1') or env['HOOK_BIND'] != '127.0.0.1':
        raise RuntimeError('verify automatizado exige binds de loopback do laboratório.')
    access = json.loads((LOCAL / 'access.json').read_text(encoding='utf-8'))
    config = json.loads(compose('config', '--format', 'json'))
    for name in ['n8n', 'postgres']:
        if config['services'][name].get('ports'):
            raise RuntimeError(name + ' publicou portas indevidamente.')
    context = ssl.create_default_context(cafile=str(LOCAL / 'tls/lab.crt'))
    # ProxyHandler({}) evita encaminhar testes localhost a proxies do SO.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
    checks = []

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    redirect_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        redirect_opener.open(urllib.request.Request('http://localhost:' + env['WEB_PORT'] + '/', headers={'Host': env['N8N_HOST']}), timeout=15)
        raise RuntimeError('HTTP sem redirect HTTPS.')
    except urllib.error.HTTPError as error:
        if error.code != 301 or error.headers.get('Location') != env['EDITOR_URL']:
            raise RuntimeError('Redirect HTTP/HTTPS inesperado.')
        checks.append({'check': 'HTTP redireciona para a porta HTTPS correta', 'status': 'PASS', 'http_status': error.code})

    def check(name, path, expected, *, hooks=False, basic=False, token=False, method='GET'):
        base = env['WEBHOOK_URL'] if hooks else env['EDITOR_URL']
        if vps:
            # IP literal também prova o defaultCertificate, sem depender de SNI.
            base = 'https://127.0.0.1:' + (env['HOOK_PORT'] if hooks else env['TLS_PORT']) + '/'
        headers = {'Host': env['N8N_HOST']}
        if basic:
            headers['Authorization'] = 'Basic ' + base64.b64encode((access['proxy_user'] + ':' + access['proxy_password']).encode()).decode()
        if token:
            headers['X-Lab-Webhook-Token'] = token if isinstance(token, str) else access['webhook_token']
        req = urllib.request.Request(base.rstrip('/') + path, headers=headers, method=method,
                                     data=b'{}' if method == 'POST' else None)
        try:
            with opener.open(req, timeout=15) as response:
                code, body, response_headers = response.status, response.read(), dict(response.headers)
        except urllib.error.HTTPError as error:
            code, body, response_headers = error.code, error.read(), dict(error.headers)
        if code != expected:
            raise RuntimeError(f'{name}: HTTP {code}, esperado {expected}.')
        checks.append({'check': name, 'status': 'PASS', 'http_status': code})
        return body, response_headers

    check('Painel exige BasicAuth', '/', 401)
    body, headers = check('Painel autenticado via HTTPS', '/', 200, basic=True)
    if not any(k.lower() == 'strict-transport-security' for k in headers):
        raise RuntimeError('HSTS não presente.')
    check('Webhook exige header do n8n', '/webhook/ares-lab', 403, hooks=True, method='POST')
    check('Webhook rejeita token incorreto', '/webhook/ares-lab', 403, hooks=True, token='invalid-lab-token', method='POST')
    body, _ = check('Webhook autenticado executa workflow', '/webhook/ares-lab', 200, hooks=True, token=True, method='POST')
    if json.loads(body) != {'ok': True, 'lab': 'ares'}:
        raise RuntimeError('Resposta do workflow inesperada.')
    check('Entrada de webhook bloqueia painel', '/', 404, hooks=True)
    check('Entrada de webhook bloqueia REST', '/rest/settings', 404, hooks=True)
    check('Entrada de webhook bloqueia outro caminho', '/webhook/other', 404, hooks=True, token=True, method='POST')
    check('Entrada de webhook bloqueia GET', '/webhook/ares-lab', 404, hooks=True)
    check('Login nativo exige sessão', '/rest/workflows', 401, basic=True)
    check('API sem sessão rejeitada (API key desabilitada no audit)', '/api/v1/workflows', 401, basic=True)
    # Prova do login nativo e atributos do cookie, sem salvar cookies/senha.
    login_base = 'https://127.0.0.1:' + env['TLS_PORT'] if vps else env['EDITOR_URL'].rstrip('/')
    req = urllib.request.Request(login_base + '/rest/login',
        data=json.dumps({'emailOrLdapLoginId': access['owner_email'], 'password': access['owner_password']}).encode(),
        headers={'Content-Type': 'application/json', 'Host': env['N8N_HOST'], 'Authorization': 'Basic ' + base64.b64encode((access['proxy_user'] + ':' + access['proxy_password']).encode()).decode()}, method='POST')
    with opener.open(req, timeout=15) as response:
        cookie = response.headers.get('Set-Cookie', '')
        if 'Secure' not in cookie or 'HttpOnly' not in cookie:
            raise RuntimeError('Cookie de sessão sem Secure/HttpOnly.')
        checks.append({'check': 'Login nativo com cookie Secure e HttpOnly', 'status': 'PASS', 'http_status': response.status})
    for name in ['n8n', 'postgres']:
        cid = compose('ps', '-q', name).strip()
        binding = json.loads(run(['docker', 'inspect', cid, '--format', '{{json .HostConfig.PortBindings}}']))
        if binding:
            raise RuntimeError(name + ' possui PortBindings no runtime.')
        checks.append({'check': name + ' sem porta publicada no runtime', 'status': 'PASS'})
    role = compose('exec', '-T', 'postgres', 'psql', '-U', 'postgres', '-d', 'postgres', '-Atc', "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname='n8n';").strip()
    if role != 'f|f|f':
        raise RuntimeError('Role n8n com privilégios indevidos no PostgreSQL.')
    checks.append({'check': 'Role n8n sem superuser/createdb/createrole', 'status': 'PASS'})
    evidence = {'executed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'scope': 'VPS Ubuntu de teste, requisições pelo loopback; teste externo registrado separadamente' if vps else 'Docker Desktop local; TLS validado com certificado de teste; nenhum acesso a VPS',
                'checks': checks}
    json_write(ROOT / ('evidence/verification-vps.json' if vps else 'evidence/verification.json'), evidence)
    print(f'{len(checks)} verificações passaram; evidências sem segredos salvas.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'render', 'before', 'up', 'after', 'verify', 'down'])
    parser.add_argument('--vps', action='store_true', help='Perfil de VPS própria: 80/443; webhook permanece loopback. verify testa localmente no Linux.')
    parser.add_argument('--host', default='localhost', help='IP/hostname da VPS usado por init --vps e pelo certificado de teste.')
    args = parser.parse_args()
    actions = {'init': lambda: init(host=args.host, vps=args.vps), 'render': render_routes, 'before': audit_before,
               'up': up, 'after': audit_after, 'verify': lambda: verify(vps=args.vps),
               'down': lambda: compose('down')}
    actions[args.action]()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
