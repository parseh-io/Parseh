# SPDX-License-Identifier: GPL-3.0-or-later
"""webexport — a document, or a deck's chosen exercises, as ONE HTML file.

TO-DO §8.38 and §9.7: a page to drop into a website, for students who have
no Parseh.  It is opened from a file:// link or off a plain static host with
no server of any kind behind it, and it is much less than the studio -- that
is the point:

  * EVERYTHING TRAVELS WITH IT.  The sheet's styles, the faces it is set in
    (cut down to the letters the page uses), the pictures, the recordings --
    cut down to the stretches the page plays, where this machine has ffmpeg
    -- and the script that makes the exercises work are all inside the one
    file.  The one thing it reaches out for is a YouTube video the document
    embeds, which plays in YouTube's own player (the owner's choice).
  * READ-ONLY BY CONSTRUCTION.  What is shipped is the RENDER, never the
    Markdown: the attributes the studio writes so that its editor can find a
    block again (the source of a target-language line, the line numbers, the
    occurrence counters) are taken off, a link to another document of the
    library keeps its words and loses everything else, and the pieces of the
    studio that write -- the ✎ buttons, the layout ⚙, + Deck -- are not in
    it.  Nor is the code behind them: the script is a slice of app.js, the
    functions an exercise needs to be answered and marked and nothing that
    could save anything (_runtime).  The one thing that does change is the
    cloud a word of the target language opens -- its transliteration, its
    reading, its colours -- and it changes the open page only: the first
    click on a word says so, in one line over the screen.
  * IT WRITES NOWHERE.  The page carries its own Content-Security-Policy, so
    no request can leave it (no connect, no form, no worker), and its script
    runs over a storage of its own that is forgotten with the tab -- the
    choices a reader makes (a theme, hiding the transliterations) last as long
    as the tab and are never written into the browser.  Nothing is scheduled:
    a deck's exercises are crammed, the way its cram page does, and a closed
    tab has changed nothing anywhere.

The answers are in the file, plainly, as the studio page holds them: a page
that marks the student's answers must know them (the owner's choice).  At
its foot the page says it was exported from Parseh, with links to Parseh's
page on GitHub and to its guide (_footer), followed only when clicked.

    document_html(doc_id, meta, markdown, media)   -> (filename, bytes)
    deck_html(deck, items, media)                  -> (filename, bytes)

`media(path)` answers the file on disk that the Markdown's `images/x.png` or
`audio/x.mp3` names, or None.  The two routes that use this are the
document's Download ▾ (server.serve_download, kind "html") and the deck's
"Export selected to HTML" (deckroutes.api_export_html).
"""
import base64
import html
import json
import os
import re
import shutil
import sys
import tempfile
import threading
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
TEMPLATES = HERE / "templates"
PARSEH = HERE.parent.parent
LIB = PARSEH / "lib"
for _p in (str(LIB), str(HERE.parent / "exlex")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audiofile            # noqa: E402  the clips, cut where ffmpeg is here
import htmlgen              # noqa: E402
import languages            # noqa: E402
import project              # noqa: E402  where Parseh lives: the two links of the foot


class ExportError(Exception):
    """Nothing can be exported (no exercise chosen, a deck that is gone)."""


# ---------------------------------------------------------------- the page's rules

# WHAT THE FILE MAY DO, said to the browser, which enforces it: its own
# inline script and styles, its own pictures, recordings and faces (data:,
# and the blob: URLs its script makes of the recordings), and a YouTube
# player where the document embeds one.  Nothing else can be fetched, posted
# or framed, and no worker can be registered -- the "writes nowhere" of the
# TO-DO, made true by the browser rather than promised by the script.
CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
       "img-src data: blob:; media-src data: blob:; font-src data:; "
       "frame-src https://www.youtube-nocookie.com; connect-src 'none'; "
       "form-action 'none'; base-uri 'none'; worker-src 'none'; object-src 'none'; "
       "manifest-src 'none'")

# THE PLAYER, and what it is told.  The page sends no referrer (its <meta
# name="referrer">): a link a student follows does not say where it was
# followed from.  But YouTube refuses to play for a player that does not say
# where it is embedded -- "Video player configuration error", its error 153
# -- so the player alone sends the address of the site, and nothing of the
# page's path (strict-origin-when-cross-origin, what YouTube asks for).
# Opened from the disk there is no site to name, and a browser sends nothing
# from a file:// page: there YouTube will not play it, whatever the page says.
YOUTUBE_PLAYER = "https://www.youtube-nocookie.com/"
PLAYER_REFERRER = "strict-origin-when-cross-origin"

