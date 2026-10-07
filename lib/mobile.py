#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The mobile interface's pages that the server writes (docs/mobile.md).

    mobile.books_page()     /m/books/, the book shelf as a phone reads it
    mobile.videos_page()    /m/videos/, the channels, as a phone reads them
    mobile.channel_page(s)  /m/videos/<channel>/, one channel's videos
    mobile.install_page(t)  /m/install/, installing the mobile interface as an app
    mobile.offline_page()   /m/offline/, what the app shows when the server is away
    mobile.kept_page()      /m/kept/, everything kept on this phone (§19.2)
    mobile.manifest()       /manifest.webmanifest, the app's description
    mobile.app_head()       the tags that make a page part of the app
    mobile.mode_switch()    the Browser | Mobile switch, for a page's bar

The mobile interface is a second set of pages made to be READ on a phone:
one column, targets a finger can hit, and nothing on them that edits.  Most
of them are a second layout of the page they stand for -- the hub, the
exercise decks, a book's reader -- and need nothing here.  The book library
is the exception: books/index.html is a static page (lib/make_index.py)
written when a book is built or put on the shelf, so a layout added to it
would reach nobody's library until the next build.  Its mobile version is a
page of its own instead, written on every request from the shelf itself,
and lib/parseh.js routes every link to /books/ there in the mobile mode.

WHAT THE SHELF SAYS.  What the browser library's card says about a book,
less everything that manages the shelf: no delete, no build, no bundle
coming in or going out.  A book whose reader has never been built has
nothing to open, and a phone cannot build it, so its card says so and is not
a link.  Everything that CAN be tapped goes to a reader, where the mobile
layer (lib/mobilereader.js) takes over.

