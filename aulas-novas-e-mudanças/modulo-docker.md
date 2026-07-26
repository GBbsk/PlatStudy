# Módulo Extra — Docker

## Fontes deste módulo

- **Documentação oficial do Docker** — docs.docker.com/get-started (o guia oficial de conceitos)
- **Documentação do Docker Compose** — docs.docker.com/compose
- **"Docker Deep Dive", Nigel Poulton, 2023** — referência técnica amplamente citada na comunidade DevOps
- **Open Container Initiative (OCI)** — opencontainers.org, o órgão que padroniza o formato de containers entre diferentes runtimes (Docker, Podman, containerd)

---

## O que estava faltando, e por que "não é opcional" não é exagero

Você já sentiu, sem nomear, os sintomas do problema que Docker resolve: a necessidade de instalar PostgreSQL localmente para rodar os testes de integração, a diferença de comportamento entre SQLite (dev) e PostgreSQL (produção), a dependência de "ter Node 20 instalado exatamente". Docker existe para eliminar essa categoria inteira de atrito, e é hoje um requisito básico — não avançado — em praticamente toda vaga de backend.

---

## Conceito central: container não é máquina virtual

A confusão mais comum de quem está começando é achar que um container é uma VM leve. Não é. Uma VM virtualiza hardware inteiro — tem seu próprio kernel de sistema operacional rodando por cima do seu. Um container **compartilha o kernel do sistema operacional host**, e isola só o processo: seu filesystem, suas variáveis de ambiente, sua rede. Isso é o que torna containers ordens de magnitude mais leves e rápidos de iniciar que VMs — segundos, não minutos.

```
Máquina Virtual                    Container
┌─────────────────────┐           ┌─────────────────────┐
│   App A  │  App B    │           │   App A  │  App B    │
├──────────┼───────────┤           ├──────────┼───────────┤
│ SO Guest │ SO Guest  │           │  (compartilha o      │
├──────────┴───────────┤           │   kernel do host)    │
│      Hypervisor       │           ├───────────────────────┤
├────────────────────────┤           │   Docker Engine        │
│   SO Host              │           ├───────────────────────┤
├────────────────────────┤           │   SO Host               │
│   Hardware              │           ├───────────────────────┤
└────────────────────────┘           │   Hardware               │
                                      └───────────────────────┘
```

O que garante que "funciona igual em qualquer lugar" não é a virtualização de hardware — é que o container empacota, junto com sua aplicação, **exatamente** as bibliotecas de sistema, versão de linguagem, e dependências que ela precisa. O host pode ser Windows, Mac, Linux, ou o servidor da Railway — o conteúdo do container é idêntico em todos.

---

## Imagem vs Container — a distinção que confunde no início

```
Imagem  = a RECEITA (read-only) — um conjunto de camadas de filesystem empacotadas
Container = uma INSTÂNCIA em execução dessa receita

Isso é análogo a:
Classe (imagem) → Instância/Objeto (container)
```

Você pode criar múltiplos containers a partir da mesma imagem, exatamente como você instancia múltiplos objetos da mesma classe em JavaScript.

---

## O `Dockerfile` — a receita da sua aplicação

```dockerfile
# Dockerfile — na raiz do projeto Linkr

# FROM define a imagem base — aqui, uma versão específica e minimalista do Node
# "alpine" é uma distribuição Linux extremamente pequena — imagens menores,
# builds mais rápidos, menos superfície de ataque de segurança
FROM node:20-alpine

# Diretório de trabalho DENTRO do container — tudo daqui pra frente roda relativo a isso
WORKDIR /app

# Copia SÓ os arquivos de dependência primeiro — não o projeto inteiro ainda
# Isso é uma otimização deliberada de cache de camadas: se package.json não
# mudou, o Docker reutiliza a camada de npm install já feita, sem reexecutar
COPY package*.json ./

RUN npm ci --omit=dev

# SÓ AGORA copia o resto do código — depois do npm install já ter rodado
COPY . .

# Documenta (não abre de fato) a porta que a aplicação usa
EXPOSE 3000

# Comando executado quando o container inicia
CMD ["node", "src/index.js"]
```

**Por que a ordem do `COPY` importa tanto:** Docker constrói imagens em **camadas**, cada instrução do Dockerfile vira uma camada, e camadas são cacheadas. Se você copiasse todo o código antes do `npm ci`, qualquer mudança em qualquer arquivo (mesmo um `.md`) invalidaria o cache e forçaria reinstalar todas as dependências do zero a cada build. Copiando só `package*.json` primeiro, o `npm ci` só reexecuta quando as dependências realmente mudam — builds subsequentes ficam segundos, não minutos.

