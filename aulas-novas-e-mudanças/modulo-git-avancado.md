# Git Avançado — Funcionalidades e Técnicas Profissionais

## Fontes deste módulo

- **Pro Git, Scott Chacon & Ben Straub, Apress, 2ª edição** — o livro oficial do Git, disponível gratuitamente em git-scm.com/book. É a referência mais completa e autoritativa que existe sobre o assunto, escrita por um dos próprios desenvolvedores da plataforma GitHub.
- **Documentação oficial do Git** — git-scm.com/docs — man pages de cada subcomando
- Nota de transparência: mesma ressalva dos módulos anteriores — conhecimento estável do meu treinamento, não busca ativa nesta conversa. Git é um software maduro (lançado por Linus Torvalds em 2005) cujos fundamentos não mudam com frequência.

---

## Por que Git avançado importa agora, especificamente

Você aprendeu o Git básico no curso: `init`, `add`, `commit`, `push`, `pull`, branch, merge, PR. Isso te leva longe — até o ponto onde você começa a trabalhar em código real de verdade, seja no Linkr, no PegadaFit, ou em qualquer emprego futuro. É nesse momento que surgem situações que o Git básico não responde bem: você commitou algo errado e já fez push, você precisa integrar mudanças de outra branch sem bagunçar o histórico, você quer desfazer só uma parte de uma mudança, o histórico virou um emaranhado ilegível. Este módulo cobre as ferramentas que resolvem essas situações.

---

## Parte 1 — Entendendo o que Git realmente é por baixo

Antes de comandos avançados, vale entender o modelo mental correto do Git — sem ele, os comandos parecem mágica (ou pior, parecem aleatórios).

### O DAG — a estrutura real de um repositório Git

Git não é um "sistema de histórico de mudanças de arquivo". Git é um **grafo dirigido acíclico (DAG) de snapshots**. Cada commit aponta para o estado completo de todos os arquivos naquele momento (um snapshot), não para um diff em relação ao anterior. Os diffs que você vê em `git diff` são calculados na hora, comparando dois snapshots — não estão armazenados assim.

```
A ← B ← C ← D  (branch main)
         ↑
          E ← F  (branch feature)
```

Cada letra é um commit (um snapshot + metadados). Cada commit aponta para seu pai. Uma **branch** é simplesmente um ponteiro móvel para um commit — quando você faz um novo commit na branch `main`, o ponteiro `main` avança para o novo commit.

`HEAD` é um ponteiro especial que aponta para onde você está agora — geralmente para uma branch, que por sua vez aponta para um commit.

```bash
# Visualizar o grafo real do seu repositório no terminal
git log --oneline --graph --all --decorate

# Saída:
# * a3f8c2d (HEAD -> main) Adiciona paginação
# * b1e9d4f Adiciona curtidas
# | * c2a7f1e (feature/comentarios) Adiciona comentários
# |/
# * d4b8e3a Cria tabela de posts
```

---

## Parte 2 — Desfazendo coisas (a parte que mais assusta)

### As três árvores do Git — working directory, staging area, commit

Antes de desfazer qualquer coisa, você precisa saber **onde** a coisa está:

```
Working Directory   →  git add  →  Staging Area (Index)  →  git commit  →  Repositório (HEAD)
(arquivos no disco)                (o que vai no próximo commit)           (histórico)
```

Cada operação de "desfazer" age em um desses três lugares, e confundi-los é o motivo de a maioria das pessoas apagar código sem querer.

### `git restore` — desfazer mudanças locais (não commitadas)

```bash
# Desfaz mudanças no working directory — volta ao estado do último commit
# CUIDADO: irreversível se as mudanças ainda não foram adicionadas ao staging
git restore src/services/posts.service.js

# Desfaz um git add (remove do staging area, mantém as mudanças no disco)
git restore --staged src/services/posts.service.js

# Desfaz tanto o staging quanto as mudanças no disco
git restore --staged --worktree src/services/posts.service.js
```

### `git commit --amend` — corrigir o último commit

```bash
# Corrige a mensagem do último commit (ainda não foi feito push)
git commit --amend -m "Mensagem correta aqui"

# Adiciona arquivos esquecidos ao último commit sem criar um novo
git add arquivo-esquecido.js
git commit --amend --no-edit   # --no-edit mantém a mensagem original
```

