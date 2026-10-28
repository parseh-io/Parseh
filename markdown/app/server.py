#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""exlex studio — local web UI for the exlex toolchain.

    python3 app/server.py [--port 8766] [--open]     # on its own, plain http

Normally it is not run like this at all: the studio is one of the doors of
Parseh, and ../../serve.py serves it at https://…/studio/ together with the
book reader, the video player and the exercise decks (deckroutes.py, at
/exercises/).  The route table, the page functions and the API below are
what that server drives; this file's own main() remains for running the
studio alone, and mounts the exercise decks at the same /exercises/.

Zero third-party dependencies for the web app itself (stdlib http.server);
the PDF build reuses the exlex modules (XeLaTeX + PyMuPDF verification).
Binds to 127.0.0.1 only — this is a personal, local tool.
"""
import argparse
import contextlib
import io
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXLEX = ROOT / "exlex"
# the toolbox's lib/ (the language registry, its fonts) sits two levels
# up; put on the path the way app/ and exlex/ are, so the studio runs on
# its own as well as under ../../serve.py
PARSEH = ROOT.parent
LIB = PARSEH / "lib"
LIB_FONTS = LIB / "fonts"
YT_LIB = PARSEH / "youtube" / "lib"
ANKI_DIR = PARSEH / "youtube" / "anki"
for p in (str(HERE), str(EXLEX), str(LIB), str(YT_LIB)):
    if p not in sys.path:
        sys.path.insert(0, p)

import activity       # noqa: E402  the Working… list a long download reports on
import audiofile      # noqa: E402
import htmlgen        # noqa: E402
import notes          # noqa: E402
import store          # noqa: E402
import envsetup       # noqa: E402
import mdparser       # noqa: E402
import texgen         # noqa: E402
import languages      # noqa: E402
import promptkit      # noqa: E402  the three parts every prompt is made of
import promptboxes    # noqa: E402  the studio's prompts in parts a person chooses
import prompts        # noqa: E402  the prompts a person wrote (lib/prompts.py)
import anki_store     # noqa: E402
import decks          # noqa: E402  the exercise decks (serve.py's hub reads it)
import deckroutes     # noqa: E402  and their routes, mounted at /exercises
import webexport      # noqa: E402  a document as one HTML page for a website (§8.38)
import texzip         # noqa: E402  a document's LaTeX with what it needs to compile elsewhere
import version        # noqa: E402  which Parseh this is, for the Server header
import crosssite      # noqa: E402  only Parseh's own pages may write (TO-DO §3.1)
import latexdraw      # noqa: E402  a latex block, compiled on its own and kept (§8.39)
import latexbatch     # noqa: E402  the drawings of many documents, made in the background without opening them (a0.5.6)
import latexrename    # noqa: E402  a theme renamed, every block put right (§8.39)
import network        # noqa: E402  who is knocking: only this computer opens its own files
import openfile       # noqa: E402  a file from anywhere on the computer, open in the studio (a0.5.2)
import getarasaac     # noqa: E402  the ARASAAC pictograms, optional and local (lib/getarasaac.py)
import arasaacsearch  # noqa: E402  a word looked for among them, for the picker (a0.5.3)
# NOTE: `verify` (and its pymupdf dependency) is imported lazily inside
# build_pdf, so the whole UI still starts when pymupdf is absent — only
# PDF verification, not the library/editor/preview, needs it.

STATIC = HERE / "static"
TEMPLATES = HERE / "templates"
MAX_BODY = 32 * 1024 * 1024   # 32 MB request-body cap

# Where the studio is mounted.  Run on its own (python3 app/server.py) it is
# the whole site and BASE is "".  Inside Parseh -- the toolbox's one server,
# ../../serve.py -- it lives under /studio, and every absolute URL a page or
# the script writes carries that prefix: the templates through {{BASE}}, the
# script through data-base on <body>, htmlgen's document links through its
# URL_BASE.  The route patterns below never see the prefix: the host strips
# it before matching.
BASE = ""

# Where the exercise decks are served, in Parseh and on their own alike: a
# document page's "+ Deck" button copies an exercise through this address.
DECKS_BASE = deckroutes.BASE

# WHICH MOUNT THIS REQUEST IS.
#
# The studio is one site under one prefix, and `BASE` is that prefix.  It now
# also serves a second kind of document: the notes that sit beside a book or a
# video, in that content's own `markdown/` directory.  They are studio
# documents in every respect -- the same store, the same editor, the same
# renderer -- so they are served by these very routes, with three things
# different: which library they are in (store.use_library), which prefix their
# links carry, and the fact that a note is never built.
#
# Held per THREAD, like store's library and texgen's DOC_INDEX, and for the
# same reason: the server is a ThreadingHTTPServer and two requests about two
# different books must not read each other's mount.  A thread that sets none
# gets the studio's own, so the studio, the command line and every test go on
# as before.
_MOUNT = threading.local()


# A LATEX BLOCK IS DRAWN BY lib/latexdraw.py (TO-DO §8.39).  The studio alone
# has no Settings, so a block that cannot be drawn names no page to mend it
# in; serve.py hands in its own Settings page's address.
htmlgen.set_latex(latexdraw.draw, latexdraw.draw_all, settings=None, peek=latexdraw.peek)
texgen.set_latex(latexdraw.draw)


def set_base(base):
    global BASE
    BASE = (base or "").rstrip("/")
    htmlgen.URL_BASE = BASE
    # the deck pages load the studio's stylesheet and script from here
    deckroutes.set_studio_base(BASE)


def base():
    """The prefix this thread's URLs carry."""
    b = getattr(_MOUNT, "base", None)
    return BASE if b is None else b


def html_only():
    """Whether this thread is serving documents that are never built: a note
    beside a book or a video is read on the page and nowhere else, so the PDF,
    the .tex and the build are refused rather than merely hidden."""
    return bool(getattr(_MOUNT, "html_only", False))


def current_session():
    """The file from the computer this thread is serving (openfile.Session), or
    None: the studio's own library, or the notes beside a book or a video."""
    return getattr(_MOUNT, "session", None)


def use_mount(base=None, html_only=False, session=None):
    """Point this thread at another mount for the rest of the request, and
    give back what it was so a caller can put it back.

    htmlgen's too: a `[…](doc:Name)` link between two notes is written by
    htmlgen from a prefix of its own, and a link that kept the studio's would
    walk out of the mount it was written in and land on a document that is
    not there.

    `session` is a file opened from the computer (open_scope): the pages then
    know it, to say so and to write to the file when asked."""
    was = (getattr(_MOUNT, "base", None), getattr(_MOUNT, "html_only", False),
           htmlgen.set_url_base(None if base is None else (base or "").rstrip("/")),
           getattr(_MOUNT, "session", None))
    _MOUNT.base = None if base is None else (base or "").rstrip("/")
    _MOUNT.html_only = bool(html_only)
    _MOUNT.session = session
    return was


def restore_mount(was):
    _MOUNT.base, _MOUNT.html_only = was[0], was[1]
    _MOUNT.session = was[3] if len(was) > 3 else None
    htmlgen.set_url_base(was[2])


class NotHere(Exception):
    """A route that this mount does not offer."""


def _has_pymupdf():
    try:
        import pymupdf  # noqa: F401
        return True
    except ImportError:
        return False


STATE = {
    "hyphenation": None,      # None = still checking, True/False afterwards
    "xelatex": shutil.which("xelatex") is not None,
    "pymupdf": _has_pymupdf(),
    "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
}
BUILD_LOCKS = {}
BUILD_LOCKS_GUARD = threading.Lock()
SERVER = {"instance": None}


# ----------------------------------------------------------------------
# startup provisioning
# ----------------------------------------------------------------------

# (file, how): None = copy from exlex/assets/fonts, then from lib/fonts;
# "kpsewhich" = ask TeX for it.  The prose faces are the studio's own and
# are named here; the TARGET-LANGUAGE faces are not, because the registry
# already says which ones travel with the toolbox -- every `web_files`
# entry of every language, gathered below.  A language that bundles a face
# and is not listed here would render in the reader and fall back to a
# system font in the studio, on the same screen, and nothing would say so.
# Japanese uses the system's CJK fonts through the CSS stacks and bundles
# nothing, so it contributes nothing and needs no exception.
WEB_FONTS = [
    ("Vazirmatn-Regular.ttf", None),
    ("Vazirmatn-Bold.ttf", None),
    ("texgyrepagella-regular.otf", "kpsewhich"),
    ("texgyrepagella-bold.otf", "kpsewhich"),
    ("texgyrepagella-italic.otf", "kpsewhich"),
    ("texgyrepagella-bolditalic.otf", "kpsewhich"),
    ("texgyreheros-regular.otf", "kpsewhich"),
    ("texgyreheros-bold.otf", "kpsewhich"),
    ("texgyreheros-italic.otf", "kpsewhich"),
    # the face that sets the NAME Parseh in the studio's bar (app.css, mobile.css), as
    # in every other bar of Parseh and on the website: no document is set in it
    ("texgyrechorus-mediumitalic.otf", None),
] + [(f, None) for f in dict.fromkeys(
    w for L in languages.LANGS.values() for w in (L.fonts.get("web_files") or []))]


def ensure_web_fonts():
    """Put every face the sheet names into static/fonts/, once.

    THE SHIPPED COPY FIRST, whatever `how` says.  TeX Gyre Pagella and Heros
    travel with the toolbox now (lib/fonts, under the GUST licence beside
    them), so the studio is set in the faces it was designed for on a
    machine with no TeX at all; asking TeX is what is left for a checkout
    that has not got them."""
    fdir = STATIC / "fonts"
    fdir.mkdir(parents=True, exist_ok=True)
    for name, how in WEB_FONTS:
        dst = fdir / name
        if dst.exists():
            continue
        shipped = [src for src in (EXLEX / "assets" / "fonts" / name, LIB_FONTS / name)
                   if src.exists()]
        if shipped:
            shutil.copy(shipped[0], dst)
        elif how is not None and shutil.which(how) is not None:
            r = subprocess.run([how, name],
                               capture_output=True, text=True)
            p = r.stdout.strip()
            if p and Path(p).exists():
                shutil.copy(p, dst)
        # else: no TeX here -- build_pdf() says so when it matters


def ensure_build_env_async():
    """Fonts + Italian hyphenation, off the request path."""
    # Every step here is best-effort and deliberately silent: the studio
    # must start on a machine with no network and browse existing
    # documents.  Nothing is lost by failing quietly — build_pdf() refuses
    # the build with a "fonts not provisioned" message, Nastaliq falls
    # back to Vazirmatn, and STATE["hyphenation"] records the outcome.
    def work():
        try:
            envsetup.ensure_fonts(verbose=False)
        except Exception:
            pass
        try:
            # Nastaliq (optional styling): assets TTF for the PDF plus a
            # woff2 for the web -- lib/fonts carries both; the derivation
            # is for a checkout that lost the woff2
            if envsetup.ensure_nastaliq(verbose=False):
                src = EXLEX / "assets" / "fonts" / envsetup.NASTALIQ_TTF
                w2 = STATIC / "fonts" / "NotoNastaliqUrdu.woff2"
                if src.exists() and not w2.exists():
                    from fontTools.ttLib import TTFont
                    ft = TTFont(str(src))
                    ft.flavor = "woff2"
                    ft.save(str(w2))
        except Exception:
            pass
        try:
            STATE["hyphenation"] = envsetup.ensure_italian_hyphenation(
                verbose=False)
        except Exception:
            STATE["hyphenation"] = False
    threading.Thread(target=work, daemon=True).start()


# The example documents are whatever is in exlex/examples/ -- every one of
# them, with no name known here.  Each is copied into a new library once,
# remembered by a .seeded-<name> marker, and only when nothing there already
# carries its title: a library that never had it, or that lost it.  A
# directory and not a list, so writing a new example is dropping the file in
# with its `target:` in the front matter and nothing else -- not a line of
# code, and nothing the registry could hold, because an example is prose
# somebody wrote and a language is whole without one.
#
# There are none at present.  The four that shipped were written when the
# studio read Persian for Italians, and the shelf stays empty until the ones
# meant for the eleven languages are written.


def language_examples():
    """The examples to offer a new library, in a stable order."""
    d = EXLEX / "examples"
    if not d.is_dir():
        return []
    return sorted(d.glob("*.md"))


def migrate_library():
    """The studio's library brought up to names, once per process
    (store.migrate_once): legacy duplicate titles told apart and
    `[…](doc:<uid>)` links written as links by name.  Said on the console
    when it did anything; never a reason not to start.  And the decks set
    to follow every rename in it from now on."""
    # the decks' exercises link to the studio's documents too: they follow
    # a rename as the documents do (registered here, not at import, so no
    # test's library can ever rewrite the decks on this machine)
    store.follow_renames(decks.rename_doc_links)
    # THE CUSTOM PROMPT THE STUDIO KEPT AS A FILE until a0.4.2 goes into the
    # person's own prompts, once (lib/prompts.py): what is said here is the one
    # place a person who never opens Settings would hear of it
    try:
        if store.move_prompt():
            print("studio: your custom prompt (library/_prompt.md) is now one of your "
                  "prompts, \"%s\"; the file is gone from the library" % prompts.STUDIO_NAME)
    except Exception as e:           # noqa: BLE001 -- a start-up chore
        print("!! the studio's custom prompt could not be moved into your prompts: %s" % e)
    try:
        out = store.migrate_once()
    except Exception as e:           # noqa: BLE001 -- a start-up chore
        print("!! the library's links could not be brought up to names: %s" % e)
        return None
    if out and (out["renamed"] or out["links"]):
        print("studio: %d document%s renamed so that names are unique, %d link%s "
              "rewritten from uid to name" % (
                  len(out["renamed"]), "" if len(out["renamed"]) == 1 else "s",
                  sum(out["links"].values()), "" if sum(out["links"].values()) == 1 else "s"))
    return out


def seed_example():
    """First run: copy each example into the library, once each, unless a
    document by that title is on the shelf already."""
    store.LIB.mkdir(parents=True, exist_ok=True)
    titles = {m.get("title", "") for m in store.list_docs()}
    for src in language_examples():
        mk = store.LIB / (".seeded-" + src.stem)
        if mk.exists():
            continue
        text = src.read_text(encoding="utf-8")
        fm, _ = mdparser.parse(text)
        if fm.get("title") not in titles:
            # in English, like the starters and for the same reason: the tag
            # is the studio talking, not the document, and the studio talks
            # to whoever opens it rather than to the first language it read
            store.create(text, tags=["example"])
        mk.write_text(time.strftime("%Y-%m-%dT%H:%M:%S"))


# ----------------------------------------------------------------------
# PDF build (reuses the exlex modules directly)
# ----------------------------------------------------------------------

def _doc_lock(doc_id):
    with BUILD_LOCKS_GUARD:
        return BUILD_LOCKS.setdefault(doc_id, threading.Lock())


