'use strict';
// Tests for quiz_core.js with the built in runner: node --test tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs'), path = require('path');
const QC = require('../quiz_core.js');

// ---------- helpers ----------
const col = (id, sgf) => ({ id, name: id, sgf });
const ST = QC.DEFAULT_ST;
const ms = (y, mo, d, h, mi) => Date.UTC(y, mo - 1, d, h || 12, mi || 0); // tests run in the container timezone (UTC); noon avoids day edges
const ALL = (() => { const a = []; for (let x = 0; x < 19; x++) for (let y = 0; y < 19; y++) a.push([x, y]); return a; })();
const eqP = (a, b) => a[0] === b[0] && a[1] === b[1];

// Toy tree. Root has setup and two children. Node qc (W to move) has the AN list and four teacher children.
// pc: AI best, rd: -0.9, re: -1.5 (teacher move worse than -1), qd: teacher move that was not evaluated (outside the analysed region); qe: AI -0.4 (not a child); se: -3.5 (ignored)
const AN1 = 'pc:0.0:0.50:50:100:C3 D4;qe:-0.4:0.20:50:40:E5;rd:-0.9:0.10:50:30:D6;re:-1.5:0.05:50:20:E6;se:-3.5:0.01:50:3:F6';
const TOY = `(;GM[1]SZ[19]AB[pd][dp]AW[dd][pp]C[root text](;B[qc]PL[W]C[black plays 3-3 side]AN[${AN1}](;W[pc]C[w1](;B[qd]C[x])(;B[qb]C[y]))(;W[rd]C[w2])(;W[re]C[w3])(;W[qd]C[w4]))(;B[cp]C[second black move]))`;

// ---------- parsing and board ----------
test('parseSgf builds the node tree and keeps escaped brackets', () => {
  const r = QC.parseSgf('(;GM[1]C[a\\]b](;B[aa])(;B[bb];W[cc]))');
  assert.equal(r.p.C[0], 'a]b');
  assert.equal(r.c.length, 2);
  assert.equal(r.c[1].c[0].p.W[0], 'cc');
  assert.equal(r.c[1].c[0].up, r.c[1]);
});

test('replay captures stones and counts moves', () => {
  // white stone at aa is captured by black ba + ab
  const r = QC.parseSgf('(;SZ[19];W[aa];B[ba];W[ee];B[ab])');
  let n = r; while (n.c.length) n = n.c[0];
  const { b, k, last } = QC.replay(n);
  assert.equal(b[0][0], 0);
  assert.equal(b[1][0], 1);
  assert.equal(k, 4);
  assert.deepEqual(last, [0, 1]);
});

test('sideToMove prefers PL and falls back to the last move', () => {
  const r = QC.parseSgf('(;SZ[19];B[aa];W[bb]PL[W];B[cc])');
  const ns = []; for (let n = r; n; n = n.c[0]) ns.push(n);
  assert.equal(QC.sideToMove(ns[0]), 1);   // empty root: black
  assert.equal(QC.sideToMove(ns[1]), 2);   // after B
  assert.equal(QC.sideToMove(ns[2]), 2);   // PL[W] wins over "after W"
  assert.equal(QC.sideToMove(ns[3]), 2);
});

test('a setup root without PL takes the side from the teacher moves', () => {
  // black stone set up by AB, both teacher moves are white: white is to move (the inferred side would be black)
  const qs = QC.extractQuestions(col('s', '(;SZ[19]AB[dd]C[start](;W[cc])(;W[dc]))'));
  assert.equal(qs.length, 1);
  assert.equal(QC.sideToMove(qs[0].node), 1);
  assert.equal(qs[0].side, 2);
  // PL wins when present
  assert.equal(QC.extractQuestions(col('s2', '(;SZ[19]AB[dd]PL[B]C[start](;W[cc])(;W[dc]))'))[0].side, 1);
  // mixed colours: fall back to the inference
  assert.equal(QC.extractQuestions(col('s3', '(;SZ[19];B[dd]C[x](;W[cc])(;B[dc]))'))[0].side, 2);
  // the transformed view carries the question side as PL
  const last = QC.viewPath(qs[0].node, 4, qs[0].side).pop();
  assert.deepEqual(last.PL, ['W']);
});

test('parseAN skips malformed entries and duplicates', () => {
  const a = QC.parseAN('pc:0.0:0.5:50:100:C3 D4;xx;qe:abc:0:0:0:;pc:-1:0:0:0:;rd:-0.9:0.1:50:30:');
  assert.deepEqual(a.map(e => e.m), ['pc', 'rd']);
  assert.deepEqual(a[0].pv, ['C3', 'D4']);
  assert.equal(a[1].loss, -0.9);
});

