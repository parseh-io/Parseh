#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the book library page, books/index.html.

    python3 lib/make_index.py

Lists every directory under books/<language>/ that has a book.json (and,
from the layout before languages, one directly under books/).  There is no
list of titles in this file: adding a book means adding a directory.  The
cards are grouped by language, in the registry's order, each group under a
heading with the language's names; above them the chip row every index page
of the toolbox carries (languages.chips_html), which lib/parseh.js wires to
the shared `parseh_lang` preference so a click hides the other languages'
cards and headings.

The page is served by ../serve.py at /books/ and links each reader by a
relative path, so it also opens straight off the disk.

It also carries the way back IN for a bundle -- bundle_panel below, which
the video index (youtube/lib/ytpages.py) imports, so that both doors take a
bundle back the same way and answer with the same words.
"""
import html
import json
import os
import re
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, LIB)
from books import all_books, ROOT, BOOKS_DIR                  # noqa: E402
import languages                                              # noqa: E402
import making                                                 # noqa: E402  a book an agent is still making says so on its card

APP_NAME = "Parseh"


def esc(s):
    return html.escape(s or "", quote=True)


# --------------------------------------------------- taking a bundle back
# A book's reader and a video's player each offer a __download: the authored
# files, zipped, to work on somewhere else.  This is the door back in, and
# the two doors must answer alike -- what was installed, which of a book's
# three shapes it came in, where it went, what is still to build -- so it is
# written once here and ytpages imports it.
#
# It carries its own stylesheet and names no class it did not define: the
# library page loads nothing but parseh.css, while the video index also has
# youtube/lib/style.css, and a panel that looked different in one door would
# be a second thing to learn.  Everything is a --token, so both themes work.
PANEL_CSS = """
<style>
.take{border:1px dashed var(--rule);border-radius:12px;background:var(--card);
  padding:18px 20px;margin-top:26px}
.take h2{font-size:16px;font-weight:400;line-height:1.3;margin:0 0 6px;color:var(--accent)}
.take p.lede{color:var(--dim);font-size:13.5px;line-height:1.6;margin:0 0 12px}
.take .zone{border:1.5px dashed var(--rule);border-radius:10px;padding:22px 14px;
  text-align:center;cursor:pointer;transition:border-color .12s,background .12s}
.take .zone:hover,.take .zone.over,.take .zone:focus{border-color:var(--accent);
  background:color-mix(in srgb,var(--accent) 6%,transparent);outline:none}
/* off the disk there is no server to post to: the zone stops pretending to
   be a button rather than failing on the click */
.take .zone.dead,.take .zone.dead:hover{cursor:default;border-color:var(--rule);
  background:none}
.take .zone .big{font-size:15px;color:var(--ink)}
.take .zone .small{font-size:12.5px;color:var(--faint);margin-top:4px}
.take .msg{font-size:13.5px;line-height:1.6;color:var(--dim);border:1px solid var(--rule);
  border-left-width:3px;border-radius:7px;padding:10px 12px;margin-top:12px}
.take .msg.good{border-left-color:var(--ok)}
.take .msg.warn{border-left-color:var(--warn)}
.take .msg.bad{border-left-color:var(--danger);color:var(--danger)}
.take .msg.busy{border-left-color:var(--accent);opacity:.75}
.take .msg b{color:var(--ink)}
.take .msg.bad b{color:inherit}
.take code{font-family:ui-monospace,Menlo,monospace;font-size:12px;background:var(--bg);
  border:1px solid var(--rule);border-radius:4px;padding:1px 5px;overflow-wrap:break-word}
.take ul{margin:7px 0 0;padding-left:18px}
.take li{margin:3px 0}
.take .act{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-top:11px}
.take .btn{font:inherit;font-size:13px;padding:7px 13px;border:1px solid var(--rule);
  border-radius:7px;background:var(--bg);color:var(--ink);cursor:pointer;
  text-decoration:none;white-space:nowrap}
