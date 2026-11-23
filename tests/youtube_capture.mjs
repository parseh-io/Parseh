// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/youtube_capture.mjs
//      CHROME_BIN must be the FULL chrome binary (chrome-linux64/chrome): the
//      headless shell cannot capture a tab.
//      YOUTUBE_CAPTURE_SHOTS=<dir> saves the cut editor's record step and its
//      recorded state, at desktop and at phone width.
//      YT_REAL=1 also records two stretches of a real YouTube embed, one from
//      the start of the video (network).
//
// Cutting a YOUTUBE VIDEO'S SOUND (lib/cardkit.js, source kind "tab"; the
// player's card sheet, youtube/lib/player.js): the page cannot read the sound
// of YouTube's frame, so the cut editor records the tab while the stretch
// plays.  Against the REAL hub (serve.main() on a temporary toolbox) with a
// YouTube video in it, and a real tab capture: Chromium with
// --auto-accept-this-tab-capture, and WITHOUT Playwright's --mute-audio (a
// muted browser captures silence).  Only YouTube itself is faked: its
// iframe_api is answered by a script of this test whose YT.Player puts a frame
// of ANOTHER origin (a second server here, http://localhost) in the page,
// which plays a pattern of tones and answers the player's calls by
// postMessage, reporting where it is every animation frame as YouTube's own
// frame does.  The tones make a cut measurable: second k of the file holds a
// tone of 300 + 50k Hz from k.000 to k.500 s, silence after, so where a clip's
// tones start and end -- and which tones they are -- says where it was cut.
//
//  a) the sheet on the video: "cut the audio…" enabled (the kit can record a
//     tab here); an exercise deck; the editor's first step says what Chrome
//     will ask and waits for "record"; recorded: the waveform where the
//     tones are, the page's player put back as it was (paused, its place,
//     volume and speed), nothing sent to the speakers; edges nudged by ear,
//     previewed from the recording; saved: the tray's file holds the tones
//     where [start, end] says, within 25 ms; used, added to the deck: the item
//     names it as front-audio and the deck has the file
//  b) the frame capture takes its picture off the same share (Chrome asked
//     once); Anki: the editor records at once, the page's own audio muted
//     while it does and the muted player unmuted for it and muted again; the
//     note's snd_front is the tray's file, whose tones are where they should be
//  c) no track processor: the AudioWorklet path, as exact
//  d) a player that stops to load halfway: the pass is played again, and the
//     clip is still exact; at 400 px, the record step and the recorded editor
//     fit, the edge inputs show their whole value
//  e) the failures, in plain words and with no clip: a browser that cannot
//     record a tab (not Chrome or Edge) and a page that is not https, where
//     "cut the audio…" is disabled and says which; Chrome not allowed
//     ("press “Allow”"), a share without its sound ("Also allow tab audio"),
//     a video whose sound is off ("no sound was captured — is the video
//     muted?")
//  f) a frame taken off a share given without its sound (its picture
//     cropped to the video): the cut asks again, and records -- the first
//     share let go for the new one, which the next frame uses
//  g) "record again" after "save clip": the saved clip is dimmed as the old
//     recording's, and "use this clip" cuts it again from the new one (a
//     different sound now); the old clip leaves the tray
//  h) the first caption, from 0 s, on a player that says PLAYING only 0.18 s
//     into playing (as YouTube does): recorded, and a clip from 0 s exact
//  i) (YT_REAL=1) a real YouTube embed records a clip with sound in it, from
//     the middle of the video and from its very start
//  j) "reach": record again sent further back than the caption would reach
//  k) the add page's transcript editor: the captions listed, moved a tenth
//     of a second at a time, and the panel that goes back into the box
//  l) the timings sheet's "draw the sound" on a YouTube video (the tab is
//     recorded while the video plays and its shape is kept as waveform.json;
//     the recorder lives in youtube/lib/tabcapture.js): in real Chrome over
//     the real tones, and again with the 25 ms tick played by the test over
//     made-up loudness and clocks, where the numbers posted are checked one
//     by one against the spec and against the checksum the old code gave
//     (YT_WAVE_OUT=<file> also saves the real run's posted body)
//  m) the same recording as the add page will use it, on a page that has
//     youtube/lib/tabcapture.js and nothing else of Parseh's: one share for
//     both consumers (the shape, and the sound as 16 kHz samples in chunks
//     with marks that say where the video was), a stop to buffer and a late
//     start, no sound in the share, a share of the screen, a browser that
//     cannot, an ad, a cancel in the middle, an hour through the chunk
//     pipeline, the picture of the share dropped; a video that ends short of
//     the length its player gave (YouTube's is rounded up) ends the recording
//     when its player says so, and a stop anywhere else is still a stall
//  n) the add page's speech to text for a YouTube video, on the fake YouTube
//     and a real tab capture, against the real transcription job (its worker a
//     stand-in for faster-whisper, lib/getstt.py a file: tests/addstt_fakes.py):
//     what the page says before anything is recorded, the video loaded in a
//     frame on screen (since a0.4.3 in the transcription workspace, a modal
//     window over the page; on a phone's layout, in the page), the tab shared
//     only in answer to the second press, the recording to its end, the words
//     put up for review and in the transcript box only when the person presses
//     "Use this transcript", the shape of the sound held and put beside the
//     video when it is added; no sound in the share, a share refused, Cancel
//     in the middle (playback, tracks, upload, the temporary sound, the box), a
//     second start refused, a video whose player rounds its length up (it was
//     cancelled as stopped), and the same in a right-to-left language on a
//     phone's width
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('YOUTUBE_CAPTURE_SHOTS') || '';
const REAL = Deno.env.get('YT_REAL') === '1';
const TMP = await Deno.makeTempDir({prefix: 'parseh-youtube-capture-'});
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want),
                                    m + (JSON.stringify(got) === JSON.stringify(want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
const near = (a, b, tol) => Math.abs(a - b) <= tol;
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 20000) {
  const t = Date.now();
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() - t > ms) throw Error('FAIL: timed out: ' + what);
    await sleep(80);
  }
}
async function run(cmd, args) {
  const o = await new Deno.Command(cmd, {args, cwd: root, stdout: 'piped', stderr: 'piped'}).output();
  return {code: o.code, out: td.decode(o.stdout), err: td.decode(o.stderr)};
}
async function ff(...args) {
  const r = await run('ffmpeg', ['-y', '-loglevel', 'error', ...args]);
  if (r.code) throw Error('ffmpeg: ' + r.err);
}
async function exists(p) { try { await Deno.stat(p); return true; } catch (_) { return false; } }
async function names(dir, re = /./) {
  const out = [];
  try { for await (const e of Deno.readDir(dir)) if (e.isFile && re.test(e.name)) out.push(e.name); } catch (_) {}
  return out.sort();
}
const readJson = async p => JSON.parse(await Deno.readTextFile(p));
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}

/* ---------------------------------------------------------------- the tones */
// 42 s, 48 kHz mono: second k a tone of 300 + 50k Hz over [k, k + 0.5)
const FAKE = TMP + '/fake';
await Deno.mkdir(FAKE, {recursive: true});
await ff('-f', 'lavfi', '-i', "aevalsrc='if(lt(mod(t\\,1)\\,0.5)\\,0.5*sin(2*PI*(300+50*floor(t))*t)\\,0)':s=48000:d=42",
         '-ac', '1', '-c:a', 'pcm_s16le', FAKE + '/tones.wav');
// and its first 12 s, for the checks that only need a video to end
await ff('-i', FAKE + '/tones.wav', '-t', '12', '-c:a', 'pcm_s16le', FAKE + '/short.wav');
// and its first 3 s, for a video shorter than the last seconds the recorder watches for an end
await ff('-i', FAKE + '/tones.wav', '-t', '3', '-c:a', 'pcm_s16le', FAKE + '/tiny.wav');
// A clip's tones, measured: decoded by ffmpeg, the loudness (RMS) of every
// 5 ms, a tone where it passes 0.1; each run's frequency from the zero
// crossings of its middle (its edges hold the codec's noise of the silence
// around).  [[start, end, Hz]] in seconds from the clip's first sample.
const ANALYSE = `
import array, json, math, subprocess, sys
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", sys.argv[1], "-ac", "1", "-ar", "48000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
x = array.array("h"); x.frombytes(raw[:len(raw) // 2 * 2])
if sys.byteorder == "big": x.byteswap()
W = 240
loud = [math.sqrt(sum(v * v for v in x[i:i + W]) / W) / 32768 for i in range(0, len(x) - W + 1, W)]
runs, start = [], None
for k, r in enumerate(loud + [0]):
    if r > 0.1 and start is None: start = k
    elif r <= 0.1 and start is not None: runs.append((start, k)); start = None
out = []
for a, b in runs:
    n = (b - a) * W
    seg = x[a * W + n // 5:b * W - n // 5]
    zc = sum(1 for i in range(1, len(seg)) if (seg[i - 1] < 0) != (seg[i] < 0))
    d = max(1, len(seg)) / 48000
    out.append([a * W / 48000, b * W / 48000, round(zc / 2 / d, 1)])
L = 2400
rms50 = [round(math.sqrt(sum(v * v for v in x[i:i + L]) / L) / 32768, 4) for i in range(0, len(x) - L + 1, L)]
print(json.dumps({"duration": len(x) / 48000, "runs": out, "peak": max((abs(v) for v in x), default=0) / 32768, "rms50": rms50}))
`;
async function measure(path) {
  const r = await run(PY, ['-c', ANALYSE, path]);
  if (r.code) throw Error('analysis: ' + r.err);
  return JSON.parse(r.out);
}
// the tones a clip [s, e] of the pattern holds, from its first sample
function expectedTones(s, e) {
  const out = [];
  for (let k = Math.floor(s) - 1; k <= Math.ceil(e); k++) {
    const a = Math.max(k, s), b = Math.min(k + 0.5, e);
    if (b - a >= 0.02) out.push([a - s, b - s, 300 + 50 * k]);
  }
  return out;
}
// every tone within 25 ms of where [s, e] puts it, each the right one
async function clipIsExact(path, s, e, what) {
  const m = await measure(path), want = expectedTones(s, e);
  const got = m.runs.filter(r => r[1] - r[0] >= 0.015);
  const show = x => JSON.stringify(x.map(r => [+r[0].toFixed(3), +r[1].toFixed(3), r[2]]));
  assert(near(m.duration, e - s, 0.03), `${what}: the clip lasts ${m.duration.toFixed(3)} s for ${s.toFixed(2)}–${e.toFixed(2)}`);
  assert(got.length === want.length && want.every((w, i) => near(got[i][0], w[0], 0.025) && near(got[i][1], w[1], 0.025)
                                                    && (w[1] - w[0] < 0.1 || near(got[i][2], w[2], 25))),
         `${what}: its tones start and end within 25 ms of where the edges put them, and are the right ones: ` +
         `got ${show(got)} want ${show(want)}`);
  return m;
}

/* ---------------------------------------------------------------- the fake YouTube */
// The frame YouTube would put in the page, from another origin: a media
// element driven by postMessage, reporting where it is every animation frame.
// ?deaf=1: a video whose sound is off whatever the player is told;
// ?stall=1: the first play stops to load for 400 ms, 1.5 s in;
// ?late=1: every play says BUFFERING for its first 0.18 s of playing, and
// PLAYING only after, as a real YouTube frame was seen to (driven: PLAYING
// first at 0.176 s of a video played from 0);
// ?over=0.6: the length it gives is that many seconds more than the sound it
// plays, as a real YouTube frame's was (driven, 13 videos: the length it gave
// at the start was the video's own rounded UP to a whole second, 596.501 s as
// 597, while the clock stopped where the sound did and the state said ENDED);
// ?ghost=0.5: every play says ENDED for its first 0.5 s of playing, as a player
// might that has not yet let go of the play before (a real one was not seen to).
const CHILD_HTML = `<!doctype html><meta charset="utf-8"><title>not YouTube</title>
<body style="margin:0;background:#1d2733;color:#cde;font:13px sans-serif;display:grid;place-items:center">
<div>a frame of another origin <b id="at">0.00</b></div><audio id="a" preload="auto"></audio>
<script>
const a = document.getElementById('a'), q = new URLSearchParams(location.search);
const deaf = q.get('deaf') === '1', late = q.get('late') === '1';
const over = +q.get('over') || 0, ghost = +q.get('ghost') || 0;
let stall = q.get('stall') === '1', stallTimer = 0, started = false, waiting = false, lateFrom = null;
a.src = q.get('src') || 'tones.wav';
if (deaf) a.muted = true;
a.addEventListener('waiting', () => { waiting = true; });
a.addEventListener('playing', () => { waiting = false; });
function state() {
  if (lateFrom != null && !a.paused && a.currentTime - lateFrom < 0.18) return 3;
  lateFrom = null;
  if (ghost && started && !a.paused && a.currentTime < ghost) return 0;
  return a.ended ? 0 : !started ? 5 : (waiting && !a.paused) ? 3 : a.paused ? 2 : 1;
}
function post() {
  parent.postMessage(JSON.stringify({event: 'infoDelivery', info: {currentTime: a.currentTime, playerState: state(),
    duration: a.duration ? a.duration + over : 0, muted: deaf ? false : a.muted, volume: Math.round(a.volume * 100), playbackRate: a.playbackRate}}), '*');
}
// its picture changes as it plays, as a video's does (a share of the tab
// sends a picture only when something in it changes)
const at = document.getElementById('at');
(function loop() { post(); at.textContent = a.currentTime.toFixed(2); requestAnimationFrame(loop); })();
addEventListener('message', e => {
  let m; try { m = JSON.parse(e.data); } catch (_) { return; }
  const x = (m.args || [])[0];
  if (m.func === 'seekTo') a.currentTime = x;
  else if (m.func === 'playVideo') {
    started = true;
    if (late) lateFrom = a.currentTime;
    a.play().catch(err => parent.postMessage(JSON.stringify({event: 'onError', info: String(err)}), '*'));
    if (stall) {
      // stops to load, and goes on by itself -- unless it is paused meanwhile
      stall = false;
      stallTimer = setTimeout(() => { a.pause(); waiting = true; post();
                                      stallTimer = setTimeout(() => { waiting = false; a.play(); }, 400); }, 1500);
    }
  }
  else if (m.func === 'pauseVideo') { clearTimeout(stallTimer); waiting = false; a.pause(); }
  else if (m.func === 'mute') a.muted = true;
  else if (m.func === 'unMute') a.muted = deaf;
  else if (m.func === 'setVolume') a.volume = Math.max(0, Math.min(1, x / 100));
  else if (m.func === 'setPlaybackRate') a.playbackRate = x;
  post();
});
a.addEventListener('loadedmetadata', () => parent.postMessage(JSON.stringify({event: 'onReady'}), '*'), {once: true});
</script>`;
// The IFrame API as the page loads it from https://www.youtube.com/iframe_api
const fakeApi = (child, query) => `(function () {
  var CHILD = ${JSON.stringify(child)}, ORIGIN = new URL(CHILD).origin;
  function Player(id, opts) {
    var self = this, el = document.getElementById(id), f = document.createElement('iframe');
    f.id = id; f.setAttribute('allow', 'autoplay');
    f.src = CHILD + '/child.html?' + ${JSON.stringify(query)};
    el.parentNode.replaceChild(f, el);
    var info = {currentTime: 0, playerState: -1, duration: 0, muted: false, volume: 100, playbackRate: 1};
    var ready = false, ev = (opts && opts.events) || {};
    window.addEventListener('message', function (e) {
      if (e.origin !== ORIGIN || e.source !== f.contentWindow) return;
      var m; try { m = JSON.parse(e.data); } catch (x) { return; }
      if (m.event === 'infoDelivery') {
        var was = info.playerState;
        for (var k in m.info) info[k] = m.info[k];
        if (ready && was !== info.playerState && ev.onStateChange) ev.onStateChange({target: self, data: info.playerState});
      } else if (m.event === 'onReady' && !ready) {
        ready = true;
        if (ev.onReady) ev.onReady({target: self});
      }
    });
    function send(func, args) { f.contentWindow.postMessage(JSON.stringify({func: func, args: args || []}), ORIGIN); }
    this.getIframe = function () { return f; };
    this.playVideo = function () { send('playVideo'); };
    this.pauseVideo = function () { send('pauseVideo'); };
    this.seekTo = function (t, ahead) { info.currentTime = t; send('seekTo', [t, ahead]); };
    this.getCurrentTime = function () { return info.currentTime; };
    this.getPlayerState = function () { return info.playerState; };
    this.getDuration = function () { return info.duration; };
    this.isMuted = function () { return info.muted; };
    this.mute = function () { info.muted = true; send('mute'); };
    this.unMute = function () { info.muted = false; send('unMute'); };
    this.getVolume = function () { return info.volume; };
    this.setVolume = function (v) { info.volume = v; send('setVolume', [v]); };
    this.getPlaybackRate = function () { return info.playbackRate; };
    this.setPlaybackRate = function (r) { info.playbackRate = r; send('setPlaybackRate', [r]); };
    (window.__fakeYT = window.__fakeYT || []).push(this);
  }
  window.YT = {Player: Player, PlayerState: {UNSTARTED: -1, ENDED: 0, PLAYING: 1, PAUSED: 2, BUFFERING: 3, CUED: 5}};
  setTimeout(function () { if (window.onYouTubeIframeAPIReady) window.onYouTubeIframeAPIReady(); }, 0);
})();`;
const P2 = freePort();
const TYPES = {html: 'text/html; charset=utf-8', wav: 'audio/wav'};
async function serveFake(req) {
  const u = new URL(req.url), name = u.pathname.replace(/^\/+/, '');
  if (name === 'child.html') return new Response(CHILD_HTML, {headers: {'content-type': TYPES.html}});
  if (!['tones.wav', 'short.wav', 'tiny.wav'].includes(name)) return new Response('404', {status: 404});
  const data = await Deno.readFile(FAKE + '/' + name);
  const h = new Headers({'content-type': TYPES.wav, 'accept-ranges': 'bytes', 'cache-control': 'no-store'});
  const m = /bytes=(\d*)-(\d*)/.exec(req.headers.get('range') || '');
  if (m) {
    const s = m[1] ? +m[1] : data.length - +m[2];
    const e = m[1] && m[2] ? Math.min(+m[2], data.length - 1) : data.length - 1;
    h.set('content-range', `bytes ${s}-${e}/${data.length}`);
    return new Response(data.slice(s, e + 1), {status: 206, headers: h});
  }
  return new Response(data, {headers: h});
}
const fakeServers = new AbortController();
Deno.serve({hostname: '127.0.0.1', port: P2, signal: fakeServers.signal, onListen() {}}, serveFake);
try { Deno.serve({hostname: '::1', port: P2, signal: fakeServers.signal, onListen() {}}, serveFake); } catch (_) {}
const CHILD = `http://localhost:${P2}`;

/* ---------------------------------------------------------------- the tree and the hub */
const IT_FIX = 'tests/fixtures/videos/italian/kL9mN1oP3qR';
const YT = 'kL9mN1oP3qR', REAL_ID = 'jNQXAC9IVRw', ZERO = 'zR0aB1cD2eF';
const ROOT = TMP + '/root', VIDEOS = ROOT + '/youtube/videos';
const TRAY = TMP + '/tray', EXERCISES = TMP + '/exercises', ANKI = TMP + '/anki';
async function copyVideo(id, edit) {
  const d = `${VIDEOS}/italian/${id}`;
  await Deno.mkdir(d + '/parts', {recursive: true});
  const meta = await readJson(IT_FIX + '/video.json');
  meta.id = id;
  meta.url = 'https://www.youtube.com/watch?v=' + id;
  await Deno.writeTextFile(d + '/video.json', JSON.stringify(meta, null, 1));
  const ann = await readJson(IT_FIX + '/annotations.json');
  ann.video = id;
  if (edit) edit(ann);
  await Deno.writeTextFile(d + '/annotations.json', JSON.stringify(ann, null, 1));
}
await Deno.mkdir(ROOT + '/youtube', {recursive: true});
await Deno.symlink(root + '/lib', ROOT + '/lib');
await Deno.symlink(root + '/youtube/lib', ROOT + '/youtube/lib');
for (const d of [TRAY, EXERCISES, ANKI, TMP + '/library']) await Deno.mkdir(d, {recursive: true});
await copyVideo(YT);
// the first caption with words at 0.4 s, so that its stretch starts at 0
const fromZero = ann => { ann.segments.splice(0, 1); ann.segments[0].start = 0.4; };
await copyVideo(ZERO, fromZero);
// the real "Me at the zoo" is 19 s: its captions end before that
if (REAL) await copyVideo(REAL_ID, ann => { ann.segments = ann.segments.filter(s => s.start < 15); fromZero(ann); });

