# Reutilização do padrão Traefik central em laboratório

Os repositórios de Marcos usam uma rede externa declarada no Compose e um file provider com routers, serviços e middlewares. O stack local reproduz esse padrão com um Traefik próprio. Não modifica o Traefik existente.

Para integração futura **somente numa réplica de laboratório**:

1. Use um único Traefik dono de 80/443. Retire o serviço Traefik deste Compose da réplica e conecte `n8n` a uma rede externa `ares_lab_proxy`, declarada como `external: true`. Declare um alias exclusivo como `ares-lab-n8n`; não faça conexão manual que se perde no recreate. PostgreSQL permanece somente em `database`.
2. Adicione ao file provider dessa réplica um serviço apontando a `http://ares-lab-n8n:5678` e um router com o Host de laboratório, `websecure`, `tls: {}` e os middlewares de autenticação/headers. Quando o Traefik central de teste já tem wildcard no store, o router consome esse certificado sem emitir outro. Não reutilize tokens/domínios da VPS real.
3. Monte `proxy.users` no **Traefik central da réplica**, no caminho referido pelo middleware BasicAuth. Montar esse arquivo só no n8n não funciona. Não use labels com senha em claro. O laboratório original dispensa o socket Docker porque usa apenas o file provider.
4. Revise `N8N_EDITOR_BASE_URL`, `N8N_WEBHOOK_URL`, `N8N_HOST` e `N8N_PROXY_HOPS`. Um Traefik diretamente na borda é um salto; adicionar outro proxy exige revisar a cadeia de confiança. Não ative `forwardedHeaders.insecure=true` indiscriminadamente.
5. Para VPN, publique o entrypoint administrativo somente no IP wg0 e tenha entrypoint/bind independente para o webhook público. O router público deve aceitar apenas a rota necessária. Não basta pôr BasicAuth no painel se uma segunda rota pública encaminhar todo o n8n.
6. Valide com resolução local do hostname, usando certificado confiável de teste, e confira `RouterName` nos access logs. Faça todos os testes HTTP do laboratório adaptados às URLs da réplica, sem usar `verify` com binds públicos: essa automação recusa binds fora de loopback deliberadamente.

Não foi aplicado nenhum desses passos à VPS ou aos repositórios de referência. Os diretórios clonados permanecem intactos.
