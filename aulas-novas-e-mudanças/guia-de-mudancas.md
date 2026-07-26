# Guia de Mudanças nas Aulas

Este documento indica exatamente o que precisa ser alterado em cada arquivo de aula existente. Para cada aula, há uma lista de seções a remover, substituir ou adicionar.

---

## aula-4.2.md — SQLite com better-sqlite3 → async/await

**Status:** SUBSTITUIÇÃO COMPLETA

O arquivo inteiro deve ser substituído pelo conteúdo de `correcao-postgresql.md` para a seção de produção, mas como a aula 4.2 cobre o aprendizado local, a correção já foi feita no arquivo `aula-4.2.md` que usa `sqlite` + `sqlite3` async. Use esse arquivo corrigido.

**Mudanças específicas na aula:**

```
REMOVER:
- Toda menção a better-sqlite3
- npm install better-sqlite3
- A API síncrona: db.prepare().get(), db.prepare().all(), db.prepare().run()
- db.pragma()
- db.transaction()

SUBSTITUIR POR (já está no arquivo corrigido aula-4.2.md):
- npm install sqlite3 sqlite
- const { open } = require('sqlite') + const sqlite3 = require('sqlite3')
- API assíncrona: db.get(), db.all(), db.run(), db.exec()
- await db.exec('PRAGMA foreign_keys = ON')
- Transações via client.query('BEGIN') / COMMIT / ROLLBACK
```

---

## aula-5.1.md — JWT: substituição completa da seção de implementação

**Status:** REESCRITA PARCIAL — estrutura da aula mantida, implementação substituída

**Seção "O Problema" — MANTER como está**

**Seção "Conceito Central" — SUBSTITUIR pelo texto abaixo:**

```
REMOVER o texto atual sobre JWT ter três partes (header/payload/signature)
— ele está correto mas incompleto.

ADICIONAR após a explicação do JWT:

---

## Onde o cliente guarda o token — a decisão mais importante

O curso anterior deixava isso implícito. Não deveria. Esta é uma decisão
de segurança, não de conveniência.

**localStorage** — acessível por qualquer JavaScript rodando na página.
Se houver uma vulnerabilidade XSS (script malicioso injetado), o atacante
lê o token com uma linha: `localStorage.getItem('token')`. É a causa mais
comum de tokens roubados em aplicações web.

**httpOnly cookie** — cookies com a flag `httpOnly` não são acessíveis
pelo JavaScript. Nem pelo seu código, nem pelo código malicioso. O
navegador os envia automaticamente nas requisições, mas nenhum
`document.cookie` os vê.

O padrão correto usa dois tokens com responsabilidades diferentes:

Access Token
  - Duração: 15 minutos
  - Retornado no body do login
  - Cliente guarda em MEMÓRIA (variável, estado do app) — nunca em localStorage
  - Enviado no header: Authorization: Bearer <token>
  - Se vazar: janela de ataque de 15 minutos

Refresh Token
  - Duração: 7 dias
  - Retornado como httpOnly cookie
  - Cliente não toca nele — o navegador gerencia automaticamente
  - Usado só para obter um novo access token quando ele expira
  - Se vazar: requer acesso físico ao dispositivo
---
```

**Seção "Instalação" — SUBSTITUIR:**

```
REMOVER:
npm install jsonwebtoken

SUBSTITUIR POR:
npm install jsonwebtoken cookie-parser
```

**Seção "Gerando e verificando tokens" — SUBSTITUIR completamente:**

```
REMOVER o arquivo src/utils/jwt.js atual (com SECRET único e expiresIn: '2h')

SUBSTITUIR pelo conteúdo de src/utils/jwt.js do arquivo correcao-auth-completa.md
que tem:
- ACCESS_SECRET e REFRESH_SECRET separados (variáveis de ambiente distintas)
- gerarAccessToken() com expiresIn: '15m'
- gerarRefreshToken() com expiresIn: '7d'
- verificarAccessToken() e verificarRefreshToken() separados
```