THE SHELVES ARE PART OF THE APP SHELL (the owner's 1 and 2, 2026-09-23;
lib/offline.py, shell()).  Kept by the worker, they open with the computer
away -- so what they show is as old as the last time it was reached.  The one
block each page is built round therefore carries `data-shell-block`: when the
worker has read the page again and found it changed, lib/keep.js puts the
fresh block in place of the one the page opened with.  /m/kept/ carries no
such mark: its list is the phone's own and the computer knows nothing of it.
"""
import html
import json
import os
import re
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import books as booklib                                      # noqa: E402
import languages                                             # noqa: E402
import make_index                                            # noqa: E402
import project                                               # noqa: E402  where Parseh lives: the phone app's icons

APP_NAME = "Parseh"


def esc(s):
    return html.escape(s or "", quote=True)


# ---------------------------------------------------------------- the app
# PARSEH AS AN APP (docs/mobile.md).  A phone's browser installs a site as an
# app -- an icon on the home screen, opening on the whole screen with no
# address bar -- when the site describes itself (the manifest below, linked
# from every page by app_head()), has a service worker (lib/sw.js, served at
# /sw.js), and is served over https with a certificate the phone trusts
# (serve.py's authority, handed over by /m/install/).  The app is the MOBILE
# INTERFACE: it opens on the mobile hub, with the mode set to mobile.
ICONS = "/lib/icons/"
# WHERE THE MANIFEST NAMES THE ICONS, which is not where the pages fetch
# them.  Chrome does not build a phone's app itself: it sends the manifest
# to a Google server, and THAT server fetches the icon addresses in it and
# packs them into the app.  It is out on the internet; this Parseh is on a
# home network or a tailnet, where nothing outside can reach it -- so an
# icon named on this server is an icon that server cannot fetch, and the
# build fails with no reason given: the install button vanishes and
# chrome://webapks stays empty.  The icons are in the repository as well,
# so the project's GitHub Pages serves the same four files at an address
# anyone can reach, and the manifest names them there.  Nothing else moves:
# the pages, the apple-touch icon and what is kept on the phone all stay on
# this server.  Empty this to name them here again.
PUBLIC_ICONS = project.ICONS_URL
# the light palette's ground (lib/parseh.css --bg), which the app's splash
# screen and the pages start on; and the dark one's, for a phone set dark
LIGHT_BG, DARK_BG = "#f3eff1", "#171214"
ACCENT = "#be3455"


def mints(user_agent):
    """Does this browser build the app on a server of somebody else's?

    ONLY CHROME ON ANDROID DOES.  It sends the manifest away to be packed
    into a real Android app (a WebAPK), and the server that packs it fetches
    the icon addresses itself, from out on the internet, where this Parseh
    cannot be reached.  That is the whole reason PUBLIC_ICONS exists -- and
    it is a reason that holds for that one browser and no other.  An iPhone
    builds nothing: it fetches the icon ITSELF, from the phone, so an
    address out on the internet is one more thing that can be out of reach
    -- and when an iPhone can fetch no icon at all it draws its own tile,
    the app's first letter on the theme colour, and keeps it until the icon
    is taken off the home screen and put back.  That is what he saw: the
    share sheet right (it reads the apple-touch tag, which is here) and Add
    to Home Screen wrong (it reads the manifest, which was pointing out).

    Chromium's other Android browsers -- Edge, Samsung Internet -- mint the
    same way and carry `Chrome/` too; Firefox on Android does not, and adds
    a plain shortcut with an icon it fetches itself.
    """
    ua = user_agent or ""
    return "Android" in ua and "Chrome/" in ua


def icon_src(name, public):
    """Where the manifest sends a browser for one icon: the public copy for
    the one browser that needs it, this server for everybody else."""
    return ((PUBLIC_ICONS if public else "") or ICONS) + name


def manifest(user_agent=None):
    """The app's description, as /manifest.webmanifest serves it.

    The icons it names depend on who is asking (`mints`): everything else in
    it is the same for everyone.
    """
    public = mints(user_agent)
    return {
        "id": "/",
        "name": APP_NAME,
        "short_name": APP_NAME,
        "description": "Reading editions with their narration, videos with their "
                       "transcripts, and exercise decks: the mobile interface.",
        "lang": "en",
        "dir": "ltr",
        # the app opens on the mobile hub, in the mobile mode (parseh.js
        # takes ?mode= off the address once it has set it)
        "start_url": "/?mode=mobile",
        "scope": "/",
        # the whole screen, a phone's own bars and all, where the phone can
        # (Android); where it cannot, an app's window with no address bar
        "display": "fullscreen",
        "display_override": ["fullscreen", "standalone"],
        "orientation": "any",
        "background_color": LIGHT_BG,
        "theme_color": ACCENT,
        "icons": [
            {"src": icon_src("parseh-192.png", public), "sizes": "192x192", "type": "image/png",
             "purpose": "any"},
            {"src": icon_src("parseh-512.png", public), "sizes": "512x512", "type": "image/png",
             "purpose": "any"},
            {"src": icon_src("parseh-maskable-512.png", public), "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
            # AND THE ONE AN IPHONE TAKES, off this server.  Since iOS 16.4
            # an iPhone reads the manifest's icons too, and picks the one
            # whose size it wants: 180, which is this and none of the three
            # above.  It is square and opaque where they are circles on
            # nothing, and it is on this server, so a phone that is away
            # still has it -- where an iPhone that can fetch no icon at all
            # draws its own tile instead, the app's first letter in the
            # theme colour, and keeps it until the icon is taken off the
            # home screen and put back.
            {"src": ICONS + "apple-touch-icon.png", "sizes": "180x180", "type": "image/png",
             "purpose": "any"},
        ],
    }


# THE WORKER, AS IT IS SERVED (TO-DO §13.16, the app's half of an update).
# A browser installs a new service worker only when the bytes of /sw.js
# change, and lib/sw.js changes only when somebody edits it -- so a release
# that happened not to touch it left every phone on the old worker, with the
# old way in and not a word said.  So the release is written into the worker
# as it is served: its version (lib/version.py, the one place it is read) and
# its build, the commit in the release's own manifest where the install has
# one.  Every release is then new bytes, every phone that reaches the computer
# takes a new worker, and that worker is what tells the page, in a line, that
# Parseh was updated (lib/sw.js, `announce`; lib/keep.js).  The build is for
# the one case the version cannot see: the same version installed twice, which
# is how a release nobody has seen yet is fixed and tried again.
#
# Two placeholders, each a quoted JavaScript string in lib/sw.js, each
# replaced by a JSON string: a version is letters, digits and dots and a
# commit is hex, but what is written into a script is written escaped.
WORKER = os.path.join(LIB, "sw.js")
WORKER_MARKS = (b"'__PARSEH_RELEASE__'", b"'__PARSEH_BUILD__'")
# where a release's manifest sits in an install (lib/release.py, MANIFEST)
RELEASE_MANIFEST = ".parseh-release.json"
_build = None


def release_build():
    """The commit this install was built from, twelve hex digits, or "".

    Read once: the manifest is written by the installer and the updater, both
    of which start the server again afterwards.  An install with no manifest
    -- a git checkout, a copy made before releases had one -- has no build,
    and its worker changes only with its version.
    """
    global _build
    if _build is None:
        _build = ""
        try:
            with open(os.path.join(os.path.dirname(LIB), RELEASE_MANIFEST),
                      encoding="utf-8") as fh:
                commit = str(json.load(fh).get("commit") or "")
            if re.fullmatch(r"[0-9a-f]{7,64}", commit):
                _build = commit[:12]
        except (OSError, ValueError, AttributeError):
            pass
    return _build


def worker():
    """/sw.js as the server answers it: lib/sw.js with this Parseh's version
    and build written in (see WORKER_MARKS).  Read from the disk every time,
    as it always was, so an edit to the worker is served without a restart."""
    import version                  # the one reader of VERSION (TO-DO §16.1)
    with open(WORKER, "rb") as fh:
        js = fh.read()
    for mark, value in zip(WORKER_MARKS, (version.VERSION, release_build())):
        js = js.replace(mark, json.dumps(value).encode("utf-8"))
    return js


# THE PAGE ARRIVES ALREADY KNOWING (the owner's rule of 2026-09-23).
#
#   "If the page knows the machine is offline when you click a thing, the
#    page you arrive at should already know it is offline and act
#    accordingly.  A book, a notebook, a deck of exercises does not change
#    from offline to online mid-use.  If I enter offline they must be the
#    offline version, full stop; if I want the online version I leave and
#    come back."
#
# lib/keep.js writes down what it found under `parseh_away`, with the terms
# it is good for in the entry itself -- but keep.js is DEFERRED, and a page's
# own scripts are not: a plain script at the foot of the body runs before a
# deferred one in the head.  So every page used to take its first breath
# believing the computer was there, whatever the page before it had learnt,
# and the ones that ask something on sight asked it.  On this computer a
# wrong guess is refused in microseconds; on a phone whose tunnel has gone
# the socket answers NOTHING and the page hangs on it for ever.
#
# This is the first thing on every page of the app, before any script of its
# own: the memory, read, and the mark set on <html> that everything else
# already keys off.  Nothing fetches, nothing waits -- it is a localStorage
# read and an attribute -- and the page's one question (lib/activity.js)
# follows a moment later and either confirms the mark or takes it off in the
# page's first breath.  Once confirmed it stays for the page's life: that is
# the second half of the rule, and it lives in lib/keep.js (`paintAway`).
#
# The mark says `assumed`: what the page before found, not what this one has,
# and an assumed away refuses no write (static/app.js, `api`) -- only one the
# page has confirmed does.
#
# AND NEVER ON A REFRESH (the owner's fall-back, 2026-09-24): "if we refresh
# the page, then it is forced to check again if the computer is online -- so
# upon refreshing, do not assume still offline."  Every refresh -- F5, the
# browser's button, a finger pulling the page down, ↻ -- is reported as
# "reload", already here in the head, the worker's cached copy included
# (driven in Chromium and Firefox); the older performance.navigation says the
# same where the newer entry is not there yet.  The memory is kept, not
# erased: the question writes it again whatever it finds.  Wrapped in a
# function so that it leaves no global behind for a page's own `let` to
# collide with.
AWAY_BOOT = (
    '<script>/* the state the page before this one found (lib/keep.js, `noted`), '
    'never acted on by a refresh */\n'
    '(function(){try{var a=JSON.parse(localStorage.getItem("parseh_away")||"null"),\n'
    'n=performance.getEntriesByType?performance.getEntriesByType("navigation")[0]:null,\n'
    'r=n?n.type==="reload":!!(performance.navigation&&performance.navigation.type===1);\n'
    'if(!r&&a&&a.away===true&&typeof a.at==="number"&&\n'
    '   Date.now()/1000-a.at<=(typeof a.trusted==="number"?a.trusted:180))\n'
    'document.documentElement.setAttribute("data-parseh-away","assumed");}catch(e){}})();</script>')


def app_head():
    """The tags that make a page part of the app: the manifest (which names
    the icons), the colour of the phone's bars, and Apple's own names for
    the same things (an iPhone reads these when it adds a page to its home
    screen).  Not a favicon: a page keeps its own.  Every page of the mobile
    interface carries them -- the hub, the shelf, the decks -- and
    lib/parseh.js adds them to a page that has none (every book's reader,
    built without them).

    AND THE OFFLINE MARK, set before anything else runs (AWAY_BOOT)."""
    return (AWAY_BOOT + '\n'
            '<link rel="manifest" href="/manifest.webmanifest">\n'
            '<link rel="apple-touch-icon" sizes="180x180" href="%(i)sapple-touch-icon.png">\n'
            '<meta name="theme-color" content="%(l)s" media="(prefers-color-scheme: light)">\n'
            '<meta name="theme-color" content="%(d)s" media="(prefers-color-scheme: dark)">\n'
            '<meta name="mobile-web-app-capable" content="yes">\n'
            '<meta name="apple-mobile-web-app-capable" content="yes">\n'
            '<meta name="apple-mobile-web-app-title" content="%(n)s">\n'
            '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
            % {"i": ICONS, "l": LIGHT_BG, "d": DARK_BG, "n": APP_NAME})


# A BOOK KEPT IN THE BACKGROUND WHILE NO PAGE WAS OPEN (the owner's decision
# of 2026-09-23; lib/keep.js and lib/sw.js, `settle`).  Android's own download
# can end with every page of Parseh closed, and a worker cannot write the
# registry (`parseh_kept` is localStorage): it leaves the end in a note
# instead, with the entry the press made, and the next page that opens writes
# it down and says its line once.  These two pages draw from the registry
# before any script of lib/keep.js could run -- and the offline page has none
# at all, since it must stand alone -- so they do it themselves, first, with
# this, and say so (`parsehMerging`) so that lib/keep.js leaves it to them.
MERGE_JS = r"""
window.parsehMerging = true;
function parsehMerge(then) {
  var JOBS = 'parseh-jobs', JOB = '/__keepjob/', lines = [], over = false;
  // one line per keep for the life of the page, however many times it is
  // asked (the worker may say one keep's end twice)
  var said = parsehMerge.said || (parsehMerge.said = {});
  function done() { if (over) return; over = true; try { then(lines); } catch (e) {} }
  // the list is drawn whatever happens, and never waits on this for long
  setTimeout(done, 3000);
  if (!window.caches) { done(); return; }
  caches.has(JOBS).then(function (y) {
    if (!y) return null;
    return caches.open(JOBS).then(function (c) {
      return c.keys().then(function (ks) {
        var paths = ks.map(function (k) { return new URL(k.url).pathname; });
        var heads = paths.filter(function (p) {
          return p.indexOf(JOB) === 0 && p.slice(JOB.length).indexOf('/') < 0;
        });
        return Promise.all(heads.map(function (p) {
          return Promise.all([c.match(p), c.match(p + '/end')]).then(function (rs) {
            if (!rs[0] || !rs[1]) return null;
            return Promise.all([rs[0].json(), rs[1].json()]).then(function (j) {
              var head = j[0], end = j[1], reg = {};
              // past the deadline the list is drawn already: this end is left
              // as it is, for the next look to write down and say
              if (over) return null;
              try { reg = JSON.parse(localStorage.getItem('parseh_kept') || '{}') || {}; } catch (e) {}
              var was = reg[head.id];
              if (!head.removed) {
                // the entry made at the press, never over a newer one
                if (end.entry && !(was && (was.at || 0) > (head.started || 0))) {
                  var e = {}, k;
                  for (k in end.entry)
                    if (Object.prototype.hasOwnProperty.call(end.entry, k)) e[k] = end.entry[k];
                  e.at = end.finished || Date.now() / 1000;
                  reg[head.id] = e;
                  try { localStorage.setItem('parseh_kept', JSON.stringify(reg)); } catch (x) {}
                }
                if (end.line && !said[head.token || p]) {
                  said[head.token || p] = true;
                  lines.push({line: end.line, bad: !!end.bad});
                }
              } else {
                // removed: nothing to say, and nobody else is to say it either
                said[head.token || p] = true;
              }
              return Promise.all(paths.filter(function (q) {
                return q === p || q.indexOf(p + '/') === 0;
              }).map(function (q) { return c.delete(q); }));
            });
          });
        }));
      });
    });
  }).then(done, done);
}
"""


def offline_page():
    """/m/offline/: what the app shows when the server cannot be reached --
    the computer asleep or off, the phone away from its network.  The
    service worker keeps it (lib/sw.js), so it is written to stand alone:
    no stylesheet, no script from anywhere, both palettes in itself."""
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(app)s is not reachable</title>
<style>
:root{color-scheme:light dark;--bg:%(l)s;--card:#fff;--ink:#241e21;--dim:#6b5d62;--accent:%(a)s;--fg:#fff}
@media (prefers-color-scheme:dark){:root{--bg:%(d)s;--card:#211a1d;--ink:#e6dade;--dim:#ac9ba1;
  --accent:#ee8aa3;--fg:#171214}}
html,body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:480px;margin:0 auto;padding:max(12vh,24px) 20px 24px}
.glyph{display:inline-flex;align-items:center;justify-content:center;width:56px;height:56px;
  border-radius:50%%;background:var(--accent);color:var(--fg);font-size:28px;padding-bottom:6px;
  box-sizing:border-box}
h1{font-size:22px;line-height:1.3;margin:18px 0 8px}
p{margin:0 0 12px;color:var(--dim)}
button{font:inherit;font-size:17px;min-height:52px;width:100%%;margin-top:14px;border:0;
  border-radius:12px;background:var(--accent);color:var(--fg);cursor:pointer}
button:disabled{opacity:.6;cursor:progress}
button.plain{background:transparent;color:var(--ink);border:1px solid var(--dim)}
button[hidden],#tried[hidden]{display:none}
#tried{margin:14px 0 0;padding:10px 14px;border:1px solid var(--accent);border-radius:12px;
  color:var(--ink);background:var(--card)}
h2{font-size:15px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);margin:28px 0 8px}
a.kept{display:flex;align-items:center;min-height:56px;padding:10px 14px;margin-bottom:8px;
  background:var(--card);border-radius:12px;color:var(--ink);text-decoration:none;font-size:17px}
#news p{margin:18px 0 0;padding:10px 14px;border:1px solid var(--accent);border-radius:12px;
  color:var(--ink);background:var(--card)}
</style>
</head><body>
<main>
  <span class="glyph" lang="fa" aria-hidden="true">&#x67E;</span>
  <h1>%(app)s cannot be reached</h1>
  <p>%(app)s runs on your computer, and this device cannot reach it now: the
  computer may be asleep or off, or this device away from its network (and
  from Tailscale, if that is how it reaches it).</p>
  <p>Once the computer is on and %(app)s is started there, try again.</p>
  <!-- TRY AGAIN SAYS THAT IT TRIED (TO-DO §2.28: "the try again button which
       doesn't do anything").  A reload of an address that fails again puts
       up this very page again, word for word, and a person cannot tell a
       press that was heard from one that was not: so the press is written
       down for the page that comes back (tryAgain, below), which says when
       it tried.  GO BACK is a button of its own, for a page the person came
       here FROM: it is not the same thing as trying again, and a computer
       that answers too slowly for this page is not mended by either. -->
  <button type="button" id="again" onclick="tryAgain()">Try again</button>
  <p id="tried" role="status" aria-live="polite" hidden></p>
  <button type="button" id="back" class="plain" onclick="history.back()" hidden>Go back</button>
  <!-- WHAT IS KEPT ON THIS PHONE still works (TO-DO §19.5): this page is
       kept by the worker and stands alone, so the list is written here from
       the phone's own registry rather than asked of anybody. -->
  <h2 id="kepth" hidden>Kept on this phone</h2>
  <div id="kept"></div>
  <div id="news" role="status"></div>
  <script>
  %(merge)s
  /* what came in the background while no page was open is written down
     first, so that the list below includes it (MERGE_JS), and its line is
     said once at the foot */
  parsehMerge(function (lines) {
    var reg = {};
    try { reg = JSON.parse(localStorage.getItem('parseh_kept') || '{}') || {}; } catch (e) {}
    var ids = Object.keys(reg), box = document.getElementById('kept');
    var news = document.getElementById('news');
    lines.forEach(function (l) {
      var p = document.createElement('p');
      p.textContent = l.line;
      news.appendChild(p);
    });
    if (!ids.length) return;
    document.getElementById('kepth').hidden = false;
    ids.sort(function (a, b) { return (reg[b].at || 0) - (reg[a].at || 0); });
    ids.forEach(function (id) {
      var a = document.createElement('a');
      a.href = reg[id].page || id;
      a.textContent = reg[id].title || id;
      a.className = 'kept';
      box.appendChild(a);
    });
  });
  </script>
  <script>
  /* TRY AGAIN TRIES, AND SAYS SO.  The press is written down (this tab's
     own memory, gone with it), the address is loaded again -- which CAN
     succeed, the moment the computer is back, and is the one thing that can
     -- and the page that comes back if it fails again reads the note and
     says when it tried.  Without that a failed try is word for word the page
     that was there before.  Only a note as young as one load counts, and
     only for a page that a reload brought (below): a try that worked leaves
     its note behind, and must not speak for a later failure. */
  var TRIED = 'parseh_tried', TRIED_FOR = 15000, TRIED_WAIT = 8000;
  function tryAgain() {
    var b = document.getElementById('again'), t = document.getElementById('tried');
    try { sessionStorage.setItem(TRIED, JSON.stringify({page: location.href, at: Date.now()})); } catch (e) {}
    b.disabled = true;
    b.textContent = 'Trying\\u2026';
    t.hidden = false;
    t.textContent = 'Asking the computer\\u2026';
    location.reload();
    /* A load that fails puts this page up again within seconds (lib/sw.js,
       DEADLINE), so a page still here after longer than that was not
       replaced -- the address answered with a file, which the browser saves
       and this page stays under.  The button must not stay "Trying…" for
       ever over that. */
    setTimeout(function () {
      b.disabled = false;
      b.textContent = 'Try again';
      t.textContent = 'Tried again at ' + new Date().toLocaleTimeString() + '.';
    }, TRIED_WAIT);
  }
  /* WAS THIS PAGE LOADED BY A RELOAD?  A try that worked leaves its note
     behind, and a NEW visit to the same address a moment later must not be
     told that somebody tried: only a reload can be the answer to a press. */
  function reloaded() {
    try { var n = performance.getEntriesByType('navigation')[0]; if (n) return n.type === 'reload'; } catch (e) {}
    try { return performance.navigation.type === 1; } catch (e) {}
    return true;
  }
  (function () {
    try {
      var note = JSON.parse(sessionStorage.getItem(TRIED) || 'null');
      sessionStorage.removeItem(TRIED);
      if (note && note.page === location.href && Date.now() - note.at < TRIED_FOR && reloaded() &&
          location.pathname !== '/m/offline/') {
        var t = document.getElementById('tried');
        t.hidden = false;
        t.textContent = 'Still cannot reach it. Tried again at ' + new Date().toLocaleTimeString() + '.';
      }
    } catch (e) {}
    /* GO BACK only where there is somewhere to go back to, and never from
       inside a frame, where it would take the whole page back with it */
    if (window.top === window && history.length > 1) document.getElementById('back').hidden = false;
  })();
  </script>
</main>
</body></html>
""" % {"app": APP_NAME, "l": LIGHT_BG, "d": DARK_BG, "a": ACCENT, "merge": MERGE_JS}