**Limitação crítica:** `--amend` reescreve o commit — gera um novo hash. Se você já fez push desse commit, vai precisar de `git push --force-with-lease` (veja abaixo). **Nunca amend em branches compartilhadas com outras pessoas** — você estaria reescrevendo história que outros já têm localmente.

### `git revert` — desfazer um commit já feito push, com segurança

```bash
# Cria um NOVO commit que desfaz as mudanças de um commit específico
# É a forma segura de desfazer em branches compartilhadas
git revert a3f8c2d

# Reverte sem abrir o editor de mensagem de commit
git revert a3f8c2d --no-edit

# Reverte múltiplos commits de uma vez
git revert a3f8c2d b1e9d4f
```

A diferença fundamental entre `revert` e `reset`: `revert` **adiciona ao histórico** — cria um novo commit que desfaz o efeito do commit alvo. O commit original continua lá. `reset` **reescreve o histórico** — apaga commits do grafo. Em branches compartilhadas, só use `revert`.

### `git reset` — mover o ponteiro da branch (com cuidado)

```bash
# --soft: move HEAD para um commit anterior, mas mantém as mudanças no staging
# Útil para "desfazer" um commit e reescrever as mudanças antes de commitar de novo
git reset --soft HEAD~1   # HEAD~1 = um commit antes do atual

# --mixed (padrão): move HEAD e limpa o staging, mas mantém as mudanças no disco
git reset HEAD~1          # mantém os arquivos modificados, mas fora do staging

# --hard: desfaz tudo — move HEAD E descarta mudanças no staging E no disco
# DESTRUTIVO — mudanças são perdidas (exceto se ainda estiverem no reflog)
git reset --hard HEAD~1
```

```
git reset --soft  HEAD~1:   Repositório ← move    Staging ← mantém    Disco ← mantém
git reset --mixed HEAD~1:   Repositório ← move    Staging ← limpa     Disco ← mantém
git reset --hard  HEAD~1:   Repositório ← move    Staging ← limpa     Disco ← limpa
```

---

## Parte 3 — Rebase, o comando que divide opiniões

### O que rebase faz, mecanicamente

```
Antes do rebase:

A ← B ← C  (main)
     ↑
      D ← E  (feature)

Depois de git rebase main na branch feature:

A ← B ← C  (main)
          ↑
           D' ← E'  (feature)
```

O rebase "move" os commits `D` e `E` para cima de `C` — na prática, ele **recria** os commits com novos hashes (`D'`, `E'`), aplicando as mesmas mudanças mas a partir de um ponto diferente. O resultado é um histórico **linear**, sem a bifurcação que um merge criaria.

### `git rebase` vs `git merge` — a diferença real

```bash
# merge: preserva o histórico exato, com a bifurcação
git checkout feature
git merge main
# Cria um "merge commit" que tem dois pais (C e E)
# Histórico: A ← B ← C ← F (merge commit com pais C e E)
#                     ↑   ↑
#                     D ← E

# rebase: reescreve o histórico para ser linear
git checkout feature
git rebase main
# D e E são recriados como D' e E' em cima de C
# Histórico depois de um fast-forward merge: A ← B ← C ← D' ← E'
```

Equipes dividem opiniões sobre qual usar. A visão prática:

```
Use merge quando:
  - Integrando uma feature branch no main (o merge commit documenta quando a feature foi integrada)
  - Em branches compartilhadas com outras pessoas
  - Você quer preservar o histórico exato de como o desenvolvimento aconteceu

Use rebase quando:
  - Atualizando sua feature branch com o que aconteceu no main enquanto você trabalhava
  - Antes de abrir um PR — deixa o histórico limpo e fácil de revisar
  - Limpando commits intermediários ("WIP", "fix", "mais uma coisa") antes do merge
```

A regra de ouro que quase todo time profissional segue: **nunca rebase em branches que outras pessoas já pushearam**. Rebase reescreve hashes — se alguém já tem os commits originais localmente, vai ter um conflito de divergência de histórico doloroso.

### Rebase interativo — o mais poderoso

```bash
# Abre um editor com os últimos 3 commits para você reorganizar
git rebase -i HEAD~3
```

```
# O editor mostra algo assim:
pick a3f8c2d Adiciona modelo de post
pick b1e9d4f WIP correção
pick c2a7f1e Finaliza serviço de post

# Você EDITA as instruções antes de fechar o editor:
pick a3f8c2d Adiciona modelo de post
squash b1e9d4f WIP correção       ← squash: junta com o commit anterior
reword c2a7f1e Finaliza serviço   ← reword: abre editor de mensagem
```

