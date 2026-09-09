#!/usr/bin/env python3
"""Build a timetable by filling required hours per subject/type from ANY turma.

  python3 scripts/solve_hours.py CC2005 CC1007 CC2003 M2040
  python3 scripts/solve_hours.py -f feup <códigos>

Unlike solve_schedule.py (which picks one turma per type, the SIGARRA enrolment
model), you may mix turmas: attend CC1007's Tuesday lecture with T1 at 14:00 and
its Thursday lecture with T2 at 15:00.

What you may NOT do is double up on the same session. Parallel turmas of a
lecture repeat the same content, so 2h of CC1007 T means Tuesday's hour AND
Thursday's hour - not any two hours. Where each turma meets once a week (PL/TP)
the turmas genuinely are interchangeable and any one slot satisfies it.

Required hours default to one turma's weekly load; override with CC1007:T=3.
"""
import itertools
import json
import sys
from collections import defaultdict
import faculdades as F

# Which faculty's data to solve against. `-f xx` anywhere in the arguments.
FACULTY = F.arg(sys.argv)

DAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
NOON = 13 * 60
m = lambda t: int(t[:2]) * 60 + int(t[3:5])


def _slot_entry(slots, cl, s):
    key = (s["day"], s["start"], s["end"])
    ent = slots.setdefault(key, {
        "day": s["day"], "start": s["start"], "end": s["end"],
        "mins": m(s["end"]) - m(s["start"]),
        "rooms": set(), "turmas": set(), "vacancies": 0,
    })
    ent["rooms"].update(s["rooms"])
    ent["turmas"].add(cl["name"])
    ent["vacancies"] = max(ent["vacancies"], cl["vacant_places"])
    return ent


def requirements(subjects, overrides, allow_restricted=False):
    """[(label, required_minutes, [slot, ...]), ...]

    Parallel turmas of a lecture repeat the SAME content: CC1007_T1 and _T2 both
    teach Tuesday and Thursday. So hours are not fungible - you need Tuesday's
    session and Thursday's session, and may only choose the TIME of each. Where
    every turma meets once a week (the PL case) the turmas really are
    interchangeable and any single slot will do.
    """
    reqs = []
    for sub in subjects:
        bytype = defaultdict(list)
        for cl in sub["classes"]:
            if not allow_restricted and "L:" in cl["name"]:
                continue
            regular = [s for s in cl["slots"] if s.get("regular")]
            if regular:
                bytype[cl["type"]].append((cl, regular))

        for typ, opts in sorted(bytype.items()):
            per_turma = {len(reg) for _, reg in opts}
            daysets = {frozenset(s["day"] for s in reg) for _, reg in opts}

            if per_turma == {1}:
                # One weekly session; every turma is an alternative time for it.
                slots = {}
                for cl, reg in opts:
                    for s in reg:
                        _slot_entry(slots, cl, s)
                need = overrides.get((sub["code"], typ),
                                     max(s["mins"] for s in slots.values()))
                reqs.append((f"{sub['code']} {typ}", need,
                             sorted(slots.values(), key=lambda s: (s["day"], s["start"])), False))
            elif len(daysets) == 1:
                override = overrides.get((sub["code"], typ))
                if override is None:
                    # Several sessions a week, same weekdays in every turma: one
                    # requirement per weekday, choose the time on each.
                    for day in sorted(next(iter(daysets))):
                        slots = {}
                        for cl, reg in opts:
                            for s in reg:
                                if s["day"] == day:
                                    _slot_entry(slots, cl, s)
                        need = max(s["mins"] for s in slots.values())
                        reqs.append((f"{sub['code']} {typ} ({DAYS[day][:3]})", need,
                                     sorted(slots.values(), key=lambda s: s["start"]), False))
                else:
                    # Explicitly asking for fewer hours than the full load: pick
                    # which sessions to attend. Never two slots on the same day -
                    # that is the same session twice.
                    slots = {}
                    for cl, reg in opts:
                        for s in reg:
                            _slot_entry(slots, cl, s)
                    reqs.append((f"{sub['code']} {typ} (parcial)", override,
                                 sorted(slots.values(), key=lambda s: (s["day"], s["start"])),
                                 True))
            else:
                # Turmas disagree on which weekdays they use - fall back to
                # hours, and say so rather than guessing.
                print(f"  ! {sub['code']} {typ}: turmas use different weekdays "
                      f"{[sorted(x) for x in daysets]}; filling by hours only.")
                slots = {}
                for cl, reg in opts:
                    for s in reg:
                        _slot_entry(slots, cl, s)
                need = overrides.get((sub["code"], typ),
                                     max(sum(m(s["end"]) - m(s["start"]) for s in reg)
                                         for _, reg in opts))
                reqs.append((f"{sub['code']} {typ}", need,
                             sorted(slots.values(), key=lambda s: (s["day"], s["start"])), True))
    return reqs


