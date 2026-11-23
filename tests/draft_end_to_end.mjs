// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/draft_end_to_end.mjs
//      PARSEH_KEEP=1 keeps the temporary tree, to read what was written
//      DRAFT_E2E_PROMPTS=<dir> keeps every prompt the pages put on the clipboard
//
// A BOOK AND A VIDEO MADE FROM PLAIN TEXT, END TO END, NOW THAT NOTHING IS
// FLAGGED A DRAFT.  The "draft" flag is gone from book.json and video.json:
// a chunk nobody has glossed is legal everywhere, always.  What stayed is the
// drafting PROCESS -- "Make the draft" on /books/add/, "Start it empty" on
// /youtube/add/ -- and this proves it still carries a text all the way to a
// glossed edition, on the REAL hub: serve.main() over a temporary tree, with
// no dictionary, no corpus and no model installed (their three folders
// pointed at empty ones), and nothing stubbed but YouTube's iframe API.
// Every action is a person's: the add pages' cards, fields and buttons, the
// reader's pencil and sheets, the player's phrases, ✎ form and region panel.
// Every prompt is READ OFF THE CLIPBOARD the page wrote it to; every answer
// is written here as an LLM would write it (a real gloss, in the scheme
// docs/lang/<code>.md gives) out of what the clipboard held, and PASTED into
// the answer box with Ctrl+V.  Python is only ever asked to READ: the .tex,
// annotations.json, verify_book, check_batch, check_annotations.
//
//  a) BOOKS -- Persian, Japanese and Chinese (the last two with their word
//     lines and the readings proposed from them, where this machine has the
//     analyzers; with none, a draft has no word lines and the checks below
//     say so), each through /books/add/ "Write it here, by hand":
//     - the note under the slug names the directory the book will be written
//       to, as the title is typed;
//     - "Make the draft" writes the book and opens its reader; book.json has
//       NO "draft" key; neither the library page nor the reader carries a
//       draft mark;
//     - every chunk is a row with its text and no gloss (a proposed reading
//       beside a word line is no gloss: data-seed says so);
//     - a blank chunk's sheet opens; its meaning typed alone is saved -- half
//       glossed, legal by hand -- and check_batch lists it (Chinese: the
//       proposed pinyin counts once the chunk is written, so the chunk is
//       complete); "delete gloss" takes it off, and "undo delete" is offered;
//     - the header's "gloss with an LLM" sheet, the whole book picked in its
//       outline, copies a prompt that names the language and lists every
//       chunk todo; the answer, pasted, "fill from the answer": filled N, the
//       rows show their glosses with no reload; the .tex holds the answer;
//       verify_book: 0 mismatched; check_batch on every paragraph (built the
//       way tests/smoke.py's para_json_from_tex builds one): 0 errors, and no
//       count note;
//     - more text through /books/add/ "Add to a book already here" -- more of
//       the last chapter, then a new chapter: the new chunks arrive blank and
//       legal (no error, no flag), check_batch counts them in one note per
//       paragraph, and the reader shows them blank beside the glossed ones.
//  b) VIDEO -- Persian, through /youtube/add/ "From YouTube" + "Nobody -- I
//     gloss it in the player", with a bare id (no network is asked for):
//     - the page is whole with NO speech to text installed (it is optional): its
//       block is the way to set it up and nothing else, and the page asked the
//       computer what it has and no transcription route, no model's host, no one;
//     - "Start it empty" writes the video and opens the player; video.json has
//       NO "draft" key, and the bare id is written as its watch URL; the
//       player shows no draft badge;
//     - every phrase is hoverable, says "nothing glossed yet" and opens ✎,
//       with no dictionary installed; one filled by hand (the meaning alone)
//       is saved;
//     - the region panel: the first and the last caption clicked, the prompt
//       copied and read, answered, pasted, filled: filled N, those captions
//       drawn again; annotations.json holds the answer;
//     - check_annotations lists the one chunk left half glossed as its one
//       error; completed by hand, it passes with no error and no count note.
//  c) last: no page threw, logged an error or had a request refused beyond
//     the few a new book and a new video are always refused; the hub printed
//     no traceback; the owner's config/, books/, youtube/videos/ and the
//     fixtures are as they were.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-draft-e2e-'});
const PROMPTS = Deno.env.get('DRAFT_E2E_PROMPTS') || '';
let promptNo = 0;
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const eq = (got, want, m) => assert(same(got, want),
  m + (same(got, want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function run(cmd, args) {
  const o = await new Deno.Command(cmd, {args, cwd: root, stdout: 'piped', stderr: 'piped'}).output();
  return {code: o.code, out: td.decode(o.stdout), err: td.decode(o.stderr)};
}
async function py(code, ...args) {
  const r = await run(PY, ['-c', code, ...args]);
  if (r.code) throw Error(r.err || r.out);
  return r.out;
}
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}
function drain(stream, sink) {
  (async () => {
    const r = stream.pipeThrough(new TextDecoderStream()).getReader();
    for (;;) { const {value, done} = await r.read(); if (done) break; sink.push(value); }
  })();
}
async function keepPrompt(name, prompt) {
  const dir = PROMPTS || TMP + '/prompts';
  await Deno.mkdir(dir, {recursive: true});
  await Deno.writeTextFile(`${dir}/${String(++promptNo).padStart(2, '0')}-${name}.md`, prompt);
}

/* ---------------- the toolbox ---------------- */
// An EMPTY shelf under <tmp>/root: no book and no video is copied in -- both
// are made here, from text, by the add pages.  lib/ and youtube/lib/ are
// linked into the tree, as the gloss_llm_* suites link them.  Whether this
// Python can cut Japanese and Chinese into words is asked here, once.
const BUILD = String.raw`
import json, os, sys
from pathlib import Path
REPO = Path(os.getcwd())
sys.path[:0] = ['lib']
tmp = Path(sys.argv[1])
root = tmp / 'root'
for d in (root / 'books', root / 'youtube' / 'videos', tmp / 'library', tmp / 'exercises',
          tmp / 'anki', tmp / 'tray', tmp / 'config', tmp / 'nodict', tmp / 'nocorpus', tmp / 'nomt'):
    d.mkdir(parents=True, exist_ok=True)
os.symlink(str(REPO / 'lib'), str(root / 'lib'))
os.symlink(str(REPO / 'youtube' / 'lib'), str(root / 'youtube' / 'lib'))
import words
print(json.dumps({'root': str(root), 'words': {c: words.available(c) for c in ('ja', 'zh')}}))
`;
// serve.main() over the temporary tree.  Every store it reads or writes is in
// there -- prefs and the network door (a suite once turned the owner's theme
// dark in the real config/), the offline door's two memories, the studio
// library, the decks, the Anki store and the clip tray -- and the three
// things that could answer for an unglossed phrase (a dictionary, a corpus, a
// model) are looked for in empty folders.
//
// THE SHELF IS THE TREE'S, and three things about it need saying to the hub,
// because a book made from text is written where the hub's own modules say
// books live, and those say the repository:
//  - books.BOOKS_DIR, and the default shelf of books.all_books/book_dirs (a
//    default argument, fixed when the function was defined -- so it is the
//    function's defaults that are pointed at the tree, which every module
//    that imported the function by name then shares): "Make the draft"
//    writes into=booklib.BOOKS_DIR, and "Add to a book already here" lists
//    the shelf; newbook.ROOT, which the add page's list is addressed from;
//  - the library page: the hub writes it with a subprocess of the
//    repository's lib/make_index.py, which would write the OWNER's
//    books/index.html -- here it is written into the tree, by the same
//    make_index, as tests/mobile_harness.library_page writes it;
//  - a reader the hub builds links lib/ by the climb from where it stands to
//    the checkout, which a page served from the temporary root cannot follow:
//    every reader the hub builds is given the hub's own path instead, the
//    moment it is built (tests/mobile_harness.built_reader's relink) -- the
//    add page opens the reader straight after the book is made.
const SERVE = String.raw`
import os, sys
from pathlib import Path
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', 'tests', '.']
tmp, port = Path(sys.argv[1]), sys.argv[2]
REPO = os.getcwd()
import prefs, network, offline
prefs.STORE = str(tmp / 'config' / 'prefs.json')
network.STORE = str(tmp / 'config' / 'network.json')
# and the LaTeX drawings' themes, their drawings and their packages
import latexthemes, latexdraw, texpackages
latexthemes.STORE = str(tmp / 'config' / 'latex.json')
# and the prompts a person wrote (lib/prompts.py)
import prompts
prompts.STORE = str(tmp / 'config' / 'prompts.json')
latexdraw.DRAWN = str(tmp / 'latex-drawn')
texpackages.TREE = str(tmp / 'texmf')
offline.DIGESTS = str(tmp / 'config' / 'digests.json')
offline.WHERES = str(tmp / 'config' / 'wheres.json')
import lookup, corpus, getmt
lookup.DICT_DIR = str(tmp / 'nodict')
corpus.CORPUS_DIR = str(tmp / 'nocorpus')
getmt.MT_DIR = str(tmp / 'nomt')
getmt.ENGINE_DIR = str(tmp / 'nomt' / 'engine')
# and speech to text (optional, the add page's): none installed, whatever this machine has
import getstt
getstt.STT_DIR = str(tmp / 'nostt')
import books
shelf = str(tmp / 'root' / 'books')
books.BOOKS_DIR = shelf
books.all_books.__defaults__ = (shelf, None)
books.book_dirs.__defaults__ = (shelf,)
import newbook
newbook.ROOT = str(tmp / 'root')
import clips, decks, store
clips.set_dir(tmp / 'tray')
import serve, ytpages
for st in {store, serve.studio.store}:
    st.LIB = tmp / 'library'
    st.set_clips_dir(tmp / 'tray')
decks.set_dir(tmp / 'exercises')
decks.set_clips_dir(tmp / 'tray')
serve.ROOT = str(tmp / 'root')
serve._AtRoot.directory = str(tmp / 'root')
ytpages.VIDEOS = str(tmp / 'root' / 'youtube' / 'videos')
serve.ANKI = ytpages.ANKI = str(tmp / 'anki')
ytpages.INBOX = str(tmp / 'anki' / 'inbox')
# "Start it empty" asks YouTube for the title and the channel (TO-DO 7.6): here YouTube cannot be reached, as on a
# computer with no network, and the page has to say so
ytpages.oembed_why = lambda vid: ({}, 'offline')
import mobile_harness

def write_library(self):
    try:
        mobile_harness.library_page(tmp / 'root')
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
    return {"ok": True, "error": ""}
serve.Handler._write_library = write_library

built = serve.Handler._rebuild_reader
def rebuild_reader(self, book):
    r = built(self, book)
    out = os.path.join(book, 'reader')
    climb = os.path.relpath(REPO, out).replace(os.sep, '/') + '/'
    for name in os.listdir(out) if os.path.isdir(out) else ():
        if name.endswith('.html'):
            p = os.path.join(out, name)
            with open(p, encoding='utf-8') as f:
                text = f.read()
            with open(p, 'w', encoding='utf-8') as f:
                f.write(text.replace(climb, '/'))
    return r
serve.Handler._rebuild_reader = rebuild_reader
sys.argv = ['serve.py', '--http', '--local', port]
serve.main()
`;
// every chunk of a chapter file as texwrite reads it
const CHUNKS = String.raw`
import json, sys
sys.path.insert(0, 'lib')
import texwrite
print(json.dumps(texwrite.read_chunks(sys.argv[1]), ensure_ascii=False))
`;
// CHECK_BATCH ON EVERY PARAGRAPH OF THE BOOK, each built the way
// tests/smoke.py's para_json_from_tex builds paragraph 0 of chapter 1 --
// read back out of the .tex with texparse, the word line and the reading
// with it -- for every chapter and every paragraph, the chapter numbered by
// its file (ch2.tex is chapter 2) -> [{ch, idx, rc, out}]
const BATCH = String.raw`
import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, 'lib')
import books, texparse as T
b = books.Book(sys.argv[1])
chapters = T.parse_book(b.main, b.lang) if "lang" in T.parse_book.__code__.co_varnames \
    else T.parse_book(b.main)
out = []
with tempfile.TemporaryDirectory() as td:
    for ch in chapters:
        no = int(re.match(r"ch(\d+)", os.path.basename(ch.path)).group(1))
        for n, para in enumerate(ch.paragraphs):
            sents = []
            for s in para.subs:
                chunks = []
                for c in s.chunks:
                    d = {"fa": c.fa, "tr": c.tr, "voc": c.voc, "en": c.en}
                    if getattr(c, "kana", ""):
                        d["kana"] = c.kana
                    if getattr(c, "wordline", ""):
                        d["words"] = c.wordline
                    chunks.append(d)
                sents.append({"chunks": chunks})
            pj = {"idx": n, "ch": no, "ann": {"sentences": sents}}
            pp = os.path.join(td, "ch%d_p%02d.json" % (no, n))
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pj, f, ensure_ascii=False)
            r = subprocess.run([sys.executable, os.path.join("lib", "check_batch.py"), pp, "--book", b.dir],
                               capture_output=True, text=True)
            out.append({"ch": no, "idx": n, "rc": r.returncode, "out": r.stdout + r.stderr,
                        "chunks": sum(len(s["chunks"]) for s in sents)})
print(json.dumps(out, ensure_ascii=False))
`;
const chunksOf = async path => JSON.parse(await py(CHUNKS, path));
const batchOf = async dir => JSON.parse(await py(BATCH, dir));
async function verifyBook(dir) {
  const r = await run(PY, ['lib/verify_book.py', '--book', dir]);
  return {code: r.code, out: (r.out + r.err).trim()};
}
async function checkVideo(dir) {
  const r = await run(PY, ['youtube/lib/check_annotations.py', dir]);
  return {code: r.code, out: (r.out + r.err).trim()};
}
const countNote = /note\s+(\d+) of (\d+) chunks have no gloss yet/;
const errorCount = out => { const m = out.match(/\n(\d+) errors?, (\d+) warnings?/); return m ? [+m[1], +m[2]] : null; };
// the ```json block the prompt ends with: the data, as the LLM receives it
function dataOf(prompt) {
  const at = prompt.lastIndexOf('```json\n');
  if (at < 0) throw Error('the prompt has no ```json block');
  const body = prompt.slice(at + 8);
  return JSON.parse(body.slice(0, body.indexOf('\n```')));
}
const fence = doc => '```json\n' + JSON.stringify(doc, null, 2) + '\n```\n';
const GLOSS = ['kana', 'tr', 'voc', 'en'];

// the owner's own files, which nothing here may touch: their digests now,
// compared at the end -- all but the offline door's two memories in config/,
// which his own running hub may write to meanwhile, and which are searched
// for this run's tree instead.  books/index.html is among them on purpose:
// "Make the draft" and "Add it" both rewrite the library page.
const OWN = String.raw`
import hashlib, json, os, sys
tmp = sys.argv[1]
out, leaks = {}, []
for top in ('config', 'books', 'youtube/videos', 'tests/fixtures/videos', 'tests/fixtures/books'):
    for d, _, files in os.walk(top):
        if '/reader' in d.replace(os.sep, '/') + '/' and top == 'tests/fixtures/books':
            continue                    # build output, gitignored
        for f in files:
            p = os.path.join(d, f)
            if p.replace(os.sep, '/') in ('config/digests.json', 'config/wheres.json'):
                try:
                    text = open(p, encoding='utf-8').read()
                except OSError:
                    continue
                if tmp in text:
                    leaks.append(p)
                continue
            out[p] = hashlib.md5(open(p, 'rb').read()).hexdigest()
print(json.dumps({'digests': out, 'leaks': leaks}, sort_keys=True))
`;
const ownBefore = JSON.parse(await py(OWN, TMP));

// THE YOUTUBE PLAYER, as the page loads it from https://www.youtube.com/iframe_api:
// the calls the page may make of it, and a clock that runs while it "plays"
const FAKE_YT = `window.YT = {Player: function (el, o) {
  var t = 0, going = false, self = this;
  window.__yt = {seeks: [], t: function () { return t; }, going: function () { return going; },
                 pause: function () { going = false; }};
  this.getCurrentTime = function () { return t; };
  this.getDuration = function () { return 40; };
  this.seekTo = function (s) { t = +s || 0; window.__yt.seeks.push(t); };
  this.playVideo = function () { going = true; };
  this.pauseVideo = function () { going = false; };
  this.getPlayerState = function () { return going ? 1 : 2; };
  this.getPlaybackRate = function () { return 1; };
  this.setPlaybackRate = function () {};
  this.mute = function () {}; this.unMute = function () {};
  this.isMuted = function () { return false; };
  setInterval(function () { if (going) t += 0.05; }, 50);
  setTimeout(function () { if (o.events && o.events.onReady) o.events.onReady({target: self}); }, 20);
}};
if (window.onYouTubeIframeAPIReady) window.onYouTubeIframeAPIReady();`;

/* ---------------- the texts, and the answers an LLM would give ---------------- */
// Two paragraphs of two sentences each: "Make the draft" cuts one chunk per
// sentence, so every chunk below is a sentence.  The glosses are written as
// the prompt asks, in the scheme docs/lang/<code>.md gives -- Persian's tr
// with ā š č x q and the hyphenated morphology (mi-, -hā, -am, ezafe -ye), no
// entry for a never-gloss word; Japanese kana as written (は, へ), Hepburn
// with macrons; Chinese pinyin with tone marks, words run together as the
// word line has them, ASCII punctuation -- and a book's voc in the macros
// and nothing else.
const BOOKS = [
  {code: 'fa', name: 'Persian', folder: 'persian', slug: 'yek-ruz-e-xub',
   title: 'یک روز خوب', title_latin: 'Yek ruz-e xub', title_en: 'A good day',
   text: 'امروز هوا خیلی خوب است. من با دوستم به پارک می‌روم.\n\n' +
         'در پارک بچه‌ها بازی می‌کنند. ما روی نیمکت می‌نشینیم و چای می‌نوشیم.',
   gloss: {
     'امروز هوا خیلی خوب است.': {tr: 'emruz havā xeyli xub ast',
       voc: String.raw`\dw{امروز}{emruz} today; \dw{هوا}{havā} weather; \vb{بودن}{budan}{باش}{bāš}{بود}{bud}{to be}`,
       en: 'the weather is very good today.'},
     'من با دوستم به پارک می‌روم.': {tr: 'man bā dust-am be pārk mi-ravam',
       voc: String.raw`\dw{دوست}{dust} friend, \nobreak+\,enclitic \textit{-am} my; \vb{رفتن}{raftan}{رو}{rav}{رفت}{raft}{to go}`,
       en: 'I am going to the park with my friend.'},
     'در پارک بچه‌ها بازی می‌کنند.': {tr: 'dar pārk bačče-hā bāzi mi-konand',
       voc: String.raw`\dw{بچه}{bačče} child, \nobreak+\,pl.\,\textit{-hā}; \vb{کردن}{kardan}{کن}{kon}{کرد}{kard}{}\bw{بازی}{bāzi}{to play}`,
       en: 'in the park the children are playing.'},
     'ما روی نیمکت می‌نشینیم و چای می‌نوشیم.': {tr: 'mā ru-ye nimkat mi-nešinim va čāy mi-nušim',
       voc: String.raw`\dw{نیمکت}{nimkat} bench; \vb{نشستن}{nešastan}{نشین}{nešin}{نشست}{nešast}{to sit}; \vb{نوشیدن}{nušidan}{نوش}{nuš}{نوشید}{nušid}{to drink}`,
       en: 'we sit on a bench and drink tea.'},
   },
   more: 'بعد از ظهر به خانه برمی‌گردیم.',
   chapter2: 'فردا باران می‌بارد. ما در خانه کتاب می‌خوانیم.'},
  {code: 'ja', name: 'Japanese', folder: 'japanese', slug: 'ii-hi',
   title: 'いい日', title_latin: 'Ii hi', title_en: 'A good day',
   text: '今日は天気がいいです。友達と公園へ行きます。\n\n' +
         '公園では子供たちが遊んでいます。ベンチに座って、お茶を飲みます。',
   gloss: {
     '今日は天気がいいです。': {kana: 'きょうはてんきがいいです。', tr: 'kyō wa tenki ga ii desu.',
       voc: String.raw`\dw{今日}{kyō} today; \dw{天気}{tenki} weather; \pw{が} marks the subject`,
       en: 'the weather is nice today.'},
     '友達と公園へ行きます。': {kana: 'ともだちとこうえんへいきます。', tr: 'tomodachi to kōen e ikimasu.',
       voc: String.raw`\dw{友達}{tomodachi} friend; \dw{公園}{kōen} park; \pw{へ} to, read \textit{e}; \vb{行く}{iku}{行き}{iki}{行って}{itte}{to go (godan; intr.)}`,
       en: 'I am going to the park with a friend.'},
     '公園では子供たちが遊んでいます。': {kana: 'こうえんではこどもたちがあそんでいます。', tr: 'kōen de wa kodomotachi ga asonde imasu.',
       voc: String.raw`\dw{子供}{kodomo} child, \nobreak+\,\textit{-tachi} plural; \vb{遊ぶ}{asobu}{遊び}{asobi}{遊んで}{asonde}{to play (godan; intr.)}`,
       en: 'in the park the children are playing.'},
     'ベンチに座って、お茶を飲みます。': {kana: 'ベンチにすわって、おちゃをのみます。', tr: 'benchi ni suwatte, ocha o nomimasu.',
       voc: String.raw`\vb{座る}{suwaru}{座り}{suwari}{座って}{suwatte}{to sit (godan; intr.)}; \dw{お茶}{ocha} tea; \vb{飲む}{nomu}{飲み}{nomi}{飲んで}{nonde}{to drink (godan; tr.)}`,
       en: 'we sit on a bench and drink tea.'},
   },
   more: '夕方、家に帰ります。',
   chapter2: '明日は雨です。家で本を読みます。'},
  {code: 'zh', name: 'Chinese', folder: 'chinese', slug: 'hao-rizi',
   title: '好日子', title_latin: 'Hao rizi', title_en: 'A good day',
   text: '今天天气很好。我和朋友去公园。\n\n' +
         '孩子们在公园里玩。我们坐在树下喝茶。',
   gloss: {
     '今天天气很好。': {tr: 'jīntiān tiānqì hěn hǎo.',
       voc: String.raw`\dw{今天}{jīntiān} today; \dw{天气}{tiānqì} weather; \dw{很}{hěn} very`,
       en: 'the weather is very good today.'},
     '我和朋友去公园。': {tr: 'wǒ hé péngyǒu qù gōngyuán.',
       voc: String.raw`\dw{朋友}{péngyǒu} friend; \dw{去}{qù} to go; \dw{公园}{gōngyuán} park`,
       en: 'I am going to the park with a friend.'},
     '孩子们在公园里玩。': {tr: 'háizimen zài gōngyuán lǐ wán.',
       voc: String.raw`\dw{孩子们}{háizimen} children; \dw{在}{zài} at, in; \dw{玩}{wán} to play`,
       en: 'the children are playing in the park.'},
     '我们坐在树下喝茶。': {tr: 'wǒmen zuò zài shùxià hēchá.',
       voc: String.raw`\dw{坐}{zuò} to sit; \dw{树下}{shùxià} under a tree; \dw{喝茶}{hēchá} to drink tea`,
       en: 'we sit under a tree and drink tea.'},
   },
   more: '晚上我们回家。',
   chapter2: '明天会下雨。我们在家看书。'},
];
// The video: a plain English opening line, then three captions of Persian as
// YouTube gives them (no harakat), one of them two sentences
const VIDEO = {
  id: 'dRfT0e2eFa1', code: 'fa',
  transcript: '0:00\nWelcome to a short Persian lesson\n0:04\nسلام، حال شما چطور است؟\n' +
              '0:09\nمن خوبم، ممنون. شما چطورید؟\n0:15\nامروز هوا خیلی خوب است.\n',
  // the video's voc is plain text: headword, sound, meaning
  gloss: {
    'سلام، حال شما چطور است؟': {tr: 'salām, hāl-e šomā četowr ast',
      voc: 'سلام salām hello (peace) · حال hāl state, how one is · چطور četowr how', en: 'hello, how are you?'},
    'من خوبم، ممنون.': {tr: 'man xub-am, mamnun',
      voc: 'خوب xub good, + -am I am · ممنون mamnun thankful, thanks', en: "I'm fine, thanks."},
    'شما چطورید؟': {tr: 'šomā četowr-id',
      voc: 'چطور četowr how, + -id you (pl./polite) are', en: 'how are you?'},
  },
  // the one filled by hand, the meaning first, the rest later
  hand: {fa: 'امروز هوا خیلی خوب است.', en: 'the weather is very good today.', tr: 'emruz havā xeyli xub ast'},
};

const errors = [];
let hub = null, browser = null;
const log = [];
try {
  const B0 = JSON.parse((await py(BUILD, TMP)).trim().split('\n').pop());
  console.log(`the analyzers here: Japanese ${B0.words.ja ? 'installed' : 'NOT installed'}, Chinese ${B0.words.zh ? 'installed' : 'NOT installed'}`);
  const port = freePort();
  hub = new Deno.Command(PY, {args: ['-c', SERVE, TMP, String(port)], cwd: root,
                              stdout: 'piped', stderr: 'piped'}).spawn();
  drain(hub.stdout, log); drain(hub.stderr, log);
  const B = `http://127.0.0.1:${port}`;
  {
    const t = Date.now();
    for (;;) {
      try { const r = await fetch(B + '/clips/api/status'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
      if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join(''));
      await sleep(250);
    }
  }
  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  const context = await browser.newContext({viewport: {width: 1280, height: 900}});
  // the clipboard, both ways: the page writes the prompt, the test reads it;
  // the test writes the answer, and Ctrl+V pastes it into the answer box
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], {origin: B});
  // nothing leaves this machine but YouTube's API, which is this test's
  const abroad = [];
  await context.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, route => {
    if (route.request().url() === 'https://www.youtube.com/iframe_api')
      return route.fulfill({contentType: 'text/javascript', body: FAKE_YT});
    abroad.push(route.request().url());
    return route.abort();
  });

  /* ---------------- helpers over a page ---------------- */
  // WHAT A PAGE MAY BE REFUSED, and nothing else.  A book with no recording
  // has no timings.json; a machine with no translation model has no
  // /mt/<pair>/meta.json nor /mt/engine/meta.json; a video whose sound was
  // never drawn has no waveform.json: the pages ask for them and do without.
  // /favicon.ico is the browser's own question, which the hub has never
  // answered.
  const optional = (status, method, path) => status === 404 && method === 'GET' &&
    (/^\/books\/[^/]+\/[^/]+\/timings\.json$/.test(path) || /^\/mt\/[^/]+\/meta\.json$/.test(path) ||
     /^\/youtube\/videos\/[^/]+\/[^/]+\/waveform\.json$/.test(path) || path === '/favicon.ico');
  const allowed = new Set();
  async function open(url, name, ready) {
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(name + ' pageerror: ' + e.message));
    page.on('response', r => {
      const u = new URL(r.url());
      if (u.host !== `127.0.0.1:${port}` || r.status() < 400) return;
      if (optional(r.status(), r.request().method(), u.pathname)) allowed.add(r.status() + ' ' + u.pathname);
      else errors.push(name + ' ' + r.status() + ' ' + r.request().method() + ' ' + u.pathname);
    });
    page.on('console', m => {
      if (m.type() !== 'error') return;
      const at = (m.location() || {}).url || '';
      // a 404 let through above is counted there, and anything from outside
      // this machine was refused by this test, the offline world it lives in
      if (/^Failed to load resource/.test(m.text())) {
        let path = '';
        try { path = new URL(at).pathname; } catch (_) {}
        if (!at.startsWith(B) || optional(404, 'GET', path)) return;
      }
      errors.push(name + ' console: ' + m.text() + (at ? ' (' + at + ')' : ''));
    });
    page.on('requestfailed', r => {
      const u = new URL(r.url());
      if (u.host === `127.0.0.1:${port}`)
        errors.push(name + ' request failed: ' + r.method() + ' ' + u.pathname + ' (' + (r.failure() || {}).errorText + ')');
    });
    if (url) await page.goto(B + url);
    if (ready) await ready(page);
    return page;
  }
  const readerReady = page => page.waitForFunction(
    () => typeof SRC !== 'undefined' && window.Parseh && document.querySelector('.sub'), null, {timeout: 30000});
  const stay = page => page.evaluate(() => { window.__stay = 'never reloaded'; });
  const stayed = page => page.evaluate(() => window.__stay === 'never reloaded');
  const text = (page, sel) => page.evaluate(sel => { const e = document.querySelector(sel); return e ? e.textContent : null; }, sel);
  const clip = page => page.evaluate(() => navigator.clipboard.readText());
  const setClip = (page, s) => page.evaluate(s => navigator.clipboard.writeText(s), s);
  const SENTINEL = 'SENTINEL — not written by the page';
  // an answer PASTED: onto the clipboard, then Ctrl+V into the emptied box
  async function paste(page, answer) {
    await setClip(page, answer);
    await page.click('#rgans');
    await page.keyboard.press('Control+A');
    await page.keyboard.press('Delete');
    await page.keyboard.press('Control+V');
    await page.waitForFunction(a => document.querySelector('#rgans').value === a, answer, {timeout: 5000});
  }
  // NO DRAFT MARK: no element named for one, no word of one on the page as
  // read, and (a reader) nothing in what the build told the page
  const draftMarks = page => page.evaluate(() => ({
    els: [...document.querySelectorAll('[id*="draft" i], [class*="draft" i], [data-draft]')].map(e => e.outerHTML.slice(0, 80)),
    said: (document.body.innerText.match(/[^\n]*\bdrafts?\b[^\n]*/gi) || []),
    meta: typeof META !== 'undefined' && META && 'draft' in META,
  }));

  /* ---------------- the reader ---------------- */
  const row = n => '.pass.p2 .row[data-c="' + n + '"]';
  // every chunk row as a person reads it: its text (the readings drawn over
  // it left out), what stands under it, and a proposed reading if any
  const rowsOf = page => page.evaluate(() => [...document.querySelectorAll('.pass.p2 .row[data-c]')].map(r => {
    const f = r.querySelector('.fa').cloneNode(true);
    f.querySelectorAll('rt, rp').forEach(x => x.remove());
    const g = r.querySelector('.gl');
    const line = s => { const e = r.querySelector('.gl ' + s); return e ? e.textContent.replace(/\s+/g, ' ').trim() : ''; };
    return {c: +r.dataset.c, fa: f.textContent.replace(/\s+/g, ' ').trim(), gl: g ? g.textContent.replace(/\s+/g, ' ').trim() : null,
            kana: line('.kana'), tr: line('.tr'), en: line('.en'), voc: line('.voc'), seed: r.dataset.seed || ''};
  }));
  // the pencil over the row under the pointer, pressed: the chunk sheet
  async function openChunk(page, n) {
    await page.mouse.move(1, 1);
    await page.evaluate(async sel => {
      document.querySelector(sel).scrollIntoView({block: 'center'});
      await new Promise(r => setTimeout(r, 250));
    }, row(n));
    await page.hover(row(n));
    await page.waitForFunction(n => !document.querySelector('#chpen').hidden && penFor && +penFor.dataset.c === n, n);
    await page.click('#chpen');
    await page.waitForFunction(n => chOpen && chN === n, n);
  }
  const waitStat = (page, re) => page.waitForFunction(
    re => new RegExp(re).test(document.querySelector('#chstat').textContent), re.source, {timeout: 20000});
  const sheetBoxes = page => page.evaluate(() => Object.fromEntries(
    ['fa', 'kana', 'tr', 'voc', 'en'].map(f => [f, (document.getElementById('ch' + f) || {}).value])));
  // the region sheet's outline: a chapter opened all the way down, then a
  // sentence of it clicked (with Shift: the stretch to it)
  async function openOutline(page, ci) {
    const ch = page.locator('#rgbox .oltree > li.ol-ch').nth(ci);
    if ((await ch.getAttribute('aria-expanded')) === 'false') await ch.locator(':scope > .olr > .oltw').click();
    for (let guard = 0; guard < 60; guard++) {
      const shut = ch.locator('li[aria-expanded="false"]');
      if (!(await shut.count())) return ch;
      await shut.first().locator(':scope > .olr > .oltw').click();
    }
    throw Error('the outline would not open');
  }
  async function clickSentence(page, ci, label, shift) {
    const ch = await openOutline(page, ci);
    const esc = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const li = ch.locator('li.ol-s').filter({has: page.locator(':scope > .olr > .olk', {hasText: new RegExp('^' + esc + '$')})});
    eq(await li.count(), 1, `the outline has sentence ${label} in chapter ${ci + 1} once`);
    await li.locator(':scope > .olr').click(shift ? {modifiers: ['Shift']} : {});
  }
  const pick = page => page.evaluate(() => {
    const p = rgPicker && rgPicker.get();
    return p ? {lo: p.lo, hi: p.hi} : null;
  });
  // "copy the prompt", pressed with a sentinel on the clipboard -> what the
  // clipboard then holds, and the summary under the button
  async function copyBookPrompt(page, name) {
    await setClip(page, SENTINEL);
    await page.click('#rgcopy');
    await page.waitForFunction(() => {
      const t = document.querySelector('#rgsum').textContent;
      return t && !/^writing the prompt…/.test(t);
    }, null, {timeout: 20000});
    const prompt = await clip(page);
    if (prompt !== SENTINEL) await keepPrompt(name, prompt);
    // `said` is the LLM row's own line (lib/llmrow.js): that it reached the clipboard is its to say
    return {prompt, sum: await text(page, '#rgsum'), said: await text(page, '#rgcopysay')};
  }
  async function fillBook(page) {
    await page.click('#rgfill');
    await page.waitForFunction(() => {
      const t = document.querySelector('#rgreport').textContent;
      return !document.querySelector('#rgreprow').hidden && t && !/^(reading the answer|replacing)…/.test(t);
    }, null, {timeout: 30000});
    return text(page, '#rgreport');
  }
  const counts = s => (s.match(/filled \d+ · completed \d+ · replaced \d+/) || [s.slice(0, 160)])[0];

  /* ---------------- a) the books ---------------- */
  const libraryWas = [];
  for (const bk of BOOKS) {
    const words = bk.code !== 'fa' && B0.words[bk.code];
    console.log(`\na) ${bk.name} (${bk.code}): a book from its text${bk.code === 'fa' ? '' : words ? ', with the word lines this machine\'s analyzer proposes' : ', with NO analyzer installed: no word lines'}`);
    const bookDir = `${B0.root}/books/${bk.folder}/${bk.slug}`;
    const readerUrl = `/books/${bk.folder}/${bk.slug}/reader/`;

    /* "Make the draft" */
    const add = await open('/books/add/', bk.code + '-add', p => p.waitForSelector('#paths .path[data-path="new"]'));
    await add.click('#paths .path[data-path="new"]');
    await add.waitForFunction(() => !document.querySelector('#lane-new').hidden);
    await add.selectOption('#lang', bk.code);
    await add.selectOption('#gloss', 'en');
    await add.fill('#slug', '');
    await add.fill('#title', bk.title);
    await add.fill('#title_latin', bk.title_latin);
    await add.fill('#title_en', bk.title_en);
    await add.fill('#chtext', bk.text);
    eq(await add.evaluate(() => [document.querySelector('#how').value, document.querySelector('#mkempty').textContent,
                                 document.querySelector('#mkempty').disabled]),
       ['sentence', 'Make the draft', false],
       `${bk.code}: "Write it here, by hand" filled in -- one chunk per sentence, "Make the draft" can be pressed`);
    // The note under the slug names the directory "Make the draft" is about
    // to create, and follows the fields as they are typed on this way too.
    // It used to be brought up to date only when the language changed:
    // newbook.py's render() returned before its slugPreview() on every way
    // but the LLM's, so here -- the slug emptied, the title typed -- it went
    // on naming whatever the form held before (on a restored form, the
    // previous book's directory), and its "a book is already at … choose
    // another slug" could never come while the slug was being typed
    eq(await text(add, '#slugprev'), `will be created as books/${bk.folder}/${bk.slug}/`,
       `${bk.code}: the note under the slug names the directory the book is written to, as the title is typed`);
    await Promise.all([add.waitForURL(B + readerUrl, {timeout: 60000}), add.click('#mkempty')]);
    const page = add;
    await readerReady(page);
    await stay(page);
    assert(true, `${bk.code}: "Make the draft" wrote the book and opened its reader at ${readerUrl}`);
    const meta = JSON.parse(await Deno.readTextFile(bookDir + '/book.json'));
    eq([('draft' in meta), meta.language, meta.gloss, meta.title], [false, bk.code, 'en', bk.title],
       `${bk.code}: book.json has NO "draft" key, and says the language, the gloss language and the title`);
    const recs = await chunksOf(bookDir + '/ch1.tex');
    const sentences = Object.keys(bk.gloss);
    eq(recs.map(r => r.fa), sentences, `${bk.code}: the .tex holds the text as ${sentences.length} chunks, one per sentence`);
    const plain = words ? (bk.code === 'ja' ? 'chrw' : 'chw') : (bk.code === 'ja' ? 'chr' : 'ch');
    eq([...new Set(recs.map(r => r.macro))], [plain], `${bk.code}: each written as \\${plain}`);
    if (words) assert(recs.every(r => r.words && r.words.replace(/\([^)]*\)/g, '').replace(/ /g, '') === r.fa),
                      `${bk.code}: each with the word line the machine proposed (${JSON.stringify(recs[0].words)})`);
    // a reading equal to what wordline.seed proposes from the word line is
    // nobody's writing
    const seedField = words ? (bk.code === 'ja' ? 'kana' : 'tr') : '';
    assert(recs.every(r => ['kana', 'tr', 'voc', 'en'].every(f => f === seedField || !(r[f] || '').trim())),
           `${bk.code}: every gloss slot is empty${seedField ? ` but the ${seedField} proposed from the words` : ''}`);
    const marks = await draftMarks(page);
    eq(marks, {els: [], said: [], meta: false}, `${bk.code}: the reader carries no draft mark -- no element, no word, nothing in META`);
    let rows = await rowsOf(page);
    eq(rows.map(r => r.fa), sentences, `${bk.code}: the reader has a row for every chunk, with its text`);
    assert(rows.every((r, k) => !r.en && !r.voc && (seedField ? (r.seed === (recs[k][seedField] || '') && r.seed !== '') : (!r.gl && !r.seed))),
           `${bk.code}: and every row is blank -- no meaning, no vocabulary${seedField ? `; only the ${seedField} the words proposed, which the row marks as a proposal (data-seed)` : ', nothing under the text'}` +
           (rows.every((r, k) => !r.en && !r.voc && (seedField ? r.seed === (recs[k][seedField] || '') && r.seed !== '' : !r.gl && !r.seed)) ? '' : ': ' + JSON.stringify(rows)));
    eq(await page.evaluate(() => SRC.map(s => [s[1], s[2] || '', s[3] || '', s[4] || '', s[5] || ''])),
       recs.map(r => [r.fa, r.kana || '', r.tr || '', '', '']),
       `${bk.code}: what the page holds for its sheets is the same${seedField ? ' -- the proposal and nothing else' : ', every gloss empty'}`);

    // the library page lists the book, with no draft mark on it
    const lib = await open('/books/', bk.code + '-library', p => p.waitForSelector('a.book'));
    const card = await lib.evaluate(slug => {
      const a = [...document.querySelectorAll('a.book')].find(x => (x.getAttribute('href') || '').includes('/' + slug + '/'));
      return a ? a.innerText.replace(/\s+/g, ' ').trim() : null;
    }, bk.slug);
    assert(card && card.includes(bk.title), `${bk.code}: the library page lists it: ${JSON.stringify(card)}`);
    eq(await draftMarks(lib), {els: [], said: [], meta: false}, `${bk.code}: the library page carries no draft mark`);
    libraryWas.push(bk.slug);
    eq(await lib.evaluate(slugs => slugs.map(s => [...document.querySelectorAll('a.book')].some(a => (a.getAttribute('href') || '').includes('/' + s + '/'))), libraryWas),
       libraryWas.map(() => true), `${bk.code}: (every book made so far is on it)`);
    await lib.close();

    /* a blank chunk's sheet; the meaning alone; delete gloss */
    const n = 0, r0 = recs[n];
    await openChunk(page, n);
    const bx = await sheetBoxes(page);
    eq([bx.fa, bx.tr || '', bx.voc, bx.en, bk.code === 'ja' ? bx.kana : ''],
       [r0.fa, seedField === 'tr' ? r0.tr : '', '', '', seedField === 'kana' ? r0.kana : ''],
       `${bk.code}: a blank chunk's sheet opens on it: its text, every gloss box empty${seedField ? ` but the proposed ${seedField}` : ''}`);
    eq(await page.evaluate(() => [!document.querySelector('#chdel').hidden, document.querySelector('#chdel').disabled,
                                  document.querySelector('#chundo').hidden]),
       [true, true, true], `${bk.code}: "delete gloss" is there but greyed out -- there is no gloss to delete -- and no undo`);
    const meaning = bk.gloss[r0.fa].en;
    await page.fill('#chen', meaning);
    await page.click('#chsave');
    await waitStat(page, /^saved en/);
    const half = (await chunksOf(bookDir + '/ch1.tex'))[n];
    eq([half.fa, half.en, half.voc, half.tr, half.kana || ''],
       [r0.fa, meaning, '', seedField === 'tr' ? r0.tr : '', seedField === 'kana' ? r0.kana : ''],
       `${bk.code}: the meaning typed alone is saved -- the .tex holds it and nothing else was written`);
    let batch = await batchOf(bookDir);
    const p0 = batch.find(b => b.ch === 1 && b.idx === 0);
    if (seedField === 'tr') {
      // Chinese: the pinyin proposed from the words counts as the chunk's own
      // once anything else is written -- the chunk is complete
      assert(p0.rc === 0 && errorCount(p0.out)[0] === 0,
             `${bk.code}: check_batch has nothing against it -- the proposed pinyin counts once the chunk is written, so the meaning completes it (${JSON.stringify(p0.out.trim().split('\n').pop())})`);
    } else {
      assert(p0.rc === 1 && errorCount(p0.out)[0] === 1 && p0.out.includes(`ERROR empty tr for '${r0.fa}'`),
             `${bk.code}: it is half glossed, legal by hand -- check_batch lists it as its one error: ${JSON.stringify((p0.out.match(/ERROR[^\n]*/) || [''])[0])}`);
    }
    assert(countNote.test(p0.out) && p0.out.match(countNote)[1] === String(p0.chunks - 1),
           `${bk.code}: and counts the other ${p0.chunks - 1} as having no gloss yet: ${JSON.stringify((p0.out.match(countNote) || [''])[0])}`);
    rows = await rowsOf(page);
    eq(rows[n].en, meaning, `${bk.code}: the row shows the meaning under the text`);
    eq(await page.evaluate(() => [document.querySelector('#chdel').disabled, document.querySelector('#chundo').hidden]),
       [false, true], `${bk.code}: "delete gloss" is offered now`);
    await page.click('#chdel');
    await waitStat(page, /^gloss deleted/);
    await page.waitForFunction(() => !document.querySelector('#chundo').hidden);
    eq(await page.evaluate(() => [document.querySelector('#chundo').textContent, document.querySelector('#chdel').disabled]),
       ['undo delete', true], `${bk.code}: "delete gloss" takes it off, and "undo delete" is offered`);
    const gone = (await chunksOf(bookDir + '/ch1.tex'))[n];
    eq([gone.macro, gone.fa, gone.kana || '', gone.tr, gone.voc, gone.en, gone.words || ''],
       [r0.macro, r0.fa, '', '', '', '', r0.words || ''],
       `${bk.code}: the .tex holds the same \\${r0.macro} with every gloss slot empty${r0.words ? ', the word line kept' : ''}`);
    batch = await batchOf(bookDir);
    assert(batch.every(b => b.rc === 0 && errorCount(b.out)[0] === 0 && b.out.match(countNote) &&
                            b.out.match(countNote)[1] === String(b.chunks) && b.out.match(countNote)[2] === String(b.chunks)),
           `${bk.code}: check_batch on every paragraph: 0 errors, and one note each: ${batch.map(b => JSON.stringify(b.out.match(countNote)[0])).join(', ')}`);
    await page.click('#chcancel');
    await page.waitForFunction(() => !chOpen);

    /* the header's "gloss with an LLM": the whole book */
    await page.click('#rgn');
    await page.waitForFunction(() => rgShown);
    const S = await page.evaluate(() => SUBS.map(s => [s[2], String(s[5])]));
    await clickSentence(page, S[0][0], S[0][1], false);
    await clickSentence(page, S[S.length - 1][0], S[S.length - 1][1], true);
    eq(await pick(page), {lo: 0, hi: S.length - 1}, `${bk.code}: the header's "gloss with an LLM", a click on ${S[0][1]} and a shift-click on ${S[S.length - 1][1]}: the whole book picked`);
    const {prompt, sum, said} = await copyBookPrompt(page, bk.code + '-book');
    assert(prompt !== SENTINEL && prompt.length > 1000, `${bk.code}: "copy the prompt" put the prompt on the clipboard (${prompt.length} characters)`);
    assert(prompt.includes(`- language: ${bk.name} (\`${bk.code}\`)`) && prompt.includes('- gloss language: **English** (`en`)') &&
           new RegExp(`^Parseh prompt · [^\\n]+\\n\\n# Gloss part of an? ${bk.name} book, in English, for Parseh`).test(prompt),
           `${bk.code}: the prompt is for a ${bk.name} book glossed in English: ${JSON.stringify(prompt.split('\n')[0])}`);
    const data = dataOf(prompt);
    const all = data.sentences.flatMap(s => s.chunks);
    eq(all.map(c => c.fa), sentences, `${bk.code}: its data holds every chunk of the book, divided as the .tex divides it`);
    eq(all.map(c => c.todo), sentences.map(() => true), `${bk.code}: every one of them todo`);
    assert(all.every(c => !c.en && !c.voc), `${bk.code}: none carrying a meaning or a vocabulary line`);
    if (words) assert(all.every((c, k) => c.words === recs[k].words), `${bk.code}: each with its word line, read-only`);
    assert(new RegExp(`${sentences.length} chunks, ${sentences.length} to gloss(?!, [1-9])`).test(sum) && /^copied/.test(said),
           `${bk.code}: the sheet says what it copied: ${JSON.stringify(sum.replace(/\s*\n\s*/g, ' | '))}`);

    /* the answer, as an LLM writes it */
    const answer = structuredClone(data);
    for (const s of answer.sentences) for (const c of s.chunks) {
      delete c.todo;
      const g = bk.gloss[c.fa];
      for (const f of GLOSS) if (g[f] !== undefined) c[f] = g[f];
    }
    await paste(page, 'Here is the JSON with every todo chunk glossed:\n\n' + fence(answer));
    const rep = await fillBook(page);
    eq(counts(rep), `filled ${sentences.length} · completed 0 · replaced 0`, `${bk.code}: "fill from the answer" reports filled ${sentences.length}`);
    eq(await page.evaluate(() => document.querySelectorAll('#rgreport details').length), 0, `${bk.code}: nothing kept, dropped or unanswered`);
    rows = await rowsOf(page);
    eq(rows.map(r => [r.fa, r.tr, r.en, r.kana]), sentences.map(s => [s, bk.gloss[s].tr, bk.gloss[s].en, bk.code === 'ja' ? bk.gloss[s].kana : '']),
       `${bk.code}: every row shows its gloss under its text`);
    assert(rows.every(r => r.voc && !r.seed), `${bk.code}: with its vocabulary line, and no reading left marked a proposal`);
    assert(await stayed(page), `${bk.code}: with no reload`);
    const done = await chunksOf(bookDir + '/ch1.tex');
    eq(done.map(r => [r.fa, r.kana || '', r.tr, r.voc, r.en]),
       sentences.map(s => [s, bk.code === 'ja' ? bk.gloss[s].kana : '', bk.gloss[s].tr, bk.gloss[s].voc, bk.gloss[s].en]),
       `${bk.code}: the .tex on disk carries exactly what the answer wrote`);
    eq([...new Set(done.map(r => r.macro))], [plain], `${bk.code}: every chunk still a \\${plain}${words ? ', its word line kept' : ''}`);
    if (words) eq(done.map(r => r.words), recs.map(r => r.words), `${bk.code}: the word lines as the machine proposed them`);
    let v = await verifyBook(bookDir);
    assert(v.code === 0 && / 0 mismatched/.test(v.out), `${bk.code}: verify_book: ${v.out.split('\n').pop().replace(/^.*\]: /, '')}`);
    batch = await batchOf(bookDir);
    assert(batch.length === 2 && batch.every(b => b.rc === 0 && errorCount(b.out)[0] === 0 && !countNote.test(b.out)),
           `${bk.code}: check_batch on both paragraphs: ${batch.map(b => `ch${b.ch} p${b.idx} ${JSON.stringify(b.out.trim().split('\n').filter(l => /errors?, \d+ warnings?|FIDELITY/.test(l)).join(' / '))}`).join('; ')} -- no count note`);
    await page.click('#rgclose');
    await page.waitForFunction(() => !rgShown);
    await page.close();

    /* more text: the last chapter, then a new one */
    for (const where of ['last', 'new']) {
      const more = where === 'last' ? bk.more : bk.chapter2;
      const ap = await open('/books/add/', bk.code + '-append-' + where, p => p.waitForSelector('#paths .path[data-path="extend"]'));
      assert(await ap.evaluate(() => !document.querySelector('#card-extend').hidden), `${bk.code}: /books/add/ offers "Add to a book already here"`);
      await ap.click('#paths .path[data-path="extend"]');
      await ap.waitForFunction(() => !document.querySelector('#lane-extend').hidden);
      const into = `/books/${bk.folder}/${bk.slug}`;
      await ap.selectOption('#addinto', into);
      await ap.check(where === 'last' ? '#addwhere_last' : '#addwhere_new');
      await ap.fill('#aptext', more);
      eq(await ap.evaluate(() => [document.querySelector('#aptext').getAttribute('lang'), document.querySelector('#ahow').value,
                                  document.querySelector('#addto').disabled]),
         [bk.code, 'sentence', false], `${bk.code}: the book chosen, "${where === 'last' ? 'More of the last chapter' : 'A new chapter'}", the text in its language, "Add it" can be pressed`);
      await ap.click('#addto');
      await ap.waitForFunction(() => !document.querySelector('#addresult').hidden, null, {timeout: 60000});
      const said = (await text(ap, '#addresult')).replace(/\s+/g, ' ').trim();
      const nSent = more.split(/(?<=[.。！？?؟])\s*/).filter(Boolean).length;
      assert(new RegExp(`^Added\\. 1 paragraphs, ${nSent} sentences, ${nSent} blank chunks, ` +
                        (where === 'last' ? 'onto the end of chapter 1\\.' : 'as chapter 2\\.')).test(said) &&
             !(await ap.evaluate(() => !!document.querySelector('#addresult .note.bad, #addresult .note.warn'))),
             `${bk.code}: the page says so, and nothing went wrong: ${JSON.stringify(said.slice(0, 110))}`);
      await ap.close();
    }
    const meta2 = JSON.parse(await Deno.readTextFile(bookDir + '/book.json'));
    assert(!('draft' in meta2), `${bk.code}: book.json still has no "draft" key`);
    const c1 = await chunksOf(bookDir + '/ch1.tex'), c2 = await chunksOf(bookDir + '/ch2.tex');
    eq(c1.slice(0, sentences.length).map(r => [r.fa, r.tr, r.en]), done.map(r => [r.fa, r.tr, r.en]),
       `${bk.code}: the glossed chunks of chapter 1 are as they were`);
    const fresh = [...c1.slice(sentences.length), ...c2];
    assert(fresh.length >= 3 && fresh.every(r => !r.voc && !r.en && GLOSS.every(f => f === seedField || !(r[f] || '').trim())),
           `${bk.code}: the ${fresh.length} chunks added arrive blank: ${JSON.stringify(fresh.map(r => r.fa))}`);
    v = await verifyBook(bookDir);
    assert(v.code === 0 && / 0 mismatched/.test(v.out), `${bk.code}: verify_book: ${v.out.split('\n').pop().replace(/^.*\]: /, '')}`);
    batch = await batchOf(bookDir);
    eq(batch.map(b => [b.ch, b.idx, b.rc, errorCount(b.out)[0], (b.out.match(countNote) || []).slice(1).join(' of ')]),
       [[1, 0, 0, 0, ''], [1, 1, 0, 0, ''], [1, 2, 0, 0, `${c1.length - sentences.length} of ${c1.length - sentences.length}`],
        [2, 0, 0, 0, `${c2.length} of ${c2.length}`]],
       `${bk.code}: check_batch: 0 errors on every paragraph, and the count note only on the two added, which are all blank`);
    // the reader, opened again: the glossed rows and the blank ones
    const again = await open(readerUrl, bk.code + '-reader-again', readerReady);
    // chapter 2 travels in a file of its own (reader/ch-1.html), fetched as
    // it comes near the window -- which, after a chapter this short, it
    // already is: read on to the end of the book, as a person does, and it
    // has arrived
    await again.keyboard.press('End');
    await again.waitForFunction(() => !document.querySelector('section.chapter[data-part]'), null, {timeout: 20000});
    rows = await rowsOf(again);
    eq(rows.map(r => r.fa), [...c1, ...c2].map(r => r.fa), `${bk.code}: the reader, opened again, has a row for every chunk of both chapters`);
    assert(rows.slice(0, sentences.length).every(r => r.en) && rows.slice(sentences.length).every(r => !r.en && !r.voc),
           `${bk.code}: the glossed ones with their meanings, the added ones blank`);
    eq(await draftMarks(again), {els: [], said: [], meta: false}, `${bk.code}: and no draft mark on it`);
    await again.close();
  }

  /* ---------------- b) the video ---------------- */
  console.log('\nb) Persian (fa): a video from its transcript, started empty');
  {
    const vdir = `${B0.root}/youtube/videos/persian/${VIDEO.id}`;
    const asked = [];
    const nAsked = abroad.length;
    const add = await open(null, 'yt-add');
    add.on('request', r => { const u = new URL(r.url()); asked.push((u.host === `127.0.0.1:${port}` ? '' : u.host) + u.pathname); });
    await add.goto(B + '/youtube/add/');
    await add.waitForSelector('#q1 .path[data-src="yt"]');
    await add.click('#q1 .path[data-src="yt"]');
    await add.click('#q2 .path[data-by="empty"]');
    await add.waitForFunction(() => !document.querySelector('#vbody').hidden && !document.querySelector('#step-empty-3').hidden);
    await add.fill('#url', VIDEO.id);
    await add.selectOption('#lang', VIDEO.code);
    await add.selectOption('#gloss', 'en');
    await add.fill('#transcript', VIDEO.transcript);
    eq(await add.evaluate(() => [document.querySelector('#empty').textContent, document.querySelector('#how').value]),
       ['Start it empty', 'sentence'], '"From YouTube" with a bare id, "Nobody — I gloss it in the player": "Start it empty", one chunk per sentence');
    // SPEECH TO TEXT IS OPTIONAL, and here there is none: the block is a way to set it up
    // and nothing else, and the page asked the computer that one thing and no one anything
    await add.waitForFunction(() => { const s = document.getElementById('stt'); return s && !s.hidden; });
    eq(await add.evaluate(() => [document.getElementById('stt').getAttribute('data-state'),
         [...document.querySelectorAll('#stt button, #stt select, #stt a[href]')].filter(e => e.getClientRects().length && !e.disabled).map(e => e.id)]),
       ['absent', ['stt_setup']], 'no speech to text: the page offers the way to set it up, and no button or picker that would do nothing');
    // (a0.4.3: opening the page lists the reviews saved for later, so that Videos can offer to continue one: a read
    // from the disk that starts nothing and sends nothing)
    eq(asked.filter(x => /transcribe(?!\/pending)|huggingface|pypi/.test(x)), [], 'and it touched no transcription route, and fetched nothing of a model');
    eq(abroad.slice(nAsked), [], 'the add page asked nothing of the network, only the computer what it has');
    eq(asked.filter(x => /^\/lookup\/api\//.test(x)), ['/lookup/api/speech'], 'and the one thing it asked was that');
    const nAbroad = abroad.length;
    // YouTube could not be reached for the title and the channel (TO-DO 7.6): the page stays, says so and how
    // to fill them later, and the player is a click away
    await add.click('#empty');
    await add.waitForSelector('#fetchnote', {timeout: 60000});
    const fetchSaid = await add.textContent('#fetchnote');
    assert(/YouTube could not be reached/.test(fetchSaid) && /video info/.test(fetchSaid),
           'no network: "Start it empty" says the title and the channel were not fetched, and where to fill them: ' + fetchSaid);
    await Promise.all([add.waitForURL(B + `/youtube/v/${VIDEO.id}/`, {timeout: 60000}),
                       add.click('#eresult a[href*="/youtube/v/"]')]);
    const page = add;
    await page.waitForSelector('#segs .seg .fa .w');
    await page.waitForFunction(() => window.__yt && document.querySelector('#novid').hidden);
    await stay(page);
    assert(true, `"Start it empty" wrote the video and opened its player at /youtube/v/${VIDEO.id}/`);
    eq(abroad.slice(nAbroad), [],
       'the pages asked nothing of the network on the way (the player\'s own YouTube frame is this test\'s stub)');
    const vmeta = JSON.parse(await Deno.readTextFile(vdir + '/video.json'));
    eq([('draft' in vmeta), vmeta.id, vmeta.language, vmeta.gloss], [false, VIDEO.id, 'fa', 'en'],
       'video.json has NO "draft" key, and says the id, the language and the gloss language');
    // the bare id typed in the URL box is written as the address it names,
    // as the LLM road (ytpages.api_add) writes it -- not as the id alone,
    // in the one field a person opens to find the source
    eq(vmeta.url, 'https://www.youtube.com/watch?v=' + VIDEO.id,
       'video.json\'s url is the watch URL of the bare id typed, as the LLM road writes it');
    eq([vmeta.title, vmeta.channel], [VIDEO.id, 'Unknown channel'],
       'and nothing was fetched for it: the title is the id and the channel unknown, as this road writes them with no network');
    let ann = JSON.parse(await Deno.readTextFile(vdir + '/annotations.json'));
    const phrases = ann.segments.flatMap((sg, i) => (sg.chunks || []).map((ch, j) => [i, j, ch]));
    eq(ann.segments.map(sg => sg.plain ? 'plain' : sg.chunks.map(ch => ch.fa)),
       ['plain', ['سلام، حال شما چطور است؟'], ['من خوبم، ممنون.', 'شما چطورید؟'], ['امروز هوا خیلی خوب است.']],
       'annotations.json: the English line plain, every Persian caption cut one chunk per sentence');
    assert(phrases.every(([, , ch]) => GLOSS.every(f => !(ch[f] || '').trim())), `every one of the ${phrases.length} chunks has an empty gloss`);
    eq(await page.evaluate(() => [!!window.YTFRANK.help, !!document.querySelector('#draft')]), [false, false],
       'no dictionary, corpus or model is installed, and there is no draft badge');
    eq(await draftMarks(page), {els: [], said: [], meta: false}, 'the player carries no draft mark anywhere');

    // the player's own helpers, as tests/gloss_llm_video.mjs has them
    const W = (i, j) => `#segs .seg[data-i="${i}"] .fa .w[data-j="${j}"]`;
    const away = async () => {
      await page.mouse.move(1, 1);
      await page.waitForFunction(() => document.querySelector('#cloud').hidden ||
                                       document.querySelector('#cloud').classList.contains('editing'));
    };
    async function point(i, what, j) {
      await page.evaluate(i => {
        const seg = document.querySelector(`#segs .seg[data-i="${i}"]`), r = seg.getBoundingClientRect();
        const top = document.querySelector('#playerwrap').getBoundingClientRect().bottom;
        scrollBy({top: r.top + r.height / 2 - (top + innerHeight) / 2, behavior: 'instant'});
      }, i);
      await sleep(120);
      const p = await page.evaluate(([i, what, j]) => {
        const seg = document.querySelector(`#segs .seg[data-i="${i}"]`);
        const panel = document.querySelector('#rgpanel');
        const pr = panel.hidden ? null : panel.getBoundingClientRect();
        const under = (x, y) => pr && x >= pr.left - 2 && x <= pr.right + 2 && y >= pr.top - 2 && y <= pr.bottom + 2;
        const els = what === 'phrase' ? [seg.querySelector(`.fa .w[data-j="${j}"]`)] : [seg.querySelector('.fa, .en-line')];
        for (const el of els) for (const r of el.getClientRects()) {
          const ys = [r.top + r.height / 2, r.top + 4, r.bottom - 4];
          const xs = [];
          for (let d = 0; d < r.width / 2; d += 3) xs.push(r.left + r.width / 2 + d, r.left + r.width / 2 - d);
          for (const y of ys) for (const x of xs) {
            if (under(x, y) || x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
            const hit = document.elementFromPoint(x, y);
            if (!hit || !seg.contains(hit)) continue;
            if (what === 'phrase' ? hit.closest('.w') !== els[0] : (hit.closest('.w') || !hit.closest('.fa, .en-line'))) continue;
            return {x, y};
          }
        }
        return null;
      }, [i, what, j]);
      if (!p) throw Error(`FAIL: no reachable point on caption ${i} (${what})`);
      return p;
    }
    async function hover(i, j) {
      for (let tries = 0; ; tries++) {
        await away();
        const p = await point(i, 'phrase', j);
        await page.mouse.move(p.x, p.y);
        try {
          await page.waitForFunction(sel => {
            const c = document.querySelector('#cloud'), w = document.querySelector(sel);
            return !c.hidden && w && w.classList.contains('hot');
          }, W(i, j), {timeout: 3000});
          return;
        } catch (e) {
          if (tries >= 2) throw e;
        }
      }
    }
    const cloudSays = () => page.evaluate(() => {
      const c = document.querySelector('#cloud'), t = s => { const e = c.querySelector(s); return e ? e.textContent.trim() : null; };
      return {unwritten: t('.unwritten'), tr: t('.tr'), en: t('.en'), edit: !!c.querySelector('.mkedit')};
    });
    const vboxes = () => page.evaluate(() => Object.fromEntries(
      [...document.querySelectorAll('#cloud .ef')].map(el => [el.dataset.f, el.value])));
    const vstat = re => page.waitForFunction(
      re => new RegExp(re).test((document.querySelector('#cloud .cstat') || {}).textContent || ''), re.source, {timeout: 20000});
    async function openEdit(i, j) {
      await hover(i, j);
      await page.click('#cloud .mkedit');
      await page.waitForFunction(w => {
        const c = document.querySelector('#cloud');
        return c.classList.contains('editing') && (c.querySelector('.ewhere') || {}).textContent === w;
      }, `segment ${i} chunk ${j}`);
    }
    async function closeEdit() {
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.querySelector('#cloud').classList.contains('editing'));
    }
    async function type(f, value) {
      await page.click(`#cloud .ef[data-f="${f}"]`);
      await page.keyboard.press('Control+A');
      await page.keyboard.press('Delete');
      if (value) await page.keyboard.insertText(value);
    }
    const annNow = async () => JSON.parse(await Deno.readTextFile(vdir + '/annotations.json'));

    /* every phrase hoverable, and ✎ */
    for (const [i, j, ch] of phrases) {
      await hover(i, j);
      const c = await cloudSays();
      eq([c.unwritten, c.en, c.edit], ['nothing glossed yet', null, true],
         `segment ${i} chunk ${j} «${ch.fa}»: a phrase, hovered, its cloud says "nothing glossed yet" and offers ✎`);
      await page.click('#cloud .mkedit');
      await page.waitForFunction(() => document.querySelector('#cloud').classList.contains('editing'));
      const b = await vboxes();
      eq([await text(page, '#cloud .ewhere'), b.fa, b.tr, b.voc, b.en], [`segment ${i} chunk ${j}`, ch.fa, '', '', ''],
         `segment ${i} chunk ${j}: ✎ opens the form on it, its text in the first box and every gloss box empty`);
      await closeEdit();
    }

    /* one filled by hand, the meaning alone */
    const [hi, hj] = phrases.find(([, , ch]) => ch.fa === VIDEO.hand.fa);
    await openEdit(hi, hj);
    await type('en', VIDEO.hand.en);
    await page.click('#cloud .esave');
    await vstat(/^saved ✓/);
    ann = await annNow();
    const handCh = ann.segments[hi].chunks[hj];
    eq([handCh.fa, handCh.en, handCh.tr || '', handCh.voc || ''], [VIDEO.hand.fa, VIDEO.hand.en, '', ''],
       `segment ${hi} chunk ${hj}: the meaning typed alone is saved -- half glossed, legal by hand`);
    await closeEdit();
    let cv = await checkVideo(vdir);
    assert(cv.code === 1 && (cv.out.match(/^ERROR/gm) || []).length === 1 && /ERROR: [^\n]*missing 'tr'/.test(cv.out),
           `check_annotations lists the half-glossed chunk as its one error: ${JSON.stringify((cv.out.match(/ERROR[^\n]*/) || [''])[0])}`);
    assert(/note: 3 of 4 chunks have no gloss yet/.test(cv.out), `and counts the other three: ${JSON.stringify((cv.out.match(/note: \d+ of[^\n]*/) || [''])[0])}`);

    /* the region panel: the first caption and the last */
    await away();
    await page.click('#rgn');
    await page.waitForFunction(() => !document.querySelector('#rgpanel').hidden);
    const last = ann.segments.length - 1;
    for (const i of [0, last]) {
      await away();
      const p = await point(i, 'line');
      await page.mouse.click(p.x, p.y);
    }
    const clock = s => Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0');
    eq(await page.evaluate(() => [document.querySelector('#rgfrom').textContent, document.querySelector('#rgto').textContent]),
       [`caption 0, ${clock(ann.segments[0].start)}`, `caption ${last}, ${clock(ann.segments[last].start)}`],
       `the panel: a click on the first caption and one on the last pick the whole video`);
    await setClip(page, SENTINEL);
    await page.click('#rgcopy');
    await page.waitForFunction(() => {
      const t = document.querySelector('#rgsum').textContent;
      return t && !/^making the prompt…/.test(t) && !document.querySelector('#rgcopy').disabled;
    }, null, {timeout: 20000});
    const prompt = await clip(page);
    const sum = await text(page, '#rgsum');
    const said = await text(page, '#rgcopysay');
    assert(prompt !== SENTINEL && prompt.length > 1000, `"copy the prompt" put the prompt on the clipboard (${prompt.length} characters)`);
    await keepPrompt('fa-video', prompt);
    assert(/^Parseh prompt · [^\n]+\n\n# Gloss part of a Persian video, in English, for Parseh/.test(prompt),
           `the prompt is for a Persian video glossed in English: ${JSON.stringify(prompt.split('\n')[0])}`);
    const data = dataOf(prompt);
    eq(data.captions.map(c => c.plain ? 'plain' : c.chunks.map(ch => [ch.fa, ch.todo || false])),
       ['plain', [['سلام، حال شما چطور است؟', true]], [['من خوبم، ممنون.', true], ['شما چطورید؟', true]], [[VIDEO.hand.fa, false]]],
       'its data: every caption, the plain one as context, every blank chunk todo, the one glossed by hand not');
    eq(data.captions[last].chunks[0].en, VIDEO.hand.en, 'the one glossed by hand sent with the meaning somebody wrote');
    assert(/4 chunks, 3 to gloss, 1 glossed sent as context/.test(sum) && /^copied/.test(said),
           `the panel says what it copied: ${JSON.stringify(sum.split('\n').slice(0, 2).join(' | '))}`);
    const answer = structuredClone(data);
    for (const c of answer.captions) for (const ch of c.chunks || []) {
      if (!ch.todo) continue;
      delete ch.todo;
      Object.assign(ch, VIDEO.gloss[ch.fa]);
    }
    await paste(page, fence(answer));
    await page.evaluate(() => [...document.querySelectorAll('#segs .seg')].forEach(el => { el.__mark = 'line ' + el.dataset.i; }));
    await page.click('#rgfill');
    await page.waitForFunction(() => {
      const t = document.querySelector('#rgreport').textContent;
      return t && !/^(reading the answer|replacing)…/.test(t) && !document.querySelector('#rgfill').disabled;
    }, null, {timeout: 30000});
    const tally = await page.evaluate(() => {
      const b = document.querySelector('#rgreport'), t = b.querySelector('.rgtally');
      return {tally: t ? t.textContent : b.textContent, lists: b.querySelectorAll('ul').length};
    });
    eq([counts(tally.tally), tally.lists], ['filled 3 · completed 0 · replaced 0', 0],
       '"fill from the answer": filled 3, and nothing kept, dropped or unanswered');
    const fresh = await page.evaluate(() => [...document.querySelectorAll('#segs .seg')].filter(el => !el.__mark).map(el => +el.dataset.i));
    eq(fresh, [1, 2], 'the two captions it wrote are drawn again, and no other');
    assert(await stayed(page), 'with no reload');
    for (const [i, j, ch] of phrases.filter(([, , ch]) => VIDEO.gloss[ch.fa])) {
      await hover(i, j);
      const c = await cloudSays();
      eq([c.unwritten, c.tr, c.en], [null, VIDEO.gloss[ch.fa].tr, VIDEO.gloss[ch.fa].en], `segment ${i} chunk ${j}: its cloud shows the answer's gloss`);
    }
    ann = await annNow();
    eq(ann.segments.flatMap(sg => (sg.chunks || []).map(ch => [ch.fa, ch.tr || '', ch.voc || '', ch.en || ''])),
       phrases.map(([, , ch]) => VIDEO.gloss[ch.fa] ? [ch.fa, VIDEO.gloss[ch.fa].tr, VIDEO.gloss[ch.fa].voc, VIDEO.gloss[ch.fa].en]
                                                    : [ch.fa, '', '', VIDEO.hand.en]),
       'annotations.json on disk carries the answer, and the meaning typed by hand');
    cv = await checkVideo(vdir);
    assert(cv.code === 1 && (cv.out.match(/^ERROR/gm) || []).length === 1 &&
           new RegExp(`ERROR: segment ${hi} \\(start [^)]*\\) chunk ${hj}: missing 'tr'`).test(cv.out) && !/have no gloss yet/.test(cv.out),
           `check_annotations: its one error the chunk left half glossed on purpose, and no count note: ${JSON.stringify((cv.out.match(/ERROR[^\n]*/) || [''])[0])}`);
    await page.click('#rgclose');
    await page.waitForFunction(() => document.querySelector('#rgpanel').hidden);

    /* the half-glossed one completed by hand */
    await openEdit(hi, hj);
    await type('tr', VIDEO.hand.tr);
    await page.click('#cloud .esave');
    await vstat(/^saved ✓/);
    await closeEdit();
    cv = await checkVideo(vdir);
    assert(cv.code === 0 && !/ERROR/.test(cv.out) && !/have no gloss yet/.test(cv.out) && /0 error\(s\)/.test(cv.out),
           `its transliteration typed in: check_annotations exits 0: ${JSON.stringify(cv.out.split('\n').pop())}`);
    const vmeta2 = JSON.parse(await Deno.readTextFile(vdir + '/video.json'));
    assert(!('draft' in vmeta2), 'video.json still has no "draft" key');
    await page.close();
  }

  /* ---------------- c) ---------------- */
  console.log('\nc) what the pages and the hub said');
  console.log('  (refused as expected: ' + [...allowed].join(', ') + ')');
  if (abroad.length) console.log('  (asked of the network, and refused by this test: ' + [...new Set(abroad)].join(', ') + ')');
  assert(!errors.length, 'no page threw, logged an error or had a request refused: ' + errors.join('; '));
  const tb = log.join('');
  assert(!/Traceback/.test(tb), 'no traceback in the hub\'s log');
  const ownAfter = JSON.parse(await py(OWN, TMP));
  eq(ownAfter.leaks, [], 'nothing of this run\'s tree was remembered in the owner\'s config/digests.json or wheres.json');
  eq(ownAfter.digests, ownBefore.digests, 'the owner\'s config/, books/ (its library page included), youtube/videos/ and the fixtures are untouched');
  console.log(`\ndraft_end_to_end: ${passed} checks passed`);
} finally {
  if (errors.length) console.log('what the pages said:\n  ' + errors.join('\n  '));
  if (browser) await browser.close();
  if (hub) { try { hub.kill('SIGTERM'); await hub.status; } catch (_) {} }
  if (!Deno.env.get('PARSEH_KEEP')) await Deno.remove(TMP, {recursive: true}).catch(() => {});
  else console.log('kept ' + TMP);
}
