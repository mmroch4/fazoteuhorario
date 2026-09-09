#!/usr/bin/env python3
"""Print a faculty's occurrence ids, ready to paste into browser_fetch.js.

  python3 scripts/ids.py                # FCUP
  python3 scripts/ids.py -f feup        # outra faculdade
  python3 scripts/ids.py -f feup --js   # a linha `const IDS = [...]` inteira

Reads data/<faculdade>/subjects.json, so run parse_ucs.py first. Keeping this
out of browser_fetch.js means the id list is never hand-maintained: it is
always derived from the catalogue that was actually parsed.
"""
import json
import sys

import faculdades as F


def main():
    argv = sys.argv[1:]
    code = F.arg(argv)
    path = F.subjects(code)
    if not path.exists():
        sys.exit(f"falta {path.relative_to(F.ROOT)} — corre primeiro "
                 f"python3 scripts/parse_ucs.py -f {code}")

    rows = json.loads(path.read_text(encoding="utf-8"))
    ids = sorted({r["occurrence_id"] for r in rows if r.get("occurrence_id")})
    if not ids:
        sys.exit(f"{code}: nenhum occurrence_id em {path.name}")

    if "--js" in argv:
        print(f'  const FACULTY = "{code}";')
        print(f"  const IDS = [{', '.join(map(str, ids))}];")
    else:
        print(json.dumps(ids))
    print(f"\n{len(ids)} ocorrências ({F.get(code)['short']})", file=sys.stderr)


if __name__ == "__main__":
    main()
