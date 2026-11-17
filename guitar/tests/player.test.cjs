'use strict';

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = name => readFileSync(join(__dirname, '..', name), 'utf8');
const storageKey = 'thrasher-guitar-studio-v1';
const hz = midi => 440 * 2 ** ((midi - 69) / 12);

function makeClock() {
  let now = 0;
  let nextId = 0;
  const timers = new Map();
  function schedule(fn, delay, repeat = false) {
    const id = ++nextId;
    timers.set(id, { fn, at: now + delay, interval: repeat ? delay : 0 });
    return id;
  }
  function advance(milliseconds) {
    const end = now + milliseconds;
    while (true) {
      const due = [...timers.entries()]
        .filter(([, timer]) => timer.at <= end)
        .sort(([idA, a], [idB, b]) => a.at - b.at || idA - idB)[0];
      if (!due) break;
      const [id, timer] = due;
      now = timer.at;
      if (timer.interval) timer.at += timer.interval;
      else timers.delete(id);
      timer.fn();
    }
    now = end;
  }
  return { get seconds() { return now / 1000; }, schedule, cancel: id => timers.delete(id), advance };
}

function audioContext(clock, tones) {
  function param() {
    return {
      value: 0,
      setValueAtTime(value) { this.value = value; },
      setTargetAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {}
    };
  }
  function node() {
    return {
      gain: param(), frequency: param(), threshold: param(), knee: param(), ratio: param(),
      connect() {}, disconnect() {}, stop() {},
      start(time) { tones.push({ time, frequency: this.frequency.value }); }
    };
  }
  return class AudioContext {
    state = 'running';
    sampleRate = 44100;
    destination = {};
    get currentTime() { return clock.seconds; }
    createBuffer(_, length) { return { getChannelData: () => new Float32Array(length) }; }
    createGain() { return node(); }
    createOscillator() { return node(); }
    createBufferSource() { return node(); }
    createBiquadFilter() { return node(); }
    createDynamicsCompressor() { return node(); }
  };
}

// The real UI handlers run against a small DOM surface. The clock records the
// Web Audio notes they schedule and runs their display callbacks at audio time.
function studio(savedState) {
  const clock = makeClock(), tones = [], elements = new Map(), listeners = new Map();
  let stored = savedState && JSON.stringify(savedState), confirmations = 0;
  function element(id) {
    if (!elements.has(id)) {
      elements.set(id, {
        textContent: '', innerHTML: '', value: '', checked: false, dataset: {},
        classList: { add() {}, remove() {}, toggle() {} }, setAttribute() {}, focus() {},
        addEventListener() {}, querySelector() { return null; },
        replaceChildren() { this.innerHTML = ''; }
      });
    }
    return elements.get(id);
  }
  const document = {
    getElementById: element,
    addEventListener(type, callback) { listeners.set(type, callback); },
    dispatchEvent() {},
    querySelector(selector) { return selector === '.stage-tabs' ? element('stageTabs') : null; },
    querySelectorAll() { return []; }
  };
  const env = {
    document, Event, navigator: {}, location: { hash: '' }, history: { replaceState() {} },
    AudioContext: audioContext(clock, tones), scrollTo() {}, addEventListener() {},
    localStorage: {
      getItem(key) { assert.equal(key, storageKey); return stored; },
      setItem(key, data) { assert.equal(key, storageKey); stored = data; }
    },
    confirm() { confirmations++; return true; },
    setTimeout: (fn, delay) => clock.schedule(fn, delay),
    setInterval: (fn, delay) => clock.schedule(fn, delay, true),
    clearTimeout: clock.cancel, clearInterval: clock.cancel
  };
  env.window = env;
  const context = vm.createContext(env);
  for (const file of ['lessons.js', 'studio.js']) vm.runInContext(source(file), context, { filename: file });

  function change(id, value) {
    const control = element(id);
    if (typeof value === 'boolean') control.checked = value;
    else control.value = String(value);
    (control.onchange || control.oninput)({ target: control });
  }
  async function press(id) {
    element(id).onclick();
    await new Promise(resolve => setImmediate(resolve));
  }
  async function choose(dataset) {
    const button = { dataset };
    listeners.get('click')({ target: { closest: () => button } });
    await new Promise(resolve => setImmediate(resolve));
  }
  async function restore(raw) {
    const file = { size: 100, text: async () => JSON.stringify({ app: 'Thrasher Guitar Studio', schema: 1, state: raw }) };
    await element('importFile').onchange({ target: { files: [file] } });
  }
  return {
    player: env.GuitarStudio, data: env.GUITAR, advance: clock.advance, element, tones,
    saved: () => JSON.parse(stored), confirmations: () => confirmations, change, press, choose, restore
  };
}

