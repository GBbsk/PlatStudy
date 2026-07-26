# Módulo Extra — Upload de Arquivos

## Fontes deste módulo

- **RFC 7578** — especificação formal do `multipart/form-data` (IETF)
- **Documentação oficial do Multer** — github.com/expressjs/multer (mantido sob a organização Express)
- **Documentação oficial do AWS SDK for JavaScript v3** — docs.aws.amazon.com/sdk-for-javascript
- **Documentação da Cloudflare R2** — developers.cloudflare.com/r2 (API compatível com S3, alternativa mais barata)
- **"Designing Data-Intensive Applications", Martin Kleppmann, O'Reilly, 2017** — capítulo sobre armazenamento de blobs e a diferença entre dados estruturados e não-estruturados

---

## O que estava faltando, e por que é grave especificamente para o Linkr

Toda a API que você construiu recebe `application/json`. Mas o Linkr — uma rede social — precisa de foto de perfil e imagem em posts, e isso nunca foi ensinado. Isso não é um detalhe cosmético: é uma classe inteira de conhecimento que você não tem — como o HTTP transporta binário, e onde binário deveria (e não deveria) ser armazenado.

---

## Conceito central: `multipart/form-data` não é JSON

Até agora, toda vez que você mandou dados para o Express, foi assim:

```
Content-Type: application/json

{"nome": "Ana", "email": "ana@email.com"}
```

Um arquivo não cabe direto dentro de uma string JSON — é binário, pode ter megabytes, e misturar binário com texto estruturado quebra o parser JSON. A solução do protocolo HTTP para "enviar arquivo + campos de texto na mesma requisição" é um Content-Type diferente: `multipart/form-data`, formalizado pela **RFC 7578**.

```
POST /usuarios/foto HTTP/1.1
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWx

------WebKitFormBoundary7MA4YWx
Content-Disposition: form-data; name="legenda"

Minha foto de perfil
------WebKitFormBoundary7MA4YWx
Content-Disposition: form-data; name="foto"; filename="perfil.jpg"
Content-Type: image/jpeg

[bytes binários da imagem aqui]
------WebKitFormBoundary7MA4YWx--
```

O `boundary` é uma string aleatória que separa cada "parte" da requisição — um "part" pode ser um campo de texto normal (como `legenda`) ou um arquivo (como `foto`, que tem `filename` e seu próprio `Content-Type`). `express.json()` não entende esse formato — ele só parseia JSON. Você precisa de um middleware específico.

---

## Multer — o middleware padrão do ecossistema Express

```bash
npm install multer
```

```js
// src/middlewares/upload.middleware.js
const multer = require('multer')

// memoryStorage: guarda o arquivo em memória (Buffer), não em disco
// Essencial quando você vai reenviar o arquivo para um storage externo (S3/R2)
// e não precisa nunca gravá-lo no filesystem do seu próprio servidor
const storage = multer.memoryStorage()

const upload = multer({
  storage,
  limits: {
    fileSize: 5 * 1024 * 1024   // 5 MB — nunca deixe sem limite
  },
  fileFilter: (req, file, cb) => {
    const tiposPermitidos = ['image/jpeg', 'image/png', 'image/webp']
    if (!tiposPermitidos.includes(file.mimetype)) {
      return cb(new Error('Formato de arquivo não suportado. Use JPEG, PNG ou WebP.'))
    }
    cb(null, true)
  }
})

module.exports = upload
```

```js
// src/routes/usuarios.routes.js
const upload = require('../middlewares/upload.middleware')

// upload.single('foto') — 'foto' precisa bater com o name do campo no form-data
router.post('/foto', autenticar, upload.single('foto'), asyncHandler(async (req, res) => {
  // req.file agora existe — populado pelo Multer, não pelo express.json()
  console.log(req.file)
  // {
  //   fieldname: 'foto',
  //   originalname: 'minha-foto.jpg',
  //   mimetype: 'image/jpeg',
  //   buffer: <Buffer ...>,   ← os bytes reais, porque usamos memoryStorage
  //   size: 234567
  // }

  // req.body continua funcionando normalmente para os OUTROS campos de texto
  console.log(req.body.legenda)

  if (!req.file) {
    return res.status(400).json({ erro: 'Nenhum arquivo enviado' })
  }

  const url = await uploadService.salvarFoto(req.file, req.usuario.id)
  res.json({ url })
}))
```

**Por que `memoryStorage`, não `diskStorage`:** `diskStorage` grava o arquivo no disco do seu próprio servidor — e você já sabe, da correção de PostgreSQL, que o filesystem de um container é efêmero. Um deploy novo apagaria todas as fotos. `memoryStorage` mantém o arquivo só como um `Buffer` na RAM, tempo suficiente para você reenviá-lo a um storage que persiste de verdade.

---

## Onde o arquivo realmente deve morar: object storage

