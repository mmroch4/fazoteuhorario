#!/usr/bin/env python3
"""Enumerate EVERY conflict-free timetable for a set of subjects.

  python3 scripts/enumerate_all.py CC2005 CC1007 CC2003 M2040
  python3 scripts/enumerate_all.py CC2005 CC1007 CC2003 M2040 CC3032 CC1007:T=1 CC2003:T=1
  python3 scripts/enumerate_all.py --json out.json --limit 50 CC2005 CC1007

Where solve_hours.py returns only the single best timetable, this returns all of
them, ranked, plus a diagnosis of which requirements are mutually impossible
when the answer is none.

Same model as solve_hours.py: you may switch turma freely from week to week and
from day to day, so what a requirement really fixes is a set of TIME SLOTS, not
a turma. Two turmas meeting at the same hour are one option, not two.
"""
import itertools
import json
import sys
from collections import defaultdict

import faculdades as F
from solve_hours import (FACULTY, DAYS, combos_for, disjoint,
                         m, requirements, score)

MAXPRINT = 20


def conflicting_pairs(options):
    """Requirement pairs that cannot both be satisfied, whatever else you pick."""
    bad = []
    for (la, ca), (lb, cb) in itertools.combinations(options, 2):
        if not any(disjoint(a + b) for a in ca for b in cb):
            bad.append((la, lb))
    return bad


def enumerate_all(options, cap=None):
    """All conflict-free timetables, as lists of (requirement label, slot)."""
    out = []
    order = sorted(range(len(options)), key=lambda i: len(options[i][1]))

    def walk(depth, chosen):
        if cap is not None and len(out) >= cap:
            return
        if depth == len(order):
            out.append(list(chosen))
            return
        label, cs = options[order[depth]]
        for pick in cs:
            # prune as early as possible: a partial timetable that already
            # overlaps can never be repaired by later choices
            if not disjoint([s for _, s in chosen] + list(pick)):
                continue
            walk(depth + 1, chosen + [(label, s) for s in pick])

    walk(0, [])
    return out


def render(chosen):
    byday = defaultdict(list)
    for label, s in chosen:
        byday[s["day"]].append((s["start"], s["end"], label, s))
    lines = []
    for day in sorted(byday):
        lines.append(f"    {DAYS[day]}")
        for st, en, label, s in sorted(byday[day]):
            code = label.split()[0]
            turmas = ",".join(sorted(t.replace(code + "_", "") for t in s["turmas"]))
            flag = "  ! sem vagas" if s["vacancies"] == 0 else ""
            lines.append(f"       {st}-{en}  {label:<22} turma(s): {turmas}{flag}")
    return "\n".join(lines)


def as_dict(chosen, sc):
    aft, tight, gaps, days = sc
    return {
        "horas_tarde": aft / 60, "horas_buraco": gaps / 60,
        "dias": days, "slots_sem_vagas": tight,
        "aulas": [
            {"dia": DAYS[s["day"]], "inicio": s["start"], "fim": s["end"],
             "requisito": label,
             "turmas": sorted(s["turmas"]), "salas": sorted(s["rooms"]),
             "vagas": s["vacancies"]}
            for label, s in sorted(chosen, key=lambda x: (x[1]["day"], x[1]["start"]))
        ],
    }


def main():
    args = sys.argv[1:]
    allow_restricted = "--allow-restricted" in args
    jsonpath, limit, cap = None, MAXPRINT, None
    codes, overrides = [], {}
    it = iter(range(len(args)))
    skip = set()
    for i, a in enumerate(args):
        if i in skip:
            continue
        if a == "--json":
            jsonpath = args[i + 1]; skip.add(i + 1)
        elif a == "--limit":
            limit = int(args[i + 1]); skip.add(i + 1)
        elif a == "--cap":
            cap = int(args[i + 1]); skip.add(i + 1)
        elif a.startswith("--"):
            continue
        elif ":" in a and "=" in a:
            spec, val = a.split("=", 1)
            code, typ = spec.split(":", 1)
            overrides[(code, typ)] = int(float(val) * 60)
        else:
            codes.append(a)
    if not codes:
        sys.exit(__doc__)

    data = json.load(open(F.timetable(FACULTY), encoding="utf-8"))
    byc = {s["code"]: s for s in data["subjects"]}
    missing = [c for c in codes if c not in byc]
    if missing:
        sys.exit(f"unknown subject codes: {missing}")

    subs = [byc[c] for c in codes]
    print("disciplinas:")
    for s in subs:
        print(f"  {s['code']:<8} {s['name']}")

    reqs = requirements(subs, overrides, allow_restricted)
    print("\nrequisitos (cada um tem de ser cumprido):")
    options = []
    for label, need, slots, one_per_day in reqs:
        cs = combos_for(need, slots, one_per_day)
        options.append((label, cs))
        times = ", ".join(f"{DAYS[s['day']][:3]} {s['start']}" for s in slots)
        print(f"  {label:<22} {need / 60:g}h  {len(cs):>3} opção(ões)   [{times}]")
        if not cs:
            sys.exit(f"  IMPOSSÍVEL: não há como atingir {need / 60:g}h em {label}")

    space = 1
    for _, cs in options:
        space *= len(cs)
    print(f"\nespaço de procura: {space:,} candidatos")

    sols = enumerate_all(options, cap)
    ranked = sorted(((score(c), c) for c in sols), key=lambda x: x[0])
    print(f"horários SEM sobreposição: {len(ranked):,}"
          + ("  (limitado por --cap)" if cap and len(ranked) >= cap else ""))

    if not ranked:
        print("\nNENHUM horário possível. Pares de requisitos incompatíveis:")
        for la, lb in conflicting_pairs(options):
            print(f"  x  {la}  <->  {lb}")
        return

    print(f"\n(ordenados por: menos horas depois das 13:00, menos slots sem "
          f"vagas, menos buracos, menos dias)")
    for n, (sc, chosen) in enumerate(ranked[:limit], 1):
        aft, tight, gaps, days = sc
        print(f"\n#{n}  {aft / 60:g}h após 13:00 | {gaps / 60:g}h de buracos | "
              f"{days} dias" + (f" | {tight} slot(s) sem vagas" if tight else ""))
        print(render(chosen))
    if len(ranked) > limit:
        print(f"\n... e mais {len(ranked) - limit:,} (usa --limit N ou --json)")

    if jsonpath:
        with open(jsonpath, "w", encoding="utf-8") as fh:
            json.dump({"disciplinas": [{"codigo": s["code"], "nome": s["name"]} for s in subs],
                       "requisitos": [{"nome": l, "horas": n / 60} for l, n, _, _ in reqs],
                       "total": len(ranked),
                       "horarios": [as_dict(c, sc) for sc, c in ranked]},
                      fh, ensure_ascii=False, indent=1)
        print(f"\nescrito: {jsonpath}  ({len(ranked):,} horários)")


if __name__ == "__main__":
    main()
