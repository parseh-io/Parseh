#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The toolbox, end to end, for every language it teaches.

    python3 tests/smoke.py            everything that needs no TeX engine
    python3 tests/smoke.py --pdf      ... and the LaTeX builds (minutes)
    python3 tests/smoke.py --only books,videos,draft,studio,anki,server,js,verbs

What it proves, in order:

  compile   every Python file compiles; every page script parses (deno, when
            the conda environment has it)
  registry  lib/languages.py lists the languages, the original four leading
  books     the fixture editions under tests/fixtures/books/, and any book
            the owner keeps under books/ (the shelf ships empty): texparse
            reads them, tex2html writes a reader with
            the language's passes (ruby + kana + a vertical pass for
            Japanese, two passes for the Latin-script ones, Arabic digits for
            Arabic), verify_book.py proves fidelity, check_batch.py and
            assemble.py accept a paragraph rebuilt from the .tex (and write
            \\chr for Japanese), texwrite.py numbers the chunks as texparse
            does and edits one of them in a copy without moving another byte,
            bundle.py takes each edition out as one file and puts it back into
            a scratch toolbox byte for byte (and refuses a zip that tries to
            write outside it) and takes a narrated one out in each of its
            three shapes -- `text` leaving nothing that points at a recording,
            `linked` plus audio/ being `full` file for file, and a `text`
            bundle landing on a narrated book costing nobody the recording;
            make_index.py writes the library page with the
            chip row; with --pdf, every fixture builds with lualatex under
            build.sh's own criteria, and build.sh itself is run when there is
            a book on the shelf for it to build
  videos    check_annotations.py on every fixture (merged in a temporary
            copy) and on whatever is under youtube/videos/, which ships empty
            too; ytpages assembles the index and -- with each fixture parked
            briefly under youtube/videos/ -- every language's player, and a
            video actually filed there gets its channel and player page as
            well; the annotator's prompt builds for every language in the
            registry; and
            bundle.py round-trips every video and refuses one whose
            annotations no longer check
  draft     lib/draft.py makes an empty edition out of each fixture's own
            text and an empty annotation out of each fixture video's
            transcript, and marks neither of them as anything: the draft
            reproduces its source, passes check_batch and check_annotations
            with one count note instead of errors (a blank chunk is legal
            everywhere), and renders -- and a chunk half written in it, its
            meaning typed and its reading blanked, is refused; an old
            "draft": true left in book.json or video.json changes nothing
  studio    every starter opens, marks its runs the way its script asks and
            numbers them as the store does; the prose table and the registry
            name one set of hyphenation patterns per language; every document
            in exlex/examples/ and tests/fixtures/studio/ renders through
            htmlgen and texgen with the target its own front matter declares
            (a Japanese one, when there is one, showing a vertical block,
            kana marks and a lemma reading); whatever documents the library
            holds carry their target; every language without a document of
            its own goes through both renderers as one built from its fixture
            edition's first chunk; with --pdf every one of those documents
            builds and verifies, the Persian fixture still at 186/186 and the
            feature test -- figures, footnotes, links, colour and blocks
            through XeLaTeX -- at 21/21
  verbs     the \\vb a dictionary hit carries: every language's recipe
            (lib/verbs/<code>.py) on its own eight cases under
            tests/fixtures/verbs/, each built into a dictionary of one entry
            -- so no dictionary need be installed -- and the core that writes
            the four shapes of one verb from what a recipe says, held to the
            PDF's macro and to both readers' reading of it
  anki      the round trip in tests/fixtures/anki/roundtrip.py (the deck store,
            one deck per language, the builds and the .apkg round trip)
  server    serve.py, started on a spare port over plain http, answers every
            door's pages and the new routes without a traceback

And after all of it, whatever --only chose: config/ beside the checkout --
the owner's preferences and the phone-keeping door's memories -- is byte for
byte as the run found it (tests/configguard.py), or the run fails.

books/, youtube/videos/ and the studio's library ship empty: what goes in
them is the owner's, not the software's.  So every one of them is tried when
something is there and skipped, by name, when nothing is -- the suite is
green on a fresh clone and says more on a full one.

Fixtures live under tests/fixtures/; nothing here writes under books/,
youtube/videos/ or the studio library except the readers of a book already
on the shelf (which build.sh rewrites anyway) -- and a fixture video is
copied under youtube/videos/<folder>/ only for the seconds its player page
is assembled, then removed.  The one thing that does stay is the server's own
first start, which test_server performs: serve.py seeds whatever example
documents exlex/examples/ holds into markdown/library/ -- none, at present --
exactly as it would for somebody opening the studio for the first time.  Standard library only; the LaTeX builds and
the JS parse use what is on the machine and say so when it is absent.

Nothing here counts languages by hand: the registry says how many there are,
and a language the fixtures do not cover yet is a SKIP naming the door it
misses, never a failure -- adding a language must not turn the suite red
before its fixtures are written (docs/languages.md section 10).
"""
import argparse
import ast
import glob
import http.client
import http.server
import importlib.util
import io
import json
import os
import re
import shutil
import threading
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
FIX = os.path.join(HERE, "fixtures")
LIB = os.path.join(ROOT, "lib")
YT = os.path.join(ROOT, "youtube")
YT_LIB = os.path.join(YT, "lib")
STUDIO = os.path.join(ROOT, "markdown")
sys.path.insert(0, LIB)
import runtime as _runtime   # noqa: E402  where the ilya-frank environment is, wherever it was made
CONDA_PY = _runtime.find_env()[1] or os.path.expanduser("~/miniconda3/envs/ilya-frank/bin/python")
PY = CONDA_PY if os.path.exists(CONDA_PY) else sys.executable
for p in (LIB, YT_LIB, os.path.join(STUDIO, "app"), os.path.join(STUDIO, "exlex")):
    if p not in sys.path:
        sys.path.insert(0, p)

FAILS, PASSES, SKIPS = [], [], []


def ok(what):
    PASSES.append(what)
    print("  ok    " + what, flush=True)


def bad(what, detail=""):
    FAILS.append(what + ((" -- " + detail) if detail else ""))
    print("  FAIL  " + what + ((": " + detail[:600]) if detail else ""), flush=True)


def skip(what):
    SKIPS.append(what)
    print("  --    " + what, flush=True)


def check(cond, what, detail=""):
    (ok if cond else lambda w, d="": bad(w, detail))(what)
    return bool(cond)


def run(cmd, cwd=None, env=None, timeout=900):
    e = dict(os.environ)
    e.update(env or {})
    # NOTHING IT STARTS SHARES THIS PROCESS'S STDIN.  `import asrworkspaceworker` is a program: it reads its code from
    # stdin until the end of the file, so where stdin was a terminal or a pipe nobody closed (a loop started from a tool,
    # say) the import check of that module waited its sixty seconds and the whole test died with TimeoutExpired; from a
    # shell with its input redirected it never did
    r = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def bundle_film_at(d):
    import bundle
    return bundle.film_at(d)


def bundle_leaf_ok(name):
    """Would lib/bundle.py let this be a directory in a bundle?"""
    import bundle
    return bool(bundle.LEAF.match(name))


def section(title):
    print("\n== " + title, flush=True)


# ------------------------------------------------------------------ compile
def test_compile():
    section("compile")
    files = []
    # lib/verbs/ is a package, one recipe per language: a recipe that does
    # not compile costs its language every \vb and says so only on the
    # server's stderr, the first time somebody opens a verb
    for pat in ("*.py", "lib/*.py", "lib/verbs/*.py", "youtube/lib/*.py",
                "markdown/app/*.py", "markdown/exlex/*.py", "tests/*.py",
                "tests/fixtures/anki/*.py"):
        files += glob.glob(os.path.join(ROOT, pat))
    rc, out = run([sys.executable, "-m", "py_compile"] + files)
    check(rc == 0, "%d Python files compile" % len(files), out)
    rc, out = run(["sh", "-n", os.path.join(ROOT, "build.sh")])
    check(rc == 0, "build.sh parses", out)
    rc, out = run(["sh", "-n", os.path.join(ROOT, "install.sh")])
    check(rc == 0, "install.sh parses", out)


def test_js():
    section("js")
    deno = (shutil.which("deno") or _runtime.tool("deno", _runtime.find_env()[0])
            or os.path.expanduser("~/miniconda3/envs/ilya-frank/bin/deno"))
    if not os.path.exists(deno):
        skip("no deno: page scripts not parsed")
        return
    scripts = {
        "lib/parseh.js": open(os.path.join(LIB, "parseh.js"), encoding="utf-8").read(),
        "lib/llm.js": open(os.path.join(LIB, "llm.js"), encoding="utf-8").read(),
        "lib/llmrow.js": open(os.path.join(LIB, "llmrow.js"), encoding="utf-8").read(),
        "lib/decomposition.js": open(os.path.join(LIB, "decomposition.js"), encoding="utf-8").read(),
        "lib/cardkit.js": open(os.path.join(LIB, "cardkit.js"), encoding="utf-8").read(),
        "youtube/lib/player.js": open(os.path.join(YT_LIB, "player.js"), encoding="utf-8").read(),
        "youtube/lib/tabcapture.js": open(os.path.join(YT_LIB, "tabcapture.js"), encoding="utf-8").read(),
        "studio app.js": open(os.path.join(STUDIO, "app", "static", "app.js"), encoding="utf-8").read(),
    }
    # the exercise decks' pages: loaded after app.js, whose globals it uses
    decks_js = os.path.join(STUDIO, "app", "static", "decks.js")
    if os.path.isfile(decks_js):
        scripts["studio decks.js"] = open(decks_js, encoding="utf-8").read()
    else:
        bad("markdown/app/static/decks.js is missing: the exercise deck pages have no script")
    # the reader's script is baked into every built reader
    import books
    import tex2html
    scripts["reader JS (tex2html.JS)"] = tex2html.JS
    import ytpages
    m = re.search(r"<script>(.*?)</script>", ytpages.ADD_PAGE_JS, re.S)
    if m:
        scripts["youtube add page JS"] = m.group(1).replace("__BASE__", '"/youtube"')
    import newbook
    page = newbook.page()
    for m in re.finditer(r"<script>(.*?)</script>", page, re.S):
        scripts["books add page JS"] = m.group(1)
    for name, src in scripts.items():
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            # a syntax check only: the body is compiled, never run
            f.write("new Function(%s);\n" % json.dumps(src))
            path = f.name
        try:
            rc, out = run([deno, "run", "--quiet", path], timeout=120)
            check(rc == 0, "%s parses" % name, out)
        finally:
            os.unlink(path)


def test_theme():
    """The one theme preference: the button cycles three palettes, the sepia
    one is defined, and nothing dark reaches a page wearing it."""
    section("theme")
    css = open(os.path.join(LIB, "parseh.css"), encoding="utf-8").read()
    js = open(os.path.join(LIB, "parseh.js"), encoding="utf-8").read()
    check("var ORDER = ['light', 'dark', 'sepia'];" in js,
          "the button cycles light / dark / sepia")
    check(":root[data-theme=sepia]{" in css,
          "lib/parseh.css defines the sepia palette")
    # sepia is a paper: it restates the ground and the ink, and leaves the
    # accent, the danger red and the good/warn pair to the light theme
    m = re.search(r":root\[data-theme=sepia\]\{(.*?)\}", css, re.S)
    body = m.group(1) if m else ""
    for tok in ("--bg", "--card", "--ink", "--dim", "--faint", "--rule", "--hl", "--boxbg"):
        check(tok + ":" in body, "sepia restates %s" % tok, body[:200])
    for tok in ("--accent", "--danger", "--ok:", "--warn"):
        check(tok not in body, "sepia leaves %s to the light theme" % tok.rstrip(":"))
    # a dark rule guarded only against [data-theme=light] would still catch
    # sepia, and the page would come out half dark
    import tex2html
    mcss = open(os.path.join(LIB, "mobile.css"), encoding="utf-8").read()
    for name, src in (("lib/parseh.css", css), ("lib/mobile.css", mcss),
                      ("the reader's sheet", tex2html.CSS)):
        bad = [ln.strip() for ln in src.splitlines()
               if "data-theme=light]" in ln and "data-theme=sepia]" not in ln]
        check(not bad, "%s: every dark rule excludes sepia too" % name, " | ".join(bad)[:300])
    # the studio's sheet has the same three, and follows the shared choice
    app_js = open(os.path.join(STUDIO, "app", "static", "app.js"), encoding="utf-8").read()
    # the sheet and the chrome: /studio/static/app.css answers with both,
    # and since the split (2026-09-23) the disk holds them apart
    app_css = "".join(open(os.path.join(STUDIO, "app", "static", n), encoding="utf-8").read()
                      for n in ("sheet.css", "app.css"))
    check('body[data-theme="sepia"]' in app_css, "the studio still has its sepia sheet")
    check('s === "sepia"' in app_js or 's === "dark" || s === "sepia"' in app_js,
          "the studio's sheet follows the shared theme into sepia")


def _ids_referenced(js):
    ids = set()
    # '#id' selectors, and getElementById('id'); a tag selector ('header',
    # 'rt') is not an id and is left alone
    for m in re.finditer(r"""(?:\$|querySelector|\$\$)\(\s*['"]#([A-Za-z][\w-]*)['"]""", js):
        ids.add(m.group(1))
    for m in re.finditer(r"""getElementById\(\s*['"]([A-Za-z][\w-]*)['"]""", js):
        ids.add(m.group(1))
    return ids


def _ids_defined(*sources):
    ids = set()
    for src in sources:
        for m in re.finditer(r"""\bid\s*=\s*['"]([A-Za-z][\w-]*)['"]""", src):
            ids.add(m.group(1))
        for m in re.finditer(r"""\.id\s*=\s*['"]([A-Za-z][\w-]*)['"]""", src):
            ids.add(m.group(1))
    return ids


def test_reading_place():
    """The mark on a subparagraph moves whether or not there is a narration.

    A string check, because it is the only kind this suite can make about a
    page's behaviour without a browser -- and this is a bug it could not
    otherwise catch, having been exactly that: `playSub` returned before it
    highlighted when the subparagraph had no time, and the click handler
    skipped a subparagraph marked `noaudio`, so in a book nobody had recorded
    -- which is every book on its first day -- the reading place could not be
    moved by any means at all.  Both are named here so that a rewrite that
    puts either back says so.
    """
    section("the reading place")
    import tex2html
    js, css = tex2html.JS, tex2html.CSS
    check("if (t[0] == null) { previewing = false" in js,
          "playSub selects first and only then asks whether there is audio")
    check("sub.classList.contains('noaudio')" not in js,
          "a click selects the subparagraph it lands in, timed or not")
    check("function nextStop(" in js and "nextStop(cur + 1, 1)" in js,
          "the arrows walk the text where nothing ahead is timed")
    check(".sub.noaudio{cursor:default}" not in css,
          "an untimed subparagraph still looks like something to click")
    # the reader's own state is the reader's, and this book's is this book's
    check("const MINE = (k) => 'bk_' + k + ':' + location.pathname;" in js,
          "where you are and the unsaved times are filed per book")
    for k in ("'bk_pos'", "'bk_edits'", "'bk_at'"):
        check(k not in js, "nothing is stored under the shared name %s" % k)


def test_dom():
    """Every element id a page script asks for by '#id' / getElementById
    exists in the page it runs in (or is made by the script itself)."""
    section("dom ids")
    import tex2html
    import ytpages
    pairs = []
    # THE PAGE THIS tex2html.py BUILDS, and not whatever an earlier run left
    # in the fixture's reader/: that is built by a later section, so every id
    # a change to the script added read as missing -- from a page built before
    # the change -- until the run after.  A copy is built here, now.
    with tempfile.TemporaryDirectory() as td:
        book = os.path.join(td, "mini-ja")
        shutil.copytree(os.path.join(FIX, "books", "japanese", "mini-ja"), book,
                        ignore=shutil.ignore_patterns("reader", ".reader-key"))
        rc, out = run([sys.executable, os.path.join(LIB, "tex2html.py"), "--book", book], cwd=book)
        reader = os.path.join(book, "reader", "index.html")
        if rc == 0 and os.path.exists(reader):
            html = open(reader, encoding="utf-8").read()
            pairs.append(("reader page (mini-ja)", tex2html.JS, html))
        else:
            bad("reader page (mini-ja): built for its ids", out[-400:])
    player = open(os.path.join(YT_LIB, "player.html"), encoding="utf-8").read()
    pairs.append(("player page", open(os.path.join(YT_LIB, "player.js"), encoding="utf-8").read(), player))
    tpl = os.path.join(STUDIO, "app", "templates")
    studio_html = "".join(open(os.path.join(tpl, n), encoding="utf-8").read()
                          for n in ("index.html", "doc.html", "edit.html", "prompt.html"))
    pairs.append(("studio pages (all templates)", open(os.path.join(STUDIO, "app", "static", "app.js"),
                                                       encoding="utf-8").read(), studio_html))
    # the exercise decks' four pages share decks.js, as the studio's share app.js
    deck_pages = [os.path.join(tpl, n) for n in ("decks.html", "deck.html", "study.html", "cram.html")]
    decks_js = os.path.join(STUDIO, "app", "static", "decks.js")
    missing = [os.path.relpath(p, ROOT) for p in deck_pages + [decks_js] if not os.path.isfile(p)]
    if missing:
        bad("exercise deck pages: every id decks.js asks for exists", "missing " + ", ".join(missing))
    else:
        pairs.append(("exercise deck pages (decks, deck, study, cram)",
                      open(decks_js, encoding="utf-8").read(),
                      "".join(open(p, encoding="utf-8").read() for p in deck_pages)))
    pairs.append(("youtube add page", ytpages.ADD_PAGE_JS, ytpages.add_page()))
    for name, js, html in pairs:
        missing = sorted(_ids_referenced(js) - _ids_defined(html, js))
        check(not missing, "%s: every id the script asks for exists" % name, ", ".join(missing))


# ------------------------------------------------------------------ registry
def test_registry():
    section("registry")
    import languages
    # the four the toolbox was built for lead, in registry order; a language
    # added later sits after them and must not fail this run (lib/newlang.py
    # --check is what proves the registry itself is sound, below)
    codes = list(languages.LANGS)
    check(codes[:4] == ["fa", "ar", "it", "ja"],
          "the original four languages, in registry order (%d in all)" % len(codes),
          ", ".join(codes))
    check(languages.get("ja").reading and languages.get("ja").vertical, "Japanese has a reading and a vertical pass")
    check(languages.get("it").run_re is None, "Italian has no script detection")
    check(languages.get("fa").strip("دَر") == "در", "Persian strips harakat")
    css = languages.css()
    check("--tl-font-ja" in css and "[data-lang=ar]" in css, "langs.css carries every language")
    check('data-lang="ja"' in languages.chips_html({"ja": 1}), "chip row marks chips with data-lang")
    # The \vb line teaches grammar, and it is written twice: lib/lang/<code>.tex
    # prints \FrankVbPres / \FrankVbPast in the PDF, the registry hands the same
    # pair to the reader.  A book whose two halves disagree teaches two
    # grammars, so the labels the reader renders are compared here with the
    # ones its own .tex sets, for every language and not only the ones with a
    # fixture (docs/languages.md section 12).
    import newlang
    import texparse as T
    drift = []
    for code in languages.CODES:
        printed = [txt.replace("\u00b7", "").strip() for kind, txt
                   in T.parse_voc("\\vb{a}{}{b}{}{c}{}{}", code) if kind == "txt"]
        if printed != list(newlang.tex_vb_labels(code)):
            drift.append("%s: the reader prints %s, lib/lang/%s.tex sets %s"
                         % (code, printed, code, list(newlang.tex_vb_labels(code))))
    check(not drift, "every language's reader prints the \\vb labels its .tex sets "
                     "(%s)" % ", ".join("%s %s/%s" % ((c,) + newlang.tex_vb_labels(c))
                                        for c in languages.CODES),
          "; ".join(drift))
    # AND BOTH HALVES SAY WHAT WAS DECIDED.  The drift test above holds the
    # two to each other, which a change made to both at once passes: Turkish
    # printed `stem` where its second form is now the -iyor present, Spanish
    # `past` over a slot that is now the third-person preterite, and Chinese
    # pres./past over a verb that has neither.  A language added later is
    # not in this table and is not asked (lib/newlang.py --check is).
    VB_LABELS = {"fa": ("pres.", "past"), "ar": ("impf.", "masdar"),
                 "it": ("pres.", "p.p."), "ja": ("stem", "-te"),
                 "fr": ("pres.", "p.p."), "de": ("pret.", "p.p."),
                 "tr": ("pres.", "aor."), "en": ("past", "p.p."),
                 "hi": ("stem", "perf."), "es": ("pres.", "pret."),
                 "zh": ("split", "can't")}
    off = ["%s: registry %s, .tex %s, want %s"
           % (c, tuple(languages.get(c).vb_labels), newlang.tex_vb_labels(c), want)
           for c, want in VB_LABELS.items() if c in languages.CODES
           and (tuple(languages.get(c).vb_labels) != want
                or tuple(newlang.tex_vb_labels(c)) != want)]
    check(not off, "the \\vb labels are the settled ones, in the registry and in "
                   "every .tex (tr pres./aor., es pres./pret., zh split/can't)",
          "; ".join(off))
    # WHAT THE THREE FORMS ARE, in words, for the chunk editor's \vb button:
    # it said "infinitive, pres. stem, past stem" in every book, which is
    # Persian's \vb and nobody else's.  Read from the registry's own file, so
    # the default languages.py fills in for a row without one cannot pass
    # for a row that has it.  Both of the registry's files, as languages.py
    # reads them: a language added on this machine is in config/languages.json.
    raw = languages.read_rows()[0]
    forms_off = [c for c in languages.CODES
                 if not (isinstance((raw.get(c) or {}).get("vb_forms"), list)
                         and len(raw[c]["vb_forms"]) == 3
                         and all(isinstance(s, str) and s.strip()
                                 for s in raw[c]["vb_forms"]))]
    check(not forms_off, "every language names the three forms of its \\vb "
                         "(vb_forms: three words each, %d languages)"
                         % len(languages.CODES), ", ".join(forms_off))
    check(all(languages.get(c).as_json().get("vb_forms") == raw[c]["vb_forms"]
              for c in languages.CODES if c not in forms_off),
          "and the page each reader embeds carries them (as_json)")
    # THE LEVELS' NAMES (a0.5.0): every pass of every language carries the word
    # its button wears, 1 to 12 characters and no two alike in a language, and
    # the page each reader embeds carries them; the settled ones are pinned
    # for the languages Parseh ships (a language added later is asked only for
    # a valid name -- tests/test_level_names.py holds the table, the refusals
    # and the rule that names a new language's passes)
    LEVELS = {"fa": "With vowels/Chunks/Plain/Nastaliq", "ar": "With vowels/Chunks/Plain",
              "ja": "Furigana/Kana only/Chunks/Plain/Vertical",
              "zh": "Pinyin/Pinyin only/Chunks/Plain/Vertical"}
    LEVELS.update({c: "Sentence/Chunks" for c in ("it", "fr", "de", "tr", "en", "hi", "es")})
    unnamed = [c for c in languages.CODES
               if languages.level_name_problems(languages.get(c).passes)
               or [p.get("name") for p in languages.get(c).as_json()["passes"]]
               != [p["name"] for p in languages.get(c).passes]]
    check(not unnamed, "every language's passes carry a valid name (%d languages)"
                       % len(languages.CODES), ", ".join(unnamed))
    off = ["%s: %s" % (c, "/".join(p["name"] for p in languages.get(c).passes))
           for c, want in LEVELS.items() if c in languages.CODES
           and "/".join(p["name"] for p in languages.get(c).passes) != want]
    check(not off, "the levels are named as the owner settled (fa With vowels/Chunks/Plain/"
                   "Nastaliq, ja Furigana/Kana only/..., zh Pinyin/Pinyin only/..., "
                   "the rest Sentence/Chunks)", "; ".join(off))
    import tex2html
    was_lang = tex2html.LANG
    try:
        tex2html.set_lang("ja")
        sheet = tex2html.chunk_editor("")
    finally:
        tex2html.LANG = was_lang
    check("dictionary form · -masu stem · -te form" in sheet,
          "the book's \\vb button says its own language's three forms "
          "(Japanese: dictionary form · -masu stem · -te form)")
    # A VIDEO'S ARABIC IS WRITTEN AS ITS CAPTIONS ARE, without the harakat,
    # while the book's \vb keeps every mark; no other language asks.
    bare = sorted(c for c in languages.CODES if languages.get(c).vb_video_bare)
    check(bare == (["ar"] if "ar" in languages.CODES else []),
          "a video's \\vb line is written bare for Arabic and for nobody else "
          "(vb_video_bare)", repr(bare))
    # the other half of "did I forget something" when a language is added:
    # every registry entry's files, folders, fonts, ids and character class
    rc, out = run([sys.executable, os.path.join(LIB, "newlang.py"), "--check"], cwd=ROOT)
    check(rc == 0, "lib/newlang.py --check finds no fault in the registry", out[-700:])


# ------------------------------------------------------------------ books
def fixture_books():
    import books
    return [books.Book(d) for d in sorted(glob.glob(os.path.join(FIX, "books", "*", "*")))
            if os.path.isfile(os.path.join(d, "book.json"))]


# The gloss's three lines are leaf divs -- the transliteration, the vocabulary
# and the English -- so a non-greedy match takes each whole and nothing else.
GLOSS_LINE = re.compile(r'<div class="(?:tr|voc|en)">(.*?)</div>')


def gloss_leaks(html):
    """Every LaTeX control word left in a built reader's glosses.

    The vocabulary field is LaTeX, and the reader must print what it means,
    not what it says: a \\textit or a \\pw reaching the page is source
    shown to the reader (it did, out of the free-text slots of \\vb and
    \\bw, until texparse parsed those like the rest of the line)."""
    return [m for line in GLOSS_LINE.findall(html)
            for m in re.findall(r"\\[a-zA-Z]+", line)]


def occurrence_drift(md, html):
    """Runs the page numbers differently from the way the store finds them.

    The hover palette addresses a run by (text, occurrence), so the moment the
    page's list and the source's list differ an edit lands on the wrong copy
    of the word.  Used on the example documents and on every starter."""
    import html as _html
    import store as _store
    _store._target_of(md)
    occs = {}
    for fa_t, occ in re.findall(r'data-fa="([^"]*)" data-occ="(\d+)"', html):
        occs.setdefault(_html.unescape(fa_t), []).append(int(occ))
    out = []
    for fa_t, lst in occs.items():
        hits = _store._run_matches(md, fa_t)
        if len(hits) != len(lst) or sorted(lst) != list(range(len(lst))):
            out.append("%s: page %s, source %d hits" % (fa_t, lst, len(hits)))
    return out


def para_json_from_tex(book, n=0):
    """Paragraph n of chapter 1 of a book, in the annotator's JSON shape,
    read back out of the built .tex with texparse."""
    import texparse as T
    chapters = T.parse_book(book.main, book.lang) if "lang" in T.parse_book.__code__.co_varnames \
        else T.parse_book(book.main)
    ch = chapters[0]
    para = ch.paragraphs[n]
    sents = []
    for s in para.subs:
        chunks = []
        for c in s.chunks:
            d = {"fa": c.fa, "tr": c.tr, "voc": c.voc, "en": c.en}
            if getattr(c, "kana", ""):
                d["kana"] = c.kana
            # the word line too: a reading proposed from the words (a drafted
            # chunk's, in a language divided into words) makes a chunk no
            # less blank only beside the words it was proposed from
            if getattr(c, "wordline", ""):
                d["words"] = c.wordline
            chunks.append(d)
        sents.append({"chunks": chunks})
    return {"idx": n, "ch": 1, "ann": {"sentences": sents}}


def texwrite_copy(book, td):
    """The editable files of a book, in a scratch directory.

    texwrite writes, and nothing in this suite may write under books/ or
    tests/fixtures/.  main.tex comes too, because the chapter ORDER is read
    from its \\input lines and nowhere else; the preamble it also inputs is
    not there and is not wanted -- book_chapters skips an input that is
    missing, exactly as texparse.parse_book does."""
    # every target gets its own directory inside the one scratch tree, and a
    # book on the shelf may share a slug with a fixture: the suite must not
    # die of a name collision it can just step around
    d, n = os.path.join(td, book.slug), 0
    while os.path.exists(d):
        n += 1
        d = os.path.join(td, "%s-%d" % (book.slug, n))
    os.makedirs(d)
    for p in glob.glob(os.path.join(book.dir, "ch*.tex")) + \
            [book.main, os.path.join(book.dir, "book.json")]:
        shutil.copy(p, d)
    if os.path.isdir(book.paras_dir):
        shutil.copytree(book.paras_dir, os.path.join(d, "source", "paras"))
    return d


def narrate(src, into):
    """A copy of a fixture edition with a narration on it, in a scratch
    directory.  -> its path

    Every place a book refers to a recording, so that the three shapes have
    all of them to differ over: the two book.json fields, the alignment and
    the review beside it, what the reader saves back into the review, the
    audio/ directory, and a `% @par` line above each subparagraph -- which is
    the one that hides inside a file every shape carries.  The recording is
    twenty bytes: this is about which files move, and a real one is the one
    thing a test may not invent.
    """
    d = os.path.join(into, os.path.basename(src))
    shutil.copytree(src, d, ignore=shutil.ignore_patterns(
        "reader", "main.pdf", "main.aux", "main.log", "main.toc", ".*-key"))
    os.makedirs(os.path.join(d, "audio"), exist_ok=True)
    with open(os.path.join(d, "audio", "audio.webm"), "wb") as f:
        f.write(b"\x1aE\xdf\xa3 not a recording")
    for rel, body in (("audio/transcript.txt", "what was said\n"),
                      ("timings.json", json.dumps(
                          {"audio": "audio/audio.webm", "book": "x",
                           "generated_by": "timestamp.py",
                           "subs": {"1.1-0": {"t0": 0.0, "t1": 1.0, "conf": 1.0,
                                              "src": "manual", "label": "1.1"}}})),
                      ("review.json", json.dumps({"audio": "audio/audio.webm",
                                                  "items": []})),
                      ("review-corrections.json", json.dumps({"1.1-0": {"t0": 0.5}})),
                      ("review.html", "<!doctype html><script>alert(1)</script>")):
        with open(os.path.join(d, rel), "w", encoding="utf-8") as f:
            f.write(body)
    # A SECOND RECORDING, covering the rest of the book.  A book can be read a
    # part at a time, and the shapes have to move every part of it: with one
    # recording a dropped file is invisible to every check below, because the
    # scalars cannot say there was more than one.
    with open(os.path.join(d, "audio", "part2.webm"), "wb") as f:
        f.write(b"\x1aE\xdf\xa3 nor is this")
    meta = json.load(open(os.path.join(d, "book.json"), encoding="utf-8"))
    meta["audio"], meta["transcript"] = "audio/audio.webm", "audio/transcript.txt"
    # the scalars go on naming the FIRST, which is what every tool that has
    # only ever known one recording reads
    meta["narrations"] = [
        {"id": "n1", "audio": "audio/audio.webm",
         "transcript": "audio/transcript.txt", "from": "", "to": "1.1"},
        {"id": "n2", "audio": "audio/part2.webm", "transcript": "",
         "from": "1.2", "to": ""}]
    with open(os.path.join(d, "book.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    for tex in sorted(glob.glob(os.path.join(d, "ch*.tex"))):
        out, n = [], 0
        for line in open(tex, encoding="utf-8").read().split("\n"):
            if line.startswith("\\begin{frank}"):
                n += 1
                out.append("%% @par 1.%d %.2f %.2f 1.00 anchor" % (n, n, n + 1))
            out.append(line)
        open(tex, "w", encoding="utf-8").write("\n".join(out))
    return d


def bundle_state(d):
    """What a book on disk says about its narration, in one comparable dict."""
    import books as booklib
    meta = json.load(open(os.path.join(d, "book.json"), encoding="utf-8"))
    return {"has_audio": booklib.Book(d).has_audio,
            "audio": meta.get("audio"), "transcript": meta.get("transcript"),
            # a book recorded in parts: the list is as much a pointer at a
            # recording as the scalars are, so a shape that leaves it behind
            # is a shape that lies about what the book still names
            "narrations": [r.get("audio") for r in (meta.get("narrations") or [])],
            "files": sorted(f for f in ("timings.json", "review.json",
                                        "review-corrections.json", "review.html")
                            if os.path.exists(os.path.join(d, f))),
            "audio_dir": sorted(os.listdir(os.path.join(d, "audio")))
                         if os.path.isdir(os.path.join(d, "audio")) else [],
            "par": sum(1 for t in sorted(glob.glob(os.path.join(d, "ch*.tex")))
                       for ln in open(t, encoding="utf-8") if ln.startswith("% @par"))}


def tree_bytes(d):
    """Every file under d, relative path -> bytes: for "the same book"."""
    out = {}
    for root, dirs, files in os.walk(d):
        dirs.sort()
        for fn in sorted(files):
            p = os.path.join(root, fn)
            out[os.path.relpath(p, d).replace(os.sep, "/")] = open(p, "rb").read()
    return out


def test_bundle_shapes(book):
    """lib/bundle.py's three shapes of a narrated book.

    A narration is the one thing in this toolbox that cannot be made again,
    and the three shapes are three answers to how much of it travels.  What
    has to hold: `text` leaves NOTHING pointing at a recording (the reader
    must open such a book with its audio controls absent, exactly as for a
    book that never had one, and books.Book.has_audio is what decides that);
    `linked` plus the audio/ directory is the `full` book, file for file;
    and a `text` bundle landing on a book that still has its narration does
    not cost anybody the recording.
    """
    import bundle
    check(bundle.AUDIO_EXTS == serve_audio_exts(),
          "bundle and serve.py agree on what a recording may be",
          "%r vs %r" % (bundle.AUDIO_EXTS, serve_audio_exts()))
    with tempfile.TemporaryDirectory() as td:
        # a book with no narration: the choice cannot matter, and does not.
        # The manifest's `exported` is a wall clock and is the one field two
        # packs of anything differ by, so it is taken out before the compare
        # -- everything else, including the file list and the filename, has
        # to be identical.
        def guts(data):
            z = zipfile.ZipFile(io.BytesIO(data))
            out = {n: z.read(n) for n in sorted(z.namelist())}
            man = json.loads(out[bundle.MANIFEST].decode())
            man.pop("exported", None)
            out[bundle.MANIFEST] = json.dumps(man, sort_keys=True).encode()
            return out
        plain = {m: bundle.pack_book(book.dir, m) for m in bundle.MODES}
        names = {fn for _d, fn in plain.values()}
        same = all(guts(plain[m][0]) == guts(plain[bundle.MODES[0]][0])
                   for m in bundle.MODES)
        check(same and len(names) == 1,
              "a book with no narration is the same bundle in all three shapes",
              "same contents: %s, names %s" % (same, names))
        w = bundle.inspect(plain["text"][0])
        check(w["audio"] == bundle.DEFAULT_MODE and "audio" not in json.loads(
                  zipfile.ZipFile(io.BytesIO(plain["text"][0])).read(bundle.MANIFEST)),
              "and its manifest names no shape at all, so it reads as the default",
              w["audio"])

        src = narrate(book.dir, td)
        zips = {}
        for m in bundle.MODES:
            data, fname = bundle.pack_book(src, m)
            zips[m] = data
            check(fname.endswith("-%s.zip" % m),
                  "a narrated book's %s bundle says so in its filename" % m, fname)
        bases, roots = {}, {}
        for m in bundle.MODES:
            bases[m] = os.path.join(td, "root-" + m)
            os.makedirs(bases[m])
            r = bundle.install(zips[m], root=bases[m])
            check(r["audio"] == m, "install reads the %s shape back off the manifest" % m,
                  r["audio"])
            roots[m] = os.path.join(bases[m], r["dir"])
        was = bundle_state(src)
        text, linked, full = (bundle_state(roots[m]) for m in bundle.MODES)
        check(text == {"has_audio": False, "audio": None, "transcript": None,
                       "narrations": [], "files": [], "audio_dir": [], "par": 0},
              "text: nothing is left pointing at a narration, and has_audio is False",
              repr(text))
        check(full["has_audio"] and full["audio"] == was["audio"]
              and full["par"] == was["par"]
              and full["audio_dir"] == ["audio.webm", "part2.webm", "transcript.txt"],
              "full: every recording, the timings and the comments all arrive", repr(full))
        check(full["narrations"] == was["narrations"]
              and len(full["narrations"]) == 2,
              "full: a book recorded in parts arrives with both parts named",
              repr(full["narrations"]))
        check(not linked["has_audio"] and linked["audio"] == was["audio"]
              and linked["par"] == was["par"] and linked["audio_dir"] == [],
              "linked: everything but the recording, and the book still names it",
              repr(linked))
        check(linked["narrations"] == was["narrations"],
              "linked: and it still names every part of it", repr(linked["narrations"]))
        check(all("review.html" not in s["files"] for s in (text, linked, full)),
              "no shape installs review.html: a bundle may not carry a page")

        # the promise `linked` makes, tested as the promise is worded
        shutil.copytree(os.path.join(src, "audio"),
                        os.path.join(roots["linked"], "audio"))
        a, b = tree_bytes(roots["linked"]), tree_bytes(roots["full"])
        check(a == b, "linked + audio/ is the full book, file for file",
              "%d vs %d files; differing: %s"
              % (len(a), len(b), sorted(set(a) ^ set(b))
                 or [k for k in a if a.get(k) != b.get(k)][:3]))

        # the case somebody could lose a recording to: the `full` install is
        # a narrated book on this machine, and the `text` bundle of the same
        # book is uploaded over it with replace
        before = bundle_state(roots["full"])
        r = bundle.install(zips["text"], replace=True, root=bases["full"])
        kept = bundle_state(roots["full"])
        check(kept["has_audio"] and kept["audio"] == before["audio"]
              and kept["transcript"] == before["transcript"]
              and kept["audio_dir"] == before["audio_dir"]
              and kept["files"] == before["files"],
              "a text bundle over a narrated book keeps the narration, and book.json "
              "names it again", repr(kept))

        # WHAT A REPLACE MUST NOT KEEP.  Everything the shape does not own
        # used to be carried across, which is right for a recording -- it
        # cannot be made again -- and wrong for anything made FROM the text,
        # because the text has just been replaced.  You brought a book back,
        # built it, and opened a reader made from the book you had replaced;
        # and could not get rid of it, because .reader-key came over too and
        # build.sh reads that key to decide the reader is current.  Where the
        # old copy had lived at another depth it was worse than stale: a
        # reader built under books/<slug>/ links ../../../lib/parseh.css,
        # which from books/<language>/<slug>/ is one level short, so every
        # stylesheet 404s and the book opens unstyled and dead.
        d = roots["full"]
        os.makedirs(os.path.join(d, "reader"), exist_ok=True)
        io.open(os.path.join(d, "reader", "index.html"), "w",
                encoding="utf-8").write("STALE READER")
        for f in (".reader-key", ".build-key", "main.pdf", "frankdraft.tex"):
            io.open(os.path.join(d, f), "w", encoding="utf-8").write("stale")
        was_audio = bundle_state(d)["audio"]
        r2 = bundle.install(zips["linked"], replace=True, root=bases["full"])
        left = sorted(f for f in (".reader-key", ".build-key", "main.pdf",
                                  "frankdraft.tex", "reader")
                      if os.path.exists(os.path.join(d, f)))
        check(not left, "a replace throws away what was made from the text it "
                        "replaced (the reader, the keys, the PDF)", repr(left))
        check(any("thrown away" in n for n in r2.get("notes", [])),
              "and says so, so nobody wonders where the reader went",
              repr(r2.get("notes")))
        check(bundle_state(d)["audio"] == was_audio,
              "while the recording, which cannot be made again, stays")
        check(any("timestamp.py --from-sidecar" in n for n in r["notes"]),
              "and says how to put the comments back", "; ".join(r["notes"])[:200])
        check(open(os.path.join(roots["full"], "audio", "audio.webm"), "rb").read()
              == open(os.path.join(src, "audio", "audio.webm"), "rb").read()
              and open(os.path.join(roots["full"], "timings.json"), "rb").read()
              == open(os.path.join(src, "timings.json"), "rb").read(),
              "the recording and the timings are byte for byte the ones that were there")


def serve_audio_exts():
    """serve.py's own list, read from the file rather than by importing the
    server into this process."""
    src = open(os.path.join(ROOT, "serve.py"), encoding="utf-8").read()
    m = re.search(r"^AUDIO_EXTS = (\(.*?\))", src, re.S | re.M)
    return ast.literal_eval(m.group(1)) if m else None


def test_texwrite(targets):
    """lib/texwrite.py: the module under the reader's edit box.

    Two things have to hold.  texwrite and texparse must number the chunks
    the same way, because the reader addresses a chunk by the number texparse
    gave it and hands that number back.  And an edit has to be surgical: one
    line of a hand-written chapter differs and not one byte else, since the
    comments, the blank lines and the line breaks in a long gloss are the
    author's and cannot be re-emitted from the chunks."""
    import tex2html
    import texparse as T
    import texwrite as X
    check({v: k for k, v in X.COLOURS.items()} == tex2html.HL,
          "texwrite and tex2html name the four colours the same way",
          "%s vs %s" % (X.COLOURS, tex2html.HL))
    with tempfile.TemporaryDirectory() as td:
        for n, b in enumerate(targets):
            tag = "%s [%s]" % (b.slug, b.lang.code)
            path = X.book_chapters(texwrite_copy(b, td))[0]["path"]
            mine = X.read_chunks(path)
            theirs = [c for p in T.parse_chapter(path, b.lang).paragraphs
                      for s in p.subs for c in s.chunks]
            check(len(mine) == len(theirs) and len(mine) > 0
                  and all(m["fa"] == t.fa and m["kana"] == t.kana and m["voc"] == t.voc
                          and m["col_tex"].strip() == t.col and m["line"] == t.line
                          for m, t in zip(mine, theirs)),
                  "%s: texwrite numbers and reads the chunks exactly as texparse does" % tag,
                  "%d vs %d chunks" % (len(mine), len(theirs)))
            i = max(k for k, c in enumerate(mine) if c["glossed"])
            before = open(path, encoding="utf-8").read().split("\n")
            X.edit_chunk(path, i, {"en": "edited by the smoke test", "col": "green"})
            after = open(path, encoding="utf-8").read().split("\n")
            back = X.read_chunks(path)[i]
            differ = [k for k in range(min(len(before), len(after))) if before[k] != after[k]]
            check(len(before) == len(after) and differ == [mine[i]["line"]]
                  and back["en"] == "edited by the smoke test" and back["col"] == "green",
                  "%s: an edit rewrites one chunk's line and no other byte" % tag,
                  "lines %s differ, wanted [%d]" % (differ, mine[i]["line"]))
            # the refusals do not depend on the language, so they are tried
            # once: an fa that would stop the paragraph reproducing its source
            # (what verify_book.py checks) and a colour that is not one of four
            if n == 0:
                refused = 0
                for bad_fields in ({"fa": mine[i]["fa"] + "zz"}, {"col": "purple"},
                                   {"en": "100% sure"}, {"notes": "hello"}):
                    try:
                        X.edit_chunk(path, i, bad_fields)
                    except X.Refused:
                        refused += 1
                check(refused == 4, "%s: texwrite refuses a broken fa, an unknown "
                      "colour, a per cent sign and a field that does not exist" % tag,
                      "%d of 4 refused" % refused)


def test_books(pdf):
    section("books")
    import books
    import languages
    # books/ ships empty: a book there is the owner's, not the software's.
    # Whatever is on the shelf is read exactly as a fixture is, and its filing
    # checked; an empty shelf is a skip that names the loss, not a failure.
    real = books.all_books()
    for b in real:
        check(b.folder == b.lang.folder,
              "%s is filed under books/%s/" % (b.slug, b.lang.folder))
    if not real:
        skip("no book under books/: only the fixture editions are tried")
    fixtures = fixture_books()
    # no count is written here: how many languages there are is the registry's
    # business.  A language whose fixture edition has not been written yet is
    # a skip and not a failure -- the smoke test only tries what it has a
    # fixture for (docs/languages.md section 10)
    covered = [b.lang.code for b in fixtures]
    check(len(set(covered)) == len(covered),
          "%d fixture editions, one per language (%s)"
          % (len(fixtures), ", ".join(b.rel_from_books() for b in fixtures)))
    for code in languages.CODES:
        if code not in covered:
            skip("no fixture edition for %s: the books door is not covered" % code)
    targets = real + fixtures
    for b in targets:
        L = b.lang
        tag = "%s [%s]" % (b.slug, L.code)
        # texparse reads it
        try:
            import texparse as T
            chs = T.parse_book(b.main)
            nchunks = sum(len(s.chunks) for ch in chs for s in ch.subs)
            check(nchunks > 0, "%s: texparse reads %d chunks" % (tag, nchunks))
            if L.reading:
                kanas = [c.kana for ch in chs for s in ch.subs for c in s.chunks if c.glossed]
                check(all(kanas), "%s: every glossed chunk carries kana" % tag)
        except Exception as e:
            bad("%s: texparse" % tag, repr(e))
            continue
        # the reader
        rc, out = run([sys.executable, os.path.join(LIB, "tex2html.py"), "--book", b.dir], cwd=b.dir)
        if not check(rc == 0, "%s: tex2html builds the reader" % tag, out):
            continue
        html = open(b.reader_html, encoding="utf-8").read()
        check('data-lang="%s"' % L.code in html and 'dir="%s"' % L.dir in html,
              "%s: reader carries data-lang and dir" % tag)
        check("langs.css" in html, "%s: reader links langs.css" % tag)
        leaks = gloss_leaks(html)
        check(not leaks, "%s: no LaTeX left in the reader's glosses" % tag,
              ", ".join(sorted(set(leaks))))
        keys = L.pass_keys
        check(('class="pass p3' in html) == ("bare" in keys), "%s: bare pass present iff the language has one" % tag)
        check(('class="pass p4' in html) == ("alt" in keys), "%s: alt pass present iff the language has one" % tag)
        if L.reading:
            check("<ruby>" in html and "<rt>" in html, "%s: pass 1 sets ruby" % tag)
            check('class="kana"' in html, "%s: the gloss has a kana line" % tag)
        if L.alt_pass and L.alt_pass.get("kind") == "vertical":
            check("vert" in html and "vertical-rl" in html, "%s: pass 4 is vertical" % tag)
        if L.code == "ar":
            check(re.search(r"[\u0660-\u0669]", html) is not None, "%s: Arabic digits in the labels" % tag)
        m = re.search(r"const META=(\{.*?\});", html, re.S)
        meta = json.loads(m.group(1)) if m else {}
        check(meta.get("lang") == L.code and meta.get("chunks") == nchunks,
              "%s: META has lang and the chunk count" % tag, json.dumps(meta)[:200])
        # fidelity of the whole book
        rc, out = run([sys.executable, os.path.join(LIB, "verify_book.py")], cwd=b.dir,
                      env={"FRANK_BOOK": b.dir})
        check(rc == 0 and "mismatched" in out and " 0 mismatched" in out,
              "%s: verify_book reproduces the source" % tag, out[-400:])
        # check_batch + assemble on paragraph 0 rebuilt from the .tex
        try:
            pj = para_json_from_tex(b, 0)
        except Exception as e:
            bad("%s: rebuilding paragraph 0 as JSON" % tag, repr(e))
            continue
        with tempfile.TemporaryDirectory() as td:
            pp = os.path.join(td, "ch1_p00.json")
            json.dump(pj, open(pp, "w", encoding="utf-8"), ensure_ascii=False)
            rc, out = run([sys.executable, os.path.join(LIB, "check_batch.py"), pp, "--book", b.dir], cwd=b.dir)
            check(rc == 0 and "0 errors" in out, "%s: check_batch 0 errors on paragraph 0" % tag, out[-600:])
            batch = os.path.join(td, "batch.json")
            json.dump({"paragraphs": [pj]}, open(batch, "w", encoding="utf-8"), ensure_ascii=False)
            src = os.path.join(b.source_dir, "src_ch1.json")
            outtex = os.path.join(td, "out.tex")
            rc, out = run([sys.executable, os.path.join(LIB, "assemble.py"), batch, src, "1", outtex,
                           "--partial", "--book", b.dir], cwd=b.dir)
            if check(rc == 0 and "ALL PARAGRAPHS CLEAN" in out, "%s: assemble is clean" % tag, out[-600:]):
                tex = open(outtex, encoding="utf-8").read()
                if L.reading:
                    check("\\chr{" in tex or "\\chrw{" in tex, "%s: assemble writes \\chr (\\chrw with its words)" % tag)
                else:
                    check(("\\ch{" in tex or "\\chw{" in tex) and "\\chr{" not in tex and "\\chrw{" not in tex, "%s: assemble writes \\ch (\\chw with its words)" % tag)
                lab = re.search(r"\\parnum\{([^}]*)\}", tex)
                check(lab is not None and languages.any_to_latin_digits(lab.group(1)) != lab.group(1)
                      if L.digits != "0123456789" else lab is not None,
                      "%s: labels in the language's digits" % tag, lab.group(0) if lab else "no \\parnum")
    test_texwrite(targets)
    # the download-and-upload door (lib/bundle.py).  Every edition out as one
    # file and back into a scratch toolbox -- never under books/, which is the
    # user's -- with the authored files byte for byte on the far side.
    import bundle
    import zipfile
    drift = []
    for b in targets:
        try:
            data, _fname = bundle.pack_book(b.dir)
            with tempfile.TemporaryDirectory() as td:
                r = bundle.install(data, root=td)
                dest = os.path.join(td, r["dir"])
                want = "books/%s/%s" % (b.lang.folder, os.path.basename(b.dir))
                if r["dir"] != want:
                    drift.append("%s installed at %s, not %s" % (b.slug, r["dir"], want))
                for rel in r["files"]:
                    if rel.endswith("/"):
                        continue
                    was = os.path.join(b.dir, rel.replace("/", os.sep))
                    now = os.path.join(dest, rel.replace("/", os.sep))
                    if open(was, "rb").read() != open(now, "rb").read():
                        drift.append("%s: %s" % (b.slug, rel))
        except Exception as e:
            drift.append("%s: %r" % (b.slug, e))
    check(not drift, "bundle: %d editions round-trip byte for byte" % len(targets),
          "; ".join(drift[:4]))
    # a zip is an archive of names: this one's name climbs out of the tree
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(bundle.MANIFEST, json.dumps({"format": bundle.FORMAT, "kind": "book",
                                                "language": "fa", "slug": "mini-fa"}))
        z.writestr("mini-fa/../../../../etc/passwd", "root:x:0:0:pwned\n")
    with tempfile.TemporaryDirectory() as td:
        try:
            bundle.install(buf.getvalue(), root=td)
            refused = "it was installed"
        except bundle.BundleError:
            refused = ""
        landed = [f for _dp, _dn, fn in os.walk(td) for f in fn]
        check(not refused and not landed,
              "bundle refuses a zip whose path escapes, and writes nothing",
              refused or str(landed))
    # and the three shapes a narrated edition comes out in.  One fixture is
    # enough and one is all there should be: what the shapes move is the
    # narration, which is the same set of files in every language.  A fixture
    # and not the real book, because this one is given a narration to take
    # away again, and the real book's directory is the user's.
    if fixtures:
        test_bundle_shapes(next((b for b in fixtures if b.lang.code == "fa"),
                                fixtures[0]))

    # A SYMLINK TO THE TOOLBOX IS A SECOND SPELLING OF ONE DIRECTORY.
    #
    # Every asset a reader links -- the stylesheet, the script, the fonts,
    # the hub -- is a path relative FROM the book TO the toolbox.  Between
    # two spellings of one directory that is not a short hop: it is a walk
    # out to the filesystem root and back down the other name, so the page
    # asks for ../../../../../../../../../../../home/…/lib/parseh.css, gets
    # nothing, and opens with no styling and no script at all.  It happens
    # the moment somebody keeps ~/allCoding as a link to a disk and runs the
    # build through it, which is a perfectly ordinary way to keep a project.
    if fixtures:
        fb = fixtures[0]
        with tempfile.TemporaryDirectory() as td:
            link = os.path.join(td, "toolbox")
            try:
                os.symlink(ROOT, link)
            except (OSError, NotImplementedError, AttributeError) as e:
                skip("no symlink here (%s): the second-spelling case is not tried"
                     % type(e).__name__)
            else:
                rel = os.path.relpath(fb.dir, ROOT)
                rc, out = run([sys.executable,
                               os.path.join(link, "lib", "tex2html.py"),
                               "--book", os.path.join(link, rel)], cwd=td)
                html = os.path.join(fb.dir, "reader", "index.html")
                page = open(html, encoding="utf-8").read() if os.path.isfile(html) else ""
                check(rc == 0 and page and link not in page and td not in page,
                      "built through a symlink to the toolbox, the reader still "
                      "links its own lib/ and not the way in",
                      (out or "")[-200:] or repr(
                          [l for l in re.findall(r'(?:href|src)="([^"]+)"', page)
                           if link in l][:2]))

    # the library page
    rc, out = run([sys.executable, os.path.join(LIB, "make_index.py")], cwd=ROOT)
    if check(rc == 0, "make_index writes books/index.html", out):
        page = open(os.path.join(ROOT, "books", "index.html"), encoding="utf-8").read()
        check("parseh-langs" in page, "library page has the chip row")
        if real:
            check('data-lang="%s"' % real[0].lang.code in page and "lang-head" in page,
                  "library page has a language heading and data-lang cards")
        check(os.path.isfile(os.path.join(LIB, "langs.css")), "lib/langs.css exists on disk")
    if pdf:
        section("books: LaTeX")
        osf = "%s/lib/fonts:/usr/share/fonts:/usr/local/share/fonts:%s/.local/share/fonts" % (
            ROOT, os.path.expanduser("~"))
        for b in fixtures:
            d = b.dir
            for ext in ("aux", "log", "toc", "out", "pdf"):
                try:
                    os.unlink(os.path.join(d, "main." + ext))
                except OSError:
                    pass
            rc, out = run(["lualatex", "-interaction=nonstopmode", "main.tex"], cwd=d,
                          env={"OSFONTDIR": osf}, timeout=900)
            log = open(os.path.join(d, "main.log"), encoding="utf-8", errors="replace").read() \
                if os.path.exists(os.path.join(d, "main.log")) else ""
            bang = [l for l in log.splitlines() if l.startswith("!")]
            lua = [l for l in log.splitlines() if l.startswith("[\\directlua]") or "attempt to " in l]
            good = os.path.exists(os.path.join(d, "main.pdf")) and "Output written on" in log and not bang and not lua
            check(good, "%s: lualatex builds cleanly" % b.slug, "\n".join((bang + lua)[:6]) or out[-500:])
            if good and shutil.which("pdftotext"):
                rc, txt = run(["pdftotext", os.path.join(d, "main.pdf"), "-"])
                if b.lang.reading:
                    kanas = re.findall(r"[\u3040-\u309F]{2,}", txt)
                    check(len(kanas) > 3, "%s: the PDF carries the kana" % b.slug)
                if b.lang.code == "ar":
                    check(re.search(r"[\u0600-\u06FF]", txt) is not None, "%s: the PDF carries Arabic" % b.slug)
        if real:
            rc, out = run(["./build.sh", real[0].slug], cwd=ROOT, timeout=1800)
            check(rc == 0 and "FAILED" not in out,
                  "build.sh builds %s" % real[0].slug, out[-800:])
        else:
            skip("no book under books/: build.sh is not tried")


# ------------------------------------------------------------------ videos
def test_videos():
    section("videos")
    import ytpages
    import languages
    # youtube/videos/ ships empty the same way books/ does.  Every video that
    # is there is checked and round-tripped; an empty shelf leaves the door to
    # the fixtures alone.
    vids = sorted(glob.glob(os.path.join(YT, "videos", "*", "*", "video.json")))
    if not vids:
        skip("no video under youtube/videos/: only the fixture videos are tried")
    for v in vids:
        d = os.path.dirname(v)
        rc, out = run([sys.executable, os.path.join(YT_LIB, "check_annotations.py"), d], cwd=YT)
        check(rc == 0 and "0 error(s)" in out, "check_annotations %s" % os.path.basename(d), out[-400:])
    fixture_videos = sorted(glob.glob(os.path.join(FIX, "videos", "*", "*", "video.json")))
    fixture_langs = [json.load(open(f, encoding="utf-8")).get("language") for f in fixture_videos]
    # a language is covered here by a fixture video or by a real one on the shelf
    real_langs = {(json.load(open(v, encoding="utf-8")).get("language") or "fa")
                  for v in vids}
    for code in languages.CODES:
        if code not in fixture_langs and code not in real_langs:
            skip("no fixture video for %s: the youtube door is not covered" % code)
    for fx in fixture_videos:
        src = os.path.dirname(fx)
        with tempfile.TemporaryDirectory() as td:
            dst = os.path.join(td, os.path.basename(src))
            shutil.copytree(src, dst)
            try:
                os.unlink(os.path.join(dst, "annotations.json"))
            except OSError:
                pass
            rc, out = run([sys.executable, os.path.join(YT_LIB, "merge_parts.py"), dst], cwd=YT)
            check(rc == 0, "merge_parts on fixture %s" % os.path.basename(src), out[-400:])
            rc, out = run([sys.executable, os.path.join(YT_LIB, "check_annotations.py"), dst], cwd=YT)
            check(rc == 0 and "0 error(s)" in out, "check_annotations on fixture %s" % os.path.basename(src), out[-400:])
            fresh = json.load(open(os.path.join(dst, "annotations.json"), encoding="utf-8"))
            kept = json.load(open(os.path.join(src, "annotations.json"), encoding="utf-8"))
            check(fresh == kept, "fixture %s: annotations.json is what merge_parts writes" % os.path.basename(src))
    st = ytpages.stats()
    check(isinstance(st.get("by_lang"), dict), "ytpages.stats() has by_lang", json.dumps(st))
    idx = ytpages.index_page()
    check("langs.css" in idx, "video index links langs.css")
    # the index's headings and cards, the channel page and the player page all
    # need a video to be about, and the first one on the shelf is as good as any
    if vids:
        meta = json.load(open(vids[0], encoding="utf-8"))
        code = meta.get("language") or "fa"
        folder = os.path.basename(os.path.dirname(os.path.dirname(vids[0])))
        vid = os.path.basename(os.path.dirname(vids[0]))
        same = [v for v in vids
                if (json.load(open(v, encoding="utf-8")).get("language") or "fa") == code]
        check(st["by_lang"].get(code, {}).get("videos") == len(same),
              "stats counts all %d %s video(s) on the shelf" % (len(same), code),
              json.dumps(st))
        check("parseh-langs" in idx and "lang-head" in idx
              and 'data-lang="%s"' % code in idx,
              "video index has the chip row, a language heading and data-lang cards")
        chan = ytpages.channel_page(ytpages.channel_slug(meta.get("channel") or ""))
        check(chan is not None and 'class="book' in chan,
              "the channel page lists the videos of %r" % (meta.get("channel") or ""))
        pg = ytpages.player_page(vid)
        check(pg is not None and "videos/%s/%s/annotations.json" % (folder, vid) in pg
              and '"code": "%s"' % code in pg,
              "the player page fetches the folder path and embeds the language")
    # every fixture video in turn, parked under youtube/videos/ for a moment:
    # the pages are how a language reaches a reader, and a fixture that only
    # ever goes through check_annotations proves nothing about them
    for fx in fixture_videos:
        src = os.path.dirname(fx)
        L = languages.get_or_default(json.load(open(fx, encoding="utf-8")).get("language"))
        vid = os.path.basename(src)
        park = os.path.join(YT, "videos", L.folder, vid)
        made_folder = not os.path.isdir(os.path.dirname(park))
        try:
            shutil.copytree(src, park)
            importlib.reload(ytpages)
            pg = ytpages.player_page(vid)
            check(pg is not None and 'data-lang="%s"' % L.code in pg
                  and '"code": "%s"' % L.code in pg,
                  "%s player page carries the language record" % L.name)
            if L.reading:
                check(pg is not None and '"reading": true' in pg,
                      "%s player page says the language has a reading" % L.name)
            found = ytpages.find_video(vid)
            m = found[0] if isinstance(found, tuple) else found
            check(isinstance(m, dict) and m.get("_lang") == L.code,
                  "find_video finds the %s fixture" % L.name, repr(found)[:200])
            st = ytpages.stats()
            check(st["by_lang"].get(L.code, {}).get("videos") == 1,
                  "stats counts the %s video" % L.name)
        finally:
            if _removable(park):
                shutil.rmtree(park, ignore_errors=True)
            if made_folder:
                try:
                    os.rmdir(os.path.dirname(park))
                except OSError:
                    pass
    importlib.reload(ytpages)
    # the prompt an annotator is handed carries that language's own
    # conventions block (docs/lang/<code>.md), so a file still half written
    # shows up here rather than in somebody's batch
    try:
        for code in languages.CODES:
            L = languages.get(code)
            p = ytpages.chat_prompt(None, code)
            check(L.name in p and "TODO" not in p,
                  "the %s video prompt names the language and has no TODO left" % L.name)
        check("kana" in ytpages.chat_prompt(None, "ja").lower(),
              "the Japanese video prompt carries the kana rule")
        p = ytpages.chat_prompt(None, "fa")
        check("š" in p or "ā" in p, "the Persian video prompt carries the transliteration scheme")
    except Exception as e:
        bad("chat_prompt", repr(e))

    # --- A FILM ON THIS MACHINE, and the subtitle file that comes with one.
    # Everything downstream -- the prompt, the checker, the blank-gloss draft
    # -- reads the panel YouTube shows, so a .srt or .vtt is TRANSLATED into
    # that rather than parsed a second way.
    srt = ("1\n00:00:06,000 --> 00:00:09,000\nسلام، ببخشید\n\n"
           "2\n00:01:02,500 --> 00:01:05,000\n<i>دو کیلو</i>\nمی‌خواهم\n")
    got = ytpages.subtitles_to_transcript(srt)
    # ...and a cue's own fraction is kept: the clock line carries one
    # (check_annotations.stamp_of), so a subtitle file is no longer rounded
    # down to the nearest second on the way in
    check(got == "0:06\nسلام، ببخشید\n1:02.5\nدو کیلو می‌خواهم\n",
          "a SubRip file becomes the transcript this toolbox already reads: "
          "the cue numbers dropped, the tags stripped, the two lines joined, "
          "the half second kept",
          repr(got))
    check(ytpages.looks_like_subtitles(srt)
          and ytpages.looks_like_subtitles("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhi\n")
          and not ytpages.looks_like_subtitles("0:06\nسلام\n"),
          "and a subtitle file is told from a pasted panel")
    roll = ("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nhello\n\n"
            "00:00:03.000 --> 00:00:05.000\nhello there\n")
    check(ytpages.subtitles_to_transcript(roll) == "0:01\nhello\n0:03\nthere\n",
          "automatic captions ROLL -- each cue repeating the last with one "
          "phrase added -- and only what is new is kept",
          repr(ytpages.subtitles_to_transcript(roll)))
    check(ytpages.subtitles_to_transcript("nothing here") == "",
          "and a file with no cues in it says so by being empty")
    # WHAT IS NOT DROPPED, both found by reading a caption nobody had read.
    digits = "1\n00:00:05,000 --> 00:00:07,000\n1979\n"
    check(ytpages.subtitles_to_transcript(digits) == "0:05\n1979\n",
          "a caption that is only digits -- a year, a price -- is a caption: "
          "SubRip's cue numbers are on the far side of the timestamp",
          repr(ytpages.subtitles_to_transcript(digits)))
    twice = ("1\n00:00:05,000 --> 00:00:07,000\nنه\n\n"
             "2\n00:02:30,000 --> 00:02:32,000\nنه\n")
    check(ytpages.subtitles_to_transcript(twice) == "0:05\nنه\n2:30\nنه\n",
          "and a line said again later is said again: only OVERLAPPING cues "
          "are rolling captions, and only those are collapsed",
          repr(ytpages.subtitles_to_transcript(twice)))
    disorder = ("1\n00:00:20,000 --> 00:00:22,000\nb\n\n"
                "2\n00:00:05,000 --> 00:00:07,000\na\n")
    check(ytpages.subtitles_to_transcript(disorder) == "0:05\na\n0:20\nb\n",
          "cues out of order are put in order, or the video's duration would "
          "be whatever cue happened to be written last",
          repr(ytpages.subtitles_to_transcript(disorder)))
    tight = ("1\n00:00:05,000 --> 00:00:07,000\nسلام\n"
             "2\n00:00:09,000 --> 00:00:11,000\nخوبی\n")
    check(ytpages.subtitles_to_transcript(tight) == "0:05\nسلام\n0:09\nخوبی\n",
          "a SubRip file written without a blank line between its cues does "
          "not glue the next cue's number onto the caption: a number is a "
          "count only when a timestamp follows it",
          repr(ytpages.subtitles_to_transcript(tight)))
    bom = "\ufeff1\r\n00:00:06,000 --> 00:00:09,000\r\nسلام\r\n"
    check(ytpages.subtitles_to_transcript(bom) == "0:06\nسلام\n",
          "a byte-order mark and CRLF are what a subtitle file off a disk "
          "actually looks like", repr(ytpages.subtitles_to_transcript(bom)))
    check(ytpages.as_transcript(digits) == ytpages.subtitles_to_transcript(digits)
          and ytpages.as_transcript("0:06\nسلام\n") == "0:06\nسلام\n",
          "and every road into the add page takes either: the page invites a "
          "subtitle file, so all three of its buttons must accept one")

    # the id a local video gets: a directory name and a URL segment, so the
    # same shape lib/bundle.py's LEAF allows and never a YouTube id
    vid = ytpages.local_id("Farsi at the greengrocer's")
    check(ytpages.is_local_id(vid) and bundle_leaf_ok(vid),
          "a local video is named after what it is, and safely", vid)
    for bad_name in ("../evil", ".hidden", "a/b", "", "fA6bK2mQ8sT"):
        check(not ytpages.is_local_id(bad_name),
              "and %r is not a name a local video may have" % bad_name)
    check(ytpages.local_id("x") != ytpages.local_id("x"),
          "two lessons called the same thing are two videos")

    # THE GUARD AND THE RESOLVER MUST READ THE SAME PATH.  static_ok used to
    # split the address as it arrived on the wire, where `%2e%2e` is not a
    # component beginning with a dot; translate_path then unquoted it and
    # normpath collapsed the result against the toolbox root, so every file
    # in the project was readable -- .tls/key.pem included -- by an address
    # whose unencoded form was refused.
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import serve as _serve
    for escape in ("/youtube/videos/%2e%2e/%2e%2e/serve.py",
                   "/youtube/videos/%2e%2e/%2e%2e/%2etls/key.pem",
                   "/youtube/videos/../../serve.py",
                   "/books/%2e%2e/%2e%2e/.tls/cert.pem",
                   "/lib/%2e%2e/serve.py"):
        check(not _serve.static_ok(escape),
              "no file is served through %s" % escape)
    for real in ("/lib/parseh.css", "/lib/mobile.css", "/youtube/lib/style.css",
                 "/youtube/videos/persian/x/media.mp4"):
        check(_serve.static_ok(real), "while %s still is" % real)

    # --- NO CEILING ON A FILE OF YOUR OWN.  A narration, a film, a bundle
    # carrying either: they are streamed to disk in pieces, and any number
    # written here could only ever be smaller than somebody's two-hour
    # lesson.  MAX_BODY is a different thing and stays: a JSON edit that
    # size is a mistake, not a film.
    import bundle
    check(not hasattr(_serve, "MAX_UPLOAD") and not hasattr(_serve, "MAX_AUDIO"),
          "no upload door carries a size ceiling any more")
    check(bundle.MAX_MEDIA is None,
          "and a bundle's media is bounded by the disk and nothing else")
    check(_serve.MAX_BODY and "/books/__upload" in _serve.UPLOAD_ROUTES,
          "while an ordinary JSON body is still bounded")

    # --- THE SHELF IS WRITTEN WHEN A BOOK ARRIVES.  The library page is a
    # file make_index writes: until it is written again, an installed book is
    # on disk and on no page, which is exactly what "the book does not
    # appear" was.  And the panel builds nothing itself -- the card on that
    # page does, like every other book's, so there is one way to build a book
    # rather than two that can disagree.
    _up = io.open(os.path.join(ROOT, "serve.py"), encoding="utf-8").read()
    _up = _up.split("def _bundle_upload", 1)[1].split("    def _book_empty", 1)[0]
    check("_write_library" in _up,
          "a bundle installed puts the book's card on the library page")
    _mi = io.open(os.path.join(LIB, "make_index.py"), encoding="utf-8").read()
    check("takebuild" not in _mi and "Parseh.buildBook" not in _mi,
          "and the panel has no build of its own: the card on the shelf builds it")

    # --- ONLY A DIRECTORY MAY HOLD THINGS.  A name owned at the top of a
    # tree used to be treated as a directory prefix whose contents are
    # checked against the extensions that prefix allows -- and a FILE has
    # none, so the allowlist was skipped under it: `media.mp4/evil.html`
    # installed and was served as text/html, and `video.json/x` came out as
    # a raw FileExistsError.
    _fx = sorted(glob.glob(os.path.join(FIX, "videos", "*", "*", "video.json")))
    _src = os.path.dirname(_fx[0])
    _said = bundle.inspect(bundle.pack_video(_src)[0])
    for nested in ("media.mp4/evil.html", "video.json/x", "transcript.txt/y"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(bundle.MANIFEST, json.dumps(
                {"format": "parseh-bundle/1", "software": "hand", "kind": "video",
                 "language": _said["language"], "gloss": _said.get("gloss") or "en",
                 "id": _said["name"], "audio": "full"}))
            for n in ("video.json", "annotations.json", "transcript.txt"):
                z.writestr(_said["name"] + "/" + n,
                           open(os.path.join(_src, n), encoding="utf-8").read())
            z.writestr(_said["name"] + "/" + nested, "x")
        with tempfile.TemporaryDirectory() as td2:
            os.makedirs(os.path.join(td2, "youtube", "videos"))
            try:
                rr = bundle.install(buf.getvalue(), root=td2)
                ok = nested in (rr.get("dropped") or [])
            except Exception as e:
                ok = False
                rr = {"error": "%s: %s" % (type(e).__name__, e)}
            check(ok, "a bundle cannot hang %s off a file's name" % nested,
                  json.dumps(rr)[:160])

    # --- AND THE TWO ROADS IN AGREE.  A language nobody teaches was refused
    # by one and quietly turned into Persian by the other; a request naming
    # both a URL and a film dropped the film without a word.
    try:
        ytpages.posted_lang("zz")
        why = "it was accepted"
    except KeyError as e:
        why = str(e.args[0])
    check("not a language" in why, "a language nobody teaches is refused, not "
          "turned into Persian", why)
    check(ytpages.posted_lang("").code == languages.get_or_default("").code,
          "while saying nothing still means the default")
    try:
        ytpages.one_source({"url": "https://youtu.be/aaaaaaaaaaa", "path": "/a.mp4"})
        both = "it was accepted"
    except ValueError as e:
        both = str(e)
    check("either an address or a file" in both,
          "and naming both an address and a film is a question, not a film "
          "dropped in silence", both)
    for plain in ("test", "film", "demo"):
        try:
            got = ytpages.local_id(plain)
        except ValueError as e:
            got = "REFUSED: %s" % e
        check(ytpages.is_local_id(got),
              "a film called %s.mp4 can be added: four letters and six hex is "
              "eleven characters, which is a YouTube id's shape, and every "
              "candidate was refused" % plain, got)

    # the download-and-upload door (lib/bundle.py): every video out as one
    # file and back into a scratch toolbox, byte for byte, and a video whose
    # annotations no longer check refused before anything is written
    import bundle
    reals = [os.path.dirname(v) for v in vids]
    drift = []
    for src in [os.path.dirname(f) for f in fixture_videos] + reals:
        try:
            data, _fname = bundle.pack_video(src)
            with tempfile.TemporaryDirectory() as td:
                r = bundle.install(data, root=td)
                dest = os.path.join(td, r["dir"])
                for rel in r["files"]:
                    if rel.endswith("/"):
                        continue
                    was = os.path.join(src, rel.replace("/", os.sep))
                    now = os.path.join(dest, rel.replace("/", os.sep))
                    if open(was, "rb").read() != open(now, "rb").read():
                        drift.append("%s: %s" % (os.path.basename(src), rel))
        except Exception as e:
            drift.append("%s: %r" % (os.path.basename(src), e))
    check(not drift, "bundle: %d videos round-trip byte for byte"
          % (len(fixture_videos) + len(reals)), "; ".join(drift[:4]))
    # A VIDEO THAT IS A FILE ON THIS MACHINE takes its film with it.  The
    # download button is how a video leaves this toolbox, and a bundle that
    # carried the glosses of a film nobody else has is a transcript of
    # nothing -- so `full` is the default here where `linked` is a book's,
    # and `text` is what somebody asks for who wants the words alone.
    with tempfile.TemporaryDirectory() as td:
        one = os.path.dirname(fixture_videos[0])
        src = os.path.join(td, os.path.basename(one))
        shutil.copytree(one, src)
        # incompressible, as a film is: this also proves it is STORED
        film = os.urandom(512 * 1024)
        with open(os.path.join(src, "media.mp4"), "wb") as f:
            f.write(film)
        check(bundle.film_at(src) == "media.mp4",
              "a video knows its own film by the file being there -- no field "
              "in video.json to keep true", bundle.film_at(src))
        data, fname = bundle.pack_video(src)
        check(fname.endswith("-full.zip"),
              "and packs it by default: the film comes with the glosses", fname)
        z = zipfile.ZipFile(io.BytesIO(data))
        inside = [n for n in z.namelist() if n.endswith("media.mp4")]
        check(len(inside) == 1, "the film is in the bundle", repr(z.namelist()))
        check(z.getinfo(inside[0]).compress_type == zipfile.ZIP_STORED,
              "STORED, not deflated: an mp4 has nothing left in it for zlib "
              "and the seconds are seconds a browser waits")
        lite, lname = bundle.pack_video(src, "text")
        check(lname.endswith("-text.zip") and len(lite) < len(data) // 4,
              "and `text` leaves it behind for somebody who wants the words",
              "%d vs %d bytes" % (len(lite), len(data)))
        with tempfile.TemporaryDirectory() as into:
            os.makedirs(os.path.join(into, "youtube", "videos"))
            r = bundle.install(data, root=into)
            back = os.path.join(into, r["dir"], "media.mp4")
            check(os.path.exists(back) and open(back, "rb").read() == film,
                  "and it comes back byte for byte on the other machine: the "
                  "film and the translation travel together")
        with tempfile.TemporaryDirectory() as into:
            os.makedirs(os.path.join(into, "youtube", "videos"))
            r = bundle.install(lite, root=into)
            check(not os.path.exists(os.path.join(into, r["dir"], "media.mp4")),
                  "while the words-alone bundle installs without one")
            # A FILM IS A FILE AND NEVER A DIRECTORY.  Every name owned at the
            # top used to be treated as a directory prefix whose contents were
            # checked against the extensions that prefix allows -- a film has
            # none, so the allowlist was skipped for everything under it, and
            # a bundle carrying <id>/media.mp4/evil.html installed it, to be
            # served as text/html from the same origin as the reader.
            said = bundle.inspect(data)          # this video's own language
            crafted = io.BytesIO()
            with zipfile.ZipFile(crafted, "w") as cz:
                cz.writestr(bundle.MANIFEST, json.dumps(
                    {"format": "parseh-bundle/1", "software": "hand",
                     "kind": "video", "language": said["language"],
                     "gloss": said.get("gloss") or "en",
                     "id": said["name"], "audio": "full"}))
                for n in ("video.json", "annotations.json", "transcript.txt"):
                    cz.writestr(said["name"] + "/" + n,
                                open(os.path.join(src, n), encoding="utf-8").read())
                cz.writestr(said["name"] + "/media.mp4/evil.html",
                            "<script>1</script>")
            with tempfile.TemporaryDirectory() as evil:
                os.makedirs(os.path.join(evil, "youtube", "videos"))
                er = bundle.install(crafted.getvalue(), root=evil)
                landed = []
                for base, _dd, fs in os.walk(os.path.join(evil, er["dir"])):
                    landed += [f for f in fs]
                check("evil.html" not in landed
                      and "media.mp4/evil.html" in (er.get("dropped") or []),
                      "a bundle cannot use a film's name as a directory to "
                      "put a page in the reader's own origin", repr(landed))
            # AND A FILM IS GIVEN UP ONLY TO ANOTHER FILM.  A bundle whose
            # manifest says `full` and carries none used to take the film
            # with it -- not to the trash, nowhere.
            hand = io.BytesIO()
            with zipfile.ZipFile(hand, "w") as hz:
                hz.writestr(bundle.MANIFEST, json.dumps(
                    {"format": "parseh-bundle/1", "software": "hand",
                     "kind": "video", "language": said["language"],
                     "gloss": said.get("gloss") or "en",
                     "id": said["name"], "audio": "full"}))
                for n in ("video.json", "annotations.json", "transcript.txt"):
                    hz.writestr(said["name"] + "/" + n,
                                open(os.path.join(src, n), encoding="utf-8").read())
            with tempfile.TemporaryDirectory() as keep:
                os.makedirs(os.path.join(keep, "youtube", "videos"))
                kr = bundle.install(data, root=keep)
                still = os.path.join(keep, kr["dir"], "media.mp4")
                bundle.install(hand.getvalue(), root=keep, replace=True)
                check(os.path.exists(still) and open(still, "rb").read() == film,
                      "and a bundle that CLAIMS a film but brings none leaves "
                      "the one that is there: a film is the video's narration, "
                      "the one thing that cannot be made again")
            # AND DOES NOT DESTROY ONE.  A shape does not own what it leaves
            # behind, so somebody handed the words alone of a video they
            # already have the film of installs the new glosses over the old
            # ones and keeps the film -- the same rule that lets a `text`
            # book bundle install without touching a recording.
            bundle.install(data, root=into, replace=True)
            kept = os.path.join(into, r["dir"], "media.mp4")
            bundle.install(lite, root=into, replace=True)
            check(os.path.exists(kept) and open(kept, "rb").read() == film,
                  "and installing the words alone over a video that HAS a "
                  "film leaves the film exactly where it was")

    victim = (reals + [os.path.dirname(f) for f in fixture_videos])[0]
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, os.path.basename(victim))
        shutil.copytree(victim, src)
        ann = os.path.join(src, "annotations.json")
        with open(ann, "a", encoding="utf-8") as f:
            f.write("}")                      # no longer JSON
        data, _fname = bundle.pack_video(src)
        with tempfile.TemporaryDirectory() as into:
            try:
                bundle.install(data, root=into)
                why = "it was installed"
            except bundle.BundleError as e:
                why = "" if "check_annotations" in str(e) else str(e)
            check(not why and not [f for _d, _n, fn in os.walk(into) for f in fn],
                  "bundle refuses a video whose annotations do not check", why)

    # A YouTube id is eleven characters of [A-Za-z0-9_-] and may perfectly
    # well begin with an underscore or a hyphen.  The name a bundle may
    # unpack under was written as "a letter or a digit, then the rest",
    # which is one rule more than the sentence beside it stated -- so a
    # bundle of `_bK2mQ8sTfA` was refused at the door with a message about
    # dots that named nothing the uploader had done.  Only a leading dot is
    # forbidden, and these are the two halves of that.
    donor = reals[0] if reals else os.path.dirname(fixture_videos[0])
    donor_lang = (json.load(open(os.path.join(donor, "video.json"),
                                 encoding="utf-8")).get("language") or "fa")
    for leaf in ("_bK2mQ8sTfA", "-bK2mQ8sTfA", "a-b_c.d"):
        man = bundle._manifest_for("video", leaf, donor_lang, "en", None)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(bundle.MANIFEST, json.dumps(man))
            for f in ("video.json", "annotations.json", "transcript.txt"):
                z.writestr(leaf + "/" + f,
                           open(os.path.join(donor, f), encoding="utf-8").read())
        with tempfile.TemporaryDirectory() as into:
            try:
                r = bundle.install(buf.getvalue(), root=into)
                check(r["dir"].endswith(leaf),
                      "a bundle unpacks under %r, which is a name a video has"
                      % leaf, r["dir"])
            except Exception as e:
                bad("a bundle unpacks under %r" % leaf, str(e)[:200])
    for leaf in ("..", "../evil", "/etc", ".ssh", "a b", "x" * 101):
        man = bundle._manifest_for("video", leaf, donor_lang, "en", None)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(bundle.MANIFEST, json.dumps(man))
            z.writestr("x/video.json", "{}")
        with tempfile.TemporaryDirectory() as into:
            try:
                bundle.install(buf.getvalue(), root=into)
                bad("a bundle naming %r is refused" % leaf, "it was installed")
            except bundle.BundleError:
                stray = [p for p in os.listdir(into)]
                check(not stray, "a bundle naming %r is refused and writes "
                                 "nothing" % leaf, repr(stray))


# ------------------------------------------------------------------- drafts
def test_draft():
    """lib/draft.py: an empty book and an empty video, for every language.

    The text of each draft is the fixture edition's own source, so the draft
    is a book whose finished twin is sitting beside it; a language whose
    fixtures are not written yet is a skip, as everywhere else here.  What is
    proved is what makes the feature real: the draft passes its own checker,
    reproduces its source, and renders -- and a chunk half written in it
    fails.

    Nothing marks a draft as one.  A chunk nobody has glossed yet is legal in
    every book and every video, so the draft is an ordinary edition whose
    chunks are all blank: book.json and video.json carry no "draft" key, each
    checker passes it with ONE count note ("N of M chunks have no gloss
    yet") and no error, and a "draft": true an older version left behind in
    book.json or video.json is never read -- the checkers say exactly what
    they say without it.  The half-written chunk is a real one: its meaning
    typed and the reading the draft proposed from its words blanked, so it
    lacks a field its language requires in every language that requires one
    (a reading proposed from the words is no gloss while the chunk is blank,
    and counts as the reading it is once anything else is written).
    """
    section("drafts")
    import books
    import draft
    import languages
    import words
    import wordline
    count_note = re.compile(r"note\s+(\d+) of (\d+) chunks have no gloss yet")
    fixtures = fixture_books()
    covered = {b.language for b in fixtures}
    for code in languages.CODES:
        if code not in covered:
            skip("no fixture edition for %s: draft.book_from_text is not covered" % code)
    for b in fixtures:
        L, tag = b.lang, "draft %s [%s]" % (b.slug, b.language)
        paras = sorted(glob.glob(os.path.join(b.paras_dir, "*.txt")))
        text = "\n\n".join(io.open(p, encoding="utf-8").read().strip() for p in paras)
        with tempfile.TemporaryDirectory() as td:
            try:
                r = draft.book_from_text(text, L, b.title, slug="draft-" + L.code,
                                         author=b.author, title_latin=b.title_latin,
                                         author_latin=b.author_latin, into=td)
            except Exception as e:
                bad("%s: book_from_text" % tag, repr(e))
                continue
            d = r["dir"]
            check(r["paragraphs"] == len(paras) and r["chunks"] == r["sentences"],
                  "%s: %d paragraphs, one chunk per sentence" % (tag, r["paragraphs"]))
            # the chapter is written with the macro the language's chunks use,
            # so filling a draft in never means renaming a macro
            tex = r["files"]["ch1.tex"]
            # -- the word-bearing form of it where this Python can propose words
            plain = "chr" if L.reading else "ch"
            named = plain + "w" if L.words and words.available(L.code) else plain
            found = set(re.findall(r"^\\(chrw|chw|chr|chp|ch)\{", tex, re.M))
            check(named in found and found <= {plain, named},
                  "%s: the chapter is written with \\%s" % (tag, named))
            check("draft" not in json.loads(r["files"]["book.json"]) and "draft" not in r,
                  "%s: book.json carries no draft flag, and the answer none" % tag,
                  r["files"]["book.json"][:300])
            # it reproduces its source, it passes its own checker, it renders
            rc, out = run([sys.executable, os.path.join(LIB, "verify_book.py")],
                          cwd=d, env={"FRANK_BOOK": d})
            check(rc == 0 and " 0 mismatched" in out,
                  "%s: verify_book reproduces the source" % tag, out[-300:])
            pj = para_json_from_tex(books.Book(d), 0)
            pp = os.path.join(td, "p0.json")
            batch = lambda para: (json.dump(para, open(pp, "w", encoding="utf-8"),
                                            ensure_ascii=False),
                                  run([sys.executable, os.path.join(LIB, "check_batch.py"),
                                       pp, "--book", d], cwd=d))[1]
            chunks = [c for s in pj["ann"]["sentences"] for c in s["chunks"]]
            rc, clean = batch(pj)
            said = count_note.findall(clean)
            check(rc == 0 and "\n0 errors" in clean
                  and said == [(str(len(chunks)), str(len(chunks)))],
                  "%s: check_batch passes it with no error and one count note, "
                  "%d of %d chunks with no gloss yet" % (tag, len(chunks), len(chunks)),
                  clean[-400:])
            rc, out = run([sys.executable, os.path.join(LIB, "tex2html.py"), "--book", d], cwd=d)
            check(rc == 0 and os.path.isfile(os.path.join(d, "reader", "index.html")),
                  "%s: tex2html builds a reader" % tag, out[-300:])
            # half written: a meaning with nothing beside it is the mistake the
            # checker exists for.  The reading the draft proposed from the
            # words (kana, or tr for Chinese) is blanked with it, so the chunk
            # really lacks what its language requires -- left in place, that
            # proposal would count as the reading it is once the meaning made
            # the chunk a written one, and a Chinese chunk would be complete
            half = json.loads(json.dumps(pj))
            first = half["ann"]["sentences"][0]["chunks"][0]
            seeded, _proposal = wordline.seed(first, L)
            first["en"] = "a meaning, and nothing else"
            if seeded:
                first[seeded] = ""
            rc, out = batch(half)
            wanted = L.require_tr or L.reading
            lacks = [e for e in ("empty tr", "no kana") if e in out]
            rest = ([] if len(chunks) == 1 else
                    [(str(len(chunks) - 1), str(len(chunks)))])
            check((rc > 0) == wanted and bool(lacks) == wanted
                  and count_note.findall(out) == rest,
                  "%s: a half-written chunk %s" % (
                      tag, "is refused (%s)" % ", ".join(lacks or ["?"]) if wanted
                      else "needs only its meaning"), out[-400:])
            # and a flag an older version wrote into book.json is never read:
            # the blank chunks are counted exactly as they are without it
            mp = os.path.join(d, "book.json")
            m = json.load(open(mp, encoding="utf-8"))
            m["draft"] = True
            json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False)
            rc, out = batch(pj)
            check(rc == 0 and out == clean,
                  "%s: a leftover \"draft\": true changes nothing check_batch says"
                  % tag, out[-400:])

    # the video side: the draft reproduces the transcript it was made from,
    # and the checker passes it -- with no flag to lean on, in every language
    import check_annotations as CA
    import annwrite
    fixture_videos = sorted(glob.glob(os.path.join(FIX, "videos", "*", "*", "video.json")))
    for vj in fixture_videos:
        src = os.path.dirname(vj)
        meta = json.load(open(vj, encoding="utf-8"))
        L = languages.get_or_default(meta.get("language"))
        tag = "draft video [%s]" % L.code
        text = io.open(os.path.join(src, "transcript.txt"), encoding="utf-8").read()
        with tempfile.TemporaryDirectory() as td:
            try:
                r = draft.video_from_transcript(text, L, video_id=meta["id"], into=td)
            except Exception as e:
                bad("%s: video_from_transcript" % tag, repr(e))
                continue
            caps = CA.parse_transcript(os.path.join(src, "transcript.txt"), L)
            ann = json.loads(r["files"]["annotations.json"])
            segs = ann["segments"]
            check(len(segs) == len(caps) and r["chunks"] > 0,
                  "%s: %d captions, %d blank chunks" % (tag, len(segs), r["chunks"]))
            check(all(bool(s.get("plain")) == c["plain"] for s, c in zip(segs, caps)),
                  "%s: the plain captions are the transcript's" % tag)
            check(not any(s.get("chunks") for s in segs if s.get("plain")),
                  "%s: a plain caption carries no chunks" % tag)
            check(all(CA.norm(L.word_sep.join(ch["fa"] for ch in s["chunks"]), L)
                      == CA.norm(s["text"], L) for s in segs if s.get("chunks")),
                  "%s: the chunks reproduce every caption" % tag)
            check("draft" not in json.loads(r["files"]["video.json"]) and "draft" not in r,
                  "%s: video.json carries no draft flag, and the answer none" % tag,
                  r["files"]["video.json"][:300])
            checker = lambda: run([sys.executable, os.path.join(YT_LIB, "check_annotations.py"),
                                   r["dir"]], cwd=YT)
            blank, glossable = CA.gloss_state(r["dir"])
            rc, out = checker()
            check(rc == 0 and "0 error(s)" in out and 0 < blank == glossable
                  and "note: %d of %d chunks have no gloss yet" % (blank, glossable) in out,
                  "%s: check_annotations passes the draft, its %d chunks counted in one "
                  "note as having no gloss yet" % (tag, glossable), out[-400:])
            # half written, as in the book: the player's editor saves the
            # reading proposed from the words taken off a blank chunk (it is
            # still blank), then a meaning typed into it (a box at a time is
            # how a gloss is filled), and the checker lists what the chunk
            # lacks -- an error wherever the language wants more than a meaning
            si, k = next((i, k) for i, s in enumerate(segs)
                         for k, ch in enumerate(s.get("chunks") or [])
                         if CA.required(ch, L))
            seeded, _proposal = wordline.seed(segs[si]["chunks"][k], L)
            try:
                for fields in ([{seeded: ""}] if seeded else []) + \
                        [{"en": "a meaning, and nothing else"}]:
                    annwrite.edit_chunk(r["dir"], si, k, fields)
            except ValueError as e:
                bad("%s: the player saves a meaning typed into a blank chunk" % tag,
                    str(e)[:300])
                continue
            rc, half = checker()
            wanted = L.require_tr or L.reading
            rest = ("note: %d of %d chunks have no gloss yet" % (blank - 1, glossable)
                    if blank > 1 else "")
            check((rc > 0) == wanted and (": missing " in half) == wanted
                  and rest in half,
                  "%s: a half-written chunk %s" % (tag, "is refused" if wanted else
                                                   "needs only its meaning"), half[-400:])
            # and a flag an older version wrote into video.json is never read:
            # it excuses neither the blank chunks nor the half-written one
            mp = os.path.join(r["dir"], "video.json")
            m = json.load(open(mp, encoding="utf-8"))
            m["draft"] = True
            json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            rc, out = checker()
            check(out == half,
                  "%s: a leftover \"draft\": true changes nothing check_annotations "
                  "says" % tag, out[-400:])


# ------------------------------------------------------------------ studio
def load_studio():
    spec = importlib.util.spec_from_file_location("parseh_studio", os.path.join(STUDIO, "app", "server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_studio(pdf):
    section("studio")
    studio = load_studio()
    import htmlgen
    import texgen
    import mdparser
    import languages
    # The +New button opens on the target language's own starting document.
    # Every registry language must have one that parses, declares itself, and
    # is written in English prose -- and must use the marks its language
    # actually has, or the starter is the generic one wearing a name.
    import server as _srv
    for L in languages.LANGS.values():
        md = _srv.new_template(L.code)
        fm, blocks = mdparser.parse(md)
        check(fm.get("target") == L.code,
              "the %s starter declares target: %s" % (L.name, L.code), repr(fm.get("target")))
        check(fm.get("lang") == "en",
              "the %s starter is written in English prose" % L.name, repr(fm.get("lang")))
        doc = htmlgen.render_document(md)
        check(doc.get("target") == L.code, "the %s starter renders" % L.name)
        tex = texgen.generate(*mdparser.parse(md))
        check("exlex-target: %s" % L.code in tex,
              "the %s starter's .tex carries the target marker" % L.name)
        # what makes it that language's own, rather than one file with the
        # code swapped: a script the toolbox can recognise needs no mark, a
        # Latin one marks every run, Japanese carries its reading
        if L.chars:
            check('dir="%s"' % L.dir in doc["html"],
                  "the %s starter has a run in its own script" % L.name)
        else:
            check('class="fa' in doc["html"],
                  "the %s starter marks its runs by hand" % L.name)
        if L.reading:
            check("data-kana" in doc["html"] and "voce-kana" in doc["html"],
                  "the %s starter shows the reading" % L.name)
            # the gloss harvester is a path of its own, not the page's: a
            # lemma whose reading renders but does not survive harvesting
            # leaves the glossary and the flashcards without it.  Asked of
            # the starter because the example document that used to be
            # asked is gone, and the starter is per-language anyway
            check(any(g.get("kana") for g in htmlgen.glosses(md)),
                  "the %s starter's glosses carry the reading" % L.name)
        if L.vertical:
            check("tl-vertical" in doc["html"] and "\\tlvertical" in tex,
                  "the %s starter sets a block vertically" % L.name)
        # A marked run is addressed by (text, occurrence), and the starter is
        # the document a language is met in first, so its runs must number the
        # same on the page as in the source.  English is where this stops
        # being obvious: prose and target are one language there, so a run is
        # a run only because a bracket says so, and _run_matches has nothing
        # else to go on.
        try:
            drifted = occurrence_drift(md, doc["html"])
            check(not drifted, "the %s starter's runs number the same on the page "
                               "as in the source" % L.name, "; ".join(drifted)[:400])
        except Exception as e:
            bad("the %s starter's occurrence sync" % L.name, repr(e))

    # The prose language (`lang:`) and the target (`target:`) may be the same
    # language, and English is the first that is: a note written in English
    # about English asks texgen's prose table for its hyphenation and the
    # registry for the reading edition's, and two different pattern names
    # would break one word one way on screen and another in print
    # (docs/languages.md section 1, and the rule texgen states over
    # _HYPHEN_PROSE).  Every code both tables know must name the same set.
    # English is the one that could have drifted: its prose row was written
    # when nobody studied English here, and it is the only row of a registry
    # language that names its patterns instead of deferring to `tex.hyphen`.
    shared = [c for c in languages.CODES if c in texgen.HYPHEN_LANGS]
    drift = ["%s: the studio says %r, lib/languages.json says %r"
             % (c, texgen.hyphenation_for(c)[0], languages.get(c).tex.get("hyphen"))
             for c in shared
             if texgen.hyphenation_for(c)[0] != languages.get(c).tex.get("hyphen")]
    check(not drift, "the studio and the reading editions hyphenate alike (%s)"
          % ", ".join("%s %s" % (c, texgen.hyphenation_for(c)[0]) for c in shared),
          "; ".join(drift))

    # Every studio document the repository has: the examples in
    # exlex/examples/, which are whatever has been written -- the four that
    # shipped were the studio's Persian-for-Italians era and are gone, and the
    # languages they covered are met below through their fixture editions
    # instead -- and the regression fixture under tests/fixtures/studio/.  The
    # target expected of each is the one its own front matter declares, read
    # by mdparser, so what this proves is that the parser and both generators
    # agree, on whatever is actually on disk.
    # An example may be absent: it is prose somebody has to write, and there
    # are none just now.  The regression fixture may NOT be -- section 11 of
    # docs/languages.md pins it at 186/186, and a glob cannot tell a document
    # deleted from one not written yet.  So it is named here, once, and its
    # 186 check further down can be reached by nothing else.
    check(os.path.isfile(os.path.join(FIX, "studio", "persiano", "persiano.md")),
          "the studio regression fixture is on disk "
          "(tests/fixtures/studio/persiano/, section 11)")
    ex = os.path.join(STUDIO, "exlex", "examples")
    want = {}
    for path in sorted(glob.glob(os.path.join(ex, "*.md"))) \
            + sorted(glob.glob(os.path.join(FIX, "studio", "*", "*.md"))):
        fm, _ = mdparser.parse(open(path, encoding="utf-8").read())
        want[os.path.relpath(path, ROOT)] = fm.get("target") or ""
    if not glob.glob(os.path.join(ex, "*.md")):
        skip("no example document in exlex/examples/: the studio door is "
             "tried on the fixtures under tests/fixtures/studio/ and on the "
             "fixture editions")
    for name, code in want.items():
        base = os.path.basename(name)
        path = os.path.join(ROOT, name)
        md = open(path, encoding="utf-8").read()
        try:
            doc = htmlgen.render_document(md)
            check(doc.get("target") == code, "%s renders (target %s)" % (name, doc.get("target")))
            fm, blocks = mdparser.parse(md)
            tex = texgen.generate(fm, blocks)
            check("exlex-target: %s" % code in tex, "%s: the .tex carries the target marker" % name)
            if code == "ja":
                check("tl-vertical" in doc["html"] and "--tl-vh" in doc["html"], "%s: a vertical block" % name)
                check("data-kana" in doc["html"], "%s: kana marks" % name)
                check("voce-kana" in doc["html"], "%s: a lemma with a reading" % name)
                gl = htmlgen.glosses(md)
                check(any(g.get("kana") for g in gl), "%s: glosses carry kana" % name)
                check("\\tlvertical" in tex, "%s: the .tex has the vertical macro" % name)
            body = tex[tex.index("\\begin{document}"):]
            if code == "it":
                check('class="fa' in doc["html"] and 'dir="ltr"' in doc["html"], "%s: marked runs render LTR" % name)
                check("\\beginR" not in body, "%s: no RTL primitives in an LTR document's body" % name)
            if code == "ar":
                check('dir="rtl"' in doc["html"] and 'lang="ar"' in doc["html"], "%s: RTL Arabic runs" % name)
            # the hover palette addresses a run by (text, occurrence): the
            # occurrences the page numbers and the ones the store finds in
            # the source must be the same list, or an edit lands elsewhere
            try:
                bad_runs = occurrence_drift(md, doc["html"])
                check(not bad_runs, "%s: page occurrences match the store's" % name, "; ".join(bad_runs)[:500])
            except Exception as e:
                bad("%s: occurrence sync" % name, repr(e))
            if code == "fa" and base == "persiano.md":
                check('lang="fa"' in doc["html"] and ("\\pe{" in body or "\\pel{" in body)
                      and "exlex-target: fa rtl" in tex, "%s: Persian unchanged in kind" % name)
        except Exception as e:
            import traceback
            bad("%s renders" % name, traceback.format_exc()[-800:])
    # Every other registry language, through the same two renderers.  The
    # document is built from that language's fixture edition -- its own first
    # chunk, marked as a target run -- so no sample text of any language is
    # written into this file, and a language is covered here the moment it
    # has an edition, without an example document being written for it.
    import languages
    covered = set(want.values())
    for b in fixture_books():
        L = b.lang
        if L.code in covered:
            continue
        try:
            c = para_json_from_tex(b, 0)["ann"]["sentences"][0]["chunks"][0]
        except Exception as e:
            bad("%s: reading a chunk for the studio" % L.code, repr(e))
            continue
        md = "---\ntitle: %s fixture\ntarget: %s\n---\n\n[%s]{tl} = *%s*\n" % (
            L.name, L.code, c["fa"], c["en"].rstrip(".,"))
        try:
            doc = htmlgen.render_document(md)
            fm, blocks = mdparser.parse(md)
            tex = texgen.generate(fm, blocks)
            check(doc.get("target") == L.code and "exlex-target: %s" % L.code in tex,
                  "a document in %s renders and carries its target" % L.name)
            check('class="fa' in doc["html"] and 'lang="%s"' % L.code in doc["html"]
                  and 'dir="%s"' % L.dir in doc["html"],
                  "%s: the marked run carries lang and dir" % L.name)
            body = tex[tex.index("\\begin{document}"):]
            check(("\\beginR" in body) == L.rtl,
                  "%s: RTL primitives only in an RTL document's body" % L.name)
        except Exception:
            import traceback
            bad("a document in %s renders" % L.name, traceback.format_exc()[-800:])
    # the library ships empty as well: the studio is proved on the examples
    # above, and on whatever documents happen to be filed
    docs = studio.store.list_docs()
    if docs:
        check(all(d.get("target") for d in docs), "library documents carry a target (%s)"
              % ", ".join("%s:%s" % (d["id"], d.get("target")) for d in docs))
    else:
        skip("the library is empty: the studio is tried on the documents "
             "under exlex/examples/ and tests/fixtures/studio/ alone")
    for d in docs:
        folder = os.path.basename(os.path.dirname(str(studio.store._doc_dir(d["id"]))))
        import languages
        check(languages.by_folder(folder) is not None and languages.by_folder(folder).code == d.get("target"),
              "%s sits under library/%s" % (d["id"], folder))
    css = studio.languages.css() if hasattr(studio, "languages") else None
    check(css is None or "--tl-font-ja" in css, "the studio can serve langs.css")
    if pdf:
        section("studio: XeLaTeX")
        for name, code in want.items():
            base = os.path.basename(name)
            with tempfile.TemporaryDirectory() as td:
                rc, out = run([PY, os.path.join(STUDIO, "exlex", "exlex.py"), "build",
                               os.path.join(ROOT, name), "-o", td, "-q"], cwd=STUDIO, timeout=900)
                m = re.search(r"verify: (\d+)/(\d+)", out)
                good = rc == 0 and m and m.group(1) == m.group(2)
                check(good, "%s builds and verifies (%s)" % (name, m.group(0) if m else out[-300:]), out[-600:])
                # A fixture's count is a property of that exact document, so
                # it is pinned: 186 is what section 11 of docs/languages.md
                # promises of the Persian one, and 21 is what the feature test
                # has always carried (8 the recordings fixture's) -- a number that
                # moves without the document moving is the regression these
                # builds exist to catch.
                pinned = {"persiano.md": "186", "feature-test.md": "21", "audio.md": "8"}
                if base in pinned and m:
                    check(m.group(2) == pinned[base],
                          "%s still checks %s strings" % (base, pinned[base]),
                          m.group(0))


# ------------------------------------------------------------------ divide
def test_divide():
    """lib/chunkdiv.py and the two writers: where a chunk ends, moved.

    The strongest thing that can be said about surgery on a file is that it
    can be undone, so most of this is a round trip: join the first two chunks
    of every fixture edition and every fixture video, cut the result back at
    the seam they were joined on, and require the file to be the file it was
    BYTE FOR BYTE -- the .tex with its indentation and its line endings, the
    .json with its own indent and its own key order.  A merge that dropped a
    field, a split that reflowed a line or a writer that normalised something
    on the way past would all show up as a difference here and nowhere else.

    Then the refusals, which are the other half of the feature: a chunk is
    divided at the places its language divides and nowhere else, and both
    writers say so in words rather than writing a file the checkers will
    reject afterwards.  What neither refuses is the gloss a cut leaves: a
    half left with no meaning is written, half glossed, for the chunk sheet
    to finish, and a chunk nobody has glossed yet divides in any book and any
    video into two blank halves -- in a language divided into words, each
    proposed the reading of its own words.
    """
    section("divide")
    import chunkdiv
    import languages
    import texwrite as X
    if YT_LIB not in sys.path:
        sys.path.insert(0, YT_LIB)
    import annwrite as A
    F = ("col", "fa", "kana", "tr", "voc", "en")

    # --- the rule itself, in every language the registry has
    for code in languages.CODES:
        L = languages.get(code)
        if L.spaced:
            got = [(c["a"], c["b"]) for c in chunkdiv.cuts("one two three", L)]
            check(got == [("one", "two three"), ("one two", "three")],
                  "%s: a chunk divides at each of its spaces and nowhere else"
                  % L.name, repr(got))
            check(chunkdiv.cuts("single", L) == [],
                  "%s: a chunk of one word does not divide" % L.name)
        else:
            check(len(chunkdiv.cuts("abcd", L)) == 3,
                  "%s: no word separator, so it divides between any two "
                  "characters" % L.name)
    # every cut puts the text back together under the checkers' own comparison
    for code in languages.CODES:
        L = languages.get(code)
        text = "الْكِتَابُ جَدِيدٌ" if code == "ar" else "کتاب تازه است" if code == "fa" \
            else "今日は天気が" if code == "ja" else "one two three"
        bad = [c["at"] for c in chunkdiv.cuts(text, L)
               if _norm_join(L, [c["a"], c["b"]]) != _norm_join(L, [text])]
        check(not bad, "%s: every place it divides joins back to the text"
              % L.name, repr(bad))

    # the pieces a page draws put the text back together, and no offset
    # arithmetic is asked of it (Python counts code points, JavaScript
    # counts UTF-16 units, and one astral character parts the two)
    for code in languages.CODES:
        L = languages.get(code)
        for text in ("one two three", "a\U0001F600b c", "x"):
            ps = chunkdiv.pieces(text, L)
            back = "".join(p_["text"] + p_["sep"] for p_ in ps)
            check(back == text, "%s: the pieces of %r are that text again"
                  % (L.name, text), repr(ps))
            check(len(ps) == len(chunkdiv.cuts(text, L)) + 1,
                  "%s: one gap between the pieces for each place it divides"
                  % L.name)
        # a gap that is not the separator is not a place: rejoining puts an
        # ordinary space there and the character is gone from the file
        if L.spaced:
            check(chunkdiv.cuts("a\tb", L) == [],
                  "%s: a tab is not a place to divide" % L.name)
            check(chunkdiv.cuts("a\u00a0b", L) == [],
                  "%s: a non-breaking space is not a place to divide" % L.name)

    # --- a book: joined, then cut back, byte for byte
    for b in fixture_books():
        src = b.dir
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, b.slug)
            shutil.copytree(src, d, ignore=shutil.ignore_patterns(
                "reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
            p = os.path.join(d, os.path.basename(b.main).replace("main.tex", "ch1.tex"))
            p = p if os.path.isfile(p) else os.path.join(d, "ch1.tex")
            before = io.open(p, encoding="utf-8", newline="").read()
            was = X.read_chunks(p)
            tag = "%s [%s]" % (b.slug, b.lang.code)
            if len(was) < 2:
                skip("%s: fewer than two chunks, nothing to join" % tag)
                continue
            try:
                r = X.merge_chunks(p, 0)
                check(r["chunks"] == len(was) - 1,
                      "%s: joining two chunks leaves %d" % (tag, len(was) - 1))
                check(r["fidelity"].startswith("ok") or "not checked" in r["fidelity"],
                      "%s: the paragraph still reproduces its source" % tag,
                      r["fidelity"])
                merged = X.read_chunks(p)[0]
                at = [c["at"] for c in chunkdiv.cuts(merged["fa"], b.lang)
                      if c["a"] == was[0]["fa"]]
                check(bool(at), "%s: the seam they were joined on is a place "
                                "the joined chunk divides" % tag)
                if at:
                    X.split_chunk(p, 0, {f: was[0].get(f, "") for f in F},
                                  {f: was[1].get(f, "") for f in F})
                    now = io.open(p, encoding="utf-8", newline="").read()
                    check(now == before, "%s: joined and cut back, the chapter "
                                         "is the chapter byte for byte" % tag,
                          _first_diff(now, before))
            except X.Refused as e:
                bad("%s: the first two chunks divide" % tag, str(e)[:300])

    # --- a video: the same round trip
    for fx in sorted(glob.glob(os.path.join(FIX, "videos", "*", "*", "video.json"))):
        src = os.path.dirname(fx)
        vid = os.path.basename(src)
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, vid)
            shutil.copytree(src, d)
            ap = os.path.join(d, "annotations.json")
            before = io.open(ap, encoding="utf-8").read()
            ann = json.load(io.open(ap, encoding="utf-8"))
            L = languages.get_or_default(
                json.load(io.open(fx, encoding="utf-8")).get("language"))
            si = next((i for i, sg in enumerate(ann["segments"])
                       if len(sg.get("chunks") or []) >= 2), None)
            if si is None:
                skip("%s: no caption with two chunks to join" % vid)
                continue
            was = [dict(c) for c in ann["segments"][si]["chunks"]]
            try:
                r = A.merge_chunks(d, si, 0)
                check(r["count"] == len(was) - 1,
                      "%s: joining two chunks leaves %d" % (vid, len(was) - 1))
                merged = r["chunks"][0]
                at = [c["at"] for c in chunkdiv.cuts(merged["fa"], L)
                      if c["a"] == was[0]["fa"]]
                check(bool(at), "%s: the seam is a place the joined chunk "
                                "divides" % vid)
                if at:
                    A.split_chunk(d, si, 0, was[0], was[1])
                    now = io.open(ap, encoding="utf-8").read()
                    check(now == before, "%s: joined and cut back, "
                          "annotations.json is itself byte for byte" % vid,
                          _first_diff(now, before))
            except ValueError as e:
                bad("%s: the first two chunks of a caption divide" % vid,
                    str(e)[:300])

    # the last chunk of a file has nothing after it: a preview says so and
    # does not fall over, which is what the sheet's two buttons both begin with
    for b in fixture_books():
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, b.slug)
            shutil.copytree(b.dir, d, ignore=shutil.ignore_patterns(
                "reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
            p = os.path.join(d, "ch1.tex")
            n = len(X.read_chunks(p))
            try:
                r = X.divide_preview(p, n - 1)
                check(r["merge"] is None and bool(r["merge_error"]),
                      "%s: the last chunk previews, with a reason it cannot be "
                      "joined" % b.slug, json.dumps(r.get("merge_error")))
            except Exception as e:
                bad("%s: the last chunk previews" % b.slug, repr(e))

    # a chapter written on Windows keeps its line endings through a division,
    # and both operations round-trip on it too
    bkc = next((b for b in fixture_books() if b.lang.code == "fa"), None)
    if bkc is not None:
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, bkc.slug)
            shutil.copytree(bkc.dir, d, ignore=shutil.ignore_patterns(
                "reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
            p = os.path.join(d, "ch1.tex")
            t = io.open(p, encoding="utf-8", newline="").read()
            io.open(p, "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n"))
            before = io.open(p, encoding="utf-8", newline="").read()
            cs = X.read_chunks(p)
            was = {f: cs[0].get(f, "") for f in F}
            cut = chunkdiv.cuts(was["fa"], bkc.lang)[0]
            X.split_chunk(p, 0, dict(was, fa=cut["a"]), dict(was, fa=cut["b"]))
            mid = io.open(p, encoding="utf-8", newline="").read()
            check("\n" not in mid.replace("\r\n", ""),
                  "a CRLF chapter keeps its line endings through a cut")
            X.merge_chunks(p, 0, was)
            check(io.open(p, encoding="utf-8", newline="").read() == before,
                  "cut then joined back, the CRLF chapter is itself byte for byte")

    # --- what both refuse
    fa = languages.get("fa")
    bk = next((b for b in fixture_books() if b.lang.code == "fa"), None)
    if bk is None:
        skip("no Persian fixture edition: the book refusals are not tried")
    else:
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, bk.slug)
            shutil.copytree(bk.dir, d, ignore=shutil.ignore_patterns(
                "reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
            p = os.path.join(d, "ch1.tex")
            cs = X.read_chunks(p)
            half = lambda i, **kw: dict({f: cs[i].get(f, "") for f in F}, **kw)
            seam = next((i for i in range(len(cs) - 1)
                         if cs[i]["label"] != cs[i + 1]["label"]), None)
            tries = [
                ("a cut through the middle of a word",
                 lambda: X.split_chunk(p, 0, half(0, fa=cs[0]["fa"][:4]),
                                       half(1, fa=cs[0]["fa"][4:]))),
                ("joining past the last chunk",
                 lambda: X.merge_chunks(p, len(cs) - 1)),
            ]
            if seam is not None:
                tries.append(("joining across a subparagraph",
                              lambda: X.merge_chunks(p, seam)))
            for name, fn in tries:
                try:
                    fn()
                    bad("texwrite refuses %s" % name, "it was written")
                except X.Refused as e:
                    check(bool(str(e).strip()),
                          "texwrite refuses %s, and says why" % name)
            # a comment between two chunks is something, and is not swallowed
            txt = io.open(p, encoding="utf-8", newline="").read()
            end = X.read_chunks(p)[0]["span"][1]
            io.open(p, "w", encoding="utf-8", newline="").write(
                txt[:end] + "\n% @par 1.1 0.0 1.0" + txt[end:])
            try:
                X.merge_chunks(p, 0)
                bad("texwrite refuses a join over a comment", "it was written")
            except X.Refused as e:
                check("per cent" in str(e) or "between them" in str(e),
                      "texwrite refuses a join that would swallow a comment",
                      str(e)[:200])

    # a join moves the boundary and changes no letter, as a cut does not --
    # without this the promise holds only where the fidelity check can judge
    if bk is not None:
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, bk.slug)
            shutil.copytree(bk.dir, d, ignore=shutil.ignore_patterns(
                "reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
            p = os.path.join(d, "ch1.tex")
            cs = X.read_chunks(p)
            try:
                X.merge_chunks(p, 0, dict({f: cs[0].get(f, "") for f in F},
                                          fa="SOMETHING ELSE ENTIRELY"))
                bad("texwrite refuses a join that rewrites the text",
                    "it was written")
            except X.Refused as e:
                check("changes no letter" in str(e),
                      "texwrite refuses a join that rewrites the text",
                      str(e)[:200])

    # ...and what it does NOT refuse: the gloss a cut leaves on either side.
    # A cut moves a boundary and the gloss comes along as it was, so a half
    # left with no meaning is written, half glossed -- check_batch lists it
    # and the chunk sheet is where it is finished, not the cut
    if bk is not None:
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, bk.slug)
            shutil.copytree(bk.dir, d, ignore=shutil.ignore_patterns(
                "reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
            p = os.path.join(d, "ch1.tex")
            cs = X.read_chunks(p)
            at = chunkdiv.cuts(cs[0]["fa"], fa)[0]
            whole = {f: cs[0].get(f, "") for f in F}
            try:
                X.split_chunk(p, 0, dict(whole, fa=at["a"]),
                              dict(whole, fa=at["b"], en=""))
                got = X.read_chunks(p)[:2]
                check([(g["fa"], bool(g["en"]), g["tr"]) for g in got]
                      == [(at["a"], True, whole["tr"]), (at["b"], False, whole["tr"])],
                      "texwrite writes a half left with no meaning: the gloss a cut "
                      "leaves is not the cut's to refuse",
                      repr([(g["fa"], g["en"]) for g in got]))
            except X.Refused as e:
                bad("texwrite writes a half left with no meaning", str(e)[:300])

    vfx = sorted(glob.glob(os.path.join(FIX, "videos", "*", "*", "video.json")))
    if not vfx:
        skip("no fixture video: the player's refusals are not tried")
    else:
        src = os.path.dirname(vfx[0])
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, os.path.basename(src))
            shutil.copytree(src, d)
            ann = json.load(io.open(os.path.join(d, "annotations.json"), encoding="utf-8"))
            plain = next((i for i, sg in enumerate(ann["segments"])
                          if sg.get("plain")), None)
            si = next(i for i, sg in enumerate(ann["segments"])
                      if len(sg.get("chunks") or []) >= 1)
            n = len(ann["segments"][si]["chunks"])
            tries = [("joining the last chunk of a caption",
                      lambda: A.merge_chunks(d, si, n - 1)),
                     ("a chunk that is not there",
                      lambda: A.split_chunk(d, si, 99, {}, {}))]
            if plain is not None:
                tries.append(("dividing a plain caption",
                              lambda: A.merge_chunks(d, plain, 0)))
            for name, fn in tries:
                try:
                    fn()
                    bad("annwrite refuses %s" % name, "it was written")
                except ValueError as e:
                    check(bool(str(e).strip()),
                          "annwrite refuses %s, and says why" % name)
            # what a page may set is EDITABLE and nothing else: `plain`
            # decides whether a chunk is asked for a gloss at all, and is the
            # author's; the note is the person's to edit, and a divide that
            # sends none carries it across (annwrite._CARRIED)
            pv = next((A.divide_preview(d, i, k)
                       for i, sg in enumerate(ann["segments"])
                       for k in range(len(sg.get("chunks") or []))
                       if not sg.get("plain")
                       and A.divide_preview(d, i, k)["cuts"]), None)
            if pv is None:
                skip("no divisible chunk in this video: what a page may set "
                     "is not tried")
            else:
                cut = pv["cuts"][0]
                half = lambda side: {k: cut[side].get(k, "")
                                     for k in ("fa", "tr", "voc", "en")}
                for key, val in (("plain", True), ("zz", "x")):
                    try:
                        A.split_chunk(d, pv["segment"], pv["index"],
                                      dict(half("first"), **{key: val}),
                                      half("second"))
                        bad("annwrite refuses a page setting %r" % key,
                            "it was written")
                    except ValueError as e:
                        check("cannot set" in str(e)
                              and ("gloss at all" in str(e)) == (key == "plain"),
                              "annwrite refuses a page setting %r%s" % (key,
                              ", and says why" if key == "plain" else ""),
                              str(e)[:160])
                # and a field that is not text is a sentence, not a traceback
                broke = json.load(io.open(os.path.join(d, "annotations.json"),
                                          encoding="utf-8"))
                broke["segments"][pv["segment"]]["chunks"][pv["index"]]["tr"] = 7
                json.dump(broke, io.open(os.path.join(d, "annotations.json"),
                                         "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
                try:
                    A.divide_preview(d, pv["segment"], pv["index"])
                    bad("annwrite refuses a chunk whose field is not text",
                        "it was accepted")
                except ValueError as e:
                    check("is int" in str(e),
                          "annwrite refuses a chunk whose field is not text",
                          str(e)[:160])
                except Exception as e:
                    bad("annwrite refuses a chunk whose field is not text",
                        repr(e))
                json.dump(ann, io.open(os.path.join(d, "annotations.json"),
                                       "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)

    # A CHUNK NOBODY HAS GLOSSED YET DIVIDES IN ANY VIDEO.  Nothing is asked
    # first -- there is no flag to ask -- and re-chunking is wanted most
    # exactly while the gloss is still to come.  In every fixture video a
    # glossed chunk has its gloss taken off through the door the player's
    # "delete gloss" uses, is divided where the preview proposes, and leaves
    # two blank halves the checker passes.
    import check_annotations as CA
    for fx in vfx:
        src = os.path.dirname(fx)
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, os.path.basename(src))
            shutil.copytree(src, d)
            L = languages.get_or_default(
                json.load(io.open(fx, encoding="utf-8")).get("language"))
            tag = "%s [%s]" % (os.path.basename(src), L.code)
            segs = A.read(d)["segments"]
            # a chunk that HAS somewhere to divide, wherever it is in the
            # video: the first one may well be a single word
            where = next(((i, k) for i, sg in enumerate(segs) if not sg.get("plain")
                          for k, c in enumerate(sg.get("chunks") or [])
                          if CA.required(c, L) and not CA.unwritten(c, L)
                          and chunkdiv.cuts(c.get("fa") or "", L)), None)
            if where is None:
                skip("%s: no glossed chunk divides, so a blank one is not "
                     "divided" % tag)
                continue
            i, k = where
            try:
                A.edit_chunk(d, i, k, dict({"tr": "", "voc": "", "en": ""},
                                           **({"kana": ""} if L.reading else {})))
                pv = A.divide_preview(d, i, k)
                cut = pv["cuts"][len(pv["cuts"]) // 2]
                sent = lambda side: {f: v for f, v in cut[side].items()
                                     if f in A.EDITABLE}
                A.split_chunk(d, i, k, sent("first"), sent("second"))
                now = A.read(d)["segments"][i]["chunks"][k:k + 2]
                errors = CA.check(d)[0]
                check([c["fa"] for c in now] == [cut["a"], cut["b"]]
                      and all(CA.unwritten(c, L) for c in now) and not errors,
                      "%s: a chunk whose gloss was deleted divides into two blank "
                      "halves, and the video still checks" % tag,
                      repr((now, errors[:2])))
            except ValueError as e:
                bad("%s: a chunk whose gloss was deleted divides" % tag, str(e)[:300])

    # ...and a blank chunk of a language divided into words carries the
    # reading proposed from its word line, which a cut cannot divide by
    # itself: each half is proposed the reading of its OWN words, so both
    # halves are as blank as the chunk was -- in a drafted video and in a
    # drafted book alike, not a first half holding the whole reading and
    # counted as half glossed
    import draft
    import words
    import wordline
    for L in (languages.get(c) for c in languages.CODES):
        if not L.words:
            continue
        if not words.available(L.code):
            skip("no analyzer for %s here: a drafted chunk carries no proposed "
                 "reading to divide" % L.name)
            continue
        vj = next((v for v in vfx if json.load(io.open(v, encoding="utf-8"))
                   .get("language") == L.code), None)
        bk_ = next((b for b in fixture_books() if b.lang.code == L.code), None)
        with tempfile.TemporaryDirectory() as td:
            doors = []
            if vj is not None:
                meta = json.load(io.open(vj, encoding="utf-8"))
                r = draft.video_from_transcript(
                    io.open(os.path.join(os.path.dirname(vj), "transcript.txt"),
                            encoding="utf-8").read(), L, video_id=meta["id"],
                    into=os.path.join(td, "videos"))
                doors.append(("video", r["dir"]))
            if bk_ is not None:
                text = io.open(sorted(glob.glob(os.path.join(bk_.paras_dir, "*.txt")))[0],
                               encoding="utf-8").read().strip()
                r = draft.book_from_text(text, L, bk_.title, slug="split-" + L.code,
                                         into=os.path.join(td, "books"))
                doors.append(("book", os.path.join(r["dir"], "ch1.tex")))
            for door, at in doors:
                tag = "a drafted %s [%s]" % (door, L.code)
                if door == "video":
                    segs = A.read(at)["segments"]
                    i, k = next((i, k) for i, sg in enumerate(segs)
                                for k, c in enumerate(sg.get("chunks") or [])
                                if c.get("words") and chunkdiv.cuts(c["fa"], L))
                    chunk = segs[i]["chunks"][k]
                    preview = lambda: A.divide_preview(at, i, k)
                else:
                    k = next(n for n, c in enumerate(X.read_chunks(at))
                             if c["words"] and chunkdiv.cuts(c["fa"], L))
                    chunk = X.read_chunks(at)[k]
                    preview = lambda: X.divide_preview(at, k)
                field, proposal = wordline.seed(chunk, L)
                check(bool(field) and chunk[field] == proposal
                      and CA.unwritten(chunk, L),
                      "%s: the chunk carries the reading proposed from its words, "
                      "and is blank" % tag, repr(chunk))
                cuts = preview()["cuts"]
                wrong = [(c["a"], h, c[h].get(field)) for c in cuts
                         for h in ("first", "second")
                         if not CA.unwritten(c[h], L)
                         or (c[h].get(field) or "") != wordline.seed(c[h], L)[1]]
                check(bool(cuts) and not wrong,
                      "%s: every cut proposes two blank halves, each with the "
                      "reading of its own words (%d cuts)" % (tag, len(cuts)),
                      repr(wrong[:3]))
                cut = cuts[len(cuts) // 2]
                try:
                    if door == "video":
                        keep = lambda h: {f: v for f, v in cut[h].items()
                                          if f in A.EDITABLE}
                        A.split_chunk(at, i, k, keep("first"), keep("second"))
                        now = A.read(at)["segments"][i]["chunks"][k:k + 2]
                    else:
                        keep = lambda h: {f: v for f, v in cut[h].items()
                                          if f in X.FIELDS}
                        X.split_chunk(at, k, keep("first"), keep("second"))
                        now = X.read_chunks(at)[k:k + 2]
                    check([c["fa"] for c in now] == [cut["a"], cut["b"]]
                          and all(CA.unwritten(c, L) for c in now),
                          "%s: divided, both halves are written blank" % tag,
                          repr([(c["fa"], c.get(field)) for c in now]))
                except ValueError as e:
                    bad("%s: a blank chunk divides" % tag, str(e)[:300])


def _norm_join(L, parts):
    """The chunks joined and normalised the way both checkers compare them."""
    s = L.strip((L.word_sep or "").join(parts))
    return re.sub(r"\s+", " ", s).strip() if L.spaced else re.sub(r"\s+", "", s)


def _first_diff(got, want):
    i = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b),
             min(len(got), len(want)))
    return "at %d: got %r want %r" % (i, got[i - 40:i + 40], want[i - 40:i + 40])


# ------------------------------------------------------------------- notes
def test_notes():
    """The notes that sit in the seams of a book or a video.

    A note is a studio document kept with the content instead of with the
    studio's library, and almost none of it is new code -- so almost all of
    this is about the two things that ARE: that the store can be pointed at
    another library and put back, and that a note says where it sits in its
    own front matter.  The rest is the studio's, and the studio's tests are
    what cover it.

    The line that matters most here is the last one: no prompt names this
    feature.  A note is somebody's own reading of their own book, and a model
    has nothing to put in one; a prompt that started asking for notes would
    fill the seams with the very thing the seams exist to escape.
    """
    section("notes")
    sys.path.insert(0, os.path.join(STUDIO, "app"))
    sys.path.insert(0, os.path.join(STUDIO, "exlex"))
    import notes
    import store
    import bundle
    import languages

    # --- the anchor: three words, and what is refused
    for side, kind, at in (("after", "sub", "۱.۲-6f8f21d7175b"),
                           ("before", "cap", "126")):
        text = notes.format_anchor(side, kind, at)
        got = notes.parse_anchor(text)
        check(got == {"side": side, "kind": kind, "at": at},
              "an anchor is written and read back the same (%s)" % text, repr(got))
    for bad in (("sideways", "sub", "x"), ("after", "chapter", "x"),
                ("after", "sub", "two words")):
        try:
            notes.format_anchor(*bad)
            bad_("an anchor %r is refused" % (bad,), "it was accepted")
        except ValueError:
            check(True, "an anchor %r is refused" % (bad,))
    check(notes.parse_anchor("somewhere else") is None,
          "an anchor nobody can read is None and not an error")

    # --- WHAT A NOTE SAYS BEFORE IT IS OPENED.  Both readers show a card on
    # hover, and what is on it is `excerpt`: the note as the page would
    # print it, without the front matter it hides, the anchor line that
    # says where it sits, the markup, and the footnotes -- the inline one
    # whose `^[` and `]` fall on two lines included, which a line-by-line
    # reading let through whole.
    md = ("---\ntitle: The ezafe\nlang: en\ntarget: fa\nanchor: after sub 1.1-abc\n---\n\n"
          "anchor: before sub 1.2-def\n\n"
          "The **ezâfe** is *unwritten* here ^[an inline footnote\nthat must go] and "
          "the `speaker` drops it[^1].\nSee [the grammar](https://example.org) and "
          "[کتاب]{tl}.\n\n[^1]: a footnote definition\n    with a continuation line\n\n"
          "- one item\n- two items\n")
    ex = notes.excerpt(md)
    check(ex == "The ezâfe is unwritten here and the speaker drops it. See the grammar "
                "and کتاب.\n• one item\n• two items",
          "a note's excerpt is its text as the page prints it, a line per block",
          repr(ex))
    leaked = [x for x in ("title:", "anchor", "1.1-abc", "**", "^[", "[^", "](", "]{",
                          "`", "footnote", "continuation") if x in ex]
    check(not leaked, "and nothing of its front matter, its anchor, its markup or "
                      "its footnotes", repr(leaked))
    words = " ".join("word%d" % i for i in range(200))
    ex = notes.excerpt("---\ntitle: t\ntarget: fa\n---\n\n" + words)
    check(len(ex) <= 280 and ex.endswith("…") and words.startswith(ex[:-1])
          and words[len(ex) - 1] == " ",
          "a long note is cut to 280 characters between two words, with an "
          "ellipsis", "%d: %r" % (len(ex), ex[-30:]))
    check(notes.excerpt("---\ntitle: t\n---\n") == "",
          "and a note that says nothing yet has nothing to preview")

    # --- a note beside a book, and the studio's own library left alone
    was_lib = store.lib()
    with tempfile.TemporaryDirectory() as td:
        content = os.path.join(td, "a-book")
        os.makedirs(content)
        with notes.library(content):
            check(store.lib() == notes.dir_for(content),
                  "inside the block the store is pointed at the content's notes")
            m = notes.create(content, "after", "sub", "۱.۱-abc123", "fa")
            n2 = notes.create(content, "before", "cap", "6", "fa")
            got = {n["id"]: n["anchor"] for n in notes.index(content)}
            check(got.get(m["id"]) == {"side": "after", "kind": "sub",
                                       "at": "۱.۱-abc123"},
                  "a note carries the anchor it was made at", repr(got))
            # the preview rides on the same list the marks are drawn from,
            # so a hover asks the server nothing of its own
            said = {n["id"]: n.get("excerpt") for n in notes.index(content)}
            check(said.get(m["id"]) == notes.excerpt(notes.starter(
                      "after", "sub", "۱.۱-abc123", "fa")) and said.get(m["id"]),
                  "and its excerpt, in the list the marks are drawn from",
                  repr(said.get(m["id"])))
            # the file is the truth: moving a note is editing one line of it
            _meta, md = store.get(n2["id"])
            store.save_markdown(n2["id"], md.replace("before cap 6", "after cap 240"))
            moved = {n["id"]: n["anchor"] for n in notes.index(content)}[n2["id"]]
            check(moved == {"side": "after", "kind": "cap", "at": "240"},
                  "a note moved by hand moves", repr(moved))
            store.save_markdown(n2["id"], md.replace("anchor: before cap 6",
                                                     "anchor: nowhere at all"))
            adrift = {n["id"]: n["anchor"] for n in notes.index(content)}[n2["id"]]
            check(adrift is None,
                  "a note whose anchor will not read is adrift, not dropped")
            where = os.path.relpath(str(store.doc_dir(m["id"])), content)
            check(where.split(os.sep)[0] == notes.DIR,
                  "a note lives under the content's own %s/" % notes.DIR, where)
        check(store.lib() == was_lib,
              "outside the block the studio's own library is back")

    # --- and they travel, in every shape of every bundle
    for b in fixture_books():
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, b.slug)
            shutil.copytree(b.dir, d, ignore=shutil.ignore_patterns(
                "reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
            with notes.library(d):
                notes.create(d, "after", "sub", "1.1-x", b.lang.code)
            for mode in bundle.MODES:
                data, _name = bundle.pack_book(d, mode)
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    got = [n for n in z.namelist() if "/%s/" % notes.DIR in n]
                check(len(got) == 2,
                      "%s: a `%s` bundle carries the note beside the book"
                      % (b.slug, mode), repr(got))
            with tempfile.TemporaryDirectory() as into:
                r = bundle.install(data, root=into)
                back = [f for f in r["files"] if notes.DIR + "/" in f]
                check(len(back) == 2, "%s: and puts it back" % b.slug, repr(back))
        break                       # one edition proves the shape for all
    for fx in sorted(glob.glob(os.path.join(FIX, "videos", "*", "*", "video.json")))[:1]:
        src = os.path.dirname(fx)
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, os.path.basename(src))
            shutil.copytree(src, d)
            with notes.library(d):
                notes.create(d, "before", "cap", "6", "fa")
            data, _name = bundle.pack_video(d)
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                got = [n for n in z.namelist() if "/%s/" % notes.DIR in n]
            check(len(got) == 2, "a video's bundle carries its notes", repr(got))

    # --- the seams a page draws them into
    import tex2html
    for b in fixture_books()[:1]:
        html = os.path.join(b.dir, "reader", "index.html")
        if not os.path.isfile(html):
            skip("no built reader for %s: the seams are not counted" % b.slug)
            continue
        page = open(html, encoding="utf-8").read()
        subs_n = page.count('class="sub')
        gaps = page.count('class="gap')
        check(gaps == subs_n + 1,
              "%s: one seam before every subparagraph and one after the last "
              "(%d for %d)" % (b.slug, gaps, subs_n))
        check('data-at=' in page and 'data-after=' in page,
              "%s: a seam names the line above it and the line below it, so "
              "`after X` and `before Y` are two spellings of one place" % b.slug)
    check("'../notes'" in tex2html.JS, "the reader asks its book for its notes")
    player = open(os.path.join(YT_LIB, "player.js"), encoding="utf-8").read()
    check("CFG.notes" in player, "the player asks its video for its notes")
    check("class = 'gap'" in player or "className = 'gap'" in player,
          "the player draws a seam between two captions")

    # --- a note is never built, and never asked for by a machine
    server = open(os.path.join(STUDIO, "app", "server.py"), encoding="utf-8").read()
    for fn in ("def serve_pdf", "def api_build"):
        i = server.index(fn)
        check("html_only()" in server[i:i + 400],
              "%s refuses on a notes mount" % fn.split()[1])
    prompts = [os.path.join(ROOT, "youtube", "docs", "chat-prompt.md"),
               os.path.join(ROOT, "youtube", "docs", "conventions.md"),
               os.path.join(ROOT, "docs", "new-book-prompt.md"),
               os.path.join(STUDIO, "exlex", "PROMPT.md")]
    leaked = []
    for f in prompts:
        if not os.path.isfile(f):
            continue
        text = open(f, encoding="utf-8").read().lower()
        for word in ("anchor:", "markdown/ directory", "a note in the seam",
                     "notes/api", "write a note here"):
            if word in text:
                leaked.append("%s: %r" % (os.path.basename(f), word))
    check(not leaked, "no prompt tells a model to write a note", "; ".join(leaked))


def bad_(what, detail=""):
    bad(what, detail)


# ------------------------------------------------------------------ lookup
def _fixture_dict(path, code, rows):
    """A dictionary of a dozen words, built here rather than downloaded.

    The real ones are 3-300 MB of somebody else's work; what the tests need
    to know is whether the cascade finds a word, not whether Wiktionary has
    it.  `rows` is [(headword, translit, pos, senses, [(form, note), ...])].
    """
    import lookup as lk
    c = lk.create(path)
    for head, tr, pos, senses, forms in rows:
        cur = c.execute("INSERT INTO entry (headword, translit, pos, sense) "
                        "VALUES (?,?,?,?)", (head, tr, pos, "\n".join(senses)))
        eid = cur.lastrowid
        for form, note in [(head, "")] + list(forms):
            for v in {form, form.casefold()}:
                c.execute("INSERT INTO form (form, entry_id, note) VALUES (?,?,?)",
                          (v, eid, note))
    c.executemany("INSERT INTO meta (key, value) VALUES (?,?)",
                  [("lang", code), ("source", "a fixture"), ("licence", "none"),
                   ("built", "2026-09-07"), ("entries", str(len(rows)))])
    c.commit()
    c.close()


def _tiny_dict(path, code, entries):
    """A dictionary of a few entries, every row exactly as written.

    _fixture_dict writes each form twice, as spelt and case-folded, which is
    right for a test of the cascade and wrong for one of the RANKING: what
    decides the order of hits is exactly the detail it smooths over -- a row
    with an empty note, a name's lower-case copy, a note that says
    `auxiliary`.  So here each row is the one given, in the order given, and
    the headword's own row (note '') first, as lib/getdict.py writes an
    entry.

    `entries` is [(headword, pos, translit, ipa, [(form, note[, roman[,
    ipa]]), ...])], everything after pos optional.  -> the ids, in order.
    """
    import lookup as lk
    c = lk.create(path)
    ids = []
    for e in entries:
        e = tuple(e) + ("", "", [])[len(e) - 2:]
        head, pos, tr, ipa, forms = e[:5]
        cur = c.execute("INSERT INTO entry (headword, translit, ipa, pos, sense) "
                        "VALUES (?,?,?,?,?)", (head, tr, ipa, pos, "a sense of " + head))
        ids.append(cur.lastrowid)
        for row in [(head, "")] + list(forms):
            form, note, roman, fipa = (tuple(row) + ("", ""))[:4]
            c.execute("INSERT INTO form (form, entry_id, note, roman, ipa) "
                      "VALUES (?,?,?,?,?)", (form, cur.lastrowid, note, roman, fipa))
    c.executemany("INSERT INTO meta (key, value) VALUES (?,?)",
                  [("lang", code), ("source", "a fixture"), ("licence", "none")])
    c.commit()
    c.close()
    return ids


class _DictDir:
    """lib/lookup.py pointed at a scratch dict/ for the length of a block.

    Every connection is closed and every built \\vb forgotten on the way in
    and on the way out: each case here is its own file, and a connection --
    or a cached verb entry -- left over from the last one must not answer
    for it, nor keep a deleted file open."""

    def __init__(self, where):
        self.where = where

    @staticmethod
    def forget():
        import lookup as lk
        have = getattr(lk._CONNS, "map", None) or {}
        for conn, _stamp in have.values():
            try:
                conn and conn.close()
            except Exception:
                pass
        lk._CONNS.map = {}
        try:
            import verbs
            verbs.clear_cache()
        except ImportError:
            pass

    def __enter__(self):
        import lookup as lk
        self.was = lk.DICT_DIR
        lk.DICT_DIR = self.where
        self.forget()
        return self

    def __exit__(self, *exc):
        import lookup as lk
        lk.DICT_DIR = self.was
        self.forget()
        return False


def test_chunker():
    """The two ways a draft may be cut, and the promise both of them keep."""
    section("chunker")
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    import chunker
    import languages

    check(chunker.DEFAULT_WAY == "sentence",
          "a draft is still cut one chunk per sentence unless somebody asks "
          "otherwise: that is what every book and video here already holds")
    check(set(chunker.WAYS) == {"sentence", "phrase"}
          and all(w in chunker.WAY_LABEL for w in chunker.WAYS),
          "and both ways are named where a page has to offer them",
          repr(chunker.WAYS))
    check("suggest" not in open(os.path.join(ROOT, "lib", "chunker.py"),
                                encoding="utf-8").read(),
          "and the chunker reaches for no model at all: it is the half that "
          "works with a dictionary and nothing else")
    try:
        chunker.chunk("x", "fa", "diagonally")
        why = "it was accepted"
    except ValueError as e:
        why = str(e)
    check("no such way" in why, "an unknown way is refused, not guessed at", why)

    # --- THE INVARIANT, which is the whole reason this may be trusted with a
    # text: whatever is cut, the pieces put back together are what came in.
    # Asked of real sentences in every language the toolbox teaches.
    SAY = {
        "fa": ["مرد پیر در تاریکی نشسته بود", "کتاب را خواندم",
               "او در تهران زندگی می‌کند", "سلام، ببخشید سیب چند است"],
        "ja": ["おばあさんは川で洗濯をしていました", "私は毎日日本語を勉強しています",
               "本を読んで映画を見ました", "はい"],
        "hi": ["बड़े घर में एक आदमी रहता था"],
        "en": ["the old man sat in the darkness"],
        "it": ["il vecchio sedeva nel buio"],
    }
    bad = []
    for code, lines in SAY.items():
        for line in lines:
            for way in chunker.WAYS:
                got = chunker.chunk(line, code, way)
                if not chunker.reproduces(got, line, code):
                    bad.append("%s/%s: %r -> %r" % (code, way, line, got))
    check(not bad, "however a line is cut, the chunks put back together are "
          "the line: %d lines in %d languages, both ways"
          % (sum(len(v) for v in SAY.values()), len(SAY)), "; ".join(bad[:3]))

    for code, lines in SAY.items():
        for line in lines:
            check(chunker.chunk(line, code, "sentence") == [line],
                  "and `sentence` is the sentence, untouched (%s)" % code)

    # --- WHAT THE PHRASE CUT IS FOR.  These are the cuts a reader wants, and
    # they are the reason any of this exists: a preposition with its noun, a
    # noun with its adjective, a verb with its auxiliary.
    if chunker.lookup.available("fa"):
        got = chunker.chunk("مرد پیر در تاریکی نشسته بود", "fa", "phrase")
        check(got == ["مرد پیر", "در تاریکی", "نشسته بود"],
              "Persian cuts into phrases: the noun with its adjective, the "
              "preposition with its noun, the verb with its auxiliary",
              " | ".join(got))
    else:
        skip("no dict/fa.db: the Persian phrase cut is not exercised")
    # Japanese never asks the dictionary: it is cut between SudachiPy's words
    # where lib/words.py has them, and off its characters where it has not --
    # the second cut here with the analyzer stood down, in any Python.
    import words as _words
    was = _words.parsed
    _words.parsed = lambda text, lang: []
    try:
        for line, want in (
                ("私は毎日日本語を勉強しています", ["私は", "毎日日本語を", "勉強しています"]),
                ("本を読んで映画を見ました", ["本を読んで", "映画を見ました"]),
                ("寒い朝に、窓を開ける。", ["寒い朝に、", "窓を開ける。"])):
            got = chunker.chunk(line, "ja", "phrase")
            check(got == want, "Japanese read off its characters is cut after a "
                  "mark, then after its particles, and the pieces grow into "
                  "phrases", " | ".join(got))
        one = chunker.chunk("私の本はここにあります", "ja", "phrase")
        check(all("の" not in c[-1:] for c in one),
              "and never after の, which binds a modifier to its noun the way "
              "an ezafe does", " | ".join(one))
    finally:
        _words.parsed = was
    if _words.available("ja"):
        for line, want in (
                ("おばあさんは桃を拾って、家に持って帰りました。",
                 ["おばあさんは", "桃を拾って、", "家に", "持って帰りました。"]),
                ("寒い朝に、窓を開ける。", ["寒い朝に、", "窓を開ける。"])):
            got = chunker.chunk(line, "ja", "phrase")
            check(got == want, "and between SudachiPy's words where it is "
                  "installed: a mark, a particle, a verb with its object",
                  " | ".join(got))
    else:
        skip("no SudachiPy in this Python: the Japanese cut between words is "
             "not exercised")

    # --- AND WHERE THERE IS NOTHING TO READ IT SAYS SO by doing nothing
    # clever: a language with no dictionary installed has no parts of speech
    # to cut by, and a cut made at random would be worse than none.
    nodict = next((L.code for L in languages.LANGS.values()
                   if not chunker.lookup.available(L.code) and L.spaced), None)
    if nodict:
        line = "one two three four five six seven"
        check(chunker.chunk(line, nodict, "phrase") == [line],
              "a language with no dictionary is not cut at random: a line "
              "with no punctuation stays whole (%s)" % nodict)
        said = "one two three, four five six"
        got = chunker.chunk(said, nodict, "phrase")
        check(got == ["one two three,", "four five six"],
              "and a line with a comma is cut at it, the one cue every writer "
              "prints (%s)" % nodict, " | ".join(got))
    else:
        skip("every language has a dictionary here: the fallback is not exercised")

    # --- AND THE CHOICE REACHES THE FILE.  Both doors take `how`, and a
    # request that says nothing gets what this toolbox has always written.
    if chunker.lookup.available("fa"):
        ways = _draft_ways()
        sent_tex, sent_n, sent_v = ways["sentence"]
        phr_tex, phr_n, phr_v = ways["phrase"]
        check(len(sent_tex) == 2 and sent_n == 2 and len(sent_v) == 2,
              "asked for sentences, a book and a video draft one chunk per "
              "sentence", "%d tex, %d counted, %d captions"
              % (len(sent_tex), sent_n, len(sent_v)))
        check(len(phr_tex) == 5 and phr_n == 5 and phr_v ==
              ["مرد پیر", "در تاریکی", "نشسته بود", "او در تهران", "زندگی می‌کند"],
              "and asked for sense groups, both cut the same phrases -- the "
              "book's .tex and the video's annotations agree",
              "%d tex, %d counted, %s" % (len(phr_tex), phr_n, " | ".join(phr_v)))
        import serve as _srv
        check(_srv.chunk_way({}) == "sentence"
              and _srv.chunk_way({"how": "phrase"}) == "phrase"
              and _srv.chunk_way({"how": "sideways"}) == "sentence",
              "a request that says nothing is cut the way it always was, and "
              "one that says something impossible is not obeyed")
    else:
        skip("no dict/fa.db: the drafts are not exercised both ways")


def test_append():
    """More text onto the end of a book that is already here."""
    section("append")
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    import draft
    import languages

    src = next((os.path.dirname(f) for f in
                sorted(glob.glob(os.path.join(FIX, "books", "persian", "*",
                                              "book.json")))), None)
    if not src:
        return skip("no Persian fixture book: appending is not exercised")
    MORE = ("مرد پیر در تاریکی نشسته بود.\n\nاو در تهران زندگی می‌کند.")

    # --- A NEW CHAPTER: its own file, its own line in main.tex
    with tempfile.TemporaryDirectory() as td:
        b = os.path.join(td, os.path.basename(src))
        shutil.copytree(src, b)
        was = sorted(draft.chapters_of(b))
        main_was = open(os.path.join(b, "main.tex"), encoding="utf-8").read()
        r = draft.add_to_book(b, MORE, how="sentence", chapter="new")
        check(r["chapter"] == was[-1] + 1 and r["where"] == "new",
              "text added as a new chapter takes the next number",
              json.dumps({k: r[k] for k in ("chapter", "where")}))
        now = sorted(draft.chapters_of(b))
        check(now == was + [was[-1] + 1],
              "and the book has one more chapter than it had", repr(now))
        made = os.path.join(b, "ch%d.tex" % r["chapter"])
        check(os.path.isfile(made), "whose .tex is on disk")
        tex = open(made, encoding="utf-8").read()
        check(tex.count("\\parstart{") == 2 and tex.count("\\chapend") == 1,
              "with a paragraph each and one end to the chapter",
              "%d parstart, %d chapend"
              % (tex.count("\\parstart{"), tex.count("\\chapend")))
        main_now = open(os.path.join(b, "main.tex"), encoding="utf-8").read()
        check("\\input{ch%d.tex}" % r["chapter"] in main_now,
              "and a line in main.tex, which is the only place the reading "
              "order is written down")
        check(main_now.startswith(main_was[:200]),
              "the rest of main.tex untouched")
        check(os.path.isfile(os.path.join(b, "source", "paras",
                                          "ch%d_p00.txt" % r["chapter"])),
              "the source paragraphs the fidelity checks read are written too")
        check(r["paragraphs"] == 2 and r["sentences"] == 2 and r["chunks"] == 2,
              "and the counts are of what was added, not of the book",
              json.dumps({k: r[k] for k in ("paragraphs", "sentences", "chunks")}))

    # --- MORE OF THE LAST CHAPTER: numbered on, nothing before it touched
    with tempfile.TemporaryDirectory() as td:
        b = os.path.join(td, os.path.basename(src))
        shutil.copytree(src, b)
        before = draft.chapters_of(b)
        last = before[-1]
        path = os.path.join(b, "ch%d.tex" % last)
        was = open(path, encoding="utf-8").read()
        n_was = was.count("\\parstart{")
        r = draft.add_to_book(b, MORE, how="sentence", chapter="last")
        check(r["chapter"] == last and r["where"] == "last",
              "text added to the end of the last chapter stays in it",
              json.dumps({k: r[k] for k in ("chapter", "where")}))
        check(draft.chapters_of(b) == before, "and makes no new chapter",
              "%r -> %r" % (before, draft.chapters_of(b)))
        now = open(path, encoding="utf-8").read()
        check(now.count("\\parstart{") == n_was + 2,
              "the paragraphs are numbered on from the ones already there",
              "%d -> %d" % (n_was, now.count("\\parstart{")))
        check(now.count("\\chapend") == 1,
              "and the chapter still ends exactly once: \\chapend moved to the "
              "new last paragraph", "%d" % now.count("\\chapend"))
        check(now.startswith(was.split("\\chapend")[0][:200]),
              "with everything that was written before it left alone")
        check(os.path.isfile(os.path.join(b, "source", "paras",
                                          "ch%d_p%02d.txt" % (last, n_was))),
              "and the new source paragraphs numbered on as well")

    # --- WHAT IT REFUSES, each with a sentence
    with tempfile.TemporaryDirectory() as td:
        b = os.path.join(td, os.path.basename(src))
        shutil.copytree(src, b)
        for text, where, want in ((" ", "new", "empty"),
                                  (MORE, "sideways", "no such place"),
                                  ("a $ b", "new", "LaTeX")):
            try:
                draft.add_to_book(b, text, chapter=where)
                why = "it was accepted"
            except ValueError as e:
                why = str(e)
            check(want.lower() in why.lower(),
                  "%r is refused with a sentence" % (want,), why[:90])
        try:
            draft.add_to_book(td, MORE)
            why = "it was accepted"
        except ValueError as e:
            why = str(e)
        check("no book here" in why, "and a directory with no book.json in it "
              "is not a book to add to", why[:90])

    # --- AND IT TAKES THE SAME CHOICE OF CUT the from-scratch draft takes
    import chunker
    if chunker.lookup.available("fa"):
        with tempfile.TemporaryDirectory() as td:
            b = os.path.join(td, os.path.basename(src))
            shutil.copytree(src, b)
            r = draft.add_to_book(b, MORE, how="phrase", chapter="new")
            check(r["chunks"] == 5 and r["how"] == "phrase",
                  "appended text is cut the way the caller asked, not always "
                  "one chunk per sentence", json.dumps({"chunks": r["chunks"]}))
    else:
        skip("no dict/fa.db: appending is not exercised with sense groups")


def _draft_ways():
    """A book and a video drafted both ways: the choice has to reach the file
    that is written, not merely the function that writes it."""
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    sys.path.insert(0, os.path.join(ROOT, "youtube", "lib"))
    import draft as _d
    import ytpages as _y
    TXT = "مرد پیر در تاریکی نشسته بود. او در تهران زندگی می‌کند."
    SRT = ("1\n00:00:06,000 --> 00:00:09,000\nمرد پیر در تاریکی نشسته بود\n\n"
           "2\n00:00:12,000 --> 00:00:15,000\nاو در تهران زندگی می‌کند\n")
    out = {}
    for way in ("sentence", "phrase"):
        b = _d.book_from_text(TXT, "fa", "t", slug="chunkprobe", how=way)
        lines = [ln for ln in b["files"]["ch1.tex"].split("\n")
                 if ln.startswith("\\ch{")]
        v = _d.video_from_transcript(_y.as_transcript(SRT), "fa",
                                     video_id="chunkprobe-a1b2c3", how=way)
        ann = json.loads(v["files"]["annotations.json"])
        vch = [c["fa"] for sg in ann["segments"] for c in (sg.get("chunks") or [])]
        out[way] = (lines, b["chunks"], vch)
    return out


def test_pronunciation():
    """The transliteration is derived from what the dictionary heard."""
    section("pronunciation")
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    import getdict
    import languages
    import lookup as lk
    import translit

    # --- WHICH REGISTER.  Wiktionary gives Persian five, and its own
    # romanisation field is the CLASSICAL one: that is where kitāb, xwāndan
    # and dōst came from, faithfully copied into every gloss by a model that
    # was handed them.  docs/lang/fa.md writes what Tehran says.
    want, avoid = translit.prefers("fa")
    check("Iran" in want and "Classical-Persian" in avoid,
          "Persian asks for the Iran reading and not the classical one",
          "%s / %s" % (want, avoid))
    o = {"sounds": [{"ipa": "/ki.ˈtaːb/", "tags": ["Classical-Persian"]},
                    {"ipa": "[kʰʲe.t̪ʰɒ́ːb̥]", "tags": ["Iran", "formal"]}]}
    check(getdict._ipa(o, "fa") == "[kʰʲe.t̪ʰɒ́ːb̥]",
          "and the build takes the one it asked for, out of the several a "
          "word has", getdict._ipa(o, "fa"))
    o2 = {"sounds": [{"ipa": "/ki.ˈtaːb/", "tags": ["Classical-Persian"]}]}
    check(getdict._ipa(o2, "fa") == "",
          "and takes none at all rather than the one it is avoiding")

    # --- THE WALK ITSELF.  A transliteration is a mechanical fact about a
    # pronunciation; these are the words the report was about, and the ones
    # that show each rule of the map.
    SAID = [("[kʰʲe.t̪ʰɒ́ːb̥]", "ketāb", "short i is e, and the aspiration is not a sound"),
            ("[xɒːn̪.d̪æn]", "xāndan", "the و of خوا is silent -- not xwāndan"),
            ("[xɒːb̥]", "xāb", "nor xwāb"),
            ("[xoʃ]", "xoš", "خو before a consonant is xo"),
            ("[d̪iː.ɹúːz]", "diruz", "long vowels are plain i and u"),
            ("[d̪uːst̪ʰ]", "dust", "not dōst"),
            ("[ʃiːɹ]", "šir", "not šēr"),
            ("[ɡ̥of.t̪ʰǽn]", "goftan", "short u is o"),
            ("[now.ɹuːz]", "nowruz", "و is w in the diphthong ow"),
            ("[vær.ˈzeʃ]", "varzeš", "and v as a consonant"),
            ("[ʔɒːb̥]", "āb", "a word-initial glottal stop is not written"),
            ("[bæʔd̪̥]", "ba'd", "while one in the middle is")]
    bad = [(i, translit.from_ipa("fa", i), w) for i, w, _why in SAID
           if translit.from_ipa("fa", i) != w]
    check(not bad, "a Persian pronunciation is written the way this edition "
          "writes one: %d words, each a rule of the map" % len(SAID),
          "; ".join("%s -> %s want %s" % b for b in bad[:3]))
    check(translit.from_ipa("ja", "[jama]") == "",
          "and a language that has not said how it writes a pronunciation "
          "gets nothing from this, rather than a guess")

    # --- NOTHING OF THE IPA SURVIVES INTO THE ROMANISATION.  Wiktionary's
    # Iranian transcription is narrow, and every allophone it writes that the
    # house scheme has no letter for used to be passed through untouched: the
    # reader was shown `zaɲg` for زنگ, `teɦrān` for تهران, `šaɦr` for شهر and
    # `čerāɢ` for چراغ -- 2297 of 13718 entries, better than one in six, each
    # one an IPA symbol sitting in a field labelled a transliteration.
    LEAKED = [("[zæɲɡʲ̥]", "zang", "the nasal before a velar is n"),
              ("[t̪ʰeɦ.ɹɒ́ːn]", "tehrān", "the voiced h of ه is h"),
              ("[t̪ʰem.sɒːʱ]", "temsāh", "and so is its final release"),
              ("[ʃæɦɹ]", "šahr", "in the middle of a word too"),
              ("[t͡ʃʰe.ɹɒːɢ̥]", "čerāq", "ق and غ have merged, and both are q"),
              ("[ɹæŋɡʲ̥]", "rang", "the velar nasal is n as well"),
              ("[mo.séɹ(ː)]", "moser", "and length is not written at all")]
    bad = [(i, translit.from_ipa("fa", i), w) for i, w, _why in LEAKED
           if translit.from_ipa("fa", i) != w]
    check(not bad, "an allophone the scheme has no letter for is mapped to "
          "the letter it belongs to, not passed through as IPA",
          "; ".join("%s -> %s want %s" % b for b in bad[:3]))

    # --- A READING IS NOT A ROMANISATION.  The same fault as Persian's, in
    # the other field: a model shown only `nihongo` and asked for the KANA of
    # a chunk answered `nihongo o benkyō suru tei`, because that is what it
    # had been handed.  Wiktionary keeps the kana in the head template.
    ja = languages.get("ja")
    check(ja.reading and ja.is_reading("にほんご") and ja.is_reading("ニホンゴ"),
          "the registry knows what a Japanese reading is written in")
    check(not ja.is_reading("日本語") and not ja.is_reading("nihongo")
          and not ja.is_reading("さんたく shite imasu"),
          "and that the text, the romanisation and a half-and-half answer "
          "are not readings")
    check(not languages.get("fa").is_reading("ketāb"),
          "a language with no reading says no to everything, rather than "
          "guessing at a check it cannot make")
    o = {"head_templates": [{"name": "ja-noun", "args": {"1": "にほんご"}}]}
    check(getdict._reading(o, ja) == "にほんご",
          "the build takes the reading out of the head template")
    check(getdict._reading({"head_templates": [{"args": {"1": "2"}}]}, ja) == "",
          "and takes nothing where the argument is not a reading")
    check(getdict._reading(o, languages.get("fa")) == "",
          "and nothing at all for a language that has no reading")
    if lk.available("ja") and lk._has_col(lk._conn("ja"), "reading"):
        h = lk._hits_for(lk._conn("ja"), "日本語")
        check(h and h[0].get("reading") == "にほんご",
              "and the dictionary answers with it, so the model is shown "
              "にほんご beside nihongo rather than nihongo alone",
              repr(h[0].get("reading") if h else None))
    else:
        skip("dict/ja.db was built before readings: not exercised")

    # --- AND THE DICTIONARY ANSWERS IN IT.  Only where the dictionary has
    # been built with pronunciations in it; one built before that still
    # answers everything else and says the romanisation it always said.
    if lk.available("fa"):
        c = lk._conn("fa")
        if lk._has_ipa(c):
            got = {}
            for w in ("کتاب", "خواندن", "دیروز", "دوست", "گفتن"):
                hits = lk._hits_for(c, w)
                got[w] = hits[0]["translit"] if hits else ""
            check(got.get("کتاب") == "ketāb" and got.get("خواندن") == "xāndan",
                  "the panel a reader sees says ketāb and xāndan, not kitāb "
                  "and xwāndan", json.dumps(got, ensure_ascii=False))
            check(all("w" not in v.replace("ow", "") for v in got.values()),
                  "and no silent letter is spoken anywhere in it",
                  json.dumps(got, ensure_ascii=False))
        else:
            skip("dict/fa.db was built before pronunciations: not exercised")
    else:
        skip("no dict/fa.db: the derived romanisation is not exercised")


# ------------------------------------------------- the corpus and the model
def test_corpus():
    """The two things a dictionary cannot do: choose a sense, and read a line.

    A dictionary lists every sense a word can carry.  Two things were added
    beside it, and neither guesses: a corpus of sentences PEOPLE translated,
    matched on the rare words of the chunk, and a translation model that runs
    in the reader's own page.  Both are optional, both are downloaded, and a
    language with neither reads exactly as it did.
    """
    section("corpus")
    sys.path.insert(0, LIB)
    import corpus
    import getcorpus                                          # noqa: F401
    import getmt
    import languages
    import lookup

    # --- SENSE RANKING.  The source records which senses are obsolete or
    # figurative and the toolbox used to throw that away, so `کشیدن` came back
    # "to suffer" and the reading the page wanted was never printed.
    got = lookup.rank_senses(["to suffer", "to pull, to draw", "to smoke"],
                             ["obsolete", "", "figuratively"])
    check([g[0] for g in got] == ["to pull, to draw", "to smoke", "to suffer"],
          "a plain sense comes before a figurative one and both before an "
          "obsolete one", repr([g[0] for g in got]))
    check([g[2] for g in got] == [0, 1, 2],
          "and each says which tier it is in, so the panel can show why")
    same = lookup.rank_senses(["one", "two", "three"], ["", "", ""])
    check([g[0] for g in same] == ["one", "two", "three"],
          "an untagged entry keeps the order the source gave it -- the sort "
          "is stable and does nothing where there is nothing to say")
    old = lookup.rank_senses(["a", "b"], [])
    check([g[0] for g in old] == ["a", "b"],
          "and a dictionary built before the tags existed passes empty tags "
          "and is unharmed")

    # LITERARY IS NOT DEMOTED, deliberately: this toolbox is pointed at
    # literature, and یار is tagged `literary` for exactly the sense a page of
    # Hafez wants.
    lit = lookup.rank_senses(["a player in a team", "friend, lover"],
                             ["", "literary"])
    check(lit[0][0] == "a player in a team" and lit[1][2] == 0,
          "`literary` and `poetic` are left alone: in the books this toolbox "
          "reads they are the sense that is meant")
    for tag in ("Iran", "Dari", "transitive", "colloquial"):
        check(lookup._sense_rank(tag) == 0,
              "and %r is not a demotion either -- it says where or how a word "
              "is used, not that it is the wrong reading" % tag)

    # --- EVERY LANGUAGE KNOWS WHAT AN OUTSIDE SOURCE CALLS IT.  Parseh keys
    # by ISO 639-1 and Tatoeba keys its exports by 639-3, and the third letter
    # is not derivable: Persian is `pes` (Western Persian), where the
    # macrolanguage `fas` has no export at all.  A language fact, so it is in
    # the registry; without it that language can have no corpus.
    missing = [c for c, L in languages.LANGS.items() if not L.iso3]
    check(not missing, "every language in the registry carries its iso3",
          repr(missing))
    check(languages.get("fa").iso3 == "pes",
          "and Persian is `pes` and not `fas`: only the first has an export",
          languages.get("fa").iso3)
    import newlang
    check("iso3" in io.open(os.path.join(LIB, "newlang.py"),
                            encoding="utf-8").read(),
          "and the tool that adds a language asks for one, so a new row is "
          "not silently born without it")

    # ONLY TO AND FROM ENGLISH.  Mozilla trains its pairs against English
    # rather than against each other, so offering a Persian-to-Italian model
    # would be offering a download that is not there.
    check(getmt.trainable("fa", "en") and getmt.trainable("en", "it"),
          "a pair with English on one side can have a model")
    check(not getmt.trainable("fa", "it"),
          "and a pair without it cannot -- Mozilla trains against English, "
          "not between other languages")
    # AND NOT ALWAYS UNDER THE CODE THE REGISTRY USES.  Mozilla names Chinese
    # by its script, so the pair to fetch for Parseh's `zh` -- which teaches
    # the simplified characters -- is zh-Hans.  A fact about the service's
    # spelling and not about the language, which is why getmt keeps the map
    # and the registry does not.
    check(getmt.service_code("zh") == "zh-Hans"
          and getmt.service_code("es") == "es"
          and getmt.service_code("fa") == "fa",
          "and a language the service spells otherwise is asked for under the "
          "service's own name, every other one under its own",
          getmt.service_code("zh"))

    # --- A CORPUS, built the way the tests build a dictionary: small, here,
    # and never downloaded.
    tmp = tempfile.mkdtemp(prefix="corpus-")
    was_dir, was_dict = corpus.CORPUS_DIR, lookup.DICT_DIR
    try:
        corpus.CORPUS_DIR = tmp
        corpus._CONNS.map, corpus._STAMPS = {}, {}
        c = corpus.create(corpus.path_for("it", "en"))
        # BIG ENOUGH FOR RARITY TO MEAN SOMETHING.  `il` is in most of these
        # and `gatto` in two, which is the whole distinction the weighting
        # rests on; five sentences cannot show it, because in five sentences
        # nothing is rare.
        rows = [("Il gatto dorme sul divano.", "The cat sleeps on the sofa."),
                ("Ho comprato un gatto.", "I bought a cat."),
                ("Il cane dorme.", "The dog sleeps.")]
        filler = [("Il libro e sul tavolo.", "The book is on the table."),
                  ("Il tavolo e grande.", "The table is big."),
                  ("Il libro e nuovo.", "The book is new."),
                  ("Il treno e in ritardo.", "The train is late."),
                  ("Il caffe e caldo.", "The coffee is hot."),
                  ("Il tempo e bello.", "The weather is fine."),
                  ("Il bambino dorme.", "The child sleeps."),
                  ("Il mare e calmo.", "The sea is calm."),
                  ("Il pane e fresco.", "The bread is fresh."),
                  ("Il lavoro e finito.", "The work is finished."),
                  ("Il film e lungo.", "The film is long."),
                  ("Il negozio e chiuso.", "The shop is closed."),
                  ("Il giardino e verde.", "The garden is green."),
                  ("Il telefono e rotto.", "The telephone is broken."),
                  ("Il vino e rosso.", "The wine is red."),
                  ("Il cielo e grigio.", "The sky is grey."),
                  ("Il letto e comodo.", "The bed is comfortable."),
                  ("Il viaggio e lungo.", "The journey is long."),
                  ("Il quadro e bello.", "The picture is beautiful."),
                  ("Il fiume e profondo.", "The river is deep."),
                  ("Il museo e aperto.", "The museum is open.")]
        rows = rows + filler
        df = {}
        for i, (a, b) in enumerate(rows, 1):
            c.execute("INSERT INTO pair (id, src, dst) VALUES (?,?,?)", (i, a, b))
            for w in corpus.words_of("it", a):
                c.execute("INSERT INTO tok (word, pair_id) VALUES (?,?)", (w, i))
                df[w] = df.get(w, 0) + 1
        c.executemany("INSERT INTO df (word, n) VALUES (?,?)", sorted(df.items()))
        for k, v in (("source", "a fixture"), ("licence", "none"),
                     ("pairs", str(len(rows)))):
            c.execute("INSERT INTO meta (key, value) VALUES (?,?)", (k, v))
        c.commit()
        c.close()
        corpus._CONNS.map, corpus._STAMPS = {}, {}

        check(corpus.available("it", "en"), "a corpus that is there is available")
        check(not corpus.available("fr", "en"),
              "and one that is not is not -- a pair with no corpus is silence, "
              "not an error")
        r = corpus.look_up("it", "en", "il gatto")
        check(r["available"] and len(r["pairs"]) >= 1,
              "a chunk sharing a rare word finds the sentence holding it",
              json.dumps(r["pairs"], ensure_ascii=False)[:120])
        check(all("gatto" in p["matched"] for p in r["pairs"]),
              "and says which word it matched on, so the reader can see why")
        check(all("The cat" in p["dst"] or "a cat" in p["dst"] for p in r["pairs"]),
              "and carries the translation a person wrote")
        first = corpus.look_up("it", "en", "il gatto", limit=1)
        second = corpus.look_up("it", "en", "il gatto", limit=5, offset=1)
        check(len(first["pairs"]) == 1 and first["more"]
              and len(second["pairs"]) == 1 and not second["more"]
              and first["pairs"][0]["src"] != second["pairs"][0]["src"],
              "corpus results page without repeats and say when more remain")

        # THE RARE WORD IS THE WHOLE POINT.  Matching on `il` would offer every
        # sentence in the corpus and mean nothing, so a match made only of
        # common words scores below the floor and is not shown.
        common = corpus.look_up("it", "en", "il")
        check(not common["pairs"],
              "a chunk of nothing but common words matches nothing: the score "
              "is weighted by how FEW sentences hold a word",
              json.dumps(common["pairs"], ensure_ascii=False)[:120])
        # AND MANY COMMON WORDS MUST NOT ADD UP TO ONE RARE ONE.  Gating on
        # the sum let `این و آن` -- three of the commonest words in Persian --
        # score 8.47 between them and offer a sentence about nothing to do
        # with the chunk.  The gate is on the rarest word in common.
        pile = corpus.look_up("it", "en", "il e")
        check(not pile["pairs"],
              "and a handful of common words does not add up to a rare one: "
              "the gate is on the rarest word, not on the total",
              json.dumps(pile["pairs"], ensure_ascii=False)[:120])
        two = corpus.look_up("it", "en", "il gatto dorme")
        one = corpus.look_up("it", "en", "il gatto")
        check(two["pairs"] and one["pairs"]
              and two["pairs"][0]["score"] > one["pairs"][0]["score"],
              "and two rare words score above one")
        check(corpus.df("it", "en", "gatto") == 2
              and corpus.df("it", "en", "nonesuch") == 0,
              "the count of sentences holding a word is readable on its own -- "
              "it is what the dictionary borrows to rank two lemmas")

        # --- THE TWO HALVES MUST FOLD A WORD THE SAME WAY, or a corpus
        # indexed on one string and a dictionary looking for another share
        # nothing at all.
        for code, text in (("it", "Il Gatto"), ("fa", "کتاب‌ها")):
            L = languages.get_or_default(code)
            words = corpus.words_of(code, text)
            if not words:
                continue
            check(all(w == lookup._fold(lookup._bare(w, L), L) for w in words),
                  "%s: the corpus folds a word exactly as the dictionary does"
                  % code, repr(words))
    finally:
        corpus.CORPUS_DIR, lookup.DICT_DIR = was_dir, was_dict
        corpus._CONNS.map, corpus._STAMPS = {}, {}
        shutil.rmtree(tmp, ignore_errors=True)

    reader = io.open(os.path.join(LIB, "tex2html.py"), encoding="utf-8").read()
    player = io.open(os.path.join(YT_LIB, "player.js"), encoding="utf-8").read()

    # --- THE THREE ARE INDEPENDENT, and the readers must not gate one on
    # another.  The dictionary and the corpus are separate downloads and the
    # model is a third; gating the panel on the dictionary alone left a reader
    # who had downloaded a corpus with no way to reach it.
    srv = io.open(os.path.join(ROOT, "serve.py"), encoding="utf-8").read()
    for key in ('"corpus_available"', '"help"'):
        check(key in srv,
              "the lookup route reports %s beside the dictionary's own "
              "availability" % key)
    check('if has_corpus:' in srv and 'if have' in srv,
          "and asks each of them separately, so a corpus answers where there "
          "is no dictionary")
    # an unglossed phrase of the target's text is live whatever is installed
    # (the owner's decision of 2026-09-23): the player no longer waits on a
    # dictionary, a corpus or a model to draw it as a phrase, so the page is
    # not told whether any of them exists before the transcript is drawn
    check("CFG.help" not in player and "YTFRANK.help" not in player,
          "the player draws an unglossed phrase live whatever is installed -- "
          "no flag from the server decides it")
    for name, src in (("the book reader", reader), ("the player", player)):
        check("DICT.ready || MT.ready" in src,
              "%s opens the panel for a model as well as a dictionary" % name)
        check("DICT.words" in src and "DICT.pairs" in src,
              "%s knows which of the two the server actually has, so it draws "
              "no empty heading" % name)
        check("corpus_limit: 5" in src and "corpus_offset:" in src
              and "pairs_more" in src and "Load more" in src,
              "%s starts with three corpus examples and can append five more "
              "until none remain" % name)

    # --- THE MODEL IS A DOWNLOAD AND NOT A DEPENDENCY.  Nothing is asserted
    # about a model being installed: the point is that the toolbox works
    # without one and says so.
    check(getmt.MT_DIR.endswith("mt"), "the models live in mt/")
    check(not getmt.available("fa", "it"),
          "a pair Mozilla never trained has no model here either, and the "
          "toolbox does not pretend it does -- the button is simply not "
          "offered")
    check(getmt.ENGINE_VERSION and "." in getmt.ENGINE_VERSION,
          "the engine version is PINNED: a dependency fetched over the network "
          "that moves on its own is one that changes under a reader",
          getmt.ENGINE_VERSION)
    check(getmt._stable("1.0") and not getmt._stable("1.0a1"),
          "and an alpha is never picked over the release it is the alpha of")

    # the glue both readers share, rather than two copies of the dirty part
    mt = io.open(os.path.join(LIB, "mt.js"), encoding="utf-8").read()
    check("initialize" in mt,
          "the engine is asked to start before it is asked to translate: "
          "without that every later call finds an undefined module")
    check("/mt/" in mt and "translator-worker.js" in mt,
          "and the worker is made from the directory its wasm sits in, which "
          "is how its own importScripts finds it")
    for name, src in (("the book reader", reader), ("the player", player)):
        check("ParsehMT" in src, "%s reaches the shared engine glue" % name)
        check("mtInto" in src and "not a gloss" in src,
              "%s draws what it answers as a machine's reading and not as a "
              "gloss" % name)
        # A CHUNK IS A FRAGMENT BY CONSTRUCTION, so the sentence is what is
        # translated: `مثل ایران با هم` alone came back "The parable of Iran
        # with Hem" where the sentence holding it came back as sense.
        check("preSentences" in src,
              "%s translates the sentences ahead, not the chunk in front of "
              "it" % name)
        check("ParsehMT.align" in src,
              "%s marks which words of that sentence are this chunk's" % name)
        # BY MEANING, NEVER BY PLACE.  The mark used to prefer the part of
        # the translation sitting where the chunk sits in its sentence, and to
        # fall back on that place -- and word order is what a translation
        # changes (a Persian verb comes last, an English one second).  Each
        # reader now hands the aligner the lookup it has just drawn, and
        # neither works out where the chunk sits any more.
        check(src.count("ParsehMT.align(") >= 2
              and all("words" in call.split(")")[0]
                      for call in src.split("ParsehMT.align(")[1:]),
              "%s hands the aligner what the dictionary says of the chunk, in "
              "its panel and in its sources column" % name,
              repr([c.split(")")[0][:70] for c in src.split("ParsehMT.align(")[1:]]))
        check("chunkMid" not in src and "ctx.mid" not in src
              and "by where it sits" not in src,
              "%s no longer places the mark by where the chunk sits" % name)
        check("ParsehMT.marked(" in src and "ParsehMT.why(" in src,
              "%s draws the mark in every place the chunk landed, and says "
              "which of its words the dictionary found there" % name)
        check("mtgo" not in src,
              "%s asks for no button: the reading is there when the panel is"
              % name)
        # the order the reader meets them in: what the words mean, then what
        # the line means, then what somebody else wrote
        mt_at, pair_at = src.find("mtInto(box"), src.find("pairsHTML(j)")
        if pair_at < 0:
            pair_at = src.find("pairsInto(box")
        check(0 < mt_at < pair_at,
              "%s draws the dictionary, then the model, then the sentences "
              "somebody translated" % name, "%d vs %d" % (mt_at, pair_at))
    # --- THE SOURCES SIDEBAR, where the gloss is actually written. Reading
    # the evidence in the reader's panel and retyping it into the editor was
    # the whole of the work, and retyping is where a romanisation loses a
    # macron.  Closed by default, because somebody who knows the language
    # wants the box and not the crowd around it.
    for name, src, opener in (("the book reader", reader, "chsrc"),
                              ("the player", player, "esrc")):
        check(opener in src,
              "%s's gloss editor has a door to the sources" % name)
        check("srcFill" in src or "sideFill" in src,
              "%s fills it from the dictionary, model, corpus and chatbot handoff"
              % name)
        check("localStorage" in src and ("SRC_KEY" in src or "SIDE_KEY" in src),
              "%s remembers whether it was left open" % name)
        check("hidden" in src and ("sideOn" in src or "srcOpen" in src),
              "%s keeps it closed until it is asked for" % name)
        check("Ask LLM" in src and "Use translation" in src
              and "ParsehLLM.collectPairs" in src and "corpus_limit: 50" in src,
              "%s can copy an external-chatbot prompt with every Tatoeba page, "
              "then accept the pasted translation" % name)
        check("LLM.sent" in src and ("ctx.sentence || text" in src
                                      or "at.sg && at.sg.text" in src),
              "%s caches a pasted translation under the complete sentence"
              % name)
    # it writes into the FORM and never into the book: everything it offers
    # lands in an unsaved field for somebody to correct
    for name, src, fields in (("the book reader", reader, ["CH.tr", "CH.voc", "CH.en"]),
                              ("the player", player, ["'tr'", "'voc'", "'en'"])):
        for f in fields:
            check(f in src,
                  "%s can put a source into %s" % (name, f.strip("'")))
    check("__edit/chunk" in reader and "/youtube/api/edit" in player,
          "and the only way any of it reaches a book or a video is the "
          "ordinary edit route, with the ordinary checkers on it")
    llm = io.open(os.path.join(LIB, "llm.js"), encoding="utf-8").read()
    check("Return ONLY the translation" in llm and "SENTENCES BEFORE:" in llm
          and "SENTENCES AFTER:" in llm and "DICTIONARY RESULTS" in llm
          and "RELEVANT TATOEBA" in llm,
          "the shared chatbot prompt asks only for a translation and carries "
          "context, visible dictionary rows and Tatoeba examples")
    check("opts.bergamot" not in llm and "opts.machine" not in llm,
          "the chatbot prompt has no input through which Bergamot output can enter")

    # --- THE SOURCES OPEN TO THE LEFT AND THE WINDOW GROWS.  They used to
    # be a block ABOVE the fields in the same sheet, so every entry pushed
    # the box it was meant to fill below the fold.  Now they are a column
    # beside the fields, first in the row, and opening them widens the
    # sheet instead of covering it; on a narrow screen they stack under the
    # fields.  (tests/mtcheck.py --panels measures the rectangles; this is
    # that the shape is there to measure.)
    style = io.open(os.path.join(YT_LIB, "style.css"), encoding="utf-8").read()
    import tex2html
    sheet = reader[reader.find('<form id="chbox"'):]
    check('<div class="chcols">' in sheet
          and 0 < sheet.find('<aside id="chside"') < sheet.find('<div class="chmain">'),
          "the book's chunk sheet is two columns, the sources before the fields")
    check("#chbox .chcols{" in tex2html.CSS and "#chbox.side " in tex2html.CSS
          and "CH.box.classList.toggle('side'" in tex2html.JS,
          "and opening the sources gives the sheet its wider `side` shape")
    check(re.search(r"@media\s*\(max-width:\s*\d+px\)\s*\{[^@]*#chbox \.chcols\{flex-direction:column",
                    tex2html.CSS),
          "which stacks, fields first, on a narrow screen")
    check('<div class="ebody">' in player
          and 0 < player.find('<div class="eside"') < player.find('<div class="emain">'),
          "the player's edit window is two columns, the sources before the fields")
    check("classList.toggle('sideon'" in player and "#cloud.editing.sideon{" in style
          and "#cloud .ebody{flex-direction:column}" in style,
          "and grows to hold them (`sideon`), stacking on a narrow screen")

    # --- CLEARLY VISIBLE LINES BETWEEN THE THREE.  The dictionary, the
    # machine's reading and the sentences somebody translated were told
    # apart by a 1px dotted rule of 1.08:1 contrast -- the same stroke that
    # sat over each block's own source line.  Each block is its own box now,
    # the dictionary included (.ddict), with a solid rule between two.
    for name, src, css in (("the book reader", reader, tex2html.CSS),
                           ("the player", player, style)):
        check("ddict" in src and ".dict>.ddict" in css,
              "%s wraps the dictionary's entries in a block of their own" % name)
        check(re.search(r"\.dict>\*\+\.dmt,#cloud \.dict>\*\+\.dpairs\{[^}]*"
                        r"border-top:2px solid", css),
              "%s rules the machine's reading and the sentences off with a "
              "solid line" % name)
        check("dvb" in src, "%s shows a verb's principal parts under it in the "
                            "panel (.dvb)" % name)

    # --- A VERB GOES IN AS A VERB.  The book's button puts the whole \vb the
    # server built; a video's vocabulary is plain text, and its button puts
    # the entry hung on the chunk's word.  Anything else is a \dw of the
    # LEMMA with the lemma's own sound -- head_sound, never the reached
    # form's translit -- in the spelling the text uses (spelled).
    check("put(CH.voc, vb.tex" in reader,
          "the book's sidebar puts a verb hit's \\vb into the vocabulary")
    # (vbEntry is the entry hung on the chunk's word -- vb.here -- or, where the video's vocabulary line is a
    # book's macros, the same entry as the book's \vb: a0.4.2)
    check("srcPut('voc', vbEntry(vb), VOC_JOIN)" in player and "function vbEntry(vb)" in player and "vb.here" in player,
          "the player's puts the verb's entry, hung on the chunk's word")
    # ...AND A VERB THAT IS MORE THAN ONE WORD HAS A BUTTON OF ITS OWN.  فکر
    # کردن is one verb: the light verb's \vb and the \bw for the word it
    # carries are ONE entry, run together with nothing between them, and the
    # video's line says the compound whole.  That is not the plain button's
    # line with something added, so it is not the plain button (lib/verbs
    # Parts.compound).
    check("(vb.compound && vb.compound.bw) ? vb.compound : null" in reader
          and "put(CH.voc, tex, '; ')" in reader
          and "(mine || vb.tex) + cp.bw" in reader,
          "a compound has its own button in the book, and it puts the \\vb and "
          "the \\bw as one entry")
    check("(vb.compound && vb.compound.plain) ? vb.compound : null" in player
          and "srcPut('voc', cpEntry(cp), VOC_JOIN)" in player and "cp.plain" in player,
          "and one in the player, which puts the compound's own plain line")
    for name, src in (("the book", reader), ("the player", player)):
        check("is ONE verb written in two words" in src
              or "is one verb written in two words" in src,
              "%s's compound button says what the pair is, in words" % name)
    m = re.search(r"function sideHit\(.*?\n\}\n", tex2html.JS, re.S)
    body = m.group(0) if m else ""
    check("h.head_sound" in body and "h.spelled || h.headword" in body
          and "'\\\\dw{' + head + '}{' + said + '}" in body,
          "the book's \\dw is the headword as the text spells it with the "
          "lemma's own sound", body[:120])
    m = re.search(r"function headSound\(h\) \{.*?\n  \}", player, re.S)
    check(m and "h.head_sound" in m.group(0) and "h.spelled" in player,
          "and the player's too")

    # A LOOKUP THAT COMES BACK LATE IS FOR A CHUNK NOBODY IS EDITING NOW:
    # without a generation number it appended its entries to the next
    # chunk's sources.
    check("const gen = ++sideGen, live = () => gen === sideGen;" in tex2html.JS
          and "if (!live()) return;" in tex2html.JS,
          "the book's sidebar drops an answer meant for a sheet since refilled")
    check("var gen = ++srcGen;" in player and "if (gen !== srcGen) return;" in player,
          "and so does the player's")

    # --- A NOTE'S PREVIEW, ON HOVER, BEFORE THE CLICK.  One card, made by
    # the script (a reader built before it has none in its page), and
    # filled with textContent ONLY: a note is a file that travels in a
    # bundle from somebody else's toolbox, and a pointer passing over its
    # mark must never do more than show letters.
    for name, src, var, fill in (
            ("the book reader", tex2html.JS, "PEEK", ("function peekFill", "function peekPlace")),
            ("the player", player, "peekEl", ("function peekLine", "function noteMark"))):
        check(re.search(r"\b%s = document\.createElement\('div'\)" % var, src)
              and "%s.id = 'ntpeek'" % var in src,
              "%s makes its note preview in the script" % name)
        i = src.find(fill[0])
        body = src[i:src.find(fill[1], i)] if i >= 0 else ""
        check(body and "innerHTML" not in body and "textContent = text" in body
              and "%s.textContent = ''" % var in body and "n.excerpt" in body
              and re.search(r"\b%s\.innerHTML\b" % var, src) is None,
              "%s fills it with the note's excerpt as text, never as HTML" % name,
              body[:200])
        check("HOVER_OK" in src and ("peekWire(b, n, why)" in src or "if (HOVER_OK)" in src),
              "%s shows it only where there is a hover" % name)

    mtjs = io.open(os.path.join(LIB, "mt.js"), encoding="utf-8").read()
    check("Array.isArray" in mtjs,
          "the engine is handed many texts at once -- ten sentences cost "
          "about what one costs, which is what makes the panel open filled")
    check("function align(target, probe, words_" in mtjs and "meaningsOf" in mtjs,
          "and the guess at which words are the chunk's is one implementation, "
          "shared by both readers rather than written twice, made from what "
          "the dictionary says the chunk's words mean")
    check("midRatio" not in mtjs and "centre - mid" not in mtjs,
          "and nothing in it reads where the chunk sits in its sentence")
    check("mt.js" in reader and "mt.js" in
          io.open(os.path.join(YT_LIB, "player.html"), encoding="utf-8").read(),
          "and both load it")
    check('mimetypes.add_type("application/wasm", ".wasm")' in
          io.open(os.path.join(ROOT, "serve.py"), encoding="utf-8").read(),
          "the server names the wasm type, which "
          "WebAssembly.instantiateStreaming refuses to work without")


def serve_hub():
    """The hub page's HTML, without a server: serve.py builds it from the
    shelves, and what matters here is only what it links to.  It lives at
    the repository root rather than in lib/, so the path goes on first."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import serve
    return serve.hub_page()


def test_lookup():
    """The dictionary behind a chunk nobody has glossed.

    Everything here is about one distinction: a dictionary is not a gloss.
    It lists what a word can mean and cannot say which is meant, so what it
    answers is marked, carries the route by which the word was found, names
    its source, and is never written anywhere.  The checks below are for the
    parts of that which a machine can hold to.
    """
    section("lookup")
    import languages
    import lookup as lk
    import translit

    # --- Devanagari to the Roman a dictionary may be keyed by.  This is the
    # walk behind `fold: "deva-iast"`, which lib/lookup.py's rules() reads out
    # of lib/lang/<code>.lookup.json: a language whose pages are Devanagari
    # and whose dictionary is romanised says so there, and the word is
    # transliterated before it is looked for.  No language in the registry
    # declares it just now, and the capability is the toolbox's rather than
    # any one language's -- so the walk is checked here on its own, and the
    # mechanism it feeds is checked below on rules set by hand.
    for deva, want in (("एवं मे सुतं", "evaṃ me sutaṃ"),
                       ("अनाथपिण्डिकस्स", "anāthapiṇḍikassa"),
                       ("कीळति", "kīḷati"),          # ḷa, which no Hindi text uses
                       ("सम्मन्तीध", "sammantīdha"),
                       ("बुद्धं सरणं गच्छामि", "buddhaṃ saraṇaṃ gacchāmi"),
                       ("सोऽहं", "so'haṃ"),           # the avagraha
                       ("१२३", "123")):
        got = translit.deva_to_iast(deva)
        check(got == want, "%s -> %s" % (deva, want), got)
    check(translit.deva_to_iast("hello ब") == "hello ba",
          "and anything not Devanagari comes through untouched")

    # --- A DICTIONARY IN THE SCRIPT ITS PAGES ARE PRINTED IN, which is the
    # ordinary case and Hindi's.
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "hi.db")
        _fixture_dict(db, "hi", [
            ("किताब", "kitāb", "noun", ["book"], [("किताबें", "plural")]),
            ("घर", "ghar", "noun", ["house, home"], []),
            ("सुनना", "sunnā", "verb", ["hears", "listens"],
             [("सुना", "perfective"), ("सुनता", "imperfective")]),
        ])
        was = lk.DICT_DIR
        lk.DICT_DIR = td
        lk._CONNS.map = {}
        try:
            check(lk.available("hi"), "a dictionary that is there is found")
            check(not lk.available("fa"), "and one that is not, is not")

            # A DICTIONARY BUILT WHILE THE SERVER IS RUNNING IS FOUND BY THE
            # THREAD THAT ALREADY LOOKED.  The connection cache was keyed by
            # language alone, so whatever a thread found the first time it
            # asked -- including "there is nothing here" -- it went on
            # answering forever.  On a threading server that meant: press
            # `get it` on the setup page, and every thread that had answered
            # a request before the build kept saying there was no dictionary.
            # It showed as the page offering `get it` for a dictionary
            # plainly in dict/, and as the reader drawing the panel's header
            # with nothing under it -- because `available` asked the
            # filesystem and `look_up` asked the cache, and the two
            # disagreed.
            check(lk.about("fa") is None and lk.look_up("fa", "کتاب") is None,
                  "before it exists, nothing is found -- and that is cached")
            shutil.copy(db, os.path.join(td, "fa.db"))
            check(lk.available("fa") and lk.about("fa"),
                  "the moment the file appears the SAME thread sees it",
                  repr(lk.about("fa")))
            check((lk.look_up("fa", "किताब") or {}).get("words") is not None,
                  "and looks up in it, rather than drawing an empty panel")
            os.unlink(os.path.join(td, "fa.db"))
            check(not lk.available("fa") and lk.about("fa") is None,
                  "and when it is thrown away, the same thread stops "
                  "claiming to have it")
            check(lk.look_up("fa", "کتاب") is None,
                  "a language with no dictionary answers None, not an empty "
                  "list: 'nothing to find with' is not 'nothing found'")
            m = lk.about("hi") or {}
            check(m.get("licence") == "none" and m.get("source") == "a fixture",
                  "the source and its licence travel in the file", repr(m))

            r = lk.look_up("hi", "किताबें")
            w = r["words"][0]
            check(w["hits"] and w["hits"][0]["headword"] == "किताब",
                  "an inflected form reaches its dictionary form",
                  json.dumps(w, ensure_ascii=False)[:200])
            check(w["hits"][0]["note"] == "plural",
                  "with what the ending was doing", w["hits"][0]["note"])

            # THE DANDA.  It is punctuation and it lives INSIDE the Devanagari
            # block, so "is it in the script" cannot answer this -- which is
            # why _keeps() asks Unicode's own categories instead.  Before it
            # did, every sentence-final word in every Devanagari text missed.
            r = lk.look_up("hi", "सुना।")
            check(r["words"][0]["hits"], "a word with the danda stuck to it is "
                  "still found", json.dumps(r["words"][0], ensure_ascii=False)[:160])

            r = lk.look_up("hi", "सुनना")
            check(r["words"][0]["hits"][0]["senses"] == ["hears", "listens"],
                  "the senses come back, capped")

            r = lk.look_up("hi", "ऽऽऽ")
            check(r["words"] == [] or not r["words"][0]["hits"],
                  "a word that is not there is not found, and says what it tried",
                  json.dumps(r["words"], ensure_ascii=False)[:160])

            # nothing here writes.  The file is opened mode=ro, so a write
            # would raise rather than corrupt -- but the check that matters is
            # that the bytes are the same afterwards.
            before = open(db, "rb").read()
            for t in ("किताबें", "सुना।", "घर", "नहीं"):
                lk.look_up("hi", t)
            check(open(db, "rb").read() == before,
                  "and a lookup leaves the dictionary byte for byte as it was")
        finally:
            lk.DICT_DIR = was
            lk._CONNS.map = {}

    # --- AND A DICTIONARY KEYED IN ANOTHER SCRIPT THAN ITS PAGES.  That is
    # what `fold: "deva-iast"` is for, and the affix rules are what make it
    # more than a second spelling to try: AN AFFIX RULE IS WRITTEN IN THE
    # DICTIONARY'S SCRIPT, NOT THE PAGE'S, so a rule applied to the surface
    # form matches nothing -- `बुद्धं` tries itself and `buddhaṃ` and stops one
    # step short of `buddha`, which is right there.  The transliterated
    # spelling has to be an INPUT to the rules and not merely another thing
    # to try.  No language in the registry declares the fold at present, so
    # the rules are set here by hand: a capability with no user is still a
    # capability, and the day a language declares it, it must already work.
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "hi.db")
        _fixture_dict(db, "hi", [
            # romanised headwords, Devanagari pages -- and `saraṇa` is listed
            # with no forms at all, so only an affix rule can reach it, which
            # is the case the checks below are about
            ("saraṇa", "", "noun", ["refuge, shelter"], []),
            ("dhamma", "", "noun", ["the teaching", "a thing"],
             [("dhammo", "nominative singular")]),
        ])
        was, rules_was = lk.DICT_DIR, dict(lk._RULES)
        lk.DICT_DIR = td
        lk._RULES["hi"] = {"fold": "deva-iast",
                           "affixes": [{"suffix": "ṃ", "add": "",
                                        "note": "-ṃ taken off"}]}
        lk._CONNS.map = {}
        try:
            r = lk.look_up("hi", "धम्मो")
            w = r["words"][0]
            check(w["hits"] and w["hits"][0]["headword"] == "dhamma",
                  "a Devanagari word reaches a romanised lemma",
                  json.dumps(w, ensure_ascii=False)[:200])
            check("transliterated" in w["via"],
                  "and the answer says by which route", w["via"])
            check(w["hits"][0]["note"] == "nominative singular",
                  "with what the ending was doing", w["hits"][0]["note"])

            r = lk.look_up("hi", "सरणं")
            w = r["words"][0]
            check(w["hits"] and w["hits"][0]["headword"] == "saraṇa",
                  "an ending is taken off the transliterated form, not the "
                  "Devanagari one", json.dumps(w, ensure_ascii=False)[:200])
            check("-ṃ taken off" in w["via"] and "transliterated" in w["via"],
                  "and the reader is told both halves of how it got there",
                  w["via"])
        finally:
            lk.DICT_DIR = was
            lk._RULES.clear(); lk._RULES.update(rules_was)
            lk._CONNS.map = {}

    # --- A LANGUAGE WITH NO WORD SEPARATOR.  `split_words` hands back the
    # whole chunk as one word, which is right everywhere else in the toolbox
    # and useless to a dictionary: 本を読んだ is not a headword.  The pieces
    # are found by longest match against the dictionary's own form table --
    # so the word list IS the dictionary, and there is nothing extra to
    # install.
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "ja.db")
        _fixture_dict(db, "ja", [
            ("昨日", "kinō", "noun", ["yesterday"], [("きのう", "another spelling")]),
            ("本", "hon", "noun", ["a book"], [("ほん", "another spelling")]),
            ("を", "o", "particle", ["the direct object"], []),
            ("読む", "yomu", "verb", ["to read"], [("読んだ", "past")]),
            ("住む", "sumu", "verb", ["to live, to dwell"], []),
        ])
        was = lk.DICT_DIR
        lk.DICT_DIR = td
        lk._CONNS.map = {}
        try:
            r = lk.look_up("ja", "昨日本を読んだ")
            got = [w["word"] for w in r["words"]]
            check(got == ["昨日", "本", "を", "読んだ"],
                  "a chunk with no spaces in it is cut into its words", repr(got))
            check(all(w["hits"] for w in r["words"]),
                  "and every one of them is found")
            check(r["words"][3]["hits"][0]["headword"] == "読む",
                  "an inflected form reaches its dictionary form",
                  json.dumps(r["words"][3], ensure_ascii=False)[:160])

            # AND THE CUT ITSELF ASKS THE LANGUAGE'S RULES.  住んで is in no
            # dictionary and is unmistakably a word; without the rules the
            # cut left 住 alone and matched んで, absurdly, against whatever
            # two-kana entry happened to exist.
            r = lk.look_up("ja", "住んでいました。")
            got = [w["word"] for w in r["words"]]
            check("住んで" in got,
                  "a te-form is one piece, because the rules say it is a word",
                  repr(got))
            w = next(w for w in r["words"] if w["word"] == "住んで")
            check(w["hits"] and w["hits"][0]["headword"] == "住む",
                  "and it reaches the verb", json.dumps(w, ensure_ascii=False)[:160])
            check("。" not in "".join(got),
                  "punctuation is passed over, not reported as a word nobody "
                  "could find", repr(got))
        finally:
            lk.DICT_DIR = was
            lk._CONNS.map = {}

    # --- MORE THAN ONE AFFIX COMES OFF.  Persian stacks them: نمی‌بینمش is
    # ne- + mi- + بین + -am + -aš, and taking exactly one affix off could
    # never reach the verb -- the prefix came off, or the enclitic did, never
    # both, and the reader was told nothing was found.
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "xx.db")
        _fixture_dict(db, "fa", [
            ("دیدن", "dīdan", "verb", ["to see"], [("بینم", "aorist first-person")]),
            ("کتاب", "kitāb", "noun", ["book"], []),
            ("می‌بینم", "mi-binam", "verb", ["I see"], []),
        ])
        os.rename(db, os.path.join(td, "fa.db"))
        was, rules_was = lk.DICT_DIR, dict(lk._RULES)
        lk.DICT_DIR = td
        lk._CONNS.map = {}
        try:
            r = lk.look_up("fa", "نمی‌بینمش")
            w = r["words"][0]
            check(w["hits"] and w["hits"][0]["headword"] == "دیدن",
                  "a prefix AND an enclitic both come off, and the verb is "
                  "found", json.dumps(w, ensure_ascii=False)[:200])
            check("," in w["via"],
                  "and the reader is told what came off, in the order it did",
                  w["via"])
            check(w["kind"] == "affix" if "kind" in w else True,
                  "a multi-step peel is still a route the language accounts for")

            # SHALLOWEST FIRST is what keeps this safe: a word that IS in the
            # dictionary is found as itself, never explained away as somebody
            # else's stem.  کتاب must not come back as کتا + ب.
            r = lk.look_up("fa", "کتاب")
            check(r["words"][0]["via"] == "as written",
                  "a word the dictionary has is found as itself",
                  r["words"][0]["via"])

            check(len(lk._routes("نمی‌بینمش", languages.get("fa"))) <= lk.MAX_ROUTES,
                  "and the search is bounded, however the rules are written")
        finally:
            lk.DICT_DIR = was
            lk._RULES.clear(); lk._RULES.update(rules_was)
            lk._CONNS.map = {}

    # a zero-width joiner left at an edge is not part of the word: Persian
    # writes نمی + ZWNJ + بینم, so the prefix coming off leaves the joiner
    # leading the stem, and nothing is keyed under that
    check(lk._trim("\u200cبینم") == "بینم" and lk._trim("بینم\u200d") == "بینم",
          "a joiner left by a peel is trimmed off the edge")

    # --- THE VERB PREFIX WRITTEN APART (`join_next`, lib/lang/fa.lookup.json).
    # A plain space where the joiner belongs is how a typewriter, an old
    # printing and much of the Web write می‌کنم -- 13 of the fixture book's
    # chunks and 210 words of 1,500 Tatoeba sentences.  Split there, می was
    # "wine" and the verb was looked for without its prefix, so `می کنم`
    # offered کندن (to dig) beside کردن.  The two are one word now, shown as
    # the text writes them; but only where together they are a verb -- می is
    # a prefix rule of its own, and `می ناب` (pure wine) came back as ناب --
    # and only with nothing but the space between them.
    with tempfile.TemporaryDirectory() as td, _DictDir(td):
        _tiny_dict(os.path.join(td, "fa.db"), "fa", [
            ("می", "noun"),
            ("کردن", "verb", "", "", [("میکنم", "first-person indicative present singular"),
                                      ("کنم", "aorist first-person indicative singular")]),
            ("کندن", "verb", "", "", [("کنم", "aorist first-person indicative singular")]),
            ("ناب", "adj"),
            ("فکر", "noun")])
        r = lk.look_up("fa", "فکر می کنم")
        got = [w["word"] for w in r["words"]]
        check(got == ["فکر", "می کنم"],
              "a mi- written apart is looked up as one word with the verb after "
              "it, and shown as the text writes the two", repr(got))
        w = r["words"][-1]
        check([h["headword"] for h in w["hits"]] == ["کردن"]
              and w["via"].startswith("as one word"),
              "and it is the verb می‌کنم is -- not wine, and not کندن (to dig), "
              "which کنم alone also is -- found `as one word`",
              json.dumps([w["via"], [h["headword"] for h in w["hits"]]], ensure_ascii=False))
        w = lk.look_up("fa", "نمی کنم")["words"][0]
        check(w["word"] == "نمی کنم" and "کردن" in [h["headword"] for h in w["hits"]]
              and "nemi-" in w["via"],
              "the negative nemi- written apart is joined too, and the reader is "
              "told it came off", json.dumps([w["word"], w["via"]], ensure_ascii=False))
        got = [w["word"] for w in lk.look_up("fa", "می، کنم")["words"]]
        check(got == ["می،", "کنم"],
              "a comma between them keeps them two words", repr(got))
        got = [(w["word"], [h["headword"] for h in w["hits"]])
               for w in lk.look_up("fa", "می ناب")["words"]]
        check(got == [("می", ["می"]), ("ناب", ["ناب"])],
              "two words that together find no verb were never one: می ناب is "
              "wine and pure, not ناب behind a verb prefix", repr(got))
        w = lk.look_up("fa", "نمی سوزانند")["words"][-1]
        check(w["word"] == "سوزانند" and not w["hits"]
              and "نمی‌سوزانند" in w["tried"],
              "a join that finds nothing leaves both words as they were, and the "
              "word after it says the joined spelling was tried too",
              json.dumps(w["tried"], ensure_ascii=False))
    check(lk._join_rule(languages.get_or_default("it")) is None,
          "and a language that declares no join_next joins nothing")
    # THE RECIPE HAS TO FIND THE JOINED WORD TOO.  lib/verbs/fa.py places the
    # hit's word among the chunk's tokens to see the compound before it, and
    # compared one token at a time it never found `می کند`: 60 of 469
    # compounds lost their reading, `گریه می کند` offered کردن with its own
    # meaning instead of the compound's empty one and the \bw left to add.
    if lk.available("fa"):
        import verbs
        r = verbs.attach(lk.look_up("fa", "گریه می کند"), "fa", "گریه می کند", "en")
        vb = next((h.get("vb") for w in r["words"] if w["word"] == "می کند"
                   for h in w["hits"] if h.get("vb")), None) or {}
        check(vb.get("lemma") == "کردن" and vb.get("tex", "").endswith("{}")
              and any("گریه" in m for m in vb.get("missing") or []),
              "and the Persian recipe finds the joined word in its chunk: گریه "
              "می کند is the compound's light verb with an empty meaning and the "
              "\\bw for گریه left to add",
              json.dumps({k: vb.get(k) for k in ("lemma", "tex", "missing")},
                         ensure_ascii=False))
        # ...AND THE WHOLE COMPOUND IS WRITTEN OUT, ready for the button that
        # puts it in as the ONE entry it is: not the light verb and a
        # sentence about the word it carries, and not two entries either
        cp = vb.get("compound") or {}
        check(cp.get("whole") == "گریه کردن"
              and cp.get("tex") == vb.get("tex", "") + "\\bw{گریه}{gerye}{to cry}"
              and cp.get("bw") == "\\bw{گریه}{gerye}{to cry}"
              and cp.get("plain", "").startswith("گریه کردن gerye kardan to cry (")
              and "\\" not in cp.get("plain", "") and cp.get("complete") is True,
              "and the compound is written out whole -- the \\vb with the \\bw run "
              "onto it for the book, the compound said and glossed as a whole for "
              "a video", json.dumps(cp, ensure_ascii=False))
    else:
        skip("the Persian recipe on a joined word (no dict/fa.db installed)")

    # --- A BETTER READING, HANDED IN.  lib/lookup never imports the model:
    # the dictionary is the half that works without one.  The caller that
    # has both passes the pieces down, and a piece the dictionary cannot
    # place is looked for under the spellings that came with it.
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "ja.db")
        _fixture_dict(db, "ja", [
            ("お爺さん", "ojiisan", "noun", ["grandfather"], []),
            ("と", "to", "particle", ["and"], []),
            ("遺産", "isan", "noun", ["an inheritance"], [("いさん", "another spelling")]),
            ("おじ", "oji", "noun", ["an uncle"], []),
            ("住む", "sumu", "verb", ["to live, to dwell"], []),
            ("居る", "iru", "verb", ["to be"], [("いました", "polite past")]),
            # a te-form the dictionary lists OUTRIGHT, which is the ordinary
            # case and the one that used to defeat the guard below
            ("見る", "miru", "verb", ["to see"], [("見て", "te-form")]),
            ("下さる", "kudasaru", "verb", ["to give"], [("ください", "please")]),
            # two plain words with no rule between them: the cut is correct
            # and nothing conjugates
            ("子供", "kodomo", "noun", ["a child"], []),
            ("の", "no", "particle", ["of"], []),
        ])
        was = lk.DICT_DIR
        lk.DICT_DIR = td
        lk._CONNS.map = {}
        try:
            got = [w["word"] for w in lk.look_up("ja", "おじいさんと")["words"]]
            check(got == ["おじ", "いさん", "と"],
                  "on its own, longest match reads おじいさん as おじ + いさん "
                  "-- two strings that are in the dictionary and neither of "
                  "which is the word", repr(got))
            r = lk.look_up("ja", "おじいさんと", pieces=[
                {"word": "おじいさん", "lemmas": ["おじいさん", "お爺さん"]},
                {"word": "と", "lemmas": ["と"]}])
            w = r["words"][0]
            check(w["word"] == "おじいさん" and w["hits"]
                  and w["hits"][0]["headword"] == "お爺さん",
                  "handed a better reading it finds the grandfather, under "
                  "the spelling that came with it",
                  json.dumps(w, ensure_ascii=False)[:180])
            check("under お爺さん" in w["via"], "and says under what", w["via"])

            # AND THE FALLBACK MUST ACCOUNT FOR ITSELF.  A model piece the
            # dictionary cannot place is cut again offline -- but only when
            # the language can EXPLAIN the cut, which is the difference
            # between 住んで (a te-form the rules take apart) and おじ+いさん
            # (two coincidences).
            # no lemmas: this is what the model actually returns for a verb
            # complex it has read as one word, and the case the fallback is
            # for.  (With a lemma it would resolve on that and never get here,
            # which is better still.)
            r = lk.look_up("ja", "住んでいました", pieces=[
                {"word": "住んでいました", "lemmas": []}])
            got = [w["word"] for w in r["words"]]
            check(got == ["住んで", "いました"] and all(w["hits"] for w in r["words"]),
                  "a piece nobody can place is cut again where the rules "
                  "account for the pieces", repr(got))
            r = lk.look_up("ja", "おじいさん", pieces=[
                {"word": "おじいさん", "lemmas": []}])
            got = [w["word"] for w in r["words"]]
            check(got == ["おじいさん"] and not r["words"][0]["hits"],
                  "and left alone, unfound, where they do not: an honest "
                  "blank beats a confident wrong answer", repr(got))

            # COULD a rule explain the piece, not DID one do the finding.
            # `_resolve` stops at the first route that resolves, and for an
            # inflected form that is usually the SURFACE one, because
            # dictionaries list inflections too.  見て is in the form table,
            # so the te-form rule that also explains it was never reached,
            # 見て + ください looked like two coincidences, and the reading
            # was thrown away.  Against the real dictionary that cost
            # してください, 待っている and 書いてある, all three of which the
            # offline cut had right.
            r = lk.look_up("ja", "見てください", pieces=[
                {"word": "見てください", "lemmas": []}])
            got = [w["word"] for w in r["words"]]
            check(got == ["見て", "ください"] and all(w["hits"] for w in r["words"]),
                  "a piece the dictionary lists outright is still ACCOUNTED "
                  "for when a rule could reach it too", repr(got))

            # AND A CUT WHERE NOTHING CONJUGATES AT ALL is still a good cut.
            # 子供 + の is two words and no rule; asking whether ANY piece
            # came through an affix rule threw it away, along with 日本の and
            # every other noun + particle in the language.
            r = lk.look_up("ja", "子供の", pieces=[{"word": "子供の", "lemmas": []}])
            got = [w["word"] for w in r["words"]]
            check(got == ["子供", "の"] and all(w["hits"] for w in r["words"]),
                  "a noun and a particle are two words, and no rule has to "
                  "vouch for either", repr(got))
            # while いさん, which the dictionary holds ONLY as `another
            # spelling` of 遺産, is not a word here and never was
            check(not lk._stands(lk._conn("ja"), "いさん",
                                 languages.get_or_default("ja")),
                  "a string held only as another spelling of something else "
                  "does not stand as a word")
            check(lk._stands(lk._conn("ja"), "子供",
                             languages.get_or_default("ja")),
                  "and one the dictionary has under its own spelling does")
        finally:
            lk.DICT_DIR = was
            lk._CONNS.map = {}

    # --- what getdict keeps, and what it now throws away
    import getdict
    ja = languages.get("ja")
    forms = {f: t for f, t, _r in getdict._forms({
        "word": "お爺さん",
        "forms": [{"form": "お爺さん", "tags": ["canonical"]},
                  {"form": "ojiisan", "tags": ["romanization"]},
                  {"form": "住む intransitive godan", "tags": ["canonical"]},
                  {"form": "ja-verb", "tags": ["inflection-template"]}],
        "head_templates": [{"name": "ja-noun", "args": {"1": "お%じい%さん"}}],
    }, ja)}
    check("おじいさん" in forms,
          "a reading in the head template becomes a form, with Wiktionary's "
          "own %% markers taken out of it", repr(sorted(forms)))
    check("住む intransitive godan" not in forms,
          "and a headword LINE is not a form of a language written without "
          "spaces", repr(sorted(forms)))
    check("ja-verb" not in forms, "nor is the name of an inflection table")
    it = languages.get("it")
    forms = {f: t for f, t, _r in getdict._forms({
        "word": "andare", "forms": [{"form": "vado", "tags": ["first-person"]}],
        "head_templates": [{"name": "it-verb", "args": {"1": "and", "2": "are"}}],
    }, it)}
    check(forms == {"vado": "first-person"},
          "a Latin-script language has no script to test against, so nothing "
          "is guessed at from its templates", repr(forms))

    # --- PERSIAN'S OWN INVENTORY covers the two things Wiktionary leaves
    # out.  One is a form carrying an object enclitic: می‌سازمت is the poem's
    # word (دوباره می‌سازمت وطن) and was the report that started this.  The
    # other is the past tense of the 456 verbs of 1402 that arrive with no
    # conjugation table at all -- 1,116 forms absent -- which is reached by
    # putting the infinitive's ن back rather than taking letters off.
    if lk.available("fa"):
        for word, want, why in (
                ("می‌سازمت", "ساختن", "the enclitic -at, on a verb Wiktionary lists"),
                ("نمی‌بینمش", "دیدن", "an enclitic AND a prefix, neither listed"),
                ("پولشان", "پول", "the -ešān enclitic on a noun"),
                ("چشمشان", "چشم", "and again"),
                ("خانه‌ات", "خانه", "the -at enclitic after a vowel"),
                ("پوسیدم", "پوسیدن", "a past tense Wiktionary does not list"),
                ("آسودیم", "آسودن", "and its plural"),
                ("نزدیم", "زدن", "the NEGATIVE past: rebuilt, not shaved, so "
                                 "it is not read as نزد the preposition")):
            r = lk.look_up("fa", word)
            w = (r or {"words": [{}]})["words"][0]
            got = w["hits"][0]["headword"] if w.get("hits") else None
            check(got == want, "%s finds %s -- %s" % (word, want, why),
                  "%s (%s)" % (got, w.get("via")))
        # A SECOND PREFIX IS ALWAYS THE SEARCH EATING THE WORD.  Each of
        # these is a headword whose opening letters look like ب + ن; without
        # the one-prefix guard they came back as village, door and saddle.
        for word in ("بنده", "بندر", "بنزین", "بنیاد"):
            r = lk.look_up("fa", word)
            w = r["words"][0]
            got = w["hits"][0]["headword"] if w.get("hits") else None
            check(got == word, "%s is itself, not two prefixes off something "
                               "else" % word, "%s (%s)" % (got, w.get("via")))
        check(lk.MAX_PEEL == 2,
              "two strips, not three: depth 3 gained no correct answer over "
              "all 16,879 headwords and invented thirty (زرتشت -> زر)")

        # and nothing that was already right may have been taken away
        for word, want in (("کتاب", "کتاب"), ("دیدن", "دیدن"), ("می‌سازم", "ساختن"),
                           ("دارم", "داشتن"), ("مردم", "مردم")):
            r = lk.look_up("fa", word)
            w = r["words"][0]
            got = w["hits"][0]["headword"] if w.get("hits") else None
            check(got == want, "%s is still %s, found as written" % (word, want),
                  "%s (%s)" % (got, w.get("via")))

        # THE FIXTURE BOOK'S mi- AND nemi- WRITTEN APART, and Tatoeba's: each
        # is its verb as one word, and what the split offered beside it --
        # نم (moisture) for نمی, the four pages of می, کرد (a Kurd) for کرد --
        # is gone.  نمی دانم also walks past the phrase page نمی‌دانم to the
        # verb a vocabulary line needs.
        for text, word, want in (("کَسی نِمی بینَد", "نِمی بینَد", "دیدن"),
                                 ("دیگَر پیرَت می دانَد", "می دانَد", "دانستن"),
                                 ("بَرایِ خود حاضِر می کَرد", "می کَرد", "کردن"),
                                 ("من آنرا کافی نمی دانم.", "نمی دانم.", "دانستن")):
            ws = lk.look_up("fa", text)["words"]
            w = next((x for x in ws if x["word"] == word), None)
            got = [h["headword"] for h in w["hits"]] if w else []
            check(got[:1] == [want] and all(h["pos"] == "verb" for h in w["hits"]),
                  "`%s` is %s, read as one word and only as the verb" % (word, want),
                  json.dumps([[x["word"] for x in ws], got], ensure_ascii=False))
    else:
        skip("no dict/fa.db: Persian's own affixes are not exercised")

    # --- EVERY MODULE STILL IMPORTS.  A module was once renamed and another
    # went on importing the old name, so a whole entry point died with
    # ModuleNotFoundError and nothing noticed, because no test ever loaded
    # it.  A module that cannot be imported is a module that cannot be
    # tested, so this comes first.
    for name in sorted(f[:-3] for f in os.listdir(os.path.join(ROOT, "lib"))
                       if f.endswith(".py") and not f.startswith("_")):
        code, out = run([sys.executable, "-c", "import " + name],
                        cwd=os.path.join(ROOT, "lib"), timeout=60)
        check(code == 0, "lib/%s.py imports" % name, out.strip().split("\n")[-1])

    # --- THE PLAYER PAGE OF A VIDEO ON YOUTUBE, AS THE SERVER WRITES IT.
    # This block used to hold the server's `help` flag to the truth (is a
    # dictionary, a corpus or a model installed for the language?), because
    # the player drew an unglossed chunk as bare text -- no hover, no cloud,
    # no ✎, no dictionary -- unless that flag or the video's draft flag said
    # something could help with it.  Neither decides anything now.  An
    # unglossed chunk is legal in every video, and the player makes every
    # unglossed chunk of target text a phrase whatever is or is not
    # installed, as a book's reader always has; it reads no `help` and no
    # draft flag at all.  Nor does the server write `help` into the page any
    # more: it went from ytpages' player config together with the lookup,
    # corpus and getmt imports that answered it, and tests/gloss_llm_video.mjs
    # holds it absent from the page the browser is served.  Whether the
    # phrase is drawn is the player's own render, which only a browser can
    # drive.  What is left to ask here is where the film is.
    sys.path.insert(0, os.path.join(ROOT, "youtube", "lib"))
    import ytpages                                             # noqa: E402
    # a video with NO film of its own: what this asks about is the YouTube
    # shape, and a local video sitting in the tree is not that
    src = None
    fx = sorted(glob.glob(os.path.join(FIX, "videos", "*", "*", "video.json")))
    park = None
    if fx:
        one = os.path.dirname(fx[0])
        park = os.path.join(ROOT, "youtube", "videos",
                            os.path.basename(os.path.dirname(one)),
                            os.path.basename(one))
        if not os.path.exists(park):
            os.makedirs(os.path.dirname(park), exist_ok=True)
            shutil.copytree(one, park)
        else:
            park = None
    try:
        for v in ytpages.list_videos():
            _m, where = ytpages.find_video(v.get("id") or "")
            if where and bundle_film_at(where):
                continue                       # that one IS a film; not this test
            src = ytpages.player_page(v.get("id") or "")
            if src:
                break
    finally:
        if park and _removable(park):
            shutil.rmtree(park, ignore_errors=True)
    if src and "window.YTFRANK=" in src:
        cfg = json.loads(src.split("window.YTFRANK=", 1)[1]
                         .split("</script>", 1)[0].strip().rstrip(";"))
        # WHERE THE FILM IS, for a video that is one.  A video on YouTube
        # says "" and the page then reaches YouTube the way it always did;
        # nothing in video.json declares either, the file being there is the
        # whole of the fact.
        check(cfg.get("media") == "",
              "a video on YouTube names no film of its own", repr(cfg.get("media")))
    else:
        skip("no video installed: the player page of a video on YouTube is not exercised")

    # --- EACH READER'S OWN SWITCH NAME.  The two readers are separate
    # scripts that do the same job with different variables: the book reader
    # keeps the dictionary switch on DICT.on, the player keeps it in `opts`.
    # Writing one file's name into the other reads as `undefined`, which is
    # falsy, which silently turns the feature OFF rather than raising
    # anything -- exactly how the player's prefetch was left never asking.
    js = open(os.path.join(ROOT, "youtube", "lib", "player.js"),
              encoding="utf-8").read()
    check("DICT.on" not in js,
          "the player does not use the book reader's DICT.on: its own "
          "switch is opts.dict")
    tex = open(os.path.join(ROOT, "lib", "tex2html.py"), encoding="utf-8").read()
    check("DICT.on" in tex,
          "while the book reader's switch is exactly that name")

    # --- ENGLISH, EXPLAINED IN ENGLISH.  Every dictionary is the English
    # Wiktionary's, so English's own senses are definitions written in the
    # language being learned, and both readers keep them behind a switch of
    # their own: offered only where the server says the dictionary defines
    # its words, off until turned on, the whole entry asked for only then,
    # and translated only on a second switch.
    player_html = open(os.path.join(ROOT, "youtube", "lib", "player.html"),
                       encoding="utf-8").read()
    for name, src, page in (("the book reader", tex, tex), ("the player", js, player_html)):
        check('id="defmode"' in page and 'id="defmt"' in page,
              "%s has a definitions switch, and one to translate them" % name)
        check("DICT.defines = !!j.definitions" in src,
              "%s offers them only where the dictionary defines its words" % name)
        check("if (defsOn()) body.senses = 'all'" in src,
              "%s asks for the whole entry only with the definitions on" % name)
        check("defsTranslated()" in src and "ParsehMT.translate(" in src.split("function defsInto", 1)[-1],
              "%s translates the definitions with the model in the page" % name)
        check("Parseh.senseLabels(" in src,
              "%s labels a definition as the other reader does (lib/parseh.js)" % name)
    check("store('yt_defs', false)" in js and "MINE('defs')) === '1'" in tex,
          "and both start with the definitions off")
    # ... and the editor's sources read them in the gloss language too, from
    # a switch of the editor's own -- the book's sheet lies over the header
    for name, src in (("the book reader", tex), ("the player", js)):
        check("'sdefmt'" in src and "'sdef'" in src and "defsRead(dict, '.sdef'" in src,
              "%s's sources read English's senses in the gloss language, from a "
              "switch over the dictionary's rows" % name)

    # --- WRITING IS ALWAYS ON IN THE BOOK READER, as it is in the player: no
    # header switch and no mode, the cloud's pencil always, and a pencil over
    # a chunk that opens no cloud -- the click on a chunk left to play.
    check("setGlossing" not in tex and 'id="edittext"' not in tex
          and "contains('glossing')" not in tex,
          "the book reader has no edit mode to turn on")
    check('id="chpen"' in tex and "function penAt" in tex
          and "p.className = 'mkedit'" in tex,
          "a pencil in every cloud, and one over a chunk that opens none")

    # --- A BOOK BROUGHT BACK GOES ON THE SHELF, AND ITS OWN CARD BUILDS IT.
    # The panel carried a build button of its own once; it was taken away on
    # purpose, so that a book installed is grey like any book nobody has built
    # and there is one way to build it rather than two.  So what is asserted
    # here is the absence -- and above all that no command to copy into a
    # terminal came back in its place, which is no door at all on a machine
    # without one.  The panel's own words, after a real upload, are driven in
    # tests/doors.mjs; what can be read off the markup is read off it here.
    import make_index
    panel = make_index.bundle_panel("book", "/books/__upload")
    check("takecopy" not in panel and "Parseh.copy" not in panel
          and "build.sh" not in panel,
          "the bring-back panel hands over no command to copy")
    check('id="takebuild"' not in panel and "buildBook" not in panel
          and 'id="takereload"' in panel,
          "it builds nothing itself, and offers the list the card is on")
    _mi = io.open(make_index.__file__, encoding="utf-8").read()
    check('class="card-build"' in _mi and "data-build=" in _mi,
          "and the book's own card is the one thing that builds it")

    # --- THE LOCAL FILM ANSWERS EVERY QUESTION THE PLAYER ASKS.  A film on
    # this machine stands behind the same object YouTube's iframe does, and
    # the list of what that object is asked was made by reading the
    # transcript's callers -- which missed the Anki panel's frame capture,
    # so `isMuted` was called on an object that had no such method and the
    # button threw on every local film.  The list is now taken from the file
    # itself: whatever the player is asked, the film must answer.
    asked = set(re.findall(r"\bplayer\.([A-Za-z_$][\w$]*)\s*\(", js))
    shim = js.split("player = {", 1)[1].split("\n    };", 1)[0] if "player = {" in js else ""
    answers = set(re.findall(r"^\s{6}([A-Za-z_$][\w$]*)\s*:\s*function", shim, re.M))
    missing = sorted(asked - answers)
    check(not missing and answers,
          "the local film answers all %d methods the player is asked for"
          % len(asked), "missing: %s" % ", ".join(missing) if missing
          else "found none -- the shim could not be read")

    # --- the two doors, and only the two doors.  The studio and the card
    # store were left out of this deliberately: neither reads a dictionary,
    # and an import here would be the first step towards their doing so.
    for mod in ("markdown/app/server.py", "markdown/app/store.py",
                "markdown/app/htmlgen.py", "youtube/lib/anki_store.py",
                "youtube/lib/anki_export.py"):
        src = open(os.path.join(ROOT, mod), encoding="utf-8").read()
        check(not re.search(r"^\s*import lookup\b", src, re.M),
              "%s does not reach for the dictionary" % mod)

    # --- IT CAN BE FOUND.  A feature reachable only from a command line
    # nobody was told about is a feature nobody has, which is what this was:
    # the page existed and nothing linked to it.  These checks lived in the
    # model's section, and would have been deleted with it.
    import lookuppage
    rows = lookuppage.dictionaries()
    check(len(rows) == len(languages.LANGS),
          "the page lists every language the toolbox teaches, whether or "
          "not it has a dictionary", "%d of %d" % (len(rows), len(languages.LANGS)))
    check(all({"code", "name", "have", "entries", "licence", "size"} <= set(r)
              for r in rows),
          "each with what it has, where it came from and how big it is")
    page = lookuppage.page()
    for want, why in (("data-get=", "a button to fetch one"),
                      ("data-remove=", "a button to throw one away"),
                      ("data-stop=", "a button to stop one on its way"),
                      ("data-all=", "and one to get everything a language can have")):
        check(want in page, "the page carries %s" % why)
    check(not re.search(r"__[A-Z]+__", page),
          "and every placeholder in it was filled",
          repr(re.findall(r"__[A-Z]+__", page)[:3]))
    check("/lookup/api/" in page,
          "and its buttons post where the server listens")
    hub = serve_hub()
    check('href="/settings/reading-help/"' in hub,
          "the hub has a door to it -- the whole difference between a "
          "feature and a feature somebody can use")
    reader = io.open(os.path.join(LIB, "tex2html.py"), encoding="utf-8").read()
    player = io.open(os.path.join(YT_LIB, "player.html"), encoding="utf-8").read()
    check('id="lookupset"' in reader and 'id="lookupset"' in player,
          "and so do both readers, beside the switch and not behind it: "
          "somebody without a dictionary is who needs to find it")

    # --- PREPARING WHAT IS COMING, in both readers.  The look-ahead used to
    # be read off the model's own state object, so deleting that object
    # would have stopped the dictionary preparing anything, silently.
    both = [reader, io.open(os.path.join(YT_LIB, "player.js"), encoding="utf-8").read()]
    for name, src in zip(("the book reader", "the player"), both):
        check("function prePump" in src and "function preTargets" in src,
              "%s prepares what is coming" % name)
        check("PRE.busy" in src and "PRE.queue.shift" in src,
              "%s prepares ONE chunk at a time" % name)
        check("PRE.touched" in src and "1500" in src,
              "%s waits for a moment's quiet first" % name)
        check(re.search(r"\bAHEAD\s*=\s*10\b", src),
              "%s looks ten sentences ahead, from a constant of its own"
              % name)


def _heads(r, word=None):
    """The headwords a lookup answered, for one word of the chunk (the first
    that has any hits, when none is named)."""
    for w in (r or {}).get("words") or []:
        if (word is None and w["hits"]) or w["word"] == word:
            return [h["headword"] for h in w["hits"]]
    return []


def test_hits():
    """What a hit carries, and the order the hits come in.

    A verb that is not among a word's four hits cannot be offered as a \\vb
    at all, and every rule below was a verb lost off the end of four, or a
    lemma handed the wrong sound: the sidebar writes what the hit says, and
    it wrote `\\dw{ساختن}{mi-sāzam}` -- the lemma with the inflected form's
    sound.  Each rule is tried on a dictionary of a few words built here,
    written the way the one case needs, so that the rule and nothing else
    decides; a few are then asked of the real dictionaries, where installed.
    """
    section("lookup: the hits")
    import unicodedata
    import lookup as lk
    import languages

    def ask(code, entries, text):
        with tempfile.TemporaryDirectory() as td, _DictDir(td):
            ids = _tiny_dict(os.path.join(td, code + ".db"), code, entries)
            return lk.look_up(code, text), ids

    # --- WHAT A HIT CARRIES.  Its entry (the only thing that tells two رفتن
    # apart, and what the verb builder reads the table of), the sound of the
    # word IN THE CHUNK (translit) and the sound of the LEMMA (head_sound),
    # which are two different things exactly when it matters.
    r, ids = ask("fa", [("ساختن", "verb", "sâxtan", "[sɒːx.t̪æn]",
                         [("می‌سازم", "first-person present singular", "mí-sâzam")])],
                 "می‌سازم")
    h = ((r["words"][0]["hits"] if r["words"] else []) or [{}])[0]
    check(h.get("entry") == ids[0], "a hit names the entry it is", repr(h.get("entry")))
    check(h.get("translit") == "mi-sāzam" and h.get("head_sound") == "sāxtan",
          "and says the word as the chunk has it (mi-sāzam) apart from the "
          "lemma's own sound (sāxtan) -- never the reached form's",
          json.dumps({k: h.get(k) for k in ("translit", "head_sound", "said")},
                     ensure_ascii=False))

    # --- A NAME REACHED THROUGH ITS LOWER CASE IS NOT THE WORD.  getdict
    # writes a capitalised headword's folded spelling beside it with the same
    # empty note, so `given` was the name Given as surely as it was give's
    # participle -- and with four places, English lost give.
    r, _ = ask("en", [("Given", "name", "", "", [("given", "")]),
                      ("give", "verb", "", "", [("given", "participle past")])],
               "he has given it")
    got = _heads(r, "given")
    check(got == ["give", "Given"],
          "a word that is a name only once its capital is gone comes after "
          "the verb it is a form of (given: give, then Given)", repr(got))

    # --- A HEADWORD OF SEVERAL WORDS reached through a bare cell of its
    # table goes after every single word: بلد بودن lists هستند with no note,
    # and هستند came back as six compounds and never as بودن.  The compound
    # is written first here, so only the rule can put it second.
    r, _ = ask("fa", [("بلد بودن", "verb", "", "", [("هستند", "")]),
                      ("بودن", "verb", "", "", [("هستند", "present plural third-person")])],
               "هستند")
    got = _heads(r)
    check(got == ["بودن", "بلد بودن"],
          "a spaced compound reached through a spaceless cell ranks below the "
          "single word (هستند: بودن, then بلد بودن)", repr(got))

    # --- AN AUXILIARY IS NOT A FORM OF THE VERB IT HELPS.  `haben` is the
    # auxiliary row of 9 243 German verbs, and `Wir haben Zeit` listed raven
    # and listen.  An entry reached only that way, or only through a
    # multiword row, is no answer; haben itself keeps its own.
    r, _ = ask("de", [("raven", "verb", "", "", [("haben", "auxiliary")]),
                      ("listen", "verb", "", "", [("haben", "multiword-construction perfect")]),
                      ("haben", "verb", "", "", [("haben", "auxiliary")])],
               "Wir haben Zeit")
    got = _heads(r, "haben")
    check(got == ["haben"],
          "an entry reached only as an auxiliary or a multiword row is not a "
          "hit (haben: not raven, not listen)", repr(got))

    # --- A BARE STEM GOES LAST, where the word is also somebody's headword
    # (fa.lookup.json `bare_stem`): در is the preposition, and دریدن's stem.
    r, _ = ask("fa", [("دریدن", "verb", "", "", [("در", "present stem")]),
                      ("در", "prep")], "در")
    got = _heads(r)
    check(got == ["در", "دریدن"],
          "a present stem that is also a word of its own ranks last (در: the "
          "preposition, then دریدن)", repr(got))

    # --- AFTER -masu, THE VERB.  The rule that takes ました off says which
    # rows answer it (`prefer`: the stem), so 来ました is 来る before 来.
    r, _ = ask("ja", [("来", "noun"),
                      ("来る", "verb", "kuru", "", [("来", "stem", "ki")])], "来ました")
    got = _heads(r)
    check(got[:1] == ["来る"],
          "after ます comes off, the entry reached through its stem comes "
          "first (来ました: 来る)", repr(got))

    # --- A SIMPLIFIED WORD IS THE WORD.  Wiktionary files Chinese under the
    # Traditional spelling and the Simplified one as a row noted
    # `Simplified-Chinese`; 幫倒忙, which carries 帮忙 with no note, came
    # first.  And the hit says how the TEXT spells it, so a Simplified book
    # is never handed a Traditional \dw.
    r, _ = ask("zh", [("幫倒忙", "verb", "bāng dàománg", "", [("帮忙", "")]),
                      ("幫忙", "verb", "bāngmáng", "", [("帮忙", "Simplified-Chinese")])],
               "帮忙")
    hits = r["words"][0]["hits"] if r["words"] else []
    check([x["headword"] for x in hits] == ["幫忙", "幫倒忙"],
          "a Simplified surface counts as the entry's own (帮忙: 幫忙 first)",
          repr([x["headword"] for x in hits]))
    check(hits and hits[0].get("spelled") == "帮忙" and not hits[-1].get("spelled"),
          "and the hit carries `spelled`, the text's own spelling",
          repr([x.get("spelled") for x in hits]))

    # --- COMPOSED FIRST.  ड़ has a code point of its own (U+095C) that NFC
    # takes apart, and no row of a dictionary holds it: typed with it, वह रो
    # पड़ी found no पड़ना.
    nfc = lambda s: unicodedata.normalize("NFC", s)
    r, _ = ask("hi", [(nfc("पड़ना"), "verb", "paṛnā", "",
                       [(nfc("पड़ी"), "feminine perfective singular", "paṛī")])],
               "वह रो प\u095cी।")
    check("पड़ना" in [nfc(x) for x in _heads(r)],
          "a word typed with a precomposed nukta letter is found (the chunk "
          "is NFC-normalised)", repr(_heads(r)))

    # --- TURKISH HAS TWO I'S.  casefold() made İstiyorum `i̇stiyorum`, with a
    # combining dot no row carries, and Islanmak `islanmak`, which is not
    # Turkish: every verb opening a sentence with either letter was lost.
    tr = languages.get_or_default("tr")
    check(lk._fold("İstiyorum", tr) == "istiyorum" and lk._fold("Islanmak", tr) == "ıslanmak",
          "Turkish folds İ to i and I to ı", "%s %s" % (lk._fold("İstiyorum", tr),
                                                        lk._fold("Islanmak", tr)))
    r, _ = ask("tr", [("istemek", "verb", "", "", [("istiyorum", "first-person present singular")]),
                      ("ıslanmak", "verb")], "İstiyorum. Islanmak")
    got = [h for w in r["words"] for h in (w["hits"] or [])[:1]]
    check([h["headword"] for h in got] == ["istemek", "ıslanmak"],
          "and so a sentence opening with either reaches its verb",
          repr([h["headword"] for h in got]))

    # --- A CAPITAL THAT OPENS A SENTENCE IS NOT A NAME'S.  `Seppe la
    # verità` answered with the name Seppe alone and never with sapere, whose
    # past it is.  The lower case is asked, and the name kept after it.
    r, _ = ask("it", [("Seppe", "name"),
                      ("sapere", "verb", "", "", [("seppe", "historic past singular third-person")])],
               "Seppe la verità")
    got = _heads(r, "Seppe")
    check(got == ["sapere", "Seppe"],
          "a capitalised first word that finds only names is looked up in "
          "lower case too, and the verb comes first (Seppe: sapere, Seppe)",
          repr(got))

    # --- AND THE REAL DICTIONARIES, where they are installed: the same
    # rules, on the rows that taught them.
    real = [("fa", "می‌سازم", lambda hs: hs and hs[0]["headword"] == "ساختن"
             and hs[0]["head_sound"] == "sāxtan" and hs[0]["translit"] != "sāxtan",
             "می‌سازم is ساختن, said sāxtan and not as the form"),
            ("fa", "هستند", lambda hs: hs and hs[0]["headword"] == "بودن",
             "هستند is بودن before any compound of it"),
            ("zh", "帮忙", lambda hs: hs and hs[0]["headword"] == "幫忙"
             and hs[0]["spelled"] == "帮忙", "帮忙 is 幫忙, spelled 帮忙"),
            ("ja", "来ました", lambda hs: hs and hs[0]["headword"] == "来る",
             "来ました is 来る"),
            ("de", "haben", lambda hs: hs and not {"raven", "listen"}
             & {h["headword"] for h in hs}, "haben lists neither raven nor listen"),
            ("hi", "वह रो प\u095cी।", lambda hs: hs and nfc(hs[0]["headword"]) == nfc("पड़ना"),
             "पड़ी typed with U+095C is पड़ना"),
            ("it", "Seppe la verità", lambda hs: hs and hs[0]["headword"] == "sapere",
             "Seppe at a sentence's head is sapere")]
    for code, text, ok_, why in real:
        if not lk.available(code):
            skip("no dict/%s.db: %s is not asked of the real dictionary" % (code, why))
            continue
        r = lk.look_up(code, text)
        w = next((w for w in r["words"] if w["hits"] and (
            code != "hi" or w["word"].startswith("प"))), None)
        hs = w["hits"] if w else []
        check(ok_(hs), "the real dictionary: %s" % why,
              json.dumps([(h["headword"], h.get("spelled"), h["translit"],
                           h["head_sound"]) for h in hs], ensure_ascii=False)[:300])


def test_getsyn():
    """What lib/getsyn.py keeps of WordNet, on a synthetic archive written
    here -- no download, and no dependence on the 30 MB the real one is.

    The rule under test is the one the module docstring measures against
    the real data: a synset links two words only where it is the FIRST
    sense BOTH of them list, not where either merely appears in it.
    Skipping that test was what let `heap`'s "a large quantity" synset
    (whose OTHER members are `mountain` and `about_face`, one a real word
    reached through a different sense of its own, one a phrase this file
    never offers at all) leak into `mountain`'s real, separate answer.
    """
    section("lookup: what a synonym table build keeps")
    import getsyn
    import tarfile

    def idx_line(lemma, pos, offset):
        return "%s %s 1 0 1 1 %s  \n" % (lemma, pos, offset)

    def data_line(offset, pos, words, gloss="x"):
        body = " ".join("%s 0" % w for w in words)
        return "%s 03 %s %02x %s 000 | %s  \n" % (offset, pos, len(words), body, gloss)

    # begin/start: mutual, each other's only (so also first) sense --
    # kept.  commence: its own primary sense is elsewhere (00000009, a
    # single-word synset with nothing to pair), so this synset is not ITS
    # first sense -- dropped, on commence's side, even though begin and
    # start still see it standing here.
    index_verb = (idx_line("begin", "v", "00000001") + idx_line("start", "v", "00000001")
                 + idx_line("commence", "v", "00000009"))
    data_verb = (data_line("00000001", "v", ["begin", "start", "commence"])
                + data_line("00000009", "v", ["commence"]))
    # heap's real first sense is the "large quantity" synset it shares
    # with mountain and the phrase about_face; mountain's real first
    # sense is a SEPARATE synset it shares with mount.  heap<->lot links
    # (both list 00000004 first); heap<->mountain must not, because
    # 00000004 is not mountain's first sense; about_face (a phrase) is
    # dropped outright, the same as every multiword lemma.
    index_noun = (idx_line("heap", "n", "00000004") + idx_line("lot", "n", "00000004")
                 + idx_line("mountain", "n", "00000005") + idx_line("mount", "n", "00000005")
                 + idx_line("about_face", "n", "00000004"))
    data_noun = (data_line("00000004", "n", ["heap", "mountain", "lot", "about_face"],
                           "a large quantity")
                + data_line("00000005", "n", ["mountain", "mount"], "a land mass"))
    index_adj = idx_line("plain", "a", "00000006")
    data_adj = data_line("00000006", "a", ["x"])          # w_cnt 1: nothing to pair
    index_adv = idx_line("soon", "r", "00000007")
    data_adv = data_line("00000007", "r", ["y"])

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in (("dict/data.verb", data_verb), ("dict/index.verb", index_verb),
                              ("dict/data.noun", data_noun), ("dict/index.noun", index_noun),
                              ("dict/data.adj", data_adj), ("dict/index.adj", index_adj),
                              ("dict/data.adv", data_adv), ("dict/index.adv", index_adv)):
            b = content.encode("latin-1")
            info = tarfile.TarInfo(name)
            info.size = len(b)
            tf.addfile(info, io.BytesIO(b))
    table = getsyn.build_from(buf.getvalue(), say=lambda *a: None)
    check(table.get("begin") == ["start"] and table.get("start") == ["begin"],
          "a word that is the ONLY other member of its own first sense links "
          "to it, both ways", json.dumps(table.get("begin")))
    check("commenc" not in table or table["commenc"] == [],
          "and a word standing in that sense, but whose OWN first sense is "
          "elsewhere, is not linked to it", json.dumps(table.get("commenc")))
    check(table.get("heap") == ["lot"] and table.get("lot") == ["heap"],
          "a real mutual pair inside a bigger synset still links",
          json.dumps([table.get("heap"), table.get("lot")]))
    check(table.get("mountain") == ["mount"] and table.get("mount") == ["mountain"],
          "mountain's own first sense is a different, smaller synset, and "
          "that is the one it links through -- not heap's",
          json.dumps([table.get("mountain"), table.get("mount")]))
    check(not any("about" in k for k in table),
          "a multiword lemma (about_face) never becomes a key or a value",
          json.dumps(sorted(table)))

    # --- stem(): the same rules lib/mt.js's `stem` runs, checked here
    # against known answers; tests/mtcheck.py --align checks the two
    # implementations agree with each other on the SAME word list.
    got = [getsyn.stem(w) for w in
          ("begin", "started", "cities", "colour", "colours", "centre",
           "realise", "goalless", "careful", "grey", "women", "went")]
    check(got == ["begin", "start", "citi", "color", "color", "center",
                  "realiz", "goal", "car", "grai", "woman", "go"],
          "stem, on its own known answers", repr(got))

    # --- install / rebuild / remove, with the network calls replaced --
    # a downloaded archive is the one thing this test does not have to
    # fetch for real, but the file it writes has to be the real shape.
    old_out, old_dir = getsyn.OUT, getsyn.MT_DIR
    with tempfile.TemporaryDirectory() as td:
        getsyn.MT_DIR = td
        getsyn.OUT = os.path.join(td, "synonyms.en.json")
        was_get = getsyn._get
        getsyn._get = lambda url, say=print, **_bar: buf.getvalue()
        try:
            check(not getsyn.installed(), "nothing installed before the first fetch")
            check(getsyn.get() is True and getsyn.installed(),
                  "get() writes the file, once")
            check(getsyn.get() is False,
                  "and does nothing the second time, without --rebuild")
            meta = json.load(io.open(getsyn.OUT, encoding="utf-8"))
            check(set(meta) >= {"source", "licence", "built", "synonyms"}
                  and meta["synonyms"].get("begin") == ["start"],
                  "the file on disk carries its own source and licence beside "
                  "the table", json.dumps(list(meta))[:200])
            check(getsyn.remove() is True and not getsyn.installed(),
                  "remove() takes it off disk")
            check(getsyn.remove() is False, "and says so the second time")
        finally:
            getsyn._get = was_get
    getsyn.OUT, getsyn.MT_DIR = old_out, old_dir


def test_getdict():
    """What lib/getdict.py keeps of an extract, on records written here.

    Each record is the shape kaikki.org hands over, cut to the fields that
    one rule reads, and goes through the same convert() a real build does
    into a scratch file: so what is checked is the row that reaches the
    dictionary, not a helper's return value.  Every rule is one a verb entry
    or the reader's panel was reading wrong before it existed.
    """
    section("lookup: what a dictionary build keeps")
    import getdict
    import sqlite3

    def built(code, records):
        with tempfile.TemporaryDirectory() as td:
            src, db = os.path.join(td, "x.jsonl"), os.path.join(td, "x.db")
            with open(src, "w", encoding="utf-8") as f:
                for rec in records:
                    rec = dict(rec, lang_code=code)
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            getdict.convert(src, code, db, say=lambda *a: None)
            c = sqlite3.connect(db)
            c.row_factory = sqlite3.Row
            out = {}
            for e in c.execute("SELECT * FROM entry ORDER BY id"):
                rows = [tuple(r) for r in c.execute(
                    "SELECT form, note, roman, ipa FROM form WHERE entry_id = ? "
                    "ORDER BY rowid", (e["id"],))]
                out.setdefault(e["headword"], []).append((dict(e), rows))
            c.close()
            return out

    def rows_of(d, head, k=0):
        return (d.get(head) or [({}, [])])[k][1]

    def entry_of(d, head, k=0):
        return (d.get(head) or [({}, [])])[k][0]

    # --- ONE ROW PER SPELLING AND MEANING.  The same string is often two
    # forms, and keeping the first tag set lost the second: Italian èssere
    # is its canonical headword AND its own auxiliary, and with no
    # auxiliary row a verb builder could not say essere takes essere.  A
    # table's repeat of what the head line already said still goes.
    d = built("it", [{"word": "essere", "pos": "verb", "senses": [{"glosses": ["to be"]}],
                      "forms": [{"form": "èssere", "tags": ["canonical"]},
                                {"form": "èssere", "tags": ["auxiliary"]},
                                {"form": "sóno", "tags": ["first-person", "present", "singular"]},
                                {"form": "sóno", "tags": ["plural", "present", "third-person"],
                                 "source": "conjugation"}]}])
    got = [(f, n) for f, n, _r, _i in rows_of(d, "essere")]
    check(("èssere", "canonical") in got and ("èssere", "auxiliary") in got,
          "a spelling that is two forms keeps both rows (èssere canonical AND "
          "auxiliary)", repr(got))
    check(got.count(("sóno", "first-person present singular")) == 1
          and not any(f == "sóno" and "third-person" in n for f, n in got),
          "while a table's repeat of the head line's spelling is left out", repr(got))

    # --- A ROW THE LANGUAGE'S SCRIPT CANNOT CONTAIN.  Persian's tables held
    # `bâš` as بودن's past stem -- a romanisation misfiled as a form, which a
    # verb builder read as the stem.  A row that SAYS it is the romanisation
    # stays, and so does every Japanese rōmaji row and rōmaji page.
    d = built("fa", [{"word": "بودن", "pos": "verb", "senses": [{"glosses": ["to be"]}],
                      "forms": [{"form": "باش", "tags": ["present", "stem"]},
                                {"form": "bâš", "tags": ["past", "stem"]},
                                {"form": "bud", "tags": ["romanization"]}]}])
    got = [f for f, _n, _r, _i in rows_of(d, "بودن")]
    check("bâš" not in got and "باش" in got and "bud" in got,
          "a Latin stem under a Persian verb is dropped, its romanisation "
          "row kept", repr(got))
    d = built("ja", [{"word": "書く", "pos": "verb", "senses": [{"glosses": ["to write"]}],
                      "head_templates": [{"name": "ja-verb", "args": {"type": "1", "tr": "trans"},
                                          "expansion": "書く • (kaku) transitive godan"}],
                      "forms": [{"form": "kaku", "tags": ["romanization"]},
                                {"form": "書き", "tags": ["stem"], "roman": "kaki"},
                                {"form": "kaki", "tags": ["stem"]}]},
                     {"word": "kaku", "pos": "romanization",
                      "senses": [{"tags": ["Rōmaji", "romanization"],
                                  "alt_of": [{"word": "書く"}]}]}])
    got = [(f, n) for f, n, _r, _i in rows_of(d, "書く")]
    check(("kaku", "romanization") in got and any(f == "kaku" and "Rōmaji" in n for f, n in got)
          and not any(f == "kaki" for f, _n in got),
          "a Japanese rōmaji row and a rōmaji page stay, a bare Latin stem "
          "does not", repr(got))

    # --- CHINESE KEEPS ITS PINYIN IN sounds[].zh_pron, which nothing read:
    # 189 032 of 189 192 entries had no translit, and the 160 that did had a
    # grammar label.  The standard reading, not Xi'an's; the verb's type into
    # entry.head, where the \vb recipe reads whether it splits.
    d = built("zh", [{"word": "睡覺", "pos": "verb", "senses": [{"glosses": ["to sleep"]}],
                      "sounds": [{"zh_pron": "fēijiāo", "tags": ["Mandarin", "Pinyin", "Xi'an"]},
                                 {"zh_pron": "shuìjiào (shui4 jiao4)",
                                  "tags": ["Mandarin", "Pinyin", "Standard"]}],
                      "head_templates": [{"name": "zh-verb", "args": {"type": "vo"}}],
                      "forms": [{"form": "verb-complement", "tags": ["romanization"]},
                                {"form": "睡觉", "tags": ["Simplified-Chinese"]}]}])
    e = entry_of(d, "睡覺")
    check(e.get("translit") == "shuìjiào" and json.loads(e.get("head") or "{}") == {"type": "vo"},
          "a Chinese verb's translit is its standard pinyin and its head says "
          "it is separable", json.dumps({k: e.get(k) for k in ("translit", "head")},
                                        ensure_ascii=False))

    # --- A JAPANESE TEMPLATE'S `tr` IS TRANSITIVITY.  する came out
    # romanised `both`; the rōmaji is in the head line, and the class and
    # the transitivity go into entry.head.
    d = built("ja", [{"word": "する", "pos": "verb", "senses": [{"glosses": ["to do"]}],
                      "head_templates": [{"name": "ja-verb", "args": {"type": "suru", "tr": "both"},
                                          "expansion": "する • (suru) transitive or intransitive"}],
                      "forms": [{"form": "し", "tags": ["stem"], "roman": "shi"}]}])
    e = entry_of(d, "する")
    check(e.get("translit") == "suru"
          and json.loads(e.get("head") or "{}") == {"class": "suru", "tr": "tr./intr."},
          "a Japanese verb is romanised from its head line, not `both`, and "
          "its class and transitivity are in entry.head",
          json.dumps({k: e.get(k) for k in ("translit", "head")}, ensure_ascii=False))

    # --- THE PERSIAN STEMS FROM ONE TABLE, THE LITERARY IRANIAN ONE: a page
    # carries five, only the header says which is which, and شدن came out
    # with the colloquial stem.  Its marks off (گُفت is گفت).
    d = built("fa", [{"word": "گفتن", "pos": "verb", "senses": [{"glosses": ["to say"]}],
                      "inflection_templates": [
                          {"name": "fa-conj", "args": {"header": "(colloquial Tehrani Persian)",
                                                       "inf": "گفتن", "pr-stem": "گ",
                                                       "pr-stem-tr": "g"}},
                          {"name": "fa-conj", "args": {"header": "(literary Iranian Persian)",
                                                       "inf": "گُفتن", "pr-stem": "گو",
                                                       "pr-stem-tr": "gu", "ps-stem": "گُفت",
                                                       "ps-stem-tr": "goft", "inf-tr": "goftán"}}]}])
    head = json.loads(entry_of(d, "گفتن").get("head") or "{}")
    check(head == {"prs": "گو", "prs_tr": "gu", "ps": "گفت", "ps_tr": "goft", "inf_tr": "goftán"},
          "a Persian verb's head holds the literary Iranian stems and sounds, "
          "not the Tehrani table's", json.dumps(head, ensure_ascii=False))

    # --- A POINTER GOES TO THE HOMOGRAPH WITH ITS OWN PART OF SPEECH.  The
    # first entry of the spelling took every pointer: helped landed on help
    # the noun.  And the page's own sound comes with it -- the only record of
    # how an English past is said.
    d = built("en", [{"word": "help", "pos": "noun", "senses": [{"glosses": ["assistance"]}]},
                     {"word": "help", "pos": "verb", "senses": [{"glosses": ["to assist"]}]},
                     {"word": "helped", "pos": "verb",
                      "sounds": [{"ipa": "/hɛlpt/", "tags": ["General-American"]}],
                      "senses": [{"tags": ["form-of", "past"],
                                  "form_of": [{"word": "help"}]}]}])
    noun, verb = rows_of(d, "help", 0), rows_of(d, "help", 1)
    check(not any(f == "helped" for f, _n, _r, _i in noun)
          and ("helped", "past", "", "/hɛlpt/") in verb,
          "a verb's form page points at the verb, with its own pronunciation "
          "(helped /hɛlpt/ under help the verb)", repr((noun, verb)))

    # --- WHAT A GERMAN SENSE SAYS ABOUT ITS USE: the auxiliary of THAT
    # meaning and the object it governs, kept as tags a verb entry reads --
    # and a register the gloss says of the OBJECT (+obj's `<q:rare>`) or of
    # a rare use (`rarely transitive`) is not the sense's: denken, the
    # commonest verb of German, was ranked last and offered as `not to
    # forget`.  Where the gloss says `(rare)` of the sense itself it stays.
    d = built("de", [
        {"word": "denken", "pos": "verb", "senses": [
            {"glosses": ["to think"],
             "raw_glosses": ["(intransitive or rarely transitive) to think [with an (+ "
                             "accusative) ‘about something’ or (rare) accusative "
                             "‘something, e.g. a thought’]"],
             "tags": ["intransitive", "rare", "transitive"],
             "info_templates": [{"name": "+obj", "args": {"1": "de", "2": "an<+acc>:acc<q:rare>"},
                                 "expansion": "[with an (+ accusative) ‘about something’ or "
                                              "(rare) accusative ‘something, e.g. a thought’]"}]},
            {"glosses": ["to exit a program"], "raw_glosses": ["(rare) to exit a program"],
             "tags": ["rare"]}]},
        {"word": "aufstehen", "pos": "verb", "senses": [
            {"glosses": ["to get up"], "raw_glosses": ["to get up [auxiliary sein]"]},
            {"glosses": ["to be open"], "raw_glosses": ["to be open [auxiliary haben or sein]"]}]},
        {"word": "helfen", "pos": "verb", "senses": [
            {"glosses": ["to help"], "info_templates": [{"name": "+obj", "args": {"2": "dat"}}]}]}])
    tags = lambda h: [set(x.split(",")) for x in (entry_of(d, h).get("sense_tags") or "").split("\n")]
    dk, au, he = tags("denken"), tags("aufstehen"), tags("helfen")
    check("rare" not in dk[0] and any(t.startswith("obj:an") for t in dk[0])
          and "rare" in dk[1],
          "denken's first sense keeps its object and loses the `rare` its "
          "+obj qualifier gave it; a sense the gloss calls rare stays rare",
          repr(dk))
    check(au == [{"aux:sein"}, {"aux:haben/sein"}] and he == [{"obj:dat"}],
          "the auxiliary of each meaning and the case a verb governs are "
          "kept as aux: and obj: tags", repr((au, he)))

    # --- THE CASE A TURKISH VERB TAKES is prose in its qualifier, and read
    # only where the qualifier is nothing but cases: kalmak's `(those with
    # -a, -e, -ıp, -ip)` names converb endings, not a dative.
    d = built("tr", [{"word": "bakmak", "pos": "verb", "senses": [
                          {"glosses": ["to look at"],
                           "raw_glosses": ["(intransitive, with dative) to look at"]}]},
                     {"word": "kalmak", "pos": "verb", "senses": [
                          {"glosses": ["to stay"], "raw_glosses": ["(those with -a, -e, -ıp, -ip) to stay"]},
                          {"glosses": ["to be left from"], "raw_glosses": ["(with -den) to be left from"]}]}])
    got = (entry_of(d, "bakmak").get("sense_tags"), entry_of(d, "kalmak").get("sense_tags"))
    check(got == ("with-dative", "\nwith-ablative"),
          "a Turkish sense's government becomes a with- tag, and prose that "
          "only looks like it does not", repr(got))

    # --- A VERB'S REFLEXIVE MEANINGS COME LAST, and the twelve-sense cap cut
    # them: ir lost irse.  A noun's thirteenth sense still goes.
    d = built("es", [{"word": "ir", "pos": "verb",
                      "senses": [{"glosses": ["to go %d" % i]} for i in range(14)]
                      + [{"glosses": ["to leave, go away"], "tags": ["reflexive"]}]},
                     {"word": "casa", "pos": "noun",
                      "senses": [{"glosses": ["house %d" % i]} for i in range(13)]
                      + [{"glosses": ["a thing"], "tags": ["reflexive"]}]}])
    ir = (entry_of(d, "ir").get("sense") or "").split("\n")
    casa = (entry_of(d, "casa").get("sense") or "").split("\n")
    check(len(ir) == 13 and ir[-1] == "to leave, go away" and len(casa) == 12,
          "a verb's reflexive sense past the cap is kept, a noun's is not",
          "ir %d, casa %d" % (len(ir), len(casa)))

    # --- ARABIC'S BARE SPELLINGS.  Its rows are vowelled and a caption is
    # not, so each row's bare spelling is a row of its own -- except where
    # that is only the headword again (the panel said `من (canonical)`).  And
    # a head that says the verb has NO verbal noun (`vn:-`) says so in
    # entry.head, so the recipe need not flag the masdar as missing.
    d = built("ar", [{"word": "زال", "pos": "verb", "senses": [{"glosses": ["to cease"]}],
                      "head_templates": [{"name": "ar-verb", "args": {"1": "I/vn:-"},
                                          "expansion": "زَالَ • (zāla) I, non-past يَزَالُ"}],
                      "forms": [{"form": "زَالَ", "tags": ["canonical", "form-i"]},
                                {"form": "يَزَالُ", "tags": ["non-past"], "roman": "yazālu"}]}])
    got = [(f, n) for f, n, _r, _i in rows_of(d, "زال")]
    check(("يزال", "non-past") in got and ("زال", "canonical form-i") not in got,
          "an Arabic row is stored bare as well, but not a canonical row "
          "that is only the headword bare", repr(got))
    check(json.loads(entry_of(d, "زال").get("head") or "{}") == {"vn_none": ["زَالَ"]},
          "and a verb whose head says `vn:-` has no masdar on record")

    # --- HINDI'S MODERN SPELLING OF A GLIDE: the tables write दिखायी and
    # current Hindi दिखाई, and a text in it reached the noun (sight) and never
    # the verb.  A verb's table only: अनुयायी is a follower, not a glide.
    d = built("hi", [{"word": "दिखाना", "pos": "verb", "senses": [{"glosses": ["to show"]}],
                      "forms": [{"form": "दिखायी", "tags": ["feminine", "perfective", "singular"],
                                 "source": "conjugation", "roman": "dikhāyī"},
                                {"form": "दिखायें", "tags": ["plural", "subjunctive"],
                                 "source": "conjugation"}]},
                     {"word": "अनुयायी", "pos": "noun", "senses": [{"glosses": ["follower"]}],
                      "forms": [{"form": "अनुयायियों", "tags": ["oblique", "plural"],
                                 "source": "declension"}]}])
    got = [(f, n, r) for f, n, r, _i in rows_of(d, "दिखाना")]
    check(("दिखाई", "feminine perfective singular", "dikhāyī") in got
          and ("दिखाएँ", "plural subjunctive", "") in got
          and len(rows_of(d, "अनुयायी")) == 2,
          "a Hindi verb's -यी/-ये cells gain their -ई/-ए spelling, a noun's "
          "do not", repr(got))

    # --- PERSIAN'S PRONOUN COLUMN.  Seven old tables head their rows with
    # من تو او ..., filed as forms of the verb: every pronoun in a sentence
    # came back as a verb hit.  A cell with none of the page's stems in it
    # goes; the optative beside it, which has one, stays.
    d = built("fa", [{"word": "آراستن", "pos": "verb", "senses": [{"glosses": ["to adorn"]}],
                      "forms": [{"form": "آرا", "tags": ["stem"]},
                                {"form": "آراست", "tags": ["stem"]},
                                {"form": "من", "tags": ["error-unrecognized-form", "singular"],
                                 "source": "conjugation"},
                                {"form": "آرایاد", "tags": ["error-unrecognized-form", "singular"],
                                 "source": "conjugation"}]}])
    got = [f for f, _n, _r, _i in rows_of(d, "آراستن")]
    check("من" not in got and "آرایاد" in got,
          "a Persian table's pronoun column is not a form of the verb; its "
          "optative is", repr(got))

    # --- ENGLISH HAS MANY ACCENTS AND IS WRITTEN IN ONE (`avoid_mode`:
    # "all").  A sound is avoided only when EVERY tag is avoided -- fix's only
    # /fɪks/ is Australia + Canada + UK + US -- a weak form never while
    # another is left, /phonemic/ before [narrow].  Persian keeps "any": a
    # sound tagged Dari is Dari.
    ipa = getdict._ipa
    got = (ipa({"sounds": [{"ipa": "/fɪks/", "tags": ["Australia", "Canada", "UK", "US"]}]}, "en"),
           ipa({"sounds": [{"ipa": "/fɪks/", "tags": ["Australia", "New-Zealand"]}]}, "en"),
           ipa({"sounds": [{"ipa": "/də/", "note": "weak form"}, {"ipa": "/duː/"}]}, "en"),
           ipa({"sounds": [{"ipa": "[pʰæs]", "tags": ["General-American"]},
                           {"ipa": "/pæs/", "tags": ["General-American"]}]}, "en"),
           ipa({"sounds": [{"ipa": "/a/", "tags": ["Dari", "formal"]}, {"ipa": "/b/"}]}, "fa"))
    check(got == ("/fɪks/", "", "/duː/", "/pæs/", "/b/"),
          "English avoids a sound only when all its tags are avoided, skips a "
          "weak form and prefers /phonemic/; Persian avoids on any tag",
          repr(got))


def test_translit():
    """The dictionary's sound, written the way the edition writes one."""
    section("lookup: the sound a hit is given")
    import translit

    # --- FRENCH IS A RESPELLING, NOT A TABLE: the final mute e, elision and
    # liaison, no doubled letters, and nothing at all for a sound the scheme
    # has no letter for (docs/lang/fr.md).
    for ipa, want, why in (("/pʁɑ̃.dʁə/", "prãdr", "a final mute e is not said"),
                           ("/mə/", "me", "unless it is the only vowel"),
                           ("/s‿ɑ̃/", "sã", "a one-consonant pronoun elides"),
                           ("/nu.z‿ɑ̃/", "nou-zã", "a liaison carries its consonant on"),
                           ("/muʁ.ʁe/", "mouré", "no letter is doubled"),
                           ("/su.v(ə).niʁ/", "souvenir", "an optional sound is kept"),
                           ("/xota/", "", "a sound with no letter gives nothing")):
        got = translit.respell_fr(ipa)
        check(got == want, "French %s is %r: %s" % (ipa, want, why), repr(got))
    check(translit.from_ipa("fr", "/o.ʒuʁ.d‿ɥi/") == "oʒourdüi",
          "and a tie inside one word is the elision it is spelt with, not a "
          "liaison (aujourd'hui)", translit.from_ipa("fr", "/o.ʒuʁ.d‿ɥi/"))

    # --- NO ARABIC WORD STARTS WITH A HAMZA in this edition: Wiktionary
    # writes one on every word that begins with a vowel (ʔarā), the edition
    # only inside a word (saʾala), and its letters are ʾ ʿ ḫ ġ.
    got = [translit.tidy_roman("ar", s) for s in ("ʔarā", "saʔala", "kataba ʔilā", "ḵaraja")]
    check(got == ["arā", "saʾala", "kataba ilā", "ḫaraja"],
          "an Arabic romanisation loses a word-initial hamza and takes the "
          "edition's letters (drop_initial)", repr(got))

    # --- WHICH OF A PERSIAN FORM'S ROWS SAYS IT: the Iranian one where
    # there is one (some verbs list the Dari table first: نمی‌دانستم came out
    # dānistam), the part after a cell's last slash (būd /bud), an empty
    # first row left empty, and the IPA only where no row romanises it.
    got = (translit.form_sound("fa", ["nē-dānistam", "némi-dânestam"]),
           translit.form_sound("fa", ["būd /bud"]),
           translit.form_sound("fa", ["", "bídihēd"]),
           translit.form_sound("fa", ["", ""], ["[bɒːd]"]))
    check(got == ("nemi-dānestam", "bud", "", "bād"),
          "a Persian form is said by its Iranian row, after its last slash, "
          "not by a Dari row behind an empty one, and by its IPA only when "
          "nothing romanises it", repr(got))


# ------------------------------------------------------------------ verbs
def test_verbs_core():
    """The \\vb a dictionary hit carries, as lib/verbs/__init__.py writes it.

    A verb used to be offered to the chunk editor as a \\dw, the one thing a
    vocabulary line is told never to do with a verb.  Now the language's
    recipe says which forms and which facts, and the core writes the four
    shapes from that one description: `tex` for a book, `plain` and `here`
    for a video, `line` for the reading panel.  What is held here is the
    core's half -- the cleaning, the meaning, the shapes agreeing with each
    other and with the reader -- tried with throwaway recipes, so that no
    language's data decides any of it.
    """
    section("verbs: the core")
    import contextlib
    import languages
    import texparse
    import texwrite
    import verbs as V
    P = V.Parts

    # --- WHAT LATEX WOULD READ AS AN INSTRUCTION IS TAKEN OUT, NOT ESCAPED:
    # texwrite refuses $ % & # _ ^ ~ \ { } escaped as well as raw, and
    # refuses the whole save.  Two of them are words, and are written as
    # the words -- Chinese 研發 is "to do R&D", and taken out it read "RD".
    got = V.sanitise("50% sure, R&D; $x_y^z~{a}\\b  c -- d --- e")
    check(got == "50 per cent sure, R and D; xyzab c – d — e",
          "a slot loses every TeX special, writes % and & as words and "
          "TeX's dashes as the dashes they print", repr(got))

    # --- THE MEANING IS ONE LINE OF A VOCABULARY ENTRY, and a sense is
    # written for a dictionary page.
    for sense, want, why in (
            ("to become; a light verb used in a large number of compound verbs.",
             "to become", "the first equivalent, up to the semicolon"),
            ("to dry (of paint, varnish or anything else that was wet)", "to dry",
             "a qualifier long enough to be a definition goes"),
            ("to dry (of paint)", "to dry (of paint)", "a short one is a fact, and stays"),
            ("to be (See the Usage Notes)", "to be", "a pointer at the source's page goes"),
            ("to take a shower or bath.", "to take a shower or bath",
             "a dictionary sentence's full stop goes"),
            ("to put, place, set, etc.", "to put, place, set, etc.",
             "an abbreviation's does not"),
            # A SENSE WRITTEN AS A SENTENCE starts small, as every other
            # verb's `to go` does: the second Arabic قال is "To nap." in its
            # source, and 173 Turkish first senses open the same way.
            ("To nap.", "to nap", "a sentence's capital To is written small"),
            ("Of rain: to pour down.", "of rain: to pour down",
             "and so is the Of of such a label"),
            ("To Germanize, to make German", "To Germanize, to make German",
             "but not before a capital, which may be a name's"),
            ("Of UN troops: to withdraw", "Of UN troops: to withdraw",
             "or an acronym's")):
        got = V.trim_meaning(sense)
        check(got == want, "the meaning: %s (%r)" % (why, want), repr(got))
    long_ = "to walk slowly and without any particular purpose or direction around the town"
    got = V.trim_meaning(long_)
    check(len(got) <= V.MEANING_CAP and long_.startswith(got) and long_[len(got)] == " ",
          "a long sense is cut at a word, within %d characters" % V.MEANING_CAP, repr(got))
    got = V.trim_meaning("to look at, to watch, to observe carefully and with great "
                         "attention, to regard")
    check(got == "to look at, to watch",
          "and at the last equivalent that fits, where there is one", repr(got))
    got = V.trim_meaning("to arrive at the station early", cap=17)
    check(got == "to arrive",
          "a cut between words never leaves a word the phrase cannot end on "
          "(Chinese 上島: '... appear in the')", repr(got))
    got = V.trim_meaning("to look at, and then at something else entirely", cap=20)
    check(got == "to look at",
          "while a cut at a comma keeps its equivalent whole, preposition and "
          "all -- `to look at` is a verb and `to look` another", repr(got))

    # --- THE FOUR SHAPES, FROM ONE DESCRIPTION.  A word of the language
    # inside an extra is a tl() token, which only the core turns into \pw:
    # a recipe writing the macro itself would see it taken apart by the
    # cleaning above.
    vb = V.compose("it", P(parts=[("andare", ""), ("vado", ""), ("andato", "")],
                           extras=["aux. " + V.tl("essere")]),
                   word="vado", of_form="vàdo", gloss="en", meaning="to go")
    want = {"tex": "\\vb{andare}{}{vado}{}{andato}{}{to go (aux. \\pw{essere})}",
            "plain": "andare · pres. vado · p.p. andato · to go (aux. essere)",
            "here": "vado vàdo (andare · pres. vado · p.p. andato · to go (aux. essere))",
            "line": "pres. vado · p.p. andato · aux. essere",
            "lemma": "andare", "labels": ["pres.", "p.p."], "extras": ["aux. essere"],
            "meaning": "to go", "parts": [["andare", ""], ["vado", ""], ["andato", ""]],
            "notes": [], "reading": "", "complete": True, "missing": []}
    off = {k: vb.get(k) for k in want if vb.get(k) != want[k]}
    check(not off, "one verb, four shapes: the book's \\vb, the video's line, the "
                   "line hung on the chunk's word, the panel's line",
          json.dumps(off, ensure_ascii=False))
    check(V.compose("it", P(parts=[("", "x"), ("vado", ""), ("andato", "")])) is None,
          "and no first form is no \\vb")
    vb = V.compose("it", P(parts=[("venire", ""), ("vengo", ""), ("venuto", "")],
                           extras=["aux. " + V.tl("essere"), "p.r. " + V.tl("venni", "vénni")]),
                   meaning="to come")
    check("(aux. \\pw{essere}; p.r. \\pw{venni} \\textit{vénni})" in vb["tex"]
          and vb["plain"].endswith("to come (aux. essere; p.r. venni vénni)")
          and vb["extras"] == ["aux. essere", "p.r. venni vénni"],
          "a word of the language in an extra is \\pw in the book, with its sound "
          "in \\textit, and plain text in the video; the extras share one "
          "parenthesis, joined by '; '", json.dumps(vb, ensure_ascii=False)[:300])

    # A MEANING THAT ALREADY ENDS IN A SHORT PARENTHETICAL (trim_meaning's
    # _unqualified keeps one that is short: "to wait (for)") must not open a
    # SECOND parenthesis right after the extras' own -- German's warten used
    # to read "to wait (for) (auf + acc.)"; the two now share one, "to wait
    # (for; auf + acc.)".  An interior parenthetical earlier in the meaning
    # is untouched: only the trailing one is a candidate.
    vb = V.compose("de", P(parts=[("warten", ""), ("wartete", ""), ("gewartet", "")],
                           extras=["auf + acc."]),
                   meaning="to wait (for)")
    check(vb["tex"].endswith("{to wait (for; auf + acc.)}")
          and vb["plain"].endswith("to wait (for; auf + acc.)"),
          "the meaning's own trailing parenthetical joins the extras' one "
          "rather than opening a second", json.dumps(vb, ensure_ascii=False)[:300])
    vb = V.compose("de", P(parts=[("sehen", ""), ("sah", ""), ("gesehen", "")],
                           extras=["aux. " + V.tl("haben")]),
                   meaning="to see (something) (a reference)")
    check(vb["tex"].endswith("{to see (something) (a reference; aux. \\pw{haben})}"),
          "only the LAST parenthetical merges; an earlier one in the meaning "
          "stays where it was", json.dumps(vb, ensure_ascii=False)[:300])

    # A PAIR WITHOUT ITS FORM IS NOT PRINTED -- the preamble's \ifblank --
    # and a sound with no form says nothing: a Chinese verb gives its split
    # and no can't form.
    vb = V.compose("zh", P(parts=[("睡觉", "shuìjiào"), ("睡了觉", "shuìle jiào"), ("", "x")]),
                   meaning="to sleep")
    check(vb["tex"] == "\\vb{睡觉}{shuìjiào}{睡了觉}{shuìle jiào}{}{}{to sleep}"
          and vb["plain"] == "睡觉 shuìjiào · split 睡了觉 shuìle jiào · to sleep"
          and vb["line"] == "split 睡了觉 shuìle jiào",
          "a blank pair is left out of every shape", json.dumps(vb, ensure_ascii=False)[:300])

    # NOT ENGLISH, NO MEANING: Wiktionary's senses are English, and a book
    # glossed in Italian gets the parenthesis alone rather than an English
    # line in an Italian gloss.  A recipe that could not fill something says
    # what, and the entry says it is not finished.
    vb = V.compose("it", P(parts=[("andare", ""), ("vado", ""), ("", "")],
                           extras=["aux. " + V.tl("essere")], missing=["past participle"]),
                   gloss="it", meaning="to go")
    check(vb["tex"] == "\\vb{andare}{}{vado}{}{}{}{(aux. \\pw{essere})}" and vb["meaning"] == ""
          and vb["complete"] is False and vb["missing"] == ["past participle"],
          "glossed in another language the meaning is left out; what is missing "
          "is named and the entry is not complete", json.dumps(vb, ensure_ascii=False)[:300])

    # --- THE VIDEO'S LINE IS THE BOOK'S \vb READ BACK.  A video's
    # vocabulary is plain text, and the one way a \vb has ever become one is
    # texparse.voc_text: a line built any other way reads one verb two ways
    # in two readers.  The slash is the case that taught it: `aux.
    # \pw{avere}/\pw{essere}` prints avere/essere, and read "avere /
    # essere" everywhere but the PDF.
    same = []
    for code, parts in (
            ("it", P(parts=[("andare", ""), ("vado", ""), ("andato", "")],
                     extras=["aux. " + V.tl("essere")])),
            ("it", P(parts=[("cominciare", ""), ("comincio", ""), ("cominciato", "")],
                     extras=["aux. " + V.tl("avere") + "/" + V.tl("essere")])),
            ("zh", P(parts=[("看见", "kànjiàn"), ("", ""), ("看不见", "kànbujiàn")])),
            ("hi", P(parts=[("करना", "karnā"), ("कर", "kar"), ("किया", "kiyā")],
                     extras=["+" + V.tl("ने")])),
            ("de", P(parts=[("fahren", ""), ("fuhr", ""), ("gefahren", "")],
                     extras=["er " + V.tl("fährt"), "aux. sein"])),
            ("it", P(parts=[("volare", ""), ("volo", ""), ("volato", "")],
                     meaning="to fly -- high, 100% & more (really)"))):
        vb = V.compose(code, parts, meaning="to go")
        back = texparse.voc_text(vb["tex"], code)
        if back != vb["plain"]:
            same.append("%s: %r vs %r" % (code, back, vb["plain"]))
    check(not same, "a video's line is exactly what texparse reads out of the "
                    "book's \\vb (a slash, a blank pair, +ने, a dash, a per cent)",
          "; ".join(same))

    # ...EXCEPT WHERE THE VIDEO IS SAID TO DIFFER, and in those three ways
    # only: an extra that is the video's alone (Persian's colloquial present:
    # videos are spoken Tehrani, books are not), the kana a Japanese
    # headword is read with (the book's chunk has its kana line), and
    # Arabic's words written bare as its captions are (vb_video_bare).
    fa = V.compose("fa", P(parts=[("گفتن", "goftan"), ("گو", "gu"), ("گفت", "goft")],
                           extras_video=["coll. " + V.tl("می‌گم", "mi-gam")]),
                   word="گفت", of_form="goft", meaning="to say")
    ja = V.compose("ja", P(parts=[("書く", "kaku"), ("書き", "kaki"), ("書いて", "kaite")],
                           extras=["godan", "tr."], reading="かく"),
                   word="書いて", meaning="to write")
    ar = V.compose("ar", P(parts=[("كَتَبَ", "kataba (I)"), ("يَكْتُبُ", "yaktubu"),
                                  ("كِتَابَة", "kitāba")],
                           notes=["masdar also: " + V.tl("كِتَاب", "kitāb")]),
                   word="يَكْتُبُ", meaning="to write")
    AR = languages.get_or_default("ar")
    check(fa["plain"] == texparse.voc_text(fa["tex"], "fa") + " (coll. می‌گم mi-gam)"
          and "می‌گم" not in fa["tex"],
          "a video-only extra is in the video's line and not in the book's \\vb",
          fa["plain"])
    check(ja["plain"].replace(" かく", "", 1) == texparse.voc_text(ja["tex"], "ja")
          and ja["plain"].startswith("書く かく kaku") and "かく" not in ja["tex"]
          and ja["reading"] == "かく",
          "a headword's kana is printed after it in the video's line and "
          "never in the \\vb", ja["plain"])
    check(ar["plain"] == V.strip_marks(texparse.voc_text(ar["tex"], "ar"), AR)
          and "كَتَبَ" in ar["tex"] and ar["plain"].startswith("كتب kataba (I)"),
          "an Arabic video line is the \\vb read back without its harakat, the "
          "book's \\vb keeping them", ar["plain"])

    # --- `here`: THE LEMMA'S ENTRY HUNG ON THE WORD THE CHUNK HAS, with
    # that word's own sound.  The word is the lemma (case aside): the entry
    # alone.  No sound from the lookup: the pair that IS the word says it --
    # English has no romanised rows, and `went (go ...)` wanted `went wɛnt`.
    check(ar["here"] == "يكتب yaktubu (%s)" % ar["plain"],
          "a word with no sound of its own takes the sound of the pair it is "
          "spelt as", ar["here"])
    # THE PAIR'S SOUND BEFORE LOOKUP'S, where the word is the pair's form
    # once the marks are off: the Persian fixture book's اُفتاد (its ُ is
    # the o of oftād) was said with lookup's aftād -- Wiktionary's Dari, on
    # its form rows -- beside the line's own `past افتاد oftād`.  A word that
    # is no pair's form keeps lookup's; a mark written otherwise makes
    # another word (Arabic يَصِلْ is the jussive yaṣil, not يَصِلُ yaṣilu).
    fall = P(parts=[("افتادن", "oftādan"), ("افت", "oft"), ("افتاد", "oftād")])
    got = V.compose("fa", fall, word="اُفتاد.", of_form="aftād", meaning="to fall")["here"]
    check(got == "اُفتاد oftād (افتادن oftādan · pres. افت oft · past افتاد oftād · to fall)",
          "a word that is a pair's form, vowelled or not, is said with that "
          "pair's sound and not lookup's", got)
    got = V.compose("fa", P(parts=[("خریدن", "xaridan"), ("خر", "xar"), ("خرید", "xarid")]),
                    word="خریدم", of_form="xaridam", meaning="to buy")["here"]
    check(got.startswith("خریدم xaridam ("), "a word that is no pair's form keeps "
                                              "lookup's sound", got)
    got = V.compose("ar", P(parts=[("وَصَلَ", "waṣala (I)"), ("يَصِلُ", "yaṣilu"),
                                   ("صِلَة", "ṣila")]),
                    word="يَصِلْ", of_form="yaṣil", meaning="to arrive")["here"]
    check(got.startswith("يصل yaṣil ("), "and a word whose marks say otherwise is "
                                          "not that pair's form", got)
    got = V.compose("en", P(parts=[("go", "ɡoʊ"), ("went", "wɛnt"), ("gone", "ɡɔn")]),
                    word="Went", meaning="to go")["here"]
    check(got.startswith("Went wɛnt (go"), "a capital does not make it another "
                                            "word either", got)
    vb = V.compose("it", P(parts=[("andare", ""), ("vado", ""), ("andato", "")]),
                   word="Andare", meaning="to go")
    check(vb["here"] == vb["plain"], "the lemma itself, capital or not, is the entry "
                                     "alone", vb["here"])

    # --- A HINT IS NOT A GAP.  Arabic lists two to seven masdars for 1 122
    # of its 7 233 verbs; the slot takes the first and the rest are `notes`,
    # in no shape at all and never in `missing`.
    check(ar["notes"] == ["masdar also: كِتَاب kitāb"] and ar["complete"]
          and "كِتَاب kitāb" not in ar["tex"] + ar["plain"] + ar["line"],
          "notes are shown beside the entry and printed in none of its shapes",
          repr(ar["notes"]))

    # --- THE TWO DOORS, on a dictionary of two words and a recipe written
    # here.  attach() is what serve.py calls on every lookup.
    with tempfile.TemporaryDirectory() as td, _DictDir(td):
        andare, casa = _tiny_dict(os.path.join(td, "it.db"), "it", [
            ("andare", "verb", "", "", [("vado", "first-person present singular", "vàdo")]),
            ("casa", "noun")])

        def recipe(ctx):
            if ctx.entry["pos"] != "verb":
                return None
            f = ctx.pick(require="first-person present")
            return P(parts=[(ctx.entry["headword"], ""), (f.form if f else "", ""),
                            ("andato", "")], extras=["aux. " + V.tl("essere")])

        def answer(kind, via):
            return {"words": [{"word": "vado", "kind": kind, "via": via,
                               "hits": [{"entry": andare, "headword": "andare", "pos": "verb",
                                         "of_form": "vàdo", "senses": ["to go"]},
                                        {"entry": casa, "headword": "casa", "pos": "noun",
                                         "senses": ["house"]}]}]}
        was = dict(V.RECIPES_OVERRIDE)
        told = set(V._TOLD)
        kept = []

        def use(fn):
            # A SWAP CLEARS THE CACHE.  A built entry is filed under the
            # recipe function's id(), and a throwaway lambda freed here can
            # hand its id to the next one -- which is then answered with the
            # first one's cached None.  The server's recipes live as long as
            # it does; a test's do not, so every swap forgets (and keeps the
            # function alive besides).
            kept.append(fn)
            V.RECIPES_OVERRIDE["it"] = fn
            V.clear_cache()
        try:
            use(recipe)
            r = V.attach(answer("surface", "as written"), "it", "vado a casa", "en")
            hs = r["words"][0]["hits"]
            check("vb" in hs[0] and "vb" not in hs[1]
                  and hs[0]["vb"]["tex"] == "\\vb{andare}{}{vado}{}{andato}{}{to go (aux. \\pw{essere})}",
                  "attach gives the verb hit its \\vb and the noun none",
                  json.dumps(hs, ensure_ascii=False)[:300])
            here = (hs[0].get("vb") or {}).get("here") or ""
            check(here.startswith("vado vàdo (andare"),
                  "a word found as written is said with its own row's sound", here)
            # REACHED THROUGH ANOTHER FORM, the hit's sound is that form's:
            # いらっしゃいます read `irasshai`, Persian خوانان `xwān`.
            for kind, via in (("affix", "the ending -o taken off"),
                              ("surface", "under andare")):
                r = V.attach(answer(kind, via), "it", "vado a casa", "en")
                here = (r["words"][0]["hits"][0].get("vb") or {}).get("here") or ""
                check(here.startswith("vado (andare"),
                      "a word reached %s does not take that form's sound"
                      % ("through an affix" if kind == "affix" else "under another "
                         "spelling"), here)

            # A RECIPE'S BUG MAY COST ITS \vb AND NEVER THE LOOKUP, and is
            # told once: the look-ahead asks ten chunks at a time, and the
            # four hundredth traceback buries the first.
            def boom(ctx):
                raise ValueError("a recipe's own bug")
            use(boom)
            V._TOLD.discard(("it", "recipe"))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                r1 = V.attach(answer("surface", "as written"), "it", "vado a casa", "en")
                V.clear_cache()
                r2 = V.attach(answer("surface", "as written"), "it", "vado a casa", "en")
            hs = [h for r in (r1, r2) for h in r["words"][0]["hits"]]
            check(len(hs) == 4 and not any("vb" in h for h in hs),
                  "a recipe that raises costs its hits their \\vb and nothing else")
            check(err.getvalue().count("verbs: it:") == 1 and "a recipe's own bug" in err.getvalue(),
                  "and is told on stderr once, with its traceback", err.getvalue()[-300:])
            use(lambda ctx: {"tex": "\\vb{x}"})
            with contextlib.redirect_stderr(io.StringIO()):
                check(V.build("it", answer("", "")["words"][0]["hits"][0], "vado") is None,
                      "a recipe that answers anything but a Parts is not believed")
            use(None)
            check(V.build("it", answer("", "")["words"][0]["hits"][0], "vado") is None,
                  "and a language with no recipe offers no \\vb: its verbs stay \\dw")

            # THE LAST WORD IS THE SAVE'S OWN.  A recipe that puts every
            # special in every slot still gets a \vb, and it is one texwrite
            # takes -- asked of the check itself and then of a real save.
            use(lambda ctx: P(
                parts=[("an$da&re", "a_n{d}a^re"), ("va%do", "v~o"), ("an#da\\to", "")],
                meaning="to go $%&#_^~\\{} far -- fast",
                extras=["aux. " + V.tl("es{se}re", "ès\\sere")], missing=["the {sound}"]))
            vb = V.build("it", answer("", "")["words"][0]["hits"][0], "vado")
            refused = ""
            try:
                texwrite._check_voc((vb or {}).get("tex") or "\\vb{}", "the smoke test")
            except texwrite.Refused as e:
                refused = str(e)
            check(vb is not None and not refused,
                  "a \\vb built from slots full of TeX specials is one texwrite "
                  "accepts", refused or json.dumps(vb, ensure_ascii=False)[:200])
            fb = next((b for b in fixture_books() if b.lang.code == "it"), None) \
                or next(iter(fixture_books()), None)
            if vb and fb:
                with tempfile.TemporaryDirectory() as bd:
                    path = texwrite.book_chapters(texwrite_copy(fb, bd))[0]["path"]
                    mine = texwrite.read_chunks(path)
                    i = max(k for k, c in enumerate(mine) if c["glossed"])
                    try:
                        texwrite.edit_chunk(path, i, {"voc": vb["tex"]})
                        back = texwrite.read_chunks(path)[i]["voc"]
                        refused = "" if back == vb["tex"] else "read back as %r" % back
                    except texwrite.Refused as e:
                        refused = str(e)
                check(not refused, "and a real save of it into a chapter goes "
                                   "through (%s)" % fb.slug, refused)
        finally:
            V.RECIPES_OVERRIDE.clear()
            V.RECIPES_OVERRIDE.update(was)
            V._TOLD.clear()
            V._TOLD.update(told)

    # --- EVERY LANGUAGE HAS ONE.  A language without lib/verbs/<code>.py
    # would simply have no \vb, which is not an error -- but a registry
    # language whose recipe will not IMPORT is one, and says so only on the
    # server's stderr.
    for code in languages.CODES:
        if not os.path.isfile(os.path.join(LIB, "verbs", "%s.py" % code)):
            skip("no lib/verbs/%s.py: %s verbs are offered as \\dw"
                 % (code, languages.get(code).name))
            continue
        check(callable(V.recipe_for(code)), "lib/verbs/%s.py imports and has a recipe" % code)


def _verb_case_dict(td, code, k, case):
    """One case of tests/fixtures/verbs/<code>.json as a dictionary of its
    own: lookup's SCHEMA, the entry, then its rows in the order given --
    rowids ascending, because a recipe takes the entry's own rows to be one
    unbroken run, as getdict writes them -- a fourth element into form.ipa.
    -> (the directory to point lookup at, the entry's id)"""
    import lookup as lk
    d = os.path.join(td, "%s-%d" % (code, k))
    os.makedirs(d)
    c = lk.create(os.path.join(d, "%s.db" % code))
    e = case["entry"]
    cols = ("headword", "translit", "ipa", "reading", "pos", "sense", "sense_tags", "head")
    eid = c.execute("INSERT INTO entry (%s) VALUES (%s)" % (", ".join(cols), ",".join("?" * len(cols))),
                    [e.get(x) or "" for x in cols]).lastrowid
    for row in case["forms"]:
        form, note, roman, ipa = (list(row) + ["", "", ""])[:4]
        c.execute("INSERT INTO form (form, entry_id, note, roman, ipa) VALUES (?,?,?,?,?)",
                  (form, eid, note or "", roman or "", ipa or ""))
    c.commit()
    c.close()
    return d, eid


def test_verbs_recipes():
    """Every language's recipe, on its own cases, with no dictionary installed.

    The forms a \\vb prints are the language's business: Persian's two stems,
    Arabic's masdar and form number, the Japanese class, a Chinese verb's
    split, German's auxiliary and the Italian one only when it is not avere.
    tests/fixtures/verbs/<code>.json holds eight real entries per language,
    cut from the Wiktionary extracts to the rows the recipe reads (README
    there), each built into a dictionary of one entry and run the way a
    reader runs it -- the lookup and then attach, or build where the chunk's
    word does not reach the entry through the rows kept -- and the \\vb that
    comes out is compared with the one written down.
    """
    section("verbs: every language's recipe")
    import languages
    import lookup as lk
    import tex2html
    import texparse
    import texwrite
    import verbs as V
    was_over = dict(V.RECIPES_OVERRIDE)
    was_t2h, was_tp = tex2html.LANG, texparse._LANG
    try:
        for code in languages.CODES:
            L = languages.get(code)
            path = os.path.join(FIX, "verbs", "%s.json" % code)
            if not os.path.isfile(path):
                skip("no tests/fixtures/verbs/%s.json: %s's recipe is not tried "
                     "offline" % (code, L.name))
                continue
            real = V.recipe_for(code)
            if not check(real is not None, "%s has a recipe to try (lib/verbs/%s.py)"
                                           % (L.name, code)):
                continue
            # what the recipe handed the core, per (entry, word), so the
            # book-only reading below is composed from the same description
            said = {}

            def spy(ctx, _real=real, _said=said):
                p = _real(ctx)
                _said[(ctx.entry["id"], ctx.word)] = (p, ctx.meaning)
                return p
            V.RECIPES_OVERRIDE[code] = spy
            tex2html.set_lang(L)
            texparse.set_lang(L)
            refused, disagree, apart = [], [], []
            with tempfile.TemporaryDirectory() as td:
                for k, case in enumerate(json.load(open(path, encoding="utf-8"))["cases"]):
                    d, eid = _verb_case_dict(td, code, k, case)
                    word, text = case.get("word") or "", case.get("text") or ""
                    gloss, run_ = case.get("gloss") or "en", case.get("run") or "build"
                    why = case.get("why") or case.get("what") or "case %d" % k
                    exp = case.get("expect")
                    if isinstance(exp, dict) and "tex" in exp and exp["tex"] is None:
                        exp = None                  # fa writes {"tex": null} for none
                    with _DictDir(d):
                        said.clear()
                        reached, vb, used = True, None, word
                        if run_ == "lookup":
                            r = lk.look_up(code, text)
                            V.attach(r, code, text, gloss)
                            hits = [(w["word"], h) for w in r["words"]
                                    if w["word"] == word or lk._bare(w["word"], L) == lk._bare(word, L)
                                    for h in w["hits"] if h.get("entry") == eid]
                            reached = bool(hits)
                            if hits:
                                used, vb = hits[0][0], hits[0][1].get("vb")
                        else:
                            e = case["entry"]
                            vb = V.build(code, {"entry": eid, "headword": e["headword"],
                                                "pos": e.get("pos") or ""}, word, text, gloss)
                    if exp is None:
                        check(reached and vb is None, "%s: %s -- no \\vb" % (code, why),
                              "not reached" if not reached else (vb or {}).get("tex", ""))
                        continue
                    diffs = {key: [exp[key], (vb or {}).get(key)] for key in exp
                             if (vb or {}).get(key) != exp[key]}
                    check(reached and not diffs, "%s: %s (%s)" % (code, why, run_),
                          ("%r does not reach its entry" % word) if not reached
                          else json.dumps(diffs, ensure_ascii=False)[:500])
                    if not vb:
                        continue
                    try:
                        texwrite._check_voc(vb["tex"], "%s case %d" % (code, k))
                    except texwrite.Refused as e:
                        refused.append(str(e))
                    # A COMPOUND GOES IN AS ONE ENTRY: the \bw run onto the
                    # \vb with nothing between them, which is what makes the
                    # pair one verb in the line and not a verb and a noun
                    # beside it -- and the book's saver has to take it.
                    cp = vb.get("compound")
                    if cp:
                        try:
                            texwrite._check_voc(cp["tex"], "%s case %d, the compound"
                                                           % (code, k))
                        except texwrite.Refused as e:
                            refused.append(str(e))
                        if cp["tex"] != vb["tex"] + cp["bw"] or "; " in cp["tex"]:
                            apart.append("case %d: %r" % (k, cp["tex"]))
                    # the \vb read back: by texparse, and by the book reader
                    back = texparse.voc_text(vb["tex"], L)
                    shown = _as_shown(tex2html.render_voc(vb["tex"]))
                    parts, meaning = said.get((eid, lk._bare(used, L)), (None, ""))
                    book = V.compose(code, parts._replace(extras_video=(), reading=""),
                                     gloss=gloss, meaning=meaning)["plain"] if parts else None
                    if L.vb_video_bare:
                        back, shown = V.strip_marks(back, L), V.strip_marks(shown, L)
                    if book != back or shown != back:
                        disagree.append("case %d: video %r, texparse %r, reader %r"
                                        % (k, book, back, shown))
            check(not refused, "%s: texwrite accepts every \\vb its cases build" % code,
                  "; ".join(refused))
            check(not apart, "%s: a compound is ONE entry -- the \\bw runs onto the "
                             "\\vb with nothing between them" % code, "; ".join(apart))
            check(not disagree,
                  "%s: every \\vb reads back, in texparse and in the book reader, as "
                  "the video's line says it -- %s" % (code, {
                      "fa": "the colloquial present aside, which is the video's alone",
                      "ja": "the kana aside, which is the video's alone",
                      "ar": "whose Arabic the video writes bare"}.get(code, "exactly")),
                  "; ".join(disagree)[:600])
    finally:
        V.RECIPES_OVERRIDE.clear()
        V.RECIPES_OVERRIDE.update(was_over)
        tex2html.LANG, texparse._LANG = was_t2h, was_tp


def _as_shown(html_):
    """A fragment of the reader's HTML as the text a browser shows: tags off,
    entities undone, and white space run together, since the vocabulary
    line is set with `white-space: normal` -- a source that writes a space
    before \\bw, which brings its own, has two in the markup and one on the
    page."""
    import html as H
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", html_))).strip()


def test_vb_macro():
    """\\vb in the PDF, in texparse and in the reader: one macro, three readings.

    It keeps its seven arguments in every language (an optional argument, or
    a macro per language, would have had eight places learn a new shape);
    what changed is that its second and third pairs print only when their
    FORM is not blank, so a Chinese verb can give its split and no can't
    form and an Arabic verb with no masdar can leave the pair out.  The PDF
    decides with \\ifblank, and the two readers of the field must decide the
    same way, or one verb reads three ways.
    """
    section("verbs: the macro")
    import tex2html
    import texparse
    pre = open(os.path.join(LIB, "frank-preamble.tex"), encoding="utf-8").read()
    m = re.search(r"\\newcommand\{\\vb\}\[7\]\{(.*?)\n\S", pre, re.S)
    body = m.group(1) if m else ""
    check("\\ifblank{#3}{}{" in body and "\\ifblank{#5}{}{" in body,
          "the preamble's \\vb prints its second and third pairs only when their "
          "form is not blank", body[:300] or "no \\vb[7] found")
    check("\\newcommand{\\FrankSound}[1]{\\ifblank{#1}{}{" in pre
          and all("\\FrankSound{#%d}" % n in body for n in (2, 4, 6)),
          "and every sound goes through \\FrankSound, which prints the space before "
          "a sound only when there is one (a blank sound had left two)")
    check(re.search(r"\\newcommand\{\\dw\}\[2\]\{[^\n]*\\FrankSound\{#2\}", pre)
          and re.search(r"\\newcommand\{\\bw\}\[3\]\{[^\n]*\\FrankSound\{#2\}", pre),
          "so do \\dw's and \\bw's")
    check(re.search(r"\\usepackage(\[[^\]]*\])?\{[^}]*etoolbox", pre),
          "and \\ifblank has etoolbox loaded to answer it")

    # THE SAME TEST IN THE PARSER: a pair loses its label with its form, a
    # form of spaces is blank as \ifblank says, and a blank SOUND is not a
    # blank pair -- a Turkish \vb has none in any slot and prints every one.
    for code, tex, want, why in (
            ("zh", "\\vb{睡觉}{shuìjiào}{睡了觉}{shuìle jiào}{}{}{to sleep}",
             "睡觉 shuìjiào · split 睡了觉 shuìle jiào · to sleep",
             "a blank third pair is not read"),
            ("zh", "\\vb{看见}{kànjiàn}{ }{}{看不见}{kànbujiàn}{to see}",
             "看见 kànjiàn · can't 看不见 kànbujiàn · to see",
             "a form of spaces is blank"),
            ("tr", "\\vb{gelmek}{}{geliyor}{}{gelir}{}{to come}",
             "gelmek · pres. geliyor · aor. gelir · to come",
             "a blank sound leaves its pair in"),
            ("it", "\\vb{cominciare}{}{comincio}{}{cominciato}{}{to begin (aux. "
                   "\\pw{avere}/\\pw{essere})}",
             "cominciare · pres. comincio · p.p. cominciato · to begin (aux. avere/essere)",
             "a slash between two words joins them, as the PDF prints it")):
        got = texparse.voc_text(tex, code)
        check(got == want, "texparse: %s (%s)" % (why, code), repr(got))
    runs = texparse.parse_voc("\\vb{睡觉}{shuìjiào}{睡了觉}{shuìle jiào}{}{}{to sleep}", "zh")
    check(not any("can't" in t for k, t in runs if k == "txt"),
          "and the blank pair's label is not in the runs the reader draws", repr(runs))

    # --- THE READER'S OWN RENDERING joins its runs by the same rule, so the
    # page, the PDF and a video's line say one thing: tex2html.render_voc
    # had its own copy of the join and still spaced the slash.
    was_t2h, was_tp = tex2html.LANG, texparse._LANG
    off = []
    try:
        for code, tex in (
                ("it", "\\vb{cominciare}{}{comincio}{}{cominciato}{}{to begin (aux. "
                       "\\pw{avere}/\\pw{essere})}"),
                ("zh", "\\vb{睡觉}{shuìjiào}{睡了觉}{shuìle jiào}{}{}{to sleep}"),
                ("fa", "\\vb{گفتن}{goftan}{گو}{gu}{گفت}{goft}{to say}; \\textit{mi-} present"),
                ("hi", "\\vb{करना}{karnā}{कर}{kar}{किया}{kiyā}{(+\\pw{ने})}\\bw{काम}{kām}{m. work}"),
                ("ar", "\\vb{وَصَلَ}{waṣala (I)}{يَصِلُ}{yaṣilu}{وُصُول}{wuṣūl}{to arrive "
                       "(+ \\pw{إِلَى})}"),
                ("de", "\\dw{Werk}{} work \\bw{Werk}{}{work}; \\vb{fahren}{}{fuhr}{}{gefahren}"
                       "{}{to drive (er \\pw{fährt}; aux. sein)}"),
                ("ja", "\\vb{書く}{kaku}{書き}{kaki}{書いて}{kaite}{to write (godan; tr.)}")):
            tex2html.set_lang(code)
            texparse.set_lang(code)
            shown = _as_shown(tex2html.render_voc(tex))
            back = texparse.voc_text(tex, code)
            if shown != back:
                off.append("%s: reader %r, texparse %r" % (code, shown, back))
    finally:
        tex2html.LANG, texparse._LANG = was_t2h, was_tp
    check(not off, "the book reader shows a vocabulary line exactly as texparse "
                   "reads it (7 languages, a slash, a blank pair, \\bw, \\textit)",
          "; ".join(off))


# ------------------------------------------------------------------ delete
def test_delete():
    """Taking a book or a video off the shelf.

    The studio has had this since it had a library: an x on the card, a
    question, and the document is gone.  A book and a video get the same
    gesture from the same place -- and one difference, which is the content's:
    a note is a page somebody can write again, and a reading edition is weeks
    of glossing with a recording beside it that may exist nowhere else.  So
    nothing is removed.  The directory is moved to `.trash` beside the others,
    which every walker here skips, so the thing is off the shelf the moment it
    lands and still on the disk afterwards.

    That last part is what most of this checks: the trash is invisible to
    everything that counts content, and the move does not collide with
    itself.
    """
    section("delete")
    import books
    if YT_LIB not in sys.path:
        sys.path.insert(0, YT_LIB)
    import ytpages

    # --- the move, and its uniqueness rule
    for name, trash_fn, dirname in (("book", books.trash_book, ".trash"),
                                    ("video", ytpages.trash_video, ".trash")):
        with tempfile.TemporaryDirectory() as td:
            shelf = os.path.join(td, "shelf")
            os.makedirs(shelf)
            was = (books.BOOKS_DIR if name == "book" else ytpages.VIDEOS)
            if name == "book":
                books.BOOKS_DIR = shelf
            else:
                ytpages.VIDEOS = shelf
            try:
                seen = []
                for _ in range(2):
                    d = os.path.join(shelf, "thing")
                    os.makedirs(d)
                    io.open(os.path.join(d, "keep.txt"), "w").write("x")
                    seen.append(trash_fn(d))
                    check(not os.path.exists(d),
                          "%s: the directory is off the shelf" % name)
                check(len(set(seen)) == 2,
                      "%s: two deletions in one second do not collide (%s)"
                      % (name, ", ".join(os.path.basename(x) for x in seen)))
                check(all(os.path.isfile(os.path.join(x, "keep.txt")) for x in seen),
                      "%s: and nothing in it was lost" % name)
                check(all(os.path.basename(os.path.dirname(x)) == dirname
                          for x in seen),
                      "%s: it went to %s/" % (name, dirname))
            finally:
                if name == "book":
                    books.BOOKS_DIR = was
                else:
                    ytpages.VIDEOS = was

    # --- and the trash is not a shelf
    with tempfile.TemporaryDirectory() as td:
        for rel in ("persian/keeper", ".trash/gone-20260101-000000",
                    ".trash/persian/also-gone"):
            d = os.path.join(td, rel)
            os.makedirs(d)
            io.open(os.path.join(d, "book.json"), "w", encoding="utf-8").write(
                '{"slug": "x", "language": "fa"}')
        got = [os.path.relpath(x, td) for x in books.book_dirs(td)]
        check(got == [os.path.join("persian", "keeper")],
              "a book in the trash is not a book: the walker skips a dot "
              "directory at either level", repr(got))

    # --- the x is on both cards, and carries where to post and what to say
    import make_index
    fb = next(iter(fixture_books()), None)
    if fb is None:
        skip("no fixture edition: the book's card is not drawn")
    else:
        html = make_index.card(fb)
        check('class="card-del"' in html and '/__delete"' in html,
              "a book's card carries the x and the address to post to",
              html[:300])
        check('data-what="' in html,
              "and the name to put in the question it asks")

    vfx = sorted(glob.glob(os.path.join(FIX, "videos", "*", "*", "video.json")))
    if not vfx:
        skip("no fixture video: the video's card is not drawn")
    else:
        d = os.path.dirname(vfx[0])
        m = json.load(io.open(vfx[0], encoding="utf-8"))
        m["_dir"] = "%s/%s" % (os.path.basename(os.path.dirname(d)),
                               os.path.basename(d))
        m["_lang"] = m.get("language") or "fa"
        m["_segments"] = m["_glossable"] = m["_glossed"] = 1
        m["_blank"] = 0
        html = ytpages.video_card(m)
        check('class="card-del"' in html and "/api/delete" in html,
              "a video's card carries the x and the address to post to",
              html[:300])
        # read the attribute the way a browser will, rather than trusting
        # one spelling of the escape: the body is JSON inside an HTML
        # attribute, and what matters is what json.loads gets at the far end
        import html as htmlesc
        vid = m["_dir"].rsplit("/", 1)[-1]
        body = re.search(r"data-body='([^']*)'", html)
        got = json.loads(htmlesc.unescape(body.group(1))) if body else {}
        check(got == {"video": vid},
              "and names, in the body it posts, the video the route will "
              "look up", repr(got))

    # one gesture, drawn twice: the page script that answers it is shared, so
    # neither door can grow a delete the other has not got
    js = open(os.path.join(LIB, "parseh.js"), encoding="utf-8").read()
    check("function cardDelete" in js and "[data-del]" in js,
          "one handler in lib/parseh.js answers both cards")
    check("confirm(" in js and "not\\ndeleted" not in js,
          "and asks before it does anything")


# ------------------------------------------------------------------ anki
def test_anki():
    section("anki")
    rc, out = run([sys.executable, os.path.join(FIX, "anki", "roundtrip.py")], cwd=ROOT, timeout=300)
    check(rc == 0, "anki round trip (one fixture deck per language, and the store's layout)",
          out[-1600:])


def _get_ok(port, path, what):
    """GET one path and check it answered at all."""
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        c.request("GET", path)
        r = c.getresponse()
        r.read()
        check(r.status == 200, "GET %s -> %s" % (path, what), str(r.status))
    except Exception as e:
        bad("GET %s" % path, repr(e))


def _get_refused(port, path, why):
    """GET one path and check it was refused, with a sentence."""
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        c.request("GET", path)
        r = c.getresponse()
        body = r.read().decode("utf-8", "replace")
        check(r.status == 404 and "never built" in body,
              "GET %s -> refused (%s)" % (path, why), "%d %s" % (r.status, body[:160]))
    except Exception as e:
        bad("GET %s" % path, repr(e))


def _post_json(port, path, body, what, want=200):
    """POST one JSON body and check the route answered as it should.

    `want` is the status expected: 200 means the route did the thing and
    said so, anything else means it refused, and a refusal has to be the
    refusal it intended rather than a traceback with a number on it -- so
    an `ok` in the body is required for 200 and forbidden otherwise.
    """
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        data = json.dumps(body).encode("utf-8")
        c.request("POST", path, data, {"Content-Type": "application/json",
                                       "Content-Length": str(len(data))})
        r = c.getresponse()
        j = json.loads(r.read().decode("utf-8"))
        check(r.status == want and bool(j.get("ok")) == (want == 200),
              "POST %s -> %s answers" % (path, what),
              "%d %s" % (r.status, json.dumps(j)[:300]))
        return j
    except Exception as e:
        bad("POST %s" % path, repr(e))
        return {}


def _one_answer(port, method, path, raw, ctype="application/json"):
    """One request on a raw keep-alive socket: (status, body, whatever bytes
    came after the answer).  Only a raw socket can see a second answer to one
    request: http.client reads each response through a buffer of its own and
    drops what follows it."""
    import socket
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    try:
        s.sendall(("%s %s HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: %s\r\n"
                   "Content-Length: %d\r\n\r\n" % (method, path, ctype, len(raw))).encode("ascii") + raw)
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        status, length = int(lines[0].split()[1]), 0
        for line in lines[1:]:
            key, _, value = line.partition(":")
            if key.strip().lower() == "content-length":
                length = int(value.strip())
        while len(rest) < length:
            chunk = s.recv(65536)
            if not chunk:
                break
            rest += chunk
        body, extra = rest[:length], rest[length:]
        s.settimeout(0.5)               # the connection stays open: wait a moment
        try:
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                extra += chunk
        except socket.timeout:
            pass
        return status, body, extra
    finally:
        s.close()


# ------------------------------------------------------------------ server
def _removable(d):
    """Whether a path a test parked may be deleted: a book or a video on one of
    the toolbox's own shelves, or in a trash beside one -- never a shelf, the
    shelves, or anything else.  Once a delete route's answer went missing, its
    trash path was joined from nothing onto the repository root, and the
    cleanup below removed the whole working copy; every rmtree of a parked
    path asks this first."""
    if not isinstance(d, str) or not d.strip():
        return False
    real = os.path.realpath(d)
    for shelves in (os.path.join(ROOT, "books"), os.path.join(YT, "videos")):
        rel = os.path.relpath(real, os.path.realpath(shelves))
        parts = rel.split(os.sep)
        if rel == "." or parts[0] == "..":
            continue
        # <language>/<item> at the least, and never a shelf's own marker
        if len(parts) >= 2 and parts[-1] not in (".trash", ".gitkeep"):
            return True
    return False


def _trash_path(j):
    """Where a delete route says it put a book or a video, or "" when it says
    nothing -- which must never become the repository root."""
    t = (j or {}).get("trash")
    return os.path.join(ROOT, t) if isinstance(t, str) and t.strip() else ""


# THE SERVER'S OWN MEMORIES GO TO A FOLDER OF THE TEST'S (TO-DO §2.25).
# serve.py started as it is starts on the owner's config/, and the sweep asks
# it for /__shell -- which hashes every file of the app and remembers each one
# in config/digests.json, so a run after any file of lib/ had changed wrote
# there.  Started through runpy instead, with the four stores pointed at a
# temporary folder first, the way tests/decks_harness.py and the harnesses
# beside it start it: the same main(), the same arguments, none of his files.
SERVE_BOOT = """
import os, runpy, sys
sys.path.insert(0, os.path.join(os.getcwd(), "lib"))
import network, offline, prefs
config = sys.argv[1]
prefs.STORE = os.path.join(config, "prefs.json")
network.STORE = os.path.join(config, "network.json")
import latexthemes, latexdraw, texpackages
latexthemes.STORE = os.path.join(config, "latex.json")
# and the prompts a person wrote (lib/prompts.py)
import prompts
prompts.STORE = os.path.join(config, "prompts.json")
latexdraw.DRAWN = os.path.join(os.path.dirname(config), "latex-drawn")
texpackages.TREE = os.path.join(os.path.dirname(config), "texmf")
sys.path.insert(0, os.path.join(os.getcwd(), "tests"))
import texmf_fixture  # noqa: E402  what the themes add to the base, as if Parseh had got it
texmf_fixture.pretend_got(texpackages, latexthemes)
offline.DIGESTS = os.path.join(config, "digests.json")
offline.WHERES = os.path.join(config, "wheres.json")
# and the languages added on this machine (lib/newlang.py keeps a copy of the path) and the speech settings
import languages, newlang, pathlib, speechconfig
languages.PERSONAL = newlang.PERSONAL = os.path.join(config, "languages.json")
speechconfig.CONFIG = pathlib.Path(config) / "speech.json"
sys.argv = ["serve.py"] + sys.argv[2:]
runpy.run_path("serve.py", run_name="__main__")
"""


def test_server():
    section("server")
    # A PORT NOBODY HOLDS, asked of the system.  The fixed 8840 + pid % 50 was
    # once held by another serve.py: this test's own server could not bind
    # it, every request went to the other one, and what came back sent the
    # cleanup after the working copy.  The server that answers is checked to
    # be this test's own as well.
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)
    config = tempfile.mkdtemp(prefix="parseh-smoke-config-")
    proc = subprocess.Popen([sys.executable, "-u", "-c", SERVE_BOOT, config,
                             "--http", "--local", str(port)],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    try:
        up = False
        for _ in range(80):
            try:
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                c.request("GET", "/")
                r = c.getresponse()
                r.read()
                up = r.status == 200
                break
            except OSError:
                time.sleep(0.25)
        if not check(up, "serve.py answers on port %d" % port):
            return
        if not check(proc.poll() is None,
                     "and the server answering is the one this test started",
                     "serve.py exited: something else holds port %d" % port):
            return
        studio = load_studio()
        import languages
        doc_ids = [d["id"] for d in studio.store.list_docs()]
        pages = ["/", "/lib/langs.css", "/lib/parseh.css", "/lib/mobile.css", "/lib/parseh.js", "/lib/llm.js", "/lib/llmrow.js", "/lib/decomposition.js", "/lib/decomposition.css",
                 "/settings/reading-help/", "/lib/fonts/NotoNaskhArabic.woff2",
                 "/books/", "/books/add/",
                 "/youtube/", "/youtube/add/",
                 "/studio/", "/studio/static/langs.css", "/studio/api/docs", "/studio/prompt", "/studio/new",
                 # the exercise decks: read-only, like everything in this sweep
                 # (neither creates exercises/ nor writes into it)
                 "/exercises/", "/exercises/api/decks",
                 "/anki/decks", "/anki/decks?lang=zz",
                 # the way in, kept: the one list saying what the installed app
                 # is made of (lib/offline.shell, read by lib/sw.js at install).
                 # Walked here because an app whose own shell answers 404 stalls
                 # on its splash and nothing else in this sweep would say so.
                 "/__shell",
                 "/anki/sync/"] \
                + ["/anki/decks?lang=%s" % c for c in languages.CODES] \
                + ["/studio/doc/%s" % i for i in doc_ids] \
                + ["/studio/doc/%s/edit" % i for i in doc_ids]
        # the pages that need a book or a video are asked for only when there
        # is one to ask about: both shelves ship empty
        import books as shelf
        import ytpages
        for b in shelf.all_books():
            if os.path.isdir(b.reader_dir):
                pages.append("/books/%s/reader/" % b.rel_from_books())
        for v in sorted(glob.glob(os.path.join(YT, "videos", "*", "*", "video.json")))[:1]:
            meta = json.load(open(v, encoding="utf-8"))
            vid = os.path.basename(os.path.dirname(v))
            folder = os.path.basename(os.path.dirname(os.path.dirname(v)))
            pages += ["/youtube/v/%s/" % vid,
                      "/youtube/videos/%s/%s/annotations.json" % (folder, vid)]
            if meta.get("channel"):
                pages.append("/youtube/c/%s/" % ytpages.channel_slug(meta["channel"]))
        for p in pages:
            try:
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                c.request("GET", p)
                r = c.getresponse()
                body = r.read()
                check(r.status == 200, "GET %s -> %d" % (p, r.status))
                if p == "/":
                    check(b"parseh-langs" in body, "the hub has the chip row")
                    check(b'href="/exercises/"' in body, "the hub has a door to the exercise decks")
                    check(body.count(b"data-counts=") >= 4,
                          "and each door's count carries its languages, for "
                          "the chips to rewrite it")
                    check(not re.search(rb'class="tag" data-lang="[a-z-]+">[A-Z][a-z]+:', body),
                          "and no door lists a tag per language beside its count")
                    check(b"/guide.pdf" not in body and b'href="/guide/"' in body
                          and b"serve.sh" not in body,
                          "its guide button opens /guide/, and nothing on it asks for a terminal")
                    # docs/mobile.md: the one page carries both layouts and
                    # the switch between them, in each layout's bar
                    check(body.count(b'data-parseh-mode="mobile"') == 2
                          and b'data-layout="mobile"' in body and b"data-mobile-page" in body
                          and b'href="/lib/mobile.css"' in body,
                          "the hub has its mobile layout and the Browser | Mobile switch")
                if p == "/__shell":
                    j = json.loads(body.decode("utf-8"))
                    check(j.get("ok") is True and j.get("pages") and j.get("files"),
                          "/__shell says what the app is made of: %d pages, %d apis, %d files"
                          % (len(j.get("pages") or []), len(j.get("apis") or []),
                             len(j.get("files") or [])), json.dumps(j)[:200])
                    check("/?mode=mobile" in (j.get("pages") or [])
                          and "/" in (j.get("pages") or []),
                          "the hub at both its addresses, the app's start address among them")
                if p == "/exercises/api/decks":
                    j = json.loads(body.decode("utf-8"))
                    check(j.get("ok") is True and isinstance(j.get("decks"), list),
                          "/exercises/api/decks answers ok with a list (%d decks)"
                          % len(j.get("decks") or []), json.dumps(j)[:200])
                if p == "/studio/api/docs":
                    j = json.loads(body.decode("utf-8"))
                    if j["docs"]:
                        check(all(d.get("target") for d in j["docs"]),
                              "/studio/api/docs items carry target (%d of them)" % len(j["docs"]))
                    else:
                        skip("the library is empty: no document or editor page was asked for")
            except Exception as e:
                bad("GET %s" % p, repr(e))
        # a Japanese card preview through the shared store
        card = {"card": {"lang": "ja", "kind": "vocab", "fa": "漢字", "kana": "かんじ", "tr": "kanji",
                         "en": "kanji", "context": "漢字を書く", "notes": "", "bidirectional": True,
                         "tags": ["japanese-youtube"], "source": {"label": "smoke", "url": ""}},
                "night": False}
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            body = json.dumps(card).encode("utf-8")
            c.request("POST", "/anki/preview", body, {"Content-Type": "application/json",
                                                     "Content-Length": str(len(body))})
            r = c.getresponse()
            j = json.loads(r.read().decode("utf-8"))
            check(r.status == 200 and j.get("ok") and "かんじ" in j.get("html", ""),
                  "POST /anki/preview renders a Japanese card with its kana", json.dumps(j)[:300])
        except Exception as e:
            bad("POST /anki/preview", repr(e))
        # a Japanese studio preview
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            body = json.dumps({"markdown": "---\ntitle: t\ntarget: ja\n---\n\n## 早い | はやい | hayai | etym | = *fast*\n\n"
                               "[早い]{kana:はやい translit:hayai} = *fast*.\n\n[\n春の夜⏎\n月が出る\n]{tl vertical}\n"}).encode("utf-8")
            c.request("POST", "/studio/api/preview", body, {"Content-Type": "application/json",
                                                           "Content-Length": str(len(body))})
            r = c.getresponse()
            j = json.loads(r.read().decode("utf-8"))
            h = (j.get("doc") or {}).get("html", "")
            check(r.status == 200 and j.get("ok") and "voce-kana" in h and "tl-vertical" in h,
                  "POST /studio/api/preview renders a Japanese lemma and a vertical block", json.dumps(j)[:300])
        except Exception as e:
            bad("POST /studio/api/preview", repr(e))

        # Downloading the documents the library shows, with none named: a
        # refusal in words, not a traceback and not an empty zip.
        _post_json(port, "/studio/api/download", {},
                   "the studio's download of the shown documents, with no ids", want=400)
        # The exercise decks' refusals, through serve.py's mount.  None of
        # them writes: an unknown deck is refused before its lock is taken,
        # and a body that is not a zip before exercises/ is looked at.
        nodeck = "/exercises/api/decks/%s/no-such-deck-smoke" % languages.get("fa").folder
        _post_json(port, nodeck + "/review", {"item": "000000000000", "rating": "good"},
                   "reviewing in a deck that is not there", want=404)
        _post_json(port, "/exercises/api/import", {},
                   "importing something that is not a deck export", want=400)
        # A picture uploaded into a deck: a body that is not a picture is
        # refused before the deck is looked at.  "+ Deck" from notes that are
        # on no shelf: refused before anything is read.  Neither writes --
        # the store's tree is the same afterwards.
        import urllib.parse
        store_root = os.path.join(ROOT, "exercises")

        def store_tree():
            seen = set()
            for dirpath, dirnames, filenames in os.walk(store_root):
                for n in dirnames + filenames:
                    seen.add(os.path.relpath(os.path.join(dirpath, n), store_root))
            return seen
        before = store_tree()
        try:
            status, body, extra = _one_answer(port, "POST", nodeck + "/images?name=smoke.png",
                                              b"not a picture", "application/octet-stream")
            j = json.loads(body.decode("utf-8"))
            check(status == 400 and j.get("ok") is False and bool(j.get("error")) and not extra,
                  "POST a deck picture whose body is not a picture -> one answer: 400, ok false",
                  "%d %s, then %r" % (status, json.dumps(j)[:160], extra[:120]))
        except Exception as e:
            bad("POST %s/images" % nodeck, repr(e))
        copy = {"doc_id": "no-such-note-smoke", "ordinal": 1, "subtype": "flashcard"}
        _post_json(port, nodeck + "/copy",
                   dict(copy, source="/books/%s/no-such-book-smoke/notes" % languages.get("fa").folder),
                   "copying from notes that are on no shelf", want=400)
        # a prefix that IS some content's notes gets past that gate (serve.py
        # registered the lookup), and is refused for the deck that is missing
        shelved = ["/books/%s/notes" % urllib.parse.quote(b.rel_from_books())
                   for b in shelf.all_books()][:1]
        shelved += ["/youtube/v/%s/notes" % os.path.basename(os.path.dirname(v))
                    for v in sorted(glob.glob(os.path.join(YT, "videos", "*", "*", "video.json")))][:1]
        for prefix in shelved:
            _post_json(port, nodeck + "/copy", dict(copy, source=prefix),
                       "copying from the notes at %s: they are found, the deck is not" % prefix,
                       want=404)
        if not shelved:
            skip("no book or video on the shelves: serve.py's notes lookup was not asked about")
        after = store_tree()
        check(after == before, "the deck refusals wrote nothing into exercises/",
              repr(sorted(after ^ before))[:300])
        # One answer per request, whatever the body: serve.py's own
        # _json_body answers an unusable body by itself, and a deck route
        # that went on after it would write a second answer into the
        # keep-alive connection -- which the NEXT request on it would read.
        # All refused before anything is written.
        for raw in (b"[]", b"", b"{nope"):
            try:
                status, body, extra = _one_answer(port, "POST", "/exercises/api/decks", raw)
                j = json.loads(body.decode("utf-8"))
                check(status == 400 and j.get("ok") is False and not extra,
                      "POST /exercises/api/decks with the body %r -> one answer: 400, ok false" % raw,
                      "%d %s, then %r" % (status, json.dumps(j)[:160], extra[:120]))
            except Exception as e:
                bad("POST /exercises/api/decks with the body %r" % raw, repr(e))
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request("GET", "/exercises/deck/%s/no-such-deck-smoke" % languages.get("fa").folder)
            r = c.getresponse()
            body = r.read().decode("utf-8", "replace")
            check(r.status == 404 and "/studio/static/app.css" in body,
                  "GET a deck page that is not there -> the studio's 404 page",
                  "%d %s" % (r.status, body[:160]))
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request("GET", "/exercises")
            r = c.getresponse()
            r.read()
            check(r.status in (301, 302) and r.getheader("Location") == "/exercises/",
                  "GET /exercises redirects to /exercises/", str(r.status))
        except Exception as e:
            bad("GET /exercises/deck/...", repr(e))

        # The divide routes over HTTP.  Only `preview`, which writes nothing
        # -- what the operations themselves do is proved in test_divide,
        # against copies -- but the route has to be reachable, and the gate
        # that decides which POSTs reach a reader at all is a separate list
        # from the one that answers them.  A fixture is parked for the
        # seconds it takes, exactly as the player pages are given one.
        parked = []
        try:
            fb = next(iter(fixture_books()), None)
            if fb is not None:
                dst = os.path.join(ROOT, "books", fb.lang.folder, fb.slug)
                if not os.path.exists(dst):
                    shutil.copytree(fb.dir, dst, ignore=shutil.ignore_patterns(
                        "reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
                    parked.append(dst)
                    _post_json(port, "/books/%s/%s/reader/__divide/chunk"
                               % (fb.lang.folder, fb.slug),
                               {"action": "preview", "index": 0},
                               "the reader's divide route")
                    # --- MORE TEXT ONTO THE END OF IT.  Addressed by the
                    # book's own path, the way __delete is, so no slug ever
                    # travels in a body.
                    import draft as _draft
                    where = "/books/%s/%s/__append" % (fb.lang.folder, fb.slug)
                    had = _draft.chapters_of(dst)
                    j = _post_json(port, where,
                                   {"text": "Alef bet gim.\n\nDal he vav.",
                                    "how": "sentence", "chapter": "new"},
                                   "the route that adds text to a book")
                    check((j or {}).get("chapter") == had[-1] + 1
                          and (j or {}).get("paragraphs") == 2,
                          "which lands as the next chapter, with the counts of "
                          "what was added", json.dumps(j)[:200])
                    check(os.path.isfile(os.path.join(
                              dst, "ch%d.tex" % ((j or {}).get("chapter") or 0))),
                          "and the chapter is on disk")
                    check("\\input{ch%d.tex}" % ((j or {}).get("chapter") or 0)
                          in open(os.path.join(dst, "main.tex"),
                                  encoding="utf-8").read(),
                          "and named in main.tex, which is the only place the "
                          "reading order is written down")
                    j = _post_json(port, where,
                                   {"text": "Zayin het tet.", "chapter": "last"},
                                   "and onto the end of the last chapter")
                    check((j or {}).get("where") == "last"
                          and _draft.chapters_of(dst) == had + [had[-1] + 1],
                          "which makes no new chapter",
                          json.dumps(j)[:160])
                    _post_json(port, where, {"text": "x", "chapter": "sideways"},
                               "a place to put it that does not exist",
                               want=400)
                    _post_json(port, "/books/%s/no-such-book/__append"
                               % fb.lang.folder, {"text": "x"},
                               "adding to a book that is not there", want=404)
                    c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
                    c.request("GET", where)
                    st = c.getresponse()
                    st.read()
                    check(st.status == 405,
                          "and the append route is POST and nothing else",
                          "GET -> %d" % st.status)
                    # --- THE BOOK'S OWN METADATA: title, author, the library
                    # card's blurb -- book.json, not a chunk.  Four of the
                    # fields are ALSO main.tex's own \newcommand lines
                    # (bookmeta's docstring says why), so the edit is
                    # checked against both files, and a value that would
                    # break main.tex refuses the whole edit rather than
                    # writing book.json alone and leaving the two apart.
                    where_meta = "/books/%s/%s/reader/__edit/meta" % (fb.lang.folder, fb.slug)
                    main_before = open(os.path.join(dst, "main.tex"),
                                       encoding="utf-8").read()
                    j = _post_json(port, where_meta,
                                   {"fields": {"title_latin": "A smoke-tested title",
                                               "blurb": "written by the smoke test"}},
                                   "the book's metadata edit route")
                    check((j or {}).get("meta", {}).get("title_latin")
                          == "A smoke-tested title"
                          and (j or {}).get("meta", {}).get("blurb")
                          == "written by the smoke test",
                          "which rewrites book.json", json.dumps(j)[:200])
                    main_after = open(os.path.join(dst, "main.tex"),
                                      encoding="utf-8").read()
                    check("\\newcommand{\\BookTitleLatin}{A smoke-tested title}"
                          in main_after and main_after != main_before,
                          "and main.tex's own \\newcommand line along with it")
                    _post_json(port, where_meta, {"fields": {"title": "bad & title"}},
                               "a title main.tex cannot hold", want=400)
                    _post_json(port, where_meta, {"fields": {"slug": "nope"}},
                               "a field that is not book.json's to edit", want=400)
                    # "reorders" (kanbun): a switch, true or absent, so a
                    # text read out of its written order is marked from the
                    # reader and not by hand
                    bj = os.path.join(dst, "book.json")
                    _post_json(port, where_meta, {"fields": {"reorders": True}},
                               "marking the book as read out of its written order")
                    check(json.load(open(bj, encoding="utf-8")).get("reorders") is True,
                          "which writes \"reorders\": true into book.json")
                    _post_json(port, where_meta, {"fields": {"reorders": False}},
                               "and unmarking it")
                    check("reorders" not in json.load(open(bj, encoding="utf-8")),
                          "which takes the key out again rather than write false")
                    _post_json(port, where_meta, {"fields": {"reorders": "yes"}},
                               "a reorders that is not true or false", want=400)
                    # the studio, mounted over this book's own markdown/
                    base = "/books/%s/%s/notes" % (fb.lang.folder, fb.slug)
                    j = _post_json(port, base + "/api/marks",
                                   {"side": "after", "kind": "sub",
                                    "at": "1.1-x", "target": fb.lang.code},
                                   "a note written into a seam")
                    nid = (j.get("note") or {}).get("id") or ""
                    for path, what in (
                            (base + "/api/marks", "the marks a page draws"),
                            (base + "/doc/" + nid, "the studio's own page for a note"),
                            (base + "/doc/" + nid + "/edit", "the studio's own editor")):
                        _get_ok(port, path, what)
                    # WHAT THE HOVER CARD SHOWS comes down with the marks:
                    # each note's first lines as plain text, its front
                    # matter and its anchor left out -- both readers put it
                    # in with textContent and ask the server nothing more
                    try:
                        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
                        c.request("GET", base + "/api/marks")
                        marks = json.loads(c.getresponse().read().decode("utf-8"))
                        mine = next((n for n in marks.get("notes") or []
                                     if n.get("id") == nid), {})
                        ex = mine.get("excerpt")
                        check(isinstance(ex, str) and ex.startswith("Written by hand")
                              and "anchor" not in ex and "title:" not in ex,
                              "GET %s/api/marks carries each note's excerpt, and "
                              "no front matter in it" % base, repr(ex))
                    except Exception as e:
                        bad("GET %s/api/marks" % base, repr(e))
                    # and the three doors a note does not have
                    for path in (base + "/pdf/" + nid,
                                 base + "/download/" + nid + "/tex",
                                 base + "/download/" + nid + "/pdf"):
                        _get_refused(port, path, "a note is never built")
                    _get_ok(port, base + "/download/" + nid + "/md",
                            "a note comes away as its own markdown")
                    # Every route the studio has is served under this prefix,
                    # so every route has to be asked WHICH library it is in.
                    # Two read the module global instead and answered about
                    # the studio's own: the Backup button on a book's notes
                    # page zipped the studio's library and none of the notes,
                    # and the status line named the studio's path beside the
                    # notes' own count.
                    try:
                        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
                        c.request("GET", base + "/api/export")
                        r = c.getresponse()
                        blob = r.read()
                        with zipfile.ZipFile(io.BytesIO(blob)) as z:
                            names = z.namelist()
                        mine = [n for n in names if nid in n]
                        check(r.status == 200 and mine and
                              not [n for n in names if "studio" in n],
                              "the notes' own backup holds the notes",
                              "%d %s" % (r.status, names[:6]))
                    except Exception as e:
                        bad("GET %s/api/export" % base, repr(e))
                    try:
                        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
                        c.request("GET", base + "/api/status")
                        r = c.getresponse()
                        st = json.loads(r.read().decode("utf-8"))
                        check(st.get("library", "").replace("\\", "/")
                              .endswith("/%s/%s/markdown" % (fb.lang.folder, fb.slug)),
                              "the notes' status names the notes' own library",
                              json.dumps(st)[:220])
                    except Exception as e:
                        bad("GET %s/api/status" % base, repr(e))
                    _get_ok(port, "/studio/api/export",
                            "and the studio's own backup still answers")
                    # and then take it off the shelf, which is the last
                    # thing anyone does to a book, so it goes last here
                    j = _post_json(port, "/books/%s/%s/__delete"
                                   % (fb.lang.folder, fb.slug), {},
                                   "the route that takes a book off the shelf")
                    gone = _trash_path(j)
                    check(not os.path.exists(dst) and os.path.isdir(gone),
                          "the book is off the shelf and in the trash, whole",
                          json.dumps(j)[:200])
                    check(os.path.isfile(os.path.join(gone, "book.json")),
                          "with its book.json still in it: nothing was deleted")
                    if gone:
                        parked.append(gone)
            fv = next(iter(sorted(glob.glob(os.path.join(
                FIX, "videos", "*", "*", "video.json")))), None)
            if fv is not None:
                meta = json.load(open(fv, encoding="utf-8"))
                L = languages.get_or_default(meta.get("language"))
                vid = os.path.basename(os.path.dirname(fv))
                dst = os.path.join(YT, "videos", L.folder, vid)
                if not os.path.exists(dst):
                    shutil.copytree(os.path.dirname(fv), dst)
                    parked.append(dst)
                    ann = json.load(open(os.path.join(dst, "annotations.json"),
                                         encoding="utf-8"))
                    si = next((i for i, sg in enumerate(ann["segments"])
                               if sg.get("chunks")), 0)
                    _post_json(port, "/youtube/api/divide",
                               {"action": "preview", "video": vid,
                                "segment": si, "chunk": 0},
                               "the player's divide route")
                    # --- THE NOTE a model leaves on a phrase is the person's to
                    # edit: written through the ✎ form's own route, answered with
                    # the chunk as it now stands, and taken off by an empty box
                    where_ann = os.path.join(dst, "annotations.json")
                    edit = {"video": vid, "segment": si, "chunk": 0}
                    j = _post_json(port, "/youtube/api/edit",
                                   dict(edit, fields={"note": "  an aside of mine  "}),
                                   "the player's edit route, a note written")
                    on_disk = json.load(open(where_ann, encoding="utf-8")
                                        )["segments"][si]["chunks"][0].get("note")
                    check((j.get("chunk_now") or {}).get("note") == "an aside of mine"
                          == on_disk,
                          "which answers with the note trimmed, and the file says "
                          "the same", repr((j.get("chunk_now"), on_disk)))
                    _post_json(port, "/youtube/api/edit",
                               dict(edit, fields={"note": ""}),
                               "and an emptied box")
                    check("note" not in json.load(open(where_ann, encoding="utf-8")
                                                  )["segments"][si]["chunks"][0],
                          "which takes the key out of the file")
                    _post_json(port, "/youtube/api/edit",
                               dict(edit, fields={"plain": True}),
                               "a page setting plain, which stays the author's",
                               want=400)
                    # --- THE VIDEO'S OWN METADATA: title, channel, level,
                    # blurb -- video.json, not a chunk.  The concrete case
                    # this route exists for: api_add's YouTube lookup got
                    # the title or the channel wrong (ytpages.edit_meta's
                    # docstring says so), and there was no way to fix it
                    # short of hand-editing the file.  Unlike a book there
                    # is nothing to rebuild, so the answer is checked
                    # straight against the file the route just wrote.
                    j = _post_json(port, "/youtube/api/editmeta",
                                   {"video": vid,
                                    "fields": {"title": "A smoke-tested title",
                                              "channel": "A smoke-tested channel"}},
                                   "the video's metadata edit route")
                    check((j or {}).get("meta", {}).get("title") == "A smoke-tested title"
                          and (j or {}).get("meta", {}).get("channel")
                          == "A smoke-tested channel",
                          "which rewrites video.json", json.dumps(j)[:200])
                    on_disk = json.load(open(os.path.join(dst, "video.json"),
                                             encoding="utf-8"))
                    check(on_disk.get("title") == "A smoke-tested title",
                          "and the file on disk agrees, with nothing to rebuild")
                    _post_json(port, "/youtube/api/editmeta",
                               {"video": vid, "fields": {"level": "expert"}},
                               "a level that is not one of the three", want=400)
                    _post_json(port, "/youtube/api/editmeta",
                               {"video": vid, "fields": {"url": "https://evil.example"}},
                               "a field that is not video.json's to edit", want=400)
                    # "reorders" (kanbun), which api_add never writes: marked
                    # from the player's sheet, true or absent
                    vj = os.path.join(dst, "video.json")
                    _post_json(port, "/youtube/api/editmeta",
                               {"video": vid, "fields": {"reorders": True}},
                               "marking the video as read out of its written order")
                    check(json.load(open(vj, encoding="utf-8")).get("reorders") is True,
                          "which writes \"reorders\": true into video.json")
                    _post_json(port, "/youtube/api/editmeta",
                               {"video": vid, "fields": {"reorders": False}},
                               "and unmarking it")
                    check("reorders" not in json.load(open(vj, encoding="utf-8")),
                          "which takes the key out again rather than write false")
                    _post_json(port, "/youtube/api/editmeta",
                               {"video": vid, "fields": {"reorders": 1}},
                               "a reorders that is not true or false", want=400)
                    j = _post_json(port, "/youtube/api/delete", {"video": vid},
                                   "the route that takes a video off the shelf")
                    gone = _trash_path(j)
                    check(not os.path.exists(dst) and os.path.isdir(gone),
                          "the video is off the shelf and in the trash, whole",
                          json.dumps(j)[:200])
                    check(os.path.isfile(os.path.join(gone, "video.json")),
                          "with its video.json still in it: nothing was deleted")
                    if gone:
                        parked.append(gone)
                    # and a video nobody has is not a 500
                    _post_json(port, "/youtube/api/delete",
                               {"video": "nOtAvIdEoAtAll"},
                               "asking to delete a video that is not there",
                               want=404)

            # --- A VERB, OFFERED AS A VERB, down the route the reader asks.
            # The book reader posts a chunk and its sentence to its own
            # __lookup, and the server hands every hit to lib/verbs on the
            # way back -- so a verb hit arrives carrying the \vb the sources
            # column puts into the vocabulary line.  Asked of the Persian
            # fixture's own verb chunks, parked for the seconds it takes: the
            # \vb that comes back must be for a verb the book itself glosses
            # in that chunk.
            import lookup as _lk
            import texparse as _T
            fab = next((b for b in fixture_books() if b.lang.code == "fa"), None)
            vdst = os.path.join(ROOT, "books", fab.lang.folder, fab.slug) if fab else ""
            if fab is None:
                skip("no Persian fixture edition: the \\vb route is not asked")
            elif not _lk.available("fa"):
                skip("no dict/fa.db: the \\vb route is not asked")
            elif os.path.exists(vdst):
                skip("books/%s/%s is on the shelf already: the \\vb route is not "
                     "asked of it" % (fab.lang.folder, fab.slug))
            else:
                shutil.copytree(fab.dir, vdst, ignore=shutil.ignore_patterns(
                    "reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
                parked.append(vdst)
                key = lambda s: fab.lang.strip(s).replace("\u200c", "")
                found, asked = None, []
                for ch in _T.parse_book(fab.main, fab.lang):
                    for s in ch.subs:
                        for c in s.chunks:
                            want = {key(x) for x in re.findall(r"\\vb\{([^{}]*)\}", c.voc)}
                            if not want or found or len(asked) >= 8:
                                continue
                            body = json.dumps({"text": c.fa, "sentence": " ".join(
                                x.fa for x in s.chunks)}).encode("utf-8")
                            h = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
                            h.request("POST", "/books/%s/%s/reader/__lookup"
                                      % (fab.lang.folder, fab.slug), body,
                                      {"Content-Type": "application/json",
                                       "Content-Length": str(len(body))})
                            j = json.loads(h.getresponse().read().decode("utf-8"))
                            vbs = [x["vb"] for w in j.get("words") or []
                                   for x in w.get("hits") or [] if x.get("vb")]
                            asked.append("%s: %s" % (c.fa, [v.get("lemma") for v in vbs]))
                            found = next((v for v in vbs if key(v.get("lemma") or "") in want),
                                         None)
                check(found and found["tex"].startswith("\\vb{")
                      and found.get("plain") and found.get("line") is not None,
                      "POST __lookup on a Persian verb chunk and its sentence gives "
                      "the verb's hit its \\vb, the verb the book glosses there (%s)"
                      % ((found or {}).get("lemma") or "none"), "; ".join(asked)[:400])

            # --- A VIDEO THAT IS A FILE ON THIS MACHINE, made the way the
            # add page makes one: a path and a subtitle file, no YouTube.
            # The film is not decoded here -- that it plays is a thing for a
            # browser to say -- but that it is linked in, carried by the
            # download and left out on request is exactly what this route
            # and that button promise.
            with tempfile.TemporaryDirectory() as td:
                mp4 = os.path.join(td, "a lesson.mp4")
                blob = os.urandom(256 * 1024)
                with open(mp4, "wb") as f:
                    f.write(blob)
                srt = ("1\n00:00:06,000 --> 00:00:09,000\nسلام، ببخشید سیب چند است\n\n"
                       "2\n00:00:12,000 --> 00:00:15,000\nکیلویی سی هزار تومان\n")
                j = _post_json(port, "/youtube/api/local",
                               {"path": mp4, "transcript": srt, "lang": "fa",
                                "title": "a lesson"},
                               "the route that makes a video out of a film here")
                vid = (j or {}).get("id") or ""
                made = os.path.join(YT, "videos", "persian", vid)
                if vid:
                    parked.append(made)
                check(bool(vid) and os.path.isfile(os.path.join(made, "media.mp4")),
                      "a film on this machine becomes a video with the film "
                      "beside its transcript", json.dumps(j)[:200])
                check((j or {}).get("how") in ("linked", "copied"),
                      "linked where the filesystem allows it, copied where "
                      "not -- either way a real file", str((j or {}).get("how")))
                meta = json.load(open(os.path.join(made, "video.json"),
                                      encoding="utf-8")) if vid else {}
                check(meta.get("url") == "",
                      "and no address is invented for it: there is no YouTube "
                      "video at a local id", repr(meta.get("url")))
                for q, want in (("", True), ("?media=text", False)):
                    c = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
                    c.request("GET", "/youtube/v/%s/__download%s" % (vid, q))
                    r = c.getresponse()
                    body = r.read()
                    z = zipfile.ZipFile(io.BytesIO(body))
                    got = any(n.endswith("media.mp4") for n in z.namelist())
                    check(r.status == 200 and got is want,
                          "the download carries the film%s"
                          % ("" if want else " only when asked to"),
                          "%d, %d kB, film=%s" % (r.status, len(body) // 1024, got))
                    if want:
                        check(z.read("%s/media.mp4" % vid) == blob,
                              "and it is the film itself, byte for byte")
                # and the player is told where the film is -- under
                # /youtube/videos/, the route that answers Range, which is
                # what lets a <video> seek at all
                page = ytpages.player_page(vid) if vid else ""
                cfg = json.loads(page.split("window.YTFRANK=", 1)[1]
                                 .split("</script>", 1)[0].strip().rstrip(";")) \
                    if "window.YTFRANK=" in page else {}
                check(cfg.get("media", "").endswith("/%s/media.mp4" % vid),
                      "and the player is told where its film is",
                      repr(cfg.get("media")))
                check(cfg.get("local") is True,
                      "and that it IS a film rather than an address")
                # A FILM THAT HAS BEEN MOVED AWAY.  `media` alone cannot say
                # what kind of video this is -- an absent film and a YouTube
                # video look the same from the page -- and without `local`
                # the reader was told to check their internet connection
                # about a file sitting on their own disk.
                os.unlink(os.path.join(made, "media.mp4"))
                page = ytpages.player_page(vid)
                cfg = json.loads(page.split("window.YTFRANK=", 1)[1]
                                 .split("</script>", 1)[0].strip().rstrip(";"))
                check(cfg.get("media") == "" and cfg.get("local") is True,
                      "a local video whose film is gone still says it is one, "
                      "so the page does not go asking YouTube for it",
                      json.dumps({k: cfg.get(k) for k in ("media", "local")}))
        finally:
            for d in parked:
                if not _removable(d):
                    bad("the server test's cleanup", "refused to delete %r: not a "
                        "book or a video on the shelves" % d)
                    continue
                shutil.rmtree(d, ignore_errors=True)
                up = os.path.dirname(d)
                # A SHELF THE TOOLBOX SHIPS STAYS PUT.  `youtube/videos/
                # <language>/` is tracked -- a .gitkeep sits in it -- and a
                # test that empties one must not then take the shelf away
                # too; the trash beside it is made on demand and may go.
                if os.path.basename(up) == ".trash":
                    try:
                        os.rmdir(up)
                    except OSError:
                        pass
    finally:
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            c.request("POST", "/__shutdown", b"", {"Content-Length": "0"})
            c.getresponse().read()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.flush()
        log.seek(0)
        text = log.read()
        log.close()
        os.unlink(log.name)
        shutil.rmtree(config, ignore_errors=True)
        check("Traceback" not in text, "no traceback in the server log", text[-1500:])


def test_wordline():
    """The word line's three parsers against one fixture: lib/wordline.py
    here, lib/wordline.lua through texlua, lib/wordline.js through deno.
    Compared by code, never by sentence."""
    section("word line")
    import languages
    import wordline as W
    F = json.load(open(os.path.join(ROOT, "tests", "fixtures", "wordline.json"), encoding="utf-8"))

    def parsed(line):
        try:
            return [list(p) for p in W.parse(line)]
        except W.WordsError as e:
            return e.code
    for c in F["parse"]:
        check(parsed(c["line"]) == c.get("error", c.get("words")),
              "wordline.py parses %r" % c["line"], repr(parsed(c["line"])))
    for c in F["render"]:
        try:
            got = W.render([tuple(p) for p in c["words"]])
        except W.WordsError as e:
            got = e.code
        check(got == c.get("error", c.get("line")), "wordline.py renders %r" % c["words"], repr(got))
    for c in F["align"]:
        try:
            got = [list(s) for s in W.align(c["fa"], [tuple(p) for p in c["words"]])]
        except W.WordsError as e:
            got = e.code
        check(got == c.get("error", c.get("spans")), "wordline.py aligns %r" % c["fa"], repr(got))
    for c in F["check"]:
        errs, warns = W.check(c["fa"], c["line"], languages.get(c["lang"]), c.get("reading", ""),
                              c.get("reorders", False), c.get("door", "book"))
        got = [[e.code for e in errs], [w.code for w in warns]]
        check(got == [c["errors"], c["warnings"]],
              "wordline.py checks %s %r" % (c["lang"], c["line"]), "%r %s" % (got, errs + warns))
    for c in F["divide"]:
        a, b, notes = W.divide(c["line"], c["a"])
        check((a, b, len(notes)) == (c["first"], c["second"], c["notes"]),
              "wordline.py divides %r after %r" % (c["line"], c["a"]), repr((a, b, notes)))

    def lua_str(s):
        return '"' + "".join("\\%d" % b for b in s.encode("utf-8")) + '"'
    texlua = shutil.which("texlua")
    if not texlua:
        skip("no texlua: lib/wordline.lua not run against the fixture")
    else:
        lines = ["local W = dofile(%s)" % lua_str(os.path.join(LIB, "wordline.lua")),
                 "local SEP, REC = string.char(31), string.char(30)",
                 "local function show(r, code)",
                 "  if not r then print('ERR\\t' .. code) return end",
                 "  local out = {}",
                 "  for _, x in ipairs(r) do out[#out+1] = x[1] .. SEP .. x[2] .. SEP .. tostring(x[3]) end",
                 "  print('OK\\t' .. table.concat(out, REC))",
                 "end"]
        for c in F["parse"]:
            lines.append("show(W.parse(%s))" % lua_str(c["line"]))
        for c in F["align"]:
            lines.append("show(W.align(%s, {%s}))" % (lua_str(c["fa"]), ",".join(
                "{%s,%s}" % (lua_str(s), lua_str(r)) for s, r in c["words"])))
        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
            script = f.name
        try:
            rc, out = run([texlua, script], timeout=60)
        finally:
            os.unlink(script)
        got = out.split("\n")
        k = 0
        for c in F["parse"]:
            want = ("ERR\t" + c["error"]) if "error" in c else "OK\t" + "\x1e".join(
                "%s\x1f%s\x1fnil" % (s, r) for s, r in c["words"])
            check(rc == 0 and k < len(got) and got[k] == want, "wordline.lua parses %r" % c["line"],
                  got[k] if k < len(got) else out[-300:])
            k += 1
        for c in F["align"]:
            want = ("ERR\t" + c["error"]) if "error" in c else "OK\t" + "\x1e".join(
                "%s\x1f%s\x1f%s" % (t, r, "false" if i is None else i) for t, r, i in c["spans"])
            check(rc == 0 and k < len(got) and got[k] == want, "wordline.lua aligns %r" % c["fa"],
                  got[k] if k < len(got) else out[-300:])
            k += 1

    deno = (shutil.which("deno") or _runtime.tool("deno", _runtime.find_env()[0])
            or os.path.expanduser("~/miniconda3/envs/ilya-frank/bin/deno"))
    if not os.path.exists(deno):
        skip("no deno: lib/wordline.js not run against the fixture")
        return
    langs = {c: languages.get(c).as_json() for c in {x["lang"] for x in F["check"]}}
    js = """
await import(%s);
const W = globalThis.ParsehWordline, F = %s, LANGS = %s, out = [];
const tried = (f) => { try { return f(); } catch (e) { return e.code; } };
for (const c of F.parse) out.push(tried(() => W.parse(c.line)));
for (const c of F.render) out.push(tried(() => W.render(c.words)));
for (const c of F.align) out.push(tried(() => W.align(c.fa, c.words)));
for (const c of F.check) {
  const r = W.check(c.fa, c.line, LANGS[c.lang], c.reading || '', !!c.reorders, c.door || 'book');
  out.push([r.errors.map((x) => x.code), r.warnings.map((x) => x.code)]);
}
console.log(JSON.stringify(out));
""" % (json.dumps("file://" + os.path.join(LIB, "wordline.js")), json.dumps(F), json.dumps(langs))
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as f:
        f.write(js)
        script = f.name
    try:
        rc, out = run([deno, "run", "--quiet", "--allow-read", script], timeout=120)
    finally:
        os.unlink(script)
    try:
        got = json.loads(out.strip().split("\n")[-1])
    except (ValueError, IndexError):
        bad("wordline.js ran", out[-400:])
        return
    wants = ([c.get("error", c.get("words")) for c in F["parse"]] +
             [c.get("error", c.get("line")) for c in F["render"]] +
             [c.get("error", c.get("spans")) for c in F["align"]] +
             [[c["errors"], c["warnings"]] for c in F["check"]])
    names = (["parses %r" % c["line"] for c in F["parse"]] +
             ["renders %r" % c["words"] for c in F["render"]] +
             ["aligns %r" % c["fa"] for c in F["align"]] +
             ["checks %s %r" % (c["lang"], c["line"]) for c in F["check"]])
    for name, g, w in zip(names, got, wants):
        check(g == w, "wordline.js " + name, repr(g))


def test_words():
    """The automatic cut: always a proposal that rejoins its text, where the
    analyzers are installed in the running Python, and nothing where not."""
    section("automatic word cutting")
    import languages
    import segmenter
    import words
    import wordline as W
    for code, text in (("ja", "山へ柴刈りに、"), ("zh", "我想要一杯茶")):
        if not words.available(code):
            skip("%s: %s is not importable in %s -- nothing cut"
                 % (code, segmenter.about(code)["packages"], sys.executable))
            check(words.line(text, code) == "", "%s: no analyzer, so no proposal" % code)
            continue
        L = languages.get(code)
        for sample, want in {
                "ja": (("おじいさんとおばあさんが住んでいました。",
                        "おじいさん と おばあさん が 住んでいました(すんでいました) 。"),
                       ("今日は良い天気ですね", "今日(きょう) は 良い(よい) 天気(てんき) です ね"),
                       ("テレビを15台買った", "テレビ を 15 台(だい) 買った(かった)")),
                "zh": (("请等一下", "请(qǐng) 等(děng) 一下(yíxià)"),
                       ("我要一杯茶", "我(wǒ) 要(yào) 一(yì) 杯(bēi) 茶(chá)"),
                       ("西安 很好", None))}[code]:
            got = words.line(sample, code)
            if want is not None:
                check(got == want, "%s cuts %s" % (code, sample), got)
            errs, _ = W.check(sample, got, L, door=W.VIDEO)
            check(got and not errs, "%s: the proposal for %s rejoins its text" % (code, sample),
                  "%r %s" % (got, errs))
        check("xī'ān" in words.line("西安", code) if code == "zh" else True,
              "zh: a syllable opening on a vowel is set off by an apostrophe (xī'ān)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", action="store_true", help="also run the LaTeX builds")
    ap.add_argument("--only", default="", help="comma-separated: compile,js,registry,books,videos,draft,divide,words,studio,notes,lookup,verbs,corpus,delete,anki,server (js includes the dom-id and theme checks)")
    a = ap.parse_args()
    only = set(x for x in a.only.split(",") if x)
    want = lambda k: not only or k in only
    os.chdir(ROOT)
    import configguard
    config_before = configguard.snapshot()
    if want("compile"):
        test_compile()
    if want("registry"):
        test_registry()
    if want("js"):
        test_js()
        test_reading_place()
        test_dom()
        test_theme()
    if want("books"):
        test_books(a.pdf)
    if want("videos"):
        test_videos()
        test_chunker()
        test_pronunciation()
        test_append()
    if want("draft"):
        test_draft()
    if want("divide"):
        test_divide()
    if want("words"):
        test_wordline()
        test_words()
    if want("studio"):
        test_studio(a.pdf)
    if want("notes"):
        test_notes()
    if want("lookup"):
        test_lookup()
        test_hits()
        test_getsyn()
        test_getdict()
        test_translit()
    if want("verbs"):
        test_verbs_core()
        test_verbs_recipes()
        test_vb_macro()
    if want("corpus"):
        test_corpus()
    if want("delete"):
        test_delete()
    if want("anki"):
        test_anki()
    if want("server"):
        test_server()
    # NOTHING HERE MAY CHANGE config/ (tests/configguard.py): the owner's
    # settings sit there, beside the checkout this runs in, and a sweep that
    # changed them must not end green.  Looked at once, after everything, so
    # that no section can be left out of it.
    section("config")
    config_after = configguard.snapshot()
    said = configguard.report(config_before, config_after)
    if said:
        print(said, flush=True)
    check(not said, "config/ is byte for byte as the run found it",
          "; ".join(configguard.changes(config_before, config_after)))
    print("\n%d passed, %d failed, %d skipped" % (len(PASSES), len(FAILS), len(SKIPS)))
    for f in FAILS:
        print("  FAIL " + f[:300])
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
