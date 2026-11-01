'use strict';
// PRIVACY GUARD. Fails if any viewer file other than engine_net.js can reach the network, or loads an absolute URL by itself.
// It reads index.html and every .js / .html / .css file of the viewer (not tests, tools, pipeline, remote, docs) as text.
// It is a guard against accidents and against drift, not a proof against someone who hides code on purpose; the source is small enough to read (see docs/ENGINE-SETUP.md).
// Run: node --test tests/     (in Docker: node:20-alpine)
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const NET_FILE = 'engine_net.js'; // the one engine client module
// The mobile edition adds exactly two more places, each allowed only what it needs and checked by the tests further down:
//   sw.js  the service worker: same-origin cache handling, so it may call fetch() and mention caches (one fetch call, guarded by an origin check)
//   pwa.js registers sw.js from the same folder, nothing else; it may name navigator.serviceWorker but has no network call at all
const SW_FILE = 'sw.js', PWA_FILE = 'pwa.js';
const ALLOW = { [SW_FILE]: new Set(['fetch()']), [PWA_FILE]: new Set(['navigator device or network API', 'service worker']) };
const SKIP_DIRS = new Set(['.git', 'node_modules', 'tests', 'tools', 'pipeline', 'remote', 'docs', 'engine-config']);
const EXT = new Set(['.js', '.mjs', '.html', '.htm', '.css']);

function walk(dir, out) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name), rel = path.relative(root, p).split(path.sep).join('/');
    if (e.isDirectory()) { if (!SKIP_DIRS.has(e.name) && !rel.startsWith('data/sgf') && !rel.startsWith('data/sources')) walk(p, out); }
    else if (EXT.has(path.extname(e.name))) out.push(rel);
  }
  return out;
}
const files = walk(root, []);
const text = Object.fromEntries(files.map(f => [f, fs.readFileSync(path.join(root, f), 'utf8')]));
const others = files.filter(f => f !== NET_FILE);