test('four count-in clicks lead into the selected bar and a single pass ends on time', async () => {
  const app = studio();
  app.player.selectLesson(3); // Four quarter notes per bar at 60 BPM.
  app.change('loopStart', 2);
  app.change('loopEnd', 2);
  app.change('loopExercise', false);
  app.change('clickEnabled', false);
  await app.press('playExercise');
  app.advance(3950);
  assert.match(app.element('playStatus').textContent, /Count in · 4/);
  assert.deepEqual(app.tones.map(t => t.frequency), [89, 81, 81, 81].map(hz));
  app.advance(140);
  assert.match(app.element('playStatus').textContent, /Exercise · bar 2 · beat 1/);
  app.advance(3800);
  assert.deepEqual(app.tones.slice(4).map(t => t.frequency), [45, 52, 55, 60].map(hz));
  assert.equal(app.player.playing, 'exercise');
  app.advance(250);
  assert.equal(app.player.playing, null);
  assert.match(app.element('playStatus').textContent, /Exercise complete/);
});

test('trainer increases after complete section passes, clamps to the target, and saves the tempo', async () => {
  const app = studio();
  app.player.selectLesson(3);
  app.change('loopStart', 2);
  app.change('loopEnd', 2);
  app.change('tempo', 97);
  app.change('countIn', false);
  app.change('speedTrainer', true);
  app.change('trainerStep', 5);
  await app.press('playExercise');

  app.advance(2600);
  assert.equal(app.player.trainerPasses, 1);
  assert.equal(app.player.bpm, 97);
  app.advance(2380); // Still before the second pass ends at 80ms + 8 × 60/97 s.
  assert.equal(app.player.bpm, 97);
  app.advance(100);
  assert.equal(app.player.bpm, 100);
  assert.equal(app.player.trainerPasses, 0);
  assert.equal(app.saved().bpms[3], 100);
  assert.match(app.element('loopSummary').textContent, /2.4 seconds per pass at 100 BPM/);
  app.advance(7000);
  assert.equal(app.player.bpm, 100);
  app.change('tempo', 120);
  app.advance(7000);
  assert.equal(app.player.bpm, 120);
  app.change('loopEnd', 3);
  assert.equal(app.player.playing, null);
  assert.equal(app.player.trainerPasses, 0);
});

test('trainer leaves a jam, metronome, and non-looping exercise at the chosen tempo', async () => {
  const app = studio();
  app.player.selectLesson(1);
  app.change('countIn', false);
  app.change('speedTrainer', true);
  for (const id of ['playJam', 'playClick']) {
    await app.press(id);
    app.advance(15000);
    assert.equal(app.player.bpm, 60);
    assert.equal(app.player.trainerPasses, 0);
  }
  app.change('loopExercise', false);
  await app.press('playExercise');
  app.advance(9000);
  assert.equal(app.player.playing, null);
  assert.equal(app.player.bpm, 60);
});

test('the transcription exercise has no hidden-tab labels or live pitch feedback', async () => {
  const app = studio();
  app.player.selectLesson(28);
  app.change('countIn', false);
  const hidden = () => {
    assert.equal(app.element('tabContent').innerHTML, '');
    assert.equal(app.element('noteInfo').textContent, '');
  };
  hidden();
  await app.press('playExercise');
  app.advance(2000);
  hidden();
  assert.ok(app.tones.length > 0);
  await app.press('hideTab');
  app.advance(1100);
  assert.match(app.element('tabContent').innerHTML, /data-note=/);
  assert.match(app.element('noteInfo').textContent, /fret/);
  await app.press('hideTab');
  hidden();
  app.advance(5000);
  hidden();
});

