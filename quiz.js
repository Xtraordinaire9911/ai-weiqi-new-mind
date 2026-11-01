/* quiz.js: the training view of the joseki viewer.
 * Logic lives in quiz_core.js (window.QC). This file only does the screens, the clicks and the single localStorage key.
 * It borrows the viewer canvas: while the view is open it swaps the viewer globals (cur, view, tree, col ...) for a clone of the
 * question position, so drawBoard() draws stones, coordinates and the crop exactly like the viewer. Closing the view restores them. */
(function () {
  'use strict';
  const QC = window.QC;
  if (!QC || !window.LIB || typeof drawBoard !== 'function') return;

  const KEY = 'josekiapp.quiz.v1'; // the only place the progress is kept
  const $id = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const pct = v => (v == null ? '-' : Math.round(v * 100) + '%');
  const BUCKET_NAME = { all: '全部', open: '开局', mid: '中段', deep: '深入' };
  const BUCKET_HINT = { all: '', open: '前4手内', mid: '5到10手', deep: '11手以上' };

  // ---------- progress in localStorage (every access guarded) ----------
  let lsOk = true;
  function load() {
    try { const t = localStorage.getItem(KEY); if (t) return QC.sanitize(JSON.parse(t)); } catch (e) { lsOk = false; }
    return QC.defaultProgress();
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(P)); } catch (e) { lsOk = false; } }
  let P = load();

  // ---------- collections and questions (built on first use) ----------
  const infos = new Map();
  function infoOf(c) {
    let i = infos.get(c.id);
    if (!i) {
      const tree = QC.parseSgf(c.sgf);
      i = { col: c, tree, qs: tree ? QC.extractQuestions(c, tree) : [], view: tree ? bbox(tree) : null };
      infos.set(c.id, i);
    }
    return i;
  }
  const allInfos = () => LIB.map(infoOf).filter(i => i.qs.length);
  // questions of a card ('all' and 'due' span every collection), narrowed by the depth filter
  const poolOf = kind => (kind === 'all' || kind === 'due' ? allInfos().flatMap(i => i.qs) : infos.get(kind).qs).filter(q => S.bucket === 'all' || q.bucket === S.bucket);

  // ---------- state ----------
  const S = { on: false, phase: 'home', bucket: 'all', saved: null, cards: [], note: '', ask: null, hv: null };
  const mount = (cls, parent, before) => { const d = document.createElement('div'); d.id = cls; before ? parent.insertBefore(d, before) : parent.appendChild(d); return d; };
  const main = cv.parentNode, section = document.querySelector('section');
  const elTop = mount('qzt', main, cv), elBot = mount('qzb', main, cv.nextSibling), elSide = mount('qzp', section, section.firstChild);

  const css = `
body.qz .bar,body.qz #cap,body.qz #info,body.qz #path{display:none!important}
body.qz aside{pointer-events:none;opacity:.45}
body.qz section>*:not(#qzp):not(#cm){display:none!important}
body.qzh #cv,body:not(.qz) #qzt,body:not(.qz) #qzb,body:not(.qz) #qzp{display:none}
#qzt,#qzb{max-width:min(80vh,100%);margin:0 auto}body.qzh #qzt{max-width:none}
.qz-head{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px}.qz-head h3{margin:0}.qz-head .sp{flex:1}
.qz-flt{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:6px 0 10px;font-size:13px}.qz-flt span{color:var(--mu)}
.qz-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
.qz-card{background:var(--pn);border:1px solid var(--bd);border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:4px}
.qz-card.dim{opacity:.55}.qz-card.hot{border-left:4px solid var(--ac)}
.qz-t{font-weight:600;line-height:1.35}.qz-s{font-size:12px;color:var(--mu)}
.qz-n{font-size:12px;color:var(--mu)}.qz-n b{font-size:26px;color:var(--fg);margin-right:3px}
.qz-m{display:grid;grid-template-columns:1fr 1fr;gap:2px 8px;font-size:12px;color:var(--mu)}.qz-m b{color:var(--fg)}
.qz-go{margin-top:4px;color:var(--ac);cursor:pointer;text-decoration:underline;font-weight:600}.qz-go.off{color:var(--mu);text-decoration:none;cursor:default}
.qz-set{margin:14px 0 8px;border:1px solid var(--bd);border-radius:6px;padding:6px 10px;background:var(--pn)}.qz-set summary{cursor:pointer}
.qz-set label{display:inline-block;margin:6px 14px 2px 0;font-size:13px}.qz-set input[type=number]{width:60px}
.qz-io{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:8px 0;font-size:12px;color:var(--mu)}
.qz-note{margin:8px 0;padding:6px 10px;border-radius:6px;background:rgba(224,160,96,.15);border:1px solid var(--ac);font-size:13px}
.qz-qh{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 6px;font-size:13px}
.qz-side{font-weight:700;font-size:16px;padding:1px 10px;border-radius:12px;border:1px solid var(--bd)}
.qz-side.b{background:#111;color:#fff}.qz-side.w{background:#f4f4f4;color:#111}
.qz-tag{padding:0 8px;border-radius:10px;border:1px solid var(--bd);color:var(--mu);font-size:12px}.qz-tag.x{border-color:#8e44ad;color:#8e44ad;font-weight:600}
.qz-cap{margin:6px 0;font-size:12px;color:var(--mu);text-align:center}
.qz-btns{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin:8px 0}
.qz-btns .pri{background:var(--ac);color:#fff;border-color:var(--ac)}.qz-btns button:disabled{opacity:.5;cursor:default}
.qz-res{padding:8px 10px;border-radius:6px;font-size:16px;font-weight:700;margin:0 0 8px;border:1px solid}
.qz-res.ok{color:var(--gd);border-color:var(--gd);background:rgba(46,139,87,.1)}.qz-res.bad{color:var(--rd);border-color:var(--rd);background:rgba(192,57,43,.1)}.qz-res.skip{color:var(--ac);border-color:var(--ac)}
.qz-acc{margin:6px 0;line-height:1.9;font-size:13px}.qz-pill{display:inline-block;margin:0 4px 4px 0;padding:0 8px;border-radius:10px;border:2px solid var(--bd)}
.qz-rules{line-height:1.75;font-size:13px}.qz-rules h4{margin:0 0 6px}.qz-rules ol{margin:0;padding-left:20px}
`;
  document.head.appendChild(Object.assign(document.createElement('style'), { textContent: css }));

  // ---------- helpers for the viewer canvas ----------
  const chain = ps => { let up = null; return ps.map(p => (up = { p, c: [], up })).pop(); }; // viewer-style nodes from QC.viewPath output
  function vbOf(i) { // video ids, same rule as open_() in index.html (the cards use them for the time links)
    if (!i.col.vb) i.col.vb = ((i.tree.p.PC || [''])[0].match(/BV\w+/g)) || i.col.videos.map(v => v.bvid);
  }
  // put the position of q on the viewer canvas, transformed by sym; the crop rectangle is transformed with it
  function showBoard(q, sym) {
    const i = infos.get(q.cid);
    vbOf(i);
    col = i.col; tree = i.tree; viewMode = 1; view = QC.symRect(sym, i.view);
    cur = chain(QC.viewPath(q.node, sym, q.side));
    sel = 0; hot = []; ghost = []; hoverG = []; hoverB = null; pinAI = null; ladderMsg = '';
    drawBoard();
  }
  const nameOf = q => infos.get(q.cid).col.name;
  const sideName = s => (s === 1 ? '黑先' : '白先');

  // the same card layout as panel() in index.html, so chips and video links keep working through the existing #cm handler
  function fillCards(co) {
    const box = $id('cm'); box.innerHTML = '';
    co.split(/\n(?=【)/).filter(s => s.trim()).forEach(s => {
      const mt = /^【([^】]+)】/.exec(s), h = mt ? mt[1].replace(/\s*@\S+/, '') : '', cls = h.includes('要点') ? 'kp' : h.includes('周边') ? 'ctx' : h.includes('AI') ? 'ai' : '';
      let body = ((mt && /@\S+/.test(mt[1]) ? '@' + /@(\S+)/.exec(mt[1])[1] + ' ' : '') + (mt ? s.slice(mt[0].length) : s)).trim();
      body = body.replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/⟨([^⟩]+)⟩/g, (a, t) => { const ps = t.trim().split(/\s+/); return ps.length > 1 ? `<span class="chip pv" data-pv="${ps.join(' ')}">${ps[0]}…${ps.length}手</span>` : `<span class="chip" data-pv="${ps[0]}">${ps[0]}</span>`; })
        .replace(/@(?:(\d+)\|)?(\d+):(\d\d)/g, (a, v, mm, ss) => `<span class="t" data-v="${v || 0}" data-t="${+mm * 60 + +ss}">▶${v ? '视频' + (+v + 1) + ' ' : ''}${mm}:${ss}</span>`);
      box.insertAdjacentHTML('beforeend', `<div class="card ${cls}">${h ? `<h5>${h}</h5>` : ''}${body}</div>`);
    });
  }

  // ---------- enter and leave ----------
  function enter() {
    if (S.on) return;
    S.saved = { cur, tree, col, view, viewMode, sel, hot, ghost, pinAI, ladderMsg, click: cv.onclick, move: cv.onmousemove, leave: cv.onmouseleave, out: cv.onmouseout, key: window.onkeydown };
    S.on = true; document.body.classList.add('qz');
    tip.style.display = 'none'; hoverG = []; hoverB = null;
    cv.onclick = onClick; cv.onmousemove = onMove; cv.onmouseleave = cv.onmouseout = onLeave; window.onkeydown = onKey;
    home();
  }
  function exit() {
    if (!S.on) return;
    const s = S.saved;
    S.on = false; S.phase = 'home';
    cur = s.cur; tree = s.tree; col = s.col; view = s.view; viewMode = s.viewMode; sel = s.sel; hot = s.hot; ghost = s.ghost; pinAI = s.pinAI; ladderMsg = s.ladderMsg;
    cv.onclick = s.click; cv.onmousemove = s.move; cv.onmouseleave = s.leave; cv.onmouseout = s.out; window.onkeydown = s.key;
    document.body.classList.remove('qz', 'qzh');
    elTop.innerHTML = elBot.innerHTML = elSide.innerHTML = '';
    draw();
  }

  // ---------- home screen ----------
  function cardsData() {
    const now = Date.now(), all = allInfos(), cards = [], sa = QC.statsOf(poolOf('all'), P, P.st, now);
    cards.push({ kind: 'due', title: '今日到期', sub: '按记忆曲线复习', st: sa, hot: sa.due > 0, due: true });
    cards.push({ kind: 'all', title: '全部定式(混合)', sub: `${all.length} 个定式交错出题`, st: sa });
    all.forEach(i => cards.push({ kind: i.col.id, title: i.col.name, sub: `${i.col.sourceName || ''} · ${i.col.series || ''}`, st: QC.statsOf(poolOf(i.col.id), P, P.st, now) }));
    return cards;
  }
  function cardHtml(c, idx) {
    const st = c.st, n = c.due ? st.due : st.total, go = c.due ? st.due > 0 : st.total > 0;
    return `<div class="qz-card${go ? '' : ' dim'}${c.hot ? ' hot' : ''}"><div class="qz-t">${esc(c.title)}</div><div class="qz-s">${esc(c.sub)}</div>`
      + `<div class="qz-n"><b>${n}</b>${c.due ? '题待复习' : '题'}</div>`
      + `<div class="qz-m"><span>已训练 <b>${st.trained}</b></span><span>正确率 <b>${pct(st.acc)}</b></span><span>已掌握 <b>${st.mastered}</b></span><span>${c.due ? '新题 ' : '到期 '}<b>${c.due ? st.fresh : st.due}</b></span></div>`
      + (go ? `<a class="qz-go" data-go="${idx}">开始训练</a>` : `<span class="qz-go off">${c.due ? '今天没有到期的题' : '没有可用的题'}</span>`) + '</div>';
  }
  function home() {
    S.phase = 'home'; S.hv = null; document.body.classList.add('qz', 'qzh');
    S.cards = cardsData();
    const used = QC.newToday(P, Date.now()), due = S.cards[0].st.due, st = P.st;
    const flt = ['all', 'open', 'mid', 'deep'].map(b => `<button data-b="${b}" class="${S.bucket === b ? 'on' : ''}" title="${BUCKET_HINT[b]}">${BUCKET_NAME[b]}${BUCKET_HINT[b] ? '(' + BUCKET_HINT[b] + ')' : ''}</button>`).join('');
    elTop.innerHTML = `<div class="qz-head"><h3>实战训练</h3><span>今日到期 <b>${due}</b> 题 · 今日新题 <b>${used}</b>/${st.limit}</span><span class="sp"></span><button data-a="exit">退出训练</button></div>`
      + (lsOk ? '' : '<div class="qz-note">无法写入浏览器存储,本次进度只在当前页面有效,请用下面的“导出进度”保存。</div>')
      + (S.note ? `<div class="qz-note">${esc(S.note)}</div>` : '')
      + `<div class="qz-flt"><span>深度</span>${flt}</div><div class="qz-grid">${S.cards.map(cardHtml).join('')}</div>`
      + `<details class="qz-set" open><summary>设置</summary>`
      + `<label>前 <input type="number" min="1" max="5" id="qs-n" value="${st.topN}"> 名 AI 推荐算对</label>`
      + `<label><input type="checkbox" id="qs-t"${st.teacher ? ' checked' : ''}> 老师讲过的着法也算对</label>`
      + `<label><input type="checkbox" id="qs-x"${st.transform ? ' checked' : ''}> 随机翻转/旋转棋盘</label>`
      + `<label><input type="checkbox" id="qs-e"${st.extra ? ' checked' : ''}> 答对后出附加题</label>`
      + `<label>每日新题上限 <input type="number" min="1" max="200" id="qs-l" value="${st.limit}"></label></details>`
      + `<div class="qz-io"><button data-a="export">导出进度</button><button data-a="import">导入进度</button><button data-a="reset">重置进度</button><span>进度只保存在本浏览器</span>`
      + `<input type="file" id="qz-file" accept=".json,application/json" hidden></div>`
      + (S.confirm ? `<div class="qz-note">${esc(S.confirm.text)} <button data-a="yes">确定</button> <button data-a="no">取消</button></div>` : '');
    elBot.innerHTML = '';
    elSide.innerHTML = `<div class="qz-rules"><h4>训练规则</h4><ol>`
      + `<li>每个分叉点、每个带 AI 评估的局面都是一道题,只考这一手。</li>`
      + `<li>点在 AI 推荐的前 ${st.topN} 名里算对(比最优差超过 3 目的不算);开着“老师讲过的着法也算对”时,老师的着法只要不比最优差 1 目以上也算对。</li>`
      + `<li>为防止死记,棋盘可能被随机翻转或旋转;答完后按原方向显示讲解,讲解里的坐标按原图。</li>`
      + `<li>复习按记忆曲线:1、2、4、7、15、30 天。答错回到第 1 档,连续两次到达最高档视为已掌握,不再出现。</li>`
      + `<li>每天先复习到期的题,再学新题(默认 20 道)。刚答过的题 10 分钟内不会重复,答错的题除外。</li>`
      + `<li>答对后可能出现附加题:沿最佳变化继续考下一手,最多两道,不计入记忆曲线。</li>`
      + `</ol></div>`;
    $id('cm').innerHTML = '';
    S.note = ''; // a note is shown once
  }

  // ---------- sessions ----------
  function start(idx) {
    const c = S.cards[idx]; if (!c) return;
    const ses = QC.buildSession(poolOf(c.kind), P, P.st, Date.now(), { mix: c.kind === 'all' || c.kind === 'due', dueOnly: c.kind === 'due' });
    if (!ses.list.length) {
      S.note = c.kind === 'due' ? '现在没有到期的题。' : `现在没有可练的题:到期的已经做完,今天的新题也到了上限(${P.st.limit})。可以在设置里调高上限。`;
      return home();
    }
    S.note = ''; S.queue = ses.list; S.i = 0; S.tally = { n: 0, ok: 0 }; S.retried = new Set(); S.seen = new Set();
    advance();
  }
  function advance() {
    if (S.i >= S.queue.length) return finish();
    startQ(S.queue[S.i++], 0);
  }
  function finish() {
    S.phase = 'end'; S.hv = null; ghost = []; hot = [];
    const t = S.tally;
    document.body.classList.add('qzh');
    elTop.innerHTML = `<div class="qz-head"><h3>本次训练完成</h3></div><p>共答 <b>${t.n}</b> 题,答对 <b>${t.ok}</b> 题(${t.n ? Math.round(100 * t.ok / t.n) : 0}%)。答错的题会在下次到期时再出现。</p><div class="qz-btns"><button class="pri" data-a="home">回到首页</button></div>`;
    elBot.innerHTML = ''; elSide.innerHTML = ''; $id('cm').innerHTML = '';
  }

  // ---------- one question ----------
  function startQ(q, extra) {
    S.q = q; S.extra = extra; S.phase = 'ask'; S.ans = null; S.fu = null; S.hv = null; S.rec = null;
    S.sym = QC.randomSym(Math.random, P.st.transform);
    document.body.classList.remove('qzh');
    const again = !extra && S.seen.has(q.id); if (!extra) S.seen.add(q.id);
    const hd = `<div class="qz-qh"><span class="qz-side ${q.side === 1 ? 'b' : 'w'}">${q.side === 1 ? '●' : '○'} ${sideName(q.side)}</span>`
      + (extra ? `<span class="qz-tag x">附加题 ${extra}/2</span>` : `<span>第 ${S.i}/${S.queue.length} 题</span>`)
      + `<span>${esc(nameOf(q))}</span><span class="qz-tag">${BUCKET_NAME[q.bucket]}</span>${again ? '<span class="qz-tag">重做</span>' : ''}</div>`;
    elTop.innerHTML = hd;
    elSide.innerHTML = `<div class="qz-rules"><h4>${extra ? '附加题' : '请选择一手'}</h4>${extra ? '这是上一题答对后接着考的下一手,不计入记忆曲线。' : '只考这一手:点在 AI 推荐的前几名或老师讲过的着法上就算对。'}<br><br>点击棋盘上的空点作答。已有棋子的点不能点。</div>`;
    $id('cm').innerHTML = '';
    elBot.innerHTML = `<div class="qz-cap">${S.sym ? `本题棋盘已随机变换(${QC.SYM_NAMES[S.sym]}),坐标标签按当前棋盘;答完后会还原。` : '棋盘保持原方向。'}</div>`
      + `<div class="qz-btns"><button data-a="show">看答案(算错)</button><button data-a="home">回到首页</button></div>`;
    if (extra) elBot.querySelector('[data-a=show]').textContent = '看答案';
    showBoard(q, S.sym);
  }

  // click -> point in displayed coordinates (null outside the visible board)
  function rawPoint(e) {
    const r = cv.getBoundingClientRect(), V = Vnow, span = Math.max(V.x1 - V.x0, V.y1 - V.y0), m = r.width / (span + 1.6);
    const x = Math.round((e.clientX - r.left - .8 * m) / m) + V.x0, y = Math.round((e.clientY - r.top - .8 * m) / m) + V.y0;
    return x < V.x0 || x > V.x1 || y < V.y0 || y > V.y1 || x < 0 || y < 0 || x >= 19 || y >= 19 ? null : [x, y];
  }
  function pick(e) { const p = rawPoint(e); return p && !rpOf(cur).b[p[0]][p[1]] ? p : null; } // occupied points are ignored
  function onMove(e) {
    if (S.phase !== 'ask') return;
    const p = pick(e);
    if (String(p) !== String(S.hv)) { S.hv = p; drawBoard(); }
  }
  function onLeave() { if (S.hv) { S.hv = null; drawBoard(); } }
  function onClick(e) {
    if (S.phase === 'ask') { const p = pick(e); if (p) answer(p); return; }
    if (S.phase === 'fb') { // click an accepted move to show its AI line, click again to hide it
      const p = rawPoint(e), a = p && S.acc.find(x => { const q = QC.pt(x.m); return q[0] === p[0] && q[1] === p[1]; });
      ghost = a && a.pv.length && !(ghost.length && ghost.join() === a.pv.map(fromGtp).join()) ? a.pv.map(fromGtp).filter(Boolean) : [];
      drawBoard();
    }
  }
  function onKey(e) {
    const t = e.target.tagName;
    if (t === 'INPUT' || t === 'SELECT' || t === 'TEXTAREA' || t === 'BUTTON') return;
    if (S.phase === 'fb' && (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowRight')) { e.preventDefault(); next(); }
    else if (e.key === 'Escape') { S.phase === 'home' ? exit() : home(); }
  }

  function answer(p) {
    const o = QC.symPoint(QC.symInverse(S.sym), p), mv = QC.sg(o[0], o[1]), r = QC.judge(S.q, P.st, mv);
    S.ans = { mv, ok: r.ok, gave: false };
    record(r.ok);
    feedback();
  }
  function giveUp() { S.ans = { mv: null, ok: false, gave: true }; record(false); feedback(); }
  function record(ok) {
    if (S.extra) return; // follow-up questions never touch the boxes
    S.rec = QC.grade(P, S.q.id, ok, Date.now());
    S.tally.n++; if (ok) S.tally.ok++;
    if (!ok && !S.retried.has(S.q.id)) { S.retried.add(S.q.id); S.queue.push(S.q); } // ask a wrong one once more at the end of the session
    save();
  }

  // feedback: back to the original orientation, accepted moves as dots, the node's commentary on the right
  function feedback() {
    const q = S.q, a = S.ans;
    S.phase = 'fb'; S.hv = null;
    S.acc = QC.acceptedOf(q, P.st);
    S.fu = a.ok && P.st.extra && S.extra < 2 ? QC.followUp(q, a.mv, infos.get(q.cid).qs, P.st) : null; // up to two follow-ups after a correct answer
    showBoard(q, 0);
    elSide.innerHTML = fbHtml();
    fillCards((q.node.p.C || [''])[0]);
    elBot.innerHTML = `<div class="qz-cap">${S.sym ? `已还原为原始方向(答题时是“${QC.SYM_NAMES[S.sym]}”),讲解里的坐标按原图。` : '棋盘保持原方向。'} 点击棋盘上的候选点可看 AI 变化。</div>`
      + `<div class="qz-btns"><button class="pri" data-a="next">${S.fu ? '附加题 ▶' : (S.i >= S.queue.length ? '完成' : '下一题')}</button>`
      + (S.fu ? '<button data-a="skipfu">跳过附加题</button>' : '')
      + (S.extra ? '' : '<button data-a="master">标记为已掌握</button>')
      + '<button data-a="home">回到首页</button></div>';
  }
  const lossTxt = l => (l == null ? '老师(无AI数据)' : l > -0.05 ? '最优' : l.toFixed(1) + '目');
  const lossCol = l => (l == null ? '#2d6cdf' : l > -0.3 ? '#2e8b57' : l > -1.5 ? '#e6a028' : '#c0392b');
  function fbHtml() {
    const q = S.q, a = S.ans, cls = a.gave ? 'skip' : a.ok ? 'ok' : 'bad', title = a.gave ? '已看答案,按答错计' : a.ok ? '回答正确' : '回答错误';
    let h = `<div class="qz-res ${cls}">${title}</div>`;
    if (a.mv) {
      const e = q.ai.find(x => x.m === a.mv), isT = q.teacher.some(t => t.m === a.mv), g = QC.gtp(QC.pt(a.mv));
      h += `<div>你的选择:<b>${g}</b>${e ? ` · ${e.loss > -0.05 ? 'AI 局部最优' : '比局部最优差 ' + (-e.loss).toFixed(1) + ' 目'}` : ' · AI 没有评估这一手'}${isT ? ' · 老师讲过' : ''}</div>`;
    }
    const V = infos.get(q.cid).view, inView = p => p[0] >= V.x0 && p[0] <= V.x1 && p[1] >= V.y0 && p[1] <= V.y1;
    h += `<div class="qz-acc">可接受的着法(${S.acc.length}):<br>` + S.acc.map(x => `<span class="qz-pill" style="border-color:${lossCol(x.loss)}"><b>${QC.gtp(QC.pt(x.m))}</b> ${lossTxt(x.loss)}${x.tags.includes('ai') ? ' · AI' : ''}${x.tags.includes('teacher') && x.loss != null ? ' · 老师' : ''}${inView(QC.pt(x.m)) ? '' : ' · 盘上未画(区域外)'}</span>`).join('') + '</div>';
    if (S.extra) h += '<div class="qz-s">附加题不计入记忆曲线。</div>';
    else if (S.rec) {
      const r = S.rec, d = r.due - QC.dayIndex(Date.now());
      h += `<div class="qz-s">记忆档位 ${r.b + 1}/${QC.INTERVALS.length} · ` + (r.mst ? '已掌握,不再出现' : d <= 0 ? '稍后会再做一次' : d === 1 ? '明天复习' : d + ' 天后复习') + '</div>';
    }
    return h;
  }
  function next() {
    if (S.phase !== 'fb') return;
    if (S.fu) return startQ(S.fu, S.extra + 1);
    advance();
  }

  // ---------- overlay drawn on top of drawBoard() (hook in index.html) ----------
  function over(o) {
    if (!S.on) return;
    const g2 = cv.getContext('2d'), X = o.X, Y = o.Y, m = o.m, V = o.V, vis = p => !!p && p[0] >= V.x0 && p[0] <= V.x1 && p[1] >= V.y0 && p[1] <= V.y1;
    g2.save(); g2.textAlign = 'center'; g2.textBaseline = 'middle';
    if (S.phase === 'ask' && vis(S.hv)) { // preview stone under the pointer
      g2.globalAlpha = .5; g2.beginPath(); g2.arc(X(S.hv[0]), Y(S.hv[1]), m * .47, 0, 7); g2.fillStyle = o.nc === 1 ? '#111' : '#f4f4f4'; g2.fill(); g2.strokeStyle = '#222'; g2.lineWidth = 1; g2.stroke();
    }
    if (S.phase === 'fb') {
      const a = S.ans;
      if (!ghost.length) S.acc.forEach(x => { // accepted moves, same colour language as the viewer's AI dots (green / orange / red by loss, blue dashed ring = teacher move)
        const p = QC.pt(x.m); if (!vis(p)) return;
        const px = X(p[0]), py = Y(p[1]), c = lossCol(x.loss);
        g2.globalAlpha = .55; g2.beginPath(); g2.arc(px, py, m * .38, 0, 7); g2.fillStyle = o.nc === 1 ? '#111' : '#f4f4f4'; g2.fill(); g2.globalAlpha = 1;
        g2.lineWidth = 3.5; g2.strokeStyle = c; g2.stroke();
        if (x.tags.includes('teacher')) { g2.save(); g2.setLineDash([5, 4]); g2.strokeStyle = '#2d6cdf'; g2.lineWidth = 2.5; g2.beginPath(); g2.arc(px, py, m * .47, 0, 7); g2.stroke(); g2.restore(); }
        const t = x.loss == null ? '老师' : x.loss > -0.05 ? '最优' : x.loss.toFixed(1);
        g2.font = `bold ${m * .3}px sans-serif`; g2.lineWidth = 3; g2.strokeStyle = 'rgba(255,255,255,.9)'; g2.strokeText(t, px, py + m * .66); g2.fillStyle = '#000'; g2.fillText(t, px, py + m * .66);
      });
      const u = a && a.mv ? QC.pt(a.mv) : null;
      if (vis(u)) { // the user's move: square mark, green when accepted, red otherwise
        const px = X(u[0]), py = Y(u[1]);
        if (!S.acc.some(x => x.m === a.mv)) { g2.globalAlpha = .55; g2.beginPath(); g2.arc(px, py, m * .38, 0, 7); g2.fillStyle = o.nc === 1 ? '#111' : '#f4f4f4'; g2.fill(); g2.globalAlpha = 1; }
        g2.lineWidth = 3.5; g2.strokeStyle = a.ok ? '#2e8b57' : '#c0392b'; g2.strokeRect(px - m * .5, py - m * .5, m, m);
        g2.font = `bold ${m * .3}px sans-serif`; g2.lineWidth = 3; g2.strokeStyle = 'rgba(255,255,255,.9)'; g2.strokeText('你', px, py - m * .7); g2.fillStyle = a.ok ? '#2e8b57' : '#c0392b'; g2.fillText('你', px, py - m * .7);
      }
    }
    g2.restore();
  }

  // ---------- buttons, settings, export, import ----------
  function download(name, text) {
    const a = document.createElement('a'), url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000);
  }
  function readSettings() {
    P.st = QC.norm({ topN: $id('qs-n').value, limit: $id('qs-l').value, teacher: $id('qs-t').checked, transform: $id('qs-x').checked, extra: $id('qs-e').checked });
    save(); home();
  }
  function act(a) {
    if (a === 'exit') exit();
    else if (a === 'home') { S.confirm = null; home(); }
    else if (a === 'show') giveUp();
    else if (a === 'next') next();
    else if (a === 'skipfu') { S.fu = null; advance(); }
    else if (a === 'master') { QC.markMastered(P, S.q.id, Date.now()); save(); const b = elBot.querySelector('[data-a=master]'); b.textContent = '已标记为已掌握'; b.disabled = true; }
    else if (a === 'export') { const d = new Date(), z = n => String(n).padStart(2, '0'); download(`josekiapp-quiz-${d.getFullYear()}${z(d.getMonth() + 1)}${z(d.getDate())}.json`, QC.exportProgress(P)); S.note = '已导出进度文件。'; home(); }
    else if (a === 'import') $id('qz-file').click();
    else if (a === 'reset') { S.confirm = { text: '确定清空全部训练进度和设置吗?此操作不能撤销。', yes: 'reset' }; home(); }
    else if (a === 'yes') { if (S.confirm && S.confirm.yes === 'reset') { P = QC.defaultProgress(); save(); S.note = '训练进度已清空。'; } S.confirm = null; home(); }
    else if (a === 'no') { S.confirm = null; home(); }
  }
  async function importFile(f) {
    try {
      const r = QC.importProgress(await f.text(), P, 'merge');
      if (r.ok) { P = r.P; save(); S.note = `已导入 ${r.count} 条记录(与现有进度合并,同一题取最近一次答题的记录)。`; } else S.note = '导入失败:' + r.error;
    } catch (e) { S.note = '导入失败:无法读取文件'; }
    home();
  }
  const root = document.body;
  root.addEventListener('click', e => {
    if (!S.on) return;
    const t = e.target.closest ? e.target.closest('[data-a],[data-go],[data-b]') : null;
    if (!t || !(elTop.contains(t) || elBot.contains(t))) return;
    if (t.dataset.a) act(t.dataset.a);
    else if (t.dataset.go !== undefined) start(+t.dataset.go);
    else if (t.dataset.b) { S.bucket = t.dataset.b; home(); }
  });
  root.addEventListener('change', e => {
    if (!S.on) return;
    if (e.target.id === 'qz-file') { if (e.target.files[0]) importFile(e.target.files[0]); e.target.value = ''; }
    else if (/^qs-/.test(e.target.id)) readSettings();
  });
  $id('bq').onclick = enter;
  window.QZ = { get on() { return S.on; }, over, enter, exit };
})();
