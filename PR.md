# Laboratório n8n com Traefik, autenticação em camadas e auditoria reproduzível

Um n8n com a porta 5678 publicada permite contornar o proxy e alcançar diretamente editor, REST e webhooks. Esta implementação publica apenas o Traefik, protege o painel com HTTPS/BasicAuth e login nativo, e restringe uma entrada independente de webhook ao método e caminho autorizados. O webhook valida seu token antes de executar o workflow.

## Decisões

- Adotar o file provider do Traefik já usado nos projetos de Marcos permite revisar rotas/middlewares e elimina a necessidade de dar o socket Docker ao proxy do laboratório.
- A autenticação básica está no Traefik: o n8n removeu suporte a `N8N_BASIC_AUTH_*` desde 1.0. O proprietário é provisionado com variáveis oficiais e hash bcrypt, sem cadastro público inicial nem segredo fixo compartilhado no repositório.
- Separar rede do proxy e rede interna PostgreSQL impede que Traefik chegue diretamente ao banco; não publicar 5678/5432 evita contorno via DNAT Docker. UFW sozinho não resolve publicação de containers.
- Bloquear nós de execução/arquivo e community packages reduz capacidades além do mínimo desta demonstração. Os nós de risco também foram removidos da versão corrigida do workflow: configurar `NODES_EXCLUDE` não limpa automaticamente workflows armazenados.
- Usar role PostgreSQL limitada, segredos aleatórios privados, digests fixos e logs com rotação torna o laboratório reproduzível e reduz privilégios/armazenamento de dados sensíveis. Fixar digest exige atualizar explicitamente quando houver correções.
- Não salvar payloads de execução reduz exposição de tokens. Como consequência, o audit mantém um aviso de credencial sem uso recente no histórico; o teste HTTP comprova o uso e esse aviso não foi ocultado.

## Validação

Execução real no Docker Desktop Linux local e na VPS própria OCI Ubuntu 26.04, com n8n 2.42.6, Traefik 3.7.12 e PostgreSQL 17.11. A VPS usa Docker Engine 29.9.0/Compose 5.6.0. Auditorias locais: `evidence/audit-before.json` e `audit-after.json`; auditorias na VPS: `audit-before-vps.json` e `audit-after-vps.json`, acompanhadas dos logs brutos.

Antes: um webhook sem autenticação, um nó Execute Command e um nó de arquivo. Depois: esses três achados ausentes; API por chave, community packages, templates e telemetria desabilitados. O audit ainda informa configurações e o aviso residual de histórico. As verificações HTTP/runtime cobrem autenticação do painel, login/cookies nativos, webhook com e sem token, bloqueio do editor/REST na entrada de webhook, role limitada e ausência de publicações de n8n/banco.

## Limites da entrega

SSH/UFW foram aplicados e validados na VPS: senha/root desabilitados, nova conexão por chave confirmada, TCP 22/80/443 permitidos, RPC desativado e proteções OCI preservadas de forma persistente. Foram executados 13 controles de host e 16 testes internos HTTP/runtime, registrados em `verification-host.json` e `verification-vps.json`. A importação via stdin mantém as fixtures privadas sem depender de igualdade de UID entre host/container. O certificado default do Traefik atende também clientes por IP sem SNI.

Depois da liberação de 80/443 por Marcos na OCI, os 11 testes externos em `verification-external.json` passaram: TLS validado com a CA de laboratório, redirecionamento HTTP, autenticação em camadas e portas diretas de n8n/banco fechadas. Não foi usada opção de ignorar a verificação TLS.

Os certificados são de teste, não confiáveis automaticamente no navegador. A VPS não tem IPv6 global; a política IPv6 foi inspecionada, sem teste externo IPv6. WireGuard é o terceiro estado do diagrama e um template, sem túnel implantado. Não há promessa de proteção integral contra SSRF, replay de provedores externos ou usuários de workflow maliciosos.

Este arquivo é o texto de um PR pronto para revisão. Nenhum PR foi aberto ou enviado, conforme a instrução de entregar localmente.