// ---------- extraction ----------
test('extraction on the toy tree: which nodes become questions', () => {
  const qs = QC.extractQuestions(col('toy', TOY));
  const by = m => qs.find(q => (q.node.p.B || q.node.p.W || ['root'])[0] === m);
  assert.equal(qs.length, 3);
  assert.ok(by('root'), 'root has two live children and text');
  assert.ok(by('qc'), 'qc carries AN');
  assert.ok(by('pc'), 'pc has two children and text');
  assert.equal(by('qc').side, 2);
  assert.equal(by('root').side, 1);
  assert.equal(by('root').depth, 0);
  assert.equal(by('qc').depth, 1);
  assert.equal(by('pc').depth, 2);
});

test('nodes without commentary and without AN are skipped, time marks do not count as commentary', () => {
  const a = QC.extractQuestions(col('a', '(;SZ[19](;B[aa]C[@0|0:12])(;B[bb]C[@1|2:03]))'));
  assert.equal(a.length, 0, 'root has no text at all');
  const b = QC.extractQuestions(col('b', '(;SZ[19]C[@0|0:05](;B[aa])(;B[bb]))'));
  assert.equal(b.length, 0, 'only a time mark');
  const c = QC.extractQuestions(col('c', '(;SZ[19]C[real text](;B[aa])(;B[bb]))'));
  assert.equal(c.length, 1);
});

test('AN alone is enough for a node with a single child', () => {
  const qs = QC.extractQuestions(col('d', '(;SZ[19]AN[aa:0.0:0.5:50:10:A19;bb:-0.3:0.2:50:5:B18](;B[aa]))'));
  assert.equal(qs.length, 1);
  assert.equal(qs[0].hasAI, true);
});

test('fewer than 2 distinct sensible moves: skipped', () => {
  // only one AI entry and the teacher plays the same move
  assert.equal(QC.extractQuestions(col('e', '(;SZ[19]C[t]AN[aa:0.0:0.5:50:10:A19](;B[aa]))')).length, 0);
  // second AI entry is worse than -3 and ignored, the teacher plays the first one
  assert.equal(QC.extractQuestions(col('f', '(;SZ[19]C[t]AN[aa:0.0:0.5:50:10:A19;bb:-3.2:0.2:50:5:B18](;B[aa]))')).length, 0);
  // the same two entries but within -3: kept
  assert.equal(QC.extractQuestions(col('g', '(;SZ[19]C[t]AN[aa:0.0:0.5:50:10:A19;bb:-2.9:0.2:50:5:B18](;B[aa]))')).length, 1);
  // the second teacher move was not evaluated although the node has AI data: it is outside the region and does not count
  assert.equal(QC.extractQuestions(col('i', '(;SZ[19]C[t]AN[aa:0.0:0.5:50:10:A19](;B[aa])(;B[ss]))')).length, 0);
  // a pass child is not a live child
  assert.equal(QC.extractQuestions(col('h', '(;SZ[19]C[t](;B[aa])(;B[]))')).length, 0);
});

test('depth buckets', () => {
  assert.equal(QC.bucketOf(0), 'open');
  assert.equal(QC.bucketOf(4), 'open');
  assert.equal(QC.bucketOf(5), 'mid');
  assert.equal(QC.bucketOf(10), 'mid');
  assert.equal(QC.bucketOf(11), 'deep');
});

// ---------- accepted set ----------
test('accepted set with the default settings', () => {
  const q = QC.extractQuestions(col('toy', TOY)).find(x => x.node.p.B && x.node.p.B[0] === 'qc');
  const acc = QC.acceptedOf(q, ST);
  assert.deepEqual(acc.map(a => a.m), ['pc', 'qe', 'rd']);             // best first
  const t = Object.fromEntries(acc.map(a => [a.m, a.tags]));
  assert.deepEqual(t.pc, ['ai', 'teacher']);
  assert.deepEqual(t.qe, ['ai']);
  assert.deepEqual(t.rd, ['ai', 'teacher']);
  assert.ok(!acc.some(a => a.m === 'qd'), 'teacher move that the analysis did not evaluate (outside the region) is not accepted on a node with AI data');
  assert.ok(!acc.some(a => a.m === 're'), 'teacher move at -1.5 is not accepted');
  assert.ok(!acc.some(a => a.m === 'se'), 'entry worse than -3 is ignored');
  assert.deepEqual(acc.find(a => a.m === 'pc').pv, ['C3', 'D4']);
});

