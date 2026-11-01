/* engine_net.js: THE ONLY FILE OF THIS PAGE THAT MAY TALK TO THE NETWORK.
 *
 * Everything the page ever sends goes through the one function EngineNet.request() below, to the address the user typed into the compute settings, and nowhere else.
 * That is also how the "网络活动" list is complete by construction: request() writes one log entry per call, before it sends anything.
 * tests/privacy.test.js fails the build if any other file of the viewer contains network code, or loads an absolute URL by itself.
 *
 * What is sent: the position as board coordinates (never a file name, never the page address), and the token in the Authorization header only.
 * What is never sent: cookies (credentials are omitted), the referrer (no-referrer), anything to any other host. Redirects are refused, so a token cannot be handed on.
 * The log lives in memory only: it is never stored and never sent anywhere; reloading the page clears it.
 */
(function (root) {
  'use strict';
  var C = root.EngineCore, log = [], subs = [];
  var PURPOSE = { '/health': '连接测试', '/models': '读取网络列表', '/analyze': '分析局面', '/stream': '实时推演', '/terminate': '终止推演', '/switch': '切换网络' };

  function note(e) { subs.forEach(function (f) { try { f(e); } catch (x) { /* a broken listener must not break a request */ } }); }
  function bytes(s) { try { return new TextEncoder().encode(s).length; } catch (e) { return String(s).length; } }
  function page() { var l = root.location || {}; return { protocol: l.protocol || '', origin: l.origin || '' }; }

  // o: { endpoint, token, path, body?, ms?, signal?, purpose?, onLine? }.  With onLine the answer is read as NDJSON and every line is handed to onLine as it arrives.
  // Resolves with the parsed JSON (or { status, lines } for a stream). Rejects with an Error that has .info (see EngineCore.mapError); message "已取消" means aborted by the caller.
  async function request(o) {
    var ep = C.validateEndpoint(o.endpoint), path = o.path, ctl = new AbortController(), timedOut = false, timer = null;
    var body = o.body == null ? undefined : JSON.stringify(o.body);
    var ent = { t: Date.now(), host: ep.ok ? ep.host : '-', path: path, purpose: o.purpose || PURPOSE[path] || path, sent: body ? bytes(body) : 0, recv: 0, status: '…', ms: null };
    var t0 = Date.now();
    log.push(ent); if (log.length > 200) log.shift(); note(ent);
    function finish(status) { ent.status = status; ent.ms = Date.now() - t0; if (timer) clearTimeout(timer); note(ent); }
    function fail(info) { finish(info.kind === 'abort' ? '已取消' : info.status ? 'HTTP ' + info.status : info.kind === 'timeout' ? '超时' : '失败'); info.endpoint = ep; info.page = page(); return C.netError(info); }
    if (!ep.ok) throw fail({ kind: 'endpoint', message: ep.error });
    if (!C.knownPath(path)) throw fail({ kind: 'protocol', message: 'unknown path' });
    var onAbort = function () { ctl.abort(); };
    if (o.signal) { if (o.signal.aborted) throw fail({ kind: 'abort' }); o.signal.addEventListener('abort', onAbort); }
    var arm = function () { if (o.ms) { if (timer) clearTimeout(timer); timer = setTimeout(function () { timedOut = true; ctl.abort(); }, o.ms); } };
    arm();
    try {
      var headers = { Authorization: 'Bearer ' + (o.token || '') };
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      var res = await fetch(ep.base + path, { method: body !== undefined ? 'POST' : 'GET', headers: headers, body: body, cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error', mode: 'cors', signal: ctl.signal });
      var ct = res.headers.get('Content-Type') || '';
      if (!res.ok) {
        var raw = await res.text().catch(function () { return ''; }), j = null;
        ent.recv += bytes(raw);
        try { j = JSON.parse(raw); } catch (x) { /* not JSON */ }
        throw fail({ kind: 'http', status: res.status, message: j && j.error, state: j && j.state });
      }
      if (o.onLine && /ndjson/.test(ct) && res.body && res.body.getReader) {
        var rd = res.body.getReader(), dec = new TextDecoder('utf-8'), parser = C.createLineParser(), lines = 0, out;
        var feed = function (r) { r.errors.forEach(function () { throw fail({ kind: 'protocol', message: 'bad line' }); }); r.msgs.forEach(function (m) { lines++; o.onLine(m); }); };
        for (;;) {
          var step = await rd.read();
          if (step.done) break;
          ent.recv += step.value.length; arm();
          feed(parser.push(dec.decode(step.value, { stream: true })));
        }
        feed(parser.push(dec.decode()));
        out = parser.end(); feed(out);
        finish(res.status);
        return { status: res.status, lines: lines };
      }
      var text = await res.text();
      ent.recv += bytes(text);
      var data;
      try { data = JSON.parse(text); } catch (x) { throw fail({ kind: 'protocol', message: 'not JSON' }); }
      finish(res.status);
      return data;
    } catch (e) {
      if (e && e.info) throw e; // already one of ours
      if (e && e.name === 'AbortError') throw fail({ kind: timedOut ? 'timeout' : 'abort' });
      throw fail({ kind: 'network' }); // the browser rejects with a TypeError for refused connections, CORS and mixed content alike, and does not say which
    } finally {
      if (o.signal) o.signal.removeEventListener('abort', onAbort);
      if (timer) clearTimeout(timer);
    }
  }

  root.EngineNet = { request: request, log: log, subscribe: function (f) { subs.push(f); }, PURPOSE: PURPOSE };
})(typeof self !== 'undefined' ? self : this);