# THE ATTRIBUTES THAT ARE THE SOURCE, or point back into it, taken off
# everything the page shows.  The studio writes them for its editor and its
# hover tools: the Markdown of a target-language line or block (so the
# overlay can open it again), the line a block starts on, where an exercise
# ends, how many times a run occurred before (the word cloud's source key), a
# formula's source twice over (data-tex stays: it is what the formula is
# drawn from), a linked document's name.  None of them is read by anything
# the exported page runs; every one of them would let its Markdown be pieced
# back together.
SOURCE_ATTRS = frozenset((
    "data-tl-src", "data-rtl-src", "data-la-src", "data-math-src",
    # (a word's data-fa travels: it is the word as it is shown, what the
    # transliteration cloud opens on, and nothing of the source)
    "data-src-line", "data-src-end", "data-occ", "data-tl-occ",
    "data-name", "data-tl-kind", "data-rtl-kind", "data-math-kind",
    "data-editor-preview", "data-idx",
    # a latex block's own LaTeX, its theme's name and its caption as written:
    # the source, which never travels (a drawing does, as a picture, and the
    # caption as the words under it)
    "data-latex-src", "data-latex-theme", "data-latex-key", "data-latex-caption",
    # and its number in the studio's page, which swaps a drawing made late
    "data-latex-idx", "data-latex-pending"))

# the pieces of the studio's page that write, or edit: never shipped -- and,
# of a latex block that could not be drawn, its LaTeX, LaTeX's log and the
# buttons that mend it on the computer: the page says it could not be drawn,
# and nothing of the source travels
DROP_CLASSES = frozenset(("video-edit", "audio-edit", "ex-edit", "ex-to-deck",
                          "latex-code", "latex-log", "latex-fix", "latex-views"))

MEDIA_SCHEME = "parseh-media:"

# The type a file is sent as, by its extension -- the extensions the studio
# accepts for pictures (store) and recordings (audiofile.EXTS).
MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
    ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".ogg": "audio/ogg", ".oga": "audio/ogg", ".opus": "audio/ogg",
    ".wav": "audio/wav", ".flac": "audio/flac", ".webm": "audio/webm",
}


def _mime(path):
    return MIME.get(Path(path).suffix.lower(), "application/octet-stream")


def _data_uri(data, mime):
    return "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))


def _slug(text, fallback):
    """A file name out of a title: letters and digits of any script kept,
    everything else a hyphen, as a page's address would have it."""
    s = re.sub(r"[^\w]+", "-", (text or "").strip().lower(), flags=re.UNICODE).strip("-_")
    return (s[:80].rstrip("-_") or fallback)


# ---------------------------------------------------------------- the media

class _Media:
    """The pictures and recordings of one page, each carried once.

    `url(path)` is what the renderer is given as its asset base: a marker
    (`parseh-media:N`) for a file that is on disk, None for one that is not
    (the renderer then draws its own placeholder, as for an unsaved preview).
    Pictures are then written into the page as data: URIs where they are
    shown.  Recordings are not: a document may play twenty clips of one long
    narration, so each distinct recording -- or, where ffmpeg is here, each
    distinct stretch of one -- is carried once, in the store the page's
    script reads (#parseh-media), and every <audio> that plays it says which
    (`data-media`).  A clip that was cut is marked `data-cut`: its window is
    the whole file now, and the script takes the window off its box before
    anything plays it."""

    def __init__(self, resolve):
        self.resolve = resolve
        self.paths = []                 # marker number -> (path on disk, name)
        self.store = {}                 # key -> data URI
        self.cuts = {}                  # (n, start, end) -> key or None
        self.whole = {}                 # n -> key
        self.images = {}                # n -> data URI
        self.tmp = None
        self.cut_count = 0
        self.can_cut = audiofile.have_ffmpeg()

    def url(self, path):
        disk = self.resolve(path)
        if disk is None:
            return None
        # one number per FILE, however often the page shows or plays it:
        # it is what the store is keyed by, so twenty uses are one copy
        disk = Path(disk).resolve()
        for n, (known, _name) in enumerate(self.paths):
            if known == disk:
                return "%s%d" % (MEDIA_SCHEME, n)
        self.paths.append((disk, path))
        return "%s%d" % (MEDIA_SCHEME, len(self.paths) - 1)

    def image(self, n):
        if n not in self.images:
            disk, _name = self.paths[n]
            self.images[n] = _data_uri(disk.read_bytes(), _mime(disk))
        return self.images[n]

    def _whole(self, n):
        if n not in self.whole:
            disk, _name = self.paths[n]
            key = "a%d" % len(self.store)
            self.store[key] = _data_uri(disk.read_bytes(), _mime(disk))
            self.whole[n] = key
        return self.whole[n]

    def _cut(self, n, start, end):
        """The stretch [start, end] of recording n, cut by ffmpeg and
        carried once -- or None where it cannot be cut (no ffmpeg, a window
        that runs to the end of a recording whose length is not known, a
        cut that fails): the whole recording is then carried instead, and
        the page plays its window out of it as the studio does."""
        k = (n, start, end)
        if k in self.cuts:
            return self.cuts[k]
        got = None
        disk, _name = self.paths[n]
        if self.can_cut:
            try:
                s = float(start or 0)
                e = float(end) if end is not None else audiofile.duration(str(disk))
                if e is not None and e > s:
                    if self.tmp is None:
                        self.tmp = tempfile.mkdtemp(prefix="parseh-export-")
                    out = audiofile.extract(str(disk), s, e,
                                            os.path.join(self.tmp, "c%d" % len(self.cuts)))
                    key = "a%d" % len(self.store)
                    self.store[key] = _data_uri(Path(out).read_bytes(), _mime(out))
                    self.cut_count += 1
                    got = key
            except (audiofile.AudioError, OSError, ValueError):
                got = None
        self.cuts[k] = got
        return got

    def audio(self, n, fragment):
        """(key, cut) for an <audio> of recording n, given the media
        fragment the renderer wrote after its URL (`#t=65.2,69`, or '')."""
        m = re.match(r"#t=([0-9.]+)(?:,([0-9.]+))?$", fragment or "")
        if m:
            key = self._cut(n, m.group(1), m.group(2))
            if key:
                return key, True
        return self._whole(n), False

    def close(self):
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp = None


