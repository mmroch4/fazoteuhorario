#!/usr/bin/env python3
"""Write the SEO head block into every page, plus robots.txt and sitemap.xml.

  python3 scripts/build_seo.py
  python3 scripts/build_seo.py --site https://horario.miguelrocha.dev

Everything that has to agree across pages — titles, descriptions, canonical
URLs, Open Graph tags, the site URL — is defined HERE and injected, so the four
pages cannot drift apart. Re-run it after changing a description or moving the
site to another domain; it replaces its own block instead of stacking a second
one, so running it twice is safe.

The site URL is stored in SITE below and rewritten by --site, which is the one
place to change when the domain is decided.
"""
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The public address of the site. Change with --site (which rewrites this file).
SITE = "https://horario.miguelrocha.dev"

REPO = "https://github.com/mmroch4/fazoteuhorario"
AUTHOR = "Miguel Rocha"
AUTHOR_URL = "https://miguelrocha.dev"
# The brand. Every page title must also carry "U.Porto", and carry it early:
# search results truncate around 60 characters, and the tail is what is lost.
NAME = "Faz o Teu Horário · U.Porto"

# Markers so the block can be found and replaced on a re-run.
BEGIN = "<!-- seo:begin  gerado por scripts/build_seo.py — não editar à mão -->"
END = "<!-- seo:end -->"

PAGES = {
    "index.html": {
        "path": "/",
        "title": "Faz o Teu Horário — turmas e horários da U.Porto",
        "desc": "Monta o teu horário da U.Porto antes da inscrição: escolhe as UCs, "
                "compara turmas, vê as sobreposições e gera todas as combinações. "
                "Grátis e sem conta.",
        "og_title": "Faz o teu horário antes da inscrição",
    },
    "subject.html": {
        "path": "/subject.html",
        "title": "Unidades curriculares da U.Porto — turmas e horários",
        "desc": "Todas as unidades curriculares com horário publicado: turmas, "
                "salas, docentes e vagas, numa grelha semanal. Dados do SIGARRA "
                "da U.Porto.",
        "og_title": "Unidades curriculares e turmas",
    },
    "guia.html": {
        "path": "/guia.html",
        "title": "Guia — como montar o teu horário na U.Porto",
        "desc": "Como usar o construtor de horários: escolher turmas, marcar faltas, "
                "cumprir as horas semanais, gerar combinações e guardar vários "
                "horários para comparar.",
        "og_title": "Guia de utilização",
    },
    "sobre.html": {
        "path": "/sobre.html",
        "title": "Sobre o projeto — Faz o Teu Horário, U.Porto",
        "desc": "Porque é que este construtor existe: decidir o horário antes da "
                "inscrição no SIGARRA e continuar a ajustá-lo durante o semestre. "
                "Projeto de código aberto.",
        "og_title": "Porque é que este projeto existe",
    },
}


def esc(s):
    return (s.replace("&", "&amp;").replace('"', "&quot;")
             .replace("<", "&lt;").replace(">", "&gt;"))


def ld_json(page, site):
    """Structured data. One graph per page, only what the page really is."""
    author = {"@type": "Person", "name": AUTHOR, "url": AUTHOR_URL}
    if page == "index.html":
        data = {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": NAME,
            "url": site + "/",
            "description": PAGES[page]["desc"],
            "applicationCategory": "EducationalApplication",
            "operatingSystem": "Any (navegador web)",
            "inLanguage": "pt-PT",
            "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
            "author": author,
            "license": "https://opensource.org/licenses/MIT",
            "codeRepository": REPO,
        }
    elif page == "guia.html":
        # The FAQ block at the bottom of the guide, so it can win a rich result.
        data = {"@context": "https://schema.org", "@type": "FAQPage",
                "inLanguage": "pt-PT", "mainEntity": faq_from_guide()}
    elif page == "sobre.html":
        data = {
            "@context": "https://schema.org", "@type": "AboutPage",
            "name": PAGES[page]["title"], "url": site + PAGES[page]["path"],
            "description": PAGES[page]["desc"], "inLanguage": "pt-PT",
            "author": author,
            "mainEntity": {"@type": "SoftwareApplication", "name": NAME,
                           "url": site + "/", "applicationCategory": "EducationalApplication",
                           "operatingSystem": "Any (navegador web)", "author": author},
        }
    else:
        data = {"@context": "https://schema.org", "@type": "CollectionPage",
                "name": PAGES[page]["title"], "url": site + PAGES[page]["path"],
                "description": PAGES[page]["desc"], "inLanguage": "pt-PT"}
    return json.dumps(data, ensure_ascii=False, indent=2)


