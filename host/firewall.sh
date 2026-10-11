#!/usr/bin/env bash
# Gera comandos para uma VM Ubuntu/Debian própria. NÃO aplica automaticamente.
set -euo pipefail
mode=${1:-proxy}
ssh_port=${SSH_PORT:-22}
admin_cidr=${ADMIN_CIDR:-}
case "$mode" in proxy|vpn) ;; *) echo 'Uso: firewall.sh proxy|vpn' >&2; exit 1 ;; esac
[[ "$ssh_port" =~ ^[0-9]+$ ]] && ((ssh_port > 0 && ssh_port < 65536)) || exit 1
if [[ "$mode" == proxy ]]; then
  [[ "$admin_cidr" =~ ^[0-9a-fA-F.:/]+$ ]] || { echo 'Defina ADMIN_CIDR do administrador.' >&2; exit 1; }
fi
cat <<'EOF'
# Execute manualmente na VM de teste. Antes: SSH por chave em segunda sessão,
# console de recuperação acessível e snapshot. Examine regras atuais: ufw status numbered.
# Máquina NOVA: retire regras prévias que liberem outras portas (incluindo IPv6).
sudo ufw default deny incoming
sudo ufw default allow outgoing
EOF
if [[ "$mode" == proxy ]]; then
  printf 'sudo ufw allow from %s to any port %s proto tcp\n' "$admin_cidr" "$ssh_port"
  printf 'sudo ufw allow 80/tcp\nsudo ufw allow 443/tcp\n'
else
  printf 'sudo ufw allow 51820/udp\n'
  printf 'sudo ufw allow in on wg0 to any port %s proto tcp\n' "$ssh_port"
  printf 'sudo ufw allow in on wg0 to any port 443 proto tcp\n'
  printf '# Se habilitar webhook: sudo ufw allow 443/tcp\n'
fi
cat <<'EOF'
sudo ufw enable
sudo ufw status verbose
# Docker usa FORWARD/DNAT. UFW sozinho não filtra ports: dos containers!
# Publique SOMENTE Traefik; não publique 5678 ou 5432.
# Para filtros adicionais em containers: DOCKER-USER no backend iptables,
# ou chain nftables própria com prioridade apropriada no backend nftables.
# Confira IPv4 E IPv6 por um segundo host seu após aplicar.
EOF
