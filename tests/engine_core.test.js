'use strict';
// Tests of the pure logic in engine_core.js. Run: node --test tests/   (see docs/ENGINE-SETUP.md; in Docker: node:20-alpine)
const test = require('node:test');
const assert = require('node:assert/strict');
const C = require('../engine_core.js');

// ---------------------------------------------------------------- NDJSON with partial chunks
test('NDJSON: whole lines, several lines in one chunk', () => {
  const p = C.createLineParser();
  const r = p.push('{"a":1}\n{"b":2}\n');
  assert.deepEqual(r.msgs, [{ a: 1 }, { b: 2 }]);
  assert.equal(r.errors.length, 0);
});

test('NDJSON: a line cut in the middle of a chunk waits for the rest', () => {
  const p = C.createLineParser();
  assert.deepEqual(p.push('{"moveInfos":[{"move":"Q').msgs, []);
  assert.deepEqual(p.push('3"}],"isDuringS').msgs, []);
  const r = p.push('earch":true}\n{"done":true}\n');
  assert.deepEqual(r.msgs, [{ moveInfos: [{ move: 'Q3' }], isDuringSearch: true }, { done: true }]);
});

test('NDJSON: any split point of a multi-line stream gives the same messages', () => {
  const full = '{"n":1}\r\n\r\n{"n":2,"t":"中文"}\n{"n":3}\n';
  for (let cut = 0; cut <= full.length; cut++) {
    const p = C.createLineParser(), got = [];
    got.push(...p.push(full.slice(0, cut)).msgs, ...p.push(full.slice(cut)).msgs, ...p.end().msgs);
    assert.deepEqual(got.map(m => m.n), [1, 2, 3], 'cut at ' + cut);
  }
});

test('NDJSON: a last line without newline is flushed by end()', () => {
  const p = C.createLineParser();
  assert.deepEqual(p.push('{"x":1}').msgs, []);
  assert.deepEqual(p.end().msgs, [{ x: 1 }]);
  assert.deepEqual(p.end().msgs, []);
});

test('NDJSON: a broken line is reported, the next ones still parse', () => {
  const p = C.createLineParser();
  const r = p.push('{"a":1}\nnot json\n{"b":2}\n');
  assert.deepEqual(r.msgs, [{ a: 1 }, { b: 2 }]);
  assert.equal(r.errors.length, 1);
  assert.match(r.errors[0].line, /not json/);
});

test('NDJSON: a line longer than the limit is dropped, not buffered forever', () => {
  const p = C.createLineParser(100);
  const r = p.push('x'.repeat(500));
  assert.equal(r.errors.length, 1);
  assert.deepEqual(p.push('{"ok":1}\n').msgs, [{ ok: 1 }]);
});

// ---------------------------------------------------------------- state machine
const run = (s, ...evs) => evs.reduce((a, e) => { const r = C.reduce(a.state, e); return { state: r.state, fx: a.fx.concat(r.fx) }; }, { state: s, fx: [] });
const fxt = r => r.fx.map(f => f.t);

test('machine: start opens a job, the first update means running', () => {
  let r = run(C.initial(), { t: 'start' });
  assert.equal(r.state.phase, 'connecting');
  assert.deepEqual(r.fx, [{ t: 'open', job: 1 }]);
  r = run(r.state, { t: 'update', job: 1, visits: 40 });
  assert.equal(r.state.phase, 'running');
  assert.equal(r.state.visits, 40);
});

test('machine: start while connecting or running is ignored (a double click opens one search)', () => {
  const a = run(C.initial(), { t: 'start' }, { t: 'start' }, { t: 'update', job: 1, visits: 1 }, { t: 'start' });
  assert.deepEqual(fxt(a), ['open']);
  assert.equal(a.state.job, 1);
});

