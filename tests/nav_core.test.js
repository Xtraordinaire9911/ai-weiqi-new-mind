'use strict';
// Tests for nav_core.js (zoom state, stepping along the variation tree, keys) with the built in runner: node --test tests/
// The trees here are small hand built toys, not real library data.
const test = require('node:test');
const assert = require('node:assert/strict');
const NC = require('../nav_core.js');

const R = (x0, y0, x1, y1) => ({ x0, y0, x1, y1 });
const area = r => (r.x1 - r.x0 + 1) * (r.y1 - r.y0 + 1);
const inside = (a, b) => a.x0 >= b.x0 && a.y0 >= b.y0 && a.x1 <= b.x1 && a.y1 <= b.y1; // a is inside b

// ---------- zoom rectangles ----------
test('focus returns the crop itself, full returns the whole board', () => {
  const f = R(0, 7, 11, 18);
  assert.equal(NC.zoomRect(NC.ZOOM.FOCUS, f), f);
  assert.deepEqual(NC.zoomRect(NC.ZOOM.FULL, f), R(0, 0, 18, 18));
});

test('the middle step of a corner crop is the square halfway to the full board', () => {
  assert.deepEqual(NC.zoomRect(NC.ZOOM.MID, R(0, 7, 11, 18)), R(0, 3, 15, 18)); // the numbers seen in the page for 点三三
  assert.deepEqual(NC.zoomRect(NC.ZOOM.MID, R(0, 0, 10, 10)), R(0, 0, 14, 14));
});

test('the middle step is square, contains the crop and stays on the board, for every crop that bbox() can produce', () => {
  for (let x0 = 0; x0 <= 8; x0++) for (let y0 = 0; y0 <= 8; y0++) for (let w = 10; w <= 18; w++) {
    const f = R(x0, y0, Math.min(18, x0 + w), Math.min(18, y0 + w)), m = NC.zoomRect(NC.ZOOM.MID, f);
    assert.equal(m.x1 - m.x0, m.y1 - m.y0, 'square ' + JSON.stringify(f));
    assert.ok(inside(f, m), 'contains the crop ' + JSON.stringify(f) + ' ' + JSON.stringify(m));
    assert.ok(inside(m, R(0, 0, 18, 18)), 'on the board');
  }
});

test('zoom rectangles grow in order focus <= middle <= full', () => {
  const f = R(2, 8, 12, 18);
  const a = area(NC.zoomRect(NC.ZOOM.FOCUS, f)), b = area(NC.zoomRect(NC.ZOOM.MID, f)), c = area(NC.zoomRect(NC.ZOOM.FULL, f));
  assert.ok(a <= b && b <= c);
});

test('squareRect centres the short side and slides back inside the board', () => {
  assert.deepEqual(NC.squareRect(R(3, 3, 9, 13)), R(1, 3, 11, 13)); // 7 wide, 11 tall -> 11 square, grown evenly
  assert.deepEqual(NC.squareRect(R(0, 0, 4, 12)), R(0, 0, 12, 12)); // cannot grow to the left: slides
  assert.deepEqual(NC.squareRect(R(14, 5, 18, 17)), R(6, 5, 18, 17));
});

test('an unknown mode falls back to the focus crop, a missing or broken crop to the full board', () => {
  const f = R(0, 7, 11, 18);
  for (const m of [0, 4, undefined, null, 'x']) assert.equal(NC.zoomRect(m, f), f);
  for (const bad of [null, undefined, {}, R(-1, 0, 5, 5), R(0, 0, 19, 5), R(5, 0, 2, 5), R(0.5, 0, 5, 5)]) assert.deepEqual(NC.zoomRect(NC.ZOOM.FOCUS, bad), R(0, 0, 18, 18));
});

test('quiz.js forces the focus crop with viewMode = 1: that id must stay "focus"', () => {
  assert.equal(NC.ZOOM.FOCUS, 1);
  assert.equal(NC.ZOOM.FULL, 2); // the old numbering of the full board, still valid for anything that stored it
});

