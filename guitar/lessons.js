'use strict';
/* Original practice material. Standard tuning; string 1 is the high e. */
(() => {
const subjects = [
 ['Chord Mastery','Hear the color. Make the change.'],
 ['Scales & Fretboard','Connect notes, not just boxes.'],
 ['Improvisation & Soloing','Make the changes audible in your lead.'],
 ['Rhythm & Groove','Build a dependable, musical pulse.'],
 ['Lead Techniques','Give a few notes more expression.'],
 ['Arpeggios & Harmony','Turn chord shapes into melodies.'],
 ['Ear Training & Theory','Connect what you hear to what you play.'],
 ['Acoustic & Fingerstyle','Independent bass and clear melody.']
];
const chord = (frets, fingers, root, intervals, tip='') => ({frets,fingers,root,intervals,tip});
const chords = {
 G:chord([3,2,0,0,0,3],[2,1,0,0,0,3],43,[0,4,7]),
 Gm:chord([-1,-1,5,3,3,3],[0,0,3,1,1,1],43,[0,3,7],'Small index-finger barre across G, B and high e. Do not play the two bass strings.'),
 G7:chord([3,2,0,0,0,1],[3,2,0,0,0,1],43,[0,4,7,10]),
 Gmaj7:chord([3,-1,0,0,0,2],[2,0,0,0,0,1],43,[0,4,7,11],'Middle finger frets low E and lightly mutes A. No thumb wrap.'),
 C:chord([-1,3,2,0,1,0],[0,3,2,0,1,0],48,[0,4,7]),
 Cmaj7:chord([-1,3,2,0,0,0],[0,3,2,0,0,0],48,[0,4,7,11]),
 C7:chord([-1,3,2,3,1,0],[0,3,2,4,1,0],48,[0,4,7,10],'The open shape omits the fifth G; it keeps C, E and B-flat, the defining tones.'),
 Cm7:chord([-1,3,5,3,4,3],[0,1,3,1,2,1],48,[0,3,7,10],'Index barre at fret 3 from A to high e; ring on D5 and middle on B4. Use the single-note exercise first if the barre is tiring.'),
 Cadd9:chord([-1,3,2,0,3,3],[0,2,1,0,3,4],48,[0,4,7,14]),
 D:chord([-1,-1,0,2,3,2],[0,0,0,1,3,2],50,[0,4,7]),
 Dm:chord([-1,-1,0,2,3,1],[0,0,0,2,3,1],50,[0,3,7]),
 D7:chord([-1,-1,0,2,1,2],[0,0,0,2,1,3],50,[0,4,7,10]),
 Dm7:chord([-1,-1,0,2,1,1],[0,0,0,2,1,1],50,[0,3,7,10],'Lightly barre B and high e at fret 1 with your index finger.'),
 Am:chord([-1,0,2,2,1,0],[0,0,2,3,1,0],45,[0,3,7]),
 Am7:chord([-1,0,2,0,1,0],[0,0,2,0,1,0],45,[0,3,7,10]),
 Asus2:chord([-1,0,2,2,0,0],[0,0,1,2,0,0],45,[0,2,7],'No third: the B replaces C-sharp or C.'),
 A:chord([-1,0,2,2,2,0],[0,0,1,2,3,0],45,[0,4,7]),
 A7:chord([-1,0,2,0,2,0],[0,0,1,0,2,0],45,[0,4,7,10]),
 Em7:chord([0,2,2,0,3,0],[0,1,2,0,3,0],40,[0,3,7,10]),
 E7:chord([0,2,0,1,0,0],[0,2,0,1,0,0],40,[0,4,7,10]),
 Fmaj7:chord([-1,-1,3,2,1,0],[0,0,3,2,1,0],53,[0,4,7,11],'Start on the D string. This four-string shape needs no barre or thumb wrap.'),
 'G/B':chord([-1,2,0,0,3,-1],[0,1,0,0,3,0],43,[0,4,7],'Play A through B only. B is the lowest note; the chord is still G major.')
};
function seq(text) {
 return text.trim().split(/\s+/).map(token => {
  const [body, length] = token.split('@'); const duration = length ? Number(length) : 0.5;
  if(body==='-') return {rest:true,duration};
  const m = /^([1-6]):([hp]?)(\d+)(?:([bs])(\d+)|(v))?(!)?$/.exec(body);
  if(!m) throw new Error('Invalid guitar note: '+token);
  return {string:Number(m[1]),fret:Number(m[3]),tech:m[2]||m[4]||m[6]||'',to:m[5]?Number(m[5]):Number(m[3]),target:!!m[7],duration};
 });
}
const p=(title,text,chordName,extra={})=>({title,notes:seq(text),chord:chordName,...extra});
const r=(title,pattern,chordName,subdivision=.5,offset=0)=>({title,kind:'rhythm',notes:pattern.split(' ').map(action=>({action,duration:subdivision})),chord:chordName,offset});
const lessons=[];
function add(subject,title,goal,why,steps,challenge,bpm,target,progression,patterns,extra={}) {
 lessons.push({id:lessons.length+1,subject,title,goal,why,steps,challenge,bpm,target,progression:progression.split(' '),patterns,...extra});
}
add(0,'Major, minor & dominant 7','Hear how one changed note changes the character of a chord.',
 'D major is D–F-sharp–A. D minor lowers the third to F. D7 keeps the major third F-sharp and adds the minor seventh C. A plain “7” means dominant seventh, not major seventh.',
 ['3 min · Tap D, Dm and D7. Sing the high-e note: F-sharp, F, then F-sharp. Listen for the extra C in D7.', '5 min · Play each four-note arpeggio. Use only the top four strings and keep the open D ringing.', '4 min · Jam one bar each of D, Dm, D7 and G. Notice how D7 wants to settle on G. This is a color comparison, not a single-scale exercise.'],
 'Make three clean cycles and name the third in each chord without looking.',60,90,'D Dm D7 G',[
 p('D · major third','4:0@1 3:2@1 2:3@1 1:2!@1','D'),
 p('Dm · minor third','4:0@1 3:2@1 2:3@1 1:1!@1','Dm'),
 p('D7 · hear C','4:0@1 3:2@1 2:1!@1 1:2@1','D7')]);
add(0,'Three seventh-chord colors','Separate major 7, minor 7 and dominant 7 by ear and by notes.',
 'Cmaj7 = C E G B. C7 = C E G B-flat. Cm7 = C E-flat G B-flat. Only maj7 has B; only Cm7 has E-flat. The Cm7 diagram uses an index barre, never a thumb-over grip.',
 ['3 min · Hear the three chord buttons. Compare Cmaj7 with C7 first, then C7 with Cm7.', '5 min · Play root, third, fifth and seventh in the tab. Say “major third, major seventh” for Cmaj7; change the words for the other two.', '4 min · Jam Cmaj7, C7, Cm7, C7. Treat each bar as its own harmony; do not force one scale over all four.'],
 'Identify each color correctly three times, then play its arpeggio.',60,85,'Cmaj7 C7 Cm7 C7',[
 p('Cmaj7 · C E G B','5:3@1 4:2!@1 3:0@1 2:0!@1','Cmaj7'),
 p('C7 · C E G B-flat','5:3@1 4:2!@1 3:0@1 3:3!@1','C7'),
 p('Cm7 · C E-flat G B-flat','5:3@1 4:1!@1 3:0@1 3:3!@1','Cm7')]);
add(0,'Smooth seventh-chord changes','Keep common tones while your fretting hand changes shape.',
 'Cmaj7 and Am7 share C, E and G. Dm7 and G7 share D and F. You do not have to lift every finger at every change. The goal is an unbroken pulse, not a fast change followed by a pause.',
 ['3 min · Inspect the four chord diagrams. Practice Cmaj7 to Am7 slowly before adding Dm7 and G7.', '5 min · Pick the written four-note group for each bar. Prepare the next shape during beat 4.', '5 min · Use the backing jam: one downstroke on beat 1, then add beat 3. Keep unused bass strings muted.'],
 'Complete four cycles without stopping the beat, even if one chord is imperfect.',60,100,'Cmaj7 Am7 Dm7 G7',[
 p('Four-bar connection','5:3@1 4:2@1 3:0@1 2:0@1 5:0@1 4:2@1 3:0@1 2:1@1 4:0@1 3:2@1 2:1@1 1:1@1 6:3@1 4:0@1 3:0@1 1:1@1','Cmaj7')]);
add(0,'Substitutions & added color','Hear Em7 as a relative-minor color and Cadd9 as an added-note color.',
 'G is G B D; Em7 is E G B D. They share three notes, but the bass changes the feeling. Cadd9 adds D to a C major triad; it does not contain a seventh. These are musical options, not universal replacements.',
 ['3 min · Alternate G and Em7, letting the common upper notes ring.', '5 min · Play the four-bar melody. The first note of each bar is a chord tone of the new harmony.', '4 min · Jam G–Em7–Cadd9–D7, then mentally compare the first two bars with holding G for both.'],
 'Explain why Em7 resembles G, and why Cadd9 is not C9.',65,100,'G Em7 Cadd9 D7',[
 p('Follow the bass, keep the melody','3:4!@1 2:3@1 1:3@1 2:3@1 4:2!@1 3:0@1 2:3@1 1:0@1 5:3!@1 4:2@1 2:3@1 1:3@1 4:0@1 3:2@1 2:1@1 1:2!@1','G')]);
add(1,'Connect pentatonic positions','Move out of one A minor pentatonic box without losing the sound.',
 'A minor pentatonic contains A C D E G. This route travels from the G string at fret 5 to high e at fret 12. Shift deliberately; there is no need to stretch one hand across the entire route.',
 ['3 min · Name C, D, E, G, A, C, D, E as you tap and hear the notes.', '5 min · Play up and back in eighth notes. Shift after high e8; keep your thumb relaxed behind the neck.', '5 min · Jam Am for four bars. Use only four notes at a time, but choose them from two neighboring positions.'],
 'Play three clean ascending and descending passes with no pause at the shift.',60,110,'Am Am Am Am',[
 p('Ascend across positions','3:5 3:7 2:5 2:8 1:5! 1:8 1:10 1:12','Am'),
 p('Return with control','1:12 1:10 1:8 1:5! 2:8 2:5 3:7 3:5','Am')]);
add(1,'Mixolydian versus Dorian','Hear C-sharp versus C while keeping the same A tonal center.',
 'A Mixolydian: A B C-sharp D E F-sharp G. A Dorian: A B C D E F-sharp G. Only the third changes. Practice Mixolydian over A7; switch the exercise to Dorian for an Am7–D7 jam.',
 ['3 min · Compare the two phrases. The third note is the important difference: C-sharp or C.', '5 min · Loop each scale slowly, singing the third before you play it.', '5 min · Select a phrase, then open Jam. The backing changes with your choice so you can hear the correct modal setting.'],
 'Choose the right third over A7 and Am7 without guessing.',60,100,'A7 A7 A7 A7',[
 p('A Mixolydian · major third','3:2 3:4 2:2! 2:3 2:5 1:2 1:3 1:5','A7',{progression:['A7','A7','A7','A7']}),
 p('A Dorian · minor third','3:2 3:4 2:1! 2:3 2:5 1:2 1:3 1:5','Am7',{progression:['Am7','D7','Am7','D7']})]);
add(1,'Horizontal fretboard navigation','Play A Dorian along one string, then locate the same notes elsewhere.',
 'The high-e frets 5, 7, 8, 10, 12, 14, 15 and 17 spell A B C D E F-sharp G A. This is A Dorian, not A natural minor: its sixth is F-sharp. Position shifts matter more than speed.',
 ['3 min · Play the route as slow quarter notes and say every note name.', '5 min · Use the eighth-note tab. Shift your whole hand rather than reaching from fret 5 to fret 17.', '5 min · Jam Am7–D7. Make a four-note phrase on high e, then find those four pitches on B and G.'],
 'Find A, C and F-sharp on two strings without counting every fret.',55,95,'Am7 D7 Am7 D7',[
 p('One-string ascent','1:5! 1:7 1:8 1:10 1:12 1:14! 1:15 1:17','Am7'),
 p('One-string descent','1:17 1:15 1:14! 1:12 1:10 1:8 1:7 1:5!','Am7')]);
add(1,'Find the thirds instantly','Locate B, E and F-sharp in two useful areas of the neck.',
 'The major third of G is B; of C is E; of D is F-sharp. On the middle strings use G4, B5 and B7. On high e use frets 7, 12 and 14. The sound and harmonic job stay the same when the position changes.',
 ['3 min · Tap the highlighted target notes. Say chord, note and location out loud.', '5 min · Hold each target for a full bar. Keep the rhythm going while you move.', '4 min · Jam G–C–D–G. Start with the middle-string targets, then try the high-e targets.'],
 'Land on all four changes in three consecutive cycles.',65,110,'G C D G',[
 p('Middle-string targets','3:4!@4 2:5!@4 2:7!@4 3:4!@4','G'),
 p('High-e targets','1:7!@4 1:12!@4 1:14!@4 1:7!@4','G')]);
add(2,'G–C–D: target the third','Make the chord change audible in a melodic lead line.',
 'Start the G phrase on B, the C phrase on E and the D phrase on F-sharp. The remaining notes connect those targets inside G major. Play eight eighth notes per bar. These are original study phrases, not a song transcription.',
 ['3 min · Learn each one-bar lick separately at 70 BPM. The gold first note is the target third.', '5 min · Loop one phrase until it is relaxed, then connect G to C and C to D.', '6 min · Start the 16-bar jam for three rounds: first play only the target thirds; next play the study licks; finally improvise and leave space.'],
 'Finish a 48-bar jam and land on the third at every chord change.',70,120,'G G C C G G D D C C G G D C G G',[
 p('G · land on B','3:4! 2:3 3:4 3:2 4:5 3:2 3:4 2:3','G'),
 p('C · land on E','2:5! 2:3 3:5 3:4 3:5 2:3 2:5 1:3','C'),
 p('D · land on F-sharp','2:7! 2:5 2:3 3:4 3:2 3:4 2:3 2:7','D')],{featured:true});
add(2,'Call and response','Make a short musical question, leave space, then answer it.',
 'A phrase does not have to fill every beat. Over Am7–D7, A Dorian supplies the notes; C marks the minor color and F-sharp identifies D7. The rests are part of the exercise, not empty time to fill.',
 ['3 min · Listen to the question and answer. Count through the rests instead of rushing into the next phrase.', '5 min · Play the two-bar example. On the D7 bar, let F-sharp announce the new harmony.', '5 min · Jam: keep the question the same for three cycles and change only the last two notes of the answer.'],
 'Play three different answers while preserving the same rhythm and space.',70,105,'Am7 D7 Am7 D7',[
 p('Question / answer · two bars','3:2 2:1! 2:5@1 -@2 2:7! 2:5 2:3@1 -@2','Am7')]);
add(2,'A Mixolydian melodic jam','Use the flat seventh as color, not as a substitute for a landing note.',
 'A Mixolydian fits an A7 vamp: A B C-sharp D E F-sharp G. G is the flat seventh; C-sharp is the major third. A minor pentatonic has C instead, so do not automatically reuse every minor-pentatonic lick unchanged.',
 ['3 min · Tap C-sharp at B2 and G at high e3. Hear their different jobs against A7.', '5 min · Play the two-bar phrase, breathing during the second-bar rest.', '5 min · Jam A7. End one phrase on A, another on C-sharp, and another on G; compare the degree of rest.'],
 'Create a two-bar phrase that uses both C-sharp and G, then resolves to A.',70,115,'A7 A7 A7 A7',[
 p('Color, then resolve','3:2 3:4 2:2! 2:3 2:5 1:2 1:3! 1:5 2:5@1 2:2!@1 3:2@1 -@1','A7')]);
add(2,'Build a 12-bar blues solo','Follow all three chords without overplaying.',
 'This A blues uses A7, D7 and E7. Their thirds are C-sharp, F-sharp and G-sharp. Blues can mix major and minor colors, but clearly targeting each chord third makes the changes easy to hear.',
 ['3 min · Play each target phrase slowly: B2 for A7, B7 for D7, G1 for E7.', '5 min · Jam one chorus using only roots and thirds. Count the four A7 bars before the first change.', '6 min · Play three choruses: sparse, more active, then sparse again. The final E7 is a turnaround back to A7.'],
 'Stay oriented through a full 12-bar chorus without watching every chord tile.',65,110,'A7 A7 A7 A7 D7 D7 A7 A7 E7 D7 A7 E7',[
 p('A7 · C-sharp','2:2!@1 3:2@1 4:2@1 -@1','A7'),
 p('D7 · F-sharp','2:7!@1 2:3@1 3:2@1 -@1','D7'),
 p('E7 · G-sharp','3:1!@1 4:2@1 2:0@1 -@1','E7')]);
add(3,'Steady eighth-note strumming','Keep your hand moving even when the strings are silent.',
 'Count 1 & 2 & 3 & 4 &. Downstrokes align with the numbers and upstrokes with the &s. A dash is a missed-string motion, not a stopped hand. The demo sounds the attacks; it cannot monitor your hand.',
 ['3 min · Mute the strings and move down-up continuously with the metronome.', '5 min · Play D – D U – U D U on G. Keep the silent downstroke on beat 3.', '5 min · Apply the same motion to G–C–D–G, changing chords only on beat 1.'],
 'Play eight bars with an uninterrupted down-up motion.',60,110,'G C D G',[
 r('Eighth-note pattern','D - D U - U D U','G')]);
add(3,'Sixteenth-note syncopation','Place offbeat attacks without losing the quarter-note pulse.',
 'Count 1 e & a, 2 e & a, 3 e & a, 4 e & a. Downstrokes fall on numbers and &s; upstrokes fall on e and a. Start slower than your eighth-note tempo.',
 ['3 min · Speak all 16 subdivisions over four clicks while lightly muting the strings.', '5 min · Play the written accents on Em7. Keep all 16 hand motions, including the silent ones.', '5 min · Jam Em7–A7. Change only on beat 1 and avoid adding an extra strum at the change.'],
 'Hold the pattern for eight bars at 70 BPM without compressing the last beat.',50,85,'Em7 A7 Em7 A7',[
 r('Sixteenth grid','D - - U - - D - D - - U - U - U','Em7',.25)]);
add(3,'Ghost strums & clean muting','Separate a pitched chord from a dry percussive attack.',
 'X means a muted strum. For open chords, lightly touch all ringing strings with the fretting hand or use careful picking-hand muting; simply releasing one fretted note will not silence the open strings.',
 ['3 min · Alternate a full chord with a fully muted X. Check that no open string keeps ringing.', '5 min · Play D X D U X U D X. Keep the X attacks quieter than the chord accents.', '4 min · Jam Em7–A7 without changing the volume of the ghost notes.'],
 'Record yourself outside the app and check for accidental pitched notes in the X attacks.',60,105,'Em7 A7 Em7 A7',[
 r('Ghost-note groove','D X D U X U D X','Em7')]);
add(3,'Playing slightly behind the beat','Hear a relaxed placement while the tempo remains steady.',
 'Behind the beat means a small, consistent delay, not gradually slowing down. Compare the two demos: the click stays fixed while the chord attacks move 25 milliseconds later. Use this as an ear exercise before trying it physically.',
 ['3 min · Compare “On the beat” and “Slightly behind” with the click enabled.', '5 min · Play the on-beat version cleanly first. Then soften the attack and experiment with a very small delay.', '5 min · Jam Gmaj7–Cmaj7–Am7–D7. Stay aligned at the next bar line; never accumulate lateness.'],
 'Switch between the two feels without changing the tempo or missing a bar line.',70,100,'Gmaj7 Cmaj7 Am7 D7',[
 r('On the beat','D - D - D - D -','Gmaj7'),
 r('Slightly behind · 25 ms','D - D - D - D -','Gmaj7',.5,.025)]);
add(4,'Bends that reach the pitch','Match a bent note to a clearly heard reference pitch.',
 'B-string fret 8 is G. A whole-step bend should reach A, the same pitch as B10. Listen to the fretted target first. The synthesized demo sweeps to the target; your ear checks your own intonation.',
 ['3 min · Play B10, sing A, then play B8 and bend toward the remembered pitch.', '5 min · Work through the reference-and-bend phrase. Support the bending finger with adjacent fingers where comfortable.', '4 min · Jam Am. Use one accurately tuned bend per phrase rather than many rushed bends.'],
 'Match three bends to the B10 reference; do not force a painful or excessively stiff bend.',60,85,'Am Am Am Am',[
 p('Reference A → bend G to A','2:10!@2 2:8b10!@2 2:8@1 2:5@1 3:7@1 -@1','Am')]);
add(4,'Hammer-ons & pull-offs','Make legato notes as clear as the picked notes around them.',
 'h before a fret means hammer onto that note; p means pull off to it. Keep the destination finger already in place for a pull-off. Do not confuse legato with simply lifting a finger and hoping the string sounds.',
 ['3 min · Pick high e5, hammer to 7 and pull back to 5. Match all three volumes.', '5 min · Play the eight-note phrase. Pick the first note on each new string; use the marked h/p motions for the others.', '5 min · Jam Am7–D7. Add one legato group to an otherwise simple, clearly articulated phrase.'],
 'Play three loops with no dropped note and no sudden volume jump.',55,100,'Am7 D7 Am7 D7',[
 p('Legato groups','1:5 1:h7 1:p5 2:8 2:p5 3:7 3:h9 3:p7','Am7')]);
add(4,'Controlled vibrato','Shape a sustained note instead of shaking it immediately.',
 'Hold the pitch steady first, then introduce an even, modest vibrato. A repeated bend-and-release motion should return to the intended pitch. The demo is a synthetic illustration, not a recording of a particular guitar technique.',
 ['3 min · Sustain B8 for four beats with no vibrato. Listen for a stable G.', '5 min · Play the phrase. Add vibrato only after the start of each marked long note.', '4 min · Jam G–C. Choose G over G and E over C, and make the ends of the phrases expressive.'],
 'Keep two sustained notes centered and even for an entire four-beat count.',60,90,'G C G C',[
 p('Hold, then add vibrato','2:8v!@4 2:5v!@4','G')]);
add(4,'Connect expressive techniques','Combine a slide, legato and a bend without losing the rhythm.',
 's means slide from the first fret to the second. b means bend toward the written target fret pitch. Plan the arrival time of the note, not just the motion of your finger. Leave a rest after the busy phrase.',
 ['3 min · Isolate B5s8, then high e5–h7–p5. Keep each motion small.', '5 min · Join the groups and the B8b10 bend. Do not rush the bend to make room for the rest.', '5 min · Jam Am. Use the complete phrase once, then answer it with only two plain notes.'],
 'Play a controlled phrase and a simple answer at the same tempo.',55,95,'Am Am Am Am',[
 p('Slide · legato · bend','2:5s8@1 1:5 1:h7 1:p5 2:8 2:8b10!@1 -@4','Am')]);
add(5,'Three-string triads','Find compact G, C and D triads on the highest three strings.',
 'G: G4–B3–e3 = B D G, a first-inversion triad. C: G5–B5–e3 = C E G, root position. D: G7–B7–e5 = D F-sharp A, root position. The lowest note of a voicing is not always its root.',
 ['3 min · Tap and name each note in the three triads. Mute the lower three strings.', '5 min · Pick the four-note patterns with even quarter notes. Let each note be distinct.', '5 min · Jam G–C–D–G using only these small triads, then turn each into a short melody.'],
 'Name the inversion of the G shape and connect all three without a full barre chord.',60,105,'G C D G',[
 p('G triad · B D G','3:4!@1 2:3@1 1:3@1 2:3@1','G'),
 p('C triad · C E G','3:5@1 2:5!@1 1:3@1 2:5@1','C'),
 p('D triad · D F-sharp A','3:7@1 2:7!@1 1:5@1 2:7@1','D')]);
add(5,'Major 7 & minor 7 arpeggios','Spell seventh chords one note at a time.',
 'An arpeggio plays the chord tones separately. Cmaj7 is 1–3–5–7; Am7 and Dm7 are 1–flat 3–5–flat 7. G7 is 1–3–5–flat 7. A major seventh is one semitone below the root; a minor seventh is two.',
 ['3 min · Say the four notes of each chord before touching the guitar.', '5 min · Play the four quarter-note arpeggios. Gold highlights the third and seventh.', '5 min · Jam Cmaj7–Am7–Dm7–G7. Change the arpeggio on beat 1 rather than finishing an old shape late.'],
 'Play one full cycle with the chord names and another with the note names spoken aloud.',60,100,'Cmaj7 Am7 Dm7 G7',[
 p('Cmaj7','5:3@1 4:2!@1 3:0@1 2:0!@1','Cmaj7'),
 p('Am7','5:0@1 5:3!@1 4:2@1 3:0!@1','Am7'),
 p('Dm7','4:0@1 4:3!@1 3:2@1 2:1!@1','Dm7'),
 p('G7','6:3@1 5:2!@1 4:0@1 4:3!@1','G7')]);
add(5,'Guide-tone voice leading','Connect thirds and sevenths with the smallest useful motion.',
 'Dm7 has F and C; G7 has B and F; Cmaj7 has E and B. Follow F–F–E on high e and C–B–B on the B string. These two short paths reveal the harmony with very little movement.',
 ['3 min · Play the high-e path F–F–E, then the B-string path C–B–B.', '5 min · Alternate the two guide tones in each bar of the written four-bar exercise.', '5 min · Jam Dm7–G7–Cmaj7–Cmaj7. Leave space and avoid filling every gap with a scale run.'],
 'Make the progression recognizable using only the guide tones.',60,100,'Dm7 G7 Cmaj7 Cmaj7',[
 p('Two compact guide-tone lines','1:1!@2 2:1!@2 1:1!@2 2:0!@2 1:0!@2 2:0!@2 1:0!@2 2:0!@2','Dm7')]);
add(5,'Arpeggios over ii–V–I','Follow Am7–D7–Gmaj7 without resetting your sense of time.',
 'In G major, Am7 is ii, D7 is V and Gmaj7 is I. Am7 = A C E G; D7 = D F-sharp A C; Gmaj7 = G B D F-sharp. The key stays the same, but the chord tones receiving emphasis change.',
 ['3 min · Name the four notes of each arpeggio. Check F-sharp in D7 and Gmaj7.', '5 min · Play the three patterns separately, then connect them one bar per chord.', '6 min · Jam Am7–D7–Gmaj7–Gmaj7. On the second Gmaj7 bar, turn the notes into a freer melodic answer.'],
 'Play three cycles, starting each chord on a different chord tone rather than always the root.',65,110,'Am7 D7 Gmaj7 Gmaj7',[
 p('Am7 · A C E G','5:0@1 5:3!@1 4:2@1 3:0@1','Am7'),
 p('D7 · D F-sharp A C','4:0@1 4:4!@1 3:2@1 2:1@1','D7'),
 p('Gmaj7 · G B D F-sharp','6:3@1 5:2!@1 4:0@1 4:4@1','Gmaj7')]);
add(6,'Hear major versus minor','Recognize the changed third without relying on the chord label.',
 'A major triad contains a major third; a minor triad lowers that third by one semitone. The listening quiz uses the same root and register so the comparison is about quality rather than a different chord position.',
 ['3 min · Hear D and Dm, then play their F-sharp and F notes on high e.', '5 min · Open the listening quiz. Listen before choosing Major or Minor; replay as often as needed.', '4 min · Play the short comparison, then try identifying the qualities with your eyes closed.'],
 'Score 8 out of 10 on new questions before increasing the pace.',60,80,'D Dm D Dm',[
 p('Hear the third change','4:0@1 3:2@1 1:2!@2 4:0@1 3:2@1 1:1!@2','D')],{quiz:'quality'});
add(6,'Hear seventh-chord colors','Recognize maj7, m7 and dominant 7 by sound.',
 'All three quiz sounds have the same C root. Cmaj7 has E and B; C7 has E and B-flat; Cm7 has E-flat and B-flat. Compare pairs before asking your ear to choose among all three.',
 ['3 min · Compare Cmaj7 and C7. Sing B descending to B-flat.', '5 min · Use the quiz. First decide whether the third is major or minor; then listen to the seventh.', '4 min · Play the arpeggio of whichever sound you just identified. Turn the ear answer into a fretboard answer.'],
 'Score 8 out of 10 and explain which note distinguished the two closest choices.',60,85,'Cmaj7 C7 Cm7 C7',[
 p('Major seventh','5:3@1 4:2@1 3:0@1 2:0!@1','Cmaj7'),
 p('Dominant seventh','5:3@1 4:2@1 3:0@1 3:3!@1','C7'),
 p('Minor seventh','5:3@1 4:1!@1 3:0@1 3:3!@1','Cm7')],{quiz:'sevenths'});
add(6,'Sing the interval','Hear and sing a major third, perfect fifth and minor seventh.',
 'Starting on C, these intervals end on E, G and B-flat. They span 4, 7 and 10 semitones. The quiz plays the notes in sequence; sing the second pitch before choosing its name.',
 ['3 min · Play C at B1 and sing E, G or B-flat before checking the target.', '5 min · Use the interval quiz. Replay the root in your mind rather than counting guitar frets.', '4 min · Play each interval pattern, then try the same interval from a different root.'],
 'Get 8 out of 10 new questions correct and sing the answer before touching the guitar.',60,80,'C C7 C C7',[
 p('C → E · major third','2:1@2 1:0!@2','C'),
 p('C → G · perfect fifth','2:1@2 1:3!@2','C'),
 p('C → B-flat · minor seventh','2:1@2 1:6!@2','C7')],{quiz:'interval'});
add(6,'Transcribe a short melody','Move from hearing a phrase to finding it without watching the tab.',
 'Transcription begins with contour and rhythm, not fast note naming. This original phrase rises from G to B, comes back down, and ends on E. Hide the tab, listen, hum, then search for the notes.',
 ['3 min · Hide the tab before using Hear exercise. Hum the phrase and clap its rhythm.', '5 min · Find the first note, then reconstruct the phrase in small groups. Reveal only after making an attempt.', '5 min · Jam G–C. Play the phrase, then make an answer with a different final note.'],
 'Rebuild the entire phrase from memory after a one-minute break.',65,100,'G C G C',[
 p('Listen · hum · find','1:3@1 1:5 1:7 1:5@1 1:3@1 2:5!@2 -@2','G')],{hideInitially:true});
add(7,'Alternating-bass fingerpicking','Keep the thumb steady while the fingers play above it.',
 'Use thumb (T) on the bass, index (i) on G, middle (m) on B and ring (a) on high e. The eight-note Am pattern is T i m a T i m a, alternating open A and low E on beats 1 and 3.',
 ['3 min · Play only A and low E with your thumb on beats 1 and 3.', '5 min · Add i–m–a between the bass notes. Keep the thumb a little stronger than the upper notes.', '5 min · Jam Am. Sustain the chord without squeezing and keep the high notes even.'],
 'Maintain eight uninterrupted bars without the bass arriving late.',50,90,'Am Am Am Am',[
 p('Am · alternating A / E bass','5:0! 3:2 2:1 1:0 6:0! 3:2 2:1 1:0','Am')]);
add(7,'Fingerstyle through changes','Keep the picking pattern intact while the fretting hand moves.',
 'Use C–G–Am–Fmaj7, one bar each. C alternates C and G bass; G alternates G and D; Am alternates A and E. On Fmaj7, repeat F on the D string to keep the grip comfortable.',
 ['3 min · Practice only the first bass note of each bar: C, G, A, F.', '5 min · Learn each eight-note picking pattern separately. Begin Fmaj7 on D3, not on a low bass string.', '6 min · Jam the four changes. Prepare the next shape during the last high-e note without cutting the rhythm short.'],
 'Play four cycles with no pause at Fmaj7.',50,90,'C G Am Fmaj7',[
 p('C · C / G bass','5:3! 3:0 2:1 1:0 6:3! 3:0 2:1 1:0','C'),
 p('G · G / D bass','6:3! 3:0 2:0 1:3 4:0! 3:0 2:0 1:3','G'),
 p('Am · A / E bass','5:0! 3:2 2:1 1:0 6:0! 3:2 2:1 1:0','Am'),
 p('Fmaj7 · repeated F bass','4:3! 3:2 2:1 1:0 4:3! 3:2 2:1 1:0','Fmaj7')]);
add(7,'Chord embellishments','Create small melodic changes inside open chord shapes.',
 'C to Cadd9 changes an upper C to D while keeping the C-major identity. Am to Asus2 replaces C with B, removing the minor third. Let your ear hear a small melody rather than treating each grip as an unrelated chord.',
 ['3 min · Compare the chord buttons. Name the changing B-string note: C–D and C–B.', '5 min · Play the four-bar study. Keep the bass and inner strings relaxed while the top note moves.', '5 min · Jam C–Cadd9–Am–Asus2. Add the embellishment only once per bar before making it busier.'],
 'Sing the changing note while holding the rest of the chord steady.',60,100,'C Cadd9 Am Asus2',[
 p('One note changes the color','5:3@1 3:0@1 2:1!@1 1:0@1 5:3@1 3:0@1 2:3!@1 1:3@1 5:0@1 3:2@1 2:1!@1 1:0@1 5:0@1 3:2@1 2:0!@1 1:0@1','C')]);
add(7,'Arrange a melody over moving bass','Combine a descending bass line with a clear upper melody.',
 'C–G/B–Am7–Fmaj7 gives bass notes C–B–A–F. G/B means a G chord with B in the bass, not a new chord quality. In this study, the melody notes E–D–C–E sit above the bass; avoid adding an unwanted open high e over the C melody note.',
 ['3 min · Play the bass C–B–A–F alone, then the melody E–D–C–E alone.', '5 min · Play the four-bar picked arrangement. Bring out the gold melody notes and keep the inner notes softer.', '6 min · Jam the progression, then stop the backing and perform the arrangement solo. Let the bass establish the harmony.'],
 'Play a complete solo pass in which both the moving bass and upper melody remain easy to hear.',50,85,'C G/B Am7 Fmaj7',[
 p('Four-bar solo arrangement','5:3@1 3:0@1 1:0!@1 2:1@1 5:2@1 3:0@1 2:3!@1 4:0@1 5:0@1 3:0@1 2:1!@1 4:2@1 4:3@1 3:2@1 1:0!@1 2:1@1','C')]);
window.GUITAR={version:'1.0.0',subjects,chords,lessons};
})();