test('machine: pause terminates, the final answer turns it into paused, resume opens a new job', () => {
  let r = run(C.initial(), { t: 'start' }, { t: 'update', job: 1, visits: 300 }, { t: 'pause' });
  assert.equal(r.state.phase, 'stopping');
  assert.deepEqual(r.fx.slice(1), [{ t: 'terminate', job: 1 }]);
  r = run(r.state, { t: 'update', job: 1, visits: 320 }, { t: 'done', job: 1, end: 'terminated' });
  assert.equal(r.state.phase, 'paused');
  assert.equal(r.state.visits, 320, 'the partial result that arrives while stopping is kept');
  r = run(r.state, { t: 'resume' });
  assert.equal(r.state.phase, 'connecting');
  assert.equal(r.state.job, 2);
  assert.deepEqual(r.fx, [{ t: 'open', job: 2 }]);
  assert.equal(r.state.visits, 320, 'resume keeps showing the old count until the new search reports');
});

test('machine: resume only works from paused; start from paused restarts from zero', () => {
  assert.deepEqual(run(C.initial(), { t: 'resume' }).fx, []);
  const p = run(C.initial(), { t: 'start' }, { t: 'update', job: 1, visits: 50 }, { t: 'pause' }, { t: 'done', job: 1, end: 'terminated' }).state;
  const r = run(p, { t: 'start' });
  assert.equal(r.state.visits, 0);
  assert.equal(r.state.job, 2);
});

test('machine: stop while running terminates, aborts, clears, and ignores late answers', () => {
  let r = run(C.initial(), { t: 'start' }, { t: 'update', job: 1, visits: 10 }, { t: 'stop' });
  assert.equal(r.state.phase, 'idle');
  assert.equal(r.state.job, 2);
  assert.deepEqual(fxt(r), ['open', 'terminate', 'abort', 'clear']);
  const late = run(r.state, { t: 'update', job: 1, visits: 999 }, { t: 'done', job: 1, end: 'terminated' });
  assert.equal(late.state.phase, 'idle');
  assert.equal(late.state.visits, 0);
});

test('machine: stop when paused or done only clears', () => {
  const p = run(C.initial(), { t: 'start' }, { t: 'update', job: 1, visits: 5 }, { t: 'pause' }, { t: 'done', job: 1, end: 'terminated' }).state;
  assert.deepEqual(fxt(run(p, { t: 'stop' })), ['clear']);
  const d = run(C.initial(), { t: 'start' }, { t: 'update', job: 1, visits: 5 }, { t: 'done', job: 1, end: 'finished' }).state;
  assert.equal(d.phase, 'done');
  assert.deepEqual(fxt(run(d, { t: 'stop' })), ['clear']);
});

test('machine: finished and timeout end as done, preempted or switch end as idle with a note', () => {
  const base = run(C.initial(), { t: 'start' }, { t: 'update', job: 1, visits: 5 }).state;
  assert.equal(run(base, { t: 'done', job: 1, end: 'finished' }).state.phase, 'done');
  const t = run(base, { t: 'done', job: 1, end: 'timeout' }).state;
  assert.equal(t.phase, 'done');
  assert.match(t.note, /时间上限/);
  const p = run(base, { t: 'done', job: 1, end: 'preempted' }).state;
  assert.equal(p.phase, 'idle');
  assert.match(p.note, /取代/);
  assert.match(run(base, { t: 'done', job: 1, end: 'switch' }).state.note, /切换网络/);
});

test('machine: a stream that closes without a final line is an error, but not while we are stopping it', () => {
  const base = run(C.initial(), { t: 'start' }, { t: 'update', job: 1, visits: 5 }).state;
  const e = run(base, { t: 'closed', job: 1 }).state;
  assert.equal(e.phase, 'error');
  assert.equal(e.err.code, 'closed');
  const s = run(base, { t: 'pause' }, { t: 'closed', job: 1 }).state;
  assert.equal(s.phase, 'paused');
});

test('machine: fail aborts and shows the error; fail while stopping means stopped', () => {
  const base = run(C.initial(), { t: 'start' }).state;
  const r = run(base, { t: 'fail', job: 1, err: { code: 'token', text: 'x', fix: 'y' } });
  assert.equal(r.state.phase, 'error');
  assert.deepEqual(r.fx, [{ t: 'abort', job: 1 }]);
  assert.equal(r.state.err.code, 'token');
  const s = run(base, { t: 'update', job: 1, visits: 1 }, { t: 'pause' }, { t: 'fail', job: 1, err: { code: 'network' } }).state;
  assert.equal(s.phase, 'paused');
  assert.equal(s.err, null);
  assert.equal(run(r.state, { t: 'start' }).state.err, null, 'a new start clears the error');
});

