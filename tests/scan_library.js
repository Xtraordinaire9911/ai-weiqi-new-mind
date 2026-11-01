// Data scan: runs the question extraction over a real library.js and prints per collection numbers.
// Usage: node tests/scan_library.js [path/to/library.js]   (the file is only read)
'use strict';
const fs = require('fs'), path = require('path');
const QC = require('../quiz_core.js');

const file = process.argv[2] || path.join(__dirname, '..', 'data', 'library.js');
const sandbox = { window: {} };
new Function('window', fs.readFileSync(file, 'utf8'))(sandbox.window);
const LIB = sandbox.window.LIB;

const rows = [], tot = { sideFromKids: 0, cols: LIB.length, withQ: 0, q: 0, empty: 0, single: 0, ai: 0, teacherOnly: 0, open: 0, mid: 0, deep: 0, acc: 0, ids: 0, dup: 0 };
const allIds = new Set();
LIB.forEach(col => {
  const qs = QC.extractQuestions(col), r = { name: col.name, q: qs.length, empty: 0, single: 0, ai: 0, teacherOnly: 0, open: 0, mid: 0, deep: 0, acc: 0 };
  qs.forEach(q => {
    const a = QC.acceptedOf(q, QC.DEFAULT_ST).length;
    if (a === 0) r.empty++;
    if (a === 1) r.single++;
    if (q.hasAI) r.ai++; else r.teacherOnly++;
    r[q.bucket]++; r.acc += a;
    if (QC.sideToMove(q.node) !== q.side) tot.sideFromKids++;
    if (allIds.has(q.id)) tot.dup++;
    allIds.add(q.id);
  });
  if (qs.length) { tot.withQ++; rows.push(r); }
  ['q', 'empty', 'single', 'ai', 'teacherOnly', 'open', 'mid', 'deep', 'acc'].forEach(k => { tot[k] += r[k]; });
});

const pad = (s, n) => String(s).padEnd(n);
console.log(`library: ${file}  (LIBT ${sandbox.window.LIBT || '?'})`);
console.log(pad('collection', 34) + ['q', 'empty', 'single', 'withAI', 'teachOnly', 'open', 'mid', 'deep', 'avgAcc'].map(h => pad(h, 10)).join(''));
rows.forEach(r => console.log(pad(r.name, 34) + [r.q, r.empty, r.single, r.ai, r.teacherOnly, r.open, r.mid, r.deep, (r.acc / r.q).toFixed(2)].map(v => pad(v, 10)).join('')));
console.log(`collections ${tot.cols}, with questions ${tot.withQ}`);
console.log(`TOTAL questions ${tot.q}, empty accepted ${tot.empty}, single accepted ${tot.single}, with AI data ${tot.ai}, teacher only ${tot.teacherOnly}`);
console.log(`side to move taken from the teacher moves instead of the last move: ${tot.sideFromKids}`);
console.log(`depth buckets open ${tot.open}, mid ${tot.mid}, deep ${tot.deep}; duplicate ids ${tot.dup}`);

// loss histogram of the AI entries that are accepted, and of the teacher moves the thresholds drop
const hist = {}, dropped = { teacherWorse: 0, teacherKept: 0, teacherNoAI: 0, outOfRegion: 0, aiTop: 0 };
LIB.forEach(col => QC.extractQuestions(col).forEach(q => {
  q.teacher.forEach(t => { if (t.out) dropped.outOfRegion++; else if (t.loss == null) dropped.teacherNoAI++; else if (t.loss >= QC.TEACHER_MIN) dropped.teacherKept++; else dropped.teacherWorse++; });
  QC.acceptedOf(q, QC.DEFAULT_ST).forEach(a => { if (a.tags.includes('ai')) { dropped.aiTop++; const b = a.loss > -0.05 ? '0 (best)' : a.loss > -0.5 ? '-0.1..-0.5' : a.loss > -1 ? '-0.6..-1.0' : a.loss > -2 ? '-1.1..-2.0' : '-2.1..-3.0'; hist[b] = (hist[b] || 0) + 1; } });
}));
console.log('accepted AI moves by loss:', JSON.stringify(hist));
console.log('teacher moves:', JSON.stringify(dropped));

// depth quantiles, used to pick the bucket limits (open <= 4, mid <= 10)
const depths = [];
LIB.forEach(col => QC.extractQuestions(col).forEach(q => depths.push(q.depth)));
depths.sort((a, b) => a - b);
const at = p => depths[Math.min(depths.length - 1, Math.floor(depths.length * p))];
console.log(`depth quantiles: min ${depths[0]}, p25 ${at(.25)}, p33 ${at(.33)}, median ${at(.5)}, p66 ${at(.66)}, p75 ${at(.75)}, max ${depths[depths.length - 1]}`);