def build_pdf(doc_id, scale, size=texgen.DEFAULT_PRINT_SIZE, mono=False):
    """Build the document's PDF at target-script `scale`, print `size`
    (texgen.PRINT_SIZES) and, with `mono`, in black and white -- the same
    .tex `exlex.py build --scale --size --mono` writes."""
    snap = store.snapshot_hash(doc_id)
    meta, markdown = store.get(doc_id)
    outdir = store.doc_dir(doc_id) / "build"
    outdir.mkdir(parents=True, exist_ok=True)

    # the bundled TTFs (Vazirmatn, Noto Naskh Arabic, Noto Nastaliq Urdu,
    # Noto Serif Devanagari) come from lib/fonts through envsetup; a build that starts before
    # the async provisioning finished copies them now, offline
    try:
        envsetup.copy_bundled_fonts(verbose=False)
    except Exception:
        pass
    fonts = EXLEX / "assets" / "fonts"
    if not fonts.is_dir():
        return {"status": "error",
                "error": "fonts not provisioned yet — run "
                         "`python3 exlex/exlex.py setup` or wait a moment "
                         "and retry."}
    # (a .part is a copy an older envsetup left half made in the folder)
    shutil.copytree(fonts, outdir / "fonts", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.part"))
    # the .tex references images/<name>; envsetup does it for both doors.
    # What an earlier build staged goes first: staging only ever added, so a
    # picture deleted since went on being printed from the build's own copy
    # while the page showed it missing.  The build folder is the studio's
    # own, and under this document's build lock.
    shutil.rmtree(outdir / "images", ignore_errors=True)
    try:
        envsetup.stage_images(store.images_dir(doc_id), outdir)
    except Exception as e:
        return {"status": "error",
                "error": "could not prepare an image for the PDF: %s" % e}

    fm, blocks = mdparser.parse(markdown)
    # the drawings first, side by side: generate() then finds each one kept
    pairs = htmlgen.latex_pairs(blocks, fm.get("target"))
    if pairs:
        latexdraw.draw_all(pairs)
    tex = texgen.generate(fm, blocks, fa_scale="%.2f" % scale,
                          docs=store.doc_index(), font_size=size, mono=mono)
    (outdir / "main.tex").write_text(tex, encoding="utf-8")
    # each drawing the .tex includes, beside it as latex/<key>.pdf; what an
    # earlier build staged goes first, as its pictures do
    drawings, drawn_failed = texgen.latex_used()
    shutil.rmtree(outdir / "latex", ignore_errors=True)
    if drawings:
        (outdir / "latex").mkdir(parents=True, exist_ok=True)
        for key, pdf in drawings:
            shutil.copy(pdf, outdir / "latex" / (key + ".pdf"))

    log = ""
    for _ in range(2):
        try:
            r = subprocess.run(
                ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                 "main.tex"],
                cwd=str(outdir), capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "xelatex timed out (300 s)"}
        except FileNotFoundError:
            return {"status": "error",
                    "error": "xelatex not found — install TeX Live"}
        log = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0:
            (outdir / "compile-error.log").write_text(log, encoding="utf-8")
            bad = [l for l in log.splitlines() if l.startswith("!")]
            return {"status": "error",
                    "error": "; ".join(bad[:4]) or "xelatex failed",
                    "log_tail": "\n".join(log.splitlines()[-40:])}

    pdf, texf = outdir / "main.pdf", outdir / "main.tex"
    build = {
        "status": "ok",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scale": round(scale, 2),
        # the print options, so the page can say what this PDF was built
        # with and that it no longer matches when they change
        "size": size,
        "mono": bool(mono),
        "stale": False,
        # the latex blocks that could not be drawn, each a framed note on the
        # paper where it would have stood (the owner, 2026-09-25)
        "latex_failed": drawn_failed,
    }
    # Verification (and page count) needs pymupdf; if it is unavailable the
    # PDF still built — report it as unverified rather than failing.
    try:
        import verify as verifier
        import pymupdf
        ok_n, failures = verifier.check(str(pdf), str(texf))
        over = verifier.scan_log(outdir / "main.log")
        with pymupdf.open(str(pdf)) as d:
            pages = d.page_count
        build.update({
            "pages": pages,
            "verify_ok": ok_n,
            "verify_failed": len(failures),
            "failures": [[s, kind] for s, kind in failures[:30]],
            "overfull": [round(x, 1) for x in over[:20]],
        })
    except ImportError:
        build.update({
            "verified": False,
            "note": "PDF built but not verified (PyMuPDF not installed).",
            "verify_ok": 0, "verify_failed": 0, "failures": [], "overfull": [],
        })
    return store.set_build(doc_id, build, snap=snap)["build"]


# ----------------------------------------------------------------------
# templating (deliberately tiny)
# ----------------------------------------------------------------------

def render_template(name, mapping):
    tpl = (TEMPLATES / name).read_text(encoding="utf-8")
    # THE MOBILE INTERFACE (docs/mobile.md, TO-DO §4.3).  The library and a
    # document carry both layouts, as the deck pages do: which is drawn is
    # decided in the head, before anything is painted, by the same snippet --
    # and the switch between them, and the tags that make the page part of
    # the app, are the deck routes' too, so there is one of each in the
    # toolbox rather than a copy per template.
    # {{BASE}} IS THIS MOUNT, {{STUDIO}} IS THE STUDIO.  They are the same
    # prefix on the studio's own pages and on the deck pages, and they part
    # company under a notes mount: a note's own links (its edit page, its
    # media, the deck it copies an exercise into) belong to the book it sits
    # beside, but the studio's FILES -- one stylesheet, one script, one
    # MathJax -- are the same bytes whichever book asked for them.  Written
    # under each book's own prefix they were a separate download, and a
    # separate cache entry, per book; written under the studio's they are
    # fetched once for the whole shelf.
    mapping = dict(mapping, BASE=base(), MODE_SCRIPT=deckroutes.MODE_SCRIPT,
                   MODE_SWITCH=deckroutes.MODE_SWITCH, APP_HEAD=deckroutes.APP_HEAD,
                   STUDIO=BASE)
    if current_session() is not None and name in ("doc.html", "edit.html"):
        tpl = _in_a_file(tpl, name, current_session())
    for k, v in mapping.items():
        tpl = tpl.replace("{{%s}}" % k, v)
    return tpl


def _in_a_file(tpl, name, sess):
    """A document page of a file opened from the computer (a0.5.2).  Three
    things differ from the library's, all of them here and none in the
    templates: the body says which session it is (static/openfile.js reads it
    to draw the file bar and to write to the file when the editor saves), the
    script and its sheet are loaded after the page's own, and the way back to
    the library goes to the studio's library -- this mount's root is the one
    document."""
    tpl = tpl.replace("<body ", '<body data-open-sid="%s" data-open-kind="%s" ' % (sess.sid, sess.kind), 1)
    if name == "doc.html":
        tpl = tpl.replace('href="{{BASE}}/"', 'href="{{STUDIO}}/"')
    foot = ('<link rel="stylesheet" href="{{STUDIO}}/static/openfile.css">\n'
            '<script src="{{STUDIO}}/static/openfile.js"></script>\n')
    return tpl.replace("</body>", foot + "</body>", 1)


def json_for_script(obj):
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")


def _lang_mapping(code):
    """The per-language template values: the target code, its name, its
    record (what the page's script reads) and the registry list (the
    library's chips and badges, the prompt page's select)."""
    L = languages.get_or_default(code)
    return {
        "TARGET": L.code,
        "TARGET_NAME": htmlgen.esc(L.name),
        "TARGET_DIR": L.dir,
        "LANG_JSON": json_for_script(L.as_json()),
        "LANGS_JSON": json_for_script(languages.chips()),
    }


def byte_range(header, size):
    """One `Range: bytes=a-b | a- | -n` against a file of `size` bytes ->
    (first, last) inclusive, or None when nothing of the file is in it (a
    416).  A header that is not a byte range raises ValueError (send_file
    then ignores it and answers the whole file), and so does a number too
    long for int() to read.  Of a list of ranges the
    first is answered, which is all a media element ever asks for:
    `bytes=0-` to begin with, `bytes=<n>-` for every seek.

    THE HUB'S RULE, TO THE LETTER.  serve.py's byte_range answers every
    header the same way (tests/test_studio_audio.py holds the two side by
    side), so a recording seeks alike in the studio run on its own and at
    /studio in the hub."""
    m = re.match(r"bytes=(\d*)-(\d*)", (header or "").strip())
    if not m:
        raise ValueError("not a byte range: %r" % header)
    first, last = m.group(1), m.group(2)
    if first == "":                           # bytes=-n: the last n
        first, last = max(0, size - int(last or 0)), size - 1
    else:
        first = int(first)
        last = int(last) if last else size - 1
    last = min(last, size - 1)
    if first > last or first >= size:
        return None
    return first, last


