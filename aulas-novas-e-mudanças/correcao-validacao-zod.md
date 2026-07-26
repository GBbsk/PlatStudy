# Correção — Validação de Schema com Zod

## O que estava errado, e por que isso é mais grave do que parece

O curso ensinou validação assim:

```js
function validar(dados, schema) {
  const erros = []
  for (const [campo, regras] of Object.entries(schema)) {
    if (regras.obrigatorio && !dados[campo]) erros.push(`${campo} é obrigatório`)
    // ...
  }
  if (erros.length > 0) throw new AppError('Dados inválidos', 400, erros)
}
```

Isso funciona. Mas "funciona" não é a régua certa aqui — a régua é "isso é o que um sistema em produção real faz, e por quê?". E a resposta é não, por três razões que vale entender a fundo, porque cada uma delas ensina algo sobre o problema real que validação resolve.

### Razão 1 — validação e tipos são o mesmo problema, resolvidos duas vezes

Pense no que uma função de validação realmente faz: ela pega um dado de formato desconhecido (o `req.body`, que tecnicamente é `any` — pode ser literalmente qualquer coisa, porque vem de fora do seu programa) e devolve um dado de formato conhecido, no qual você confia para o resto do código.

Isso é, conceitualmente, **a mesma operação que um sistema de tipos faz**. TypeScript, por exemplo, existe para garantir que se uma variável é declarada como `string`, ela é `string` em todo o programa. Mas o TypeScript só verifica isso em tempo de compilação — ele não tem como saber se o JSON que chegou pela rede realmente corresponde ao tipo que você declarou. Em outras palavras: **na fronteira entre o seu sistema e o mundo externo (rede, banco, arquivo), tipos estáticos não te protegem, porque eles são apagados em tempo de execução.**

A validação manual com `if`s resolve isso, mas de forma isolada — ela verifica os dados, mas não produz nenhum tipo que o resto do código possa usar com confiança. Você ainda trata `req.body.setup` como `any` depois da validação, porque não há nada ligando "eu validei isso" a "o TypeScript/JSDoc sabe que isso é seguro agora".

Uma biblioteca de schema como o **Zod** resolve os dois problemas de uma vez: ela valida em tempo de execução (a parte que você já fazia) **e** produz um tipo estático correspondente (a parte que faltava). Isso significa que depois de validar, o compilador (ou seu editor, via JSDoc/TS) sabe exatamente o formato do dado, e vai te avisar se você tentar acessar um campo que não existe ou usar do jeito errado.

### Razão 2 — validação manual não compõe

"Compor" aqui significa: você consegue construir validações complexas a partir de validações simples, sem reescrever nada.

```js
// Você já tem uma validação de "email válido" em algum lugar
// Agora precisa de "email válido, mas opcional"
// Com if manual, você reescreve a lógica com uma condição a mais

// Com Zod, você compõe:
const emailObrigatorio = z.string().email()
const emailOpcional    = emailObrigatorio.optional()
```

Isso parece pequeno em um exemplo isolado, mas em um sistema real com dezenas de endpoints, você constantemente reaproveita partes de validação — "esse campo de senha é usado tanto no registro quanto na troca de senha", "esse formato de UUID é usado em todo path param". Validação manual replicada vira, na prática, N versões ligeiramente diferentes da mesma regra, cada uma podendo divergir com o tempo.

### Razão 3 — a mensagem de erro é sua interface pública, e validação manual trata isso como afterthought

Pense assim: quando alguém integra com a sua API — um frontend, um app mobile, outro backend — a única coisa que essa pessoa vê quando erra é a mensagem de erro. Ela não vê seu código. A mensagem de erro **é** a documentação de runtime da sua API.

```json
{ "erro": "Dados inválidos", "detalhes": ["setor deve ter pelo menos 10 caracteres"] }
```

