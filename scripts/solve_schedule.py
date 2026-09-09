#!/usr/bin/env python3
"""Pick one turma per (subject, class type) to build the best weekly timetable.

  python3 scripts/solve_schedule.py CC2005 CC1007 CC2003 M2040
  python3 scripts/solve_schedule.py -f feup <códigos>

Preferences (in order):
  1. no overlaps at all
  2. as few hours as possible after 13:00
  3. fewer days on campus, and less dead time between classes

Only *regular* slots (>= 3 meetings) count as commitments; one-off sessions are
reported separately so they can't distort the weekly picture.
"""
import itertools
import json
import os
import re
import sys
from collections import defaultdict
import faculdades as F

FACULTY = F.arg(sys.argv)

DAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
NOON = 13 * 60          # anything after this counts as "afternoon"
m = lambda t: int(t[:2]) * 60 + int(t[3:5])


def load(codes):
    data = json.load(open(F.timetable(FACULTY), encoding="utf-8"))
    byc = {s["code"]: s for s in data["subjects"]}
    missing = [c for c in codes if c not in byc]
    if missing:
        sys.exit(f"unknown subject codes: {missing}")
    return [byc[c] for c in codes]


def decisions(subjects, need_vacancy=False, allow_restricted=False):
    """One decision per (subject, class type); options are the turmas."""
    out = []
    for sub in subjects:
        bytype = defaultdict(list)
        for cl in sub["classes"]:
            # "M2040_TP3 (L:Q)" is reserved for Licenciatura em Química; the
            # catalogue also uses L:CTA and L:SDIB. Not yours unless you say so.
            if not allow_restricted and "L:" in cl["name"]:
                continue
            regular = [s for s in cl["slots"] if s.get("regular")]
            if regular:
                bytype[cl["type"]].append((cl, regular))
        for t, opts in sorted(bytype.items()):
            # Dropping full turmas can make a subject unschedulable; only apply
            # the filter when it still leaves something to choose from.
            if need_vacancy:
                free = [o for o in opts if o[0]["vacant_places"] > 0]
                if free:
                    opts = free
            out.append((sub, t, opts))
    return out


def overlap(a, b):
    if a["day"] != b["day"]:
        return 0
    return max(0, min(m(a["end"]), m(b["end"])) - max(m(a["start"]), m(b["start"])))


def score(choice):
    """(clash, afternoon, days, gaps, earliest-start-bonus) - all minimised."""
    slots = [(sub, cl, s) for sub, cl, ss in choice for s in ss]
    clash = 0
    for (_, _, a), (_, _, b) in itertools.combinations(slots, 2):
        clash += overlap(a, b)

    byday = defaultdict(list)
    for _, _, s in slots:
        byday[s["day"]].append((m(s["start"]), m(s["end"])))

    # Measure afternoon and gaps on MERGED intervals: when two classes overlap
    # you are only ever on campus once, so summing both would double-count.
    afternoon = gaps = 0
    for day, iv in byday.items():
        iv.sort()
        merged = []
        for st, en in iv:
            if merged and st <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], en))
            else:
                merged.append((st, en))
        afternoon += sum(max(0, en - max(st, NOON)) for st, en in merged)
        for i in range(1, len(merged)):
            gaps += merged[i][0] - merged[i - 1][1]
    return clash, afternoon, len(byday), gaps


def describe(choice):
    slots = [(sub, cl, s) for sub, cl, ss in choice for s in ss]
    byday = defaultdict(list)
    for sub, cl, s in slots:
        byday[s["day"]].append((s["start"], s["end"], sub["code"], cl["name"],
                                s["rooms"], cl["vacant_places"]))
    lines = []
    for day in sorted(byday):
        for st, en, code, name, rooms, vagas in sorted(byday[day]):
            # A 0-vacancy turma may simply not be available when you enrol.
            warn = "  ⚠ SEM VAGAS" if vagas == 0 else f"  {vagas} vagas"
            lines.append(f"    {DAYS[day]:<8} {st}-{en}  {code:<8} {name:<18} "
                         f"sala {','.join(rooms) or '-':<10}{warn}")
    return "\n".join(lines)


PRESETS = F.ROOT / "assets" / "presets.js"
# Kept in sync with the comment at the top of presets.js: rewriting the file
# replaces it, and the format notes are the only documentation it has.
HEADER = """/* Horários que acompanham o site, mostrados em "Horários guardados" como
   "Exemplos incluídos" — só de leitura, iguais para toda a gente.

   Os horários de cada pessoa NÃO vivem aqui: ficam no navegador dela
   (localStorage, chave "fcup-presets-v1"), guardados pelo botão "Guardar o
   horário atual". Isto é só para distribuir um horário com o próprio site.

   Formato de cada entrada:
     name   obrigatório — o título do botão
     picks  obrigatório — nomes das turmas, tal como aparecem nos dados
     note   opcional    — linha de descrição por baixo do nome
     skips  opcional    — aulas a marcar como falta, "TURMA|dia|HH:MM"
                          (dia: 0 = segunda … 5 = sábado)
     sem    opcional    — "1S" ou "2S"; carregar o horário troca o semestre

   Gerado por:  python3 scripts/solve_schedule.py <códigos> --save-preset="Nome"     */
window.TIMETABLE_PRESETS = """