# WHAT IS KEPT ON THIS PHONE (TO-DO §19.2).  The list itself is the phone's,
# not the computer's -- what a phone has kept is known to that phone alone
# (lib/keep.js keeps a registry beside the worker's caches) -- so this page is
# a frame the phone fills in, and it works with the computer away as well as
# with it here.  It says what each thing is, how big it was when it was kept,
# when that was, whether its notes came with it, opens each, and gives back
# the room by removing one; and it says how much room the phone has left
# (navigator.storage.estimate).
KEPT_JS = r"""<script>
""" + MERGE_JS + r"""
(function () {
  var list = document.getElementById('m-keptlist'), none = document.getElementById('m-keptnone');
  var JOBS = 'parseh-jobs', JOB = '/__keepjob/', BG = 'parseh-keep:';
  function big(n) {
    n = +n || 0;
    return n >= 1e9 ? (n / 1e9).toFixed(1) + ' GB' : n >= 1e6 ? (n / 1e6).toFixed(1) + ' MB'
         : n >= 1e3 ? Math.round(n / 1e3) + ' kB' : n + ' bytes';
  }
  function when(at) {
    var s = Math.max(0, Date.now() / 1000 - (at || 0));
    return s < 3600 ? 'kept a moment ago' : s < 86400 ? 'kept ' + Math.round(s / 3600) + ' hours ago'
         : 'kept ' + Math.round(s / 86400) + ' days ago';
  }
  function jobWrite(key, v) {
    return caches.open(JOBS).then(function (c) {
      return c.put(key, new Response(JSON.stringify(v), {headers: {'Content-Type': 'application/json'}}));
    });
  }
  // every note of one thing marked `removed`, and its downloads stopped;
  // resolves with their tokens.  Nothing at all where nothing was ever kept
  // in the background -- the iPad -- and no cache is made for asking.
  function stopAll(id) {
    if (!window.caches) return Promise.resolve([]);
    return caches.has(JOBS).then(function (y) {
      if (!y) return [];
      return caches.open(JOBS).then(function (c) {
        return c.keys().then(function (ks) {
          var heads = ks.map(function (k) { return new URL(k.url).pathname; })
            .filter(function (p) { return p.indexOf(JOB) === 0 && p.slice(JOB.length).indexOf('/') < 0; });
          return Promise.all(heads.map(function (p) {
            return c.match(p).then(function (r) { return r ? r.json() : null; }).then(function (h) {
              if (!h || h.id !== id) return null;
              h.removed = true;
              return jobWrite(p, h).then(function () { return h.token; });
            });
          }));
        });
      }).then(function (ts) {
        ts = ts.filter(Boolean);
        var sw = navigator.serviceWorker;
        if (!ts.length || !sw || !sw.getRegistration) return ts;
        return sw.getRegistration().then(function (r) {
          if (!r || !r.backgroundFetch) return ts;
          return r.backgroundFetch.getIds().then(function (ids) {
            return Promise.all(ids.filter(function (n) {
              return n.indexOf(BG) === 0 && ts.indexOf(n.slice(BG.length).split(':')[0]) >= 0;
            }).map(function (n) {
              return r.backgroundFetch.get(n).then(function (x) { return x ? x.abort() : false; })
                .catch(function () { return false; });
            }));
          });
        }).then(function () { return ts; }, function () { return ts; });
      });
    }).catch(function () { return []; });
  }
  // a keep's notes, gone once its thing has been dropped
  function forget(token) {
    caches.has(JOBS).then(function (y) {
      if (!y) return null;
      return caches.open(JOBS).then(function (c) {
        return c.keys().then(function (ks) {
          return Promise.all(ks.filter(function (k) {
            var p = new URL(k.url).pathname;
            return p === JOB + token || p.indexOf(JOB + token + '/') === 0;
          }).map(function (k) { return c.delete(k); }));
        });
      });
    }).catch(function () {});
  }
  /* WHAT IS STILL COMING IN THE BACKGROUND (the owner, 2026-09-23): a book
     whose download Android is still bringing is listed here too, as "coming —
     43%", with Stop in place of Remove.  Read from the browser's own list of
     downloads and the note each press left (lib/keep.js), never made up: a
     browser with no background downloads at all -- the iPad -- finds nothing
     and draws exactly the list it always drew. */
  var jobs = {};
  function coming() {
    jobs = {};
    var sw = navigator.serviceWorker;
    if (!window.caches || !sw || !sw.getRegistration) return Promise.resolve();
    return caches.has(JOBS).then(function (y) {
      if (!y) return null;
      return sw.getRegistration().then(function (r) {
        if (!r || !r.backgroundFetch) return null;
        return Promise.all([caches.open(JOBS), r.backgroundFetch.getIds()]).then(function (a) {
          var c = a[0], by = {};
          (a[1] || []).forEach(function (name) {
            if (name.indexOf(BG) !== 0) return;
            var t = name.slice(BG.length).split(':')[0];
            (by[t] = by[t] || []).push(name);
          });
          return Promise.all(Object.keys(by).map(function (t) {
            return c.match(JOB + t).then(function (res) { return res ? res.json() : null; })
              .then(function (head) {
                if (head && !head.removed) jobs[head.id] = {head: head, names: by[t], bf: r.backgroundFetch};
              });
          }));
        });
      });
    }).catch(function () {});
  }
  // how far a keep still coming has got, in the note's own weights -- a
  // download of it that is over counting what its note says it brought, read
  // BEFORE anything is shown, since the figure never goes back
  function follow(job, tag) {
    var want = job.head.want || {}, total = 0, seen = {};
    var w = function (list) {
      return (list || []).reduce(function (n, u) { return n + ((want[u] && want[u].bytes) || 0); }, 0);
    };
    Object.keys(job.head.parts || {}).forEach(function (p) { total += w(job.head.parts[p]); });
    var live = {};
    job.names.forEach(function (n) { live[n.split(':')[2]] = true; });
    var over = Object.keys(job.head.parts || {}).filter(function (p) { return !live[p]; });
    var top = 0;
    function show() {
      var got = 0;
      for (var k in seen) if (Object.prototype.hasOwnProperty.call(seen, k)) got += seen[k];
      top = Math.max(top, Math.min(99, total ? Math.floor(got * 100 / total) : 0));
      tag.textContent = 'coming — ' + top + '%';
    }
    tag.textContent = 'coming';
    caches.open(JOBS).then(function (c) {
      return Promise.all(over.map(function (p) {
        return c.match(JOB + job.head.token + '/' + p).then(function (r) { return r ? r.json() : null; })
          .then(function (o) {
            if (o && !o.settling) {
              seen[p] = w(o.put || []);
              total = Math.max(0, total - w(o.failed || []));
            } else seen[p] = w(job.head.parts[p]);   // over, and being put away
          });
      }));
    }).catch(function () {}).then(function () {
      show();
      job.names.forEach(function (n) {
        job.bf.get(n).then(function (r) {
          if (!r) return;
          var part = n.split(':')[2];
          var moved = function () { seen[part] = r.downloaded || 0; show(); };
          r.addEventListener('progress', moved);
          moved();
        });
      });
    });
  }
  function draw(lines) {
    var reg = {};
    try { reg = JSON.parse(localStorage.getItem('parseh_kept') || '{}') || {}; } catch (e) {}
    list.textContent = '';
    none.hidden = true;
    var ids = Object.keys(reg);
    Object.keys(jobs).forEach(function (id) { if (!reg[id]) ids.push(id); });
    if (!ids.length) none.hidden = false;
    ids.sort(function (a, b) {
      var x = reg[a] || (jobs[a] || {}).head || {}, y = reg[b] || (jobs[b] || {}).head || {};
      return (y.at || y.started || 0) - (x.at || x.started || 0);
    });
    ids.forEach(function (id) { card(id, reg[id], jobs[id], reg); });
    (lines || []).forEach(function (l) {
      var p = document.createElement('p');
      p.className = 'm-keptnews' + (l.bad ? ' kp-bad' : '');
      p.setAttribute('role', 'status');
      p.textContent = l.line;
      list.parentNode.appendChild(p);
    });
    // the room is said where something is listed, as it always was
    if (ids.length) room();
  }
  function card(id, r, job, reg) {
    var card = document.createElement('div');
    card.className = 'm-book m-kept';
    var a = document.createElement('a');
    a.className = 'm-keptopen';
    a.href = (r && r.page) || (job && job.head.page) || id;
    a.innerHTML = '<div class="m-btitle"></div><div class="m-tags"></div>';
    a.querySelector('.m-btitle').textContent = (r && r.title) || (job && job.head.title) || id;
    var tags = a.querySelector('.m-tags');
    // WHETHER ITS NOTES CAME WITH IT (TO-DO §0, the notes kept with their
    // book).  Both answers are worth a tag, because both are acted on in the
    // same one press: the card opens the book, and Change what is kept is
    // the tick.  But only where the answer is KNOWN -- lib/keep.js writes
    // `notes` into the registry only for a thing that can have notes at all,
    // so a deck, a document, and anything kept before any of this existed
    // carry nothing here and get no tag.  A tag guessed for them would be a
    // tag that lies, which is worse than a tag that is missing.
    var mine = [];
    if (r) {
      mine = [[r.kind || 'kept', 'tag'], [big(r.bytes), 'tag on'], [when(r.at), 'tag']];
      if (r.notes === true) mine.push(['with its notes', 'tag']);
      else if (r.notes === false) mine.push(['without its notes', 'tag']);
    } else mine = [['book', 'tag']];
    mine.forEach(function (t) {
      var s = document.createElement('span');
      s.className = t[1];
      s.textContent = t[0];
      tags.appendChild(s);
    });
    if (job) {
      // on its way, not missing: lib/keep.js leaves such a card as it is
      card.setAttribute('data-kp-coming', '');
      var c = document.createElement('span');
      c.className = 'tag on m-coming';
      tags.appendChild(c);
      follow(job, c);
    }
    card.appendChild(a);
    if (job) {
      /* STOP, in place of Remove, while it is coming (the owner): it does
         what Cancel on the notification does -- the whole keep stops, and
         what had come stays -- and the line then says it was stopped on this
         phone.  The worker says when it has been put away, and the list is
         drawn again from what it wrote down. */
      var stop = document.createElement('button');
      stop.type = 'button';
      stop.className = 'm-keptoff m-keptstop';
      stop.textContent = 'Stop';
      stop.addEventListener('click', function () {
        stop.disabled = true;
        // the note as it is NOW, not as it was drawn: a keep removed or ended
        // meanwhile is not brought back by writing an old copy of it
        caches.open(JOBS).then(function (c) { return c.match(JOB + job.head.token); })
          .then(function (r) { return r ? r.json() : null; })
          .then(function (h) {
            if (!h || h.removed) { again(); return null; }
            h.stopped = 'here';
            return jobWrite(JOB + h.token, h).then(function () {
              return Promise.all(job.names.map(function (n) {
                return job.bf.get(n).then(function (x) { return x ? x.abort() : false; })
                  .catch(function () { return false; });
              }));
            });
          }).catch(function () { stop.disabled = false; });
      });
      card.appendChild(stop);
      list.appendChild(card);
      return;
    }
    var off = document.createElement('button');
    off.type = 'button';
    off.className = 'm-keptoff';
    off.textContent = 'Remove from this phone';
    off.addEventListener('click', function () {
      // A DECK THAT IS OUT MAY NOT BE REMOVED (the owner's 8 and 9,
      // 2026-09-23): what has been answered on this phone is nowhere else
      // until it is given back, and the copy is what the study page reads.
      // decks.js keeps the check-out under parseh_deck_out:<folder>/<slug>.
      var out = /^\/exercises\/deck\/([a-z]+)\/([a-z0-9][a-z0-9-]*)\/$/.exec(id), held = null;
      if (out) {
        try { held = JSON.parse(localStorage.getItem('parseh_deck_out:' + out[1] + '/' + out[2]) || 'null'); }
        catch (e) {}
      }
      if (held) {
        var no = card.querySelector('.m-keptwhy') || document.createElement('p');
        no.className = 'm-keptwhy';
        no.textContent = 'This deck is out on this phone: what has been answered here is not on ' +
                         'the computer yet. Give it back on its own page first.';
        card.appendChild(no);
        return;
      }
      off.disabled = true;
      var w = navigator.serviceWorker && navigator.serviceWorker.controller;
      var tokens = [];
      // ONCE, and from the registry as it is when it runs: the list may have
      // been drawn again meanwhile, from what a keep ending wrote down
      var ended = false;
      var done = function () {
        if (ended) return;
        ended = true;
        var now = {};
        try { now = JSON.parse(localStorage.getItem('parseh_kept') || '{}') || {}; } catch (e) {}
        delete now[id];
        try { localStorage.setItem('parseh_kept', JSON.stringify(now)); } catch (e) {}
        tokens.forEach(forget);
        if (card.isConnected) {
          card.remove();
          if (!Object.keys(now).length && !list.querySelector('.m-kept')) none.hidden = false;
          room();
        } else again();
      };
      /* WHAT IS STILL COMING OF IT IS STOPPED FIRST, and nothing of it is put
         away (the owner): the notes say `removed` before the download is
         stopped -- looked at now, when Remove is pressed, not when the list
         was drawn, since a Save may have started one from another page. */
      stopAll(id).then(function (t) {
        tokens = t;
        if (!w) { done(); return; }
        var hear = function (e) {
          if (!e.data || !e.data.dropped) return;
          navigator.serviceWorker.removeEventListener('message', hear);
          done();
        };
        navigator.serviceWorker.addEventListener('message', hear);
        w.postMessage({drop: id});
        setTimeout(done, 4000);
      });
    });
    card.appendChild(off);
    list.appendChild(card);
  }
  function room() {
    var say = document.getElementById('m-room');
    if (!navigator.storage || !navigator.storage.estimate) return;
    navigator.storage.estimate().then(function (e) {
      var used = e.usage || 0, all = e.quota || 0;
      say.textContent = all ? 'This phone is holding ' + big(used) + ', and has about ' +
                              big(Math.max(0, all - used)) + ' left for Parseh.'
                            : 'This phone is holding ' + big(used) + '.';
    });
  }
  // what came while no page was open is written down first, then drawn
  function again() { parsehMerge(function (lines) { coming().then(function () { draw(lines); follow_(); }); }); }
  // a keep drawn as coming that lib/keep.js on this page is not following yet
  // -- one started after the page loaded -- is followed, so that its end,
  // however it comes, draws the page again
  function follow_() {
    if (Object.keys(jobs).length && window.ParsehKeep && window.ParsehKeep.follow) window.ParsehKeep.follow();
  }
  again();
  // and a keep that ends while this page is open is drawn again from what
  // the worker wrote down
  if (navigator.serviceWorker)
    navigator.serviceWorker.addEventListener('message', function (e) {
      var d = e.data || {};
      if (d.kept && d.token) again();
    });
  // and a keep cut short, which lib/keep.js writes down on this page too
  document.addEventListener('parseh:kept-written', function (e) {
    var more = (e.detail && e.detail.lines) || [];
    parsehMerge(function (lines) { coming().then(function () { draw(more.concat(lines)); }); });
  });
})();
</script>"""