# ---------------------------------------------------------------- the render, cleaned

_VOID = frozenset(("area", "base", "br", "col", "embed", "hr", "img", "input",
                   "link", "meta", "source", "track", "wbr"))


class _Clean(HTMLParser):
    """The rendered HTML again, with what may not travel taken out (the
    module docstring says what, and why) and the media pointed at the
    page's own copies.  htmlgen writes well-formed HTML, so a stream that
    re-emits every tag it is handed, less the ones it drops, is the render
    itself -- nothing is re-flowed, re-quoted beyond escaping, or reordered."""

    def __init__(self, media):
        super().__init__(convert_charrefs=False)
        self.media = media
        self.out = []
        self.stack = []                 # (tag, dropped, renamed-to)
        self.dropping = 0               # > 0 inside an element being left out

    # -- helpers
    def _attrs(self, attrs):
        return "".join(' %s' % k if v is None else ' %s="%s"' % (k, html.escape(v, quote=True))
                       for k, v in attrs)

    def _rewrite(self, tag, attrs):
        """-> (tag, attrs, drop) for one start tag."""
        d = dict(attrs)
        classes = (d.get("class") or "").split()
        if DROP_CLASSES.intersection(classes):
            return tag, attrs, True
        keep = []
        for k, v in attrs:
            if k in SOURCE_ATTRS:
                continue
            keep.append((k, v))
        attrs = keep
        # ANOTHER DOCUMENT OF THE LIBRARY: its words stay, and nothing else
        # of it -- not its address, not its name (the owner's choice)
        if tag == "a" and "doclink" in classes:
            return "span", [("class", "doclink-plain")], False
        if tag == "span" and "doclink-dead" in classes:
            return "span", [("class", "doclink-plain")], False
        # the page's own copy of a picture or a recording
        src = d.get("src") or ""
        if src.startswith(MEDIA_SCHEME):
            rest = src[len(MEDIA_SCHEME):]
            m = re.match(r"(\d+)(#.*)?$", rest)
            n, frag = int(m.group(1)), m.group(2) or ""
            attrs = [(k, v) for k, v in attrs if k != "src"]
            if tag == "img":
                attrs.append(("src", self.media.image(n)))
            else:
                key, cut = self.media.audio(n, frag)
                attrs.append(("data-media", key))
                if cut:
                    attrs.append(("data-cut", "1"))
                elif frag:
                    attrs.append(("data-frag", frag))
        # a YouTube player says which site it is on (YOUTUBE_PLAYER)
        if tag == "iframe" and src.startswith(YOUTUBE_PLAYER):
            attrs = [(k, v) for k, v in attrs if k != "referrerpolicy"]
            attrs.append(("referrerpolicy", PLAYER_REFERRER))
        return tag, attrs, False

    # -- the stream
    def handle_starttag(self, tag, attrs):
        void = tag in _VOID
        if self.dropping:
            if not void:
                self.stack.append((tag, True, tag))
                self.dropping += 1
            return
        new, attrs, drop = self._rewrite(tag, attrs)
        if drop:
            if not void:
                self.stack.append((tag, True, tag))
                self.dropping += 1
            return
        self.out.append("<%s%s>" % (new, self._attrs(attrs)))
        if not void:
            self.stack.append((tag, False, new))

    def handle_startendtag(self, tag, attrs):
        if self.dropping:
            return
        new, attrs, drop = self._rewrite(tag, attrs)
        if not drop:
            self.out.append("<%s%s>" % (new, self._attrs(attrs)))

    def handle_endtag(self, tag):
        if tag in _VOID:
            return
        # close up to the matching open tag (htmlgen closes what it opens)
        while self.stack:
            t, dropped, new = self.stack.pop()
            if dropped:
                self.dropping -= 1
            elif not self.dropping:
                self.out.append("</%s>" % new)
            if t == tag:
                break

    def handle_data(self, data):
        if not self.dropping:
            self.out.append(data)

    def handle_entityref(self, name):
        if not self.dropping:
            self.out.append("&%s;" % name)

    def handle_charref(self, name):
        if not self.dropping:
            self.out.append("&#%s;" % name)

    def handle_comment(self, data):
        pass                            # a comment is the author's, never the page's

    def handle_decl(self, decl):
        pass

    def handle_pi(self, data):
        pass

    def unknown_decl(self, data):
        pass


