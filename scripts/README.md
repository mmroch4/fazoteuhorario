# `scripts/` — extrair dados e resolver horários

Dois grupos de scripts, com propósitos diferentes:

- **[Extração](#extração)** — produzem `data/timetable.js`, o único ficheiro de
  que o site precisa. Corre-os quando os horários do SIGARRA mudam.
- **[Análise](#análise)** — resolvem horários na linha de comandos. Opcionais: o
  site faz o mesmo no navegador. Servem para explorar, e para gerar horários
  para distribuir com o site.

**Requisitos:** Python 3.9 ou mais recente, só biblioteca padrão. O
`fetch_timetables.sh` (alternativo) precisa de `curl` e `jq`.

**Corre sempre a partir da raiz do repositório.** Os scripts resolvem os
caminhos a partir da localização deles, por isso funcionam de qualquer
diretório, mas os exemplos assumem a raiz.

**Todos aceitam `-f <faculdade>`** (ou `--faculty`), com a sigla do SIGARRA.
Sem a opção, assumem a FCUP:

```sh
python3 scripts/build_data.py            # FCUP
python3 scripts/build_data.py -f feup    # FEUP
python3 scripts/build_data.py --all      # todas as que já têm dados
```

As faculdades conhecidas estão em [`faculdades.py`](faculdades.py) — é o único
sítio onde se acrescenta uma. Os ficheiros de cada uma vivem em
`data/<sigla>/`, e o índice `data/faculdades.json`, escrito pelo
`build_data.py`, é o que diz ao site quais existem.

---

## Extração

O caminho completo, do SIGARRA até ao ficheiro que o site carrega. Ver o
diagrama em [`data/README.md`](../data/README.md).

### 1. Que UCs existem → `data/<sigla>/subjects.json`

A lista de UCs, turmas e vagas não está em nenhuma API: está numa tabela HTML.

1. No SIGARRA, abre a página de **turmas** da FCUP (a que lista todas as UCs com
   as suas turmas e vagas).
2. Guarda-a como `data/<sigla>/ucs.html` (<kbd>Ctrl</kbd>+<kbd>S</kbd>, "só HTML").
3. Extrai:

```sh
python3 scripts/parse_ucs.py            # lê data/fcup/ucs.html
# 723 subject/type rows -> data/fcup/subjects.json
# 1472 classes total
```

`parse_ucs.py <entrada.html> [saída.json]` — sem o segundo argumento escreve em
`data/subjects.json`. É um parser de tabela: as linhas-chave têm quatro células
com `rowspan` (ano, nome, código, tipo) e o resto da linha são pares
*(turma, vagas)*.

### 2. Quando são as aulas → `data/<sigla>/raw/`

Os horários vêm da API de calendários do SIGARRA. Não é preciso login, mas está
atrás da Cloudflare. Há duas vias.

**Via A — do navegador (fiável, recomendada).** A Cloudflare aceita um separador
real de navegador sem discussão, e o pedido é *same-origin*, por isso não há
CORS nem cookies para copiar.

1. Abre <https://sigarra.up.pt/fcup/pt/web_page.inicial> no Chrome.
2. <kbd>F12</kbd> → Console (escreve `allow pasting` se o Chrome pedir).
3. Cola o conteúdo de `scripts/browser_fetch.js` e <kbd>Enter</kbd>. Demora
   alguns minutos e descarrega `raw_all.json`.
4. Parte o ficheiro num por ocorrência:

```sh
python3 scripts/import_raw_all.py ~/Downloads/raw_all.json
# wrote 465 files to .../data/raw/
```

A lista de ocorrências está no topo do `browser_fetch.js`. Nunca a escrevas à
mão — gera-a com o [`ids.py`](#idspy--a-lista-de-ocorrências-para-o-browser_fetchjs):

```sh
python3 scripts/ids.py -f feup --js
```

**Via B — do terminal.** Mais prático de automatizar, mas apanha 403 da
Cloudflare com frequência.

```sh
scripts/fetch_timetables.sh              # tudo, saltando o que já está descarregado
scripts/fetch_timetables.sh 589587       # só estas ocorrências
FORCE=1 scripts/fetch_timetables.sh      # voltar a descarregar mesmo o que está em cache
DELAY=3 scripts/fetch_timetables.sh      # segundos entre pedidos (por omissão 1.5)
YEAR=2027 scripts/fetch_timetables.sh    # outro ano letivo
```

Envia um conjunto completo de cabeçalhos de Chrome (largar qualquer um deles dá
403) e recua exponencialmente quando é recusado. As falhas ficam em
`data/failed.txt`; voltar a correr tenta só essas.

### 3. Juntar tudo → `data/<sigla>/timetable.js`

```sh
python3 scripts/build_data.py
# 464 subjects -> data/timetable.json (493 KB)
#   raw files: ok=372 empty=92 missing=0
#   classes with slots: 986, without: 486
#   weekly slots: 1666 (of which one-off: 500)
```

Junta `subjects.json` (o quê, quantas vagas) com `raw/*.json` (quando, onde),
pelo nome da turma. Escreve `timetable.json` **e** `timetable.js` — o segundo é
o primeiro embrulhado em `window.TIMETABLE_DATA = …;`, porque o Chrome recusa
`fetch()` em `file://` e o site tem de funcionar aberto a partir do disco.

É aqui que se decide o que é uma aula semanal: a API devolve uma entrada por
ocorrência real, e menos de 3 ocorrências passa a `regular: false`. Ver
[`data/README.md`](../data/README.md#dois-campos-que-valem-explicação).

O aviso `WARNING N calendar classes not in subjects.json` é normal: são turmas
de UCs partilhadas entre cursos.

---

## Análise

Opcionais. Os três leem `data/timetable.json` e aceitam códigos de UC.

### `solve_schedule.py` — uma turma por tipo

O modelo de inscrição do SIGARRA: escolhe-se **uma** turma por tipo de aula e é
essa para o semestre inteiro.

```sh
python3 scripts/solve_schedule.py CC2005 CC1007 CC2003 M2040
python3 scripts/solve_schedule.py CC2005 CC1007 --with-vacancies      # só turmas com vagas
python3 scripts/solve_schedule.py CC2005 CC1007 --save-preset="1.º ano turno A"
```

Ordena por: sem sobreposições → menos horas depois das 13h → menos dias e menos
tempo morto. Com `--save-preset` acrescenta o resultado a `assets/presets.js`,
que o site mostra como "Exemplos incluídos" — para distribuir um horário **com o
site**. Os horários pessoais não se guardam assim: guardam-se no próprio site,
que os põe no `localStorage`.

### `solve_hours.py` — trocar de turma entre dias

O modelo que o site usa. O que importa é cumprir as **horas semanais** de cada
UC e tipo; a turma pode variar de dia para dia.

```sh
python3 scripts/solve_hours.py CC2005 CC1007 CC2003 M2040
python3 scripts/solve_hours.py CC2005 CC1007 CC1007:T=1     # só 1h de CC1007 T
```

O que **não** se pode é duplicar a mesma sessão: turmas paralelas de uma teórica
repetem a matéria, por isso 2h de `CC1007 T` significam a hora de terça *e* a de
quinta, não duas horas quaisquer. Quando cada turma se reúne uma vez por semana
(o caso das PL/TP) as turmas são de facto intermutáveis e qualquer horário
serve. `assets/solver.js` implementa o mesmo modelo em JavaScript.

### `enumerate_all.py` — todas as soluções, não só a melhor

```sh
python3 scripts/enumerate_all.py CC2005 CC1007 CC2003 M2040
python3 scripts/enumerate_all.py --limit 50 --json data/out/combos.json CC2005 CC1007
```

Devolve **todos** os horários sem sobreposições, ordenados, e — quando não há
nenhum — diz que pares de requisitos são impossíveis de conciliar, que é a
informação útil. Escreve com `--json` para `data/out/` (ignorado pelo git: os
ficheiros chegam a centenas de MB).

### `ids.py` — a lista de ocorrências para o `browser_fetch.js`

```sh
python3 scripts/ids.py -f feup --js
```

Imprime `const FACULTY` e `const IDS = [...]` prontos a colar no topo do
`browser_fetch.js`. Assim a lista sai sempre do catálogo que o `parse_ucs.py`
acabou de ler, em vez de ser mantida à mão.

---

## SEO

### `build_seo.py` — metadados, robots.txt e sitemap.xml

```sh
python3 scripts/build_seo.py
python3 scripts/build_seo.py --site https://horario.miguelrocha.dev
```

Injeta em cada página o `<title>`, a meta description, o `canonical`, as tags
Open Graph/Twitter, os ícones e os dados estruturados JSON-LD; escreve
`robots.txt`, `site.webmanifest` e `sitemap.xml`. Tudo o que tem de concordar
entre páginas está definido no dicionário `PAGES`, no topo do ficheiro — é aí
que se muda um título ou uma descrição, nunca no HTML.

O bloco fica delimitado por `<!-- seo:begin -->` / `<!-- seo:end -->` e é
substituído a cada execução, por isso correr o script duas vezes é seguro.

Dois pormenores que valem a pena:

- **O endereço do site vive na constante `SITE`.** `--site` reescreve-a neste
  ficheiro e regenera tudo, para o domínio existir num só sítio.
- **As perguntas frequentes do JSON-LD são lidas do `guia.html`**, do bloco
  `<dl class="faq">`. Assim os dados estruturados não podem contradizer o que a
  página diz — editar o guia chega, basta voltar a correr o script.

---

## Notas

- Os scripts não têm dependências e não escrevem fora de `data/` e de
  `assets/presets.js`.
- Os caminhos são resolvidos a partir de `Path(__file__).parent.parent`, por
  isso correm bem de qualquer diretório e de qualquer `cron`.
- Se algo falhar, o primeiro sítio a olhar é `data/failed.txt` e o valor de
  `status` de cada UC em `timetable.json`.
