# Correção — O Problema de N+1 Queries

## O que estava errado, e por que ele é o tipo de bug mais traiçoeiro que existe

Esse problema nunca foi mencionado no curso, e isso é grave por um motivo específico: **N+1 é um bug de performance que não aparece em nenhum teste manual, não aparece com poucos dados, e só se manifesta exatamente no momento em que o projeto tem sucesso** — quando o volume de dados cresce. É o tipo de problema que passa despercebido em desenvolvimento, passa despercebido em code review se ninguém souber procurar por ele, e vira um incêndio em produção.

Vamos entender exatamente o que é, por que ele nasce naturalmente do jeito como a maioria das pessoas pensa sobre buscar "uma lista de coisas, cada uma com seus detalhes relacionados", e como resolvê-lo de duas formas diferentes, cada uma certa em contextos diferentes.

---

## O que é, mecanicamente

Imagine que você quer listar os posts do feed do Linkr, e para cada post, mostrar quantas curtidas ele tem. A forma mais natural — e mais perigosa — de escrever isso é:

```js
// ❌ Isso é uma N+1 query, mesmo parecendo um código razoável
async function buscarFeedComCurtidas() {
  // 1 query: busca os posts
  const posts = await query('SELECT * FROM posts ORDER BY criado_em DESC LIMIT 20')

  // N queries: uma PARA CADA post, dentro do loop
  const postsComCurtidas = await Promise.all(
    posts.rows.map(async post => {
      const { rows } = await query(
        'SELECT COUNT(*) AS total FROM curtidas WHERE post_id = $1',
        [post.id]
      )
      return { ...post, totalCurtidas: rows[0].total }
    })
  )

  return postsComCurtidas
}
```

Conte as queries que esse código realmente executa: **1** para buscar os 20 posts, mais **20** (uma para cada post, dentro do `.map()`) para buscar as curtidas de cada um. Total: **21 queries** para uma única resposta HTTP. Esse é o "N+1": 1 query inicial, mais N queries adicionais, uma para cada item do resultado da primeira.

Com 20 posts, isso ainda "funciona" — lento, mas funciona, porque o banco de dados local responde em menos de 1ms por query e ninguém percebe a diferença testando manualmente. O problema é que **o número de queries escala linearmente com o número de resultados**. Com 200 posts na página, são 201 queries. Com um endpoint de admin que lista 5.000 registros, são 5.001 queries — e cada uma delas tem overhead de rede real (mesmo que pequeno, multiplicado por 5.000 deixa de ser pequeno), além de competir por conexões limitadas no pool.

---

## Por que isso nasce naturalmente — a armadilha psicológica

Ninguém escreve N+1 de propósito. Ele nasce porque a forma mais natural de **pensar** sobre o problema ("para cada post, eu preciso buscar as curtidas dele") se traduz diretamente, sem fricção, em código que faz literalmente isso — um loop, com uma busca dentro. O código até parece limpo e legível: você lê `posts.map(post => buscarCurtidas(post.id))` e entende exatamente a intenção.

O problema é que essa forma de pensar ignora uma diferença fundamental entre **memória** e **banco de dados**: iterar sobre um array em memória e chamar uma função para cada item é praticamente grátis, porque não há latência de rede envolvida. Fazer o equivalente com queries de banco de dados não é grátis — cada query, mesmo rápida, tem overhead de round-trip. `Promise.all` até paraleliza as chamadas, o que ajuda um pouco, mas não elimina o problema: você ainda está abrindo N operações de rede quando deveria ter usado uma.

---

## A solução 1: JOIN — trazer tudo em uma única query

Quando os dados relacionados podem ser expressos como uma junção de tabelas (que é exatamente o caso de "post + contagem de curtidas"), a resposta correta é deixar o banco de dados fazer esse trabalho, porque é exatamente para isso que bancos relacionais existem — eles são otimizados para combinar dados de múltiplas tabelas de forma eficiente, com índices, muito melhor do que você conseguiria fazendo isso manualmente em JavaScript.

```js
// ✅ Uma única query, usando JOIN + GROUP BY
async function buscarFeedComCurtidas() {
  const { rows } = await query(`
    SELECT
      p.id,
      p.titulo,
      p.url,
      p.criado_em,
      COUNT(c.id) AS total_curtidas
    FROM posts p
    LEFT JOIN curtidas c ON c.post_id = p.id
    GROUP BY p.id
    ORDER BY p.criado_em DESC
    LIMIT 20
  `)

  return rows
}
```

Isso é **1 query**, não 21. O `LEFT JOIN` conecta cada post às suas curtidas (posts sem nenhuma curtida ainda aparecem, com `total_curtidas = 0`, por isso `LEFT` e não `INNER`), e o `GROUP BY p.id` agrupa as linhas resultantes por post, permitindo que `COUNT(c.id)` conte quantas curtidas cada post específico tem.