**Seção "A rota de login" — SUBSTITUIR completamente:**

```
REMOVER a rota de login atual inteira

SUBSTITUIR pelo conteúdo completo do arquivo correcao-auth-completa.md,
que inclui:
- src/config/cookies.js (novo arquivo)
- src/repositories/refresh-tokens.repository.js (novo arquivo)
- Rota POST /auth/register (com cookie httpOnly)
- Rota POST /auth/login (com cookie httpOnly)
- Rota POST /auth/refresh (NOVA — não existia antes)
- Rota POST /auth/logout (com clearCookie)
- Rota POST /auth/logout-todos (NOVA)
- Rota GET /auth/me (mantida)
```

**Seção "Fluxo completo de autenticação" (exemplos com curl) — SUBSTITUIR:**

```
REMOVER os exemplos de curl que não incluem refresh

SUBSTITUIR pelo fluxo de três etapas:
1. Login → recebe accessToken no body + cookie httpOnly automático
2. Usar accessToken no header Authorization: Bearer
3. Quando receber 401 com codigo: "TOKEN_EXPIRADO" → chamar POST /auth/refresh
   (o cookie vai automaticamente, sem código extra)
4. Recebe novo accessToken → continua
5. Logout → POST /auth/logout → cookie limpo pelo servidor
```

**Seção "Variáveis de ambiente" — SUBSTITUIR:**

```
REMOVER:
JWT_SECRET=chave-aqui

SUBSTITUIR POR:
JWT_ACCESS_SECRET=<gere com: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))">
JWT_REFRESH_SECRET=<gere outro valor DIFERENTE do access secret>
# Chaves diferentes: se uma vazar, a outra continua segura.
# Se usar a mesma chave, um refresh token poderia ser aceito como access token.
```

---

## aula-5.2.md — Senhas e Boas Práticas: três adições

**Status:** ADIÇÕES — não remove nada, só acrescenta seções

**ADICIONAR nova seção após "Integrando bcrypt no registro e login":**

```
Título da seção nova: "SELECT explícito — nunca traga senha_hash por acidente"

Inserir o conteúdo da seção "1. SELECT explícito" do arquivo
correcao-seguranca-logging.md integralmente, incluindo:

- Explicação do problema (SELECT * + destructuring é frágil)
- COLUNAS_PUBLICAS como constante
- Duas funções separadas: buscarPorId (sem hash) e buscarPorEmail (com hash, só para auth)
- Comentário explicando por que a separação existe
```

**ADICIONAR nova seção após a anterior:**

```
Título: "Sanitização de Input — proteção contra XSS armazenado"

Inserir o conteúdo da seção "2. Sanitização de Input" do arquivo
correcao-seguranca-logging.md, incluindo:

- Explicação do que é XSS armazenado e quando o backend deve ajudar
- npm install validator
- src/utils/sanitizar.js completo
- Exemplo de uso no service
- Nota sobre quando isso é mais ou menos relevante (API JSON vs renderização HTML)
```

**Seção "Rate limiting" existente — ADICIONAR aviso após o código atual:**

```
MANTER o código existente com express-rate-limit

ADICIONAR no final da seção, após o código:

---
⚠️ Limitação importante: o rate limiting acima guarda os contadores
em MEMÓRIA, dentro do processo Node. Em uma aplicação com múltiplas
instâncias (dois containers, dois dynos), cada instância tem seus
próprios contadores — um usuário pode fazer 100 requisições em cada
instância, contornando o limite completamente.

Para rate limiting distribuído que funciona com múltiplas instâncias,
você precisa de um store centralizado como Redis:

npm install ioredis rate-limit-redis

[inserir o código de correcao-seguranca-logging.md, seção
"3. Rate Limiting com Redis"]

Para desenvolvimento e projetos single-instance, o store em memória
funciona. Documente a limitação explicitamente no código com um comentário.
---
```

---

## aula-7.2.md (Node course) — Deploy: substituição da seção de banco de dados

