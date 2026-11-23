// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — the service worker of the mobile interface (docs/mobile.md, §19).
   Served by serve.py at /sw.js, so that its scope is the whole toolbox;
   registered by lib/parseh.js and by the studio's pages while the mode is
   mobile.

   IT USED TO KEEP NOTHING.  Parseh is a server on somebody's own computer,
   and every page came from there, fresh; the worker existed because a browser
   installs only a site that has one, and answered a page of its own when the
   computer could not be reached.  §19 reverses that: what has been KEPT ON
   THIS PHONE is answered from the phone, so a book, a video, a document or a
   deck works with the computer asleep, off or a train away.

   WHAT IS KEPT, AND WHERE.  One cache per thing -- `parseh-kept-<id>` -- so
   that removing a book is deleting one cache, and two books share nothing but
   the shared files (`parseh-shared`), which are kept once for all of them.
   The page decides what goes in: it asks the computer what a thing is made of
   (`<thing>/__offline`, lib/offline.py) and sends the list here (lib/keep.js).

   AND A BOOK MAY ARRIVE BY THE BROWSER'S OWN DOWNLOAD (the owner's decision
   of 2026-09-23).  Where the page's registration has Background Fetch -- on
   Android -- lib/keep.js hands a book to it rather than to `keep` here, since
   a browser stops this worker's event after five minutes and a narration
   does not arrive inside that; this file then only PUTS IT AWAY when the
   browser wakes it (`settle`, near the end of the keeping half).  The iPad
   and Firefox keep by `keep`, exactly as before.

   WHICH COPY ANSWERS: THE KEPT ONE (the owner's choice, 2026-09-22).  A page
   opens at once, with no wait for a computer that may be asleep, and what is
   newer is found behind it -- the small parts of a kept thing are fetched
   again in the background and put back in the cache, so the next open has
   them.  Anything not kept goes to the network exactly as it did, and a
   NAVIGATION that fails is answered with the offline page.

   THE APP MUST OPEN AT ALL (the owner's 1 and 2, 2026-09-23; TO-DO §0).  It
   did not: it stalled on its own splash, for two reasons that had to be put
   right together.

     - THE DEADLINE.  `fetch` waits for a socket, not for a computer.  With a
       network present but the computer unreachable -- asleep, or a Tailscale
       peer that is down -- the socket never settles, respondWith never
       resolves, and the splash stays for ever.  Every navigation now has
       about two and a half seconds (DEADLINE), so a hanging socket falls
       exactly where a refused one falls -- unless the computer is there
       and only slow, which the worker does not decide by itself: see
       `navigate`.  A door with no kept copy behind it waits a great deal
       longer (PATIENT), because nothing could take its place and some
       doors are honestly slow; but it waits, and does not hang.  (Whether
       the computer is there at all is not asked through here: see the end
       of this file.)
     - THE APP SHELL.  The app's start address is `/?mode=mobile` and it was
       in no cache, so there was nothing for the deadline to fall back to.
       The way in is kept now -- the hub, the shelves, the two libraries and
       Kept on this phone, with their sheets and their scripts -- from one
       list the computer gives at `/__shell` (lib/offline.py, shell()).

   AND THE APP MUST INSTALL AT ALL (the owner, from his phone, later the same
   day).  It stopped installing: Chrome offered, he accepted, and no icon
   appeared.  This worker is why.  Keeping the way in had been written into
   the INSTALL event, and that event grew until it fetched fifty-nine
   addresses weighing three and a quarter megabytes, one after another, with
   nothing but the installation waiting on it -- so over a tunnel the worker
   stayed in `installing` for minutes, and a site whose worker has not
   activated is a site the browser will not install.  Chromium's own guidance
   is that the install event caches the bare minimum and that anything large
   or optional is fetched afterwards.

   SO THE WORKER WARMS ITSELF, AND IS ASKED TO.  `install` caches the app's
   own two pages, as it did before any of §19, and activates at once; neither
   it nor `activate` waits on the shell.  The way in and the studio's faces
   are fetched by `warm` instead, which a PAGE asks for by message once it is
   open and drawn (lib/keep.js, and the install page) -- one address at a
   time, passing over whatever this phone already holds, and saying as it
   goes how far it has got, so that the owner reads "Getting ready — 41 of
   59" rather than watching a silence that looks like nothing happening (his
   decision, 2026-09-23).  A warm may be cut off at any moment, because the
   browser stops a worker whenever it likes; that costs nothing, because the
   caches are the whole of the state and the next ask carries on from what is
   in them.

   A SHELL PAGE IS NOT THE "CANNOT BE REACHED" PAGE.  It opens as it always
   does, wearing the offline chip; `/m/offline/` is left for a navigation that
   is neither kept nor in the shell.  And it must not show yesterday's shelf
   in silence: a shell page is answered from the phone AND read again behind
   the page, and when the computer's answer differs the clients are told
   (`shellFresh`), so lib/keep.js puts the fresh list in place of the one the
   page opened with.  The two lists a library page asks for rather than
   carries -- the decks and the documents -- go the other way round: the
   computer first, under the same deadline, and the phone's last copy behind
   it.

   SEEKING IN A KEPT RECORDING.  A recording is played by `Range` requests and
   the Cache API knows nothing of ranges: a kept narration would play from
   0:00 and refuse to be moved.  So a range asked of a kept file is cut here,
   out of the whole response, and answered 206 with the headers a media
   element needs.  That is what makes ↺ and ↻ work on a train.

   WHAT HAS NO ANSWER OFFLINE says so at once rather than hanging: looking a
   word up, the translation, an UNKEPT note and every door that writes
   (§19.6 -- the owner chose to keep no dictionary and no
   translation model on the phone).  They are answered 503 with a line of
   JSON saying it needs the computer.

   A NOTE, THOUGH, CAN NOW BE KEPT (the owner's second block of 2026-09-23).
   A kept book carries its notes' bare pages, their pictures and the seams'
   list that is how the reader finds them; a kept copy is looked at before
   any of the refusals below, so what is kept is answered and only what is
   not is refused.  Two things follow from it here:

     - THE SEAMS' LIST IS A DOOR, not a file.  `<mount>/api/marks` is what
       says which notes exist and where they sit, and it is asked of the
       computer first under the ordinary deadline with the kept copy behind
       it (`isDoor`), so a note written at the desk this morning shows its
       mark the moment the phone can reach the computer -- and the same list
       still opens the book on a train.
     - THE STUDIO'S OWN FILES ARE SHARED.  A note opens on the studio's
       sheet and in its own faces, and those are kept once for the phone
       rather than once per book: see `isShared`.  And ONCE means once: what
       any cache of this origin holds already -- the app shell keeps the same
       faces -- is not sent for a second time (`keep`), and when the last
       kept thing goes, what the shell does not itself need is given back
       (`reclaim`).  */
'use strict';
/* WHICH PARSEH THIS WORKER CAME WITH (TO-DO §13.16, the app's half of an
   update).  A browser installs a new worker only when the bytes of /sw.js
   change, and a release that did not happen to edit this file changed none
   of them: the phone went on running the old worker, holding the old way in,
   and nothing anywhere told the person that the Parseh on his computer was
   another one.  So the server writes this Parseh's version and build into
   the two strings below AS IT SERVES THE FILE (lib/mobile.py, worker()):
   every release is different bytes, so every release is a new worker on
   every phone the next time it reaches the computer, and that worker is what
   says, in one line on the page, that Parseh was updated.

   THE BUILD IS THE RELEASE'S COMMIT, where the install has a release
   manifest to read it from, and nothing where it has none.  It is there for
   the one case the version cannot tell apart: the same version installed
   twice, which is how a build nobody has seen yet is iterated on -- fixed,
   rebuilt under the same number, installed again -- and each of those is a
   new worker too.

   READ OFF THE DISK UNSTAMPED -- by a test, or by any server that does not
   know to write it -- the worker knows no release at all, and says nothing
   rather than announcing a placeholder. */
const RELEASE = '__PARSEH_RELEASE__';
const BUILD = '__PARSEH_BUILD__';
const STAMPED = RELEASE.indexOf('__') !== 0;
// where the worker writes down, in the app's own cache, which release it is
// and whether it replaced another: the one thing it must still know after
// the browser has stopped it and woken it again
const NOTE = '/__release';
// the digest a kept file was kept with, written on the kept copy itself (see
// `stamped`, and `check` for what it is for)
const KEPT_DIGEST = 'X-Parseh-Kept-Digest';
const APP = 'parseh-app-3';            // the offline page
const SHARED = 'parseh-shared';        // the sheets, the scripts, the faces
const SHELL = 'parseh-shell-1';        // the way in: the hub and the shelves
const KEPT = 'parseh-kept-';           // one cache per thing kept
const OFFLINE = '/m/offline/';
// the app's own two pages, kept with the worker: the offline home, and the
// list of what is kept -- both have to open with the computer away (§19.5)
const OWN = [OFFLINE, '/m/kept/'];
// where the computer says what the way in is made of (lib/offline.py, shell())
const SHELL_DOOR = '/__shell';
// TWO DEADLINES, AND WHICH IS WHICH IS DECIDED BY WHAT WOULD ANSWER INSTEAD.
//
// DEADLINE is the one for an ask that HAS a copy on this phone -- a
// navigation to a kept or shell page, a door whose last answer is in a cache.
// Long enough for a computer that is merely slow, short enough that nobody
// watches a splash screen wondering whether it is broken; past it, the
// phone's own copy is the better of the two answers, so waiting longer buys
// nothing.  For a navigation to a page NOTHING kept it is the point where
// the page is asked whether the computer is answering (`navigate`), and not
// the point where the computer is called gone.
//
// PATIENT is the one for an ask with NOTHING behind it, and it exists because
// having no fallback is not a reason to wait FOR EVER.  `fetch` waits for a
// socket and not for a computer: towards a computer that is asleep on a
// network that is up, the socket settles neither way, and a page waiting on
// a door with nothing behind it would wait with it.  It is generous rather
// than short because the failure at this end is the opposite one: some doors
// are honestly slow (a waveform drawn off a film, a deck read after an
// import), and cutting a slow SUCCESS short, with no copy to put in its
// place, turns a working thing into a refusal.  Half a minute is longer than
// any honest door and far shorter than never.
const DEADLINE = 2500;
const PATIENT = 30000;
// How long a page has to say that the computer is answering it, once it is
// asked (`computerAnswers`): one message there and one back, and between them
// the page's own question to the computer, which a computer that is there
// answers in a few hundred milliseconds.  Short, because whoever does not
// answer in it is a silence, and a silence costs this on top of DEADLINE.
const ASKED = 1500;

// What only the computer can answer: asked for offline, it is refused at
// once.  `/notes/` is still here although a note can now be kept, and it is
// right that it is: `answer` looks in the caches BEFORE it ever consults
// this list, so a kept note is served and only one that was never kept --
// or one written since -- falls through to the refusal.
const NEEDS_COMPUTER = [
  // /__later is the flags to review later (lib/later.js): refused at once
  // like /__prefs, never answered from a copy -- the page keeps its own
  // (localStorage) and sends what it flagged away when the computer is back
  /\/__lookup/, /\/mt\//, /\/__prefs$/, /\/__later$/, /\/notes\//,
  /\/api\/llm/, /\/__narration\//, /\/__save\//, /\/__edit\//
];

// never kept and honestly slow: raced against DEADLINE a navigation to one
// fell to /m/offline/ while the computer was still making it (TO-DO §2.28)
const MADE_ON_DEMAND = /(\/download\/[a-z0-9-]+\/(md|tex|pdf|zip|html)|\/__download\/?|\/__backup|\/__narration\/export|\/api\/backup|\/api\/export|\/api\/decks\/[^\/]+\/[^\/]+\/export|\/anki\/build\/.+\.apkg|\/api\/backups\/(settings|everything))$/;

// the shell's own list, as the computer last gave it; read back from the
// cache the first time a page asks for something, so that a worker woken to
// answer one request does not go to the computer for it.  `shellRead` is
// remembered apart, so that a phone with no shell at all looks for it once
// rather than on every request.
let shellList = null, shellRead = false;
// and, worked out of that list once there IS one, where the studio's own
// files answer: see `studioIs`, which is what tells a shared file from a
// book's own, and which is careful not to write down an answer it reached
// with no list in hand.
let studioPrefix = null;

/* INSTALL FETCHES TWO SMALL PAGES AND NOTHING ELSE -- see the top of this
   file for what happened when it fetched the shell as well.  What is here is
   what was here before §19 was ever written: the offline home and the list of
   what is kept, a few kilobytes, and both of them addresses that must answer
   with the computer away or the app has nothing at all to say for itself.

   `skipWaiting` is called first and not last, so that it is called whatever
   the disk does with those two pages.  An installed app whose offline page is
   missing is a small loss and the next install mends it; an app whose worker
   never activates is an app the browser refuses to install, which is the
   whole of it. */
self.addEventListener('install', e => {
  self.skipWaiting();
  // AN UPDATE, OR A FIRST INSTALL?  While this worker installs, the one it is
  // about to replace is still the registration's active worker -- and on a
  // phone installing the app for the first time there is none.  That is the
  // whole difference between "Parseh was updated" and nothing to say, and it
  // can only be asked HERE: once this worker activates, it is the active one.
  const replacing = !!self.registration.active;
  // AND EVEN THESE TWO HAVE A DEADLINE.  `cache.add` is a fetch, and a fetch
  // waits for a socket rather than for a computer: on the very network this
  // file was written for -- a phone with wifi and a computer asleep behind it
  // -- two small pages can hold the install event open until Chrome's own
  // watchdog ends it, which is the fault this whole arrangement exists to
  // remove, in miniature.  So each page is raced, and the event itself is
  // raced again: an app whose offline page is missing is a small loss that
  // the next install mends; an app whose worker never activates is an app the
  // browser refuses to install.  The note of which release this is rides
  // beside the race and not inside it: it is one write to this phone's own
  // disk, and asks the computer nothing.
  e.waitUntil(Promise.all([
    noteRelease(replacing),
    Promise.race([
      caches.open(APP).then(c => Promise.all(OWN.map(u =>
        reach(new Request(u, {cache: 'reload'}), DEADLINE)
          .then(res => (res && res.ok ? c.put(new Request(u), res) : null))
          .catch(() => {})))),
      new Promise(done => setTimeout(done, DEADLINE + 500)),
    ]),
  ]).catch(() => {}));
});

/* ACTIVATE DROPS WHAT AN OLD WORKER LEFT AND CLAIMS THE OPEN PAGES.  The
   shell is not read here either, and that is the point rather than an
   oversight: install and activate are the two states the browser watches
   before it will call this app installed, so an activate that waits on a
   computer that may be asleep is the same fault in the second of them.

   WHAT IT DROPS IS NAMED BY PREFIX, AND TWO PREFIXES ARE NEVER AMONG THEM
   (TO-DO §13.16, the owner's promise that an update keeps what the phone
   kept).  `parseh-kept-*` and `parseh-shared` are the books, videos and decks
   somebody spent hours of a tunnel bringing here, and no release may sweep
   them: only the app's own pages and its way in are dropped, and only where
   a release has moved their names.

   AND THEN IT SAYS SO, to the pages it has just claimed: a new worker taking
   over a page under somebody's thumb is exactly the silent swap the owner
   does not want, so every page open at that moment is told which release
   this is, and says it in a line (lib/keep.js).  Nothing is reloaded: the
   page goes on as it was, and the next one it opens is the new release's. */
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => (k.startsWith('parseh-app-') && k !== APP) ||
                                               (k.startsWith('parseh-shell-') && k !== SHELL))
                                  .map(k => caches.delete(k))))
    .catch(() => {})
    .then(() => self.clients.claim())
    .then(() => announce())
    .catch(() => {}));
});