# ----------------------------------------------------------------------
# HTTP handler
# ----------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    # the studio is Parseh's, so it answers with Parseh's version -- heard
    # only when it runs on its own: inside Parseh, serve.py answers
    server_version = "exlex-studio/" + version.VERSION
    protocol_version = "HTTP/1.1"

    # ---- helpers ------------------------------------------------------

    def _body(self):
        # Read the request body at most once and cache it, so it is always
        # fully drained from the socket regardless of which branch handles
        # the request — an undrained body on a keep-alive connection would
        # be parsed as the start of the NEXT request (connection desync).
        if getattr(self, "_raw", None) is not None:
            return self._raw
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        n = max(0, min(n, MAX_BODY))
        self._raw = self.rfile.read(n) if n else b""
        return self._raw

    def _json_body(self):
        raw = self._body()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def send_bytes(self, data, ctype, code=200, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if getattr(self, "_head", False):
            return                       # HEAD: headers only, no body
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, obj, code=200):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8", code)

    def send_html(self, text, code=200):
        self.send_bytes(text.encode("utf-8"),
                        "text/html; charset=utf-8", code,
                        {"Cache-Control": "no-cache"})

    def send_file(self, path, download_name=None, inline_type=None):
        """A file, and of a file that is not a download, the one byte range
        a `Range:` header asks for (byte_range): a recording must answer
        those for a page to seek in it."""
        path = Path(path)
        if not path.is_file():
            return self.send_json({"error": "not found"}, 404)
        # audio types are fixed by audiofile, not left to the platform's
        # table, which disagrees with itself about .opus, .wav and .webm
        ctype = inline_type or audiofile.mime_for(path.name) \
            or mimetypes.guess_type(str(path))[0] \
            or "application/octet-stream"
        extra = {"Cache-Control": "no-cache"}
        if path.suffix in (".ttf", ".otf", ".woff2"):
            extra = {"Cache-Control": "max-age=86400"}
        if path.suffix in (".svg", ".pdf"):
            # an uploaded SVG can carry scripts, and so can a PDF: both are
            # inert where the page uses them (an <img>, and for a PDF the
            # rastered .pdf.png twin), but neutralise direct navigation to
            # the file as well
            if path.suffix == ".svg":
                ctype = "image/svg+xml"
            extra["Content-Security-Policy"] = \
                "default-src 'none'; style-src 'unsafe-inline'"
        if download_name:
            extra["Content-Disposition"] = (
                'attachment; filename="%s"' % download_name)
            return self.send_bytes(path.read_bytes(), ctype, 200, extra)
        size = path.stat().st_size
        extra["Accept-Ranges"] = "bytes"
        code, first, last = 200, 0, size - 1
        rng = self.headers.get("Range")
        try:
            # answered as the hub answers it (byte_range): a header that is
            # not a byte range is ignored (RFC 9110 14.2), the whole file
            span = byte_range(rng, size) if rng else False
        except ValueError:
            span = False
        if span is None:
            extra["Content-Range"] = "bytes */%d" % size
            return self.send_bytes(b"", ctype, 416, extra)
        if span:
            code, (first, last) = 206, span
            extra["Content-Range"] = "bytes %d-%d/%d" % (first, last, size)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(max(0, last - first + 1)))
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()
        if getattr(self, "_head", False):
            return
        # read and written a piece at a time: a 30 MB recording is not held
        # in memory once per listener
        left = last - first + 1
        try:
            with open(path, "rb") as f:
                f.seek(first)
                while left > 0:
                    chunk = f.read(min(left, 256 * 1024))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except OSError:
            pass            # the listener left, or the file went away
        if left > 0:
            # the length promised was not kept: the connection must not be
            # reused, or its next request would be read out of this answer
            self.close_connection = True

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n"
                         % (time.strftime("%H:%M:%S"), fmt % args))

    # ---- routing ------------------------------------------------------

    def handle(self):
        """A browser that goes away between two requests of a connection it kept
        open is weather, not a fault.  socketserver prints a full traceback
        for the reset that comes out of the next read, and a studio run on its
        own (this server, not serve.py's, which says the same of its own
        clients in handle_error) printed one each time a page was closed.  A
        real bug in a route is still caught and shown by _routes."""
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True

    def _dispatch(self, method):
        self._raw = None
        # ONLY PARSEH'S OWN PAGES MAY WRITE (lib/crosssite.py): run on its
        # own, the studio is a server on this computer as the hub is, and a
        # page on another site open in the same browser could save over a
        # document or delete one.  Asked before the body is read, which is
        # then left unread: the connection is not used again.  Inside Parseh
        # serve.py asks the same before it hands a request to the routes.
        if method not in crosssite.SAFE:
            crossed = crosssite.refusal(self.headers)
            if crossed:
                self.close_connection = True
                return self.send_json({"ok": False, "error": crossed}, 403)
        # Chunked bodies have no Content-Length, so _body() cannot drain
        # them; rather than desync the connection, refuse them outright.
        te = (self.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" in te:
            self.close_connection = True
            return self.send_json(
                {"error": "chunked Transfer-Encoding not supported"}, 411)
        # A body larger than the cap cannot be drained (reading part of it
        # would desync the connection): refuse it and close.
        try:
            declared = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            declared = 0
        if declared > MAX_BODY:
            self.close_connection = True
            return self.send_json({"error": "request body too large"}, 413)
        # Always consume the body up front, so it is drained even when the
        # route is unmatched or the handler raises before reading it.
        self._body()

        parsed = urllib.parse.urlsplit(self.path)
        self.query = urllib.parse.parse_qs(parsed.query)
        path = parsed.path
        # the exercise decks sit beside the studio at the same address they
        # have inside Parseh; their routes answer for themselves
        if path == deckroutes.BASE:
            return self.send_bytes(b"", "text/plain; charset=utf-8", 302,
                                   {"Location": deckroutes.BASE + "/"})
        if path.startswith(deckroutes.BASE + "/"):
            return deckroutes.dispatch(self, method, path[len(deckroutes.BASE):])
        # a file from the computer, open in the studio: the very same routes,
        # on its working copy (serve_open)
        opened = re.match(r"^/open/([0-9a-f]{12})(/.*)?$", path)
        if opened:
            return serve_open(self, method, opened.group(1), opened.group(2), self._routes)
        return self._routes(method, path)

    def _routes(self, method, path):
        """The route table, for a path with the mount's prefix already taken
        off it."""
        for m, pattern, fn in ROUTES:
            if m != method:
                continue
            match = re.match(pattern, path)
            if match:
                try:
                    return fn(self, *match.groups())
                except KeyError:
                    if fn in PAGES:
                        return self.send_html(render_template("404.html", {}), 404)
                    return self.send_json({"error": "document not found"}, 404)
                except json.JSONDecodeError:
                    return self.send_json({"error": "bad JSON body"}, 400)
                except store.StoreError as e:
                    return self.send_json({"error": str(e)}, 400)
                except Exception as e:  # surface, don't crash the thread
                    import traceback
                    traceback.print_exc()
                    return self.send_json({"error": str(e)}, 500)
        if method == "GET":
            return self.send_html(render_template("404.html", {}), 404)
        return self.send_json({"error": "no such endpoint"}, 404)

    def do_GET(self):
        self._head = False
        self._dispatch("GET")

    def do_HEAD(self):
        self._head = True
        self._dispatch("GET")

    def do_POST(self):
        self._head = False
        self._dispatch("POST")

    def do_PUT(self):
        self._head = False
        self._dispatch("PUT")

    def do_PATCH(self):
        self._head = False
        self._dispatch("PATCH")

    def do_DELETE(self):
        self._head = False
        self._dispatch("DELETE")


# ----------------------------------------------------------------------
# pages
# ----------------------------------------------------------------------

def page_index(h):
    # the chip row is rendered here, with the counts, as every index page
    # of the toolbox does; app.js wires it (parseh.js is not loaded here)
    m = _lang_mapping(None)
    m["LANG_CHIPS"] = languages.chips_html(store.lang_counts())
    h.send_html(render_template("index.html", m))


def api_doc_offline(h, doc_id):
    """What this document is made of, as addresses (lib/offline.py, §19.8).

    The studio renders a document on the server, so keeping one means keeping
    the rendered PAGE -- nothing on a phone could render it -- with the
    pictures it shows, its recordings to pick, and the studio's own sheets
    and scripts.

    TWO BASES, exactly as render_template hands the page {{BASE}} and
    {{STUDIO}}.  The document itself belongs to THIS mount -- under a notes
    mount that is the book or the video it sits beside -- but the studio's
    FILES are the same bytes whichever book asked for them, and they answer
    at the studio's own prefix.  Named under each book's prefix instead, a
    phone keeping a note from the second book would download the sheet, the
    script and MathJax all over again, which is the one thing the owner's
    decision 3 forbids: the studio's scripts are paid once for the phone."""
    import offline
    rec = offline.document(store, doc_id, base(), BASE)
    if rec is None:
        return h.send_json({"ok": False, "error": "no such document"}, 404)
    rec["ok"] = True
    rec["shared"] = offline.shared()
    rec.update(offline.totals(rec))
    h.send_json(rec)


def page_prompt(h):
    h.send_html(render_template("prompt.html", _lang_mapping(None)))


def _edit_mapping(code, source=""):
    """The editor's template values: the language's, the recordings its
    Audio button takes, as lib/audiofile.py lists them (the picker's accept,
    the formats its title and a refused drop name), and where the exercise
    decks answer -- the editor loads an exercise out of one, as a document
    page copies one into one (DECKS_BASE, page_doc)."""
    m = _lang_mapping(code)
    decks_here = not html_only() or bool(source)
    m.update({"AUDIO_ACCEPT": htmlgen.esc(audiofile.ACCEPT),
              "AUDIO_HUMAN": htmlgen.esc(audiofile.HUMAN),
              "DECKS_BASE": DECKS_BASE if decks_here else "",
              "NOTES_SOURCE": htmlgen.esc(source)})
    return m


def prose_record(code):
    """The prose language (the front matter's `lang:`) as the editor needs
    it: the gloss record, whose `dir` is the way the source is written by
    default -- a Persian writing to teach English writes right to left --
    and whose `taught` says the registry has a face for it.  A code this
    toolbox cannot set is English, as everywhere a gloss is read."""
    return languages.gloss_or_default(code).as_json()


def _prose_mapping(markdown):
    fm, _blocks = mdparser.parse(markdown)
    return {"PROSE_JSON": json_for_script(prose_record(fm.get("lang")))}


def page_new(h):
    """The editor on a starting document.

    `?target=<code>` says which language's starter to open with; the
    library's +New link carries the toolbox's shared language preference
    there, the way the add-a-video and prompt pages default their own
    selects.  A bare /new -- a typed URL, a bookmark, the link before the
    script has run -- gets the registry's first language, and the front
    matter is one line to change either way.
    """
    L = languages.get_or_default(_q1(h, "target") or None)
    m = _edit_mapping(L.code)
    markdown = new_template(L.code)
    m.update({
        "DOC_ID": "",
        "TITLE": "New %s document" % L.name,
        "MARKDOWN": htmlgen.esc(markdown),
        "NAMES_MARK": htmlgen.esc(store.names_mark()),
    })
    m.update(_prose_mapping(markdown))
    h.send_html(render_template("edit.html", m))


def backlinks_html(doc_id):
    """The "Linked from" drawer's list (store.backlinks), as HTML: each
    document that links here, its title a link to it -- under this mount's
    prefix, so a note's drawer stays among the notes -- and the words around
    each of its links, the link's own shown text marked.  All plain text,
    escaped, each line in its own direction (a Persian note's context is
    right to left, the English around it not)."""
    found = store.backlinks(doc_id)
    if not found:
        return 0, '<p class="links-empty">No document links here yet.</p>'
    esc = htmlgen.esc
    rows = []
    for e in found:
        snips = "".join(
            '<p class="link-snippet" dir="auto">%s<mark>%s</mark>%s</p>'
            % (esc(s["before"]), esc(s["link"]), esc(s["after"])) for s in e["snippets"])
        rows.append('<li class="link-from"><a class="link-doc" dir="auto" href="%s/doc/%s">%s</a>%s</li>'
                    % (base(), esc(e["id"]), esc(e["title"]), snips))
    return len(found), ('<ul class="links-list" aria-label="Documents that link here">%s</ul>'
                        % "".join(rows))


def page_doc(h, doc_id):
    meta, markdown = store.get(doc_id)
    live = getattr(h, "query", {}).get("live", [""])[0] == "1"
    linked_n, linked = backlinks_html(doc_id)
    # A note beside a book or a video offers "+ Deck" as a studio document
    # does, when the deck routes know which notes its prefix stands for
    # (serve.py tells them; the studio run alone has no notes).  The page
    # then names that prefix, and the copy reads the document from there.
    # A mount they do not know gets no button and no deck address.
    source = _notes_source()
    decks_here = not html_only() or bool(source)
    doc = htmlgen.render_document(markdown,
                                  asset_base=base() + "/media/%s/" % doc_id,
                                  docs=store.doc_index(),
                                  deck_button=decks_here, latex_defer=True)
    m = _lang_mapping(doc["target"])
    m.update({
        "DECKS_BASE": DECKS_BASE if decks_here else "",
        "NOTES_SOURCE": htmlgen.esc(source),
        "DOC_ID": doc_id,
        "TITLE": htmlgen.esc(meta.get("title") or doc_id),
        "LANG": htmlgen.esc(doc["lang"] or "en"),
        "ARTICLE": doc["html"],
        "TOC": doc["toc"],
        "BACKLINKS": linked,
        "BACKLINKS_N": str(linked_n),
        "META_JSON": json_for_script(meta),
        "GLOSSES_JSON": json_for_script(htmlgen.glosses(markdown)),
        # ?live=1: this page is the preview of an editor open in another tab
        # (static/live.js); the page is the same one, drawn from the editor's
        # text as it is typed
        "LIVE": "1" if live else "",
        "LIVE_SCRIPT": ('<script src="%s/static/live.js"></script>' % BASE) if live else "",
    })
    h.send_html(render_template("doc.html", m))


# The scale a target script is set at when nobody has said otherwise; the
# same three numbers app.js's defaultScale gives, written here because the
# bare note page has no app.js to ask.
_FA_SCALE = {"latin": "1.0", "arabic": "1.52"}


def page_note(h, doc_id):
    """A NOTE, AND NOTHING ELSE: the rendered document on the studio's sheet,
    with no editor and none of the studio's scripts (templates/note.html).

    The document page is what a note used to open as, and it costs about
    1.3 MB every time -- app.css, app.js, the exercise forms, the mode
    switch, the keeping and explaining scripts, the activity poll -- for a
    page that is read a dozen times in a session and written on almost
    never.  This is the same document, rendered by the same renderer, on the
    same sheet (static/sheet.css, which both pages link), and "open in the
    studio" in its header is one click from the whole of it.

    AN EXERCISE SENDS THE READER TO THE FULL PAGE INSTEAD.  Without the
    studio's script an exercise is a box that cannot be answered, checked or
    copied: nothing inert is ever shown, so a note that holds one is
    redirected to the document page, which is what it always was.  The
    question is asked of the RENDER (htmlgen's `exercises`) rather than of
    the markdown, because only the render knows what a block became -- a
    malformed exercise block is still an exercise box on the page.
    """
    meta, markdown = store.get(doc_id)
    doc = htmlgen.render_document(markdown,
                                  asset_base=base() + "/media/%s/" % doc_id,
                                  docs=store.doc_index(),
                                  deck_button=False, latex_defer=True)
    if doc["exercises"]:
        return h.send_bytes(b"", "text/plain; charset=utf-8", 302,
                            {"Location": "%s/doc/%s" % (base(), doc_id)})
    L = languages.get_or_default(doc["target"])
    # MathJax only where there is maths.  Every renderer writes a formula as
    # <span class="math" …> holding its own TeX, so a page that never draws
    # one still says what it was; lib/mathjax.js is a small loader and the
    # two megabytes behind it are fetched only once it finds something.
    #
    # BASE, NOT base(): the studio's own prefix, and not this note's mount.
    # The loader works out where the heavy library is from its own src, so
    # one linked under a book's prefix would go on to ask that book for
    # tex-svg.js -- two megabytes fetched, and kept on a phone, once per
    # book.  templates/doc.html names the same two addresses, so the bare
    # note page and the document page share one copy of each (TO-DO §0).
    maths = 'class="math' in doc["html"]
    m = {
        "DOC_ID": doc_id,
        "TITLE": htmlgen.esc(meta.get("title") or doc_id),
        "LANG": htmlgen.esc(doc["lang"] or "en"),
        "TARGET": L.code,
        "SCRIPT": htmlgen.esc(L.script or ""),
        "FA_SCALE": _FA_SCALE.get(L.script, "1.2"),
        "ARTICLE": doc["html"],
        "STUDIO_DOC": "%s/doc/%s" % (base(), doc_id),
        "MATH_HEAD": ('<link rel="stylesheet" href="%s/static/mathjax.css">'
                      % BASE) if maths else "",
        # typeset after the page is standing, and only then: this is the one
        # thing the sheet cannot draw by itself
        "MATH_FOOT": ('<script src="%s/static/mathjax.js"></script>\n'
                      '<script>window.ParsehMath && '
                      'ParsehMath.typeset(document.getElementById("sheet"));'
                      '</script>' % BASE) if maths else "",
        # the drawings it opened without, made afterwards -- written into the
        # page, as everything it runs is, and only when there are some
        "LATEX_FOOT": ("<script>%s</script>" % (STATIC / "latexwait.js").read_text(encoding="utf-8")
                       if doc.get("latex_pending") else ""),
    }
    h.send_html(render_template("note.html", m))


def page_edit(h, doc_id):
    # the renames the page has seen go with its text: its saves follow the
    # ones made after (store.save, `since`)
    meta, markdown, mark = store.edit_view(doc_id)
    # the notes beside a book or a video, as page_doc reads them: the decks
    # take an exercise from that shelf's documents and give one back to them
    source = _notes_source()
    m = _edit_mapping(meta.get("target"), source)
    m.update({
        "DOC_ID": doc_id,
        "TITLE": htmlgen.esc(meta.get("title") or doc_id),
        "MARKDOWN": htmlgen.esc(markdown),
        "NAMES_MARK": htmlgen.esc(mark),
    })
    m.update(_prose_mapping(markdown))
    h.send_html(render_template("edit.html", m))


def serve_langs_css(h):
    """The per-language CSS tokens, generated from the registry (the
    Parseh server serves the same text at /lib/langs.css)."""
    h.send_bytes(languages.css().encode("utf-8"),
                 "text/css; charset=utf-8", 200, {"Cache-Control": "no-cache"})


def serve_app_js(h):
    """The page script, with the toolbox's one case fold spliced into it
    (`languages.FOLD_JS`, exactly as tex2html.py splices it into the
    reader's).  The filters in the browser and the search in store.py are
    then the same function, and neither can drift from the other."""
    src = (STATIC / "app.js").read_text(encoding="utf-8")
    h.send_bytes(src.replace("__FOLD__", languages.FOLD_JS).encode("utf-8"),
                 "text/javascript; charset=utf-8", 200,
                 {"Cache-Control": "no-cache"})


def serve_llmrow_js(h):
    """The row of controls every page that hands out a prompt draws
    (lib/llmrow.js): copy, the size, the reminder.

    The studio's pages link it as /lib/llmrow.js, which is the toolbox's own
    when the studio is mounted in it.  Run on its own the studio has no /lib/
    at all -- the scripts it links there (explain.js, keep.js) are simply not
    found, and the pages do without them -- so this one file, which the
    prompt page cannot do without, is answered for here."""
    try:
        data = (LIB / "llmrow.js").read_bytes()
    except OSError:
        return h.send_json({"error": "not found"}, 404)
    h.send_bytes(data, "text/javascript; charset=utf-8", 200,
                 {"Cache-Control": "no-cache"})


def serve_gear_file(h, name):
    """The gear's two files (lib/pagesettings.js and its sheet): the panel every
    page of Parseh opens for its own settings, a0.5.0 -- and the page zoom
    (lib/pagezoom.js), which the same pages link first of all and whose
    Zoom group the panel draws.

    The studio's document, editor and exercise pages link them as
    /lib/pagesettings.js, which is the toolbox's own when the studio is mounted
    in it.  Run on its own the studio has no /lib/, and without these two its
    pages would have no way to set the text at all -- the sliders that stood
    in the document's toolbar are rows of that panel now -- so they are
    answered for here, as llmrow.js is."""
    ctype = "text/css" if name.endswith(".css") else "text/javascript"
    try:
        data = (LIB / name).read_bytes()
    except OSError:
        return h.send_json({"error": "not found"}, 404)
    h.send_bytes(data, ctype + "; charset=utf-8", 200, {"Cache-Control": "no-cache"})


def serve_picker_file(h, name):
    """The pictogram picker's two files (lib/pictograms.js and its sheet, a0.5.3): the frame the editor
    and the exercise form open to look for an ARASAAC pictogram.

    The studio's pages link the script as /lib/pictograms.js, which is the toolbox's own when the studio is
    mounted in it; run on its own the studio has no /lib/, and without these two the button of the editor
    and of the form would do nothing (the form hides its own when the script is not there).  The script
    links its sheet from beside itself, so the one route answers both."""
    ctype = "text/css" if name.endswith(".css") else "text/javascript"
    try:
        data = (LIB / name).read_bytes()
    except OSError:
        return h.send_json({"error": "not found"}, 404)
    h.send_bytes(data, ctype + "; charset=utf-8", 200, {"Cache-Control": "no-cache"})


def serve_prompt_options(h):
    """The choices a person makes for one prompt, which the row (lib/llmrow.js)
    draws beside the copy button: the scheme of the transliteration.  The
    toolbox answers this path itself (serve.py, with a book's or a video's own
    record as well); run on its own the studio answers it here, for
    ?surface=<studio-doc|studio-exercises>&lang=<code>."""
    surface, L = _q1(h, "surface"), languages.LANGS.get(_q1(h, "lang"))
    if surface not in promptkit.SURFACES:
        return h.send_json({"ok": False, "error": "%r is not a place a prompt is handed out from" % surface}, 400)
    if L is None:
        return h.send_json({"ok": False, "error": "%r is not a language of Parseh" % _q1(h, "lang")}, 400)
    h.send_json({"ok": True, "options": promptkit.describe(surface, L)})


def serve_app_css(h):
    """The studio's sheet, and the chrome around it, under the one name.

    static/sheet.css is the reading sheet on its own -- the faces, the
    palette, the LaTeX-styled view -- split out so that the bare note page
    can link it and nothing else (page_note).  static/app.css is the rest.

    They are put back together HERE, rather than by an @import at the head
    of app.css, so that /static/app.css goes on answering with exactly what
    it always answered with.  Everything that ever asked for that address
    keeps working untouched: the deck pages, a document kept on a phone (the
    worker caches the answer, and an answer that named a second file would
    have left that file uncached and the page blank), and every template
    that links it.  Two files to write in, one address to ask for.
    """
    sheet = (STATIC / "sheet.css").read_text(encoding="utf-8")
    chrome = (STATIC / "app.css").read_text(encoding="utf-8")
    h.send_bytes((sheet + "\n" + chrome).encode("utf-8"),
                 "text/css; charset=utf-8", 200, {"Cache-Control": "no-cache"})


def serve_static(h, rel):
    rel = urllib.parse.unquote(rel)
    path = (STATIC / rel).resolve()
    if not str(path).startswith(str(STATIC.resolve())):
        return h.send_json({"error": "forbidden"}, 403)
    h.send_file(path)


# MATHS, SERVED FROM lib/ AND NOT COPIED INTO static/.  The fonts are
# copied (ensure_web_fonts) because a build needs them on disk beside the
# TeX; MathJax is only ever read by a browser, and two megabytes duplicated
# into a second directory at every start is two megabytes for nothing.  The
# studio answers for them here so that it works the same whether it is
# mounted in the toolbox (where /lib/ is the hub's) or run on its own.
#
# AND THEY ARE THE ONE THING HERE WORTH CACHING.  Everything else these
# routes serve is somebody's work, which is why it goes out `no-cache` -- a
# reload must show the edit.  MathJax is two megabytes of checkout that
# change only when the checkout does, and it was being fetched afresh every
# time a note with a formula was opened, which on a phone over a tunnel is
# the whole wait.  serve.py grants the same day to /lib/mathjax/ for the
# rest of the toolbox; this is that same exemption, for the copies the
# studio (and every note beside a book) asks for under its own prefix.
MATH_CACHE = "max-age=86400"


def send_math(h, path, ctype):
    """One of the MathJax files, with the day's cache on it.

    Sent whole rather than through `send_file`, because the handler
    answering may not be this module's: the toolbox runs these very routes
    under its own prefixes (serve.py, _studio), and its `send_file` chooses
    the header itself and takes no say in it.  `send_bytes` is the one
    helper both handlers offer on the same terms, and nothing here is big
    enough or seekable enough to want the other.

    A file that is NOT there gets the ordinary 404, which is never kept: a
    404 held for a day would outlive the file's arrival.
    """
    try:
        data = Path(path).read_bytes()
    except OSError:
        return h.send_json({"error": "not found"}, 404)
    h.send_bytes(data, ctype, 200, {"Cache-Control": MATH_CACHE})


def serve_math_js(h, _m=None):
    send_math(h, LIB / "mathjax.js", "text/javascript; charset=utf-8")


def serve_math_css(h, _m=None):
    send_math(h, LIB / "mathjax.css", "text/css; charset=utf-8")


def serve_math_lib(h, rel):
    rel = urllib.parse.unquote(rel)
    path = (LIB / "mathjax" / rel).resolve()
    if not str(path).startswith(str((LIB / "mathjax").resolve())):
        return h.send_json({"error": "forbidden"}, 403)
    send_math(h, path, "text/javascript; charset=utf-8")


def serve_pdf(h, doc_id):
    if html_only():
        return h.send_json({"error": NEVER_BUILT}, 404)
    store.get(doc_id)  # 404 if unknown
    h.send_file(store.doc_dir(doc_id) / "build" / "main.pdf",
                inline_type="application/pdf")


NEVER_BUILT = ("a note beside a book or a video is read on its page and "
               "nowhere else: it is never built to a PDF and never taken "
               "away as LaTeX. Copy it into the studio if you want either.")


def serve_download(h, doc_id, kind):
    if kind in ("tex", "texzip", "pdf") and html_only():
        return h.send_json({"error": NEVER_BUILT}, 404)
    meta, _ = store.get(doc_id)
    slug = re.sub(r"-[0-9a-f]{6}$", "", doc_id) or "documento"
    if kind == "texzip":
        # the .tex of the last build with what it includes -- its pictures, its latex drawings as compiled PDFs AND as the
        # LaTeX they came from, its fonts -- so that it compiles in Overleaf or anywhere, and a drawing can be changed
        _meta, markdown = store.get(doc_id)
        try:
            data = texzip.tex_zip(doc_id, meta.get("title") or slug, markdown)
        except texzip.NotBuilt:
            return h.send_json({"error": "There is no LaTeX yet: build the PDF first, and the LaTeX it was built from comes away."}, 404)
        return h.send_bytes(data, "application/zip", 200,
                            {"Content-Disposition": 'attachment; filename="%s-latex.zip"' % slug})
    if kind == "zip":
        # the markdown and the pictures and recordings it shows, laid out as
        # they are kept here (<slug>.md beside images/ and audio/): what the
        # library's upload takes back
        return h.send_bytes(store.doc_zip(doc_id, slug), "application/zip", 200,
                            {"Content-Disposition": 'attachment; filename="%s.zip"' % slug})
    if kind == "html":
        # ONE PAGE FOR A WEBSITE (TO-DO §8.38): the document as it reads,
        # with its exercises working, its pictures and recordings inside it,
        # and nothing of its Markdown -- webexport says what goes in and why
        _meta, markdown = store.get(doc_id)
        name, data = webexport.document_html(doc_id, meta, markdown, _doc_file(doc_id))
        return h.send_bytes(data, "text/html; charset=utf-8", 200,
                            {"Content-Disposition": webexport.disposition(name),
                             "Cache-Control": "no-store"})
    d = store.doc_dir(doc_id)
    files = {
        "md": (d / "source.md", slug + ".md"),
        "tex": (d / "build" / "main.tex", slug + ".tex"),
        "pdf": (d / "build" / "main.pdf", slug + ".pdf"),
    }
    path, name = files[kind]
    h.send_file(path, download_name=name)


def _doc_file(doc_id):
    """The file on disk a document's Markdown names (`images/cat.png`,
    `audio/word.mp3`), or None -- what the HTML export carries into the page
    (webexport).  A PDF figure is shown through its SVG twin, built here when
    it is missing, as the media route builds it (serve_media)."""
    def find(path):
        kind, _, name = (path or "").partition("/")
        try:
            if kind == "images":
                p = store.image_path(doc_id, name)
                if not p.exists() and name.lower().endswith(".pdf.svg"):
                    store.ensure_pdf_twin(p.with_name(p.name[:-4]))
            elif kind == "audio":
                p = store.audio_path(doc_id, name)
            else:
                return None
        except (KeyError, ValueError, OSError):
            return None
        return p if p.is_file() else None
    return find


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------

def _q1(h, key, default=""):
    return h.query.get(key, [default])[0]


def api_list(h):
    tags = [t for t in _q1(h, "tags").split(",") if t]
    exclude_tags = [t for t in _q1(h, "exclude_tags").split(",") if t]
    docs = store.list_docs(
        q=_q1(h, "q"), tags=tags, exclude_tags=exclude_tags,
        intext=_q1(h, "intext") == "1",
        sort=_q1(h, "sort", "updated"))
    h.send_json({"docs": docs})


def _header_lists():
    """The two languages a header names, as its dialog offers them: the ones
    a note can be written in (the gloss languages) and the ones it can be
    about (the registry)."""
    return {"langs": [{"code": c, "name": languages.GLOSSES[c].name}
                      for c in languages.GLOSS_CODES],
            "targets": [{"code": L.code, "name": L.name} for L in languages.LANGS.values()]}


def _name_conflict(h, e):
    """store.NameConflict -> 409, with what the name-conflict dialog asks
    about: every clash and, on a second answer, what is wrong with the names
    it was given.  Nothing was written."""
    h.send_json(e.answer(), 409)


def _renames_query(h):
    """?renames= (the raw-body routes: a zip, a backup): the JSON the
    name-conflict dialog answered, or None when it is not JSON at all."""
    raw = _q1(h, "renames")
    if not raw:
        return {}
    try:
        got = json.loads(raw)
    except (ValueError, RecursionError):
        return None
    return got if isinstance(got, dict) else None


def api_create(h):
    """A new document from markdown.

    `header`: what an upload's dialog answered -- the header fields its file
    lacked, added to the file's header (store.fill_header).  `check_header`
    asks for that dialog: a file without the header a document is filed by,
    or short of some of it, is answered 422 with what is missing and what to
    offer, and nothing is made.  Without either, as it always was.

    A title another document of the library has is answered 409
    (store.NameConflict), nothing made, until `renames` -- the name-conflict
    dialog's answer -- settles it.  `name` is the uploaded file's."""
    body = h._json_body()
    text = body.get("markdown", "")
    if not text.strip():
        return h.send_json({"error": "empty document"}, 400)
    header = body.get("header")
    if isinstance(header, dict):
        text = store.fill_header(store.extract_markdown(text), header)
    elif body.get("check_header"):
        markdown = store.extract_markdown(text)
        state = store.header_state(markdown)
        if state["missing"]:
            return h.send_json(dict(
                state, **_header_lists(), ok=False, header_needed=True,
                defaults=store.header_defaults(markdown, str(body.get("name") or "")),
                error="the header is missing " + ", ".join(state["missing"])), 422)
    try:
        meta = store.create(text, tags=body.get("tags") or [], renames=body.get("renames"),
                            strict=True, file=str(body.get("name") or "") or None,
                            since=body.get("since"))
    except store.NameConflict as e:
        return _name_conflict(h, e)
    _adopt(meta["id"])
    try:
        _unused, markdown = store.get(meta["id"])
        latexdraw.own_source(_latex_owner(meta["id"]), markdown)
    except Exception as e:                                   # noqa: BLE001
        sys.stderr.write("[studio] could not record new LaTeX drawings: %s\n" % e)
    store.migrate_after_import([])         # its links by uid, written by name
    h.send_json({"meta": meta}, 201)


def api_import_zip(h):
    """Documents out of a zip: a document's Download ▾ "Markdown + media"
    or several documents at once (store.import_zip).  ?headers= is the JSON
    the upload's dialog answered: for each markdown file named, the header
    fields it lacked, or null to leave that file out.  A file whose header is
    incomplete and has no answer there gets the whole zip answered 422, every
    such file named with what it lacks, and nothing is made.  Then the
    names: a title taken, by a document here or by another file of the zip,
    is answered 409, nothing made, until ?renames= settles it."""
    raw = _q1(h, "headers")
    try:
        headers = json.loads(raw) if raw else {}
    except (ValueError, RecursionError):
        headers = None
    if not isinstance(headers, dict):
        return h.send_json({"ok": False, "error": "bad headers"}, 400)
    renames = _renames_query(h)
    if renames is None:
        return h.send_json({"ok": False, "error": "bad renames"}, 400)
    try:
        out = store.import_zip(h._body(), headers, renames)
    except store.HeaderNeeded as e:
        return h.send_json(dict(
            _header_lists(), ok=False, header_needed=True, files=e.files,
            error="some markdown files in the zip have an incomplete header"), 422)
    except store.NameConflict as e:
        return _name_conflict(h, e)
    h.send_json(dict(out, ok=True), 201)


def api_get(h, doc_id):
    meta, markdown = store.get(doc_id)
    h.send_json({"meta": meta, "markdown": markdown})


def api_save(h, doc_id):
    """The editor's Save.  The answer carries the markdown as written: a
    save that renames the document rewrites its own links to itself
    (store.save), a rename made elsewhere since the editor opened is
    followed in its links (`since`, the page's names mark), and the editor
    takes that text back so its next save does not undo them -- with the
    mark it now stands at.  A new title another document has is answered
    409, and nothing saved, until `renames` (the name-conflict dialog's)
    settles it."""
    body = h._json_body()
    try:
        with store.names_held():
            meta, markdown = store.save(doc_id, body.get("markdown", ""), body.get("renames"),
                                        since=body.get("since"))
            mark = store.names_mark()
    except store.NameConflict as e:
        return _name_conflict(h, e)
    _adopt(doc_id)
    # Saved source, unlike the editor buffer, owns its drawings.  This also
    # promotes a matching temporary preview without compiling it again.
    try:
        latexdraw.own_source(_latex_owner(doc_id), markdown)
    except Exception as e:                                   # noqa: BLE001 -- never lose a save
        sys.stderr.write("[studio] could not record LaTeX drawing ownership: %s\n" % e)
    h.send_json({"meta": meta, "markdown": markdown, "names_mark": mark})


def _latex_owner(doc_id):
    """An internal stable owner, scoped to this library rather than a title."""
    return "document:%s:%s" % (os.path.realpath(str(store.lib())), doc_id)


def _adopt(doc_id):
    """What a saved document names and does not hold, brought in: the
    starter's own pictures and recording (store.adopt_starter_media), then
    whatever the clip tray holds (store.adopt_media).  The text is written
    by then, and nothing here may turn a good save into an error: a file
    that cannot be copied is said on the console, and the page shows it as
    missing."""
    try:
        store.adopt_starter_media(doc_id)
    except Exception as e:           # noqa: BLE001 -- never fails the save
        sys.stderr.write("[studio] %s: the starter's pictures were not copied in (%s)\n"
                         % (doc_id, e))
    try:
        return store.adopt_media(doc_id)
    except Exception as e:           # noqa: BLE001 -- never fails the save
        sys.stderr.write("[studio] %s: nothing brought from the clip tray (%s)\n"
                         % (doc_id, e))
        return None


def api_meta(h, doc_id):
    try:
        meta = store.update_meta(doc_id, h._json_body())
    except store.NameConflict as e:
        return _name_conflict(h, e)
    h.send_json({"meta": meta})


def api_latex_themes(h):
    """The sheet's themes, each with what this computer lacks of it (the files
    Settings checks, or the compiler), and where Settings is when this Parseh
    has one: the sheet marks the theme and offers to install."""
    import latexthemes
    import texpackages
    doc = latexthemes.all_of()
    found = texpackages.installed_many(sorted({f for t in doc["themes"]
                                               for _p, f, _tl, _l in latexthemes.files_needed(t)}))
    got, missing = texpackages.manifest(), {}
    for t in doc["themes"]:
        gone = []
        if latexdraw.compiler(t["compiler"]) is None:
            gone.append({"id": t["compiler"], "install": None})
        for pid, names in texpackages.missing_for(t, got, found):
            gone.append({"id": pid, "install": ",".join(names)})
        if gone:
            missing[t["name"]] = gone
    h.send_json({"themes": [t["name"] for t in doc["themes"]], "default": doc["default"],
                 "missing": missing, "settings": htmlgen.LATEX.get("settings")})


def api_latex_preview(h):
    """One block, drawn as the sheet is typed in -- the drawing it will be."""
    body = h._json_body() or {}
    tex = str(body.get("tex") or "")[:20000]
    theme = str(body.get("theme") or "") or None
    if not tex.strip():
        return h.send_json({"ok": False, "said": "Nothing to draw yet."})
    r = latexdraw.draw(tex, theme, preview=True)
    if r.get("ok"):
        return h.send_json({"ok": True, "url": BASE + r["url"], "w": r["w"], "h": r["h"], "key": r.get("key")})
    return h.send_json({k: r.get(k) for k in ("ok", "kind", "said", "line", "detail", "fix", "key", "marks")})


def serve_latex(h, name):
    """A drawing latexdraw made: named by its key, so it never changes."""
    path = latexdraw.file_of(name)
    if path is None:
        return h.send_json({"error": "no such drawing"}, 404)
    # the document TeX was given and the log it wrote: plain text, shown on the page and never downloaded
    return h.send_file(Path(path), inline_type="text/plain; charset=utf-8" if path.endswith((".tex", ".log")) else None)


def api_arasaac_search(h):
    """A word looked for among the ARASAAC pictograms (lib/arasaacsearch.py): what the picker
    shows as thumbnails.  A read, though it is asked with a POST -- the words travel in a body, not in
    an address -- and one that touches nothing: what is on this computer's disk, and nothing a client
    sends becomes a path."""
    body = h._json_body() or {}
    try:
        out = arasaacsearch.search(body.get("q", ""), body.get("locales"), body.get("display"),
                                   body.get("offset"), body.get("limit"), body.get("sensitive") is True)
    except getarasaac.ArasaacError as e:
        return h.send_json({"ok": False, "error": e.say, "code": e.code}, 400)
    return h.send_json(out)


def serve_arasaac_picture(h, pid):
    """One pictogram's picture, by its number: the picker's thumbnail and preview, and the bytes the
    editor and the exercise form carry into a document as their own copy (docs/arasaac.md, 5.7)."""
    found = arasaacsearch.picture(pid)
    if found is None:
        return h.send_json({"error": "no such pictogram here"}, 404)
    try:
        data = Path(found).read_bytes()
    except OSError:
        return h.send_json({"error": "no such pictogram here"}, 404)
    query = urllib.parse.urlsplit(h.path).query
    h.send_bytes(data, "image/png", 200, {"Cache-Control": arasaacsearch.cache_control(query)})


def serve_media(h, doc_id, name):
    store.get(doc_id)                       # 404 if unknown doc
    path = store.image_path(doc_id, name)
    # A PDF figure is shown through the SVG twin written beside it.  Build
    # it on demand when it is missing, so a figure uploaded before the
    # twin existed — or one whose twin was deleted — repairs itself
    # instead of showing a broken image.
    if not path.exists() and name.lower().endswith(".pdf.svg"):
        store.ensure_pdf_twin(path.with_name(path.name[:-4]))
    h.send_file(path)


def api_images_list(h, doc_id):
    store.get(doc_id)
    h.send_json({"images": store.list_images(doc_id)})


def api_image_upload(h, doc_id):
    """Raw-body upload: POST /api/docs/<id>/images?name=foo.png"""
    store.get(doc_id)
    name = store.save_image(doc_id, _q1(h, "name", "img"), h._body())
    h.send_json({"name": name, "path": "images/" + name,
                 "url": base() + "/media/%s/images/%s" % (doc_id, name)}, 201)


def api_image_delete(h, doc_id, name):
    store.delete_image(doc_id, name)
    h.send_json({"ok": True})


def serve_audio(h, doc_id, name):
    """A recording, Range-aware (Handler.send_file): an <audio> seeks."""
    store.get(doc_id)                       # 404 if unknown doc
    h.send_file(store.audio_path(doc_id, name))


def serve_starter_media(h, kind, name):
    """One of the pictures and the recording the starters show
    (store.starter_media), read-only: where the editor's preview loads one
    the document does not hold yet (_preview_assets) -- a document not saved
    yet holds none.  Once a save has copied it in, the document's own copy
    is shown, under /media/<id>/."""
    path = store.starter_media(kind, name)
    if path is None:
        return h.send_json({"error": "not found"}, 404)
    h.send_file(path)


def api_audio_list(h, doc_id):
    store.get(doc_id)
    h.send_json({"audio": store.list_audio(doc_id)})


def api_audio_upload(h, doc_id):
    """Raw-body upload: POST /api/docs/<id>/audio?name=word.mp3"""
    store.get(doc_id)
    name = store.save_audio(doc_id, _q1(h, "name", "audio"), h._body())
    h.send_json({"name": name, "path": "audio/" + name,
                 "url": base() + "/media/%s/audio/%s" % (doc_id, name)}, 201)


def api_audio_delete(h, doc_id, name):
    store.delete_audio(doc_id, name)
    h.send_json({"ok": True})


def api_adopt(h, doc_id):
    """POST {"markdown"?}: bring from the clip tray the recordings and
    pictures that markdown names (by default the saved source) and the
    document lacks -> {"adopted": [...], "missing": [...]}.  The editor
    sends what was just pasted, before it is saved."""
    body = h._json_body()
    markdown = body.get("markdown") if isinstance(body, dict) else None
    if markdown is not None and not isinstance(markdown, str):
        return h.send_json({"error": "markdown must be text"}, 400)
    h.send_json(store.adopt_media(doc_id, markdown))


def api_image_layout(h, doc_id):
    body = h._json_body()
    try:
        start = body.get("start")
        end = body.get("end")
        meta = store.set_image_layout(
            doc_id, int(body.get("index", -1)), int(body.get("width", 60)),
            str(body.get("align", "left")), int(body.get("offset", 0)),
            start=None if start in (None, "") else float(start),
            end=None if end in (None, "") else float(end))
    except (TypeError, ValueError):
        return h.send_json({"error": "bad layout values"}, 400)
    h.send_json({"meta": meta})


def api_la_layout(h, doc_id):
    """Persist the layout panel of a `[…]{la}` block: attrs only."""
    body = h._json_body()
    try:
        meta = store.set_la_layout(
            doc_id, str(body.get("content", "")),
            int(body.get("occurrence", 0)), int(body.get("width", 100)),
            int(body.get("offset", 0)), str(body.get("align", "left")),
            body.get("bg") or None)
    except (TypeError, ValueError):
        return h.send_json({"error": "bad layout values"}, 400)
    h.send_json({"meta": meta})


def api_la_layout_pure(h):
    """Editor-buffer variant: rewrite the given markdown, store nothing."""
    body = h._json_body()
    try:
        markdown = store.la_layout_markdown(
            body.get("markdown", ""), str(body.get("content", "")),
            int(body.get("occurrence", 0)), int(body.get("width", 100)),
            int(body.get("offset", 0)), str(body.get("align", "left")),
            body.get("bg") or None)
    except (TypeError, ValueError):
        return h.send_json({"error": "bad layout values"}, 400)
    h.send_json({"markdown": markdown})


def api_image_layout_pure(h):
    """Editor-buffer variant of the embed layout rewrite."""
    body = h._json_body()
    try:
        start = body.get("start")
        end = body.get("end")
        markdown = store.image_layout_markdown(
            body.get("markdown", ""), int(body.get("index", -1)),
            int(body.get("width", 60)), str(body.get("align", "left")),
            int(body.get("offset", 0)),
            start=None if start in (None, "") else float(start),
            end=None if end in (None, "") else float(end))
    except (TypeError, ValueError):
        return h.send_json({"error": "bad layout values"}, 400)
    h.send_json({"markdown": markdown})


def api_tl_edit(h):
    """Pure rewrite for the target-text overlay editor: replace one block
    of the given (possibly unsaved) markdown buffer.  Served at
    /api/tl-edit and at the old /api/rtl-edit."""
    body = h._json_body()
    try:
        occ = int(body.get("occurrence", 0))
    except (TypeError, ValueError):
        occ = 0
    lines = body.get("lines")
    if not isinstance(lines, list):
        return h.send_json({"error": "lines must be a list"}, 400)
    markdown = store.tl_edit_markdown(
        body.get("markdown", ""), str(body.get("kind", "mark")),
        str(body.get("content", "")), occ, [str(l) for l in lines],
        font=body.get("font") or None, bg=body.get("bg") or None,
        vertical=bool(body.get("vertical")),
        height=body.get("height") or None)
    h.send_json({"markdown": markdown})


api_rtl_edit = api_tl_edit


def api_recolor(h):
    """Pure recolouring for the editor: rewrite the given markdown buffer
    (which may be unsaved) without touching any stored document."""
    body = h._json_body()
    text = (body.get("text") or "").strip()
    if not text:
        return h.send_json({"error": "no run given"}, 400)
    try:
        occ = int(body.get("occurrence", 0))
    except (TypeError, ValueError):
        occ = 0
    markdown = store.recolor_markdown(
        body.get("markdown", ""), text, occ, body.get("color") or None)
    h.send_json({"markdown": markdown})


def api_colour_selection(h):
    """Pure selection-first colouring for Studio's unsaved source buffer."""
    body = h._json_body() or {}
    source = body.get("markdown", "")

    # A textarea reports UTF-16 code-unit offsets; Python strings are
    # indexed by Unicode code point.  Convert at the HTTP boundary so an
    # emoji before the selection cannot move a colour edit into source
    # markup.  Grapheme expansion in the browser normally makes every edge
    # an exact boundary; consuming a split surrogate is the safe fallback.
    def from_utf16(value):
        try:
            wanted = max(0, int(value))
        except (TypeError, ValueError):
            wanted = 0
        units = 0
        for i, ch in enumerate(source):
            if units >= wanted:
                return i
            units += 2 if ord(ch) > 0xFFFF else 1
        return len(source)

    start, end = from_utf16(body.get("start", 0)), from_utf16(body.get("end", 0))
    markdown, caret = store.colour_selection_markdown(
        source, start, end, body.get("color") or None)
    caret_utf16 = sum(2 if ord(ch) > 0xFFFF else 1 for ch in markdown[:caret])
    h.send_json({"markdown": markdown, "caret": caret_utf16})


def api_color(h, doc_id):
    """Set/clear the colour mark on one run, in the markdown."""
    body = h._json_body()
    text = (body.get("text") or "").strip()
    if not text:
        return h.send_json({"error": "no run given"}, 400)
    try:
        occ = int(body.get("occurrence", 0))
    except (TypeError, ValueError):
        occ = 0
    color = body.get("color") or None
    meta, _ = store.set_run_color(doc_id, text, occ, color)
    h.send_json({"meta": meta, "color": color})


def _run_and_occurrence(h, body):
    """Shared argument check for the per-run mark endpoints."""
    text = (body.get("text") or "").strip()
    if not text:
        return None, 0
    try:
        return text, int(body.get("occurrence", 0))
    except (TypeError, ValueError):
        return text, 0


def api_translit(h, doc_id):
    """Set/clear the transliteration mark on one run."""
    body = h._json_body()
    text, occ = _run_and_occurrence(h, body)
    if not text:
        return h.send_json({"error": "no run given"}, 400)
    tr = body.get("translit")
    tr = tr.strip() if isinstance(tr, str) else None
    meta, _ = store.set_run_translit(doc_id, text, occ, tr or None)
    h.send_json({"meta": meta, "translit": tr or None})


def api_translit_pure(h):
    """The same rewrite on an unsaved editor buffer, touching no file."""
    body = h._json_body()
    text, occ = _run_and_occurrence(h, body)
    if not text:
        return h.send_json({"error": "no run given"}, 400)
    tr = body.get("translit")
    tr = tr.strip() if isinstance(tr, str) else None
    markdown = store.retranslit_markdown(
        body.get("markdown", ""), text, occ, tr or None)
    h.send_json({"markdown": markdown, "translit": tr or None})


def api_kana(h, doc_id):
    """Set/clear the reading (kana) mark on one run -- the languages with
    a reading only (the store refuses the others)."""
    body = h._json_body()
    text, occ = _run_and_occurrence(h, body)
    if not text:
        return h.send_json({"error": "no run given"}, 400)
    kana = body.get("kana")
    kana = kana.strip() if isinstance(kana, str) else None
    meta, _ = store.set_run_kana(doc_id, text, occ, kana or None)
    h.send_json({"meta": meta, "kana": kana or None})


def api_kana_pure(h):
    """The same rewrite on an unsaved editor buffer, touching no file."""
    body = h._json_body()
    text, occ = _run_and_occurrence(h, body)
    if not text:
        return h.send_json({"error": "no run given"}, 400)
    kana = body.get("kana")
    kana = kana.strip() if isinstance(kana, str) else None
    markdown = store.rekana_markdown(
        body.get("markdown", ""), text, occ, kana or None)
    h.send_json({"markdown": markdown, "kana": kana or None})


def api_palette(h):
    h.send_json({"palette": [{"name": n, "hex": "#" + v}
                             for n, v in htmlgen.PALETTE.items()]})


def api_duplicate(h, doc_id):
    meta = store.duplicate(doc_id)
    try:
        _unused, markdown = store.get(meta["id"])
        latexdraw.own_source(_latex_owner(meta["id"]), markdown)
    except Exception as e:                                   # noqa: BLE001
        sys.stderr.write("[studio] could not record copied LaTeX drawings: %s\n" % e)
    h.send_json({"meta": meta}, 201)


def api_doc_drawings(h, doc_id):
    """A page opened before its drawings were made (htmlgen's latex_defer)
    has them made here, a few at a time, each answer carrying the page's
    article as it now renders: the page swaps in the drawings that are
    there, and asks again while some are left.  Only the saved document's own
    drawings are made, so nothing the page sends is ever compiled."""
    meta, markdown = store.get(doc_id)
    body = h._json_body() or {}
    try:
        batch = max(1, min(8, int(body.get("batch") or 4)))
    except (TypeError, ValueError):
        batch = 4
    missing = [(t, th, i) for t, th, i in htmlgen.latex_wanted(markdown)
               if latexdraw.peek(t, th, inline=i).get("ok") is None]
    todo = missing[:batch]
    blocks = [(t, th) for t, th, i in todo if not i]
    marks = [(t, th) for t, th, i in todo if i]
    if blocks:
        latexdraw.draw_all(blocks)
    if marks:
        latexdraw.draw_all(marks, inline=True)
    doc = htmlgen.render_document(markdown, asset_base=base() + "/media/%s/" % doc_id,
                                  docs=store.doc_index(), deck_button=False, latex_defer=True)
    h.send_json({"html": doc["html"], "drawn": len(todo), "left": len(missing) - len(todo),
                 "pending": doc.get("latex_pending", 0)})


def api_latex_make(h):
    """THE LATEX DRAWINGS OF SEVERAL DOCUMENTS, made without opening them (a0.5.6).  The body is {ids: [...]}.  Nothing is read
    here and nothing waits: a helper process of the lowest priority (lib/latexbatch.py) is started, and it reads those
    documents, counts the distinct drawings not made yet, and makes them, on every page's activity bar.  The answer is the job's
    status, which the page asks again every second (GET)."""
    try:
        body = h._json_body() or {}
    except ValueError:
        return h.send_json({"error": "That was not JSON."}, 400)
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and store.ID_RE.match(i) for i in ids):
        return h.send_json({"error": "Say which documents."}, 400)
    import languages
    import latexthemes
    import texpackages
    env = {"library": str(store.lib()), "drawn": latexdraw.DRAWN, "themes": latexthemes.STORE,
           "tex_tree": texpackages.TREE, "languages": languages.PERSONAL}
    token = activity.clean_job((h.query.get("job") or [None])[0])
    try:
        status = latexbatch.start(list(dict.fromkeys(ids)), env, page=base() + "/", job=token)
    except latexbatch.Busy as e:
        return h.send_json(dict(latexbatch.status(), error=str(e)), 409)
    h.send_json(dict(status, shown=len(ids)))


