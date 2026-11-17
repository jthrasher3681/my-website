'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const {MessageChannel} = require('node:worker_threads');

const source = fs.readFileSync(path.join(__dirname, '../../guitar/sw.js'), 'utf8');
const production = 'https://example.test/guitar/';
const legacy = 'thrasher-guitar-studio-v1.0.0';
const release = '1.2.0';
const protectedFiles = ['index.html', 'lock.js?v=1.2.0', 'lock.css?v=1.2.0',
  'crypto.js?v=1.2.0', 'course.enc.json?v=1.2.0', 'manifest.webmanifest',
  'icon.svg', 'icon-192.png', 'icon-512.png'];

function fixture(scope = production, script = source) {
  const stores = new Map();
  const handlers = new Map();
  const windows = [];
  const state = {online: true, claims: 0, skips: 0, requests: [], navigated: [], checked: [], fail: false};
  const href = file => new URL(file, scope).href;
  const key = version => 'thrasher-guitar-studio-' + new URL(scope).pathname + '-v' + version;
  const seed = (name, entries) => stores.set(name, new Map(entries));
  const cacheStorage = {
    keys: async () => [...stores.keys()],
    delete: async name => stores.delete(name),
    match: async (url, {cacheName}) => stores.get(cacheName)?.get(url),
    open: async name => {
      if (!stores.has(name)) seed(name);
      return {
        match: async url => stores.get(name)?.get(url),
        addAll: async requests => {
          state.requests.push(...requests);
          if (state.fail) throw new Error('download failed');
          for (const request of requests) stores.get(name).set(request.url, 'cached ' + request.url);
        }
      };
    }
  };
  const self = {
    registration: {scope},
    clients: {
      claim: async () => { state.claims++; },
      matchAll: async options => { assert.equal(options.type, 'window'); return windows; }
    },
    skipWaiting: async () => { state.skips++; },
    addEventListener: (type, fn) => handlers.set(type, fn)
  };
  vm.runInNewContext(script, {self, caches: cacheStorage, URL, Request, Response, crypto: webcrypto,
    MessageChannel, setTimeout, clearTimeout,
    fetch: async request => {
      if (!state.online) throw new Error('offline');
      return 'network ' + request.url;
    }
  });
  function fire(type, fields = {}) {
    let result;
    const capture = promise => { result = promise; };
    handlers.get(type)({ports: [], ...fields, waitUntil: capture, respondWith: capture});
    return result;
  }
  function get(file, mode = 'cors', method = 'GET') {
    return fire('fetch', {request: {url: href(file), mode, method}});
  }
  function client(id, file, respond) {
    const item = {id, url: href(file),
      postMessage: (message, ports) => {
        assert.equal(message.type, 'IS_LOCK_SHELL');
        state.checked.push(id);
        respond?.(message, ports, item);
      },
      navigate: async url => { state.navigated.push([id, url]); }
    };
    windows.push(item);
  }
  return {state, stores, href, key, seed, fire, get, client};
}

test('fresh installation atomically precaches exactly the public shell and encrypted bundle', async () => {
  const f = fixture();
  await f.fire('install');
  assert.deepEqual(f.state.requests.map(request => request.url).sort(), protectedFiles.map(f.href).sort());
  assert.ok(f.state.requests.every(request => request.cache === 'reload'));
  assert.equal(f.state.skips, 1);
  f.client('fresh', '', (message, ports) => {
    ports[0].postMessage({type: 'LOCK_SHELL_PRESENT', requestId: message.requestId});
  });
  await f.fire('activate');
  assert.equal(f.state.claims, 1);
  assert.deepEqual(f.state.checked, ['fresh']);
  assert.deepEqual(f.state.navigated, []);
  let reply;
  await f.fire('message', {data: {type: 'GET_COURSE_VERSION'}, ports: [{postMessage: value => { reply = value; }}]});
  assert.equal(reply.version, release);
  assert.equal(reply.offlineReady, true);
});

test('the shell and ciphertext work offline without a plaintext course fallback', async () => {
  const f = fixture();
  await f.fire('install');
  f.state.online = false;
  for (const file of ['', '?source=home', 'index.html#lesson-9']) {
    assert.equal(await f.get(file, 'navigate'), 'cached ' + f.href('index.html'));
  }
  for (const file of protectedFiles.slice(1)) assert.equal(await f.get(file), 'cached ' + f.href(file));
  for (const file of ['/guitar-similar/', '/', 'https://other.test/guitar/lessons.js', 'unknown.png']) {
    assert.equal(f.get(file), undefined);
  }
  assert.equal(f.get('', 'navigate', 'POST'), undefined);
  assert.equal(f.get('course.enc.json?v=unknown'), undefined);
});