/* ---- which release this is, and telling the pages ------------------------
   THE NOTE.  Written at install, in the app's own cache, beside the two pages
   it keeps there: this release, its build, whether it replaced a worker, and
   which release that worker had noted -- where it had noted one at all, which
   no worker before this file did.  A worker the browser stops and wakes again
   an hour later knows its own release (it is in its bytes) and nothing else,
   and a page opened then must still be able to learn that the app was
   updated since it last looked. */
async function noteRelease(replacing) {
  if (!STAMPED) return;
  try {
    const c = await caches.open(APP);
    let before = null;
    try {
      const was = await c.match(NOTE);
      before = was ? await was.json() : null;
    } catch (err) { before = null; }
    await c.put(new Request(NOTE), new Response(JSON.stringify({
      version: RELEASE, build: BUILD, replaced: replacing,
      previous: replacing && before && before.version ? String(before.version) : '',
      at: Date.now() / 1000}), {headers: {'Content-Type': 'application/json'}}));
  } catch (err) {
    // no note: the pages learn the release from the worker's own bytes and
    // the phone's own memory (lib/keep.js), and lose only the first-update
    // case -- a line not said, never an install refused
  }
}

/* WHAT THIS WORKER SAYS WHEN ASKED.  Its own release always, from its own
   bytes; whether it REPLACED another only from a note that is its own -- a
   note left by a newer worker that was then thrown away before it activated
   says nothing about this one. */
async function releaseSays() {
  const plain = {version: STAMPED ? RELEASE : '', build: STAMPED ? BUILD : '',
                 replaced: false, previous: ''};
  if (!STAMPED) return plain;
  try {
    const res = await (await caches.open(APP)).match(NOTE);
    const note = res ? await res.json() : null;
    if (note && note.version === RELEASE && note.build === BUILD)
      return {version: RELEASE, build: BUILD, replaced: !!note.replaced,
              previous: String(note.previous || '')};
  } catch (err) { /* no note that can be read: the plain answer */ }
  return plain;
}

async function announce() {
  const said = await releaseSays();
  if (said.version && said.replaced) await tellClients({updated: said});
}

/* ---- the way in, warmed -------------------------------------------------
   THE LIST, FROM WHEREVER IT CAN BE HAD.  In memory first, because a warm
   asked twice in one sitting must not go back to the computer for a list it
   is holding; then the copy in the shell's cache, which is how a worker the
   browser has just woken knows what the shell is without a word to anybody;
   and only then the door itself, which is the one fetch a warm makes before
   it has a list at all.

   Nothing here runs at install or at activate any more, so this is also the
   only thing that ever puts `/__shell` in a cache.  Which means the set of
   addresses a warm walks is refreshed when the shell's cache is emptied --
   that is, when SHELL's version moves and `activate` drops the old one, which
   is exactly what that version is for.  What the shell pages SAY does not
   wait for any of that: each is read again behind the page it answered
   (`renew`), and the clients are told when it has changed. */
async function shellNow() {
  /* THE LIST IS ASKED FOR AGAIN EVERY TIME A WARM IS, and that is not waste.
     It is one small answer, and it is the only thing that can tell a phone
     that the app has grown a page or a face since it was warmed: read once
     and remembered for ever, a phone that had warmed one release would never
     fetch anything added in the next, and the fault would be invisible --
     everything it already had would go on working.  The copy in the cache is
     what answers when the computer does not. */
  try {
    const res = await reach(new Request(SHELL_DOOR, {cache: 'no-store', credentials: 'same-origin'}),
                            PATIENT);
    if (!res || !res.ok) return null;
    const list = await res.clone().json();
    const cache = await caches.open(SHELL);
    await cache.put(new Request(SHELL_DOOR), res.clone());
    shellList = list;
    shellRead = true;
    studioPrefix = null;               // a fresh list may mount the studio elsewhere
    return list;
  } catch (err) {
    // the computer is away: whatever was last read is the best there is, and
    // with nothing read at all there is nothing to warm
    return await shellSays();
  }
}

/* WHICH ADDRESSES A WARM MEANS.  `way-in` is everything a person needs to GET
   somewhere -- the pages, the two lists those pages ask for, the sheets and
   the scripts they load.  `studio` is what a studio page needs to LOOK like
   itself, which is the faces its sheet names and which no phone should fetch
   until a page that wants them says so (lib/offline.py, shell(): `later`).
   A list this worker does not know is no addresses, not an error: an older
   computer answering a newer app simply has no `later` to give. */
function warmWhat(list, what) {
  if (!list) return [];
  if (what === 'studio') return (list.later || []).filter(Boolean);
  // WHAT A PAGE IS MADE OF COMES BEFORE THE PAGE ITSELF.  A warm can stop at
  // any address -- the computer goes away, the app is closed -- and what it
  // has reached by then is what a phone opens with.  Cached the other way
  // round, the commonest half-warm state was the hub present and its sheet
  // and its script absent: the app opened on unstyled markup that did
  // nothing, which is worse than the page that says the computer cannot be
  // reached, because it looks like Parseh broken rather than Parseh away.
  // Files first, then the lists, then the pages: a page is only ever in the
  // cache once the things it asks for are there too.
  return [].concat(list.files || [], list.apis || [], list.pages || []).filter(Boolean);
}