def api_latex_make_status(h):
    h.send_json(latexbatch.status())


def api_latex_make_stop(h):
    h.send_json(latexbatch.stop())


def api_delete(h, doc_id):
    try:
        named = latexdraw._source_keys(store.get(doc_id)[1])
    except Exception:                                        # noqa: BLE001 -- only for the grace
        named = ()
    store.delete(doc_id)
    latexdraw.forget_owner(_latex_owner(doc_id), also=named)
    h.send_json({"ok": True})


def api_build(h, doc_id):
    if html_only():
        return h.send_json({"error": NEVER_BUILT}, 404)
    body = h._json_body()
    try:
        scale = float(body.get("scale") or 1.52)
    except (TypeError, ValueError):
        scale = 1.52
    import math
    if not math.isfinite(scale):        # reject NaN/inf from the JSON body
        scale = 1.52
    scale = min(max(scale, 0.8), 3.0)
    # the print options: absent is the normal build, anything else must be
    # one of them -- a size the class cannot set is refused, not guessed at
    size = body.get("size")
    if size is None:
        size = texgen.DEFAULT_PRINT_SIZE
    elif isinstance(size, bool) or not isinstance(size, (int, float)) \
            or size not in texgen.PRINT_SIZES:
        return h.send_json({"error": "size must be one of %s"
                            % ", ".join(map(str, texgen.PRINT_SIZES))}, 400)
    mono = body.get("mono")
    if mono is None:
        mono = False
    elif not isinstance(mono, bool):
        return h.send_json({"error": "mono must be true or false"}, 400)
    lock = _doc_lock(doc_id)
    if not lock.acquire(blocking=False):
        return h.send_json({"error": "build already running"}, 409)
    try:
        result = build_pdf(doc_id, scale, int(size), mono)
    finally:
        lock.release()
    h.send_json({"build": result}, 200 if result["status"] == "ok" else 500)