const BOOT = `
import os, sys
from pathlib import Path
REPO = Path(sys.argv[1]); tmp = Path(sys.argv[2]); port = sys.argv[3]
for folder in ("tests", "markdown/exlex", "markdown/app", "youtube/lib", "lib", "."):   # tests LAST on the path
    sys.path.insert(0, str(REPO / folder))
os.chdir(str(REPO))
# SPEECH TO TEXT (section n): the computer's state is a file the suite edits,
# and lib/getstt.py is tests/addstt_fakes.py's stand-in -- so that what this
# machine has installed never matters, and nothing is fetched
if os.environ.get("ADD_STT_FAKE"):
    import addstt_fakes
    sys.modules["getstt"] = addstt_fakes.make(os.environ["ADD_STT_FAKE"])
    import speechconfig
    speechconfig.CONFIG = tmp / "config" / "speech.json"
    sys.modules["getstt"].preferences_file = speechconfig.CONFIG
import audiofile, clips, decks, store
clips.set_dir(tmp / "tray")
import serve, ytpages
for st in {store, serve.studio.store}:
    st.LIB = tmp / "library"
    st.set_clips_dir(tmp / "tray")
decks.set_dir(tmp / "exercises")
decks.set_clips_dir(tmp / "tray")
# WHAT THIS MACHINE KEEPS, into the temporary tree (lib/prefs.py, and
# lib/network.py since the network settings): a suite must never read the
# owner's own reading places, theme or network doors -- nor write them, which
# is what happened here: a suite turned the theme to dark in the real
# config/prefs.json and every page of the next suite opened dark.
import prefs
import network
prefs.STORE = str(tmp / "config" / "prefs.json")
network.STORE = str(tmp / "config" / "network.json")
# and the LaTeX drawings' themes, their drawings and their packages
import latexthemes, latexdraw, texpackages
latexthemes.STORE = str(tmp / "config" / "latex.json")
# and the prompts a person wrote (lib/prompts.py)
import prompts
prompts.STORE = str(tmp / "config" / "prompts.json")
latexdraw.DRAWN = str(tmp / "latex-drawn")
texpackages.TREE = str(tmp / "texmf")
import offline  # the phone-keeping memories (lib/offline.py) too
offline.DIGESTS = str(tmp / "config" / "digests.json")
offline.WHERES = str(tmp / "config" / "wheres.json")
serve.ROOT = str(tmp / "root")
serve._AtRoot.directory = str(tmp / "root")
ytpages.VIDEOS = str(tmp / "root" / "youtube" / "videos")
serve.ANKI = ytpages.ANKI = str(tmp / "anki")
ytpages.INBOX = str(tmp / "anki" / "inbox")

# "Start it empty" fetches the title and the channel as the LLM road does (TO-DO 7.6): never YouTube itself
# from a suite, so it is told what YouTube would say
ytpages.oembed_why = lambda vid: ({"title": "A video", "channel": "A channel"}, "")
sys.argv = ["serve.py", "--http", "--local", port]
serve.main()
`;
const port = freePort(), log = [];
const STTF = TMP + '/sttfake';               // the computer's speech to text, as files (section n)
await Deno.mkdir(STTF, {recursive: true});
const hub = new Deno.Command(PY, {args: ['-c', BOOT, root, TMP, String(port)], cwd: root,
                                  env: {ADD_STT_FAKE: STTF}, stdout: 'piped', stderr: 'piped'}).spawn();
for (const s of [hub.stdout, hub.stderr])
  (async () => { for await (const chunk of s.pipeThrough(new TextDecoderStream())) log.push(chunk); })();
const BASE = `http://127.0.0.1:${port}`;
{
  const t = Date.now();
  for (;;) {
    try { const r = await fetch(BASE + '/clips/api/status'); const j = await r.json(); if (r.ok && j.ffmpeg) break; } catch (_) {}
    if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join(''));
    await sleep(250);
  }
}

/* ---------------------------------------------------------------- the browsers */
const ARGS = ['--autoplay-policy=no-user-gesture-required', '--disable-audio-output'];
const launch = args => chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true, args,
                                        // a muted browser captures silence
                                        ignoreDefaultArgs: ['--mute-audio']});
const browser = await launch(['--auto-accept-this-tab-capture', ...ARGS]);
let browserNo = null;
const errors = [];
// A page of the player.  `query` goes to the fake frame; `init` runs in the
// page before its own scripts.  Every getDisplayMedia call is counted (and the
// share it gave kept, in __streams), so is every call for the microphone
// (__gum), and every connection of an audio node to the speakers.  The
// intervals a page has running are listed in __intervals (id -> ms), and
// __virt is a clock the test can turn: while __virt.on, every 25 ms interval
// -- the waveform recorder's tick, and nothing else here -- is held instead
// of run, and __virt.run(...) plays the ticks itself, one by one, against
// levels and player clocks the test made up (section l).
async function newPage(b, {width = 1280, height = 900, query = 'src=tones.wav', init = null, real = false} = {}) {
  const context = await b.newContext({viewport: {width, height}});
  await context.addInitScript(() => {
    window.__asked = [];
    window.__streams = [];
    window.__gum = 0;
    window.__toSpeakers = 0;
    const md = navigator.mediaDevices;
    if (md && md.getDisplayMedia) {
      const ask = md.getDisplayMedia.bind(md);
      md.getDisplayMedia = o => { window.__asked.push(o); return ask(o).then(s => { window.__streams.push(s); return s; }); };
    }
    if (md && md.getUserMedia) {
      const mic = md.getUserMedia.bind(md);
      md.getUserMedia = o => { window.__gum++; return mic(o); };
    }
    for (const name of ['getUserMedia', 'webkitGetUserMedia', 'mozGetUserMedia'])
      if (navigator[name]) { const old = navigator[name].bind(navigator); navigator[name] = (...a) => { window.__gum++; return old(...a); }; }
    // every AudioContext made, and every track cloned, to be found closed and
    // stopped afterwards
    window.__contexts = [];
    window.__clones = [];
    if (window.AudioContext) {
      const Made = window.AudioContext;
      window.AudioContext = class extends Made { constructor(...a) { super(...a); window.__contexts.push(this); } };
    }
    if (window.MediaStreamTrack) {
      const clone = MediaStreamTrack.prototype.clone;
      MediaStreamTrack.prototype.clone = function (...a) { const c = clone.apply(this, a); window.__clones.push(c); return c; };
    }
    window.__intervals = new Map();
    window.__virt = {on: false, timers: [], n: 0, k: 0, levels: null, clocks: null};
    const si = window.setInterval.bind(window), ci = window.clearInterval.bind(window);
    window.setInterval = function (fn, ms, ...rest) {
      if (window.__virt.on && ms === 25) {
        const id = 1e9 + ++window.__virt.n;
        window.__virt.timers.push({id, fn});
        return id;
      }
      const id = si(fn, ms, ...rest);
      window.__intervals.set(id, ms);
      return id;
    };
    window.clearInterval = function (id) {
      const at = window.__virt.timers.findIndex(t => t.id === id);
      if (at >= 0) { window.__virt.timers.splice(at, 1); return; }
      window.__intervals.delete(id);
      ci(id);
    };
    // what the analyser "hears" while the test plays the ticks: the tick's level
    // as the loudest sample of the window, one of them negative
    if (window.AnalyserNode) {
      const heard = AnalyserNode.prototype.getFloatTimeDomainData;
      AnalyserNode.prototype.getFloatTimeDomainData = function (buf) {
        const v = window.__virt;
        if (!v.on || !v.levels) return heard.call(this, buf);
        buf.fill(0);
        const level = v.levels[v.k] || 0;
        buf[3] = level * 0.25;
        buf[buf.length >> 1] = -level;
      };
    }
    // play the ticks: each one reads the clock the test made for it
    window.__virt.run = (max) => {
      const v = window.__virt, seen = [];
      let k = 0;
      for (; k < max && v.timers.length; k++) {
        v.k = k;
        v.timers.slice().forEach(t => t.fn());
        const s = document.querySelector('.tl-stat');
        if (s && seen[seen.length - 1] !== s.textContent) seen.push(s.textContent);
      }
      return {ticks: k, said: seen};
    };
    if (window.AudioNode) {
      const connect = AudioNode.prototype.connect;
      AudioNode.prototype.connect = function (to, ...rest) {
        if (to instanceof AudioDestinationNode) window.__toSpeakers++;
        return connect.call(this, to, ...rest);
      };
    }
  });
  for (const f of [].concat(init || [])) await context.addInitScript(f);
  const page = await context.newPage();
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource|youtube\.com/.test(m.text())) errors.push('console: ' + m.text()); });
  page.on('response', r => {
    const u = new URL(r.url());
    if (u.host === `127.0.0.1:${port}` && r.status() >= 400
        && /^\/(clips|exercises\/api|anki|youtube\/api|lib\/cardkit|studio\/static)/.test(u.pathname))
      errors.push(r.status() + ' ' + r.request().method() + ' ' + u.pathname);
  });
  if (!real) {
    // nothing leaves the machine: YouTube's API is this test's
    await context.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, route => route.abort());
    await context.route('https://www.youtube.com/iframe_api', route =>
      route.fulfill({status: 200, contentType: 'text/javascript', body: fakeApi(CHILD, query)}));
  }
  return {context, page};
}
// drawn: laid out and visible (whatever its hidden attribute says)
const rendered = (page, sel) => page.evaluate(sel => {
  const el = document.querySelector(sel);
  return !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
}, sel);
const shown = (page, sel) => page.evaluate(sel => {
  const el = document.querySelector(sel);
  if (!el || el.closest('[hidden]')) return false;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
}, sel);
// really on screen: inside the viewport, and what is at its middle is it
const onScreen = (page, sel) => page.evaluate(sel => {
  const el = document.querySelector(sel);
  if (!el || el.closest('[hidden]')) return false;
  const r = el.getBoundingClientRect();
  const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return r.width > 0 && r.left >= 0 && r.top >= 0 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1 && !!hit && el.contains(hit);
}, sel);
const text = (page, sel) => page.evaluate(sel => document.querySelector(sel).textContent, sel);
const value = (page, sel) => page.evaluate(sel => document.querySelector(sel).value, sel);
const stat = page => page.evaluate(() => { const s = document.querySelector('.pc-stat'); return s ? s.textContent : ''; });
async function shot(page, name) {
  if (!SHOTS) return;
  await Deno.mkdir(SHOTS, {recursive: true});
  await page.screenshot({path: `${SHOTS}/${name}.png`});
}
// the fake frame, as the page sees it
const childFrame = page => page.frames().find(f => f.url().startsWith(CHILD));
const childState = page => childFrame(page).evaluate(() => {
  const a = document.querySelector('audio');
  return {t: a.currentTime, paused: a.paused, muted: a.muted, volume: a.volume, rate: a.playbackRate};
});
async function openVideo(page, id = YT) {
  await page.goto(`${BASE}/youtube/v/${id}/`);
  await page.waitForSelector('.seg .fa .w');
  await until(() => page.evaluate(() => window.__fakeYT && __fakeYT[0] && __fakeYT[0].getDuration() > 40), 'the fake player is ready');
}
async function altClick(page, sel) {
  await page.mouse.move(2, 2);
  await page.locator(sel).click({modifiers: ['Alt']});
  await until(() => page.evaluate(() => !document.querySelector('#anki').hidden), 'the card sheet opens');
}
// the editor's record step, then the recording: resolves once the editor
// holds a recording, with the status it says
async function recordIn(page, what, {click = true} = {}) {
  if (click) {
    assert(await onScreen(page, '.pc-cut .pc-record'), what + ': the record button is on screen');
    await page.click('.pc-cut .pc-record');
  }
  await until(async () => {
    // a recording that failed says so at once, in what it said
    if (await page.evaluate(() => document.querySelector('.pc-stat').classList.contains('pc-bad')))
      throw Error('FAIL: ' + what + ': the stretch is not recorded: ' + await stat(page));
    return (await shown(page, '.pc-strip')) && /^recorded /.test(await stat(page)) &&
           await page.evaluate(() => document.querySelector('.pc-strip').classList.contains('pc-drawn'));
  }, what + ': the stretch is recorded (' + await stat(page) + ')', 40000);
  return stat(page);
}
// what the strip shows, [from, to], as the scale under it prints them
const viewOf = page => page.evaluate(() => {
  const sc = document.querySelector('.pc-strip').nextElementSibling;
  return [parseFloat(sc.children[0].textContent), parseFloat(sc.children[2].textContent)];
});
// the waveform's canvas: how much is drawn at the middle of each [t0, t1]
const drawnAt = (page, spans) => page.evaluate(spans => {
  const c = document.querySelector('.pc-wave'), strip = c.parentNode;
  const v0 = parseFloat(strip.nextElementSibling.children[0].textContent), v1 = parseFloat(strip.nextElementSibling.children[2].textContent);
  const x = c.getContext('2d'), k = c.width / strip.clientWidth;
  return spans.map(([a, b]) => {
    const px = Math.round(((a + b) / 2 - v0) / (v1 - v0) * c.width);
    const col = x.getImageData(Math.max(0, px - 2 * k), 0, Math.max(1, 4 * k), c.height).data;
    let on = 0;
    for (let i = 3; i < col.length; i += 4) if (col[i] > 0) on++;
    return on / (col.length / 4);
  });
}, spans);
async function saveAndUse(page, what, video = YT) {
  const s = +(await value(page, '.pc-cut input.e0')), e = +(await value(page, '.pc-cut input.e1'));
  const before = await names(TRAY, /\.(mp3|m4a|wav)$/);
  await page.click('.pc-cut .pc-save');
  await until(async () => /saved to the clip tray/.test(await stat(page)), what + ': the clip is saved', 20000);
  const fresh = (await names(TRAY, /\.(mp3|m4a|wav)$/)).filter(n => !before.includes(n));
  assert(fresh.length === 1, `${what}: one new file in the tray: ${fresh}`);
  const meta = await readJson(`${TRAY}/${fresh[0]}.json`);
  assert(meta.source && meta.source.kind === 'youtube' && meta.source.video === video && near(meta.source.start, s, 0.001),
         `${what}: the tray says where it was cut from: ${JSON.stringify(meta.source)}`);
  await page.click('.pc-cut .pc-use');
  await until(() => page.evaluate(() => !document.querySelector('.pc-root') && !document.querySelector('#asndprev').hidden), what + ': the editor closes on the clip');
  eq(await page.evaluate(() => document.querySelector('#asndname').textContent.split(' · ')[0]), fresh[0], what + ': the sheet shows the clip');
  return {name: fresh[0], s, e};
}

