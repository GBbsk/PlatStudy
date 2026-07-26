# Módulo Extra — BEM: Metodologia de Nomenclatura CSS

## Fontes deste módulo

- **getbem.com** — o site oficial da metodologia, mantido pela comunidade que a formalizou
- **Yandex** — a empresa russa de tecnologia onde o BEM foi originalmente desenvolvido internamente (por volta de 2009), antes de ser publicado como metodologia aberta
- **"CSS: The Definitive Guide", Eric Meyer & Estelle Weyl, O'Reilly, 5ª edição** — referência canônica de CSS que discute problemas de especificidade e escala em projetos grandes, o pano de fundo que justifica metodologias como BEM
- Nota de transparência: assim como nos módulos anteriores, não fiz busca ativa — isso é conhecimento estável do meu treinamento sobre uma metodologia amplamente documentada e pouco mudada desde sua criação.

---

## O que estava faltando, e por que é sutil de perceber sozinho

No curso de CSS você usa classes como `.card-projeto`, `.navbar`, `.hero`, `.botao`. Funciona bem — porque o portfólio é pequeno, e você é a única pessoa escrevendo esse CSS. O problema com nomenclatura CSS não aparece em projetos pequenos; ele aparece especificamente quando **duas condições se combinam**: o projeto cresce (centenas de componentes) e/ou mais de uma pessoa escreve CSS nele. Nenhuma das duas condições existiu nos seus projetos até agora, então o problema nunca apareceu — mas ele é extremamente real assim que você trabalha em um time.

---

## O problema estrutural que BEM resolve

CSS tem uma característica que o diferencia de praticamente toda linguagem de programação que você já usou: **todo seletor é global por padrão**. Em JavaScript, uma variável dentro de uma função não vaza para fora dela — você já viu isso com escopo de função e closures no curso de JS. Em CSS, não existe essa proteção nativa: uma classe `.title` definida em qualquer arquivo CSS do projeto afeta **qualquer elemento** com essa classe, em **qualquer lugar** da página, sem nenhum aviso.

```css
/* arquivo: card.css */
.title {
  font-size: 1.2rem;
  color: gray;
}

/* arquivo: hero.css, escrito por outra pessoa, meses depois */
.title {
  font-size: 3rem;
  color: white;
}
/* Sem querer, a segunda regra pode sobrescrever a primeira,
   ou vice-versa, dependendo só da ORDEM de carregamento dos arquivos —
   não existe isolamento entre eles */
```

Isso é exatamente o tipo de "vazamento de escopo" que você aprendeu a evitar em JavaScript com módulos (`require`/`module.exports` no curso de Node) — CSS, por padrão, não tem esse mecanismo. BEM é uma **convenção de nomenclatura** (não uma ferramenta, não uma extensão da linguagem) que simula esse isolamento manualmente, através de um padrão de nomes que qualquer pessoa do time segue.

---

## A estrutura: Block, Element, Modifier

```
Block__Element--Modifier
```

**Block (Bloco)** — um componente independente e reutilizável, que faz sentido sozinho. `card`, `navbar`, `botao`, `formulario-contato`.

**Element (Elemento)** — uma parte do bloco que não faz sentido fora dele. Um `title` só existe dentro de um `card` específico — ele não é reutilizável isoladamente. Separado do bloco por dois underscores: `__`.

**Modifier (Modificador)** — uma variação do bloco ou elemento — um estado ou versão diferente. Separado por dois hífens: `--`.

```css
/* Block */
.card { }

/* Element — parte do card, sem sentido fora dele */
.card__titulo { }
.card__descricao { }
.card__imagem { }

/* Modifier — variação do card */
.card--destaque { }
.card--desabilitado { }

/* Modifier em um elemento específico */
.card__titulo--grande { }
```

```html
<article class="card card--destaque">
  <img class="card__imagem" src="..." alt="...">
  <h3 class="card__titulo card__titulo--grande">Linkr API</h3>
  <p class="card__descricao">Rede social minimalista...</p>
</article>
```

---

## Por que essa sintaxe específica, e não outra qualquer

