# Laboratório n8n com Traefik, autenticação em camadas e auditoria reproduzível

Um n8n com a porta 5678 publicada permite contornar o proxy e alcançar diretamente editor, REST e webhooks. Esta implementação publica apenas o Traefik, protege o painel com HTTPS/BasicAuth e login nativo, e restringe uma entrada independente de webhook ao método e caminho autorizados. O webhook valida seu token antes de executar o workflow.

## Decisões

- Adotar o file provider do Traefik já usado nos projetos de Marcos permite revisar rotas/middlewares e elimina a necessidade de dar o socket Docker ao proxy do laboratório.
- A autenticação básica está no Traefik: o n8n removeu suporte a `N8N_BASIC_AUTH_*` desde 1.0. O proprietário é provisionado com variáveis oficiais e hash bcrypt, sem cadastro público inicial nem segredo fixo compartilhado no repositório.
- Separar rede do proxy e rede interna PostgreSQL impede que Traefik chegue diretamente ao banco; não publicar 5678/5432 evita contorno via DNAT Docker. UFW sozinho não resolve publicação de containers.
- Bloquear nós de execução/arquivo e community packages reduz capacidades além do mínimo desta demonstração. Os nós de risco também foram removidos da versão corrigida do workflow: configurar `NODES_EXCLUDE` não limpa automaticamente workflows armazenados.
- Usar role PostgreSQL limitada, segredos aleatórios privados, digests fixos e logs com rotação torna o laboratório reproduzível e reduz privilégios/armazenamento de dados sensíveis. Fixar digest exige atualizar explicitamente quando houver correções.
- Não salvar payloads de execução reduz exposição de tokens. Como consequência, o audit mantém um aviso de credencial sem uso recente no histórico; o teste HTTP comprova o uso e esse aviso não foi ocultado.

## Aderência à documentação oficial

Os controles partem das páginas [Security](https://docs.n8n.io/deploy/host-n8n/configure-n8n/security.md) e [Run security audits](https://docs.n8n.io/deploy/host-n8n/configure-n8n/security/run-security-audits.md) do n8n. O README traz a tabela de rastreabilidade: ação recomendada → local de implementação → status, incluindo o que a documentação oferece e não foi adotado (SSO por dependência de licença, SSRF pendente, rotação de chave parcial).

## Declaração de uso de IA

A implementação deste laboratório foi desenvolvida com assistência de IA (OpenAI ChatGPT/Codex para o material inicial; Claude Code da Z.ai para organização, CI, implantação do estado VPN e revisão). A IA redigiu rascunhos de configuração, scripts e documentação, sempre sob direção e revisão humana: a sequência `before → up → verify → after` foi executada de fato na máquina local e na VPS própria, os testes externos rodaram a partir de outro host, e as evidências em `evidence/` refletem execuções reais — não saídas redigidas. Nenhum segredo passou por prompts ou repositório; credenciais são geradas localmente por `scripts/lab.py init`.

## Validação

Execução real no Docker Desktop Linux local e na VPS própria OCI Ubuntu 26.04, com n8n 2.42.6, Traefik 3.7.12 e PostgreSQL 17.11. A VPS usa Docker Engine 29.9.0/Compose 5.6.0. Auditorias locais: `evidence/audit-before.json` e `audit-after.json`; auditorias na VPS: `audit-before-vps.json` e `audit-after-vps.json`, acompanhadas dos logs brutos.

Antes: um webhook sem autenticação, um nó Execute Command e um nó de arquivo. Depois: esses três achados ausentes; API por chave, community packages, templates e telemetria desabilitados. O audit ainda informa configurações e o aviso residual de histórico. As verificações HTTP/runtime cobrem autenticação do painel, login/cookies nativos, webhook com e sem token, bloqueio do editor/REST na entrada de webhook, role limitada e ausência de publicações de n8n/banco.

## Limites da entrega

SSH/UFW foram aplicados e validados na VPS: senha/root desabilitados, nova conexão por chave confirmada, TCP 22/80/443 permitidos, RPC desativado e proteções OCI preservadas de forma persistente. Foram executados 13 controles de host e 16 testes internos HTTP/runtime, registrados em `verification-host.json` e `verification-vps.json`. A importação via stdin mantém as fixtures privadas sem depender de igualdade de UID entre host/container. O certificado default do Traefik atende também clientes por IP sem SNI.

O estado 03 foi implantado na mesma VPS: túnel WireGuard em 51820/udp, painel bindado em `10.77.0.1:443` (TLS 1.2, BasicAuth), SSH restrito à interface `wg0` e portas públicas 22/80/443 removidas do UFW, preservando as regras OCI. Do exterior, 22/80/443 não conectam; pelo túnel, o painel responde 401 sem BasicAuth e 200 com, com certificado validado — [verification-vpn.json](evidence/verification-vpn.json). Sem webhook público, restou apenas 51820/udp de superfície, como no terceiro estado do diagrama.

Depois da liberação de 80/443 por Marcos na OCI, os 11 testes externos em `verification-external.json` passaram: TLS validado com a CA de laboratório, redirecionamento HTTP, autenticação em camadas e portas diretas de n8n/banco fechadas. Não foi usada opção de ignorar a verificação TLS.

Os certificados são de teste, não confiáveis automaticamente no navegador. A VPS não tem IPv6 global; a política IPv6 foi inspecionada, sem teste externo IPv6. WireGuard é o terceiro estado do diagrama e um template, sem túnel implantado. Não há promessa de proteção integral contra SSRF, replay de provedores externos ou usuários de workflow maliciosos.
