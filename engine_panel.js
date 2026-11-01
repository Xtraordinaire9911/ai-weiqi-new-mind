/* engine_panel.js: the "KataGo 继续推演" card in the right column (below the commentary, never over the board).
 *
 * It draws a card and wires it to what the viewer already has. It does not re-implement any rule:
 *   - the position -> query, the teaching region, the Black -> side-to-move conversion, the candidate string and the forced evaluation of the teacher's moves are the
 *     viewer's own RC.query / RC.region / RC.conv / RC.mkAN / RC.forceTeacher (index.html);
 *   - the board is drawn by the viewer's own drawBoard(): the live result is stored on the node as node.live (the same field a single-shot analysis fills),
 *     so candidate dots, ring colours, hover previews and tooltips follow the existing rules without any copy of that code here.
 * Live nodes are in-memory only (node.live on the current node, or a trial node made by RC.click); nothing is ever added to the library tree.
 * All traffic goes through EngineNet.request (engine_net.js). Settings (visits cap, region, best line) live in localStorage, every access in try/catch.
 * The pure logic (state machine, NDJSON, caps, errors, SGF) is in engine_core.js and tested with node:test.
 */
(function (root) {
  'use strict';
  var C = root.EngineCore, NET = root.EngineNet, H = null, KEY = 'josekiapp.ep.v1';
  var S = { cap: 1000, region: true, best: true, open: false };
  try { var o = JSON.parse(root.localStorage.getItem(KEY) || 'null'); if (o) { if (o.cap === 'max' || [200, 1000, 5000].indexOf(o.cap) >= 0) S.cap = o.cap; S.region = o.region !== false; S.best = o.best !== false; S.open = !!o.open; } } catch (e) { /* storage blocked: defaults */ }
  function save() { try { root.localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* ignore */ } }

  var st = C.initial(), jobs = {}, lastNode = null, myGhost = null, models = null, modelsKey = '', loadingModels = false, switching = null, note = '', copied = '', sgfText = '';
  var follow = C.createDebouncer(300), box = null, pauseTimer = null, netDirty = false;
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var MODES = { off: '缓存', local: '本机', remote: '远程' };

  var CSS = '#ep .ep{border:1px solid var(--bd);border-left:4px solid var(--ac);border-radius:6px;padding:8px 10px;margin:8px 0;line-height:1.5;background:var(--pn);font-size:13px}' +
    '#ep h5{margin:0 0 2px;font-size:12px;color:var(--ac)}#ep .ept{font-weight:600;margin-bottom:3px}' +
    '#ep .eps{font-size:12px;color:var(--mu);display:flex;gap:6px;align-items:center;flex-wrap:wrap}#ep .eps i{width:8px;height:8px;border-radius:50%;background:var(--bd);display:inline-block;flex:none}' +
    '#ep .eps i.ok{background:var(--gd)}#ep .eps i.bad{background:var(--rd)}#ep .eps i.busy{background:var(--ac)}' +
    '#ep .epr{display:flex;gap:6px;margin:7px 0}#ep .epr button{flex:1;padding:4px 2px}' +
    '#ep button:disabled{opacity:.45;cursor:default}#ep button:disabled:hover{border-color:var(--bd);color:inherit}' +
    '#ep .epg{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:6px;font-size:12px}#ep .epg label{display:grid;gap:2px;color:var(--mu)}#ep select{width:100%;font-size:12px;padding:3px 4px}' +
    '#ep .epk{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;margin:6px 0 2px;align-items:center}#ep .epk label{white-space:nowrap}' +
    '#ep .epe{margin:6px 0;padding:5px 8px;border-radius:5px;border:1px solid var(--rd);color:var(--rd);font-size:12px;line-height:1.5}#ep .epe b{color:inherit}' +
    '#ep .epn{margin:6px 0;font-size:12px;color:var(--mu)}' +
    '#ep table{width:100%;border-collapse:collapse;margin:6px 0 2px;font-size:12px}#ep th{font-weight:400;color:var(--mu);text-align:left;padding:1px 3px;border-bottom:1px solid var(--bd)}#ep td{padding:2px 3px;border-bottom:1px solid var(--bd)}' +
    '#ep td.l{font-variant-numeric:tabular-nums}#ep tr:hover td{background:var(--bg)}#ep .epw{padding:0 6px;font-size:11px}' +
    '#ep .epb{margin:6px 0;font-size:12px}#ep .epb button{margin-left:6px;font-size:12px;padding:2px 8px}' +
    '#ep .epp{margin-top:8px;padding-top:6px;border-top:1px dashed var(--bd);font-size:11px;color:var(--mu);line-height:1.55}' +
    '#ep details{margin-top:5px;font-size:12px;color:var(--mu)}#ep summary{cursor:pointer;user-select:none}#ep summary:hover{color:var(--ac)}' +
    '#ep .epl{max-height:150px;overflow:auto;margin-top:3px}#ep .epl div{display:grid;grid-template-columns:52px 1fr 52px 44px;gap:4px;padding:1px 0;border-bottom:1px solid var(--bd);font-variant-numeric:tabular-nums}' +
    '#ep .epl span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}#ep textarea{width:100%;height:70px;font-size:11px}#ep a{color:var(--ac)}';

  function cfg() { return H.RC.cfg(); }
  function bridge() { var c = cfg(); return c.ok && c.info ? c.info : null; }
  function canRun() { var b = bridge(); return !!b && Array.isArray(b.features) && b.features.indexOf('stream') >= 0 && b.state === 'ready' && !switching; }
  function curLive() { var n = H.cur(); return n ? H.RC.live(n) : null; } // any live result of the current node: from this panel or from a single-shot analysis
  function isLeaf() { var n = H.cur(); return !!n && n.c.length === 0; }

  // ------------------------------------------------------------------ state machine glue
  function dispatch(ev) {
    var r = C.reduce(st, ev);
    st = r.state;
    r.fx.forEach(runFx);
    render();
  }
  function runFx(fx) {
    var j = jobs[fx.job];
    if (fx.t === 'open') startJob(fx.job);
    else if (fx.t === 'terminate') {
      if (j) sendTerminate(j);
      if (st.phase === 'stopping') { clearTimeout(pauseTimer); pauseTimer = setTimeout(function () { if (st.phase === 'stopping' && j) j.ctl.abort(); }, 6000); } // failsafe: never wait for a stream forever
    } else if (fx.t === 'abort') { if (j) j.ctl.abort(); }
    else if (fx.t === 'cancelFollow') follow.cancel();
    else if (fx.t === 'clear') {
      var n = H.cur();
      if (n && n.live && n.live.eng) n.live = null;
      if (n) n.busy = 0;
      if (myGhost && H.getGhost() === myGhost) H.setGhost([]);
      myGhost = null;
      H.draw();
    }
  }
  function sendTerminate(j) {
    var c = cfg();
    NET.request({ endpoint: c.endpoint, token: c.token, path: '/terminate', body: { id: j.cid }, ms: 8000 }).catch(function () { /* the stream abort ends the search on the bridge as well */ });
  }

  // ------------------------------------------------------------------ one search
  async function startJob(id) {
    var node = H.cur(), c = cfg(), b = c.info || {}, j = { id: id, node: node, ctl: new AbortController(), cid: 'e' + Date.now().toString(36) + id, t0: performance.now(), done: false, last: null };
    jobs[id] = j; lastNode = node; note = '';
    if (!canRun()) return dispatch({ t: 'fail', job: id, err: b.features ? C.mapError({ kind: 'http', status: 503, state: b.state }) : C.mapError({ kind: 'old' }) });
    var cap = C.effectiveCap(S.cap, b.limits), q = H.RC.query(node, cap.visits, j.cid);
    q.reportDuringSearchEvery = 0.5;
    if (!S.region) { delete q.allowMoves; delete q.avoidMoves; } // the viewer's rule is "only the teaching region"; leaving it is the user's explicit choice (checkbox)
    node.busy = 1;
    try {
      await NET.request({ endpoint: c.endpoint, token: c.token, path: '/stream', body: q, ms: 30000, signal: j.ctl.signal, onLine: function (m) { onMsg(j, m); } });
      if (!j.done) dispatch({ t: 'closed', job: id });
    } catch (e) {
      if (st.job === id) dispatch({ t: 'fail', job: id, err: e && e.info ? { code: e.code, text: e.text, fix: e.fix } : { code: 'unknown', text: String(e && e.message || e), fix: '' } });
    } finally {
      node.busy = 0;
      if (node.live && node.live.run) node.live.run = false; // however the search ended (cancelled, failed), it is no longer running
      setTimeout(function () { delete jobs[id]; }, 15000);
    }
  }
  function onMsg(j, m) {
    if (st.job !== j.id) return; // an answer of an older search
    if (m.error) return dispatch({ t: 'fail', job: j.id, err: C.mapError({ kind: 'http', status: 502, message: m.error }) });
    var fin = !!m.done, end = (m.bridge && m.bridge.end) || 'finished';
    if (m.moveInfos && m.moveInfos.length) {
      var P;
      try { P = H.RC.conv(m); } catch (e) { return dispatch({ t: 'fail', job: j.id, err: C.mapError({ kind: 'perspective' }) }); } // RC.conv refuses an answer that does not declare Black's perspective
      var cand = P.cand.slice(), tv = Math.max.apply(null, cand.map(function (x) { return x.v; })), vis = (m.rootInfo && m.rootInfo.visits) || tv;
      j.last = { cand: cand, tv: tv, P: P };
      j.node.live = { mode: cfg().mode, pl: P.t, an: H.RC.mkAN(cand, tv), vis: vis, ms: (m.bridge && m.bridge.ms) || Math.round(performance.now() - j.t0), fake: P.fake, run: !fin, eng: 1 };
      dispatch({ t: 'update', job: j.id, visits: vis });
      autoGhost(j.node);
      if (H.cur() === j.node) H.draw();
    }
    if (fin) finishJob(j, end);
  }
  async function finishJob(j, end) {
    j.done = true;
    if (end === 'finished' && j.last && j.node.c.length) { // a node with teacher moves: evaluate the ones the search did not visit enough, like the single-shot analysis
      note = '补充评估老师的着法…'; render();
      try { await H.RC.forceTeacher(j.node, j.last.cand, j.last.tv, j.ctl.signal); j.node.live.an = H.RC.mkAN(j.last.cand, j.last.tv); } catch (e) { /* the search result stays */ }
      note = '';
    }
    if (j.node.live) j.node.live.run = false;
    dispatch({ t: 'done', job: j.id, end: end });
    autoGhost(j.node);
    if (H.cur() === j.node) H.draw();
  }
  // the best line as a preview in the viewer's "old look" (numbered dashed ring stones, dots stay). Does not touch a pinned line or one the user clicked.
  function autoGhost(node) {
    if (!S.best || node !== H.cur() || H.pinned()) return;
    var g = H.getGhost();
    if (g.length && g !== myGhost) return;
    var rows = C.parseAN(node.live && node.live.an);
    myGhost = rows.length ? rows[0].pv.map(H.fromGtp).filter(Boolean) : null;
    H.setGhost(myGhost || []);
  }

  // ------------------------------------------------------------------ the bridge's networks
  async function loadModels() {
    var c = cfg(), b = bridge();
    if (!b || !Array.isArray(b.features) || b.features.indexOf('models') < 0 || loadingModels) return;
    var key = c.endpoint + '|' + b.modelId + '|' + b.state;
    if (key === modelsKey) return;
    loadingModels = true;
    try { var r = await NET.request({ endpoint: c.endpoint, token: c.token, path: '/models', ms: 8000 }); models = r; modelsKey = key; } catch (e) { models = null; modelsKey = key; }
    loadingModels = false; render();
  }
  async function switchModel(id) {
    var c = cfg();
    if (!id || switching) return;
    switching = { id: id, state: 'stopping' }; note = ''; render();
    var failed = '';
    try {
      await NET.request({ endpoint: c.endpoint, token: c.token, path: '/switch', body: { model: id }, ms: 200000, onLine: function (m) {
        switching.state = m.state || switching.state; if (m.state === 'failed' || m.state === 'error') failed = m.error || '切换失败'; render();
      } });
    } catch (e) { failed = e.text || e.message; }
    switching = null; modelsKey = ''; models = null;
    note = failed ? '切换没有成功,仍在使用原来的网络:' + failed : '';
    H.RC.refresh(); // /health again: backend, model id, state
    render();
  }

  // ------------------------------------------------------------------ copy "adopt this line"
  async function copyText(t) {
    try { await root.navigator.clipboard.writeText(t); return true; } catch (e) { /* try the old way */ }
    try { var ta = document.createElement('textarea'); ta.value = t; ta.style.cssText = 'position:fixed;left:-9999px'; document.body.appendChild(ta); ta.select(); var ok = document.execCommand('copy'); document.body.removeChild(ta); return ok; } catch (e2) { return false; }
  }
  async function adopt() {
    var n = H.cur(), l = curLive(), rows = l ? C.parseAN(l.an) : [];
    if (!rows.length || !rows[0].pv.length) return;
    var q = H.RC.query(n, 1, 'sgf'), best = rows[0];
    sgfText = C.sgfSnippet(q, l.pl, best.pv, 'KataGo 局部推演(只搜讲解区域),' + C.fmtN(l.vis) + ' 次');
    copied = (await copyText(sgfText)) ? 'ok' : 'manual';
    render();
  }

  // ------------------------------------------------------------------ rendering
  function stateText() {
    var c = cfg(), l = curLive(), vis = st.visits || (l && l.vis) || 0, j = jobs[st.job], secs = j ? ((performance.now() - j.t0) / 1000).toFixed(1) : '0.0';
    if (switching) return '切换网络:' + ({ stopping: '停止中', loading: '加载中', rollback: '恢复原网络', ready: '完成' }[switching.state] || '加载中') + '…';
    switch (st.phase) {
      case 'connecting': return '连接中…';
      case 'running': return '搜索中 ' + C.fmtN(vis) + ' 次 · ' + secs + ' 秒' + (note ? ' · ' + note : '');
      case 'stopping': return '正在停止…';
      case 'paused': return '已暂停 · ' + C.fmtN(vis) + ' 次';
      case 'done': return '已完成 · ' + C.fmtN(vis) + ' 次' + (st.note ? ' · ' + st.note : '');
      case 'error': return '出错';
      default: return c.mode === 'off' ? '缓存,不联网' : c.ok ? (l ? '上次结果 ' + C.fmtN(l.vis) + ' 次' : '空闲') : '未连接';
    }
  }
  function dotClass() {
    var c = cfg();
    if (st.phase === 'error' || (c.mode !== 'off' && !c.ok && c.msg && c.msg !== '连接中…')) return 'bad';
    if (switching || st.phase === 'running' || st.phase === 'connecting' || st.phase === 'stopping') return 'busy';
    return c.mode !== 'off' && c.ok ? 'ok' : '';
  }
  function modelLabel() {
    var b = bridge();
    if (!b) return '-';
    var m = models && models.models && models.models.filter(function (x) { return x.active; })[0];
    return m ? m.label : (b.model || b.modelId || '-');
  }
  function netRows() {
    return NET.log.slice(-40).reverse().map(function (e) {
      var t = new Date(e.t), hh = ('0' + t.getHours()).slice(-2) + ':' + ('0' + t.getMinutes()).slice(-2) + ':' + ('0' + t.getSeconds()).slice(-2);
      return '<div title="' + esc(e.purpose + ' · 发送 ' + e.sent + ' 字节 · 收到 ' + e.recv + ' 字节' + (e.ms != null ? ' · ' + e.ms + ' 毫秒' : '')) + '"><span>' + hh + '</span><span>' + esc(e.host) + esc(e.path) + ' · ' + esc(e.purpose) + '</span><span>' + (e.sent + e.recv) + ' B</span><span>' + esc(e.status) + '</span></div>';
    }).join('') || '<div><span>本页还没有发出任何请求</span></div>';
  }
  function render() {
    if (!box) return;
    var c = cfg(), n = H.cur(), leaf = isLeaf(), show = leaf || S.open, l = curLive(), rows = l ? C.parseAN(l.an) : [], b = bridge(), ok = canRun();
    var bt = $('bep'); if (bt) bt.classList.toggle('on', S.open && !leaf);
    box.style.display = show ? '' : 'none';
    if (!show) return;
    $('ept').textContent = leaf ? '这条变化到此为止?用 KataGo 继续推演' : '用 KataGo 推演这个局面';
    $('epd').className = dotClass();
    $('epst').textContent = MODES[c.mode] + ' · ' + modelLabel() + ' · ' + ((b && b.backend) || '-') + ' · ' + stateText();
    var bs = C.buttons(st.phase, !!(l && l.eng), ok), set = function (id, v) { $(id).disabled = !v; };
    set('epgo', bs.start); set('eppa', bs.pause); set('eprs', bs.resume); set('epsp', bs.stop);
    $('epm').value = c.mode; $('epcap').value = String(S.cap); $('epre').checked = S.region; $('epbl').checked = S.best;
    var busy = st.phase === 'running' || st.phase === 'connecting' || st.phase === 'stopping', ms = $('epmo');
    var opts = models && models.models && models.models.length ? models.models : null;
    if (!ms.dataset.sig || ms.dataset.sig !== (opts ? opts.map(function (x) { return x.id + x.active; }).join() : '-')) {
      ms.innerHTML = opts ? opts.map(function (x) { return '<option value="' + esc(x.id) + '"' + (x.active ? ' selected' : '') + '>' + esc(x.label) + (x.active ? ' ✓' : '') + '</option>'; }).join('') : '<option>' + (b ? '(桥没有提供网络列表)' : '(未连接)') + '</option>';
      ms.dataset.sig = opts ? opts.map(function (x) { return x.id + x.active; }).join() : '-';
    }
    ms.disabled = !opts || busy || !!switching;
    $('epcap').title = C.effectiveCap(S.cap, b && b.limits).note || '';
    var msg = '';
    if (st.err) msg = '<div class="epe"><b>' + esc(st.err.text) + '</b>' + (st.err.fix ? '<br>→ ' + esc(st.err.fix) : '') + '</div>';
    else if (c.mode === 'off') msg = '<div class="epn">现在用的是缓存(不联网)。把「算力」换成「本机」或「远程」后才能推演。</div>';
    else if (!c.ok) msg = '<div class="epn">' + (c.msg === '连接中…' ? '连接中…' : '未连接' + (c.msg ? ':' + esc(c.msg) : '') + '。') + ' <button id="epcfg">打开算力设置</button></div>';
    else if (b && b.features && b.features.indexOf('stream') < 0) msg = '<div class="epe"><b>这个桥不支持实时推演(版本太旧)</b><br>→ 更新 remote/katago_bridge.py 到 v2</div>';
    else if (b && b.state && b.state !== 'ready') msg = '<div class="epn">桥的引擎状态:' + esc(b.state) + (b.error ? '(' + esc(b.error) + ')' : '') + '</div>';
    if (note && st.phase !== 'running') msg += '<div class="epn">' + esc(note) + '</div>';
    if (copied === 'ok') msg += '<div class="epn">已复制 SGF(没有联网)。</div>';
    else if (copied === 'manual') msg += '<div class="epn">浏览器不让自动复制,请手动复制:</div><textarea readonly id="epsgf">' + esc(sgfText) + '</textarea>';
    $('epmsg').innerHTML = msg;
    // candidates: points lost vs the local best (never a whole-board win rate), visits, the line as chips
    var shown = rows.slice(0, 5);
    $('eptb').innerHTML = shown.length ? '<table><tr><th>着手</th><th>比最优差(目)</th><th>次数</th><th>变化</th><th></th></tr>' + shown.map(function (r, i) {
      return '<tr data-i="' + i + '"><td><span class="chip" data-pv="' + r.move + '">' + r.move + '</span></td><td class="l">' + C.fmtLoss(r.loss) + '</td><td class="l">' + C.fmtN(r.visits) + (r.forced ? '*' : '') + '</td><td>' +
        (r.pv.length > 1 ? '<span class="chip pv" data-pv="' + r.pv.join(' ') + '">' + r.pv.length + '手</span>' : '') + '</td><td><button class="epw" data-mv="' + r.move + '" title="在棋盘上试下这一手">走</button></td></tr>';
    }).join('') + '</table>' + (shown.some(function (r) { return r.forced; }) ? '<div class="epn">* 老师的着法,单独评估</div>' : '') : '';
    $('epbest').innerHTML = shown.length && shown[0].pv.length ? '最佳线:' + shown[0].pv.map(function (m) { return '<span class="chip" data-pv="' + m + '">' + m + '</span>'; }).join('') + ' <button id="epad" title="把当前局面加这条线复制成 SGF,不联网">采用这条线</button>' : '';
    $('epnetc').textContent = String(NET.log.length);
    if ($('epnet').open) $('epnl').innerHTML = netRows();
  }

  // ------------------------------------------------------------------ build
  function build() {
    var css = document.createElement('style'); css.textContent = CSS; document.head.appendChild(css);
    box = $('ep');
    box.innerHTML = '<div class="ep"><h5>KataGo 继续推演</h5><div class="ept" id="ept"></div><div class="eps"><i id="epd"></i><span id="epst"></span></div>' +
      '<div class="epr"><button id="epgo">开始</button><button id="eppa">暂停</button><button id="eprs">继续</button><button id="epsp">停止</button></div>' +
      '<div class="epg"><label>算力<select id="epm"><option value="off">缓存(不联网)</option><option value="local">本机</option><option value="remote">远程 GPU</option></select></label>' +
      '<label>网络<select id="epmo"></select></label><label>次数上限<select id="epcap">' + C.CAPS.map(function (x) { return '<option value="' + x.v + '">' + x.label + '</option>'; }).join('') + '</select></label></div>' +
      '<div class="epk"><label><input type="checkbox" id="epre"> 只搜讲解区域</label><label><input type="checkbox" id="epbl"> 显示最佳线</label></div>' +
      '<div id="epmsg"></div><div id="eptb"></div><div class="epb" id="epbest"></div>' +
      '<div class="epp">隐私:不含统计、第三方请求或 cookie;地址、token、设置只存在本浏览器的 localStorage。只有选了「本机/远程」,才会把当前局面的坐标发到你自己填的地址(token 只放在 Authorization 头里),作者收不到任何数据。' +
      '联网代码只在 engine_net.js,可自行审计,自动测试(tests/privacy.test.js)会检查这一点。</div>' +
      '<details id="epnet"><summary>网络活动(<span id="epnetc">0</span>)</summary><div class="epl" id="epnl"></div></details>' +
      '<div class="epn"><a href="docs/ENGINE-SETUP.md" target="_blank" rel="noopener">设置说明:本机 KataGo / 远程 GPU</a></div></div>';
    box.addEventListener('click', function (e) {
      var t = e.target;
      if (t.closest && t.closest('.chip') && t.dataset.pv) return H.chipClick(t);
      if (t.id === 'epgo') dispatch({ t: 'start' });
      else if (t.id === 'eppa') dispatch({ t: 'pause' });
      else if (t.id === 'eprs') dispatch({ t: 'resume' });
      else if (t.id === 'epsp') { copied = ''; note = ''; dispatch({ t: 'stop' }); }
      else if (t.id === 'epcfg') { var d = $('rc'); d.open = true; d.scrollIntoView({ block: 'nearest' }); var inp = $('rce'); if (inp) inp.focus(); }
      else if (t.id === 'epad') adopt();
      else if (t.dataset && t.dataset.mv) playMove(t.dataset.mv);
    });
    box.addEventListener('change', function (e) {
      var t = e.target;
      if (t.id === 'epm') H.RC.setMode(t.value);
      else if (t.id === 'epcap') { S.cap = t.value === 'max' ? 'max' : Number(t.value); save(); render(); }
      else if (t.id === 'epre') { S.region = t.checked; save(); if (!S.region) note = '不限区域时候选点可能在当前视野之外,可点「视角:全盘」查看'; render(); }
      else if (t.id === 'epbl') { S.best = t.checked; save(); if (!S.best && myGhost && H.getGhost() === myGhost) { H.setGhost([]); myGhost = null; H.draw(); } else if (S.best && curLive()) { autoGhost(H.cur()); H.draw(); } render(); }
      else if (t.id === 'epmo') switchModel(t.value);
    });
    // hovering a table row shows that line on the board the same way hovering its candidate dot does (the viewer's hover preview)
    var tb = $('eptb'), hov = null;
    tb.addEventListener('mouseover', function (e) { var tr = e.target.closest && e.target.closest('tr[data-i]'); if (!tr || tr === hov) return; hov = tr; var rows = C.parseAN((curLive() || {}).an), r = rows[Number(tr.dataset.i)]; if (r) H.hover(r.pv.map(H.fromGtp).filter(Boolean)); });
    tb.addEventListener('mouseleave', function () { if (hov) { hov = null; H.clearHover(); } });
    $('epnet').addEventListener('toggle', function () { if ($('epnet').open) $('epnl').innerHTML = netRows(); });
    var bar = document.querySelector('.bar');
    if (bar) { var bt = document.createElement('button'); bt.id = 'bep'; bt.textContent = '推演'; bt.title = '用 KataGo 继续推演这个局面(终点会自动显示)'; bt.onclick = function () { S.open = !S.open; save(); render(); }; bar.appendChild(bt); }
  }
  // 走: play the candidate as a trial node (the viewer's RC.click: region check, suicide check, not added to the tree) and, if a search was active, continue there after a short pause
  function playMove(mv) {
    var q = C.gtpToXY(mv), before = H.cur(), active = st.phase !== 'idle';
    if (!q) return;
    H.RC.click(q[0], q[1], { noAnalyze: true });
    if (H.cur() !== before && active) follow.call(function () { dispatch({ t: 'start' }); });
  }

  function init(host) {
    H = host;
    if (!$('ep') || !C || !NET) return;
    build();
    H.RC.on(function () { loadModels(); render(); });
    NET.subscribe(function () { if (netDirty) return; netDirty = true; setTimeout(function () { netDirty = false; if (box && $('epnetc')) { $('epnetc').textContent = String(NET.log.length); if ($('epnet').open) $('epnl').innerHTML = netRows(); } }, 400); });
    root.addEventListener('pagehide', function () { Object.keys(jobs).forEach(function (k) { jobs[k].ctl.abort(); }); }); // closing the page closes the stream; the bridge notices and stops the search
    render();
    loadModels();
  }
  // called by the viewer's go(): any navigation cancels a running search at once, so no search is left behind
  function onGo() { copied = ''; note = ''; dispatch({ t: 'navigate' }); }

  root.EnginePanel = { init: init, onGo: onGo };
})(typeof self !== 'undefined' ? self : this);
