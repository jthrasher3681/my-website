'use strict';
(() => {
 const $ = id => document.getElementById(id);
 const G = window.GUITAR;
 const normalize = value => String(value).normalize('NFKD').toLowerCase()
  .replace(/[♯#]/g, ' sharp ').replace(/♭/g, ' flat ')
  .replace(/[^a-z0-9]+/g, ' ').trim();
 const index = new Map(G.lessons.map(lesson => [lesson.id, normalize([
  lesson.id, lesson.title, lesson.goal, lesson.why, ...lesson.steps,
  G.subjects[lesson.subject][0], ...lesson.progression,
  ...lesson.patterns.map(pattern => pattern.title)
 ].join(' '))]));
 let query = '', filter = 'all', wasFiltered = false;

 function filterLibrary() {
  const terms = normalize(query).split(/\s+/).filter(Boolean);
  const active = terms.length > 0 || filter !== 'all';
  let matches = 0;
  for (const nav of [$('courseNav'), $('mobileCourseNav')]) {
   let count = 0;
   for (const group of nav.querySelectorAll('.subject-group')) {
    let groupMatches = 0;
    for (const button of group.querySelectorAll('[data-lesson]')) {
     const completed = !!button.querySelector('.done');
     const text = index.get(Number(button.dataset.lesson)) || '';
     const visible = terms.every(term => text.includes(term)) &&
      (filter === 'all' || (filter === 'complete' ? completed : !completed));
     button.hidden = !visible;
     if (visible) { count++; groupMatches++; }
    }
    group.hidden = groupMatches === 0;
    if (active && groupMatches) group.open = true;
    else if (wasFiltered && !active) group.open = !!group.querySelector('[aria-current="true"]');
   }
   matches = count;
  }
  const result = !active ? '' : matches ? matches + (matches === 1 ? ' lesson matches' : ' lessons match') :
   !terms.length && filter === 'complete' ? 'No completed lessons yet.' :
   !terms.length && filter === 'incomplete' ? 'All 32 checkpoints complete.' : 'No matches. Try another term.';
  document.querySelectorAll('[data-library-results]').forEach(element => { element.textContent = result; });
  document.querySelectorAll('[data-library-clear]').forEach(button => { button.hidden = !active; });
  wasFiltered = active;
 }
 function syncFilters() {
  document.querySelectorAll('[data-library-search]').forEach(input => { if (input.value !== query) input.value = query; });
  document.querySelectorAll('[data-library-filter]').forEach(select => { select.value = filter; });
  filterLibrary();
 }
 document.querySelectorAll('[data-library-search]').forEach(input => {
  input.addEventListener('input', () => { query = input.value; syncFilters(); });
  input.addEventListener('search', () => { query = input.value; syncFilters(); });
 });
 document.querySelectorAll('[data-library-filter]').forEach(select => {
  select.addEventListener('change', () => { filter = select.value; syncFilters(); });
 });
 document.querySelectorAll('[data-library-clear]').forEach(button => {
  button.addEventListener('click', () => {
   query = ''; filter = 'all'; syncFilters();
   button.closest('.library-search').querySelector('input').focus();
  });
 });
 document.addEventListener('guitar:library-rendered', filterLibrary);
 filterLibrary();

 /* A waiting update is applied only when the player chooses it. */
 let registration = null, waitingWorker = null, reloadReady = false;
 let offlineReady = false, applying = false, updateTimeout = null, statusTicket = 0;
 let offlineProblem = '', earlierCache = false;
 const updateBox = $('courseUpdate'), applyButton = $('applyUpdate');
 const newerVersion = (a, b) => {
  if (!/^\d+\.\d+\.\d+$/.test(a || '') || !/^\d+\.\d+\.\d+$/.test(b || '')) return false;
  const left = a.split('.').map(Number), right = b.split('.').map(Number);
  for (let i = 0; i < 3; i++) if (left[i] !== right[i]) return left[i] > right[i];
  return false;
 };

 function offlineStatus() {
  if (!navigator.onLine) {
   $('offlineStatus').textContent = offlineReady ? 'You are offline · cached lessons and audio are ready.' :
    earlierCache ? 'You are offline · only an earlier course version has been verified in the cache.' :
    'You are offline · this device’s course cache has not been verified.';
  } else if (waitingWorker || reloadReady) {
   $('offlineStatus').textContent = 'A course update is ready · apply it after practice.';
  } else if (!offlineReady && (offlineProblem || earlierCache)) {
   $('offlineStatus').textContent = offlineProblem || 'An earlier course is cached · reopen online to finish updating.';
  } else {
   $('offlineStatus').textContent = offlineReady ? 'Offline course ready · progress stays on this device.' :
    'Online mode · preparing the course for offline practice.';
  }
 }
 async function verifyOffline(worker) {
  if (!worker) return;
  const ticket = ++statusTicket;
  const result = await new Promise(resolve => {
   const channel = new MessageChannel();
   const timeout = setTimeout(() => { channel.port1.close(); resolve(null); }, 2500);
   channel.port1.onmessage = event => {
    clearTimeout(timeout); channel.port1.close(); resolve(event.data);
   };
   try { worker.postMessage({type:'GET_COURSE_VERSION'}, [channel.port2]); }
   catch (_) { clearTimeout(timeout); channel.port1.close(); resolve(null); }
  });
  if (ticket !== statusTicket) return;
  offlineReady = !!result?.offlineReady && result.version === G.version;
  earlierCache = !!result?.version && newerVersion(G.version, result.version);
  if (result?.version && newerVersion(result.version, G.version) && !waitingWorker) {
   reloadReady = true; showUpdate();
  } else if (offlineReady && !waitingWorker && !applying) {
   reloadReady = false; updateBox.hidden = true;
  }
  offlineStatus();
  if (!result && !waitingWorker && !reloadReady && navigator.onLine && !offlineProblem) {
   $('offlineStatus').textContent = 'Online mode · reopen after the course update to confirm offline availability.';
  }
 }
 function showUpdate(worker) {
  if (worker) waitingWorker = worker;
  if (!waitingWorker && !reloadReady) return;
  updateBox.hidden = false;
  $('updateMessage').textContent = 'Update when you finish this pass. Playback will stop; your saved progress is kept.';
  applyButton.disabled = false;
  applyButton.textContent = 'Update course';
  offlineStatus();
 }
 $('dismissUpdate').addEventListener('click', () => { updateBox.hidden = true; });
 applyButton.addEventListener('click', () => {
  window.GuitarStudio?.stop();
  if (reloadReady && !waitingWorker) { location.reload(); return; }
  const worker = registration?.waiting || waitingWorker;
  if (!worker || worker.state === 'redundant') {
   waitingWorker = null; updateBox.hidden = true; offlineStatus(); return;
  }
  applying = true; applyButton.disabled = true; applyButton.textContent = 'Updating…';
  $('updateMessage').textContent = 'Loading the updated course. Your practice progress is saved.';
  clearTimeout(updateTimeout);
  updateTimeout = setTimeout(() => {
   applying = false; applyButton.disabled = false; applyButton.textContent = 'Try update again';
   $('updateMessage').textContent = 'The update is taking longer than expected. Try again, or close all course windows and reopen.';
  }, 10000);
  try { worker.postMessage({type:'ACTIVATE_COURSE_UPDATE'}); }
  catch (_) {
   clearTimeout(updateTimeout); applying = false; applyButton.disabled = false;
   $('updateMessage').textContent = 'The update could not start. Reopen the course and try again.';
  }
 });

 if ('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.addEventListener('controllerchange', () => {
   if (applying) {
    clearTimeout(updateTimeout);
    if (!window.GuitarStudio?.playing && !window.GuitarStudio?.scheduledVoices) { location.reload(); return; }
    applying = false; waitingWorker = null; reloadReady = true; showUpdate();
    $('updateMessage').textContent = 'The update is installed. Finish playing, then choose Update course to reload.';
    return;
   }
   waitingWorker = null;
   verifyOffline(navigator.serviceWorker.controller);
  });
  navigator.serviceWorker.register('./sw.js', {scope:'./', updateViaCache:'none'}).then(reg => {
   registration = reg;
   if (reg.waiting && reg.active) showUpdate(reg.waiting);
   const watch = worker => {
    if (!worker) return;
    worker.addEventListener('statechange', () => {
     if (worker.state === 'installed' && reg.active && reg.active !== worker) showUpdate(reg.waiting || worker);
     if (worker.state === 'redundant' && !reg.active && navigator.onLine) {
      offlineProblem = 'Online mode · offline download did not finish. Reopen online to try again.';
      offlineStatus();
     }
    });
   };
   watch(reg.installing);
   reg.addEventListener('updatefound', () => watch(reg.installing));
   navigator.serviceWorker.ready.then(ready => verifyOffline(ready.active));
  }).catch(() => {
   offlineProblem = 'Online mode · offline caching is unavailable in this browser.';
   offlineStatus();
  });
  if (navigator.serviceWorker.controller) verifyOffline(navigator.serviceWorker.controller);
 } else {
  offlineProblem = 'Online mode · offline installation requires HTTPS and service-worker support.';
  offlineStatus();
 }
 window.addEventListener('offline', offlineStatus);
 window.addEventListener('online', () => { offlineStatus(); registration?.update().catch(() => {}); });
 document.addEventListener('visibilitychange', () => {
  if (!document.hidden && (registration?.waiting || reloadReady)) showUpdate(registration?.waiting);
 });
})();