Object storage é uma categoria de serviço (S3 da AWS, R2 da Cloudflare, Cloud Storage do Google) desenhada especificamente para armazenar blobs binários — diferente de um banco de dados relacional, que é otimizado para dados estruturados e pequenos. A ideia central: você nunca guarda o arquivo em si no seu banco de dados nem no seu servidor — você guarda só a **URL** dele, e o arquivo vive em um serviço separado, feito para isso.

```
Fluxo:
1. Cliente manda o arquivo pro SEU servidor (via multipart/form-data)
2. Seu servidor reenvia o arquivo pro object storage (S3/R2)
3. O object storage retorna uma URL pública (ou assinada) do arquivo
4. Você salva só essa URL no banco de dados PostgreSQL — nunca o binário
```

```bash
npm install @aws-sdk/client-s3
```

```js
// src/config/storage.js
const { S3Client } = require('@aws-sdk/client-s3')

// Cloudflare R2 usa a MESMA API do S3 — só muda o endpoint
// Isso é intencional: R2 foi desenhado para ser compatível com o SDK do S3
const s3 = new S3Client({
  region: 'auto',
  endpoint: process.env.R2_ENDPOINT,
  credentials: {
    accessKeyId:     process.env.R2_ACCESS_KEY,
    secretAccessKey: process.env.R2_SECRET_KEY
  }
})

module.exports = s3
```

```js
// src/services/upload.service.js
const { PutObjectCommand } = require('@aws-sdk/client-s3')
const { randomUUID } = require('crypto')
const s3 = require('../config/storage')
const AppError = require('../utils/AppError')

async function salvarFoto(arquivo, usuarioId) {
  // Nome único — nunca confie no nome original do arquivo (pode colidir, pode ter caracteres perigosos)
  const extensao = arquivo.mimetype.split('/')[1]
  const chave = `usuarios/${usuarioId}/${randomUUID()}.${extensao}`

  await s3.send(new PutObjectCommand({
    Bucket:      process.env.R2_BUCKET,
    Key:         chave,
    Body:        arquivo.buffer,       // o Buffer que veio do Multer
    ContentType: arquivo.mimetype
  }))

  // A URL pública final — depende de como seu bucket está configurado
  return `${process.env.R2_PUBLIC_URL}/${chave}`
}

module.exports = { salvarFoto }
```

---

## O padrão mais avançado (e mais usado em produção): upload direto do cliente

O fluxo acima funciona, mas tem uma ineficiência: o arquivo passa duas vezes pela rede — cliente → seu servidor → S3. Para arquivos grandes, isso é lento e consome a banda do seu próprio servidor à toa.

O padrão de produção real usa **URLs pré-assinadas**: seu servidor não recebe o arquivo — ele só gera uma permissão temporária, e o cliente manda o arquivo **direto** para o S3/R2.

```js
// src/services/upload.service.js
const { PutObjectCommand } = require('@aws-sdk/client-s3')
const { getSignedUrl } = require('@aws-sdk/s3-request-presigner')
const s3 = require('../config/storage')

async function gerarUrlUpload(usuarioId, nomeArquivo, tipoMime) {
  const chave = `usuarios/${usuarioId}/${randomUUID()}-${nomeArquivo}`

  const comando = new PutObjectCommand({
    Bucket: process.env.R2_BUCKET,
    Key: chave,
    ContentType: tipoMime
  })

  // URL válida por 5 minutos — o cliente tem essa janela para fazer o upload
  const urlAssinada = await getSignedUrl(s3, comando, { expiresIn: 300 })

  return {
    urlUpload: urlAssinada,               // o cliente faz PUT direto aqui
    urlFinal: `${process.env.R2_PUBLIC_URL}/${chave}`  // URL para salvar no banco depois
  }
}
```

```
Fluxo com URL pré-assinada:
1. Cliente pede ao SEU servidor: "quero subir uma foto.jpg"
2. Servidor gera uma URL assinada (sem tocar no arquivo) e devolve
3. Cliente faz PUT DIRETO pro S3/R2 usando essa URL — servidor não participa
4. Cliente avisa o servidor "terminei", servidor salva a urlFinal no banco
```

Esse é o padrão que você vai encontrar em produtos reais com upload de mídia em escala (Instagram, Twitter) — o servidor de aplicação nunca lida com o peso do arquivo em si, só autoriza e registra.

---

## Resumo

- `multipart/form-data` (RFC 7578) é o formato HTTP para enviar arquivos junto com campos de texto — `express.json()` não entende esse formato, você precisa do Multer
- `memoryStorage` do Multer mantém o arquivo em RAM temporariamente — nunca use `diskStorage` em produção, pelo mesmo motivo que SQLite não funciona: filesystem efêmero
- Arquivos nunca vivem no banco de dados relacional — você guarda só a URL; o binário vive em object storage (S3, R2)
- Sempre limite `fileSize` e valide `mimetype` — um endpoint de upload sem limites é uma porta aberta para abuso
- O padrão de produção real usa URLs pré-assinadas, evitando que o arquivo passe duas vezes pela rede via seu servidor