test('top N and the teacher switch', () => {
  const q = QC.extractQuestions(col('toy', TOY)).find(x => x.node.p.B && x.node.p.B[0] === 'qc');
  assert.deepEqual(QC.acceptedOf(q, { ...ST, teacher: false }).map(a => a.m), ['pc', 'qe', 'rd']);
  assert.deepEqual(QC.acceptedOf(q, { ...ST, teacher: false, topN: 1 }).map(a => a.m), ['pc']);
  assert.deepEqual(QC.acceptedOf(q, { ...ST, topN: 2 }).map(a => a.m), ['pc', 'qe', 'rd']); // rd comes in as a teacher move
  assert.deepEqual(QC.acceptedOf(q, { ...ST, topN: 5, teacher: false }).map(a => a.m), ['pc', 'qe', 'rd', 're']); // se is below -3
  assert.deepEqual(QC.acceptedOf(q, { ...ST, topN: 99, teacher: false }).map(a => a.m), ['pc', 'qe', 'rd', 're']); // topN is clamped to 5
});

test('thresholds are inclusive: -3.0 for AI entries and -1.0 for teacher moves', () => {
  const q = {
    ai: QC.parseAN('aa:0.0:0.5:50:10:;bb:-3.0:0.1:50:10:;cc:-3.1:0.1:50:10:;dd:-1.0:0.1:50:10:;ee:-1.1:0.1:50:10:'),
    teacher: [{ m: 'dd', loss: -1.0 }, { m: 'ee', loss: -1.1 }]
  };
  // AI side: bb at exactly -3.0 is in, cc at -3.1 is out
  assert.deepEqual(QC.acceptedOf(q, { ...ST, topN: 5, teacher: false }).map(a => a.m), ['aa', 'dd', 'ee', 'bb']);
  // teacher side with top 1: dd at exactly -1.0 is in, ee at -1.1 is out
  assert.deepEqual(QC.acceptedOf(q, { ...ST, topN: 1 }).map(a => a.m), ['aa', 'dd']);
});

test('moves tied with the Nth loss are kept', () => {
  const q = { ai: QC.parseAN('aa:0.0:0.5:50:10:;bb:-0.1:0.3:50:10:;cc:-0.1:0.2:50:10:;dd:-0.1:0.1:50:10:;ee:-0.5:0.1:50:10:'), teacher: [] };
  assert.deepEqual(QC.acceptedOf(q, ST).map(a => a.m), ['aa', 'bb', 'cc', 'dd']);
  assert.deepEqual(QC.acceptedOf(q, { ...ST, topN: 2 }).map(a => a.m), ['aa', 'bb', 'cc', 'dd']);
  assert.deepEqual(QC.acceptedOf(q, { ...ST, topN: 1 }).map(a => a.m), ['aa']);
});

test('teacher moves without AI data are accepted, with data they need loss >= -1', () => {
  const q = { ai: [], teacher: [{ m: 'aa', loss: null }, { m: 'bb', loss: null }] };
  assert.equal(QC.acceptedOf(q, ST).length, 2);
  assert.equal(QC.acceptedOf(q, { ...ST, teacher: false }).length, 0);
  // a node without any AN: every teacher child is accepted (the toy root)
  const root = QC.extractQuestions(col('toy', TOY)).find(x => x.depth === 0);
  assert.deepEqual(QC.acceptedOf(root, ST).map(a => a.m).sort(), ['cp', 'qc']);
  assert.equal(root.hasAI, false);
});

test('judge returns the hit entry', () => {
  const q = QC.extractQuestions(col('toy', TOY)).find(x => x.node.p.B && x.node.p.B[0] === 'qc');
  assert.equal(QC.judge(q, ST, 'pc').ok, true);
  assert.deepEqual(QC.judge(q, ST, 'pc').hit.tags, ['ai', 'teacher']);
  assert.equal(QC.judge(q, ST, 're').ok, false);
  assert.equal(QC.judge(q, ST, 'zz').hit, null);
});

// ---------- ids ----------
test('hash53 is pinned so that stored progress keeps matching', () => {
  // values were computed once with this algorithm; a change here would orphan every stored record
  assert.equal(QC.hash53(''), 'wvjl67o803');
  assert.equal(QC.hash53('Bdp|Wfq'), '2bs13u9vd8z');
  assert.equal(QC.hash53('AB:dp,pd|Bqc'), '1n7vgypci6h');
  // the key of a position: setup lists sorted, then the moves
  const r = QC.parseSgf('(;SZ[19]AB[pd][dp];B[qc])');
  assert.equal(QC.posKey(r.c[0]), 'AB:dp,pd|Bqc');
});

