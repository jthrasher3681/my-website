# Guitar Practice Studio

32 original intermediate guitar lessons, grouped into eight subjects, with 61 playable studies across 91 measures. Version 1.1.0. Static HTML/CSS/JavaScript: no build step, account, analytics, microphone, CDN, or server-side storage.

[View the reviewed practice screen](docs/practice-tools.jpg)

## Publishing

Keep this directory at `/guitar/` in the existing GitHub Pages source. The root homepage, CNAME, workflows and other applications are intentionally unchanged. Open `https://jthrashercompanies.com/guitar/`. Deep links use `#lesson-1` through `#lesson-32`; the featured G-C-D exercise is lesson 9.

## Features

- Learn / Play / Jam workflow in every lesson, with concrete steps and checkpoints.
- Search all lessons by topic, title or teaching content; filter completed or unfinished lessons on desktop and mobile.
- Note-by-note playable standard-tuning tabs, duration-aware bar layout, focus-note coloring and synchronized highlighting.
- Isolate any complete bar range, with a four-beat count-in and accurate repeat boundaries. Narrow tablature follows the playing note horizontally without moving the page.
- Optional tempo trainer: add 2 or 5 BPM every 2 or 4 completed passes, stopping at the lesson target. It does not listen to or assess the player; switch it off or slow down whenever more clean repetitions are needed.
- Eight- and sixteenth-note rhythm grids, muted attacks, slide/bend synthesis and illustrative vibrato.
- Web Audio clock scheduling, 40–160 BPM, optional count-in, click, volume and looping.
- Chord diagrams with finger numbers and synthetic previews; no thumb-over shapes. The treble-triad lesson uses its exact small grips, and the chord-embellishment comparison keeps high e open.
- Per-lesson backing progressions, 1/3/6 rounds or continuous playback, optional third/root cue.
- Randomized chord-quality, seventh-quality and interval quizzes.
- Local notes, tempo, completion, selected phrase, practice stage, bar range and playback preferences; JSON export/import remains compatible with version 1.0 backups. No cross-device sync or live-playing assessment.
- Hidden ear-training tabs also conceal pitch descriptions and note highlighting until revealed. Original chromatic-approach and sparse fingerstyle variations in lessons 9 and 10.
- Scoped service worker, standalone web manifest and Home Screen icons. Offline use requires one successful online cache installation. An update waits until the player selects Update course; progress is retained.

## Upgrading an installed app

Version 1.0 did not have an update button. Close every open Guitar Studio tab and Home Screen window, then reopen online once to load 1.1.0. Confirm the version and “Offline course ready” in the footer. Later releases can use the Update course banner. New files are downloaded together before activation; an earlier release remains cached for older open tabs.

## Local testing

From the repository root: `python3 -m http.server 8000`; visit `http://localhost:8000/guitar/`. Test all 32 lesson selectors, every phrase, chord previews, each transport mode, tempo changes, finite jams, Stop, quizzes, progress reload, export/import and offline reload. Test small portrait viewports and keyboard navigation. Audio deliberately stops on page hide/lock rather than promising unreliable background scheduling.

Run the dependency-free regression checks with `node --test guitar/tests/*.test.cjs`. They verify musical pitch expectations, complete measures, hidden answers, old progress backups, selected-bar scheduling, tempo-training limits, matching triad previews, and scoped offline update behavior. These tests use a simulated audio clock and service-worker environment; browser and physical-device checks remain separate.

## Maintenance

Lesson data is in `lessons.js`. String 1 is high e; string 6 is low E. Durations are quarter-note beats. A note token `2:8b10!@2` means B-string fret 8 bent toward fret 10's pitch, highlighted, held for two beats. `1:h7` and `1:p5` indicate legato arrivals; `2:5s8` is a slide, and `2:8v` adds vibrato. The default duration is half a beat. `-@1` is a one-beat rest. Each exercise has complete 4/4 bars.

Multi-chord patterns use `barChords` for bar captions. A pattern may provide `voicing` for its principal chord or `voicings` by chord name for exact instructional diagrams/previews. Backing jams use the canonical chord definitions.

When updating cached files, change the release in `sw.js`, `lessons.js`, and the four script/stylesheet query strings in `index.html` together. Keep the offline asset list complete, including `ui.js`. The worker caches only the course root/index and its known assets, scopes cache cleanup to the current installation path, and retains the immediately preceding release. Do not broaden its production scope beyond `/guitar/`. `ui.js` handles lesson search and the explicit update prompt; `studio.js` owns the player and progress.
