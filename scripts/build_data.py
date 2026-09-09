#!/usr/bin/env python3
"""Merge subjects.json + raw/*.json into one dataset per faculty for the UI.

  python3 scripts/build_data.py                  # a FCUP
  python3 scripts/build_data.py -f feup          # outra faculdade
  python3 scripts/build_data.py --all            # todas as que têm dados

Writes data/<faculdade>/timetable.json and .js, and refreshes the index in
data/faculdades.json that the site reads to know which faculties exist.

subjects.json gives the authoritative list of subjects/classes and their
vacancies; the calendar API gives when and where each class actually meets.
They join on class name (e.g. "CC2005_PL6"), which the two sources agree on.

The API returns one entry per actual occurrence (a class meeting 12 times
appears 12 times). We group those into weekly slots and keep the occurrence
count, because "Tuesdays, 10 times" and "one Monday in December" are very
different commitments and the raw `week_days` field does not distinguish them.
"""
import datetime
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from datetime import timezone

import faculdades as F

SEMESTER_RE = re.compile(r"\((\dS|A)\)\s*$")
# Fewer than this many meetings is an extra session, not a weekly commitment.
REGULAR_MIN = 3


def hhmm(t):
    return (t or "")[:5]


# SIGARRA prefixes a teacher's name with their staff number: "203447 - Maria
# Gabriela Faria Arala Chaves". The number means nothing to a student, so it is
# dropped. A few entries arrive without it ("Docente Convidado") and are kept
# whole. The `acronym` ("MGFAC") is only the fallback: it is not unique either -
# "RG" is two different people - and nobody knows their lecturer by initials.
STAFF_NO_RE = re.compile(r"^\s*\d+\s*-\s*")


def person_name(person):
    name = STAFF_NO_RE.sub("", (person.get("name") or "").strip()).strip()
    return name or (person.get("acronym") or "").strip()


def load_events(occ_id, raw_dir):
    """Return ({class_name: [slot, ...]}, semester, status, {class_name: turma_id})."""
    path = raw_dir / f"{occ_id}.json"
    if not path.exists():
        return {}, None, "missing", {}
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)

    events = payload.get("data") or []
    semester = None
    slots = defaultdict(dict)   # class_name -> (day, start, end) -> slot
    turma_ids = {}

    for ev in events:
        for uc in ev.get("ucs") or []:
            if uc.get("sigarra_id") == occ_id and not semester:
                m = SEMESTER_RE.search(uc.get("name") or "")
                if m:
                    semester = m.group(1)

        # Derive the weekday from THIS occurrence's date. The event-level
        # `week_days` list can name several days (a block spanning Mon+Tue),
        # so trusting it would both invent and drop meetings.
        date = (ev.get("start") or "")[:10]
        if len(date) != 10:
            continue
        try:
            day = datetime.date.fromisoformat(date).weekday()
        except ValueError:
            continue

        start, end = hhmm(ev.get("hour_start")), hhmm(ev.get("hour_end"))
        if not start or not end:
            continue
        key = (day, start, end)

        for cl in ev.get("classes") or []:
            name = (cl.get("acronym") or cl.get("name") or "").strip()
            if not name:
                continue
            if cl.get("sigarra_id"):
                turma_ids[name] = cl["sigarra_id"]
            slot = slots[name].get(key)
            if slot is None:
                slot = slots[name][key] = {
                    "day": day, "start": start, "end": end,
                    "type": (ev.get("typology") or {}).get("acronym"),
                    "rooms": set(), "teachers": set(), "dates": set(),
                }
            # The room's `name` ("FC1007"), not its `acronym` ("007"): the acronym
            # is only the door number, and it repeats across buildings — "007" is
            # both FC1007 and FC2007. The name is what gets you to the right room.
            slot["rooms"].update((r.get("name") or r.get("acronym") or "").strip()
                                 for r in (ev.get("rooms") or [])
                                 if (r.get("name") or r.get("acronym")))
            slot["teachers"].update(
                person_name(p) for p in (ev.get("persons") or []) if person_name(p))
            slot["dates"].add(date)

    merged = {}
    for name, bykey in slots.items():
        out = []
        for slot in bykey.values():
            dates = sorted(slot.pop("dates"))
            slot["rooms"] = sorted(slot["rooms"])
            slot["teachers"] = sorted(slot["teachers"])
            slot["occurrences"] = len(dates)
            slot["first_date"] = dates[0]
            slot["last_date"] = dates[-1]
            # The 1st semester runs Sep-Jan (January is exams / late classes),
            # the 2nd Feb-Jul.
            month = int(dates[0][5:7])
            slot["semester"] = "1S" if (month >= 8 or month == 1) else "2S"
            slot["regular"] = len(dates) >= REGULAR_MIN
            out.append(slot)
        merged[name] = sorted(out, key=lambda s: (s["day"], s["start"]))
    return merged, semester, ("ok" if events else "empty"), turma_ids