/* THE WARMING NOW GOING ON, so that two pages asking at once are one pass and
   not two racing ones.  It is memory and only memory, and it is right that
   it is: the browser stops this worker whenever it likes, and what has to
   survive that is not a note saying how far we got -- it is the files, which
   are in the caches. */
const warming = Object.create(null);

/* WHAT A PAGE ASKS FOR: `{warm: 'way-in'}` or `{warm: 'studio'}`.  An ask is
   cheap on purpose, so that a page may send it every time it opens without
   thinking: a phone that holds everything already fetches nothing at all,
   because every address is passed over, and a phone that was cut off halfway
   through carries on where it stopped for the same reason. */
function warm(what) {
  if (what !== 'way-in' && what !== 'studio') return Promise.resolve();
  if (!warming[what])
    warming[what] = warmList(what).catch(() => {}).then(() => { delete warming[what]; });
  return warming[what];
}

/* ONE ADDRESS AT A TIME, AND SAYING SO.  One at a time because fifty-nine at
   once is the same three megabytes of tunnel in a heap, and because what it
   costs is then something the owner can watch going down rather than a wait
   he has to trust.

   WHAT IS ALREADY ON THE PHONE IS PASSED OVER, asked of the caches and not
   guessed from the address -- the same question `keep` asks, asked by the
   same `held`.  The two caches leant on are the shell's, which nothing but
   this worker empties, and the shared one, which is freed only when nothing
   at all is kept (`reclaim`); a kept BOOK's cache is not among them, for the
   reason spelt out over `keep` -- it leaves when the book does, and the shell
   must not be left pointing at a face that went with somebody's book.

   A FAILURE TELLS US WHICH KIND IT WAS.  An answer that is not ok is this one
   address being wrong -- a face renamed, a script not built yet -- so it is
   counted as settled and the rest of the list goes on.  A fetch that THROWS
   is the computer being away, and then every address after it would throw as
   well, one deadline at a time; so the pass stops there.  Nothing is lost:
   what was fetched is in the cache, and the next ask starts from it. */
async function warmList(what) {
  const list = await shellNow();
  const urls = warmWhat(list, what);
  const of = urls.length;
  // Even with nothing to do the clients are told it is over, because a page
  // that lit "Getting ready" the moment it asked has to be able to put it out.
  if (!of) { await tellClients({warmed: {what: what, of: 0, done: 0}}); return; }
  /* WHERE EACH LIST LANDS, and it is not the same place.  The way in is the
     APP's: it belongs in the shell, which `reclaim` reads to know what may
     never be swept.  The studio's faces are not the app's -- they are what a
     kept note, a kept document and a studio page all draw with -- so they go
     into the SHARED cache, the one thing on this phone whose life is "while
     anything at all is kept".  Put in the shell, as they were at first, they
     were a trap: `keep` skips what the shell holds, so a book kept afterwards
     never fetched them, and the next time the shell's version was bumped they
     went with it and left that book's notes drawing in whatever face the
     phone had. */
  const cache = await caches.open(what === 'studio' ? SHARED : SHELL);
  const shared = await caches.open(SHARED);
  const app = await caches.open(APP);
  let done = 0;
  await tellClients({warming: {what: what, done: done, of: of}});
  for (const url of urls) {
    const req = new Request(url);
    try {
      if (!(await held(req, [cache, shared, app]))) {
        // AND IT YIELDS TO THE PAGE.  `priority: 'low'` tells the browser
        // that nothing here is being waited for by anybody: a warm must
        // never take bandwidth from what somebody is reading or watching,
        // which is exactly how it came to starve a video's own player on a
        // phone over a tunnel.  A browser that does not know the hint
        // ignores it and the warm is merely as it was.
        const res = await reach(new Request(url, {cache: 'no-store', credentials: 'same-origin',
                                                  priority: 'low'}),
                                PATIENT);
        if (res && res.ok) {
          await cache.put(req, res.clone());
          // THE HUB IS ASKED FOR AT TWO ADDRESSES.  The app starts at
          // `/?mode=mobile` (lib/mobile.py's manifest) and every link home goes
          // to `/`; caches.match tells the two apart, so the one answer is put
          // under both or the way in is kept for one of them only.
          const q = url.indexOf('?');
          if (q > 0) await cache.put(new Request(url.slice(0, q)), res.clone());
        }
      }
    } catch (err) {
      break;                           // the computer is away: it stops here
    }
    // settled, whether it was fetched or was here already: what this counts
    // is how much of the list is behind us, which is the honest thing to show
    done++;
    await tellClients({warming: {what: what, done: done, of: of}});
  }
  // Said whether the list was walked to the end or given up on partway -- it
  // means "this worker has stopped working on that list", which is what a
  // page showing a bar needs to know -- AND IT SAYS WHICH OF THE TWO IT WAS.
  // A pass that stopped because the computer went away announced itself as
  // finished, and the install page then read "Ready: its pages are on this
  // phone now" over a list that was mostly not fetched.  `done` is how far it
  // really got; the next ask picks up what is left.
  await tellClients({warmed: {what: what, of: of, done: done}});
}

/* IS THIS ADDRESS ON THE PHONE ALREADY?  Asked of the caches that the job may
   lean on, and of no others -- `keep` and `warmList` differ only in which
   those are, and the reasoning behind each is written over each of them. */
async function held(req, where) {
  for (const c of where)
    if (await c.match(req, {ignoreVary: true})) return true;
  return false;
}

async function shellSays() {
  if (shellRead) return shellList;
  // SET WHEN THE READING IS DONE, not when it begins: two requests arriving
  // together both call this, and a flag raised first sent the second one away
  // with `null` -- which made isShellApi answer false for a door that is one,
  // for as long as that worker lived.
  const res = await caches.match(SHELL_DOOR);
  if (!res) { shellRead = true; return null; }
  try { shellList = await res.json(); } catch (err) { shellList = null; }
  shellRead = true;
  return shellList;
}

async function isShellApi(url) {
  const list = await shellSays();
  return !!(list && (list.apis || []).indexOf(url.pathname) >= 0);
}

/* ---- what the page asks of the worker (lib/keep.js) ---------------------
   keep: a thing's addresses, into its own cache, one by one, with progress
   sent back; free: some of them out of it again, which is what Change what
   is kept does with a recording that has been unticked; drop: that cache,
   gone; inside: what its cache holds now, so that the list of recordings can
   be drawn with the kept ones ticked; kept: what is here, and how big.

   check: whether what was kept is still WHOLE, address by address, which is
   the one question the sheet used to answer by guessing (the owner's 3,
   2026-09-23: "the boxes should by default show the things that are actually
   kept in memory, and there should be a check of this, it should actually
   look for the file and check that the download was complete and correct").

   warm: the app getting ITSELF ready -- the way in, or the studio's faces --
   which install no longer does and a page therefore asks for once it is open.
   It is the one ask here that answers EVERY client rather than the one that
   sent it (`tellClients`), because the bar reading "Getting ready — 41 of 59"
   may be on a page that did not ask and because two pages asking are one
   pass; and it is the one ask the pages must not send in the browser mode,
   since this is the APP getting ready and a tab is not the app.

   release: which Parseh this worker came with, and whether it replaced
   another -- asked by every mobile page as it opens, because a page opened
   after the worker activated was not there to be told (`announce`).        */
self.addEventListener('message', e => {
  const msg = e.data || {};
  const reply = what => { if (e.source) e.source.postMessage(what); };
  if (msg.release) e.waitUntil(releaseSays().then(r => reply({release: r})));
  else if (msg.warm) e.waitUntil(warm(msg.warm));
  else if (msg.keep) e.waitUntil(keep(msg.keep, reply));
  else if (msg.free) e.waitUntil(free(msg.free, reply));
  else if (msg.drop) e.waitUntil(drop(msg.drop, reply));
  else if (msg.inside) e.waitUntil(inside(msg.inside, reply));
  else if (msg.check) e.waitUntil(check(msg, reply));
  else if (msg.kept) e.waitUntil(kept(reply));
});

/* ---- is what was kept still whole? -------------------------------------
   A TICK USED TO MEAN "THIS ADDRESS IS A KEY IN THIS CACHE" and nothing more
   (the owner's 3, 2026-09-23).  It did not mean the body was all there, or
   that it was the file at all: a 503 refusal kept by mistake, a page the
   computer sent where a picture was asked for, a fetch cut off halfway by a
   tunnel -- every one of them leaves a key in the cache and every one of them
   ticked a box.  That is the fault this answers: the sheet now ticks from
   here and from nothing else, and what cannot be shown to be whole is
   unticked, so Save fetches it again.

   WHAT "WHOLE" MEANS, and it is decided by what the record can promise:

     - a refusal or a failure that was kept is never whole (`res.ok`);
     - an HTML page where a file was expected is never whole: the computer
       answering a page -- a login, a "not found", a shell -- where a
       recording or a picture was asked for is the commonest lie a cache can
       be told, and the content type shows it at no cost at all;
     - where the record gives a DIGEST, the body must hash to it.  That is
       the whole truth about the file, and the computer gives one for every
       file it can afford to hash (lib/offline.py, DIGEST_MAX);
     - where it does not -- a narration of two hundred megabytes, which
       WebCrypto cannot hash without holding all of it in memory at once --
       the LENGTH must match.  The header says it, so nothing is read at all.

   AND WHERE THE RECORD'S SIZE IS AN ESTIMATE, THE LENGTH IS NOT A PROMISE.
   A note's page and an exercise's are RENDERED by the computer, and what
   lib/offline.py weighs for them is the source on the disk plus the wrapper
   -- an honest guess at what they will cost and never the answer's own byte
   count.  The record says so itself (`check: "here"`, lib/offline.py's
   _door): the phone may test that it HAS that answer and must test nothing
   else about it.  Where an older computer's record says nothing, the address
   is read instead -- one that names no file (it ends in a slash, or in
   nothing) is composed -- because measuring a rendered page against a guess
   would untick everything the sheet has, which is a worse lie than the one
   being mended.                                                            */
const A_FILE = /\.([a-z0-9]{1,5})(\?|$)/i;
// what is certainly not a page: asked for at one of these addresses, an HTML
// body is the computer talking about the file rather than the file
const NOT_A_PAGE = /\.(mp3|m4a|ogg|opus|wav|flac|mp4|webm|mkv|mov|png|jpe?g|gif|webp|svg|avif|ico|css|js|json|txt|woff2?|ttf|otf)(\?|$)/i;
// the ceiling on what this will read into memory to hash or to measure: a
// phone has to go on working while it does, and anything above it is a file
// the computer was never asked to digest either
const READABLE = 12 * 1024 * 1024;