def _preview_assets(doc_id):
    """Where the editor's preview loads a file the buffer names from
    (htmlgen._asset_url): the document's own, under /media/<id>/ -- except
    a starter's picture or recording the document has never held, which is
    shown from where the starters keep it (serve_starter_media) until a
    save copies it in (store.adopt_starter_media).  One it has held and no
    longer does was deleted by its owner, and a save will not bring it back:
    it is the document's own address, missing, as the reading view shows
    it.  A document not saved yet (`doc_id` None) holds nothing, so the
    starters' files are all it can show: any other file it names has no
    URL, and the preview draws its placeholder."""
    mount = base()                    # `base` is the mount's own name now
    own = mount + "/media/%s/" % doc_id if doc_id else None
    held = store.starter_media_held(doc_id) if doc_id else set()

    def url(path):
        kind, _, name = path.partition("/")
        if store.starter_media(kind, name) is not None and path not in held \
                and not (doc_id and (store.doc_dir(doc_id) / kind / name).is_file()):
            return mount + "/starter-media/" + path
        return own + path if own else None
    return url


def api_preview(h):
    """Render an unsaved buffer.  The answer's `doc` carries `target`
    (the code the front matter resolved to) and `lang_record`, so the
    editor follows a `target:` typed into the front matter live, and
    `prose` (prose_record), so it follows a `lang:` too: the way the source
    is written by default."""
    body = h._json_body()
    doc_id = body.get("doc_id") or ""
    try:
        if not (store.ID_RE.match(doc_id) and store.doc_dir(doc_id).is_dir()):
            doc_id = None
    except KeyError:
        doc_id = None
    try:
        if body.get("page"):
            # THE PREVIEW IN ITS OWN TAB (static/live.js): the buffer drawn as the
            # reading page draws a saved document -- its hover tools off, its
            # exercises answerable, the contents beside it -- but with the
            # drawings made now, as the editor's own preview makes them, since
            # an unsaved text has none kept.  Nothing is written.
            doc = htmlgen.render_document(body.get("markdown", ""),
                                          asset_base=_preview_assets(doc_id),
                                          docs=store.doc_index(),
                                          latex_preview=True)
            doc["glosses"] = htmlgen.glosses(body.get("markdown", ""))
        else:
            doc = htmlgen.render_document(body.get("markdown", ""),
                                          asset_base=_preview_assets(doc_id),
                                          docs=store.doc_index(),
                                          editor_preview=True)
        doc["prose"] = prose_record(doc.get("lang"))
        h.send_json({"ok": True, "doc": doc})
    except Exception as e:
        h.send_json({"ok": False, "error": str(e)})


