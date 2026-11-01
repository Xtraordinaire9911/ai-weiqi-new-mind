// Registers the service worker (sw.js, same folder) and offers a safe update. It sends no data anywhere.
// Update flow: a new worker waits; the page shows a notice; only a tap on it activates the new worker and reloads.
(function () {
  'use strict';
  if (!('serviceWorker' in navigator)) return;
  const secure = location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  if (!secure) return; // service workers need a secure context; over plain http on a LAN the page simply works without the cache
  let reloading = false;
  function offer(reg) {
    const w = reg.waiting; if (!w || !navigator.serviceWorker.controller) return;
    const t = document.createElement('div');
    t.setAttribute('role', 'status');
    t.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);bottom:calc(76px + env(safe-area-inset-bottom,0px));z-index:70;background:#262521;color:#fff;border:1px solid #e0a060;border-radius:20px;padding:10px 16px;font-size:15px;max-width:92vw;text-align:center';
    t.textContent = '有新版本,点这里更新';
    const go = function () { w.postMessage('skip-waiting'); t.textContent = '正在更新…'; };
    t.onclick = go; document.body.appendChild(t);
  }
  navigator.serviceWorker.addEventListener('controllerchange', function () { if (reloading) return; reloading = true; location.reload(); });
  addEventListener('load', function () {
    navigator.serviceWorker.register('sw.js').then(function (reg) {
      offer(reg);
      reg.addEventListener('updatefound', function () {
        const nw = reg.installing; if (!nw) return;
        nw.addEventListener('statechange', function () { if (nw.state === 'installed') offer(reg); });
      });
    }).catch(function () { /* no worker: the page works as before */ });
  });
})();