.take .btn:hover{border-color:var(--accentlt);color:var(--accent)}
.take .btn.go{background:var(--accent);border-color:var(--accent);color:var(--accent-fg)}
.take .btn.go:hover{color:var(--accent-fg);filter:brightness(1.12)}
.take .btn[disabled]{opacity:.6;cursor:wait}
.take .stat{font-size:12.5px;color:var(--dim);overflow-wrap:anywhere}
.take .stat.bad{color:var(--danger)}
</style>
"""

PANEL_HTML = """
<section class="take" id="take">
  <h2>&#8681; Bring a __KIND__ back</h2>
  <p class="lede">__LEDE__</p>
  <div class="zone" id="takezone" tabindex="0" role="button">
    <div class="big">Choose the zip &mdash; or drop it here</div>
    <div class="small">__WHAT__</div>
  </div>
  <input type="file" id="takefile" accept=".zip,application/zip,application/x-zip-compressed" hidden>
  <div class="msg" id="takemsg" hidden></div>
</section>
"""

# The one thing this script must never do is throw a refusal away: every
# answer the endpoint gives is a sentence written for the person who pressed
# the button, and the only work here is to put it on the page.
PANEL_JS = r"""
<script>
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var POST = __POST__, NAMES = __NAMES__;   // {code: name}, from the registry
  // A book's download comes in three shapes and the manifest says which, so
  // the answer can name it -- in the reader's own words, because the door
  // that wrote the zip and the door that takes it back must call the three
  // the same thing.  What is said of each is what the ZIP carries, which is
  // a fact of the manifest; what the toolbox then does with a narration
  // already on the shelf is bundle.py's to say, and it says it in the notes
  // below.  A video has no shapes and no such field, and gets no sentence.
  var SHAPES = {
    text: ['the text alone', 'it carries no narration at all &mdash; no recording, no ' +
           'timings, no alignment review, and its book.json says the book has none'],
    linked: ['everything but the recording', 'it carries the timings and the ' +
             'alignment review, but not the audio file itself'],
    full: ['all of it', 'the recording came with it']
  };
  var zone = $('takezone'), pick = $('takefile'), msg = $('takemsg');
  var chosen = null;                      // kept, so "replace" needs no second pick
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function say(cls, h) { msg.hidden = false; msg.className = 'msg ' + cls; msg.innerHTML = h; }
  function size(n) {
    n = Number(n) || 0;
    return n < 1024 ? n + ' bytes' : (n / 1024).toFixed(n < 102400 ? 1 : 0) + ' kB';
  }
  // the library page also opens straight off the disk, where there is no
  // server to post to: a control that cannot work says so instead
  if (location.protocol === 'file:') {
    zone.removeAttribute('tabindex');
    zone.className = 'zone dead';
    zone.innerHTML = '<div class="small">This page is open off the disk. Start the ' +
      'server and open it there to take a bundle back.</div>';
    return;
  }
  // on the activity list (lib/activity.js, through parseh.js) while the
  // zip goes up and is installed: a film-sized bundle takes minutes, and
  // every other page -- the hub above all -- says so too
  function working(label) {
    return window.Parseh && Parseh.working ? Parseh.working(label)
      : {url: function (u) { return u; }, end: function () {}};
  }
  function send(file, replace) {
    chosen = file;
    say('busy', 'Reading <b>' + esc(file.name) + '</b>&hellip;');
    var act = working('Uploading ' + file.name);
    fetch(act.url(POST + '?name=' + encodeURIComponent(file.name) + (replace ? '&replace=1' : '')),
      {method: 'POST', headers: {'Content-Type': 'application/zip'}, body: file})
      .then(function (r) { return r.json().then(function (j) { return [r.status, j]; }); })
      .then(function (pair) { act.end(!!(pair[1] && pair[1].ok)); done(pair[0], pair[1]); })
      .catch(function (e) { act.end(false); say('bad', esc(String(e))); });
  }
  function done(status, j) {
    if (j && j.ok) { return installed(j); }
    var sentence = esc((j && j.error) || ('the server answered ' + status));
    if (j && j.exists) {
      // the one refusal with a way forward: the sentence already names what
      // is there, and the button is called what the sentence calls it.
      // It is also the only moment before anything is written, so the shape
      // is named HERE and not only in the answer -- somebody about to
      // overwrite a narrated book with a bundle that carries no narration
      // should read that while there is still a "leave it" to press
      var about = SHAPES[j.audio];
      if (about) sentence += ' This one was packed as <b>' + esc(about[0]) +
        '</b>: ' + about[1] + '.';
      say('warn', sentence + '<div class="act"><button type="button" class="btn go" ' +
        'id="takereplace">replace</button><button type="button" class="btn" ' +
        'id="takecancel">leave it</button></div>');
      $('takereplace').onclick = function () { send(chosen, true); };
      $('takecancel').onclick = function () { msg.hidden = true; };
      return;
    }
    say('bad', sentence);
  }
  function installed(j) {
    var lang = NAMES[j.language] || j.language;
    // "an Italian book": Arabic, Italian and English take the other article,
    // and a sentence that gets it wrong is the first thing a reader notices
    var art = /^[aeiou]/i.test(lang) ? 'an ' : 'a ';
    var h = '<b>' + esc(j.name) + '</b> is in, at <code>' + esc(j.dir) + '</code> &mdash; ' +
      art + esc(lang) + ' ' + esc(j.kind) + ', ' + (j.files || []).length + ' files, ' +
      size(j.bytes) + '.';
    // install refuses a replace that would land anywhere but where the old
    // copy is, so naming the path again here would only repeat the one above
    if (j.replaced) h += ' It replaced the copy that was there.';
    // and which of the three shapes it was, whether or not it replaced
    // anything: it is the difference between a book that has a narration and
    // one that only says it has, and nothing else on the page shows it
    var shape = SHAPES[j.audio];
    if (shape) h += ' Packed as <b>' + esc(shape[0]) + '</b>: ' + shape[1] + '.';
    if ((j.notes || []).length) h += '<ul><li>' + j.notes.map(esc).join('</li><li>') + '</li></ul>';
    var act = [];
    // A BOOK IS NOT BUILT FROM HERE.  It is on the shelf the moment it is
    // installed -- the server writes the library page again as part of the
    // answer -- so it stands among the others, grey, exactly like a book
    // nobody has built yet, and the `build` button on its own card builds it.
    // There used to be a second build here, with its own ways of going
    // wrong; one way to build a book is fewer than two.
    if (j.kind === 'book')
      h += ' It is on the shelf now, <b>not built yet</b>: reload the list and ' +
        'press <b>build</b> on its card, as for any book that has never been built.';
    if (j.library && j.library.ok === false)
      h += ' (The list could not be written again' +
        (j.library.error ? ': ' + esc(j.library.error) : '') +
        ' — run <code>python3 lib/make_index.py</code> if it stays empty.)';
    // a book's reader is not in a bundle -- it is built -- so the link is
    // offered only when install says it carried an old one over
    var href = j.kind === 'video' ? '/youtube/v/' + encodeURIComponent(j.name) + '/'
      : ((j.kept || []).indexOf('reader') >= 0 ? '/' + j.dir + '/reader/' : '');
    if (href) act.push('<a class="btn go" href="' + esc(href) + '">Open the ' +
      (j.kind === 'video' ? 'player' : 'reader') + ' &rarr;</a>');
    act.push('<button type="button" class="btn go" ' +
      'id="takereload">reload the list</button>');
    h += '<div class="act">' + act.join('') + '</div>';
    say('good', h);
    if ($('takereload')) $('takereload').onclick = function () { location.reload(); };
  }
  zone.onclick = function () { pick.click(); };
  zone.onkeydown = function (e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick.click(); }
  };
  // the input is emptied after every pick: a refusal is usually mended in
  // the same zip, and a file input fires nothing when the file chosen is the
  // one it is already holding
  pick.onchange = function () {
    var f = pick.files[0];
    pick.value = '';
    if (f) send(f, false);
  };
  ['dragenter', 'dragover'].forEach(function (n) {
    zone.addEventListener(n, function (e) { e.preventDefault(); zone.classList.add('over'); });
  });
  ['dragleave', 'drop'].forEach(function (n) {
    zone.addEventListener(n, function (e) { e.preventDefault(); zone.classList.remove('over'); });
  });
  zone.addEventListener('drop', function (e) {
    var f = e.dataTransfer && e.dataTransfer.files[0];
    if (f) send(f, false);
  });
})();
</script>
"""

_PANEL_LEDE = {
    "book": "A reading edition you took away with the reader's <b>download</b>, worked on "
            "elsewhere, and zipped up again. Its authored files &mdash; the chapters, "
            "book.json, the sources the fidelity checks read &mdash; go back where they "
            "came from; its narration, its PDF and its built reader stay as they are. "
            "A narrated book is downloaded in one of three shapes &mdash; <b>the text "
            "alone</b>, <b>everything but the recording</b>, <b>all of it</b> &mdash; and "
            "every bundle's manifest says which it is &mdash; so a zip that carries no "
            "narration says so, and says so before it replaces a book that has one.",
    "video": "A video you took away with the player's <b>download</b>, worked on elsewhere, "
             "and zipped up again. video.json, annotations.json, the transcript and the "
             "part files go back where they came from, and the player reads them at once.",
}


SHELF_HTML = """
<section class="take shelf" id="shelf">
  <h2>&#8681; The whole shelf</h2>
  <p class="lede">__SHELF_DESCRIPTION__</p>
  <p class="row">
    <a class="btn" id="shelfget" href="__BACKUP__">Backup every __KIND__</a>
    <button type="button" class="btn" id="shelfput">Load from backup</button>
    <input type="file" id="shelffile" accept=".zip,application/zip,application/x-zip-compressed" hidden>
  </p>
  <div class="msg" id="shelfmsg" hidden></div>
