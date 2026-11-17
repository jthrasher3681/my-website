'use strict';

// 1.1.0: reviewed curriculum, section practice and safe in-app updates.

const RELEASE = '1.1.0';
const SCOPE = new URL(self.registration.scope);
const CACHE_PREFIX = 'thrasher-guitar-studio-' + SCOPE.pathname + '-v';
const CACHE = CACHE_PREFIX + RELEASE;
const LEGACY_CACHE = 'thrasher-guitar-studio-v1.0.0';
const HAS_LEGACY_CACHE = SCOPE.pathname === '/guitar/';
const RELEASE_NUMBER = /^\d+\.\d+\.\d+$/;
const VERSIONED_FILES = new Set(['studio.css', 'lessons.js', 'studio.js', 'ui.js']);
const SHARED_FILES = new Set(['manifest.webmanifest', 'icon.svg', 'icon-192.png', 'icon-512.png']);
const DOCUMENT = new URL('index.html', SCOPE).href;

function versionedUrl(file, version) {
  const url = new URL(file, SCOPE);
  url.searchParams.set('v', version);
  return url.href;
}

self.addEventListener('install', event => {
  // addAll commits the entire course in a single operation. Bypass stale HTTP cache entries.
  const urls = [DOCUMENT, ...Array.from(SHARED_FILES, file => new URL(file, SCOPE).href),
    ...Array.from(VERSIONED_FILES, file => versionedUrl(file, RELEASE))];
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    try {
      await cache.addAll(urls.map(url => new Request(url, {cache: 'reload'})));
    } catch (error) {
      if (!await cache.match(DOCUMENT)) await caches.delete(CACHE);
      throw error;
    }
  })());
});

self.addEventListener('message', event => {
  if (event.data?.type === 'ACTIVATE_COURSE_UPDATE') event.waitUntil(self.skipWaiting());
  if (event.data?.type === 'GET_COURSE_VERSION') {
    event.ports[0]?.postMessage({version: RELEASE, offlineReady: true});
  }
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    // CacheStorage lists caches in creation order. Leave any later install in progress
    // alone, and keep the previous course available to tabs that still run its page.
    const prior = names.slice(0, Math.max(0, names.indexOf(CACHE))).filter(name =>
      (HAS_LEGACY_CACHE && name === LEGACY_CACHE) ||
      (name.startsWith(CACHE_PREFIX) && RELEASE_NUMBER.test(name.slice(CACHE_PREFIX.length)))
    );
    await Promise.all(prior.slice(0, -1).map(name => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== SCOPE.origin || !url.pathname.startsWith(SCOPE.pathname)) return;

  const file = url.pathname.slice(SCOPE.pathname.length);
  if (request.mode === 'navigate' && (file === '' || file === 'index.html')) {
    event.respondWith(caches.match(DOCUMENT, {cacheName: CACHE}).then(saved => saved || fetch(request)));
  } else if (SHARED_FILES.has(file) && !url.search) {
    // The precache used plain URL keys. Use the same keys for requests from the page,
    // which can have different Accept headers when the server sends Vary: Accept.
    event.respondWith(caches.match(url.href, {cacheName: CACHE}).then(saved => saved || fetch(request)));
  } else if (VERSIONED_FILES.has(file)) {
    const version = url.searchParams.get('v');
    if (version && RELEASE_NUMBER.test(version) && url.search === '?v=' + version) {
      event.respondWith(caches.match(url.href, {cacheName: CACHE_PREFIX + version}).then(saved => saved || fetch(request)));
    } else if (!url.search) {
      event.respondWith((async () => {
        // The original release used unversioned JS and CSS. Its open tabs keep their matching assets.
        const legacy = HAS_LEGACY_CACHE && await caches.match(url.href, {cacheName: LEGACY_CACHE});
        return legacy || await caches.match(versionedUrl(file, RELEASE), {cacheName: CACHE}) || fetch(request);
      })());
    }
  }
});