try {
/* ================================================================ a) an exercise deck */
console.log('a) the editor records the stretch, and cuts it');
const {context, page} = await newPage(browser);
await page.goto(BASE + '/');
await page.evaluate(() => localStorage.clear());
await openVideo(page);
eq(await page.evaluate(() => [!!document.querySelector('#film'), document.querySelector('#yt').tagName, ParsehCards.canCaptureTab(), ParsehCards.tabProblem()]),
   [false, 'IFRAME', true, ''], 'a YouTube video: no film, the player\'s frame of another origin, and this Chrome can record the tab');
// the person's own player settings, which the recording must leave as they were
await page.evaluate(() => { __fakeYT[0].setVolume(40); __fakeYT[0].setPlaybackRate(1.25); __fakeYT[0].seekTo(16.2, true); });
await until(async () => { const c = await childState(page); return near(c.volume, 0.4, 0.01) && c.rate === 1.25 && near(c.t, 16.2, 0.05); }, 'the player set up');
await altClick(page, '.seg[data-i="3"] .w[data-j="1"] .wd >> nth=1');
eq(await page.evaluate(() => { const b = document.querySelector('#asnd'); return [document.querySelector('#afa').value, b.disabled, b.title, document.querySelector('#asndwhy').getClientRects().length > 0]; }),
   ['chilo', false, 'record this tab while the video plays the stretch this card is about, cut the clip out of it by ear, and put it on the card', false],
   'the sheet on "chilo": "cut the audio…" enabled on a YouTube video, saying what it does');
await page.click('#atdeck');
await until(() => page.evaluate(() => document.querySelector('#asavelab').textContent === 'add to deck'), 'the exercise deck destination');
await page.fill('#adecknew', 'Dal video');
await page.click('#asnd');
await until(() => shown(page, '.pc-cut .pc-take'), 'the editor opens on its record step');
const step = await page.evaluate(() => ({text: document.querySelector('.pc-take-text').textContent,
  drawn: ['.pc-strip', '.pc-scale', '.pc-rows', '.pc-save', '.pc-use', '.pc-again', '.pc-hint'].map(s => document.querySelector('.pc-cut ' + s).getClientRects().length > 0),
  record: getComputedStyle(document.querySelector('.pc-cut .pc-record')).backgroundColor,
  use: getComputedStyle(document.querySelector('.pc-cut .pc-use')).backgroundColor,
  asked: window.__asked.length}));
eq(step.drawn, [false, false, false, false, false, false, false], 'before a recording the editor draws no strip, no rows and nothing to save');
eq(step.record, step.use, '"record" is drawn as the step\'s one action, in the colour of "use this clip"');
assert(/sound is cut from a recording of this tab/.test(step.text) && /14\.00–21\.00 s plays once, sound on/.test(step.text) &&
       /press “Allow”, and leave “Also allow tab audio” turned on/.test(step.text) && step.asked === 0,
       'it says what happens and what Chrome will ask, and has not asked yet: ' + step.text);
await shot(page, 'record-step-desktop');
await recordIn(page, '"chilo"');
const asked = await page.evaluate(() => window.__asked.map(o => ({audio: !!o.audio, preferCurrentTab: o.preferCurrentTab, video: o.video})));
eq(asked, [{audio: true, preferCurrentTab: true, video: true}], 'Chrome was asked once, for this tab with its sound');
const after1 = await childState(page);
assert(after1.paused && near(after1.t, 16.2, 0.1) && near(after1.volume, 0.4, 0.01) && after1.rate === 1.25 && !after1.muted,
       'the player is put back as it was: paused at its place, its volume and its speed: ' + JSON.stringify(after1));
eq(await page.evaluate(() => window.__toSpeakers), 0, 'nothing of the recording was connected to the speakers');
const v1 = await page.evaluate(() => [document.querySelector('.pc-cut input.e0').value, document.querySelector('.pc-cut input.e1').value,
                                     document.querySelector('.pc-scale').textContent]);
eq(v1.slice(0, 2), ['17.62', '18.83'], 'the edges start at the word\'s share of the caption');
eq(await page.evaluate(() => ['.pc-take', '.pc-strip', '.pc-rows', '.pc-again', '.pc-save', '.pc-use'].map(s => document.querySelector('.pc-cut ' + s).getClientRects().length > 0)),
   [false, true, true, true, true, true], 'recorded: the first step gives way to the strip, the rows, "record again", save and use');
const drawn = await drawnAt(page, [[16, 16.5], [16.5, 17], [19, 19.5], [19.5, 20]]);
assert(drawn[0] > 0.25 && drawn[1] < 0.05 && drawn[2] > 0.25 && drawn[3] < 0.05,
       'the waveform is drawn from the recording: the tones are there, the silences empty: ' + JSON.stringify(drawn.map(x => +x.toFixed(2))));
await shot(page, 'recorded-desktop');
// by ear: the start half a second earlier, the end a tenth later; each nudge
// plays from the recording
await page.click('.pc-cut [data-e="s-5"]');
await until(() => page.evaluate(() => { const p = document.querySelector('.pc-play'); return !p.paused && p.currentTime > 0.1; }), 'the start nudge plays');
const heard = await page.evaluate(() => { const p = document.querySelector('.pc-play'); return [p.src.slice(0, 5), p.readyState]; });
assert(heard[0] === 'blob:' && heard[1] >= 2, 'the nudge is played from the recording itself: ' + heard);
await page.click('.pc-cut [data-e="e+"]');
eq([await value(page, '.pc-cut input.e0'), await value(page, '.pc-cut input.e1')], ['17.12', '18.93'], 'the edges moved');
const clipA = await saveAndUse(page, '"chilo"');
await clipIsExact(`${TRAY}/${clipA.name}`, clipA.s, clipA.e, '"chilo"');
await page.locator('#adirfwd:visible').click({timeout: 1500}).catch(() => {});   // the sheet's default is a pair; this is about the recording
await page.click('#asave');
await until(() => page.evaluate(() => /^added ✓/.test(document.querySelector('#astat').textContent)), 'the card goes into the deck', 20000);
{
  let slug = '';
  for await (const e of Deno.readDir(EXERCISES + '/italian')) if (e.isDirectory && !e.name.startsWith('.')) slug = e.name;
  const DECK = `${EXERCISES}/italian/${slug}`, items = await names(DECK + '/items', /\.json$/);
  const item = await readJson(`${DECK}/items/${items[0]}`);
  assert(items.length === 1 && item.markdown.includes('front-audio: audio/' + clipA.name) && await exists(`${DECK}/audio/${clipA.name}`),
         'the deck\'s exercise names the recording as front-audio, and the deck has the file:\n' + item.markdown);
  eq(await text(page, '#astat'), 'added ✓ — a vocabulary card for “chilo”, with its recording, to “Dal video” — open the deck', 'the sheet says it went in with its recording');
}

/* ================================================================ b) the frame, and Anki */
console.log('b) the frame capture shares the tab; Anki');
await page.click('#ashot');
await until(() => page.evaluate(() => { const i = document.querySelector('#ashotimg'); return !document.querySelector('#ashotprev').hidden && i.naturalWidth > 100; }),
            'the frame is captured', 40000).catch(async e => { throw Error(e.message + ': ' + await text(page, '#astat')); });
eq(await page.evaluate(() => window.__asked.length), 1, 'the frame is taken off the same share: Chrome was not asked again');
await page.keyboard.press('Escape');
await until(() => page.evaluate(() => document.querySelector('#anki').hidden), 'the sheet closes');
// the person had muted the player: it is unmuted for the recording and muted again
await page.evaluate(() => __fakeYT[0].mute());
await until(async () => (await childState(page)).muted, 'the player muted');
await altClick(page, '.seg[data-i="2"] .w[data-j="1"] .wd >> nth=1');
await page.click('#atanki');
await until(() => page.evaluate(() => document.querySelector('#asavelab').textContent === 'save card'), 'Anki');
await page.fill('#adecknew', 'Italiano::YouTube');
// a sound of the page's own: it must not be heard in the tab's recording
await page.evaluate(name => {
  const a = document.createElement('audio');
  a.id = 'pagesound'; a.loop = true; a.src = '/clips/media/' + name;
  document.body.appendChild(a);
  return a.play();
}, clipA.name);
await page.click('#asnd');
const during = await until(() => page.evaluate(() => {
  const s = document.querySelector('.pc-stat'), a = document.querySelector('#pagesound');
  return s && /^recording .*: \d/.test(s.textContent) ? {muted: a.muted, paused: a.paused, stat: s.textContent, record: document.querySelector('.pc-take').getClientRects().length > 0} : null;
}), 'the recording starts by itself: the tab is shared already');
assert(during.muted && during.paused && during.record, 'it records at once, with the page\'s own audio muted and stopped meanwhile: ' + JSON.stringify(during));
const childDuring = await childState(page);
assert(!childDuring.muted && childDuring.volume === 1 && childDuring.rate === 1, 'the player plays unmuted, at full volume and normal speed while it records: ' + JSON.stringify(childDuring));
await recordIn(page, '"mele"', {click: false});
const after2 = await childState(page);
assert(after2.muted && near(after2.volume, 0.4, 0.01) && after2.rate === 1.25 && after2.paused,
       'the muted player is muted again after it: ' + JSON.stringify(after2));
eq(await page.evaluate(() => [window.__asked.length, document.querySelector('#pagesound').muted]), [1, false], 'still one question from Chrome, and the page\'s audio is unmuted again');
await page.evaluate(() => document.querySelector('#pagesound').remove());
const clipB = await saveAndUse(page, '"mele"');
await clipIsExact(`${TRAY}/${clipB.name}`, clipB.s, clipB.e, '"mele"');
await page.click('#asave');
await until(() => page.evaluate(() => document.querySelector('#anki').hidden), 'the Anki card is saved and the sheet closes', 20000);
{
  let slug = '';
  for await (const e of Deno.readDir(ANKI + '/italian')) if (e.isDirectory) slug = e.name;
  const cards = await names(`${ANKI}/italian/${slug}/cards`, /\.json$/);
  const note = await readJson(`${ANKI}/italian/${slug}/cards/${cards[0]}`);
  assert(note.fa === 'mele' && /-front-audio\.(mp3|m4a|wav)$/.test(note.snd_front || '') && note.snd_back === null,
         'the Anki note carries the recording on the front: ' + JSON.stringify({fa: note.fa, snd_front: note.snd_front, snd_back: note.snd_back}));
  const media = await Deno.readFile(`${ANKI}/italian/${slug}/media/${note.snd_front}`), tray = await Deno.readFile(`${TRAY}/${clipB.name}`);
  assert(media.length === tray.length && media.every((b, i) => b === tray[i]), 'its media/ holds the tray\'s clip, byte for byte');
}
await page.evaluate(() => __fakeYT[0].unMute());
await context.close();

/* ================================================================ c) the worklet path */
console.log('c) no track processor: an AudioWorklet');
{
  const {context: cw, page: pw} = await newPage(browser, {init: () => {
    delete window.MediaStreamTrackProcessor;
    window.__worklets = 0;
    const add = AudioWorklet.prototype.addModule;
    AudioWorklet.prototype.addModule = function (...a) { window.__worklets++; return add.apply(this, a); };
  }});
  await openVideo(pw);
  await altClick(pw, '.seg[data-i="5"] .w[data-j="1"] .wd');
  await pw.click('#asnd');
  await until(() => shown(pw, '.pc-cut .pc-record'), 'the record step');
  await recordIn(pw, 'the worklet');
  eq(await pw.evaluate(() => [typeof MediaStreamTrackProcessor, window.__worklets, window.__toSpeakers]), ['undefined', 1, 0],
     'recorded through an AudioWorklet, which is connected to no speaker');
  await pw.click('.pc-cut [data-e="s-5"]');
  const clipW = await saveAndUse(pw, 'the worklet');
  await clipIsExact(`${TRAY}/${clipW.name}`, clipW.s, clipW.e, 'the worklet');
  await cw.close();
}

/* ================================================================ d) a stall, and the phone */
console.log('d) a player that stops to load; the phone');
{
  const {context: cp, page: pp} = await newPage(browser, {width: 400, height: 820, query: 'src=tones.wav&stall=1'});
  await openVideo(pp);
  await pp.evaluate(() => document.querySelector('.seg[data-i="3"]').scrollIntoView({block: 'center'}));
  await altClick(pp, '.seg[data-i="3"] .w[data-j="1"] .wd >> nth=1');
  await pp.click('#asnd');
  await until(() => shown(pp, '.pc-cut .pc-record'), 'the record step on the phone');
  assert(await onScreen(pp, '.pc-cut .pc-take') && await pp.evaluate(() => document.querySelector('.pc-cut').scrollWidth <= document.querySelector('.pc-cut').clientWidth),
         'at 400 px the record step is on screen, nothing wider than the editor');
  await shot(pp, 'record-step-phone');
  await pp.click('.pc-cut .pc-record');
  await until(async () => /once more/.test(await stat(pp)), 'the stall is noticed and the stretch played once more', 30000);
  assert(true, 'the player stopped to load: ' + await stat(pp));
  await recordIn(pp, 'after the stall', {click: false});
  for (const sel of ['.pc-strip', '.pc-cut [data-e="s-1"]', '.pc-cut [data-e="e+1"]', '.pc-cut [data-e="rv"]',
                     '.pc-cut input.pc-r0', '.pc-cut input.pc-r1',
                     '.pc-cut .pc-again', '.pc-cut .pc-save', '.pc-cut .pc-use'])
    assert(await onScreen(pp, sel), `at 400 px ${sel} is on screen`);
  // the edges' inputs show their whole value, a long video's too: an input
  // whose text is cut scrolls, wider than it is (spin buttons and all)
  const fit = async () => pp.evaluate(() => [...document.querySelectorAll('.pc-cut .edit input')].map(inp => [inp.value, inp.scrollWidth, inp.clientWidth]));
  const f1 = await fit();
  assert(f1.map(f => f[0]).join() === '17.62,18.83,0,0' && f1.every(([, sw, cw]) => sw <= cw),
         'at 400 px each edge\'s input, and the two reach boxes, show their whole value ' +
         '(scrollWidth within clientWidth): ' + JSON.stringify(f1));
  await pp.evaluate(() => { const i = document.querySelector('.pc-cut input.e0'); i.value = '1234.56'; });
  const f2 = await fit();
  assert(f2[0][1] <= f2[0][2], 'and a value of an hour-long video, 1234.56: ' + JSON.stringify(f2[0]));
  await pp.evaluate(() => { document.querySelector('.pc-cut input.e0').value = '17.62'; });
  assert(await pp.evaluate(() => document.documentElement.scrollWidth <= innerWidth && document.querySelector('.pc-cut').scrollWidth <= document.querySelector('.pc-cut').clientWidth),
         'at 400 px nothing is wider than the phone');
  await shot(pp, 'recorded-phone');
  const clipS = await saveAndUse(pp, 'after the stall');
  await clipIsExact(`${TRAY}/${clipS.name}`, clipS.s, clipS.e, 'after the stall');
  await cp.close();
}

/* ================================================================ e) failures */
console.log('e) failures, said in plain words');
// a clip must not come of any of them
const trayBefore = await names(TRAY);
browserNo = await launch(ARGS);
{
  // where no tab can be recorded, the button says why, and which it is
  const why = async (init, what) => {
    const {context: cx, page: px} = await newPage(browserNo, {init});
    await openVideo(px);
    await altClick(px, '.seg[data-i="3"] .w[data-j="1"] .wd >> nth=1');
    const r = await px.evaluate(() => { const b = document.querySelector('#asnd'), h = document.querySelector('#asndwhy');
      return [b.disabled, b.title, h.getClientRects().length > 0 ? h.textContent : null]; });
    await cx.close();
    return r;
  };
  // Firefox and Safari: no userAgentData, which only Chromium has
  eq(await why(() => { Object.defineProperty(Navigator.prototype, 'userAgentData', {get: () => undefined}); }),
     [true, 'a YouTube video’s sound is cut from a recording of this tab, and only Chrome and Edge, on a computer, can record the sound of a tab',
      'a YouTube video’s sound is cut from a recording of this tab, and only Chrome and Edge, on a computer, can record the sound of a tab'],
     'not Chrome or Edge: "cut the audio…" is disabled, and says so under it');
  eq(await why(() => { Object.defineProperty(window, 'isSecureContext', {get: () => false}); }),
     [true, 'a YouTube video’s sound is cut from a recording of this tab, and recording this tab needs the page opened at the toolbox’s https address, in Chrome or Edge',
      'a YouTube video’s sound is cut from a recording of this tab, and recording this tab needs the page opened at the toolbox’s https address, in Chrome or Edge'],
     'not https: disabled, saying to open the https address');
}
{
  // Chrome's question answered "Cancel"
  const {context: c1, page: p1} = await newPage(browserNo, {init: () => {
    navigator.mediaDevices.getDisplayMedia = () => Promise.reject(new DOMException('Permission denied', 'NotAllowedError'));
  }});
  await openVideo(p1);
  await altClick(p1, '.seg[data-i="3"] .w[data-j="1"] .wd >> nth=1');
  await p1.click('#asnd');
  await p1.click('.pc-cut .pc-record');
  await until(async () => /press “Allow”/.test(await stat(p1)), 'the refusal is said');
  const r1 = await p1.evaluate(() => ({stat: document.querySelector('.pc-stat').textContent, bad: document.querySelector('.pc-stat').classList.contains('pc-bad'),
                                       again: !document.querySelector('.pc-take').hidden && document.querySelector('.pc-record').getAttribute('aria-disabled') === 'false',
                                       strip: document.querySelector('.pc-strip').getClientRects().length === 0 &&
                                              document.querySelector('.pc-rows').getClientRects().length === 0}));
  eq(r1, {stat: 'the tab was not shared, so nothing was recorded: press “record” and, when Chrome asks, press “Allow”', bad: true, again: true, strip: true},
     'not allowed: it says to press Allow, and "record" can be pressed again');
  await shot(p1, 'refused-desktop');
  await p1.keyboard.press('Escape');
  await c1.close();

  // shared without its sound
  const {context: c2, page: p2} = await newPage(browserNo, {init: () => {
    navigator.mediaDevices.getDisplayMedia = () => {
      const c = document.createElement('canvas');
      c.width = 64; c.height = 36;
      c.getContext('2d').fillRect(0, 0, 64, 36);
      return Promise.resolve(c.captureStream(5));
    };
  }});
  await openVideo(p2);
  await altClick(p2, '.seg[data-i="3"] .w[data-j="1"] .wd >> nth=1');
  await p2.click('#asnd');
  await p2.click('.pc-cut .pc-record');
  await until(async () => /Also allow tab audio/.test(await stat(p2)), 'the missing sound is said');
  eq(await stat(p2), 'the tab was shared without its sound: press “record” and, when Chrome asks, leave “Also allow tab audio” turned on',
     'no sound in the share: it says to leave "Also allow tab audio" on');
  await c2.close();
}
{
  // a video whose sound is off
  const {context: c3, page: p3} = await newPage(browser, {query: 'src=tones.wav&deaf=1'});
  await openVideo(p3);
  await altClick(p3, '.seg[data-i="2"] .w[data-j="1"] .wd >> nth=1');
  await p3.click('#asnd');
  await p3.click('.pc-cut .pc-record');
  await until(async () => /no sound was captured/.test(await stat(p3)), 'the silence is said', 40000);
  eq(await stat(p3), 'no sound was captured — is the video muted? Turn its sound on and record again', 'silence: it asks whether the video is muted');
  assert(await p3.evaluate(() => document.querySelector('.pc-strip').getClientRects().length === 0 && document.querySelector('.pc-rows').getClientRects().length === 0) &&
         await rendered(p3, '.pc-cut .pc-record'),
         'and offers "record" again, with nothing to cut');
  await c3.close();
}
eq(await names(TRAY), trayBefore, 'none of the failures put anything in the tray');

/* ================================================================ f) a share without its sound */
console.log('f) a frame off a share without its sound, then a cut');
{
  // the first time Chrome asked, "Also allow tab audio" was turned off
  const {context: cf, page: pf} = await newPage(browser, {init: () => {
    const md = navigator.mediaDevices, ask = md.getDisplayMedia.bind(md);
    window.__shares = [];
    md.getDisplayMedia = o => ask(window.__shares.length ? o : Object.assign({}, o, {audio: false}))
      .then(s => { window.__shares.push(s); return s; });
  }});
  await openVideo(pf);
  await altClick(pf, '.seg[data-i="3"] .w[data-j="1"] .wd >> nth=1');
  const frame = async what => {
    await pf.evaluate(() => document.querySelector('#ashotimg').removeAttribute('src'));
    await pf.click('#ashot');
    await until(() => pf.evaluate(() => { const i = document.querySelector('#ashotimg'); return !document.querySelector('#ashotprev').hidden && i.naturalWidth > 100; }),
                what, 40000).catch(async e => { throw Error(e.message + ': ' + await text(pf, '#astat')); });
  };
  await frame('the frame is captured off a share without sound');
  eq(await pf.evaluate(() => __shares.map(s => s.getTracks().map(t => t.kind + ':' + t.readyState).sort().join())), ['video:live'],
     'the frame came off a share with no sound in it');
  await pf.click('#asnd');
  await until(() => shown(pf, '.pc-cut .pc-take'), 'the record step');
  assert(/Chrome asks first/.test(await text(pf, '.pc-take-text')) && !/^recording/.test(await stat(pf)),
         'the share has no sound: the editor says Chrome will ask, and waits for "record"');
  await recordIn(pf, 'after a frame off a share without sound');
  eq(await pf.evaluate(() => [__asked.map(o => !!o.audio), __shares.map(s => s.getTracks().map(t => t.kind + ':' + t.readyState).sort().join())]),
     [[false, true], ['video:ended', 'audio:live,video:live']],
     'Chrome was asked once more, with the sound, and the share without it was let go for the new one');
  const clipF = await saveAndUse(pf, 'after a frame off a share without sound');
  await clipIsExact(`${TRAY}/${clipF.name}`, clipF.s, clipF.e, 'after a frame off a share without sound');
  await frame('the next frame is captured');
  eq(await pf.evaluate(() => __asked.length), 2, 'the next frame is taken off the new share: Chrome was not asked a third time');
  await cf.close();
}

/* ================================================================ g) record again after saving */
console.log('g) "record again" after "save clip"');
{
  const {context: cg, page: pg} = await newPage(browser);
  const uploads = [];
  pg.on('request', r => { if (/\/clips\/api\/upload/.test(r.url())) uploads.push(r.url()); });
  await openVideo(pg);
  await altClick(pg, '.seg[data-i="3"] .w[data-j="1"] .wd >> nth=1');
  await pg.click('#asnd');
  await until(() => shown(pg, '.pc-cut .pc-record'), 'the record step');
  await recordIn(pg, 'the first recording');
  const quiet = await drawnAt(pg, [[16.5, 17]]);
  await pg.click('.pc-cut .pc-save');
  await until(async () => /saved to the clip tray/.test(await stat(pg)), 'the first clip is saved', 20000);
  const first = (await text(pg, '.pc-cut .pc-name')).split(' · ')[0];
  assert(await exists(`${TRAY}/${first}`) && uploads.length === 1 && quiet[0] < 0.05, 'the first recording\'s clip is in the tray: ' + first);
  // the video's sound is now one steady 1000 Hz tone, as if the first take had caught something else
  await childFrame(pg).evaluate(() => {
    const rate = 8000, n = rate * 42, buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
    const put = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    put(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); put(8, 'WAVE'); put(12, 'fmt '); v.setUint32(16, 16, true);
    v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true);
    v.setUint16(32, 2, true); v.setUint16(34, 16, true); put(36, 'data'); v.setUint32(40, n * 2, true);
    for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, Math.round(Math.sin(2 * Math.PI * 1000 * i / rate) * 12000), true);
    const a = document.querySelector('audio');
    a.src = URL.createObjectURL(new Blob([buf], {type: 'audio/wav'}));
    return new Promise(r => a.addEventListener('loadedmetadata', r, {once: true}));
  });
  await pg.click('.pc-cut .pc-again');
  await until(async () => /^recording /.test(await stat(pg)), 'recording again');
  await until(() => pg.evaluate(() => !document.querySelector('.pc-cut').classList.contains('pc-busy')), 'the second recording is made', 40000);
  const loud = await drawnAt(pg, [[16.5, 17]]);
  const ed = await pg.evaluate(() => ({stat: document.querySelector('.pc-stat').textContent,
                                       stale: document.querySelector('.pc-saved').classList.contains('pc-stale'),
                                       opacity: getComputedStyle(document.querySelector('.pc-saved')).opacity}));
  assert(loud[0] > 0.25, 'the strip shows the new recording, sound where the old one was silent: ' + loud[0].toFixed(2));
  eq(ed, {stat: 'the clip saved is of the recording before this one: “use this clip” cuts it again, from this one', stale: true, opacity: '0.55'},
     'the clip saved before is dimmed, and said to be the old recording\'s');
  await shot(pg, 'record-again-after-save');
  await pg.click('.pc-cut .pc-use');
  await until(() => pg.evaluate(() => !document.querySelector('.pc-root') && !document.querySelector('#asndprev').hidden), 'the editor closes on the clip', 20000);
  const used = (await text(pg, '#asndname')).split(' · ')[0];
  assert(used !== first && uploads.length === 2 && await exists(`${TRAY}/${used}`) && !(await exists(`${TRAY}/${first}`)),
         `"use this clip" cut a new clip (${used}) off the new recording, and the old one (${first}) left the tray`);
  const m = await measure(`${TRAY}/${used}`);
  assert(m.runs.length === 1 && near(m.runs[0][0], 0, 0.025) && near(m.runs[0][1], m.duration, 0.025) && near(m.runs[0][2], 1000, 25),
         'the card\'s clip is the new sound, one steady 1000 Hz tone end to end: ' + JSON.stringify(m.runs));
  await cg.close();
}

/* ================================================================ h) from 0 s, PLAYING said late */
console.log('h) the first caption, from 0 s, on a player that says PLAYING late');
{
  const {context: ch, page: ph} = await newPage(browser, {query: 'src=tones.wav&late=1'});
  await openVideo(ph, ZERO);
  // what the kit reads: where the video is by the first PLAYING it hears
  await ph.evaluate(() => {
    const p = __fakeYT[0], get = p.getPlayerState;
    window.__firstPlaying = null;
    p.getPlayerState = function () { const st = get.call(p); if (st === 1 && __firstPlaying == null) __firstPlaying = p.getCurrentTime(); return st; };
  });
  await altClick(ph, '.seg[data-i="0"] .w[data-j="0"] .wd >> nth=0');
  await ph.click('#asnd');
  await until(() => shown(ph, '.pc-cut .pc-record'), 'the record step');
  assert(/the stretch 0\.00–/.test(await text(ph, '.pc-take-text')), 'the stretch starts at the start of the video: ' + await text(ph, '.pc-take-text'));
  const r = await recordIn(ph, 'from 0 s');
  const firstPlaying = await ph.evaluate(() => window.__firstPlaying);
  assert(firstPlaying >= 0.15, `the player said PLAYING first ${firstPlaying.toFixed(3)} s into the video, and the stretch is recorded all the same: ${r}`);
  assert(/^recorded 0\.00–/.test(r), 'the recording holds the video from 0 s: ' + r);
  await ph.fill('.pc-cut input.e0', '0');
  await ph.press('.pc-cut input.e0', 'Enter');
  await ph.fill('.pc-cut input.e1', '1.3');
  await ph.press('.pc-cut input.e1', 'Enter');
  eq([await value(ph, '.pc-cut input.e0'), await value(ph, '.pc-cut input.e1')], ['0.00', '1.30'], 'the edges at 0 and 1.3 s');
  const clipZ = await saveAndUse(ph, 'from 0 s', ZERO);
  await clipIsExact(`${TRAY}/${clipZ.name}`, clipZ.s, clipZ.e, 'from 0 s');
  await ch.close();
}

/* ================================================================ i) a real YouTube embed */
if (REAL) {
  console.log('i) a real YouTube embed (YT_REAL=1)');
  for (const [where, seg] of [['the middle', 1], ['the start', 0]]) {
    const {context: cr, page: pr} = await newPage(browser, {real: true});
    await pr.goto(`${BASE}/youtube/v/${REAL_ID}/`);
    await pr.waitForSelector('.seg .fa .w');
    await altClick(pr, `.seg[data-i="${seg}"] .w[data-j="0"] .wd >> nth=0`);
    await until(() => pr.evaluate(() => !document.querySelector('#asnd').disabled), 'the YouTube player is ready', 30000);
    await pr.click('#asnd');
    await pr.click('.pc-cut .pc-record');
    await until(async () => /^recorded /.test(await stat(pr)) || await pr.evaluate(() => document.querySelector('.pc-stat').classList.contains('pc-bad')),
                'the real embed is recorded', 90000);
    const r = await stat(pr);
    assert(/^recorded /.test(r), `${where} of a real YouTube video is recorded: ${r}`);
    if (seg === 0) {
      assert(/^recorded 0\.00–/.test(r), 'from 0 s');
      await pr.fill('.pc-cut input.e0', '0');
      await pr.press('.pc-cut input.e0', 'Enter');
      await pr.fill('.pc-cut input.e1', '2');
      await pr.press('.pc-cut input.e1', 'Enter');
    }
    const before = await names(TRAY, /\.(mp3|m4a|wav)$/);
    const s = +(await value(pr, '.pc-cut input.e0')), e = +(await value(pr, '.pc-cut input.e1'));
    await pr.click('.pc-cut .pc-save');
    await until(async () => /saved to the clip tray/.test(await stat(pr)), 'saved', 20000);
    const fresh = (await names(TRAY, /\.(mp3|m4a|wav)$/)).filter(n => !before.includes(n));
    const m = await measure(`${TRAY}/${fresh[0]}`);
    assert(fresh.length === 1 && near(m.duration, e - s, 0.03) && m.peak > 0.02,
           `${where}: a real YouTube embed gives a clip of ${m.duration.toFixed(3)} s for ${s}–${e} with sound in it (peak ${m.peak.toFixed(3)})`);
    // the video's first moments are its room noise, not the silence of a
    // recording made before the video played
    if (seg === 0)
      assert(m.rms50.slice(0, 4).every(x => x > 0.003), 'from 0 s, its first 200 ms hold the video\'s sound, not silence: ' + JSON.stringify(m.rms50.slice(0, 6)));
    await cr.close();
  }
}