test('machine: stale events (older job number) change nothing', () => {
  const a = run(C.initial(), { t: 'start' }, { t: 'stop' }, { t: 'start' }).state;
  assert.equal(a.job, 3);
  for (const ev of [{ t: 'update', job: 1, visits: 7 }, { t: 'done', job: 1, end: 'finished' }, { t: 'fail', job: 1, err: {} }, { t: 'closed', job: 2 }]) {
    assert.deepEqual(run(a, ev).state, a, JSON.stringify(ev));
  }
});

test('machine: navigation while running cancels at once (terminate + abort), the old answers are ignored', () => {
  const r = run(C.initial(), { t: 'start' }, { t: 'update', job: 1, visits: 80 }, { t: 'navigate' });
  assert.equal(r.state.phase, 'idle');
  assert.deepEqual(fxt(r), ['open', 'terminate', 'abort', 'cancelFollow']);
  assert.equal(run(r.state, { t: 'update', job: 1, visits: 99 }).state.phase, 'idle');
});

test('machine: navigation while idle, paused or done sends nothing to the bridge', () => {
  for (const s of [C.initial(),
    run(C.initial(), { t: 'start' }, { t: 'update', job: 1, visits: 1 }, { t: 'pause' }, { t: 'done', job: 1, end: 'terminated' }).state,
    run(C.initial(), { t: 'start' }, { t: 'update', job: 1, visits: 1 }, { t: 'done', job: 1, end: 'finished' }).state]) {
    const r = run(s, { t: 'navigate' });
    assert.deepEqual(fxt(r), ['cancelFollow']);
    assert.equal(r.state.phase, 'idle');
  }
});

test('machine: random walk of events never leaves two streams open, nor one open while idle, paused, done or in error', () => {
  let seed = 12345;
  const rnd = n => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) % n;
  for (let round = 0; round < 300; round++) {
    let s = C.initial();
    const inflight = new Set();
    for (let i = 0; i < 60; i++) {
      const evs = [{ t: 'start' }, { t: 'pause' }, { t: 'resume' }, { t: 'stop' }, { t: 'navigate' },
        { t: 'update', job: s.job, visits: i }, { t: 'done', job: s.job, end: 'finished' }, { t: 'done', job: s.job, end: 'terminated' }, { t: 'closed', job: s.job }, { t: 'fail', job: s.job, err: {} },
        { t: 'update', job: s.job - 1, visits: i }, { t: 'done', job: s.job - 1, end: 'finished' }];
      const ev = evs[rnd(evs.length)], prev = s, r = C.reduce(s, ev);
      s = r.state;
      r.fx.forEach(f => { if (f.t === 'open') inflight.add(f.job); if (f.t === 'abort') inflight.delete(f.job); });
      // a stream also ends by itself when its own final line, close or failure is accepted
      if (['done', 'closed', 'fail'].includes(ev.t) && ev.job === prev.job && ['connecting', 'running', 'stopping'].includes(prev.phase)) inflight.delete(prev.job);
      assert.ok(inflight.size <= 1, 'two streams open after ' + JSON.stringify(ev));
      if (['idle', 'paused', 'done', 'error'].includes(s.phase)) assert.equal(inflight.size, 0, 'a stream is still open in phase ' + s.phase + ' after ' + JSON.stringify(ev));
    }
  }
});

test('buttons: which buttons work in which phase', () => {
  const b = (p, r, ok) => C.buttons(p, r, ok);
  assert.deepEqual(b('idle', false, true), { start: true, pause: false, resume: false, stop: false });
  assert.deepEqual(b('idle', false, false), { start: false, pause: false, resume: false, stop: false });
  assert.deepEqual(b('running', true, true), { start: false, pause: true, resume: false, stop: true });
  assert.deepEqual(b('connecting', false, true), { start: false, pause: true, resume: false, stop: true });
  assert.deepEqual(b('stopping', true, true), { start: false, pause: false, resume: false, stop: true });
  assert.deepEqual(b('paused', true, true), { start: false, pause: false, resume: true, stop: true });
  assert.deepEqual(b('done', true, true), { start: true, pause: false, resume: false, stop: true });
  assert.equal(b('error', false, true).start, true);
});