**Ações disponíveis no rebase interativo:**

```
pick    → mantém o commit como está
reword  → mantém o commit, mas deixa você editar a mensagem
edit    → para na execução do rebase neste commit, permitindo fazer amend
squash  → junta este commit com o anterior (prompts para nova mensagem)
fixup   → igual ao squash, mas descarta a mensagem deste commit
drop    → remove o commit completamente do histórico
```

**Caso de uso real — antes de abrir um PR:**

```bash
# Você trabalhou numa feature ao longo de 3 dias, com commits como:
# "começa implementação"
# "wip"
# "fix"
# "acho que funciona agora"
# "esqueci de adicionar o validador"
# "revisando de novo"

# Antes do PR, limpa tudo em um único commit significativo:
git rebase -i main   # todos os commits da sua branch em relação ao main

# No editor, dá squash em tudo menos o primeiro,
# e escreve uma mensagem de commit clara:
# "feat: adiciona sistema de curtidas com verificação de duplicata"
```

---

## Parte 4 — `git stash` — salvando trabalho sem commitar

```bash
# Salva tudo que está modificado (working directory + staging) numa pilha temporária
# Seu working directory volta ao estado do último commit — limpo para mudar de branch
git stash

# Com uma descrição (recomendado)
git stash push -m "trabalho em progresso na feature de curtidas"

# Lista todos os stashes salvos
git stash list
# stash@{0}: On feature/curtidas: trabalho em progresso na feature de curtidas
# stash@{1}: WIP on main: a3f8c2d Adiciona paginação

# Aplica o stash mais recente (mantém na lista)
git stash apply

# Aplica e remove da lista ao mesmo tempo
git stash pop

# Aplica um stash específico
git stash apply stash@{1}

# Remove um stash sem aplicar
git stash drop stash@{0}

# Limpa todos os stashes
git stash clear
```

**Caso de uso mais comum:** você está no meio de uma mudança, alguém pede pra você olhar um bug urgente em outra branch. Você não quer commitar código incompleto. `git stash` salva o estado atual, você muda de branch, corrige o bug, volta, e `git stash pop` restaura o trabalho de onde parou.

---

## Parte 5 — `git bisect` — encontrando o commit que introduziu um bug

Imagine que você tem um bug que definitivamente não existia 3 semanas atrás, e desde então houve 50 commits. Encontrar manualmente qual dos 50 causou o bug é tedioso. `git bisect` faz uma **busca binária no histórico**: você diz qual commit era bom (bug não existia) e qual é ruim (bug existe), e ele divide o histórico ao meio automaticamente.

```bash
# Inicia o bisect
git bisect start

# Marca o commit atual como ruim (o bug existe agora)
git bisect bad

# Marca um commit antigo que você sabe que era bom
git bisect good a3f8c2d

# O Git faz checkout no commit do meio do histórico
# Você testa se o bug existe naquele commit, e informa:
git bisect good   # bug não existe neste commit → bisect pula para a segunda metade
git bisect bad    # bug existe neste commit → bisect pula para a primeira metade

# Após alguns rounds, o Git aponta exatamente qual commit introduziu o bug
# b1e9d4f is the first bad commit

# Encerra o bisect e volta para onde você estava
git bisect reset
```

Com 50 commits, bisect encontra o culpado em no máximo **6 rounds** (log₂(50) ≈ 6). É a diferença entre "vou olhar cada commit até achar" e "vou testar 6 vezes e pronto".

---

## Parte 6 — `git cherry-pick` — pegando um commit específico de outra branch

```bash
# Aplica as mudanças de um commit específico na branch atual,
# criando um novo commit com o mesmo conteúdo mas hash diferente
git cherry-pick a3f8c2d

# Cherry-pick múltiplos commits
git cherry-pick a3f8c2d b1e9d4f

# Cherry-pick de um range
git cherry-pick a3f8c2d^..b1e9d4f   # todos os commits de a3f8c2d até b1e9d4f (inclusive)

# Cherry-pick sem commitar automaticamente (deixa no staging pra você revisar)
git cherry-pick a3f8c2d --no-commit
```

**Caso de uso real:** você corrigiu um bug crítico na branch de desenvolvimento, mas esse bug também afeta a branch de produção atual. Em vez de fazer um merge (que traria código ainda em desenvolvimento) ou replicar manualmente a correção, você cherry-pick só aquele commit de correção para a branch de produção.

---

## Parte 7 — `git reflog` — a rede de segurança