</section>
"""

SHELF_JS = """
<script>
(function () {
  var get = document.getElementById('shelfget');
  var put = document.getElementById('shelfput');
  var pick = document.getElementById('shelffile');
  var msg = document.getElementById('shelfmsg');
  if (!get || !put || !pick) return;
  function say(cls, html) {
    msg.hidden = false; msg.className = 'msg ' + cls; msg.innerHTML = html;
  }
  // OPENED OFF THE DISK there is no server to ask, and a link to one would
  // 404 without a word.  The panel above says the same of itself.
  if (location.protocol === 'file:') {
    get.removeAttribute('href');
    get.classList.add('off'); put.disabled = true;
    say('note', 'Open this page from the toolbox&rsquo;s own address to back up or restore.');
    return;
  }
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function plural(n, one) { return n + ' ' + (n === 1 ? one : one + 's'); }
  // on the activity list while the backup goes up and is put back (as the
  // panel above does for one bundle)
  function working(label) {
    return window.Parseh && Parseh.working ? Parseh.working(label)
      : {url: function (u) { return u; }, end: function () {}};
  }
  function send(file, replace) {
    say('busy', 'Putting <b>' + esc(file.name) + '</b> back&hellip; this can take a while.');
    put.disabled = true;
    var act = working('Restoring from ' + file.name);
    return fetch(act.url('__RESTORE__?name=' + encodeURIComponent(file.name) + (replace ? '&replace=1' : '')), {
      method: 'POST', headers: {'Content-Type': 'application/zip'}, body: file
    }).then(function (r) { return r.json().then(function (j) { return [r, j]; }); })
      .then(function (pair) {
        var j = pair[1];
        act.end(!!j.ok);
        if (!j.ok) { say('bad', esc(j.error || 'that could not be put back')); return; }
        var back = (j.restored || []).length, kept = (j.kept || []).length;
        var notes = j.warnings || [];
        if (kept && !replace) {
          say('ask', plural(kept, '__KIND__') + ' here already were left as they are: <b>'
              + esc((j.kept || []).slice(0, 4).join(', ')) + '</b>.'
              + ' <button type="button" class="btn" id="shelfrep">Replace them</button>'
              + ' <button type="button" class="btn" id="shelfkeep">Keep mine</button>'
              + '<br><small>Replacing sends the backup again and loses anything'
              + ' written since it was made.</small>');
          document.getElementById('shelfrep').onclick = function () { send(file, true); };
          document.getElementById('shelfkeep').onclick = function () {
            say('ok', plural(back, '__KIND__') + ' put back; the rest left as they are.');
          };
          return;
        }
        // a warning is not a failure: something put back and something
        // skipped is still something put back
        say(back ? 'ok' : 'bad', plural(back, '__KIND__') + ' put back'
            + (kept ? ', ' + kept + ' left as they are' : '')
            + (notes.length ? '<br><small>' + esc(notes[0]) + '</small>' : '')
            + (back ? ' &mdash; <a href="">reload the page</a> to see them.' : '.'));
      })
      .catch(function (e) { act.end(false); say('bad', esc(e.message || 'that could not be sent')); })
      .then(function () { put.disabled = false; });
  }
  put.addEventListener('click', function () { pick.click(); });
  pick.addEventListener('change', function () {
    var f = pick.files && pick.files[0];
    pick.value = '';
    if (f) send(f, false);
  });
})();
</script>
"""


def shelf_panel(kind, backup, restore):
    """Backup and restore for the WHOLE shelf, beside the door one book or
    one video comes in by.

    The two are deliberately next to each other: the panel above takes one
    bundle, and a backup is nothing but every one of those bundles in a zip
    -- so what this gives can be taken apart and fed to that, one at a time,
    on a day when only one of them is wanted.
    """
    description = (
        "Back up the whole book shelf as one zip. It holds one "
        "<b>everything but the recording</b> bundle per book. "
        "It leaves out audio/ to save space: copy each book&rsquo;s audio/ directory "
        "separately by hand, then rebuild its reader after restoring it. "
        "Each bundle is a zip the door above can take on its own."
        if kind == "book" else
        "Back up the whole video shelf as one zip. It holds one bundle per "
        "video &mdash; the same zips the door above "
        "takes one at a time &mdash; so any video can be put back by hand."
    )
    return (SHELF_HTML.replace("__KIND__", kind)
            .replace("__SHELF_DESCRIPTION__", description).replace("__BACKUP__", backup)
            + SHELF_JS.replace("__KIND__", kind).replace("__RESTORE__", restore))


def bundle_panel(kind, post):
    """The file picker that posts a bundle to `post` and shows what came back.

    `kind` is the one this door deals in ("book"/"video"): the endpoint
    refuses the other kind by name, and the words here say which is meant.
    The language names are embedded from the registry, so the answer can
    say "a Japanese book" from the code the endpoint returns.
    """
    names = {L.code: L.name for L in languages.LANGS.values()}
    return (PANEL_CSS
            + PANEL_HTML.replace("__KIND__", kind)
                        .replace("__LEDE__", _PANEL_LEDE[kind])
                        .replace("__WHAT__", "&lt;%s&gt;-%s.zip, the download the %s offers"
                                 % ("slug" if kind == "book" else "id", kind,
                                    "reader" if kind == "book" else "player"))
            + PANEL_JS.replace("__POST__", json.dumps(post))
                      .replace("__NAMES__", json.dumps(names, ensure_ascii=False)
                               .replace("</", "<\\/")))


def stats(book):
    """What the built reader says about itself, if it has been built."""
    out = {"built": False}
    if not os.path.exists(book.reader_html):
        return out
    head = open(book.reader_html, encoding="utf-8").read()
    m = re.search(r"const META=(\{.*?\});", head, re.S)
    if m:
        try:
            out.update(json.loads(m.group(1)))
            out["built"] = True
        except ValueError:
            pass
    return out


def card(b):
    st = stats(b)
    L = b.lang
    tags = []
    # A BOOK AN AGENT IS STILL MAKING says where the making stands, from its
    # making.json (lib/making.py).  The page is a file, written when a book
    # is built and not when the agent writes a batch, so this is what the
    # making was the last time it was written; the script at the foot of the
    # page asks the server again, and moves it while the tab is open.
    made = making.is_making(b.dir)
    if made:
        doc, _bad = making.read(b.dir)
        tags.append('<span class="tag on" data-making-tag>being made &middot; %s</span>'
                    % esc(making.stage_words(doc or {})))
    if st.get("built"):
        tags.append('<span class="tag">%s chapters</span>'
                    % len(st.get("chapters", [])))
        tags.append('<span class="tag">%s subparagraphs</span>' % st.get("subs", 0))
        if b.has_audio:
            n, tot = st.get("timed", 0), st.get("subs", 0)
            tags.append('<span class="tag on">audio &middot; %d/%d timed</span>'
                        % (n, tot))
        else:
            tags.append('<span class="tag no">no audio yet</span>')
    else:
        tags.append('<span class="tag no">not built yet</span>')

    # the reader's own file, not its directory: a directory URL is fine when
    # serve.py answers, but the page also opens off the disk, where only a
    # file resolves
    href = b.rel_from_books() + "/reader/index.html"
    cls = "book" if st.get("built") else "book pending"
    # building it from here: the server runs ./build.sh as a job and parseh.js
    # polls it.  A book with no reader has nothing for its card to open, so
    # the whole card builds it; a built one keeps the button in the corner.
    build = "%s/__build" % b.rel_from_books()
    what = b.title_latin or b.slug
    # The title and author are in the book's language: they carry its lang
    # and dir, and the card's data-lang picks the face (parseh.css reads the
    # --tl-font token langs.css sets for that data-lang).
    attrs = L.html_attrs()
    # the x is inside the card's own <a>, as the studio's is: parseh.js
    # catches it in the capture phase so the click never follows the link
    delete_btn = ('<button type="button" class="card-del" title="take this book '
                  'off the shelf" data-del="%s/__delete" data-what="%s">'
                  '&#10005;</button>'
                  % (esc(b.rel_from_books()), esc(b.title_latin or b.slug)))
    build_btn = ('<button type="button" class="card-build" title="%s" data-build="%s" '
                 'data-what="%s">%s</button>'
                 % ("build it again: the PDF and the reader (./build.sh)" if st.get("built")
                    else "build this book: its reader and its PDF (./build.sh)",
                    esc(build), esc(what), "rebuild" if st.get("built") else "build"))
    whole = "" if st.get("built") else ' data-build="%s" data-what="%s"' % (esc(build), esc(what))
    if made:
        whole += ' data-making="%s"' % esc(b.rel_from_books())
    return """<a class="%s" href="%s" data-lang="%s"%s>
  %s%s
  <div class="fa"%s>%s</div>
  <div class="by"%s>%s</div>
  <div class="lat">%s <i>&mdash; %s</i></div>
  <div class="blurb">%s</div>
  <div class="tags">%s</div>