Essa mensagem, escrita manualmente, é fácil de esquecer de atualizar, fácil de ficar inconsistente entre endpoints diferentes (um diz "obrigatório", outro diz "é necessário"), e não tem estrutura previsível para o cliente parsear programaticamente (qual campo exatamente falhou? em qual posição do array?).

Uma lib de schema gera mensagens de erro estruturadas e localizáveis por padrão, com o caminho exato do campo que falhou — inclusive em objetos aninhados e arrays.

---

## O que é Zod, tecnicamente

Zod é uma biblioteca de **schema declarativo com inferência de tipos**. "Declarativo" significa que você descreve *o formato que o dado deveria ter*, não *os passos para verificar o dado* — a diferença entre dizer "isso deve ser um objeto com um campo `nome` que é string de 2 a 100 caracteres" e escrever manualmente o `if` que checa isso.

```bash
npm install zod
```

```js
const { z } = require('zod')

// Isso é uma DESCRIÇÃO da forma dos dados, não uma função de checagem procedural
const schemaUsuario = z.object({
  nome:  z.string().min(2).max(100),
  email: z.string().email(),
  idade: z.number().int().positive().optional()
})
```

Por baixo dos panos, o Zod constrói uma árvore de regras a partir dessa descrição, e usa essa árvore tanto para validar em runtime quanto (via TypeScript) para derivar o tipo estático correspondente — por isso "inferência de tipos".

---

## Construindo schemas — do básico ao real

### Tipos primitivos e seus refinamentos

```js
// String, com refinamentos encadeados — cada um adiciona uma restrição
z.string()                    // qualquer string
z.string().min(10)            // mínimo 10 caracteres
z.string().max(200)           // máximo 200 caracteres
z.string().email()            // formato de email válido
z.string().url()              // formato de URL válida
z.string().uuid()             // formato de UUID válido
z.string().regex(/^[a-z0-9_]+$/)  // regex customizado

// Number
z.number()
z.number().int()              // deve ser inteiro
z.number().positive()         // maior que zero
z.number().min(0).max(100)    // intervalo

// Boolean
z.boolean()

// Enum — restringe a um conjunto fechado de valores
z.enum(['programacao', 'geral', 'trocadilho', 'dad-joke'])
```

Repare que cada refinamento (`.min()`, `.email()`, etc.) retorna um **novo schema**, imutável — isso é o que permite a composição mencionada antes. `z.string()` sozinho é reutilizável; `z.string().email()` é outro schema, construído em cima do primeiro, também reutilizável.

### Objetos — a unidade real de validação de um endpoint

```js
const schemaCriarPiada = z.object({
  setup:     z.string().min(10).max(200),
  punchline: z.string().min(5).max(200),
  categoria: z.enum(['programacao', 'geral', 'trocadilho', 'dad-joke'])
})
```

Isso descreve exatamente o body esperado de `POST /jokes`. Um objeto Zod validando um objeto JavaScript verifica, de uma vez: presença de cada campo obrigatório, tipo de cada campo, e as regras específicas de cada um — tudo isso é uma única operação, não uma sequência de `if`s independentes que podem ficar dessincronizados entre si.

### Campos opcionais e valores default

```js
const schemaPost = z.object({
  titulo:    z.string().min(5).max(200),
  url:       z.string().url(),
  descricao: z.string().max(500).optional(),        // pode não existir
  destaque:  z.boolean().default(false)              // se ausente, assume false
})
```

`optional()` é semanticamente diferente de "string vazia permitida" — ele diz "este campo pode simplesmente não estar presente no objeto". Isso é uma distinção que validação manual frequentemente confunde (checar `!dados.campo` trata `undefined`, `null`, `''` e `0` da mesma forma, quando na verdade são situações diferentes).

### Arrays

```js
const schemaComTags = z.object({
  titulo: z.string().min(5),
  tags: z.array(
    z.string().regex(/^[a-z0-9-]+$/).max(20)
  ).max(5)   // no máximo 5 tags no array
})
```