/* ================================================================ j) reach: record again, further back */
console.log('j) "reach": record again sent further back than the caption');
{
  const {context: cj, page: pj} = await newPage(browser);
  await openVideo(pj);
  await altClick(pj, '.seg[data-i="3"] .w[data-j="1"] .wd >> nth=1');
  await pj.click('#asnd');
  await until(() => shown(pj, '.pc-cut .pc-record'), 'the record step');
  await recordIn(pj, 'the first recording');
  const before = await viewOf(pj);
  eq(await pj.evaluate(() => {
       const r = document.querySelector('.pc-cut .pc-row-r'), i = r.querySelectorAll('input.pc-r');
       return [r.getClientRects().length > 0, i.length, i[0].value, i[1].value,
               [...r.childNodes].map(n => n.textContent).join('|')];
     }),
     [true, 2, '0', '0', 'reach|start||s|end||s'],
     'the reach row stands with the recording, both edges at 0 s');

  // the caption cut the sentence across: the words wanted are two seconds
  // before it.  Type -2 on the start and press Enter -- which records.
  await pj.fill('.pc-cut input.pc-r0', '-2');
  await pj.press('.pc-cut input.pc-r0', 'Enter');
  await until(async () => /^recording /.test(await stat(pj)), 'Enter in the reach box records again');
  await until(() => pj.evaluate(() => !document.querySelector('.pc-cut').classList.contains('pc-busy')),
              'the second recording is made', 40000);
  const after = await viewOf(pj);
  assert(near(after[0], before[0] - 2, 0.1) && near(after[1], before[1], 0.1),
         `the strip reaches two seconds further back and no further on: ${JSON.stringify(before)} -> ${JSON.stringify(after)}`);

  // a half second that was out of reach before: whole seconds hold the tone
  // that says which second of the video it is
  const s0 = Math.ceil(after[0] + 0.01), e0 = s0 + 0.5;
  assert(s0 < before[0], `${s0} s was outside the first recording (it began at ${before[0]})`);
  await pj.fill('.pc-cut input.e0', String(s0));
  await pj.press('.pc-cut input.e0', 'Enter');
  await pj.fill('.pc-cut input.e1', String(e0));
  await pj.press('.pc-cut input.e1', 'Enter');
  eq([await value(pj, '.pc-cut input.e0'), await value(pj, '.pc-cut input.e1')],
     [s0.toFixed(2), e0.toFixed(2)], 'the cursors go where only the reach put sound');
  const used = await saveAndUse(pj, 'the clip from before the caption');
  await clipIsExact(`${TRAY}/${used.name}`, s0, e0,
                    'the card\u2019s clip is the video\u2019s own second ' + s0 + ', out of reach before');
  await cj.close();
}

/* ============================================ k) the add page's transcript editor, by ear */
console.log('k) the transcript edited before the video is added, a tenth of a second at a time');
{
  const {context: ck, page: pk} = await newPage(browser);
  await pk.goto(`${BASE}/youtube/add/`);
  // the body opens once both questions are answered
  await pk.click('.path[data-src="yt"]');
  await pk.click('.path[data-by="llm"]');
  await pk.waitForSelector('#transcript', {state: 'visible'});
  await pk.fill('#url', `https://www.youtube.com/watch?v=${YT}`);
  await pk.selectOption('#lang', 'it');
  await pk.fill('#transcript', '0:10\nPrima frase\n0:14\nSeconda frase\n0:20\nTerza frase\n');
  await pk.click('#subedit');
  await pk.waitForSelector('.se-row');
  eq(await pk.$$eval('.se-row', rs => rs.map(r => [r.querySelector('.se-at').value, r.querySelector('.se-text').value])),
     [['0:10', 'Prima frase'], ['0:14', 'Seconda frase'], ['0:20', 'Terza frase']],
     'the pasted panel opens as its captions');
  assert(await pk.locator('.se-yt iframe').count() === 1, 'the video itself is in the editor');
  eq(await pk.$$eval('.se-row', rs => rs[0].querySelectorAll('.se-when button').length), 6,
     'each caption carries the six steps, three on either side of its time');
  eq(await pk.locator('button[data-a="ear"]').count(), 0, 'and nothing records anything here');
  // The two roads out of a bad transcript.  "tidy up" is there for every
  // language and works once that language's dictionary is installed, so what
  // the button shows must be what the server says about this machine; the
  // prompt needs nothing installed and is always there.
  const says = await (await pk.request.post(`${BASE}/youtube/api/transcript`,
    {data: {transcript: '0:01\nCiao a tutti\n', lang: 'it'}})).json();
  eq(await pk.locator('.se-btn:has-text("tidy up")').isVisible(), !!says.can_tidy,
     `"tidy up" is offered exactly where the dictionary is (can_tidy ${says.can_tidy})`);
  eq(await pk.locator('.se-btn:has-text("or with an LLM")').isVisible(), true,
     'and the prompt is offered whatever is installed');

  // a tenth at a time: the step the panel could not hold before
  const row = pk.locator('.se-row').first();
  await row.locator('button[data-d="-0.1"]').click();
  await row.locator('button[data-d="-0.1"]').click();
  eq(await row.locator('.se-at').inputValue(), '0:09.8', 'two tenths earlier, and the box says so');
  eq(await pk.textContent('.se-box .se-head .se-stat'), 'caption 1 at 0:09.8', 'and the editor says which');
  await row.locator('button[data-d="0.5"]').click();
  await row.locator('button[data-d="1"]').click();
  eq(await row.locator('.se-at').inputValue(), '0:11.3', 'a half and a second later');
  // a time typed with a fraction is read, and one that is whole stays whole
  await pk.locator('.se-row').nth(1).locator('.se-at').fill('0:14.25');
  await pk.locator('.se-row').nth(1).locator('.se-at').press('Enter');
  eq(await pk.$$eval('.se-row .se-at', is => is.map(i => i.value)), ['0:11.3', '0:14.25', '0:20'],
     'the panel holds fractions and whole seconds side by side');

  // the panel goes back into the box, and nothing else on the page moved
  await pk.click('.se-foot .se-use');
  await pk.waitForSelector('.se-box', {state: 'detached'});
  eq(await pk.inputValue('#transcript'),
     '0:11.3\nPrima frase\n0:14.25\nSeconda frase\n0:20\nTerza frase\n',
     'the box holds the edited panel, fractions and all, in the one format everything downstream reads');
  eq(await pk.textContent('#sestat'), 'the transcript was edited', 'and the page says so');

  // and the road on from there still works, from the panel as it now is
  await pk.click('#prepare');
  await until(async () => (await pk.textContent('#pinfo')).includes('captions'), 'the prompt is prepared', 20000);
  const said = await pk.textContent('#pinfo');
  assert(/3 captions/.test(said), 'the prompt is built from the edited panel: ' + said);
  await ck.close();
}

/* ============================ l) the timings sheet draws a YouTube video's sound, from the tab */
console.log('l) "draw the sound": the tab is recorded while the video plays, and the shape is kept');
const wavePath = (id = YT) => `${VIDEOS}/italian/${id}/waveform.json`;
let realWave = null;      // the numbers the first real recording posted, for section m
// the timings sheet, opened; a press can land before the captions have
// loaded and be refused, so it is pressed until the sheet is up
async function openTimings(page) {
  await page.waitForSelector('.seg .fa .w');
  for (let i = 0; i < 30; i++) {
    await page.click('#captimes');
    try { await page.waitForSelector('.tl-root', {timeout: 1000}); return; } catch (_) {}
  }
  throw Error('FAIL: the timings sheet never opened');
}
const tlStat = page => page.evaluate(() => {
  const s = document.querySelector('.tl-stat');
  return s ? {text: s.textContent, bad: s.classList.contains('tl-bad')} : null;
});
// the sheet's last word on a recording: drawn, or refused
const tlSettled = (page, what, ms = 90000) => until(async () => {
  const s = await tlStat(page);
  return s && (s.text === 'the sound is drawn' || s.bad) ? s : null;
}, what, ms);
// the waveforms this section posts, as the page sends them
function watchPosts(page) {
  const posts = [];
  page.on('request', r => {
    if (r.method() === 'POST' && new URL(r.url()).pathname === '/youtube/api/waveform') posts.push(JSON.parse(r.postData()));
  });
  return posts;
}
// A number is kept to three decimals, 0 to 1, and one of them is 1
const threeDecimals = peaks => peaks.every(v => typeof v === 'number' && v >= 0 && v <= 1 && Math.abs(v * 1000 - Math.round(v * 1000)) < 1e-6);
const sha256 = async s => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)))]
  .map(b => b.toString(16).padStart(2, '0')).join('');
{
  // l0) THE BASELINE, real Chrome, real tones: what the recorder posts
  const WAVE_OUT = Deno.env.get('YT_WAVE_OUT') || '';
  const {context: c0, page: p0} = await newPage(browser);
  const posts = watchPosts(p0);
  await openVideo(p0);
  // the person's own speed, which the recording must give back
  await p0.evaluate(() => __fakeYT[0].setPlaybackRate(1.25));
  await until(async () => (await childState(p0)).rate === 1.25, 'the speed is set');
  await openTimings(p0);
  eq(await p0.evaluate(() => { const b = document.querySelector('[data-x="wave"]'); return b && [b.hidden, b.disabled]; }), [false, false],
     'the sheet offers "draw the sound", live: this Chrome can record a tab and there is no picture yet');
  await p0.click('[data-x="wave"]');
  assert(/sharing this tab|listening/.test((await tlStat(p0)).text), 'the sheet says it is at work: ' + (await tlStat(p0)).text);
  const done0 = await tlSettled(p0, 'the sound is drawn (real time: it takes as long as the video does)');
  assert(!done0.bad && done0.text === 'the sound is drawn', 'the sheet says the sound is drawn: ' + done0.text);
  eq(posts.length, 1, 'one waveform was posted');
  const w0 = posts[0], dur0 = await p0.evaluate(() => __fakeYT[0].getDuration());
  eq([w0.video, w0.rate, w0.peaks.length], [YT, 20, Math.ceil(dur0 * 20) + 1],
     `it is this video's, at 20 numbers a second, one for every 50 ms of its ${dur0} s`);
  assert(threeDecimals(w0.peaks) && Math.max(...w0.peaks) === 1, 'each number is between 0 and 1 to three decimals, and the loudest is 1');
  // second k of the tones is a tone over [k, k + .5): the middle of that half
  // second is tall and the middle of the silence after it is flat
  const seen0 = [];
  for (const k of [2, 9, 17, 26, 34, 40]) {
    const loud = w0.peaks.slice(k * 20 + 3, k * 20 + 8), quiet = w0.peaks.slice(k * 20 + 13, k * 20 + 18);
    seen0.push(`${k}s tone ${JSON.stringify(loud)} silence ${JSON.stringify(quiet)}`);
    assert(Math.min(...loud) > 0.5 && Math.max(...quiet) < 0.1, `second ${k}: tall where its tone is (${Math.min(...loud)}+), flat in the silence after it (${Math.max(...quiet)} at most)`);
  }
  console.log('     raw: ' + seen0.join('\n          '));
  console.log('     raw: posted ' + w0.peaks.length + ' numbers, sha256 ' + await sha256(JSON.stringify(w0)));
  realWave = w0.peaks;
  if (WAVE_OUT) await Deno.writeTextFile(WAVE_OUT, JSON.stringify(w0));
  eq(await p0.evaluate(() => [__asked.map(o => [!!o.audio, o.preferCurrentTab, o.video]), __toSpeakers, __gum]), [[[true, true, true]], 0, 0],
     'Chrome was asked once, for this tab with its sound; nothing was sent to the speakers; the microphone was never asked');
  const kept0 = await Deno.readTextFile(wavePath());
  assert(kept0.startsWith('{"rate": 20.0, "peaks": [') && JSON.stringify((JSON.parse(kept0)).peaks) === JSON.stringify(w0.peaks),
         'the file beside the video holds exactly what was posted, in the canonical shape: ' + kept0.slice(0, 40));
  const after0 = await childState(p0);
  assert(after0.paused && after0.rate === 1.25, 'the video is paused and its speed is given back: ' + JSON.stringify(after0));
  eq(await p0.evaluate(() => __streams.map(s => s.getTracks().map(t => t.kind + ':' + t.readyState).sort().join())), ['audio:live,video:live'],
     'the share is left live, as the frame capture and the cut editor find it');
  await p0.waitForSelector('.tl-strip.tl-drawn');
  await p0.keyboard.press('Escape');
  await p0.waitForSelector('.tl-root', {state: 'detached'});
  await openTimings(p0);
  eq(await p0.evaluate(() => !document.querySelector('[data-x="wave"]')), true,
     'the sheet drew it, and on the next opening does not offer to draw what is drawn');
  await c0.close();
  await Deno.remove(wavePath());
}

// l1) THE BASELINE, EXACT.  A real recording's numbers vary with the timing
// of every tick, so this plays the ticks itself: the page's real code, its
// real share and audio graph, and the 25 ms tick turned by the test (__virt),
// with the loudness of every tick and the player's clock made up here.  What
// the recorder must post is then a function of those two lists alone, written
// out below from the spec: the number filed under round(t * 20), the loudest
// of every hearing, the whole thing divided by its loudest, three decimals;
// it ends at 0.3 s before the end or after 400 ticks of a stopped clock; a
// reading that is not a time is skipped.  The old code's output is compared
// to it number for number, and so must the refactored code's be.
const GOLD_TICKS = 2100;
const goldLevel = k => Math.fround(k % 97 === 0 ? 0 : 0.02 + 0.95 * Math.abs(Math.sin(k * 0.137)) * (0.4 + 0.6 * Math.abs(Math.cos(k * 0.011))));
function goldRun(kind) {
  const levels = [], clocks = [];
  let pos = 0;
  for (let k = 0; k < GOLD_TICKS; k++) {
    levels.push(kind === 'silent' ? 0 : goldLevel(k));
    if (kind === 'full' && k === 900) clocks.push(null);          // a reading that is not a number
    else if (kind === 'full' && k === 901) clocks.push('inf');    // nor is this
    else clocks.push(pos);
    if (kind === 'frozen') { if (k < 200) pos += 0.025; }         // stops at 4.975 s, for good
    else {
      if (!(k >= 400 && k < 480)) pos += 0.025;                   // a stall of two seconds from tick 400 (10 s)
      if (k === 1200) pos -= 0.5;                                 // a seek back of half a second
    }
  }
  return {levels, clocks};
}
function waveOracle({levels, clocks}, dur) {
  const n = Math.ceil(dur * 20) + 1, peaks = new Array(n).fill(0), said = [];
  let stalled = 0, last = -1, ticks = 0;
  for (let k = 0; k < levels.length; k++) {
    ticks = k + 1;
    const t = clocks[k] === null ? NaN : clocks[k] === 'inf' ? Infinity : clocks[k];
    if (!isFinite(t)) continue;
    const slot = Math.round(t * 20);
    if (slot >= 0 && slot < n && levels[k] > peaks[slot]) peaks[slot] = levels[k];
    if (Math.abs(t - last) < 0.01) stalled++; else stalled = 0;
    last = t;
    if (slot % 20 === 0) {
      const s = 'listening… ' + Math.round(Math.max(0, Math.min(1, t / dur)) * 100) + '%';
      if (said[said.length - 1] !== s) said.push(s);
    }
    if (t >= dur - 0.3 || stalled > 400) break;
  }
  const top = Math.max(...peaks);
  return {ticks, said, top, peaks: top ? peaks.map(p => Math.round(p / top * 1000) / 1000) : null};
}
// A page whose recorder is played by the test: the share is granted, the
// recorder is asked, and its tick waits for the test
async function goldPage(kind, {rate = 1.5} = {}) {
  const {context, page} = await newPage(browser);
  const posts = watchPosts(page);
  await openVideo(page);
  await page.evaluate(r => __fakeYT[0].setPlaybackRate(r), rate);
  await until(async () => (await childState(page)).rate === rate, 'the speed is set');
  await openTimings(page);
  const g = goldRun(kind), dur = await page.evaluate(() => __fakeYT[0].getDuration());
  await page.evaluate(({levels, clocks}) => {
    const v = window.__virt;
    v.levels = levels;
    v.clocks = clocks.map(c => c === null ? NaN : c === 'inf' ? Infinity : c);
    v.on = true;
    __fakeYT[0].getCurrentTime = () => v.clocks[v.k];
  }, g);
  await page.click('[data-x="wave"]');
  await until(() => page.evaluate(() => __virt.timers.length === 1), 'the recorder is listening (its tick is held)', 30000);
  return {context, page, posts, g, dur, oracle: waveOracle(g, dur)};
}
{
  console.log('   the numbers it posts, tick by tick, against the spec (a stall, a seek back, readings that are not times)');
  const {context, page, posts, g, dur, oracle} = await goldPage('full');
  assert(oracle.top > 0 && oracle.ticks > 1700 && oracle.ticks < GOLD_TICKS, `the made-up recording is played to its end: ${oracle.ticks} ticks, loudest ${oracle.top}`);
  const r = await page.evaluate(() => __virt.run(2100));
  eq(r.ticks, oracle.ticks, 'it ended on the same tick as the spec ends it (0.3 s before the end)');
  eq(r.said, oracle.said, `the sheet's percentages went ${oracle.said.length} times, as the spec says (whole percents of the clock's place in the video)`);
  const done = await tlSettled(page, 'the drawn sound is kept', 30000);
  assert(!done.bad, 'the sheet says: ' + done.text);
  eq(posts.length, 1, 'one waveform was posted');
  const same = JSON.stringify(posts[0].peaks) === JSON.stringify(oracle.peaks);
  assert(same, 'every one of the ' + oracle.peaks.length + ' numbers posted is the number the spec gives' +
         (same ? '' : ': first difference at ' + oracle.peaks.findIndex((p, i) => p !== posts[0].peaks[i])));
  assert(posts[0].rate === 20 && posts[0].video === YT && posts[0].peaks.length === Math.ceil(dur * 20) + 1, 'at 20 a second, for this video, one number more than the seconds say');
  // THE NUMBERS THE OLD RECORDER POSTED for these made-up ticks, taken when
  // the recorder was still in player.js, as a checksum of the body: the
  // refactor into youtube/lib/tabcapture.js, and the second consumer added
  // to it, must post the very same bytes
  const GOLDEN = '9a0057ddfe4d49d0c0b5b0f5e87dbd57e75fd0b463faabd9b669b48ae7c7beb8';
  const sum = await sha256(JSON.stringify({video: YT, rate: 20, peaks: oracle.peaks}));
  console.log(`     raw: golden posted body sha256 ${sum} (${oracle.peaks.length} numbers, ${oracle.ticks} ticks)`);
  eq(sum, GOLDEN, 'the spec\'s numbers are the numbers the recorder posted before it was moved, byte for byte');
  assert(JSON.stringify(posts[0]) === JSON.stringify({video: YT, rate: 20, peaks: oracle.peaks}), 'and the body posted is exactly that, key order and all');
  const kept = await readJson(wavePath());
  assert(kept.rate === 20 && JSON.stringify(kept.peaks) === JSON.stringify(oracle.peaks), 'and the file on disk holds them');
  const childNow = await childState(page);
  assert(childNow.paused && childNow.rate === 1.5, 'the video is paused, its speed given back: ' + JSON.stringify(childNow));
  eq(await page.evaluate(() => [__asked.length, __gum]), [1, 0], 'one share, and the microphone never asked');
  // THE LISTENER THAT USED TO STAY.  The recorder listened for the share to end
  // and never stopped listening: once the drawing was kept, Chrome's "Stop
  // sharing" ran its stop again -- paused whatever was playing then, and put
  // the video's speed back.  It is taken off at the end of the recording.
  const stale = await page.evaluate(() => {
    const p = __fakeYT[0], calls = [];
    for (const m of ['pauseVideo', 'setPlaybackRate', 'playVideo']) { const f = p[m]; p[m] = (...a) => { calls.push(m); return f.apply(p, a); }; }
    __streams[0].getAudioTracks()[0].dispatchEvent(new Event('ended'));
    return calls;
  });
  eq(stale, [], 'after the recording, the share ending touches the player no more');
  await context.close();
  await Deno.remove(wavePath());
}
{
  console.log('   a clock that stops for good ends the recording after ten seconds of it, and what was heard is kept');
  const {context, page, posts, oracle} = await goldPage('frozen');
  const r = await page.evaluate(() => __virt.run(2100));
  eq(r.ticks, oracle.ticks, `ended by the stalled clock on tick ${oracle.ticks} (the clock stood still for 400 ticks, 10 s), as the spec ends it`);
  assert(oracle.ticks > 590 && oracle.ticks < 620, 'that is 200 ticks of play and a little over 400 of standing still');
  const done = await tlSettled(page, 'the partial sound is kept', 30000);
  assert(!done.bad, 'it ends as a success, not an error: ' + done.text);
  assert(JSON.stringify(posts[0].peaks) === JSON.stringify(oracle.peaks), 'and posts the partial picture, number for number');
  await context.close();
  await Deno.remove(wavePath());
}
{
  console.log('   nothing heard: refused in words, and nothing posted');
  const {context, page, posts} = await goldPage('silent');
  await page.evaluate(() => __virt.run(2100));
  const done = await tlSettled(page, 'the silence is said', 30000);
  eq(done, {text: 'nothing was heard — the tab was shared without its sound, or the video is muted', bad: true}, 'a whole video of silence says so');
  eq(posts.length, 0, 'and nothing was posted');
  eq(await exists(wavePath()), false, 'nor kept');
  await context.close();
}
{
  console.log('   the person stops sharing while it draws');
  const {context, page, posts} = await goldPage('full');
  await page.evaluate(() => __virt.run(300));
  await page.evaluate(() => __streams[0].getAudioTracks()[0].dispatchEvent(new Event('ended')));
  const done = await tlSettled(page, 'the stop is said', 30000);
  eq(done, {text: 'the tab stopped being shared while the sound was being drawn', bad: true}, 'the sheet says the share stopped');
  eq(posts.length, 0, 'and nothing was posted');
  eq(await page.evaluate(() => __virt.timers.length), 0, 'the tick is stopped');
  const after = await childState(page);
  assert(after.paused && after.rate === 1.5, 'the video is paused and its speed given back: ' + JSON.stringify(after));
  await context.close();
}

