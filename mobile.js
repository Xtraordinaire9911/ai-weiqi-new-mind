// Mobile edition of the viewer: phone and tablet layout, touch equivalents of the hover features, and the https notice for the engine card.
// It only reads and rearranges the page. It has no network code (see tests/privacy.test.js); the service worker lives in sw.js and is registered by pwa.js.
// Desktop (wide landscape windows) keeps the original three columns: every rule below sits inside a media query for the phone and tablet modes.
(function () {
  'use strict';

  // ---------------------------------------------------------------- layout modes
  // A: stacked, for portrait windows up to 1100 px wide (phones, tablets, foldables): sticky board on top, commentary below, fixed control bar at the bottom.
  // B: side by side, for landscape windows up to 1199 px wide: board on the left (as tall as the window), panel on the right.
  // Everything else (wide landscape) is the original desktop layout.
  const QA = '(orientation:portrait) and (max-width:1100px)';
  const QB = '(orientation:landscape) and (max-width:1199px)';
  const MODE = '(orientation:portrait) and (max-width:1100px),(orientation:landscape) and (max-width:1199px)';

  const css = `
:root{--sat:env(safe-area-inset-top,0px);--sab:env(safe-area-inset-bottom,0px);--sal:env(safe-area-inset-left,0px);--sar:env(safe-area-inset-right,0px);--barh:56px}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
@supports (height:100dvh){body{height:100dvh}}
.m-only{display:none}
#mtoast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(var(--barh) + var(--sab) + 12px);z-index:60;max-width:min(92vw,420px);padding:8px 14px;border-radius:18px;background:rgba(20,20,20,.88);color:#fff;font-size:.9rem;line-height:1.4;text-align:center;pointer-events:none;opacity:0;transition:opacity .15s}
#mtoast.on{opacity:1}#mtoast button{pointer-events:auto}
#mtoast.act{pointer-events:auto}
@media ${MODE}{
  :root{--bs:min(100vw,calc(100dvh - var(--barh) - var(--sab) - var(--sat) - 220px),64dvh)}
  html{font-size:100%}
  body{font-size:.9375rem;overflow-x:hidden;padding-left:var(--sal);padding-right:var(--sar);min-width:0}
  .m-only{display:inline-flex}
  /* touch targets and the iOS zoom rule */
  button,select,summary,.chip,.t,#path span,#list div{min-height:44px}
  button{min-width:44px;padding:6px 10px}
  input,select,textarea,#rc select,#rc input[type=text],#rc input[type=password],#ep select,#ep textarea{font-size:max(16px,1rem)!important}
  input[type=checkbox]{width:22px;height:22px;vertical-align:middle}
  #list div{display:flex;align-items:center;padding:6px 10px}
  .chip,.t{display:inline-flex;align-items:center;padding:4px 10px;margin:3px 2px}
  .card{font-size:1rem}.card h5{font-size:.8rem}
  #path{flex-wrap:nowrap;overflow-x:auto;font-size:.8rem;padding-bottom:4px;-webkit-overflow-scrolling:touch}#path span{flex:none;display:inline-flex;align-items:center;padding:0 12px}
  #info{font-size:.9rem;padding:2px 8px}
  #ver,#prog,.qz-s,.qz-n,.qz-m,.qz-io,.qz-cap{font-size:.8rem!important}
  footer{font-size:.75rem;padding-bottom:calc(3px + var(--sab))}
  img,canvas,table{max-width:100%}
  section,main,aside{overflow-wrap:anywhere}
  /* the board: no scroll, zoom or text selection while a finger is on it */
  canvas{touch-action:none;-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;-webkit-tap-highlight-color:transparent;width:var(--bs);max-width:100%;max-height:none;cursor:default}
  /* bottom control bar */
  .bar{position:fixed;left:0;right:0;bottom:0;z-index:40;margin:0;gap:4px;flex-wrap:nowrap;justify-content:stretch;padding:6px calc(8px + var(--sar)) calc(6px + var(--sab)) calc(8px + var(--sal));background:var(--pn);border-top:1px solid var(--bd);box-shadow:0 -2px 8px rgba(0,0,0,.08)}
  .bar>button{flex:1 1 0;min-width:44px;min-height:44px;padding:4px 2px;font-size:.8rem;display:inline-flex;align-items:center;justify-content:center;text-align:center;white-space:normal;line-height:1.15;overflow:hidden}
  .bar>button.on{background:var(--ac);color:#fff;border-color:var(--ac)}
  #mmore{position:fixed;left:0;right:0;bottom:calc(var(--barh) + var(--sab));z-index:39;display:none;grid-template-columns:repeat(auto-fit,minmax(104px,1fr));gap:6px;padding:10px calc(10px + var(--sar)) 10px calc(10px + var(--sal));background:var(--pn);border-top:1px solid var(--bd);box-shadow:0 -4px 14px rgba(0,0,0,.18);max-height:50dvh;overflow:auto}
  body.mmore #mmore{display:grid}
  #mmore button{display:flex!important;align-items:center;justify-content:center;min-height:48px}
  /* collection list and the compute card: a drawer */
  aside{position:fixed;z-index:50;background:var(--pn);max-height:none;visibility:hidden;transition:transform .2s,visibility 0s .2s;padding-top:calc(10px + var(--sat));padding-bottom:calc(10px + var(--sab))}
  body.mdraw aside{visibility:visible;transform:none;transition:transform .2s}
  #mdx{position:sticky;top:-10px;z-index:2;display:flex;justify-content:space-between;align-items:center;margin:-10px -10px 6px;padding:6px 10px;background:var(--pn);border-bottom:1px solid var(--bd)}
  #mscrim{position:fixed;inset:0;z-index:45;background:rgba(0,0,0,.4);display:none}
  body.mdraw #mscrim{display:block}
  #rc{position:static;margin:14px 0 0;padding:8px 0;font-size:.9rem}
  #rc .rcb{gap:8px}#rc .rcr button{font-size:.9rem}
  .mnote{margin:6px 0;padding:6px 10px;border-radius:6px;border:1px solid var(--ac);font-size:.8rem;line-height:1.5;color:var(--fg);background:rgba(224,160,96,.12)}
  #ep table{display:block;overflow-x:auto}
  body.qz #mdbtn{opacity:.4;pointer-events:none}
}
@media ${QA}{
  body{display:flex;flex-direction:column;height:auto;min-height:100dvh;padding-top:var(--sat);padding-bottom:calc(var(--barh) + var(--sab))}
  main{display:contents}
  main>*{flex:none}
  canvas{position:sticky;top:var(--sat);z-index:20;align-self:center;box-shadow:0 0 0 100vmax var(--bg);clip-path:inset(-1px -100vmax -1px -100vmax)}
  #info,#path,#cap{margin-left:8px;margin-right:8px}
  #cap{max-width:none!important}
  #qzt,#qzb{max-width:none!important;padding:0 10px}
  body.qz #qzt:not(:empty){margin-top:8px}
  section{flex:1 0 auto;overflow:visible;max-height:none;border-left-width:0;border-top-width:1px;padding:10px 12px}
  #vars{scroll-margin-top:calc(var(--bs) + var(--sat) + 8px)}
  footer{order:9}
  aside{left:0;right:0;bottom:0;top:calc(var(--sat) + 8vh);border-radius:14px 14px 0 0;border-top:1px solid var(--bd);transform:translateY(105%);box-shadow:0 -6px 20px rgba(0,0,0,.25)}
}
@media ${QB}{
  :root{--ft:40px;--bs:calc(100dvh - var(--ft) - var(--sat) - var(--sab))}
  body{grid-template-columns:minmax(0,var(--bs)) minmax(0,1fr);grid-template-rows:minmax(0,1fr) var(--ft);height:100dvh;padding-top:var(--sat)}
  main{padding:0;overflow:hidden;display:flex;flex-direction:column}
  main>*{flex:none}
  canvas{margin:0;width:var(--bs);max-width:100%}
  #info,#path,#cap{display:none}
  section{padding-bottom:calc(var(--barh) + 12px);max-height:none}
  footer{grid-column:1/-1;height:var(--ft);overflow:auto;padding-bottom:var(--sab)}
  .bar{left:calc(var(--bs) + var(--sal));bottom:calc(var(--ft) + var(--sab) - 0px);padding-left:8px}
  #mmore{left:calc(var(--bs) + var(--sal));bottom:calc(var(--barh) + var(--ft) + var(--sab))}
  aside{top:0;bottom:0;left:0;width:min(380px,92vw);border-right:1px solid var(--bd);transform:translateX(-105%);box-shadow:6px 0 20px rgba(0,0,0,.25)}
  body.qzh{grid-template-columns:minmax(0,1fr) minmax(0,300px)}
  body.qzh #qzt,body.qzh #qzb{overflow:auto}
  main{overflow:auto}
  #qzt,#qzb{max-width:none!important}
}
@media (orientation:landscape) and (max-width:700px){.bar{gap:2px;padding-left:4px;padding-right:calc(4px + var(--sar))}}
@media (prefers-reduced-motion:reduce){aside,#mtoast{transition:none!important}}
`;
  const st = document.createElement('style');
  st.id = 'mobile-css';
  st.textContent = css;
  document.head.appendChild(st);

  // ---------------------------------------------------------------- DOM work (after the page exists)
  const $ = id => document.getElementById(id);
  let mq, built = false, orig = [];

  function toast(msg, ms) {
    let t = $('mtoast');
    if (!t) { t = document.createElement('div'); t.id = 'mtoast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = msg; t.className = 'on';
    clearTimeout(toast.h); toast.h = setTimeout(() => { t.className = ''; }, ms || 1800);
  }
  window.mToast = toast;

  function mkBtn(id, label, title) {
    const b = document.createElement('button');
    b.id = id; b.textContent = label; if (title) b.title = title; b.className = 'm-only';
    return b;
  }

  // Phone bar: previous, next, variations, view mode, AI dots, more. Everything else moves into the "more" sheet.
  function build() {
    const bar = document.querySelector('.bar');
    if (!bar || built) return;
    built = true;
    orig = Array.from(bar.children);
    const more = document.createElement('div'); more.id = 'mmore';
    const scrim = document.createElement('div'); scrim.id = 'mscrim';
    const bv = mkBtn('mvbtn', '变化', '跳到变化列表'), bm = mkBtn('mmbtn', '更多'), bd = mkBtn('mdbtn', '目录'), bc = mkBtn('mcbtn', '算力');
    bv.onclick = () => { closeAll(); const v = $('vars'); if (v) v.scrollIntoView({ block: 'start', behavior: 'smooth' }); };
    bm.onclick = () => { document.body.classList.toggle('mmore'); };
    bd.onclick = () => openDrawer(false);
    bc.onclick = () => openDrawer(true);
    scrim.onclick = closeAll;
    const keep = ['b1', 'b2', 'mvbtn', 'bf', 'ba', 'mmbtn'];
    const parts = { b1: $('b1'), b2: $('b2'), mvbtn: bv, bf: $('bf'), ba: $('ba'), mmbtn: bm };
    bar.textContent = '';
    keep.forEach(k => bar.appendChild(parts[k]));
    ['b0', 'b3', 'bn', 'bl', 'bk', 'bq'].forEach(k => { const e = $(k) || orig.find(o => o.id === k); if (e) more.appendChild(e); });
    more.appendChild(bd); more.appendChild(bc);
    // buttons added later by other modules (the engine panel adds one) go into the sheet
    new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => { if (n.nodeType === 1 && n.parentNode === bar && !keep.includes(n.id)) { orig.push(n); more.appendChild(n); } }))).observe(bar, { childList: true });
    document.body.appendChild(more); document.body.appendChild(scrim);
    more.addEventListener('click', e => { if (e.target.closest('button') && !/^m(d|c)btn$/.test(e.target.closest('button').id)) document.body.classList.remove('mmore'); });
    // drawer header with a close button
    const as = document.querySelector('aside');
    if (as && !$('mdx')) { const h = document.createElement('div'); h.id = 'mdx'; h.innerHTML = '<b>目录与算力</b>'; const x = document.createElement('button'); x.textContent = '关闭'; x.onclick = closeAll; h.appendChild(x); as.insertBefore(h, as.firstChild); }
    // choosing a collection closes the drawer
    const list = $('list'); if (list) list.addEventListener('click', e => { if (e.target.closest('div')) setTimeout(closeAll, 0); });
    bar.setAttribute('role', 'toolbar'); bar.setAttribute('aria-label', '棋谱控制');
    markState();
  }
  function unbuild() {
    const bar = document.querySelector('.bar');
    if (!bar || !built) return;
    built = false; closeAll();
    ['mmore', 'mscrim', 'mvbtn', 'mmbtn', 'mdbtn', 'mcbtn', 'mdx'].forEach(i => { const e = $(i); if (e) e.remove(); });
    orig.filter(e => e.id && !e.classList.contains('m-only')).forEach(e => bar.appendChild(e));
    bar.removeAttribute('role');
  }
  function markState() { const b = $('ba'); const bf = $('bf'); void b; void bf; }

  function openDrawer(toCompute) {
    document.body.classList.remove('mmore');
    document.body.classList.add('mdraw');
    const rc = $('rc');
    if (toCompute && rc) { rc.open = true; setTimeout(() => rc.scrollIntoView({ block: 'center' }), 50); }
  }
  function closeAll() { document.body.classList.remove('mdraw', 'mmore'); }
  addEventListener('keydown', e => { if (e.key === 'Escape') closeAll(); });

  function sync() { if (mq.matches) build(); else unbuild(); }

  // ---------------------------------------------------------------- engine card notice (https and phones)
  function engineNote() {
    const https = location.protocol === 'https:';
    const m = $('rcm'), mode = m ? m.value : 'off';
    const text = '手机无法连接电脑上的 127.0.0.1 KataGo:在手机上,127.0.0.1 指的是手机自己。'
      + (https ? ' 当前页面通过 https 打开,浏览器会拦截 http 开头的桥接地址(混合内容),请使用 https 的远程 GPU 桥接地址;本机引擎只能在电脑上用本地版页面。' : ' 想在手机上用算力,请填局域网内电脑的地址或 https 的远程 GPU 桥接地址;推荐保持默认的「缓存」,不联网。');
    [$('rcn'), $('ep')].forEach((host, i) => {
      if (!host) return;
      let n = host.parentNode.querySelector(':scope > .mnote[data-k="' + i + '"]');
      const show = (mode !== 'off' || i === 1) && (https || mq.matches);
      if (!show) { if (n) n.remove(); return; }
      if (!n) { n = document.createElement('div'); n.className = 'mnote'; n.dataset.k = i; host.parentNode.insertBefore(n, i === 1 ? host : host.nextSibling); }
      if (n.textContent !== text) n.textContent = text;
    });
  }

  // ---------------------------------------------------------------- touch: long press previews, release clears, tap acts
  // Same rules as the mouse: the long press feeds the very same mouse handlers of the board (hover isolation, numbering from 1, colours, level hierarchy).
  function touchSetup() {
    const cv = $('cv');
    if (!cv || !window.PointerEvent) return;
    const HOLD = 320, SLOP = 10, QUIZ_R = 0.7;
    let pid = null, sx = 0, sy = 0, timer = 0, previewing = false, swallow = 0, lastTouch = 0, qpt = null, qtime = 0;
    const fake = (e) => ({ clientX: e.clientX, clientY: e.clientY, target: cv, type: 'mousemove', preventDefault() {}, stopPropagation() {} });
    const quizAsk = () => document.body.classList.contains('qz') && !!document.querySelector('#qzb [data-a=show]');
    const cell = () => { const r = cv.getBoundingClientRect(), V = window.Vnow || { x0: 0, x1: 18, y0: 0, y1: 18 }; return r.width / (Math.max(V.x1 - V.x0, V.y1 - V.y0) + 1.6); };
    const isTouch = e => e.pointerType === 'touch' || e.pointerType === 'pen';

    // ignore the mouse events that browsers synthesise after a touch (they would start a hover by themselves)
    ['mousemove', 'mouseover', 'mouseout', 'mouseleave'].forEach(t => cv.addEventListener(t, e => { if (e.isTrusted && Date.now() - lastTouch < 900) e.stopImmediatePropagation(); }, true));
    // ghost click guard: the click that follows a long press must not act
    cv.addEventListener('click', e => { if (swallow && Date.now() < swallow) { e.stopImmediatePropagation(); e.preventDefault(); swallow = 0; } }, true);
    cv.addEventListener('contextmenu', e => { if (Date.now() - lastTouch < 1500) e.preventDefault(); });

    function endPreview() {
      clearTimeout(timer); timer = 0;
      if (previewing) { previewing = false; swallow = Date.now() + 600; if (quizAsk() && cv.onmouseleave) { /* quiz keeps its marked point until confirmed */ } else if (typeof clearHover === 'function') clearHover(); }
    }
    cv.addEventListener('pointerdown', e => {
      if (!isTouch(e) || pid !== null) return;
      pid = e.pointerId; sx = e.clientX; sy = e.clientY; lastTouch = Date.now(); previewing = false;
      try { cv.setPointerCapture(pid); } catch (x) { /* not all engines allow it */ }
      if (quizAsk()) return; // the quiz uses taps, see pointerup
      timer = setTimeout(() => { previewing = true; if (cv.onmousemove) cv.onmousemove(fake({ clientX: sx, clientY: sy })); if (navigator.vibrate) try { navigator.vibrate(8); } catch (x) { /* optional */ } }, HOLD);
    });
    cv.addEventListener('pointermove', e => {
      if (!isTouch(e) || e.pointerId !== pid) return;
      lastTouch = Date.now();
      if (previewing) { if (cv.onmousemove) cv.onmousemove(fake(e)); }
      else if (Math.hypot(e.clientX - sx, e.clientY - sy) > SLOP) { clearTimeout(timer); timer = 0; }
    });
    cv.addEventListener('pointerup', e => {
      if (!isTouch(e) || e.pointerId !== pid) return;
      lastTouch = Date.now(); pid = null;
      if (quizAsk() && !previewing) {
        // quiz: first tap marks a point, a second tap on the same point confirms; this is hard to misclick
        const m = cell(), now = Date.now();
        e.preventDefault();
        if (qpt && now - qtime < 8000 && Math.hypot(e.clientX - qpt.x, e.clientY - qpt.y) < m * QUIZ_R) { qpt = null; if (cv.onclick) cv.onclick(fake(e)); toast('', 1); }
        else {
          qpt = { x: e.clientX, y: e.clientY }; qtime = now;
          if (cv.onmousemove) cv.onmousemove(fake(e));
          toast('已标记这一点,再点一次同一位置确认落子;点别处可改选', 2600);
        }
        swallow = Date.now() + 500; // the browser click that follows is replaced by the logic above
        return;
      }
      endPreview();
    });
    cv.addEventListener('pointercancel', e => { if (e.pointerId === pid) { pid = null; endPreview(); } });
    // leaving the quiz question forgets the marked point
    new MutationObserver(() => { if (!quizAsk()) qpt = null; }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
    // the page must never zoom by double tap on the board
    cv.addEventListener('dblclick', e => e.preventDefault());
    // a pinch on the board is not a gesture of the board: keep the page from zooming through it
    cv.addEventListener('gesturestart', e => e.preventDefault());
    // a second finger cancels a pending long press
    cv.addEventListener('touchstart', e => { if (e.touches.length > 1) { clearTimeout(timer); timer = 0; } }, { passive: true });
  }

  function init() {
    mq = matchMedia(MODE);
    if (mq.addEventListener) mq.addEventListener('change', sync); else if (mq.addListener) mq.addListener(sync);
    sync(); touchSetup();
    const m = $('rcm'); if (m) m.addEventListener('change', () => setTimeout(engineNote, 0));
    new MutationObserver(engineNote).observe(document.querySelector('section') || document.body, { childList: true });
    engineNote();
    addEventListener('resize', () => { if (!mq.matches) closeAll(); });
  }
  if (document.readyState === 'complete') init(); else addEventListener('load', init);
})();