// ---------------------------------------------------------------- debounce + navigation
function fakeTimers() {
  let now = 0, id = 0; const q = new Map();
  return {
    set: (fn, ms) => { q.set(++id, { fn, at: now + ms }); return id; },
    clear: h => q.delete(h),
    advance(ms) { now += ms; [...q.entries()].filter(([, t]) => t.at <= now).sort((a, b) => a[1].at - b[1].at).forEach(([h, t]) => { q.delete(h); t.fn(); }); },
    size: () => q.size
  };
}

test('debounce: rapid calls run the last one once, after the quiet time', () => {
  const T = fakeTimers(), d = C.createDebouncer(300, T), hits = [];
  d.call(() => hits.push('a')); T.advance(100);
  d.call(() => hits.push('b')); T.advance(100);
  d.call(() => hits.push('c'));
  assert.ok(d.pending());
  T.advance(299); assert.deepEqual(hits, []);
  T.advance(1); assert.deepEqual(hits, ['c']);
  assert.ok(!d.pending());
});

test('debounce: cancel drops the pending call', () => {
  const T = fakeTimers(), d = C.createDebouncer(300, T), hits = [];
  d.call(() => hits.push('x')); d.cancel(); T.advance(1000);
  assert.deepEqual(hits, []);
  assert.equal(T.size(), 0);
});

test('navigation: quick navigation cancels the running search every time and a follow-up start fires only once, after the pause', () => {
  const T = fakeTimers(), follow = C.createDebouncer(300, T), sent = { terminate: 0, open: 0 };
  let s = C.initial();
  const send = ev => { const r = C.reduce(s, ev); s = r.state; r.fx.forEach(f => { if (f.t === 'terminate') sent.terminate++; if (f.t === 'open') sent.open++; if (f.t === 'cancelFollow') follow.cancel(); }); };
  send({ t: 'start' }); send({ t: 'update', job: s.job, visits: 10 });
  // the user plays a move from the table (a follow-up start is scheduled), then taps the arrow keys quickly
  send({ t: 'navigate' }); follow.call(() => send({ t: 'start' }));
  T.advance(100); send({ t: 'navigate' });                          // another navigation inside the pause: the scheduled start is cancelled
  assert.equal(follow.pending(), false);
  follow.call(() => send({ t: 'start' })); T.advance(100);
  follow.call(() => send({ t: 'start' })); T.advance(300);          // the last one runs once
  assert.equal(sent.open, 2, 'the first search plus exactly one follow-up');
  assert.equal(sent.terminate, 1, 'the first search was terminated by the first navigation, nothing was left running');
  assert.equal(s.phase, 'connecting');
});

// ---------------------------------------------------------------- caps
test('caps: numbers pass, "until stopped" means the bridge ceiling, over-limit is lowered with a note', () => {
  const lim = { streamMaxVisits: 20000, streamMaxSeconds: 900 };
  assert.deepEqual(C.effectiveCap(200, lim), { visits: 200, capped: false, note: '' });
  assert.equal(C.effectiveCap('1000', lim).visits, 1000);
  const u = C.effectiveCap('max', lim);
  assert.equal(u.visits, 20000); assert.ok(u.capped); assert.match(u.note, /20000/); assert.match(u.note, /900/);
  const o = C.effectiveCap(5000, { streamMaxVisits: 2000 });
  assert.equal(o.visits, 2000); assert.ok(o.capped); assert.match(o.note, /2000/);
  assert.equal(C.effectiveCap('max', null).visits, 20000, 'no limits known: a safe default ceiling');
  assert.equal(C.effectiveCap('abc', lim).visits, 200, 'garbage falls back to the smallest option');
  assert.deepEqual(C.CAPS.map(c => c.v), [200, 1000, 5000, 'max']);
});