# A LATEX BLOCK'S DRAWING TRAVELS AS WHAT WAS DRAWN (TO-DO §8.39): the SVG
# lib/latexdraw.py made, inside the page as a data: URI -- nothing reading the
# page needs LaTeX, a compiler, or Parseh.
_LATEX_SRC_RE = re.compile(r'src="[^"]*/latex/([0-9a-f]{64})\.svg"')


def _drawings(rendered):
    import latexdraw

    def one(m):
        path = latexdraw.file_of(m.group(1) + ".svg")
        if not path:
            return m.group(0)
        with open(path, "rb") as fh:
            return 'src="%s"' % _data_uri(fh.read(), "image/svg+xml")
    return _LATEX_SRC_RE.sub(one, rendered)


def clean(rendered, media):
    """The rendered HTML fit to travel (_Clean)."""
    p = _Clean(media)
    p.feed(_drawings(rendered))
    p.close()
    return "".join(p.out)


# ---------------------------------------------------------------- the faces

_FACE_RE = re.compile(r"@font-face\s*\{[^}]*\}", re.S)
_FAMILY_RE = re.compile(r"font-family\s*:\s*['\"]?([^;'\"]+)['\"]?")
_URL_RE = re.compile(r"url\(\s*['\"]?(fonts/[^)'\"]+)['\"]?\s*\)\s*format\(\s*['\"]?([a-z0-9]+)['\"]?\s*\)")

# the letters the page's own chrome writes whatever the document says: the
# buttons and notes of the exercises and of the cram, in the studio's prose
# (ASCII, Latin-1, the typographer's punctuation, the arrows and ticks)
_CHROME = ("".join(chr(c) for c in range(0x20, 0x7f)) +
           "".join(chr(c) for c in range(0xa0, 0x100)) +
           "‐‑–—‘’‚“”„†‡•…‰′″‹›€™←↑→↓↔⇄⌃⌄✓✔✗✕✖✎⚙★☆▲▼◀▶●○◐□■·×÷±≈≠≤≥−")


def _faces_css(css, text, lang):
    """The sheet's @font-face rules with their fonts inside them.

    A face is carried only where the page can use it -- the Latin faces the
    prose is set in, and the target language's own (its --tl-font and
    --tl-alt, from the registry) -- and, where fontTools is here (it is in
    environment.yml, for the reader's fonts), cut down to the characters the
    page holds, as WOFF2: a Persian page carries a few kilobytes of Vazirmatn
    rather than its whole alphabet.  Without fontTools the whole face goes in.
    A face none of whose letters the page uses is left out altogether."""
    wanted_families = {"TeX Gyre Pagella", "TeX Gyre Heros"}
    stack = " ".join(str(v) for v in (lang.fonts or {}).values())
    for fam in re.findall(r"'([^']+)'|\"([^\"]+)\"|([A-Za-z][\w ]+)", stack):
        wanted_families.add(next(x for x in fam if x).strip())
    chars = set(text) | set(_CHROME)
    try:
        from fontTools import subset as ftsubset          # noqa: F401
        have_ft = True
    except Exception:
        have_ft = False
    out = []
    cache = {}
    for rule in _FACE_RE.findall(css):
        fam = _FAMILY_RE.search(rule)
        if not fam or fam.group(1).strip() not in wanted_families:
            continue
        urls = _URL_RE.findall(rule)
        if not urls:
            continue
        rel, fmt = urls[0]
        path = STATIC / rel
        if not path.is_file():
            continue
        if path not in cache:
            cache[path] = _subset(path, chars) if have_ft else (path.read_bytes(), fmt)
        got = cache[path]
        if got is None:
            continue                    # nothing of this face on the page
        data, fmt = got
        mime = {"woff2": "font/woff2", "opentype": "font/otf",
                "truetype": "font/ttf"}.get(fmt, "application/octet-stream")
        head = rule[:rule.index("src")].rstrip()
        out.append("%s\n  src: url(%s) format(\"%s\"); }"
                   % (head, _data_uri(data, mime), fmt))
    return "\n".join(out)


