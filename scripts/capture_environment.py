"""Registra versões, limites e proveniência reais no host Linux, sem segredos."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import lab

ROOT = Path(__file__).resolve().parents[1]
def run(*args):
    return subprocess.check_output(args, text=True).strip()

os_release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
services = {}
for name in ['traefik', 'n8n', 'postgres']:
    cid = lab.compose('ps', '-q', name).strip()
    obj = json.loads(run('docker', 'inspect', cid))[0]
    services[name] = {'image_reference': obj['Config']['Image'],
        'status': obj['State']['Status'], 'health': obj['State'].get('Health', {}).get('Status', 'not-configured'),
        'user': obj['Config']['User'], 'memory_limit_bytes': obj['HostConfig']['Memory'],
        'memory_and_swap_limit_bytes': obj['HostConfig']['MemorySwap'],
        'published_host_ports': [value['HostPort'] for values in (obj['HostConfig']['PortBindings'] or {}).values() for value in values]}
files = {}
for name in ['audit-before.json', 'audit-after.json', 'verification-vps.json', 'verification-host.json']:
    path = ROOT / 'evidence' / name
    files[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'modified_at_utc': dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()}
output = {'executed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
    'scope': 'VPS própria OCI de teste; nenhum endereço, hostname pessoal ou segredo',
    'os': os_release['PRETTY_NAME'].strip('"'), 'architecture': run('uname', '-m'),
    'docker_engine': run('docker', 'version', '--format', '{{.Server.Version}}'),
    'compose': run('docker', 'compose', 'version', '--short'),
    'services': services, 'evidence_provenance': files}
lab.json_write(ROOT / 'evidence/environment-vps.json', output)
print('Ambiente e proveniência registrados sem segredos.')
