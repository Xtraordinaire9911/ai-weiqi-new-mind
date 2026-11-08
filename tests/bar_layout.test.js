'use strict';
// Static guards for the stable control bar and the user controlled zoom. They read the source text of the viewer (no browser), so they cannot prove that the
// buttons do not move, the browser measurements in the pull request do that; they stop the usual ways of breaking it again:
// display:none on a bar button, a label that changes at run time, a zoom that is set by a node, a bar button that the phone layout forgets.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const read = f => fs.readFileSync(path.join(root, f), 'utf8');
const html = read('index.html'), mobile = read('mobile.js'), panel = read('engine_panel.js');

const barHtml = html.slice(html.indexOf('<div class="bar"'), html.indexOf('<div id="cap"'));
const buttons = [...barHtml.matchAll(/<button\b([^>]*)>([^<]*)<\/button>/g)].map(m => ({ id: /\bid="([^"]+)"/.exec(m[1])[1], cls: (/\bclass="([^"]+)"/.exec(m[1]) || [, ''])[1].split(/\s+/), attrs: m[1], label: m[2].replace(/︎/g, '') })); // U+FE0E asks for the plain text look of the arrow symbols (the emoji look differs from button to button)
const ids = buttons.map(b => b.id);
const WIDTH = { i: 44, s: 60, m: 84 }; // must match the css below; checked in the next tests

test('the bar has the buttons in the agreed order: steps, then the zoom group, then the tools', () => {
  assert.deepEqual(ids, ['b0', 'br5', 'b1', 'b2', 'bf5', 'b3', 'bzo', 'bzi', 'bn', 'ba', 'bl', 'bk', 'bq']);
});

test('the fast steps sit symmetrically around the step buttons: home, back 5, back, next, forward 5, end', () => {
  const row = ids.slice(0, 6);
  assert.deepEqual(row, ['b0', 'br5', 'b1', 'b2', 'bf5', 'b3']);
  assert.equal(buttons[1].label, '⏪'); assert.equal(buttons[4].label, '⏩');
});

test('the zoom buttons are a separate group: a rule element between the steps and the zoom pair, none inside the steps', () => {
  const row1 = barHtml.slice(barHtml.indexOf('id="brn"') + 8, barHtml.indexOf('id="brt"'));
  const order = [...row1.matchAll(/id="(b[0-9a-z]+)"|class="sep"/g)].map(m => m[1] || 'SEP');
  assert.deepEqual(order, ['b0', 'br5', 'b1', 'b2', 'bf5', 'b3', 'SEP', 'bzo', 'bzi']);
});

test('every bar button has a width class (icon, two characters or wide) and a constant label', () => {
  for (const b of buttons) {
    assert.ok(b.cls.some(c => c in WIDTH), b.id + ' has no width class');
    assert.ok(b.label.length > 0, b.id + ' has no label');
  }
  assert.ok(buttons.filter(b => b.cls.includes('i')).every(b => b.label.length === 1), 'icon buttons hold a single symbol');
});

test('the width classes are fixed pixel widths in the css, and the engine panel button joins with a width class', () => {
  for (const [c, px] of Object.entries(WIDTH)) {
    if (c === 's') assert.match(html, new RegExp('\\.bar button\\{[^}]*\\bwidth:' + px + 'px'), 'base width');
    else assert.match(html, new RegExp('\\.bar button\\.' + c + '\\{[^}]*\\bwidth:' + px + 'px'), 'width of .' + c);
  }
  assert.match(panel, /bt\.className\s*=\s*'s'/);
  assert.match(panel, /getElementById\('brt'\)/);
});

test('the widest row still fits the narrowest desktop column, so the rows never wrap there', () => {
  // desktop layout starts at 1200 px (landscape): 1200 - 240 sidebar - 380 panel - 20 padding - 15 scrollbar
  const COLUMN = 1200 - 240 - 380 - 20 - 15, GAP = 6, SEP = 1 + 2 * 10, LABEL = 52;
  const w = id => WIDTH[buttons.find(b => b.id === id).cls.find(c => c in WIDTH)];
  const row1 = ['b0', 'br5', 'b1', 'b2', 'bf5', 'b3'].map(w), row1w = row1.reduce((a, b) => a + b, 0) + 5 * GAP + GAP + SEP + GAP + w('bzo') + GAP + LABEL + GAP + w('bzi');
  const row2 = ['bn', 'ba', 'bl', 'bk', 'bq'].map(w).concat([WIDTH.s]), row2w = row2.reduce((a, b) => a + b, 0) + (row2.length - 1) * GAP; // the sixth button is the engine panel's
  assert.ok(row1w <= COLUMN, 'row 1 is ' + row1w + ' wide, the column ' + COLUMN);
  assert.ok(row2w <= COLUMN, 'row 2 is ' + row2w + ' wide, the column ' + COLUMN);
});

