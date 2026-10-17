"""Verifica controles reais do host Linux; executar com sudo em sessão SSH nova."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
def run(*args):
    return subprocess.check_output(args, text=True)

checks = []
def check(name, condition):
    checks.append({'check': name, 'status': 'PASS' if condition else 'FAIL'})

effective = dict(line.split(' ', 1) for line in run('/usr/sbin/sshd', '-T').splitlines() if ' ' in line)
expected = {'passwordauthentication': 'no', 'kbdinteractiveauthentication': 'no',
    'pubkeyauthentication': 'yes', 'permitrootlogin': 'no', 'authenticationmethods': 'publickey'}
for key, value in expected.items():
    check('SSH ' + key + ' ' + value, effective.get(key) == value)
ufw = run('ufw', 'status', 'verbose')
check('UFW ativo com entrada padrão negada', 'Status: active' in ufw and 'deny (incoming)' in ufw)
rules = [line for line in ufw.splitlines() if 'ALLOW' in line]
check('Regras UFW somente TCP 22/80/443 em IPv4 e IPv6', len(rules) == 6 and all(line.split()[0] in ['22/tcp', '80/tcp', '443/tcp'] for line in rules))
before = run('iptables', '-S', 'ufw-before-output')
check('Proteção OCI persistente precede ACCEPT de saída', next((x for x in before.splitlines() if x.startswith('-A')), '') == '-A ufw-before-output -d 169.254.0.0/16 -j ares-instance-services')
original = run('iptables', '-S', 'InstanceServices')
preserved = run('iptables', '-S', 'ares-instance-services')
check('Regras OCI preservadas integralmente', [x.replace('InstanceServices', 'ares-instance-services') for x in original.splitlines() if x.startswith('-A')] == [x for x in preserved.splitlines() if x.startswith('-A')])
rpc = subprocess.run(['systemctl', 'is-active', 'rpcbind.socket', 'rpcbind.service'], capture_output=True, text=True)
check('RPC serviço/socket inativos', rpc.stdout.splitlines() == ['inactive', 'inactive'])
timer = subprocess.run(['systemctl', 'is-active', 'ares-host-rollback.timer'], capture_output=True, text=True)
check('Reversão automática cancelada após nova conexão', timer.stdout.strip() == 'inactive')
check('Verificação executada por SSH', bool(os.environ.get('SSH_CONNECTION')))
swap = run('swapon', '--show', '--bytes', '--noheadings', '--output', 'NAME,SIZE')
swap_sizes = [next((int(x) for x in line.split()[1:] if x.isdecimal()), 0)
    for line in swap.splitlines() if line.split()[0] == '/swap-ares']
check('Swap de 2 GiB ativo', any(size >= 2 * 1024**3 - 1024**2 for size in swap_sizes))
auto_conf = Path('/etc/apt/apt.conf.d/20auto-upgrades')
apt_timer = subprocess.run(['systemctl', 'is-active', 'apt-daily-upgrade.timer'], capture_output=True, text=True)
check('Atualizações automáticas de segurança ativas', auto_conf.exists() and 'Unattended-Upgrade "1"' in auto_conf.read_text(encoding='utf-8') and apt_timer.stdout.strip() == 'active')
output = {'executed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
    'scope': 'VPS própria OCI Ubuntu; endereços/credenciais omitidos',
    'ssh_effective': {k: effective.get(k) for k in expected}, 'ufw_status': ufw,
    'ipv6_global_present': bool(run('ip', '-6', 'addr', 'show', 'scope', 'global').strip()),
    'checks': checks}
(ROOT / 'evidence/verification-host.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'checks': len(checks), 'passed': sum(x['status'] == 'PASS' for x in checks)}))
if any(x['status'] != 'PASS' for x in checks):
    raise SystemExit(1)