{
  console.log('   why a tab cannot be recorded: the card kit\'s words, and the module\'s, the same');
  // The card kit says it for the sheets that cut a clip; the module says it for
  // the add page, which never loads the card kit.  In every browser that
  // cannot, they must say the same thing.
  const both = async (init, what) => {
    const {context: cx, page: px} = await newPage(browser, {init});
    await openVideo(px);
    const r = await px.evaluate(() => [ParsehCards.tabProblem(), ParsehTabCapture.problem(), ParsehTabCapture.capability()]);
    await cx.close();
    eq(r[0], r[1], `${what}: the card kit and the module say the same: ${JSON.stringify(r[1])}`);
    eq(r[2], {ok: r[1] === '', why: r[1]}, `${what}: capability() is that, as {ok, why}`);
    return r[1];
  };
  eq(await both(() => {}, 'Chrome'), '', 'this Chrome can record a tab');
  eq(await both(() => { Object.defineProperty(Navigator.prototype, 'userAgentData', {get: () => undefined}); }, 'not Chromium'),
     'only Chrome and Edge, on a computer, can record the sound of a tab', 'Firefox and Safari have no userAgentData');
  eq(await both(() => { Object.defineProperty(window, 'isSecureContext', {get: () => false}); }, 'not https'),
     'recording this tab needs the page opened at the toolbox’s https address, in Chrome or Edge', 'a page that is not https');
  eq(await both(() => { const ua = navigator.userAgentData; Object.defineProperty(Navigator.prototype, 'userAgentData', {get: () => ({brands: ua.brands, mobile: true})}); }, 'a phone'),
     'only Chrome and Edge, on a computer, can record the sound of a tab', 'a phone');
  eq(await both(() => { navigator.mediaDevices.getDisplayMedia = undefined; }, 'no getDisplayMedia'),
     'only Chrome and Edge, on a computer, can record the sound of a tab', 'no way to share a tab');
  eq(await both(() => { delete window.AudioContext; delete window.webkitAudioContext; delete window.MediaStreamTrackProcessor; }, 'no Web Audio'),
     'this browser cannot read the sound of a shared tab', 'nothing to read the sound with');
}
{
  console.log('   cancelled mid-way: everything let go, and a second recording works');
  const {context: cc, page: pc} = await newPage(browser);
  await openVideo(pc);
  await pc.evaluate(() => __fakeYT[0].setPlaybackRate(1.25));
  await until(async () => (await childState(pc)).rate === 1.25, 'the speed is set');
  const before = await pc.evaluate(() => [...__intervals.keys()]);
  const start = keep => pc.evaluate(keep => {
    window.__ended = [];
    window.__rec = ParsehTabCapture.record({player: __fakeYT[0], keepShare: keep, onEnd: r => __ended.push(r)});
    window.__settled = null;
    __rec.promise.then(r => { __settled = ['ok', r.reason]; }, e => { __settled = ['no', e.message]; });
  }, keep);
  const playing = async what => until(async () => { const c = await childState(pc); return !c.paused && c.t > 0.4 && await pc.evaluate(() => __rec.state) === 'listening'; }, what);
  await start(false);
  eq(await pc.evaluate(() => [['sharing', 'listening'].includes(__rec.state), ParsehTabCapture.busy()]), [true, true],
     'asked for the share, and busy');
  await playing('the video plays and the recording listens');
  eq(await pc.evaluate(() => ParsehTabCapture.record({player: __fakeYT[0], onEnd: () => {}}).promise.then(() => 'started', e => e.message)),
     'a recording is already under way in this page', 'a second recording is refused while one is under way');
  await pc.evaluate(() => __rec.cancel());
  const after = await pc.evaluate(() => ({
    state: __rec.state, busy: ParsehTabCapture.busy(), ended: __ended, settled: __settled,
    contexts: __contexts.map(c => [c.sampleRate > 0, c.state]),
    tracks: __streams.map(s => s.getTracks().map(t => t.kind + ':' + t.readyState).sort().join()),
    intervals: [...__intervals.keys()], gum: __gum, asked: __asked.length}));
  eq([after.state, after.busy, after.ended, after.settled], ['done', false, ['cancelled'], ['ok', 'cancelled']],
     'cancelled: done, not busy, ended once with the reason, and the promise kept with it');
  eq(after.contexts, [[true, 'closed']], 'the audio context is closed');
  eq(after.tracks, ['audio:ended,video:ended'], 'every track of the share is stopped');
  eq(after.intervals, before, 'no timer of its own is left running');
  const c1 = await childState(pc);
  assert(c1.paused && c1.rate === 1.25, 'the player is paused and its speed given back: ' + JSON.stringify(c1));
  eq([after.gum, after.asked], [0, 1], 'the microphone was never asked, and Chrome once');
  // and again: no state was left behind, the share is asked for anew
  await start(true);
  await playing('the second recording plays');
  await pc.evaluate(() => __rec.cancel());
  eq(await pc.evaluate(() => [__rec.state, __ended, __settled, ParsehTabCapture.busy(), __asked.length,
                              __streams[1].getTracks().map(t => t.kind + ':' + t.readyState).sort().join(),
                              __contexts.map(c => c.state).join()]),
     ['done', ['cancelled'], ['ok', 'cancelled'], false, 2, 'audio:live,video:live', 'closed,closed'],
     'a second recording works; kept share stays live when asked to, both contexts closed');
  await cc.close();
}

/* ====================== m) one share, two consumers: the shape and the sound of the tab */
console.log('m) the tab recorded once, for the shape AND for the transcript (youtube/lib/tabcapture.js, as the add page uses it)');
// A page that has the module and nothing else of Parseh's -- no player, no card
// kit: what the add page is -- with a YouTube player of the fake's put in it by
// the module's own embed().  `wake` says what the screen's wake lock was asked.
// It is sent by a small server of its own, not made up by the browser's routing:
// a page the test invents has no address, Chrome takes it for a page of the
// internet, and refuses it a frame on this machine (local network access).
const TC_PAGE = `<!doctype html><meta charset="utf-8"><title>tab capture</title>
<div id="box" style="width:320px;height:180px"></div><script src="${BASE}/youtube/lib/tabcapture.js"></script>`;
const P3 = freePort();
Deno.serve({hostname: '127.0.0.1', port: P3, signal: fakeServers.signal, onListen() {}}, req =>
  new URL(req.url).pathname === '/blank.html'
    ? new Response(TC_PAGE, {headers: {'content-type': 'text/html; charset=utf-8'}}) : new Response('404', {status: 404}));
const WAKE = () => {
  window.__wake = {asked: [], released: 0};
  Object.defineProperty(navigator, 'wakeLock', {configurable: true, value: {request: async type => {
    window.__wake.asked.push(type);
    return {release: async () => { window.__wake.released++; }, addEventListener() {}};
  }}});
};
async function tcPage({query = 'src=tones.wav', init = null, embed = true, minLength = 10} = {}) {
  const {context, page} = await newPage(browser, {query, init: init ? [WAKE, init] : [WAKE]});
  await page.goto(`http://127.0.0.1:${P3}/blank.html`);
  if (embed) {
    const bad = await page.evaluate(id => ParsehTabCapture.embed(document.getElementById('box'), id, {})
      .then(p => { window.__p = p; return ''; }, e => e.message), YT);
    if (bad) throw Error('FAIL: the embedded player did not come: ' + bad);
    await until(() => page.evaluate(n => __p.getDuration() > n, minLength), 'the embedded player knows its length');
  }
  return {context, page};
}
// a recording, started in the page; what it reports is collected in __got
const startRec = (page, opts = {}) => page.evaluate(o => {
  window.__got = {chunks: [], marks: [], prog: [], peaks: null, ended: [], result: null, error: null, started: 0};
  window.__rec = ParsehTabCapture.record(Object.assign({
    player: __p, wave: true, pcm: true, keepShare: false,
    onStart: () => { __got.started++; },
    onProgress: (t, d) => __got.prog.push([t, d]),
    onPeaks: (p, r) => { __got.peaks = {peaks: p, rate: r}; },
    onChunk: (pcm, off, sig) => { __got.chunks.push({off, pcm, sig}); },
    onMark: (f, t) => __got.marks.push([f, t]),
    onEnd: r => __got.ended.push(r)
  }, o));
  __rec.promise.then(r => { __got.result = r; }, e => { __got.error = {message: e.message, reason: e.reason}; });
}, opts);
const recOver = (page, what, ms = 90000) => until(() => page.evaluate(() => !!(__got.result || __got.error)), what, ms);
// the sound as the page collected it: 16-bit samples, and where each chunk began
async function collected(page) {
  const r = await page.evaluate(() => {
    const cs = __got.chunks, all = new Int16Array(cs.reduce((a, c) => a + c.pcm.length, 0));
    let at = 0;
    for (const c of cs) { all.set(c.pcm, at); at += c.pcm.length; }
    const bytes = new Uint8Array(all.buffer);
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return {b64: btoa(bin), chunks: cs.map(c => [c.off, c.pcm.length]), marks: __got.marks};
  });
  const pcm = Uint8Array.from(atob(r.b64), c => c.charCodeAt(0));
  const wav = new Uint8Array(44 + pcm.length), v = new DataView(wav.buffer);
  const put = (o, t) => { for (let i = 0; i < t.length; i++) v.setUint8(o + i, t.charCodeAt(i)); };
  put(0, 'RIFF'); v.setUint32(4, 36 + pcm.length, true); put(8, 'WAVE'); put(12, 'fmt '); v.setUint32(16, 16, true);
  v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, 16000, true); v.setUint32(28, 32000, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true); put(36, 'data'); v.setUint32(40, pcm.length, true);
  wav.set(pcm, 44);
  const path = `${TMP}/collected-${Math.random().toString(36).slice(2)}.wav`;
  await Deno.writeFile(path, wav);
  return {path, samples: pcm.length / 2, chunks: r.chunks, marks: r.marks, tones: (await measure(path))};
}
// Where the video was at sample f of the sound, from the marks alone: on from the
// last mark at the speed of the sound -- unless the mark after it says the video
// stood still over that stretch (a stop to buffer)
function videoAt(marks, f) {
  let i = 0;
  for (let j = 0; j < marks.length; j++) { if (marks[j][0] <= f) i = j; else break; }
  const m = marks[i], next = marks[i + 1];
  if (next && f > m[0]) {
    const sound = (next[0] - m[0]) / 16000, video = next[1] - m[1];
    if (sound >= 0.1 && video < 0.5 * sound) return m[1];
  }
  return m[1] + (f - m[0]) / 16000;
}
// each whole tone of the sound, where the marks put it in the video against
// where the video has it: second k of the pattern starts at k.000
function toneErrors(tones, marks) {
  return tones.runs.filter(r => r[1] - r[0] >= 0.4 && r[0] > 0.05).map(r => {
    const k = Math.round((r[2] - 300) / 50);
    return {k, hz: r[2], atStream: r[0], error: videoAt(marks, Math.round(r[0] * 16000)) - k};
  });
}
const median = a => { const b = [...a].sort((x, y) => x - y); return b.length ? b[b.length >> 1] : NaN; };
const shape = peaks => {
  const bad = [];
  for (const k of [2, 9, 17, 26, 34, 40]) {
    const loud = peaks.slice(k * 20 + 3, k * 20 + 8), quiet = peaks.slice(k * 20 + 13, k * 20 + 18);
    if (!(Math.min(...loud) > 0.5 && Math.max(...quiet) < 0.1)) bad.push(k);
  }
  return bad;
};
const gotOf = page => page.evaluate(() => ({error: __got.error, ended: __got.ended, started: __got.started,
  result: __got.result && {reason: __got.result.reason, rate: __got.result.rate, samples: __got.result.samples,
                           reached: __got.result.reached, duration: __got.result.duration,
                           peaks: __got.result.peaks && __got.result.peaks.slice()},
  peaksSaid: __got.peaks && [__got.peaks.rate, __got.peaks.peaks.length], prog: __got.prog}));