</a>""" % (cls, esc(href), esc(L.code), whole, delete_btn, build_btn, attrs, esc(b.title), attrs, esc(b.author),
           esc(b.title_latin), esc(b.author_latin),
           esc(b.meta.get("blurb", "")), "".join(tags))


# A CARD OF A BOOK BEING MADE MOVES while the page is open: the stage and how long
# ago the agent last wrote, asked of the server for each such card and again every
# few seconds while the tab is showing.  A page opened off the disk has no server
# to ask and keeps what it was written with; so does one that cannot reach it.
MAKING_JS = """<script>
(function () {
  if (location.protocol === 'file:') return;
  var cards = Array.prototype.slice.call(document.querySelectorAll('a.book[data-making]'));
  if (!cards.length) return;
  function ago(s) {
    s = Math.max(0, Math.round(s));
    if (s < 90) return 'just now';
    if (s < 5400) return Math.round(s / 60) + ' minutes ago';
    if (s < 129600) return Math.round(s / 3600) + ' hours ago';
    return Math.round(s / 86400) + ' days ago';
  }
  function poll() {
    cards.forEach(function (card) {
      fetch(card.getAttribute('data-making') + '/__making', {cache: 'no-store'})
        .then(function (r) { return r.json(); })
        .then(function (j) {
          var tag = card.querySelector('[data-making-tag]');
          if (!tag || !j.ok) return;
          if (!j.making) { tag.textContent = 'finished'; card.removeAttribute('data-making'); return; }
          tag.textContent = 'being made \u00b7 ' + j.words +
            (j.updated ? ' \u00b7 ' + ago(j.now - j.updated) : '');
        }).catch(function () {});
    });
  }
  poll();
  setInterval(function () { if (!document.hidden) poll(); }, 8000);
})();
</script>"""


def lang_head(L, n):
    """The heading over one language's cards: the English name, the native
    name in the language's own face, the count."""
    return ('<h2 class="lang-head" data-lang="%s"><span class="name">%s</span>'
            '<bdi class="native"%s>%s</bdi><span class="n">%d</span></h2>'
            % (esc(L.code), esc(L.name), L.html_attrs(), esc(L.native), n))


