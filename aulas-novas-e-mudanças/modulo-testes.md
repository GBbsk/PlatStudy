# Módulo Extra — Testes com Jest e Supertest

## Por que testes não são opcionais

Um projeto sem testes tem um problema fundamental: você não sabe se ele funciona — você acredita que funciona com base na última vez que testou manualmente. À medida que o projeto cresce, essa crença vai ficando mais frágil. Você altera um service, quebra um comportamento em outro lugar, e só descobre quando alguém reporta o bug em produção.

Testes automatizados resolvem isso de forma sistemática. E têm um benefício colateral importante: eles forçam uma arquitetura melhor. Código difícil de testar é código mal estruturado — dependências ocultas, responsabilidades misturadas, acoplamento desnecessário. A arquitetura em camadas que você construiu (routes → controllers → services → repositories) existe em parte *porque* ela é testável.

---

## Tipos de teste que vamos escrever

```
Teste Unitário
  Testa uma função isolada, sem dependências reais
  → services testados com repositórios mockados
  → rápido, fácil de isolar a causa de falha

Teste de Integração
  Testa o sistema inteiro de ponta a ponta, via HTTP
  → faz uma requisição real para o Express
  → banco de dados real (de teste, separado do dev)
  → mais lento, mas verifica que as peças se encaixam
```

Para o Linkr, os dois tipos têm papéis diferentes:
- **Unitários** para lógica de negócio nos services (regras de validação, lógica de follow, etc.)
- **Integração** para as rotas HTTP (garante que o pipeline completo funciona)

---

## Instalação

```bash
npm install -D jest supertest @types/jest

# Para compatibilidade com módulos ES no Jest
npm install -D babel-jest @babel/core @babel/preset-env
```

```js
// jest.config.js
module.exports = {
  testEnvironment: 'node',
  testMatch: ['**/__tests__/**/*.test.js'],
  setupFilesAfterFramework: ['./__tests__/setup.js'],
  coverageDirectory: 'coverage',
  collectCoverageFrom: ['src/**/*.js', '!src/index.js'],
  // Tempo máximo por teste — evita testes que travam indefinidamente
  testTimeout: 10000
}
```

```json
// package.json — scripts de teste
{
  "scripts": {
    "test":         "jest",
    "test:watch":   "jest --watch",
    "test:coverage": "jest --coverage",
    "test:ci":      "jest --ci --coverage --forceExit"
  }
}
```

---

## Banco de dados de teste — ambiente isolado

Testes de integração precisam de um banco separado do banco de desenvolvimento. Misturar os dois significa que testes podem destruir dados reais, e dados reais podem interferir nos testes.

```env
# .env.test — carregado automaticamente quando NODE_ENV=test
DATABASE_URL=postgresql://postgres:senha@localhost:5432/linkr_test
JWT_ACCESS_SECRET=test-access-secret-minimo-32-caracteres-aqui
JWT_REFRESH_SECRET=test-refresh-secret-minimo-32-caracteres-aqui
NODE_ENV=test
LOG_LEVEL=silent
```

```js
// __tests__/setup.js
// Executado uma vez antes de todos os testes
const { executarMigrations } = require('../src/database/migrations')
const { query, fechar }      = require('../src/database/connection')

// Carrega as variáveis do .env.test
require('dotenv').config({ path: '.env.test' })

// Antes de toda suite de testes
beforeAll(async () => {
  await executarMigrations()
})

// Antes de cada teste individual — garante isolamento completo
beforeEach(async () => {
  // Limpa todas as tabelas na ordem correta (respeitando foreign keys)
  await query('TRUNCATE TABLE refresh_tokens, curtidas, comentarios, follows, posts, usuarios CASCADE')
})

// Depois de todos os testes — fecha o pool de conexões
afterAll(async () => {
  await fechar()
})
```

---

## Helpers de teste — dados reutilizáveis

