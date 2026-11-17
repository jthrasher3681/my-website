'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ui = fs.readFileSync(path.join(__dirname, '../ui.js'), 'utf8');
const pageVersion = '1.2.0';
const newer = '1.10.0';
const turn = () => new Promise(resolve => setImmediate(resolve));

class Element extends EventTarget {
  querySelectorAll() { return []; }
  emit(name) { this.dispatchEvent(new Event(name)); }
}

function worker(version) {
  const instance = new Element();
  instance.commands = [];
  instance.postMessage = (message, ports) => {
    instance.commands.push(message.type);
    if (message.type === 'GET_COURSE_VERSION') ports[0].postMessage({version, offlineReady: true});
  };
  return instance;
}

class TestChannel {
  constructor() {
    this.port1 = {close() {}};
    this.port2 = {postMessage: data => queueMicrotask(() => this.port1.onmessage({data}))};
  }
}

async function page({activeVersion = pageVersion, waiting = false, controlled = true} = {}) {
  const document = new Element(), window = new Element(), serviceWorker = new Element();
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  }
  document.getElementById = element;
  element('courseUpdate').hidden = true;
  const reg = Object.assign(new Element(), {
    active: activeVersion ? worker(activeVersion) : null, waiting: waiting ? worker(newer) : null
  });
  let markReady;
  const ready = new Promise(resolve => { markReady = resolve; });
  if (reg.active) markReady(reg);
  Object.assign(serviceWorker, {
    ready, controller: controlled ? reg.active : null, register: async () => reg
  });
  const status = {stops: 0, reloads: 0};
  const player = {playing: 'exercise', scheduledVoices: 0,
    stop() { this.playing = null; this.scheduledVoices = 0; status.stops++; }
  };
  Object.assign(window, {GUITAR: {lessons: [], version: pageVersion}, isSecureContext: true, GuitarStudio: player});
  const navigator = {onLine: true, serviceWorker};
  const location = {reload: () => { status.reloads++; }};
  vm.runInNewContext(ui, {window, document, navigator, location, MessageChannel: TestChannel, setTimeout, clearTimeout});
  await turn();
  async function activate(version) {
    reg.waiting = null;
    reg.active = serviceWorker.controller = worker(version);
    markReady(reg);
    serviceWorker.emit('controllerchange');
    await turn();
  }
  return {activate, element, navigator, player, reg, serviceWorker, status, window};
}

test('first installation verifies offline readiness and claims the page without reloading', async () => {
  const p = await page({activeVersion: null, controlled: false});
  p.reg.installing = worker(pageVersion);
  p.reg.emit('updatefound');
  p.reg.installing.state = 'installed';
  p.reg.waiting = p.reg.installing;
  p.reg.installing.emit('statechange');
  assert.equal(p.element('courseUpdate').hidden, true);
  await p.activate(pageVersion);
  assert.match(p.element('offlineStatus').textContent, /Offline course ready/);
  assert.equal(p.element('courseUpdate').hidden, true);
  assert.deepEqual(p.status, {stops: 0, reloads: 0});
});

test('a waiting update stops playback and reloads once after the player applies it', async () => {
  const p = await page({waiting: true});
  assert.equal(p.element('courseUpdate').hidden, false);
  p.element('applyUpdate').emit('click');
  assert.ok(p.reg.waiting.commands.includes('ACTIVATE_COURSE_UPDATE'));
  await p.activate(newer);
  assert.deepEqual(p.status, {stops: 1, reloads: 1});
});

test('restarting playback during activation defers reload until the next explicit update', async () => {
  const p = await page({waiting: true});
  p.element('applyUpdate').emit('click');
  p.player.playing = 'jam';
  await p.activate(newer);
  assert.equal(p.player.playing, 'jam');
  assert.deepEqual(p.status, {stops: 1, reloads: 0});
  assert.equal(p.element('courseUpdate').hidden, false);
  p.element('applyUpdate').emit('click');
  assert.deepEqual(p.status, {stops: 2, reloads: 1});
});

test('older, newer, and matching controllers give the appropriate update and offline status', async () => {
  const p = await page({activeVersion: '1.1.0'});
  assert.match(p.element('offlineStatus').textContent, /earlier course/i);
  assert.equal(p.element('courseUpdate').hidden, true);
  p.navigator.onLine = false;
  p.window.emit('offline');
  assert.match(p.element('offlineStatus').textContent, /offline.*earlier course/i);
  await p.activate(newer);
  assert.equal(p.element('courseUpdate').hidden, false);
  await p.activate(pageVersion);
  assert.equal(p.element('courseUpdate').hidden, true);
  assert.match(p.element('offlineStatus').textContent, /offline.*ready/i);
  assert.deepEqual(p.status, {stops: 0, reloads: 0});
});

test('an uncontrolled tab notices a newly waiting worker for an existing installation', async () => {
  const p = await page({controlled: false});
  p.reg.installing = worker(newer);
  p.reg.emit('updatefound');
  p.reg.installing.state = 'installed';
  p.reg.waiting = p.reg.installing;
  p.reg.installing.emit('statechange');
  assert.equal(p.element('courseUpdate').hidden, false);
  assert.deepEqual(p.status, {stops: 0, reloads: 0});
});