**Status:** SUBSTITUIÇÃO PARCIAL

**Seção "O que acontece no deploy?" ou similar — MANTER**

**Seção sobre banco de dados em produção — SUBSTITUIR completamente:**

```
REMOVER:
- Toda a parte que sugere usar SQLite no Railway
- O script "start": "node scripts/seed.js && node src/index.js"
- Qualquer menção de "dados são perdidos a cada deploy" como algo aceitável

SUBSTITUIR POR (do arquivo correcao-postgresql.md):

Título: "Banco de dados em produção — PostgreSQL"

Conteúdo:
- Explicação de por que SQLite não funciona em ambientes de container
  (filesystem efêmero — dados perdidos a cada deploy)
- npm install pg
- src/database/connection.js com Pool (versão PostgreSQL)
- src/database/migrations.js (versão PostgreSQL com tipos reais)
- Diferenças de sintaxe SQLite → PostgreSQL (tabela completa)
- Setup no Railway: adicionar PostgreSQL add-on, variável DATABASE_URL
- O RETURNING do PostgreSQL eliminando o SELECT após INSERT
- COALESCE para updates parciais
```

**Seção de variáveis de ambiente no deploy — ATUALIZAR:**

```
SUBSTITUIR:
DATABASE_URL=sqlite:./dados/banco.db

POR:
DATABASE_URL=${Postgres.DATABASE_URL}
# Railway resolve automaticamente para a URL completa do PostgreSQL add-on
```

---

## aula-6.2.md (Node course) — Tratamento de Erros: adicionar logger com Pino

**Status:** ADIÇÃO — nova seção no final

**ADICIONAR nova seção "Logging estruturado com Pino" antes do Resumo:**

```
Inserir integralmente a seção "4. Logging estruturado com Pino"
do arquivo correcao-seguranca-logging.md, incluindo:

- Por que Pino (vs Winston, vs console.log manual)
- npm install pino pino-http + npm install -D pino-pretty
- src/config/logger.js completo com redact de campos sensíveis
- src/middlewares/logger.middleware.js substituindo o logger manual atual
- Exemplos de saída em desenvolvimento (pino-pretty) e produção (JSON puro)
- Atualização do error handler para usar logger.warn/logger.error
```

**Seção "Middleware de logging profissional" existente — SUBSTITUIR:**

```
REMOVER o logger manual atual (com res.on('finish') e console.log)

SUBSTITUIR pelo conteúdo do pino-http do arquivo correcao-seguranca-logging.md
```

---

## exercicio-5.md — Auth: atualizar requisitos

**Status:** ATUALIZAÇÃO DE REQUISITOS

**Seção "Requisitos de Segurança" — SUBSTITUIR:**

```
REMOVER:
- JWT com expiração de 2 horas (linha única)
- Qualquer menção de token em localStorage

SUBSTITUIR POR:
- Access token com expiração de 15 minutos
- Refresh token com expiração de 7 dias, armazenado em httpOnly cookie
- Duas chaves JWT separadas: JWT_ACCESS_SECRET e JWT_REFRESH_SECRET
- Rota POST /auth/refresh que renova o access token via cookie
- Rota POST /auth/logout que revoga o refresh token e limpa o cookie
- Rotação de refresh token: cada uso invalida o token anterior e emite um novo
- Refresh tokens armazenados no banco como hash (SHA-256), nunca o token em si
```

**Seção "Endpoints que você deve implementar" — ADICIONAR:**

```
ADICIONAR após POST /auth/login:

POST /auth/refresh
  Requer: cookie httpOnly com refresh token válido
  Retorna: novo accessToken no body + novo refresh token no cookie (rotação)
  Retorna 401 se: cookie ausente, token inválido, token revogado

POST /auth/logout
  Revoga o refresh token no banco e limpa o cookie
  Retorna 200 sempre (não vaza informação sobre se o token existia)

POST /auth/logout-todos
  Requer autenticação (access token válido)
  Revoga TODOS os refresh tokens do usuário (útil para "sair em todos os dispositivos")
```