test('no bar button is ever hidden with display:none; conditional buttons are dimmed through disabled', () => {
  assert.ok(!/style="[^"]*display\s*:\s*none/.test(barHtml), 'inline display:none in the bar');
  assert.ok(/<button id="bl"[^>]*\bdisabled\b/.test(barHtml), 'the ladder button starts dimmed, not hidden');
  const BAR_IDS = 'b0|br5|b1|b2|bf5|b3|bzo|bzi|bn|ba|bl|bk|bq|bep|zl';
  const bad = new RegExp("\\$\\('(" + BAR_IDS + ")'\\)\\s*\\.(style|hidden|innerHTML|classList\\.add\\('hidden)", 'g');
  for (const [f, s] of [['index.html', html], ['mobile.js', mobile], ['engine_panel.js', panel]]) assert.deepEqual([...s.matchAll(bad)].map(m => m[0]), [], f + ' hides or restyles a bar button');
  assert.ok(!/bl\.style|\$\('bl'\)\.style/.test(html), 'the ladder button is not toggled with style');
});

test('button labels never change at run time (only the zoom label span does)', () => {
  const BTN = 'b0|br5|b1|b2|bf5|b3|bzo|bzi|bn|ba|bl|bk|bq';
  const bad = new RegExp("\\$\\('(" + BTN + ")'\\)\\s*\\.(textContent|innerText|innerHTML)\\s*=", 'g');
  for (const [f, s] of [['index.html', html], ['mobile.js', mobile]]) assert.deepEqual([...s.matchAll(bad)].map(m => m[0]), [], f + ' relabels a bar button');
});

test('the caption strip and the path have reserved space and are not shown or hidden with display', () => {
  assert.match(html, /#cap\{[^}]*\bheight:\d+px/, 'fixed strip height');
  assert.match(html, /#cap\{[^}]*visibility:hidden/, 'hidden by visibility, not display');
  assert.match(html, /#path\{[^}]*\bheight:\d+px/, 'fixed path height');
  assert.match(html, /main\{scrollbar-gutter:stable\}/, 'the column keeps its width when a scrollbar appears');
  assert.ok(!/\$\('cap'\)\.style\.display|cap\.style\.display/.test(html), 'cap display is not toggled');
});

test('the visible region is the user\'s choice only: no auto mode, no zoom change tied to a node', () => {
  assert.ok(!/viewMode\s*===\s*0|VM\[|VM=|视角:自动|>自动</.test(html), 'auto mode leftovers in index.html');
  assert.match(html, /V=NC\.zoomRect\(viewMode,view\)/);
  const writes = [...html.matchAll(/\bviewMode\s*=(?!=)/g)].map(m => html.slice(Math.max(0, m.index - 60), m.index + 40).replace(/\s+/g, ' '));
  assert.equal(writes.length, 2, 'viewMode is assigned in exactly two places: its initial value and setZoom(): ' + writes.join(' | '));
  assert.ok(writes.some(w => /let viewMode=NC\.loadZoom/.test(w)) && writes.some(w => /function setZoom/.test(w)));
  const go = /function go\(n\)\{[^\n]*\}/.exec(html)[0];
  assert.ok(!/viewMode|setZoom/.test(go), 'go() must not touch the zoom');
  const open = /function open_\(c\)\{[^\n]*\}/.exec(html)[0];
  assert.ok(!/viewMode|setZoom/.test(open), 'open_() must not touch the zoom, only the focus crop');
  assert.ok(/view=bbox\(tree\)/.test(open), 'the focus crop is computed once per collection');
  assert.ok(!/bbox\(/.test(html.replace(/function bbox\([\s\S]*?\n/, '').replace(open, '')), 'bbox() is not called per node');
});

test('the zoom is stored only in a guarded localStorage access and nav_core.js is loaded before the page script', () => {
  assert.ok(html.indexOf('<script src="nav_core.js">') > 0 && html.indexOf('<script src="nav_core.js">') < html.indexOf('let store=null'));
  assert.match(html, /try\{store=window\.localStorage\}catch\(e\)\{\}/);
});

test('the fast step uses NC.FAST and the keys go through NC.keyAction', () => {
  assert.match(html, /NC\.stepForward\(cur,sel,NC\.FAST\)/);
  assert.match(html, /NC\.stepBack\(cur,NC\.FAST,tree\)/);
  assert.match(html, /NC\.keyAction\(e\)/);
  assert.match(html, /onkeydown=e=>/, 'assigned as a property, the training view saves and restores it');
});

test('the phone layout places every bar button: nothing is left detached', () => {
  const keep = /const BAR_KEEP = \[([^\]]*)\]/.exec(mobile)[1].match(/'[^']+'/g).map(s => s.slice(1, -1));
  for (const id of ['b0', 'br5', 'b1', 'b2', 'bf5', 'b3', 'bzo', 'bzi', 'ba']) assert.ok(keep.includes(id), id + ' belongs in the phone bar');
  assert.match(mobile, /\.br\{display:contents\}/);
  assert.match(mobile, /repeat\(6,minmax\(44px,1fr\)\)/, 'six columns, touch size');
  assert.ok(!/'bf'|\$\('bf'\)/.test(mobile), 'the old view button is gone');
  assert.match(mobile, /--barh:106px/, 'two rows of 44px plus padding');
});

test('nav_core.js is part of the offline shell and of the site builder', () => {
  assert.match(read('sw.js'), /'nav_core\.js'/);
  assert.match(read('tools/make_site.py'), /'nav_core\.js'/);
});