```js
// __tests__/helpers.js
const request = require('supertest')
const app     = require('../src/app')

// Cria um usuário e retorna o accessToken — usado em testes que precisam de auth
async function criarUsuarioEToknen(dados = {}) {
  const defaults = {
    nome:     'Usuário Teste',
    username: `user_${Date.now()}`,   // único a cada chamada
    email:    `teste_${Date.now()}@email.com`,
    senha:    'TesteSenha1'
  }

  const res = await request(app)
    .post('/api/v1/auth/register')
    .send({ ...defaults, ...dados })

  if (res.status !== 201) {
    throw new Error(`Falha ao criar usuário de teste: ${JSON.stringify(res.body)}`)
  }

  return {
    usuario:     res.body.usuario,
    accessToken: res.body.accessToken
  }
}

// Cria um post e retorna o objeto criado
async function criarPost(accessToken, dados = {}) {
  const defaults = {
    titulo:    'Post de Teste com título longo o suficiente',
    url:       `https://exemplo.com/post-${Date.now()}`,
    descricao: 'Descrição do post de teste'
  }

  const res = await request(app)
    .post('/api/v1/posts')
    .set('Authorization', `Bearer ${accessToken}`)
    .send({ ...defaults, ...dados })

  if (res.status !== 201) {
    throw new Error(`Falha ao criar post de teste: ${JSON.stringify(res.body)}`)
  }

  return res.body
}

module.exports = { criarUsuarioEToknen, criarPost }
```

---

## Testes de integração — rotas de autenticação

```js
// __tests__/auth.test.js
const request = require('supertest')
const app     = require('../src/app')
const { criarUsuarioEToknen } = require('./helpers')

describe('POST /api/v1/auth/register', () => {
  it('cria usuário e retorna accessToken', async () => {
    const res = await request(app)
      .post('/api/v1/auth/register')
      .send({
        nome:     'Ana Silva',
        username: 'anasilva',
        email:    'ana@email.com',
        senha:    'MinhaSenh4'
      })

    expect(res.status).toBe(201)
    expect(res.body).toHaveProperty('accessToken')
    expect(res.body.usuario).toMatchObject({
      nome:  'Ana Silva',
      email: 'ana@email.com'
    })
    // senha_hash nunca deve aparecer na resposta
    expect(res.body.usuario).not.toHaveProperty('senha_hash')
    expect(res.body.usuario).not.toHaveProperty('senha')
  })

  it('retorna 409 quando o email já existe', async () => {
    await criarUsuarioEToknen({ email: 'duplicado@email.com' })

    const res = await request(app)
      .post('/api/v1/auth/register')
      .send({
        nome:  'Outro Usuário',
        email: 'duplicado@email.com',
        senha: 'OutraSenh4'
      })

    expect(res.status).toBe(409)
    expect(res.body).toHaveProperty('erro')
  })

  it('retorna 400 quando a senha é fraca', async () => {
    const res = await request(app)
      .post('/api/v1/auth/register')
      .send({
        nome:  'Teste',
        email: 'fraco@email.com',
        senha: '123'     // fraca demais
      })

    expect(res.status).toBe(400)
    expect(res.body).toHaveProperty('detalhes')
    expect(Array.isArray(res.body.detalhes)).toBe(true)
    expect(res.body.detalhes.length).toBeGreaterThan(0)
  })
})

describe('POST /api/v1/auth/login', () => {
  beforeEach(async () => {
    await criarUsuarioEToknen({
      email: 'login@email.com',
      senha: 'LoginSenh4'
    })
  })

  it('retorna accessToken com credenciais válidas', async () => {
    const res = await request(app)
      .post('/api/v1/auth/login')
      .send({ email: 'login@email.com', senha: 'LoginSenh4' })

    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('accessToken')
    // Cookie httpOnly deve estar presente na resposta
    expect(res.headers['set-cookie']).toBeDefined()
    expect(res.headers['set-cookie'].some(c => c.includes('refresh_token'))).toBe(true)
  })

  it('retorna 401 com senha errada — mesma mensagem que email inexistente', async () => {
    const resSenhaErrada = await request(app)
      .post('/api/v1/auth/login')
      .send({ email: 'login@email.com', senha: 'SenhaErrada1' })

    const resEmailInexistente = await request(app)
      .post('/api/v1/auth/login')
      .send({ email: 'naoexiste@email.com', senha: 'QualquerCoisa1' })

    // As duas respostas devem ter a mesma mensagem — timing attack prevention
    expect(resSenhaErrada.status).toBe(401)
    expect(resEmailInexistente.status).toBe(401)
    expect(resSenhaErrada.body.erro).toBe(resEmailInexistente.body.erro)
  })
})