**Seção "Estrutura do Banco de Dados" — ADICIONAR tabela:**

```
ADICIONAR após a tabela usuarios:

Tabela refresh_tokens:
CREATE TABLE refresh_tokens (
  id         TEXT/UUID PRIMARY KEY,
  usuario_id TEXT/UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expira_em  TEXT/TIMESTAMPTZ NOT NULL,
  criado_em  TEXT/TIMESTAMPTZ NOT NULL
);
```

---

## projeto-final.md (Linkr) — atualizar banco de dados e auth

**Status:** ATUALIZAÇÕES EM DOIS PONTOS

**Seção de banco de dados — SUBSTITUIR SQLite por PostgreSQL:**

```
REMOVER:
- Qualquer schema com TEXT para datas e UUIDs
- Referência a better-sqlite3 ou sqlite

SUBSTITUIR POR:
- Schema com UUID PRIMARY KEY DEFAULT gen_random_uuid()
- TIMESTAMPTZ para datas
- Referência ao arquivo correcao-postgresql.md para setup completo
```

**Seção de deploy — ATUALIZAR:**

```
REMOVER:
- Sugestão de seed no script "start"
- Menção de SQLite como banco de produção

SUBSTITUIR POR:
- PostgreSQL add-on no Railway
- DATABASE_URL=${Postgres.DATABASE_URL}
- Migrations executadas automaticamente no startup (sem seed no start)
- Seed como comando separado: npm run seed (só executado manualmente uma vez)
```

**Seção de auth — ADICIONAR requisitos:**

```
ADICIONAR na lista de requisitos técnicos:

- Access token: 15 minutos, retornado no body
- Refresh token: 7 dias, retornado como httpOnly cookie
- Rota POST /auth/refresh implementada
- Rotação de refresh token ativa
- Tabela refresh_tokens no banco
```

---

## Arquivos novos que devem ser CRIADOS (não existiam antes)

```
src/config/cookies.js           — configuração do cookie httpOnly (do correcao-auth-completa.md)
src/config/logger.js            — configuração do pino (do correcao-seguranca-logging.md)
src/config/redis.js             — configuração do ioredis (do correcao-seguranca-logging.md)
src/repositories/refresh-tokens.repository.js  — (do correcao-auth-completa.md)
src/utils/sanitizar.js          — (do correcao-seguranca-logging.md)
__tests__/setup.js              — (do modulo-testes.md)
__tests__/helpers.js            — (do modulo-testes.md)
__tests__/auth.test.js          — (do modulo-testes.md)
__tests__/posts.test.js         — (do modulo-testes.md)
__tests__/unit/posts.service.test.js  — (do modulo-testes.md)
jest.config.js                  — (do modulo-testes.md)
.env.test                       — (do modulo-testes.md)
.github/workflows/testes.yml    — (do modulo-testes.md)
```

---

## Pacotes novos que devem ser adicionados

```
PRODUÇÃO (npm install):
cookie-parser       — leitura de cookies httpOnly
pg                  — driver PostgreSQL
pino                — logging estruturado
pino-http           — middleware de logging HTTP
validator           — sanitização e validação de strings
ioredis             — cliente Redis (para rate limiting distribuído)
rate-limit-redis    — store Redis para express-rate-limit

DESENVOLVIMENTO (npm install -D):
pino-pretty         — formata logs pino para terminal em desenvolvimento
jest                — test runner
supertest           — testes HTTP de integração

REMOVER (não são mais necessários):
better-sqlite3      — substituído por sqlite + sqlite3
```

---

## aula-3.2.md — Middlewares: adicionar validação com Zod após a validação manual

**Status:** ADIÇÃO DE SEÇÃO — a validação manual ensinada permanece como base conceitual, Zod é adicionado como o padrão real de produção