```bash
# Construir a imagem a partir do Dockerfile
$ docker build -t linkr-api .

# Rodar um container a partir dessa imagem
$ docker run -p 3000:3000 --env-file .env linkr-api
#              ↑ mapeia porta 3000 do HOST para a 3000 do CONTAINER
```

---

## `docker-compose` — orquestrando múltiplos containers juntos

Sua aplicação real precisa de mais que só o Node — precisa do PostgreSQL, possivelmente do Redis. Rodar cada um manualmente com `docker run` é tedioso e frágil. O Docker Compose descreve todos os serviços relacionados em um único arquivo declarativo.

```yaml
# docker-compose.yml — na raiz do projeto

services:
  api:
    build: .                    # constrói a partir do Dockerfile local
    ports:
      - "3000:3000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    # environment sobrescreve o .env especificamente para o container,
    # apontando para o hostname do serviço postgres, não localhost
    environment:
      DATABASE_URL: postgresql://postgres:senha@postgres:5432/linkr
      REDIS_URL: redis://redis:6379

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: senha
      POSTGRES_DB: linkr
    ports:
      - "5432:5432"
    volumes:
      - dados_postgres:/var/lib/postgresql/data
      # volume nomeado: persiste os dados MESMO se o container for destruído
      # e recriado — diferente do filesystem comum do container, que é efêmero

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  dados_postgres:
```

```bash
# Sobe TODOS os serviços de uma vez, na rede interna que o Compose cria automaticamente
$ docker compose up

# Em background
$ docker compose up -d

# Para tudo
$ docker compose down

# Para tudo E remove os volumes (apaga os dados do Postgres também)
$ docker compose down -v
```

**O ponto central que resolve o problema real:** dentro da rede Docker criada pelo Compose, o serviço `api` acessa o Postgres pelo hostname `postgres` (o nome do serviço no YAML), não por `localhost`. Docker resolve esse nome internamente. Isso significa: qualquer pessoa que clonar o repositório roda `docker compose up` e tem o ambiente **inteiro** — Node, Postgres, Redis, nas versões corretas — rodando em minutos, sem instalar nada além do Docker no próprio sistema.

---

## `.dockerignore` — evitando lixo na imagem

```
# .dockerignore — mesma ideia do .gitignore, mas para o build da imagem

node_modules
.git
.env
npm-debug.log
coverage
__tests__
```

Sem isso, o `COPY . .` do Dockerfile copiaria `node_modules` do seu host (que pode ter binários compilados para o SO errado) para dentro do container, inflando a imagem e potencialmente causando erros de compatibilidade.

---

## Multi-stage build — otimizando o tamanho final da imagem

```dockerfile
# Dockerfile com multi-stage — usado em produção real para imagens menores

# Stage 1: instala dependências e faz qualquer build necessário
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# Stage 2: imagem final, só com o necessário para RODAR, não para desenvolver
FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/src ./src
COPY package*.json ./
EXPOSE 3000
CMD ["node", "src/index.js"]
```

A imagem final não carrega ferramentas de build, arquivos de teste, ou qualquer coisa usada só durante o processo de instalação — só o necessário para executar. Isso reduz o tamanho da imagem (deploys mais rápidos) e a superfície de ataque de segurança (menos coisa instalada = menos vulnerabilidades possíveis).

---

## Conectando com o que você já aprendeu: por que isso substitui parte do "Setup Profissional"

Lembra da Aula 1.2 do curso de Node, sobre configurar `nodemon`, `.env`, estrutura de pastas? Docker Compose é o próximo degrau natural dessa mesma preocupação — "como eu garanto que qualquer pessoa consegue rodar este projeto exatamente como eu rodo". `nodemon` resolve isso para hot-reload; Docker Compose resolve isso para **o ambiente inteiro**, incluindo o banco de dados que antes exigia instalação manual e específica do sistema operacional de cada desenvolvedor.

---

## Resumo

- Container compartilha o kernel do host e isola só o processo — muito mais leve que uma VM, que virtualiza hardware inteiro
- Imagem é a receita read-only; container é uma instância em execução dessa receita — a mesma relação entre classe e objeto
- A ordem das instruções no Dockerfile importa por causa do cache de camadas: dependências antes do código, para não reinstalar tudo a cada mudança
- `docker-compose.yml` orquestra múltiplos serviços (API, Postgres, Redis) com uma rede interna onde cada serviço acessa o outro pelo nome, não por `localhost`
- Volumes nomeados persistem dados do Postgres mesmo quando o container é destruído — resolve o mesmo problema de filesystem efêmero, mas no ambiente de desenvolvimento
- Multi-stage builds produzem imagens finais menores, sem ferramentas de desenvolvimento desnecessárias em produção
