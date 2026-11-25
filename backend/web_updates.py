"""Retire Flutter's legacy offline cache without touching account storage."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter()

RETIRE_WORKER = """
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil((async () => {
  const names = await caches.keys();
  await Promise.all(names.filter(name => name.startsWith('flutter-')).map(name => caches.delete(name)));
  await self.registration.unregister();
  const windows = await self.clients.matchAll({type: 'window'});
  await Promise.all(windows.map(client => client.navigate(client.url)));
})()));
"""

UPDATE_PAGE = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tushum AI yangilanmoqda</title>
<style>body{margin:0;background:#f3f6f8;color:#182d3d;font:18px system-ui;display:grid;min-height:100vh;place-items:center}main{max-width:440px;padding:32px}a{color:#0c5f69}</style>
</head><body><main><h1>Tushum AI</h1><p id="status">Ilovaning yangi versiyasi ochilmoqda…</p>
<p>Hisobingiz va saqlangan ma’lumotlaringiz saqlanadi.</p>
<a id="continue" href="/?sahifa=ai-suhbatlar">AI suhbatlarga o‘tish</a></main>
<script>
(async () => {
  try {
    if ('serviceWorker' in navigator) {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.filter(reg => [reg.active,reg.waiting,reg.installing].some(worker => worker && new URL(worker.scriptURL).pathname === '/flutter_service_worker.js')).map(reg => reg.unregister()));
    }
    if ('caches' in window) {
      const names = await caches.keys();
      await Promise.all(names.filter(name => name.startsWith('flutter-')).map(name => caches.delete(name)));
    }
    const target = new URL('/', location.origin);
    target.searchParams.set('sahifa','ai-suhbatlar');
    target.searchParams.set('yangilandi',Date.now().toString());
    document.querySelector('#continue').href = target.href;
    location.replace(target.href);
  } catch (_) {
    document.querySelector('#status').textContent = 'Yangilash tugamadi. Quyidagi havolani qayta oching.';
  }
})();
</script></body></html>"""


@router.get("/yangilash", include_in_schema=False)
def update_page():
    return HTMLResponse(UPDATE_PAGE, headers={"Cache-Control": "no-store"})


@router.get("/flutter_service_worker.js", include_in_schema=False)
def retired_worker():
    return Response(
        RETIRE_WORKER,
        media_type="application/javascript",
        headers={"Cache-Control": "no-store", "Service-Worker-Allowed": "/"},
    )
