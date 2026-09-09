#!/usr/bin/env python3
"""The faculties of the U.Porto, and where each one's files live.

Every script that touches data goes through here, so adding a faculty is one
entry in FACULDADES plus running the pipeline for it — never a change spread
across five scripts.

A faculty's code is its SIGARRA acronym, which is also the path segment used by
both the calendar API and the public pages:

    https://sigarra.up.pt/calendarios-api/api/v1/events/<code>/uc/<id>/
    https://sigarra.up.pt/<code>/pt/ucurr_geral.ficha_uc_view?pv_ocorrencia_id=<id>

`ready` says whether we have published data for it. The site lists only the
ready ones; the rest are here so that adding them is a data problem, not a code
problem.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

FACULDADES = [
    # code      name                                                  short
    ("fcup",   "Faculdade de Ciências",                              "FCUP",   True),
    ("feup",   "Faculdade de Engenharia",                            "FEUP",   False),
    ("fep",    "Faculdade de Economia",                              "FEP",    False),
    ("flup",   "Faculdade de Letras",                                "FLUP",   False),
    ("fmup",   "Faculdade de Medicina",                              "FMUP",   False),
    ("fdup",   "Faculdade de Direito",                               "FDUP",   False),
    ("fpceup", "Faculdade de Psicologia e de Ciências da Educação",  "FPCEUP", False),
    ("ffup",   "Faculdade de Farmácia",                              "FFUP",   False),
    ("fmdup",  "Faculdade de Medicina Dentária",                     "FMDUP",  False),
    ("fcnaup", "Faculdade de Ciências da Nutrição e Alimentação",    "FCNAUP", False),
    ("fadeup", "Faculdade de Desporto",                              "FADEUP", False),
    ("fbaup",  "Faculdade de Belas Artes",                           "FBAUP",  False),
    ("icbas",  "Instituto de Ciências Biomédicas Abel Salazar",      "ICBAS",  False),
]

BY_CODE = {c: {"code": c, "name": n, "short": s, "ready": r}
           for c, n, s, r in FACULDADES}
READY = [c for c, _, _, r in FACULDADES if r]


def get(code):
    """Look up a faculty, failing with a usable message rather than a KeyError."""
    code = (code or "").lower().strip()
    if code not in BY_CODE:
        raise SystemExit(
            f"faculdade desconhecida: {code!r}\n"
            f"conhecidas: {', '.join(BY_CODE)}\n"
            f"para acrescentar uma, edita FACULDADES em scripts/faculdades.py")
    return BY_CODE[code]


# --- where each faculty's files live -----------------------------------------
def dir_of(code):        return DATA / get(code)["code"]
def raw_dir(code):       return dir_of(code) / "raw"
def subjects(code):      return dir_of(code) / "subjects.json"
def timetable(code):     return dir_of(code) / "timetable.json"
def timetable_js(code):  return dir_of(code) / "timetable.js"
def ucs_html(code):      return dir_of(code) / "ucs.html"
def failed(code):        return dir_of(code) / "failed.txt"

INDEX = DATA / "faculdades.json"


def api_base(code):
    return f"https://sigarra.up.pt/calendarios-api/api/v1/events/{get(code)['code']}/uc"


def arg(argv, default="fcup"):
    """Pull `--faculty xx` (or `-f xx`) out of a script's argv, in place.

    Returns the code and removes the flag from argv, so the caller can go on
    parsing its own positional arguments as if it were not there."""
    for flag in ("--faculty", "--faculdade", "-f"):
        if flag in argv:
            i = argv.index(flag)
            if i + 1 >= len(argv):
                raise SystemExit(f"{flag} precisa de um código de faculdade")
            code = argv[i + 1]
            del argv[i:i + 2]
            return get(code)["code"]
    return default
