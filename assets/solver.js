/* Combination engine: builds every overlap-free weekly timetable that meets the
   required hours per subject/type, allowing you to switch turma freely.

   This is the browser port of solve_hours.py / enumerate_all.py. The model it
   encodes is the whole point, so it is worth stating plainly:

   A turma is not a commitment - it is a TIME at which a session is taught. What
   you actually owe each week is a set of SESSIONS, and for each session you may
   pick any turma that teaches it. So:

     - PL/TP where every turma meets once a week: the turmas are pure
       alternatives. One 2h slot, any turma, satisfies the 2h.
     - T where every turma meets twice a week on the same weekdays (CC1007_T1 is
       Tue 14:00 + Thu 14:00, T2 is Tue 15:00 + Thu 15:00): Tuesday and Thursday
       teach DIFFERENT material, so you owe one Tuesday hour AND one Thursday
       hour. You may take Tuesday from T1 and Thursday from T2 - that is the
       flexibility - but two Tuesday hours are the same hour twice and do not
       add up to the weekly load.

   Everything below follows from that distinction.  */
window.SOLVER = (function () {
  "use strict";

  const min = t => (+t.slice(0, 2)) * 60 + (+t.slice(3, 5));
  const DAY3 = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

  /* ---- requirements ----------------------------------------------------- */

  /* Merge slots that share (day, start, end): two turmas meeting at the same
     hour are ONE option, not two, and we keep both names so the UI can pick
     whichever still has vacancies. */
  function slotEntry(map, cl, s) {
    const key = s.day + "|" + s.start + "|" + s.end;
    let e = map.get(key);
    if (!e) {
      e = {day: s.day, start: s.start, end: s.end,
           mins: min(s.end) - min(s.start),
           rooms: new Set(), turmas: new Set(), vacancies: 0};
      map.set(key, e);
    }
    (s.rooms || []).forEach(r => e.rooms.add(r));
    e.turmas.add(cl.name);
    e.vacancies = Math.max(e.vacancies, cl.vacant_places || 0);
    return e;
  }

  const bySlot = (a, b) => a.day - b.day || min(a.start) - min(b.start);

  /* subjects: raw subject objects. weeklySlots(cl) -> the regular slots of a
     turma in the semester being planned. overrides: {"CODE|TYPE": minutes}. */
  function requirements(subjects, weeklySlots, overrides, allowRestricted) {
    const reqs = [], notes = [];
    overrides = overrides || {};

    for (const sub of subjects) {
      const byType = new Map();
      for (const cl of sub.classes) {
        if (!allowRestricted && cl.name.includes("L:")) continue;
        const reg = weeklySlots(cl);
        if (reg.length) {
          if (!byType.has(cl.type)) byType.set(cl.type, []);
          byType.get(cl.type).push({cl, reg});
        }
      }

      for (const type of [...byType.keys()].sort()) {
        const opts = byType.get(type);
        const perTurma = new Set(opts.map(o => o.reg.length));
        const daySets = new Set(opts.map(o =>
          [...new Set(o.reg.map(s => s.day))].sort().join(",")));
        const ov = overrides[sub.code + "|" + type];
        const base = {code: sub.code, type, subject: sub};

        if (perTurma.size === 1 && perTurma.has(1)) {
          // One weekly session; every turma is an alternative time for it.
          const map = new Map();
          for (const {cl, reg} of opts) for (const s of reg) slotEntry(map, cl, s);
          const slots = [...map.values()].sort(bySlot);
          const full = Math.max(...slots.map(s => s.mins));
          reqs.push({...base, label: `${sub.code} ${type}`, key: sub.code + "|" + type,
                     need: ov == null ? full : ov, full, slots, onePerDay: false});

        } else if (daySets.size === 1 && ov == null) {
          // Several sessions a week on the same weekdays in every turma: one
          // requirement per weekday, and you choose only the TIME on each.
          const days = [...daySets][0].split(",").map(Number);
          for (const day of days) {
            const map = new Map();
            for (const {cl, reg} of opts)
              for (const s of reg) if (s.day === day) slotEntry(map, cl, s);
            const slots = [...map.values()].sort(bySlot);
            const full = Math.max(...slots.map(s => s.mins));
            reqs.push({...base, label: `${sub.code} ${type} (${DAY3[day]})`,
                       key: sub.code + "|" + type, day,
                       need: full, full, slots, onePerDay: false});
          }

        } else if (daySets.size === 1) {
          // Explicitly asking for fewer hours than the full load: choose WHICH
          // sessions to attend. Never two on the same weekday - same session.
          const map = new Map();
          for (const {cl, reg} of opts) for (const s of reg) slotEntry(map, cl, s);
          const slots = [...map.values()].sort(bySlot);
          const full = Math.max(...opts.map(o =>
            o.reg.reduce((a, s) => a + min(s.end) - min(s.start), 0)));
          reqs.push({...base, label: `${sub.code} ${type} (parcial)`,
                     key: sub.code + "|" + type,
                     need: ov, full, slots, onePerDay: true, partial: true});

        } else {
          // Turmas disagree on which weekdays they use. Fall back to filling
          // hours, and say so rather than silently guessing.
          notes.push(`${sub.code} ${type}: as turmas usam dias diferentes — `
                   + `preenchido só por horas.`);
          const map = new Map();
          for (const {cl, reg} of opts) for (const s of reg) slotEntry(map, cl, s);
          const slots = [...map.values()].sort(bySlot);
          const full = Math.max(...opts.map(o =>
            o.reg.reduce((a, s) => a + min(s.end) - min(s.start), 0)));
          reqs.push({...base, label: `${sub.code} ${type}`, key: sub.code + "|" + type,
                     need: ov == null ? full : ov, full, slots, onePerDay: true});
        }
      }
    }
    return {reqs, notes};
  }

  /* ---- combinations ----------------------------------------------------- */

  function disjoint(slots) {
    for (let i = 0; i < slots.length; i++)
      for (let j = i + 1; j < slots.length; j++) {
        const a = slots[i], b = slots[j];
        if (a.day === b.day && min(a.start) < min(b.end) && min(b.start) < min(a.end))
          return false;
      }
    return true;
  }

  function combinations(arr, k) {
    const out = [], cur = [];
    (function rec(start) {
      if (cur.length === k) { out.push(cur.slice()); return; }
      for (let i = start; i <= arr.length - (k - cur.length); i++) {
        cur.push(arr[i]); rec(i + 1); cur.pop();
      }
    })(0);
    return out;
  }

  /* Minimal non-overlapping slot sets whose total duration reaches `need`.
     "Minimal" means dropping any one slot would break the requirement - it
     stops the solver from padding your week with redundant hours. */
  function combosFor(need, slots, onePerDay) {
    const out = [];
    for (let k = 1; k <= slots.length; k++) {
      for (const pick of combinations(slots, k)) {
        const total = pick.reduce((a, s) => a + s.mins, 0);
        if (total < need) continue;
        // Two slots on the same weekday are the same session twice.
        if (onePerDay && new Set(pick.map(s => s.day)).size !== pick.length) continue;
        if (pick.some(s => total - s.mins >= need)) continue;
        if (disjoint(pick)) out.push(pick);
      }
      if (out.length && k >= 2) break;   // deeper picks can only be non-minimal
    }
    return out;
  }

  /* ---- enumeration ------------------------------------------------------ */

  /* Depth-first over the requirements, most constrained first, rejecting a
     partial timetable the moment it overlaps. That is what keeps a search space
     of tens of thousands from ever being materialised. */
  function enumerate(options, cap) {
    const out = [];
    const order = options.map((o, i) => i)
      .sort((a, b) => options[a].combos.length - options[b].combos.length);
    let truncated = false;

    (function walk(depth, chosen) {
      if (out.length >= cap) { truncated = true; return; }
      if (depth === order.length) { out.push(chosen.slice()); return; }
      const opt = options[order[depth]];
      for (const pick of opt.combos) {
        let ok = true;
        for (const s of pick) {
          for (const c of chosen) {
            if (c.slot.day === s.day && min(c.slot.start) < min(s.end)
                && min(s.start) < min(c.slot.end)) { ok = false; break; }
          }
          if (!ok) break;
        }
        if (!ok) continue;
        const next = chosen.concat(pick.map(s => ({req: opt.req, slot: s})));
        walk(depth + 1, next);
        if (out.length >= cap) return;
      }
    })(0, []);

    return {solutions: out, truncated};
  }

  /* Requirement pairs that cannot both be satisfied whatever else you pick -
     the actionable answer when the enumeration comes back empty. */
  function conflictingPairs(options) {
    const bad = [];
    for (let i = 0; i < options.length; i++)
      for (let j = i + 1; j < options.length; j++) {
        const A = options[i], B = options[j];
        let any = false;
        for (const a of A.combos) { for (const b of B.combos)
          if (disjoint(a.concat(b))) { any = true; break; } if (any) break; }
        if (!any) bad.push([A.req.label, B.req.label]);
      }
    return bad;
  }

  /* ---- scoring ---------------------------------------------------------- */

  const MORNING = 11 * 60;

  function shape(chosen) {
    const byDay = new Map();
    for (const {slot} of chosen) {
      if (!byDay.has(slot.day)) byDay.set(slot.day, []);
      byDay.get(slot.day).push([min(slot.start), min(slot.end)]);
    }
    let gaps = 0, early = 0, span = 0;
    for (const iv of byDay.values()) {
      iv.sort((a, b) => a[0] - b[0]);
      const mg = [];
      for (const [st, en] of iv) {
        if (mg.length && st <= mg[mg.length - 1][1])
          mg[mg.length - 1][1] = Math.max(mg[mg.length - 1][1], en);
        else mg.push([st, en]);
      }
      for (let i = 1; i < mg.length; i++) gaps += mg[i][0] - mg[i - 1][1];
      for (const [st, en] of mg) {
        early += Math.max(0, Math.min(en, MORNING) - st);
        span += en - st;
      }
    }
    const full = chosen.filter(c => c.slot.vacancies === 0).length;
    return {gaps, early, days: byDay.size, full, span};
  }

  // `crit` is an ordered list of active criteria; ties always fall back to a
  // fixed order so the ranking is stable between runs.
  const CRITERIA = {
    gaps:    s => s.gaps,
    morning: s => s.early,
    days:    s => s.days,
    vacancy: s => s.full,
  };

  function scorer(crit) {
    const active = crit.filter(c => CRITERIA[c]);
    return chosen => {
      const s = shape(chosen);
      return {vec: active.map(c => CRITERIA[c](s)).concat([s.gaps, s.days, s.early, s.span]),
              shape: s};
    };
  }

  const cmp = (a, b) => {
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] - b[i];
    return 0;
  };

  /* ---- entry point ------------------------------------------------------ */

  /* opts: {weeklySlots, overrides, allowRestricted, criteria, cap} */
  function solve(subjects, opts) {
    opts = opts || {};
    const cap = opts.cap || 4000;
    const {reqs, notes} = requirements(
      subjects, opts.weeklySlots, opts.overrides, opts.allowRestricted);

    const options = [];
    for (const req of reqs) {
      const combos = combosFor(req.need, req.slots, req.onePerDay);
      options.push({req, combos});
    }
    const impossible = options.filter(o => !o.combos.length).map(o => o.req);
    let space = 1;
    for (const o of options) space *= Math.max(o.combos.length, 1);

    if (impossible.length)
      return {reqs, notes, options, space, impossible, solutions: [], conflicts: []};

    const {solutions, truncated} = enumerate(options, cap);
    const score = scorer(opts.criteria || ["gaps", "morning"]);
    const ranked = solutions.map(c => ({chosen: c, ...score(c)}))
                            .sort((a, b) => cmp(a.vec, b.vec));

    return {reqs, notes, options, space, impossible: [], truncated, solutions: ranked,
            conflicts: ranked.length ? [] : conflictingPairs(options)};
  }

  return {solve, requirements, combosFor, enumerate, disjoint, shape, min};
})();
