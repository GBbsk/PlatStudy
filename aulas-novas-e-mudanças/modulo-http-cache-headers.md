# Módulo Extra — Cache HTTP: `Cache-Control` e `ETag`

## Fontes deste módulo

- **RFC 7234** — "Hypertext Transfer Protocol (HTTP/1.1): Caching", a especificação formal do IETF que define `Cache-Control` e a semântica de cache em HTTP
- **RFC 7232** — "Hypertext Transfer Protocol (HTTP/1.1): Conditional Requests", especificação que define `ETag`, `If-None-Match` e requisições condicionais
- **MDN Web Docs (developer.mozilla.org)** — a referência mais usada na indústria para documentação de headers HTTP, mantida pela Mozilla com contribuição ativa da comunidade
- Nota de transparência: mesma ressalva dos módulos anteriores — isto é conhecimento estável do meu treinamento sobre um protocolo padronizado há décadas, não resultado de busca ativa nesta conversa.

---

## O que estava faltando, e por que é a "outra metade" do cache que você aprendeu

No módulo anterior, você aprendeu cache no **servidor** — Redis guardando resultado de queries para não repetir trabalho no banco. Existe uma camada de cache completamente diferente, que acontece **no cliente** (navegador, ou qualquer HTTP client) e que é parte do próprio protocolo HTTP, não uma ferramenta externa. Você já estudou HTTP a fundo — verbos, status codes, headers de autenticação — mas nunca os headers que controlam cache, que são igualmente parte do protocolo, formalizados nas RFCs 7234 e 7232.

---

## Onde esse cache vive, e por que ele é diferente do Redis

```
Cliente (navegador)  ←──── requisição ────→  Seu servidor  ←──── query ────→  Banco
       ↑
   Cache HTTP vive AQUI — no cliente, ou em um proxy/CDN no meio do caminho
```

O cache do Redis evita que **seu servidor** repita trabalho ao consultar o banco. O cache HTTP evita que o **cliente** precise sequer fazer uma nova requisição — ou, quando precisa confirmar se algo mudou, evita que o **servidor precise reenviar o corpo inteiro da resposta** se nada mudou. São dois níveis diferentes da mesma ideia (evitar trabalho redundante), atuando em pontos diferentes do caminho entre cliente e banco de dados.

---

## `Cache-Control` — a resposta do servidor dizendo por quanto tempo o cliente pode confiar

```
Cache-Control: max-age=3600
```

Isso diz ao cliente: "você pode reutilizar esta resposta, sem fazer nenhuma nova requisição, por até 3600 segundos (1 hora)". Durante essa janela, o navegador nem tenta contatar o servidor de novo — ele usa a cópia local, o que é ainda mais rápido que o cache-aside do Redis, porque elimina a viagem de rede inteira, não só o trabalho do banco de dados.

```js
// Express — definindo Cache-Control em uma resposta
app.get('/api/v1/categorias', asyncHandler(async (req, res) => {
  const categorias = await categoriasRepo.buscarTodas()

  // Categorias mudam raramente — cache agressivo faz sentido aqui
  res.set('Cache-Control', 'public, max-age=3600')
  res.json(categorias)
}))
```

```
Diretivas comuns de Cache-Control:

public              → pode ser cacheado por qualquer intermediário (CDN, proxy),
                       não só o navegador do usuário final
private             → só o navegador do usuário final pode cachear —
                       apropriado para dados específicos de UM usuário
no-cache            → o cliente PODE guardar a resposta, mas deve sempre
                       revalidar com o servidor antes de reutilizá-la
                       (nome enganoso — não significa "não cacheie nunca")
no-store            → nunca guarde essa resposta em cache algum,
                       em lugar nenhum — para dados verdadeiramente sensíveis
max-age=N           → por quantos segundos a resposta é considerada "fresca"
```

```js
// Dados sensíveis de autenticação NUNCA devem ser cacheados
app.get('/api/v1/auth/me', autenticar, asyncHandler(async (req, res) => {
  res.set('Cache-Control', 'no-store')
  res.json(usuario)
}))
```

---

## `ETag` — uma "impressão digital" do conteúdo, para revalidação eficiente

`max-age` funciona bem para dados que mudam raramente e previsivelmente. Mas e quando você não sabe de antemão quanto tempo o dado vai ficar válido? `ETag` resolve isso de um jeito diferente: em vez de dizer "confie por X segundos", o servidor gera um hash (a "impressão digital") do conteúdo, e o cliente usa esse hash para perguntar, de forma barata, "isso ainda é a versão mais atual?"

```
Primeira requisição:

Cliente → GET /api/v1/posts/abc123
Servidor → 200 OK
           ETag: "a1b2c3d4"
           [corpo completo da resposta, com todos os dados do post]
```