test('question ids are stable across regenerated data and differ across positions and collections', () => {
  const a = QC.extractQuestions(col('c1', TOY)).map(q => q.id);
  const b = QC.extractQuestions(col('c1', TOY)).map(q => q.id);
  assert.deepEqual(a, b);
  assert.equal(new Set(a).size, a.length);
  // regenerated: other comments, other AN values, same moves
  const regen = TOY.replace(/C\[[^\]]*\]/g, 'C[new text]').replace(AN1, 'pc:0.0:0.9:50:100:C3;qe:-0.2:0.2:50:40:E5');
  assert.deepEqual(QC.extractQuestions(col('c1', regen)).map(q => q.id), a);
  // other collection id: same hash part, different prefix
  const other = QC.extractQuestions(col('c2', TOY)).map(q => q.id);
  assert.ok(a.every((id, i) => id.startsWith('c1#') && other[i] === 'c2#' + id.slice(3)));
  // other moves: another id
  const moved = QC.extractQuestions(col('c1', TOY.replace('B[qc]', 'B[qd]'))).map(q => q.id);
  assert.notDeepEqual(moved, a);
  // setup list order does not matter
  const reordered = QC.extractQuestions(col('c1', TOY.replace('AB[pd][dp]', 'AB[dp][pd]'))).map(q => q.id);
  assert.deepEqual(reordered, a);
});

// ---------- symmetries ----------
test('symmetry 0 is the identity', () => {
  ALL.forEach(p => assert.deepEqual(QC.symPoint(0, p), p));
});

test('every symmetry is a bijection of the board', () => {
  for (let t = 0; t < 8; t++) {
    const seen = new Set(ALL.map(p => QC.symPoint(t, p).join(',')));
    assert.equal(seen.size, 361, 'symmetry ' + t);
    ALL.forEach(p => { const q = QC.symPoint(t, p); assert.ok(q[0] >= 0 && q[0] < 19 && q[1] >= 0 && q[1] < 19); });
  }
});

test('the 8 symmetries are pairwise different', () => {
  for (let a = 0; a < 8; a++) for (let b = a + 1; b < 8; b++) {
    assert.ok(ALL.some(p => !eqP(QC.symPoint(a, p), QC.symPoint(b, p))), `${a} vs ${b}`);
  }
});

test('inverse round trip', () => {
  for (let t = 0; t < 8; t++) {
    const i = QC.symInverse(t);
    ALL.forEach(p => {
      assert.deepEqual(QC.symPoint(i, QC.symPoint(t, p)), p);
      assert.deepEqual(QC.symPoint(t, QC.symPoint(i, p)), p);
    });
  }
});

test('group closure: composing two symmetries is a symmetry', () => {
  for (let a = 0; a < 8; a++) for (let b = 0; b < 8; b++) {
    const c = QC.symCompose(a, b);
    assert.ok(c >= 0 && c < 8, `${a}o${b}`);
    ALL.forEach(p => assert.deepEqual(QC.symPoint(c, p), QC.symPoint(a, QC.symPoint(b, p))));
  }
});

test('corners and star points map to corners and star points', () => {
  const corner = { 1: [18, 0], 2: [18, 18], 3: [0, 18], 4: [18, 0], 5: [0, 18], 6: [0, 0], 7: [18, 18] }; // image of (0,0)
  Object.entries(corner).forEach(([t, want]) => assert.deepEqual(QC.symPoint(+t, [0, 0]), want, 'symmetry ' + t));
  const star = new Set(); [3, 9, 15].forEach(x => [3, 9, 15].forEach(y => star.add(x + ',' + y)));
  for (let t = 0; t < 8; t++) {
    star.forEach(s => assert.ok(star.has(QC.symPoint(t, s.split(',').map(Number)).join(',')), 'star under ' + t));
    [[0, 0], [18, 0], [0, 18], [18, 18]].forEach(c => { const r = QC.symPoint(t, c); assert.ok((r[0] === 0 || r[0] === 18) && (r[1] === 0 || r[1] === 18)); });
  }
});

