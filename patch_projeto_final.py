import os
import re

with open('/home/bsk/plat-estudos/PlatStudy/aulas-node/projeto-final.md', 'r') as f:
    content = f.read()

# 1. Schema
schema_target = """CREATE TABLE usuarios (
  id          TEXT PRIMARY KEY,
  nome        TEXT NOT NULL,
  username    TEXT NOT NULL UNIQUE,
  email       TEXT NOT NULL UNIQUE,
  bio         TEXT,
  senha_hash  TEXT NOT NULL,
  criado_em   TEXT NOT NULL
);

CREATE TABLE posts (
  id           TEXT PRIMARY KEY,
  titulo       TEXT NOT NULL,
  url          TEXT NOT NULL,
  descricao    TEXT,
  usuario_id   TEXT NOT NULL,
  criado_em    TEXT NOT NULL,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE curtidas (
  id         TEXT PRIMARY KEY,
  usuario_id TEXT NOT NULL,
  post_id    TEXT NOT NULL,
  criado_em  TEXT NOT NULL,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
  FOREIGN KEY (post_id)    REFERENCES posts(id)    ON DELETE CASCADE,
  UNIQUE (usuario_id, post_id)   -- um usuário só pode curtir um post uma vez
);

CREATE TABLE comentarios (
  id         TEXT PRIMARY KEY,
  texto      TEXT NOT NULL,
  usuario_id TEXT NOT NULL,
  post_id    TEXT NOT NULL,
  criado_em  TEXT NOT NULL,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
  FOREIGN KEY (post_id)    REFERENCES posts(id)    ON DELETE CASCADE
);

CREATE TABLE follows (
  id          TEXT PRIMARY KEY,
  seguidor_id TEXT NOT NULL,
  seguido_id  TEXT NOT NULL,
  criado_em   TEXT NOT NULL,
  FOREIGN KEY (seguidor_id) REFERENCES usuarios(id) ON DELETE CASCADE,
  FOREIGN KEY (seguido_id)  REFERENCES usuarios(id) ON DELETE CASCADE,
  UNIQUE (seguidor_id, seguido_id)   -- não pode seguir a mesma pessoa duas vezes
);"""

schema_repl = """CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE usuarios (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome        TEXT NOT NULL,
  username    TEXT NOT NULL UNIQUE,
  email       TEXT NOT NULL UNIQUE,
  bio         TEXT,
  senha_hash  TEXT NOT NULL,
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE posts (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  titulo       TEXT NOT NULL,
  url          TEXT NOT NULL,
  descricao    TEXT,
  usuario_id   UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  criado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE curtidas (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  post_id    UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  criado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (usuario_id, post_id)
);

CREATE TABLE comentarios (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  texto      TEXT NOT NULL,
  usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  post_id    UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  criado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE follows (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  seguidor_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  seguido_id  UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (seguidor_id, seguido_id)
);

CREATE TABLE refresh_tokens (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expira_em  TIMESTAMPTZ NOT NULL,
  criado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);"""
content = content.replace(schema_target, schema_repl)

# 2. Requisitos Técnicos
# Database
db_target = """### Banco de Dados
- SQLite com `better-sqlite3`
- WAL mode e foreign keys ativos
- Statements preparados fora das funções
- Migrations executadas no startup
- Seed script que popula dados iniciais se o banco estiver vazio
- Nenhum valor de usuário interpolado diretamente em SQL"""

db_repl = """### Banco de Dados
- PostgreSQL via `pg` driver (veja `correcao-postgresql.md` para setup)
- Pool de conexões em produção
- Schema usando UUIDs e TIMESTAMPTZ
- Migrations executadas automaticamente no startup
- Seed script como comando separado: `npm run seed` (só executado manualmente uma vez)
- Valores sanitizados / passados por parâmetros ($1, $2, etc)"""
content = content.replace(db_target, db_repl)

# Security Requirements
sec_target = """### Segurança
- bcrypt com cost factor 10 para senhas
- JWT com expiração de 2 horas
- `JWT_SECRET` com mínimo 32 caracteres validado no startup"""

sec_repl = """### Segurança
- bcrypt com cost factor 10 para senhas
- Access token: 15 minutos, retornado no body
- Refresh token: 7 dias, retornado como httpOnly cookie, com rotação e tabela `refresh_tokens`
- Chaves separadas `JWT_ACCESS_SECRET` e `JWT_REFRESH_SECRET`, mín 32 caracteres validado no startup
- Rota `POST /auth/refresh` implementada"""
content = content.replace(sec_target, sec_repl)

# Deploy
dep_target = """### Deploy
- Aplicação rodando em URL pública (Railway ou Render)
- `PORT` de `process.env.PORT`
- Todas as variáveis de ambiente configuradas na plataforma
- Health check respondendo `200` na URL pública"""

dep_repl = """### Deploy
- Aplicação rodando em URL pública (Railway ou Render)
- PostgreSQL add-on no Railway
- DATABASE_URL=${Postgres.DATABASE_URL}
- `PORT` de `process.env.PORT`
- Todas as variáveis de ambiente configuradas na plataforma
- Health check respondendo `200` na URL pública"""
content = content.replace(dep_target, dep_repl)

# NPM install instructions
npm_target = "npm install express better-sqlite3 bcrypt jsonwebtoken dotenv helmet cors express-rate-limit"
npm_repl = "npm install express pg bcrypt jsonwebtoken cookie-parser dotenv helmet cors express-rate-limit"
content = content.replace(npm_target, npm_repl)

with open('/home/bsk/plat-estudos/PlatStudy/aulas-node/projeto-final.md', 'w') as f:
    f.write(content)

print("Patched projeto-final.md")