test('practice preferences and lesson selections round-trip, including mute and selected bars', async () => {
  const app = studio();
  app.player.selectLesson(3);
  app.change('loopStart', 2);
  app.change('loopEnd', 3);
  app.player.setStage('jam');
  app.player.selectLesson(1);
  await app.choose({ pattern: '2' });
  app.player.setStage('play');
  const settings = { volume: 0, countIn: false, clickEnabled: false, loopExercise: false, showNotes: false, guideTone: true, speedTrainer: true, trainerStep: 5, trainerPasses: 4 };
  for (const [id, value] of Object.entries(settings)) app.change(id, value);

  const loaded = studio(app.saved());
  assert.equal(loaded.player.lessonId, 1);
  assert.equal(loaded.player.patternIndex, 2);
  assert.equal(loaded.player.stage, 'play');
  for (const [id, value] of Object.entries(settings)) {
    const control = loaded.element(id);
    assert.equal(typeof value === 'boolean' ? control.checked : Number(control.value), value);
  }
  loaded.player.selectLesson(3);
  assert.equal(loaded.player.stage, 'jam');
  assert.equal(loaded.player.loopSelection.start, 2);
  assert.equal(loaded.player.loopSelection.end, 3);
  await loaded.press('resetLoop');
  assert.equal(loaded.player.loopSelection.start, 1);
  assert.equal(loaded.player.loopSelection.end, 4);
});

test('schema-1 backups restore original progress and malformed input cannot replace it', async () => {
  const app = studio();
  const legacy = { last: 1, rounds: 0, done: { 1: true }, notes: { 1: '<practice>' }, bpms: { 1: 61 } };
  await app.restore(legacy);
  assert.equal(app.player.lessonId, 1);
  assert.equal(app.player.bpm, 61);
  assert.equal(app.element('notes').value, '<practice>');
  assert.equal(app.element('complete').checked, true);
  assert.equal(Number(app.element('rounds').value), 0);
  for (const invalid of ['broken', [], {}, { ...legacy, last: [1] }, { ...legacy, notes: 'invalid' }]) {
    await app.restore(invalid);
  }
  assert.equal(app.confirmations(), 1);
  assert.equal(app.saved().done[1], true);

  await app.restore({
    ...legacy,
    practice: { 1: { pattern: 99, stage: 'missing', sections: { 0: { start: -1, end: 99 } } } },
    settings: { volume: false, guideTone: 'yes', trainerPasses: -1, trainerStep: 6 }
  });
  assert.equal(app.player.patternIndex, 0);
  assert.equal(app.player.stage, 'learn');
  assert.equal(app.player.loopSelection.start, 1);
  assert.equal(app.player.loopSelection.end, 1);
  assert.equal(Number(app.element('volume').value), 65);
  assert.equal(app.element('guideTone').checked, false);
  assert.equal(Number(app.element('trainerPasses').value), 2);
});

test('exercise buttons preview three treble notes while the jam retains its full chords and bass', async () => {
  const app = studio();
  app.player.selectLesson(21);
  const tonesSince = index => app.tones.slice(index).map(t => t.frequency);
  for (const [name, frets, pitches] of [
    ['G', '4, 3, 3', [59, 62, 67]],
    ['C', '5, 5, 3', [60, 64, 67]],
    ['D', '7, 7, 5', [62, 66, 69]]
  ]) {
    const before = app.tones.length;
    await app.choose({ chord: name });
    assert.ok(app.element('chordDiagram').innerHTML.includes('muted, muted, muted, ' + frets));
    assert.deepEqual(tonesSince(before), pitches.map(hz));
  }
  const beforePreview = app.tones.length;
  const fullG = [43, 47, 50, 55, 59, 67];
  await app.choose({ jambar: '0' });
  assert.deepEqual(tonesSince(beforePreview), fullG.map(hz));
  const beforeJam = app.tones.length;
  app.change('countIn', false);
  app.change('clickEnabled', false);
  await app.press('playJam');
  assert.deepEqual(tonesSince(beforeJam), [...fullG, 31].map(hz));
});
