'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../sw.js'), 'utf8');
const scope = 'https://example.test/guitar/';
const key = version => 'thrasher-guitar-studio-/guitar/-v' + version;
const legacy = 'thrasher-guitar-studio-v1.0.0';
const release = '1.1.0';
const href = (file, root = scope) => new URL(file, root).href;

function fixture(root = scope) {
  const stores = new Map();
  const listeners = {};
  const state = {skips: 0, claims: 0, requests: [], fail: false, online: true};

  function seed(name, entries = []) { stores.set(name, new Map(entries)); }
  function urlOf(request) { return typeof request === 'string' ? request : request.url; }

  const caches = {
    keys: async () => [...stores.keys()],
    delete: async name => stores.delete(name),
    match: async (request, {cacheName}) => stores.get(cacheName)?.get(urlOf(request)),
    open: async name => {
      if (!stores.has(name)) seed(name);
      return {
        match: async request => stores.get(name).get(urlOf(request)),
        addAll: async requests => {
          state.requests.push(...requests);
          if (state.fail) throw new Error('download failed');
          for (const request of requests) stores.get(name).set(request.url, 'cached ' + request.url);
        }
      };
    }
  };
  const self = {
    registration: {scope: root},
    clients: {claim: async () => { state.claims++; }},
    skipWaiting: async () => { state.skips++; },
    addEventListener: (type, fn) => { listeners[type] = fn; }
  };
  vm.runInNewContext(source, {self, URL, Request, caches,
    fetch: async request => {
      if (!state.online) throw new Error('offline');
      return 'network ' + urlOf(request);
    }
  });

  function fire(type, fields = {}) {
    let result;
    const capture = promise => { result = promise; };
    listeners[type]({...fields, waitUntil: capture, respondWith: capture});
    return result;
  }
  function get(file, mode = 'cors', method = 'GET') {
    return fire('fetch', {request: {url: href(file, root), mode, method}});
  }
  return {stores, state, seed, fire, get};
}

test('install downloads a complete fresh release and waits for explicit activation', async () => {
  const {state, fire} = fixture();
  await fire('install');
  const files = ['index.html', 'studio.css?v=1.1.0', 'lessons.js?v=1.1.0', 'studio.js?v=1.1.0',
    'ui.js?v=1.1.0', 'manifest.webmanifest', 'icon.svg', 'icon-192.png', 'icon-512.png'];
  assert.deepEqual(state.requests.map(request => request.url).sort(), files.map(file => href(file)).sort());
  assert.ok(state.requests.every(request => request.cache === 'reload'));
  assert.equal(state.skips, 0);
  await fire('message', {data: {type: 'irrelevant'}});
  assert.equal(state.skips, 0);
  await fire('message', {data: {type: 'ACTIVATE_COURSE_UPDATE'}});
  assert.equal(state.skips, 1);
  let reply;
  await fire('message', {data: {type: 'GET_COURSE_VERSION'}, ports: [{postMessage(value) { reply = value; }}]});
  assert.equal(reply.version, release);
  assert.equal(reply.offlineReady, true);
});

test('a failed install leaves the earlier course available', async () => {
  const {state, stores, seed, fire} = fixture();
  seed(legacy, [[href('index.html'), 'old document']]);
  state.fail = true;
  await assert.rejects(fire('install'), /download failed/);
  assert.deepEqual([...stores.keys()], [legacy]);
  assert.equal(stores.get(legacy).get(href('index.html')), 'old document');
  assert.equal(state.skips, 0);
});

test('offline documents and assets resolve only inside the course', async () => {
  const {state, fire, get} = fixture();
  await fire('install');
  state.online = false;
  for (const file of ['', '?utm_source=home', 'index.html#lesson-9']) {
    assert.equal(await get(file, 'navigate'), 'cached ' + href('index.html'));
  }
  assert.equal(await get('studio.js?v=1.1.0'), 'cached ' + href('studio.js?v=1.1.0'));
  assert.equal(await get('icon.svg'), 'cached ' + href('icon.svg'));
  for (const file of ['unknown', '/guitar-other/', '/', 'https://other.test/guitar/']) {
    assert.equal(get(file, 'navigate'), undefined);
  }
  assert.equal(get('', 'navigate', 'POST'), undefined);
  assert.equal(get('studio.js?preview=1'), undefined);
  await assert.rejects(get('studio.js?v=1.2.0'), /offline/);
});

test('retire only older releases of this scope and keep matching prior assets', async () => {
  const {state, stores, seed, fire, get} = fixture();
  seed(legacy, [[href('studio.js'), 'original script']]);
  seed('thrasher-guitar-studio-/another/course/-v1.0.0');
  seed('unrelated-app');
  await fire('install');
  await fire('activate');
  assert.equal(await get('studio.js'), 'original script');
  assert.equal(await get('studio.js?v=1.1.0'), 'cached ' + href('studio.js?v=1.1.0'));
  assert.equal(state.claims, 1);

  // Simulate two prior releases in creation order, plus a newer install in progress.
  const next = fixture();
  for (const name of [legacy, 'unrelated-app', 'thrasher-guitar-studio-/another/course/-v1.0.0',
    key('debug'), key('1.0.1'), key(release), key('1.2.0')]) next.seed(name);
  const old = href('studio.js?v=1.0.1');
  next.stores.get(key('1.0.1')).set(old, 'previous script');
  await next.fire('activate');
  assert.equal(await next.get('studio.js?v=1.0.1'), 'previous script');
  assert.equal(next.stores.has(legacy), false);
  assert.equal(next.stores.size, 6);
  assert.equal(stores.has(legacy), true);
});

test('a preview installation cannot delete the production legacy cache', async () => {
  const {seed, stores, fire} = fixture('https://example.test/preview/guitar/');
  seed(legacy);
  const priorPreview = 'thrasher-guitar-studio-/preview/guitar/-v1.0.1';
  seed(priorPreview);
  await fire('install');
  await fire('activate');
  assert.ok(stores.has(legacy));
  assert.ok(stores.has(priorPreview));
});
