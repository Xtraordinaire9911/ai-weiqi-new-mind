/* engine_core.js: the pure logic of the KataGo engine panel.
 * No DOM, no network, no timers of its own (timers are passed in), so it runs unchanged in the browser and under node:test (tests/engine_core.test.js).
 * The panel (engine_panel.js) only draws and wires; everything that can be decided without a page lives here:
 *   NDJSON parsing (partial chunks), the start/pause/resume/stop state machine, the debounce helper, visit caps, error mapping, endpoint checks,
 *   parsing of the candidate string (AN) the viewer already uses, and the SGF snippet for "adopt this line".
 * Perspective conversion is NOT here on purpose: it stays in the viewer's RC.conv (Black's perspective -> side to move), the panel calls that one.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.EngineCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var LET = 'ABCDEFGHJKLMNOPQRST';

  // ---------------------------------------------------------------- NDJSON with partial chunks
  // push(text) returns the complete lines parsed so far; a line that is cut in the middle of a chunk waits for the next one. end() flushes a last line without newline.
  function createLineParser(maxLine) {
    var buf = '', cap = maxLine || 1048576;
    function take(line, out) {
      line = line.trim();
      if (!line) return;
      try { out.msgs.push(JSON.parse(line)); } catch (e) { out.errors.push({ line: line.slice(0, 80), message: String(e.message || e) }); }
    }
    return {
      push: function (chunk) {
        var out = { msgs: [], errors: [] }, i;
        buf += chunk;
        while ((i = buf.indexOf('\n')) >= 0) { take(buf.slice(0, i), out); buf = buf.slice(i + 1); }
        if (buf.length > cap) { out.errors.push({ line: '', message: 'line too long' }); buf = ''; }
        return out;
      },
      end: function () { var out = { msgs: [], errors: [] }; take(buf, out); buf = ''; return out; }
    };
  }

  // ---------------------------------------------------------------- endpoint checks (the token never goes into the address)
  function isLoopback(h) {
    h = String(h || '').toLowerCase().replace(/^\[|\]$/g, '');
    return h === 'localhost' || h === '::1' || /\.localhost$/.test(h) || /^127\.\d+\.\d+\.\d+$/.test(h);
  }
  function validateEndpoint(s) {
    s = String(s == null ? '' : s).trim();
    if (!s) return { ok: false, code: 'empty', error: '请先填写桥接地址' };
    var u;
    try { u = new URL(s); } catch (e) { return { ok: false, code: 'syntax', error: '地址格式不对,例如 http://127.0.0.1:8787' }; }
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return { ok: false, code: 'scheme', error: '地址要以 http:// 或 https:// 开头' };
    if (u.username || u.password) return { ok: false, code: 'creds', error: '地址里不要写用户名或密码;token 填在 token 栏' };
    if (u.search || u.hash) return { ok: false, code: 'query', error: '地址里不要带参数或 #;token 只填在 token 栏,不会出现在地址里' };
    return { ok: true, base: u.origin + u.pathname.replace(/\/+$/, ''), host: u.host, hostname: u.hostname, protocol: u.protocol, loopback: isLoopback(u.hostname) };
  }
  var PATHS = { '/health': 1, '/models': 1, '/analyze': 1, '/stream': 1, '/terminate': 1, '/switch': 1 };
  function knownPath(p) { return PATHS[p] === 1; }

  // ---------------------------------------------------------------- errors: what happened -> short Chinese text + a one line fix
  // info: { kind: 'network'|'http'|'timeout'|'abort'|'protocol'|'endpoint'|'perspective'|'old', status, message, state, endpoint: validateEndpoint result, page: { protocol, origin } }
  function mapError(info) {
    var i = info || {}, pg = i.page || {}, ep = i.endpoint || {}, origin = pg.origin && pg.origin !== 'null' ? pg.origin : 'http://localhost:8765', m = i.message ? String(i.message).slice(0, 160) : '';
    switch (i.kind) {
      case 'abort': return { code: 'abort', text: '已取消', fix: '' };
      case 'endpoint': return { code: 'endpoint', text: m || '地址不对', fix: '检查左侧「算力」里的桥接地址' };
      case 'timeout': return { code: 'timeout', text: '桥没有响应(超时)', fix: '确认桥还在运行,网络通畅' };
      case 'perspective': return { code: 'perspective', text: '响应没有声明黑方视角,已拒绝(避免视角错误)', fix: '确认连的是本项目的 katago_bridge.py' };
      case 'old': return { code: 'old', text: '这个桥不支持实时推演(版本太旧)', fix: '更新 remote/katago_bridge.py 到 v2' };
      case 'protocol': return { code: 'protocol', text: '桥的响应格式不对', fix: '确认连的是本项目的 katago_bridge.py(v2)' };
      case 'network':
        if (pg.protocol === 'https:' && ep.protocol === 'http:' && !ep.loopback) return { code: 'mixed', text: '浏览器拦截了:https 页面不能访问 http 地址', fix: '改用 https 地址;或用 SSH 转发后填 http://127.0.0.1:8787' };
        if (pg.protocol === 'file:' || pg.origin === 'null') return { code: 'file-origin', text: '无法连接(桥没启动,或桥不接受 file:// 页面)', fix: '启动桥时加 --allow-file-origin,或改从 http://localhost:8765 打开页面' };
        return { code: 'network', text: '无法连接(桥没启动、地址错、或来源未放行)', fix: '确认桥已启动且地址端口正确;页面来源不是 ' + origin + ' 时,启动桥要加 --allow-origin ' + origin };
      case 'http':
        switch (i.status) {
          case 401: return { code: 'token', text: 'token 不对', fix: '重新复制桥启动时打印的 token' };
          case 403: return { code: 'origin', text: '桥拒绝了这个页面的来源', fix: '启动桥时加 --allow-origin ' + origin };
          case 404: return { code: 'notfound', text: '找不到接口,这可能不是本项目的桥', fix: '检查地址;推演需要 katago_bridge.py v2' };
          case 409: return { code: 'busy', text: '桥正在切换网络', fix: '等切换结束再试' };
          case 429: return { code: 'busy', text: '桥正忙(并发已满)', fix: '稍后再试,或先停止其他分析' };
          case 503: return { code: 'unavailable', text: i.state === 'switching' ? '桥正在加载网络' : '引擎还没准备好', fix: '等几秒再开始' };
          case 502: return { code: 'engine', text: '引擎出错' + (m ? ':' + m : ''), fix: '看桥的终端输出,必要时重启桥' };
          case 504: return { code: 'timeout', text: '这次搜索超时', fix: '降低次数上限' };
          case 400: case 413: return { code: 'rejected', text: '桥拒绝了请求' + (m ? ':' + m : ''), fix: '把页面和桥都更新到最新版' };
          default: return { code: 'http', text: (m || '桥返回错误') + ' (HTTP ' + i.status + ')', fix: '看桥的终端输出' };
        }
      default: return { code: 'unknown', text: m || '出错了', fix: '' };
    }
  }
  // An Error that carries the mapped info (engine_net.js throws these). message = text plus the fix; "已取消" stays exactly that (RC compares it).
  function netError(info) {
    var r = mapError(info), e = new Error(r.code === 'abort' ? r.text : r.text + (r.fix ? ' → ' + r.fix : ''));
    e.info = info; e.code = r.code; e.text = r.text; e.fix = r.fix;
    return e;
  }

  // ---------------------------------------------------------------- visit caps
  var CAPS = [{ v: 200, label: '200 次' }, { v: 1000, label: '1000 次' }, { v: 5000, label: '5000 次' }, { v: 'max', label: '直到停止' }];
  // limits: the bridge's /health "limits" ({ streamMaxVisits, streamMaxSeconds }). "until stopped" means the bridge's own ceiling, never really unlimited.
  function effectiveCap(sel, limits) {
    var top = limits && limits.streamMaxVisits > 0 ? limits.streamMaxVisits : 20000, secs = limits && limits.streamMaxSeconds > 0 ? limits.streamMaxSeconds : 900;
    if (sel === 'max') return { visits: top, capped: true, note: '直到停止(桥的上限:' + top + ' 次或 ' + secs + ' 秒)' };
    var n = Math.round(Number(sel));
    if (!(n >= 1)) n = 200;
    if (n > top) return { visits: top, capped: true, note: '已按桥的上限降到 ' + top + ' 次' };
    return { visits: n, capped: false, note: '' };
  }

  // ---------------------------------------------------------------- state machine (pure): reduce(state, event) -> { state, fx }
  // phases: idle | connecting | running | stopping | paused | done | error.   fx are things the panel must do: open, terminate, abort, clear, cancelFollow.
  // A job number guards against stale answers: every start/resume/stop/navigate moves it on, and events carrying an older number are ignored.
  function initial() { return { phase: 'idle', job: 0, err: null, visits: 0, end: null, note: '', after: null }; }
  var live = function (p) { return p === 'connecting' || p === 'running'; };
  function reduce(s, ev) {
    var fx = [], n = Object.assign({}, s), same = ev.job === undefined || ev.job === s.job;
    switch (ev.t) {
      case 'start': case 'resume':
        if (live(s.phase) || s.phase === 'stopping') return { state: s, fx: fx };
        if (ev.t === 'resume' && s.phase !== 'paused') return { state: s, fx: fx };
        n.phase = 'connecting'; n.job = s.job + 1; n.err = null; n.end = null; n.note = ''; n.after = null;
        if (ev.t === 'start') n.visits = 0;
        fx.push({ t: 'open', job: n.job });
        break;
      case 'pause':
        if (!live(s.phase)) return { state: s, fx: fx };
        n.phase = 'stopping'; n.after = 'paused';
        fx.push({ t: 'terminate', job: s.job });
        break;
      case 'stop':
        if (live(s.phase) || s.phase === 'stopping') { fx.push({ t: 'terminate', job: s.job }, { t: 'abort', job: s.job }); n.job = s.job + 1; }
        n.phase = 'idle'; n.err = null; n.visits = 0; n.end = null; n.note = ''; n.after = null;
        fx.push({ t: 'clear' });
        break;
      case 'navigate':
        if (live(s.phase) || s.phase === 'stopping') { fx.push({ t: 'terminate', job: s.job }, { t: 'abort', job: s.job }); n.job = s.job + 1; }
        n.phase = 'idle'; n.err = null; n.end = null; n.note = ''; n.after = null; n.visits = 0;
        fx.push({ t: 'cancelFollow' });
        break;
      case 'update':
        if (!same || !(live(s.phase) || s.phase === 'stopping')) return { state: s, fx: fx };
        if (s.phase === 'connecting') n.phase = 'running';
        n.visits = ev.visits || 0;
        break;
      case 'done': case 'closed':
        if (!same) return { state: s, fx: fx };
        if (s.phase === 'stopping') { n.phase = s.after || 'idle'; n.after = null; n.end = ev.end || null; break; }
        if (!live(s.phase)) return { state: s, fx: fx };
        if (ev.t === 'closed') { n.phase = 'error'; n.err = { code: 'closed', text: '连接中断', fix: '检查网络和桥,然后重新开始' }; break; }
        n.end = ev.end || 'finished';
        if (n.end === 'finished' || n.end === 'timeout') { n.phase = 'done'; n.note = n.end === 'timeout' ? '已到桥的时间上限' : ''; }
        else { n.phase = 'idle'; n.note = n.end === 'preempted' ? '被另一次搜索取代' : n.end === 'switch' ? '切换网络时已结束' : '搜索已结束'; }
        break;
      case 'fail':
        if (!same) return { state: s, fx: fx };
        if (s.phase === 'stopping') { n.phase = s.after || 'idle'; n.after = null; break; } // we wanted it to stop anyway
        if (!live(s.phase)) return { state: s, fx: fx };
        n.phase = 'error'; n.err = ev.err || { code: 'unknown', text: '出错了', fix: '' }; n.after = null;
        fx.push({ t: 'abort', job: s.job });
        break;
      default: return { state: s, fx: fx };
    }
    return { state: n, fx: fx };
  }
  // which buttons are usable in a phase (the panel only applies this)
  function buttons(phase, hasResult, sourceOk) {
    var busy = live(phase), stopping = phase === 'stopping';
    return {
      start: !!sourceOk && !busy && !stopping && phase !== 'paused',
      pause: busy,
      resume: !!sourceOk && phase === 'paused',
      stop: busy || stopping || phase === 'paused' || !!hasResult
    };
  }

  // ---------------------------------------------------------------- debounce (timers are injected, so tests need no real clock)
  function createDebouncer(delay, timers) {
    // wrapped on purpose: a browser throws "Illegal invocation" when the bare setTimeout is stored in an object and called as its method
    var t = timers || { set: function (f, ms) { return setTimeout(f, ms); }, clear: function (id) { clearTimeout(id); } }, h = null;
    return {
      call: function (fn) { if (h !== null) t.clear(h); h = t.set(function () { h = null; fn(); }, delay); },
      cancel: function () { if (h !== null) { t.clear(h); h = null; } },
      pending: function () { return h !== null; }
    };
  }

  // ---------------------------------------------------------------- coordinates
  function gtpToXY(t) { var m = /^([A-HJ-T])(\d{1,2})$/.exec(t); if (!m) return null; var y = 19 - Number(m[2]); return y < 0 || y > 18 ? null : [LET.indexOf(m[1]), y]; }
  function xyToSgf(x, y) { return String.fromCharCode(97 + x, 97 + y); }
  function gtpToSgf(t) { if (t === 'pass') return ''; var q = gtpToXY(t); return q ? xyToSgf(q[0], q[1]) : ''; }
  function sgfToGtp(s) { return s && s.length >= 2 ? LET[s.charCodeAt(0) - 97] + (19 - (s.charCodeAt(1) - 97)) : ''; }

  // ---------------------------------------------------------------- the candidate string the viewer draws: "sgf:loss:prior:wr:visits:pv pv pv;..." (loss = points vs the local best, <= 0)
  function parseAN(an) {
    var rows = [];
    String(an || '').split(';').forEach(function (s) {
      if (!s) return;
      var f = s.split(':'), mv = sgfToGtp(f[0]);
      if (!/^[A-HJ-T](1[0-9]|[1-9])$/.test(mv)) return;
      rows.push({ move: mv, loss: Number(f[1]), prior: Number(f[2]), visits: Number(f[4]) || 0, forced: Number(f[2]) < 0, pv: (f[5] || '').split(' ').filter(function (m) { return m === 'pass' || /^[A-HJ-T](1[0-9]|[1-9])$/.test(m); }) });
    });
    rows.sort(function (a, b) { return b.loss - a.loss || b.visits - a.visits; });
    return rows;
  }
  function fmtLoss(l) { return l > -0.05 ? '最优' : l.toFixed(1); }
  function fmtN(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  // ---------------------------------------------------------------- "adopt this line": an SGF with the position, the moves so far, and the AI line as the continuation
  // q: { initialStones: [['B','D4']...], moves: [['B','Q16']...], initialPlayer?, komi, rules }, first: 'B'|'W' (side to move), pv: ['Q3','D17', ...] in GTP
  var RULE_NAMES = { japanese: 'Japanese', chinese: 'Chinese', 'tromp-taylor': 'Tromp-Taylor', aga: 'AGA', korean: 'Korean', 'new-zealand': 'NZ', 'stone-scoring': 'Japanese', 'ancient-area': 'Chinese' };
  function esc(t) { return String(t).replace(/\\/g, '\\\\').replace(/]/g, '\\]'); }
  function sgfSnippet(q, first, pv, note) {
    var b = [], w = [], out = '(;GM[1]FF[4]CA[UTF-8]SZ[19]KM[' + (q.komi == null ? 6.5 : q.komi) + ']RU[' + (RULE_NAMES[q.rules] || 'Japanese') + ']';
    (q.initialStones || []).forEach(function (s) { var c = gtpToSgf(s[1]); if (c) (s[0] === 'B' ? b : w).push('[' + c + ']'); });
    if (b.length) out += 'AB' + b.join('');
    if (w.length) out += 'AW' + w.join('');
    if (!(q.moves || []).length && (q.initialPlayer || first)) out += 'PL[' + (q.initialPlayer || first) + ']';
    out += 'C[' + esc(note || 'KataGo 局部推演') + ']';
    (q.moves || []).forEach(function (m) { out += ';' + m[0] + '[' + gtpToSgf(m[1]) + ']'; });
    var col = first === 'W' ? 'W' : 'B';
    (pv || []).forEach(function (m, i) { out += ';' + col + '[' + gtpToSgf(m) + ']' + (i === 0 ? 'C[' + esc('以下为 KataGo 推演的最佳线,不是老师的讲解') + ']' : ''); col = col === 'B' ? 'W' : 'B'; });
    return out + ')';
  }

  return {
    createLineParser: createLineParser, isLoopback: isLoopback, validateEndpoint: validateEndpoint, knownPath: knownPath,
    mapError: mapError, netError: netError, CAPS: CAPS, effectiveCap: effectiveCap,
    initial: initial, reduce: reduce, buttons: buttons, createDebouncer: createDebouncer,
    gtpToXY: gtpToXY, gtpToSgf: gtpToSgf, sgfToGtp: sgfToGtp, parseAN: parseAN, fmtLoss: fmtLoss, fmtN: fmtN, sgfSnippet: sgfSnippet
  };
});