test('labels on the transformed board', () => {
  // D4 is (3,15); expected label of the same stone after each transformation
  const want = ['D4', 'D16', 'Q16', 'Q4', 'Q4', 'D16', 'Q16', 'D4'];
  want.forEach((w, t) => assert.equal(QC.symLabel(t, 'D4'), w, 'symmetry ' + t));
  assert.equal(QC.symLabel(1, 'A19'), 'T19');
  assert.equal(QC.symLabel(4, 'J10'), 'L10');   // the letter I is skipped: J is column index 8, its mirror is index 10 = L (K is the centre)
  // every label survives a round trip and is a valid label
  for (let t = 0; t < 8; t++) ALL.forEach(p => {
    const lab = QC.gtp(p), tl = QC.symLabel(t, lab);
    assert.ok(QC.fromGtp(tl), tl);
    assert.equal(QC.symLabel(QC.symInverse(t), tl), lab);
    assert.deepEqual(QC.fromGtp(tl), QC.symPoint(t, p));
  });
});

test('sgf coordinates: passes stay, points map', () => {
  for (let t = 0; t < 8; t++) { assert.equal(QC.symSgf(t, ''), ''); assert.equal(QC.symSgf(t, 'tt'), 'tt'); }
  assert.equal(QC.symSgf(4, 'dp'), 'pp');   // mirror left-right: x 3 -> 15
  assert.equal(QC.symSgf(1, 'aa'), 'sa');
});

test('crop rectangle follows the board', () => {
  const r = { x0: 0, y0: 8, x1: 10, y1: 18 };
  assert.deepEqual(QC.symRect(0, r), r);
  assert.deepEqual(QC.symRect(4, r), { x0: 8, y0: 8, x1: 18, y1: 18 });
  assert.deepEqual(QC.symRect(1, r), { x0: 0, y0: 0, x1: 10, y1: 10 });
  for (let t = 0; t < 8; t++) { const o = QC.symRect(t, r); assert.equal(o.x1 - o.x0, 10); assert.equal(o.y1 - o.y0, 10); }
});

// build viewer-like nodes from viewPath output
const chain = ps => { let up = null; return ps.map(p => (up = { p, c: [], up })).pop(); };

test('viewPath: the transformed position equals the transformed original (captures included)', () => {
  const root = QC.parseSgf('(;SZ[19]AB[pd][dp]AW[dd][pp];W[aa];B[ba];W[ee];B[ab];W[qf];B[gg]PL[W])');
  let leaf = root; while (leaf.c.length) leaf = leaf.c[0];
  const base = QC.replay(leaf).b;
  assert.equal(base[0][0], 0, 'the white stone at aa was captured');
  for (let t = 0; t < 8; t++) {
    const tb = QC.replay(chain(QC.viewPath(leaf, t))).b;
    ALL.forEach(p => { const q = QC.symPoint(t, p); assert.equal(tb[q[0]][q[1]], base[p[0]][p[1]], `sym ${t} at ${p}`); });
    const last = chain(QC.viewPath(leaf, t));
    assert.equal(QC.sideToMove(last), 2, 'PL survives the transformation');
  }
});

test('accepted answers: transformed click maps back to the original move', () => {
  const q = QC.extractQuestions(col('toy', TOY)).find(x => x.node.p.B && x.node.p.B[0] === 'qc');
  const acc = QC.acceptedOf(q, ST);
  for (let t = 0; t < 8; t++) {
    const shown = acc.map(a => QC.symSgf(t, a.m));
    shown.forEach((s, i) => {
      const click = QC.pt(s), orig = QC.symPoint(QC.symInverse(t), click), mv = QC.sg(orig[0], orig[1]);
      assert.equal(mv, acc[i].m);
      assert.equal(QC.judge(q, ST, mv).ok, true);
    });
  }
});

test('randomSym respects the switch and covers the range', () => {
  assert.equal(QC.randomSym(Math.random, false), 0);
  const rng = QC.mulberry32(7), seen = new Set();
  for (let i = 0; i < 200; i++) seen.add(QC.randomSym(rng, true));
  assert.equal(seen.size, 8);
});

// ---------- scheduler ----------
test('Leitner boxes: intervals 0,1,2,4,7,15,30 and mastery after reaching the last box twice', () => {
  const P = QC.defaultProgress(), id = 'x#1';
  let now = ms(2026, 1, 1);
  const days = [];
  for (let i = 0; i < 7; i++) {
    const r = QC.grade(P, id, true, now);
    days.push(r.due - QC.dayIndex(now));
    if (i < 6) assert.equal(r.mst, 0, 'not mastered after answer ' + (i + 1));
    now += QC.DAY * Math.max(1, QC.INTERVALS[r.b]);
  }
  assert.deepEqual(days, [1, 2, 4, 7, 15, 30, 30]);   // box after answer 1..7 is 1,2,3,4,5,6,6
  assert.equal(P.q[id].b, QC.TOP_BOX);
  assert.equal(P.q[id].mst, 1, 'mastered on the second arrival in the last box');
  assert.equal(P.q[id].n, 7);
  assert.equal(P.q[id].ok, 7);
});