// ---------- zoom steps ----------
test('zooming out walks focus, middle, full and stops at the end; zooming in walks back', () => {
  const f = R(0, 7, 11, 18), Z = NC.ZOOM;
  assert.deepEqual(NC.zoomLevels(f), [Z.FOCUS, Z.MID, Z.FULL]);
  assert.equal(NC.stepZoom(Z.FOCUS, NC.OUT, f), Z.MID);
  assert.equal(NC.stepZoom(Z.MID, NC.OUT, f), Z.FULL);
  assert.equal(NC.stepZoom(Z.FULL, NC.OUT, f), Z.FULL);
  assert.equal(NC.stepZoom(Z.FULL, NC.IN, f), Z.MID);
  assert.equal(NC.stepZoom(Z.MID, NC.IN, f), Z.FOCUS);
  assert.equal(NC.stepZoom(Z.FOCUS, NC.IN, f), Z.FOCUS);
});

test('the end stops report themselves (the buttons are dimmed there)', () => {
  const f = R(0, 7, 11, 18), Z = NC.ZOOM;
  assert.equal(NC.canStep(Z.FOCUS, NC.IN, f), false);
  assert.equal(NC.canStep(Z.FOCUS, NC.OUT, f), true);
  assert.equal(NC.canStep(Z.MID, NC.IN, f), true);
  assert.equal(NC.canStep(Z.MID, NC.OUT, f), true);
  assert.equal(NC.canStep(Z.FULL, NC.OUT, f), false);
  assert.equal(NC.canStep(Z.FULL, NC.IN, f), true);
});

test('a crop that already covers the board leaves no step to take, so neither button does anything', () => {
  const full = R(0, 0, 18, 18), Z = NC.ZOOM;
  assert.deepEqual(NC.zoomLevels(full), [Z.FULL]);
  for (const m of [Z.FOCUS, Z.MID, Z.FULL]) { assert.equal(NC.canStep(m, NC.OUT, full), false); assert.equal(NC.canStep(m, NC.IN, full), false); }
});

test('steps that would draw the same rectangle are skipped', () => {
  const f = R(0, 0, 17, 17), Z = NC.ZOOM; // the middle step would already be the full board
  assert.deepEqual(NC.zoomLevels(f), [Z.FOCUS, Z.FULL]);
  assert.equal(NC.stepZoom(Z.FOCUS, NC.OUT, f), Z.FULL);
  assert.equal(NC.stepZoom(Z.FULL, NC.IN, f), Z.FOCUS);
});

test('the zoom does not depend on any node: the same call gives the same answer however often it is asked', () => {
  const f = R(0, 7, 11, 18);
  let m = NC.ZOOM.MID;
  for (let i = 0; i < 20; i++) assert.deepEqual(NC.zoomRect(m, f), R(0, 3, 15, 18));
  assert.equal(NC.stepZoom(NC.ZOOM.FOCUS, NC.IN, f), NC.ZOOM.FOCUS);
});

// ---------- persistence ----------
const fakeStore = (init) => { const m = new Map(Object.entries(init || {})); return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => { m.set(k, String(v)); }, m }; };

test('the zoom survives a save and a load, for every state', () => {
  for (const mode of NC.ZOOM_ORDER) {
    const s = fakeStore();
    assert.equal(NC.saveZoom(s, null, mode), true);
    assert.equal(NC.loadZoom(s, null), mode);
  }
});

test('the stored value is a readable name, not an id', () => {
  const s = fakeStore();
  NC.saveZoom(s, NC.STORE_KEY, NC.ZOOM.FULL);
  assert.deepEqual(JSON.parse(s.m.get(NC.STORE_KEY)), { zoom: 'full' });
});

test('nothing stored, garbage, or an unknown name gives the focus crop', () => {
  assert.equal(NC.loadZoom(fakeStore(), NC.STORE_KEY), NC.ZOOM.FOCUS);
  for (const bad of ['', 'x', '{', 'null', '[]', '{"zoom":"auto"}', '{"zoom":2}', '{"zoom":null}', '{"z":"full"}']) assert.equal(NC.parseZoom(bad), NC.ZOOM.FOCUS, bad);
});