def _subset(path, chars):
    """(woff2 bytes, "woff2") of the face at `path` with only `chars` in it,
    its layout features whole (an Arabic script's joining forms and a
    Devanagari conjunct are reached through them, not through a code
    point), or None when the face has none of them; the whole file when the
    cut fails."""
    import logging
    from fontTools import subset as ftsubset
    from fontTools.ttLib import TTFont
    # the subsetter names every table it drops (a font's FFTM, its meta) on
    # the console, a warning per face per export: said nowhere anyone reads
    logging.getLogger("fontTools").setLevel(logging.ERROR)
    try:
        font = TTFont(str(path))
        cmap = font.getBestCmap() or {}
        codes = sorted(ord(c) for c in chars if ord(c) in cmap)
        if not codes:
            return None
        opts = ftsubset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        opts.glyph_names = False
        opts.hinting = False
        sub = ftsubset.Subsetter(options=opts)
        sub.populate(unicodes=codes)
        sub.subset(font)
        import io
        buf = io.BytesIO()
        font.flavor = "woff2"
        font.save(buf)
        return buf.getvalue(), "woff2"
    except Exception:
        fmt = {".woff2": "woff2", ".otf": "opentype", ".ttf": "truetype"}.get(
            path.suffix.lower(), "opentype")
        return path.read_bytes(), fmt


def _css(text, lang, math):
    """Every rule the page needs, in one sheet: the studio's sheet and its
    chrome (served as one at /static/app.css: server.serve_app_css), the
    registry's per-language tokens, the export's own few (export.css), and
    MathJax's where there is maths -- with the faces put inside (_faces_css)
    and every other font-face rule of the sheet left behind."""
    sheet = (STATIC / "sheet.css").read_text(encoding="utf-8")
    chrome = (STATIC / "app.css").read_text(encoding="utf-8")
    faces = _faces_css(sheet, text, lang)
    sheet = _FACE_RE.sub("", sheet)
    parts = [faces, sheet, chrome, languages.css(),
             (STATIC / "export.css").read_text(encoding="utf-8")]
    if math:
        parts.append((LIB / "mathjax.css").read_text(encoding="utf-8"))
    css = "\n".join(parts)
    # anything still pointing at a file of the studio's (a stray url() in a
    # rule nothing here uses) could only fail, and quietly: taken out
    css = re.sub(r"url\(\s*['\"]?(?!data:)[^)]*\)", "none", css)
    return css


# ---------------------------------------------------------------- the script

# WHAT OF app.js THE PAGE RUNS.  The studio's script is one file for every
# page it has -- the library, the reading view, the editor, the prompt page --
# and most of it talks to the server: saving, colouring, laying out, copying
# into a deck.  The exported page takes a slice of it and no more: the
# declarations below and everything they use, and the few statements that
# every page of the studio runs for its media (a clip plays its window, one
# recording of an exercise sounds at a time, a YouTube clip replays).  The
# slice is worked out from app.js as it is today, every time, so a helper an
# exercise comes to need later is carried without anybody remembering to.
ROOTS = ("bindExercises", "bindFootnoteClouds", "armClipReplay", "applyTypo",
         # the cloud a word of the target language opens: its transliteration
         # (and kana), and the colours -- changed on the open page only, by
         # appliers that touch the DOM and nothing else (bindPageCloud)
         "bindPageCloud",
         "loadTypo", "defaultScale", "lang", "langAttrs", "TYPO_DEFAULTS",
         "sharedSheetTheme", "foldCase", "escAttr", "clipWindow", "watchClipEnd",
         "flipCard", "toggleCardAudio", "openCardZoom")
STATEMENTS = (r'^document\.addEventListener\("play"',
              r'^document\.addEventListener\("seeked"',
              r'^for \(const type of \["pause", "ended", "emptied"\]\)',
              r'^window\.addEventListener\("message"',
              r'^try \{ hideExerciseTransliterations')
_RUNTIME = {}
_RUNTIME_LOCK = threading.Lock()


