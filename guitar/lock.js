'use strict';
(() => {
 const RELEASE = '1.2.0';
 const $ = id => document.getElementById(id);
 const form = $('unlockForm'), passwordInput = $('coursePassword'), button = $('unlockButton');
 const status = $('unlockStatus'), reveal = $('togglePassword'), reload = $('lockReload');
 let opening = false, hasOpened = false, departed = false, registration = null;
 let offlineReady = false, offlineProblem = '', statusTicket = 0;

 // Distinguish this shell from an open pre-password copy during migration.
 if ('serviceWorker' in navigator) navigator.serviceWorker.addEventListener('message', event => {
  if (event.data?.type === 'IS_LOCK_SHELL') {
   (event.ports[0] || event.source)?.postMessage({type:'LOCK_SHELL_PRESENT', requestId:event.data.requestId});
  }
 });

 function setStatus(message, error = false) {
  status.textContent = message;
  status.classList.toggle('error', error);
  passwordInput.setAttribute('aria-invalid', error ? 'true' : 'false');
 }

 function offlineStatus() {
  const element = $('lockOfflineStatus');
  if (!element || hasOpened) return;
  element.textContent = offlineReady ?
   (navigator.onLine ? 'Offline access ready · your password is required each time.' : 'You are offline · enter your password to open the saved course.') :
   (!navigator.onLine ? 'You are offline · connect once to save the encrypted course on this device.' :
   offlineProblem || 'Preparing offline access…');
 }

 async function checkWorker(worker) {
  if (!worker || hasOpened) return;
  const ticket = ++statusTicket;
  const result = await new Promise(resolve => {
   const channel = new MessageChannel();
   const timeout = setTimeout(() => {channel.port1.close();resolve(null);}, 3000);
   channel.port1.onmessage = event => {clearTimeout(timeout);channel.port1.close();resolve(event.data);};
   try {worker.postMessage({type:'GET_COURSE_VERSION'}, [channel.port2]);}
   catch (_) {clearTimeout(timeout);channel.port1.close();resolve(null);}
  });
  if (ticket !== statusTicket || hasOpened) return;
  offlineReady = result?.version === RELEASE && !!result.offlineReady;
  if (result?.version && result.version !== RELEASE && /^\d+\.\d+\.\d+$/.test(result.version)) {
   const next = result.version.split('.').map(Number), here = RELEASE.split('.').map(Number);
   const difference = next.findIndex((value, index) => value !== here[index]);
   if (difference >= 0 && next[difference] > here[difference]) {location.reload();return;}
  }
  if (!result && navigator.onLine) offlineProblem = 'Connect and reopen once to finish saving offline access.';
  offlineStatus();
 }

 if ('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.addEventListener('controllerchange', () => checkWorker(navigator.serviceWorker.controller));
  navigator.serviceWorker.register('./sw.js', {scope:'./', updateViaCache:'none'}).then(reg => {
   registration = reg;
   const activateWhileLocked = worker => {
    if (!worker || hasOpened || opening) return;
    if (worker.state === 'installed' && reg.active) worker.postMessage({type:'ACTIVATE_COURSE_UPDATE'});
   };
   if (reg.waiting) activateWhileLocked(reg.waiting);
   const watch = worker => {
    if (!worker) return;
    worker.addEventListener('statechange', () => {
     activateWhileLocked(worker);
     if (worker.state === 'redundant' && !reg.active) {
      offlineProblem = 'Offline download did not finish. Reopen online to try again.';offlineStatus();
     }
    });
   };
   watch(reg.installing);
   reg.addEventListener('updatefound', () => watch(reg.installing));
   navigator.serviceWorker.ready.then(ready => checkWorker(ready.active));
  }).catch(() => {offlineProblem = 'Online access is ready. Offline saving is unavailable in this browser.';offlineStatus();});
  if (navigator.serviceWorker.controller) checkWorker(navigator.serviceWorker.controller);
 } else {
  offlineProblem = 'Online access only · offline saving requires a supported browser and HTTPS.';
  offlineStatus();
 }
 window.addEventListener('offline', offlineStatus);
 window.addEventListener('online', () => {offlineStatus();registration?.update().catch(() => {});});

 function lockCourse() {
  window.GuitarStudio?.stop();
  document.documentElement.style.visibility = 'hidden';
  location.reload();
 }
 window.addEventListener('pagehide', () => {
  departed = true;
  passwordInput.value = '';passwordInput.type = 'password';
  if (hasOpened || opening) {
   window.GuitarStudio?.stop();
   // Hide the decrypted page before a back/forward cache snapshot can be reused.
   document.documentElement.style.visibility = 'hidden';
  }
 });
 window.addEventListener('pageshow', event => {
  if (event.persisted) {location.reload();return;}
  departed = false;
 });

 async function runScript(source, name) {
  const url = URL.createObjectURL(new Blob([source], {type:'text/javascript'}));
  const script = document.createElement('script');
  script.src = url;
  script.dataset.courseSource = name;
  try {
   await new Promise((resolve, reject) => {
    script.onload = resolve;
    script.onerror = () => reject(new Error('Course script could not load.'));
    document.body.appendChild(script);
   });
  } finally {script.remove();URL.revokeObjectURL(url);}
 }

 async function mountCourse(payload) {
  const files = payload.files;
  const parsed = new DOMParser().parseFromString(files['index.html'].content, 'text/html');
  // All executable course code comes from the authenticated bundle. Keep the
  // shell's CSP and metadata; never request the former plaintext assets.
  parsed.querySelectorAll('script, link[rel="stylesheet"], base, meta[http-equiv]').forEach(node => node.remove());
  const style = document.createElement('style');
  style.textContent = files['studio.css'].content;
  document.head.querySelectorAll('link[rel="stylesheet"]').forEach(node => node.remove());
  document.head.appendChild(style);
  document.title = parsed.title || 'Guitar Practice Studio';
  document.body.replaceChildren(...Array.from(parsed.body.childNodes, node => document.importNode(node, true)));
  hasOpened = true;
  for (const name of ['lessons.js','studio.js','ui.js']) {
   if (departed) return;
   await runScript(files[name].content, name);
  }
  if (!window.GuitarStudio || window.GUITAR?.version !== RELEASE) throw new Error('Course startup did not finish.');
  $('lockCourse').addEventListener('click', lockCourse);
  window.GuitarLock = Object.freeze({lock:lockCourse, release:RELEASE});
  $('lessonTitle')?.focus({preventScroll:true});
  document.documentElement.style.visibility = '';
 }

 reveal.addEventListener('click', () => {
  const showing = passwordInput.type === 'password';
  passwordInput.type = showing ? 'text' : 'password';
  reveal.textContent = showing ? 'Hide' : 'Show';
  reveal.setAttribute('aria-label', showing ? 'Hide password' : 'Show password');
  reveal.setAttribute('aria-pressed', String(showing));
 });
 reload.addEventListener('click', () => location.reload());
 passwordInput.addEventListener('input', () => {if (!opening) setStatus('');});
 form.addEventListener('submit', async event => {
  event.preventDefault();
  if (opening || !passwordInput.value || !window.GuitarCrypto || !crypto.subtle) return;
  opening = true;button.disabled = true;passwordInput.disabled = true;reveal.disabled = true;reload.hidden = true;
  setStatus('Unlocking your course…');
  let password = passwordInput.value, payload = null, phase = 'download';
  try {
   const response = await fetch('./course.enc.json?v=' + RELEASE, {cache:'no-store', credentials:'same-origin'});
   if (!response.ok) throw new Error('Course download failed.');
   const text = await response.text();
   if (text.length > 16000000) throw new Error('Course download is invalid.');
   const envelope = JSON.parse(text);
   if (envelope.release !== RELEASE) throw new Error('The course has been updated.');
   phase = 'decrypt';
   payload = await window.GuitarCrypto.decrypt(envelope, password);
   password = '';passwordInput.value = '';
   if (departed) return;
   phase = 'mount';
   await mountCourse(payload);
  } catch (_) {
   if (hasOpened) {
    // A partially initialized app must not remain visible after a failed start.
    window.GuitarStudio?.stop();
    for (const element of document.body.children) element.hidden = true;
    const main = document.createElement('main');
    main.style.cssText = 'max-width:560px;margin:15vh auto;padding:24px';
    const heading = document.createElement('h1');heading.textContent = 'The course could not open.';
    const copy = document.createElement('p');copy.textContent = 'Your progress is still saved. Reload and enter your password to try again.';
    const retry = document.createElement('button');retry.textContent = 'Return to password screen';retry.onclick = lockCourse;
    main.append(heading,copy,retry);document.body.appendChild(main);
   } else if (!departed) {
    setStatus(phase === 'decrypt' ? 'That password didn’t unlock the course. Try again.' :
     navigator.onLine ? 'The encrypted course could not load. Reload the page and try again.' :
     'The course is not saved on this device yet. Connect to the internet and try again.', true);
    reload.hidden = phase !== 'download';
   }
  } finally {
   password = '';payload = null;passwordInput.value = '';passwordInput.type = 'password';
   reveal.textContent = 'Show';reveal.setAttribute('aria-label','Show password');reveal.setAttribute('aria-pressed','false');
   opening = false;
   if (!hasOpened) {
    button.disabled = false;passwordInput.disabled = false;reveal.disabled = false;
    if (!departed) passwordInput.focus({preventScroll:true});
   }
  }
 });

 if (!window.isSecureContext || !window.GuitarCrypto || !window.crypto?.subtle) {
  setStatus('Open this course over HTTPS in an up-to-date browser to unlock it.', true);
  button.disabled = true;
 } else {button.disabled = false;}
})();