def groups(bs):
    """The cards grouped by language, in registry order; languages without
    a book get no heading."""
    out, counts = [], {}
    for L in languages.LANGS.values():
        mine = [b for b in bs if b.language == L.code]
        if not mine:
            continue
        counts[L.code] = len(mine)
        out.append(lang_head(L, len(mine)))
        out.extend(card(b) for b in mine)
    return "\n".join(out), counts


def main():
    bs = all_books()
    for b in bs:
        b.check_placement()
    # the readers and this page link lib/langs.css by a relative path, so the
    # generated tokens have to exist ON DISK beside parseh.css (the server
    # also answers /lib/langs.css itself, for the pages it assembles)
    languages.write_css()
    lib_rel = os.path.relpath(LIB, BOOKS_DIR).replace(os.sep, "/")
    cards, counts = groups(bs)
    # The chip row filters the cards and the headings; the "Add a book" card
    # carries no data-lang and must stay whatever is picked, so the selector
    # names only the cards that have one.
    chips = languages.chips_html(counts, selector="a.book[data-lang], .lang-head")
    page = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Books &mdash; %(app)s</title>
<link rel="stylesheet" href="%(lib)s/parseh.css">
<link rel="stylesheet" href="%(lib)s/langs.css">
<script src="%(lib)s/parseh.js"></script>
</head><body class="index">
<div class="parseh-bar">
  <a class="home" href="../" title="the hub"><span class="glyph">&#x67E;</span>%(app)s</a>
  <span class="where">books</span>
  <span class="sp"></span>
  <button type="button" data-parseh-theme title="theme">&#9680;</button>
  <button type="button" class="stop" data-parseh-stop title="stop the server">&#9211; stop</button>