def _code_only(src):
    """`src` with its comments, strings and regular expressions blanked out,
    so that the names left are names the code USES: a comment that mentions
    initDoc must not bring initDoc -- and the server calls in it -- into the
    page.  A template literal's ${...} is code and stays."""
    out, i, n = [], 0, len(src)
    last = ""                           # the last significant character
    word_before = ""
    REGEX_AFTER = set("(,=:[!&|?{};+-*%~^<>")
    KEYWORDS = {"return", "typeof", "case", "do", "else", "in", "of", "new",
                "delete", "void", "throw", "instanceof", "yield", "await"}

    def skip_string(j, q):
        j += 1
        while j < n and src[j] != q:
            if src[j] == "\\":
                j += 1
            elif src[j] == "\n":
                break
            j += 1
        return j + 1

    def template(j):
        # returns (index after the closing backtick, code of its ${...})
        codes = []
        j += 1
        while j < n:
            c = src[j]
            if c == "\\":
                j += 2
                continue
            if c == "`":
                return j + 1, codes
            if c == "$" and j + 1 < n and src[j + 1] == "{":
                depth, k = 1, j + 2
                start = k
                while k < n and depth:
                    ch = src[k]
                    if ch in "'\"":
                        k = skip_string(k, ch)
                        continue
                    if ch == "`":
                        k, inner = template(k)
                        continue
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                    k += 1
                codes.append(src[start:k - 1])
                j = k
                continue
            j += 1
        return j, codes

    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")
            continue
        if c in "'\"":
            i = skip_string(i, c)
            out.append(" ")
            last = "a"
            continue
        if c == "`":
            i, codes = template(i)
            out.append(" " + " ".join(_code_only(x) for x in codes) + " ")
            last = "a"
            continue
        if c == "/" and (last in REGEX_AFTER or last == "" or word_before in KEYWORDS):
            # a regular expression: to its closing slash, past a class
            j, cls = i + 1, False
            while j < n and src[j] != "\n":
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "[":
                    cls = True
                elif ch == "]":
                    cls = False
                elif ch == "/" and not cls:
                    break
                j += 1
            j += 1
            while j < n and (src[j].isalnum()):
                j += 1
            i = j
            out.append(" ")
            last = "a"
            continue
        out.append(c)
        if not c.isspace():
            last = c
            if c.isalnum() or c in "_$":
                m = re.match(r"[A-Za-z_$][\w$]*", src[i:])
                if m and (i == 0 or not (src[i - 1].isalnum() or src[i - 1] in "_$")):
                    word_before = m.group(0)
                    out.append(src[i + 1:i + len(m.group(0))])
                    i += len(m.group(0))
                    last = "a"
                    continue
            word_before = ""
        i += 1
    return "".join(out)


def _statements(src):
    """app.js as its top-level statements: [(first line, text)].  The file
    is written with every top-level statement starting at the left margin
    and everything inside one indented, which is what this reads; a line at
    the margin that closes a bracket, or goes on with else / catch /
    finally, belongs to the statement above it."""
    lines = src.split("\n")
    starts, in_block = [], False
    for i, line in enumerate(lines):
        if in_block:
            if "*/" in line:
                in_block = False
            continue
        if not line or line[0] in " \t":
            continue
        if line.startswith("/*"):
            in_block = "*/" not in line[2:]
            continue
        if line.startswith("//") or line[0] in "}])":
            continue
        if re.match(r"(else|catch|finally)\b", line):
            continue
        starts.append(i)
    out = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(lines)
        out.append((lines[s], "\n".join(lines[s:e])))
    return out


def _declares(first):
    m = re.match(r"(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)", first)
    if m:
        return [m.group(1)]
    m = re.match(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)", first)
    return [m.group(1)] if m else []


def _runtime():
    """The slice of app.js the page runs (ROOTS, STATEMENTS), in the file's
    own order, with the toolbox's case fold spliced in as the studio's server
    splices it (server.serve_app_js).  Worked out once per version of app.js."""
    path = STATIC / "app.js"
    stamp = path.stat().st_mtime_ns
    with _RUNTIME_LOCK:
        if _RUNTIME.get("stamp") == stamp:
            return _RUNTIME["js"]
        src = path.read_text(encoding="utf-8")
        stmts = _statements(src)
        defines = {}
        codes = []
        for idx, (first, text) in enumerate(stmts):
            code = _code_only(text)
            codes.append(code)
            for name in _declares(first):
                defines.setdefault(name, idx)
        names = set(defines)
        chosen, todo = set(), []
        for name in ROOTS:
            if name in defines:
                todo.append(defines[name])
        for idx, (first, _text) in enumerate(stmts):
            if any(re.match(p, first) for p in STATEMENTS):
                todo.append(idx)
        while todo:
            idx = todo.pop()
            if idx in chosen:
                continue
            chosen.add(idx)
            refs = set(re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)", codes[idx]))
            for name in refs & names:
                if defines[name] not in chosen:
                    todo.append(defines[name])
        js = "\n".join(stmts[i][1] for i in sorted(chosen))
        js = js.replace("__FOLD__", languages.FOLD_JS)
        _RUNTIME.update(stamp=stamp, js=js)
        return js


