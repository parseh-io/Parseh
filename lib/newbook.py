#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The "add a book" page: three ways in, and only one of them on screen.

A book is not a paste-the-answer job.  It is days of work, paragraph by
paragraph.  There are three ways to begin one, and they need almost
disjoint facts -- which is why the page asks WHICH FIRST and then shows
that one alone:

  1. by hand, here.  A chapter is pasted and POSTed to /books/__empty,
     which drafts the whole book with the text divided and every gloss
     blank -- a chunk nobody has glossed yet is legal everywhere, so the
     book reads and builds from the first minute -- and the reader (which
     has its own editor, a chunk by hand or a region at a time with an
     LLM) is where it is filled in.  It needs the book's facts and a
     chapter, and none of the four fields the outside folder needs.

  2. onto a book already here.  POST <book>/__append, addressed by the
     book's own path so no slug ever travels in a body.  Its body is
     three keys -- text, how, chapter -- and NOT ONE of the identity
     fields: the language, the gloss and the title are the book's
     already, read from its book.json.  The text may be a file instead
     (a PDF with its pages, an epub, a text file), sent as the body and
     recovered by lib/sourcetext.py.  For a book an agent is making, or
     one it made and the person wants it to go on with, the text is
     handed to the AGENT as a part (lib/making.py add_part) instead.

  3. made by an agent, in place.  The book's facts and its original -- a
     file the person picks, uploaded, so no path is typed on the server --
     become a folder under books/ (lib/making.py), with the instructions
     the agent reads; the person opens that folder in whatever agent they
     use.  Parseh never starts an agent.  Nothing is copied and nothing is
     brought back: the agent works on the real tree, and the book is on
     the library from the first minute, marked being made, where its
     making panel watches it grow.  Every device let in may make the
     folder; only opening it is the computer's.

What used to be a single fifteen-field block above three mutually
exclusive actions, with the mapping stated only in prose, is now
structure: the ten identity fields are built ONCE, in #ident, and MOVED
(appendChild, never cloned -- a clone would fork the values, the
listeners and the saved draft) into whichever way needs them.  The
original file, its pages, the edition to learn from and the box about the
person's own books render in way 3 alone, inside a labelled box that says
so.

The instructions the agent reads are lib/making.py's, and the server
produces them: this file lays the page out and fills none of their
placeholders, so the text the page shows is the text the folder gets.
Everything the page needs to know about the toolbox (the built books with
their languages and sizes, for Learn from; the books already on the shelf
-- built or not, because a name is taken either way -- and every language
of the registry) is embedded as JSON.  The language select defaults to
the toolbox's shared preference (Parseh.lang, the chip rows' choice).

