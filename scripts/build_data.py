#!/usr/bin/env python3
"""Merge subjects.json + data/raw/*.json into one dataset for the timetable UI.

  python3 scripts/build_data.py            # -> data/timetable.json and .js

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
from collections import defaultdict
from pathlib import Path
from datetime import timezone

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SUBJECTS = ROOT / "data" / "subjects.json"
OUT = ROOT / "data" / "timetable.json"
SEMESTER_RE = re.compile(r"\((\dS|A)\)\s*$")
# Fewer than this many meetings is an extra session, not a weekly commitment.
REGULAR_MIN = 3


def hhmm(t):
    return (t or "")[:5]


def load_events(occ_id):
    """Return ({class_name: [slot, ...]}, semester, status, {class_name: turma_id})."""
    path = RAW / f"{occ_id}.json"
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
            slot["rooms"].update(r["acronym"] for r in (ev.get("rooms") or []) if r.get("acronym"))
            slot["teachers"].update(p["acronym"] for p in (ev.get("persons") or []) if p.get("acronym"))
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


def main():
    with open(SUBJECTS, encoding="utf-8") as fh:
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
        by_name, semester, status, turma_ids = load_events(sub["occurrence_id"])
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

    out = {
        "generated": datetime.datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subjects": [subjects[k] for k in order],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(blob)
    # Chrome refuses fetch() on file:// URLs, so the pages load data via <script>.
    with open(OUT.with_suffix(".js"), "w", encoding="utf-8") as fh:
        fh.write("window.TIMETABLE_DATA = " + blob + ";\n")

    print(f"{len(order)} subjects -> {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
    print(f"  raw files: ok={stats['ok']} empty={stats['empty']} missing={stats['missing']}")
    print(f"  classes with slots: {stats['classes_with_slots']}, without: {stats['classes_without_slots']}")
    print(f"  weekly slots: {stats['slots']} (of which one-off: {stats['one_off_slots']})")
    if unmatched:
        print(f"  WARNING {len(unmatched)} calendar classes not in subjects.json: {unmatched[:8]}")


if __name__ == "__main__":
    main()
