#!/usr/bin/env python3
"""Split the browser-fetched raw_all.json into data/raw/<occurrence_id>.json.

  python3 scripts/import_raw_all.py ~/Downloads/raw_all.json

browser_fetch.js downloads everything as one file; build_data.py expects one
file per occurrence (same layout fetch_timetables.sh produces), so the two
routes stay interchangeable.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Downloads/raw_all.json")
    with open(src, encoding="utf-8") as fh:
        blob = json.load(fh)

    fetched = blob.get("fetched", blob)
    failed = blob.get("failed", [])

    OUT.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    for occ_id, payload in fetched.items():
        if not isinstance(payload, dict) or "data" not in payload:
            skipped += 1
            continue
        with open(OUT / f"{occ_id}.json", "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
        written += 1

    print(f"wrote {written} files to {OUT}/" + (f", skipped {skipped} malformed" if skipped else ""))
    if failed:
        print(f"{len(failed)} occurrences failed in the browser: {failed[:10]}")
    print("next: python3 scripts/build_data.py")


if __name__ == "__main__":
    main()