def build(code):
    """Build one faculty. Returns the index entry describing what came out."""
    subjects_path, raw = F.subjects(code), F.raw_dir(code)
    if not subjects_path.exists():
        raise SystemExit(f"{code}: falta {subjects_path.relative_to(F.ROOT)} — "
                         f"corre primeiro parse_ucs.py -f {code}")
    with open(subjects_path, encoding="utf-8") as fh:
        rows = json.load(fh)

    subjects, order = {}, []
    for row in rows:
        key = row["code"]
        if key not in subjects:
            subjects[key] = {
                "code": row["code"], "name": row["name"],
                "occurrence_id": row["occurrence_id"],
                "academic_year": row["academic_year"],
                "semester": None, "status": None, "classes": [],
            }
            order.append(key)
        for cl in row["classes"]:
            subjects[key]["classes"].append({
                "name": cl["name"], "type": row["type"],
                "vacant_places": cl["vacant_places"], "turma_id": None, "slots": [],
            })

    stats = defaultdict(int)
    unmatched = []
    for key in order:
        sub = subjects[key]
        by_name, semester, status, turma_ids = load_events(sub["occurrence_id"], raw)
        sub["semester"] = semester
        sub["status"] = status
        stats[status] += 1
        seen = set()
        for cl in sub["classes"]:
            cl["slots"] = by_name.get(cl["name"], [])
            cl["turma_id"] = turma_ids.get(cl["name"])
            if cl["slots"]:
                seen.add(cl["name"])
                stats["classes_with_slots"] += 1
                stats["slots"] += len(cl["slots"])
                stats["one_off_slots"] += sum(1 for s in cl["slots"] if not s["regular"])
            else:
                stats["classes_without_slots"] += 1
        for name in by_name:
            if name not in seen:
                unmatched.append(f"{sub['code']}:{name}")

    fac = F.get(code)
    out = {
        "faculty": {"code": fac["code"], "name": fac["name"], "short": fac["short"]},
        "generated": datetime.datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subjects": [subjects[k] for k in order],
    }
    dest = F.timetable(code)
    dest.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    dest.write_text(blob, encoding="utf-8")
    # Chrome refuses fetch() on file:// URLs, so the pages load data via <script>.
    # The faculty code is in the global name, so two faculties can be loaded at
    # once later on without one overwriting the other.
    F.timetable_js(code).write_text(
        f'window.TIMETABLE_DATA_{code.upper()} = ' + blob + ";\n"
        f'window.TIMETABLE_DATA = window.TIMETABLE_DATA_{code.upper()};\n',
        encoding="utf-8")

    kb = dest.stat().st_size / 1024
    print(f"{code}: {len(order)} UCs -> {dest.relative_to(F.ROOT)} ({kb:.0f} KB)")
    print(f"  raw: ok={stats['ok']} empty={stats['empty']} missing={stats['missing']}")
    print(f"  turmas com horário: {stats['classes_with_slots']}, sem: {stats['classes_without_slots']}")
    print(f"  horários semanais: {stats['slots']} (pontuais: {stats['one_off_slots']})")
    if unmatched:
        print(f"  AVISO {len(unmatched)} turmas do calendário fora de subjects.json: {unmatched[:6]}")

    return {
        "code": fac["code"], "name": fac["name"], "short": fac["short"],
        "file": f"data/{code}/timetable.js",
        "subjects": len(order),
        "with_slots": stats["classes_with_slots"],
        "generated": out["generated"],
        "size_kb": round(kb),
    }


def write_index(entries):
    """The small file the site loads first, to know which faculties exist.

    Written twice: .json for the scripts, .js for the site. The site cannot
    fetch() JSON from a file:// URL, and the whole point of this index is that
    it loads before anything else — so it has to be a plain <script>."""
    entries.sort(key=lambda e: e["name"])
    blob = {"generated": datetime.datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "faculdades": entries}
    F.INDEX.write_text(json.dumps(blob, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    F.INDEX.with_suffix(".js").write_text(
        "window.FACULDADES_INDEX = "
        + json.dumps(blob, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")
    total = sum(e["subjects"] for e in entries)
    print(f"\nindice -> {F.INDEX.relative_to(F.ROOT)} (+ .js): "
          f"{len(entries)} faculdade(s), {total} UCs")


def main():
    argv = sys.argv[1:]
    if "--all" in argv:
        # Every faculty that actually has data on disk, not every faculty known.
        codes = [c for c in F.BY_CODE if F.subjects(c).exists()]
        if not codes:
            raise SystemExit("nenhuma faculdade tem dados em data/")
    else:
        codes = [F.arg(argv)]

    # Keep entries for faculties built earlier but not rebuilt now, so building
    # one faculty does not drop the others out of the index.
    entries = []
    if F.INDEX.exists():
        try:
            entries = [e for e in json.loads(F.INDEX.read_text(encoding="utf-8"))["faculdades"]
                       if e["code"] not in codes]
        except (ValueError, KeyError):
            entries = []
    for code in codes:
        entries.append(build(code))
    write_index(entries)


if __name__ == "__main__":
    main()
