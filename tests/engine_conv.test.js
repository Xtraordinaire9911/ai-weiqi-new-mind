'use strict';
// The engine panel must not carry its own copy of the perspective conversion or the candidate string: it calls the viewer's RC.conv / RC.mkAN.
// These tests (1) check that the panel files contain no perspective code, and (2) run the REAL conv / mkAN text taken out of index.html, so a change there is caught.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const read = f => fs.readFileSync(path.join(root, f), 'utf8');
const html = read('index.html');

// cut "function name(...){ ... }" out of the page source by matching braces
function grab(src, header) {
  const i = src.indexOf(header);
  assert.ok(i >= 0, 'not found in index.html: ' + header);
  let depth = 0, j = src.indexOf('{', i);
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}' && --depth === 0) return src.slice(i, k + 1);
  }
  throw new Error('unbalanced: ' + header);
}
const lineOf = (src, start) => { const i = src.indexOf(start); assert.ok(i >= 0, start); return src.slice(i, src.indexOf('\n', i)); };

function loadRC() {
  const code = [lineOf(html, "const N=19,L='ABCDEFGHJKLMNOPQRST'"), lineOf(html, 'const gtp=([x,y])=>'), grab(html, 'function conv(d)'), grab(html, 'function mkAN(cand,tv)'),
    'this.conv=conv;this.mkAN=mkAN;this.fromGtp=fromGtp;'].join('\n');
  const box = {};
  vm.runInNewContext('(function(){' + code + '}).call(box)', { box });
  return box;
}
const RC = loadRC();

const reply = (cur, rootScore, infos, over) => Object.assign({
  bridge: { winratesAs: 'BLACK', fake: false },
  rootInfo: { currentPlayer: cur, scoreLead: rootScore, winrate: 0.6, visits: 100 },
  moveInfos: infos
}, over);
const info = (move, order, lead, wr, pv) => ({ move, order, visits: 100 - order * 10, scoreLead: lead, winrate: wr, prior: 0.3, pv });

test('panel files hold no perspective code (they call RC.conv)', () => {
  for (const f of ['engine_panel.js', 'engine_core.js', 'engine_net.js']) {
    const s = read(f);
    for (const w of ['scoreLead', 'winrate', 'currentPlayer', 'winratesAs']) {
      assert.ok(!s.includes(w), f + ' mentions ' + w + ': the Black -> side to move conversion must stay in RC.conv');
    }
  }
  const panel = read('engine_panel.js');
  assert.ok(/RC\.conv\(/.test(panel) && /RC\.mkAN\(/.test(panel) && /RC\.query\(/.test(panel) && /RC\.forceTeacher\(/.test(panel), 'the panel must use the viewer functions');
});

test('conv: Black to move keeps the sign, White to move flips scores and win rates', () => {
  const b = RC.conv(reply('B', 3, [info('Q3', 0, 3.2, 0.61, ['Q3', 'D17'])]));
  assert.equal(b.t, 'B'); assert.equal(b.score, 3); assert.equal(b.cand[0].s, 3.2); assert.equal(b.cand[0].wr, 0.61);
  const w = RC.conv(reply('W', 3, [info('D3', 0, 3.2, 0.61, ['D3'])]));
  assert.equal(w.t, 'W'); assert.equal(w.score, -3); assert.equal(w.cand[0].s, -3.2); assert.ok(Math.abs(w.cand[0].wr - 0.39) < 1e-9);
});

test('conv: refuses a response that does not declare Black\'s perspective, or has no candidates', () => {
  assert.throws(() => RC.conv(reply('B', 1, [info('Q3', 0, 1, 0.5, ['Q3'])], { bridge: { winratesAs: 'SIDETOMOVE' } })), /黑方视角/);
  assert.throws(() => RC.conv(reply('B', 1, [info('Q3', 0, 1, 0.5, ['Q3'])], { bridge: {} })), /黑方视角/);
  assert.throws(() => RC.conv(reply('B', 1, [])), /候选点/);
  assert.throws(() => RC.conv({ bridge: { winratesAs: 'BLACK' }, rootInfo: null, moveInfos: [] }), /候选点/);
});

test('conv: keeps order, caps at 14 candidates and 8 moves, and drops pv strings that are not moves', () => {
  const many = Array.from({ length: 20 }, (_, i) => info('Q' + (i % 9 + 1), 19 - i, 1, 0.5, ['Q3']));
  const r = RC.conv(reply('B', 1, many));
  assert.equal(r.cand.length, 14);
  assert.deepEqual(r.cand.map(c => c.m).slice(0, 2), many.slice().sort((a, b) => a.order - b.order).slice(0, 2).map(c => c.move));
  const pv = ['Q3', 'D17', 'pass', '<img src=x onerror=alert(1)>', 'Z99', 'A1', 'B2', 'C3', 'D4', 'E5', 'F6', 'G7'];
  const c = RC.conv(reply('B', 1, [info('Q3', 0, 1, 0.5, pv)])).cand[0];
  assert.deepEqual(c.pv, ['Q3', 'D17', 'pass', 'A1', 'B2', 'C3', 'D4', 'E5']);
});

test('mkAN: best = 0.0, the others are points worse than the best; unreliable candidates are left out; forced moves always stay', () => {
  const cand = [{ m: 'Q3', v: 100, s: 2.0, wr: 0.55, p: 0.3, pv: ['Q3', 'D17'] }, { m: 'D3', v: 50, s: 1.5, wr: 0.5, p: 0.2, pv: ['D3'] },
    { m: 'R4', v: 3, s: 9.0, wr: 0.9, p: 0.01, pv: ['R4'] }, { m: 'C3', v: 100, s: -1, wr: 0.3, p: -1, pv: ['C3'], f: 1 }];
  const an = RC.mkAN(cand, 100);
  assert.equal(an, 'pq:0.0:0.30:55:100:Q3 D17;dq:-0.5:0.20:50:50:D3;cq:-3.0:-1.00:30:100:C3');
  assert.ok(!an.includes('qp:'), 'the 3-visit candidate (R4 = qp) does not decide the best');
});