```
Requisição seguinte, o cliente já tem essa versão em cache local:

Cliente → GET /api/v1/posts/abc123
           If-None-Match: "a1b2c3d4"     ← "eu já tenho esta versão, mudou?"

Servidor calcula o ETag atual do post:
  Se for IGUAL ao que o cliente mandou → 304 Not Modified (SEM corpo nenhum)
  Se for DIFERENTE → 200 OK, com o corpo completo da nova versão e um novo ETag
```

O ganho aqui é sutil mas real: numa resposta `304 Not Modified`, o servidor **não reenvia o corpo da resposta** — só confirma que o que o cliente já tem continua válido. Para um post com uma descrição longa ou uma lista grande de comentários, isso economiza banda real, mesmo que o servidor ainda precise processar a requisição para calcular o ETag e compará-lo.

```js
// Express tem suporte nativo a ETag — habilitado por padrão em res.json()
// quando você usa um pacote como 'etag', ou implementando manualmente:

const crypto = require('crypto')

app.get('/api/v1/posts/:id', asyncHandler(async (req, res) => {
  const post = await postsRepo.buscarPorId(req.params.id)
  if (!post) return res.status(404).json({ erro: 'Post não encontrado' })

  const conteudo = JSON.stringify(post)
  const etagAtual = crypto.createHash('md5').update(conteudo).digest('hex')

  // Compara com o que o cliente já tinha
  if (req.headers['if-none-match'] === etagAtual) {
    return res.status(304).end()   // sem corpo — o cliente já tem a versão certa
  }

  res.set('ETag', etagAtual)
  res.json(post)
}))
```

---

## Por que os dois existem — não são a mesma coisa, resolvem problemas complementares

```
Cache-Control (max-age):
  "Confie nisso por X tempo, sem NENHUMA requisição nova"
  Mais eficiente (zero requisições durante a janela de confiança)
  Risco: pode servir dado desatualizado até o max-age expirar

ETag (If-None-Match):
  "Faça a requisição, mas deixe o servidor decidir barato se precisa reenviar tudo"
  Sempre há uma requisição de rede, mas o corpo só é reenviado se mudou
  Mais preciso (nunca serve dado realmente desatualizado sem saber)
```

Na prática, sistemas de produção real combinam os dois: `Cache-Control` com um `max-age` curto (para não sobrecarregar o servidor com validações constantes) e `ETag` como rede de segurança para quando o cliente precisa revalidar depois que o `max-age` expira.

```
Cache-Control: public, max-age=60
ETag: "a1b2c3d4"
```

```
Fluxo combinado:

0-60s:   cliente usa a cópia local, ZERO requisições (Cache-Control)
Após 60s: cliente faz uma requisição de revalidação com If-None-Match
          Se nada mudou → 304, sem reenviar o corpo (ETag)
          Se mudou → 200, com o corpo novo e um ETag novo
```

---

## Conectando explicitamente ao Redis (o módulo anterior)

Vale entender onde cada camada de cache atua, porque elas não competem — se somam:

```
Cliente                Servidor                    Redis          PostgreSQL
   │                        │                         │                │
   │──── GET /posts/1 ─────→│                         │                │
   │  (sem cache local,      │                         │                │
   │   ou expirado)          │──── verifica cache ────→│                │
   │                        │←──── MISS ───────────────│                │
   │                        │────────── query real ───────────────────→│
   │                        │←───────── resultado ──────────────────────│
   │                        │──── salva no Redis ──────→│                │
   │←── 200 + Cache-Control ─│                         │                │
   │     + ETag              │                         │                │
```

O `Cache-Control`/`ETag` evita que o **cliente** precise nem perguntar de novo. O Redis evita que, quando o cliente **precisa** perguntar (porque o cache dele expirou), o **servidor** precise ir até o banco de novo. Cada camada resolve o mesmo problema geral (evitar trabalho redundante) em um ponto diferente da cadeia.

---

## Resumo

- Cache HTTP (RFC 7234, RFC 7232) é uma camada de cache diferente do Redis — vive no cliente ou em intermediários de rede (CDN), não no seu servidor
- `Cache-Control: max-age=N` diz ao cliente para reutilizar a resposta por N segundos sem nenhuma nova requisição — o mecanismo mais eficiente, mas com risco de servir dado desatualizado dentro dessa janela
- `Cache-Control: private` para dados de um único usuário; `public` para dados cacheáveis por qualquer intermediário; `no-store` para dados sensíveis que nunca devem ser guardados em cache algum
- `ETag` + `If-None-Match` (RFC 7232) permite revalidação barata: o cliente pergunta "isso mudou?" e o servidor responde `304 Not Modified` sem reenviar o corpo, se nada mudou
- Produção real combina os dois: `max-age` curto para reduzir requisições, `ETag` como revalidação eficiente depois que o `max-age` expira
- Essa camada de cache é complementar ao Redis, não concorrente — cada uma atua em um ponto diferente do caminho entre cliente e banco de dados
