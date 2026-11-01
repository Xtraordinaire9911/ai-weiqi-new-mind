'use strict';
// engine_net.js against a real HTTP server on 127.0.0.1 (random port): headers, the activity log, NDJSON in odd chunks, abort, timeout and error mapping.
const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const C = require('../engine_core.js');
const self_ = { EngineCore: C, location: { protocol: 'http:', origin: 'http://localhost:8765' } };
new Function('self', fs.readFileSync(path.join(__dirname, '..', 'engine_net.js'), 'utf8'))(self_);
const NET = self_.EngineNet;

const seen = [];
let mode = 'json';
const srv = http.createServer((req, res) => {
  let body = '';
  req.on('data', d => body += d);
  req.on('end', () => {
    seen.push({ method: req.method, url: req.url, headers: req.headers, body });
    if (req.headers.authorization !== 'Bearer secret-token') { res.writeHead(401, { 'Content-Type': 'application/json' }); return res.end('{"error":"invalid token"}'); }
    if (req.url === '/stream' && mode === 'chunks') {
      res.writeHead(200, { 'Content-Type': 'application/x-ndjson' });
      const parts = ['{"n":1,"x":"中', '文"}\n{"n":2}\n{"n', '":3,"done":true}'];
      let i = 0; const t = setInterval(() => { if (i < parts.length) res.write(parts[i++]); else { clearInterval(t); res.end('\n'); } }, 15);
      return;
    }
    if (req.url === '/stream' && mode === 'hang') { res.writeHead(200, { 'Content-Type': 'application/x-ndjson' }); res.write('{"n":1}\n'); return; }
    if (req.url === '/stream' && mode === 'garbage') { res.writeHead(200, { 'Content-Type': 'application/x-ndjson' }); return res.end('{"n":1}\nnot json\n'); }
    if (req.url === '/health') { res.writeHead(200, { 'Content-Type': 'application/json' }); return res.end('{"ok":true,"bridge":{"winratesAs":"BLACK"}}'); }
    res.writeHead(404, { 'Content-Type': 'application/json' }); res.end('{"error":"not found"}');
  });
});
let base;
test.before(() => new Promise(r => srv.listen(0, '127.0.0.1', () => { base = 'http://127.0.0.1:' + srv.address().port; r(); })));
test.after(() => { srv.closeAllConnections && srv.closeAllConnections(); srv.close(); });

test('GET: sends only the token header, no cookie, no referrer, the token is not in the URL; one log entry with host, path, bytes, status', async () => {
  const n0 = NET.log.length, s0 = seen.length;
  const r = await NET.request({ endpoint: base + '/', token: 'secret-token', path: '/health' });
  assert.equal(r.ok, true);
  const q = seen[s0];
  assert.equal(q.method, 'GET'); assert.equal(q.url, '/health');
  assert.equal(q.headers.authorization, 'Bearer secret-token');
  assert.ok(!('cookie' in q.headers) && !('referer' in q.headers), 'no cookie, no referer');
  assert.ok(!q.url.includes('secret') && !JSON.stringify(q.headers).replace('Bearer secret-token', '').includes('secret'));
  assert.equal(NET.log.length, n0 + 1);
  const e = NET.log[NET.log.length - 1];
  assert.equal(e.host, new URL(base).host); assert.equal(e.path, '/health'); assert.equal(e.purpose, '连接测试'); assert.equal(e.status, 200); assert.ok(e.recv > 10 && e.ms >= 0);
});

test('POST: the body is JSON, the log counts the bytes sent', async () => {
  const s0 = seen.length, n0 = NET.log.length;
  await NET.request({ endpoint: base, token: 'secret-token', path: '/health', body: { id: 'a', moves: [['B', 'D4']] } });
  assert.equal(seen[s0].method, 'POST'); assert.equal(seen[s0].headers['content-type'], 'application/json');
  assert.deepEqual(JSON.parse(seen[s0].body), { id: 'a', moves: [['B', 'D4']] });
  assert.equal(NET.log[n0].sent, Buffer.byteLength(seen[s0].body));
});