def morning_of(combo):
    """Minutes of class before 13:00, counted on merged intervals."""
    byday = defaultdict(list)
    for _, _, ss in combo:
        for s in ss:
            byday[s["day"]].append((m(s["start"]), m(s["end"])))
    total = 0
    for iv in byday.values():
        iv.sort()
        merged = []
        for st, en in iv:
            if merged and st <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], en))
            else:
                merged.append((st, en))
        total += sum(max(0, min(en, NOON) - st) for st, en in merged)
    return total


def save_preset(name, combo, stats):
    """Add (or replace) a named preset in presets.js."""
    existing = []
    if PRESETS.exists():
        txt = open(PRESETS, encoding="utf-8").read()
        mt = re.search(r"window\.TIMETABLE_PRESETS\s*=\s*(\[.*?\]);", txt, re.S)
        if mt:
            try:
                existing = json.loads(mt.group(1))
            except json.JSONDecodeError:
                print(f"  ! {PRESETS} is not machine-readable; leaving it alone.")
                return
    clash, aft, days, gaps = stats
    entry = {
        "name": name,
        "note": (f"{morning_of(combo)/60:g}h "
                 f"de manhã · {aft/60:g}h de tarde · {days} dias · {gaps/60:g}h de buracos"
                 + (f" · {clash} min sobrepostos (inevitável)" if clash else " · sem sobreposições")),
        "picks": sorted(cl["name"] for _, cl, _ in combo),
    }
    existing = [e for e in existing if e.get("name") != name] + [entry]
    with open(PRESETS, "w", encoding="utf-8") as fh:
        fh.write(HEADER + json.dumps(existing, ensure_ascii=False, indent=2) + ";\n")
    print(f"\nsaved preset {name!r} to {PRESETS} ({len(entry['picks'])} turmas)")


def main():
    args = sys.argv[1:]
    need_vac = "--with-vacancies" in args
    allow_restricted = "--allow-restricted" in args
    preset_name = next((a.split("=", 1)[1] for a in args
                        if a.startswith("--save-preset=")), None)
    codes = [a for a in args if not a.startswith("--")]
    if not codes:
        sys.exit(__doc__)
    subjects = load(codes)
    decs = decisions(subjects, need_vac, allow_restricted)

    total = 1
    for _, _, o in decs:
        total *= len(o)
    print(f"{len(decs)} decisions, {total:,} combinations")
    for sub, t, opts in decs:
        print(f"  {sub['code']:<8} {t:<3} {len(opts):>2} option(s): "
              + ", ".join(cl["name"].replace(sub["code"] + "_", "") for cl, _ in opts))

    # one-off sessions are excluded from the weekly optimisation - list them
    extras = []
    for sub in subjects:
        for cl in sub["classes"]:
            for s in cl["slots"]:
                if not s.get("regular"):
                    extras.append(f"    {cl['name']:<18} {DAYS[s['day']]} {s['start']}-{s['end']}"
                                  f"  ({s['occurrences']}x, {s['first_date']})")
    if extras:
        print("\nOne-off sessions (not weekly, excluded from the optimisation):")
        print("\n".join(sorted(set(extras))))

    results = []
    for combo in itertools.product(*[[(sub, cl, ss) for cl, ss in o] for sub, _, o in decs]):
        results.append((score(combo), combo))
    results.sort(key=lambda r: (r[0][0], r[0][1], r[0][2] * 60 + r[0][3]))

    floor = results[0][0][0]
    tier = [r for r in results if r[0][0] == floor]
    if floor == 0:
        print(f"\nconflict-free combinations: {len(tier):,} of {total:,}")
    else:
        print(f"\nNo conflict-free combination. Best possible keeps {floor} min/week "
              f"of overlap ({len(tier):,} ways to achieve it).")

    seen, shown = set(), 0
    for (clash, aft, days, gaps), combo in tier:
        sig = (aft, days, gaps)
        if sig in seen:
            continue
        seen.add(sig)
        shown += 1
        print(f"\n--- option {shown}: {aft/60:.1f}h after 13:00 | {days} days on campus"
              f" | {gaps/60:.1f}h of gaps ---")
        print(describe(combo))
        if clash:
            slots = [(sub, cl, s) for sub, cl, ss in combo for s in ss]
            print("    overlaps:")
            for (s1, c1, a), (s2, c2, b) in itertools.combinations(slots, 2):
                ov = overlap(a, b)
                if ov:
                    print(f"      {c1['name']} × {c2['name']} — {DAYS[a['day']]}, {ov} min")
        if shown == 1 and preset_name:
            save_preset(preset_name, combo, (clash, aft, days, gaps))
        if shown == 5:
            break


if __name__ == "__main__":
    main()