{
  console.log('   m1) the whole video, both consumers, one share');
  const {context, page} = await tcPage();
  assert(await page.evaluate(() => [typeof window.ParsehCards, typeof window.ParsehTimeline, typeof window.ParsehTabCapture].join()) === 'undefined,undefined,object',
         'the page has the module and neither the card kit nor the timeline: the module stands alone');
  await startRec(page);
  await recOver(page, 'the whole video is recorded (real time, 42 s)');
  const g = await gotOf(page);
  eq(g.error, null, 'it was recorded without an error');
  eq([g.result.reason, g.ended, g.started], ['ended', ['ended'], 1], 'it ended because the video did: once, and started once');
  eq(await page.evaluate(() => [__asked.length, __gum, __toSpeakers]), [1, 0, 0],
     'Chrome was asked ONCE for both consumers; the microphone was never asked; nothing went to the speakers');
  const ctxs = await page.evaluate(() => __contexts.map(c => [c.sampleRate, c.state]));
  assert(ctxs.length === 2 && ctxs[0][0] >= 44100 && ctxs[1][0] === 16000 && ctxs.every(c => c[1] === 'closed'),
         'two audio contexts: the browser\'s own rate for the shape, 16000 for the sound; both closed: ' + JSON.stringify(ctxs));
  eq(await page.evaluate(() => [__streams.map(s => s.getTracks().map(t => t.readyState).join()), __clones.map(c => c.readyState)]),
     [['ended,ended'], ['ended']], 'every track of the share is stopped, and so is the clone the sound read');
  const c = await collected(page);
  assert(c.chunks[0][0] === 0 && c.chunks.every((x, i) => i === 0 || x[0] === c.chunks[i - 1][0] + c.chunks[i - 1][1]),
         `the ${c.chunks.length} chunks are contiguous: each begins where the last ended, the first at 0`);
  assert(c.chunks.slice(0, -1).every(x => x[1] === 80000) && c.chunks.at(-1)[1] > 0 && c.chunks.at(-1)[1] <= 80000,
         'each is five seconds of 16 kHz but the last, which is what was left: ' + JSON.stringify(c.chunks.map(x => x[1])));
  eq(g.result.samples, c.samples, 'and the result says how many samples there were: ' + c.samples);
  assert(c.samples / 16000 > 42 && c.samples / 16000 < 43.5, `42 s of video is ${(c.samples / 16000).toFixed(3)} s of sound`);
  const tones = c.tones.runs.filter(r => r[1] - r[0] >= 0.4);
  assert(tones.length >= 41 && tones.length <= 42, `${tones.length} tones in the sound: the video's 42`);
  const hz = tones.map(r => Math.abs(r[2] - (300 + 50 * Math.round((r[2] - 300) / 50))));
  assert(Math.max(...hz) <= 25, 'each at its own frequency, 300 Hz + 50 Hz a second, within 25 Hz (16 kHz reached the worklet intact): ' +
         JSON.stringify(tones.slice(0, 6).map(r => r[2])) + '…');
  console.log('     raw: first tones in the sound ' + JSON.stringify(tones.slice(0, 5).map(r => [+r[0].toFixed(3), +r[1].toFixed(3), r[2]])) +
              ', the sound ' + (c.samples / 16000).toFixed(3) + ' s, ' + c.marks.length + ' marks ' + JSON.stringify(c.marks.slice(0, 4)));
  const errs = toneErrors(c.tones, c.marks);
  assert(errs.length >= 40 && errs.every(e => Math.abs(e.error) <= 0.15),
         `the marks put every tone where the video has it, within 150 ms (worst ${Math.max(...errs.map(e => Math.abs(e.error))).toFixed(3)} s, median ${median(errs.map(e => e.error)).toFixed(3)} s over ${errs.length})`);
  assert(c.marks.length >= 1 && c.marks[0][0] >= 0 && c.marks[0][0] < 16000, 'the first mark is made as the sound begins: ' + JSON.stringify(c.marks[0]));
  assert(c.marks.every((m, i) => i === 0 || (m[0] > c.marks[i - 1][0] && m[1] >= c.marks[i - 1][1] - 0.001)), 'the marks are in order, in the sound and in the video');
  eq(g.peaksSaid, [20, 841], 'the shape came too, from the same recording: 20 numbers a second, 841 of them');
  eq(shape(g.result.peaks), [], 'tall where the tones are and flat in the silences, as when the shape is drawn alone');
  assert(g.result.peaks.every(v => v >= 0 && v <= 1) && Math.max(...g.result.peaks) === 1, 'between 0 and 1, the loudest 1');
  assert(shape(realWave).length === 0, '(and the shape drawn alone, for comparison, is that shape)');
  const back = g.prog.findIndex((p, i) => i > 0 && p[0] < g.prog[i - 1][0] - 0.001);
  if (back >= 0) console.log('     raw: the clock read backwards in progress: ' + JSON.stringify(g.prog.slice(Math.max(0, back - 2), back + 3)));
  assert(g.prog.length >= 40 && g.prog.at(-1)[0] >= 40.9 && g.prog.every(p => p[1] === 42) && back < 0,
         `progress is the video's clock over its length, ${g.prog.length} times (twice at every whole second), the last at ${g.prog.at(-1)[0].toFixed(2)} of 42`);
  eq(await page.evaluate(() => [__wake.asked, __wake.released, ParsehTabCapture.busy()]), [['screen'], 1, false],
     'the screen was kept awake while it recorded, and let go; not busy any more');
  await context.close();
}
{
  console.log('   m2) a video that stops to buffer, and one that is muted');
  const {context, page} = await tcPage({query: 'src=short.wav&stall=1'});
  await page.evaluate(() => { __p.mute(); __p.setVolume(40); });
  await until(async () => { const s = await childState(page); return s.muted && near(s.volume, 0.4, 0.01); }, 'the player is muted and turned down');
  await startRec(page, {unmute: true});
  const during = await until(async () => { const s = await childState(page); return !s.muted && s.volume === 1 && !s.paused && s.t > 0.3 ? s : null; },
                             'the muted video is unmuted and turned up while it records');
  assert(during, 'unmuted, at full volume, while it records: ' + JSON.stringify(during));
  await recOver(page, 'the short video is recorded', 40000);
  const g = await gotOf(page);
  eq([g.error, g.result.reason], [null, 'ended'], 'a video that stopped to load ends as any other');
  const after = await childState(page);
  assert(after.muted && near(after.volume, 0.4, 0.01) && after.paused, 'muted again and turned down again, and paused: ' + JSON.stringify(after));
  const c = await collected(page);
  const sound = c.samples / 16000;
  assert(sound > 12.2 && sound < 13.5, `12 s of video and a stop of 0.4 s is ${sound.toFixed(3)} s of sound: the recording is longer than the video by the stop`);
  // a stretch of the marks in which the video stood still while the sound went on
  let still = 0;
  for (let i = 1; i < c.marks.length; i++) {
    const s = (c.marks[i][0] - c.marks[i - 1][0]) / 16000, v = c.marks[i][1] - c.marks[i - 1][1];
    if (s >= 0.1 && v < 0.5 * s) still += s - v;
  }
  assert(still > 0.15 && still < 0.9, `the marks say the video stood still for ${still.toFixed(3)} s while the sound went on (the fake's stop is 0.4 s)`);
  const errs = toneErrors(c.tones, c.marks);
  assert(errs.length >= 8 && errs.every(e => Math.abs(e.error) <= 0.15),
         `and every whole tone is where the video has it, within 150 ms, before the stop and after it (worst ${Math.max(...errs.map(e => Math.abs(e.error))).toFixed(3)} s over ${errs.length}: ${JSON.stringify(errs.map(e => [e.k, +e.error.toFixed(3)]))})`);
  console.log('     raw: marks ' + JSON.stringify(c.marks));
  await context.close();
}
{
  console.log('   m3) a video that says it is playing 0.18 s late');
  const {context, page} = await tcPage({query: 'src=short.wav&late=1'});
  await startRec(page);
  await recOver(page, 'the short video is recorded', 40000);
  const g = await gotOf(page);
  eq([g.error, g.result.reason], [null, 'ended'], 'recorded to its end');
  const c = await collected(page);
  const errs = toneErrors(c.tones, c.marks);
  assert(errs.length >= 8 && errs.every(e => Math.abs(e.error) <= 0.15),
         `every whole tone is where the video has it, within 150 ms (worst ${Math.max(...errs.map(e => Math.abs(e.error))).toFixed(3)} s over ${errs.length})`);
  console.log('     raw: first tone at ' + c.tones.runs[0][0].toFixed(3) + ' s of the sound, marks ' + JSON.stringify(c.marks.slice(0, 6)));
  await context.close();
}
{
  console.log('   m4) no sound in the share: said at once, before anything plays');
  const noSound = () => {
    navigator.mediaDevices.getDisplayMedia = () => {
      const c = document.createElement('canvas');
      c.width = 64; c.height = 36;
      c.getContext('2d').fillRect(0, 0, 64, 36);
      return Promise.resolve(c.captureStream(5));
    };
  };
  const {context, page} = await tcPage({init: noSound});
  await page.evaluate(() => {
    window.__calls = [];
    for (const m of ['playVideo', 'seekTo', 'pauseVideo', 'setPlaybackRate']) { const f = __p[m]; __p[m] = (...a) => { __calls.push(m); return f.apply(__p, a); }; }
  });
  const t0 = Date.now();
  await startRec(page);
  await recOver(page, 'the missing sound is said', 5000);
  const took = Date.now() - t0;
  const g = await gotOf(page);
  eq(g.error, {message: 'the share came without its sound — share this tab again and turn on “Share tab audio”', reason: 'error'},
     'the sentence tells the person to turn on “Share tab audio”');
  assert(took < 3000, `and it says so at once (${took} ms), not after the video`);
  eq(await page.evaluate(() => [__calls, __got.chunks.length, __got.marks.length, __got.ended, __contexts.length, ParsehTabCapture.busy(), __gum]),
     [[], 0, 0, ['error'], 0, false, 0], 'the video was never played, nothing was recorded, no context was made, and not busy');
  eq((await childState(page)).t, 0, 'the video is where it was: at its start');
  await startRec(page, {pcm: false});
  await recOver(page, 'the missing sound is said, for the shape alone too', 5000);
  eq((await gotOf(page)).error, {message: 'the share came without its sound — share this tab again and leave “Also allow tab audio” turned on', reason: 'error'},
     'for the shape alone it is the words it always was');
  await context.close();
}
{
  console.log('   m5) a window or the whole screen is not this tab');
  const window_ = () => {
    const ask = navigator.mediaDevices.getDisplayMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getDisplayMedia = o => ask(o).then(s => {
      const v = s.getVideoTracks()[0], was = v.getSettings.bind(v);
      v.getSettings = () => Object.assign(was(), {displaySurface: 'monitor'});
      return s;
    });
  };
  const {context, page} = await tcPage({init: window_});
  await page.evaluate(() => {
    window.__calls = [];
    for (const m of ['playVideo', 'seekTo']) { const f = __p[m]; __p[m] = (...a) => { __calls.push(m); return f.apply(__p, a); }; }
  });
  await startRec(page);
  await recOver(page, 'the wrong share is refused', 8000);
  eq((await gotOf(page)).error, {message: 'a window or the whole screen was shared, not this tab — share this tab again, with “Share tab audio” turned on', reason: 'error'},
     'a share of the whole screen is refused, in words');
  eq(await page.evaluate(() => [__calls, __streams.map(s => s.getTracks().map(t => t.readyState).join()), __got.chunks.length, ParsehTabCapture.busy()]),
     [[], ['ended,ended'], 0, false], 'nothing played, the share was let go so that the next press asks again, and not busy');
  // for the shape alone nothing has changed: it never looked
  await startRec(page, {pcm: false});
  await until(() => page.evaluate(() => __rec.state === 'listening'), 'the shape alone is not refused for it', 8000);
  await page.evaluate(() => __rec.cancel());
  await context.close();
}
{
  console.log('   m6) a browser that cannot: capability() says why, in the card kit\'s words');
  const said = async (init, what) => {
    const {context, page} = await tcPage({init, embed: false});
    const r = await page.evaluate(async () => {
      const cap = ParsehTabCapture.capability();
      let err = '';
      if (!cap.ok) err = await ParsehTabCapture.record({player: {getDuration: () => 42}, pcm: true}).promise.then(() => '', e => e.message);
      return [cap, ParsehTabCapture.problem(), ParsehTabCapture.capability({pcm: false}), __asked.length, err];
    });
    await context.close();
    eq(r[0], {ok: r[1] === '', why: r[1]}, `${what}: capability() is problem(), as {ok, why}`);
    return r;
  };
  eq((await said(() => {}, 'Chrome'))[0], {ok: true, why: ''}, 'this Chrome can');
  for (const [init, what, sentence] of [
    [() => { Object.defineProperty(Navigator.prototype, 'userAgentData', {get: () => undefined}); }, 'Firefox or Safari',
     'only Chrome and Edge, on a computer, can record the sound of a tab'],
    [() => { Object.defineProperty(window, 'isSecureContext', {get: () => false}); }, 'a page that is not https',
     'recording this tab needs the page opened at the toolbox’s https address, in Chrome or Edge'],
    [() => { const ua = navigator.userAgentData; Object.defineProperty(Navigator.prototype, 'userAgentData', {get: () => ({brands: ua.brands, mobile: true})}); }, 'a phone',
     'only Chrome and Edge, on a computer, can record the sound of a tab'],
    [() => { delete window.AudioWorkletNode; }, 'a browser with no AudioWorklet', 'this browser cannot read the sound of a shared tab']]) {
    const r = await said(init, what);
    eq(r[0], {ok: false, why: sentence}, `${what}: the exact sentence`);
    eq(r[4], sentence, `${what}: record() refuses with it`);
    eq(r[3], 0, `${what}: and never asks Chrome to share anything`);
  }
  const noWorklet = await said(() => { delete window.AudioWorkletNode; }, 'no AudioWorklet');
  eq(noWorklet[2], {ok: true, why: ''}, 'without the worklet the shape alone can still be drawn: capability({pcm: false}) is the card kit\'s test');
}
{
  console.log('   m7) YouTube plays an ad');
  for (const [what, hook] of [
    ['the length changes under the recording', () => { window.__ad = () => { __p.getDuration = () => 15; }; }],
    ['the clock runs backwards', () => { window.__ad = () => { const g = __p.getCurrentTime; __p.getCurrentTime = () => g.call(__p) - 4; }; }]]) {
    const {context, page} = await tcPage({query: 'src=tones.wav'});
    await page.evaluate(hook);
    await startRec(page);
    await until(async () => (await childState(page)).t > 3.3, 'the video plays', 20000);
    await page.evaluate(() => __ad());
    await recOver(page, 'the ad is noticed', 8000);
    const g = await gotOf(page);
    eq(g.error, {message: 'YouTube played an ad, so the recording was stopped — an ad’s sound would end up in the transcript', reason: 'ad'},
       `${what}: the recording stops, in words`);
    eq(await page.evaluate(() => [__got.ended, ParsehTabCapture.busy(), __contexts.map(c => c.state).join(),
                                  __streams.map(s => s.getTracks().map(t => t.readyState).join())]),
       [['ad'], false, 'closed,closed', ['ended,ended']], `${what}: ended once, not busy, both contexts closed, the share let go`);
    const c = await childState(page);
    assert(c.paused, `${what}: and the video is paused`);
    await context.close();
  }
}
{
  console.log('   m8) cancelled mid-way: the sound stops, everything is let go, a second recording works');
  const {context, page} = await tcPage({query: 'src=short.wav'});
  await page.evaluate(() => __p.setPlaybackRate(1.25));
  await until(async () => (await childState(page)).rate === 1.25, 'the speed is set');
  const before = await page.evaluate(() => [...__intervals.keys()]);
  await startRec(page, {pcm: {chunkSeconds: 1}});
  await until(() => page.evaluate(() => __got.chunks.length >= 2 && __got.marks.length >= 1), 'two chunks and a mark have come', 20000);
  eq(await page.evaluate(() => { const e = new Event('beforeunload', {cancelable: true}); window.dispatchEvent(e); return e.defaultPrevented; }), true,
     'while it records, leaving the page is asked about');
  const beforeCancel = await page.evaluate(() => __got.chunks.length);
  await page.evaluate(() => __rec.cancel());
  const g = await page.evaluate(() => ({ended: __got.ended, result: __got.result && __got.result.reason, error: __got.error,
    state: __rec.state, busy: ParsehTabCapture.busy(), aborted: __got.chunks.map(c => c.sig.aborted), n: __got.chunks.length,
    contexts: __contexts.map(c => c.state), tracks: __streams.map(s => s.getTracks().map(t => t.readyState).join()),
    clones: __clones.map(c => c.readyState), intervals: [...__intervals.keys()], wake: [__wake.asked, __wake.released], gum: __gum}));
  eq([g.ended, g.result, g.error, g.state, g.busy], [['cancelled'], 'cancelled', null, 'done', false], 'ended once as cancelled, and not busy');
  eq([g.contexts, g.tracks, g.clones], [['closed', 'closed'], ['ended,ended'], ['ended']], 'both contexts closed, the share and the clone stopped');
  eq(g.intervals, before, 'no timer of its own is left running');
  eq(g.wake, [['screen'], 1], 'the screen\'s wake lock was given back');
  assert(g.aborted.every(x => x === true) && g.n >= beforeCancel, 'what onChunk was sent is told to abort (its signal): ' + JSON.stringify(g.aborted));
  eq(await page.evaluate(() => { const e = new Event('beforeunload', {cancelable: true}); window.dispatchEvent(e); return e.defaultPrevented; }), false,
     'and leaving the page is not asked about any more');
  const after = await childState(page);
  assert(after.paused && after.rate === 1.25, 'the video is paused and its speed given back: ' + JSON.stringify(after));
  await sleep(1500);
  eq(await page.evaluate(() => __got.chunks.length), g.n, 'no chunk arrives after the cancel');
  eq(g.gum, 0, 'the microphone was never asked');
  // and again, to the end
  await startRec(page);
  await recOver(page, 'the second recording ends', 40000);
  const h = await gotOf(page);
  eq([h.error, h.result.reason, h.ended], [null, 'ended', ['ended']], 'the second recording runs to the video\'s end: nothing was left behind');
  eq(await page.evaluate(() => [__asked.length, __contexts.map(c => c.state).join(), __wake.released]), [2, 'closed,closed,closed,closed', 2],
     'Chrome asked once for each, and everything of both is closed');
  await context.close();
}
{
  console.log('   m8b) the other ways it ends: the clock stops for ten seconds; the person stops sharing');
  const {context, page} = await tcPage({query: 'src=short.wav'});
  const before = await page.evaluate(() => [...__intervals.keys()]);
  await startRec(page);
  await until(async () => (await childState(page)).t > 1.2, 'the video plays', 20000);
  await page.evaluate(() => __p.pauseVideo());
  await recOver(page, 'the stopped clock ends the recording', 40000);
  const g = await gotOf(page);
  eq([g.error, g.result.reason, g.ended], [null, 'stalled', ['stalled']], 'a video that stood still for ten seconds ends as stalled, once');
  assert(g.result.reached > 1.2 && g.result.reached < 3 && g.result.samples > 10 * 16000, `having reached ${g.result.reached.toFixed(2)} s of its 12, with ${(g.result.samples / 16000).toFixed(1)} s of sound (the ten seconds of standing still)`);
  eq(await page.evaluate(() => [ParsehTabCapture.busy(), __contexts.map(c => c.state).join(), __streams.map(s => s.getTracks().map(t => t.readyState).join())]),
     [false, 'closed,closed', ['ended,ended']], 'and everything is let go');
  await startRec(page);
  await until(() => page.evaluate(() => __rec.state === 'listening' && __got.marks.length > 0), 'the second recording listens');
  await page.evaluate(() => __streams.at(-1).getAudioTracks()[0].dispatchEvent(new Event('ended')));
  await recOver(page, 'the share ending ends the recording', 8000);
  const h = await gotOf(page);
  eq(h.error, {message: 'the tab stopped being shared while its sound was being recorded', reason: 'share-ended'}, 'the person stopping the share ends it as share-ended, in words');
  eq(await page.evaluate(() => [__got.ended, ParsehTabCapture.busy(), __contexts.map(c => c.state).join(), __clones.map(c => c.readyState).join(), [...__intervals.keys()]]),
     [['share-ended'], false, 'closed,closed,closed,closed', 'ended,ended', before],
     'ended once, not busy, all four contexts closed, both clones stopped, no timer left');
  await context.close();
}
{
  console.log('   m8c) a video that ends short of the length its player gave: the recording ends with the video, not ten seconds after');
  // YouTube's length is the video's rounded UP to a whole second, and its clock stops where the video
  // does: driven on 13 real videos, 7 stopped more than 0.3 s short of the length and every one said
  // ENDED as its clock stopped.  The recording sat ten seconds and said the video "stopped moving".
  // ?over=0.6 is that: the player says 12.6 s for the 12 s that play.
  {
    const {context, page} = await tcPage({query: 'src=short.wav&over=0.6'});
    eq(await page.evaluate(() => Math.round(__p.getDuration() * 10) / 10), 12.6, 'the player gives 12.6 s for the 12 s that play');
    await startRec(page);
    await recOver(page, 'the recording ends with the video', 40000);
    const g = await gotOf(page);
    eq([g.error, g.result.reason, g.ended, g.started], [null, 'ended', ['ended'], 1],
       'it ended because the video did, and not as a stall: once, and started once');
    assert(g.result.reached > 11.9 && g.result.reached < 12.05 && near(g.result.duration, 12.6, 0.01),
           `having reached ${g.result.reached.toFixed(3)} s, the video's 12 (the player's 12.6 is not a place the clock goes to)`);
    const c = await collected(page);
    assert(c.samples / 16000 > 12 && c.samples / 16000 < 14,
           `and it did not wait: 12 s of video is ${(c.samples / 16000).toFixed(2)} s of sound (ten seconds of waiting would be 22)`);
    const errs = toneErrors(c.tones, c.marks);
    assert(errs.length >= 10 && errs.at(-1).k === 11 && errs.every(e => Math.abs(e.error) <= 0.15),
           `the video's last whole tone (11 s, 850 Hz) is in the sound, where the marks put it: ${JSON.stringify(errs.slice(-2))}`);
    assert(g.result.peaks.length >= 253 && Math.min(...g.result.peaks.slice(223, 228)) > 0.5, 'and in the shape');
    eq(await page.evaluate(() => [ParsehTabCapture.busy(), __contexts.map(c => c.state).join(), __streams.map(s => s.getTracks().map(t => t.readyState).join()),
                                  __clones.map(c => c.readyState).join()]),
       [false, 'closed,closed', ['ended,ended'], 'ended'], 'and everything is let go: not busy, both contexts closed, the share and the clone stopped');
    await context.close();
  }
  {
    // the shape alone (the timings sheet's "draw the sound"), and how long after the player said "ended" the recording said so, measured in the page
    const {context, page} = await tcPage({query: 'src=short.wav&over=0.6'});
    await startRec(page, {pcm: false});
    await page.evaluate(() => {
      window.__lag = {ended: 0, done: 0};
      const over = () => { if (!__lag.done) __lag.done = performance.now(); };
      __rec.promise.then(over, over);
      (function watch() {
        if (!__lag.ended && __p.getPlayerState() === 0) __lag.ended = performance.now();
        if (!__lag.ended || !__lag.done) requestAnimationFrame(watch);
      })();
    });
    await recOver(page, 'the shape is drawn to the video\'s end', 40000);
    await until(() => page.evaluate(() => __lag.ended > 0 && __lag.done > 0), 'the page has seen both the player and the recording say it', 5000);
    const g = await gotOf(page);
    const lag = await page.evaluate(() => __lag);
    eq([g.error, g.result.reason, g.ended], [null, 'ended', ['ended']], 'the shape alone ends as the video does, once');
    // the player's "ended" is seen on a frame, the recording's on its own 25 ms tick: either may be seen first, by a frame
    assert(lag.done - lag.ended > -1000 && lag.done - lag.ended < 2000,
           `within two seconds of the player saying it had ended (${Math.round(lag.done - lag.ended)} ms; a stall is ten seconds): ${JSON.stringify(lag)}`);
    assert(g.result.reached > 11.9 && g.result.reached < 12.05 && Math.min(...g.result.peaks.slice(223, 228)) > 0.5,
           `with the last tone in it (reached ${g.result.reached.toFixed(3)} s)`);
    await context.close();
  }
  {
    // a video that has not ended is not ended by this: paused three seconds from its end, it stalls, and says so
    const {context, page} = await tcPage({query: 'src=short.wav&over=0.6'});
    await startRec(page);
    await until(async () => (await childState(page)).t > 9, 'the video plays to nine seconds', 30000);
    await page.evaluate(() => __p.pauseVideo());
    await recOver(page, 'the stopped clock ends the recording', 40000);
    const g = await gotOf(page);
    eq([g.error, g.result.reason, g.ended], [null, 'stalled', ['stalled']],
       'a video paused three seconds from its end stalls: it was not played to its end, and its last seconds are not written off as an end');
    assert(g.result.reached > 9 && g.result.reached < 10.5 && g.result.samples > 18 * 16000,
           `having reached ${g.result.reached.toFixed(2)} s of the 12, with ${(g.result.samples / 16000).toFixed(1)} s of sound (the ten seconds of standing still)`);
    await context.close();
  }
  {
    // a player that cannot say what it is doing has only its clock: near the end, ten seconds still is the end
    const {context, page} = await tcPage({query: 'src=short.wav&over=0.6'});
    await page.evaluate(() => { __p.getPlayerState = undefined; });
    await startRec(page);
    await recOver(page, 'ten seconds of a stopped clock near the end end the recording', 60000);
    const g = await gotOf(page);
    eq([g.error, g.result.reason, g.ended], [null, 'ended', ['ended']],
       'a player with no state: a clock that stood still for ten seconds within five of the length is the end of the video');
    assert(g.result.reached > 11.9 && g.result.reached < 12.05 && g.result.samples / 16000 > 21.5 && g.result.samples / 16000 < 27,
           `having reached ${g.result.reached.toFixed(3)} s, with ${(g.result.samples / 16000).toFixed(1)} s of sound (the ten seconds of standing still, and the tail)`);
    await context.close();
  }
  {
    // the "ended" a player still says as a play begins, of the play before, is not this play's end: nothing is
    // done with the word until the video has played for a second.  (A real YouTube was driven and did not say
    // it, so this is a player as it might be, not as seen.)
    const {context, page} = await tcPage({query: 'src=tiny.wav&over=0.6&ghost=0.5', minLength: 1});
    await startRec(page);
    await recOver(page, 'the short video is recorded', 30000);
    const g = await gotOf(page);
    eq([g.error, g.result.reason, g.ended], [null, 'ended', ['ended']], 'the video ends as it does');
    assert(g.result.reached > 2.9 && g.result.reached < 3.05 && g.result.samples / 16000 > 3 && g.result.samples / 16000 < 5,
           `at its own end, not at once: reached ${g.result.reached.toFixed(3)} s of the 3, with ${(g.result.samples / 16000).toFixed(2)} s of sound`);
    await context.close();
  }
}
{
  console.log('   m9) an hour of sound through the pipeline: nothing piles up');
  const {context, page} = await tcPage({embed: false});
  const r = await page.evaluate(async () => {
    // 3600 s of 16 kHz sound in the worklet's quarter-second blocks, handed
    // over as fast as the page can, to a send that takes a moment each time
    const CHUNK = 80000, BLOCK = 4000, BLOCKS = 3600 * 4;
    let sent = 0, next = 0, gaps = 0, most = 0, aborted = 0, failed = null;
    const ctl = new AbortController();
    const line = ParsehTabCapture._pipeline(CHUNK, (pcm, off) => {
      if (off !== next) gaps++;
      next = off + pcm.length; sent += pcm.length;
      return new Promise(ok => setTimeout(ok, 0));
    }, ctl.signal, e => { failed = e.message; });
    for (let i = 0; i < BLOCKS; i++) {
      line.push(new Int16Array(BLOCK));
      most = Math.max(most, line.held() + line.queued());
      if (i % 20 === 19) await new Promise(ok => setTimeout(ok, 2));   // a chunk's worth, and the send gets its turn
    }
    await line.end();
    const easy = {sent, gaps, most, held: line.held(), queued: line.queued(), failed};
    // and a send that never answers: what piles up is held for five minutes of
    // sound and no more, and then the recording gives up, in words
    let stuck = null, stuckMost = 0, said = null;
    const jam = ParsehTabCapture._pipeline(CHUNK, () => new Promise(() => {}), ctl.signal, e => { said = e.message; });
    for (let i = 0; i < BLOCKS && !said; i++) { jam.push(new Int16Array(BLOCK)); stuckMost = Math.max(stuckMost, jam.held() + jam.queued()); }
    stuck = {said, most: stuckMost, held: jam.held(), queued: jam.queued()};
    // and a send that fails is the recording's failure, not a silent hole
    let boom = null;
    const bad = ParsehTabCapture._pipeline(CHUNK, () => Promise.reject(new Error('the server said no')), ctl.signal, e => { boom = e.message; });
    bad.push(new Int16Array(CHUNK));
    await new Promise(ok => setTimeout(ok, 50));
    return {easy, stuck, boom};
  });
  eq([r.easy.sent, r.easy.gaps, r.easy.failed], [3600 * 16000, 0, null], 'an hour of sound went through, in order, with no gap and no failure');
  assert(r.easy.most <= 2 * 80000 + 4000, `at no moment did more than two chunks' worth wait (${r.easy.most} samples, an hour is 57 600 000)`);
  eq([r.easy.held, r.easy.queued], [0, 0], 'and nothing is held at the end');
  assert(r.stuck.said === 'the sound could not be sent as fast as it was recorded, so the recording was stopped' && r.stuck.most <= 300 * 16000 + 80000 + 4000,
         `a send that never answers is given up on after five minutes of sound (${(r.stuck.most / 16000).toFixed(0)} s held at the most), in words`);
  eq([r.stuck.held, r.stuck.queued], [0, 0], 'and what waited is let go');
  eq(r.boom, 'the server said no', 'a send that fails ends the recording with what it said');
  await context.close();
}
{
  console.log('   m9b) a video whose sound is off: only the end says nothing was heard');
  const {context, page} = await tcPage({query: 'src=short.wav&deaf=1'});
  await startRec(page, {unmute: true});
  await recOver(page, 'the silence is said', 40000);
  const g = await gotOf(page);
  eq(g.error, {message: 'nothing was heard — the tab was shared without its sound, or the video is muted', reason: 'error'},
     'a whole video of silence says so (the share has its sound; the video has none): at the end, not before');
  eq(await page.evaluate(() => [__got.ended, ParsehTabCapture.busy(), __contexts.map(c => c.state).join(), __streams.map(s => s.getTracks().map(t => t.readyState).join())]),
     [['error'], false, 'closed,closed', ['ended,ended']], 'and everything is let go');
  await context.close();
}
{
  console.log('   m10) the picture of the share stopped (dropVideo): the sound goes on');
  const {context, page} = await tcPage({query: 'src=short.wav'});
  await startRec(page, {dropVideo: true});
  const during = await until(() => page.evaluate(() => __rec.state === 'listening' ? __streams[0].getTracks().map(t => t.kind + ':' + t.readyState).sort().join() : null),
                             'the recording listens');
  eq(during, 'audio:live,video:ended', 'while it records, the picture is stopped and the sound is live');
  await recOver(page, 'the short video is recorded', 40000);
  const g = await gotOf(page);
  eq([g.error, g.result.reason], [null, 'ended'], 'recorded to the end without the picture');
  const c = await collected(page);
  const tones = c.tones.runs.filter(r => r[1] - r[0] >= 0.4);
  assert(tones.length === 12 && Math.max(...tones.map(r => Math.abs(r[2] - (300 + 50 * Math.round((r[2] - 300) / 50))))) <= 25,
         `all 12 tones are in the sound, at their frequencies: ${tones.length}`);
  const flat = [2, 5, 9].filter(k => !(Math.min(...g.result.peaks.slice(k * 20 + 3, k * 20 + 8)) > 0.5 && Math.max(...g.result.peaks.slice(k * 20 + 13, k * 20 + 18)) < 0.1));
  eq([g.result.peaks.length, flat], [241, []], 'and the shape of the 12 seconds is as with the picture: tall at the tones, flat between');
  const errs = toneErrors(c.tones, c.marks);
  assert(errs.length >= 8 && errs.every(e => Math.abs(e.error) <= 0.15), `and the marks put every tone where the video has it (worst ${Math.max(...errs.map(e => Math.abs(e.error))).toFixed(3)} s)`);
  // kept, the share's picture is not touched: the player's frame capture needs it
  await startRec(page, {dropVideo: true, keepShare: true});
  await until(() => page.evaluate(() => __rec.state === 'listening'), 'the second recording listens');
  eq(await page.evaluate(() => __streams.at(-1).getTracks().map(t => t.kind + ':' + t.readyState).sort().join()), 'audio:live,video:live',
     'a share that is kept keeps its picture: dropVideo is for a share that will be let go');
  await page.evaluate(() => __rec.cancel());
  // and a kept share is what the next recording finds: Chrome is not asked again
  const askedBefore = await page.evaluate(() => __asked.length);
  await startRec(page, {keepShare: true});
  await until(() => page.evaluate(() => __rec.state === 'listening'), 'the third recording listens');
  await page.evaluate(() => __rec.cancel());
  eq(await page.evaluate(() => [__asked.length, __streams.length]), [askedBefore, askedBefore], 'a kept share serves the next recording: Chrome is not asked again');
  await context.close();
}
{
  console.log('   m10b) the YouTube player for the recording: what it says when it cannot come');
  const {context, page} = await tcPage({embed: false});
  const r = await page.evaluate(async () => {
    const out = {};
    for (const code of [2, 5, 100, 101, 150, 7]) {
      window.YT = {Player: function (id, opts) { setTimeout(() => opts.events.onError({data: code}), 5); }};
      let said = null;
      out[code] = await ParsehTabCapture.embed(document.getElementById('box'), 'kL9mN1oP3qR', {onError: (c, w) => { said = [c, w]; }})
        .then(() => 'ready', e => [e.message, e.code, said]);
    }
    window.YT = {Player: function () {}};
    out.never = await ParsehTabCapture.embed(document.getElementById('box'), 'kL9mN1oP3qR', {timeout: 300}).then(() => 'ready', e => e.message);
    const took = async (length) => {
      window.YT = {Player: function (id, opts) { this.getDuration = () => length; setTimeout(() => opts.events.onReady({}), 5); }};
      const t0 = performance.now();
      const p = await ParsehTabCapture.embed(document.getElementById('box'), 'kL9mN1oP3qR', {lengthWait: 400});
      return [typeof p.getDuration, Math.round(performance.now() - t0)];
    };
    out.knowing = await took(42);
    out.notknowing = await took(0);
    return out;
  });
  const words = {2: 'YouTube does not know this address', 5: 'YouTube will not play this video in this browser',
    100: 'this video is gone from YouTube — it was taken down, or it was made private',
    101: 'the owner of this video does not allow it to be played outside YouTube',
    150: 'the owner of this video does not allow it to be played outside YouTube', 7: 'YouTube would not play this video (error 7)'};
  for (const code of [2, 5, 100, 101, 150, 7])
    eq(r[code], [words[code], code, [code, words[code]]], `YouTube's error ${code}: the promise says it in words, and so does onError`);
  eq(r.never, 'YouTube’s player did not start', 'a player that never says it is ready is given up on, in words');
  assert(r.knowing[0] === 'function' && r.knowing[1] < 300, `a player that knows the video's length is ready at once (${r.knowing[1]} ms)`);
  assert(r.notknowing[0] === 'function' && r.notknowing[1] >= 380 && r.notknowing[1] < 1500, `one that does not say it is waited for, for a moment and no longer (${r.notknowing[1]} ms)`);
  // the API script that cannot be fetched
  const {context: c2, page: p2} = await tcPage({embed: false});
  await c2.route('https://www.youtube.com/iframe_api', route => route.abort());
  eq(await p2.evaluate(() => ParsehTabCapture.embed(document.getElementById('box'), 'kL9mN1oP3qR', {}).then(() => 'ready', e => e.message)),
     'YouTube’s player could not be fetched — Parseh itself is answering, so it is YouTube this computer cannot reach',
     'YouTube\'s script that cannot be fetched is said to be YouTube\'s, not Parseh\'s');
  await c2.close();
  // ...and once the network is back the next try gets a player: the script that failed is not left
  // in the page to stop every later try adding its own (it waited the whole time, then said "did not start")
  const {context: c3, page: p3} = await tcPage({embed: false});
  let fetches = 0;
  await c3.route('https://www.youtube.com/iframe_api', route => fetches++ === 0 ? route.abort() : route.fallback());
  const again = await p3.evaluate(async () => {
    const first = await ParsehTabCapture.embed(document.getElementById('box'), 'kL9mN1oP3qR', {})
      .then(() => 'ready', e => e.message);
    const t0 = performance.now();
    const second = await ParsehTabCapture.embed(document.getElementById('box'), 'kL9mN1oP3qR', {timeout: 8000})
      .then(p => typeof p.getDuration, e => e.message);
    return {first, second, took: Math.round(performance.now() - t0),
            tags: document.querySelectorAll('script[data-tc-yt]').length};
  });
  eq(again.first, 'YouTube’s player could not be fetched — Parseh itself is answering, so it is YouTube this computer cannot reach',
     'the first try, with the network away, says it could not fetch');
  eq([again.second, again.tags, fetches], ['function', 1, 2],
     'and the second, with it back, fetches the script again and gets a player, not "did not start" after the whole wait');
  assert(again.took < 7000, `at once, and not after its timeout (${again.took} ms)`);
  await c3.close();
  await context.close();
}
{
  console.log('   m10c) a video that never starts is said not to have started, and nothing of the tab is kept');
  // playVideo ignored -- an age or consent screen, a slow start, autoplay refused in the frame: the
  // clock stays at 0 for ten seconds.  It was "nothing was heard — shared without its sound, or the
  // video is muted" (the share and the mute were fine), and with a sound in the tab it was a success
  for (const loud of [false, true]) {
    const {context, page} = await tcPage({query: 'src=short.wav'});
    await page.evaluate(() => { __p.playVideo = function () {}; });
    if (loud) await page.evaluate(src => { window.__beep = new Audio(src); window.__beep.loop = true; return window.__beep.play(); }, CHILD + '/tones.wav');
    await startRec(page);
    await recOver(page, 'the clock that never moves ends the recording', 40000);
    const g = await gotOf(page);
    eq([g.result, g.error, g.ended, g.peaksSaid],
       [null, {message: 'the video did not start playing — its clock never moved. Check that it plays in the player (it may be unavailable, or slow to start), then try again', reason: 'error'}, ['error'], null],
       `${loud ? 'with a sound in the tab' : 'in silence'}: said in words, no recording is handed on and no waveform is posted`);
    eq(await page.evaluate(() => [ParsehTabCapture.busy(), __contexts.map(c => c.state).filter(s => s !== 'closed').length]),
       [false, 0], 'and the recording is let go');
    await context.close();
  }
}
{
  console.log('   m11) the pages the worklet is built in set no policy against it');
  for (const path of ['/youtube/add/', `/youtube/v/${YT}/`])
    eq((await fetch(BASE + path)).headers.get('content-security-policy'), null, `${path} sends no Content-Security-Policy: a Blob URL worklet is allowed`);
}