def kept_page():
    """/m/kept/: everything kept on this phone, what each takes and the room
    left, each openable and each removable (TO-DO §19.2)."""
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kept on this phone &mdash; %(app)s</title>
%(head)s
<link rel="stylesheet" href="/lib/parseh.css">
<link rel="stylesheet" href="/lib/langs.css">
<link rel="stylesheet" href="/lib/mobile.css">
<script src="/lib/parseh.js"></script>
</head><body class="m-page" data-mobile-page data-browser-page="/">
%(bar)s
<main class="m-main">
  <h1 class="m-h1">Kept on this phone</h1>
  <p class="m-tagline">These work with the computer asleep, off, or a train away. Everything
  else needs it.</p>
  <p id="m-room" class="m-small">&nbsp;</p>
  <div class="m-shelf" id="m-keptlist"></div>
  <div class="m-empty" id="m-keptnone" hidden>
    <p>Nothing is kept on this phone yet.</p>
    <p>Open a book or a video and press <b>Keep on this phone</b> under <b>&ctdot;</b>.</p>
  </div>
</main>
%(js)s
</body></html>
""" % {"app": APP_NAME, "head": app_head(), "bar": bar("Kept here"), "js": KEPT_JS}


def mode_switch():
    """The switch between the browser and the mobile interface, for a page's
    top bar: two buttons parseh.js wires (Parseh.mode), the one in force
    filled in.  Which one that is, the page learns from <html data-mode>
    before it paints; aria-pressed here is only where it starts."""
    return ('<span class="parseh-mode" role="group" aria-label="interface">'
            '<button type="button" data-parseh-mode="browser" aria-pressed="true" '
            'title="the browser interface: every page, with everything that edits">'
            'Browser</button>'
            '<button type="button" data-parseh-mode="mobile" aria-pressed="false" '
            'title="the mobile interface: pages made for a phone, to read and to study, '
            'with nothing on them that edits">Mobile</button></span>')


def bar(where):
    """The mobile layout's bar, as the hub's: the way home, where this is,
    the switch and the theme -- nothing that stops or administers anything.
    A .parseh-bar, so on a phone it slides away on the way down and comes
    back on the way up like every other bar (parseh.js, bars())."""
    return ('<div class="parseh-bar m-bar">\n'
            '  <a class="home" href="/"><span class="glyph" lang="fa">&#x67E;</span>'
            '<span class="word">%s</span></a>\n'
            '  <span class="m-where">%s</span>\n'
            '  <span class="sp"></span>\n'
            '  %s\n'
            '  <button type="button" data-parseh-theme title="theme">&#9680;</button>\n'
            '</div>' % (APP_NAME, esc(where), mode_switch()))


def reader_href(b):
    """A book's reader, by the hub's own absolute address (the page is only
    ever served, never opened off the disk)."""
    return "/books/%s/reader/" % b.rel_from_books()


def book_card(b):
    """One book on the mobile shelf: a link to its reader, or -- a book never
    built -- a card that says so and opens nothing."""
    st = make_index.stats(b)
    L = b.lang
    attrs = L.html_attrs()
    tags = []
    if st.get("built"):
        n = len(st.get("chapters", []))
        tags.append('<span class="tag">%d chapter%s</span>' % (n, "" if n == 1 else "s"))
        if b.has_audio:
            timed, subs = st.get("timed", 0), st.get("subs", 0)
            tags.append('<span class="tag on">narrated &middot; %d/%d timed</span>'
                        % (timed, subs))
    else:
        tags.append('<span class="tag no">not built yet</span>')
    title = ('<div class="m-btitle"%s>%s</div>' % (attrs, esc(b.title))) if b.title else ""
    author = ('<div class="m-bby"%s>%s</div>' % (attrs, esc(b.author))) if b.author else ""
    latin = esc(b.title_latin or b.slug)
    if b.author_latin:
        latin += " <i>&mdash; %s</i>" % esc(b.author_latin)
    blurb = b.meta.get("blurb", "")
    inner = """  %s%s
  <div class="m-blat">%s</div>%s
  <div class="m-tags">%s</div>""" % (
        title, author, latin,
        ('\n  <div class="m-bblurb">%s</div>' % esc(blurb)) if blurb else "",
        "".join(tags))
    if not st.get("built"):
        # nothing to open: a phone does not build a book (docs/mobile.md)
        return ('<div class="m-book m-off" data-lang="%s">\n%s\n'
                '  <div class="m-bnote">Its reader has not been built yet: that is done in '
                'the browser interface, from the book&rsquo;s card in the library.</div>\n'
                '</div>' % (esc(L.code), inner))
    # data-subs: how many subparagraphs the reader has, which is what the
    # reading place it keeps (a subparagraph's index) is counted against.
    # data-place: how far the TOOLBOX says this book has been read (§4.9,
    # lib/prefs.py) -- so a phone that has never opened it still shows the
    # place made at the computer.  This browser's own, where it has one and
    # it is further on, wins over it (READ_ON_JS).
    href = reader_href(b)
    kept = ""
    rec = _place_for(href)
    if rec:
        kept = ' data-place="%d" data-place-by="%s"' % (int(rec.get("pct") or 0),
                                                        esc(str(rec.get("by") or "")))
    return ('<a class="m-book" href="%s" data-lang="%s" data-subs="%d"%s>\n%s\n</a>'
            % (esc(href), esc(L.code), int(st.get("subs", 0) or 0), kept, inner))


def _place_for(href):
    """What the toolbox knows of where this book was last read, by whichever
    device read it (lib/prefs.py).  The library links a reader by reader/ and
    by reader/index.html: both addresses are asked, as the page's own script
    asks localStorage for both."""
    try:
        import prefs
        kept = prefs.places()
    except Exception:
        return None
    for path in (href, href + "index.html"):
        rec = kept.get(path)
        if isinstance(rec, dict) and rec.get("pct"):
            return rec
    return None


def lang_head(L, n):
    """The heading over one language's books: its English name, its own
    name in its own face, how many."""
    return ('<h2 class="m-lhead" data-lang="%s"><span class="name">%s</span>'
            '<bdi class="native"%s>%s</bdi><span class="n">%d</span></h2>'
            % (esc(L.code), esc(L.name), L.html_attrs(), esc(L.native), n))


# THE READING PLACE.  Two of them may be known.  The toolbox keeps one per
# book, whichever device read it (lib/prefs.py, §4.9), and the card above
# arrives with it as data-place; this browser keeps its own, under bk_pos: and
# the reader's address, as {i: the subparagraph's index} (lib/tex2html.py,
# save()).  The library links a reader by reader/index.html and this page by
# reader/, so both addresses are asked.  The further of the two is what the
# card says, and the reader is linked at the address this browser's place was
# kept under, so it opens there.  Nothing is written.
#
# It is drawn again whenever the shelf is: the page opens from the phone's
# copy of itself and lib/keep.js swaps the block when the computer's answer
# lands (parseh:shell-filled), and the cards that arrive then are the
# computer's, which know nothing of what this browser has read.
READ_ON_JS = r"""<script>
(function () {
 function mark() {
  var cards = document.querySelectorAll('a.m-book[data-subs]:not(.m-read)');
  for (var i = 0; i < cards.length; i++) {
    var a = cards[i], base = a.getAttribute('href'), subs = +a.getAttribute('data-subs') || 0;
    // a card lib/keep.js has made untappable -- the book is not on this phone
    // and the computer is away -- has no address to read a place against
    if (!base) continue;
    var at = null, where = base;
    [base, base + 'index.html'].forEach(function (p) {
      if (at !== null) return;
      try {
        var v = JSON.parse(localStorage.getItem('bk_pos:' + p) || 'null');
        if (v && typeof v.i === 'number' && v.i > 0) { at = v.i; where = p; }
      } catch (e) {}
    });
    var mine = (at !== null && subs) ? Math.max(1, Math.min(100, Math.round((at + 1) * 100 / subs))) : 0;
    var theirs = +a.getAttribute('data-place') || 0;
    var pct = Math.max(mine, theirs);
    if (!pct) continue;
    var tag = document.createElement('span');
    tag.className = 'tag on m-readon';
    tag.textContent = 'read on · ' + pct + '%';
    if (theirs > mine && a.getAttribute('data-place-by'))
      tag.title = 'where it was last read, on ' + a.getAttribute('data-place-by');
    var tags = a.querySelector('.m-tags');
    if (tags) tags.insertBefore(tag, tags.firstChild);
    a.style.setProperty('--m-read', pct + '%');
    a.classList.add('m-read');
    if (mine) a.setAttribute('href', where);
  }
 }
 mark();
 document.addEventListener('parseh:shell-filled', mark);
})();
</script>"""


# What this phone is doing about the app, said live on /m/install/: in the
# app already; a browser that installs nothing; a page not trusted (the
# service worker refused -- the certificate); ready, with the browser's own
# Install behind the button (parseh.js keeps it: Parseh.app).
INSTALL_JS = r"""<script>
(function () {
  var say = document.getElementById('m-appnow'), P = window.Parseh;
  function put(cls, text) { say.className = 'm-appnow ' + cls; say.textContent = text; }
  function look() {
    if (P && P.app && P.app.standalone()) {
      put('ok', 'This is the app: Parseh is installed on this phone, and open on its whole screen.');
      return;
    }
    if (!('serviceWorker' in navigator) || !window.isSecureContext) {
      put('no', location.protocol === 'http:' && !/^(localhost|127\.)/.test(location.hostname)
        ? 'This page came over plain http: a phone installs an app only from https.'
        : 'This browser cannot install a site as an app. On Android use Chrome; on an iPhone, Safari.');
      return;
    }
    put('wait', 'Asking this browser whether it can install Parseh…');
    navigator.serviceWorker.register('/sw.js').then(function () {
      if (P && P.app && P.app.canPrompt())
        put('ok', 'Ready: this phone trusts Parseh, and its browser can install it. Step 2.');
      else
        put('ok', 'This phone trusts Parseh. Install it as step 2 says: the browser has not offered ' +
                  'its own Install button on this page, or it has been used already.');
    }, function () {
      put('no', 'This phone does not trust Parseh’s certificate yet: step 1 first, then open this page again.');
    });
  }
  if (P && P.app) P.app.onChange(look);
  look();
})();
</script>"""


def install_page(tls):
    """/m/install/: how to install the mobile interface on this phone as an
    app.  `tls` says what the server speaks: "authority" (serve.py's own
    certificate, whose authority this page hands over), "own" (one put in
    .tls/ by hand, which a phone may trust already), or "http"."""
    if tls == "authority":
        cert = """  <section class="m-step">
    <h2><span class="m-n">1</span> This phone trusts Parseh</h2>
    <p>Parseh makes its own certificate, so a phone trusts it only once it has been told
    to &mdash; that is the warning a browser shows the first time. A browser tab goes on after
    the warning; an app does not. Tell this phone once, and it trusts every certificate
    Parseh makes from then on.</p>
    <a class="m-btn" href="/m/install/parseh-ca.crt">Download the certificate</a>
    <p class="m-how"><b>Android:</b> open <i>Settings</i> and search for <i>CA certificate</i>
    (it is under <i>Security</i>, <i>Encryption &amp; credentials</i>, <i>Install a
    certificate</i>); choose <i>CA certificate</i>, <i>Install anyway</i>, and pick
    <i>Parseh-CA.crt</i> from the downloads. Then close this tab and open Parseh again.</p>
    <p class="m-how"><b>iPhone, iPad:</b> allow the download; then in <i>Settings</i>, open
    <i>Profile Downloaded</i> and <i>Install</i> it; then <i>General</i>, <i>About</i>,
    <i>Certificate Trust Settings</i>, and turn on full trust for <i>Parseh local
    authority</i>.</p>
    <p class="m-small">It can vouch for this computer and nothing else: only for its own
    name, its local and Tailscale addresses. It is taken off the phone where it was put on,
    in the same settings.</p>
  </section>"""
    elif tls == "own":
        cert = """  <section class="m-step">
    <h2><span class="m-n">1</span> This phone trusts Parseh</h2>
    <p>This server speaks with a certificate that was put in place by hand, not one Parseh
    made. If it comes from an authority the phone already trusts &mdash; Tailscale&rsquo;s own
    certificates do, as do Let&rsquo;s Encrypt&rsquo;s &mdash; there is nothing to do here.
    The line at the top of this page says whether the phone trusts it.</p>
  </section>"""
    else:
        cert = """  <section class="m-step">
    <h2><span class="m-n">1</span> This phone trusts Parseh</h2>
    <p>Parseh is being served over plain http this time, and a phone installs an app only
    from https &mdash; the computer itself, at <i>localhost</i>, is the one exception.
    Started as it usually is, Parseh speaks https.</p>
  </section>"""
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(app)s as an app</title>
%(head)s
<link rel="stylesheet" href="/lib/parseh.css">
<link rel="stylesheet" href="/lib/mobile.css">
<script src="/lib/parseh.js"></script>
</head><body class="m-page" data-mobile-page data-browser-page="/">
%(bar)s
<main class="m-main m-install">
  <p class="m-elsewhere">This page belongs to the mobile interface, and the browser
  interface is on: switching to it goes to <a href="/">the hub</a>.</p>
  <h1 class="m-h1">%(app)s as an app</h1>
  <p class="m-tagline">Installed, the mobile interface opens from an icon on the home
  screen, on the whole screen: no address bar over the page, no browser around it.</p>
  <p id="m-appnow" class="m-appnow wait" role="status" aria-live="polite">&nbsp;</p>
%(cert)s
  <section class="m-step">
    <h2><span class="m-n">2</span> Install it</h2>
    <button type="button" class="m-btn" data-parseh-install hidden>Install %(app)s</button>
    <p class="m-how"><b>Android, Chrome:</b> <i>Install %(app)s</i>, here, once the browser
    offers it (the button appears just above); or the browser&rsquo;s <i>&#8942;</i> menu,
    <i>Install app</i> (<i>Add to Home screen</i> in some versions).</p>
    <p class="m-how"><b>iPhone, iPad, Safari:</b> the <i>Share</i> button, then <i>Add to
    Home Screen</i>.</p>
    <p class="m-small">The app is this server: it opens wherever the computer running
    %(app)s can be reached &mdash; on its network, or anywhere over Tailscale &mdash; and
    says so when it cannot.</p>
    <p class="m-small">Installing is the quick part: the icon is on the home screen the
    moment it is pressed, and %(app)s then fetches the pages it needs to open with the
    computer away &mdash; the hub, the shelves, their sheets and scripts. The line below
    counts them as they come, so it is worth staying on this page until it says it is
    ready.</p>
    <p data-parseh-warm="stay" role="status" hidden></p>
  </section>
</main>
%(js)s
</body></html>
""" % {"app": APP_NAME, "head": app_head(), "bar": bar("As an app"), "cert": cert,
       "js": INSTALL_JS}