Aqui está uma vantagem concreta sobre validação manual: se a tag no índice 2 do array falhar, o Zod te diz exatamente isso — `tags.2` — sem você precisar escrever um loop com índice manualmente para rastrear qual posição falhou.

---

## Validando e tratando o resultado

```js
const resultado = schemaCriarPiada.safeParse(req.body)

if (!resultado.success) {
  // resultado.error é um objeto ZodError, com uma estrutura rica de erros
  console.log(resultado.error.issues)
  // [
  //   {
  //     code: 'too_small',
  //     path: ['setup'],
  //     message: 'String must contain at least 10 character(s)'
  //   }
  // ]
}

if (resultado.success) {
  // resultado.data é o dado JÁ VALIDADO E TIPADO
  // Em TypeScript, resultado.data tem o tipo exato inferido do schema
  const piada = resultado.data
}
```

`safeParse` (em vez de `parse`) é a escolha certa para validação de entrada de usuário — ele retorna um objeto de resultado em vez de lançar exceção, o que deixa explícito no seu código que essa é uma operação que pode falhar de forma esperada (dado inválido de usuário), diferente de uma exceção de programação (bug).

```js
// parse() lança exceção — use quando um dado inválido é um BUG, não uma entrada de usuário
// Ex: validando uma variável de ambiente, que deveria estar sempre correta
const config = schemaConfig.parse(process.env)

// safeParse() retorna resultado — use para dados de usuário, que podem legitimamente estar errados
const resultado = schemaCriarPiada.safeParse(req.body)
```

Essa distinção entre `parse` e `safeParse` reflete uma distinção mais ampla e importante em todo tratamento de erros: **erro esperado (dado de usuário inválido) e erro inesperado (bug) merecem tratamento diferente**, exatamente o princípio que já orientou o `AppError` vs `Error` genérico no error handler do curso.

---

## Middleware de validação — integrando ao Express

```js
// src/middlewares/validar.middleware.js

// Factory de middleware — recebe um schema, devolve um middleware específico para ele
// Isso é o mesmo padrão de "middleware que retorna middleware" que você já viu
// no curso original com validarCampos(camposObrigatorios)
function validarBody(schema) {
  return (req, res, next) => {
    const resultado = schema.safeParse(req.body)

    if (!resultado.success) {
      // Transforma o formato de erro do Zod no formato de resposta da sua API
      // Isso mantém o CONTRATO de resposta de erro consistente com o resto do curso,
      // mesmo trocando o motor de validação por baixo
      const detalhes = resultado.error.issues.map(issue => {
        const caminho = issue.path.join('.')
        return caminho ? `${caminho}: ${issue.message}` : issue.message
      })

      return res.status(400).json({
        erro: 'Dados inválidos',
        detalhes
      })
    }

    // Substitui req.body pelo dado JÁ VALIDADO E NORMALIZADO
    // (valores default aplicados, tipos coeridos quando o schema pede)
    req.body = resultado.data
    next()
  }
}

module.exports = { validarBody }
```

```js
// src/schemas/piadas.schema.js
const { z } = require('zod')

const criarPiadaSchema = z.object({
  setup:     z.string().min(10, 'setup deve ter pelo menos 10 caracteres').max(200),
  punchline: z.string().min(5, 'punchline deve ter pelo menos 5 caracteres').max(200),
  categoria: z.enum(['programacao', 'geral', 'trocadilho', 'dad-joke'], {
    errorMap: () => ({ message: 'categoria inválida' })
  })
})

// Para PATCH, todos os campos ficam opcionais — reaproveitando o schema de criação
const atualizarPiadaSchema = criarPiadaSchema.partial()

module.exports = { criarPiadaSchema, atualizarPiadaSchema }
```

Note o `.partial()` — ele pega um schema já existente e torna todos os campos opcionais, sem você reescrever nada. Isso é exatamente o tipo de composição que validação manual não te dá de graça.

