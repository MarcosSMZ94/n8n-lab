# Entrega para avaliação — 11/10/2026

Foram identificados dois cards pendentes atribuídos a Marcos na lista Fazer. Os outros dois cards atribuídos já estavam Aprovados. Nenhum card foi alterado, movido, comentado ou anexado; nenhum PR foi enviado.

| Card | Entrega preparada | Pendência para concluir o fluxo do card |
|---|---|---|
| [VPS n8n endurecido](https://trello.com/c/qoDdZAAo) | Repositório local, Compose, `.env.example`, README/PR, implantação na VPS de teste, SSH/UFW verificados e auditorias reais antes/depois | Publicação do repositório/PR depende da avaliação |
| [Diagrama dos três estados](https://trello.com/c/hBCoj99o) | PNG exportado, fonte SVG editável e gerador Python; portas, firewall, Traefik, n8n, banco e WireGuard | Anexar ao card depois da avaliação, se desejado |

## Abrir primeiro

- `README.md`: instruções e comparação das auditorias.
- `diagrams/n8n-three-states.png`: imagem pronta.
- `diagrams/n8n-three-states.svg`: fonte vetorial editável (Inkscape/editor SVG).
- `PR.md`: decisões técnicas e validação para um futuro PR.
- `evidence/verification.json`: resultados reais dos testes HTTP/runtime.
- `evidence/verification-vps.json` e `verification-host.json`: 16 testes internos e 13 controles de host na VPS.
- `evidence/verification-external.json`: teste externo com o estado real da conectividade.
- `evidence/audit-before-vps.json` e `audit-after-vps.json`: auditorias reais executadas na VPS, com logs correspondentes.
- `host/README.md`: configurações SSH/UFW/WireGuard e limites do teste.

O endereço do stack local é `https://localhost:18443/`; para reativá-lo, o Docker Desktop precisa estar aberto. Suas credenciais ficam em `.local/access.json`. A VPS foi implantada em `/opt/ares/n8n-lab`, com credenciais próprias; a cópia privada para avaliação fica em `.local/vps/access.json`, e as instruções pessoais em `.local/vps/ACESSO.md`. Esses arquivos não entram no Git/ZIP. Quem extrair o ZIP deve gerar novas credenciais com `python scripts/lab.py init` ou o perfil `init --vps --host`.

A baseline vulnerável usa CLI sem rede e sem portas. No depois, os achados de webhook desprotegido, Execute Command e acesso a arquivos desaparecem. Permanecem a seção informativa de configurações e um aviso de credencial sem histórico de uso recente; não há alegação de auditoria sem achados.

Foi testado Docker Desktop Linux no computador local e a VPS OCI Ubuntu 26.04 fornecida por Marcos. SSH somente por chave, root/senha desabilitados, UFW 22/80/443, regras OCI preservadas, RPC inativo e swap ativo passaram na verificação de host. Uma conexão SSH nova foi aceita e a autenticação por senha foi rejeitada. n8n/PostgreSQL não publicam portas. A entrada separada de webhook continua em loopback.

**Validação concluída:** 13 controles de host, 16 testes internos e 11 testes externos passaram. Marcos liberou TCP 80/443 nas regras OCI; o teste externo confirmou HTTP→HTTPS, certificado correto, BasicAuth, login nativo obrigatório e ausência de conexão em 111/5678/5432/19443. Não houve teste IPv6 externo porque o host não tem IPv6 global.

Os certificados são de teste, com validação explícita pelos scripts; não são confiáveis automaticamente no navegador. O cenário WireGuard está documentado no PNG/SVG e no template, sem túnel implantado. O aviso residual do audit sobre histórico de credencial permanece explicado no README.

O repositório Git local tem base `main` e branch `feat/n8n-hardening`, sem remoto configurado. O diretório `../entregas/` contém o ZIP e um patch Git da implementação para revisão.

## Reconstruir a imagem

`python scripts/network_diagram.py` regenera o SVG sem dependências externas. Para exportar PNG com Inkscape instalado:

```bash
inkscape diagrams/n8n-three-states.svg --export-type=png --export-filename=diagrams/n8n-three-states.png
```

O PNG entregue foi renderizado com Sharp do runtime local do Codex e inspecionado visualmente. O ZIP inclui o PNG e o SVG prontos, sem precisar instalar ferramentas de desenho.