function hex(buf) {
  const b = new Uint8Array(buf);
  let out = '';
  for (let i = 0; i < b.length; i++) out += (b[i] < 16 ? '0' : '') + b[i].toString(16);
  return out;
}

/* `seen`, where it is given, is told what the body hashed to and handed the
   body itself -- `check` needs both to tell a copy Parseh has since UPDATED
   from one that is broken, and a second read of the same body to learn them
   would cost the phone twice what the first did. */
async function whole(res, want, seen) {
  if (!res || !res.ok) return false;
  const url = want.url || '';
  const type = (res.headers.get('content-type') || '').toLowerCase();
  if (NOT_A_PAGE.test(url) && type.indexOf('text/html') === 0) return false;
  // the computer composed this answer and promises nothing about its bytes:
  // that it is here, and is not a refusal, is the whole of what can be asked
  if (want.check === 'here') return true;
  const digest = (want.digest || '').toLowerCase();
  const bytes = +want.bytes || 0;
  /* EVERY TEST THAT COSTS NOTHING COMES BEFORE THE ONE THAT COSTS THE PHONE
     ITS MEMORY.  The ceiling above is the promise that this will not read a
     narration into a phone to look at it -- and the ceiling used to be tested
     on `body.byteLength`, which is to say AFTER the whole body had been read,
     so it guarded nothing at all: a 228 MB recording was pulled into memory
     and only then found too big to hash.  The response says its own length in
     a header, and the record says what the computer weighed; either is enough
     to know that a body must not be touched, and both are free. */
  const said = res.headers.get('content-length');
  const size = said === null ? NaN : parseInt(said, 10);
  const told = size >= 0;
  if (told ? size > READABLE : bytes > READABLE) {
    // ABOVE THE CEILING, THE LENGTH IS THE WHOLE OF THE ANSWER, and where not
    // even the length is known the file keeps the benefit of the doubt: the
    // tests above have been passed, and a worker that reads two hundred
    // megabytes to draw a sheet is a worker that hangs the phone the sheet
    // was opened on.  An address that names no file is not measured at all,
    // for the reason written over `A_FILE`: what the computer composes as it
    // answers has no length anybody here can predict.
    if (!bytes || !A_FILE.test(url)) return true;
    // THE HEADER IS WHAT IT WAS STORED WITH, NOT WHAT IS THERE.  A download
    // the tunnel cut short keeps the Content-Length the computer sent, so a
    // torn 38 kB recording still says 38 kB and passed this test while half
    // of it was missing (driven in the suite: a body of 19,349 bytes under a
    // header of 38,699, called whole).  The body's REAL length is asked of a
    // Blob, which in a cache is a handle to what is on the disk: its `size`
    // is exact and reading it costs no memory, where arrayBuffer would pull
    // a whole narration into the phone.
    if (told && size !== bytes) return false;
    try {
      return (await res.clone().blob()).size === bytes;
    } catch (err) {
      return told ? size === bytes : true;       // no Blob here: the header is all there is
    }
  }
  // THE DIGEST, WHERE THERE IS ONE.  A browser whose worker has no WebCrypto
  // at all falls through to the length rather than calling everything broken:
  // the check may be weaker there, it may not be wrong.
  if (/^[0-9a-f]{64}$/.test(digest) && self.crypto && self.crypto.subtle) {
    const body = await res.arrayBuffer();
    // nothing said how big it was and it turns out to be over the ceiling:
    // it is read now and there is no unreading it, but it is not hashed on
    // top of that, and the length it really has is what it is judged by
    if (body.byteLength > READABLE) return !bytes || body.byteLength === bytes;
    const sum = hex(await self.crypto.subtle.digest('SHA-256', body));
    if (seen) { seen.sum = sum; seen.body = body; }
    return sum === digest;
  }
  if (!bytes || !A_FILE.test(url)) return true;   // nothing to measure against
  // and here too it is the body that is measured and not the header it was
  // stored with, for the reason written above; under the ceiling either way
  // of reading it is cheap, and the Blob is the one that cannot be fooled
  if (told && size !== bytes) return false;
  try {
    return (await res.clone().blob()).size === bytes;
  } catch (err) {
    return (await res.arrayBuffer()).byteLength === bytes;
  }
}

/* WHICH CACHES ARE LOOKED IN, AND IT IS THE VERY QUESTION `keep` ASKS.  The
   two have to agree, because between them they are one promise made twice:
   this says a box may be ticked, and that decides whether Save fetches the
   file behind it.  They did not agree.  This looked in the SHELL and in the
   app's own two pages as well, so a studio face that only the shell held was
   called whole and ticked -- while `keep` refuses to lean on the shell
   deliberately (the shell is the APP's copy, dropped whole whenever SHELL's
   version is bumped), so Save never fetched one of this thing's own, and the
   thing went on borrowing the app's until the next release took it away and
   left its notes drawing in whatever face the phone had.  A tick that says
   "there is no need to fetch this" must rest on a cache that will outlive
   the thing it was ticked for: this thing's own, and the shared one, which
   is freed only when nothing at all is kept (`reclaim`).  NOT another kept
   thing's cache either -- a face that answers today because somebody else's
   book holds it goes when that book does.

   The thing's own cache is opened only when it EXISTS.  `caches.open` makes
   one where there is none, and an empty `parseh-kept-…` left lying about is
   not nothing: `reclaim` reads "any kept cache at all" as "something is still
   kept here", and would then never give the shared four megabytes back.

   AND AN UPDATE IS NOT DAMAGE (TO-DO §13.16, the owner: the keep check must
   not cry wolf).  The digest the page hands this is the computer's NOW, and
   a new release of Parseh changes its own scripts by design -- so every kept
   copy of /lib/'s files failed its digest the morning after an update, and
   the sheet called a phone full of perfectly good books "no longer whole".
   What tells the two apart is the digest each file was KEPT with, which is
   written on the kept copy itself (`stamped`, by `keep`, `settle` and
   `renew`).  A body is then one of three things:

     - it hashes to the computer's digest: WHOLE.  Where the digest it was
       kept with is another -- `renew` brought the new release's copy and
       could not write it down, or the copy predates the writing down --
       the record is REFRESHED to the digest it really has, and nothing is
       fetched: the file is `updated`, and the next release is measured
       against the file that is here, not against the one that was;
     - it hashes to the digest it was kept with, and the computer's has
       moved on since: still WHOLE -- nothing in it was lost -- and
       `updated`, and NOT fetched again (kept things can be big, the owner's
       words).  A page that uses it brings the new copy behind itself, as
       every kept page's small parts are (`renew`);
     - it hashes to neither: NO LONGER WHOLE, exactly as before.  A copy with
       no digest written on it is measured against the computer's alone, as
       every copy was before this. */
async function check(job, reply) {
  const id = job.check, want = (job.want || []).filter(x => x && x.url);
  const keys = await caches.keys();
  const where = [];
  if (keys.indexOf(KEPT + id) >= 0) where.push(await caches.open(KEPT + id));
  if (keys.indexOf(SHARED) >= 0) where.push(await caches.open(SHARED));
  const urls = [];
  for (const w of want) {
    let here = false, sound = false, updated = false;
    try {
      const req = new Request(w.url);
      let res = null, from = null;
      for (const c of where) {
        res = await c.match(req, {ignoreVary: true});
        if (res) { from = c; break; }
      }
      here = !!res;
      if (res) {
        const seen = {};
        sound = await whole(res, w, seen);
        const kept = (res.headers.get(KEPT_DIGEST) || '').toLowerCase();
        const now = (w.digest || '').toLowerCase();
        if (sound && seen.sum && kept !== seen.sum) {
          if (kept) updated = true;
          await from.put(req, stamped(res, seen.sum, seen.body));
        } else if (!sound && seen.sum && kept && seen.sum === kept && kept !== now) {
          sound = true;
          updated = true;
        }
      }
    } catch (err) {
      // a cache that will not open, a body that will not read: what cannot be
      // shown to be whole is not whole, and Save fetches it again
    }
    urls.push({url: w.url, here: here, whole: here && sound, updated: here && updated});
  }
  reply({check: id, urls: urls});
}

/* THE DIGEST A FILE WAS KEPT WITH, WRITTEN ON THE COPY (see `check`).  A
   header on the stored answer rather than a list kept somewhere beside it,
   because the copy and the note about it must never part: `drop` deleting a
   cache, `free` taking one address out, `renew` putting a fresh copy in --
   each of them takes the note with the file and needs to know nothing about
   it.  What is written is what the computer SAID the file was when the
   phone took it, never what the phone happened to receive: a download cut
   short would otherwise be written down as the truth about itself, and the
   check would call it whole for ever.  An answer with no digest to write --
   a recording too big to hash, a page the computer composes -- is put as it
   came.  `body`, where given, is the answer's body already read. */
function stamped(res, digest, body) {
  digest = (digest || '').toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(digest)) return body === undefined ? res : fresh(res, body, '');
  return fresh(res, body === undefined ? res.body : body, digest);
}
function fresh(res, body, digest) {
  const head = new Headers(res.headers);
  if (digest) head.set(KEPT_DIGEST, digest);
  else head.delete(KEPT_DIGEST);
  return new Response(body, {status: res.status, statusText: res.statusText, headers: head});
}

/* WHAT TWO THINGS BOTH NEED IS KEPT ONCE (the owner's 3, 4 and 5 of
   2026-09-23, second block).  A file that is the same bytes whichever book
   asked for it belongs in `parseh-shared`, not in a copy per book: the
   studio's sheet, its script, its THIRTEEN faces (1.83 MB) and MathJax
   (2.1 MB) are what a note opens on, and a shelf of ten books that each kept
   its own copy would be forty megabytes of the same four.

   Two prefixes say it.  `/lib/` is the toolbox's own, as it always was.  The
   second is the studio's own `…/static/`: the studio answers its files under
   its own mount (markdown/app/server.py, serve_static and the maths routes),
   and the bare note page links them at the STUDIO'S canonical address rather
   than at the book's notes mount for exactly this reason -- so two books'
   notes already ask for the same address, and this is what keeps the answer
   once.

   BUT ONLY THE STUDIO'S OWN, NAMED IN FULL, and never any path with
   `/static/` somewhere in it.  A book's slug is the owner's own word for his
   book, and `/books/persian/static/reader/…` is a perfectly ordinary address
   for one: read as shared, that book's own pages would be written into
   `parseh-shared`, where they belong to nothing, are freed by no drop, and
   "Remove from this phone" would quietly leave them behind while telling him
   the room was given back. */