describe('POST /api/v1/auth/refresh', () => {
  it('emite novo accessToken com refresh token válido no cookie', async () => {
    // 1. Faz login para obter o cookie com refresh token
    const loginRes = await request(app)
      .post('/api/v1/auth/login')
      .send({ email: 'login@email.com', senha: 'LoginSenh4' })

    const cookies = loginRes.headers['set-cookie']

    // 2. Usa o cookie para obter um novo access token
    const refreshRes = await request(app)
      .post('/api/v1/auth/refresh')
      .set('Cookie', cookies)

    expect(refreshRes.status).toBe(200)
    expect(refreshRes.body).toHaveProperty('accessToken')
    // O novo accessToken deve ser diferente do anterior
    expect(refreshRes.body.accessToken).not.toBe(loginRes.body.accessToken)
  })

  it('retorna 401 sem cookie de refresh token', async () => {
    const res = await request(app).post('/api/v1/auth/refresh')
    expect(res.status).toBe(401)
  })
})
```

---

## Testes de integração — rotas de posts

```js
// __tests__/posts.test.js
const request = require('supertest')
const app     = require('../src/app')
const { criarUsuarioEToknen, criarPost } = require('./helpers')

describe('GET /api/v1/posts', () => {
  it('retorna lista vazia quando não há posts', async () => {
    const res = await request(app).get('/api/v1/posts')

    expect(res.status).toBe(200)
    expect(res.body.dados).toEqual([])
    expect(res.body.paginacao).toMatchObject({ total: 0 })
  })

  it('retorna posts com dados de paginação corretos', async () => {
    const { accessToken } = await criarUsuarioEToknen()
    await criarPost(accessToken)
    await criarPost(accessToken)
    await criarPost(accessToken)

    const res = await request(app).get('/api/v1/posts?porPagina=2')

    expect(res.status).toBe(200)
    expect(res.body.dados).toHaveLength(2)
    expect(res.body.paginacao).toMatchObject({
      total:       3,
      pagina:      1,
      porPagina:   2,
      totalPaginas: 2
    })
  })
})

describe('POST /api/v1/posts', () => {
  it('cria post quando autenticado', async () => {
    const { accessToken } = await criarUsuarioEToknen()

    const res = await request(app)
      .post('/api/v1/posts')
      .set('Authorization', `Bearer ${accessToken}`)
      .send({
        titulo:    'Post válido com título suficientemente longo',
        url:       'https://exemplo.com/post-valido',
        descricao: 'Uma descrição qualquer'
      })

    expect(res.status).toBe(201)
    expect(res.body).toMatchObject({
      titulo: 'Post válido com título suficientemente longo',
      url:    'https://exemplo.com/post-valido'
    })
    expect(res.body).toHaveProperty('id')
    expect(res.body).toHaveProperty('criado_em')
  })

  it('retorna 401 sem token', async () => {
    const res = await request(app)
      .post('/api/v1/posts')
      .send({ titulo: 'Qualquer', url: 'https://exemplo.com' })

    expect(res.status).toBe(401)
  })

  it('retorna 400 com URL inválida', async () => {
    const { accessToken } = await criarUsuarioEToknen()

    const res = await request(app)
      .post('/api/v1/posts')
      .set('Authorization', `Bearer ${accessToken}`)
      .send({
        titulo: 'Título válido e longo o suficiente',
        url:    'nao-e-uma-url'
      })

    expect(res.status).toBe(400)
  })

  it('retorna 403 quando usuário não é o autor tenta editar', async () => {
    const { accessToken: tokenAutor }    = await criarUsuarioEToknen()
    const { accessToken: tokenOutroUser } = await criarUsuarioEToknen()
    const post = await criarPost(tokenAutor)

    const res = await request(app)
      .patch(`/api/v1/posts/${post.id}`)
      .set('Authorization', `Bearer ${tokenOutroUser}`)
      .send({ titulo: 'Tentativa de edição não autorizada' })

    expect(res.status).toBe(403)
  })
})

describe('POST /api/v1/posts/:id/curtir', () => {
  it('incrementa curtidas e retorna o total atualizado', async () => {
    const { accessToken } = await criarUsuarioEToknen()
    const post = await criarPost(accessToken)

    const res = await request(app)
      .post(`/api/v1/posts/${post.id}/curtir`)
      .set('Authorization', `Bearer ${accessToken}`)

    expect(res.status).toBe(201)
    expect(res.body.totalCurtidas).toBe(1)
  })

  it('retorna 409 ao curtir o mesmo post duas vezes', async () => {
    const { accessToken } = await criarUsuarioEToknen()
    const post = await criarPost(accessToken)

    await request(app)
      .post(`/api/v1/posts/${post.id}/curtir`)
      .set('Authorization', `Bearer ${accessToken}`)

    const res = await request(app)
      .post(`/api/v1/posts/${post.id}/curtir`)
      .set('Authorization', `Bearer ${accessToken}`)

    expect(res.status).toBe(409)
  })
})
```

---

## Testes unitários — services com mocks

```js
// __tests__/unit/posts.service.test.js
const postsService = require('../../src/services/posts.service')
const postsRepo    = require('../../src/repositories/posts.repository')
const AppError     = require('../../src/utils/AppError')

