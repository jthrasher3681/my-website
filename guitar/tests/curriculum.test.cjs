'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = { window: {} };
const file = path.join(__dirname, '..', 'lessons.js');
vm.runInNewContext(fs.readFileSync(file, 'utf8'), context, { filename: file });
const { chords, lessons } = structuredClone(context.window.GUITAR);

const openStrings = [40, 45, 50, 55, 59, 64]; // MIDI, low E to high e
const pitchClasses = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B'];
const spellings = {
  G: 'G B D', Gm: 'G Bb D', G7: 'G B D F', Gmaj7: 'G B D F#',
  C: 'C E G', Cmaj7: 'C E G B', C7: 'C E G Bb', Cm7: 'C Eb G Bb', Cadd9: 'C E G D',
  D: 'D F# A', Dm: 'D F A', D7: 'D F# A C', Dm7: 'D F A C',
  Am: 'A C E', Am7: 'A C E G', Asus2: 'A B E', A: 'A C# E', A7: 'A C# E G',
  Em7: 'E G B D', E7: 'E G# B D', Fmaj7: 'F A C E', 'G/B': 'G B D'
};

function pitch(note) {
  return openStrings[6 - note.string] + note.fret;
}

function soundingPitches(shape) {
  return shape.frets.flatMap((fret, index) => fret < 0 ? [] : [openStrings[index] + fret]);
}

function tones(pitches) {
  return new Set(pitches.map(p => pitchClasses[p % 12]));
}

function checkShape(name, shape) {
  const expected = spellings[name].split(' ');
  assert.equal(pitchClasses[shape.root % 12], expected[0], name + ' root');
  assert.deepEqual(tones(shape.intervals.map(i => shape.root + i)), new Set(expected), name + ' spelling');
  assert.equal(shape.frets.length, 6, name);
  assert.equal(shape.fingers.length, 6, name);
  for (const [index, fret] of shape.frets.entries()) {
    assert.ok(Number.isInteger(fret) && fret >= -1, name + ' frets');
    const finger = shape.fingers[index];
    assert.ok(fret > 0 ? Number.isInteger(finger) && finger >= 1 && finger <= 4 : finger === 0,
      name + ' fingering on string ' + (6 - index));
  }
  const pitches = soundingPitches(shape);
  // The course uses an open C7 shell, and explicitly teaches its omitted fifth.
  if (name === 'C7') {
    assert.match(shape.tip, /omit.*fifth/i);
    expected.splice(expected.indexOf('G'), 1);
  }
  assert.deepEqual(tones(pitches), new Set(expected), name + ' sounding shape');
  if (name === 'G/B') assert.equal(pitchClasses[Math.min(...pitches) % 12], 'B');
}

test('chord spellings and fingerings sound the intended harmonies in standard tuning', () => {
  assert.deepEqual(new Set(Object.keys(chords)), new Set(Object.keys(spellings)));
  for (const [name, shape] of Object.entries(chords)) checkShape(name, shape);
  for (const lesson of lessons) {
    for (const pattern of lesson.patterns) {
      if (pattern.voicing) checkShape(pattern.chord, pattern.voicing);
    }
  }
});

test('each study fits full 4/4 bars and references playable harmonies', () => {
  for (const lesson of lessons) {
    for (const pattern of lesson.patterns) {
      const label = 'Lesson ' + lesson.id + ', ' + pattern.title;
      const harmonies = [...lesson.progression, pattern.chord, ...(pattern.progression || []),
        ...(pattern.barChords || [])];
      for (const chord of harmonies) assert.ok(Object.hasOwn(chords, chord), label + ': ' + chord);
      let elapsed = 0;
      for (const note of pattern.notes) {
        assert.ok(note.duration > 0 && Number.isInteger(note.duration * 4), label + ' subdivision');
        assert.ok(elapsed % 4 + note.duration <= 4, label + ' event crosses bar line');
        if (!note.rest && !note.action) {
          assert.ok(Number.isInteger(note.string) && note.string >= 1 && note.string <= 6, label);
          assert.ok(Number.isInteger(note.fret) && note.fret >= 0, label);
        }
        elapsed += note.duration;
      }
      assert.ok(elapsed >= 4 && elapsed % 4 === 0, label + ' incomplete bar');
      if (pattern.barChords) {
        assert.equal(pattern.barChords.length, elapsed / 4, label + ' bar labels');
        assert.equal(pattern.barChords[0], pattern.chord, label + ' first harmony');
      }
    }
  }
});