test('a storage that throws (private window, blocked site data, no storage at all) never breaks anything', () => {
  const boom = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  assert.equal(NC.loadZoom(boom, NC.STORE_KEY), NC.ZOOM.FOCUS);
  assert.equal(NC.saveZoom(boom, NC.STORE_KEY, NC.ZOOM.MID), false);
  assert.equal(NC.loadZoom(null, NC.STORE_KEY), NC.ZOOM.FOCUS);
  assert.equal(NC.saveZoom(null, NC.STORE_KEY, NC.ZOOM.MID), false);
});

test('the old auto mode is not a stored state any more', () => {
  assert.equal(NC.parseZoom(JSON.stringify({ zoom: 'auto' })), NC.ZOOM.FOCUS);
  assert.ok(!Object.values(NC.ZOOM_KEY).includes('auto'));
  assert.ok(!Object.values(NC.ZOOM_NAME).some(n => n.includes('自动')));
});

// ---------- points outside the view ----------
test('outside() keeps only points off the view, once each, edges count as inside', () => {
  const V = R(0, 7, 11, 18);
  assert.deepEqual(NC.outside([[11, 7], [0, 18], [12, 7], [5, 6], [15, 15], [15, 15, 2]], V), [[12, 7], [5, 6], [15, 15]]);
  assert.deepEqual(NC.outside([], V), []);
  assert.deepEqual(NC.outside(null, V), []);
});

test('clipRect cuts a named region to the view or says it is wholly outside', () => {
  const V = R(0, 7, 11, 18);
  assert.deepEqual(NC.clipRect([11, 12, 18, 18], V), [11, 12, 11, 18]); // 右下 only touches the right edge
  assert.equal(NC.clipRect([12, 0, 18, 7], V), null);
  assert.deepEqual(NC.clipRect([0, 0, 18, 18], V), [0, 7, 11, 18]);
});

test('listPts names the first few points and counts the rest', () => {
  const nm = p => 'P' + p[0];
  assert.equal(NC.listPts([[1], [2], [3]], nm, 5), 'P1 P2 P3');
  assert.equal(NC.listPts([[1], [2], [3], [4], [5], [6], [7]], nm, 5), 'P1 P2 P3 P4 P5 +2');
});

// ---------- stepping ----------
// node(name, ...children); parents are linked like the viewer's parse() does
function node(name, ...kids) { const n = { name, c: kids, up: null }; kids.forEach(k => { k.up = n; }); return n; }
const line = (len, tag) => { let n = node(tag + len); for (let i = len - 1; i >= 0; i--) n = node(tag + i, n); return n; }; // a chain tag0 -> tag1 -> ... -> tag<len>
const at = (n, k) => { while (k-- > 0) n = n.c[0]; return n; };

test('the jump is 5 moves', () => { assert.equal(NC.FAST, 5); });

test('fast forward goes 5 moves along a chain', () => {
  const root = line(12, 'm');
  const r = NC.stepForward(root, 0, 5);
  assert.equal(r.steps, 5); assert.equal(r.node.name, 'm5');
});

test('fast forward stops at a leaf and says how far it got', () => {
  const root = line(3, 'm');
  const r = NC.stepForward(root, 0, 5);
  assert.equal(r.node.name, 'm3'); assert.equal(r.steps, 3);
  const again = NC.stepForward(r.node, 0, 5);
  assert.equal(again.node, r.node); assert.equal(again.steps, 0);
});

test('fast forward takes the selected variation first, then the first child of every later node', () => {
  const a = line(6, 'a'), b = line(6, 'b'), c = line(6, 'c');
  const root = node('root', a, b, c);
  assert.equal(NC.stepForward(root, 0, 5).node.name, 'a4');
  assert.equal(NC.stepForward(root, 1, 5).node.name, 'b4');
  assert.equal(NC.stepForward(root, 2, 5).node.name, 'c4');
});

test('fast forward ignores a stale selection index instead of getting stuck', () => {
  const root = node('root', line(6, 'a'), line(6, 'b'));
  assert.equal(NC.stepForward(root, 7, 5).node.name, 'a4');
  assert.equal(NC.stepForward(root, -1, 5).node.name, 'a4');
});