# ---------------------------------------------------------------- videos
# THE VIDEOS, as a phone reads them (TO-DO §4.2).  The browser index is one
# card per channel and the videos a tap inside it; this shelf used to be a
# flat list instead -- every video of every channel, under a heading per
# channel -- and on a phone that is a page you scroll past rather than one
# you choose from.  So it is the browser's shape now (the owner, 2026-09-23):
# ONE CARD PER CHANNEL, saying its name, how many videos it holds and how
# many of them are glossed to the end, and opening the channel page that has
# always been there at /m/videos/<slug>/.  A channel with videos in two
# languages is two cards, one under each language's heading, exactly as the
# browser's index does it -- which is also what makes the chip row honest: a
# card counts only the videos of the language it is filed under.
#
# Nothing here writes: no delete, no add, no bundle either way.  A video with
# no annotations at all has nothing to read and says so on its own card,
# inside the channel; every other card opens the player, where
# lib/mobileplayer.js takes over.
#
# AND WITH THE COMPUTER AWAY (the owner's 1 and 2, 2026-09-23).  This shelf
# is a shell page, kept by the worker, so it opens in airplane mode showing
# the channels the computer had when it was last reached -- but a channel
# PAGE is only on the phone if the app warmed it (lib/offline.py, shell()),
# and one added since the last warming is on nobody's phone at all.  A card
# whose page is not here must therefore look like one that cannot be opened,
# the way a book whose reader was never built already does: CHANNELS_JS asks
# the phone's own caches, address by address, and draws the rest as m-off.
def _video_card(m):
    import ytpages
    vid = m["_dir"].rsplit("/", 1)[-1]
    L = languages.get_or_default(m.get("_lang"))
    attrs = L.html_attrs()
    tags = []
    if m.get("duration"):
        tags.append('<span class="tag">%s</span>' % esc(m["duration"]))
    if m.get("_kind") == "audio":
        tags.append('<span class="tag">&#9834; a sound</span>')
    if m.get("level"):
        tags.append('<span class="tag">%s</span>' % esc(m["level"]))
    if m["_segments"] and not m.get("_blank"):
        tags.append('<span class="tag on">%d captions glossed</span>' % m["_segments"])
    elif m.get("_blank"):
        tags.append('<span class="tag on">%d of %d chunks glossed</span>'
                    % (m["_glossable"] - m["_blank"], m["_glossable"]))
    native = esc(ytpages.native_title(m) or m.get("title") or vid)
    title = ('<div class="m-btitle"%s>%s</div>' % (attrs, native)) if native else ""
    latin = esc(m.get("title") or vid)
    inner = """  %s
  <div class="m-bby">%s</div>
  <div class="m-blat">%s</div>
  <div class="m-tags">%s</div>""" % (title, esc(m.get("channel") or ""), latin, "".join(tags))
    if not m["_segments"]:
        return ('<div class="m-book m-off" data-lang="%s">\n%s\n'
                '  <div class="m-bnote">Nothing has been glossed in this video yet: '
                'that is done in the browser interface.</div>\n</div>'
                % (esc(L.code), inner))
    return ('<a class="m-book" href="/youtube/v/%s/" data-lang="%s">\n%s\n</a>'
            % (esc(vid), esc(L.code), inner))


