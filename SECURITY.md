# Política de segurança

Escopo: o laboratório deste repositório, executado em máquina ou VPS própria de teste. Nenhum segredo real é versionado; `.env` e `.local/` ficam fora do Git por design.

Para reportar uma vulnerabilidade, use o GitHub Security Advisories deste repositório ("Report a vulnerability"), que é privado por padrão. Não abra issue pública com segredos, credenciais, endereços reais ou logs brutos.

O certificado emitido por `scripts/lab.py init` é de teste e não representa confiança de produção. O estado de administração por VPN (WireGuard) é referência documentada e não constitui uma implantação de túnel.