// anything that can send data, read the user's identity or place, or build code from strings
const BANNED = [
  [/\bfetch\s*\(/, 'fetch()'], [/\bXMLHttpRequest\b/, 'XMLHttpRequest'], [/\bWebSocket\b/, 'WebSocket'], [/\bEventSource\b/, 'EventSource'],
  [/\bsendBeacon\b/, 'sendBeacon'], [/\bimportScripts\b/, 'importScripts'], [/\bimport\s*\(/, 'dynamic import()'],
  [/\bnavigator\s*\.\s*geolocation\b/, 'navigator.geolocation'], [/\bnavigator\s*\.\s*(mediaDevices|connection|serviceWorker|credentials|bluetooth|usb)\b/, 'navigator device or network API'],
  [/\bserviceWorker\b/i, 'service worker'], [/\bnew\s+(Shared)?Worker\b/, 'Worker'], [/\bRTCPeerConnection\b/, 'WebRTC'], [/\bWebTransport\b/, 'WebTransport'],
  [/\bdocument\s*\.\s*cookie\b/, 'document.cookie'], [/\bindexedDB\b/, 'indexedDB'],
  [/\bnew\s+Image\s*\(/, 'new Image()'], [/\bnew\s+Audio\s*\(/, 'new Audio()'], [/\beval\s*\(/, 'eval()'], [/\bnew\s+Function\s*\(/, 'new Function()'],
  [/createElement(NS)?\(\s*['"`](script|img|link|iframe|embed|object|audio|video|source|track|frame|form)['"`]/i, 'creating a loading element'],
  [/\.(src|srcset|action|data|poster|ping)\s*=(?!=)/, 'assigning a loading attribute'], [/setAttribute\(\s*['"`](src|srcset|href|action|data|poster|ping)['"`]/, 'setAttribute of a loading attribute'],
  [/\b(window|self|globalThis|top|parent)\s*\[/, 'dynamic property access on the global object (hides APIs)'],
  [/\blocation\s*(\.\s*(href|assign|replace)\s*=(?!=)|\.\s*(assign|replace)\s*\()/, 'navigating away'], [/\bdocument\s*\.\s*location\b/, 'document.location'],
  [/<(script|link|img|iframe|embed|object|audio|video|source|track|frame)\b[^>]*?\b(src|href|data|poster)\s*=\s*["']?(https?:)?\/\//i, 'an element that loads an absolute URL'],
  [/url\(\s*["']?(https?:)?\/\//i, 'css url() with an absolute URL'], [/@import/i, 'css @import'],
  [/<meta[^>]+http-equiv\s*=\s*["']?refresh/i, 'meta refresh'], [/<form\b/i, '<form>'], [/<base\b/i, '<base>']
];

test('the scan sees the viewer files (index.html, the engine files, the library)', () => {
  for (const f of ['index.html', 'engine_core.js', 'engine_net.js', 'engine_panel.js', 'data/library.js']) assert.ok(files.includes(f), f + ' is not scanned');
});

test('no network API or hidden loading outside engine_net.js', () => {
  const hits = [];
  for (const f of others) for (const [re, what] of BANNED) { const m = re.exec(text[f]); if (m && !(ALLOW[f] && ALLOW[f].has(what))) hits.push(f + ': ' + what + ' (' + m[0].slice(0, 40).replace(/\s+/g, ' ') + ')'); }
  assert.deepEqual(hits, [], 'network code must live in ' + NET_FILE + ' only');
});

test('the scan sees the mobile files too', () => { for (const f of ['mobile.js', SW_FILE, PWA_FILE]) assert.ok(files.includes(f), f + ' is not scanned'); });

test('engine_net.js and sw.js are the only files with fetch, and each has exactly one fetch call', () => {
  const calls = (text[NET_FILE].match(/\bfetch\s*\(/g) || []).length;
  assert.equal(calls, 1, 'one fetch call: the single engine client function');
  for (const bad of ['XMLHttpRequest', 'WebSocket', 'EventSource', 'sendBeacon', 'importScripts']) assert.ok(!text[NET_FILE].includes(bad), NET_FILE + ' uses ' + bad);
});

test('engine_net.js never sends cookies, a referrer, or follows a redirect; the token is only in the Authorization header', () => {
  const s = text[NET_FILE];
  assert.match(s, /credentials:\s*'omit'/); assert.match(s, /referrerPolicy:\s*'no-referrer'/); assert.match(s, /redirect:\s*'error'/);
  const fetchLine = s.split('\n').find(l => /\bfetch\s*\(/.test(l));
  assert.match(fetchLine, /ep\.base \+ path/, 'the address is the validated base plus a known path, nothing else');
  assert.ok(!/token/i.test(fetchLine.replace(/headers: headers/, '')), 'no token in the fetch URL line');
  const uses = s.split('\n').filter(l => /\.token|token\b/.test(l) && !/^\s*(\/\/|\*|\/\*)/.test(l) && !/^\s*\*/.test(l));
  assert.ok(uses.every(l => /Authorization|o\.token|token:/.test(l)), 'the token appears only where the Authorization header is built: ' + uses.join(' | '));
});

test('absolute URLs in the viewer are links the user clicks or the loopback defaults; nothing loads by itself', () => {
  const URL_RE = /\b(?:https?|wss?|ftp):\/\/[^\s"'`<>)\\]+/g;
  const CLICK_HOSTS = /^(www\.bilibili\.com|(www\.)?github\.com|creativecommons\.org|polyformproject\.org|katagotraining\.org|lifein19x19\.com)$/;
  const bad = [];
  for (const f of others) {
    for (const m of text[f].matchAll(URL_RE)) {
      let host = ''; try { host = new URL(m[0].replace(/\$\{[^}]*\}/g, 'x')).hostname; } catch (e) { host = '?'; }
      if (['127.0.0.1', 'localhost', '[::1]'].includes(host)) continue; // the default address of the user's own bridge
      const before = text[f].slice(Math.max(0, m.index - 80), m.index);
      const click = /(href\s*=\s*["']?|\bopen\(\s*[`'"]|\bREPO_URL\s*=\s*['"])$/.test(before) || /(^|\n)\s*(\/\/|\*|\/\*|#|<!--)[^\n]*$/.test(before);
      if (!(CLICK_HOSTS.test(host) && click)) bad.push(f + ': ' + m[0].slice(0, 70));
    }
  }
  assert.deepEqual(bad, [], 'an absolute URL that is neither a clicked link nor a loopback default');
});

test('index.html loads only relative scripts and stylesheets that exist, the engine files in the right order', () => {
  const html = text['index.html'], srcs = [...html.matchAll(/<script[^>]*\bsrc="([^"]+)"/g)].map(m => m[1]);
  for (const s of srcs) { assert.ok(!/^([a-z]+:)?\/\//i.test(s), 'absolute script src: ' + s); assert.ok(fs.existsSync(path.join(root, s)), 'missing file: ' + s); }
  assert.ok(!/<link[^>]+rel=["']?(stylesheet|preload|prefetch|preconnect|dns-prefetch|modulepreload)/i.test(html), 'no <link> that loads or pre-connects');
  const i = n => srcs.indexOf(n);
  assert.ok(i('engine_core.js') >= 0 && i('engine_core.js') < i('engine_net.js') && i('engine_net.js') < i('engine_panel.js'), 'order: core, net, panel');
  assert.ok(i('engine_net.js') < html.indexOf('window.RC=(()=>'), 'engine_net.js is loaded before the compute switch runs');
});

test('localStorage is only touched inside try/catch', () => {
  const bad = [];
  for (const f of others) {
    const s = text[f];
    if (f === 'data/library.js') continue;
    for (const m of s.matchAll(/\blocalStorage\s*(\.\s*(getItem|setItem|removeItem|clear|key|length)\b|\[)/g)) { // real accesses; a mention in a comment or in text does not count
      const before = s.slice(Math.max(0, m.index - 400), m.index), after = s.slice(m.index, m.index + 400);
      const tryAt = before.lastIndexOf('try'), catchAfter = after.search(/\bcatch\b/);
      if (tryAt < 0 || catchAfter < 0) bad.push(f + ' @' + m.index);
    }
  }
  assert.deepEqual(bad, []);
});

test('the panel tells the user the privacy facts that the code backs up', () => {
  const p = text['engine_panel.js'];
  for (const w of ['不含统计', 'cookie', 'localStorage', 'Authorization', 'engine_net.js', 'tests/privacy.test.js', '作者收不到任何数据']) assert.ok(p.includes(w), 'privacy statement lacks: ' + w);
  assert.ok(fs.existsSync(path.join(root, 'tests/privacy.test.js')), 'the test named in the statement exists');
});

test('sw.js only handles same-origin requests: origin check first, one fetch, no absolute URL, no other network API', () => {
  const s = text[SW_FILE];
  assert.equal((s.match(/\bfetch\s*\(/g) || []).length, 1, 'one fetch call');
  const guard = s.search(/url\.origin\s*!==\s*self\.location\.origin\)\s*return/), resp = s.search(/respondWith\s*\(/);
  assert.ok(guard >= 0 && resp > guard, 'cross-origin requests return before respondWith');
  assert.ok(!/\b(?:https?|wss?):\/\//.test(s), 'no absolute URL in sw.js');
  for (const bad of ['XMLHttpRequest', 'WebSocket', 'EventSource', 'sendBeacon', 'importScripts', 'indexedDB', 'openWindow', 'Notification', 'PushManager', 'sync.register']) assert.ok(!s.includes(bad), SW_FILE + ' uses ' + bad);
  assert.match(s, /req\.method\s*!==\s*'GET'\)\s*return/, 'only GET is handled');
});

test('pwa.js has no network call and registers only the same-folder sw.js', () => {
  const s = text[PWA_FILE];
  for (const bad of ['fetch', 'XMLHttpRequest', 'WebSocket', 'EventSource', 'sendBeacon', 'importScripts']) assert.ok(!s.includes(bad), PWA_FILE + ' uses ' + bad);
  const regs = [...s.matchAll(/\.register\(([^)]*)\)/g)].map(m => m[1].trim());
  assert.deepEqual(regs, ["'sw.js'"], 'the one register call names sw.js with no path or URL');
});

test('the cache name follows the visible interface version and the shell list only names files that exist', () => {
  const ver = /VIEWER_VER\s*=\s*'([^']+)'/.exec(text['index.html'])[1], sv = /const VER = '([^']+)'/.exec(text[SW_FILE])[1];
  assert.equal(sv, ver, 'bump VER in sw.js together with VIEWER_VER in index.html');
  assert.match(text[SW_FILE], /'joseki-shell-v' \+ VER/);
  const shell = /const SHELL = \[([\s\S]*?)\];/.exec(text[SW_FILE])[1];
  for (const f of [...shell.matchAll(/'([^']+)'/g)].map(m => m[1]).filter(f => f !== './')) assert.ok(fs.existsSync(path.join(root, f)), 'sw.js lists a missing file: ' + f);
  assert.ok(fs.existsSync(path.join(root, 'manifest.webmanifest')));
  const mf = JSON.parse(fs.readFileSync(path.join(root, 'manifest.webmanifest'), 'utf8'));
  for (const i of mf.icons) assert.ok(fs.existsSync(path.join(root, i.src)), 'manifest icon missing: ' + i.src);
});
