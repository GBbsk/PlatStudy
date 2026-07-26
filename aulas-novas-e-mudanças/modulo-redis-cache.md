# Módulo Extra — Redis como Cache (Cache-Aside Pattern)

## Fontes deste módulo

- **Documentação oficial do Redis** — redis.io/docs (particularmente a seção de estruturas de dados e expiração de chaves)
- **"Designing Data-Intensive Applications", Martin Kleppmann, O'Reilly, 2017** — capítulo 3 discute caching e o tradeoff entre consistência e performance; é a referência mais citada da indústria sobre esse tema
- **"System Design Interview", Alex Xu, 2020** — cobre o padrão cache-aside especificamente no contexto de arquitetura de sistemas web, com diagramas de fluxo similares ao que será usado aqui
- Nota de transparência: como nos módulos anteriores, esta é uma síntese do meu conhecimento de treinamento, não resultado de busca ativa nesta conversa.

---

## O que estava faltando, e por que Redis-só-para-rate-limit é um uso incompleto

No curso, Redis apareceu uma única vez: como store para rate limiting distribuído. Isso é um uso legítimo, mas é uma fração pequena do motivo pelo qual Redis é tão presente em arquiteturas de produção. O uso mais comum, de longe, é **cache** — e esse uso conecta diretamente com um problema que você já nomeou e resolveu parcialmente: N+1 queries.

---

## O paralelo com N+1 que você já entende

Lembra do problema de N+1: fazer a mesma categoria de trabalho repetidamente quando uma única operação resolveria. N+1 acontece **dentro de uma única requisição** (buscar curtidas de cada post, um por um, em vez de uma vez só). Cache resolve um problema irmão, mas que acontece **entre requisições diferentes, ao longo do tempo**: se 1.000 usuários pedem o mesmo feed de posts populares no mesmo minuto, seu banco de dados processa a mesma query pesada 1.000 vezes, mesmo que o resultado seja idêntico para todos eles.

```
N+1 (dentro de uma requisição):
  1 requisição → 21 queries ao banco (uma por item de uma lista)

Falta de cache (entre requisições):
  1.000 requisições idênticas → 1.000 execuções da MESMA query pesada,
  mesmo que o resultado não tenha mudado entre a primeira e a última
```

Os dois problemas têm a mesma raiz filosófica: trabalho redundante que poderia ter sido evitado, porque o resultado já era conhecido ou previsível.

---

## Por que Redis, especificamente, e não guardar isso em uma variável no Node

Você poderia pensar: "por que não guardar o resultado em uma variável JavaScript, em memória, no próprio processo Node?" Essa técnica existe e se chama *in-memory caching* — e ela tem exatamente a mesma limitação que você já viu com rate limiting em memória: **não funciona com múltiplas instâncias**. Se você escalar sua aplicação para dois processos (dois containers, duas réplicas), cada um teria seu próprio cache isolado, desperdiçando a oportunidade de reaproveitar o trabalho já feito por outra instância, e pior — os dois caches poderiam ficar dessincronizados entre si.

Redis resolve isso sendo um serviço **externo e compartilhado**: todas as instâncias da sua aplicação leem e escrevem no mesmo Redis, então o cache é efetivamente único, não importa quantas réplicas do Node estejam rodando.

```
Sem Redis (cache em memória do Node):
  Instância A: cache = { feed: [...] }
  Instância B: cache = {}   ← vazio, não sabe do cache da A

Com Redis (cache compartilhado):
  Instância A e B leem/escrevem no MESMO Redis
  O cache é efetivamente um só, visível para todas as instâncias
```

---

## O padrão Cache-Aside — o mais comum na indústria

Existem várias estratégias de cache (write-through, write-behind, cache-aside). **Cache-aside** é a mais simples e mais usada em aplicações web CRUD como o Linkr, porque a aplicação controla explicitamente quando ler e escrever no cache — sem nenhuma mágica automática por trás.

```
Fluxo de LEITURA (cache-aside):

1. Aplicação recebe uma requisição de leitura (ex: GET /posts/trending)
2. Verifica se o resultado já existe no Redis (cache HIT ou MISS)
3. Se HIT: retorna o valor do Redis diretamente — nunca toca o PostgreSQL
4. Se MISS: busca no PostgreSQL, salva o resultado no Redis
   (com um tempo de expiração), e retorna
```

```js
// src/services/posts.service.js
const redis = require('../config/redis')
const postsRepo = require('../repositories/posts.repository')

async function buscarTrending() {
  const chaveCache = 'posts:trending'

  // Passo 1: tenta o cache primeiro
  const cacheado = await redis.get(chaveCache)

  if (cacheado) {
    // HIT — o dado já existe no Redis, desserializa e retorna
    // Nunca chegamos a tocar o banco de dados nesta requisição
    return JSON.parse(cacheado)
  }

  // MISS — não estava no cache, busca de verdade no banco
  const trending = await postsRepo.buscarTrending()

  // Salva no Redis para as PRÓXIMAS requisições reaproveitarem
  // EX 60 = expira em 60 segundos — depois disso, o próximo pedido
  // vai gerar um MISS de novo, refazendo a query e atualizando o cache
  await redis.set(chaveCache, JSON.stringify(trending), 'EX', 60)

  return trending
}
```

