/* Shared helpers for index.html and subject.html:
   subject colours (persisted, shared between both pages) and the details popup. */
window.FCUP = (function () {
  "use strict";

  const DAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];
  const YEAR = 2026, PERIODS = [1, 2, 4, 5, 8];

  // Chosen to stay legible with white text on a light page.
  const PALETTE = [
    "#2563eb", "#7c3aed", "#059669", "#d97706", "#dc2626", "#0891b2",
    "#db2777", "#4f46e5", "#65a30d", "#c026d3", "#0d9488", "#ea580c",
  ];

  // Namespaced per faculty: two faculties can use the same subject code, and a
  // colour chosen for CC1007 at the FCUP says nothing about another CC1007.
  const KEY = (window.FTH && window.FTH.key) ? window.FTH.key("colors-v1")
                                             : "fth-fcup-colors-v1";
  let colors = {};
  try { colors = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { colors = {}; }
  const persist = () => { try { localStorage.setItem(KEY, JSON.stringify(colors)); } catch (e) {} };

  // Unassigned subjects get a stable colour derived from the code, so the same
  // subject looks the same on both pages without anyone having to pick one.
  function autoColour(code) {
    let h = 0;
    for (let i = 0; i < code.length; i++) h = (h * 31 + code.charCodeAt(i)) >>> 0;
    return PALETTE[h % PALETTE.length];
  }
  const colourOf = code => colors[code] || autoColour(code);
  const isCustom = code => Boolean(colors[code]);
  function setColour(code, hex) {
    if (hex) colors[code] = hex; else delete colors[code];
    persist();
  }

  const esc = s => String(s == null ? "" : s)
    .replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const min = t => (+t.slice(0, 2)) * 60 + (+t.slice(3, 5));
  const fmtDur = m => (m % 60 ? (m / 60).toFixed(1).replace(".", ",") : m / 60) + " h";
  // The faculty acronym is a path segment in every SIGARRA URL, so the links
  // have to follow whichever faculty's data is loaded. The dataset carries it;
  // "fcup" is only the fallback for data built before that field existed.
  const faculty = () =>
    (window.TIMETABLE_DATA && window.TIMETABLE_DATA.faculty
     && window.TIMETABLE_DATA.faculty.code) || "fcup";
  const ucURL = occ =>
    "https://sigarra.up.pt/" + faculty() + "/pt/ucurr_geral.ficha_uc_view?pv_ocorrencia_id=" + occ;
  const turmaURL = id =>
    "https://sigarra.up.pt/" + faculty() + "/pt/hor_geral.turmas_view?pv_turma_id=" + id +
    "&pv_ano_lectivo=" + YEAR + PERIODS.map(p => "&pv_periodos=" + p).join("");

  /* ---- side-by-side layout for overlapping classes ---------------------- */
  /* Items are {slot: {start, end}, ...}. Groups items into clusters of mutually
     overlapping classes and assigns each a lane, so two classes at the same
     hour render next to each other instead of hiding one another. Sets _lane
     (0-based) and _lanes (width of that item's cluster) on each item. */
  function packDay(items) {
    const sorted = items.slice().sort((a, b) =>
      min(a.slot.start) - min(b.slot.start) || min(a.slot.end) - min(b.slot.end));
    const out = [];
    let cluster = [], clusterEnd = -1;

    const flush = () => {
      if (!cluster.length) return;
      const lanes = [];                      // lanes[k] = end time of last item
      for (const it of cluster) {
        let k = lanes.findIndex(end => end <= min(it.slot.start));
        if (k === -1) { k = lanes.length; lanes.push(0); }
        lanes[k] = min(it.slot.end);
        it._lane = k;
      }
      for (const it of cluster) { it._lanes = lanes.length; out.push(it); }
      cluster = []; clusterEnd = -1;
    };

    for (const it of sorted) {
      if (cluster.length && min(it.slot.start) >= clusterEnd) flush();
      cluster.push(it);
      clusterEnd = Math.max(clusterEnd, min(it.slot.end));
    }
    flush();
    return out;
  }

  /* ---- colour picker ---------------------------------------------------- */
  // onChange is called after the palette is updated so the page can re-render.
  function swatches(code, onChange) {
    const wrap = document.createElement("div");
    wrap.className = "swatches noprint";
    const current = colourOf(code);
    for (const hex of PALETTE) {
      const b = document.createElement("button");
      b.className = "sw";
      b.style.background = hex;
      b.title = hex;
      b.setAttribute("aria-pressed", String(hex.toLowerCase() === current.toLowerCase()));
      b.onclick = ev => { ev.preventDefault(); ev.stopPropagation(); setColour(code, hex); onChange(); };
      wrap.appendChild(b);
    }
    const custom = document.createElement("input");
    custom.type = "color";
    custom.value = current;
    custom.title = "Cor personalizada";
    custom.style.cssText = "width:22px;height:22px;padding:0;border:1px solid var(--line);"
                         + "border-radius:5px;background:none;cursor:pointer";
    custom.oninput = () => { setColour(code, custom.value); onChange(); };
    wrap.appendChild(custom);

    if (isCustom(code)) {
      const rst = document.createElement("button");
      rst.className = "chip";
      rst.style.cssText = "padding:1px 8px;font-size:11px";
      rst.textContent = "repor";
      rst.onclick = ev => { ev.preventDefault(); setColour(code, null); onChange(); };
      wrap.appendChild(rst);
    }
    return wrap;
  }

  /* ---- details popup ---------------------------------------------------- */
  function dialogEl() {
    let d = document.getElementById("details");
    if (d) return d;
    d = document.createElement("dialog");
    d.id = "details";
    d.innerHTML = '<div id="dhead"></div><div id="dbody"></div><div id="dfoot"></div>';
    document.body.appendChild(d);
    // Clicking the backdrop (i.e. outside the panel) closes it.
    d.addEventListener("click", ev => { if (ev.target === d) d.close(); });
    return d;
  }

  /* info: {subject, cls, slot, onColour} */
  function showDetails(info) {
    const {subject, cls, slot} = info;
    const d = dialogEl();
    const colour = colourOf(subject.code);
    d.style.setProperty("--c", colour);

    const short = cls.name.replace(subject.code + "_", "");
    d.querySelector("#dhead").innerHTML =
      `<b>${esc(subject.code)} · ${esc(short)}</b>`
      + `<span>${esc(subject.name)}</span>`;

    const rows = [];
    if (slot) {
      // Everything below is escaped: it ultimately comes from the SIGARRA API.
      rows.push(["Quando", `${esc(DAYS[slot.day])}, ${esc(slot.start)} – ${esc(slot.end)}`
                 + ` <span class="tag">${esc(fmtDur(min(slot.end) - min(slot.start)))}</span>`]);
      rows.push(["Sala", slot.rooms.length ? esc(slot.rooms.join(", ")) : "—"]);
      rows.push(["Docentes", slot.teachers.length ? esc(slot.teachers.join(", ")) : "—"]);
      rows.push(["Período", `${esc(slot.first_date)} → ${esc(slot.last_date)}`
                 + (slot.occurrences
                     ? ` <span class="tag">${esc(slot.occurrences)}× no semestre</span>` : "")]);
      if (slot.regular === false) {
        rows.push(["Atenção", '<span style="color:var(--bad)">aula pontual — não é semanal</span>']);
      }
    } else {
      rows.push(["Quando", '<span class="empty">sem horário publicado</span>']);
    }
    rows.push(["Tipo", `<span class="ty" style="background:${esc(colour)}">${esc(cls.type)}</span>`]);
    rows.push(["Vagas", cls.vacant_places === 0
      ? '<span style="color:var(--bad)">sem vagas</span>' : esc(cls.vacant_places)]);
    rows.push(["Ano", `${esc(subject.academic_year)}.º`
      + (subject.semester ? ` · ${esc(subject.semester)}` : "")]);

    d.querySelector("#dbody").innerHTML =
      "<dl>" + rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("") + "</dl>";

    const foot = d.querySelector("#dfoot");
    foot.innerHTML =
      `<a class="btn" href="subject.html#${encodeURIComponent(subject.code)}">Horário da UC</a>`
      + `<a class="btn" href="${ucURL(subject.occurrence_id)}" target="_blank" rel="noopener">Ficha ↗</a>`
      + (cls.turma_id
          ? `<a class="btn" href="${turmaURL(cls.turma_id)}" target="_blank" rel="noopener">Turma ↗</a>`
          : "")
      + `<span class="grow"></span>`;
    const close = document.createElement("button");
    close.className = "primary";
    close.textContent = "Fechar";
    close.onclick = () => d.close();
    foot.appendChild(close);

    // "Skip this session" - for a class that is on your official timetable but
    // that you have decided not to attend (e.g. it clashes with an elective).
    if (info.skip) {
      const on = info.skip.isSkipped();
      const b = document.createElement("button");
      b.style.cssText = "flex-basis:100%;text-align:left";
      b.textContent = on ? "↩ Voltar a assistir a esta aula"
                         : "✕ Marcar esta aula como falta";
      b.onclick = () => { info.skip.toggle(); showDetails(info); };
      foot.appendChild(b);
      if (on) {
        const p = document.createElement("p");
        p.style.cssText = "flex-basis:100%;margin:0;font-size:12px;color:var(--muted)";
        p.textContent = "Não conta para sobreposições nem para as horas semanais.";
        foot.appendChild(p);
      }
    }

    if (info.onColour) {
      const pick = document.createElement("div");
      pick.style.cssText = "flex-basis:100%;display:flex;gap:8px;align-items:center;"
                         + "border-top:1px solid var(--line);padding-top:10px;margin-top:2px";
      pick.innerHTML = '<span style="font-size:12px;color:var(--muted)">Cor da UC</span>';
      pick.appendChild(swatches(subject.code, () => {
        info.onColour();
        showDetails(info);          // repaint the popup in the new colour
      }));
      foot.appendChild(pick);
    }

    if (!d.open) d.showModal();
  }

  return {DAYS, PALETTE, faculty, colourOf, setColour, isCustom, swatches, showDetails,
          packDay, esc, min, ucURL, turmaURL};
})();
