# Host Ubuntu/Debian de teste

Controles aplicados em 11/10/2026 à VPS **própria de laboratório** fornecida por Marcos: Ubuntu 26.04 LTS, SSH 22 somente por chave, root/senha/keyboard-interactive desabilitados, UFW com 22/80/443 TCP em IPv4/IPv6. Uma conexão SSH nova funcionou após a alteração e a tentativa externa sem chave foi rejeitada com `Permission denied (publickey)`. O host não tem endereço IPv6 global; o teste externo IPv6 não foi executado.

Docker Engine 29.9.0 e Compose 5.6.0 foram instalados pelo repositório oficial. A VM tem cerca de 1 GiB de RAM e recebeu swap de 2 GiB. Os containers têm limites de memória; esse tamanho é suficiente para a fixture de teste, sem caracterizar dimensionamento de produção. RPC não usado foi desativado.

UFW substitui `iptables-persistent` nessa imagem. As regras OCI `InstanceServices` foram copiadas integralmente para uma chain persistente em `before.rules`, antes das liberações de saída; iSCSI, DNS e metadata não foram removidos. Recarregar UFW preservou essa proteção. Backups ficam em `/root/ares-host-backup`; a reversão automática de cinco minutos foi cancelada após confirmar a nova sessão SSH.

Resultados sem endereços/segredos: [verification-host.json](../evidence/verification-host.json). O script `harden-oracle-lab.py` recusa UFW ativo, backup/drop-in existente ou regras INPUT diferentes da imagem OCI nova; não serve para uma VPS com outros workloads.

## Reproduzir em outra VPS própria nova

Transfira apenas os arquivos entregáveis para a VM. As chaves SSH, a senha da chave e os segredos do computador não fazem parte do stack. Antes de qualquer alteração, confirme a chave SSH em outra sessão e mantenha acesso ao console OCI.

```bash
sudo bash host/bootstrap-ubuntu.sh
# Somente imagem OCI Ubuntu nova, nas condições verificadas pelo script:
sudo python3 host/harden-oracle-lab.py
# Em uma NOVA sessão SSH confirmada:
sudo systemctl stop ares-host-rollback.timer
sudo --preserve-env=SSH_CONNECTION python3 host/verify-host.py
sudo python3 scripts/lab.py init --vps --host <IP_OU_HOSTNAME_DO_LAB>
sudo python3 scripts/lab.py before
sudo python3 scripts/lab.py up
sudo python3 scripts/lab.py verify --vps
sudo python3 scripts/lab.py after
```

O perfil VPS publica 80/443 no IPv4 do host; 19443 continua exclusivamente em loopback. `init --vps --host` gera um certificado de teste novo com SAN do endereço indicado e de localhost. O certificado não é confiável automaticamente no navegador. Para uso além da avaliação, substitua-o por certificado emitido por uma CA confiável para seu domínio de teste.

Na OCI, as Security Lists/NSGs também devem permitir TCP 80/443 da origem de avaliação. Abrir UFW não altera a camada de rede da nuvem. Para teste externo, copie privadamente apenas `.local/access.json` e `.local/tls/lab.crt` da VPS para `.local/vps/access.json` e `.local/vps/lab.crt` no cliente, e execute `python scripts/verify_external.py --host <IP_DO_LAB> --private-dir .local/vps`. Não copie a chave privada TLS ou `.env`.

## Estado 02 — proxy

