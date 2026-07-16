import os
import re

# Patch aula-7.2.md
with open('/home/bsk/plat-estudos/PlatStudy/aulas-node/aula-7.2.md', 'r') as f:
    aula72 = f.read()

# Replace config/env.js
env_js_target = """const variaveis = {
  port:        Number(process.env.PORT) || 3000,
  nodeEnv:     process.env.NODE_ENV || 'development',
  jwtSecret:   process.env.JWT_SECRET,
  databaseUrl: process.env.DATABASE_URL || './dados/banco.db',
}

// Valida variáveis obrigatórias
const obrigatorias = ['JWT_SECRET']
const faltando = obrigatorias.filter(v => !process.env[v])

if (faltando.length > 0) {
  console.error('❌ Variáveis de ambiente obrigatórias não configuradas:', faltando.join(', '))
  process.exit(1)
}

if (variaveis.jwtSecret && variaveis.jwtSecret.length < 32) {
  console.error('❌ JWT_SECRET deve ter pelo menos 32 caracteres')
  process.exit(1)
}"""

env_js_repl = """const variaveis = {
  port:             Number(process.env.PORT) || 3000,
  nodeEnv:          process.env.NODE_ENV || 'development',
  jwtAccessSecret:  process.env.JWT_ACCESS_SECRET,
  jwtRefreshSecret: process.env.JWT_REFRESH_SECRET,
  databaseUrl:      process.env.DATABASE_URL,
}

// Valida variáveis obrigatórias
const obrigatorias = ['JWT_ACCESS_SECRET', 'JWT_REFRESH_SECRET', 'DATABASE_URL']
const faltando = obrigatorias.filter(v => !process.env[v])

if (faltando.length > 0) {
  console.error('❌ Variáveis de ambiente obrigatórias não configuradas:', faltando.join(', '))
  process.exit(1)
}

if (variaveis.jwtAccessSecret && variaveis.jwtAccessSecret.length < 32) {
  console.error('❌ JWT_ACCESS_SECRET deve ter pelo menos 32 caracteres')
  process.exit(1)
}"""

aula72 = aula72.replace(env_js_target, env_js_repl)

# Replace env vars in Railway
env_vars_target = """NODE_ENV=production
JWT_SECRET=<gere com: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))">
DATABASE_URL=./dados/banco.db
PORT=3000"""

env_vars_repl = """NODE_ENV=production
JWT_ACCESS_SECRET=<gere com: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))">
JWT_REFRESH_SECRET=<gere outro valor diferente>
DATABASE_URL=${Postgres.DATABASE_URL}
PORT=3000"""

aula72 = aula72.replace(env_vars_target, env_vars_repl)

with open('/home/bsk/plat-estudos/PlatStudy/aulas-node/correcao-postgresql.md', 'r') as f:
    pg_content = f.read()

# Extract the sections needed
start_marker = "## O problema com SQLite em produção"
end_marker = "## Inicialização atualizada"
idx_start = pg_content.find(start_marker)
idx_end = pg_content.find(end_marker)
pg_sections = pg_content[idx_start:idx_end].strip()

# Replace Passo 4
passo4_target = """### Passo 4 — Configurar o banco de dados

SQLite em arquivo funciona no Railway, mas tem uma limitação: os dados são perdidos a cada novo deploy (o filesystem é efêmero). Para desenvolvimento/aprendizado isso é aceitável. Para produção real, você usaria PostgreSQL.

Para ter o banco populado após o deploy, adicione o seed no script de start:

```json
{
  "scripts": {
    "start": "node scripts/seed.js && node src/index.js"
  }
}
```

Ou adicione uma rota de setup protegida por uma variável de ambiente:

```js
// Rota temporária para seed em produção — remova depois
app.post('/setup', (req, res) => {
  if (req.headers['x-setup-key'] !== process.env.SETUP_KEY) {
    return res.sendStatus(403)
  }
  require('../scripts/seed')
  res.json({ mensagem: 'Seed executado' })
})
```"""

passo4_repl = "### Passo 4 — Banco de dados em produção — PostgreSQL\n\n" + pg_sections

aula72 = aula72.replace(passo4_target, passo4_repl)

# Replace the manual logger with pino logger
logger_target = """// src/middlewares/logger.middleware.js
const fs = require('fs')
const path = require('path')

function logger(req, res, next) {
  const inicio = Date.now()

  res.on('finish', () => {
    const duracao = Date.now() - inicio
    const nivel   = res.statusCode >= 500 ? 'ERROR'
                  : res.statusCode >= 400 ? 'WARN'
                  : 'INFO'

    const linha = JSON.stringify({
      timestamp: new Date().toISOString(),
      nivel,
      method:     req.method,
      path:       req.path,
      status:     res.statusCode,
      duracao_ms: duracao,
      ip:         req.ip,
      user_agent: req.headers['user-agent']
    })

    // Em produção: só console (Railway/Render capturam o stdout)
    // Em desenvolvimento: também salva em arquivo
    console.log(linha)

    if (process.env.NODE_ENV === 'development') {
      const arquivo = path.join(__dirname, '../../logs/requests.log')
      fs.appendFile(arquivo, linha + '\\n', () => {})
    }
  })

  next()
}

module.exports = logger"""

with open('/home/bsk/plat-estudos/PlatStudy/aulas-node/correcao-seguranca-logging.md', 'r') as f:
    sec_content = f.read()

# find pino http
pino_idx = sec_content.find("// src/middlewares/logger.middleware.js — substitui o logger manual anterior")
pino_end = sec_content.find("module.exports = httpLogger\n```", pino_idx) + len("module.exports = httpLogger")
pino_code = sec_content[pino_idx:pino_end]

aula72 = aula72.replace(logger_target, pino_code)

with open('/home/bsk/plat-estudos/PlatStudy/aulas-node/aula-7.2.md', 'w') as f:
    f.write(aula72)

print("Patched aula-7.2.md")
