/* Service Worker：让 PWA 能离线打开、加到主屏后表现正常。
 *
 * 策略很保守（避免缓存了旧版本导致「改了没生效」这个经典坑）：
 *   · 静态资源（图标/manifest）：cache-first
 *   · 页面和 API：network-first，失败才回缓存
 *   · /api/ask：**永不缓存**（每次都要新结果）
 */

const CACHE = "city-agent-v14";
const STATIC = [
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/manifest.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(STATIC)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // API 一律不缓存（尤其是 /api/ask，要新结果）
  if (url.pathname.startsWith("/api/")) return;

  // 静态资源：cache-first
  if (STATIC.includes(url.pathname)) {
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request))
    );
    return;
  }

  // 页面：network-first，失败回缓存
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
  }
});