```js
// src/routes/jokes.routes.js
const { validarBody } = require('../middlewares/validar.middleware')
const { criarPiadaSchema, atualizarPiadaSchema } = require('../schemas/piadas.schema')

router.post('/',
  autenticar,
  validarBody(criarPiadaSchema),
  asyncHandler(controller.criar)
)

router.patch('/:id',
  autenticar,
  validarBody(atualizarPiadaSchema),
  asyncHandler(controller.atualizar)
)
```

Repare que o `controller.criar` não muda nada — ele já esperava `req.body` validado. O que mudou foi **quem** garante essa validação e **como** ela é descrita, não o contrato entre as camadas.

---

## Validando variáveis de ambiente com o mesmo raciocínio

Esta é uma aplicação do mesmo princípio em outro lugar do sistema, que vale entender porque é o mesmo problema estrutural: `process.env` é, tecnicamente, um objeto de strings vindo de fora do seu programa (do sistema operacional ou do arquivo `.env`) — exatamente como `req.body` vem de fora, da rede.

O curso original validava só a **presença** das variáveis:

```js
const obrigatorias = ['PORT', 'JWT_SECRET']
const faltando = obrigatorias.filter(v => !process.env[v])
if (faltando.length > 0) { process.exit(1) }
```

Isso não verifica **formato**. Uma `PORT=abc` passa por essa validação (a string existe, não é vazia), e só vai quebrar depois, em um lugar distante do problema real — quando o `app.listen(PORT)` falhar de um jeito confuso.

```js
// src/config/env.schema.js
const { z } = require('zod')

const envSchema = z.object({
  PORT: z.string()
    .regex(/^\d+$/, 'PORT deve ser um número')
    .transform(Number)          // depois de validar como string numérica, converte para number
    .refine(n => n > 0 && n < 65536, 'PORT deve estar entre 1 e 65535'),

  NODE_ENV: z.enum(['development', 'production', 'test']),

  DATABASE_URL: z.string().url('DATABASE_URL deve ser uma URL válida de conexão'),

  JWT_ACCESS_SECRET: z.string().min(32, 'JWT_ACCESS_SECRET deve ter pelo menos 32 caracteres'),
  JWT_REFRESH_SECRET: z.string().min(32, 'JWT_REFRESH_SECRET deve ter pelo menos 32 caracteres'),

  LOG_LEVEL: z.enum(['trace', 'debug', 'info', 'warn', 'error', 'fatal']).default('info')
})

// parse() aqui é intencional, não safeParse — uma variável de ambiente errada
// é um erro de CONFIGURAÇÃO, não uma entrada de usuário. Faz sentido derrubar
// o processo imediatamente com uma mensagem clara, em vez de continuar rodando
// com configuração inválida
function validarEnv() {
  try {
    return envSchema.parse(process.env)
  } catch (erro) {
    console.error('❌ Configuração de ambiente inválida:')
    erro.issues.forEach(issue => {
      console.error(`   - ${issue.path.join('.')}: ${issue.message}`)
    })
    process.exit(1)
  }
}

module.exports = { validarEnv }
```

```js
// src/config/env.js
require('dotenv').config()
const { validarEnv } = require('./env.schema')

// config já vem validado E com os tipos corretos (PORT já é number, não string)
const config = validarEnv()

module.exports = {
  port: config.PORT,
  nodeEnv: config.NODE_ENV,
  isDevelopment: config.NODE_ENV === 'development',
  isProduction: config.NODE_ENV === 'production',
  databaseUrl: config.DATABASE_URL,
  jwtAccessSecret: config.JWT_ACCESS_SECRET,
  jwtRefreshSecret: config.JWT_REFRESH_SECRET,
  logLevel: config.LOG_LEVEL
}
```

O ganho aqui não é só cosmético. `PORT` chega como `string` do `process.env` sempre — é assim que variáveis de ambiente funcionam no sistema operacional, não existe "number" nesse nível. O `.transform(Number)` converte isso uma única vez, no ponto de entrada, e o resto da aplicação nunca mais precisa lembrar de fazer `Number(process.env.PORT)` — que é exatamente o tipo de conversão espalhada e repetida que gera bugs quando alguém esquece de fazer em um lugar novo.