test('fast forward passes forks: after the first step it follows the first child', () => {
  const deep = node('d0', node('d1', node('d2')), node('x1'));
  const root = node('root', deep);
  const r = NC.stepForward(root, 0, 5);
  assert.equal(r.node.name, 'd2'); assert.equal(r.steps, 3);
});

test('fast back goes 5 parents up and stops at the root', () => {
  const root = line(12, 'm');
  const start = at(root, 12);
  assert.equal(NC.stepBack(start, 5).node.name, 'm7');
  assert.equal(NC.stepBack(at(root, 3), 5).node, root);
  const r = NC.stepBack(at(root, 3), 5);
  assert.equal(r.steps, 3);
  assert.equal(NC.stepBack(root, 5).steps, 0);
});

test('fast back stops at the given root even though the parser gives it a parent', () => {
  const helper = { name: 'helper', c: [], up: null }, root = line(8, 'm'); // like parse(): the first node hangs under an empty helper node
  root.up = helper; helper.c.push(root);
  const r = NC.stepBack(at(root, 3), 5, root);
  assert.equal(r.node, root); assert.equal(r.steps, 3);
  assert.equal(NC.stepBack(root, 5, root).steps, 0);
  assert.equal(NC.stepBack(root, 5).node, helper, 'without the root argument it would walk one step too far');
});

test('fast back from a trial node that is not among its parent\'s children still walks up', () => {
  const root = line(8, 'm'), parent = at(root, 6), trial = { name: 'trial', c: [], up: parent };
  assert.equal(NC.stepBack(trial, 5).node.name, 'm2');
  assert.equal(NC.stepForward(trial, 0, 5).node, trial);
});

test('zero or negative counts do not move', () => {
  const root = line(5, 'm');
  assert.equal(NC.stepForward(root, 0, 0).node, root);
  assert.equal(NC.stepBack(at(root, 3), 0).node.name, 'm3');
  assert.equal(NC.stepBack(at(root, 3), -2).node.name, 'm3');
});

test('back then forward along the same line returns to the start', () => {
  const root = line(14, 'm'), start = at(root, 9);
  const back = NC.stepBack(start, 5).node, fwd = NC.stepForward(back, 0, 5).node;
  assert.equal(fwd, start);
});

// ---------- keys ----------
const K = (key, o) => Object.assign({ key, shiftKey: false, ctrlKey: false, altKey: false, metaKey: false }, o);

test('the existing keys keep their meaning', () => {
  assert.equal(NC.keyAction(K('ArrowLeft')), 'back');
  assert.equal(NC.keyAction(K('ArrowRight')), 'fwd');
  assert.equal(NC.keyAction(K('ArrowUp')), 'varUp');
  assert.equal(NC.keyAction(K('ArrowDown')), 'varDown');
  assert.equal(NC.keyAction(K('Home')), 'home');
  assert.equal(NC.keyAction(K('End')), 'end');
});

test('PageUp, PageDown and Shift with the left and right arrows are the fast steps', () => {
  assert.equal(NC.keyAction(K('PageUp')), 'fastBack');
  assert.equal(NC.keyAction(K('PageDown')), 'fastFwd');
  assert.equal(NC.keyAction(K('ArrowLeft', { shiftKey: true })), 'fastBack');
  assert.equal(NC.keyAction(K('ArrowRight', { shiftKey: true })), 'fastFwd');
});

test('Ctrl, Alt and Meta combinations are left to the browser (Alt+Left is back)', () => {
  for (const m of ['ctrlKey', 'altKey', 'metaKey']) for (const k of ['ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown', 'Home', 'End', 'ArrowUp']) assert.equal(NC.keyAction(K(k, { [m]: true })), null, m + k);
});

test('other keys do nothing', () => {
  for (const k of ['a', ' ', 'Enter', 'Escape', 'Tab', '+', '-', '0']) assert.equal(NC.keyAction(K(k)), null, k);
  assert.equal(NC.keyAction(null), null);
});