def faq_from_guide():
    """Read the <dl class="faq"> out of guia.html so the two cannot disagree."""
    html = (ROOT / "guia.html").read_text(encoding="utf-8")
    block = re.search(r'<dl class="faq">(.*?)</dl>', html, re.S)
    if not block:
        return []
    pairs = re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", block.group(1), re.S)
    strip = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()
    return [{"@type": "Question", "name": strip(q),
             "acceptedAnswer": {"@type": "Answer", "text": strip(a)}}
            for q, a in pairs]


def head_block(page, site):
    p = PAGES[page]
    url = site + p["path"]
    img = site + "/assets/og.png"
    t, d, ogt = esc(p["title"]), esc(p["desc"]), esc(p["og_title"])
    return f"""{BEGIN}
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#2563eb">
<link rel="icon" href="favicon.ico" sizes="32x32">
<link rel="icon" href="assets/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
<link rel="manifest" href="site.webmanifest">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(NAME)}">
<meta property="og:locale" content="pt_PT">
<meta property="og:title" content="{ogt}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Grelha semanal de horário com as aulas de cinco unidades curriculares">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{ogt}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{img}">
<script type="application/ld+json">
{ld_json(page, site)}
</script>
{END}"""


def patch_page(page, site):
    f = ROOT / page
    html = f.read_text(encoding="utf-8")

    # Replace an earlier run's block; otherwise drop the hand-written title and
    # description and insert after the viewport meta.
    if BEGIN in html:
        html = re.sub(re.escape(BEGIN) + ".*?" + re.escape(END), head_block(page, site),
                      html, flags=re.S)
    else:
        html = re.sub(r"[ \t]*<title>.*?</title>\n", "", html, flags=re.S)
        html = re.sub(r'[ \t]*<meta name="description".*?>\n', "", html, flags=re.S)
        anchor = '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        if anchor not in html:
            raise SystemExit(f"{page}: não encontrei a meta viewport para ancorar o bloco")
        html = html.replace(anchor, anchor + head_block(page, site) + "\n", 1)

    html = html.replace('<html lang="pt">', '<html lang="pt-PT">', 1)
    f.write_text(html, encoding="utf-8")
    print(f"  {page}")


def write_robots(site):
    (ROOT / "robots.txt").write_text(
        "# Faz o Teu Horário — U.Porto\n"
        "User-agent: *\n"
        "Allow: /\n\n"
        "# Nada aqui é privado; o sitemap lista também a página de cada UC.\n"
        f"Sitemap: {site}/sitemap.xml\n", encoding="utf-8")
    print("  robots.txt")


def write_manifest(site):
    (ROOT / "site.webmanifest").write_text(json.dumps({
        "name": NAME + " — construtor de horários",
        "short_name": "Horário",
        "description": PAGES["index.html"]["desc"],
        "start_url": "./index.html",
        "scope": "./",
        "display": "standalone",
        "lang": "pt-PT",
        "background_color": "#f7f8fa",
        "theme_color": "#2563eb",
        "icons": [
            {"src": "assets/icon.svg", "sizes": "any", "type": "image/svg+xml"},
            {"src": "assets/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
        ],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("  site.webmanifest")


def write_sitemap(site):
    """One URL per page, plus one per UC that has a published timetable.

    subject.html reads ?code=CC1007 as well as #CC1007, and only the query form
    is a distinct URL to a crawler - so that is the form the sitemap uses."""
    data = json.loads((ROOT / "data" / "timetable.json").read_text(encoding="utf-8"))
    today = datetime.date.today().isoformat()
    lastmod = (data.get("generated") or today)[:10]

    urls = [(site + p["path"], "1.0" if p["path"] == "/" else "0.8", lastmod)
            for p in PAGES.values()]
    n_ucs = 0
    for sub in data["subjects"]:
        if not any(c["slots"] for c in sub["classes"]):
            continue                       # nothing to show, nothing to index
        urls.append((f"{site}/subject.html?code={sub['code']}", "0.5", lastmod))
        n_ucs += 1

    body = "".join(
        f"  <url>\n    <loc>{esc(u)}</loc>\n    <lastmod>{m}</lastmod>\n"
        f"    <priority>{p}</priority>\n  </url>\n" for u, p, m in urls)
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + body + "</urlset>\n", encoding="utf-8")
    print(f"  sitemap.xml ({len(urls)} URLs: {len(PAGES)} páginas + {n_ucs} UCs)")


def set_site(new):
    """Rewrite SITE in this file, so the value lives in exactly one place."""
    f = Path(__file__)
    t = f.read_text(encoding="utf-8")
    f.write_text(re.sub(r'^SITE = ".*"$', f'SITE = "{new}"', t, count=1, flags=re.M),
                 encoding="utf-8")


def main():
    site = SITE
    if "--site" in sys.argv:
        site = sys.argv[sys.argv.index("--site") + 1].rstrip("/")
        set_site(site)
    print(f"site: {site}")
    for page in PAGES:
        patch_page(page, site)
    write_robots(site)
    write_manifest(site)
    write_sitemap(site)


if __name__ == "__main__":
    main()