def api_tags(h):
    h.send_json({"tags": store.all_tags()})


def api_exercise_decks(h):
    """The optional known-vocabulary sources for exercise prompting; with
    ?target=<code>, only the decks of that language -- the page's."""
    target = _q1(h, "target")
    lang = languages.get_or_default(target).code if target else None
    h.send_json({"decks": anki_store.decks(str(ANKI_DIR), lang=lang)})


def _deck_vocabulary(paths):
    available = {d["path"]: d for d in anki_store.decks(str(ANKI_DIR))}
    selected = []
    for rel in paths if isinstance(paths, list) else []:
        if rel in available and rel not in selected:
            selected.append(rel)
    rows, seen = [], set()
    for rel in selected:
        cdir = ANKI_DIR / rel / "cards"
        if not cdir.is_dir():
            continue
        for path in sorted(cdir.glob("*.json")):
            card = anki_store.read_json(str(path)) or {}
            for target, reading, translit, meaning in (
                    (card.get("fa"), card.get("kana"), card.get("tr"), card.get("en")),
                    (card.get("opp"), card.get("opp_kana"), card.get("opp_tr"), "opposite")):
                target = str(target or "").strip()
                if not target:
                    continue
                row = (target, str(reading or "").strip(),
                       str(translit or "").strip(), str(meaning or "").strip())
                key = tuple(languages.fold(x) for x in row)
                if key not in seen:
                    seen.add(key); rows.append(row)
    return rows


def _rtl_markdown_guidance(target, exercises=False):
    """Instructions for composing isolated RTL boxes in an LTR Markdown run.

    This is appended only to prompts whose selected target is RTL.  Keeping it
    here makes the ordinary Studio authoring prompt and the exercise workflow
    teach the same distinction, including when the user has a custom base
    prompt installed.
    """
    parts = ["""
## Mixed-direction sequences for %s — binding

First decide the direction of the **containing expression**, independently of
the direction inside each target-language run.

- A continuous %s phrase or sentence is one RTL unit. Write its words in
  normal logical/read-aloud order inside a single `[...]{tl}` mark (or as the
  dialect otherwise permits). Never reverse characters, words, or punctuation
  inside that unit.
- A question, answer, choice, derivation, list, table cell, label, explanation,
  or flashcard field can instead be an **LTR-framed expression containing
  separate RTL components**. Operators and separators such as `+`, `→`, `=`,
  `/`, commas, parentheses, bullets, numbering, or intervening prose keep that
  surrounding expression LTR. Treat every separately marked RTL component as
  an indivisible visual box and write those boxes in the Markdown in the order
  they must appear **from left to right on the finished page**. When the boxes
  are successive parts of an RTL word or phrase, this means reversing their
  linguistic/read-aloud order at the box level. Keep the text *inside* every
  box in its natural order and keep each LTR separator between the same two
  boxes.

For example, the Persian word *dānešgāh* is read and analysed from the right as
`dān + -eš + -gāh`, but an LTR answer that displays its isolated components
must be authored in this visual left-to-right order:

```markdown
[گاه]{#6B6B1A translit:-gāh} + [ش]{#C28E0E translit:-eš} + [دان]{translit:dān}
```

Do not put the read-first root `dān` in the leftmost visual box: isolating the
runs would display the component sequence backwards. This rule is general and
does not depend on the plus sign. Apply the same box-order test with every
operator, separator, label, or piece of surrounding LTR prose. Before returning
the Markdown, mentally inspect the rendered line from left to right, then
verify that reading its RTL components from right to left gives the intended
linguistic order. This box-level source ordering is the only reversal involved;
it does not conflict with the rule never to reverse text inside an RTL run.
""".strip() % (target.name, target.name)]
    if exercises:
        parts.append("""
For exercises, apply that rule to every learner-visible field: the exercise
prompt, each answer or selectable segment, both sides of a matching pair,
explanations, and embedded flashcard fields. Do not assume that wrapping each
individual RTL chunk is sufficient; check the order of the chunks in their LTR
container.

A fill sentence is the one place where that box-order question does not
arise, because the sentence is not a row of LTR boxes: write it as ONE
target-language mark with its blanks inside, in natural logical order, and
never reverse anything in it.

```markdown
:::exercise fill-blanks
prompt: Complete the phrase below using the correct option.
text: [من بابک [[slot]]]{tl}
- [slot] [هَستَم]{tl}
- [ ] [است]{tl}
- [ ] [هَست]{tl}
:::
```

The mark is spread over the pieces round each blank when the document is
parsed, and the sentence as a whole is then laid out right to left, so each
blank is drawn where it is read. A blank that opens the sentence is written
`text: [[[slot]] شُما چیه؟]{tl}` — the first bracket opens the mark, and
`[[slot]]` is the blank. The answer row names the same blank: `- [slot] …`.
Write the blanks in the order they are read, not in any visual order, and do
not set `content-direction` for such a sentence; it needs none.

For `construct-sentence`, movable chunks follow the target language's reading
direction by default. Number them in spoken/logical order. For a sentence whose
spoken/logical order is `first_word second_word`, write exactly this pattern:

```markdown
:::exercise construct-sentence
prompt: Construct the sentence.
- [1] [first_word]{tl}
- [2] [second_word]{tl}
:::
```

Thus `first_word` occupies the rightmost slot and is read first from the right;
if the answer wraps, its next line starts at the right edge too. Use
`answer-direction: rtl` or `answer-direction: ltr` only when this particular
answer needs a different flow from the target language. This is separate from
`content-direction`, which controls the activity body's writing direction.
`order-sentences` remains a vertical list in normal chronological/logical order.
""".strip())
    return "\n\n".join(parts)


def api_exercise_prompt(h):
    """The exercise prompt, and what the dialog draws from it: `boxes` (the dialect's, default the ones
    the page already uses), `types` (the exercise types, default the ones it has, or all), `level` and
    `length`; answered with the prompt, its size, every box and type with its size and whether it is on,
    and what the page uses (`preticked`)."""
    body = h._json_body()
    chosen = None
    try:
        markdown = str(body.get("markdown") or "")
        # THE PROMPT OF THE PERSON'S THAT THE MENU CHOSE (`prompt`, an id), judged against the page's language
        fm, _blocks = mdparser.parse(markdown)
        chosen = prompts.resolve("studio-exercises", body.get("prompt"), languages.get_or_default(fm["target"]))
        a, rows = exercise_prompt(markdown, body.get("decks") or [], boxes=body.get("boxes"),
                                  types=body.get("types"), level=body.get("level"),
                                  length=body.get("length"), translit=body.get("translit"), chosen=chosen)
    except prompts.PromptsError as e:
        return h.send_json({"error": str(e)}, e.status)
    except (promptboxes.Refused, promptkit.OptionError) as e:
        return h.send_json({"error": str(e)}, 400)
    except promptkit.PromptError as e:
        return h.send_json({"error": prompts.unmade(chosen, e) if chosen
                            else "the prompt could not be made: %s" % e}, 400)
    boxes = promptboxes.catalog(a.target, a.boxes, exercising=True)
    types = promptboxes.types_catalog(a.target, a.types)
    _inert(chosen, boxes + types, exercising=True)
    h.send_json({"prompt": a.text, "vocabulary": len(rows), "boxes": boxes, "types": types,
                 "preticked": {"boxes": a.page_boxes, "types": a.page_types},
                 "options": promptkit.describe("studio-exercises", a.target, a.options),
                 "custom": _custom(chosen), "size": promptboxes.size(a.text),
                 # the short request for a chat that has the skill (lib/skills.py), made from the same prompt
                 "skill": _skill(lambda s: s.for_exercises(a.target, a, a.boxes, a.types, body.get("level"),
                                                           body.get("length"), chosen), "parseh-markdown")})


def exercise_prompt(markdown, decks=(), boxes=None, types=None, level="", length="", translit=None, chosen=None):
    """The prompt that has a model add exercises to a page, in its three
    parts (lib/promptkit.py), and the known words from the Anki decks it
    carries.  Its dialect is built from the boxes ticked -- by default the
    ones the page already uses -- and its exercises from the types ticked;
    `translit` is the scheme of the transliteration the request chose
    ("ipa" or "classic", promptkit.OPTIONS).  `chosen` is a prompt of the person's own for this place
    (prompts.resolve): one added to Parseh's takes the boxes and the types like Parseh's own; one in place
    of it takes them only if it carries their blocks, and is otherwise copied whole (_takes_boxes).
    -> (promptkit.Assembled, rows); what the request came to is on the Assembled, for the route that
    answers with it: `target`, `boxes` and `types` ticked, and what the page uses as `page_boxes` and
    `page_types` (all the types, when it holds no exercise)"""
    rows = _deck_vocabulary(decks)
    fm, _blocks = mdparser.parse(markdown)
    target = languages.get_or_default(fm["target"])
    options = promptkit.resolve("studio-exercises", target, promptkit.given({"translit": translit}))
    page_boxes, page_types = promptboxes.page_uses(markdown)
    page_types = page_types or list(promptboxes.TYPE_IDS)
    on_boxes = page_boxes if boxes is None else promptboxes.ticked(boxes)
    on_types = page_types if types is None else promptboxes.ticked_types(types)
    if not on_types:
        raise promptboxes.Refused("tick at least one exercise type: there is nothing to ask for without one")
    extras = []
    if target.dir == "rtl":
        extras.append(_rtl_markdown_guidance(target, exercises=True))
    # THE DIALECT IS BUILT FROM THE BOXES, NOT EMBEDDED WHOLE: a jolly card takes any block of it, so the
    # model has to know what the page uses, and the person ticks the rest -- but it is asked for exercises
    # here, not a page, and the instructions above say what to return (the studio's own contract, which
    # asks for a file, is not part of it).  The custom authoring prompt is the studio page's choice and
    # does not carry over: the dialog has its own.
    conventions = promptkit.language_text("studio-exercises", target, options=options)
    promptkit.check("\n".join(extras + [conventions]), "studio-exercises")  # Parseh's own
    if _takes_boxes(chosen, exercising=True):
        extras.append("## The page's Markdown dialect\n\n"
                      "What follows describes what the page's Markdown dialect lets an exercise use; where it "
                      "differs from the output instructions above, the instructions above win.\n\n"
                      + "\n\n".join(x for x in (promptboxes.dialect_text(target, on_boxes, on_types, options),
                                                conventions) if x))
    elif conventions:
        # A PROMPT COPIED WHOLE says what the page's dialect lets an exercise use in its own words: what the
        # boxes teach is not added after it, and what is true of the language still is
        extras.append(conventions)
    data = [promptboxes.level_length(level, length)]
    if rows:
        data.extend([
            "Known vocabulary from the selected Anki decks follows as tab-separated "
            "target, reading, transliteration, and meaning fields. It is optional vocabulary "
            "you may freely use; do not force every item into an exercise.",
            "```tsv\ntarget\treading\ttransliteration\tmeaning\n%s\n```" % "\n".join(
                "\t".join(x.replace("\t", " ").replace("\n", " ") for x in row)
                for row in rows),
        ])
    data.append("Here is the complete Markdown page to augment. Add the exercises now, and answer with the "
                "whole page:\n```markdown\n%s\n```" % markdown.rstrip())
    a = promptkit.assemble("studio-exercises", target,
                           flags=promptboxes.flags(target, on_boxes, on_types, exercising=True),
                           extras=extras, data="\n\n".join(x for x in data if x), options=options,
                           instructions=chosen.instructions if chosen else None,
                           custom=chosen.name if chosen else None)
    a.target, a.boxes, a.types = target, on_boxes, on_types
    a.page_boxes, a.page_types = page_boxes, page_types
    return a, rows


def lang_block(code, options=None):
    """The language's conventions (docs/lang/<code>.md) for the prompt page,
    cut to what a document needs (lib/promptkit.py) and read at request time;
    empty when the file is not there.  `options`: what the request chose of the
    scheme of the transliteration (promptkit.OPTIONS)."""
    return promptkit.language_text("studio-doc", languages.get_or_default(code), options=options)


def _target_line(L):
    """The line the prompt opens with, after its version line: which language
    the document is about."""
    return ("target: %s — this document is about %s: write `target: %s` in the "
            "front matter." % (L.code, L.name, L.code))


def _prompt_record(L):
    """The stored prompt as an older page has it, {text, custom}: it edits and
    copies a text and knows no marks and no boxes, so the default is the whole
    prompt for this language, every box it is offered ticked, its answer
    contract after it (promptboxes.legacy_text)."""
    out = store.get_prompt()
    if not out.get("custom"):
        out["text"] = promptboxes.legacy_text(L)
    return out


def _prompt_tail(L, text, custom, options=None):
    """What follows the instructions on the prompt page: the language's
    conventions and, where the text lacks it, the rule for the boxes of a
    right-to-left target."""
    blocks = [lang_block(L.code, options)]
    # The shipped prompt contains this rule itself so it also works when
    # copied directly from disk. Add it here for every custom override (and
    # for an older shipped prompt that lacks it), preserving the guarantee
    # without repeating the full section in the normal copied prompt.
    has_box_rule = ("Mixed-direction sequences:" in text or
                    "Mixed-direction sequences for" in text)
    if L.dir == "rtl" and (custom or not has_box_rule):
        blocks.append(_rtl_markdown_guidance(L))
    return "\n\n".join(x for x in blocks if x)