```
MANTER a seção "Middleware de validação" com o código manual como está —
ela tem valor pedagógico real: mostra O QUE validação faz, mecanicamente,
antes de delegar isso para uma biblioteca. Não remover.

ADICIONAR imediatamente depois uma seção nova:
"Validação de schema com Zod — o padrão real de produção"

Inserir o conteúdo integral do arquivo correcao-validacao-zod.md:

- A explicação de por que validação manual e sistema de tipos resolvem
  o mesmo problema de forma fragmentada (seção "O que estava errado, e
  por que isso é mais grave do que parece" — as três razões: tipos,
  composição, mensagem de erro como interface pública)
- npm install zod
- Construção de schemas: primitivos e refinamentos, objetos, arrays,
  optional/default, enum
- safeParse vs parse, e a conexão explícita com AppError vs Error
  (erro esperado de usuário vs erro de configuração/bug)
- src/middlewares/validar.middleware.js reescrito com validarBody(schema)
- src/schemas/piadas.schema.js como convenção de organização
- .partial() reaproveitando o schema de criação no PATCH, sem duplicar regras
- A seção final "Por que isso não é só mais uma biblioteca" — a
  generalização do princípio para toda fronteira de dados externos
- A comparação lado a lado antes/depois, no fim do arquivo

NÃO resumir essas explicações — o valor pedagógico está exatamente em
entender o PORQUÊ estrutural, não só copiar a sintaxe do Zod.
```

**Seção "Resumo" da aula — ADICIONAR aos bullets existentes:**

```
- Validação de schema (Zod) resolve o mesmo problema que validação manual,
  mas de forma composável, com mensagens de erro estruturadas por campo,
  e (em TypeScript) com tipos derivados automaticamente — é o padrão
  usado em produção
- safeParse() para dados de usuário, onde inválido é uma situação
  esperada; parse() para configuração interna (variáveis de ambiente),
  onde inválido é um erro de configuração que deveria derrubar o processo
- O mesmo princípio de "portão único de validação na fronteira de dados
  externos" se aplica a req.body, req.query, process.env, e respostas
  de APIs externas que a aplicação consome
```

---

## aula-1.2.md (Node course) — Configuração de projeto: validação de env com Zod

**Status:** SUBSTITUIÇÃO DA VALIDAÇÃO DE ENV

```
REMOVER a validação manual atual em src/config/env.js:

const obrigatorias = ['PORT', 'NODE_ENV']
const faltando = obrigatorias.filter(v => !process.env[v])
if (faltando.length > 0) { process.exit(1) }

SUBSTITUIR pela seção "Validando variáveis de ambiente com o mesmo
raciocínio" do arquivo correcao-validacao-zod.md, incluindo:

- Explicação de que process.env é, estruturalmente, a mesma categoria
  de problema que req.body: dados vindos de fora do programa, sem
  garantia de formato
- src/config/env.schema.js com z.object() cobrindo PORT, NODE_ENV,
  DATABASE_URL, JWT_ACCESS_SECRET, JWT_REFRESH_SECRET, LOG_LEVEL
- .transform(Number) para PORT — conversão string→number feita UMA vez,
  no ponto de entrada, não repetida em cada lugar que usa a porta
- .refine() validando o range correto de uma porta TCP (1–65535)
- parse() (não safeParse) com a explicação de por quê: variável de
  ambiente errada é erro de CONFIGURAÇÃO, não entrada de usuário —
  faz sentido derrubar o processo imediatamente com mensagem clara
- src/config/env.js atualizado consumindo o schema

ADICIONAR o exemplo concreto do problema que isso resolve: PORT="abc"
passava despercebido pela validação antiga (que só checava presença,
não formato), e só quebrava depois, longe da causa raiz, quando
app.listen(PORT) falhasse de forma confusa.
```

---

## Novo módulo — Testes com Jest e Supertest

**Status:** MÓDULO NOVO — inserir na grade curricular