O reflog registra **todo movimento de HEAD** nos últimos 90 dias, mesmo operações que "apagaram" commits. É a rede de segurança para quando você faz um `git reset --hard` e se arrepende.

```bash
# Mostra o histórico de todos os movimentos de HEAD
git reflog

# Saída:
# a3f8c2d (HEAD -> main) HEAD@{0}: reset: moving to HEAD~3
# b1e9d4f HEAD@{1}: commit: Adiciona curtidas
# c2a7f1e HEAD@{2}: commit: Adiciona posts
# ...

# Para recuperar commits "perdidos" por um reset --hard:
git reset --hard HEAD@{1}   # volta para onde HEAD estava antes do reset

# Ou cria uma nova branch a partir de um ponto do reflog
git checkout -b recuperacao HEAD@{2}
```

**Regra prática:** antes de qualquer operação destrutiva (`reset --hard`, `rebase`, `filter-branch`), anote o hash atual com `git log --oneline -1`. Se algo der errado, `git reflog` te leva de volta.

---

## Parte 8 — `git worktree` — múltiplos working directories do mesmo repositório

```bash
# Cria um segundo working directory ligado ao MESMO repositório,
# em outra pasta, na branch especificada
git worktree add ../linkr-hotfix hotfix/login

# Agora você tem:
# ~/projetos/linkr/         ← working directory original (branch main)
# ~/projetos/linkr-hotfix/  ← segundo working directory (branch hotfix/login)
# Os dois compartilham o MESMO repositório Git (.git/)

# Você pode trabalhar nos dois ao mesmo tempo, sem stash, sem trocar de branch
# Em cada pasta, git status/commit/push funciona normalmente

# Lista todos os worktrees
git worktree list

# Remove um worktree quando terminar
git worktree remove ../linkr-hotfix
```

**Caso de uso:** você está no meio de uma feature complexa (impossível de fazer stash limpo), e chega um bug urgente de produção. Com worktree, você abre uma segunda cópia do projeto já na branch de hotfix, corrige, faz push, e volta para a feature sem ter saído dela.

---

## Parte 9 — `git sparse-checkout` — só as pastas que você precisa

(Expandindo o que você acabou de aprender na conversa anterior)

```bash
# Fluxo completo
git init meu-projeto
cd meu-projeto
git remote add origin https://github.com/usuario/repo
git sparse-checkout init --cone   # --cone é o modo mais performático

# Define as pastas que você quer
git sparse-checkout set src/services src/repositories

# Puxa os dados
git pull origin main

# Adiciona mais pastas depois
git sparse-checkout add src/controllers

# Lista o que está configurado
git sparse-checkout list

# Desabilita (volta a ver tudo)
git sparse-checkout disable
```

---

## Parte 10 — `git blame` e `git log` avançado

```bash
# Mostra quem editou cada linha de um arquivo, em qual commit, e quando
git blame src/services/posts.service.js

# Blame mostrando só um range de linhas
git blame -L 10,25 src/services/posts.service.js

# Segue o histórico de uma função específica (--function, flag -L com função)
git log -L :buscarTodos:src/repositories/posts.repository.js

# Log buscando em mensagens de commit
git log --grep="autenticação"

# Log buscando por mudanças em uma string específica no código
# "quem tocou nessa string em qualquer commit do histórico?"
git log -S "JWT_ACCESS_SECRET"

# Log de um arquivo específico — histórico completo daquele arquivo
git log --follow -- src/services/auth.service.js
# --follow rastreia renomeações do arquivo

# Log formatado
git log --format="%h %an %ar %s"   # hash curto, autor, há quanto tempo, mensagem
```

---

## Parte 11 — `git push --force-with-lease` — o force push seguro

```bash
# NUNCA use isso em branches compartilhadas (main, develop)
# Útil quando você reescreveu história LOCAL (amend, rebase) e precisa atualizar o remote

# ❌ git push --force — empurra sem verificar se alguém pusheu depois de você
#    Isso pode apagar commits de outras pessoas silenciosamente

# ✅ git push --force-with-lease — só empurra se o remote está
#    exatamente como você esperava (baseado na sua cópia local do remote)
#    Se alguém commitou enquanto você trabalhava, o comando FALHA em vez de apagar
git push --force-with-lease origin feature/minha-branch
```

---

## Parte 12 — `.gitattributes` — além do `.gitignore`