async function isShared(url) {
  let path = url;
  try { path = new URL(url, self.location.origin).pathname; } catch (err) { /* a path already */ }
  if (/^\/lib\//.test(path)) return true;
  /* AND THE PLAYER'S OWN TWO FILES, which every video asks for and which are
     the same bytes for all of them: /youtube/lib/player.js is 267 kB and its
     sheet 53 kB, so twenty kept videos holding their own copies is 6.4 MB of
     one script.  The mount is learnt, not written down, for the same reason
     the studio's is: serve.py decides where the videos live. */
  const vids = await videoLibIs();
  if (vids && path.slice(0, vids.length) === vids) return true;
  const studio = await studioIs();
  return !!studio && path.slice(0, studio.length) === studio;
}

/* WHERE THE STUDIO IS MOUNTED, LEARNT RATHER THAN ASSUMED.  This worker is
   given no configuration at all -- serve.py decides the studio's mount, and
   `/studio` written here would be a second copy of that decision, wrong the
   day it moves.  What the worker does have is the shell list, and the list
   names the studio's sheets and scripts IN FULL, and its thirteen faces in
   `later` (lib/offline.py, shell(): studio_files and studio_faces, every one
   of them under `<studio>/static/`).  So the prefix is read off those
   addresses: everything up to and including the `/static/` they all share.
   Both lists are looked at, because which of the two carries the studio's
   files is lib/offline.py's business and not this file's.

   WITH NO SHELL LIST YET there is no answer -- and none is WRITTEN DOWN
   either, which is the half of this worth reading.  The list arrives late
   now: nothing fetches it at install, so a worker woken to answer one
   request may be asked this before any page has asked for a warm.  Were the
   empty answer remembered, every studio file would go into kept things' own
   caches for the rest of that worker's life, long after the list had come.
   So it is worked out afresh until there is something to work it out from.

   Until then the studio's files go into the kept thing's own cache.  That
   costs the room twice on a second book rather than telling a lie: they are
   still kept, still answered, and still freed when the thing that paid for
   them is removed.  And the empty answer stays EMPTY rather than becoming a
   prefix that matches everything -- `isShared` tests it before it compares,
   because `/books/persian/static/reader/…` is an ordinary address for one of
   the owner's own books and reading it as the studio's would write that
   book's pages into a cache no "Remove from this phone" ever frees. */
/* AND WHERE THE PLAYER'S OWN FILES ANSWER, learnt the same way and for the
   same reason.  A video's record names them in full (lib/offline.py,
   PLAYER_FILES) under the video mount's own /lib/, so the prefix is read off
   a record rather than written down here -- serve.py decides that mount, and
   `/youtube/lib/` written in this file would be a second copy of its
   decision, wrong the day it moves.  There is no shell list to read it from
   (a video is not part of the way in), so it is learnt from the first kept
   video that names it, through `sawVideoLib` below, and remembered. */
let videoLib = null;
function sawVideoLib(urls) {
  if (videoLib) return;
  for (const url of urls || []) {
    let path = url;
    try { path = new URL(url, self.location.origin).pathname; } catch (err) { /* a path */ }
    const at = path.indexOf('/lib/');
    // not the toolbox's own /lib/, which is shared already and starts at 0
    if (at > 0) { videoLib = path.slice(0, at + '/lib/'.length); return; }
  }
}
async function videoLibIs() { return videoLib || ''; }

async function studioIs() {
  if (studioPrefix !== null) return studioPrefix;
  const list = await shellSays();
  if (!list) return '';
  studioPrefix = '';
  for (const url of [].concat(list.files || [], list.later || [])) {
    let path = url;
    try { path = new URL(url, self.location.origin).pathname; } catch (err) { /* a path already */ }
    const at = path.indexOf('/static/');
    if (at >= 0) { studioPrefix = path.slice(0, at + '/static/'.length); break; }
  }
  return studioPrefix;
}

/* WHAT THIS PHONE ALREADY HOLDS IS NOT FETCHED AGAIN (the owner's 4: ONCE).
   The studio's thirteen faces are 1.83 MB and a warmed app shell holds them
   too, so a first keep of a book with notes used to send for the very bytes
   that were already lying on the disk, and then hold them twice.  "A warmed
   one": since the faces left the way in, the shell has them once `warm` has
   been asked for them, and before that this phone simply has not got them
   and the fetch below is the honest answer.

   "ALREADY HERE" IS ASKED OF THE CACHES, NOT GUESSED FROM THE ADDRESS, and
   that is the whole of why this works.  A cache is the only thing that knows
   what is on the disk, and it is the same question `answer` will ask when a
   page comes for the file later -- `caches.match` looks in all of them, so a
   face sitting in the shell's cache answers a note's page as perfectly as a
   copy in the shared one would.  Deciding from the address instead would
   mean writing down here which list holds what, and the two lists would be
   wrong about each other the first time either moved.

   WHICH CACHES MAY BE LEANT ON (`held`), and the rule is the same one every
   time: lean only on a cache that will outlive the thing being kept.  For a
   KEEP those are the shared cache -- freed only when nothing at all is kept
   (`reclaim`) -- and this thing's own.  NOT the shell: its copies are the
   app's, dropped whole whenever the shell's version is bumped, so a book that
   had leant on it would silently lose a stylesheet at the next release.  NOT
   another thing's cache either, which goes when that thing is removed.
   For a WARM the answer is the shell (it is the app's own list), the shared
   cache, and the two pages the install event put in the app's.

   A RENEW STILL GOES TO THE COMPUTER.  Bringing a changed file is the one
   job that must not stop at "there is something under that address" -- that
   something is precisely what is out of date.  The worker's own `renew` (it
   fetches unconditionally) and a job that says `renew` are both exempt.   */
async function keep(job, reply) {
  const id = job.id, urls = (job.urls || []).filter(Boolean);
  // a kept video names the player's own files: that is where this worker
  // learns the video mount, which is how it knows they are shared
  sawVideoLib(urls);
  const cache = await caches.open(KEPT + id);
  const shared = await caches.open(SHARED);
  const again = !!job.renew;
  // what the computer said each file was, as the page read it off the record
  // (lib/keep.js, digestsOf): written on each copy as it is put (`stamped`)
  const digests = job.digests || {};
  let done = 0, failed = [], already = 0;
  for (const url of urls) {
    try {
      const req = new Request(url);
      // NOT THE SHELL.  A file the shell happens to hold is the APP's copy,
      // and the app's copies are dropped whole whenever the shell's version
      // is bumped -- so a book kept while the shell held its stylesheet would
      // quietly lose it at the next release, having never fetched one of its
      // own.  The shared cache is the one that outlives a release and is
      // freed only when nothing is kept at all.
      const have = again ? false : await held(req, [shared, cache]);
      if (have) {
        already++;
      } else {
        const to = (await isShared(url)) ? shared : cache;
        // no-store on the way in: what is kept must be the computer's answer
        // now, not something a browser cache answered a week ago
        const res = await fetch(new Request(url, {cache: 'no-store', credentials: 'same-origin'}));
        if (!res || !res.ok) throw new Error('the computer answered ' + (res && res.status));
        await to.put(req, stamped(res, digests[url]));
      }
    } catch (err) {
      failed.push(url);
    }
    done++;
    reply({keeping: id, done, of: urls.length, failed: failed.length});
  }
  reply({kept: id, done, of: urls.length, failed, already, version: job.version || ''});
}

/* GIVING THE ROOM BACK WITHOUT GIVING THE THING BACK (the owner's 4,
   2026-09-23).  Keeping used to be all or nothing: a narrated book whose
   second recording was no longer wanted had to be removed whole and kept
   again.  This takes named addresses out of one thing's cache and leaves the
   rest of it where it is. */
async function free(job, reply) {
  const cache = await caches.open(KEPT + job.id);
  let gone = 0;
  for (const url of (job.urls || []).filter(Boolean)) {
    try { if (await cache.delete(new Request(url), {ignoreVary: true})) gone++; }
    catch (err) { /* it is not there: that is what was wanted anyway */ }
  }
  reply({freed: job.id, gone});
}

async function drop(id, reply) {
  const gone = await caches.delete(KEPT + id);
  const shared = await reclaim();
  reply({dropped: id, gone, shared});
}

/* THE LAST THING OUT TURNS THE LIGHT OFF (the owner's 4, and "Remove from
   this phone" says it gives the room back).  The shared cache is paid for by
   whoever keeps the first thing that needs it -- the studio's sheet, its
   thirteen faces, MathJax: about four megabytes -- and nothing ever asked for
   it back.  Remove the one book that had notes and those four megabytes sat
   on the phone for ever, referred to by nothing, while the button that
   removed it promised the room.

   WHILE ANYTHING IS STILL KEPT, NOTHING HERE IS FREED, because the shared
   cache holds no record of which thing wanted which file and a sweep that
   guessed would take the faces out from under the book still on the phone.
   So the test is the plainest one there is: no `parseh-kept-` cache at all.

   AND THEN THE WHOLE OF IT GOES.  Nothing is kept, so nothing is left that
   this cache was filled for.  The app keeps everything it needs to open --
   its way in is in the SHELL cache, which this sweep does not touch -- and
   the studio's faces, which live here, are fetched afresh the next time a
   studio page is opened: that is the bargain the owner chose when he asked
   for them to wait for a page that wants them.  An earlier cut of this kept
   whatever the shell also held and freed the rest, which was the wrong way
   about twice: what the shell holds is the redundant copy, and what it does
   not hold is the one that was doing the work. */
async function reclaim() {
  const keys = await caches.keys();
  if (keys.some(k => k.startsWith(KEPT))) return 0;
  if (keys.indexOf(SHARED) < 0) return 0;
  /* NOTHING IS KEPT, so nothing is left that this cache was filled for, and
     the room goes back -- which is the whole of what "Remove from this phone"
     promises.  It used to keep whatever the SHELL also held and free the
     rest, which is the wrong way about twice over: what the shell holds is
     the copy that is redundant, and what it does not hold is the copy that
     was doing the work.  The app itself loses nothing it cannot get again:
     its own way in is in the shell, and the studio's faces are fetched afresh
     the next time a studio page is opened, which is the bargain the owner
     chose when he asked for them to wait for a page that needs them. */
  const shared = await caches.open(SHARED);
  let freed = 0;
  for (const req of await shared.keys())
    if (await shared.delete(req, {ignoreVary: true})) freed++;
  return freed;
}

async function inside(id, reply) {
  const c = await caches.open(KEPT + id);
  const reqs = await c.keys();
  // WHAT IS KEPT ONCE FOR THE WHOLE PHONE IS ANSWERED TOO (the owner's 3, 4
  // and 5).  A thing's own cache says nothing about the studio's sheet, its
  // faces or MathJax, because those are shared -- and a sheet that could not
  // see them would offer to fetch four megabytes that the last book kept
  // already, which is a lie told in the one place where the numbers are the
  // whole point.
  //
  // AND THE SHELL'S ARE NOT AMONG THEM, which is the half worth reading.
  // The shell holds the studio's sheet and, once the faces have been warmed,
  // those as well -- and it was listed here on the grounds that whatever it
  // holds `keep` will not send for again.  That has not been true since
  // `keep` was told to lean on the shared cache and on nothing else: the
  // shell is the APP's copy and goes whenever SHELL's version is bumped, so
  // a sheet that counted it quoted the owner nothing for files Save was
  // going to fetch, and a book kept on the strength of it lost them at the
  // next release.  The question the sheet is really asking is "what does
  // this phone hold ONCE, for everything, and will still hold next month",
  // and the answer to that is the shared cache.  Read at the moment it is
  // asked, so a sheet opened before another book kept its notes and one
  // opened after each say what was true when it was drawn.
  const s = await caches.open(SHARED);
  const mine = await s.keys();
  // as addresses, the way lib/offline.py names them, so that the page can
  // tick a recording by comparing it with the list the computer gave
  const path = q => { const u = new URL(q.url); return u.pathname + u.search; };
  const once = [...new Set(mine.map(path))];
  reply({inside: id, urls: reqs.map(path), shared: once});
}

async function kept(reply) {
  const keys = await caches.keys();
  const out = [];
  for (const k of keys) {
    if (!k.startsWith(KEPT)) continue;
    const c = await caches.open(k);
    const reqs = await c.keys();
    out.push({id: k.slice(KEPT.length), files: reqs.length});
  }
  reply({keptList: out});
}

/* ---- a book kept in the background: Android's own download --------------
   THE OWNER'S DECISION OF 2026-09-23.  A narrated book is hundreds of
   megabytes, often in ONE recording, and `keep` above could not bring it:
   it runs inside one message event, and Chromium stops a worker whose event
   has run five minutes (driven: stopped at 310 s, the fetch in flight cut,
   no `catch` run, no `{kept}` sent).  So where the page's registration has
   Background Fetch, a BOOK is handed to the browser's own download machinery
   instead, which goes on with the page closed, the browser closed and the
   phone locked, and shows Android's own notification with its own Cancel.
   Everywhere else -- the iPad, Firefox -- `keep` above does it exactly as it
   always did: that is not a lesser way, it is the whole feature there.

   THE PAGE STARTS IT, NOT THIS FILE.  Since Chrome 149 a worker may not
   start a background fetch at all (driven: NotAllowedError, "not allowed in
   service worker environments", although `'backgroundFetch' in
   self.registration` is still true here).  lib/keep.js decides, per press,
   on the page's own registration, and starts two downloads: the text first
   (with the notes, which travel with it), then the recordings -- so a book
   opens on a train as soon as its text is in.  It leaves a NOTE for this
   file (`JOBS`), since the download may end with every page closed and a
   worker the browser has only just woken: what the thing is, which of its
   addresses each download holds, what each should weigh, and the registry
   entry to write once it is done.

   THE DOWNLOAD ENDING IS NOT THE KEEP ENDING (the owner's brief).  The
   browser wakes this worker with backgroundfetchsuccess / fail / abort, and
   `settle` then does what `keep` does address by address: looks at each
   answer, puts what is whole where `isShared` says, and says `{kept}` in the
   same words -- to every page, since this event has no page to answer.  A
   success is not taken on trust: a connection refused under the download
   can end in "success" over an EMPTY body with status 200 and the file's own
   Content-Length (driven, four ways), so every answer is measured
   (`arrived`) before it is put away, and a phone that runs out of room while
   putting it away is a keep that did not happen, whatever the download said.

   WHAT A KEEP ENDING PART-WAY LEAVES (the owner): what arrived.  A Cancel on
   either notification stops the whole keep; a file the computer no longer
   has, and no room on the phone, are each said in their own words.  Remove
   (lib/keep.js, /m/kept/) marks the note `removed` first, and then nothing
   of that download is put away at all. */
const JOBS = 'parseh-jobs';            // the notes a background keep leaves for this file and the pages
const JOB = '/__keepjob/';             // their keys: addresses no page ever asks for
const BG = 'parseh-keep:';             // a download's id: BG + token + ':' + part + ':' + thing

function bgId(id) {
  if (typeof id !== 'string' || id.indexOf(BG) !== 0) return null;
  const rest = id.slice(BG.length);
  const a = rest.indexOf(':'), b = rest.indexOf(':', a + 1);
  if (a < 1 || b <= a + 1) return null;
  return {token: rest.slice(0, a), part: rest.slice(a + 1, b), id: rest.slice(b + 1)};
}
const secs = () => Date.now() / 1000;

// A NOTE IS READ WITHOUT MAKING A CACHE: `caches.open` makes one where there
// is none, and a worker woken on a phone that never kept anything in the
// background has no business leaving an empty one behind.
async function jobRead(key) {
  try {
    if (!(await caches.has(JOBS))) return null;
    const res = await (await caches.open(JOBS)).match(new Request(key));
    return res ? await res.json() : null;
  } catch (err) {
    return null;
  }
}
async function jobWrite(key, value) {
  const c = await caches.open(JOBS);
  await c.put(new Request(key), new Response(JSON.stringify(value),
                                             {headers: {'Content-Type': 'application/json'}}));
}

/* IS THIS ANSWER THE FILE, WHOLE?  `whole` is the sheet's own question and
   it is asked here unchanged, with what the record said the file weighs.
   One thing is asked before it, because the background download has a way
   of lying that `keep` never met: an answer whose body is shorter than the
   length it carries -- empty, when the connection was refused -- which
   `whole` passes wherever the record promises nothing about the bytes (a
   composed page, the `reader/` alias).  A Blob's size is the body on the
   disk, and reading it costs no memory. */
async function arrived(res, url, want) {
  const said = parseInt(res.headers.get('content-length') || '', 10);
  if (said >= 0) {
    let size = -1;
    try { size = (await res.clone().blob()).size; } catch (err) { size = -1; }
    if (size >= 0 && size !== said) return false;
  }
  try {
    return await whole(res.clone(), Object.assign({}, want || {}, {url: url}));
  } catch (err) {
    return false;
  }
}

/* A CANCEL STOPS THE WHOLE KEEP (the owner, 2026-09-23).  A press is two
   downloads, and the notification's Cancel belongs to one of them; a book
   whose text was cancelled and whose recordings then came anyway is not what
   anybody pressing Cancel meant.  So the other download of the same press is
   stopped too -- `abort` is allowed here where `fetch` is not. */
async function stopOthers(at, head) {
  const bf = self.registration.backgroundFetch;
  if (!bf) return;
  for (const part of Object.keys(head.parts || {})) {
    if (part === at.part) continue;
    try {
      const r = await bf.get(BG + head.token + ':' + part + ':' + head.id);
      if (r) await r.abort();
    } catch (err) { /* it had ended already: nothing to stop */ }
  }
}

/* REMOVED WHILE IT WAS COMING.  Nothing of it is put away, and what a put
   already in flight wrote is taken out again: `drop` may have run between
   the note being read and the answer being written, and a `parseh-kept-`
   cache nobody has written down is room nobody can give back (`reclaim`). */
async function thrownAway(head) {
  if (!head || !head.id) return;
  try {
    await caches.delete(KEPT + head.id);
    await reclaim();
  } catch (err) { /* nothing to take out */ }
}

/* THE LINE A PAGE SAYS, and the words are the owner's.  One fact, one set
   of words: cancelled, no room, and a file the computer no longer has are
   three different things and each is said as itself. */
function keptLine(head, all, nothing) {
  const t = head.title || 'it';
  if (all.cancelled) {
    return t + ': ' + (all.here ? 'stopped on this phone' : 'stopped from the notification') +
           (nothing ? ' — nothing of it had come yet' : ' — what had come is on this phone');
  }
  const said = [];
  const n = all.noRoom.length, g = all.gone.length;
  if (n) said.push('no room on this phone for ' + n + ' of its files');
  if (g) said.push(g + ' of its files ' + (g === 1 ? 'is' : 'are') + ' no longer on the computer');
  const rest = all.failed.length - n - g;
  if (said.length && rest > 0)
    said.push(rest + ' more could not be kept — try again with the computer awake');
  if (said.length) return t + ': ' + said.join('; ');
  if (all.failed.length)
    return all.failed.length + ' of its files could not be kept — try again with the computer awake';
  return t + ' is on this phone now';
}

/* AND THE NOTIFICATION'S LAST WORDS, which the browser lets this file change
   once, while the event is running, and never on a Cancel. */
async function lastWords(e, how, at, head, out, end) {
  if (how === 'abort' || typeof e.updateUI !== 'function') return;
  const t = head.title || 'it';
  let title = '';
  const failed = end ? end.failed.length : out.failed.length;
  const full = end ? end.noRoom : out.noRoom.length;
  if (full) title = t + ': no room on this phone';
  else if (failed) title = t + ': ' + failed + ' of its files could not be kept';
  else if (end) title = t + ' is on this phone now';
  else if (at.part === 'text') title = t + ' — its text is on this phone; its recordings are next';
  if (!title) return;
  try { await e.updateUI({title: title}); } catch (err) { /* the event is over: nothing to say */ }
}

/* WHEN EVERY DOWNLOAD OF THE PRESS HAS BEEN PUT AWAY, the keep has ended.
   Each download writes its own outcome before it looks at the others', so
   the second of two to finish always sees both; if both see both, the page
   hears `{kept}` twice for one token and writes it down once. */
async function finish(e, how, at, head, out) {
  const outs = {};
  for (const part of Object.keys(head.parts || {})) {
    const o = part === at.part ? out : await jobRead(JOB + head.token + '/' + part);
    if (!o || o.settling) return lastWords(e, how, at, head, out, null);
    outs[part] = o;
  }
  const all = {failed: [], gone: [], noRoom: [], put: 0, cancelled: false, here: false};
  for (const part of Object.keys(outs)) {
    const o = outs[part];
    all.failed = all.failed.concat(o.failed || []);
    all.gone = all.gone.concat(o.gone || []);
    all.noRoom = all.noRoom.concat(o.noRoom || []);
    all.put += (o.put || []).length;
    if (o.cancelled) all.cancelled = true;
    if (o.here) all.here = true;
  }
  const nothing = !all.put;
  // WHAT BROUGHT NOTHING IS NOT WRITTEN DOWN where writing it would say
  // something untrue: a first keep (the book is not kept), and Keep it again
  // (the phone still holds the version it had, and the out-of-date bar must
  // go on offering the new one).  A Save that brought nothing still freed
  // what he unticked, and its entry says so.
  const drop = nothing && !!(head.first || head.again);
  const end = {kept: head.id, token: head.token, done: (head.urls || []).length,
               of: (head.urls || []).length, failed: all.failed, already: head.already || 0,
               version: head.version || '', gone: all.gone.length, noRoom: all.noRoom.length,
               cancelled: all.cancelled, nothing: drop,
               line: keptLine(head, all, nothing),
               bad: !!(all.failed.length || all.cancelled),
               // WHAT A FIRST KEEP THAT BROUGHT NOTHING WRITES DOWN IS NOTHING
               // (the owner: the book stays not kept and its button says Keep
               // on this phone).  A Save that brought nothing still happened:
               // what it freed is gone, and its entry says what is ticked now.
               entry: drop ? null : head.entry,
               finished: secs()};
  try { await jobWrite(JOB + head.token + '/end', end); } catch (err) { /* the pages still hear it */ }
  if (end.nothing && head.first) {
    // and the empty cache the page made for it goes, or `reclaim` would read
    // it as something still kept and never give the shared room back
    try {
      const c = await caches.open(KEPT + head.id);
      if (!(await c.keys()).length) { await caches.delete(KEPT + head.id); await reclaim(); }
    } catch (err) { /* it stays: reconcile's business then */ }
  }
  await tellClients(end);
  return lastWords(e, how, at, head, out, end);
}

async function settle(e, how) {
  const at = bgId(e.registration.id);
  if (!at) return;
  const key = JOB + at.token, mine = key + '/' + at.part;
  const head = await jobRead(key);
  // no note, or one that says Remove: nothing of this download is kept
  if (!head || head.removed) return;
  // SAID FIRST, so that a page looking in while this runs knows it is being
  // put away and not lost; the browser stops an event after five minutes,
  // and a note left saying "settling" long after is how a page tells that
  try { await jobWrite(mine, {part: at.part, settling: true, at: secs()}); } catch (err) { /* go on */ }
  if (how === 'abort' && !head.overrun) await stopOthers(at, head);
  const out = {part: at.part, put: [], failed: [], gone: [], noRoom: [],
               cancelled: how === 'abort' && !head.overrun,
               here: how === 'abort' && head.stopped === 'here', finished: 0};
  // THE BROWSER RAN OUT OF ROOM while it was storing the download: what had
  // not come is "no room", in its own words, not an ordinary failure
  const quota = how === 'fail' && e.registration.failureReason === 'quota-exceeded';
  sawVideoLib(head.urls);
  const cache = await caches.open(KEPT + head.id);
  const shared = await caches.open(SHARED);
  const mineUrls = (head.parts || {})[at.part] || [];
  const own = {};
  for (const u of mineUrls) {
    try { own[new URL(u, self.location.origin).href] = u; } catch (err) { own[u] = u; }
  }
  const seen = {};
  let records = [];
  try { records = await e.registration.matchAll(); } catch (err) { records = []; }
  let full = false;
  for (const r of records) {
    const url = own[r.request.url] || r.request.url;
    if (seen[url]) continue;
    seen[url] = true;
    let res = null;
    // an answer that had not come when the download ended -- a Cancel, or the
    // end of the road -- is not kept, and is one of the files that failed
    try { res = await r.responseReady; } catch (err) { res = null; }
    if (!res) { out.failed.push(url); if (quota) out.noRoom.push(url); continue; }
    if (!res.ok) {
      out.failed.push(url);
      if (res.status === 404 || res.status === 410) out.gone.push(url);
      continue;
    }
    if (full) { out.failed.push(url); out.noRoom.push(url); continue; }
    if (!(await arrived(res, url, (head.want || {})[url]))) { out.failed.push(url); continue; }
    // and Remove may have been pressed while this was running
    const now = await jobRead(key);
    if (!now || now.removed) return thrownAway(head);
    try {
      // with the digest the page's note says the computer gave it (`stamped`)
      await ((await isShared(url)) ? shared : cache)
        .put(new Request(url), stamped(res, ((head.want || {})[url] || {}).digest));
      out.put.push(url);
    } catch (err) {
      out.failed.push(url);
      // THE PHONE IS FULL, and every put after this one would fail the same
      // way: the rest are counted as the same fact rather than tried
      if (err && err.name === 'QuotaExceededError') { full = true; out.noRoom.push(url); }
    }
  }
  for (const u of mineUrls) if (!seen[u]) { out.failed.push(u); if (quota) out.noRoom.push(u); }
  const last = await jobRead(key);
  if (!last || last.removed) return thrownAway(head);
  out.finished = secs();
  try { await jobWrite(mine, out); } catch (err) { /* the outcome is still told below */ }
  return finish(e, how, at, head, out);
}

self.addEventListener('backgroundfetchsuccess', e => {
  if (bgId(e.registration.id)) e.waitUntil(settle(e, 'success').catch(() => {}));
});
self.addEventListener('backgroundfetchfail', e => {
  if (bgId(e.registration.id)) e.waitUntil(settle(e, 'fail').catch(() => {}));
});
self.addEventListener('backgroundfetchabort', e => {
  if (bgId(e.registration.id)) e.waitUntil(settle(e, 'abort').catch(() => {}));
});
/* A TAP ON THE FINISHED NOTIFICATION OPENS THE BOOK (the owner).  Its page is
   its id -- a book is kept under its reader's own address -- so nothing here
   depends on a note that may have been written down and cleared an hour ago,
   which is how long Android leaves a finished notification up. */
self.addEventListener('backgroundfetchclick', e => {
  const at = bgId(e.registration.id);
  if (!at) return;
  e.waitUntil(self.clients.matchAll({type: 'window', includeUncontrolled: true}).then(all => {
    for (const c of all) {
      try {
        if (new URL(c.url).pathname === at.id && 'focus' in c) return c.focus();
      } catch (err) { /* not a page of ours */ }
    }
    return self.clients.openWindow(at.id);
  }).catch(() => {}));
});

/* ---- answering --------------------------------------------------------- */
function needsComputer(url) {
  return NEEDS_COMPUTER.some(re => re.test(url));
}

/* A DOOR: an address that answers with what the computer knows, rather than
   with a file that is the same every time.  Every one of them in this toolbox
   is under an `api/` (the decks', the studio's, the player's, and the seams'
   list a reader asks for at `<mount>/api/marks`) or is one of the two `__`
   doors a kept thing carries; a page, a sheet, a script, a picture, a
   recording or a note's bare page is not.  See `answer` for why the
   difference matters -- and the owner's 7 of 2026-09-23 for why the marks
   list in particular must be one: a note written at the desk has to appear
   in the seam the next time the phone can reach the computer, without
   anything being kept again. */
function isDoor(url) {
  return /\/api\//.test(url.pathname) || /\/__(offline|shell)$/.test(url.pathname);
}

/* The fresh answer into whichever cache already held that address -- the kept
   thing's own, or the shell's -- so the copy that answers when the computer is
   away is the last one the computer gave, and nothing is cached that was not
   being kept already. */
function stash(request, res) {
  caches.keys().then(async keys => {
    for (const k of keys) {
      if (!k.startsWith(KEPT) && k !== SHARED && k !== SHELL) continue;
      const c = await caches.open(k);
      if (await c.match(request, {ignoreVary: true})) {
        await c.put(new Request(request.url), res);
        return;
      }
    }
  }).catch(() => {});
}

function refused() {
  return new Response(JSON.stringify({ok: false, offline: true,
                                      error: 'this needs the computer, which cannot be reached'}),
                      {status: 503, headers: {'Content-Type': 'application/json; charset=utf-8'}});
}

/* A FETCH WITH A DEADLINE.  `fetch` gives up when the socket does, and a
   socket opened towards a computer that is asleep on a network that is up
   settles neither way: that is what left the app on its splash.  The race is
   deliberately not an abort -- a browser that has no AbortController on its
   worker would then answer nothing at all -- so the hanging fetch is left to
   the browser to bury while the phone answers in its place. */
function reach(request, ms) {
  return within(fetch(request), ms || DEADLINE);
}

// A fetch already made, waited for again: the deadline's error says that it
// was the deadline (`late`), so that it is not taken for the network's own
function within(fetching, ms) {
  return Promise.race([
    fetching,
    new Promise((_, no) => setTimeout(() => {
      const err = new Error('the computer did not answer within the deadline');
      err.late = true;
      no(err);
    }, ms)),
  ]);
}

/* A NAVIGATION IS GIVEN THE DEADLINE, AND AT THE DEADLINE THE PAGE IS ASKED
   (the owner, 2026-09-28).  It used to be given the deadline and no more: a
   page nothing had kept, asked of a computer that was ALIVE and took longer
   than two and a half seconds to begin -- a big document, a tunnel in a slow
   hour -- was answered with the page that says Parseh cannot be reached, and
   Try again met the same deadline and the same page.  That is one slow answer
   taken for a verdict, which is the one thing offline is not.

   So at the deadline the worker does not decide by itself.  It asks the pages
   whether the computer is answering (`computerAnswers`), and while it is, it
   goes on waiting for the very fetch it made -- never a second one, so a page
   that is slow to make is made once -- until PATIENT from the start.  Where it
   is not, or nobody says, the answer is what it always was.  A refusal never
   gets here: it fails at once and falls at once. */
async function navigate(request) {
  const began = Date.now();
  const coming = fetch(request);
  try {
    return await within(coming, DEADLINE);
  } catch (err) {
    if (!err.late || !(await computerAnswers())) throw err;
  }
  return await within(coming, began + PATIENT - Date.now());
}

/* WHETHER THE COMPUTER IS ANSWERING, asked of the pages and not of the
   computer.  The page's poll (lib/activity.js) is the one asker of the
   computer, and all that is asked of a page here is to ask it NOW: each page
   that is open is sent one message with a port, and answers on the port
   `there` -- when its own question has been answered by the computer AFTER
   this one was put -- or `away` at once, when it has judged the computer gone
   already.  Nothing older counts.  What a page said a few seconds ago is no
   evidence of a computer that has been suspended since, and the silence of a
   suspended computer is just what a page cannot tell from a slow one for
   forty-five seconds: so a page that has heard nothing in ASKED -- or is
   frozen, or hidden, or has no poll -- is a silence, and a silence is a no.

   ONE `there` FROM ANY PAGE IS ENOUGH, since a computer that answered one
   page is there.  No page open at all -- a link typed in a fresh tab, or
   opened from another app -- has nobody to ask and is a no at once, which is
   where it stood before the pages were asked at all. */
async function computerAnswers() {
  let pages = [];
  try { pages = await self.clients.matchAll({type: 'window', includeUncontrolled: true}); }
  catch (err) { /* nobody to ask */ }
  if (!pages.length) return false;
  return new Promise(done => {
    let left = pages.length;
    const lines = [];
    const end = yes => { clearTimeout(gone); lines.forEach(line => line.port1.close()); done(yes); };
    const gone = setTimeout(() => end(false), ASKED);
    const said = there => {
      if (there) end(true);
      else if (--left === 0) end(false);
    };
    for (const page of pages) {
      try {
        const line = new MessageChannel();
        lines.push(line);
        line.port1.onmessage = e => said(!!e.data && e.data.state === 'there');
        page.postMessage({reachAsk: true}, [line.port2]);
      } catch (err) { said(false); }
    }
  });
}

// a range, cut out of a whole kept response (the Cache API answers no ranges)
async function ranged(res, range) {
  const m = /^bytes=(\d*)-(\d*)$/.exec((range || '').trim());
  if (!m) return res;
  const body = await res.arrayBuffer();
  const size = body.byteLength;
  let start = m[1] === '' ? null : parseInt(m[1], 10);
  let end = m[2] === '' ? null : parseInt(m[2], 10);
  if (start === null && end === null) return res;
  if (start === null) { start = Math.max(0, size - end); end = size - 1; }        // bytes=-N
  else if (end === null || end >= size) end = size - 1;
  if (start > end || start >= size)
    return new Response(null, {status: 416, headers: {'Content-Range': 'bytes */' + size}});
  const head = new Headers(res.headers);
  head.set('Content-Range', `bytes ${start}-${end}/${size}`);
  head.set('Content-Length', String(end - start + 1));
  head.set('Accept-Ranges', 'bytes');
  return new Response(body.slice(start, end + 1), {status: 206, statusText: 'Partial Content',
                                                   headers: head});
}

async function tellClients(what) {
  const all = await self.clients.matchAll({type: 'window'});
  all.forEach(c => c.postMessage(what));
}

// the small parts of a kept thing are looked at again behind the page, so the
// next open has whatever the computer has changed (§19.4) -- and so is a shell
// page, which would otherwise show yesterday's shelf until the worker's own
// version moved.  When a shell page has really changed the clients are told,
// and lib/keep.js swaps the list in place of the one the page opened with.
//
// EVERY COPY OF IT, NOT THE FIRST ONE FOUND (TO-DO §13.16, which asked that
// this be confirmed -- and it was not so).  /lib/'s scripts are in the app's
// way in AND in the cache kept once for the phone, and the fresh answer used
// to go into whichever of the two this phone had made first, and stop.
// `caches.match` answers from that same first cache, so the page ran the new
// script while the other copy stayed the old release's for good: never
// answered while the first was there, never renewed -- and it is the copy the
// keep check reads, and the one a kept page falls back on the day a release
// drops the way in.  So each cache that holds the address gets it, the app's
// own two pages among them (a release's /m/kept/ used to wait for the next
// worker to be installed before anybody saw it).
//
// AND WHAT IT PUTS INTO A KEPT THING CARRIES ITS DIGEST (`stamped`), taken of
// the body it has just read whole from the computer: that is the file the
// computer has now, and the keep check measures the next release against it.
// Read once, under the ceiling the check reads under; a body that breaks off
// on the way is no answer, and nothing is put.  Above the ceiling the answer
// goes in as it came, as it always did -- nobody was going to hash it.
function renew(request) {
  const url = request.url;
  if (/\.(mp3|m4a|ogg|opus|wav|flac|mp4|webm|mkv|mov)(\?|$)/i.test(url)) return;  // never the heavy ones
  const nav = request.mode === 'navigate';
  fetch(new Request(url, {cache: 'no-store', credentials: 'same-origin'})).then(async res => {
    if (!res || !res.ok) return;
    const said = parseInt(res.headers.get('content-length') || '', 10);
    let body = null, sum = null;
    if (!(said > READABLE)) {
      try { body = await res.clone().arrayBuffer(); } catch (err) { return; }
    }
    const keys = await caches.keys();
    for (const k of keys) {
      if (!k.startsWith(KEPT) && k !== SHARED && k !== SHELL && k !== APP) continue;
      const c = await caches.open(k);
      const had = await c.match(request, {ignoreVary: true});
      if (!had) continue;
      if (k === SHELL && nav) {
        const was = await had.clone().text();
        const now = body ? new TextDecoder().decode(body) : await res.clone().text();
        await c.put(new Request(url), body ? fresh(res, body, '') : res.clone());
        if (was !== now) await tellClients({shellFresh: url});
        continue;
      }
      if ((k.startsWith(KEPT) || k === SHARED) && body && self.crypto && self.crypto.subtle) {
        if (sum === null) sum = hex(await self.crypto.subtle.digest('SHA-256', body));
        await c.put(new Request(url), fresh(res, body, sum));
        continue;
      }
      await c.put(new Request(url), body ? fresh(res, body, '') : res.clone());
    }
  }).catch(() => {});
}

async function answer(r, url) {
  const nav = r.mode === 'navigate';
  // THE LISTS A LIBRARY PAGE ASKS FOR are the other way round from a page:
  // the computer's answer when it comes within the deadline, the phone's last
  // copy when it does not.  The page paints whichever arrives and knows
  // nothing about it.  The copy is matched at the bare address, because the
  // studio's library asks with the search and the sort in the query.
  if (await isShellApi(url)) {
    const bare = new Request(url.pathname);
    try {
      const res = await reach(r);
      if (res && res.ok) {
        const c = await caches.open(SHELL);
        c.put(bare, res.clone()).catch(() => {});
      }
      return res;
    } catch (err) {
      const had = await caches.match(bare, {ignoreVary: true});
      return had || refused();
    }
  }
  // A DOOR IS NOT A FILE.  Keeping a deck or a document copies its doors too,
  // so that it opens with the computer away -- but a door's answer is what the
  // computer knows NOW: who has this deck, what is due, what has been
  // answered.  Served from the kept copy while the computer is right there,
  // the page reads yesterday's state and acts on it: taking a deck out (which
  // keeps it first) left the page showing a deck that was not out, because the
  // record it re-read came out of the copy taken a second earlier.  So a door
  // asks the computer first, under the same deadline as everything else, and
  // the kept copy is what answers when the computer does not -- which is the
  // whole of what keeping was for.
  if (isDoor(url)) {
    const had = await caches.match(r, {ignoreVary: true});
    try {
      // WHICH OF THE TWO DEADLINES, and neither of them is none.  With a kept
      // copy in hand the short one (DEADLINE): waiting past it is the worse
      // of the two answers, since the phone has one ready.  With no copy the
      // patient one (PATIENT), which used to be no deadline at all -- and a
      // door with nothing behind it is exactly where a fetch hangs for ever,
      // because the socket towards a sleeping computer never settles either
      // way.  PATIENT is generous because the other failure is real too: a
      // door that is honestly slow and would have succeeded must not be cut
      // short when nothing can take its place.
      const res = await reach(r, had ? DEADLINE : PATIENT);
      if (res && res.ok) stash(r, res.clone());
      return res;
    } catch (err) {
      if (had) return had;
      if (needsComputer(url.pathname)) return refused();
      throw err;
    }
  }
  // WHAT IS KEPT ANSWERS FIRST, whether the computer is there or not -- and so
  // does the way in, which is kept for exactly that reason
  let hit = await caches.match(r, {ignoreVary: true, ignoreSearch: false});
  /* AND A KEPT PAGE REACHED WITH A QUERY IS STILL THAT PAGE.  A query means a
     different answer at a DOOR, and those are answered above, where the
     search is part of the address.  A PAGE is another matter: cramming a
     picked handful opens <deck>/cram?selected=<ids>, where the ids are
     whatever was ticked a moment ago -- an address no record could ever have
     named, for a page that was kept.  Matched strictly it missed the cache
     and fell to the offline page with the whole deck sitting on the phone.
     So a navigation that misses asks once more without the query; what the
     page then does with the ids it was given is the page's own affair, and
     everything it needs is kept. */
  if (!hit && nav && url.search)
    hit = await caches.match(r, {ignoreVary: true, ignoreSearch: true});
  if (hit) {
    renew(r);
    const range = r.headers.get('range');
    return range ? ranged(hit.clone(), range) : hit;
  }
  try {
    /* A SUBRESOURCE HAS A DEADLINE TOO, and until now it had none: a
       navigation was raced and everything else was handed a bare fetch.  So
       ONE address a kept page asks for and nobody kept -- a script, a
       stylesheet, a picture -- was enough to hold that page open for ever on
       the network this worker exists for, a phone with wifi and a computer
       asleep behind it.  That is exactly how a single missing 39 kB script
       (/lib/mt.js, a parser-blocking one) stopped every kept book from
       opening in airplane mode, half drawn, with no error anywhere (the
       owner, 2026-09-23).  It is the long deadline, because a subresource
       that is merely slow has nothing to fall back to either -- but it is a
       deadline, and a page that ends with a broken picture or an unstyled
       paragraph is a page, where one that never parses is nothing.  A
       NAVIGATION is the one that is given the short deadline, and is asked
       about at it (`navigate`). */
    return await (nav ? navigate(r) : reach(r, PATIENT));
  } catch (err) {
    if (nav) {
      // neither kept nor part of the way in: this is what /m/offline/ is for
      const page = await caches.match(OFFLINE);
      if (page) return page;
    }
    if (needsComputer(url.pathname)) return refused();
    throw err;
  }
}

/* AND ONE ADDRESS THIS WORKER NEVER ANSWERS: `/__activity`, the page's one
   question "is the computer there?" (lib/activity.js; TO-DO §2.24).  It used
   to be a door with no copy, so it waited PATIENT and then answered a 503 of
   its own -- which made a socket refused in a millisecond and half a minute
   of silence look exactly alike to the page, and gave the page's thirty
   seconds and the worker's three no way to agree.  Left to the browser, the
   page hears the network itself: a refusal fails at once, silence does not
   end, and the page cancels an ask it has given up on -- which frees the
   connection, as a race here never did. */
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET') return;                       // nothing that writes
  const url = new URL(r.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === '/__activity' || MADE_ON_DEMAND.test(url.pathname)) return;
  e.respondWith(answer(r, url));
});