test('a wrong answer goes back to box 0 and resets the streak', () => {
  const P = QC.defaultProgress(), id = 'x#2';
  let now = ms(2026, 1, 1);
  for (let i = 0; i < 6; i++) { QC.grade(P, id, true, now); now += QC.DAY * 30; }
  assert.equal(P.q[id].b, 6);
  assert.equal(P.q[id].top, 1);
  const r = QC.grade(P, id, false, now);
  assert.equal(r.b, 0);
  assert.equal(r.top, 0);
  assert.equal(r.mst, 0);
  assert.equal(r.due, QC.dayIndex(now), 'due again today');
  assert.equal(QC.isRetry(r), true);
  // back up: two arrivals needed again
  for (let i = 0; i < 6; i++) { QC.grade(P, id, true, now); now += QC.DAY * 30; }
  assert.equal(P.q[id].mst, 0);
  QC.grade(P, id, true, now);
  assert.equal(P.q[id].mst, 1);
});

test('first answer counts as a new question for the day, repeats do not', () => {
  const P = QC.defaultProgress(), now = ms(2026, 3, 1);
  QC.grade(P, 'a#1', true, now); QC.grade(P, 'a#2', false, now); QC.grade(P, 'a#1', true, now + 1000);
  assert.equal(QC.newToday(P, now), 2);
  assert.equal(QC.newToday(P, now + QC.DAY), 0, 'next day starts again');
});

test('markMastered removes a question from training', () => {
  const P = QC.defaultProgress(), now = ms(2026, 3, 1);
  const qs = mkQs('c', 5);
  QC.markMastered(P, qs[0].id, now);
  const s = QC.buildSession(qs, P, ST, now);
  assert.deepEqual(s.list.map(q => q.id), qs.slice(1).map(q => q.id));
});

// ---------- session builder ----------
function mkQs(cid, n, extra) {
  return Array.from({ length: n }, (_, i) => Object.assign({
    id: `${cid}#${i}`, cid, ai: [], teacher: [{ m: 'aa', loss: null }, { m: 'bb', loss: null }], depth: i, bucket: 'mid', side: 1
  }, extra));
}

test('session: due reviews first, then new questions up to the daily limit', () => {
  const qs = mkQs('c', 50), P = QC.defaultProgress(), now = ms(2026, 2, 10);
  // three questions answered earlier and due today
  [['c#3', 2], ['c#7', 0], ['c#9', 1]].forEach(([id, b]) => { P.q[id] = { b, due: QC.dayIndex(now), last: now - 3 * QC.DAY, n: 1, ok: 1, top: 0, mst: 0 }; });
  const s = QC.buildSession(qs, P, ST, now);
  assert.equal(s.due, 3);
  assert.equal(s.fresh, 20);
  assert.equal(s.list.length, 23);
  assert.deepEqual(s.list.slice(0, 3).map(q => q.id), ['c#7', 'c#9', 'c#3'], 'lowest box first');
  assert.ok(s.list.slice(3).every(q => !P.q[q.id]));
});

test('session: the limit counts what was started today', () => {
  const qs = mkQs('c', 50), P = QC.defaultProgress(), now = ms(2026, 2, 10);
  P.day = { d: QC.dayIndex(now), n: 15 };
  assert.equal(QC.buildSession(qs, P, ST, now).fresh, 5);
  P.day.n = 20;
  assert.equal(QC.buildSession(qs, P, ST, now).fresh, 0);
  P.day = { d: QC.dayIndex(now) - 1, n: 20 };
  assert.equal(QC.buildSession(qs, P, ST, now).fresh, 20);
  assert.equal(QC.buildSession(qs, P, { ...ST, limit: 7 }, now).fresh, 7);
  assert.equal(QC.buildSession(qs, QC.defaultProgress(), ST, now, { dueOnly: true }).list.length, 0);
});

