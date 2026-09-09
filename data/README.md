# `data/` — os horários

Tudo o que o site sabe sobre a FCUP está aqui. Os ficheiros formam uma cadeia:
cada um é produzido a partir do anterior, e só o último interessa ao site.

```
  SIGARRA (página de turmas)          SIGARRA (API de calendários)
            │                                      │
            │ parse_ucs.py                         │ browser_fetch.js
            ▼                                      ▼   ou fetch_timetables.sh
     subjects.json                              raw/*.json
     UCs, turmas, vagas                    eventos, um ficheiro por UC
            │                                      │
            └──────────────┬───────────────────────┘
                           │ build_data.py
                           ▼
              timetable.json  +  timetable.js
                    ← é isto que o site carrega
```

## Ficheiros versionados

| ficheiro         | tamanho | o que é |
| ---------------- | ------- | ------- |
| `timetable.js`   | ~500 KB | **O ficheiro que o site carrega.** O mesmo JSON de `timetable.json`, embrulhado em `window.TIMETABLE_DATA = …;` para poder ser carregado por `<script>`. O Chrome recusa `fetch()` em `file://`, e assim o site funciona mesmo aberto a partir do disco. |
| `timetable.json` | ~500 KB | O conjunto de dados completo: UCs, turmas, vagas e horários já normalizados. É o que os scripts de análise leem. |
| `subjects.json`  | ~230 KB | UCs, tipos de aula, turmas e vagas, extraídos da página de turmas do SIGARRA. Não tem horários. Serve de lista autoritativa e diz ao `fetch_timetables.sh` que ocorrências descarregar. |

## Ficheiros ignorados pelo git

Grandes, regeneráveis, e não são nossos para redistribuir — por isso estão no
`.gitignore`. Ver [`scripts/README.md`](../scripts/README.md) para os produzir.

| caminho         | tamanho | o que é |
| --------------- | ------- | ------- |
| `raw/`          | ~19 MB  | A resposta em bruto da API de calendários, um ficheiro por ocorrência de UC (`<occurrence_id>.json`). É a matéria-prima do `build_data.py`. |
| `raw_all.json`  | ~18 MB  | O mesmo conteúdo num único ficheiro, tal como o `browser_fetch.js` o descarrega. O `import_raw_all.py` parte-o em `raw/`. |
| `ucs.html`      | ~500 KB | A página de turmas do SIGARRA, guardada do navegador. Entrada do `parse_ucs.py`. |
| `failed.txt`    | —       | Ocorrências que o `fetch_timetables.sh` não conseguiu descarregar. Voltar a correr o script tenta só essas. |
| `fetch.log`     | —       | Registo da última extração. |
| `out/`          | varia   | Resultados do `enumerate_all.py --json`. Podem chegar a centenas de MB. |

## A estrutura de `timetable.json`

```jsonc
{
  "generated": "2026-09-08T22:30:00+00:00",   // quando foi construído
  "subjects": [
    {
      "code": "CC1007",
      "name": "Estruturas de Dados",
      "occurrence_id": 589587,        // o id da UC no SIGARRA
      "academic_year": 2,             // ano curricular
      "semester": "1S",               // "1S", "2S", "A" (anual) ou null
      "status": "ok",                 // ok | empty | missing (ver abaixo)
      "classes": [
        {
          "name": "CC1007_PL1",       // o nome da turma, a chave que junta as duas fontes
          "type": "PL",               // T, TP, PL, …
          "vacant_places": 24,
          "turma_id": 274314,
          "slots": [
            {
              "day": 4,               // 0 = segunda … 5 = sábado
              "start": "16:00",
              "end": "18:00",
              "type": "PL",
              "rooms": ["157"],
              "teachers": ["ERBM"],   // siglas dos docentes
              "occurrences": 12,      // quantas vezes acontece no semestre
              "first_date": "2026-09-18",
              "last_date": "2026-12-11",
              "semester": "1S",
              "regular": true         // ver abaixo
            }
          ]
        }
      ]
    }
  ]
}
```

### Dois campos que valem explicação

**`regular`** — a API devolve uma entrada por *ocorrência real* de uma aula: uma
aula que acontece 12 vezes aparece 12 vezes. O `build_data.py` agrupa-as em
horários semanais e conta as repetições. Menos de **3** repetições não é um
compromisso semanal — é uma reposição ou uma aula extra na última semana do
semestre. Essas ficam `regular: false`, e o site desenha-as a tracejado, não as
conta nas horas e não as acusa como sobreposição. O campo `week_days` que a API
traz não serve para isto: chega a nomear vários dias para o mesmo bloco, o que
inventaria e perderia aulas. O dia é por isso derivado da data de cada
ocorrência.

**`status`** — diz o que aconteceu ao descarregar aquela UC: `ok` (há eventos),
`empty` (a API respondeu mas sem aulas — normal quando o semestre ainda não foi
publicado) ou `missing` (não há ficheiro em `raw/`). Na extração de setembro de
2026: 464 UCs, das quais 372 `ok` e 92 `empty`. O `semester` da UC vem do nome
da ocorrência no SIGARRA e é `null` quando ela não o declara — daí as 98 UCs sem
semestre; o `semester` de cada *horário* é sempre deduzido das datas, e é esse
que o site usa para filtrar.

## Notas

- As duas fontes juntam-se pelo **nome da turma** (`CC2005_PL6`), no qual as
  duas concordam. Umas poucas turmas do calendário não existem em
  `subjects.json` (UCs partilhadas entre cursos); o `build_data.py` avisa e
  ignora-as.
- O semestre de cada horário é deduzido do mês da primeira aula: setembro a
  janeiro é `1S`, fevereiro a julho é `2S`.
- Os dados pertencem à U.Porto/FCUP. Estão aqui como cópia de conveniência, não
  são cobertos pela licença MIT do código, e podem estar desatualizados.
