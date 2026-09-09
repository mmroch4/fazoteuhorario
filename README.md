# Faz o Teu Horário · U.Porto

Construtor de horários para a Universidade do Porto (dados da Faculdade de
Ciências).

Escolhes as unidades curriculares, experimentas turmas, e a semana desenha-se ao
lado — com as sobreposições assinaladas e as horas semanais contadas.

Serve os dois momentos que a inscrição no SIGARRA deixa de fora: **decidir antes**
(chegar à inscrição com a escolha feita e um plano B, em vez de cruzar horários
à pressa na altura) e **ajustar depois** (montar a semana a partir de várias
turmas do mesmo tipo, durante o período de aulas).

**[→ Abrir o site](https://horario.miguelrocha.dev)** ·
**[→ Guia de utilização](guia.html)** ·
**[→ Sobre o projeto](sobre.html)**

> **Não é uma página oficial da FCUP nem da U.Porto.** Os dados vêm do SIGARRA,
> podem estar desatualizados, e a inscrição nas turmas faz-se no SIGARRA.

---

## O que faz

- **Grelha semanal** com as aulas de todas as UCs que escolheres, cada uma com a
  sua cor, e as sobreposições assinaladas a vermelho.
- **Várias turmas do mesmo tipo em simultâneo.** É a ideia central: uma teórica
  com duas aulas por semana não te obriga à mesma turma nos dois dias. Podes ir à
  `T1` na terça e à `T2` na quinta, e marcar as outras aulas como falta.
- **Contador de horas** por UC e por tipo de aula, que percebe que turmas
  paralelas repetem a mesma matéria e por isso não somam.
- **Gerador de combinações**: enumera todas as semanas sem sobreposições que
  cumprem as horas exigidas e ordena-as por critérios (evitar manhãs, menos
  buracos, menos dias, preferir turmas com vagas). Quando não há solução, diz
  que par de requisitos é impossível de conciliar.
- **Aulas pontuais** (reposições, aulas extra) distinguidas das semanais, para
  não contarem como compromisso nem como sobreposição.
- **Horários guardados** no navegador, com link partilhável.
- **Exportação em `.md` ou `.txt`** do horário escolhido, com as datas da primeira
  e da última aula de cada turma — pronta a dar a uma IA para criar os eventos no
  Google Calendar.
- **Impressão** só da grelha, para PDF ou papel.

## Como correr

Não é preciso instalar nada nem construir nada. É HTML, CSS e JavaScript sem
dependências — abre `index.html` no navegador:

```sh
git clone https://github.com/mmroch4/fazoteuhorario.git
cd fazoteuhorario
xdg-open index.html          # ou: open index.html   (macOS)
```

Para publicar, serve a pasta como ficheiros estáticos — GitHub Pages, Netlify,
`python3 -m http.server`, qualquer um serve. Não há back-end.

> Um servidor local (`python3 -m http.server 8000`) evita as restrições do
> Chrome a `file://` e é o mais parecido com o site publicado.

## Estrutura

```
├── index.html          construtor de horários (a página principal)
├── subject.html        catálogo de UCs e horário de cada uma
├── guia.html           guia de utilização, para quem chega de novo
├── sobre.html          porque é que o projeto existe
├── assets/             CSS e JavaScript do site
│   ├── boot.js           escolhe a faculdade e carrega os dados dela
│   ├── style.css         tema partilhado pelas quatro páginas
│   ├── common.js         cores das UCs, popup de detalhes, utilitários
│   ├── solver.js         gerador de combinações (corre no navegador)
│   └── presets.js        horários distribuídos com o site (vazio por omissão)
├── data/               os horários — ver data/README.md
│   ├── faculdades.json   índice: que faculdades existem e onde
│   ├── faculdades.js     o mesmo, para o site carregar
│   └── fcup/             uma pasta por faculdade
│       ├── timetable.js    o ficheiro que o site carrega
│       ├── timetable.json  o mesmo, para os scripts
│       └── subjects.json   UCs, turmas e vagas
├── scripts/            extração e análise — ver scripts/README.md
├── robots.txt          ┐
├── sitemap.xml         │ gerados por scripts/build_seo.py
├── site.webmanifest    ┘
└── LICENSE             MIT
```

O site precisa apenas dos quatro HTML, de `assets/` e do `timetable.js` de cada
faculdade. Tudo o resto — `scripts/`, `subjects.json`, `timetable.json` —
existe para **produzir** esses ficheiros e para análise em linha de comandos.

## Atualizar os dados

Os horários são uma fotografia do SIGARRA no dia em que foram extraídos. Para os
renovar, ver **[scripts/README.md](scripts/README.md)** — em resumo:

```sh
# 1. Guardar a página de turmas do SIGARRA como data/fcup/ucs.html, e extrair
python3 scripts/parse_ucs.py

# 2. Descarregar os eventos do calendário (browser_fetch.js é a via fiável)
python3 scripts/import_raw_all.py ~/Downloads/raw_all.json

# 3. Construir o ficheiro que o site carrega
python3 scripts/build_data.py
```

Todos os passos aceitam `-f <sigla>` para outra faculdade (`-f feup`). As
faculdades conhecidas estão em `scripts/faculdades.py`.

Requisitos: Python 3.9+ (biblioteca padrão, sem dependências). O
`fetch_timetables.sh`, alternativa em linha de comandos, precisa de `curl` e
`jq`.

## Várias faculdades

O site serve uma faculdade de cada vez, escolhida por esta ordem: `?f=<sigla>`
no URL, depois a última escolha guardada, depois a FCUP. O índice
`data/faculdades.js` (~1 KB) carrega sempre; os ~500 KB de horários de uma
faculdade só carregam quando ela é escolhida — é isso que impede o site de
crescer para vários MB à medida que faculdades são acrescentadas.

O seletor de faculdade só aparece quando houver mais do que uma com dados.

Para acrescentar uma faculdade não é preciso mexer no site: corre o pipeline
com `-f <sigla>` (ver [scripts/README.md](scripts/README.md)) e ela passa a
existir no índice.

## SEO e publicação

Os títulos, descrições, tags Open Graph, dados estruturados, `robots.txt`,
`sitemap.xml` e `site.webmanifest` são todos gerados a partir de um só sítio —
`scripts/build_seo.py` — para as quatro páginas não poderem divergir:

```sh
python3 scripts/build_seo.py
```

O bloco injetado em cada página está delimitado por `<!-- seo:begin -->` e
`<!-- seo:end -->`; correr o script outra vez substitui-o em vez de o duplicar.

**O endereço do site** está numa única constante (`SITE`) no topo desse script.
Quando decidires o domínio final, um comando trata de tudo — páginas, sitemap e
robots:

```sh
python3 scripts/build_seo.py --site https://horario.miguelrocha.dev
```

O ficheiro `CNAME` na raiz é o que diz ao GitHub Pages para servir o site em
`horario.miguelrocha.dev`. Se mudares de domínio, tens de mudar os dois: o
`CNAME` e o `--site`.

O `sitemap.xml` inclui uma entrada por UC com horário publicado, na forma
`subject.html?code=CC1007` — que é a que um motor de busca trata como URL
distinto. A página lê tanto `?code=` como `#`, e ajusta o título, a descrição e
o `canonical` à UC que está a mostrar.

## Privacidade

O site não tem conta, servidor, cookies nem análise de utilização. Tudo o que
guardas fica no teu navegador, em `localStorage`:

| chave                          | conteúdo                                       |
| ------------------------------ | ---------------------------------------------- |
| `fth-<faculdade>-horario-v1`   | seleção atual, faltas, semestre e preferências |
| `fth-<faculdade>-presets-v1`   | os horários guardados                          |
| `fth-<faculdade>-colors-v1`    | as cores escolhidas para cada UC               |
| `fth-faculdade`                | a última faculdade escolhida                   |

As chaves são por faculdade, para um horário feito na FCUP não colidir com um
feito noutra. As chaves antigas (`fcup-*`) são migradas na primeira visita.

Limpar os dados do site no navegador apaga tudo isto. Os links de partilha
(`#pick=…`) levam o horário dentro do próprio endereço — não há upload.

## Contribuir

Problemas e sugestões nos *issues*. O código é propositadamente simples: sem
build, sem framework, sem dependências, e é assim que se pretende que fique.
Duas convenções valem a pena:

- **Comentários explicam o porquê, não o quê.** Quase todas as decisões pouco
  óbvias — turmas paralelas não somarem horas, aulas pontuais não contarem como
  sobreposição, faltas serem por aula e não por turma — estão comentadas onde
  são implementadas.
- **Todos os textos visíveis estão em português.** O código e os comentários
  estão em inglês.

## Licença

[MIT](LICENSE) — © 2026 Miguel Rocha.

A licença cobre o código. **Não cobre os dados**: os horários e as fichas de UC
pertencem à U.Porto/FCUP e estão aqui apenas como cópia de conveniência. Por
isso os ficheiros de origem descarregados (`data/raw/`, `data/ucs.html`) estão
no `.gitignore`.

---

Feito por [Miguel Rocha](https://miguelrocha.dev).
