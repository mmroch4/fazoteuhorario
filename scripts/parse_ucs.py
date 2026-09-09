#!/usr/bin/env python3
"""Extract subjects + their classes from a SIGARRA "turmas" table into JSON.

Usage:  python3 scripts/parse_ucs.py input.html [output.json]
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TableParser(HTMLParser):
    """Collect each <tr> as a list of (css_class, text, href) cell tuples."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._cell = None
        self._cls = None
        self._href = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._cls = attrs.get("class", "")
            self._href = None
        elif tag == "a" and self._cell is not None:
            self._href = attrs.get("href", "")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            text = "".join(self._cell).replace("\xa0", " ").strip()
            self._row.append((self._cls, text, self._href))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_entityref(self, name):
        self.handle_data({"nbsp": " ", "amp": "&", "lt": "<", "gt": ">"}.get(name, ""))


OCC_RE = re.compile(r"pv_ocorrencia_id=(\d+)")


def pairs_from(cells):
    """Turn trailing (name, vagas) cells into class dicts, dropping ' - ' fillers."""
    out = []
    for (cls_a, name, _), (_cls_b, vagas, _) in zip(cells[::2], cells[1::2]):
        if "l" in cls_a.split() or name in ("", "-"):
            continue
        out.append({"name": name, "vacant_places": int(vagas)})
    return out


def parse(html):
    p = TableParser()
    p.feed(html)

    subjects = []
    for row in p.rows:
        if not row:
            continue
        # Header rows have no <td>; key rows start with the 4 rowspan'd "k" cells.
        key = [c for c in row if "k" in c[0].split()]
        if len(key) == 4:
            year, name, code, type_ = (c[1] for c in key)
            occ = OCC_RE.search(key[1][2] or "")
            subjects.append({
                "code": code,
                "name": name,
                "occurrence_id": int(occ.group(1)) if occ else None,
                "academic_year": int(year),
                "type": type_,
                "classes": pairs_from(row[4:]),
            })
        elif subjects and row:
            # Continuation row: more classes for the previous subject/type.
            subjects[-1]["classes"].extend(pairs_from(row))
    return subjects


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else ROOT / "data" / "subjects.json"
    with open(src, encoding="utf-8") as fh:
        subjects = parse(fh.read())
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(subjects, fh, ensure_ascii=False, indent=2)
    print(f"{len(subjects)} subject/type rows -> {dst}")
    print(f"{sum(len(s['classes']) for s in subjects)} classes total")


if __name__ == "__main__":
    main()
