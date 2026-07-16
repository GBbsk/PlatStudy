import os

with open('/home/bsk/plat-estudos/PlatStudy/aulas-node/exercicio-5.md', 'r') as f:
    content = f.read()

# 1. Endpoints
ep_target = """POST /api/v1/auth/login
```
Autentica um usuário existente. Retorna token JWT. Mensagem de erro genérica em qualquer falha (não revele se o email existe)."""

ep_repl = """POST /api/v1/auth/login
```
Autentica um usuário existente. Retorna token JWT. Mensagem de erro genérica em qualquer falha (não revele se o email existe).

```
POST /api/v1/auth/refresh
```
Requer: cookie httpOnly com refresh token válido
Retorna: novo accessToken no body + novo refresh token no cookie (rotação)
Retorna 401 se: cookie ausente, token inválido, token revogado

```
POST /api/v1/auth/logout
```
Revoga o refresh token no banco e limpa o cookie
Retorna 200 sempre (não vaza informação sobre se o token existia)

```
POST /api/v1/auth/logout-todos
```
Requer autenticação (access token válido)
Revoga TODOS os refresh tokens do usuário (útil para "sair em todos os dispositivos")"""

content = content.replace(ep_target, ep_repl)

# 2. Requisitos de Segurança
sec_target = "- JWT com expiração de 2 horas\n- Chave JWT carregada de variável de ambiente (`JWT_SECRET`) com mínimo de 32 caracteres — valide o tamanho na inicialização"
sec_repl = """- Access token com expiração de 15 minutos
- Refresh token com expiração de 7 dias, armazenado em httpOnly cookie
- Duas chaves JWT separadas: JWT_ACCESS_SECRET e JWT_REFRESH_SECRET (valide tamanho de ambas na inicialização)
- Rota POST /auth/refresh que renova o access token via cookie
- Rota POST /auth/logout que revoga o refresh token e limpa o cookie
- Rotação de refresh token: cada uso invalida o token anterior e emite um novo
- Refresh tokens armazenados no banco como hash (SHA-256), nunca o token em si"""
content = content.replace(sec_target, sec_repl)

# 3. Estrutura do Banco
db_target = """CREATE TABLE usuarios (
  id        TEXT PRIMARY KEY,
  nome      TEXT NOT NULL,
  email     TEXT NOT NULL UNIQUE,
  senha_hash TEXT NOT NULL,
  criado_em TEXT NOT NULL
);
```"""

db_repl = """CREATE TABLE usuarios (
  id        TEXT PRIMARY KEY,
  nome      TEXT NOT NULL,
  email     TEXT NOT NULL UNIQUE,
  senha_hash TEXT NOT NULL,
  criado_em TEXT NOT NULL
);
```

**Tabela `refresh_tokens`:**
```sql
CREATE TABLE refresh_tokens (
  id         TEXT/UUID PRIMARY KEY,
  usuario_id TEXT/UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expira_em  TEXT/TIMESTAMPTZ NOT NULL,
  criado_em  TEXT/TIMESTAMPTZ NOT NULL
);
```"""
content = content.replace(db_target, db_repl)

# 4. .env.example
env_target = """# Gere com: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
JWT_SECRET="""
env_repl = """# Gere com: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
JWT_ACCESS_SECRET=
JWT_REFRESH_SECRET="""
content = content.replace(env_target, env_repl)

# 5. Bonus
bonus_target = """1. **Refresh token:** JWT de acesso expira em 2 horas. Implemente um endpoint `POST /auth/refresh` que recebe um refresh token (JWT separado com expiração de 7 dias) e retorna um novo access token sem precisar de senha. O refresh token deve ser armazenado no banco e invalidado no logout.

2. **Blacklist de tokens:** Quando o usuário troca a senha, tokens JWT antigos ainda são válidos até expirarem. Implemente uma tabela `tokens_invalidados` no banco e verifique nela no middleware de autenticação. Um token invalidado deve retornar `401` mesmo que ainda não tenha expirado."""

bonus_repl = """1. **Blacklist de tokens:** Quando o usuário troca a senha, tokens JWT antigos ainda são válidos até expirarem. Implemente uma tabela `tokens_invalidados` no banco e verifique nela no middleware de autenticação. Um token invalidado deve retornar `401` mesmo que ainda não tenha expirado."""
content = content.replace(bonus_target, bonus_repl)

with open('/home/bsk/plat-estudos/PlatStudy/aulas-node/exercicio-5.md', 'w') as f:
    f.write(content)

print("Patched exercicio-5.md")