test('legacy asset URLs never return lessons, including from another cache or a network fallback', async () => {
  const f = fixture();
  const files = ['lessons.js?v=1.1.0', 'studio.js', 'ui.js?foo', 'studio.css?v=1.0.0',
    'docs/practice-tools.jpg', 'tests/ui.test.cjs?raw=1', '%6cessons.js?x=2', 'docs%2fpractice-tools.jpg'];
  f.seed(f.key('1.1.0'), files.map(file => [f.href(file), 'old plaintext']));
  for (const file of files) {
    for (const method of ['GET', 'HEAD']) {
      const res = await f.get(file, 'navigate', method);
      assert.equal(res.status, 404);
      assert.equal(await res.text(), '');
      assert.equal(res.headers.get('Cache-Control'), 'no-store');
    }
  }
});

test('first protected upgrade drops all plaintext caches and reloads only old course clients', async () => {
  const f = fixture();
  const oldKeys = [legacy, f.key('1.0.0'), f.key('1.1.0')];
  const preservedKeys = ['unrelated-app', 'thrasher-guitar-studio-/other/-v1.1.0', f.key('debug'), f.key('1.3.0')];
  for (const name of [...oldKeys, ...preservedKeys]) f.seed(name);
  f.client('old', '#lesson-9', message => {
    // A reply from another window cannot mark this old one as protected.
    f.fire('message', {source: {id: 'different-window'}, data: {type: 'LOCK_SHELL_PRESENT', requestId: message.requestId}});
  });
  f.client('locked', 'index.html', (message, ports) => {
    ports[0].postMessage({type: 'LOCK_SHELL_PRESENT', requestId: message.requestId});
  });
  f.client('fallback', '?standalone=1', (message, ports, item) => {
    f.fire('message', {source: item, data: {type: 'LOCK_SHELL_PRESENT', requestId: message.requestId}});
  });
  f.client('other-app', '/other-app/');
  f.client('course-doc', 'docs/');
  await f.fire('install');
  assert.equal(f.state.skips, 1);
  await f.fire('activate');
  assert.equal(f.state.claims, 1);
  assert.deepEqual([...f.stores.keys()].sort(), [...preservedKeys, f.key(release)].sort());
  assert.deepEqual(f.state.checked.sort(), ['fallback', 'locked', 'old']);
  assert.deepEqual(f.state.navigated, [['old', f.href('index.html#lesson-9')]]);
});

test('an open plaintext tab is replaced even when all prior caches were evicted', async () => {
  const f = fixture();
  f.client('plaintext', 'index.html?ref=practice#lesson-6');
  await f.fire('install');
  assert.equal(f.state.skips, 1);
  await f.fire('activate');
  assert.deepEqual(f.state.navigated, [['plaintext', f.href('?ref=practice#lesson-6')]]);
});

test('preview installation only migrates its own prior caches', async () => {
  const f = fixture('https://example.test/preview/guitar/');
  for (const name of [legacy, 'thrasher-guitar-studio-/guitar/-v1.1.0', f.key('1.1.0')]) f.seed(name);
  await f.fire('install');
  await f.fire('activate');
  assert.equal(f.state.skips, 1);
  assert.equal(f.stores.has(legacy), true);
  assert.equal(f.stores.has('thrasher-guitar-studio-/guitar/-v1.1.0'), true);
  assert.equal(f.stores.has(f.key('1.1.0')), false);
});

test('subsequent protected releases wait for deliberate activation', async () => {
  const f = fixture(production, source.replace("const RELEASE = '1.2.0'", "const RELEASE = '1.3.0'"));
  f.seed(f.key(release));
  f.client('protected', '');
  await f.fire('install');
  assert.equal(f.state.skips, 0);
  await f.fire('message', {data: {type: 'ACTIVATE_COURSE_UPDATE'}});
  assert.equal(f.state.skips, 1);
  await f.fire('activate');
  assert.equal(f.stores.has(f.key(release)), false);
  assert.deepEqual(f.state.navigated, []);
});

test('a failed atomic download never activates a broken release', async () => {
  const f = fixture();
  f.seed(legacy);
  f.state.fail = true;
  await assert.rejects(f.fire('install'), /download failed/);
  assert.deepEqual([...f.stores.keys()], [legacy]);
  assert.equal(f.state.skips, 0);
});