1. Crie um usuário administrativo sem ser root e instale sua chave pública em `~/.ssh/authorized_keys` (diretório 0700 e arquivo 0600). Mantenha console da VM e snapshot. Confirme uma segunda conexão por chave antes de desabilitar senha.
2. Copie `sshd-hardening.conf` para `/etc/ssh/sshd_config.d/00-ares-lab.conf`. Valide `sudo sshd -t` e `sudo sshd -T`. Includes e regras `Match` podem alterar o resultado efetivo; confira `passwordauthentication no`, `kbdinteractiveauthentication no`, `permitrootlogin no` e `authenticationmethods publickey` para o usuário/IP real.
3. Recarregue `sudo systemctl reload ssh` no Ubuntu/Debian e abra outra sessão por chave. Uma tentativa por senha deve falhar. O arquivo não troca a porta atual nem cria usuários/chaves automaticamente.
4. Gere os comandos do firewall com `ADMIN_CIDR=<seu_ip>/32 SSH_PORT=22 bash host/firewall.sh proxy`. Revise e aplique na VM nova. O script imprime o plano; não executa UFW. Se o SSH usar outra porta, use o valor real.
5. Na VM, use `init --vps --host` em uma configuração nova, ou configure `.env`: `ADMIN_BIND=0.0.0.0`, `WEB_PORT=80`, `TLS_PORT=443`, `N8N_HOST=<dominio_do_lab>`, `EDITOR_URL=https://<dominio_do_lab>/`. A entrada opcional de webhook deve continuar fechada em loopback. O certificado deve cobrir o endereço utilizado.
6. Re-renderize as rotas, valide `docker compose config --quiet` e suba. De outro host seu, confirme que 80 redireciona, 443 exige autenticação e 5678/5432 não conectam, em IPv4 e, quando atribuído, IPv6. Na implantação atual, SSH permanece público somente por chave; limitar ao CIDR pessoal do administrador exige conhecer seu IP estável, sem usar o IP temporário do agente.

Portas Docker usam encaminhamento; uma regra UFW para INPUT não faz desaparecer uma publicação indevida de container. Confirme `docker compose ps`, `docker inspect ...HostConfig.PortBindings` e um teste externo. Não publique a porta interna de n8n nem a do banco.

## Estado 03 — VPN e webhook opcional

Instale WireGuard na VM e no cliente próprios. Gere as chaves em cada máquina, nunca no repositório. Use `wg0.conf.example` preenchido em `/etc/wireguard/wg0.conf`, com permissão 0600. O servidor usa `10.77.0.1/24`; o cliente, `10.77.0.2/32`. Cada peer autoriza apenas o IP daquele cliente. Ative `wg-quick@wg0` e confirme o handshake com `wg show`.

Depois de confirmar que SSH via túnel funciona, gere o plano `SSH_PORT=22 bash host/firewall.sh vpn`, remova regras anteriores que liberavam SSH público e confirme as regras efetivas. Opcionalmente adicione `ListenAddress 10.77.0.1` ao sshd: isso exige wg0 presente antes de iniciar o sshd. Regra de firewall por interface e teste externo continuam necessários. Sem roteamento/NAT, essa VPN é apenas de administração do servidor.

Mude o bind do painel para `ADMIN_BIND=10.77.0.1`, `TLS_PORT=443`. O DNS usado pelo administrador deve resolver o hostname do painel para `10.77.0.1`, e o certificado precisa cobrir esse hostname. Gere certificado válido pela CA privada do laboratório ou DNS-01 em um domínio **de teste** seu. Não copie a chave/certificado de produção.

Se existir webhook público, configure `HOOK_BIND=<IP_DA_INTERFACE_DA_VM>` e `HOOK_PORT=443`; nunca use `0.0.0.0:443`, pois isso também ocupa o IP wg0 usado pelo painel. Na OCI com NAT, o bind usa o IP privado atribuído à interface; o IP público externo não existe como interface local. A URL de webhook aponta para o endereço público, com certificado que o cubra. Para hostnames distintos de editor e webhook, adapte a regra Host do router `synthetic-hook` em `.local/dynamic/routes.yml`; essa configuração não deve ampliar os caminhos autorizados.

A rota pública aceita somente o caminho e método da fixture, e o n8n valida o token. `/`, `/rest/*`, `/api/*`, `/webhook-test/*`, outros caminhos e GET não devem alcançar o editor pela entrada pública. Não copie um `PathPrefix(/)` para o hostname público. Se não precisar de webhook público, feche essa publicação e a regra pública 443; resta apenas UDP 51820 para estabelecer o túnel.

Confira de um cliente fora da VPN e de outro dentro dela. Fora: SSH/painel não conectam; somente o webhook permitido responde, exigindo autenticação. Dentro: painel HTTPS e SSH por chave funcionam. Registre portas, resultados e logs sem credenciais. **WireGuard não foi implantado:** este estado é o diagrama e o roteiro de referência solicitados no segundo card.
