# Correção — Migrations Versionadas

## O que estava errado, e por que só aparece quando já é tarde demais

O curso ensinou isso como "migrations":

```js
async function executarMigrations() {
  await query(`
    CREATE TABLE IF NOT EXISTS usuarios (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      nome TEXT NOT NULL,
      ...
    )
  `)
}
```

Isso não é uma migration. É um script de inicialização idempotente — ele garante que a tabela existe, e é seguro rodar várias vezes porque `IF NOT EXISTS` não falha se ela já existir. Isso é útil, mas resolve só uma fatia pequena do problema real que migrations existem para resolver, e a fatia que ele não resolve é exatamente a que aparece quando o projeto já tem gente usando ele de verdade.

O sintoma de que algo está errado nunca aparece em desenvolvimento solo, com um banco vazio que você recria a hora que quiser. Ele aparece no primeiro dia em que:

- Você precisa **adicionar uma coluna** a uma tabela que já tem dados reais
- Um **segundo desenvolvedor** entra no projeto com um banco local diferente do seu
- Você precisa saber **em que estado exato** está o banco de produção, comparado ao de staging
- Algo deu errado e você precisa **reverter** uma mudança de schema sem perder dados

`CREATE TABLE IF NOT EXISTS` não responde a nenhuma dessas perguntas. Ele só responde "a tabela existe?" — um sim/não binário, sem nenhuma noção de *quais mudanças* já foram aplicadas e em que ordem.

---

## O problema central: schema é estado, e estado precisa de histórico

Pense no paralelo mais próximo que você já conhece bem: **Git**. Se você não tivesse histórico de commits — só um botão "salvar estado atual do arquivo" — você não conseguiria saber o que mudou entre duas versões, não conseguiria reverter uma mudança específica sem perder as outras, e duas pessoas trabalhando no mesmo arquivo não teriam como saber se estão na mesma versão.

Schema de banco de dados tem exatamente o mesmo problema estrutural. O schema de um banco **é um estado que muda ao longo do tempo**, e cada mudança (adicionar uma coluna, criar um índice, alterar um tipo) precisa ser:

1. **Registrada** — o que mudou, exatamente
2. **Ordenada** — em que sequência as mudanças aconteceram
3. **Idempotente** — pode ser aplicada de novo sem quebrar se já foi aplicada
4. **Reversível** (idealmente) — existe um caminho de volta se precisar desfazer

`CREATE TABLE IF NOT EXISTS` cumpre parcialmente o item 3, e nenhum dos outros três. Isso é o "castelo de cartas": funciona perfeitamente enquanto você é a única pessoa, com o único banco, que nunca precisou alterar uma tabela que já tinha dados. No momento em que qualquer uma dessas condições muda, o sistema desmorona.

---

## O que uma ferramenta de migrations real resolve

Uma migration de verdade é um **arquivo versionado**, com um nome que embute a ordem (geralmente um timestamp), contendo o SQL de "ir para frente" e, idealmente, o de "voltar":

```
migrations/
├── 20240115143000_criar_usuarios.sql
├── 20240115143530_criar_posts.sql
├── 20240120091500_adicionar_bio_usuarios.sql
└── 20240122160000_criar_indice_posts_criado_em.sql
```

O nome do arquivo carrega a ordem cronológica. A ferramenta de migration mantém, dentro do próprio banco, uma tabela de controle (geralmente chamada `schema_migrations` ou `migrations`) que registra **quais desses arquivos já foram executados naquele banco específico**:

```sql
-- Tabela que a ferramenta de migration cria e gerencia automaticamente
CREATE TABLE schema_migrations (
  versao     TEXT PRIMARY KEY,
  aplicada_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Quando você roda o comando de migrate, a ferramenta:

1. Olha essa tabela e vê quais versões já foram aplicadas naquele banco
2. Compara com os arquivos de migration que existem no projeto
3. Executa **só os que ainda não foram aplicados**, na ordem correta
4. Registra cada um como aplicado, para não rodar de novo

Isso resolve exatamente os quatro pontos que `CREATE TABLE IF NOT EXISTS` não resolve: cada mudança é um arquivo (registrada), a ordem é explícita no nome (ordenada), rodar de novo não faz nada porque a tabela de controle já sabe o que foi aplicado (idempotente), e cada migration pode ter uma contraparte de reversão (reversível).

---

## Ferramenta: node-pg-migrate

Para o stack do curso (Node + PostgreSQL + `pg`), a ferramenta mais direta e sem excesso de abstração é `node-pg-migrate`.

```bash
npm install -D node-pg-migrate
```

```json
// package.json
{
  "scripts": {
    "migrate":      "node-pg-migrate",
    "migrate:up":   "node-pg-migrate up",
    "migrate:down": "node-pg-migrate down",
    "migrate:create": "node-pg-migrate create"
  }
}
```

```env
# .env — a ferramenta lê DATABASE_URL diretamente
DATABASE_URL=postgresql://postgres:senha@localhost:5432/linkr
```

### Criando a primeira migration

```bash
npm run migrate:create -- criar-tabela-usuarios
```

Isso gera um arquivo com timestamp automático:

```js
// migrations/1705329001234_criar-tabela-usuarios.js

exports.up = pgm => {
  pgm.createExtension('pgcrypto', { ifNotExists: true })

  pgm.createTable('usuarios', {
    id:         { type: 'uuid', primaryKey: true, default: pgm.func('gen_random_uuid()') },
    nome:       { type: 'text', notNull: true },
    username:   { type: 'text', notNull: true, unique: true },
    email:      { type: 'text', notNull: true, unique: true },
    bio:        { type: 'text' },
    senha_hash: { type: 'text', notNull: true },
    criado_em:  { type: 'timestamptz', notNull: true, default: pgm.func('now()') }
  })
}

// down é o INVERSO exato do up — como desfazer esta migration especificamente
exports.down = pgm => {
  pgm.dropTable('usuarios')
}
```

Repare no par `up`/`down`. Isso é o que Git faz com um commit e seu revert: toda mudança tem uma operação inversa explícita, escrita por quem entende a mudança, não inferida automaticamente por uma ferramenta que poderia errar.

### A migration que expõe o problema real: adicionar uma coluna depois

```bash
npm run migrate:create -- adicionar-bio-usuarios
```

```js
// migrations/1705415401000_adicionar-bio-usuarios.js

exports.up = pgm => {
  pgm.addColumn('usuarios', {
    telefone: { type: 'text' }
  })
}

exports.down = pgm => {
  pgm.dropColumn('usuarios', 'telefone')
}
```

Esse é exatamente o cenário que `CREATE TABLE IF NOT EXISTS` não resolve. Se você tivesse escrito o schema original com a tabela já criada, e depois precisasse adicionar `telefone`, a abordagem antiga do curso não tinha absolutamente nenhum mecanismo para isso — você precisaria editar manualmente o `CREATE TABLE` original (que não executa de novo, porque a tabela já existe) e rodar um `ALTER TABLE` à parte, sem nenhum registro de que isso aconteceu, sem nenhuma forma de saber se aquele `ALTER TABLE` específico já rodou naquele banco ou não.

Com migrations, você simplesmente cria um novo arquivo. Ele é uma unidade de mudança independente, com sua própria ordem, seu próprio registro de execução, e seu próprio caminho de reversão.

### Executando

```bash
# Aplica todas as migrations pendentes, na ordem
$ npm run migrate:up

> Migrating files:
> - 1705329001234_criar-tabela-usuarios
> - 1705415401000_adicionar-bio-usuarios
migrated up ok

# Reverte a última migration aplicada
$ npm run migrate:down

> Migrating files:
> - 1705415401000_adicionar-bio-usuarios
migrated down ok
```

---

## Como isso muda o fluxo de trabalho em equipe

Este é o ponto que só faz sentido quando você imagina um segundo desenvolvedor entrando no projeto — que é exatamente o cenário que o curso nunca simulou, porque foi construído para uma pessoa só.

```
Sem migrations versionadas:
  Dev A cria uma coluna nova, direto no banco dele, sem deixar rastro no código
  Dev B clona o repositório
  Dev B roda o projeto — o banco dele NÃO tem a coluna que o Dev A criou
  O código de Dev A, que já espera aquela coluna, quebra na máquina de Dev B
  Ninguém sabe exatamente qual é a diferença entre os dois bancos