Isso não é uma técnica nova para você — é exatamente o padrão que já apareceu na aula de PostgreSQL do curso (`COLUNAS_POST` com `COUNT(DISTINCT c.id)`), mas nunca foi conectado explicitamente ao **motivo** de existir: ele já era a solução certa para N+1, só que sem o nome do problema que estava sendo resolvido.

### Quando JOIN não é suficiente — dados que não colapsam em uma linha

JOIN funciona bem quando o dado relacionado pode ser **agregado** em um valor único por linha (uma contagem, uma soma, um booleano de "existe ou não"). Mas às vezes você quer a **lista completa** de itens relacionados, não um resumo — por exemplo, os últimos 5 comentários de cada post em uma listagem. Isso não colapsa bem em um JOIN simples, porque um post com 5 comentários geraria 5 linhas na junção, distorcendo a contagem de posts e exigindo agregação em JSON (possível no PostgreSQL, mas mais complexo). Para esses casos, a solução correta é a segunda técnica.

---

## A solução 2: Batching — uma query extra, não N

Quando o relacionamento não colapsa bem em JOIN, a técnica certa ainda não é voltar para uma query por item — é fazer **uma segunda query, buscando todos os relacionados de uma vez**, e depois combinar os resultados em memória (o que, como já vimos, é rápido e sem custo real).

```js
// ✅ 2 queries no total, não 1 + N
async function buscarFeedComComentariosRecentes() {
  // Query 1: busca os posts
  const { rows: posts } = await query(
    'SELECT * FROM posts ORDER BY criado_em DESC LIMIT 20'
  )

  const postIds = posts.map(p => p.id)

  if (postIds.length === 0) return []

  // Query 2: busca TODOS os comentários de TODOS esses posts, de uma vez
  // ANY($1) compara o post_id contra cada elemento do array — equivalente
  // a um WHERE post_id IN (id1, id2, id3, ...) mas mais seguro com parâmetros
  const { rows: comentarios } = await query(
    `SELECT id, texto, post_id, criado_em
     FROM comentarios
     WHERE post_id = ANY($1)
     ORDER BY criado_em DESC`,
    [postIds]
  )

  // Combina em memória — isso é rápido, não envolve rede
  const comentariosPorPost = comentarios.reduce((mapa, c) => {
    if (!mapa[c.post_id]) mapa[c.post_id] = []
    if (mapa[c.post_id].length < 5) mapa[c.post_id].push(c)  // só os 5 mais recentes
    return mapa
  }, {})

  return posts.map(post => ({
    ...post,
    comentariosRecentes: comentariosPorPost[post.id] || []
  }))
}
```

Repare na estrutura: **2 queries totais**, independente de quantos posts existirem. Se forem 20 posts ou 2.000, ainda são exatamente 2 queries — a primeira busca os posts, a segunda busca *todos* os comentários relacionados a *todos* esses posts de uma vez, usando `WHERE post_id = ANY($1)` (o equivalente do PostgreSQL para "está contido nesta lista"). A combinação dos dois resultados — decidir qual comentário pertence a qual post — acontece em JavaScript, em memória, o que é essencialmente instantâneo comparado a uma query de rede.

Esse padrão tem nome na literatura de bancos de dados e é chamado de **batching** ou **dataloader pattern** (o nome vem de uma biblioteca do Facebook, `dataloader`, criada originalmente para resolver esse exato problema em APIs GraphQL, onde N+1 é ainda mais fácil de introduzir acidentalmente).

---

## Como reconhecer N+1 no seu próprio código — o padrão a procurar

A assinatura visual mais confiável de N+1 é: **uma chamada `await` (ou uma query) dentro de um `.map()`, `.forEach()`, ou loop `for`, onde o array sendo iterado veio de uma query anterior.**

```js
// Esse padrão, sempre que você o vir, é um sinal de alerta
const resultado = await Promise.all(
  itensDeUmaQueryAnterior.map(async item => {
    return await outraQuery(item.id)   // ← isso roda uma vez POR item
  })
)
```

Não é proibido rodar uma query dentro de um loop — existem casos legítimos (por exemplo, operações que precisam mesmo ser sequenciais e têm efeitos colaterais diferentes cada uma). Mas toda vez que você reconhecer esse padrão especificamente para **buscar dados relacionados de forma somente-leitura**, pare e pergunte: "isso pode virar um único JOIN, ou um único batching com `WHERE id = ANY(...)`?" Na esmagadora maioria dos casos de leitura, a resposta é sim.

---

## Ferramentas que ajudam a detectar N+1 automaticamente