/* ================================================================ n) the add page's speech to text, for a YouTube video */
console.log('n) the add page: a YouTube video recorded through the tab, and transcribed on this computer');
{
  const TMPAUDIO = STTF + '/stt/tmp';
  const HOLD = `${VIDEOS}/.waveforms`;
  const NID = 'zA1bC2dE3fG';
  const setSttState = patch => Deno.writeTextFile(STTF + '/state.json', JSON.stringify(Object.assign(
    {runtime: true, models: ['large-v3-turbo', 'large-v3'], cuda: {ready: false, name: '', why: ''}, no_lang: [], busy: false}, patch)));
  const setSttFake = cfg => Deno.writeTextFile(STTF + '/fake.json', JSON.stringify(cfg));
  const ITALIAN = [[0.0, 2.0, ' Buongiorno a tutti'], [2.5, 4.5, ' oggi andiamo al mercato'], [6.0, 8.0, ' compriamo la frutta']];
  const PERSIAN = [[0.0, 2.0, ' سلام دنیا'], [2.5, 4.5, ' امروز به بازار می‌رویم'], [6.0, 8.0, ' میوه می‌خریم']];
  await setSttState({});
  await setSttFake({segments: ITALIAN});
  const shotN = async (page, name) => {
    const dir = Deno.env.get('YOUTUBE_CAPTURE_SHOTS');
    if (!dir) return;
    await Deno.mkdir(dir, {recursive: true});
    await page.screenshot({path: `${dir}/${name}.png`, fullPage: true});
  };
  const ph = page => page.evaluate(() => document.getElementById('stt').getAttribute('data-state'));
  const inPh = (page, want, what, ms = 30000) => until(async () => (await ph(page)) === want, what, ms);
  // refusals the page is MEANT to be given are not errors of the page: the hook that
  // counts every 4xx of the job's routes is told which of them it may forget
  const forgive = (before, re, what) => {
    const got = errors.splice(before);
    assert(got.every(e => re.test(e)), `${what}: only refusals that were meant (${JSON.stringify(got)})`);
    return got.length;
  };
  // The page goes to the video's own page on the answer of /api/empty, and Playwright cannot read the body
  // of a response of a page it has left (Network.getResponseBody: "No resource with given identifier
  // found"): reading it after the click, or chained onto waitForResponse, is a race the page wins whenever
  // it navigates first.  So the test answers for the page: it fetches the door's answer itself, keeps its
  // body, and hands the same answer on.  Set before the click; `.body` is a promise of the door's body.
  async function watchEmpty(page) {
    let kept, lost;
    const body = new Promise((ok, bad) => { kept = ok; lost = bad; });
    body.catch(() => {});
    const timer = setTimeout(() => lost(Error('FAIL: the door /api/empty was never asked, 40 s after it was watched (the page is at ' + page.url() + ')')), 40000);
    body.then(() => clearTimeout(timer), () => clearTimeout(timer));
    await page.route(/\/api\/empty$/, async route => {
      try {
        const r = await route.fetch();
        kept(await r.json());
        await route.fulfill({response: r});
      } catch (e) { lost(e); }
    });
    return {body};       // (not the promise itself: an async function would wait for it before returning)
  }
  const fakeLog = () => Deno.readTextFile(STTF + '/fake.log').then(t => t.split('\n').filter(Boolean).map(l => JSON.parse(l)), () => []);
  const status = (page, job) => page.request.post(`${BASE}/youtube/api/transcribe/status`, {data: {job}}).then(r => r.json());
  // the add page on a YouTube video, with a transcript in the box or not
  async function addPage({lang = 'it', width = 1280, init = null, box = '', id = NID, query = 'src=short.wav'} = {}) {
    const {context, page} = await newPage(browser, {width, query, init});
    page.calls = [];
    page.hosts = [];
    page.dialogs = [];
    page.on('request', r => {
      const u = new URL(r.url());
      if (/\/api\/transcribe\//.test(u.pathname)) page.calls.push(u.pathname.replace(/^.*\/transcribe\//, '') + u.search);
      if (u.host !== `127.0.0.1:${port}`) page.hosts.push(u.host);
    });
    page.on('dialog', d => { page.dialogs.push(d.message()); d.accept(); });
    await page.goto(`${BASE}/youtube/add/?src=yt&by=empty`);
    await page.waitForSelector('#transcript', {state: 'visible'});
    await page.fill('#url', `https://www.youtube.com/watch?v=${id}`);
    await page.selectOption('#lang', lang);
    if (box) await page.fill('#transcript', box);
    await page.waitForFunction(() => { const s = document.getElementById('stt'); return s && !s.hidden; });
    return {context, page};
  }
  // press Transcribe, and wait for the video to be loaded in its frame
  async function toReady(page) {
    const start = page.waitForResponse(r => /transcribe\/start$/.test(r.url()));
    await page.click('#stt_go');
    const j = await (await start).json();
    await inPh(page, 'ready', 'the video is loaded and waits for the second press');
    // the player's calls, kept, to see what was done to it
    await page.evaluate(() => {
      window.__calls = [];
      const p = __fakeYT[__fakeYT.length - 1];
      for (const m of ['playVideo', 'pauseVideo', 'seekTo']) { const f = p[m]; p[m] = (...a) => { __calls.push(m); return f.apply(p, a); }; }
    });
    return j;
  }
  // what must fit: the block on the page, or -- while the transcription workspace is open, a modal
  // window over the page that is the whole screen -- the window, which must itself be on the screen
  const fits = page => page.evaluate(() => {
    const w = document.getElementById('stt_workspace'), open = !!(w && w.open);
    const s = open ? w : document.getElementById('stt'), r = s.getBoundingClientRect(), bad = [];
    const vw = document.documentElement.clientWidth;
    if (open && (r.left < -1 || r.right > vw + 1)) bad.push('the workspace sticks out of the screen: ' + Math.round(r.left) + ' to ' + Math.round(r.right) + ' of ' + vw);
    if (document.documentElement.scrollWidth > vw + 1) bad.push('the page scrolls sideways: ' + document.documentElement.scrollWidth + ' > ' + vw);
    for (const e of s.querySelectorAll('*')) {
      if (!e.getClientRects().length || e.closest('[hidden]')) continue;
      const b = e.getBoundingClientRect();
      if (b.width && (b.left < r.left - 1 || b.right > r.right + 1)) bad.push((e.id || e.tagName) + ' sticks out');
    }
    return bad;
  });
  // the workspace's own title bar and "Return to Add Video": inside the window, on the screen, nothing over
  // them, and the window's content begins below them.  (The page's stylesheet knows a bare <header> as the
  // player's fixed bar that slides away when the page is scrolled: it took the workspace's out of the window,
  // over the top of its content, and, on a phone's width, off the screen.)
  const headOk = page => page.evaluate(() => {
    const w = document.getElementById('stt_workspace'), h = w.querySelector('.stt-workspace-head'), bad = [];
    const wr = w.getBoundingClientRect(), hr = h.getBoundingClientRect();
    if (hr.left < wr.left - 1 || hr.right > wr.right + 1 || hr.top < wr.top - 1 || hr.bottom > wr.bottom + 1) bad.push('the title bar is not inside the window');
    if (w.querySelector('.stt-workspace-columns').getBoundingClientRect().top < hr.bottom - 1) bad.push('the content begins under the title bar');
    for (const id of ['stt_workspace_title', 'stt_back']) {
      const r = document.getElementById(id).getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      if (!(r.top >= 0 && r.bottom <= innerHeight && hit && document.getElementById(id).contains(hit))) bad.push(id + ' is not on the screen, or something is over it');
    }
    return bad;
  });
  const captured = page => page.evaluate(() => ({
    tracks: __streams.map(s => s.getTracks().map(t => t.readyState)),
    contexts: __contexts.map(c => c.state), busy: ParsehTabCapture.busy(), asked: __asked.length,
    frames: document.querySelectorAll('#stt_frame iframe').length, calls: window.__calls || []}));
  // Since a0.4.3 every result is PENDING: the words are put up for review in the workspace, and the box
  // is written only when the person presses "Use this transcript" (and, if it holds words of their
  // own that the result would replace, asked first: the dialog the page counts in page.dialogs).
  const inReview = (page, what, ms = 90000) => inPh(page, 'review', what, ms);
  async function useIt(page) {
    await page.click('#stt_use');
    await inPh(page, 'idle', '"Use this transcript" ends the review');
  }
  const panelStarts = async (page, lang = 'it') => {
    const r = await (await page.request.post(`${BASE}/youtube/api/transcript`, {data: {transcript: await page.inputValue('#transcript'), lang}})).json();
    return r.captions.map(c => [c.start, c.text]);
  };
  const BOX = '0:01\nCiao a tutti\n0:05\nA presto\n';

  {
    console.log('   n1) the whole road: what is said first, the video loaded, the tab shared on the second press, the words, the video added');
    const {context, page} = await addPage({box: BOX});
    const how = await text(page, '#stt_how');
    for (const w of [/real time/, /from its beginning/, /this tab/, /Share tab audio/, /in front/])
      assert(w.test(how), `before anything is recorded the page says ${w}: ${how}`);
    eq(await page.evaluate(() => [__asked.length, document.querySelectorAll('#stt_frame iframe').length]), [0, 0], 'nothing is shared yet and no video is loaded');
    eq(page.hosts, [], 'and nothing was asked of YouTube, or of anyone, because the page was opened');
    eq(await page.evaluate(() => [document.getElementById('stt_rec').hidden, document.getElementById('stt_go').hidden]), [true, false], 'the one action is Transcribe');
    const started = await toReady(page);
    eq(started.video_id, NID, 'the computer said which video it is (the page did not guess)');
    eq(page.dialogs.length, 1, 'a box with a transcript in it was asked about, once, before anything began');
    const frame = await page.$eval('#stt_frame iframe', f => { const r = f.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), getComputedStyle(f).display, !f.closest('[hidden]')]; });
    assert(frame[0] >= 200 && frame[1] >= 200 && frame[2] !== 'none' && frame[3], `the video is in a frame on screen, ${frame[0]} x ${frame[1]}`);
    eq((await captured(page)).asked, 0, 'the tab is still not shared: the browser asks only in answer to a press');
    const how2 = await text(page, '#stt_how');
    assert(/Start recording/.test(how2) && /Share tab audio/.test(how2) && /in front/.test(how2), 'and the page says what the press will do: ' + how2);
    // The editor would play a second copy of the video: it cannot be reached while this one waits.  Since
    // a0.4.3 the video is loaded in the transcription workspace, a modal window that is the whole screen
    // and cannot be closed until the recording is cancelled or done: the page behind it is inert, so
    // "Edit the transcript…" is under the window and nothing can focus or press it (the sentence that
    // says "finish or cancel that first" is for the layout where the video stays in the page: n1c).
    const behind = await page.evaluate(() => {
      const w = document.getElementById('stt_workspace'), b = document.getElementById('subedit');
      b.scrollIntoView({block: 'center'});
      const r = b.getBoundingClientRect(), top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      b.focus();
      return {open: w.open, modal: w.matches(':modal'), framed: w.contains(document.getElementById('stt_frame')),
              coveredBy: top && w.contains(top) ? 'the workspace' : top && (top.id || top.tagName), focusable: document.activeElement === b};
    });
    eq(behind, {open: true, modal: true, framed: true, coveredBy: 'the workspace', focusable: false},
       'the video waits in the modal workspace: "Edit the transcript…" behind it is covered, and cannot be focused');
    eq(await page.locator('.se-box').count(), 0, 'and no editor is open');
    eq(await headOk(page), [], 'the workspace\'s title bar and "Return to Add Video" are in the window, on the screen, over nothing');
    await shotN(page, 'n1-ready');
    await page.click('#stt_rec');
    eq((await captured(page)).asked, 1, 'the browser was asked to share the tab, in answer to that press');
    await inPh(page, 'recording', 'recording');
    await until(async () => /^Recording \d+:\d\d \/ 0:12…$/.test(await text(page, '#stt_say')), 'the page counts the recording against the video\'s length', 40000);
    const bar1 = +(await page.getAttribute('#stt_bar', 'aria-valuenow'));
    await sleep(2500);
    const bar2 = +(await page.getAttribute('#stt_bar', 'aria-valuenow'));
    assert(bar2 > bar1, `the bar moves with the video (${bar1} -> ${bar2})`);
    eq(await page.evaluate(() => [document.getElementById('stt_go').hidden, document.getElementById('stt_cancel').hidden]), [true, false], 'no second start from here; Cancel is there');
    const sz = await page.$eval('#stt_frame iframe', f => { const r = f.getBoundingClientRect(); return [r.width, r.height]; });
    assert(sz[0] >= 200 && sz[1] >= 200, 'the frame stays on screen while it records');
    await shotN(page, 'n1-recording');
    await inReview(page, 'the recording ends and the words are put up for review');
    eq(await page.inputValue('#transcript'), BOX, 'the words wait in the review: the box is exactly as it was');
    eq(page.dialogs.length, 1, 'and it asked no second time: the box did not change while it ran');
    await shotN(page, 'n1-review');
    {
      const c = await captured(page);
      eq([c.busy, c.contexts.every(x => x === 'closed'), c.tracks.every(t => t.every(x => x === 'ended'))], [false, true, true],
         'the tab, both contexts and every track are let go as soon as the recording is done');
    }
    await useIt(page);
    // the box held words of the person's own, which the result replaces: asked, in the words of the review, before it did
    eq([page.dialogs.length, /^Replace the transcript in the box with this reviewed transcript\?/.test(page.dialogs[1] || '')], [2, true],
       'a box with words in it was asked about a second time, when they were to be replaced: ' + JSON.stringify(page.dialogs));
    const read = await panelStarts(page);
    eq(read.map(r => r[1]), ['Buongiorno a tutti', 'oggi andiamo al mercato', 'compriamo la frutta'], 'the words are in the transcript box, one caption each');
    assert(read.every((r, i) => Math.abs(r[0] - [0, 2.5, 6][i]) < 0.75), `on the video's own clock, within the start of the recording: ${JSON.stringify(read.map(r => r[0]))}`);
    assert(/The transcript is in the box: 3 captions/.test(await text(page, '#stt_note')), await text(page, '#stt_note'));
    const c = await captured(page);
    eq([c.frames, c.busy, c.contexts.every(x => x === 'closed'), c.tracks.every(t => t.every(x => x === 'ended'))], [0, false, true, true],
       'the video is out of its frame, and the tab, both contexts and every track are let go');
    const rec = (await fakeLog()).filter(r => r.kind === 'transcribe').pop();
    assert(rec && rec.samples >= 12 * 16000 && rec.samples <= 13.6 * 16000 && rec.peak > 0.3 && rec.language === 'it' && rec.device === 'cpu',
           `the sound the tab gave reached the worker: ${JSON.stringify(rec && {samples: rec.samples, peak: rec.peak, language: rec.language, device: rec.device})}`);
    eq(await names(TMPAUDIO), [], 'the temporary sound is deleted');
    const held = await names(HOLD, /\.json$/);
    eq(held.length, 1, 'the shape of the sound is held for the video: ' + held);
    const wave = await readJson(`${HOLD}/${held[0]}`);
    assert(wave.rate === 20 && wave.peaks.length >= 241 && wave.peaks.length <= 243 && Math.max(...wave.peaks) === 1, `in the canonical shape: rate ${wave.rate}, ${wave.peaks.length} numbers`);
    assert(!(await exists(`${VIDEOS}/italian/${NID}`)), 'the video was NOT added');
    // the order of what was sent: the pieces in order from 0, the marks and the shape before the last piece
    const calls = page.calls, lastAt = calls.findIndex(x => /^audio\?.*last=1/.test(x));
    const offsets = calls.filter(x => /^audio\?/.test(x) && !/last=1/.test(x)).map(x => +/offset=(\d+)/.exec(x)[1]);
    assert(offsets[0] === 0 && offsets.every((o, i) => i === 0 || o > offsets[i - 1]) && offsets.length >= 2, `the sound went in pieces, in order, from sample 0: ${offsets}`);
    assert(calls.indexOf('marks') > -1 && calls.indexOf('marks') < lastAt && calls.indexOf('wave') > -1 && calls.indexOf('wave') < lastAt,
           `the marks and the shape went before the last piece: ${JSON.stringify(calls.filter(x => !/^status/.test(x)))}`);
    assert(lastAt > -1 && calls.indexOf('result') > lastAt, 'and the words were asked for after it');
    // and now the video, the way a pasted transcript adds one
    const empty = await watchEmpty(page);
    await page.click('#empty');
    const made = await empty.body;
    eq([made.ok, made.waveform], [true, {kept: true, buckets: wave.peaks.length}], 'the door that made the video was given the token and kept the waveform');
    await page.waitForURL(new RegExp(`/youtube/v/${NID}/$`), {timeout: 30000});
    const beside = await readJson(`${VIDEOS}/italian/${NID}/waveform.json`);
    eq(beside, wave, 'waveform.json lands beside the video, as the player\'s own door writes it');
    eq(Object.keys(beside), ['rate', 'peaks'], 'in the shape it has always had');
    eq(await names(HOLD, /\.json$/), [], 'and the hold is spent');
    await context.close();
  }

  {
    console.log('   n1c) on the phone\'s layout the video stays in the page: "Edit the transcript…" is put off while it is loaded');
    // the layout is the person's choice (parseh_mode); there is no workspace over the page, the frame is
    // where the block put it, and the second copy of the video the editor would play is refused (with a
    // transcript in the box: with none, the editor says "paste the transcript first" before anything)
    const {context, page} = await addPage({width: 390, box: BOX, init: () => { try { localStorage.setItem('parseh_mode', 'mobile'); } catch (_) {} }});
    eq(await page.evaluate(() => document.documentElement.getAttribute('data-mode')), 'mobile', 'the page is in the phone\'s layout');
    await toReady(page);
    eq(await page.evaluate(() => { const w = document.getElementById('stt_workspace'); return [w.open, w.contains(document.getElementById('stt_frame'))]; }),
       [false, false], 'no workspace is over the page, and the frame is in the page');
    await page.evaluate(() => document.getElementById('subedit').scrollIntoView({block: 'center'}));
    assert(await onScreen(page, '#subedit'), '"Edit the transcript…" is there to be pressed: nothing is over it');
    await page.click('#subedit');
    eq([await page.locator('.se-box').count(), await page.evaluate(() => document.getElementById('parseh-toast').textContent)],
       [0, 'the video in the frame above is being recorded — finish or cancel that first'], '"Edit the transcript…" is put off while the video is loaded here');
    await shotN(page, 'n1c-ready-390-mobile');
    await page.click('#stt_cancel');
    await inPh(page, 'idle', 'Cancel');
    await context.close();
  }

  {
    console.log('   n1b) a video whose length its player rounds up, as YouTube\'s does: the recording ends with the video and the words come');
    // it ended as "The video stopped moving for ten seconds, so the recording was stopped and nothing was written"
    // with the bar at its end: the clock stops where the video does, up to a second short of the length
    const {context, page} = await addPage({query: 'src=short.wav&over=0.6'});
    await toReady(page);
    await page.click('#stt_rec');
    await inPh(page, 'recording', 'recording');
    await inReview(page, 'the recording ends and the words are put up for review', 40000);
    assert(!/stopped moving/.test(await text(page, '#stt_note')), 'the page did not say the video stopped moving: ' + await text(page, '#stt_note'));
    await useIt(page);
    const note = await text(page, '#stt_note');
    assert(/The transcript is in the box: 3 captions/.test(note) && !/stopped moving/.test(note),
           'the words are in the box, and the page did not say the video stopped moving: ' + note);
    eq((await panelStarts(page)).map(r => r[1]), ['Buongiorno a tutti', 'oggi andiamo al mercato', 'compriamo la frutta'], 'one caption each');
    const rec = (await fakeLog()).filter(r => r.kind === 'transcribe').pop();
    assert(rec && rec.samples >= 12 * 16000 && rec.samples <= 15 * 16000,
           `the sound the tab gave reached the worker: ${rec && (rec.samples / 16000).toFixed(2)} s for a video of 12 (it did not wait ten seconds for a video that had ended)`);
    const c = await captured(page);
    eq([c.frames, c.busy, c.contexts.every(x => x === 'closed'), c.tracks.every(t => t.every(x => x === 'ended'))], [0, false, true, true],
       'the video is out of its frame, and the tab, both contexts and every track are let go');
    eq(await names(TMPAUDIO), [], 'the temporary sound is deleted');
    eq((await names(HOLD, /\.json$/)).length, 1, 'the shape of the sound is held for the video, which has not been added');
    await context.close();
    // let the held shape go, so the next section starts clean
    for (const n of await names(HOLD, /\.json$/)) await Deno.remove(`${HOLD}/${n}`);
  }

  {
    console.log('   n2) a share without its sound: said at once, the video never plays, and the button can be pressed again');
    const noSound = () => {
      navigator.mediaDevices.getDisplayMedia = () => {
        const c = document.createElement('canvas');
        c.width = 64; c.height = 36;
        c.getContext('2d').fillRect(0, 0, 64, 36);
        return Promise.resolve(c.captureStream(5));
      };
    };
    const {context, page} = await addPage({init: noSound});
    const j = await toReady(page);
    const t0 = Date.now();
    await page.click('#stt_rec');
    await until(async () => /came without its sound/.test(await text(page, '#stt_note')), 'the missing sound is said', 8000);
    assert(Date.now() - t0 < 4000, `at once (${Date.now() - t0} ms), not after the video`);
    eq(await text(page, '#stt_note'), 'The share came without its sound — share this tab again and turn on “Share tab audio”.', 'in a sentence that says what to turn on');
    const c = await captured(page);
    eq(c.calls, [], 'the video was never played, sought or paused');
    eq([await ph(page), await page.evaluate(() => !document.getElementById('stt_rec').hidden)], ['ready', true], 'the job and the video are still good: the button can be pressed again');
    eq(page.calls.filter(x => /^(audio|marks|wave)/.test(x)), [], 'nothing was sent to the computer');
    eq((await status(page, j.job)).state, 'awaiting-audio', 'the computer still waits for it');
    await page.click('#stt_cancel');
    await inPh(page, 'idle', 'Cancel');
    eq([(await status(page, j.job)).state, await names(TMPAUDIO), await names(HOLD, /\.json$/)], ['cancelled', [], []], 'cancelled, and nothing of it left');
    await context.close();
  }

  {
    console.log('   n3) a share that is refused: said, and the button can be pressed again');
    const refuse = () => { navigator.mediaDevices.getDisplayMedia = () => Promise.reject(new DOMException('Permission denied', 'NotAllowedError')); };
    const {context, page} = await addPage({init: refuse});
    await toReady(page);
    await page.click('#stt_rec');
    await until(async () => /not allowed to record this tab/.test(await text(page, '#stt_note')), 'the refusal is said', 8000);
    eq(await text(page, '#stt_note'), 'The browser was not allowed to record this tab. Press Start recording again, choose this tab, and press “Share”.', 'in the person\'s words');
    eq([await ph(page), (await captured(page)).calls], ['ready', []], 'and the video is untouched and waits');
    await page.click('#stt_cancel');
    await inPh(page, 'idle', 'Cancel');
    await context.close();
  }

  {
    console.log('   n4) Cancel in the middle of the recording: playback, tracks, upload, the temporary sound, and the box');
    const {context, page} = await addPage({box: 'my own words'});
    const j = await toReady(page);
    await page.click('#stt_rec');
    await inPh(page, 'recording', 'recording');
    await until(async () => (await names(TMPAUDIO, /\.pcm$/)).length === 1, 'the first piece of the sound has reached the computer', 40000);
    const before = errors.length;
    await page.click('#stt_cancel');
    await inPh(page, 'idle', 'Cancel ends it');
    await sleep(600);
    const c = await captured(page);
    assert(c.calls.includes('playVideo') && c.calls.includes('pauseVideo'), 'the video was played and then stopped: ' + c.calls);
    eq([c.frames, c.busy, c.contexts.every(x => x === 'closed'), c.tracks.every(t => t.every(x => x === 'ended'))], [0, false, true, true], 'the frame, the tab, both contexts and every track are gone');
    eq(await page.inputValue('#transcript'), 'my own words', 'the box is exactly as it was');
    const st = await status(page, j.job);
    eq([st.state, st.stopped], ['cancelled', true], 'the computer agrees');
    eq([await names(TMPAUDIO), await names(HOLD, /\.json$/)], [[], []], 'no temporary sound, no held waveform');
    assert(page.calls.includes('cancel') && !page.calls.some(x => /^wave/.test(x) || /last=1/.test(x)),
           'it told the computer, and sent neither the shape nor a last piece: ' + JSON.stringify(page.calls.filter(x => !/^status/.test(x))));
    forgive(before, /^(409|404) POST \/youtube\/api\/transcribe\/(audio|marks|wave)$/, 'a piece that was on its way when it was cancelled');
    // nothing is stuck: it can be started again, and cancelled again
    await page.click('#stt_go');
    await inPh(page, 'ready', 'a second start after Cancel works');
    await page.click('#stt_cancel');
    await inPh(page, 'idle', 'and can be cancelled');
    await context.close();
  }

  {
    console.log('   n5) a second start while one records is refused, on this page and on another');
    const a = await addPage({box: 'a'});
    await toReady(a.page);
    await a.page.click('#stt_rec');
    await inPh(a.page, 'recording', 'the first is recording');
    const b = await addPage();
    const before = errors.length;
    await b.page.click('#stt_go');
    await until(async () => /Another transcription is running/.test(await text(b.page, '#stt_note')), 'the second is refused, in words');
    eq(await text(b.page, '#stt_note'), 'Another transcription is running. Wait for it to finish, or stop it from the page that started it.', 'in these words');
    const cb = await captured(b.page);
    eq([await ph(b.page), cb.asked, cb.frames, await b.page.evaluate(() => !document.getElementById('stt_go').hidden)],
       ['idle', 0, 0, true], 'and it loaded no video, shared nothing, and is not stuck');
    eq(forgive(before, /^409 POST \/youtube\/api\/transcribe\/start$/, 'the refusal'), 1, 'one refusal of the computer');
    await b.context.close();
    const mark = errors.length;
    await a.page.click('#stt_cancel');
    await inPh(a.page, 'idle', 'the first is cancelled');
    await sleep(600);
    forgive(mark, /^(409|404) POST \/youtube\/api\/transcribe\//, 'what was on its way');
    await a.context.close();
  }

  {
    console.log('   n6) the same road in Persian, on a phone\'s width, on a page turned right to left');
    await setSttFake({segments: PERSIAN});
    const ID6 = 'zC1dE2fG3hI';
    const {context, page} = await addPage({lang: 'fa', width: 390, id: ID6});
    await page.evaluate(() => { document.documentElement.dir = 'rtl'; });
    eq(await fits(page), [], 'idle: the block fits');
    assert(/Persian/.test(await text(page, '#stt_lang')) && /فارسی/.test(await text(page, '#stt_lang')), 'the language names itself: ' + await text(page, '#stt_lang'));
    await toReady(page);
    eq(await fits(page), [], 'the video is loaded: it fits, on 390 px');
    eq(await headOk(page), [], 'and its title bar and "Return to Add Video" are on the screen, though the page behind was scrolled');
    const frame = await page.$eval('#stt_frame iframe', f => { const r = f.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; });
    assert(frame[0] >= 200 && frame[1] >= 200, `and the frame is ${frame[0]} x ${frame[1]}: no smaller than YouTube plays`);
    await shotN(page, 'n6-ready-390-rtl');
    await page.click('#stt_rec');
    await inPh(page, 'recording', 'recording');
    await until(async () => /^Recording \d+:\d\d \/ 0:12…$/.test(await text(page, '#stt_say')), 'counting', 40000);
    eq(await fits(page), [], 'recording: it fits');
    await shotN(page, 'n6-recording-390-rtl');
    await inReview(page, 'the words are put up for review');
    eq(await fits(page), [], 'in review: it fits');
    await shotN(page, 'n6-review-390-rtl');
    await useIt(page);
    const box = await page.inputValue('#transcript');
    assert(/سلام دنیا/.test(box) && /میوه/.test(box), 'the Persian text is in the box, as Whisper wrote it: ' + JSON.stringify(box));
    eq(await fits(page), [], 'done: it fits');
    await shotN(page, 'n6-done-390-rtl');
    assert(await page.evaluate(() => !document.getElementById('stt_tied').hidden), 'the box is tied to the video that made it');
    // another address: the box is no longer tied to it, and the waveform held for the first
    // video does not come with a video that is not it
    const held = await names(HOLD, /\.json$/);
    eq(held.length, 1, 'the shape of the sound is held for the video');
    await page.fill('#url', `https://www.youtube.com/watch?v=zD1eF2gH3iJ`);
    assert(await page.evaluate(() => document.getElementById('stt_tied').hidden), 'a different address: no longer tied');
    assert(/no longer tied to speech to text: the video changed/.test(await text(page, '#stt_note')), await text(page, '#stt_note'));
    await page.selectOption('#lang', 'fa');
    const empty = await watchEmpty(page);
    await page.click('#empty');
    const made = await empty.body;
    eq([made.ok, 'waveform' in made], [true, false], 'the video that is not the recorded one is made without its waveform (the token was not sent)');
    eq((await names(HOLD, /\.json$/)).length, 1, 'and the held one is not spent on it');
    await context.close();
    await setSttFake({segments: ITALIAN});
    // the shape of that run's sound is still held: let it go, so the next section starts clean
    for (const n of await names(HOLD, /\.json$/)) await Deno.remove(`${HOLD}/${n}`);
  }

  {
    console.log('   n7) the computer refusing a piece of the recording: said in its own words, nothing left behind');
    for (const [name, answer, want] of [
      ['a gap', {status: 409, body: {ok: false, code: 'gap', have: 0, error: 'A piece of the recording is missing.'}},
       'A piece of the recording went missing on its way, so it was stopped.'],
      ['no room', {status: 507, body: {ok: false, code: 'no-room', error: 'There was not enough disk space to finish the capture.'}},
       'There was not enough disk space to finish the capture.']]) {
      const {context, page} = await addPage({box: 'my own words'});
      const j = await toReady(page);
      const before = errors.length;
      // the second piece of the sound is the one the computer refuses (the first, at sample 0, goes through)
      await page.route(/transcribe\/audio\?.*offset=80000/, route => route.fulfill({status: answer.status, contentType: 'application/json', body: JSON.stringify(answer.body)}));
      await page.click('#stt_rec');
      await inPh(page, 'recording', 'recording');
      await until(async () => (await text(page, '#stt_note')).length > 0, `${name}: said`, 40000);
      eq(await text(page, '#stt_note'), want, `${name}: in a sentence`);
      await inPh(page, 'idle', `${name}: and idle again`);
      const c = await captured(page);
      eq([c.frames, c.busy, c.tracks.every(t => t.every(x => x === 'ended'))], [0, false, true], `${name}: the video, the tab and the tracks are let go`);
      eq(await page.inputValue('#transcript'), 'my own words', `${name}: the box is as it was`);
      await until(async () => (await status(page, j.job)).state === 'cancelled', `${name}: the computer was told to let the job go`);
      eq([await names(TMPAUDIO), await names(HOLD, /\.json$/)], [[], []], `${name}: no temporary sound, no held waveform`);
      forgive(before, /^(409|507|404) POST \/youtube\/api\/transcribe\/(audio|marks|wave)$/, `${name}: the refusal that was made up for it`);
      await context.close();
    }
  }

  {
    console.log('   n8) the person stops sharing the tab while it records');
    const {context, page} = await addPage({box: 'my own words'});
    const j = await toReady(page);
    await page.click('#stt_rec');
    await inPh(page, 'recording', 'recording');
    await until(async () => /^Recording 0:0[2-9]/.test(await text(page, '#stt_say')), 'a little of it is recorded', 30000);
    await page.evaluate(() => __streams[0].getAudioTracks()[0].dispatchEvent(new Event('ended')));     // Chrome's "Stop sharing"
    await until(async () => /stopped being shared/.test(await text(page, '#stt_note')), 'said', 10000);
    eq(await text(page, '#stt_note'), 'The tab stopped being shared while its sound was being recorded.', 'in a sentence');
    await inPh(page, 'idle', 'idle again');
    eq(await page.inputValue('#transcript'), 'my own words', 'the box is as it was');
    await until(async () => (await status(page, j.job)).state === 'cancelled', 'the computer was told to let the job go');
    eq([await names(TMPAUDIO), await names(HOLD, /\.json$/)], [[], []], 'nothing of it is left');
    await context.close();
  }

  {
    console.log('   n9) leaving the page ends a recording: the browser asks first, and the computer is told');
    const {context, page} = await addPage({box: BOX});
    const j = await toReady(page);
    await page.click('#stt_rec');
    await inPh(page, 'recording', 'recording');
    await until(async () => (await names(TMPAUDIO, /\.pcm$/)).length === 1, 'the first piece of the sound is on the computer', 40000);
    eq(await page.evaluate(() => { const e = new Event('beforeunload', {cancelable: true}); window.dispatchEvent(e); return e.defaultPrevented; }),
       true, 'the browser is asked before the page is left while it records');
    const before = errors.length;
    await page.goto('about:blank');          // leaving the page (the browser's own question is answered yes by addPage)
    const stateOf = job => fetch(`${BASE}/youtube/api/transcribe/status`, {method: 'POST', headers: {'content-type': 'application/json'},
                                                                          body: JSON.stringify({job})}).then(r => r.json()).then(j => j.state);
    await until(async () => (await stateOf(j.job)) === 'cancelled', 'the computer was told (a beacon at pagehide)', 15000);
    eq(await names(TMPAUDIO), [], 'and the temporary sound is gone');
    forgive(before, /^(409|404) POST \/youtube\/api\/transcribe\/(audio|marks|wave)$/, 'a piece that was on its way');
    await context.close();
  }

  {
    console.log('   n10) YouTube that cannot be reached: said, the computer let go, nothing stuck');
    const {context, page} = await addPage();
    await context.route('https://www.youtube.com/iframe_api', route => route.abort());
    const start = page.waitForResponse(r => /transcribe\/start$/.test(r.url()));
    await page.click('#stt_go');
    const j = await (await start).json();
    await until(async () => /could not be fetched/.test(await text(page, '#stt_note')), 'the video that cannot be loaded is said', 30000);
    eq(await text(page, '#stt_note'), 'YouTube’s player could not be fetched — Parseh itself is answering, so it is YouTube this computer cannot reach.', 'in a sentence that says whose fault it is');
    await inPh(page, 'idle', 'and it is idle again');
    await until(async () => (await status(page, j.job)).state === 'cancelled', 'the computer was told to let the job go');
    eq([await names(TMPAUDIO), (await captured(page)).frames, await page.evaluate(() => !document.getElementById('stt_go').hidden)], [[], 0, true], 'nothing is left, and Transcribe is there');
    await context.close();
  }
}

assert(errors.length === 0, 'no page error and no failed request: ' + JSON.stringify(errors));
assert(!/Traceback/.test(log.join('')), 'no traceback in the hub\'s log');
console.log(`\nyoutube_capture: ${passed} checks passed`);
} catch (e) {
  console.log(e.stack || e);
  console.log('page errors:', JSON.stringify(errors));
  console.log('hub log tail:\n' + log.join('').slice(-3000));
  Deno.exitCode = 1;
} finally {
  await browser.close();
  if (browserNo) await browserNo.close();
  fakeServers.abort();
  try { hub.kill('SIGTERM'); await hub.status; } catch (_) {}
  await Deno.remove(TMP, {recursive: true}).catch(() => {});
}
