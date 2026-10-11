#!/usr/bin/env bash
# Somente VM Ubuntu própria de laboratório, sem workloads existentes.
set -euo pipefail
test "$(id -u)" -eq 0 || { echo 'Execute com sudo.' >&2; exit 1; }
. /etc/os-release
test "$ID" = ubuntu || { echo 'Este bootstrap exige Ubuntu.' >&2; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y ca-certificates curl openssl ufw
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
# A VM utilizada tem 1 GiB de RAM. Não sobrescreve swap existente.
if [ "$(awk '/MemTotal/ {print $2}' /proc/meminfo)" -lt 2000000 ] && ! swapon --show --noheadings | grep -q .; then
  test ! -e /swap-ares || { echo '/swap-ares já existe; revise manualmente.' >&2; exit 1; }
  fallocate -l 2G /swap-ares
  chmod 0600 /swap-ares
  mkswap /swap-ares
  swapon /swap-ares
  echo '/swap-ares none swap sw 0 0' >> /etc/fstab
fi
docker version --format 'Docker Engine {{.Server.Version}}'
docker compose version
free -h
