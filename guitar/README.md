# Guitar Practice Studio

32 original intermediate guitar lessons, grouped into eight subjects. Static HTML/CSS/JavaScript: no build step, account, analytics, microphone, CDN, or server-side storage.

## Publishing

Keep this directory at `/guitar/` in the existing GitHub Pages source. The root homepage, CNAME, workflows and other applications are intentionally unchanged. Open `https://jthrashercompanies.com/guitar/`. Deep links use `#lesson-1` through `#lesson-32`; the featured G-C-D exercise is lesson 9.

## Features

- Learn / Play / Jam workflow in every lesson, with concrete steps and checkpoints.
- Note-by-note playable standard-tuning tabs, duration-aware bar layout, focus-note coloring and synchronized highlighting.
- Eight- and sixteenth-note rhythm grids, muted attacks, slide/bend synthesis and illustrative vibrato.
- Web Audio clock scheduling, 40–160 BPM, optional count-in, click, volume and looping.
- Chord diagrams with finger numbers and synthetic previews; no thumb-over shapes.
- Per-lesson backing progressions, 1/3/6 rounds or continuous playback, optional third/root cue.
- Randomized chord-quality, seventh-quality and interval quizzes.
- Local notes, tempo and completion; JSON export/import. No cross-device sync or live-playing assessment.
- Scoped service worker, standalone web manifest and Home Screen icons. Offline use requires one successful online cache installation.

## Local testing

From the repository root: `python3 -m http.server 8000`; visit `http://localhost:8000/guitar/`. Test all 32 lesson selectors, every phrase, chord previews, each transport mode, tempo changes, finite jams, Stop, quizzes, progress reload, export/import and offline reload. Test small portrait viewports and keyboard navigation. Audio deliberately stops on page hide/lock rather than promising unreliable background scheduling.

## Maintenance

Lesson data is in `lessons.js`. String 1 is high e; string 6 is low E. Durations are quarter-note beats. A note token `2:8b10!@2` means B-string fret 8 bent toward fret 10's pitch, highlighted, held for two beats. `1:h7` and `1:p5` indicate legato arrivals; `2:5s8` is a slide, and `2:8v` adds vibrato. The default duration is half a beat. `-@1` is a one-beat rest. Each exercise has complete 4/4 bars.

When updating cached files, increment the cache version in `sw.js`. It may only delete caches whose names begin with `thrasher-guitar-studio-`, and only intercept requests within `/guitar/`. Do not broaden its scope to the site's root.
