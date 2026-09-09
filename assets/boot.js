/* Which faculty are we showing, and loading its data before the page runs.
 *
 * The site used to be one faculty with its 500 KB of timetables in a <script>
 * tag in the HTML. With every U.Porto faculty that becomes several megabytes on
 * every visit, so the data file is now chosen at runtime and loaded on demand;
 * only the ~1 KB index (data/faculdades.js) is loaded up front.
 *
 * Loading is still via <script> rather than fetch() because the pages must keep
 * working when opened straight off the disk, and Chrome refuses fetch() on
 * file:// URLs.
 */
window.FTH = (function () {
  "use strict";

  const INDEX = (window.FACULDADES_INDEX || {faculdades: []}).faculdades;
  const DEFAULT = "fcup";
  const PICK_KEY = "fth-faculdade";

  const byCode = Object.fromEntries(INDEX.map(f => [f.code, f]));
  const known = code => Object.prototype.hasOwnProperty.call(byCode, code);

  /* ---------- which faculty ---------------------------------------------
     The URL wins, so a shared link always opens the faculty it was made for,
     whatever the person receiving it had chosen before. */
  function resolve() {
    const fromUrl = (new URLSearchParams(location.search).get("f") || "").toLowerCase();
    if (known(fromUrl)) return fromUrl;
    let saved = null;
    try { saved = localStorage.getItem(PICK_KEY); } catch (e) {}
    if (known(saved)) return saved;
    return known(DEFAULT) ? DEFAULT : (INDEX[0] || {}).code;
  }

  const code = resolve();
  const current = byCode[code] || {code: code, name: code, short: (code || "").toUpperCase()};

  /* ---------- storage ----------------------------------------------------
     Keys are namespaced per faculty: two faculties may well use the same
     subject code, and a schedule made of FCUP turmas means nothing under FEUP.
     The un-namespaced keys from before this existed are migrated once. */
  const key = name => "fth-" + current.code + "-" + name;

  const LEGACY = {"horario-v1": "fcup-horario-v1",
                  "presets-v1": "fcup-presets-v1",
                  "colors-v1":  "fcup-colors-v1"};
  function migrate() {
    if (current.code !== "fcup") return;      // the old keys were only ever FCUP
    for (const [name, old] of Object.entries(LEGACY)) {
      try {
        const v = localStorage.getItem(old);
        if (v !== null && localStorage.getItem(key(name)) === null) {
          localStorage.setItem(key(name), v);
        }
      } catch (e) { /* private mode, quota, blocked storage: nothing to migrate */ }
    }
  }
  migrate();

  function switchTo(next) {
    if (!known(next) || next === current.code) return;
    try { localStorage.setItem(PICK_KEY, next); } catch (e) {}
    const u = new URL(location.href);
    u.searchParams.set("f", next);
    u.hash = "";                 // a schedule or UC from another faculty is meaningless here
    location.href = u.toString();
  }

  /* A link to this page for another faculty; the default one keeps a clean URL
     so the canonical of the home page stays "/". */
  function urlFor(next, path) {
    const p = path || location.pathname.split("/").pop() || "index.html";
    return next === DEFAULT ? p : p + "?f=" + encodeURIComponent(next);
  }

  /* ---------- loading ----------------------------------------------------- */
  /* Per-faculty page identity. The default faculty keeps the clean URL, so the
     home page canonical stays "/" and nothing about today's SEO changes. */
  function applySeo() {
    if (current.code === DEFAULT) return;
    document.title = document.title.replace(/U\.Porto/, current.short) ;
    const can = document.querySelector('link[rel="canonical"]');
    if (can) can.href = can.href.split("?")[0] + "?f=" + current.code;
    const og = document.querySelector('meta[property="og:url"]');
    if (og) og.content = og.content.split("?")[0] + "?f=" + current.code;
  }

  function fail(msg) {
    const box = document.createElement("div");
    box.className = "notice";
    box.style.cssText = "margin:16px";
    box.innerHTML = "<b>Não foi possível carregar os horários</b>" + msg;
    (document.querySelector("main") || document.body).prepend(box);
  }

  function boot(run) {
    if (!current.file) {                       // no data at all: say so, don't hang
      ready(() => {
        fail(" Ainda não há horários publicados para esta faculdade.");
        run(new Error("sem dados"));
      });
      return;
    }
    const s = document.createElement("script");
    s.src = current.file;
    s.onload = () => {
      // build_data.py writes both the namespaced global and the plain one; take
      // the namespaced one so a second faculty loaded later cannot shadow it.
      window.TIMETABLE_DATA = window["TIMETABLE_DATA_" + current.code.toUpperCase()]
                           || window.TIMETABLE_DATA;
      ready(() => { applySeo(); mountPicker(document.getElementById("facslot")); run(null); });
    };
    s.onerror = () => ready(() => {
      fail(" O ficheiro de dados da " + current.short + " não carregou. "
           + "Verifica a ligação e recarrega a página.");
      run(new Error("falhou " + current.file));
    });
    document.head.appendChild(s);
  }
  const ready = fn => document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", fn) : fn();

  /* ---------- faculty picker ---------------------------------------------
     Hidden while there is only one faculty: a menu with a single option is
     noise. It appears by itself the day a second one has data. */
  function picker() {
    if (INDEX.length < 2) return null;
    const sel = document.createElement("select");
    sel.className = "facsel noprint";
    sel.setAttribute("aria-label", "Faculdade");
    for (const f of INDEX) {
      const o = document.createElement("option");
      o.value = f.code;
      o.textContent = f.short;
      o.title = f.name;
      sel.appendChild(o);
    }
    sel.value = current.code;
    sel.onchange = () => switchTo(sel.value);
    return sel;
  }

  function mountPicker(into) {
    const el = picker();
    if (el && into) into.appendChild(el);
    return el;
  }

  /* When the data was pulled from SIGARRA. With faculties maintained at
     different rhythms this stops being a detail. */
  function freshness() {
    const d = (current.generated || "").slice(0, 10);
    return d ? {date: d, label: "dados de " + d.split("-").reverse().join("/")} : null;
  }

  return {index: INDEX, current, code: current.code, key, boot,
          switchTo, urlFor, picker, mountPicker, freshness, DEFAULT};
})();