def _script(math):
    """The one <script> the page runs: the app.js slice and the export's own
    boot (static/export.js), inside a function whose `localStorage` and
    `sessionStorage` are storages of its own -- so every choice the reader
    makes lasts as long as the tab and not a moment longer, and nothing the
    studio's code would have written down is written anywhere.  With maths,
    MathJax itself before it, configured as lib/mathjax.js configures it."""
    memory = (
        "function parsehMemory() {\n"
        "  // A storage that is forgotten with the tab: what the page's script\n"
        "  // is given in the place of localStorage and sessionStorage.\n"
        "  const held = new Map();\n"
        "  return {\n"
        "    getItem: k => held.has(String(k)) ? held.get(String(k)) : null,\n"
        "    setItem: (k, v) => { held.set(String(k), String(v)); },\n"
        "    removeItem: k => { held.delete(String(k)); },\n"
        "    clear: () => held.clear(),\n"
        "    key: i => Array.from(held.keys())[i] || null,\n"
        "    get length() { return held.size; }\n"
        "  };\n"
        "}\n")
    boot = (STATIC / "export.js").read_text(encoding="utf-8")
    js = (memory + "(function (localStorage, sessionStorage) {\n\"use strict\";\n"
          + _runtime() + "\n" + boot + "\n})(parsehMemory(), parsehMemory());\n")
    return js.replace("</script", "<\\/script")


def _math_scripts():
    """MathJax, carried whole into a page that has a formula (it is 2 MB, so
    a page without one carries none of it), and configured before it starts
    as lib/mathjax.js configures it: nothing typeset until asked, each formula
    carrying its own glyphs, no menu."""
    lib = (LIB / "mathjax" / "tex-svg.js").read_text(encoding="utf-8")
    conf = ("window.MathJax = {startup: {typeset: false}, svg: {fontCache: 'local'}, "
            "options: {enableMenu: false}};")
    return ("<script>%s</script>\n<script>%s</script>"
            % (conf, lib.replace("</script", "<\\/script")))


# ---------------------------------------------------------------- the pages

def _json(obj):
    """JSON for a <script type="application/json">: nothing in it can close
    the element it sits in."""
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")


def _fill(name, mapping):
    tpl = (TEMPLATES / name).read_text(encoding="utf-8")
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: mapping.get(m.group(1), m.group(0)), tpl)


def _text_of(fragment):
    """The characters a piece of HTML shows (and holds in its attributes: an
    alt, a title), for the faces to be cut to."""
    s = re.sub(r"<[^>]*?(?:alt|title|aria-label)=\"([^\"]*)\"[^>]*>", r" \1 ", fragment)
    return html.unescape(re.sub(r"<[^>]+>", " ", s))


def _has_math(fragment):
    return 'class="math' in fragment


def _glosses_html(items, L):
    """The document's glosses as one table (the studio's ⇄ Glosses, read
    only: the words, their reading where the language has one, their
    transliteration and their translation, in the order the text has them),
    with a filter box the page's script works."""
    if not items:
        return ""
    head = ("<th>%s</th>%s<th>%s</th><th>Translation</th>"
            % (html.escape(L.name), "<th>%s</th>" % html.escape(L.reading_label or "Reading")
               if L.reading else "", html.escape((L.translit_label or "transliteration").capitalize())))
    rows = []
    for g in items:
        rows.append(
            '<tr><td class="gl-fa" lang="%s" dir="%s">%s</td>%s<td class="gl-tr">%s</td>'
            '<td class="gl-tx">%s</td></tr>'
            % (L.code, L.dir, html.escape(g["fa"]),
               '<td class="gl-kana" lang="%s">%s</td>' % (L.code, html.escape(g.get("kana") or "—"))
               if L.reading else "",
               html.escape(g.get("translit") or "—"), html.escape(g.get("tr") or "")))
    return ('<details class="xp-panel xp-glosses"><summary>Glosses <span class="xp-count">%d</span>'
            '</summary><input class="gl-filter xp-gl-filter" type="search" '
            'placeholder="Filter the glosses" aria-label="Filter the glosses" autocomplete="off" '
            'spellcheck="false"><div class="gl-body"><table class="gl-table%s"><thead><tr>%s</tr>'
            '</thead><tbody>%s</tbody></table></div></details>'
            % (len(items), " dir-rtl" if L.dir == "rtl" else "", head, "".join(rows)))


