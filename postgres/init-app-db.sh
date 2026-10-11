#!/bin/sh
# Executado somente na inicialização de um volume PostgreSQL novo.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$N8N_APP_PASSWORD" <<'SQL'
CREATE ROLE n8n LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE n8n OWNER n8n;
SQL