def studio_prompt(L, custom_text=None, boxes=None, level="", length="", translit=None, chosen=None):
    """The authoring prompt for a target language, in its three parts
    (lib/promptkit.py): the instructions -- Parseh's, with only the boxes
    ticked (by default the lesson's), or the text of a custom prompt -- with
    the language's conventions after them, then the answer contract, then
    the learner's level and the length asked for, one line each.  The
    question is the data, and is added by whoever copies.  `translit` is the
    scheme of the transliteration the request chose ("ipa" or "classic",
    promptkit.OPTIONS).  `chosen` is a prompt of the person's own for this
    place (prompts.resolve), in place of `custom_text`: the version line names
    it, one added to Parseh's goes after the instructions and takes the boxes
    like them, one in place of them takes the boxes only if it carries their
    blocks (promptboxes.has_box_marks).
    -> promptkit.Assembled"""
    if chosen is not None:
        custom_text = chosen.instructions
    custom = custom_text is not None
    on = promptboxes.ticked(boxes)
    options = promptkit.resolve("studio-doc", L, promptkit.given({"translit": translit}))
    # a person's own text in place of Parseh's may lack what the shipped prompt carries (the rule for a
    # right-to-left target); Parseh's words and then theirs do not (_prompt_tail)
    tail = (_prompt_tail(L, custom_text, chosen is None or chosen.kind == "replace", options)
            if custom else lang_block(L.code, options))
    promptkit.check(tail, "studio-doc")         # Parseh's own, put in by hand
    return promptkit.assemble("studio-doc", L, custom=chosen.name if chosen else custom, lead=_target_line(L),
                              instructions=custom_text, flags=promptboxes.flags(L, on),
                              values=promptboxes.values(L), includes=promptboxes.includes(),
                              extras=[tail], data=promptboxes.level_length(level, length),
                              options=options)


def _query_or_none(h, key):
    """A query value that may be BLANK: `boxes=` says none ticked, and the
    parsed query drops it (urllib's default), so the raw one is asked too.
    None where the request does not carry the key at all."""
    if key in h.query:
        return h.query[key][0]
    raw = urllib.parse.parse_qs(urllib.parse.urlsplit(getattr(h, "path", "") or "").query,
                                keep_blank_values=True)
    return raw[key][0] if key in raw else None


# WHY EVERY BOX IS GREYED for a prompt of the person's that is copied whole (brief 8.6): said once, beside each
INERT = ("your prompt is copied just as you wrote it, so these boxes change nothing in it: it has no "
         "{{?name}} blocks for them to switch")


def _takes_boxes(chosen, exercising=False):
    """Whether the boxes (and, for the exercise prompt, the exercise types) act on a person's prompt: Parseh's
    own and one added to it, yes; one in place of Parseh's only if it carries their blocks -- `{{?id}}` of a
    box, of its `no_<id>`, or of a type -- and otherwise it is copied whole."""
    if chosen is None or chosen.kind == "added":
        return True
    if promptboxes.has_box_marks(chosen.text):
        return True
    return exercising and any(m.startswith("type_") for m in prompts.markers(chosen.text))


def _inert(chosen, rows, exercising=False):
    """Grey what a prompt copied whole cannot use: every box this language is offered (and every type), with the
    one sentence that says why (static/promptpick.js draws `disabled`)."""
    if _takes_boxes(chosen, exercising):
        return
    for row in rows:
        if row.get("shown", True):
            row["disabled"] = INERT


def _skill(make, name):
    """The short request for a chat that has the skill (lib/skills.py), or why there is none: the studio run alone
    has lib/ beside it, and a fault in making the request never takes the prompt with it."""
    import skills
    return skills.safe(lambda: make(skills), name)


def _custom(chosen):
    """What an answer says of the prompt it carries: false for Parseh's own, else which of the person's."""
    return {"id": chosen.id, "name": chosen.name, "kind": chosen.kind} if chosen else False


def api_prompt_get(h):
    """The prompt, plus -- for ?target=<code> -- that language's own
    conventions block, kept apart from the editable text.

    `prompt` is the whole of it as lib/promptkit.py assembles it -- version
    line, target line, instructions with only the boxes ticked
    (?boxes=<id,id,...>: none given, the lesson's; empty, none), the
    language's conventions, the answer contract, the learner's level
    (?level=) and the length asked for (?length=) -- which is what a page
    copies; `header` and `contract` are two of its parts, for showing them.
    `boxes`, `presets`, `levels` and `lengths` are what the page draws its
    choices from, `size` and `always_chars` what it says of the cost.

    `text` (the editable prompt), `custom` and `lang_block` are what a page
    of before the boxes composed a prompt from, the block after the text:
    kept for it, and never used by the page that draws the boxes."""
    L = languages.get_or_default(_q1(h, "target"))
    out = _prompt_record(L)
    out["target"] = L.code
    out["target_name"] = L.name
    out["lang_block"] = _prompt_tail(L, out["text"], bool(out.get("custom")))
    chosen = None
    try:
        # THE PROMPT THE MENU CHOSE, `prompt=<id>`, is what the answer is made from: the one custom prompt this
        # page used to keep is a prompt among the others now, and is chosen like them.  `custom` says which
        chosen = prompts.resolve("studio-doc", _q1(h, "prompt"), L)
        on = promptboxes.ticked(_query_or_none(h, "boxes"))
        level, length, translit = _q1(h, "level"), _q1(h, "length"), _q1(h, "translit")
        a = studio_prompt(L, None, on, level, length, translit, chosen=chosen)
        out.update(prompt=a.text, header=a.header, contract=a.contract,
                   boxes=promptboxes.catalog(L, on), presets=promptboxes.presets(),
                   levels=promptboxes.levels(), lengths=promptboxes.lengths(),
                   options=promptkit.describe("studio-doc", L, a.options),
                   always_chars=len(studio_prompt(L, None, [], translit=translit, chosen=chosen).text),
                   size=promptboxes.size(a.text), custom=_custom(chosen),
                   # the short request for a chat that has the skill (lib/skills.py), made from the same prompt
                   skill=_skill(lambda s: s.for_studio(L, a, on, level, length, chosen), "parseh-markdown"))
        _inert(chosen, out["boxes"])
    except prompts.PromptsError as e:
        return h.send_json({"error": str(e)}, e.status)
    except (promptboxes.Refused, promptkit.OptionError) as e:
        return h.send_json({"error": str(e)}, 400)
    except promptkit.PromptError as e:
        if chosen:
            return h.send_json({"error": prompts.unmade(chosen, e)}, 400)
        # an older page's own prompt may say what the kit refuses; the page still has its text and its
        # block, and is told
        out["prompt_error"] = str(e)
    h.send_json(out)


def api_prompt_put(h):
    body = h._json_body()
    store.set_prompt(body.get("text", ""))
    h.send_json(_prompt_record(languages.get_or_default(_q1(h, "target"))))


def api_prompt_delete(h):
    store.reset_prompt()
    h.send_json(_prompt_record(languages.get_or_default(_q1(h, "target"))))


def api_prompts(h, what):
    """The prompts a person wrote (lib/prompts.py): the studio's own copy of the
    routes Settings' page and the row beside every copy button call at
    /settings/api/prompts/ in the toolbox -- the studio run alone has no
    Settings, and one shared module answers for both."""
    code, out = prompts.api(what, h._json_body())
    h.send_json(out, code)


def api_prompts_export(h):
    prompts.send_export(h, _q1(h, "id"))


def api_status(h):
    h.send_json({
        "docs": len(store.list_docs()),
        "languages": store.lang_counts(),
        "xelatex": STATE["xelatex"],
        "pymupdf": STATE["pymupdf"],
        "hyphenation": STATE["hyphenation"],
        "started": STATE["started"],
        "library": str(store.lib()),
    })


def api_export(h):
    """The whole library as one zip.

    A large library says so WHILE IT PACKS, on the Working… list: the
    Backup button is a plain link, so the answer goes to the browser and
    there is no page left to write on, and the list is what every page of
    the toolbox shows while a download is being made.  Nothing is refused
    here -- the restore's ceilings are far above it (store.LIB_MAX_*) -- but
    a library growing towards them should be noticed long before."""
    act = getattr(h, "_act", None)     # this request's Working… entry, in Parseh
    files = raw = told = 0
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(store.lib().rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(store.lib())
            if rel.parts[0].startswith("."):
                continue
            # sources + metadata always; of the build dir, only the PDF
            if "build" in rel.parts and f.name != "main.pdf":
                continue
            zf.write(f, str(rel))
            files, raw = files + 1, raw + f.stat().st_size
            # said once on crossing, then as it keeps growing: the figures
            # are what is worth watching, not the crossing
            if act and (files > store.LIB_WARN_FILES or raw > store.LIB_WARN_BYTES) \
                    and (not told or files - told >= 500):
                told = files
                activity.relabel(act, store.big_backup_note(
                    "The backup of the studio library", files, raw))
    name = "exlex-library-%s.zip" % time.strftime("%Y%m%d-%H%M")
    h.send_bytes(buf.getvalue(), "application/zip", 200,
                 {"Content-Disposition": 'attachment; filename="%s"' % name})


def api_import_library(h):
    """A backup put back: the zip the Backup button gives, as the body.

    ?replace=1 overwrites a document that is already here; without it such a
    document is kept and named in the answer, so a restore never quietly eats
    work that is newer than the backup.  The body is spooled to disk by the
    hub (serve.py's UPLOAD_ROUTES) for a library of any size, and read from
    there; the studio on its own still has its 32 MB body cap.

    A document with another id whose name is taken is answered 409, nothing
    written, until ?renames= (the name-conflict dialog's answer) settles it;
    the page sends the zip again, as it does for ?replace=1.
    """
    spool = getattr(h, "_spool", None)
    source = spool if spool else h._body()
    if not source:
        return h.send_json({"ok": False, "error": "nothing to restore: send "
                            "the backup zip as the body"}, 400)
    renames = _renames_query(h)
    if renames is None:
        return h.send_json({"ok": False, "error": "bad renames"}, 400)
    try:
        out = store.import_library(source, replace=_q1(h, "replace") == "1",
                                   renames=renames)
    except store.NameConflict as e:
        return _name_conflict(h, e)
    except store.StoreError as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)
    h.send_json(dict(out, ok=True), 201)


def _download_ids(h):
    """The ids a download asks for and the shape it wants -> (ids, shape).

    From either body the route accepts: the library page's plain form
    (`ids=a,b&shape=zip`, urlencoded -- a form submit is what lets the browser
    save the answer as a file) or JSON `{"ids": [...], "shape": "md"}`.  The
    shape is "md" unless "zip" is asked for by name, so a caller that has
    never heard of it gets what it always got.  (None, "md") for a JSON body
    that does not parse."""
    text = (h._body() or b"").decode("utf-8", "replace").strip()
    if text.startswith("{"):
        try:
            body = json.loads(text)
        except (json.JSONDecodeError, RecursionError):     # nested too deep counts as unreadable
            return None, "md"
        raw = body.get("ids") if isinstance(body, dict) else None
        if isinstance(raw, str):
            raw = raw.split(",")
        values = [v for v in raw if isinstance(v, str)] if isinstance(raw, list) else []
        shape = body.get("shape") if isinstance(body, dict) else ""
    else:
        form = urllib.parse.parse_qs(text)
        values = [part for v in form.get("ids", []) for part in v.split(",")]
        shape = (form.get("shape") or [""])[0]
    return values, ("zip" if shape == "zip" else "md")


def api_download(h):
    """The documents the library page shows, at once.

    Either shape the per-document Download offers: one zip of their .md
    sources, or -- shape=zip -- one zip holding each document's OWN zip, the
    markdown with its tags, its pictures and its recordings beside it,
    exactly as that document's own Download gives it.  A zip of zips is the
    only honest way to carry media for many documents at once: their
    images/ and audio/ would otherwise land in one heap with every name free
    to collide.

    Unknown or malformed ids are skipped rather than refused -- a document
    deleted in another tab should not cost the others."""
    values, shape = _download_ids(h)
    if values is None:
        return h.send_json({"ok": False, "error": "bad JSON body"}, 400)
    docs, seen = [], set()
    for doc_id in (v.strip() for v in values):
        if doc_id in seen or not store.ID_RE.match(doc_id):
            continue
        seen.add(doc_id)
        try:
            source = (store.doc_dir(doc_id) / "source.md").read_bytes()
        except (KeyError, OSError):
            continue
        docs.append((doc_id, source))
    if not docs:
        return h.send_json({"ok": False, "error": "no documents to download"}, 400)
    # the name the per-document download gives (the id without its random
    # suffix), unless two documents would land on one name: those keep the
    # whole id, which is unique -- repeated until no name is shared
    names = {doc_id: re.sub(r"-[0-9a-f]{6}$", "", doc_id) or doc_id
             for doc_id, _ in docs}
    while True:
        counts = {}
        for n in names.values():
            counts[n] = counts.get(n, 0) + 1
        clash = [i for i, n in names.items() if counts[n] > 1 and n != i]
        if not clash:
            break
        for i in clash:
            names[i] = i
    buf = io.BytesIO()
    made = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc_id, source in docs:
            if shape == "zip":
                try:
                    inner = store.doc_zip(doc_id, names[doc_id])
                except (KeyError, OSError, store.StoreError):
                    continue          # deleted between the two passes
                # deflated already, inside: stored here rather than squeezed twice
                zf.writestr(names[doc_id] + ".zip", inner, zipfile.ZIP_STORED)
            else:
                zf.writestr(names[doc_id] + ".md", source)
            made += 1
    if not made:
        return h.send_json({"ok": False, "error": "no documents to download"}, 400)
    name = ("studio-%d-documents%s-%s.zip"
            % (made, "-with-media" if shape == "zip" else "",
               time.strftime("%Y%m%d-%H%M")))
    h.send_bytes(buf.getvalue(), "application/zip", 200,
                 {"Content-Disposition": 'attachment; filename="%s"' % name})


def api_shutdown(h):
    h.send_json({"ok": True, "message": "server stopping"})

    def stop():
        time.sleep(0.3)
        srv = SERVER["instance"]
        if srv:
            srv.shutdown()
    threading.Thread(target=stop, daemon=True).start()


# the deck pages' Stop button stops the same server, in Parseh as on its own
deckroutes.set_shutdown(api_shutdown)


# What the +New button hands you: one starter per language, in
# exlex/starters/<code>.md, because a starter is prose and prose belongs in
# a file somebody can edit without touching Python.  They are not the same
# document with `target:` swapped -- a Persian one shows a run being
# recognised by its script and a couplet in nastaliq, a Japanese one shows
# the kana riding in the braces and a block set vertically, a Latin-script
# one shows every run being marked by hand because nothing can recognise
# it.  The prose language is English throughout: `lang:` is what picks the
# hyphenation, and English is what an undeclared document gets from TeX
# anyway (exlex/texgen.py, DEFAULT_HYPHEN).
STARTERS = EXLEX / "starters"


def new_template(code=None):
    """The starting document for a language.

    A language with no file of its own still gets a usable one, built from
    its registry row: an eighth language works the day its row lands, and
    whoever writes its starter drops a <code>.md in exlex/starters/ with
    nothing else to change.
    """
    L = languages.get_or_default(code)
    path = STARTERS / ("%s.md" % L.code)
    if path.exists():
        return path.read_text(encoding="utf-8")
    # the generic one: the front matter, the box, and the single sentence
    # that differs between a script the toolbox can recognise and one it
    # cannot (docs/languages.md, 5)
    if L.chars:
        how = ("%s inside English prose needs no mark: the script is enough.\n"
               "A paragraph with no Latin letters in it at all is laid out as\n"
               "%s on its own." % (L.name, L.name))
    else:
        how = ("%s is written in the same alphabet as the prose around it, so a\n"
               "run of it cannot be recognised and has to be **marked**:\n"
               "`[a word]{tl}`." % L.name)
    return ("---\n"
            "title: New %s note\n"
            "subtitle: what the note is about\n"
            "note: the small line under the title\n"
            "lang: en\n"
            "target: %s\n"
            "---\n"
            "\n"
            "> The box at the top is for the one thing worth remembering.\n"
            "> Delete it if the note does not need one.\n"
            "\n"
            "%s\n"
            "\n"
            "## headword | %s | short etymology | = *translation*\n"
            "\n"
            "- **First** what the entry is for.\n"
            "- **Then** the senses it treats.\n"
            % (L.name, L.code, how, L.translit_label))