// Substitui o repositório real por um mock — nenhuma query chega ao banco
jest.mock('../../src/repositories/posts.repository')

describe('postsService.criar', () => {
  const usuarioId = 'usuario-uuid-qualquer'

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('lança AppError 400 quando titulo é curto demais', async () => {
    await expect(
      postsService.criar({ titulo: 'curto', url: 'https://ok.com' }, usuarioId)
    ).rejects.toThrow(AppError)

    await expect(
      postsService.criar({ titulo: 'curto', url: 'https://ok.com' }, usuarioId)
    ).rejects.toMatchObject({ statusCode: 400 })
  })

  it('lança AppError 400 quando URL é inválida', async () => {
    await expect(
      postsService.criar({ titulo: 'Título válido e longo', url: 'nao-e-url' }, usuarioId)
    ).rejects.toMatchObject({ statusCode: 400 })
  })

  it('chama o repositório com dados sanitizados quando válido', async () => {
    postsRepo.criar.mockResolvedValue({ id: 'novo-id', titulo: 'Título OK' })

    const dados = {
      titulo:    '  Título com espaços extra  ',
      url:       'https://exemplo.com/post',
      descricao: '<script>alerta</script>'  // deve ser sanitizado
    }

    await postsService.criar(dados, usuarioId)

    expect(postsRepo.criar).toHaveBeenCalledWith(
      expect.objectContaining({
        titulo:    'Título com espaços extra',    // trim aplicado
        descricao: '&lt;script&gt;alerta&lt;/script&gt;'  // XSS escapado
      })
    )
  })

  it('lança AppError 403 quando não é o autor tentando editar', async () => {
    postsRepo.buscarPorId.mockResolvedValue({
      id:         'post-id',
      usuario_id: 'autor-real'
    })

    await expect(
      postsService.atualizar('post-id', { titulo: 'Novo título' }, 'outro-usuario')
    ).rejects.toMatchObject({ statusCode: 403 })
  })
})
```

---

## Cobertura de testes — o que mede e o que não mede

```bash
$ npm run test:coverage

---------|---------|----------|---------|---------|
File     | % Stmts | % Branch | % Funcs | % Lines |
---------|---------|----------|---------|---------|
services |   92.31 |    87.50 |   100   |   92.31 |
repos    |   85.71 |    75.00 |   100   |   85.71 |
---------|---------|----------|---------|---------|
```

Cobertura de 100% não é o objetivo — é uma métrica, não uma garantia. Você pode ter 100% de cobertura com testes que não verificam nada relevante. O que você realmente quer:

- **Caminhos de erro cobertos** — `it('retorna 403 quando...')`, `it('retorna 400 quando...')`
- **Comportamentos críticos cobertos** — curtida duplicada, edição por não-autor, timing attack no login
- **Testes que falham quando o comportamento muda** — se você quebrar algo, o teste deve capturar

---

## CI — rodando testes automaticamente

```yaml
# .github/workflows/testes.yml
name: Testes

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: senha
          POSTGRES_DB: linkr_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - run: npm ci

      - name: Rodar testes
        run: npm run test:ci
        env:
          DATABASE_URL: postgresql://postgres:senha@localhost:5432/linkr_test
          JWT_ACCESS_SECRET: secret-de-teste-com-pelo-menos-32-chars
          JWT_REFRESH_SECRET: outro-secret-de-teste-com-32-chars-ok
          NODE_ENV: test
          LOG_LEVEL: silent
```

Com isso, todo push e todo PR roda os testes automaticamente no GitHub Actions. Código quebrado não passa despercebido.

---

## Estrutura final de pastas com testes

```
linkr-api/
├── src/
│   ├── app.js
│   ├── index.js
│   ├── config/
│   ├── database/
│   ├── repositories/
│   ├── services/
│   ├── controllers/
│   ├── routes/
│   ├── middlewares/
│   └── utils/
├── __tests__/
│   ├── setup.js              ← configuração global dos testes
│   ├── helpers.js            ← factories reutilizáveis
│   ├── auth.test.js          ← testes de integração: auth
│   ├── posts.test.js         ← testes de integração: posts
│   ├── usuarios.test.js      ← testes de integração: usuários
│   └── unit/
│       ├── posts.service.test.js
│       └── auth.service.test.js
├── jest.config.js
├── .env
├── .env.test
└── package.json
```