test('lesson 21 teaches exactly the three treble strings in each triad diagram', () => {
  const expected = { G: [59, 62, 67], C: [60, 64, 67], D: [62, 66, 69] }; // B-D-G, C-E-G, D-F#-A
  const { patterns } = lessons.find(l => l.id === 21);
  assert.deepEqual(patterns.map(p => p.chord), ['G', 'C', 'D']);
  for (const { chord, voicing, notes } of patterns) {
    assert.deepEqual(voicing.frets.slice(0, 3), [-1, -1, -1]);
    assert.deepEqual(soundingPitches(voicing), expected[chord]);
    assert.deepEqual(new Set(notes.map(pitch)), new Set(expected[chord]));
    for (const note of notes) assert.equal(note.fret, voicing.frets[6 - note.string]);
  }
});

test('lesson 31 changes only the B string for each embellishment in the diagrams and tab', () => {
  const pattern = lessons.find(l => l.id === 31).patterns[0];
  assert.deepEqual(pattern.barChords, ['C', 'Cadd9', 'Am', 'Asus2']);
  for (const [firstBar, delta] of [[0, 2], [2, -1]]) {
    const [first, second] = pattern.barChords.slice(firstBar, firstBar + 2).map(name => chords[name]);
    assert.deepEqual(second.frets.map((fret, index) => fret - first.frets[index]), [0, 0, 0, 0, delta, 0]);
    const start = firstBar * 4;
    const before = pattern.notes.slice(start, start + 4);
    const after = pattern.notes.slice(start + 4, start + 8);
    assert.equal(before[2].string, 2);
    for (let i = 0; i < 4; i++) {
      assert.equal(after[i].string, before[i].string);
      assert.equal(pitch(after[i]) - pitch(before[i]), before[i].string === 2 ? delta : 0);
    }
  }
});

test('lesson 9 targets B, E and F-sharp and resolves the chromatic pickup on the C downbeat', () => {
  const { patterns } = lessons.find(l => l.id === 9);
  for (const [chord, third] of Object.entries({ G: 'B', C: 'E', D: 'F#' })) {
    const first = patterns.find(p => p.chord === chord && !p.barChords).notes[0];
    assert.equal(first.target, true);
    assert.equal(pitchClasses[pitch(first) % 12], third);
  }
  const pickup = patterns.find(p => p.barChords?.join(' ') === 'G C');
  const atBeat = new Map();
  let elapsed = 0;
  for (const note of pickup.notes) {
    atBeat.set(elapsed, note);
    elapsed += note.duration;
  }
  // Written "4 & 1": D4, E-flat4, E4, in the same octave.
  assert.deepEqual([3, 3.5, 4].map(beat => pitch(atBeat.get(beat))), [62, 63, 64]);
  assert.equal(atBeat.get(4).target, true);
});

test('the transcription exercise starts hidden and its instructions do not give away the melody', () => {
  const lesson = lessons.find(l => l.id === 28);
  assert.equal(lesson.hideInitially, true);
  const copy = [lesson.title, lesson.goal, lesson.why, ...lesson.steps, lesson.challenge,
    ...lesson.patterns.map(p => p.title)].join(' ');
  // G–C is the backing harmony given for the later jam. The exercise should
  // leave the first pitch, peak and resolution for the learner to find.
  const instructions = copy.replace(/\bG\s*[-–—]\s*C\b/g, '');
  assert.doesNotMatch(instructions, /\b(?:G|B|E)\b/);
});