Em projetos com ORMs (Prisma, Sequelize, TypeORM), N+1 é ainda mais fácil de introduzir sem perceber, porque o ORM esconde a query por trás de uma chamada que parece inofensiva, como `post.autor` acessado dentro de um loop. Como o curso usa SQL direto via `pg`, você não tem esse risco escondido — mas em compensação, também não tem uma ferramenta de ORM avisando automaticamente.

A forma prática de detectar N+1 no seu próprio projeto, sem depender de ferramentas externas:

```js
// Ative o log de queries do driver pg temporariamente durante desenvolvimento
const { Pool } = require('pg')

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  // Não existe um "log: true" nativo no pg — a forma mais direta é
  // logar manualmente toda vez que query() for chamada
})

const queryOriginal = pool.query.bind(pool)
pool.query = async (...args) => {
  console.log('[SQL]', args[0].slice(0, 80))  // primeiros 80 chars da query
  return queryOriginal(...args)
}
```

Com isso, rodando um endpoint suspeito no ambiente de desenvolvimento, você literalmente **vê no terminal** se uma única requisição HTTP está dispando 1 query ou 21. Esse tipo de instrumentação simples, olhada durante o desenvolvimento de qualquer endpoint que envolva listas com dados relacionados, é o hábito que evita que N+1 chegue em produção.

---

## Aplicando ao repositório de posts do Linkr

```js
// src/repositories/posts.repository.js — versão que evita N+1 desde o início

// Feed com curtidas e comentários — TUDO em uma única query, via JOIN + agregação
async function buscarTodos({ pagina = 1, porPagina = 10 } = {}) {
  const limite = Math.min(50, Number(porPagina))
  const offset = (Math.max(1, Number(pagina)) - 1) * limite

  // Uma única query resolve posts + autor + contagem de curtidas +
  // contagem de comentários, tudo de uma vez — isso é o que já estava
  // certo na correção de PostgreSQL, agora com o nome do problema
  // que essa estrutura evita: N+1
  const { rows: dados } = await query(`
    SELECT
      p.id, p.titulo, p.url, p.descricao, p.criado_em,
      u.id AS autor_id, u.nome AS autor_nome, u.username AS autor_username,
      COUNT(DISTINCT c.id)  AS total_curtidas,
      COUNT(DISTINCT cm.id) AS total_comentarios
    FROM posts p
    JOIN usuarios u          ON p.usuario_id = u.id
    LEFT JOIN curtidas c      ON c.post_id = p.id
    LEFT JOIN comentarios cm  ON cm.post_id = p.id
    GROUP BY p.id, u.id
    ORDER BY p.criado_em DESC
    LIMIT $1 OFFSET $2
  `, [limite, offset])

  return dados
}

// Se precisar dos ÚLTIMOS 3 COMENTÁRIOS de cada post (não só a contagem),
// isso não colapsa em JOIN — usa batching com uma segunda query
async function buscarComUltimosComentarios(posts) {
  const postIds = posts.map(p => p.id)
  if (postIds.length === 0) return posts

  const { rows: comentarios } = await query(`
    SELECT DISTINCT ON (post_id) post_id, texto, criado_em
    FROM comentarios
    WHERE post_id = ANY($1)
    ORDER BY post_id, criado_em DESC
  `, [postIds])
  // DISTINCT ON (post_id) é um recurso específico do PostgreSQL:
  // pega só a primeira linha de cada grupo de post_id, respeitando o ORDER BY
  // — aqui, o comentário mais recente de cada post, em uma única query

  const comentarioPorPost = Object.fromEntries(
    comentarios.map(c => [c.post_id, c])
  )

  return posts.map(post => ({
    ...post,
    ultimoComentario: comentarioPorPost[post.id] || null
  }))
}
```

---

## Resumo

- N+1 é o padrão de 1 query inicial seguida de N queries adicionais, uma por item do resultado — nasce naturalmente de pensar "para cada item, busco o relacionado" e traduzir isso direto em um loop com query dentro
- O número de queries escala linearmente com o volume de dados — por isso o bug é invisível em desenvolvimento (poucos registros) e se torna crítico exatamente quando o projeto cresce
- Quando o dado relacionado colapsa em um valor agregado por linha (contagem, soma, existência), a solução é JOIN + GROUP BY em uma única query
- Quando o dado relacionado é uma lista que não colapsa bem (últimos N comentários, por exemplo), a solução é batching: uma segunda query com `WHERE coluna = ANY($1)`, combinando os resultados em memória depois — total de 2 queries, não 1+N
- O sinal de alerta a procurar no próprio código: uma chamada de query dentro de `.map()`/`.forEach()`/loop, iterando sobre resultado de uma query anterior
- Instrumentar temporariamente o `pool.query` para logar cada SQL disparado é uma forma simples de literalmente ver quantas queries uma requisição está gerando, durante o desenvolvimento