test('session: nothing answered in the last 10 minutes comes back, except the retry of a wrong answer', () => {
  const qs = mkQs('c', 4), P = QC.defaultProgress(), now = ms(2026, 2, 10, 12, 0), today = QC.dayIndex(now);
  P.q['c#0'] = { b: 2, due: today, last: now - 5 * 60000, n: 3, ok: 3, top: 0, mst: 0 };   // too recent
  P.q['c#1'] = { b: 2, due: today, last: now - 11 * 60000, n: 3, ok: 3, top: 0, mst: 0 };  // old enough
  P.q['c#2'] = { b: 0, due: today, last: now - 1 * 60000, n: 1, ok: 0, top: 0, mst: 0 };   // wrong a minute ago: retry allowed
  P.q['c#3'] = { b: 6, due: today, last: now - 40 * 60000, n: 9, ok: 9, top: 2, mst: 1 };  // mastered
  const s = QC.buildSession(qs, P, ST, now, { dueOnly: true });
  assert.deepEqual(s.list.map(q => q.id), ['c#2', 'c#1']);
  // not due yet
  P.q['c#1'].due = today + 1;
  assert.deepEqual(QC.buildSession(qs, P, ST, now, { dueOnly: true }).list.map(q => q.id), ['c#2']);
});

test('session: mixed mode interleaves collections, keeps the order inside each, and is reproducible with a seed', () => {
  const qs = [...mkQs('a', 10), ...mkQs('b', 10), ...mkQs('c', 10)], P = QC.defaultProgress(), now = ms(2026, 2, 10);
  const run = seed => QC.buildSession(qs, P, ST, now, { mix: true, rng: QC.mulberry32(seed) }).list.map(q => q.id);
  const one = run(1);
  assert.equal(one.length, 20);
  assert.equal(new Set(one.slice(0, 3).map(id => id[0])).size, 3, 'first round has all three collections');
  ['a', 'b', 'c'].forEach(c => { const mine = one.filter(id => id[0] === c).map(id => +id.split('#')[1]); assert.deepEqual(mine, mine.slice().sort((x, y) => x - y)); });
  assert.deepEqual(run(1), one);
  assert.notDeepEqual(run(2), one);
  // single collection mode keeps the tree order
  const plain = QC.buildSession(qs, P, ST, now).list.map(q => q.id);
  assert.deepEqual(plain.slice(0, 3), ['a#0', 'a#1', 'a#2']);
});

test('session: settings decide which questions are usable', () => {
  const qs = mkQs('c', 3);
  assert.equal(QC.buildSession(qs, QC.defaultProgress(), ST, ms(2026, 2, 10)).list.length, 3);
  assert.equal(QC.buildSession(qs, QC.defaultProgress(), { ...ST, teacher: false }, ms(2026, 2, 10)).list.length, 0, 'teacher only questions have no accepted move without teacher moves');
});

test('stats per card', () => {
  const qs = mkQs('c', 4), P = QC.defaultProgress(), now = ms(2026, 2, 10), today = QC.dayIndex(now);
  P.q['c#0'] = { b: 3, due: today + 4, last: now - QC.DAY, n: 4, ok: 3, top: 0, mst: 0 };
  P.q['c#1'] = { b: 6, due: today + 30, last: now - QC.DAY, n: 8, ok: 8, top: 2, mst: 1 };
  P.q['c#2'] = { b: 1, due: today, last: now - QC.DAY, n: 2, ok: 1, top: 0, mst: 0 };
  const s = QC.statsOf(qs, P, ST, now);
  assert.deepEqual(s, { total: 4, trained: 3, acc: 12 / 14, mastered: 1, due: 1, fresh: 1 });
});

// ---------- follow-up questions ----------
test('follow-up: best reply, then the next question of the same side', () => {
  // W question at the root; after W[aa] black replies (AN prefers bb), then W is asked again
  const sgf = '(;SZ[19]C[t]PL[W](;W[aa]AN[cc:-0.8:0.1:50:10:;bb:0.0:0.5:50:10:](;B[cc]C[r1](;W[dd]C[x])(;W[ee]C[y]))(;B[bb]C[r2](;W[ff]C[x2])(;W[gg]C[y2])))(;W[hh]))';
  const qs = QC.extractQuestions(col('fu', sgf));
  const root = qs.find(q => q.depth === 0); // the parsed root hangs below a dummy node, so test the depth
  const f = QC.followUp(root, 'aa', qs, ST);
  assert.ok(f, 'follow-up exists');
  assert.equal(f.node.p.B[0], 'bb', 'the reply with the better AI loss is followed');
  assert.equal(f.side, root.side);
  assert.equal(QC.followUp(root, 'hh', qs, ST), null, 'no continuation after hh');
  assert.equal(QC.followUp(root, 'zz', qs, ST), null, 'move that is not a teacher move');
});