```
O conteúdo completo já está pronto no arquivo modulo-testes.md.

POSIÇÃO SUGERIDA na grade: após o Módulo 6 (Arquitetura em Camadas e
Tratamento de Erros) e antes do Módulo 7 (REST e Deploy) do curso de Node.

RAZÃO da posição: testes de integração via Supertest fazem sentido
depois que a arquitetura em camadas e o error handler já existem — os
testes verificam exatamente esses contratos (status codes, formato de
erro, AppError). Colocar testes antes desses módulos não teria o que
testar de forma significativa.

O módulo cobre:
- Diferença entre teste unitário (service com repositório mockado) e
  teste de integração (HTTP real via Supertest contra o app Express)
- Banco de dados de teste isolado (.env.test, TRUNCATE entre testes)
- Helpers reutilizáveis (criarUsuarioEToken, criarPost)
- Testes de integração completos para auth (register, login, refresh)
  e posts (CRUD, curtidas, autorização)
- Testes unitários com jest.mock() no repositório
- O que cobertura de código mede e o que NÃO garante
- CI com GitHub Actions rodando testes automaticamente a cada push,
  incluindo o serviço PostgreSQL como container de teste

Ao integrar na grade, os exercícios anteriores (Exercício 3 em diante)
podem ganhar um requisito adicional: "escreva pelo menos 3 testes de
integração cobrindo os casos de erro principais desta rota" — reforça
o hábito de testar continuamente, não só no fim do curso.
```

---

## aula-4.2.md — SQLite/PostgreSQL: substituir CREATE TABLE IF NOT EXISTS por migrations versionadas

**Status:** SUBSTITUIÇÃO DE SEÇÃO — muda a forma de gerenciar schema em todo o curso

```
REMOVER de src/database/migrations.js (tanto na versão SQLite quanto
na versão PostgreSQL da correcao-postgresql.md):

async function executarMigrations() {
  await query(`CREATE TABLE IF NOT EXISTS usuarios (...)`)
  await query(`CREATE TABLE IF NOT EXISTS posts (...)`)
  ...
}

Esse padrão garante só que a tabela existe, mas não tem noção de
histórico, ordem entre mudanças, ou reversão — resolve bem o caso de
"banco vazio, uma pessoa só" e quebra assim que existe uma segunda
pessoa no projeto ou uma tabela que já tem dados e precisa mudar.

SUBSTITUIR pelo conteúdo integral do arquivo correcao-migrations.md,
que inclui:

- A explicação do paralelo com Git (schema é estado, estado precisa
  de histórico) — seção "O problema central: schema é estado, e
  estado precisa de histórico"
- npm install -D node-pg-migrate
- Estrutura de pasta migrations/ com um arquivo por mudança, timestamp
  no nome
- Cada migration com par up/down (fazer e desfazer)
- O exemplo concreto que expõe por que isso importa: adicionar uma
  coluna a uma tabela que já existe e já tem dados
- A tabela de controle pgmigrations que o node-pg-migrate cria
  automaticamente no banco, registrando o que já foi aplicado
- A seção "Como isso muda o fluxo de trabalho em equipe" — o cenário
  de dois desenvolvedores com bancos locais diferentes
- Deploy: migrate:up rodando como parte do script "start", separado
  da lógica da aplicação (o index.js não sabe mais nada sobre migrations)

REMOVER completamente a chamada de executarMigrations() dentro de
src/index.js — migrations passam a rodar ANTES do processo Node
iniciar, via npm run migrate:up no script "start", não dentro do
código da aplicação.
```

**Seção "Resumo" da aula — ADICIONAR:**

```
- CREATE TABLE IF NOT EXISTS garante existência, mas não tem histórico,
  ordem ou reversão — não é o mesmo que uma migration real
- Ferramentas de migration (node-pg-migrate) mantêm uma tabela de
  controle no próprio banco, registrando exatamente quais mudanças de
  schema já foram aplicadas — o mesmo princípio de histórico versionado
  que já existe no Git para código
- Migrations são commitadas no Git junto com o código que depende delas,
  e rodam como parte do processo de deploy, não dentro da aplicação
```