Com migrations versionadas:
  Dev A cria uma migration nova, commita o ARQUIVO no Git junto com o código que a usa
  Dev B faz git pull
  Dev B roda `npm run migrate:up`
  O banco de Dev B agora tem exatamente as mesmas mudanças de schema que o de Dev A
  O histórico de migrations no repositório é a fonte da verdade do schema,
  não a memória de ninguém
```

Isso é o motivo pelo qual toda migration deve ser commitada no Git **junto com** o código que depende dela — a migration é parte do código, não uma operação manual feita "por fora" e esquecida.

---

## Deploy — migrations em produção

```json
// package.json — o comando de start em produção roda migrations antes de subir o servidor
{
  "scripts": {
    "start": "npm run migrate:up && node src/index.js"
  }
}
```

Isso parece igual ao que o curso já fazia com `executarMigrations()` chamado no `index.js` — e a intenção é a mesma (garantir que o schema está atualizado antes de aceitar tráfego). A diferença é que agora **cada mudança de schema em produção é rastreável**: você sabe exatamente quais migrations já rodaram em produção, consultando a tabela `pgmigrations` (nome default da tabela de controle) diretamente:

```sql
SELECT * FROM pgmigrations ORDER BY run_on DESC;

--  name                                | run_on
-- -------------------------------------|------------------------
--  1705415401000_adicionar-bio-usuarios | 2024-01-16 09:15:00
--  1705329001234_criar-tabela-usuarios  | 2024-01-15 14:30:01
```

Se um deploy falhar no meio de uma migration (por exemplo, a conexão cair), você sabe exatamente qual migration ficou pendente, e pode investigar e reaplicar só ela — em vez de reexecutar um script gigante de `CREATE TABLE IF NOT EXISTS` inteiro e torcer para que nada quebre por já existir parcialmente.

---

## Substituindo o `migrations.js` do curso

```js
// src/database/migrations.js — REMOVER este arquivo inteiro

// A lógica que estava aqui (CREATE TABLE IF NOT EXISTS para cada tabela)
// se torna, em vez disso, uma sequência de arquivos individuais em migrations/,
// um por mudança de schema, gerenciados pelo node-pg-migrate.
```

```js
// src/index.js — a chamada de migrations muda de forma
// ANTES:
const { executarMigrations } = require('./database/migrations')
await executarMigrations()

// DEPOIS: migrations não rodam mais dentro do código da aplicação —
// elas rodam como um passo SEPARADO, antes do processo Node iniciar
// (via npm run migrate:up no script "start", como mostrado acima)
// O index.js não precisa mais saber nada sobre migrations
```

Essa mudança também resolve um problema sutil de arquitetura: misturar "lógica de aplicação" com "lógica de gestão de schema" no mesmo processo significa que toda subida do servidor recalcula e reexecuta comandos DDL — operações que deveriam ser deliberadas e raras, não acopladas ao ciclo de vida normal de start do servidor.

---

## Resumo

- `CREATE TABLE IF NOT EXISTS` garante que a tabela existe, mas não tem noção de histórico, ordem, ou reversão — resolve só uma fatia do problema de gerenciar schema ao longo do tempo
- Schema de banco é estado que muda continuamente, e estado que muda precisa de histórico — o mesmo princípio que justifica a existência do Git para código
- Migrations versionadas (um arquivo por mudança, com timestamp no nome, par `up`/`down`) resolvem os quatro requisitos que faltavam: registro, ordem, idempotência e reversão
- `node-pg-migrate` mantém uma tabela de controle no próprio banco (`pgmigrations`) que registra o que já foi aplicado — rodar `migrate:up` de novo só executa o que está pendente
- Migrations devem ser commitadas no Git junto com o código que depende delas — são parte do código, não uma operação manual à parte
- Em produção, `migrate:up` roda como parte do processo de deploy, não dentro do código da aplicação — separando gestão de schema (deliberada, rara) do ciclo de vida do servidor (frequente, automático)