// ---------------------------------------------------------------- endpoint
test('endpoint: accepts http(s), keeps a path prefix, drops trailing slashes', () => {
  assert.deepEqual(C.validateEndpoint(' http://127.0.0.1:8787/ '), { ok: true, base: 'http://127.0.0.1:8787', host: '127.0.0.1:8787', hostname: '127.0.0.1', protocol: 'http:', loopback: true });
  const p = C.validateEndpoint('https://u123-8787.example.org/proxy/8787//');
  assert.equal(p.base, 'https://u123-8787.example.org/proxy/8787'); assert.equal(p.loopback, false);
});

test('endpoint: refuses anything that could carry the token in the address or send it somewhere odd', () => {
  const bad = { '': 'empty', 'not a url': 'syntax', 'ftp://x.example/': 'scheme', 'javascript:alert(1)': 'scheme', 'file:///etc/passwd': 'scheme',
    'http://user:pw@example.org': 'creds', 'http://127.0.0.1:8787/?token=abc': 'query', 'https://x.example/#tok': 'query' };
  for (const [s, code] of Object.entries(bad)) { const r = C.validateEndpoint(s); assert.equal(r.ok, false, s); assert.equal(r.code, code, s); }
});

test('endpoint: loopback detection', () => {
  for (const h of ['localhost', '127.0.0.1', '127.5.5.5', '[::1]', '::1', 'app.localhost']) assert.ok(C.isLoopback(h), h);
  for (const h of ['example.org', '192.168.1.5', '10.0.0.2', '127.0.0.1.evil.example']) assert.ok(!C.isLoopback(h), h);
  assert.ok(C.knownPath('/stream') && !C.knownPath('/etc/passwd') && !C.knownPath('/stream?x=1'));
});

// ---------------------------------------------------------------- error mapping
test('errors: https page + plain http remote address is named as mixed content, with the fix', () => {
  const r = C.mapError({ kind: 'network', endpoint: C.validateEndpoint('http://203.0.113.5:8787'), page: { protocol: 'https:', origin: 'https://josekis.example' } });
  assert.equal(r.code, 'mixed'); assert.match(r.text, /https/); assert.match(r.fix, /SSH/);
});

test('errors: an https page may call http://127.0.0.1 (browsers allow loopback), so that is not called mixed content', () => {
  const r = C.mapError({ kind: 'network', endpoint: C.validateEndpoint('http://127.0.0.1:8787'), page: { protocol: 'https:', origin: 'https://josekis.example' } });
  assert.equal(r.code, 'network');
  assert.match(r.fix, /--allow-origin https:\/\/josekis\.example/);
});

test('errors: a page opened from file:// is told to use --allow-file-origin', () => {
  const r = C.mapError({ kind: 'network', endpoint: C.validateEndpoint('http://127.0.0.1:8787'), page: { protocol: 'file:', origin: 'null' } });
  assert.equal(r.code, 'file-origin'); assert.match(r.fix, /--allow-file-origin/);
});

test('errors: http statuses map to a short reason and a one line fix', () => {
  const m = (status, extra) => C.mapError(Object.assign({ kind: 'http', status, page: { protocol: 'http:', origin: 'http://localhost:8765' } }, extra));
  assert.equal(m(401).code, 'token');
  assert.match(m(403).fix, /--allow-origin http:\/\/localhost:8765/);
  assert.equal(m(404).code, 'notfound');
  assert.equal(m(409).code, 'busy');
  assert.equal(m(429).code, 'busy');
  assert.match(m(503, { state: 'switching' }).text, /加载网络/);
  assert.equal(m(504).code, 'timeout');
  assert.equal(m(502, { message: 'KataGo process exited' }).code, 'engine');
  assert.match(m(400, { message: 'maxVisits must be in 1..20000' }).text, /maxVisits/);
  assert.match(m(418).text, /418/);
});

test('errors: every kind has Chinese text and (except abort) a fix; netError keeps the info and the exact "已取消"', () => {
  for (const kind of ['network', 'http', 'timeout', 'protocol', 'endpoint', 'perspective', 'old']) {
    const r = C.mapError({ kind, status: 500, page: {} });
    assert.match(r.text, /[一-鿿]/, kind);
    assert.ok(r.fix || kind === 'http', kind);
  }
  assert.equal(C.mapError({ kind: 'abort' }).fix, '');
  const e = C.netError({ kind: 'abort' });
  assert.equal(e.message, '已取消');
  const f = C.netError({ kind: 'http', status: 401 });
  assert.equal(f.code, 'token'); assert.match(f.message, /token 不对 → /); assert.equal(f.info.status, 401);
});