</div>
<main>
  <h1 class="idx">Books</h1>
%(chips)s
%(cards)s
<a class="book sync add" href="add/">
  <div class="chname">&#65291; Add a book</div>
  <div class="blurb">A new reading edition, in any of the languages. Paste a chapter and get
  the whole book with every gloss blank, to write yourself in the reader &mdash; or have an
  agent make it: Parseh makes the book&rsquo;s folder and the agent you use fills it in, while you
  watch it grow here and steer it.</div>
</a>
%(take)s
  <footer class="idx">
    Each book is a directory under <code>books/&lt;language&gt;/</code> with a
    <code>book.json</code>. A card&rsquo;s <b>build</b> button makes that book&rsquo;s
    reader and PDF; <code>./build.sh</code> does every book from a terminal.
  </footer>
</main>
%(making)s
</body></html>
""" % {"app": APP_NAME, "lib": lib_rel, "cards": cards, "chips": chips,
       "take": (bundle_panel("book", "/books/__upload")
                + shelf_panel("book", "/books/__backup", "/books/__restore")),
       "making": MAKING_JS}
    out = os.path.join(BOOKS_DIR, "index.html")
    open(out, "w", encoding="utf-8").write(page)
    print("books/index.html  %d book%s: %s"
          % (len(bs), "" if len(bs) == 1 else "s",
             ", ".join("%s [%s]" % (b.rel_from_books(), b.language) for b in bs)))


if __name__ == "__main__":
    main()
