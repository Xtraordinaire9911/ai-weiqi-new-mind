/* quiz_core.js: pure logic of the joseki training mode (no DOM, no storage).
 * UMD: exposes window.QC in the browser and module.exports in node (tests run in Docker).
 * Data model follows index.html: node {p:{PROP:[vals]}, c:[children], up}, AN entries "sgfcoord:loss:prior:winrate:visits:pv",
 * loss 0 is best and negative is worse (points), PL[B|W] is the side to move. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.QC = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ---------- constants ----------
  const N = 19, M = N - 1, LETTERS = 'ABCDEFGHJKLMNOPQRST', EPS = 1e-9;
  const AI_MIN = -3;                 // AI candidates worse than this many points are never accepted
  const TEACHER_MIN = -1;            // a teacher move is accepted when its AI loss is at least this (or when it has no AI data)
  const INTERVALS = [0, 1, 2, 4, 7, 15, 30]; // Leitner boxes (days); index 0 = "wrong, ask again soon"
  const TOP_BOX = INTERVALS.length - 1, MASTER_STREAK = 2;
  const DAY = 86400000, MIN_GAP = 10 * 60000; // no repeat inside 10 minutes (except the retry of a wrong answer)
  const BUCKETS = { open: [0, 4], mid: [5, 10], deep: [11, 999] }; // depth = moves played before the question
  const DEFAULT_ST = { topN: 3, teacher: true, transform: true, limit: 20, extra: true };

  // ---------- SGF and board (same model as index.html; duplicated here because the page code cannot be loaded in node) ----------
  function parseSgf(s) {
    let i = 0;
    function val() { let v = ''; i++; while (i < s.length && s[i] !== ']') { if (s[i] === '\\') i++; v += s[i++]; } i++; return v; }
    function seq(par) {
      let last = par;
      while (i < s.length) {
        const ch = s[i];
        if (ch === ';') {
          i++;
          const n = { p: {}, c: [], up: last };
          while (i < s.length) {
            while (/\s/.test(s[i])) i++;
            const m = /^[A-Za-z]+/.exec(s.slice(i, i + 10));
            if (!m) break;
            i += m[0].length;
            const a = [];
            while (s[i] === '[' || /\s/.test(s[i])) { if (s[i] === '[') a.push(val()); else i++; }
            n.p[m[0]] = (n.p[m[0]] || []).concat(a);
          }
          last.c.push(n); last = n;
        } else if (ch === '(') { i++; seq(last); } else if (ch === ')') { i++; return; } else i++;
      }
    }
    i = s.indexOf('(') + 1;
    const r0 = { p: {}, c: [], up: null };
    seq(r0);
    return r0.c[0] || null;
  }
  const pt = v => (v && v.length >= 2 ? [v.charCodeAt(0) - 97, v.charCodeAt(1) - 97] : null);
  const onBoard = q => !!q && q[0] >= 0 && q[1] >= 0 && q[0] < N && q[1] < N;
  const sg = (x, y) => String.fromCharCode(97 + x, 97 + y);
  const gtp = ([x, y]) => LETTERS[x] + (N - y);
  const fromGtp = t => (/^[A-HJ-T]([1-9]|1[0-9])$/.test(t) ? [LETTERS.indexOf(t[0]), N - +t.slice(1)] : null);
  function expand(v) {
    if (!v.includes(':')) return [v];
    const [a, b] = v.split(':'), A = pt(a), B = pt(b), o = [];
    for (let x = A[0]; x <= B[0]; x++) for (let y = A[1]; y <= B[1]; y++) o.push(sg(x, y));
    return o;
  }
  const pathTo = node => { const a = []; for (let n = node; n; n = n.up) a.unshift(n); return a; };
  const isSetup = n => !!(n.p.AB || n.p.AW || n.p.AE);
  // the move of a node as {col, m, q}; null for setup nodes, passes and off-board points
  function nodeMove(n) {
    if (isSetup(n)) return null;
    const col = n.p.B ? 1 : n.p.W ? 2 : 0;
    if (!col) return null;
    const m = n.p[col === 1 ? 'B' : 'W'][0], q = pt(m);
    return onBoard(q) ? { col, m, q } : null;
  }

  // replay with captures, same rules as replay() in index.html; returns {b, k (moves played), last}
  function replay(node) {
    const b = Array.from({ length: N }, () => Array(N).fill(0));
    let k = 0, last = null;
    const nb = (x, y) => [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]].filter(([a, c]) => a >= 0 && c >= 0 && a < N && c < N);
    function grp(x, y) {
      const c = b[x][y], seen = new Set([x + ',' + y]), st = [[x, y]], g = []; let lib = 0;
      while (st.length) {
        const [a, d] = st.pop(); g.push([a, d]);
        for (const [e, f] of nb(a, d)) {
          if (b[e][f] === 0) lib++;
          else if (b[e][f] === c && !seen.has(e + ',' + f)) { seen.add(e + ',' + f); st.push([e, f]); }
        }
      }
      return { g, lib };
    }
    for (const n of pathTo(node)) {
      for (const [key, c] of [['AB', 1], ['AW', 2], ['AE', 0]]) (n.p[key] || []).flatMap(expand).forEach(v => { const q = pt(v); if (onBoard(q)) b[q[0]][q[1]] = c; });
      for (const [key, c] of [['B', 1], ['W', 2]]) {
        if (!n.p[key]) continue;
        const q = pt(n.p[key][0]);
        if (!onBoard(q)) continue;
        b[q[0]][q[1]] = c; k++; last = q;
        for (const [e, f] of nb(q[0], q[1])) if (b[e][f] === 3 - c) { const r = grp(e, f); if (!r.lib) r.g.forEach(([a, d]) => { b[a][d] = 0; }); }
        const r = grp(q[0], q[1]);
        if (!r.lib) r.g.forEach(([a, d]) => { b[a][d] = 0; });
      }
    }
    return { b, k, last };
  }
  // side to move after this node: PL if present, otherwise the opposite of the last move on the path (same order as nextCol in index.html)
  function sideToMove(node) {
    const pl = (node.p.PL || [''])[0];
    if (pl) return pl === 'B' ? 1 : 2;
    for (let n = node; n; n = n.up) if (n.p.B || n.p.W) return n.p.B ? 2 : 1;
    return 1;
  }

  // side to move of a question: PL when present, else the colour of the teacher's moves (a setup root has no last move to infer from), else the last move
  function questionSide(node, kids) {
    if ((node.p.PL || [''])[0]) return sideToMove(node);
    if (kids.length && kids.every(k => k.mv.col === kids[0].mv.col)) return kids[0].mv.col;
    return sideToMove(node);
  }

  // ---------- AN parsing ----------
  function parseAN(s) {
    const out = [], seen = new Set();
    String(s || '').split(';').filter(Boolean).forEach(e => {
      const [m, l, p, wr, vis, pv] = e.split(':'), q = pt(m), loss = parseFloat(l);
      if (!onBoard(q) || !isFinite(loss) || m.length !== 2 || seen.has(m)) return;
      seen.add(m);
      out.push({ m, loss, prior: parseFloat(p), wr: parseFloat(wr), vis: parseInt(vis, 10), pv: (pv || '').split(' ').filter(Boolean) });
    });
    return out;
  }

  // ---------- question extraction ----------
  // 53-bit string hash (cyrb53): stable across runs, so progress survives regenerated data when the position is the same
  function hash53(str) {
    let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
    for (let i = 0; i < str.length; i++) {
      const ch = str.charCodeAt(i);
      h1 = Math.imul(h1 ^ ch, 2654435761); h2 = Math.imul(h2 ^ ch, 1597334677);
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
  }
  // the moves path of a node: setup lists (sorted) and moves from the root, nothing else (comments and AI data may change between runs)
  function posKey(node) {
    const t = [];
    for (const n of pathTo(node)) {
      for (const k of ['AB', 'AW', 'AE']) if (n.p[k]) t.push(k + ':' + n.p[k].flatMap(expand).sort().join(','));
      for (const k of ['B', 'W']) if (n.p[k]) t.push(k + n.p[k][0]);
    }
    return t.join('|');
  }
  const bucketOf = depth => (depth <= BUCKETS.open[1] ? 'open' : depth <= BUCKETS.mid[1] ? 'mid' : 'deep');
  // real teacher text: a comment that only holds video time marks like "@0|0:38" does not count
  const hasText = c => !!c && c.replace(/@(?:\d+\|)?\d+:\d\d/g, '').trim().length > 0;
  const liveKids = n => n.c.map(c => ({ n: c, mv: nodeMove(c) })).filter(k => k.mv);

  // Every node with two or more live children or with an AN property is a question: position = stones so far, task = the next move
  // of the side to move. Skipped: nodes with neither commentary nor AN, and nodes with fewer than 2 distinct sensible moves.
  function extractQuestions(col, tree) { // tree: optional, an already parsed copy of col.sgf (the UI keeps it for the crop)
    const root = tree || (col && col.sgf ? parseSgf(col.sgf) : null), out = [];
    if (!root) return out;
    (function walk(n) {
      const kids = liveKids(n), anRaw = (n.p.AN || [''])[0];
      if (kids.length >= 2 || anRaw) {
        const text = hasText((n.p.C || [''])[0]);
        if (text || anRaw) {
          const rp = replay(n), ai = parseAN(anRaw).filter(e => !rp.b[pt(e.m)[0]][pt(e.m)[1]]);
          const teacher = [], seen = new Set();
          kids.forEach(k => {
            if (seen.has(k.mv.m) || rp.b[k.mv.q[0]][k.mv.q[1]]) return;
            seen.add(k.mv.m);
            const e = ai.find(a => a.m === k.mv.m);
            teacher.push({ m: k.mv.m, loss: e ? e.loss : null, out: !e && ai.length > 0 }); // out: the node has AI data but this move was not evaluated, so it lies outside the analysed region (tenuki or another corner)
          });
          const sensible = new Set(ai.filter(e => e.loss >= AI_MIN - EPS).map(e => e.m).concat(teacher.filter(t => !t.out).map(t => t.m)));
          if (sensible.size >= 2) {
            out.push({
              id: col.id + '#' + hash53(posKey(n)), cid: col.id, node: n, side: questionSide(n, kids),
              depth: rp.k, bucket: bucketOf(rp.k), ai, teacher, hasAI: ai.length > 0, hasText: text
            });
          }
        }
      }
      n.c.forEach(walk);
    })(root);
    return out;
  }

  // ---------- accepted answers ----------
  function norm(st) {
    const s = Object.assign({}, DEFAULT_ST, st || {});
    s.topN = Math.min(5, Math.max(1, Math.round(+s.topN) || DEFAULT_ST.topN));
    s.limit = Math.min(200, Math.max(1, Math.round(+s.limit) || DEFAULT_ST.limit));
    s.teacher = !!s.teacher; s.transform = !!s.transform; s.extra = !!s.extra;
    return s;
  }
  // Accepted = AI top N by loss (entries worse than AI_MIN ignored; moves tied with the Nth loss are kept because the loss is rounded to 0.1)
  // united with the teacher's own moves whose AI loss is at least TEACHER_MIN. Teacher moves without any AI data count as accepted when the
  // node has no AI data at all; on a node that has AI data a teacher move that was not evaluated lies outside the analysed region (tenuki), so it is not accepted.
  // Each entry keeps its tags: 'ai' (AI top N) and/or 'teacher'. Sorted best first, entries without a loss last.
  function acceptedOf(q, st) {
    const s = norm(st), out = new Map();
    const add = (e, tag) => {
      let a = out.get(e.m);
      if (!a) { a = { m: e.m, loss: null, tags: [], pv: [] }; out.set(e.m, a); }
      if (e.loss != null) a.loss = e.loss;
      if (e.pv && e.pv.length && !a.pv.length) a.pv = e.pv;
      if (!a.tags.includes(tag)) a.tags.push(tag);
    };
    const pool = q.ai.filter(e => e.loss >= AI_MIN - EPS).sort((a, b) => b.loss - a.loss || (b.prior || 0) - (a.prior || 0));
    pool.forEach((e, i) => { if (i < s.topN || Math.abs(e.loss - pool[s.topN - 1].loss) < EPS) add(e, 'ai'); });
    if (s.teacher) {
      q.teacher.forEach(t => {
        if (!t.out && (t.loss == null || t.loss >= TEACHER_MIN - EPS)) add({ m: t.m, loss: t.loss, pv: (q.ai.find(e => e.m === t.m) || {}).pv }, 'teacher');
      });
    }
    return [...out.values()].sort((a, b) => (b.loss == null ? -99 : b.loss) - (a.loss == null ? -99 : a.loss));
  }
  function judge(q, st, mv) {
    const hit = acceptedOf(q, st).find(a => a.m === mv) || null;
    return { ok: !!hit, hit };
  }

  // ---------- board symmetries ----------
  // 8 maps of the 19x19 board: 0 identity, 1 rotate 90 cw, 2 rotate 180, 3 rotate 270 cw, 4 mirror left-right, 5 mirror top-bottom, 6 transpose, 7 anti-transpose
  const SYM = [
    ([x, y]) => [x, y], ([x, y]) => [M - y, x], ([x, y]) => [M - x, M - y], ([x, y]) => [y, M - x],
    ([x, y]) => [M - x, y], ([x, y]) => [x, M - y], ([x, y]) => [y, x], ([x, y]) => [M - y, M - x]
  ];
  const SYM_NAMES = ['原方向', '顺时针旋转90度', '旋转180度', '逆时针旋转90度', '左右镜像', '上下镜像', '沿主对角线翻转', '沿副对角线翻转'];
  const symPoint = (t, p) => SYM[t](p);
  const sameP = (a, b) => a[0] === b[0] && a[1] === b[1];
  const PROBES = [[0, 0], [1, 5], [18, 3], [7, 12]]; // enough to tell the 8 maps apart
  function symFind(f) { // index of the symmetry that behaves like function f, -1 when none
    return SYM.findIndex((s, i) => PROBES.every(p => sameP(s(p), f(p))));
  }
  const SYM_INV = [0, 3, 2, 1, 4, 5, 6, 7]; // rotations 90 and 270 undo each other, the others are involutions
  const symInverse = t => SYM_INV[t];
  // composition: first b, then a
  const symCompose = (a, b) => symFind(p => SYM[a](SYM[b](p)));
  const symSgf = (t, v) => { const q = pt(v); if (!onBoard(q)) return v; const r = SYM[t](q); return sg(r[0], r[1]); }; // passes and off-board marks stay as they are
  const symLabel = (t, label) => { const q = fromGtp(label); return q ? gtp(SYM[t](q)) : label; }; // the label the same point has on the transformed board
  function symRect(t, r) { // crop rectangle {x0,y0,x1,y1} on the transformed board
    const a = SYM[t]([r.x0, r.y0]), b = SYM[t]([r.x1, r.y1]);
    return { x0: Math.min(a[0], b[0]), y0: Math.min(a[1], b[1]), x1: Math.max(a[0], b[0]), y1: Math.max(a[1], b[1]) };
  }
  // props of every node from the root to this node, transformed; only what the board needs (setup, move, PL on the last node)
  function viewPath(node, t, side) { // side: the side to move of the question (defaults to the inferred one)
    const path = pathTo(node);
    return path.map((n, i) => {
      const p = {};
      for (const k of ['AB', 'AW', 'AE']) if (n.p[k]) p[k] = n.p[k].flatMap(expand).map(v => symSgf(t, v));
      for (const k of ['B', 'W']) if (n.p[k]) p[k] = [symSgf(t, n.p[k][0])];
      if (i === path.length - 1) p.PL = [(side || sideToMove(node)) === 1 ? 'B' : 'W'];
      return p;
    });
  }
  function randomSym(rng, on) { return on === false ? 0 : Math.floor((rng || Math.random)() * 8); }

  // ---------- random helpers ----------
  function mulberry32(seed) {
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  function shuffle(arr, rng) {
    const a = arr.slice(), r = rng || Math.random;
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  }

  // ---------- progress and scheduler (Leitner boxes) ----------
  // progress = {v:1, st:settings, q:{id:{b:box, due:day index, last:ms, n:answers, ok:correct answers, top:consecutive arrivals in the last box, mst:1 when mastered}}, day:{d:day index, n:new questions started that day}}
  const defaultProgress = () => ({ v: 1, st: norm(), q: {}, day: { d: 0, n: 0 } });
  function dayIndex(ms) { return Math.floor((ms - new Date(ms).getTimezoneOffset() * 60000) / DAY); } // local calendar day
  const newToday = (P, now) => (P.day && P.day.d === dayIndex(now) ? P.day.n : 0);
  // retry of a wrong answer: box 0 with at least one answer
  const isRetry = r => r.b === 0 && r.n > 0;
  // due and allowed to show: not mastered, due day reached, and not answered in the last 10 minutes unless it is a retry of a wrong one
  function eligible(r, now) {
    if (!r || r.mst) return false;
    return r.due <= dayIndex(now) && (isRetry(r) || now - r.last >= MIN_GAP);
  }
  // record one graded answer (mutates P); correct = one box up, wrong = back to box 0 (due again today)
  function grade(P, id, ok, now) {
    const fresh = !P.q[id], r = P.q[id] || (P.q[id] = { b: 0, due: 0, last: 0, n: 0, ok: 0, top: 0, mst: 0 });
    if (fresh) { const d = dayIndex(now); if (!P.day || P.day.d !== d) P.day = { d, n: 0 }; P.day.n++; }
    r.n++; r.last = now;
    if (ok) {
      r.ok++; r.b = Math.min(r.b + 1, TOP_BOX);
      r.top = r.b === TOP_BOX ? r.top + 1 : 0;
      if (r.top >= MASTER_STREAK) r.mst = 1;
    } else { r.b = 0; r.top = 0; }
    r.due = dayIndex(now) + INTERVALS[r.b];
    return r;
  }
  function markMastered(P, id, now) {
    const fresh = !P.q[id], r = P.q[id] || (P.q[id] = { b: 0, due: 0, last: now, n: 0, ok: 0, top: 0, mst: 0 });
    if (fresh) { const d = dayIndex(now); if (!P.day || P.day.d !== d) P.day = { d, n: 0 }; P.day.n++; } // a question handled today also uses up one of today's new slots
    r.mst = 1;
    return r;
  }
  const usable = (qs, st) => qs.filter(q => acceptedOf(q, st).length > 0);

  // per card numbers: count (usable questions), trained, accuracy, mastered, due now, new ones still unseen
  function statsOf(qs, P, st, now) {
    const u = usable(qs, st);
    let trained = 0, n = 0, ok = 0, mastered = 0, due = 0, fresh = 0;
    u.forEach(q => {
      const r = P.q[q.id];
      if (!r) { fresh++; return; }
      if (r.n > 0 || r.mst) trained++;
      n += r.n; ok += r.ok;
      if (r.mst) mastered++; else if (eligible(r, now)) due++;
    });
    return { total: u.length, trained, acc: n ? ok / n : null, mastered, due, fresh };
  }
  // one question per collection in turn, collections in random order each round; inside a collection the order is kept
  function interleave(list, rng) {
    const g = new Map();
    list.forEach(q => { if (!g.has(q.cid)) g.set(q.cid, []); g.get(q.cid).push(q); });
    const out = []; let ks = [...g.keys()];
    while (ks.length) {
      shuffle(ks, rng).forEach(k => out.push(g.get(k).shift()));
      ks = ks.filter(k => g.get(k).length);
    }
    return out;
  }
  // Daily session: due reviews first (lowest box, then most overdue), then new questions up to today's remaining limit.
  // opts: {mix: interleave collections, dueOnly: no new questions, rng}
  function buildSession(qs, P, st, now, opts) {
    const o = opts || {}, s = norm(st), rng = o.rng || Math.random;
    let due = [], fresh = [];
    usable(qs, s).forEach(q => { const r = P.q[q.id]; if (!r) fresh.push(q); else if (eligible(r, now)) due.push(q); });
    due.sort((a, b) => P.q[a.id].b - P.q[b.id].b || P.q[a.id].due - P.q[b.id].due);
    if (o.mix) { due = interleave(due, rng); fresh = interleave(fresh, rng); } // interleave before the cut so every collection gets its share
    fresh = fresh.slice(0, o.dueOnly ? 0 : Math.max(0, s.limit - newToday(P, now)));
    return { list: due.concat(fresh), due: due.length, fresh: fresh.length };
  }

  // ---------- follow-up questions (附加题) ----------
  // After a correct answer: follow the teacher child that matches the move, play the best reply (better AI loss, else the first child),
  // and ask the next question of the same side that lies on that line (up to 8 plies). qs = questions of the same collection.
  const fuIndex = new WeakMap();
  function followUp(q, mv, qs, st) {
    let idx = fuIndex.get(qs);
    if (!idx) { idx = new Map(qs.map(x => [x.node, x])); fuIndex.set(qs, idx); }
    let n = q.node.c.find(c => { const m = nodeMove(c); return m && m.m === mv; });
    for (let step = 0; n && step < 8; step++) {
      const ks = liveKids(n);
      if (!ks.length) return null;
      const an = parseAN((n.p.AN || [''])[0]);
      const loss = k => { const e = an.find(a => a.m === k.mv.m); return e ? e.loss : -99; };
      n = ks.reduce((best, k) => (loss(k) > loss(best) ? k : best), ks[0]).n; // ties keep the first child (main line)
      const f = idx.get(n);
      if (f && f.side === q.side && acceptedOf(f, st).length > 0) return f;
    }
    return null;
  }

  // ---------- save, export, import ----------
  const num = (v, lo, hi, d) => { v = +v; return isFinite(v) ? Math.min(hi, Math.max(lo, v)) : d; };
  function sanitize(P) {
    const out = defaultProgress();
    if (!P || typeof P !== 'object') return out;
    out.st = norm(P.st);
    if (P.q && typeof P.q === 'object') {
      Object.keys(P.q).forEach(id => {
        const r = P.q[id];
        if (!r || typeof r !== 'object' || id.length > 300 || id === '__proto__') return;
        out.q[id] = {
          b: Math.round(num(r.b, 0, TOP_BOX, 0)), due: Math.round(num(r.due, 0, 1e6, 0)), last: Math.round(num(r.last, 0, 1e14, 0)),
          n: Math.round(num(r.n, 0, 1e6, 0)), ok: Math.round(num(r.ok, 0, 1e6, 0)), top: Math.round(num(r.top, 0, 99, 0)), mst: r.mst ? 1 : 0
        };
        if (out.q[id].ok > out.q[id].n) out.q[id].ok = out.q[id].n;
      });
    }
    if (P.day && typeof P.day === 'object') out.day = { d: Math.round(num(P.day.d, 0, 1e6, 0)), n: Math.round(num(P.day.n, 0, 1e6, 0)) };
    return out;
  }
  const EXPORT_APP = 'josekiapp-quiz';
  function exportProgress(P, now) {
    return JSON.stringify({ app: EXPORT_APP, v: 1, saved: new Date(now == null ? Date.now() : now).toISOString(), data: sanitize(P) });
  }
  // mode 'merge' (default): per question the record with the later last answer wins, settings come from the file;
  // mode 'replace': the file replaces everything. Returns {ok, P, error, count}.
  function importProgress(text, cur, mode) {
    let j;
    try { j = JSON.parse(text); } catch (e) { return { ok: false, error: '不是有效的 JSON 文件' }; }
    if (!j || j.app !== EXPORT_APP || !j.data) return { ok: false, error: '这不是本训练模块导出的进度文件' };
    if (j.v !== 1) return { ok: false, error: '进度文件版本不支持: ' + j.v };
    const inc = sanitize(j.data);
    if (mode === 'replace' || !cur) return { ok: true, P: inc, count: Object.keys(inc.q).length };
    const out = sanitize(cur);
    Object.keys(inc.q).forEach(id => { if (!out.q[id] || inc.q[id].last > out.q[id].last) out.q[id] = inc.q[id]; });
    out.st = inc.st;
    if (inc.day.d > out.day.d) out.day = inc.day;
    return { ok: true, P: out, count: Object.keys(inc.q).length };
  }

  return {
    // constants
    N, INTERVALS, TOP_BOX, MASTER_STREAK, MIN_GAP, DAY, BUCKETS, DEFAULT_ST, AI_MIN, TEACHER_MIN, SYM_NAMES,
    // sgf and board
    parseSgf, pt, sg, gtp, fromGtp, expand, replay, sideToMove, questionSide, parseAN, nodeMove, hasText,
    // questions
    hash53, posKey, bucketOf, extractQuestions, norm, acceptedOf, judge, followUp,
    // symmetries
    symPoint, symInverse, symCompose, symSgf, symLabel, symRect, viewPath, randomSym,
    // scheduler and session
    mulberry32, shuffle, defaultProgress, dayIndex, eligible, isRetry, grade, markMastered, statsOf, interleave, buildSession, newToday,
    // persistence helpers
    sanitize, exportProgress, importProgress
  };
});