def _channel_card(c):
    """One channel on the mobile shelf: the whole card is the way into it.

    The tags are the browser index's (youtube/lib/ytpages.py, channel_card),
    in the mobile shelf's own clothes -- how many videos, how many are
    glossed to the end, the levels they are marked with.  "Fully glossed" has
    to mean no chunk left blank as well as every caption glossed, or a video
    whose chunks are still being filled in would be counted here as finished
    work.

    One tag is this shelf's own: a channel where NOTHING has been glossed
    opens on a page where every card says there is nothing to read, and it is
    better said on the outside than found on the inside.

    data-m-page is the address the card opens, said twice so that CHANNELS_JS
    still knows it after taking the href away.

    THE NAME IS WHATEVER YOUTUBE CALLS THE CHANNEL, and that is Persian for
    one channel and Latin for the next -- "Daughter of Iran [Comprehensible
    Input]" is his, under the Persian heading.  So it is given dir="auto" and
    no lang: the browser reads the direction off the first real letter, and
    the bracket of that name stays at the end of it.  Forcing the language's
    direction on it instead threw the bracket to the wrong end of the line.

    And it is set in the language's READING face, not its display one, which
    is the same choice the browser index makes (lib/parseh.css, a.book.chan
    .chname uses --tl-font).  A book's title on the shelf is target text and
    earns the display face; a channel's name is the app's own chrome, and
    Persian's display face is Nastaliq, which carries a line and a half of
    leading with it and set two lines of a Latin channel name a thumb apart.
    The card says so in its own tokens rather than asking for a rule of its
    own: --tl-alt is what .m-btitle draws with, so on this card --tl-alt IS
    --tl-font, and --tl-alt-lh (the leading Nastaliq needs) is nobody's here.
    """
    L = languages.get_or_default(c["lang"])
    n = len(c["videos"])
    glossed = sum(1 for m in c["videos"]
                  if m["_segments"] and m["_glossed"] >= m["_segments"] and not m["_blank"])
    readable = sum(1 for m in c["videos"] if m["_segments"])
    levels = sorted({m.get("level") for m in c["videos"] if m.get("level")})
    tags = ['<span class="tag on">%d video%s</span>' % (n, "" if n == 1 else "s")]
    if glossed:
        tags.append('<span class="tag">%d fully glossed</span>' % glossed)
    for lvl in levels:
        tags.append('<span class="tag">%s</span>' % esc(lvl))
    if not readable:
        tags.append('<span class="tag no">nothing glossed yet</span>')
    href = "/m/videos/%s/" % c["slug"]
    return ('<a class="m-book m-chancard" href="%s" data-m-page="%s" data-lang="%s"'
            ' style="--tl-alt:var(--tl-font);--tl-alt-lh:1">\n'
            '  <div class="m-btitle" dir="auto">%s</div>\n'
            '  <div class="m-tags">%s</div>\n'
            '</a>' % (esc(href), esc(href), esc(L.code), esc(c["name"]), "".join(tags)))


