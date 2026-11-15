// 오프라인 지원 — 일정 페이지는 네트워크 우선(최신 유지), 사진·지도·글꼴은 저장본 우선
const CACHE = "hkmo-v1";
const TILES = "hkmo-tiles";
const MAX_TILES = 500;
const CORE = ["./", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];
const ASSET_HOSTS = ["cdnjs.cloudflare.com", "fonts.googleapis.com", "fonts.gstatic.com", "upload.wikimedia.org"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE && k !== TILES).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const storable = r => r && (r.ok || r.type === "opaque");

async function trimTiles() {
  const c = await caches.open(TILES);
  const keys = await c.keys();
  for (let i = 0; i < keys.length - MAX_TILES; i++) await c.delete(keys[i]);
}

async function pageFirst(req) {
  const c = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (res.ok) await c.put("./", res.clone());
    return res;
  } catch (err) {
    return (await c.match("./")) || Response.error();
  }
}

async function assetCached(req, cacheName, e) {
  const c = await caches.open(cacheName);
  const hit = await c.match(req, { ignoreVary: true });
  const net = fetch(req).then(async res => {
    if (storable(res)) { await c.put(req, res.clone()); if (cacheName === TILES) await trimTiles(); }
    return res;
  }).catch(() => null);
  if (hit) { e.waitUntil(net); return hit; }
  return (await net) || Response.error();
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const same = url.origin === self.location.origin;
  if (same && (req.mode === "navigate" || /\/(index\.html)?$/.test(url.pathname))) { e.respondWith(pageFirst(req)); return; }
  if (url.hostname === "tile.openstreetmap.org") { e.respondWith(assetCached(req, TILES, e)); return; }
  if (same || ASSET_HOSTS.includes(url.hostname)) e.respondWith(assetCached(req, CACHE, e));
});

// 페이지가 보내준 사진·라이브러리 주소를 미리 저장
self.addEventListener("message", e => {
  if (!e.data || e.data.type !== "warm") return;
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    await Promise.all((e.data.urls || []).map(async u => {
      if (await c.match(u, { ignoreVary: true })) return;
      try {
        let res = await fetch(u, { mode: "cors" }).catch(() => null);
        if (!res || !res.ok) res = await fetch(u, { mode: "no-cors" });
        if (storable(res)) await c.put(u, res);
      } catch (err) {}
    }));
    if (e.source) e.source.postMessage({ type: "warmed" });
  })());
});