// ---------- export and import ----------
function sampleProgress() {
  const P = QC.defaultProgress();
  P.st = { topN: 2, teacher: false, transform: false, limit: 5, extra: false };
  P.q['a#1'] = { b: 3, due: 20500, last: ms(2026, 1, 5), n: 4, ok: 3, top: 0, mst: 0 };
  P.q['b#2'] = { b: 6, due: 20600, last: ms(2026, 1, 6), n: 9, ok: 9, top: 2, mst: 1 };
  P.day = { d: 20500, n: 3 };
  return P;
}

test('export and import round trip', () => {
  const P = sampleProgress(), text = QC.exportProgress(P, ms(2026, 1, 7));
  assert.equal(JSON.parse(text).app, 'josekiapp-quiz');
  const r = QC.importProgress(text, null, 'replace');
  assert.equal(r.ok, true);
  assert.deepEqual(r.P, P);
  const r2 = QC.importProgress(text, QC.defaultProgress());
  assert.deepEqual(r2.P, P);
});

test('import merge keeps the newer record per question', () => {
  const file = sampleProgress(), mine = sampleProgress();
  mine.q['a#1'] = { b: 1, due: 1, last: ms(2026, 1, 9), n: 5, ok: 3, top: 0, mst: 0 };     // newer than the file
  mine.q['b#2'] = { b: 0, due: 1, last: ms(2026, 1, 1), n: 1, ok: 0, top: 0, mst: 0 };     // older than the file
  mine.q['c#3'] = { b: 2, due: 7, last: ms(2026, 1, 2), n: 1, ok: 1, top: 0, mst: 0 };     // only here
  const r = QC.importProgress(QC.exportProgress(file), mine);
  assert.equal(r.P.q['a#1'].n, 5);
  assert.equal(r.P.q['b#2'].mst, 1);
  assert.ok(r.P.q['c#3']);
});

test('import rejects bad files and cleans odd values', () => {
  assert.equal(QC.importProgress('not json').ok, false);
  assert.equal(QC.importProgress('{"app":"other","v":1,"data":{}}').ok, false);
  assert.equal(QC.importProgress('{"app":"josekiapp-quiz","v":2,"data":{}}').ok, false);
  const dirty = '{"app":"josekiapp-quiz","v":1,"data":{"st":{"topN":99,"limit":-4,"teacher":0},"q":{"x#1":{"b":99,"due":-5,"last":"abc","n":-3,"ok":50,"top":1,"mst":1},"__proto__":{"b":1},"y#1":5}}}';
  const r = QC.importProgress(dirty, null, 'replace');
  assert.equal(r.ok, true);
  assert.equal(r.P.st.topN, 5);
  assert.equal(r.P.st.limit, 1);
  assert.equal(r.P.st.teacher, false);
  assert.deepEqual(r.P.q['x#1'], { b: 6, due: 0, last: 0, n: 0, ok: 0, top: 1, mst: 1 });
  assert.deepEqual(Object.keys(r.P.q), ['x#1']);
  assert.equal(Object.getPrototypeOf(r.P.q), Object.prototype);
});

// ---------- real data smoke test (skipped when the library is not mounted) ----------
test('real library: invariants of all extracted questions', t => {
  const file = path.join(__dirname, '..', 'data', 'library.js');
  if (!fs.existsSync(file)) return t.skip('data/library.js not found');
  const win = {};
  new Function('window', fs.readFileSync(file, 'utf8'))(win);
  const ids = new Set();
  let total = 0;
  win.LIB.forEach(c => {
    QC.extractQuestions(c).forEach(q => {
      total++;
      assert.ok(!ids.has(q.id), 'duplicate id ' + q.id); ids.add(q.id);
      assert.ok(q.side === 1 || q.side === 2);
      const board = QC.replay(q.node).b, acc = QC.acceptedOf(q, ST);
      assert.ok(acc.length >= 1, 'no accepted move in ' + q.id);
      acc.forEach(a => { const p = QC.pt(a.m); assert.equal(board[p[0]][p[1]], 0, 'accepted move on a stone in ' + q.id); });
      const best = q.ai.filter(e => e.loss > -0.05);
      best.forEach(e => assert.ok(acc.some(a => a.m === e.m), 'AI best missing in ' + q.id));
    });
  });
  assert.ok(total > 0);
});