---

## Por que isso não é "só mais uma biblioteca" — a ideia central que fica

O padrão que conecta as duas aplicações acima (validar `req.body` e validar `process.env`) é este: **toda vez que um dado atravessa a fronteira entre "fora do seu programa" e "dentro do seu programa", ele deveria passar por um portão único de validação, que ao mesmo tempo (a) rejeita o que é inválido com uma mensagem clara e (b) produz um dado em que o resto do código pode confiar sem revalidar.**

Essa fronteira existe em vários lugares que talvez você não tenha pensado como "a mesma categoria de problema":

- Body de uma requisição HTTP (`req.body`)
- Query string (`req.query`)
- Variáveis de ambiente (`process.env`)
- Resposta de uma API externa que você consome (`fetch` de outro serviço)
- Conteúdo lido de um arquivo (`JSON.parse` de um arquivo de configuração)

Em todos esses casos, o dado chega como `any` — sem garantia nenhuma de formato — e o seu trabalho é transformá-lo em algo confiável antes de deixá-lo se espalhar pelo resto do sistema. Zod (ou bibliotecas equivalentes como Yup, Joi) existem para resolver essa categoria inteira de problema de forma consistente, em vez de você reinventar uma versão ad-hoc dela em cada lugar onde ela aparece.

---

## Comparação lado a lado — o antes e o depois

```js
// ANTES (validação manual do curso original)
function validarPiada(req, res, next) {
  const { setup, punchline, categoria } = req.body
  const erros = []

  if (setup && setup.trim().length < 10) {
    erros.push('setup deve ter pelo menos 10 caracteres')
  }
  if (punchline && punchline.trim().length < 5) {
    erros.push('punchline deve ter pelo menos 5 caracteres')
  }
  const categoriasValidas = ['programacao', 'geral', 'trocadilho', 'dark']
  if (categoria && !categoriasValidas.includes(categoria)) {
    erros.push(`categoria deve ser uma de: ${categoriasValidas.join(', ')}`)
  }

  if (erros.length > 0) {
    return res.status(400).json({ erro: erros.join('. ') })
  }
  next()
}
```

```js
// DEPOIS (Zod)
const criarPiadaSchema = z.object({
  setup:     z.string().min(10),
  punchline: z.string().min(5),
  categoria: z.enum(['programacao', 'geral', 'trocadilho', 'dad-joke'])
})

router.post('/', validarBody(criarPiadaSchema), asyncHandler(controller.criar))
```

O segundo não é só "mais curto". Ele é reutilizável (`.partial()` no PATCH), composável (você pode extrair `z.string().min(10)` e reusar em outro schema), gera erros estruturados por campo (não uma string concatenada), e — em um projeto com TypeScript — dá tipagem estática automática do resultado, eliminando uma classe inteira de bugs de "esqueci de checar esse campo antes de usar".

---

## Resumo

- Validação manual com `if`s resolve o problema imediato, mas não resolve o problema estrutural: dados vindos de fora do seu programa não têm garantia de formato, e você precisa de um único portão consistente de validação, não `if`s espalhados
- Zod descreve schemas declarativamente e os usa tanto para validar em runtime quanto para derivar tipos estáticos — as duas metades do mesmo problema, resolvidas juntas
- `safeParse` para dados de usuário (erro esperado, trate com uma resposta HTTP); `parse` para configuração interna como variáveis de ambiente (erro inesperado, derrube o processo)
- Schemas compõem: `.optional()`, `.partial()`, `.extend()` permitem reaproveitar definições sem duplicar lógica
- O mesmo princípio de validação de schema deveria ser aplicado em toda fronteira de entrada de dados: `req.body`, `req.query`, `process.env`, respostas de APIs externas
- O contrato de resposta de erro da API (`{ erro, detalhes }`) se mantém — trocar o motor de validação por baixo não muda o que o cliente da API recebe
