'use strict';
(() => {
const G=window.GUITAR, $=id=>document.getElementById(id);
const STORE='thrasher-guitar-studio-v1';
const TUNING=[64,59,55,50,45,40];
const NAMES=['C','C♯','D','E♭','E','F','F♯','G','G♯','A','B♭','B'];
const SPELLINGS={G:'G B D',Gm:'G B♭ D',G7:'G B D F',Gmaj7:'G B D F♯',C:'C E G',Cmaj7:'C E G B',C7:'C E G B♭',Cm7:'C E♭ G B♭',Cadd9:'C E G D',D:'D F♯ A',Dm:'D F A',D7:'D F♯ A C',Dm7:'D F A C',Am:'A C E',Am7:'A C E G',Asus2:'A B E',A:'A C♯ E',A7:'A C♯ E G',Em7:'E G B D',E7:'E G♯ B D',Fmaj7:'F A C E','G/B':'G B D · bass B'};
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const noteName=(n,octave=false)=>NAMES[((n%12)+12)%12]+(octave?Math.floor(n/12)-1:'');
const midi=n=>TUNING[n.string-1]+n.fret;
const totalBeats=p=>p.notes.reduce((a,n)=>a+n.duration,0);
const validId=x=>Number.isInteger(Number(x))&&Number(x)>=1&&Number(x)<=32;
let state={last:9,done:{},notes:{},bpms:{},rounds:3}, canSave=true;
function cleanState(x){
 const s={last:validId(x?.last)?Number(x.last):9,done:{},notes:{},bpms:{},rounds:[0,1,3,6].includes(Number(x?.rounds))?Number(x.rounds):3};
 for(let i=1;i<=32;i++){
  if(x?.done?.[i]===true)s.done[i]=true;
  if(typeof x?.notes?.[i]==='string')s.notes[i]=x.notes[i].slice(0,4000);
  if(Number.isFinite(x?.bpms?.[i])&&x.bpms[i]>=40&&x.bpms[i]<=160)s.bpms[i]=Math.round(x.bpms[i]);
 }
 return s;
}
try{const stored=localStorage.getItem(STORE);if(stored)state=cleanState(JSON.parse(stored));}catch(e){canSave=false;}
function save(){try{localStorage.setItem(STORE,JSON.stringify(state));canSave=true;}catch(e){canSave=false;}$('saveStatus').textContent=canSave?'Saved on this device':'Storage unavailable · export a backup';}
let lesson=G.lessons[state.last-1], pi=0, stage='learn', tabIsHidden=false, chordSelected='', bpm=70, toastTimer;
const pattern=()=>lesson.patterns[pi];
const progression=()=>pattern().progression||lesson.progression;
function notify(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4200);}
function libraryHTML(){return G.subjects.map((s,k)=>{
 const group=G.lessons.filter(l=>l.subject===k),done=group.filter(l=>state.done[l.id]).length;
 return '<details class="subject-group" '+(k===lesson.subject?'open':'')+'><summary><span>'+esc(s[0])+'</span><span>'+done+' / 4</span></summary>'+group.map(l=>'<button class="lesson-link" data-lesson="'+l.id+'" aria-current="'+(l.id===lesson.id)+'"><span class="num">'+String(l.id).padStart(2,'0')+'</span><span>'+esc(l.title)+'</span>'+(state.done[l.id]?'<span class="done" aria-label="completed">✓</span>':'')+'</button>').join('')+'</details>';
 }).join('');}
function renderLibrary(){const html=libraryHTML();$('courseNav').innerHTML=html;$('mobileCourseNav').innerHTML=html;const count=Object.values(state.done).filter(Boolean).length;$('courseCount').textContent=count+' of 32 completed';$('courseProgress').value=count;$('mobileProgress').textContent=count+' of 32 completed';}
function setStage(name,focus=false){
 stage=name;
 for(const s of ['learn','play','jam']){const b=$('tab'+s[0].toUpperCase()+s.slice(1));b.setAttribute('aria-selected',String(s===name));b.tabIndex=s===name?0:-1;$(s+'Panel').hidden=s!==name;if(s===name&&focus)b.focus();}
}
function selectLesson(id,scroll=true){
 if(!validId(id))return;
 stopEngine(false);lesson=G.lessons[Number(id)-1];pi=0;tabIsHidden=!!lesson.hideInitially;state.last=lesson.id;chordSelected=pattern().chord;quiz=null;quizStats={right:0,total:0};
 bpm=state.bpms[lesson.id]||lesson.bpm;$('tempo').value=bpm;$('bpm').textContent=bpm;$('rounds').value=state.rounds;
 $('lessonNumber').textContent='LESSON '+String(lesson.id).padStart(2,'0')+' / 32';$('subjectName').textContent=G.subjects[lesson.subject][0];$('lessonTitle').textContent=lesson.title;$('lessonGoal').textContent=lesson.goal;$('tempoGoal').textContent='Start '+lesson.bpm+' · work toward '+lesson.target+' BPM';
 $('why').textContent=lesson.why;$('steps').innerHTML=lesson.steps.map(t=>'<li><span>'+esc(t)+'</span></li>').join('');$('challenge').textContent=lesson.challenge;$('complete').checked=!!state.done[lesson.id];$('notes').value=state.notes[lesson.id]||'';
 $('previousLesson').disabled=lesson.id===1;$('nextLesson').disabled=lesson.id===32;$('version').textContent=G.version;
 renderLibrary();renderPatterns();renderTab();renderChords();renderJam();renderQuiz();setStage('learn');
 try{history.replaceState(null,'','#lesson-'+lesson.id);}catch(e){}save();
 if(scroll){window.scrollTo({top:0,behavior:'auto'});$('lessonTitle').focus({preventScroll:true});}
}
function selectPattern(index){stopEngine(false);pi=Math.max(0,Math.min(Number(index),lesson.patterns.length-1));chordSelected=pattern().chord;renderPatterns();renderTab();renderChords();renderJam();}
function renderPatterns(){$('patternButtons').innerHTML=lesson.patterns.map((p,i)=>'<button data-pattern="'+i+'" class="'+(i===pi?'active':'')+'" aria-pressed="'+(i===pi)+'">'+esc(p.title)+'</button>').join('');$('exerciseTitle').textContent=pattern().kind==='rhythm'?'Rhythm grid':'Lead & picking tablature';}
function countLabel(beat){const q=Math.floor(beat)+1,f=Math.round((beat%1)*4);return f===0?String(q):['','e','&','a'][f];}
function fretLabel(n){if(n.tech==='b'||n.tech==='s')return n.fret+n.tech+n.to;if(n.tech==='v')return n.fret+'~';return (n.tech||'')+n.fret;}
function measures(p){const result=[];let bar=[],time=0,start=0;p.notes.forEach((n,index)=>{bar.push({...n,index,beat:time});time+=n.duration;if(time>=4-.001){result.push({notes:bar,start});start+=time;bar=[];time=0;}});if(bar.length)result.push({notes:bar,start});return result;}
function renderTab(){
 const p=pattern(),show=$('showNotes').checked;
 $('tabContent').hidden=tabIsHidden;$('tabHidden').hidden=!tabIsHidden;$('hideTab').textContent=tabIsHidden?'Reveal tab':'Hide tab';$('hideTab').setAttribute('aria-expanded',String(!tabIsHidden));
 $('noteInfo').textContent=p.kind==='rhythm'?'Tap an attack to hear it. Keep moving through the silent steps.':'Tap a note for its pitch and fretboard location.';
 $('tabContent').innerHTML=measures(p).map((bar,bi)=>{
  if(p.kind==='rhythm')return '<div class="tab-measure"><div class="measure-label">Bar '+(bi+1)+' · '+esc(p.chord)+'</div><div class="rhythm-grid">'+bar.notes.map(n=>'<button data-note="'+n.index+'" class="rhythm-hit '+(n.action==='-'?'rest':n.action==='X'?'ghost':'')+'" aria-label="Count '+countLabel(n.beat)+', '+(n.action==='D'?'downstroke':n.action==='U'?'upstroke':n.action==='X'?'muted attack':'silent motion')+'"><small>'+countLabel(n.beat)+'</small><b>'+ (n.action==='-'?'–':n.action)+'</b></button>').join('')+'</div></div>';
  const columns='22px '+bar.notes.map(n=>'minmax(30px,'+n.duration+'fr)').join(' ');
  let html='<div class="tab-measure"><div class="measure-label">Bar '+(bi+1)+' · 4/4</div><div class="tab-grid" style="grid-template-columns:'+columns+'"><div></div>'+bar.notes.map(n=>'<div class="tab-count">'+countLabel(n.beat)+'</div>').join('');
  for(let s=1;s<=6;s++){
   html+='<div class="string-name">'+['e','B','G','D','A','E'][s-1]+'</div>';
   for(const n of bar.notes){
    if(n.rest&&s===3){html+='<div class="tab-cell rest"><span>R</span></div>';continue;}
    html+='<div class="tab-cell">';
    if(n.string===s){const pitch=midi(n),label=fretLabel(n);html+='<button class="'+(n.target?'target':'')+'" data-note="'+n.index+'" aria-label="'+esc(noteName(pitch,true)+', string '+s+', fret '+label+', '+n.duration+' beats')+'">'+esc(label)+(show?'<small>'+noteName(n.tech==='b'||n.tech==='s'?TUNING[s-1]+n.to:pitch)+'</small>':'')+'</button>';}
    html+='</div>';
   }
  }
  return html+'</div></div>';
 }).join('');
}
function chordPitches(name){return G.chords[name].frets.map((f,i)=>f<0?null:TUNING[5-i]+f).filter(n=>n!==null);}
function targetFor(name){const c=G.chords[name],third=c.intervals.includes(4)?4:c.intervals.includes(3)?3:0;return {name:noteName(c.root+third),midi:c.root+third+12,label:third?'TARGET THIRD':'TARGET ROOT'};}
function diagram(name){
 const c=G.chords[name],positive=c.frets.filter(n=>n>0),base=Math.max(...positive)<=4?1:Math.min(...positive);let svg='<svg class="chord-diagram" role="img" aria-label="'+esc(name+' guitar fingering, low E to high e: '+c.frets.map(f=>f<0?'muted':f===0?'open':f).join(', '))+'" viewBox="0 0 180 190">';
 for(let i=0;i<6;i++){const x=28+i*24;svg+='<path d="M'+x+' 36V151" stroke="#56717a" stroke-width="1"/>';svg+='<text x="'+x+'" y="176" text-anchor="middle" fill="#afc2c4" font-size="11">'+['E','A','D','G','B','e'][i]+'</text>';}
 for(let f=0;f<=5;f++)svg+='<path d="M28 '+(36+23*f)+'H148" stroke="#67818a" stroke-width="'+(f===0&&base===1?3:1)+'"/>';
 if(base>1)svg+='<text x="8" y="52" fill="#afc2c4" font-size="10">'+base+'</text>';
 c.frets.forEach((f,i)=>{const x=28+i*24;if(f<=0){svg+='<text x="'+x+'" y="24" text-anchor="middle" fill="#afc2c4" font-size="15">'+(f<0?'×':'○')+'</text>';}else{const y=36+(f-base+.5)*23;svg+='<circle cx="'+x+'" cy="'+y+'" r="9.5" fill="#8ee0c1"/><text x="'+x+'" y="'+(y+3.5)+'" text-anchor="middle" font-size="11" font-weight="700" fill="#102b25">'+c.fingers[i]+'</text>';}});
 return svg+'</svg>';
}
function showChord(name){chordSelected=name;$('chordDiagram').innerHTML=diagram(name);$('chordName').textContent=name;$('chordNotes').textContent=SPELLINGS[name]||G.chords[name].intervals.map(i=>noteName(G.chords[name].root+i)).join(' · ');$('chordTip').textContent=G.chords[name].tip||'Fret with your fingertips and play only the marked strings. Keep your thumb comfortably behind the neck.';document.querySelectorAll('[data-chord]').forEach(b=>{b.classList.toggle('active',b.dataset.chord===name);b.setAttribute('aria-pressed',String(b.dataset.chord===name));});}
function renderChords(){const names=[...new Set([...progression(),...lesson.patterns.map(p=>p.chord)])];$('chordButtons').innerHTML=names.map(n=>'<button data-chord="'+esc(n)+'">'+esc(n)+'</button>').join('');if(!names.includes(chordSelected))chordSelected=names[0];showChord(chordSelected);}
function renderJam(){const prog=progression();$('jamTitle').textContent=prog.length+'-bar '+(lesson.featured?'G–C–D jam':'practice jam');$('jamProgression').innerHTML=prog.map((c,i)=>'<button class="jam-tile" data-jambar="'+i+'" aria-label="Bar '+(i+1)+', '+esc(c)+'"><small>'+String(i+1).padStart(2,'0')+'</small><b>'+esc(c)+'</b></button>').join('');setJamBar(0,1,false);updateJamDuration();}
function updateJamDuration(){const len=progression().length,rounds=Number($('rounds').value),seconds=Math.round(len*4*rounds*60/bpm);$('jamDuration').textContent=rounds?len+' bars × '+rounds+' round'+(rounds===1?'':'s')+' · '+Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')+' at this tempo, plus the optional count-in.':len+' bars · repeats until you press Stop.';}
function setJamBar(index,round,playing){const prog=progression(),name=prog[index],target=targetFor(name);$('currentChord').textContent=name;$('targetNote').textContent=target.name;$('targetLabel').textContent=target.label;$('nextChord').textContent=prog[(index+1)%prog.length];document.querySelectorAll('[data-jambar]').forEach(b=>{b.classList.toggle('active',playing&&Number(b.dataset.jambar)===index);b.classList.toggle('preview',!playing&&Number(b.dataset.jambar)===index);});const stage=(round-1)%3;const titles=['Make the changes clear','Develop the phrase','Make it your own'];const tasks=lesson.featured?['Play only B over G, E over C, and F-sharp over D. Hold the notes and leave space.','Use the three study licks. Land on the third on beat 1, then connect with nearby notes.','Improvise freely, keeping the third as your landing note. Answer busy phrases with a rest.']:['Play the lesson material simply and stay with the chord changes.','Add one small variation without changing the pulse.','Improvise or arrange your own version. Keep the lesson’s musical goal audible.'];$('roundTitle').textContent='Round '+round+' · '+titles[stage];$('roundChallenge').textContent=tasks[stage];}
function setTempo(value){bpm=Math.max(40,Math.min(160,Math.round(Number(value)||lesson.bpm)));$('tempo').value=bpm;$('bpm').textContent=bpm;state.bpms[lesson.id]=bpm;save();updateJamDuration();}
/* Web Audio: scheduled against AudioContext time, not a metronome setInterval. */
let ctx=null,master=null,noise=null,transport=null,scheduler=null,session=0;
const voices=new Set(),uiTimers=new Set();
async function ensureAudio(){
 if(!ctx){const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)throw new Error('This browser does not support the audio player.');ctx=new Audio({latencyHint:'interactive'});master=ctx.createGain();master.gain.value=Number($('volume').value)/100*.8;const compressor=ctx.createDynamicsCompressor();compressor.threshold.value=-16;compressor.knee.value=18;compressor.ratio.value=4;master.connect(compressor);compressor.connect(ctx.destination);noise=ctx.createBuffer(1,Math.floor(ctx.sampleRate*.08),ctx.sampleRate);const a=noise.getChannelData(0);for(let i=0;i<a.length;i++)a[i]=(Math.random()*2-1)*(1-i/a.length);}
 if(ctx.state!=='running')await ctx.resume();if(ctx.state!=='running')throw new Error('Audio is paused. Tap Play again and check your device volume.');
}
function track(source,cleanup){voices.add(source);source.onended=()=>{voices.delete(source);try{source.disconnect();cleanup?.();}catch(e){}};}
function tone(pitch,when,duration=.3,volume=.12,tech='',endPitch=pitch,type='lead'){
 if(!ctx)return;duration=Math.max(.055,duration);when=Math.max(ctx.currentTime,when);const osc=ctx.createOscillator(),gain=ctx.createGain(),f=440*Math.pow(2,(pitch-69)/12);osc.type=type==='click'?'sine':'triangle';osc.frequency.setValueAtTime(f,when);
 if(tech==='b'||tech==='s')osc.frequency.exponentialRampToValueAtTime(440*Math.pow(2,(endPitch-69)/12),when+Math.min(duration*.65,.35));
 let lfo=null,depth=null;if(tech==='v'&&duration>.3){lfo=ctx.createOscillator();depth=ctx.createGain();lfo.frequency.value=5;depth.gain.setValueAtTime(0,when);depth.gain.linearRampToValueAtTime(f*.007,when+.3);lfo.connect(depth);depth.connect(osc.frequency);lfo.start(when);lfo.stop(when+duration+.03);}
 const level=volume*(tech==='h'||tech==='p'?.85:1);gain.gain.setValueAtTime(.0001,when);gain.gain.exponentialRampToValueAtTime(Math.max(.0002,level),when+.006);gain.gain.exponentialRampToValueAtTime(Math.max(.0002,level*.45),when+Math.min(.12,duration*.45));gain.gain.exponentialRampToValueAtTime(.0001,when+duration);osc.connect(gain);gain.connect(master);track(osc,()=>{gain.disconnect();if(lfo){try{lfo.stop();}catch(e){}lfo.disconnect();depth.disconnect();}});osc.start(when);osc.stop(when+duration+.035);
}
function muted(when){const src=ctx.createBufferSource(),gain=ctx.createGain(),filter=ctx.createBiquadFilter();src.buffer=noise;filter.type='highpass';filter.frequency.value=1400;gain.gain.setValueAtTime(.16,when);gain.gain.exponentialRampToValueAtTime(.0001,when+.065);src.connect(filter);filter.connect(gain);gain.connect(master);track(src,()=>{gain.disconnect();filter.disconnect();});src.start(when);src.stop(when+.08);}
function soundChord(name,when,hold=.8,volume=.035,direction='D'){const notes=chordPitches(name);if(direction==='U')notes.reverse();notes.forEach((n,i)=>tone(n,when+i*.012,hold,volume));}
function clickAt(when,accent){tone(accent?89:81,when,.045,accent?.14:.085,'',0,'click');}
function later(when,fn,ticket=session){const timer=setTimeout(()=>{uiTimers.delete(timer);if(ticket===session)fn();},Math.max(0,(when-ctx.currentTime)*1000));uiTimers.add(timer);}
function playingButtons(mode){$('playExercise').setAttribute('aria-pressed',String(mode==='exercise'));$('playClick').setAttribute('aria-pressed',String(mode==='click'));$('playJam').setAttribute('aria-pressed',String(mode==='jam'));$('floatingPlayer').hidden=!mode;}
function stopEngine(announce=true,message='Stopped · ready for another pass.'){
 session++;clearInterval(scheduler);scheduler=null;transport=null;for(const timer of uiTimers)clearTimeout(timer);uiTimers.clear();for(const source of voices){try{source.stop();}catch(e){}}voices.clear();playingButtons('');document.querySelectorAll('.sounding').forEach(e=>e.classList.remove('sounding'));document.querySelectorAll('#beatDots i').forEach(e=>e.classList.remove('on'));document.querySelectorAll('.jam-tile.active').forEach(e=>e.classList.remove('active'));if(announce)$('playStatus').textContent=message;else $('playStatus').textContent='Ready · choose an exercise or jam.';return session;
}
function audioAction(fn){try{Promise.resolve(fn()).catch(e=>{stopEngine(false);notify(e.message||'Could not start audio. Tap Play again.');});}catch(e){stopEngine(false);notify(e.message||'Audio could not start.');}}
function highlightNote(index){document.querySelectorAll('[data-note]').forEach(b=>b.classList.toggle('sounding',Number(b.dataset.note)===index));}
function noteDescription(n){if(n.rest)return 'Rest for '+n.duration+' beat'+(n.duration===1?'':'s')+'.';const names=['high e','B','G','D','A','low E'];const end=(n.tech==='b'||n.tech==='s')?' → '+noteName(TUNING[n.string-1]+n.to,true):'';return noteName(midi(n),true)+end+' · '+names[n.string-1]+' string · fret '+fretLabel(n)+(n.target?' · focus note':'');}
async function previewNote(index){const p=pattern(),n=p.notes[index],ticket=stopEngine(false);await ensureAudio();if(ticket!==session)return;document.querySelectorAll('[data-note]').forEach(b=>b.classList.toggle('selected',Number(b.dataset.note)===index));if(p.kind==='rhythm'){$('noteInfo').textContent=n.action==='-'?'Silent hand motion — keep the pulse.':n.action==='X'?'Muted attack — stop every string from ringing.':(n.action==='D'?'Downstroke':'Upstroke')+' on '+p.chord;if(n.action==='X')muted(ctx.currentTime+.01);else if(n.action!=='-')soundChord(p.chord,ctx.currentTime+.01,.4,.035,n.action);}else{$('noteInfo').textContent=noteDescription(n);if(!n.rest)tone(midi(n),ctx.currentTime+.01,Math.min(1.8,n.duration*60/bpm),.15,n.tech,TUNING[n.string-1]+n.to);}}
async function previewChord(name){const ticket=stopEngine(false);showChord(name);await ensureAudio();if(ticket!==session)return;soundChord(name,ctx.currentTime+.02,1.4,.035);}
async function startEngine(mode){
 if(transport?.mode===mode){stopEngine();return;}
 const ticket=stopEngine(false);await ensureAudio();if(ticket!==session)return;
 if(mode==='exercise')setStage('play');if(mode==='jam')setStage('jam');
 const p=pattern(),events=new Map();let at=0;p.notes.forEach((n,i)=>{events.set(Math.round(at*4),{n,i});at+=n.duration;});
 transport={mode,p,events,ticks:Math.round(at*4),tick:$('countIn').checked?-16:0,nextTime:ctx.currentTime+.08,prog:[...progression()],rounds:Number($('rounds').value),ended:false};
 playingButtons(mode);$('floatingStatus').textContent=mode==='jam'?'Backing jam':mode==='click'?'Metronome':'Exercise playing';scheduler=setInterval(schedule,25);schedule();
}
function schedule(){
 const t=transport;if(!t||t.ended)return;
 if(t.nextTime<ctx.currentTime-.4)t.nextTime=ctx.currentTime+.03;
 while(t.nextTime<ctx.currentTime+.13&&!t.ended){
  const tick=t.tick,when=t.nextTime,spb=60/bpm,quarter=((tick%16)+16)%16;
  if(tick>=0&&((t.mode==='exercise'&&!$('loopExercise').checked&&tick>=t.ticks)||(t.mode==='jam'&&t.rounds>0&&tick>=t.prog.length*16*t.rounds))){t.ended=true;clearInterval(scheduler);scheduler=null;later(when,()=>stopEngine(true,t.mode==='jam'?'Jam complete · take a breath and log your progress.':'Exercise complete · repeat when ready.'));break;}
  if(quarter%4===0){
   if(tick<0||t.mode==='click'||$('clickEnabled').checked)clickAt(when,quarter===0);
   const beat=quarter/4;
   later(when,()=>{document.querySelectorAll('#beatDots i').forEach((e,i)=>e.classList.toggle('on',i===beat));if(tick<0){$('playStatus').textContent='Count in · '+(beat+1)+' of 4';return;}if(t.mode==='jam'){const index=Math.floor(tick/16)%t.prog.length,round=Math.floor(tick/(16*t.prog.length))+1;setJamBar(index,round,true);$('playStatus').textContent='Round '+round+' · bar '+(index+1)+' / '+t.prog.length+' · beat '+(beat+1);$('floatingStatus').textContent=t.prog[index]+' · round '+round+' · bar '+(index+1);}else{$('playStatus').textContent=(t.mode==='click'?'Metronome':'Exercise')+' · bar '+(Math.floor(tick/16)+1)+' · beat '+(beat+1);}});
  }
  if(tick>=0&&t.mode==='exercise'){
   const event=t.events.get(tick%t.ticks);
   if(event){const {n,i}=event;if(t.p.kind==='rhythm'){const time=when+(t.p.offset||0);if(n.action==='X')muted(time);else if(n.action!=='-')soundChord(t.p.chord,time,spb*.7,.035,n.action);}else if(!n.rest)tone(midi(n),when,n.duration*spb*.92,.15,n.tech,TUNING[n.string-1]+n.to);later(when,()=>{highlightNote(i);if(t.p.kind!=='rhythm')$('noteInfo').textContent=noteDescription(n);});}
  }
  if(tick>=0&&t.mode==='jam'){
   const index=Math.floor(tick/16)%t.prog.length,name=t.prog[index],c=G.chords[name];
   if(quarter===0){soundChord(name,when,spb*3.7,.023);tone(Math.min(...chordPitches(name))-12,when,spb*1.5,.18);if($('guideTone').checked){const target=targetFor(name);tone(target.midi,when+.025,spb*.9,.10);}}
   if(quarter===8)tone(c.root+7-12,when,spb*1.3,.12);
  }
  t.tick++;t.nextTime+=spb/4;
 }
}
/* Listening quizzes: fixed root/register, randomized quality, one score per question. */
let quiz=null,quizStats={right:0,total:0};
function quizOptions(){if(lesson.quiz==='quality')return [{label:'Major',intervals:[0,4,7]},{label:'Minor',intervals:[0,3,7]}];if(lesson.quiz==='sevenths')return [{label:'Major 7 · maj7',intervals:[0,4,7,11]},{label:'Minor 7 · m7',intervals:[0,3,7,10]},{label:'Dominant 7 · 7',intervals:[0,4,7,10]}];return [{label:'Major third',interval:4},{label:'Perfect fifth',interval:7},{label:'Minor seventh',interval:10}];}
function renderQuiz(){$('quizCard').hidden=!lesson.quiz;$('quizTitle').textContent=lesson.quiz==='interval'?'Name the interval':lesson.quiz==='sevenths'?'Name the seventh-chord color':'Major or minor?';$('quizScore').textContent=quizStats.right+' / '+quizStats.total+' correct';$('quizAnswers').innerHTML=lesson.quiz?quizOptions().map((o,i)=>'<button data-answer="'+i+'" '+(!quiz||quiz.answered?'disabled':'')+'>'+esc(o.label)+'</button>').join(''):'';$('quizFeedback').textContent='Ready when you are.';$('replayQuestion').disabled=!quiz;}
async function playQuestion(){if(!quiz)return;const question=quiz,ticket=stopEngine(false);await ensureAudio();if(ticket!==session||quiz!==question)return;const time=ctx.currentTime+.08;if(lesson.quiz==='interval'){tone(60,time,.6,.16);tone(60+question.option.interval,time+.8,.9,.16);}else{const root=lesson.quiz==='quality'?62:60;question.option.intervals.forEach((i,k)=>tone(root+i,time+k*.012,1.5,.055));}}
function newQuestion(){const options=quizOptions();quiz={index:Math.floor(Math.random()*options.length),answered:false};quiz.option=options[quiz.index];renderQuiz();$('quizFeedback').textContent='Listen, sing what you hear, then choose.';audioAction(playQuestion);}
function answerQuestion(index){if(!quiz||quiz.answered)return;quiz.answered=true;quizStats.total++;const correct=Number(index)===quiz.index;if(correct)quizStats.right++;document.querySelectorAll('[data-answer]').forEach(b=>{b.disabled=true;if(Number(b.dataset.answer)===quiz.index)b.classList.add('correct');else if(Number(b.dataset.answer)===Number(index))b.classList.add('incorrect');});$('quizScore').textContent=quizStats.right+' / '+quizStats.total+' correct';$('quizFeedback').textContent=(correct?'Correct. ':'That was ')+quiz.option.label+'. Replay the sound, or start a new question.';}
/* UI actions. Lesson data is trusted static content; imported notes use value/textContent. */
document.addEventListener('click',event=>{
 const b=event.target.closest('button');if(!b)return;
 if(b.dataset.lesson){selectLesson(Number(b.dataset.lesson));if($('libraryDialog').open)$('libraryDialog').close();}
 else if(b.dataset.pattern!==undefined)selectPattern(Number(b.dataset.pattern));
 else if(b.dataset.stage)setStage(b.dataset.stage);
 else if(b.dataset.goto)setStage(b.dataset.goto);
 else if(b.dataset.note!==undefined)audioAction(()=>previewNote(Number(b.dataset.note)));
 else if(b.dataset.chord)audioAction(()=>previewChord(b.dataset.chord));
 else if(b.dataset.jambar!==undefined){const index=Number(b.dataset.jambar);audioAction(async()=>{await previewChord(progression()[index]);setJamBar(index,1,false);});}
 else if(b.dataset.answer!==undefined)answerQuestion(Number(b.dataset.answer));
});
$('openLibrary').onclick=()=>$('libraryDialog').showModal();$('closeLibrary').onclick=()=>$('libraryDialog').close();
$('tempo').oninput=e=>setTempo(e.target.value);$('slower').onclick=()=>setTempo(bpm-5);$('faster').onclick=()=>setTempo(bpm+5);
$('playExercise').onclick=()=>audioAction(()=>startEngine('exercise'));$('playClick').onclick=()=>audioAction(()=>startEngine('click'));$('playJam').onclick=()=>audioAction(()=>startEngine('jam'));$('startJam').onclick=()=>audioAction(()=>startEngine('jam'));$('stopAudio').onclick=()=>stopEngine();$('floatingStop').onclick=()=>stopEngine();
$('volume').oninput=()=>{if(master)master.gain.setTargetAtTime(Number($('volume').value)/100*.8,ctx.currentTime,.02);};
$('rounds').onchange=()=>{state.rounds=Number($('rounds').value);if(transport?.mode==='jam')stopEngine(true,'Jam length changed · press Start to begin again.');save();updateJamDuration();};
$('showNotes').onchange=renderTab;$('hideTab').onclick=()=>{tabIsHidden=!tabIsHidden;renderTab();};
$('complete').onchange=()=>{state.done[lesson.id]=$('complete').checked;save();renderLibrary();};$('notes').oninput=()=>{state.notes[lesson.id]=$('notes').value;save();};
$('previousLesson').onclick=()=>selectLesson(lesson.id-1);$('nextLesson').onclick=()=>selectLesson(lesson.id+1);
$('newQuestion').onclick=newQuestion;$('replayQuestion').onclick=()=>audioAction(playQuestion);
$('exportProgress').onclick=()=>{const payload={app:'Thrasher Guitar Studio',schema:1,exportedAt:new Date().toISOString(),state};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='guitar-studio-progress.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);notify('Progress backup created.');};
$('importProgress').onclick=()=>$('importFile').click();$('importFile').onchange=async e=>{const file=e.target.files?.[0];if(!file)return;try{if(file.size>500000)throw new Error('That file is too large to be a progress backup.');const x=JSON.parse(await file.text());if(x.app!=='Thrasher Guitar Studio'||x.schema!==1||!x.state)throw new Error('Choose a Guitar Studio progress backup.');if(!confirm('Replace this browser’s practice progress with the selected backup?'))return;state=cleanState(x.state);save();selectLesson(state.last);notify('Practice progress restored.');}catch(err){notify(err.message||'Could not read the backup.');}finally{e.target.value='';}};
document.querySelector('.stage-tabs').addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const stages=['learn','play','jam'],index=stages.indexOf(stage),next=e.key==='Home'?0:e.key==='End'?2:(index+(e.key==='ArrowRight'?1:2))%3;setStage(stages[next],true);});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&transport){stopEngine();return;}if(e.code==='Space'&&!e.target.closest('input,textarea,select,button,a,summary,dialog,[contenteditable]')){e.preventDefault();if(transport)stopEngine();else audioAction(()=>startEngine('exercise'));}});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&(transport||voices.size))stopEngine(true,'Paused because the app was hidden. Tap Play to resume practice.');});
window.addEventListener('pagehide',()=>stopEngine(false));window.addEventListener('hashchange',()=>{const m=/^#lesson-(\d+)$/.exec(location.hash);if(m&&validId(m[1])&&Number(m[1])!==lesson.id)selectLesson(Number(m[1]));});
const first=/^#lesson-(\d+)$/.exec(location.hash);selectLesson(first&&validId(first[1])?Number(first[1]):state.last,false);
/* Scoped offline cache: never controls or caches the rest of the website. */
if('serviceWorker' in navigator&&window.isSecureContext){navigator.serviceWorker.register('./sw.js',{scope:'./',updateViaCache:'none'}).then(reg=>{navigator.serviceWorker.ready.then(()=>$('offlineStatus').textContent='Offline course ready · progress stays on this device.');reg.addEventListener('updatefound',()=>{const worker=reg.installing;worker?.addEventListener('statechange',()=>{if(worker.state==='installed'&&navigator.serviceWorker.controller)$('offlineStatus').textContent='Course update cached · reopen after practice to use it.';});});}).catch(()=>$('offlineStatus').textContent='Online mode · offline caching is unavailable in this browser.');}else $('offlineStatus').textContent='Online mode · offline installation requires HTTPS or localhost.';
window.addEventListener('offline',()=>{$('offlineStatus').textContent='You are offline · cached lessons and audio remain available.';});
/* Read-only diagnostics for browser testing; no remote services or personal data. */
window.GuitarStudio={get lessonId(){return lesson.id;},get audioState(){return ctx?.state||'not-started';},get playing(){return transport?.mode||null;},get scheduledVoices(){return voices.size;},get bpm(){return bpm;},stop:()=>stopEngine(),selectLesson,setStage};
})();