def disjoint(slots):
    for a, b in itertools.combinations(slots, 2):
        if a["day"] == b["day"] and m(a["start"]) < m(b["end"]) and m(b["start"]) < m(a["end"]):
            return False
    return True


def combos_for(need, slots, one_per_day=False):
    """Minimal non-overlapping slot sets whose total >= need."""
    out = []
    for k in range(1, len(slots) + 1):
        for pick in itertools.combinations(slots, k):
            if sum(s["mins"] for s in pick) < need:
                continue
            # Two slots on the same weekday are the same session twice.
            if one_per_day and len({s["day"] for s in pick}) != len(pick):
                continue
            # minimal: dropping any slot must break the requirement
            if any(sum(x["mins"] for x in pick if x is not s) >= need for s in pick):
                continue
            if disjoint(pick):
                out.append(pick)
        if out and k >= 2:
            break          # deeper combinations can only be non-minimal
    return out


def merged_days(chosen):
    byday = defaultdict(list)
    for _, s in chosen:
        byday[s["day"]].append((m(s["start"]), m(s["end"])))
    out = {}
    for day, iv in byday.items():
        iv.sort()
        mg = []
        for st, en in iv:
            if mg and st <= mg[-1][1]:
                mg[-1] = (mg[-1][0], max(mg[-1][1], en))
            else:
                mg.append((st, en))
        out[day] = mg
    return out


def score(chosen):
    days = merged_days(chosen)
    afternoon = gaps = 0
    for mg in days.values():
        afternoon += sum(max(0, en - max(st, NOON)) for st, en in mg)
        gaps += sum(mg[i][0] - mg[i - 1][1] for i in range(1, len(mg)))
    # prefer slots that still have vacancies
    tight = sum(1 for _, s in chosen if s["vacancies"] == 0)
    return afternoon, tight, gaps, len(days)


def main():
    args = sys.argv[1:]
    allow_restricted = "--allow-restricted" in args
    overrides = {}
    codes = []
    for a in args:
        if a.startswith("--"):
            continue
        if ":" in a and "=" in a:
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

    reqs = requirements([byc[c] for c in codes], overrides, allow_restricted)
    print("requirements (each must be satisfied):")
    options = []
    for label, need, slots, one_per_day in reqs:
        cs = combos_for(need, slots, one_per_day)
        options.append((label, cs))
        print(f"  {label:<22} {need/60:g}h  from {len(slots)} slot(s)"
              f" -> {len(cs)} way(s)")
        if not cs:
            sys.exit(f"  IMPOSSIBLE: cannot reach {need/60:g}h for {label}")

    total = 1
    for _, cs in options:
        total *= len(cs)
    print(f"\nsearch space: {total:,} candidate timetables")

    best = None
    feasible = 0
    for pick in itertools.product(*[cs for _, cs in options]):
        chosen = [(options[i][0], s) for i, group in enumerate(pick) for s in group]
        if not disjoint([s for _, s in chosen]):
            continue
        feasible += 1
        sc = score(chosen)
        if best is None or sc < best[0]:
            best = (sc, chosen)

    print(f"conflict-free timetables: {feasible:,}")
    if not best:
        print("\nNo overlap-free timetable exists, even with fully flexible turmas.")
        return

    (aft, tight, gaps, days), chosen = best
    print(f"\nBEST: {aft/60:g}h após 13:00 | {gaps/60:g}h de buracos | {days} dias"
          + (f" | {tight} slot(s) sem vagas" if tight else ""))
    byday = defaultdict(list)
    for label, s in chosen:
        byday[s["day"]].append((s["start"], s["end"], label, s))
    for day in sorted(byday):
        print(f"  {DAYS[day]}")
        for st, en, label, s in sorted(byday[day]):
            code = label.split()[0]
            turmas = ",".join(sorted(t.replace(code + "_", "") for t in s["turmas"]))
            flag = "  ⚠ sem vagas" if s["vacancies"] == 0 else ""
            print(f"     {st}-{en}  {label:<22} turma(s): {turmas:<12}"
                  f" sala {','.join(sorted(s['rooms'])) or '-':<10}{flag}")


if __name__ == "__main__":
    main()