// ---------------------------------------------------------------- candidate string + coordinates
test('coordinates: GTP and SGF round trip over the whole board, "I" is skipped', () => {
  for (let x = 0; x < 19; x++) for (let y = 0; y < 19; y++) {
    const g = 'ABCDEFGHJKLMNOPQRST'[x] + (19 - y), s = C.gtpToSgf(g);
    assert.equal(s, String.fromCharCode(97 + x, 97 + y)); assert.equal(C.sgfToGtp(s), g); assert.deepEqual(C.gtpToXY(g), [x, y]);
  }
  assert.equal(C.gtpToXY('I5'), null); assert.equal(C.gtpToXY('A20'), null); assert.equal(C.gtpToSgf('pass'), '');
});

test('parseAN: reads the viewer candidate string, best first, forced moves flagged, bad pv entries dropped, win rate ignored', () => {
  const an = 'dq:-0.5:0.20:50:50:D3 D17;pq:0.0:0.30:55:100:Q3 D17 pass <b>;dc:-2.3:-1.00:30:100:D17';
  const rows = C.parseAN(an);
  assert.deepEqual(rows.map(r => r.move), ['Q3', 'D3', 'D17']);
  assert.deepEqual(rows[0], { move: 'Q3', loss: 0, prior: 0.3, visits: 100, forced: false, pv: ['Q3', 'D17', 'pass'] });
  assert.equal(rows[2].forced, true);
  assert.ok(!('wr' in rows[0]) && !('winrate' in rows[0]), 'no whole-board win rate is exposed');
  assert.deepEqual(C.parseAN(''), []);
  assert.deepEqual(C.parseAN('zz;:::'), []);
  assert.equal(C.fmtLoss(0), '最优'); assert.equal(C.fmtLoss(-0.04), '最优'); assert.equal(C.fmtLoss(-1.26), '-1.3');
  assert.equal(C.fmtN(1234567), '1,234,567'); assert.equal(C.fmtN(950), '950');
});

// ---------------------------------------------------------------- SGF for "adopt this line"
test('sgf: position, moves so far, then the AI line as the continuation (colors alternate from the side to move)', () => {
  const q = { initialStones: [['B', 'D4'], ['W', 'Q16']], moves: [['B', 'C3']], komi: 6.5, rules: 'japanese' };
  assert.equal(C.sgfSnippet(q, 'W', ['D17', 'R4'], 'note'),
    '(;GM[1]FF[4]CA[UTF-8]SZ[19]KM[6.5]RU[Japanese]AB[dp]AW[pd]C[note];B[cq];W[dc]C[以下为 KataGo 推演的最佳线,不是老师的讲解];B[qp])');
});

test('sgf: no moves yet writes PL, a pass is an empty point, ] and \\ in the note are escaped', () => {
  const q = { initialStones: [['B', 'D4']], moves: [], initialPlayer: 'W', komi: 0.5, rules: 'chinese' };
  const s = C.sgfSnippet(q, 'W', ['pass', 'Q16'], 'a]b\\c');
  assert.match(s, /RU\[Chinese\]/); assert.match(s, /KM\[0\.5\]/); assert.match(s, /PL\[W\]/);
  assert.match(s, /C\[a\\\]b\\\\c\]/);
  assert.match(s, /;W\[\]C\[/); assert.match(s, /;B\[pd\]\)$/);
  assert.ok(s.startsWith('(') && s.endsWith(')'));
});

test('debounce: the default timers need no injection and are not called as methods of another object', async () => {
  const d = C.createDebouncer(10), hits = [];
  d.call(() => hits.push(1)); d.call(() => hits.push(2));
  await new Promise(r => setTimeout(r, 60));
  assert.deepEqual(hits, [2]);
  const src = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', 'engine_core.js'), 'utf8');
  assert.ok(!/set:\s*setTimeout\b/.test(src), 'a browser throws Illegal invocation for { set: setTimeout }.set(...)');
});