def _contents_html(toc):
    """The document's contents, when it has sections, as a panel that opens
    and shuts (its links jump within the page)."""
    if not toc or toc.count("<a ") < 2:
        return ""
    return ('<details class="xp-panel xp-contents"><summary>Contents</summary>%s</details>'
            % toc)


# WHERE THE PAGE CAME FROM, said at its foot (the owner's wish): Parseh, its
# page on GitHub and its guide.  Links, followed only when clicked, and each
# into a tab of its own: this page keeps nothing, so leaving it would lose
# every answer given on it.
GITHUB = project.GITHUB_URL
GUIDE = project.GUIDE_URL


def _footer():
    link = '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
    return ('<footer class="xp-foot"><p>This page was exported from Parseh. %s · %s</p></footer>'
            % (link % (GITHUB, "Parseh on GitHub"), link % (GUIDE, "Parseh’s guide")))


def document_html(doc_id, meta, markdown, media):
    """One document as one HTML file: (filename, bytes).  The module
    docstring says what is in it and what is not."""
    M = _Media(media)
    try:
        doc = htmlgen.render_document(markdown, colophon=False, asset_base=M.url,
                                      docs=None, deck_button=False, export=True)
        L = languages.get_or_default(doc["target"])
        article = clean(doc["html"], M)
        contents = _contents_html(doc["toc"])
        glosses = _glosses_html(htmlgen.glosses(markdown), L)
        title = meta.get("title") or doc.get("title") or doc_id
        math = _has_math(article)
        text = " ".join((title, _text_of(article), _text_of(contents), _text_of(glosses)))
        page = _fill("export_doc.html", {
            "CSP": CSP,
            "TITLE": html.escape(title),
            "LANG": html.escape(doc.get("lang") or "en"),
            "TARGET": L.code,
            "CSS": _css(text, L, math),
            "CONTENTS": contents,
            "GLOSSES": glosses,
            "ARTICLE": article,
            "FOOTER": _footer(),
            "LANG_JSON": _json(L.as_json()),
            "MEDIA_JSON": _json(M.store),
            "MATH": _math_scripts() if math else "",
            "SCRIPT": _script(math),
        })
    finally:
        M.close()
    slug = re.sub(r"-[0-9a-f]{6}$", "", doc_id) or _slug(title, "document")
    return slug + ".html", page.encode("utf-8")


def deck_html(deck, items, media, render):
    """Chosen exercises of a deck as one HTML file that crams them:
    (filename, bytes).

    `items` are the exercises in the order they were chosen; `render(item,
    asset_base, preview)` is the deck's own renderer (decks.render_item),
    run twice for each: the exercise as it is answered, and solved -- the
    correct answer the cram page shows beside a wrong one, and under an
    exercise of the end's lists.  What travels of each is its kind, its
    excerpt and those two renders; its Markdown, its footnotes, its tags and
    its schedule do not."""
    if not items:
        raise ExportError("choose the exercises to export first")
    M = _Media(media)
    try:
        L = languages.get_or_default(deck.get("lang"))
        cards = []
        text = [deck.get("name") or ""]
        for n, it in enumerate(items):
            html_q = clean(render(it, M.url, False), M)
            html_a = clean(render(it, M.url, True), M)
            text += [it.get("excerpt") or "", it.get("label") or "",
                     _text_of(html_q), _text_of(html_a)]
            cards.append({"item": {"id": "x%d" % n, "label": it.get("label") or "",
                                   "subtype": it.get("subtype") or "",
                                   "excerpt": it.get("excerpt") or ""},
                          "html": html_q, "solution": html_a})
        math = any(_has_math(c["html"]) or _has_math(c["solution"]) for c in cards)
        title = deck.get("name") or "Exercises"
        page = _fill("export_deck.html", {
            "CSP": CSP,
            "TITLE": html.escape(title),
            "TARGET": L.code,
            "CSS": _css(" ".join(text), L, math),
            "FOOTER": _footer(),
            "LANG_JSON": _json(L.as_json()),
            "CARDS_JSON": _json(cards),
            "MEDIA_JSON": _json(M.store),
            "MATH": _math_scripts() if math else "",
            "SCRIPT": _script(math),
        })
    finally:
        M.close()
    return (deck.get("slug") or _slug(title, "exercises")) + ".html", page.encode("utf-8")


def disposition(name):
    """The Content-Disposition of a download called `name`: an ASCII name
    every browser takes, and the name itself (RFC 6266) for those that read
    it -- a deck named in Persian keeps its name."""
    import urllib.parse
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "export.html"
    if not ascii_name.lower().endswith(".html"):
        ascii_name += ".html"
    return ("attachment; filename=\"%s\"; filename*=UTF-8''%s"
            % (ascii_name, urllib.parse.quote(name, safe="")))