```bash
# .gitattributes — configura como o Git trata diferentes tipos de arquivo

# Normaliza quebras de linha (CRLF Windows vs LF Unix)
# Sem isso, arquivos editados no Windows aparecem como completamente modificados
# no diff, por causa só da quebra de linha diferente
* text=auto

# Força LF em arquivos de código
*.js text eol=lf
*.ts text eol=lf

# Marca arquivos binários — Git não tenta fazer diff de texto neles
*.png binary
*.jpg binary
*.pdf binary

# Linguagem para o GitHub Linguist (aparece nas estatísticas do repositório)
*.md linguist-documentation=true
```

---

## Parte 13 — Hooks — automatizando ações no Git

Hooks são scripts que o Git executa automaticamente em momentos específicos. Vivem em `.git/hooks/`.

```bash
# Para criar um hook, crie um arquivo executável na pasta .git/hooks/
# O nome define quando ele roda

# pre-commit: roda antes de cada commit
# Útil para rodar lint e testes antes de commitar
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/sh
npm run lint
if [ $? -ne 0 ]; then
  echo "Lint falhou — commit bloqueado"
  exit 1
fi
EOF

chmod +x .git/hooks/pre-commit
```

**Problema com hooks em `.git/hooks/`:** não são commitados no repositório — cada desenvolvedor precisaria configurar manualmente. A solução padrão da indústria é `husky`:

```bash
npm install -D husky
npx husky init

# Cria .husky/pre-commit — este ARQUIVO é commitado junto com o projeto
echo "npm run lint" > .husky/pre-commit
```

```json
// package.json — o prepare script instala o husky automaticamente
// quando alguém faz npm install no projeto
{
  "scripts": {
    "prepare": "husky"
  }
}
```

**Hooks mais úteis:**

```
pre-commit       → lint, formatação, testes rápidos
commit-msg       → valida o formato da mensagem de commit (Conventional Commits)
pre-push         → testes completos antes de mandar para o remote
prepare-commit-msg → popula automaticamente parte da mensagem de commit
```

---

## Parte 14 — Conventional Commits — padronizando mensagens

Uma convenção amplamente adotada na indústria para mensagens de commit, que torna o histórico legível por humanos e parseable por ferramentas (geração automática de changelog, versionamento semântico).

```
<tipo>(<escopo opcional>): <descrição curta>

<corpo opcional — explica o POR QUE, não o O QUE>

<rodapé opcional — breaking changes, referências a issues>
```

```bash
# Tipos mais comuns:
feat:     nova funcionalidade
fix:      correção de bug
docs:     só mudanças de documentação
style:    formatação, sem mudança de lógica
refactor: refatoração sem nova funcionalidade nem correção
test:     adiciona ou corrige testes
chore:    tarefas de manutenção (bump de versão, configuração)

# Exemplos:
git commit -m "feat(auth): implementa refresh token com rotação"
git commit -m "fix(posts): corrige N+1 na busca do feed"
git commit -m "refactor(services): extrai lógica de validação para Zod"

# Breaking change — indica que a API mudou de forma incompatível
git commit -m "feat(auth)!: remove suporte a tokens sem expiração

BREAKING CHANGE: todos os tokens existentes precisam ser regenerados.
Tokens sem expiração não são mais aceitos pelo middleware de autenticação."
```

---

## Resumo — mapa mental dos comandos

```
Desfazer mudanças:
  restore           → desfaz no working directory ou staging (não altera histórico)
  commit --amend    → reescreve o último commit (não compartilhado)
  revert            → cria um commit de desfazer (seguro em branches compartilhadas)
  reset             → move o ponteiro da branch (--soft/--mixed/--hard)

Trabalhar com histórico:
  rebase            → reaplica commits em cima de outro ponto base
  rebase -i         → reorganiza, junta, edita commits interativamente
  cherry-pick       → aplica um commit específico na branch atual
  reflog            → vê todo histórico de movimentos de HEAD (rede de segurança)

Trabalho paralelo:
  stash             → salva trabalho em progresso temporariamente
  worktree          → múltiplos working directories do mesmo repositório

Investigação:
  blame             → quem escreveu cada linha, em qual commit
  bisect            → busca binária para encontrar o commit que introduziu um bug
  log -S            → busca mudanças de uma string específica no histórico

Performance e configuração:
  sparse-checkout   → só baixa as pastas que você precisa
  .gitattributes    → configura tratamento de tipos de arquivo
  hooks / husky     → automatiza ações em momentos específicos do fluxo Git
```
