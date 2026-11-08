/* nav_core.js: pure logic of the viewer board controls (no DOM, no network).
 * UMD: exposes window.NC in the browser and module.exports in node (tests run in Docker, see tests/README.md).
 * It covers three things: the zoom state (which part of the board is shown, chosen by the user only), stepping along the variation tree
 * (also several moves at once) and the mapping from key presses to those actions. index.html owns the buttons and the canvas.
 * Rectangles are {x0,y0,x1,y1} in board coordinates 0..18, the same shape bbox() in index.html returns. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.NC = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const LAST = 18;
  const FULL = { x0: 0, y0: 0, x1: LAST, y1: LAST };

  // ---------- zoom ----------
  // The zoom state is the number stored in the viewer variable viewMode. The numbers are ids, not an order: quiz.js sets viewMode = 1 to force
  // the focus crop, so 1 has to stay "focus" (that was the meaning before the auto mode was removed). The order of the steps is ZOOM_ORDER.
  const ZOOM = { FOCUS: 1, FULL: 2, MID: 3 };
  const ZOOM_ORDER = [ZOOM.FOCUS, ZOOM.MID, ZOOM.FULL]; // zooming out walks this list to the right, zooming in to the left
  const ZOOM_NAME = { 1: '聚焦', 3: '扩大', 2: '全盘' };
  const ZOOM_KEY = { 1: 'focus', 3: 'mid', 2: 'full' }; // what is written to localStorage, so the stored value does not depend on the ids
  const STORE_KEY = 'josekiapp.view.v1';
  const OUT = 1, IN = -1; // directions for stepZoom

  const sameRect = (a, b) => a.x0 === b.x0 && a.y0 === b.y0 && a.x1 === b.x1 && a.y1 === b.y1;
  const validRect = r => !!r && [r.x0, r.y0, r.x1, r.y1].every(v => Number.isInteger(v) && v >= 0 && v <= LAST) && r.x0 <= r.x1 && r.y0 <= r.y1;

  // grow [lo, hi] to `size` lines, centred, then slide it back inside the board
  function fit(lo, hi, size) {
    let a = lo - Math.floor((size - (hi - lo)) / 2), b = a + size;
    if (a < 0) { b -= a; a = 0; }
    if (b > LAST) { a -= b - LAST; b = LAST; }
    return [Math.max(0, a), b];
  }
  // the canvas draws every cell square, so a crop is always as wide as it is tall (bbox() in index.html does the same for the focus crop)
  function squareRect(r) {
    const size = Math.min(LAST, Math.max(r.x1 - r.x0, r.y1 - r.y0)), [x0, x1] = fit(r.x0, r.x1, size), [y0, y1] = fit(r.y0, r.y1, size);
    return { x0, y0, x1, y1 };
  }
  // halfway between the focus crop and the full board on every edge
  function midRect(focus) {
    return squareRect({ x0: Math.floor(focus.x0 / 2), y0: Math.floor(focus.y0 / 2), x1: Math.ceil((focus.x1 + LAST) / 2), y1: Math.ceil((focus.y1 + LAST) / 2) });
  }
  // The rectangle to draw. `focus` is the crop computed once per collection from its stones. An unknown mode or a missing crop falls back safely:
  // unknown mode -> focus (old stored values), missing or broken crop -> the full board.
  function zoomRect(mode, focus) {
    if (!validRect(focus) || mode === ZOOM.FULL) return FULL;
    if (mode === ZOOM.MID) return midRect(focus);
    return focus;
  }
  // The modes that really differ for this crop, in zoom order. A crop that already covers most of the board makes the middle step (or all of them) identical to a neighbour, and a
  // button that changes nothing is worse than no button. Built from the wide end, so when two steps draw the same rectangle the wider one ("full") is the one that stays.
  function zoomLevels(focus) {
    const out = [];
    for (let i = ZOOM_ORDER.length - 1; i >= 0; i--) {
      const m = ZOOM_ORDER[i];
      if (!out.length || !sameRect(zoomRect(m, focus), zoomRect(out[0], focus))) out.unshift(m);
    }
    return out;
  }
  // next mode when zooming in (IN) or out (OUT); stays where it is at the end of the range. A mode that looks like a neighbour for this crop counts as that neighbour.
  function stepZoom(mode, dir, focus) {
    const lv = zoomLevels(focus), here = zoomRect(mode, focus);
    let i = lv.findIndex(m => sameRect(zoomRect(m, focus), here));
    if (i < 0) i = 0;
    const j = i + (dir > 0 ? 1 : -1);
    return j < 0 || j >= lv.length ? mode : lv[j];
  }
  const canStep = (mode, dir, focus) => stepZoom(mode, dir, focus) !== mode;

  // storage is anything with getItem and setItem (localStorage in the page, a fake in the tests); every access is guarded, a failure just means no memory
  function parseZoom(text) {
    try {
      const o = JSON.parse(text), hit = ZOOM_ORDER.find(m => ZOOM_KEY[m] === (o && o.zoom));
      if (hit) return hit;
    } catch (e) { /* not JSON: use the default */ }
    return ZOOM.FOCUS;
  }
  function loadZoom(store, key) {
    try { return parseZoom(store.getItem(key || STORE_KEY)); } catch (e) { return ZOOM.FOCUS; }
  }
  function saveZoom(store, key, mode) {
    try { store.setItem(key || STORE_KEY, JSON.stringify({ zoom: ZOOM_KEY[mode] || 'focus' })); return true; } catch (e) { return false; }
  }

  // ---------- points that are not in the current view ----------
  // points are [x, y, ...] arrays as the viewer keeps them (stones, ghost moves, highlighted coordinates)
  const inRect = (p, V) => !!p && p[0] >= V.x0 && p[0] <= V.x1 && p[1] >= V.y0 && p[1] <= V.y1;
  function outside(points, V) {
    const seen = new Set(), out = [];
    (points || []).forEach(p => { const k = p[0] + ',' + p[1]; if (!inRect(p, V) && !seen.has(k)) { seen.add(k); out.push(p); } });
    return out;
  }
  // a region [x0,y0,x1,y1] cut to the view, or null when they do not touch
  function clipRect(r, V) {
    const x0 = Math.max(r[0], V.x0), y0 = Math.max(r[1], V.y0), x1 = Math.min(r[2], V.x1), y1 = Math.min(r[3], V.y1);
    return x0 > x1 || y0 > y1 ? null : [x0, y0, x1, y1];
  }
  // "Q16 R14 +2": the first `max` points by name, then how many more
  function listPts(points, name, max) {
    const m = max || 5, head = points.slice(0, m).map(name).join(' ');
    return points.length > m ? head + ' +' + (points.length - m) : head;
  }

  // ---------- stepping along the variation tree ----------
  // 5 moves per jump: a joseki line in the library is mostly 8 to 20 moves long, so 5 skips a good part of a line without overshooting a short one,
  // 3 needs too many presses on long lines and 10 can skip a whole short line. Both the buttons and the keys use this value.
  const FAST = 5;
  // Forward: the first step takes the variation selected in the list (sel), later steps take the first child, exactly like pressing the next button n times
  // (going to a node resets the selection). Stops at a leaf. Returns {node, steps}; steps is how far it really went.
  function stepForward(node, sel, n) {
    let cur = node, steps = 0;
    while (steps < n && cur && cur.c && cur.c.length) {
      cur = (steps === 0 && cur.c[sel]) || cur.c[0];
      steps++;
    }
    return { node: cur, steps };
  }
  // Back: up the parent chain, stops at the root. A trial node (not listed among its parent's children) walks up the same way.
  // `root` is the collection's first node: the SGF parser hangs it under an empty helper node, so "no parent" would run one step past it onto an empty board.
  function stepBack(node, n, root) {
    let cur = node, steps = 0;
    while (steps < n && cur && cur.up && cur !== root) { cur = cur.up; steps++; }
    return { node: cur, steps };
  }

  // ---------- keys ----------
  // Returns the action name for a keydown event or null. Ctrl, Alt and Meta combinations belong to the browser (Alt+Left is "back"), so they are not ours.
  // Shift only changes the left and right arrows into the fast jump.
  function keyAction(e) {
    if (!e || e.ctrlKey || e.altKey || e.metaKey) return null;
    switch (e.key) {
      case 'ArrowLeft': return e.shiftKey ? 'fastBack' : 'back';
      case 'ArrowRight': return e.shiftKey ? 'fastFwd' : 'fwd';
      case 'PageUp': return 'fastBack';
      case 'PageDown': return 'fastFwd';
      case 'ArrowUp': return 'varUp';
      case 'ArrowDown': return 'varDown';
      case 'Home': return 'home';
      case 'End': return 'end';
      default: return null;
    }
  }

  return {
    LAST, FULL, ZOOM, ZOOM_ORDER, ZOOM_NAME, ZOOM_KEY, STORE_KEY, OUT, IN, FAST,
    squareRect, midRect, zoomRect, zoomLevels, stepZoom, canStep, parseZoom, loadZoom, saveZoom,
    outside, clipRect, listPts, stepForward, stepBack, keyAction
  };
});