---

## Por que tempo de expiração é a decisão de design mais importante aqui

O parâmetro `EX 60` acima não é um detalhe técnico menor — é a decisão central de qualquer sistema de cache, e ela expressa um tradeoff fundamental que Kleppmann chama, em *Designing Data-Intensive Applications*, de tensão entre **consistência** e **performance**.

```
Tempo de expiração CURTO (ex: 10 segundos):
  + dados quase sempre atualizados (pouca inconsistência)
  - cache HIT menos frequente — menos economia de trabalho no banco

Tempo de expiração LONGO (ex: 1 hora):
  + cache HIT muito mais frequente — grande economia de trabalho no banco
  - dados podem ficar "desatualizados" por até 1 hora
```

Não existe um valor certo universal — a escolha depende de quão tolerante o dado específico é a estar levemente desatualizado. O "trending" de posts populares pode tolerar 60 segundos de atraso sem problema real — ninguém percebe. O saldo de uma conta bancária não toleraria isso.

---

## Invalidação de cache — o problema que Phil Karlton descreveu como um dos dois mais difíceis da computação

Existe uma citação amplamente atribuída a Phil Karlton (engenheiro que trabalhou na Netscape e na SGI) segundo a qual só existem duas coisas difíceis em ciência da computação: invalidação de cache e nomear coisas. É citada com frequência em discussões técnicas sobre cache, embora a atribuição exata seja difícil de rastrear em uma fonte primária única — vale tratá-la como folclore da indústria, não uma citação bibliográfica verificável.

O problema real que ela descreve: e se um post novo for criado, e você não quiser esperar até 60 segundos para ele aparecer no trending? Você precisa **invalidar** (apagar) o cache manualmente, no momento exato em que o dado muda:

```js
// src/services/posts.service.js
async function curtir(postId, usuarioId) {
  const resultado = await postsRepo.curtirPost(postId, usuarioId)

  // Depois de uma curtida, o "trending" pode ter mudado —
  // invalida o cache imediatamente, forçando um recálculo na próxima leitura
  await redis.del('posts:trending')

  return resultado
}
```

```js
// Padrão mais genérico: invalidar por PREFIXO, quando várias chaves
// relacionadas precisam expirar juntas
async function invalidarCachePost(postId) {
  const chaves = await redis.keys(`post:${postId}:*`)
  if (chaves.length > 0) {
    await redis.del(...chaves)
  }
}
```

O tradeoff aqui é justamente por que Karlton (ou quem quer que tenha originado a citação) descreve isso como difícil: você precisa identificar **todo lugar** onde uma mudança de dado pode afetar um cache existente, e nenhuma ferramenta faz isso automaticamente por você — é uma responsabilidade que recai inteiramente sobre quem projeta o sistema.

---

## O que cachear, e o que nunca cachear

```
Bons candidatos a cache:
  - Listagens públicas que mudam pouco (posts populares, categorias)
  - Perfis públicos de usuário (visualizados muito mais do que editados)
  - Resultados de agregações caras (contagens, médias, rankings)

Maus candidatos a cache:
  - Dados sensíveis a consistência imediata (saldo, estoque em tempo real)
  - Dados específicos de UMA sessão de usuário sem estratégia de invalidação clara
  - Qualquer coisa onde "levemente desatualizado" causa dano real
```

---

## Conectando ao Linkr

```js
// src/repositories/usuarios.repository.js
const redis = require('../config/redis')

async function buscarPerfilPublico(username) {
  const chave = `perfil:${username}`

  const cacheado = await redis.get(chave)
  if (cacheado) return JSON.parse(cacheado)

  const perfil = await query(`
    SELECT u.id, u.nome, u.username, u.bio,
           COUNT(DISTINCT p.id) AS total_posts,
           COUNT(DISTINCT f.id) AS total_seguidores
    FROM usuarios u
    LEFT JOIN posts p    ON p.usuario_id = u.id
    LEFT JOIN follows f  ON f.seguido_id = u.id
    WHERE u.username = $1
    GROUP BY u.id
  `, [username])

  if (!perfil.rows[0]) return null

  // Perfis mudam pouco (bio, contadores) — 5 minutos de cache é razoável
  await redis.set(chave, JSON.stringify(perfil.rows[0]), 'EX', 300)

  return perfil.rows[0]
}
```

---

## Resumo

- Cache resolve trabalho redundante **entre requisições diferentes ao longo do tempo** — o problema irmão de N+1, que resolve trabalho redundante **dentro de uma única requisição**
- Cache em memória do próprio processo Node tem a mesma limitação do rate limiting em memória: não funciona com múltiplas instâncias — Redis resolve isso sendo um serviço compartilhado
- Cache-aside é o padrão mais comum: a aplicação verifica o cache, se não existir busca no banco e popula o cache, com um tempo de expiração
- O tempo de expiração é a decisão central de design — expressa o tradeoff entre consistência (dados sempre atualizados) e performance (menos carga no banco)
- Invalidação de cache — apagar o cache manualmente quando o dado subjacente muda — é amplamente descrita na indústria como um dos problemas mais difíceis de acertar, porque exige identificar manualmente todo ponto de mutação que afeta um cache existente