# WHICH CHANNELS THIS PHONE CAN ACTUALLY OPEN, while the computer is away.
# The shelf itself is kept with the app and opens whatever happens; a channel
# page is only on the phone if the app warmed it, and a channel added since
# the last warming is on nobody's.  Tapping such a card would go nowhere, so
# it is drawn and cannot be tapped, with a line saying why -- the same face a
# book whose reader was never built has always worn (m-book m-off).
#
# The phone's caches are asked directly: caches.match() searches every cache
# of this origin, which is precisely the question "would this page open with
# nothing behind it".  Nothing here decides whether the computer is away --
# that is lib/keep.js's probe, which writes data-parseh-away on <html> -- and
# nothing here is drawn until the caches have answered: until then a card
# stays tappable, because the worse mistake is to refuse a page this phone
# really holds.  A browser with no cache storage at all (a page over plain
# http, the browser mode) has no offline story to be honest about and is left
# alone.
CHANNELS_JS = r"""<script>
(function () {
  // what the note may promise is only what the worker really does: nothing
  // puts a page in a cache by being opened (lib/sw.js, answer(): a navigation
  // nobody kept is fetched and not stashed), so this says where what IS kept
  // can be found instead of promising that a tap would fetch it
  var NOTE = "Not on this phone: this channel's list is the computer's, and opens again " +
             'when it can be reached. What was kept from it is in the list the offline ' +
             'chip above opens.';
  function cards() {
    return Array.prototype.slice.call(document.querySelectorAll('.m-chancard[data-m-page]'));
  }
  function away() { return document.documentElement.hasAttribute('data-parseh-away'); }
  function off(card) {
    if (card.classList.contains('m-chanoff')) return;
    card.classList.add('m-chanoff', 'm-off');
    var href = card.getAttribute('href');
    if (href) { card.setAttribute('data-m-href', href); card.removeAttribute('href'); }
    card.setAttribute('aria-disabled', 'true');
    var note = document.createElement('div');
    note.className = 'm-bnote m-channote';
    note.textContent = NOTE;
    card.appendChild(note);
  }
  function on(card) {
    if (!card.classList.contains('m-chanoff')) return;
    card.classList.remove('m-chanoff', 'm-off');
    var href = card.getAttribute('data-m-href');
    if (href) { card.setAttribute('href', href); card.removeAttribute('data-m-href'); }
    card.removeAttribute('aria-disabled');
    var note = card.querySelector('.m-channote');
    if (note) note.remove();
  }
  function paint() {
    var gone = away();
    cards().forEach(function (card) {
      if (gone && card.getAttribute('data-m-here') === '0') off(card); else on(card);
    });
  }
  function look() {
    var all = cards();
    if (!all.length) return;
    if (!window.caches) {
      all.forEach(function (card) { card.setAttribute('data-m-here', '1'); });
      paint();
      return;
    }
    all.forEach(function (card) {
      caches.match(card.getAttribute('data-m-page')).catch(function () { return true; })
        .then(function (hit) { card.setAttribute('data-m-here', hit ? '1' : '0'); paint(); });
    });
  }
  look();
  // the block is the computer's, and lib/keep.js swaps a fresh one in when the
  // worker finds this page has changed: the cards that arrive then are cards
  // nobody has asked the caches about yet
  document.addEventListener('parseh:shell-filled', look);
  new MutationObserver(paint).observe(document.documentElement,
    {attributes: true, attributeFilter: ['data-parseh-away']});
  // a channel page reaches this phone only while the computer is there, so the
  // walk is worth making again the moment the app has finished getting ready
  if (navigator.serviceWorker)
    navigator.serviceWorker.addEventListener('message', function (e) {
      if (e.data && e.data.warmed) look();
    });
})();
</script>"""