---

## Nova aula/seção — N+1 Queries

**Status:** CONTEÚDO NOVO — inserir dentro do Módulo 4 (Persistência) do curso de Node, como uma seção adicional após a aula de PostgreSQL/SQLite, ou como uma aula própria (4.3) antes do Exercício 4

```
POSIÇÃO SUGERIDA: logo depois da aula de banco de dados (4.2), antes
do exercício que pede queries com JOIN e GROUP BY (Exercício 4). Isso
porque o Exercício 4 já pede uma query de stats com agregação — o
conceito de N+1 dá o PORQUÊ dessa exigência, que antes era só uma
instrução sem justificativa ("faça em SQL, não em JavaScript").

Inserir o conteúdo integral do arquivo correcao-n-mais-1.md, que inclui:

- A definição mecânica do problema com um exemplo de código que parece
  razoável mas dispara 21 queries em vez de 1
- A explicação de POR QUE isso nasce naturalmente (a armadilha
  psicológica de traduzir "para cada item, busco o relacionado"
  direto em um loop, ignorando que iterar em memória e fazer round-trips
  de rede têm custos completamente diferentes)
- Por que o bug é invisível em desenvolvimento e só aparece quando o
  projeto cresce — a característica mais perigosa desse tipo de problema
- Solução 1: JOIN + GROUP BY, para dados que colapsam em um valor
  agregado por linha (contagem, soma, existência)
- Solução 2: batching com WHERE coluna = ANY($1), para dados que NÃO
  colapsam bem (lista de itens relacionados, como últimos comentários)
  — total de 2 queries, não 1+N
- O sinal de alerta a procurar no próprio código: await/query dentro
  de .map()/.forEach()/loop, iterando resultado de query anterior
- Uma técnica simples de instrumentar pool.query para logar cada SQL
  disparado durante desenvolvimento, tornando o problema visível

CONECTAR EXPLICITAMENTE com a aula 4.2 (PostgreSQL): a query de stats
com COUNT/GROUP BY que já existia no curso original era, sem nomear,
a aplicação da Solução 1 (JOIN). Vale voltar nessa aula e adicionar uma
nota apontando essa conexão — "isso que você fez aqui evita N+1, veja
a aula seguinte para entender por quê".
```

**Atualização no exercicio-4.md — ADICIONAR nota:**

```
ADICIONAR uma nota de contexto na seção "Query de JOIN que você vai
precisar":

"Esta query resolve deliberadamente o problema de N+1: buscar os posts
e DEPOIS, para cada um, buscar a contagem de curtidas separadamente
geraria uma query por post. O JOIN + GROUP BY faz isso em uma única
operação, não importa quantos posts existam."
```

---

## Resumo por arquivo

| Arquivo | Tipo de mudança | Urgência |
|---------|----------------|----------|
| aula-4.2.md | Substituição completa: async/await (feito) + migrations versionadas | 🔴 Crítico |
| aula-5.1.md | Reescrita da implementação de auth | 🔴 Crítico |
| aula-5.2.md | Três adições: SELECT, XSS, Redis limiter | 🟡 Importante |
| aula-6.2.md | Substituir logger manual por pino | 🟡 Importante |
| aula-7.2.md | Substituir SQLite por PostgreSQL no deploy | 🔴 Crítico |
| aula-3.2.md | Adicionar validação com Zod após validação manual | 🟡 Importante |
| aula-1.2.md (env) | Validação de env com Zod schema | 🟢 Melhoria |
| exercicio-4.md | Nota conectando JOIN à prevenção de N+1 | 🟢 Melhoria |
| exercicio-5.md | Atualizar requisitos de auth | 🔴 Crítico |
| projeto-final.md | Atualizar banco e auth | 🔴 Crítico |
| Novo módulo de testes | Inserir na grade entre Módulo 6 e 7 | 🟡 Importante |
| Nova aula/seção N+1 | Inserir após aula 4.2, antes do Exercício 4 | 🟡 Importante |