A book declares TWO languages: the one it teaches and the one its
glosses are WRITTEN in (docs/languages.md section 3).  The second select
is that, defaulting to English -- which is what every book in the
toolbox is glossed in, and what a book.json with no "gloss" means -- and
offering both the languages the toolbox teaches and the prose languages
it can only set.
"""
import html
import json
import os
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, LIB)
from books import all_books, ROOT                              # noqa: E402
import chunker                                                 # noqa: E402
import languages                                               # noqa: E402
import make_index                                              # noqa: E402
import promptkit                                               # noqa: E402
import making                                                  # noqa: E402  the folder way 3 makes, and who may make it

APP_NAME = "Parseh"
DOCS = os.path.join(ROOT, "docs")


def esc(s):
    return html.escape(str(s or ""), quote=True)


def references():
    """Every finished, built book, with what the page says about it and the
    language it is in: what the agent may be shown, when the person picks
    one, as an example of the method.  A book still being made is no example
    of anything yet."""
    out = []
    for b in all_books():
        st = make_index.stats(b)
        if not st.get("built") or making.is_making(b.dir):
            continue
        chapters = len(st.get("chapters", []))
        stats = ("%d chapter%s, %d paragraphs, %d subparagraphs, %d chunks%s%s"
                 % (chapters, "" if chapters == 1 else "s", st.get("paragraphs", 0),
                    st.get("subs", 0), st.get("chunks", 0),
                    ", narrated" if b.has_audio else "",
                    ", with notes" if os.path.isfile(os.path.join(b.dir, "NOTES.md")) else ""))
        out.append({"path": b.rel_from_books(), "lang": b.language, "lang_name": b.lang.name,
                    "title": b.title_latin or b.title or b.slug, "stats": stats,
                    "has_notes": os.path.isfile(os.path.join(b.dir, "NOTES.md")),
                    "paragraphs": st.get("paragraphs", 0)})
    # the edition with notes, and the biggest, is the one to learn from
    out.sort(key=lambda r: (-int(r["has_notes"]), -r["paragraphs"]))
    return out


def shelf():
    """Every book already here -- built or not -- with where it lives.

    Two jobs, and the second is why this is data and not only markup.
    The way that adds to a book needs the list to choose from, and each
    option carries the book's own language so the text box takes that
    book's face and direction rather than the identity select's.  And the
    slug field needs the names ALREADY TAKEN, so the page can say a name
    is taken before the write refuses it (draft._write refuses on a
    book.json that exists, whatever state the book is in).  references()
    cannot answer that: it holds BUILT books only, and the likeliest
    collision of all is with a draft nobody has built yet.

    The href is worked out from the DIRECTORY rather than from the slug,
    so a book from before languages (lying directly under books/) is
    addressed correctly too.  `state` says whether an agent made the book
    ("making", "finished", or "none" for one nobody made that way): text
    added to one it is making becomes a part the agent takes, and a book
    it is making is no example.
    """
    out = []
    for b in all_books():
        try:
            rel = os.path.relpath(b.dir, os.path.join(ROOT, "books"))
        except ValueError:
            continue
        rel = rel.replace(os.sep, "/")
        out.append({"path": "/books/" + rel, "rel": rel,
                    "folder": b.lang.folder, "dirname": os.path.basename(b.dir),
                    "lang": b.language, "lang_name": b.lang.name,
                    "dir": b.lang.dir, "making": making.is_making(b.dir),
                    "state": making.state(b.dir),
                    "name": b.meta.get("title_latin") or b.meta.get("title") or rel})
    return out


def conventions(L):
    """docs/lang/<code>.md, the language's binding annotation conventions as
    a book from scratch takes them (lib/promptkit.py: all of them, the flags of
    a book resolved), read now rather than at import so an edit to the file
    reaches the next request.  A missing file is said to be missing, in one
    line, rather than leaving the prompt with a hole."""
    return promptkit.language_text("book-new", L)


def lang_records():
    """One record per language of the registry, in its order, with what the
    page lays out: its names, its folder and its direction."""
    return [{"code": L.code, "name": L.name, "native": L.native, "folder": L.folder,
             "dir": L.dir, "standard_name": L.standard_name,
             "varieties": [{"key": v["key"], "name": v.get("name") or v["key"]} for v in L.varieties]}
            for L in languages.LANGS.values()]


def gloss_records():
    """One record per language a book's glosses may be written in.

    languages.GLOSSES is the whole answer -- the eight the toolbox teaches,
    each named by the registry, then the prose languages it can set but does
    not teach -- so nothing is listed here.  `taught` is what divides the
    select into its two groups: a language with a folder under books/ and a
    language this toolbox only writes in.
    """
    return [G.as_json() for G in languages.GLOSSES.values()]


# \BookLang, \BookGloss and \FrankLib come before the preamble, which reads
# them; the preamble \providecommand's all three (\BookGloss as `en', which is
# what a book that says nothing means) so the reference's older main.tex still
# builds.  ../../../lib: the book sits two directories under books/.
MAIN_TEX = r'''%% {{TITLE_LATIN}} - {{AUTHOR_LATIN}} ({{LANG_NAME}}, glossed in {{GLOSS_NAME}}).  Build with:  ./build.sh {{SLUG}}
\newcommand{\BookLang}{{{LANG}}}
\newcommand{\BookGloss}{{{GLOSS}}}
\newcommand{\FrankLib}{../../../lib}
\newcommand{\BookTitle}{{{TITLE}}}
\newcommand{\BookAuthor}{{{AUTHOR}}}
\newcommand{\BookTitleLatin}{{{TITLE_LATIN_UPPER}}}
\newcommand{\BookAuthorLatin}{{{AUTHOR_LATIN}}}
\input{\FrankLib/frank-preamble.tex}
\input{\FrankLib/frank-frontmatter.tex}

% one \input per batch, added as each batch is assembled and checked:
% \input{ch1.tex}    % chapter 1, paragraphs 0-9
% \input{ch1b.tex}   % paragraphs 10-19
% ...

\end{document}'''


def page():
    """The page.  Every device let in may make a book's folder and add text to
    one (the owner, 2026-09-29): nothing on it is shut by who is asking."""
    refs = references()
    langs = lang_records()
    glosses = gloss_records()
    books = shelf()
    data = {"refs": refs, "langs": langs, "glosses": glosses, "books": books,
            "default_lang": languages.DEFAULT, "default_gloss": languages.DEFAULT_GLOSS,
            "original_exts": list(making.ORIGINAL_EXTS)}
    # The ways a draft may be cut, named once (lib/chunker.py) so this page
    # and the video's cannot come to disagree about what they offer.  All of
    # them are offered whatever is installed, and NOT disabled by what this
    # toolbox can do today: the language is chosen on this same form, so a
    # page rendered once cannot know which language the answer will be about,
    # and greying out `sense groups' because the DEFAULT language has no
    # dictionary would be wrong for every other one.  What each needs is said
    # beside the select, and a way that cannot be carried out falls back --
    # to the dictionary cut, or to one chunk per sentence -- rather than
    # failing.
    def how_opts(el_id):
        return ('<select id="%s">%s</select>'
                % (el_id, "".join('<option value="%s"%s>%s</option>'
                                  % (w, " selected" if w == chunker.DEFAULT_WAY else "",
                                     html.escape(chunker.WAY_LABEL[w]))
                                  for w in chunker.WAYS)))
    # each option carries the book's own language: the text box of the way
    # that adds to a book takes ITS face and direction, never the identity
    # select's, which is about a book that does not exist yet
    # (a book an agent is still making is listed and chosen like any other, and what is
    # added to it is handed to the agent as a part: blank chunks put into it would be
    # erased by its next batch)
    into_opts = "".join(
        '<option value="%s" data-lang="%s" data-dir="%s" data-langname="%s" data-name="%s" data-state="%s">'
        '%s &mdash; %s%s</option>'
        % (esc(b["path"]), esc(b["lang"]), esc(b["dir"]), esc(b["lang_name"]), esc(b["name"]), esc(b["state"]),
           esc(b["name"]), esc(b["rel"]),
           " (being made)" if b["making"] else " (made by an agent)" if b["state"] == "finished" else "")
        for b in books)
    lang_opts = "".join('<option value="%s">%s &mdash; %s</option>'
                        % (esc(L["code"]), esc(L["name"]), esc(L["native"]))
                        for L in langs)
    # two groups, because the two halves are not the same kind of thing: one
    # is a language with a folder under books/ and a conventions file, the
    # other a language this toolbox can only write and set
    gloss_opts = "".join(
        '<optgroup label="%s">%s</optgroup>'
        % (label, "".join('<option value="%s">%s &mdash; %s</option>'
                          % (esc(G["code"]), esc(G["name"]), esc(G["native"]))
                          for G in glosses if G["taught"] is taught))
        for taught, label in ((True, "taught here"), (False, "written in, not taught")))
    ref_opts = '<option value="">none</option>' + "".join(
        '<option value="%s" data-lang="%s">%s (%s) &mdash; %s</option>'
        % (esc(r["path"]), esc(r["lang"]), esc(r["title"]), esc(r["lang_name"]), esc(r["stats"]))
        for r in refs)
    # The card for "add to a book already here" is not offered when there is
    # nothing to add to.  The LANE stays in the markup whatever the shelf
    # holds -- every control it owns is read by save() and the draft restore,
    # and a missing one would take the whole script down on a toolbox with no
    # books yet, which is every first run.
    extend_hidden = "" if books else " hidden"
    return r'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Add a book &mdash; ''' + APP_NAME + r'''</title>
<link rel="stylesheet" href="/lib/parseh.css">
<link rel="stylesheet" href="/lib/langs.css">
<link rel="stylesheet" href="/youtube/lib/style.css">
<script src="/lib/parseh.js"></script>
<script src="/lib/llmrow.js"></script>
<style>
/* Both add pages sit at body.wizard main{max-width:820px} (youtube/lib/style.css),
   which already has its matching footer rule.  The 860px this page used to
   force was for the command blocks, and those are inside a <details> now. */
.step label{display:block;margin:10px 0 4px;font-size:13.5px;color:var(--dim)}
.step label.inline{display:flex;align-items:center;gap:8px;margin:0;flex-wrap:wrap}
.step input[type=text],.step input:not([type]),.step select,.step textarea{width:100%;font:inherit;
  font-size:14px;padding:7px 10px;border:1px solid var(--rule);border-radius:7px;
  background:var(--bg);color:var(--ink)}
.step label.inline select{width:auto}
/* the title and author fields are in the book's language: the face and the
   direction follow the select.  data-lang sits on #ident, the block that
   TRAVELS between the ways -- put it on a wrapper that stays behind and the
   fields lose their face the moment the block is moved into another lane. */
.step input[data-tl]{font-family:var(--tl-font,inherit)}
.step textarea{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;line-height:1.5;
  resize:vertical;white-space:pre}
.step .grid{display:grid;grid-template-columns:1fr 1fr;gap:4px 14px}
.step .grid .wide{grid-column:1/-1}
.step .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:12px}
.step pre.cmd{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;line-height:1.55;
  background:var(--bg);border:1px solid var(--rule);border-radius:8px;padding:10px 12px;
  overflow:auto;max-height:420px;white-space:pre;color:var(--ink);margin:8px 0}
.step pre.cmd.wrap{white-space:pre-wrap;overflow-wrap:anywhere}
.step .why{font-size:13.5px;line-height:1.65;color:var(--dim)}
.step .why b{color:var(--ink)}
.step ol{padding-left:20px;margin:0}
.step li{font-size:13.5px;line-height:1.7;color:var(--dim);margin:2px 0}
.step code,.pathnote code,.fieldnote code{font-family:ui-monospace,Menlo,monospace;
  font-size:12px;background:var(--bg);border:1px solid var(--rule);border-radius:4px;padding:0 4px}
.step details{margin:8px 0 0}
.step summary{cursor:pointer;color:var(--dim);font-size:13.5px}
.stat{color:var(--accent);font-size:12.5px}
.stat.warn{color:var(--warn)}
/* the chapter is text in the book's language, not a command: it overrides
   the monospace the command blocks share, and wraps */
.step textarea[data-tl]{font-family:var(--tl-font,inherit);font-size:15px;
  line-height:1.8;white-space:pre-wrap}
/* the prose links wear the accent: the browser's own link colour is the one
   thing on these pages that follows neither theme's palette */
.step a,.pathnote a,footer.idx a{color:var(--accent)}
/* a refusal from a door may be several lines (the control-character one
   quotes thirty characters of context under its sentence) and must read as
   it was written */
.note.bad{white-space:pre-wrap}
.note .row{margin-top:10px}
/* .wbtn was written for a <button>; the reader link in an answer is an <a>
   wearing it, and an inline box ignores the vertical padding */
a.wbtn{display:inline-block;text-decoration:none;color:var(--accent-fg)}

/* ---------------- the chooser ----------------
   Not a <fieldset>/<legend>: a legend inside a display:grid fieldset is the
   one layout engines still disagree about, and one taken as a grid item
   steals the first card's cell -- three cards silently become two and one.
   A <p> naming the group through aria-labelledby says the same thing to a
   screen reader and lays out the same everywhere. */
.qlab{display:block;margin:0 0 10px;font:400 13px/1.3 inherit;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint)}
.paths{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 6px}
.paths.two{grid-template-columns:repeat(2,minmax(0,1fr))}
@media (max-width:760px){.paths,.paths.two{grid-template-columns:1fr}}
.path{display:block;width:100%;text-align:start;font:inherit;cursor:pointer;
  background:var(--card);color:var(--ink);border:1px solid var(--rule);
  border-radius:12px;padding:14px 15px 12px;transition:border-color .12s,transform .12s}
.path:hover{border-color:var(--accentlt);transform:translateY(-1px)}
.path:focus-visible{outline:2px solid var(--accentlt);outline-offset:2px}
.path b{display:block;font-size:15px;font-weight:600;color:var(--ink)}
.path span{display:block;margin-top:4px;font-size:12.5px;line-height:1.5;color:var(--dim)}
.path em{display:block;margin-top:8px;font-style:normal;font-size:11px;
  letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}
/* "chosen" wears the chip row's own signature, so it reads here exactly as
   it does on every language row in the toolbox (parseh.css .chip.on) */
.path[aria-checked="true"]{border-color:var(--accent);background:var(--hl)}
.path[aria-checked="true"] em{color:var(--accent)}
.pathnote{max-width:34rem;margin:0 auto;padding:26px 0;text-align:center;
  color:var(--dim);font-size:13px;line-height:1.6}
.pathnote b{color:var(--ink)}
.pathnote .also{display:block;margin-top:10px;color:var(--faint);font-size:12px}

/* ---------------- one sentence under one control ----------------
   Requirement 4: every option says what it does, where it is, in a line.
   Anything longer than a line goes behind the way's own disclosure. */
.fieldnote{display:block;margin-top:4px;font-size:12px;line-height:1.5;color:var(--faint)}
.fieldnote b{color:var(--dim)}
.fieldnote.warn{color:var(--warn)}
.fieldnote.bad{color:var(--danger)}
/* a disabled button keeps its pointer events (style.css only dims it), so
   its title can still say what is missing -- but a touch screen never shows
   a title, and there the same sentence is printed instead */
.whysmall{display:none}
@media (max-width:620px){.whysmall{display:block}}

/* ---------------- the disclosure ----------------
   The narration panel's device, in this page's tokens: one button per way,
   opening one labelled box.  What is read once and never again must not sit
   between a person and the buttons. */
.hbtn{font:inherit;font-size:13px;padding:5px 10px;border:1px solid var(--rule);
  background:transparent;color:var(--dim);border-radius:6px;cursor:pointer;margin-top:14px}
.hbtn:hover{border-color:var(--accentlt);color:var(--accent)}
.hbox{background:var(--boxbg);border:1px solid var(--rule);border-radius:10px;
  padding:10px 12px;margin-top:10px}
.hlab{color:var(--dim);font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;
  margin-bottom:8px}
.hbox p{font-size:12.5px;line-height:1.55;color:var(--faint);margin:0 0 8px}
.hbox p:last-child{margin-bottom:0}
.hbox p b{color:var(--dim)}
.hbox label{margin-top:6px}
/* the folder that was made: its path is what gets copied into an agent's chat,
   so it wraps rather than scrolls and selects whole with one click */
.step code.bigpath,.note code.bigpath{display:block;margin:10px 0;padding:8px 10px;font-size:12.5px;
  overflow-wrap:anywhere;user-select:all}
.handover{margin:12px 0 4px;font-size:14px;color:var(--ink)}
</style>
</head><body class="index wizard">
<div class="parseh-bar">
  <a class="home" href="/" title="the hub"><span class="glyph">&#x67E;</span>''' + APP_NAME + r'''</a>
  <span class="where"><a href="/books/">books</a> &rsaquo; add<span id="crumb"></span></span>
  <span class="sp"></span>
  <button type="button" data-parseh-theme title="theme">&#9680;</button>
  <button type="button" class="stop" data-parseh-stop title="stop the server">&#9211; stop</button>
</div>
<main>
  <h1 class="idx">Add a book</h1>
  <p class="sub" style="max-width:46rem">A reading edition is made paragraph by paragraph,
  with a checker after every batch &mdash; days of work, not one answer.</p>

  <p class="qlab" id="q1lab">What are you doing?</p>
  <div class="paths" id="paths" role="radiogroup" aria-labelledby="q1lab">
    <button type="button" class="path" role="radio" aria-checked="false" tabindex="0"
            data-path="new" aria-controls="lane-new">
      <b>Write it here, by hand</b>
      <span>Paste a chapter. It is cut into paragraphs and sentences with every gloss left
        blank, and the reader opens on it.</span>
      <em>needs: the book&rsquo;s facts, and a chapter</em>
    </button>
    <button type="button" class="path" role="radio" aria-checked="false" tabindex="-1"
            data-path="extend" aria-controls="lane-extend" id="card-extend"''' + extend_hidden + r'''>
      <b>Add to a book already here</b>
      <span>More text onto the end of a book on the shelf. Nothing already written is touched
        or re-cut.</span>
      <em>needs: a book, and the text</em>
    </button>
    <button type="button" class="path" role="radio" aria-checked="false" tabindex="-1"
            data-path="llm" aria-controls="lane-llm">
      <b>Let an agent make it</b>
      <span>Parseh makes the book&rsquo;s folder; the agent you use fills it in, batch by batch,
        while you watch the book grow in the library and steer it.</span>
      <em>needs: the facts, the original file &mdash; and an agent that works in a folder</em>
    </button>
  </div>

  <p class="pathnote" id="nopath">Three ways in. <b>By hand</b> and <b>add to a book</b> write
    to the shelf straight away; <b>an agent</b> gets a folder of its own on the shelf, made here,
    and does the work in it.
    <span class="also">Already have an exported <code>&lt;slug&gt;-book.zip</code>? Bring it
      back from <a href="/books/">the library page</a>.</span></p>

<!-- ===================== way 1: write it here, by hand ===================== -->
<div id="lane-new" hidden>
<section class="step" id="step-new-1">
  <div class="shead"><span class="num">1</span><h2>The book</h2></div>
  <div class="sbody" id="facts-new">

  <!-- THE IDENTITY BLOCK, BUILT ONCE.  choose() MOVES it (appendChild) into
       the way that needs it -- ways 1 and 3.  A move keeps every value,
       every listener and the saved draft; a clone would fork all three. -->
  <div id="ident">
  <div class="grid">
    <label>Language <select id="lang">''' + lang_opts + r'''</select>
      <span class="fieldnote">The language the book teaches &mdash; it sets the folder it is
        filed under, the fonts it is set in, and the conventions it is annotated by.</span></label>
    <label>Glosses in <select id="gloss">''' + gloss_opts + r'''</select>
      <span class="fieldnote">The language the meanings are written <b>in</b>. An Italian
        learning Persian wants them in Italian.</span>
      <span class="fieldnote" id="glossnote"></span></label>
    <label id="variety_lbl" hidden>Written in <select id="variety"></select>
      <span class="fieldnote">The variety of the language the text is in: the dictionary looks a word up in
        its own dictionary and with its own rules first. It can be changed later in the reader's dictionary
        panel.</span></label>
    <label class="wide">Slug (directory name, ascii) <input id="slug" placeholder="hekayat-e-…" autocomplete="off">
      <span class="fieldnote">The directory name. Left empty it is made from the
        transliterated title.</span>
      <span class="fieldnote" id="slugprev"></span></label>
    <label>Year <input id="year" placeholder="1921" title="Printed on the title page; it is written into book.json and shown on the library card."></label>
    <label><span id="title_lbl">Title, in the language</span> <input id="title" data-tl placeholder="فارسی شکر است"></label>
    <label>Title, transliterated <input id="title_latin" placeholder="Farsi shekar ast">
      <span class="fieldnote">The ascii spelling: the slug falls back to it, and the half
        title is set from it in capitals.</span></label>
    <label><span id="title_en_lbl">Title, in English</span> <input id="title_en" placeholder="Persian is Sugar">
      <span class="fieldnote">The title as the gloss language says it, for the library
        card.</span></label>
    <label><span id="author_lbl">Author, in the language</span> <input id="author" data-tl placeholder="محمدعلی جمال‌زاده"></label>
    <label>Author, transliterated <input id="author_latin" placeholder="Mohammad-Ali Jamalzadeh"
      title="Written into book.json and set as the byline of the half title."></label>
    <label class="wide">One-sentence blurb <input id="blurb" placeholder="What the book is.">
      <span class="fieldnote">One sentence, for the library card.</span></label>
  </div>
  </div>

  </div>
</section>

<section class="step" id="step-new-2">
  <div class="shead"><span class="num">2</span><h2>The chapter</h2></div>
  <div class="sbody">
  <label><span id="text_lbl">The chapter, in the language</span> &mdash; a blank line between
    paragraphs, or one to a line
    <textarea id="chtext" data-tl rows="10" spellcheck="false"></textarea></label>
  <div class="row">
    <label class="inline">Cut the text into ''' + how_opts("how") + r'''</label>
  </div>
  <span class="fieldnote">A chunk is what a reader hovers. <b>Sense groups</b> needs this
    language&rsquo;s installed dictionary and falls back to one chunk per sentence without it
    &mdash; either way you can re-cut any chunk in the reader.</span>
  </div>
</section>

<section class="step" id="step-new-3">
  <div class="shead"><span class="num">3</span><h2>Make it</h2></div>
  <div class="sbody">
  <div class="row">
    <button type="button" class="wbtn" id="mkempty">Make the draft</button>
    <span class="stat" id="estat"></span>
  </div>
  <span class="fieldnote whysmall" id="mkwhy"></span>
  <div id="eresult" aria-live="polite" hidden></div>
  <button type="button" class="hbtn" aria-expanded="false" aria-controls="how-new">how this works</button>
  <div class="hbox" id="how-new" hidden>
    <p><b>What it writes:</b> <code>book.json</code>, <code>main.tex</code>, the chapter&rsquo;s
      <code>.tex</code>, and the source files the fidelity checks read.</p>
    <p><b>Every gloss starts blank</b>, and that is legal: a chunk nobody has glossed yet
      reads, builds and passes the checker as it is (a half-written one is still caught). You
      fill them in in the reader &mdash; a chunk at a time by hand, or a region at a time with
      an LLM.</p>
    <p><b>For Japanese and Chinese</b> the word line is proposed by the toolbox and left for
      you to correct; every other line is blank.</p>
    <p><b>Sense groups</b> cuts at the edges of phrases &mdash; a preposition with its noun, a
      noun with its adjectives, a verb with its auxiliaries &mdash; reading the parts of speech
      out of the language&rsquo;s dictionary.</p>
    <p><b>The reader opens at once.</b> The card on <a href="/books/">the library page</a> is
      written with it; the PDF comes with the next <code>./build.sh</code>, or the button in
      the answer above.</p>
  </div>
  </div>
</section>
</div>

<!-- ===================== way 2: add to a book already here ================= -->
<div id="lane-extend" hidden>
<section class="step" id="step-add-1">
  <div class="shead"><span class="num">1</span><h2>Which book</h2></div>
  <div class="sbody">
  <div class="row">
    <label class="inline">Add to <select id="addinto">''' + into_opts + r'''</select>
      <span class="tag" id="addlang"></span></label>
  </div>
  <span class="fieldnote">Its language, its glosses and its title are the book&rsquo;s already
    &mdash; they are not asked again.</span>
  <div id="addwho" hidden style="margin-top:10px">
    <label class="inline"><input type="radio" name="addwho" id="addwho_agent" value="agent" checked>
      The agent makes it</label>
    <span class="fieldnote" id="addwho_agent_note"></span>
    <label class="inline" style="margin-top:8px"><input type="radio" name="addwho" id="addwho_me" value="me">
      I gloss it myself</label>
    <span class="fieldnote" id="addwho_me_note"></span>
  </div>
  </div>
</section>

<section class="step" id="step-add-2">
  <div class="shead"><span class="num">2</span><h2>Where it goes</h2></div>
  <div class="sbody">
  <label class="inline"><input type="radio" name="addwhere" id="addwhere_new" value="new" checked>
    A new chapter</label>
  <span class="fieldnote">Its own opening and its own line in <code>main.tex</code> &mdash;
    another story, another lesson.</span>
  <label class="inline" style="margin-top:10px"><input type="radio" name="addwhere" id="addwhere_last" value="last">
    More of the last chapter</label>
  <span class="fieldnote">Continues it, its paragraphs numbered on from the ones already there.
    This is the only thing on the page that edits a file that already exists.</span>
  <label class="inline" id="addauto_row" style="margin-top:10px" hidden><input type="radio" name="addwhere" id="addwhere_auto" value="auto">
    Let the agent decide</label>
  <span class="fieldnote" id="addauto_note" hidden>It reads the start of the text: a chapter heading begins a new
    chapter, a start in the middle of a sentence goes on in the last paragraph, and what it decided is
    written in <code>NOTES.md</code> and shown in the making panel.</span>
  </div>
</section>

<section class="step" id="step-add-3">
  <div class="shead"><span class="num">3</span><h2>The text</h2></div>
  <div class="sbody">
  <label><span id="aptext_lbl">The text</span> &mdash; a blank line between paragraphs, or one
    to a line
    <textarea id="aptext" data-tl rows="10" spellcheck="false"></textarea></label>
  <label>Or a file &mdash; a PDF with a text layer, an epub or a plain text file
    <input type="file" id="apfile" accept=".pdf,.epub,.txt,application/pdf,application/epub+zip,text/plain">
    <span class="fieldnote" id="apfilenote">Sent as it is and read here; with a file chosen, the box above is not used.</span></label>
  <label>PDF pages, first&ndash;last <input id="appages" placeholder="13-21">
    <span class="fieldnote" id="appagesnote">Counted from 0, for a PDF only. Leave empty for the whole file.</span></label>
  <div class="row" id="ahowrow">
    <label class="inline">Cut the text into ''' + how_opts("ahow") + r'''</label>
  </div>
  <span class="fieldnote" id="ahownote">A chunk is what a reader hovers. <b>Sense groups</b> needs this
    language&rsquo;s installed dictionary and falls back to one chunk per sentence without it
    &mdash; either way you can re-cut any chunk in the reader.</span>
  </div>
</section>

<section class="step" id="step-add-4">
  <div class="shead"><span class="num">4</span><h2>Add it</h2></div>
  <div class="sbody">
  <div class="row">
    <button type="button" class="wbtn" id="addto">Add it</button>
    <span class="stat" id="addstat"></span>
  </div>
  <span class="fieldnote whysmall" id="addwhy"></span>
  <div id="addresult" aria-live="polite" hidden></div>
  <button type="button" class="hbtn" aria-expanded="false" aria-controls="how-add">how this works</button>
  <div class="hbox" id="how-add" hidden>
    <p><b>Nothing written before is touched or re-cut</b> &mdash; the old chapters are read
      only to be numbered on from.</p>
    <p><b>More of the last chapter</b> rewrites that chapter&rsquo;s file: its
      <code>\chapend</code> moves to the end of the new text, and
      <code>source/src_chN.json</code> is merged.</p>
    <p><b>The new chunks arrive with every gloss blank</b>, as a new book&rsquo;s do, and
      that is legal. You fill them in in the reader &mdash; a chunk at a time by hand, or a
      region at a time with an LLM.</p>
  </div>
  </div>
</section>
</div>

<!-- ===================== way 3: an agent makes it, here =================== -->
<div id="lane-llm" hidden>
<section class="step" id="step-llm-1">
  <div class="shead"><span class="num">1</span><h2>The book</h2></div>
  <div class="sbody" id="facts-llm">
  <!-- #ident is moved in here by choose('llm') -->
  <div class="hbox">
    <div class="hlab">only for a book an agent makes</div>
    <label>The original <input type="file" id="original"
        accept=".pdf,.epub,.txt,application/pdf,application/epub+zip,text/plain">
      <span class="fieldnote">A PDF with a text layer, an epub or a plain text file. It is copied
        into the book&rsquo;s own folder, in <code>original/</code>, and goes nowhere else.</span>
      <span class="fieldnote" id="originalnote"></span></label>
    <label>PDF pages, first&ndash;last <input id="pages" placeholder="13-21">
      <span class="fieldnote" id="pagesnote">Counted from 0, for a PDF only. Leave empty for the
        whole file.</span></label>
    <label>Learn from <select id="ref">''' + ref_opts + r'''</select>
      <span class="fieldnote" id="refnote"></span></label>
    <label class="inline" style="margin-top:12px"><input type="checkbox" id="examples">
      let the agent look at my finished books in this language, as examples</label>
    <span class="fieldnote" id="examplesnote"></span>
  </div>
  </div>
</section>

<section class="step" id="step-llm-2">
  <div class="shead"><span class="num">2</span><h2>Make the book&rsquo;s folder</h2></div>
  <div class="sbody">
  <p class="why">The folder is made in <code>books/</code>, with the original inside it and the
    instructions for the agent. The book is on <a href="/books/">the library page</a> at once,
    marked <b>being made</b>.</p>
  <label class="inline"><input type="checkbox" id="alltext"> this is all the text</label>
  <span class="fieldnote">Left unticked, you may give the agent more text later &mdash; another file, or
    pasted, from the making panel in the book&rsquo;s reader or from <b>add to a book</b> on this page
    &mdash; and it takes each part as it comes. The file you chose is part 1.</span>
  <div class="row">
    <button type="button" class="wbtn" id="mkfolder">make the book&rsquo;s folder</button>
    <span class="stat" id="mkstat"></span>
  </div>
  <span class="fieldnote whysmall" id="mkfwhy"></span>
  <div id="mkresult" aria-live="polite" hidden></div>
  </div>
</section>

<section class="step" id="step-llm-3">
  <div class="shead"><span class="num">3</span><h2>The instructions</h2></div>
  <div class="sbody">
  <p class="why">They are written into the folder as <code>AGENTS.md</code>, which any agent can be
    told to read and several read by themselves. For an agent that does not, copy them here.</p>
  <div id="instrmount"></div>
  <button type="button" class="hbtn" aria-expanded="false" aria-controls="how-llm">how this works</button>
  <div class="hbox" id="how-llm" hidden>
    <p><b>Parseh never starts an agent</b> and does not name one as the way: use any that works in
      a folder. It writes the folder and the instructions, and shows you where.</p>
    <p><b>The agent works on the real tree</b>: Parseh&rsquo;s own tools, run with Parseh&rsquo;s own
      Python, writing only inside the book&rsquo;s folder. Nothing is copied out and nothing is
      brought back.</p>
    <p><b>You watch it in the library and the reader</b>: the book&rsquo;s card says where the
      making stands, and the reader has a making panel &mdash; look at it now, the PDF of the
      chapters so far, what to change from now on, and <b>finish</b> when it is done. While it is
      made, the reader does not edit: the agent writes the book from its own files.</p>
  </div>
  </div>
</section>
</div>
</main>
<footer class="idx">
  <span id="foot-all">A book is written paragraph by paragraph: the reader is rebuilt the
  moment text lands, the PDF with the next <code>./build.sh</code>.</span>
  <span id="foot-llm" hidden>The instructions are written by Parseh into the book&rsquo;s folder
  (<code>AGENTS.md</code>); the conventions per language are <code>docs/lang/&lt;code&gt;.md</code>.</span>
</footer>
<script id="data" type="application/json">''' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + r'''</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById('data').textContent);
  var $ = function (id) { return document.getElementById(id); };
  var KEY = 'bk_add_draft';
  // the fields the notes under way 3's form are worked out from: these, and
  // only these, re-render on every keystroke
  var FIELDS = ['lang', 'gloss', 'ref', 'slug', 'year', 'title', 'title_latin', 'title_en',
                'author', 'author_latin', 'blurb', 'pages'];
  // saved and restored, but never a reason to re-render: the two texts feed
  // nothing else (re-rendering on every keystroke of a pasted chapter would
  // make typing it a chore), and the rest feed only a body.
  // `how` had no listener at all before this: choosing "sense groups" was
  // never saved and silently reverted to one chunk per sentence on reload.
  var SAVE_ONLY = ['how', 'ahow', 'addinto', 'chtext', 'aptext'];
  var LANES = {'new': 'lane-new', 'extend': 'lane-extend', 'llm': 'lane-llm'};
  var PATH = '';
  var IDENT = $('ident');
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
  // every read and write of a control is guarded: the "add to a book" card
  // is not offered on an empty shelf, and a page whose script died on a null
  // would take save(), render() and every button down with it
  function val(id, v) {
    var el = $(id);
    if (!el) return '';
    if (v !== undefined && v !== null) el.value = v;
    return el.value;
  }
  FIELDS.concat(SAVE_ONLY).forEach(function (k) { if (saved[k]) val(k, saved[k]); });
  if (saved.addwhere === 'last') { if ($('addwhere_last')) $('addwhere_last').checked = true; }
  if (saved.examples && $('examples')) $('examples').checked = true;
  function addWhere() {
    return ($('addwhere_last') && $('addwhere_last').checked) ? 'last'
         : ($('addwhere_auto') && $('addwhere_auto').checked && !$('addauto_row').hidden) ? 'auto' : 'new';
  }
  // the language: the draft's if there is one, else the toolbox's shared
  // preference (the chip rows' pick, Parseh.lang), else the registry's default
  if (!saved.lang) {
    var pref = (window.Parseh && Parseh.lang && Parseh.lang.get) ? Parseh.lang.get() : 'all';
    var known = D.langs.some(function (l) { return l.code === pref; });
    val('lang', known ? pref : D.default_lang);
  }
  // the gloss has no shared preference to take: it is not what you are
  // reading, it is what you write, and English is what every book in the
  // toolbox is glossed in and what a book.json with no "gloss" means
  if (!saved.gloss) val('gloss', D.default_gloss);
  function save() {
    var o = {};
    FIELDS.concat(SAVE_ONLY).forEach(function (k) { o[k] = val(k); });
    o.addwhere = addWhere();
    o.examples = !!($('examples') && $('examples').checked);
    o.path = PATH;
    try { localStorage.setItem(KEY, JSON.stringify(o)); } catch (e) {}
  }
  // the toolbox's one case fold, spliced in from languages.FOLD_JS, and then
  // the ASCII that NFKD leaves: the slug the studio's store makes for the
  // same title, character for character.  A plain toLowerCase knows nothing
  // of Turkish, and a directory name is where that shows worst -- it spells
  // İ as i plus a combining dot and leaves ı and the breve of ğ un-ASCII, so
  // "Yağmurlu bir kış" came out yag-murlu-bir-k-s.
  var foldCase = ''' + languages.FOLD_JS + r''';
  function slugify(s) {
    // the hyphens are stripped and THEN it is cut to 40, exactly as
    // draft.slugify does (re.sub(...).strip("-")[:40]); cutting first would
    // leave a trailing hyphen here and not there, and the directory way 3's
    // script creates would differ from the one way 1's door creates
    return foldCase(s).normalize('NFKD').replace(/[^\x00-\x7f]/g, '')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40);
  }
  function langRec() {
    return D.langs.filter(function (l) { return l.code === val('lang'); })[0] || D.langs[0];
  }
  function glossRec() {
    return D.glosses.filter(function (g) { return g.code === val('gloss'); })[0]
      || D.glosses.filter(function (g) { return g.code === D.default_gloss; })[0];
  }
  // The edition to learn from is the person's choice and "none" until they
  // make one: nothing is picked for them
  function refRec() {
    return D.refs.filter(function (r) { return r.path === val('ref'); })[0] || null;
  }
  function slugNow() {
    return slugify(val('slug') || val('title_latin') || val('title') || 'new-book') || 'new-book';
  }
  // THE NAME, BEFORE IT CAN REFUSE.  draft._write refuses a directory that
  // already holds a book.json, whatever state that book is in -- so the list
  // compared against is every book on the shelf (D.books), not the built
  // ones: the likeliest collision of all is with a draft nobody has built.
  function taken(slug, folder) {
    return D.books.some(function (b) { return b.folder === folder && b.dirname === slug; });
  }
  function slugPreview() {
    var L = langRec(), slug = slugNow(), el = $('slugprev');
    if (!el) return;
    var hit = taken(slug, L.folder);
    el.className = 'fieldnote' + (hit ? ' warn' : '');
    el.innerHTML = hit
      ? 'a book is already at <code>books/' + esc(L.folder) + '/' + esc(slug) +
        '/</code> &mdash; choose another slug'
      : 'will be created as <code>books/' + esc(L.folder) + '/' + esc(slug) + '/</code>';
  }
  // The one pairing the reading editions refuse: a right-to-left gloss of a
  // left-to-right text.  The gloss block is one paragraph in the gloss's
  // direction, and a vocabulary line of Latin entries in it comes out with
  // its entries reversed, because the punctuation between them takes the
  // paragraph's direction (lib/frank-preamble.tex says it at length, and
  // stops the build).  The other three pairings all set: it is offered where
  // it works and taken off the list where it does not, rather than left to
  // be discovered by a LaTeX error days later.
  function applyGloss() {
    var L = langRec(), G = glossRec();
    var bad = function (g) { return g.dir === 'rtl' && L.dir !== 'rtl'; };
    Array.prototype.forEach.call($('gloss').options, function (o) {
      var g = D.glosses.filter(function (x) { return x.code === o.value; })[0];
      o.disabled = !!(g && bad(g));
    });
    if (bad(G)) { val('gloss', D.default_gloss); G = glossRec(); }
    var note;
    if (G.code === L.code)
      note = 'Glossed in the language it teaches: the meanings are definitions rather than ' +
             'translations. That is this book\'s choice, not a property of ' + L.name + '.';
    else if (G.taught)
      note = L.name + ' is what the reader is learning; ' + G.name +
             ' is what the book talks to them in.';
    else
      note = 'The meanings are written in ' + G.name + ', which this toolbox sets but does ' +
             'not teach: no folder under books/, no conventions file.';
    var off = D.glosses.filter(bad).map(function (g) { return g.name; });
    if (off.length)
      note += ' ' + off.join(' and ') + ' are greyed out: a right-to-left gloss of a ' +
              'left-to-right text cannot have its vocabulary lines set in order.';
    $('glossnote').textContent = note;
    // the one field the gloss-language refactor never reached: the label
    // follows the gloss, the key in book.json stays title_en
    $('title_en_lbl').textContent = 'Title, in ' + (G.name || 'English');
  }
  function applyLang() {
    var L = langRec();
    // data-lang rides on the block that TRAVELS between the ways: langs.css
    // hands --tl-font down from it to every input[data-tl] inside, and a
    // wrapper left behind in another lane would hand down nothing
    IDENT.setAttribute('data-lang', L.code);
    $('title_lbl').textContent = 'Title, ' + L.name;
    // the varieties of the language, where it has any (Arabic's dialects): the standard one first
    var vs = L.varieties || [], vsel = $('variety'), keep = vsel.value;
    $('variety_lbl').hidden = !vs.length;
    vsel.innerHTML = '';
    [{key: '', name: L.standard_name || L.name}].concat(vs).forEach(function (v) {
      var o = document.createElement('option'); o.value = v.key; o.textContent = v.name; vsel.appendChild(o);
    });
    vsel.value = vs.some(function (v) { return v.key === keep; }) ? keep : '';
    $('author_lbl').textContent = 'Author, ' + L.name;
    // the chapter is the book's own text: its face comes from langs.css
    // through data-lang, and Persian and Arabic read the other way
    $('text_lbl').textContent = 'The chapter, in ' + L.name;
    $('chtext').setAttribute('data-lang', L.code);
    $('chtext').setAttribute('dir', L.dir);
    $('chtext').setAttribute('lang', L.code);
    ['title', 'author'].forEach(function (id) {
      $(id).setAttribute('dir', L.dir); $(id).setAttribute('lang', L.code);
      // the Persian placeholders are the reference's; another language gets none
      $(id).placeholder = (L.code === D.default_lang)
        ? (id === 'title' ? 'فارسی شکر است' : 'محمدعلی جمال‌زاده') : '';
    });
    slugPreview();
  }
  // the book chosen to add to, by its name (the transliterated title, else
  // the title), for the activity list's label of its build
  function intoName() {
    var sel = $('addinto');
    var o = sel ? sel.options[sel.selectedIndex] : null;
    return o ? (o.getAttribute('data-name') || '') : '';
  }
  // THE OTHER TEXT BOX TAKES THE BOOK'S LANGUAGE, NOT THE SELECT'S.  The
  // book being added to has its own language in its own book.json, and
  // add_to_book reads it from there: pasting Persian into a Persian book
  // while the identity select says Italian used to give a left-to-right box
  // in the wrong face.  Run on every change of the select AND after the
  // draft is restored, or a reloaded page opens with the wrong one.
  function applyInto() {
    var sel = $('addinto');
    if (!sel) return;
    var o = sel.options[sel.selectedIndex];
    var code = o ? (o.getAttribute('data-lang') || '') : '';
    var dir = o ? (o.getAttribute('data-dir') || 'ltr') : 'ltr';
    var name = o ? (o.getAttribute('data-langname') || '') : '';
    var ta = $('aptext');
    if (code) { ta.setAttribute('data-lang', code); ta.setAttribute('lang', code); }
    ta.setAttribute('dir', dir);
    $('aptext_lbl').textContent = name ? ('The text, in ' + name) : 'The text';
    $('addlang').textContent = name;
    applyWho();
  }
  // WHO GLOSSES THE TEXT, for a book an agent made.  Being made, the agent takes it as a PART: blank
  // chunks put into a book whose truth is annot/ would be erased by its next assembly, so "I gloss it
  // myself" is only after the making is finished.  Finished, either: by hand as any book's, or by
  // the agent, which reopens the making first.  A book nobody made this way has no such choice.
  function intoState() {
    var sel = $('addinto'), o = sel ? sel.options[sel.selectedIndex] : null;
    return o ? (o.getAttribute('data-state') || 'none') : 'none';
  }
  function byAgent() {
    return intoState() !== 'none' && $('addwho_agent').checked;
  }
  function applyWho() {
    var st = intoState();
    if (!$('addwho')) return;
    $('addwho').hidden = st === 'none';
    $('addwho_me').disabled = st === 'making';
    // a finished book starts at "I gloss it myself": nothing is being made, so the plain way is the default
    if (st !== lastState) { $('addwho_me').checked = st === 'finished'; $('addwho_agent').checked = st !== 'finished'; }
    lastState = st;
    if (st === 'making') $('addwho_agent').checked = true;
    $('addwho_agent_note').textContent = st === 'making'
      ? 'The text becomes the next part: the agent takes it before its next batch, as the place below says.'
      : st === 'finished' ? 'This reopens the making: the text becomes a part, and the agent takes it when you tell it to carry on.' : '';
    $('addwho_me_note').textContent = st === 'making'
      ? 'Only once the making is finished: the agent writes this book from its own files, so blank chunks put in now would be erased by its next batch.'
      : st === 'finished' ? 'Blank chunks at the end of the book, glossed in the reader a region at a time with an LLM, or by hand.' : '';
    var agent = byAgent();
    $('addauto_row').hidden = $('addauto_note').hidden = !agent;
    // the agent deciding is what a part starts as; the person's own pick stays until the way changes
    if (agent && !wasAgent) $('addwhere_auto').checked = true;
    if (!agent && $('addwhere_auto').checked) $('addwhere_new').checked = true;
    wasAgent = agent;
    $('ahowrow').hidden = $('ahownote').hidden = agent;
  }
  var wasAgent = false, lastState = '';
  function render() {
    // THE NOTE UNDER THE SLUG IS NOT WAY 3'S ALONE: "Write it here, by hand"
    // names a slug in the same identity block, and its door creates the very
    // directory the note names.  It sat below the gate, so on that way it was
    // brought up to date only when the language changed: typing a title, or
    // emptying the slug of a restored draft, left it naming the previous
    // book's directory, and "a book is already at … choose another slug"
    // never came while the slug that would be refused was typed.  Here,
    // before the gate, it follows every field on every way that shows it.
    slugPreview();
    if (PATH !== 'llm') return;
    var L = langRec(), ref = refRec(), file = $('original').files[0];
    // the edition to learn from, said as what it does to the agent
    $('refnote').className = 'fieldnote';
    $('refnote').textContent = !D.refs.length
      ? 'There is no finished book here to learn from, and that is fine: the agent works from ' +
        'the instructions alone.'
      : !ref ? 'None: the agent works from the instructions alone.'
      : ref.title + ' is shown to the agent as an example of the method: it reads it where it ' +
        'lies and never changes it.' + (ref.lang === L.code ? '' :
          ' It is in ' + ref.lang_name + ', not ' + L.name + ': the conventions of ' + L.name +
          ' still decide every chunk.');
    // the box about the person's own books: what ticking it does, and how many it names
    var mine = D.books.filter(function (b) { return b.lang === L.code && !b.making; }).length;
    $('examplesnote').textContent = mine
      ? 'Off, the agent is shown none of your books. Ticked, the instructions name where your ' +
        mine + ' finished ' + L.name + ' book' + (mine === 1 ? ' is' : 's are') +
        ', as examples only: it never writes there.'
      : 'You have no finished ' + L.name + ' book yet, so there is nothing to show.';
    // the original as it was chosen, and a file the tools cannot read named at once
    var ext = file ? (file.name.match(/\.[^.]*$/) || [''])[0].toLowerCase() : '';
    var known = D.original_exts.indexOf(ext) >= 0;
    $('originalnote').className = 'fieldnote' + (file && !known ? ' warn' : '');
    $('originalnote').textContent = !file ? '' : !known
      ? file.name + ' is not a PDF, an epub or a plain text file: the tools cannot read it.'
      : file.name + ', ' + size(file.size) + '.';
    // a page range that is not a range is dropped, and so is one for a file with no pages
    var pages = val('pages').trim(), range = /^\d+\s*[-\u2013]\s*\d+$/.test(pages);
    $('pagesnote').className = 'fieldnote' + (pages && (!range || (file && ext !== '.pdf')) ? ' warn' : '');
    $('pagesnote').textContent = (pages && !range) ? 'The page range is ignored: write it 13-21.'
      : (pages && file && ext !== '.pdf') ? 'A page range is for a PDF: it is ignored for this file.'
      : 'Counted from 0, for a PDF only. Leave empty for the whole file.';
    if (instructions) refreshSoon();
  }
  // the file chosen to be added, named with its size and what is wrong with it, before anything is sent
  function addNotes() {
    if (!$('apfile')) return;
    var f = $('apfile').files[0], ext = f ? (f.name.match(/\.[^.]*$/) || [''])[0].toLowerCase() : '';
    var known = D.original_exts.indexOf(ext) >= 0;
    $('apfilenote').className = 'fieldnote' + (f && !known ? ' warn' : '');
    $('apfilenote').textContent = !f ? 'Sent as it is and read here; with a file chosen, the box above is not used.'
      : !known ? f.name + ' is not a PDF, an epub or a plain text file: it cannot be read.'
      : f.name + ', ' + size(f.size) + '.';
    var pages = val('appages').trim(), range = /^\d+\s*[-–]\s*\d+$/.test(pages);
    $('appagesnote').className = 'fieldnote' + (pages && (!range || (f && ext !== '.pdf')) ? ' warn' : '');
    $('appagesnote').textContent = (pages && !range) ? 'The page range is ignored: write it 13-21.'
      : (pages && f && ext !== '.pdf') ? 'A page range is for a PDF: it is ignored for this file.'
      : 'Counted from 0, for a PDF only. Leave empty for the whole file.';
  }
  function size(n) {
    return n < 1024 * 1024 ? Math.max(1, Math.round(n / 1024)) + ' kB' : (n / 1048576).toFixed(1) + ' MB';
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }

  /* ---------------- which way, and only that way ---------------- */
  var CRUMB = {'new': ' &rsaquo; by hand', 'extend': ' &rsaquo; add to a book',
               'llm': ' &rsaquo; made by an agent'};
  function choose(p, push, focusIt) {
    if (!LANES[p]) p = '';                       // an unknown ?path= falls back to the chooser
    if (p === 'extend' && !D.books.length) p = '';   // nothing to add to: the chooser, not an empty select
    PATH = p;
    Object.keys(LANES).forEach(function (k) { $(LANES[k]).hidden = k !== p; });
    Array.prototype.forEach.call(document.querySelectorAll('.path'), function (b) {
      var on = b.dataset.path === p;
      b.setAttribute('aria-checked', String(on));
      b.tabIndex = on ? 0 : -1;
    });
    if (!p) {                                    // nothing chosen: the first card is the way in
      var first = document.querySelector('.path:not([hidden])');
      if (first) first.tabIndex = 0;
    }
    $('nopath').hidden = !!p;
    $('crumb').innerHTML = CRUMB[p] || '';
    $('foot-all').hidden = (p === 'llm');
    $('foot-llm').hidden = (p !== 'llm');
    // A MOVE, NEVER A CLONE.  appendChild takes the block with its values,
    // its listeners and its place in the saved draft; a clone would fork all
    // three and show up only as "my title disappeared when I switched".
    if (p === 'new') $('facts-new').appendChild(IDENT);
    if (p === 'llm') $('facts-llm').insertBefore(IDENT, $('facts-llm').firstChild);
    if (p === 'llm') render();                   // the one gated call: way 3 must not open on empty <pre>s
    // (render() brings the slug note up to date on way 3; on the others it is
    // done here, the warning under it being worded for the way chosen)
    else slugPreview();
    ticks();
    save();
    if (push) {
      try { history.replaceState(null, '', '/books/add/' + (p ? '?path=' + p : '')); } catch (e) {}
    }
    // the keyboard lands inside the way without the page moving; never on a
    // restore or a deep link, where the caret would jump into a textarea
    // before the cards have been read
    if (focusIt && p) {
      var el = $(LANES[p]).querySelector('input,select,textarea,button');
      if (el) el.focus({preventScroll: true});
    }
  }
  Array.prototype.forEach.call(document.querySelectorAll('.path'), function (b) {
    b.addEventListener('click', function () { choose(b.dataset.path, true, true); });
    b.addEventListener('keydown', function (e) {
      var keys = {ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1};
      if (!(e.key in keys)) return;
      e.preventDefault();
      var all = Array.prototype.filter.call(document.querySelectorAll('.path'),
                  function (x) { return !x.hidden; });
      var i = all.indexOf(b);
      var next = all[(i + keys[e.key] + all.length) % all.length];
      next.focus();
      choose(next.dataset.path, true, false);
    });
  });
  // a step's number becomes a ticked circle when what it asks for is there:
  // progress said by the control itself, which is what numbered instructions
  // are for (style.css .step.ok .num)
  function tick(id, ok) { var el = $(id); if (el) el.classList.toggle('ok', !!ok); }
  function ticks() {
    tick('step-new-1', !!val('title').trim());
    tick('step-new-2', !!val('chtext').trim());
    tick('step-add-1', !!val('addinto'));
    tick('step-add-3', !!val('aptext').trim() || !!($('apfile') && $('apfile').files.length));
    tick('step-llm-1', !!(val('title').trim() && $('original').files.length));
    gate();
  }
  // a button that cannot act says why, in its title -- and, where no title is
  // ever shown, in a line under it.  style.css dims a disabled .wbtn and
  // leaves its pointer events alone, so the tooltip is readable.
  function gate() {
    var why = !val('title').trim() ? 'the title comes first'
            : !val('chtext').trim() ? 'paste the chapter first' : '';
    $('mkempty').disabled = !!why;
    $('mkempty').title = why;
    $('mkwhy').textContent = why;
    // the folder's button says why it cannot be pressed, in words: what is missing
    var L = langRec(), mwhy = !val('title').trim() ? 'the title comes first'
             : !$('original').files.length ? 'choose the original first'
             : taken(slugNow(), L.folder) ? 'a book is already at books/' + L.folder + '/' + slugNow() +
               '/ -- choose another slug' : '';
    $('mkfolder').disabled = !!mwhy;
    $('mkfolder').title = mwhy;
    $('mkfwhy').textContent = mwhy;
    var awhy = !val('addinto') ? 'there is no book here to add to yet'
             : !val('aptext').trim() && !($('apfile') && $('apfile').files.length) ? 'paste the text, or choose a file, first' : '';
    if ($('addto')) {
      $('addto').disabled = !!awhy;
      $('addto').title = awhy;
      $('addwhy').textContent = awhy;
    }
  }

  /* ---------------- the answers the doors give ---------------- */
  // The PDF is the one thing a writing way leaves undone, and this page has
  // never offered the button for it though parseh.js has exported it all
  // along: the library page and the reader both build from one.  `name` is
  // the book's name as the server names the build on the activity list, so
  // the pill says it from the click on.
  function buildRow(folder, slug, name) {
    return '<div class="row"><button type="button" class="wbtn quiet" data-buildnow="/books/' +
      esc(folder) + '/' + esc(slug) + '/__build" data-book="' + esc(name || '') +
      '">build the PDF now</button><span class="stat" data-buildsay></span></div>';
  }
  function wireBuild(res) {
    var b = res.querySelector('[data-buildnow]');
    if (!b) return;
    var say = res.querySelector('[data-buildsay]');
    b.onclick = function () {
      Parseh.buildBook(b.getAttribute('data-buildnow'), 'the PDF', {
        book: b.getAttribute('data-book') || '', button: b,
        say: function (msg, err) {
          say.textContent = msg;
          say.className = 'stat' + (err ? ' warn' : '');
        }
      });
    };
  }
  // The two doors' shared tail: the library card and the PDF are written by
  // other programs, and when one of them fails the book is still on disk.
  // Both keys came back before this and were dropped on the floor.
  function afterWrote(j) {
    var h = '';
    if (j.reader && !j.reader.ok)
      h += '<div class="note bad"><b>The reader was not built &mdash; the book is on disk, ' +
        'the page to read it is not:</b> ' + esc(j.reader.error || 'tex2html failed') + '</div>';
    if (j.library && !j.library.ok)
      h += '<div class="note warn"><b>The book is written, but the library page was not ' +
        'rewritten</b> &mdash; it will appear after the next build. ' +
        esc(j.library.error || '') + '</div>';
    return h;
  }
  // on the activity list while the server writes the book and builds its
  // reader (lib/activity.js, through parseh.js)
  function working(label) {
    return Parseh.working ? Parseh.working(label)
      : {url: function (u) { return u; }, end: function () {}};
  }
  // Every other button on this page copies something for you to run; these
  // two write the book itself, so what they say back is the endpoint's own
  // sentence -- a title that leaves no ascii for a directory name, a slug
  // already taken, a paragraph LaTeX cannot set -- never "failed".
  $('mkempty').onclick = function () {
    var text = val('chtext');
    if (!val('title').trim()) { Parseh.toast('the title comes first', true); $('title').focus(); return; }
    if (!text.trim()) { Parseh.toast('paste the chapter first', true); $('chtext').focus(); return; }
    var res = $('eresult'); res.hidden = true;
    $('estat').textContent = 'drafting…'; $('mkempty').disabled = true;
    var act = working('Writing the book ' + val('title').trim());
    fetch(act.url('/books/__empty'), {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({lang: val('lang'), gloss: val('gloss'), variety: val('variety'),
        text: text, slug: val('slug').trim(),
        title: val('title').trim(), title_latin: val('title_latin').trim(),
        title_en: val('title_en').trim(), author: val('author').trim(),
        author_latin: val('author_latin').trim(), year: val('year').trim(),
        blurb: val('blurb').trim(), how: val('how')})})
      .then(function (r) { return r.json(); })
      .then(function (j) {
        act.end(!!j.ok);
        $('mkempty').disabled = false; $('estat').textContent = ''; res.hidden = false;
        gate();
        if (!j.ok) {
          res.innerHTML = '<div class="note bad"><b>' + esc(j.error || 'failed') + '</b></div>';
          res.scrollIntoView({behavior: 'smooth', block: 'nearest'});
          return;
        }
        var href = '/books/' + j.folder + '/' + j.slug + '/reader/';
        var h = '<div class="note good"><b>Drafted.</b> ' + j.paragraphs + ' paragraphs, ' +
          j.sentences + ' sentences, ' + j.chunks + ' blank chunks, in <code>books/' +
          esc(j.folder) + '/' + esc(j.slug) + '/</code>. <a href="' + esc(href) +
          '"><b>Open the reader &rarr;</b></a>' +
          // the name draft.py gave it: the transliterated title, else the slug
          buildRow(j.folder, j.slug, val('title_latin').trim() || j.slug) + '</div>';
        h += afterWrote(j);
        res.innerHTML = h;
        wireBuild(res);
        res.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        // where the glossing is actually done; the library page lists it at
        // once, and the PDF waits for the button above or the next build
        if (!j.reader || j.reader.ok) location.href = href;
      })
      .catch(function (e) { act.end(false); $('mkempty').disabled = false; $('estat').textContent = '';
        gate(); Parseh.toast(String(e), true); });
  };
  // Onto a book that is already here.  It posts to the BOOK's own address --
  // the select carries it -- so no slug travels in a body and the route
  // resolves it exactly as __delete does.
  // THE TEXT GOES AS A FILE OR AS PASTED TEXT, to one of two doors: __append (blank chunks, glossed by the
  // person) or, for a book an agent makes, __making/part (a part the agent takes).  A file is the body,
  // named in the query with its page range; the agent's door reopens a finished making first.
  function sendText(into, file, text, agent, act) {
    var where = addWhere(), door = into + (agent ? '/__making/part' : '/__append'), post = function (url, init) {
      return fetch(url, init).then(function (r) { return r.json(); });
    };
    var go = function () {
      if (file)
        return post(act.url(door + '?name=' + encodeURIComponent(file.name) + '&pages=' + encodeURIComponent(val('appages').trim()) +
                            '&chapter=' + where + '&how=' + encodeURIComponent(val('ahow'))),
                    {method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: file});
      return post(act.url(door), {method: 'POST', headers: {'Content-Type': 'application/json'},
                                  body: JSON.stringify({text: text, how: val('ahow'), chapter: where})});
    };
    if (agent && intoState() === 'finished')
      return post(into + '/__making/reopen', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'})
        .then(function (o) { if (!o.ok) return o; return go(); });
    return go();
  }
  if ($('addto')) $('addto').onclick = function () {
    var text = val('aptext'), into = val('addinto'), file = $('apfile').files[0], agent = byAgent();
    if (!into) { Parseh.toast('there is no book here to add to yet', true); return; }
    if (!text.trim() && !file) { Parseh.toast('paste the text, or choose a file, first', true); $('aptext').focus(); return; }
    var res = $('addresult'); res.hidden = true;
    $('addstat').textContent = 'adding…'; $('addto').disabled = true;
    var act = working('Adding text to the book'), reopened = agent && intoState() === 'finished';
    sendText(into, file, text, agent, act)
      .then(function (j) {
        act.end(!!j.ok);
        $('addto').disabled = false; $('addstat').textContent = ''; res.hidden = false;
        gate();
        if (!j.ok) {
          res.innerHTML = '<div class="note bad"><b>' + esc(j.error || 'failed') + '</b></div>';
          res.scrollIntoView({behavior: 'smooth', block: 'nearest'});
          return;
        }
        var href = into + '/reader/';
        var parts = into.replace(/^\/books\//, '').split('/');
        if (j.part) {
          // handed to the agent: nothing is cut or written here, the agent does it from the part
          res.innerHTML = '<div class="note good"><b>Added as part ' + j.part.n + '.</b> The agent takes it ' +
            'before its next batch' + (reopened ? ' &mdash; the making was reopened: tell it to carry on' : '') +
            '. It goes ' + (j.part.chapter === 'auto' ? 'where the agent decides' : j.part.chapter === 'new' ? 'in a chapter of its own' :
              'on in the last chapter') + '.<div class="row"><a class="wbtn" href="' + esc(href) +
            '">Open the reader &rarr;</a><button type="button" class="wbtn quiet" id="addmore">Add another part</button></div></div>';
          var more = $('addmore');
          if (more) more.onclick = function () { val('aptext', ''); $('apfile').value = ''; save(); ticks(); addNotes();
                                                 $('aptext').focus(); res.hidden = true; };
          if (reopened) { var o = $('addinto').options[$('addinto').selectedIndex]; if (o) o.setAttribute('data-state', 'making'); applyWho(); }
          res.scrollIntoView({behavior: 'smooth', block: 'nearest'});
          return;
        }
        var h = '<div class="note good"><b>Added.</b> ' + j.paragraphs + ' paragraphs, ' +
          j.sentences + ' sentences, ' + j.chunks + ' blank chunks, ' +
          (j.where === 'new' ? 'as chapter ' : 'onto the end of chapter ') + j.chapter + '.' +
          (j.pdf_stale ? '<span class="fieldnote">the PDF is out of date until the next build</span>' : '') +
          '<div class="row">' +
          '<a class="wbtn" href="' + esc(href) + '">Open the reader &rarr;</a>' +
          '<button type="button" class="wbtn quiet" id="addmore">Add another chapter</button>' +
          '</div>' +
          (parts.length >= 2 ? buildRow(parts[0], parts[1], intoName()) : '') +
          '</div>';
        h += afterWrote(j);
        res.innerHTML = h;
        wireBuild(res);
        // NO REDIRECT HERE, deliberately.  This way's rhythm is repeated
        // appends, and jumping to the reader broke it every time -- and hid
        // the counts, which were only ever seen when something failed.  The
        // reader is one click away.
        var again = $('addmore');
        if (again) again.onclick = function () {
          val('aptext', ''); $('apfile').value = ''; save(); ticks(); addNotes(); $('aptext').focus();
          res.hidden = true;
        };
        res.scrollIntoView({behavior: 'smooth', block: 'nearest'});
      })
      .catch(function (e) { act.end(false); $('addto').disabled = false; $('addstat').textContent = '';
        gate(); Parseh.toast(String(e), true); });
  };

  /* ---------------- way 3: an agent makes it, here ---------------- */
  // The book's facts as the server takes them.  The half title is set in
  // capitals, and the registry's code is the locale that decides which:
  // Turkish uppercases bir to BİR and kış to KIŞ.  The browser carries that
  // rule and Python's upper() does not, so it is sent already made.
  function bookFields(originalName) {
    var L = langRec();
    var f = {lang: L.code, gloss: val('gloss'), slug: val('slug').trim(), title: val('title').trim(),
             title_latin: val('title_latin').trim(), title_en: val('title_en').trim(),
             author: val('author').trim(), author_latin: val('author_latin').trim(),
             year: val('year').trim(), blurb: val('blurb').trim(), pages: val('pages').trim(),
             title_latin_upper: (val('title_latin').trim() || slugNow()).toLocaleUpperCase(L.code),
             original: originalName || ''};
    // the scheme of the transliteration is a fact of the book, written into it; the row says which
    var chosen = instructions ? instructions.options() : {};
    if (chosen.translit) f.translit = chosen.translit;
    return f;
  }
  // THE INSTRUCTIONS, WHAT THE SERVER WOULD WRITE INTO THE FOLDER: the same
  // text the folder gets, produced by lib/making.py, so this page fills none
  // of its placeholders and cannot say one thing while the folder says another.
  function getInstructions() {
    var f = $('original').files[0], chosen = instructions ? instructions.options() : {};
    return fetch('/books/__making/instructions', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({book: bookFields(f ? f.name : ''), reference: val('ref'),
                            examples: !!$('examples').checked, marks: chosen.marks || null,
                            prompt: instructions ? instructions.promptId() : ''})})
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j.ok) throw new Error(j.error || 'the instructions could not be made');
        // the request for the parseh-book skill, which the row offers beside the copy of the instructions
        if (instructions && instructions.skillOf) instructions.skillOf(j.skill || null);
        return j.text;
      });
  }
  // THE ONE SEAM FOR THE LLM ROW (lib/llmrow.js, brief 3.6): everything a
  // person presses to hand the instructions over is drawn by this function
  // alone -- the prompt menu of their own prompts, the size line before the
  // copy, the choices (the scheme of the transliteration, the short vowels of a
  // language that has them), the skill request -- and each of them is the
  // row's, never this page's.  `getText()` answers the text as a promise;
  // what the row shows and copies is what it returns, and the folder gets the
  // same text, because the server makes both.
  function mountInstructionsRow(mount, getText) {
    mount.innerHTML =
      '<details id="ishow"><summary>the instructions, as they will be written</summary>' +
      '<pre class="cmd wrap" id="itext"></pre></details><div id="irow"></div>';
    var box = mount.querySelector('#itext'), det = mount.querySelector('#ishow');
    var none = {options: function () { return {}; }, promptId: function () { return ''; },
                setLang: function () {}, refresh: function () { return Promise.resolve(''); },
                invalidate: function () {}, open: function () { return false; }};
    if (!window.ParsehLLMRow) {
      mount.querySelector('#irow').textContent = 'the instructions helper could not be loaded';
      return none;
    }
    var row = ParsehLLMRow.mount(mount.querySelector('#irow'), {
      surface: 'book-new', lang: langRec().code, cls: 'wbtn quiet',
      label: 'copy the instructions',
      ids: {copy: 'icopy', size: 'ilen', say: 'icopysay'},
      remind: 'paste them into an agent that does not read AGENTS.md from the folder.',
      getText: function () {
        return getText().then(function (t) { box.textContent = t; return t; });
      },
      box: function () { det.open = true; return box; },
      // a size to say as soon as there is something to say it of: the sheet open, or a title written
      measure: function () { return det.open || !!val('title').trim(); },
      onOption: function () { refreshSoon(); }
    });
    det.addEventListener('toggle', function () { if (det.open) row.refresh(); });
    return {
      refresh: function () { return row.refresh(); }, invalidate: function () { row.invalidate(); },
      open: function () { return det.open; }, setLang: function (code) { row.setLang(code); },
      options: function () { return row.options(); },
      // the person's own prompt for the instructions, chosen in the row's menu ('' is Parseh's)
      promptId: function () { return typeof row.promptId === 'function' ? row.promptId() : ''; },
      skillOf: function (spec) { if (typeof row.skillOf === 'function') row.skillOf(spec); }
    };
  }
  var instructions = null;
  var refreshTimer = null, seenThen = '';
  // the page asks for this on every change of anything; what is held is dropped only when what the
  // instructions are made from has changed (a press of the copy button changes none of it)
  function madeFrom() {
    var f = $('original').files[0];
    return JSON.stringify([bookFields(f ? f.name : ''), val('ref'), !!$('examples').checked,
                           instructions ? instructions.options() : {}, instructions ? instructions.promptId() : '']);
  }
  function refreshSoon() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(function () {
      if (!instructions) return;
      var seen = madeFrom();
      if (seen === seenThen) return;
      seenThen = seen;
      instructions.invalidate();
    }, 400);
  }
  instructions = mountInstructionsRow($('instrmount'), getInstructions);
  seenThen = madeFrom();
  $('lang').addEventListener('change', function () { instructions.setLang(val('lang')); });
  // the folder is made from the file the person picked, sent as the body of the
  // request -- so it is copied by the server, on this computer or on Windows,
  // with no path typed anywhere -- and the book's facts ride in the address
  $('mkfolder').onclick = function () {
    var file = $('original').files[0];
    if (!val('title').trim()) { Parseh.toast('the title comes first', true); $('title').focus(); return; }
    if (!file) { Parseh.toast('choose the original first', true); $('original').focus(); return; }
    var res = $('mkresult'); res.hidden = true;
    $('mkstat').textContent = 'making the folder…'; $('mkfolder').disabled = true;
    var act = working('Making the folder of ' + val('title').trim());
    var facts = bookFields(file.name);
    facts.reference = val('ref');
    facts.examples = !!$('examples').checked;
    facts.more_coming = !$('alltext').checked;
    // what the row says of the short vowels, and the person's own prompt for the instructions, if one is chosen
    var chosen = instructions.options();
    if (chosen.marks) facts.marks = chosen.marks;
    if (instructions.promptId()) facts.prompt = instructions.promptId();
    fetch(act.url('/books/__make?name=' + encodeURIComponent(file.name) +
                  '&book=' + encodeURIComponent(JSON.stringify(facts))),
      {method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: file})
      .then(function (r) { return r.json(); })
      .then(function (j) {
        act.end(!!j.ok);
        $('mkstat').textContent = ''; res.hidden = false;
        gate();
        if (!j.ok) {
          res.innerHTML = '<div class="note bad"><b>' + esc(j.error || 'failed') + '</b></div>';
          res.scrollIntoView({behavior: 'smooth', block: 'nearest'});
          return;
        }
        var base = '/books/' + j.dir;
        D.books.push({path: base, rel: j.dir, folder: j.folder, dirname: j.slug, lang: j.language,
                      making: true, state: 'making', name: val('title_latin').trim() || j.slug});
        render();
        gate();
        res.innerHTML = '<div class="note good"><b>The folder is made</b>, and the book is on ' +
          '<a href="/books/">the library page</a>, marked <b>being made</b>.' +
          '<code class="bigpath">' + esc(j.path) + '</code>' +
          '<div class="row"><button type="button" class="wbtn quiet" id="mkcopy">copy the path</button>' +
          // opening a folder is the computer's own act (a file manager on its screen): another device is told so
          (j.here ? '<button type="button" class="wbtn quiet" id="mkopen">open the folder</button>' : '') +
          '<a class="wbtn" href="' + esc(base) + '/reader/">open the reader &rarr;</a></div>' +
          (j.here ? '' : '<span class="fieldnote" id="mkopensaid">' + esc(j.open_said) + '</span>') +
          '<p class="handover">Open this folder in the agent you use, and tell it: ' +
          '<b>read AGENTS.md and begin</b>.</p>' +
          '<span class="fieldnote">Parseh does not start an agent and does not choose one for you: ' +
          'any agent that works in a folder will do.</span></div>' + afterWrote(j);
        $('mkcopy').onclick = function () { Parseh.copy(j.path, true); };
        if ($('mkopen')) $('mkopen').onclick = function () {
          fetch(base + '/__making/open', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                          body: '{}'})
            .then(function (r) { return r.json(); })
            .then(function (o) { Parseh.toast(o.ok ? 'opened' : (o.error || 'it could not be opened'), !o.ok); })
            .catch(function (e) { Parseh.toast(String(e), true); });
        };
        res.scrollIntoView({behavior: 'smooth', block: 'nearest'});
      })
      .catch(function (e) { act.end(false); $('mkstat').textContent = ''; gate(); Parseh.toast(String(e), true); });
  };

  /* ---------------- wiring ---------------- */
  FIELDS.forEach(function (k) {
    var el = $(k);
    if (!el) return;
    el.addEventListener('input', function () { save(); ticks(); render(); });
    el.addEventListener('change', function () { save(); ticks(); render(); });
  });
  SAVE_ONLY.forEach(function (k) {
    var el = $(k);
    if (!el) return;
    el.addEventListener('input', function () { save(); ticks(); });
    el.addEventListener('change', function () { save(); ticks(); });
  });
  ['original', 'examples'].forEach(function (k) {
    $(k).addEventListener('change', function () { save(); ticks(); render(); });
  });
  ['addwhere_new', 'addwhere_last', 'addwhere_auto'].forEach(function (k) {
    var el = $(k);
    if (el) el.addEventListener('change', function () { save(); });
  });
  ['addwho_agent', 'addwho_me'].forEach(function (k) {
    var el = $(k);
    if (el) el.addEventListener('change', function () { applyWho(); save(); });
  });
  ['apfile', 'appages'].forEach(function (k) {
    var el = $(k);
    if (el) { el.addEventListener('input', function () { ticks(); addNotes(); });
              el.addEventListener('change', function () { ticks(); addNotes(); }); }
  });
  if ($('addinto')) $('addinto').addEventListener('change', function () { applyInto(); });
  $('lang').addEventListener('change', function () {
    applyLang(); applyGloss(); save(); ticks(); render(); });
  $('gloss').addEventListener('change', function () { applyGloss(); save(); render(); });
  Array.prototype.forEach.call(document.querySelectorAll('.hbtn'), function (b) {
    b.onclick = function () {
      var box = $(b.getAttribute('aria-controls'));
      var open = box.hidden;
      box.hidden = !open;
      b.setAttribute('aria-expanded', String(open));
    };
  });
  // THE ORDER MATTERS, now that render() is gated.  The draft is restored and
  // the language and the gloss are applied -- and only then is a way chosen,
  // which performs the single gated render.
  applyLang();
  applyGloss();
  applyInto();
  var want = (location.search.match(/[?&]path=([a-z]+)/) || [])[1] || saved.path || '';
  choose(want, false, false);
})();
</script>
</body></html>
'''