A escolha de `__` e `--` (em vez de, por exemplo, um único hífen para tudo) é deliberada: hífen simples já é usado dentro de nomes compostos comuns em CSS (`card-projeto`, `menu-principal`), então usar só hífen simples criaria ambiguidade — `.card-titulo` poderia ser lido como "um bloco chamado card-titulo" ou "o elemento titulo do bloco card". Os delimitadores duplos (`__` e `--`) nunca aparecem naturalmente em nomes compostos normais, então são inequívocos: ao ver `__`, você sabe imediatamente "isso é um elemento"; ao ver `--`, sabe "isso é uma variação".

---

## O que BEM resolve na prática — reescrevendo o CSS do portfólio

Compare a versão que você já escreveu com a versão em BEM:

```css
/* ANTES — classes soltas, sem indicação de hierarquia ou relação */
.card-projeto { }
.card-projeto h3 { }          /* depende da estrutura HTML específica para funcionar */
.card-projeto p { }           /* se você mudar de <p> para <span>, quebra */
.card-projeto .links { }      /* .links pode colidir com outro .links em outro lugar */

/* DEPOIS — em BEM, cada classe é auto-descritiva e independente da estrutura HTML */
.card { }
.card__titulo { }             /* funciona em QUALQUER tag — h3, span, o que for */
.card__descricao { }
.card__links { }              /* nome único, nunca colide com outro .links do projeto */
```

A diferença central: no "antes", o CSS depende de **estrutura HTML específica** (`.card-projeto h3` só funciona se o título realmente for um `<h3>` dentro do card). No "depois" (BEM), cada classe é **autocontida** — não importa qual tag HTML você usa, a classe `.card__titulo` sempre significa a mesma coisa, e você pode trocar a tag sem quebrar o CSS.

---

## Modificadores substituindo cascata condicional

```css
/* ANTES — você precisaria de seletores compostos ou !important
   para expressar "este card específico é diferente" */
.card-projeto.especial {
  border-color: gold;
}

/* DEPOIS — o modificador é explícito na própria classe,
   sem depender de COMBINAR duas classes e torcer pela especificidade certa */
.card--destaque {
  border-color: gold;
}
```

```html
<!-- A leitura do HTML já comunica a intenção, sem precisar abrir o CSS para entender -->
<article class="card card--destaque">
```

Isso conecta diretamente com o que você aprendeu na Aula 2.1 do curso de CSS sobre especificidade e cascata: BEM é, em essência, uma estratégia para **manter a especificidade sempre baixa e uniforme** — toda classe BEM tem especificidade `0-1-0` (uma única classe), nunca combina seletores (`.card.destaque`), nunca depende de aninhamento (`.card h3`). Isso elimina a maior fonte de bugs de cascata que você documentou naquela aula: conflitos de especificidade inesperados.

---

## Quando BEM é exagero (honestidade sobre o tradeoff)

Para o seu portfólio pessoal, sozinho, com um CSS de algumas centenas de linhas, BEM é opcional — o ganho é real mas pequeno, porque o problema que ele resolve (colisão de nomes, ambiguidade de escopo) exige escala para se manifestar. Vale aplicar mesmo assim, porque construir o hábito agora custa pouco e paga dividendos quando você trabalhar em projetos maiores ou em time.

Onde BEM se torna claramente necessário: qualquer projeto com múltiplos desenvolvedores escrevendo CSS, ou qualquer projeto grande o suficiente para que você mesmo não lembre, três meses depois, se uma classe é segura de reutilizar.

---

## Resumo

- CSS não tem isolamento de escopo nativo — toda classe é global por padrão, diferente de variáveis em JavaScript
- BEM (Block, Element, Modifier) é uma convenção de nomenclatura, criada na Yandex, que simula esse isolamento através de nomes estruturados e inequívocos
- `Block__Element` marca uma parte que só faz sentido dentro do bloco; `Block--Modifier` marca uma variação do bloco
- Os delimitadores duplos (`__`, `--`) foram escolhidos por serem inequívocos — nunca aparecem em nomes compostos comuns
- BEM mantém a especificidade sempre uniforme e baixa (uma classe = `0-1-0`), evitando a fonte mais comum de bugs de cascata em CSS
- O ganho de BEM escala com o tamanho do projeto e o número de pessoas escrevendo CSS — em projetos pequenos e solo, é uma boa prática opcional; em projetos de time, é praticamente necessário