def _videos_frame(title, tagline, body, where, browser_page, chips="", elsewhere="", js=""):
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s &mdash; %(app)s</title>
%(head)s
<link rel="stylesheet" href="/lib/parseh.css">
<link rel="stylesheet" href="/lib/langs.css">
<link rel="stylesheet" href="/lib/mobile.css">
<script src="/lib/parseh.js"></script>
</head><body class="m-page" data-mobile-page data-browser-page="%(browser)s">
%(bar)s
<main class="m-main">
  <p class="m-elsewhere">%(elsewhere)s</p>
  <h1 class="m-h1">%(title)s</h1>
%(tagline)s%(chips)s
<div class="m-shelf" data-shell-block>
%(body)s</div>
</main>
%(js)s
</body></html>
""" % {"app": APP_NAME, "head": app_head(), "bar": bar(where), "title": esc(title),
       "tagline": ('  <p class="m-tagline">%s</p>\n' % tagline) if tagline else "", "chips": chips, "body": body, "browser": esc(browser_page),
       "js": js,
       "elsewhere": elsewhere or ('This page belongs to the mobile interface, and the browser '
                                  'interface is on: switching to it goes to '
                                  '<a href="/youtube/">the videos</a>.')}


def videos_page():
    """/m/videos/: the channels, grouped by language in the registry's order,
    one card each -- the videos are a tap inside, on the channel's own page."""
    import ytpages
    chans = ytpages.list_channels()
    counts, out = {}, []
    for L in languages.LANGS.values():
        mine = [c for c in chans if c["lang"] == L.code]
        if not mine:
            continue
        # a language's heading counts its VIDEOS, as the browser index's does
        # and as the chips do: the cards under it are channels, and "3
        # channels" beside a chip reading 16 would be two numbers for the
        # same thing
        counts[L.code] = sum(len(c["videos"]) for c in mine)
        out.append(lang_head(L, counts[L.code]))
        out.extend(_channel_card(c) for c in mine)
    chips = languages.chips_html(counts, cls="parseh-langs m-langs",
                                 selector=".m-book[data-lang], .m-lhead")
    if not chans:
        out.append('<div class="m-empty"><p>No video is here yet.</p>'
                   '<p>Videos are added in the browser interface &mdash; the switch is at '
                   'the top of this page.</p></div>')
    return _videos_frame("Videos", "", "\n".join(out), "Videos", "/youtube/", chips, js=CHANNELS_JS)


def channel_page(slug):
    """/m/videos/<channel>/: one channel's videos, of every language it has."""
    import ytpages
    chans = [c for c in ytpages.list_channels() if c["slug"] == slug]
    if not chans:
        return None
    name = chans[0]["name"]
    out = []
    for c in chans:
        L = languages.get_or_default(c["lang"])
        out.append(lang_head(L, len(c["videos"])))
        out.extend(_video_card(m) for m in c["videos"])
    # THE WAY BACK, said on the page.  The shelf is the channels now, so this
    # is where every video is reached from and the way out of it should not be
    # only the phone's own back gesture: the tagline carries the crumb the
    # browser's channel page has always carried.
    tagline = ('Every video of this channel. '
               '<a href="/m/videos/">&lsaquo; all channels</a>')
    return _videos_frame(name, tagline, "\n".join(out), name,
                         "/youtube/c/%s/" % slug,
                         elsewhere=('This page belongs to the mobile interface, and the browser '
                                    'interface is on: switching to it goes to '
                                    '<a href="/youtube/c/%s/">this channel</a>.' % esc(slug)))


def books_page():
    """/m/books/: every book on the shelf, grouped by language in the
    registry's order under the chip row that filters them, as the library
    groups them."""
    bs = booklib.all_books()
    groups, counts = [], {}
    for L in languages.LANGS.values():
        mine = [b for b in bs if b.language == L.code]
        if not mine:
            continue
        counts[L.code] = len(mine)
        groups.append(lang_head(L, len(mine)))
        groups.extend(book_card(b) for b in mine)
    chips = languages.chips_html(counts, cls="parseh-langs m-langs",
                                 selector=".m-book[data-lang], .m-lhead")
    empty = "" if bs else (
        '<div class="m-empty"><p>No book is on the shelf yet.</p>'
        '<p>Books are added and built in the browser interface &mdash; the switch '
        'is at the top of this page.</p></div>')
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Books &mdash; %(app)s</title>
%(head)s
<link rel="stylesheet" href="/lib/parseh.css">
<link rel="stylesheet" href="/lib/langs.css">
<link rel="stylesheet" href="/lib/mobile.css">
<script src="/lib/parseh.js"></script>
</head><body class="m-page" data-mobile-page data-browser-page="/books/">
%(bar)s
<main class="m-main">
  <p class="m-elsewhere">This is the book shelf of the mobile interface, and the
  browser interface is on: <a href="/books/">the library</a> is its page.</p>
  <h1 class="m-h1">Books</h1>
%(chips)s
<div class="m-shelf" data-shell-block>
%(groups)s</div>%(empty)s
</main>
%(readon)s
</body></html>
""" % {"app": APP_NAME, "head": app_head(), "bar": bar("Books"), "chips": chips,
       "groups": "\n".join(groups), "empty": empty, "readon": READ_ON_JS}


if __name__ == "__main__":
    sys.stdout.write(books_page())
