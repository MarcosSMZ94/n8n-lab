"""Aplica SSH/UFW em uma imagem OCI Ubuntu nova, com rollback em 5 minutos.

Executar com sudo, antes de iniciar os containers. Recusa regras inesperadas.
Depois de confirmar NOVA conexão SSH por chave, cancelar ares-host-rollback.timer.
Backups privados em /root/ares-host-backup. Não usar numa VPS com workloads.
"""
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
BACKUP = Path('/root/ares-host-backup')

def run(*args):
    return subprocess.check_output(args, text=True)

if run('id', '-u').strip() != '0':
    raise SystemExit('Execute com sudo.')
if BACKUP.exists():
    raise SystemExit('Backup existente; revise o estado antes de repetir.')
if 'Status: active' in run('ufw', 'status'):
    raise SystemExit('UFW já ativo; aplicação automática recusada.')
legacy_input = [
    '-A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT',
    '-A INPUT -p icmp -j ACCEPT',
    '-A INPUT -i lo -j ACCEPT',
    '-A INPUT -p tcp -m state --state NEW -m tcp --dport 22 -j ACCEPT',
    '-A INPUT -j REJECT --reject-with icmp-host-prohibited',
]
current = [x for x in run('iptables', '-S', 'INPUT').splitlines() if x.startswith('-A')]
if current != legacy_input:
    raise SystemExit('INPUT não corresponde à imagem OCI nova; revise manualmente.')
protected = [x for x in run('iptables-save').splitlines() if x.startswith('-A InstanceServices ')]
if not protected:
    raise SystemExit('Proteções InstanceServices não encontradas; aplicação recusada.')
dropin = Path('/etc/ssh/sshd_config.d/00-ares-lab.conf')
if dropin.exists():
    raise SystemExit('Drop-in já existente; não será sobrescrito.')
BACKUP.mkdir(mode=0o700)
for name in ['before.rules', 'before6.rules', 'ufw.conf', 'user.rules', 'user6.rules']:
    shutil.copy2(Path('/etc/ufw') / name, BACKUP / name)
(BACKUP / 'iptables.v4').write_text(run('iptables-save'))
(BACKUP / 'iptables.v6').write_text(run('ip6tables-save'))
rollback = BACKUP / 'rollback.sh'
rollback.write_text('''#!/bin/sh
set -eu
rm -f /etc/ssh/sshd_config.d/00-ares-lab.conf
/usr/sbin/sshd -t
systemctl reload ssh
ufw disable
cp /root/ares-host-backup/before.rules /etc/ufw/before.rules
cp /root/ares-host-backup/before6.rules /etc/ufw/before6.rules
iptables-restore < /root/ares-host-backup/iptables.v4
ip6tables-restore < /root/ares-host-backup/iptables.v6
''')
rollback.chmod(0o700)
run('systemd-run', '--unit=ares-host-rollback', '--on-active=5m', str(rollback))
shutil.copy2(HERE / 'sshd-hardening.conf', dropin)
dropin.chmod(0o644)
run('/usr/sbin/sshd', '-t')
run('systemctl', 'reload', 'ssh')
# UFW substitui iptables-persistent. Preservar a proteção OCI também após reboot.
rules = Path('/etc/ufw/before.rules')
text = rules.read_text()
text = text.replace(':ufw-before-input - [0:0]', ':ares-instance-services - [0:0]\n:ufw-before-input - [0:0]')
oci = '\n'.join(x.replace('-A InstanceServices ', '-A ares-instance-services ', 1) for x in protected)
text = text.replace('# allow all on loopback', '# Proteção OCI preservada, antes de ACCEPT de saída.\n' + oci + '\n-A ufw-before-output -d 169.254.0.0/16 -j ares-instance-services\n\n# allow all on loopback')
# Serviços de descoberta não são necessários neste laboratório.
text = '\n'.join(x for x in text.splitlines() if not ('-A ufw-before-input' in x and ('--dport 5353' in x or '--dport 1900' in x))) + '\n'
rules.write_text(text)
run('ufw', 'default', 'deny', 'incoming')
run('ufw', 'default', 'allow', 'outgoing')
for port in ['22', '80', '443']:
    run('ufw', 'allow', port + '/tcp')
run('ufw', '--force', 'enable')
# Agora INPUT é governada por UFW; retirar somente as cinco regras conhecidas.
import shlex
for rule in legacy_input:
    run('iptables', *shlex.split(rule.replace('-A INPUT ', '-D INPUT ', 1)))
run('iptables', '-D', 'FORWARD', '-j', 'REJECT', '--reject-with', 'icmp-host-prohibited')
# A imagem nova não usa NFS: fechar o serviço RPC desnecessário.
subprocess.run(['systemctl', 'disable', '--now', 'rpcbind.socket', 'rpcbind.service'], check=True)
print(run('ufw', 'status', 'verbose'))
print('Confirme NOVA sessão SSH por chave e cancele: sudo systemctl stop ares-host-rollback.timer')
