'use strict';
// Logic test of sw.js with a fake service worker scope: no browser needed. Run: node --test tests/sw.test.js (in Docker: node:20-alpine)
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'sw.js'), 'utf8');
const ORIGIN = 'https://site.test';

function makeWorld(net) {
  const store = new Map(); // cache name -> Map(url -> Response)
  const handlers = {};
  const calls = { fetch: [], skip: 0, claim: 0 };
  const key = r => (typeof r === 'string' ? new URL(r, ORIGIN + '/app/').href : r.url);
  const mkCache = name => {
    if (!store.has(name)) store.set(name, new Map());
    const m = store.get(name);
    return {
      async addAll(reqs) { for (const r of reqs) { const res = await world.fetch(r); if (!res.ok) throw new Error('bad ' + key(r)); m.set(key(r), res); } },
      async match(r, o) { const k = key(r), v = m.get((o && o.ignoreSearch) ? k.split("?")[0] : k); return v ? v.clone() : undefined; },
      async put(r, res) { m.set(key(r), res); },
      async keys() { return [...m.keys()].map(u => ({ url: u })); },
    };
  };
  const world = {
    self: { location: { origin: ORIGIN, href: ORIGIN + '/app/sw.js' }, addEventListener: (t, f) => { handlers[t] = f; }, skipWaiting() { calls.skip++; }, clients: { claim: async () => { calls.claim++; } } },
    caches: { open: async n => mkCache(n), keys: async () => [...store.keys()], delete: async n => store.delete(n) },
    fetch: async r => { calls.fetch.push(key(r)); const res = await net(key(r)); Object.defineProperty(res, "type", { value: "basic" }); return res; },
    Request: class { constructor(u, o) { this.url = new URL(u, ORIGIN + '/app/').href; this.method = 'GET'; this.mode = 'no-cors'; Object.assign(this, o); } },
    Response, URL, Promise, console,
  };
  vm.runInNewContext(SRC, Object.assign(world, { self: world.self }));
  return { world, store, handlers, calls };
}
const okNet = u => { const r = new Response('body of ' + u, { status: 200 }); return r; };
const reqOf = (p, extra) => Object.assign({ url: new URL(p, ORIGIN + '/app/').href, method: 'GET', mode: 'no-cors' }, extra);
async function runFetch(w, req) {
  let answered, waits = [];
  const ev = { request: req, respondWith: p => { answered = p; }, waitUntil: p => waits.push(p) };
  w.handlers.fetch(ev);
  const res = answered ? await answered : null;
  await Promise.all(waits);
  return res;
}
async function install(w) { let p; w.handlers.install({ waitUntil: x => { p = x; } }); await p; }

test('install caches the whole shell, and the cache name carries the interface version', async () => {
  const w = makeWorld(okNet); await install(w);
  const ver = /const VER = '([^']+)'/.exec(SRC)[1];
  assert.deepEqual([...w.store.keys()], ['joseki-shell-v' + ver]);
  const urls = [...w.store.get('joseki-shell-v' + ver).keys()];
  assert.ok(urls.some(u => u.endsWith('/app/index.html')) && urls.some(u => u.endsWith('/app/data/library.js')) && urls.some(u => u.endsWith('/app/sw.js') === false));
});

test('a missing file makes install fail, so a broken deploy never replaces a working worker', async () => {
  const w = makeWorld(u => (u.endsWith('quiz.js') ? new Response('', { status: 404 }) : okNet(u)));
  await assert.rejects(install(w));
});

test('activate removes older joseki caches and keeps foreign ones', async () => {
  const w = makeWorld(okNet); await install(w);
  w.store.set('joseki-shell-v0.1', new Map()); w.store.set('someone-else', new Map());
  let p; w.handlers.activate({ waitUntil: x => { p = x; } }); await p;
  const names = [...w.store.keys()];
  assert.ok(!names.includes('joseki-shell-v0.1') && names.includes('someone-else') && names.some(n => n.startsWith('joseki-shell-v')));
  assert.equal(w.calls.claim, 1);
});

test('cross-origin and non-GET requests are not touched', async () => {
  const w = makeWorld(okNet); await install(w); const n = w.calls.fetch.length;
  assert.equal(await runFetch(w, reqOf('https://www.bilibili.com/video/BV1?t=3')), null);
  assert.equal(await runFetch(w, reqOf('http://127.0.0.1:8787/health')), null);
  assert.equal(await runFetch(w, reqOf('index.html', { method: 'POST' })), null);
  assert.equal(w.calls.fetch.length, n, 'no network call was made for them');
  for (const m of w.store.values()) for (const u of m.keys()) assert.ok(u.startsWith(ORIGIN), 'only same-origin urls are cached: ' + u);
});

test('offline: cached files come from the cache without any network call', async () => {
  const w = makeWorld(okNet); await install(w);
  w.world.fetch = async () => { throw new Error('offline'); };
  const res = await runFetch(w, reqOf('index.html'));
  assert.match(await res.text(), /index\.html/);
  const lib = await runFetch(w, reqOf('data/library.js?x=1'));
  assert.match(await lib.text(), /library\.js/, 'query strings are ignored');
});

test('offline: an uncached page navigation falls back to index.html, other files answer 503', async () => {
  const w = makeWorld(okNet); await install(w);
  w.world.fetch = async () => { throw new Error('offline'); };
  const nav = await runFetch(w, reqOf('some/other/page', { mode: 'navigate' }));
  assert.match(await nav.text(), /index\.html/);
  const other = await runFetch(w, reqOf('nothing.js'));
  assert.equal(other.status, 503);
});

test('library.js is served from the cache and refreshed in the background (the pipeline changes it without a version bump)', async () => {
  let v = 1; const w = makeWorld(u => new Response('lib v' + (u.endsWith('library.js') ? v : 0)));
  await install(w); v = 2; const before = w.calls.fetch.length;
  const first = await runFetch(w, reqOf('data/library.js'));
  assert.equal(await first.text(), 'lib v1', 'cache first');
  assert.equal(w.calls.fetch.length, before + 1, 'one background refresh');
  const second = await runFetch(w, reqOf('data/library.js'));
  assert.equal(await second.text(), 'lib v2', 'the next open sees the refreshed data');
});

test('error responses are not cached', async () => {
  const w = makeWorld(u => (u.endsWith('late.js') ? new Response('nope', { status: 500 }) : okNet(u))); await install(w);
  await runFetch(w, reqOf('late.js'));
  const names = [...w.store.values()].flatMap(m => [...m.keys()]);
  assert.ok(!names.some(u => u.endsWith('late.js')));
});

test('skip-waiting happens only when the page asks for it', async () => {
  const w = makeWorld(okNet); await install(w);
  assert.equal(w.calls.skip, 0);
  w.handlers.message({ data: 'something else' }); assert.equal(w.calls.skip, 0);
  w.handlers.message({ data: 'skip-waiting' }); assert.equal(w.calls.skip, 1);
});
