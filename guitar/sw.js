'use strict';

const RELEASE = '1.2.0';
const FIRST_LOCKED_RELEASE = '1.2.0';
const SCOPE = new URL(self.registration.scope);
const CACHE_PREFIX = 'thrasher-guitar-studio-' + SCOPE.pathname + '-v';
const CACHE = CACHE_PREFIX + RELEASE;
const LEGACY_CACHE = 'thrasher-guitar-studio-v1.0.0';
const DOCUMENT = new URL('index.html', SCOPE).href;
const VERSIONED = ['lock.js', 'lock.css', 'crypto.js', 'course.enc.json'];
const SHARED = ['manifest.webmanifest', 'icon.svg', 'icon-192.png', 'icon-512.png'];
const PUBLIC_URLS = new Set([DOCUMENT, ...SHARED.map(file => new URL(file, SCOPE).href),
  ...VERSIONED.map(file => new URL(file + '?v=' + RELEASE, SCOPE).href)]);
const REMOVED = new Set(['lessons.js', 'studio.js', 'ui.js', 'studio.css']);
const pendingShellChecks = new Map();

function olderThan(version, limit) {
  const parts = version.split('.').map(Number);
  const target = limit.split('.').map(Number);
  for (let i = 0; i < parts.length; i++) {
    if (parts[i] !== target[i]) return parts[i] < target[i];
  }
  return false;
}

function isOlderCache(name, limit) {
  if (SCOPE.pathname === '/guitar/' && name === LEGACY_CACHE) return true;
  if (!name.startsWith(CACHE_PREFIX)) return false;
  const version = name.slice(CACHE_PREFIX.length);
  return /^\d+\.\d+\.\d+$/.test(version) && olderThan(version, limit);
}

function needsPasswordMigration(names) {
  // An open plaintext tab can outlive eviction of its service worker's cache.
  return RELEASE === FIRST_LOCKED_RELEASE || names.some(name => isOlderCache(name, FIRST_LOCKED_RELEASE));
}

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    try {
      await cache.addAll([...PUBLIC_URLS].map(url => new Request(url, {cache: 'reload'})));
    } catch (error) {
      if (!await cache.match(DOCUMENT)) await caches.delete(CACHE);
      throw error;
    }
    if (needsPasswordMigration(await caches.keys())) {
      await self.skipWaiting();
    }
  })());
});

self.addEventListener('message', event => {
  const data = event.data;
  if (data?.type === 'ACTIVATE_COURSE_UPDATE') event.waitUntil(self.skipWaiting());
  if (data?.type === 'GET_COURSE_VERSION') {
    event.ports[0]?.postMessage({version: RELEASE, offlineReady: true});
  }
  if (data?.type === 'LOCK_SHELL_PRESENT') {
    const check = pendingShellChecks.get(data.requestId);
    if (check && check.clientId === event.source?.id) check.finish(true);
  }
});

function hasLockShell(client) {
  const requestId = crypto.randomUUID();
  const channel = new MessageChannel();
  return new Promise(resolve => {
    function finish(present) {
      clearTimeout(timer);
      pendingShellChecks.delete(requestId);
      channel.port1.close();
      resolve(present);
    }
    const timer = setTimeout(() => finish(false), 1000);
    pendingShellChecks.set(requestId, {clientId: client.id, finish});
    channel.port1.onmessage = event => {
      if (event.data?.type === 'LOCK_SHELL_PRESENT' && event.data.requestId === requestId) finish(true);
    };
    try {
      client.postMessage({type: 'IS_LOCK_SHELL', requestId}, [channel.port2]);
    } catch (_) {
      finish(false);
    }
  });
}

function isCourseWindow(client) {
  const url = new URL(client.url);
  return url.origin === SCOPE.origin &&
    (url.pathname === SCOPE.pathname || url.pathname === SCOPE.pathname + 'index.html');
}

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    const migration = needsPasswordMigration(names);
    await Promise.all(names.filter(name => isOlderCache(name, RELEASE)).map(name => caches.delete(name)));
    await self.clients.claim();
    if (migration) {
      const windows = await self.clients.matchAll({type: 'window'});
      await Promise.all(windows.filter(isCourseWindow).map(async client => {
        if (!await hasLockShell(client)) {
          // Change the path so a deep link cannot turn this into a same-document navigation.
          const url = new URL(client.url);
          url.pathname = url.pathname === SCOPE.pathname ? SCOPE.pathname + 'index.html' : SCOPE.pathname;
          // Navigation can wait for activation. Start it without waiting for it here.
          client.navigate(url.href).catch(() => {});
        }
      }));
    }
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== SCOPE.origin || !url.pathname.startsWith(SCOPE.pathname)) return;
  let file;
  try { file = decodeURIComponent(url.pathname.slice(SCOPE.pathname.length)); }
  catch (_) { return; }
  if (REMOVED.has(file) || /^(docs|tests)(\/|$)/.test(file)) {
    event.respondWith(Promise.resolve(new Response(null, {status: 404, headers: {'Cache-Control': 'no-store'}})));
    return;
  }
  if (request.method !== 'GET') return;
  const isNavigation = request.mode === 'navigate' && (file === '' || file === 'index.html');
  const cacheUrl = isNavigation ? DOCUMENT : url.href;
  if (PUBLIC_URLS.has(cacheUrl)) {
    event.respondWith(caches.match(cacheUrl, {cacheName: CACHE}).then(saved => saved || fetch(request)));
  }
});