test('a wrong token gives the mapped token error and a log entry with the status', async () => {
  await assert.rejects(NET.request({ endpoint: base, token: 'nope', path: '/health' }), e => e.code === 'token' && /token 不对/.test(e.message) && e.info.status === 401);
  assert.equal(NET.log[NET.log.length - 1].status, 'HTTP 401');
});

test('NDJSON stream: lines cut at odd places (even inside a Chinese character) arrive complete and in order', async () => {
  mode = 'chunks';
  const got = [];
  const r = await NET.request({ endpoint: base, token: 'secret-token', path: '/stream', body: { id: 's' }, ms: 2000, onLine: m => got.push(m) });
  assert.deepEqual(got, [{ n: 1, x: '中文' }, { n: 2 }, { n: 3, done: true }]);
  assert.equal(r.lines, 3);
  assert.equal(NET.log[NET.log.length - 1].purpose, '实时推演');
});

test('NDJSON stream: a garbage line is a protocol error', async () => {
  mode = 'garbage';
  await assert.rejects(NET.request({ endpoint: base, token: 'secret-token', path: '/stream', body: {}, ms: 2000, onLine() {} }), e => e.code === 'protocol');
});

test('abort: the caller\'s signal stops a stream and the message is exactly 已取消', async () => {
  mode = 'hang';
  const ctl = new AbortController(), got = [];
  const p = NET.request({ endpoint: base, token: 'secret-token', path: '/stream', body: {}, signal: ctl.signal, ms: 5000, onLine: m => { got.push(m); ctl.abort(); } });
  await assert.rejects(p, e => e.message === '已取消' && e.code === 'abort');
  assert.equal(got.length, 1);
  assert.equal(NET.log[NET.log.length - 1].status, '已取消');
});

test('idle timeout: a stream that goes quiet ends with the timeout error', async () => {
  mode = 'hang';
  await assert.rejects(NET.request({ endpoint: base, token: 'secret-token', path: '/stream', body: {}, ms: 120, onLine() {} }), e => e.code === 'timeout');
});

test('a closed port is a network error with the one line fix, and it is logged', async () => {
  const dead = http.createServer(); await new Promise(r => dead.listen(0, '127.0.0.1', r));
  const port = dead.address().port; await new Promise(r => dead.close(r));
  await assert.rejects(NET.request({ endpoint: 'http://127.0.0.1:' + port, token: 'x', path: '/health', ms: 2000 }), e => e.code === 'network' && /--allow-origin http:\/\/localhost:8765/.test(e.message));
  assert.equal(NET.log[NET.log.length - 1].status, '失败');
});

test('a bad address or an unknown path never reaches the network (but is logged)', async () => {
  const s0 = seen.length, n0 = NET.log.length;
  await assert.rejects(NET.request({ endpoint: base + '/?token=secret-token', token: 'secret-token', path: '/health' }), e => e.code === 'endpoint' && !/secret-token/.test(e.message));
  await assert.rejects(NET.request({ endpoint: 'ftp://x.example', token: 't', path: '/health' }), e => e.code === 'endpoint');
  await assert.rejects(NET.request({ endpoint: base, token: 't', path: '/etc/passwd' }), e => e.code === 'protocol');
  assert.equal(seen.length, s0, 'no request was made');
  assert.equal(NET.log.length, n0 + 3, 'each attempt is in the activity list');
});

test('the log is capped and subscribers are told about every change', async () => {
  let calls = 0; NET.subscribe(() => calls++);
  for (let i = 0; i < 3; i++) await NET.request({ endpoint: base, token: 'secret-token', path: '/health' });
  assert.ok(calls >= 6, 'start and finish of each request: ' + calls);
  for (let i = 0; i < 210; i++) await NET.request({ endpoint: 'bad', token: 't', path: '/health' }).catch(() => {});
  assert.ok(NET.log.length <= 200);
});