# ----------------------------------------------------------------------
# a file from anywhere on the computer, open in the studio (a0.5.2)
# ----------------------------------------------------------------------
#
# openfile.py keeps the sessions: a Markdown or zip file read into a working
# copy in a temporary folder, written back only by Save.  The working copy is
# a studio library of ONE document, so the studio serves it as it serves the
# notes beside a book: with its routes, run with the library
# (store.use_library) and the prefix (use_mount) pointed at it for the length
# of the request.  /open/<sid>/ is that prefix -- /studio/open/<sid>/ inside
# Parseh -- and everything under it is the studio's own pages and doors, on
# the file.  What is new here is only the door in (the file browser and Open),
# the two doors on a session (its state, Save and Close), and what a session
# does not offer: the library's own business.
#
# ANY DEVICE PARSEH LETS IN (the owner, 2026-10-19: "make it available from remote
# too").  The file browser lists any folder the program can read and Save writes
# to any path it can write -- on the computer Parseh RUNS on, wherever the person
# asking is sitting.  Who may ask is the same door as for the rest of the studio
# (serve.py's gate: this computer, a VPN, a device let in with the code), and
# nothing here asks again.  What the page has to be told is where the files ARE:
# a phone's "Open a file" shows the disk of the computer Parseh runs on, not the
# phone's, and says so (_where).  A file on the device in the hand is another
# thing, which Upload .md / .zip already is.


def _where(h):
    """Where the files the file doors show are, as a page says it: the name of
    the computer Parseh runs on, and whether the device asking is another one.
    (A handler with no client address, a test's fake, is taken for another
    device: the page then says whose disk it is looking at.)"""
    ip = (getattr(h, "client_address", None) or ("",))[0]
    return {"host": socket.gethostname(), "remote": network.where(ip) != network.SELF}


def open_prefix(sess):
    """The address the studio serves a session under."""
    return BASE + "/open/" + sess.sid


@contextlib.contextmanager
def open_scope(sess):
    """The studio, pointed at a session for the length of the block: its
    library, and its prefix (so the links of every page stay inside it)."""
    was_lib = store.use_library(sess.library)
    was_mount = use_mount(open_prefix(sess), html_only=False, session=sess)
    try:
        yield sess
    finally:
        restore_mount(was_mount)
        store.use_library(was_lib)


# What a file opened from the computer does not offer: the library's own
# business, where a second document, a deleted one or a whole backup would
# mean nothing (the library is this one document, and it is not kept).
_NOT_IN_A_FILE = (
    ("GET", r"^/new$"), ("POST", r"^/api/docs$"), ("POST", r"^/api/docs/zip$"),
    ("POST", r"^/api/library/zip$"), ("POST", r"^/api/docs/[a-z0-9\-]+/duplicate$"),
    ("DELETE", r"^/api/docs/[a-z0-9\-]+$"), ("GET", r"^/api/export$"),
    ("POST", r"^/api/download$"), ("POST", r"^/api/latex/make(?:/stop)?$"), ("GET", r"^/api/latex/make$"),
    ("GET", r"^/doc/[a-z0-9\-]+/__offline$"),
)
NOT_IN_A_FILE = ("That belongs to the studio's library, not to a file opened from the computer: "
                 "close the file and do it from the library.")


def serve_open(h, method, sid, sub, run):
    """/open/<sid>/…: the studio's own routes, on the working copy of a file
    opened from the computer.  `run(method, sub)` is the route table of
    whoever hosts the studio (the studio alone, or serve.py's /studio)."""
    try:
        sess = openfile.get(sid)
    except KeyError:
        if method == "GET":
            return h.send_html(render_template("404.html", {}), 404)
        return h.send_json({"ok": False, "error": "That file is not open any more: open it again "
                                                  "from the library."}, 404)
    sub = sub or "/"
    with open_scope(sess):
        if method == "GET" and sub == "/":
            # the way "back" from the editor, and the root of the mount: the document
            return h.send_bytes(b"", "text/plain; charset=utf-8", 302,
                                {"Location": "%s/doc/%s" % (base(), sess.doc_id)})
        for m, pattern in _NOT_IN_A_FILE:
            if m == method and re.match(pattern, sub):
                return h.send_json({"ok": False, "error": NOT_IN_A_FILE}, 404)
        return run(method, sub)


def session_library(prefix):
    """The working copy behind a session's prefix, or None: what the exercise
    decks ask (deckroutes.set_notes_resolver) before a document page offers
    "+ Deck" and before a copy reads the document, as they ask serve.py for a
    book's notes."""
    m = re.fullmatch(re.escape(BASE) + r"/open/([0-9a-f]{12})", prefix or "")
    if not m:
        return None
    try:
        return openfile.get(m.group(1)).library
    except KeyError:
        return None


deckroutes.set_notes_resolver(session_library)


def _notes_source():
    """The prefix the deck routes read this thread's document from, when it is
    not the studio's own library: the notes beside a book or a video, or a file
    opened from the computer -- as long as they know the prefix."""
    if (html_only() or current_session() is not None) and deckroutes.notes_source_ok(base()):
        return base()
    return ""


def _session_say(sess):
    """A session, for the lists and for opening it: its state, and where its pages are."""
    return dict(sess.state(), url=open_prefix(sess) + "/doc/" + sess.doc_id,
                edit=open_prefix(sess) + "/doc/" + sess.doc_id + "/edit")


def api_file(h, what):
    """The doors about the computer's files rather than about one document:
    where to start (places), a folder's contents (list), open a file (open),
    and what is open (sessions).  All POST: a page of another site cannot
    send one (crosssite), and none of them reads or writes anything the
    person did not ask for by name."""
    body = h._json_body() or {}
    if what == "places":
        return h.send_json(dict(_where(h), ok=True, places=openfile.places()))
    if what == "list":
        return h.send_json(dict(openfile.listing(str(body.get("path") or ""), hidden=bool(body.get("hidden")),
                                                 everything=bool(body.get("everything"))), **_where(h)))
    if what == "sessions":
        return h.send_json(dict(_where(h), ok=True, sessions=[_session_say(s) for s in openfile.live()]))
    try:
        got = openfile.open_path(str(body.get("path") or ""), entry=body.get("entry") or None)
    except openfile.OpenError as e:
        return h.send_json(e.answer(), 409 if e.code == "busy" else 400)
    if "choose" in got:
        return h.send_json({"ok": True, "choose": got["choose"], "name": got["name"]})
    return h.send_json(dict(_session_say(got["session"]), ok=True, again=got["again"]))


def api_file_session(h, what):
    """The doors on the file this page is about: its state (is there anything
    the file does not hold? did somebody change the file?), Save, and Close.
    Under /open/<sid>/, so the session is the mount's and a body names none."""
    sess = current_session()
    if sess is None:
        return h.send_json({"ok": False, "error": "This is not a file opened from the computer."}, 404)
    body = h._json_body() or {}
    if what == "state":
        return h.send_json(dict(_where(h), ok=True, state=sess.state(), library=BASE + "/"))
    if what == "save":
        try:
            out = sess.save(target=body.get("target") or None, overwrite=bool(body.get("overwrite")),
                            force=bool(body.get("force")), accept_loss=bool(body.get("accept_loss")))
        except openfile.OpenError as e:
            return h.send_json(e.answer(), 400)
        out.update(_where(h), library=BASE + "/")
        return h.send_json(out)
    out = sess.close(discard=bool(body.get("discard")))
    if out.get("ok"):
        try:
            latexdraw.forget_owner(_latex_owner(sess.doc_id))
        except Exception as e:                               # noqa: BLE001 -- only housekeeping
            sys.stderr.write("[studio] could not let go of the LaTeX drawings of a closed file: %s\n" % e)
        out["library"] = BASE + "/"
    return h.send_json(out)


ROUTES = [
    ("GET",    r"^/$",                                    page_index),
    ("GET",    r"^/new$",                                 page_new),
    ("GET",    r"^/prompt$",                              page_prompt),
    ("GET",    r"^/doc/([a-z0-9\-]+)$",                   page_doc),
    # the same document with no editor and no scripts, for a note opened
    # over a reader or a player (page_note)
    ("GET",    r"^/note/([a-z0-9\-]+)$",                  page_note),
    # what a document is made of, for a phone to keep (§19.3, §19.8)
    ("GET",    r"^/doc/([a-z0-9\-]+)/__offline$",         api_doc_offline),
    ("GET",    r"^/doc/([a-z0-9\-]+)/edit$",              page_edit),
    ("GET",    r"^/pdf/([a-z0-9\-]+)$",                   serve_pdf),
    ("GET",    r"^/download/([a-z0-9\-]+)/(md|tex|texzip|pdf|zip|html)$", serve_download),
    ("GET",    r"^/static/langs\.css$",                   serve_langs_css),
    # the sheet and the chrome, put back together under the name every page
    # already links (serve_app_css); static/sheet.css is served as it is, by
    # the general static route below, for the bare note page
    ("GET",    r"^/static/app\.css$",                     serve_app_css),
    ("GET",    r"^/static/app\.js$",                      serve_app_js),
    ("GET",    r"^/lib/llmrow\.js$",                      serve_llmrow_js),
    ("GET",    r"^/lib/(pagesettings\.(?:js|css)|pagezoom\.js)$", serve_gear_file),
    ("GET",    r"^/lib/(pictograms\.(?:js|css))$",         serve_picker_file),
    ("GET",    r"^/__prompt/options$",                    serve_prompt_options),
    ("GET",    r"^/static/mathjax\.js$",                  serve_math_js),
    ("GET",    r"^/static/mathjax\.css$",                 serve_math_css),
    ("GET",    r"^/static/mathjax/(.+)$",                  serve_math_lib),
    ("GET",    r"^/static/(.+)$",                         serve_static),
    # the LaTeX drawing sheet: the themes to choose from, and a block drawn as
    # it is typed (static/exform.js, openLatexOverlay)
    # the pictogram picker (lib/pictograms.js): a word looked for among the ARASAAC pictograms
    # installed here, and a picture of one by its number
    ("POST",   r"^/api/arasaac/search$",                  api_arasaac_search),
    ("GET",    r"^/arasaac/([0-9]{1,7})\.png$",           serve_arasaac_picture),
    ("GET",    r"^/api/latex/themes$",                    api_latex_themes),
    ("POST",   r"^/api/latex/preview$",                   api_latex_preview),
    ("POST",   r"^/api/latex/make$",                      api_latex_make),
    ("GET",    r"^/api/latex/make$",                      api_latex_make_status),
    ("POST",   r"^/api/latex/make/stop$",                 api_latex_make_stop),
    # a latex block's drawing, by its key (lib/latexdraw.py): one address for
    # the whole toolbox, whichever page or note shows it
    ("GET",    r"^/latex/([0-9a-f]{64}\.(?:svg|pdf|tex|log))$", serve_latex),
    ("GET",    r"^/media/([a-z0-9\-]+)/images/([A-Za-z0-9._\-]+)$", serve_media),
    ("GET",    r"^/api/docs/([a-z0-9\-]+)/images$",       api_images_list),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/images$",       api_image_upload),
    ("DELETE", r"^/api/docs/([a-z0-9\-]+)/images/([A-Za-z0-9._\-]+)$", api_image_delete),
    ("GET",    r"^/media/([a-z0-9\-]+)/audio/([A-Za-z0-9._\-]+)$", serve_audio),
    ("GET",    r"^/starter-media/(images|audio)/([A-Za-z0-9._\-]+)$", serve_starter_media),
    ("GET",    r"^/api/docs/([a-z0-9\-]+)/audio$",        api_audio_list),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/audio$",        api_audio_upload),
    ("DELETE", r"^/api/docs/([a-z0-9\-]+)/audio/([A-Za-z0-9._\-]+)$", api_audio_delete),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/adopt$",        api_adopt),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/image-layout$", api_image_layout),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/la-layout$",    api_la_layout),
    ("GET",    r"^/api/docs$",                            api_list),
    ("POST",   r"^/api/docs$",                            api_create),
    ("POST",   r"^/api/docs/zip$",                        api_import_zip),
    ("POST",   r"^/api/library/zip$",                     api_import_library),
    ("GET",    r"^/api/docs/([a-z0-9\-]+)$",              api_get),
    ("PUT",    r"^/api/docs/([a-z0-9\-]+)$",              api_save),
    ("PATCH",  r"^/api/docs/([a-z0-9\-]+)/meta$",         api_meta),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/color$",        api_color),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/drawings$",     api_doc_drawings),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/translit$",     api_translit),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/kana$",         api_kana),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/duplicate$",    api_duplicate),
    ("DELETE", r"^/api/docs/([a-z0-9\-]+)$",              api_delete),
    ("POST",   r"^/api/docs/([a-z0-9\-]+)/build$",        api_build),
    ("POST",   r"^/api/preview$",                         api_preview),
    ("POST",   r"^/api/recolor$",                         api_recolor),
    ("POST",   r"^/api/colour-selection$",                api_colour_selection),
    ("POST",   r"^/api/translit$",                        api_translit_pure),
    ("POST",   r"^/api/kana$",                            api_kana_pure),
    ("POST",   r"^/api/tl-edit$",                         api_tl_edit),
    ("POST",   r"^/api/rtl-edit$",                        api_tl_edit),
    ("POST",   r"^/api/la-layout$",                       api_la_layout_pure),
    ("POST",   r"^/api/image-layout$",                    api_image_layout_pure),
    ("GET",    r"^/api/tags$",                            api_tags),
    ("GET",    r"^/api/exercise-decks$",                   api_exercise_decks),
    ("POST",   r"^/api/exercise-prompt$",                  api_exercise_prompt),
    ("GET",    r"^/api/palette$",                         api_palette),
    ("GET",    r"^/api/prompt$",                          api_prompt_get),
    ("PUT",    r"^/api/prompt$",                          api_prompt_put),
    ("DELETE", r"^/api/prompt$",                          api_prompt_delete),
    ("POST",   r"^/api/prompts/(state|list|get|parseh|save|uptodate|import|delete)$", api_prompts),
    ("GET",    r"^/api/prompts/export$",                  api_prompts_export),
    ("GET",    r"^/api/status$",                          api_status),
    ("GET",    r"^/api/export$",                          api_export),
    ("POST",   r"^/api/download$",                        api_download),
    ("POST",   r"^/api/shutdown$",                        api_shutdown),
    # a file from anywhere on the computer, open in the studio (a0.5.2): the
    # doors about the computer's files, and the doors on the file a page is about
    ("POST",   r"^/api/file/(places|list|open|sessions)$", api_file),
    ("POST",   r"^/api/file/(state|save|close)$",          api_file_session),
]

# The routes that are a page the browser goes to: a document that is not
# there (deleted, its address kept on a page still open) is answered with the
# studio's own 404 page, not the JSON an API call gets.
PAGES = (page_doc, page_note, page_edit)


def main():
    ap = argparse.ArgumentParser(description="exlex studio web server")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--open", action="store_true",
                    help="open the browser after starting")
    a = ap.parse_args()

    ensure_web_fonts()
    seed_example()
    migrate_library()
    ensure_build_env_async()
    try:
        left = openfile.sweep()                 # what the last run left of the files opened from the computer
        if left["kept"]:
            print("%d file(s) opened from the computer still hold changes that were never saved: "
                  "the library page offers them back" % len(left["kept"]))
    except Exception as e:                      # noqa: BLE001 -- housekeeping never stops the studio from starting
        print("could not look through the files opened from the computer: %s" % e)

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    srv.daemon_threads = True
    SERVER["instance"] = srv
    url = "http://127.0.0.1:%d/" % a.port
    print("exlex studio serving at %s  (library: %s)" % (url, store.LIB))
    if a.open:
        threading.Timer(0.4, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        openfile.shutdown()                     # the working copies with nothing unsaved go with the server
        latexbatch.shutdown()                   # and the helper that makes many documents' drawings, with its TeX
    print("exlex studio stopped.")


if __name__ == "__main__":
    main()
