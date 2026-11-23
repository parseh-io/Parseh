#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build an Anki .apkg from a deck directory under anki/.

    python3 lib/anki_export.py anki/<folder>/<deck-slug> [out.apkg]

A deck directory is what the player's card dashboard writes, filed under
its language's folder (docs/languages.md section 2):

    anki/<folder>/<slug>/deck.json          {"name": …, "lang": "fa", "id": …}
    anki/<folder>/<slug>/cards/<id>.json    one card per file -- the ground truth
    anki/<folder>/<slug>/media/<id>-*.jpg   the screenshots those cards reference
    anki/<folder>/<slug>/media/<id>-*-audio.<ext>   and their recordings

The directory carries the language, so build_deck takes the path and asks
nothing else; the package it writes is anki/build/<folder>-<slug>.apkg,
named after both because two languages may hold a deck of the same name.
A deck lying directly under anki/ is the layout from before languages and
still builds, its cards read as Persian unless they say otherwise.

The .apkg is the legacy schema-11 package (a zip holding a small SQLite
collection plus numbered media files) that every Anki since 2.1 imports.
Each note's GUID is fixed at the moment the card is saved, so re-importing
a rebuilt deck UPDATES the existing notes instead of duplicating them:
edit a card's JSON, rebuild, re-import, and the note follows.  (Deleting
a card's JSON removes it from future builds, but Anki never deletes notes
on import -- prune those in Anki itself.)  The flip side: an import also
OVERWRITES fields edited inside Anki, so if the deck has been edited
there, pull those edits home first with lib/sync_apkg.py, then rebuild.
Cards marked anki-owned by that sync are left out of the build entirely.

Note types, one pair per language (docs/languages.md section 4).  A card
says which language it is in (`lang`, a registry code; absent means
Persian, the toolbox's first language) and which kind it is (`vocab` or
`opposites`), and the pair picks the note type.  Persian's two are the
historical ones -- "Frank YouTube Persian": Persian / Transliteration /
English / Context / Notes / FrontImage / BackImage / Source / Reverse /
ReverseOnly, and "Frank Persian Opposites" -- and their ids, names,
fields and templates are kept byte for byte, because a note type's shape
can never change once notes have been studied with it (anki/README.md).
Every other language gets a pair of its own from the registry's `anki`
record: the same fields with the text field named after the language
("Japanese"), plus a Reading field (and OppositeReading) for a language
with a kana-like reading.  MODELS below is the one table of them all;
import_apkg, sync_apkg, notetypes and check_shape read it.

Template 1 asks <language> -> the meaning; template 2 asks the meaning ->
<language> and exists only while the Reverse field is non-empty (the
bidirectional checkbox).  The language's bundled web face rides along in
the package when it has one (Vazirmatn for Persian, Noto Naskh Arabic
for Arabic), so the cards wear the same face as the reader; a language
that bundles none relies on the device's own fonts.

THE MEANING IS NOT NECESSARILY ENGLISH.  The field is called "English"
and always will be -- a note type's field list is half of what Anki
matches it by, so renaming it would fork a second note type in every
collection that holds the old one -- but what is IN it is written in the
card's gloss language (`gloss`, a code languages.gloss accepts; absent
means English, which is what every card made before the field existed
means).  What that changes is the TEMPLATE and the stylesheet, which
Anki does update in place on import: the divs holding the meaning and
the notes carry that language's lang and dir, so an Italian meaning
hyphenates as Italian and an Arabic one runs right to left.  With an
English gloss every note type comes out byte for byte what it always
was.

Standard library only: sqlite3, zipfile, json.
"""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.realpath(__file__))
# the registry lives in the toolbox's lib/, two levels up.  Under the
# server that directory is already on sys.path; run as a script from
# youtube/ (or from the repository root) it is not, so add it here --
# appended, not inserted, so the server's own ordering is never disturbed
_ROOT_LIB = os.path.normpath(os.path.join(HERE, "..", "..", "lib"))
try:
    import languages
except ImportError:
    if _ROOT_LIB not in sys.path:
        sys.path.append(_ROOT_LIB)
    import languages

MODEL_ID = 1724563200001
# ReverseOnly was added (last, matching the live Anki collection exactly)
# to hold the third direction: non-empty means the Persian -> English card
# is suppressed and only English -> Persian is asked -- for a note like
# "body -> tan / badan" whose forward direction is asked by two separate
# per-word notes instead
FIELD_NAMES = ["Persian", "Transliteration", "English", "Context", "Notes",
               "FrontImage", "BackImage", "Source", "Reverse", "ReverseOnly"]
# A second, separate note type for OPPOSITES cards ("what is the opposite
# of X?").  Separate on purpose: adding fields or templates to an existing
# model would make Anki refuse to update the notes already studied with it,
# so the vocab model above must never change shape -- see anki/README.md.
OPP_MODEL_ID = 1724563200002
OPP_FIELD_NAMES = ["Persian", "Transliteration", "Opposite", "OppositeTr",
                   "Notes", "FrontImage", "BackImage", "Source", "Reverse"]


def _field_list(L, kind):
    """The field names of a language's note type of this kind, in order:
    the text field named after the language, then (for a language with a
    reading) Reading right after it, and OppositeReading right after
    Opposite.  For Persian this yields FIELD_NAMES / OPP_FIELD_NAMES
    exactly, which _build_models checks."""
    field = L.anki.get("field") or L.name
    if kind == "opposites":
        out = [field] + (["Reading"] if L.reading else []) \
            + ["Transliteration", "Opposite"] \
            + (["OppositeReading"] if L.reading else []) \
            + ["OppositeTr", "Notes", "FrontImage", "BackImage", "Source",
               "Reverse"]
    else:
        out = [field] + (["Reading"] if L.reading else []) \
            + ["Transliteration", "English", "Context", "Notes",
               "FrontImage", "BackImage", "Source", "Reverse", "ReverseOnly"]
    return out


def _build_models():
    """{mid: {"lang", "kind", "fields", "name", "field"}} for every
    language in the registry -- the ONE table of this toolbox's note
    types.  Persian's two entries are pinned to the historical constants
    above, and the table refuses to load if the registry ever disagreed
    with them: a drifted Persian model would fork a second note type in
    every collection that holds the old one."""
    out = {}
    for L in languages.LANGS.values():
        a = L.anki
        for kind, mid_key, name_key in (("vocab", "vocab_model", "vocab_name"),
                                        ("opposites", "opposites_model",
                                         "opposites_name")):
            mid = a.get(mid_key)
            if not mid:
                continue                # a language without Anki note types
            out[int(mid)] = {"lang": L.code, "kind": kind,
                             "fields": _field_list(L, kind),
                             "name": a.get(name_key)
                             or "Frank %s%s" % (L.name, " Opposites"
                                                 if kind == "opposites" else ""),
                             "field": a.get("field") or L.name}
    fa_v, fa_o = out.get(MODEL_ID), out.get(OPP_MODEL_ID)
    if (not fa_v or fa_v["fields"] != FIELD_NAMES or fa_v["lang"] != "fa"
            or not fa_o or fa_o["fields"] != OPP_FIELD_NAMES
            or fa_o["lang"] != "fa"):
        raise SystemExit("lib/languages.json's Persian anki record no longer "
                         "matches the historical note types %d / %d -- "
                         "their shape can never change (anki/README.md)"
                         % (MODEL_ID, OPP_MODEL_ID))
    return out


MODELS = _build_models()


def lang_for_code(v, where="card"):
    """The language record a card's `lang` value names -- the ONE reading
    of that value, shared by the build, the previews, the store and the
    sync.  Absent or empty means Persian: every card made before
    languages were declared says nothing.  Anything else must be a
    registry code (case and surrounding space forgiven, as the registry
    does).  A value that is not one -- a hand edit gone wrong, "xx", a
    number -- is refused with a ValueError rather than filed as Persian:
    a Japanese card built into the Persian note type would lose its kana
    and, once studied, come back from the next sync as Persian for good.
    `where` names the card in the message."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return languages.get_or_default(None)
    if isinstance(v, str):
        try:
            return languages.get(v)
        except KeyError:
            pass
    raise ValueError("%s: unknown language %r (known: %s)"
                     % (where, v, ", ".join(languages.CODES)))


def lang_of(card):
    """The card's language record -- Persian when it says nothing,
    ValueError when it says something that is not a language."""
    if not isinstance(card, dict):
        return languages.get_or_default(None)
    return lang_for_code(card.get("lang"),
                         "card %s" % (card.get("id") or "(unnamed)"))


def gloss_for_code(v, where="card"):
    """The gloss language a card's `gloss` value names -- what its meaning
    and its notes are WRITTEN in, which is not what the card teaches.

    Absent or empty means English: every card made before the field
    existed says nothing and meant English.  Anything else must be a code
    languages.gloss accepts -- the languages the toolbox teaches plus the
    prose-only ones -- and a value that is not one is refused rather than
    quietly taken as English, for lang_for_code's reason turned round: a
    card built as English would carry no lang at all, and its meaning
    would be hyphenated and laid out as English on every device that
    reviews it, with nothing on the card to say so."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return languages.gloss(None)
    if isinstance(v, str):
        try:
            return languages.gloss(v)
        except KeyError:
            pass
    raise ValueError("%s: unknown gloss language %r (a gloss may be written "
                     "in: %s)" % (where, v, ", ".join(languages.GLOSS_CODES)))


def gloss_of(card):
    """The card's gloss language -- English when it says nothing."""
    if not isinstance(card, dict):
        return languages.gloss(None)
    return gloss_for_code(card.get("gloss"),
                          "card %s" % (card.get("id") or "(unnamed)"))


def model_for(card):
    """The note type id a card builds into: from its language (`lang`,
    default Persian) and its kind."""
    L = lang_of(card)
    return int(L.anki["opposites_model" if kind_of(card) == "opposites"
                      else "vocab_model"])


# What the LIVE collection says the note types look like -- their CSS and
# their templates -- captured by a sync or a bootstrap import (see
# lib/notetypes.py).  A note type's appearance lives in the note type, so
# no card file can hold it; without this the constants below would be
# re-asserted over every restyling done inside Anki.  The constants stay
# as the fallback for a store that has never seen an export.
OVERRIDES_NAME = "notetypes.json"


def load_overrides(anki_dir):
    """{mid: snapshot} from anki/notetypes.json; {} when there is none."""
    try:
        with open(os.path.join(anki_dir, OVERRIDES_NAME),
                  encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                if isinstance(v, dict):
                    out[int(k)] = v
            except (TypeError, ValueError):
                continue
    return out


def _str_or(v, fallback):
    """A captured value counts when it is a string -- EMPTY INCLUDED.

    Emptiness is a real answer: a Styling box cleared inside Anki must
    stay cleared, not silently collect the stylesheet below again.  Only
    a missing or non-string value falls back, which also keeps a
    malformed capture from reaching .replace() and wedging the preview.
    """
    return v if isinstance(v, str) else fallback


def _tmpl_pair(ov, mid, ord_, qfmt, afmt):
    """The (question, answer) template for one direction: the captured
    one when the collection has taught us it, else the built-in."""
    snap = (ov or {}).get(mid) or {}
    tmpls = snap.get("templates")
    if isinstance(tmpls, list) and len(tmpls) > ord_:
        t = tmpls[ord_]
        if isinstance(t, dict) and (isinstance(t.get("qfmt"), str)
                                    or isinstance(t.get("afmt"), str)):
            return (_str_or(t.get("qfmt"), qfmt),
                    _str_or(t.get("afmt"), afmt))
    return qfmt, afmt


def _css_for(ov, mid, G=None):
    return _str_or(((ov or {}).get(mid) or {}).get("css"), model_css(mid, G))


def _name_for(ov, mid, default):
    """The note type's own name, when the collection has taught us one --
    otherwise a rebuild would quietly revert a rename made in Anki, the
    very kind of overwrite this capture exists to stop."""
    n = ((ov or {}).get(mid) or {}).get("name")
    return n if isinstance(n, str) and n.strip() else default


def kind_of(card):
    """A card's note type: "opposites" or (default) "vocab"."""
    return "opposites" if card.get("kind") == "opposites" else "vocab"


def is_reverse_only(card):
    """True for a card asking only English -> Persian.  Vocab only: the
    opposites model has no ReverseOnly field."""
    return bool(card.get("reverse_only")) and kind_of(card) != "opposites"


# ---- fonts ---------------------------------------------------------------
# A language's main web face travels inside the package under a leading
# underscore (Anki's convention for media that is not a note's own), so
# the cards wear the reader's face on every device.  Only a language
# whose registry entry lists a web file has one; the others rely on the
# device's fonts, which every phone has for its own script.  The file is the
# toolbox's own, in lib/fonts/ (with its licence there); the copies the video
# player used to keep beside this module are gone.
FONT_DIRS = (os.path.join(_ROOT_LIB, "fonts"),)


def font_file(L):
    """The bare file name of the language's main web face
    ("Vazirmatn.woff2"), or None when it ships none."""
    files = (L.fonts or {}).get("web_files") or []
    return files[0] if files else None


def font_media_name(L):
    """The name the face has INSIDE the package ("_Vazirmatn.woff2"), or
    None -- the same string the model's @font-face names."""
    fn = font_file(L)
    return ("_" + fn) if fn else None


def font_path(L):
    """Where the face is on disk, or None when the language has none or
    the file is missing (the build then goes on without it, as it always
    did when the woff2 was absent)."""
    fn = font_file(L)
    if not fn:
        return None
    for d in FONT_DIRS:
        p = os.path.join(d, fn)
        if os.path.exists(p):
            return p
    return None


def _css_family(L):
    """The font-family the model's CSS sets on the text.  Persian keeps
    its historical two-name stack byte for byte (the model's CSS is part
    of what a Persian collection already holds); the others take the
    registry's stack, whose first name is the bundled face when there is
    one."""
    if L.code == "fa":
        return "Vazirmatn, serif"
    return L.css_font()


def _css_face(L):
    """The @font-face line for the bundled face, or nothing."""
    media = font_media_name(L)
    if not media:
        return ""
    fam = (L.fonts or {}).get("main") or L.name
    if not re.match(r"^[A-Za-z0-9_-]+$", fam):
        fam = '"%s"' % fam
    return '@font-face { font-family: %s; src: url("%s"); }\n' % (fam, media)


SCHEMA = """
CREATE TABLE col (
    id integer primary key, crt integer not null, mod integer not null,
    scm integer not null, ver integer not null, dty integer not null,
    usn integer not null, ls integer not null, conf text not null,
    models text not null, decks text not null, dconf text not null,
    tags text not null
);
CREATE TABLE notes (
    id integer primary key, guid text not null, mid integer not null,
    mod integer not null, usn integer not null, tags text not null,
    flds text not null, sfld integer not null, csum integer not null,
    flags integer not null, data text not null
);
CREATE TABLE cards (
    id integer primary key, nid integer not null, did integer not null,
    ord integer not null, mod integer not null, usn integer not null,
    type integer not null, queue integer not null, due integer not null,
    ivl integer not null, factor integer not null, reps integer not null,
    lapses integer not null, left integer not null, odue integer not null,
    odid integer not null, flags integer not null, data text not null
);
CREATE TABLE revlog (
    id integer primary key, cid integer not null, usn integer not null,
    ease integer not null, ivl integer not null, lastIvl integer not null,
    factor integer not null, time integer not null, type integer not null
);
CREATE TABLE graves (
    usn integer not null, oid integer not null, type integer not null
);
CREATE INDEX ix_notes_usn on notes (usn);
CREATE INDEX ix_cards_usn on cards (usn);
CREATE INDEX ix_revlog_usn on revlog (usn);
CREATE INDEX ix_cards_nid on cards (nid);
CREATE INDEX ix_cards_sched on cards (did, queue, due);
CREATE INDEX ix_revlog_cid on revlog (cid);
CREATE INDEX ix_notes_csum on notes (csum);
"""

# the cards wear the reader's clothes -- same greys, same face as the
# reader.  One sheet for every language: %(face)s is the @font-face of
# the bundled font (empty when there is none), %(font)s the stack,
# %(dir)s "direction: rtl; " for a right-to-left language and nothing
# for the others.  Filled for Persian this is, byte for byte, the sheet
# the Persian note types have always carried (CSS below); the .kana rule
# is appended only for a language with a reading, so Persian's sheet
# does not gain a rule its collection has never had.
CSS_TEMPLATE = """%(face)s.card { font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 17px; text-align: center;
  color: #1a1a1a; background-color: #faf9f7; }
.card.nightMode { color: #e8e6e3; background-color: #14151a; }
.fa { font-family: %(font)s; font-size: 34px; line-height: 1.9;
  %(dir)s}
.ctx { font-family: %(font)s; font-size: 21px; line-height: 1.9;
  %(dir)scolor: #6b6b6b; margin-top: 10px; }
.nightMode .ctx { color: #9a978f; }
.tr { font-style: italic; color: #6b6b6b; font-size: 15px; margin-top: 8px; }
.nightMode .tr { color: #9a978f; }
.en { font-size: 20px; }
.notes { font-size: 14px; color: #6b6b6b; margin-top: 12px; text-align: left;
  display: inline-block; max-width: 40em; line-height: 1.5; }
.nightMode .notes { color: #9a978f; }
img { max-width: 100%%; max-height: 46vh; border-radius: 8px; margin: 8px 0; }
.src { font-size: 12px; color: #a8a8a8; margin-top: 14px; }
.src a { color: #7a5c3e; text-decoration: none; }
.nightMode .src a { color: #c9a227; }
hr#answer { border: none; border-top: 1px solid #e2ded8; margin: 14px 0; }
.nightMode hr#answer { border-top-color: #2a2c33; }
.q { font-size: 46px; letter-spacing: .1em; text-transform: uppercase;
  color: #6b6b6b; margin-bottom: 8px; }
.nightMode .q { color: #9a978f; }
"""

# the reading line (kana) sits right under the text, in the same face
# and a little smaller, as the reader's gloss shows it
CSS_KANA = """.kana { font-family: %(font)s; font-size: 17px; line-height: 1.6;
  color: #6b6b6b; margin-top: 2px; }
.nightMode .kana { color: #9a978f; }
"""

# The one thing on a card that is aligned to a side instead of centred is
# the notes block, and the sheet aligns it left.  The templates give the
# meaning and the notes the gloss language's dir, which turns the text
# round -- but text-align: left survives that and would leave every line
# of an Arabic note starting at the far edge and ending in mid-air.  Only
# a right-to-left gloss needs the rule, so every sheet in the toolbox
# today comes out byte for byte the sheet it has always been.
CSS_GLOSS_RTL = """.notes { text-align: right; }
"""


def _is_english(G):
    """True for the gloss language every card had before there was a field
    to say otherwise.  The templates and the sheet are then untouched, which
    is what keeps the note types of a Persian collection byte for byte what
    Anki already holds."""
    return G is None or G.code == languages.DEFAULT_GLOSS


def lang_css(L, G=None):
    """The stylesheet of this language's note types, for a deck whose
    meanings are written in G (English when not said)."""
    css = CSS_TEMPLATE % {"face": _css_face(L), "font": _css_family(L),
                          "dir": "direction: rtl; " if L.rtl else ""}
    if L.reading:
        css += CSS_KANA % {"font": _css_family(L)}
    if not _is_english(G) and G.rtl:
        css += CSS_GLOSS_RTL
    return css


def model_css(mid, G=None):
    return lang_css(languages.get(MODELS[mid]["lang"]), G)


# the Persian sheet as it has always been -- kept under its old name for
# the modules that read it (and the fixture test compares it to the old
# exporter's literal)
CSS = lang_css(languages.get("fa"))

# The templates, written once for Persian; a language's own are these
# with {{Persian}} -> {{<its field>}} and, for a language with a reading,
# a kana line right under each text div (see lang_templates)
QFMT1 = """{{^ReverseOnly}}
{{#FrontImage}}<div>{{FrontImage}}</div>{{/FrontImage}}
<div class="fa">{{Persian}}</div>
{{/ReverseOnly}}"""

AFMT1 = """{{FrontSide}}
<hr id=answer>
<div class="en">{{English}}</div>
{{#Transliteration}}<div class="tr">{{Transliteration}}</div>{{/Transliteration}}
{{#Context}}<div class="ctx">{{Context}}</div>{{/Context}}
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
{{#BackImage}}<div>{{BackImage}}</div>{{/BackImage}}
{{#Source}}<div class="src">{{Source}}</div>{{/Source}}"""

QFMT2 = """{{#Reverse}}
<div class="en">{{English}}</div>
{{#BackImage}}<div>{{BackImage}}</div>{{/BackImage}}
{{/Reverse}}"""

AFMT2 = """{{FrontSide}}
<hr id=answer>
<div class="fa">{{Persian}}</div>
{{#Transliteration}}<div class="tr">{{Transliteration}}</div>{{/Transliteration}}
{{#Context}}<div class="ctx">{{Context}}</div>{{/Context}}
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
{{#FrontImage}}<div>{{FrontImage}}</div>{{/FrontImage}}
{{#Source}}<div class="src">{{Source}}</div>{{/Source}}"""

OPP_QFMT1 = """{{#FrontImage}}<div>{{FrontImage}}</div>{{/FrontImage}}
<div class="q">what is the opposite of</div>
<div class="fa">{{Persian}}</div>
{{#Transliteration}}<div class="tr">{{Transliteration}}</div>{{/Transliteration}}"""

OPP_AFMT1 = """{{FrontSide}}
<hr id=answer>
<div class="fa">{{Opposite}}</div>
{{#OppositeTr}}<div class="tr">{{OppositeTr}}</div>{{/OppositeTr}}
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
{{#BackImage}}<div>{{BackImage}}</div>{{/BackImage}}
{{#Source}}<div class="src">{{Source}}</div>{{/Source}}"""

OPP_QFMT2 = """{{#Reverse}}
{{#BackImage}}<div>{{BackImage}}</div>{{/BackImage}}
<div class="q">what is the opposite of</div>
<div class="fa">{{Opposite}}</div>
{{#OppositeTr}}<div class="tr">{{OppositeTr}}</div>{{/OppositeTr}}
{{/Reverse}}"""

OPP_AFMT2 = """{{FrontSide}}
<hr id=answer>
<div class="fa">{{Persian}}</div>
{{#Transliteration}}<div class="tr">{{Transliteration}}</div>{{/Transliteration}}
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
{{#FrontImage}}<div>{{FrontImage}}</div>{{/FrontImage}}
{{#Source}}<div class="src">{{Source}}</div>{{/Source}}"""

READING_LINE = '\n{{#Reading}}<div class="kana">{{Reading}}</div>{{/Reading}}'
OPP_READING_LINE = ('\n{{#OppositeReading}}<div class="kana">{{OppositeReading}}'
                    '</div>{{/OppositeReading}}')


def _localise(tmpl, L, G=None):
    """One Persian template made the language's own.  For Persian glossed
    in English the text comes back untouched (the field is "Persian",
    there is no reading, and the meaning needs no lang of its own), which
    is what keeps the historical templates byte for byte.

    The two divs that get G's lang and dir are the ones holding PROSE the
    reader is meant to read: the meaning and the notes.  Not the
    transliteration, which is a romanisation of the target and belongs to
    no gloss language; not the context or the opposite, which are target
    text; and not the "what is the opposite of" line, which is the
    toolbox's own chrome and stays in the one language the chrome is in.
    """
    field = L.anki.get("field") or L.name
    if L.reading:
        tmpl = tmpl.replace('<div class="fa">{{Persian}}</div>',
                            '<div class="fa">{{Persian}}</div>' + READING_LINE)
        tmpl = tmpl.replace('<div class="fa">{{Opposite}}</div>',
                            '<div class="fa">{{Opposite}}</div>'
                            + OPP_READING_LINE)
    if not _is_english(G):
        attrs = G.html_attrs()
        for cls in ("en", "notes"):
            tmpl = tmpl.replace('<div class="%s">' % cls,
                                '<div class="%s"%s>' % (cls, attrs))
    return tmpl.replace("{{Persian}}", "{{%s}}" % field)


def lang_templates(mid, G=None):
    """[(name, qfmt, afmt)] -- the two directions of this note type, with
    the built-in templates, for a deck whose meanings are written in G.

    The direction a template asks in is named after the two languages it
    actually holds, so a card asking Persian for its Italian meaning does
    not present itself in the browser as "Persian → English"."""
    m = MODELS[mid]
    L = languages.get(m["lang"])
    if m["kind"] == "opposites":
        pairs = [("Opposite of the word", OPP_QFMT1, OPP_AFMT1),
                 ("Opposite of the answer", OPP_QFMT2, OPP_AFMT2)]
    else:
        gname = "English" if _is_english(G) else G.name
        pairs = [("%s → %s" % (L.name, gname), QFMT1, AFMT1),
                 ("%s → %s" % (gname, L.name), QFMT2, AFMT2)]
    return [(n, _localise(q, L, G), _localise(a, L, G)) for n, q, a in pairs]


LATEX_PRE = ("\\documentclass[12pt]{article}\n\\special{papersize=3in,5in}\n"
             "\\usepackage[utf8]{inputenc}\n\\usepackage{amssymb,amsmath}\n"
             "\\pagestyle{empty}\n\\setlength{\\parindent}{0in}\n"
             "\\begin{document}\n")
LATEX_POST = "\\end{document}"

CONF = {"activeDecks": [1], "addToCur": True, "collapseTime": 1200,
        "curDeck": 1, "curModel": str(MODEL_ID), "dueCounts": True,
        "estTimes": True, "newBury": True, "newSpread": 0, "nextPos": 1,
        "sortBackwards": False, "sortType": "noteFld", "timeLim": 0}

DCONF = {"1": {"autoplay": True, "id": 1, "maxTaken": 60, "mod": 0,
               "name": "Default", "replayq": True, "timer": 0, "usn": 0,
               "new": {"bury": True, "delays": [1, 10],
                       "initialFactor": 2500, "ints": [1, 4, 7], "order": 1,
                       "perDay": 20, "separate": True},
               "lapse": {"delays": [10], "leechAction": 0, "leechFails": 8,
                         "minInt": 1, "mult": 0},
               "rev": {"bury": True, "ease4": 1.3, "fuzz": 0.05, "ivlFct": 1,
                       "maxIvl": 36500, "minSpace": 1, "perDay": 100}}}


def h(s):
    """Plain text -> field HTML: escaped, newlines kept as breaks."""
    s = (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace("\n", "<br>")


def _tmpl(ov, mid, ord_, name, qfmt, afmt):
    q, a = _tmpl_pair(ov, mid, ord_, qfmt, afmt)
    snap = (ov or {}).get(mid) or {}
    ts = snap.get("templates")
    t = ts[ord_] if isinstance(ts, list) and len(ts) > ord_ \
        and isinstance(ts[ord_], dict) else {}
    return {"name": t.get("name") or name, "ord": ord_,
            "qfmt": q, "afmt": a,
            "bqfmt": t.get("bqfmt", "") or "", "bafmt": t.get("bafmt", "") or "",
            "did": None}


def model_json(mid, now, ov=None, gloss=None):
    """The note type as the collection's `models` blob holds it.

    Everything is derived from MODELS and the registry: the text field
    (and Context / Opposite) is flagged right-to-left only for an RTL
    language; `req` names the fields each template needs by POSITION,
    so it follows the Reading fields a language inserts.  For Persian's
    two ids, glossed in English, the result is exactly what the exporter
    has always written.

    `gloss` reaches only the templates and the CSS -- the id, the name and
    the field list, which are what Anki matches a note type by, do not
    depend on it, so changing a deck's gloss language updates the note
    type in place instead of forking a second one.
    """
    m = MODELS[mid]
    L = languages.get(m["lang"])
    names = m["fields"]
    rtl_fields = ({m["field"], "Context"} if m["kind"] == "vocab"
                  else {m["field"], "Opposite"}) if L.rtl else set()
    flds = [{"name": name, "ord": i, "sticky": False,
             "rtl": name in rtl_fields,
             "font": "Arial", "size": 20, "media": []}
            for i, name in enumerate(names)]
    tmpls = [_tmpl(ov, mid, i, n, q, a)
             for i, (n, q, a) in enumerate(lang_templates(mid, gloss))]
    # template 1 needs the text; template 2 the answer side and Reverse
    back = "Opposite" if m["kind"] == "opposites" else "English"
    req = [[0, "all", [0]],
           [1, "all", [names.index(back), names.index("Reverse")]]]
    return {"id": mid,
            "name": _name_for(ov, mid, m["name"]),
            "type": 0,
            "mod": now, "usn": -1, "sortf": 0, "did": 1,
            "flds": flds, "tmpls": tmpls, "css": _css_for(ov, mid, gloss),
            "latexPre": LATEX_PRE, "latexPost": LATEX_POST,
            "req": req,
            "tags": [], "vers": []}


def opp_model_json(now, ov=None):
    """The Persian opposites model -- the old entry point, kept for the
    callers that still name it."""
    return model_json(OPP_MODEL_ID, now, ov)


def deck_dict(did, name, now):
    return {"id": did, "name": name, "desc": "", "mod": now, "usn": -1,
            "collapsed": False, "browserCollapsed": False, "dyn": 0,
            "conf": 1, "extendNew": 10, "extendRev": 50,
            "newToday": [0, 0], "revToday": [0, 0],
            "lrnToday": [0, 0], "timeToday": [0, 0]}


def _media_field(card, side):
    """FrontImage or BackImage: the picture, then the recording.

    A RECORDING HAS NO FIELD OF ITS OWN, and never will: a note type's
    shape cannot change once notes have been studied with it (see
    anki/README.md), so the sound rides in the field that already sits on
    the right side of every template, captured ones included -- Anki plays
    a `[sound:file]` wherever in a card it is written, and with the deck's
    autoplay on, the front's recording plays when its side is asked."""
    img, snd = card.get("img_" + side), card.get("snd_" + side)
    return (('<img src="%s">' % img if img else "")
            + ("[sound:%s]" % snd if snd else ""))


def _source_html(card):
    src = card.get("source")
    if not isinstance(src, dict):        # a hand-edited card must not be able
        src = {}                         # to take the whole build down
    label, url = h(src.get("label") or ""), src.get("url") or ""
    return ('<a href="%s">%s</a>' % (h(url), label or h(url))) if url else label


def note_fields(card):
    """The note's field values, in its model's field order.

    Every value the card can carry is named here and the model's field
    list picks and orders them, so the Reading fields a language inserts
    fall into place without a per-language branch; a model without a
    field simply never asks for it.  For a Persian card this is the same
    list, in the same order, the exporter has always written."""
    m = MODELS[model_for(card)]
    # a reverse-only card still needs Reverse set: the English -> Persian
    # template is gated on it, and ReverseOnly only suppresses the forward
    rev_only = is_reverse_only(card)
    vals = {m["field"]: h(card.get("fa")),
            "Reading": h(card.get("kana")),
            "Transliteration": h(card.get("tr")),
            "English": h(card.get("en")),
            "Context": h(card.get("context")),
            "Opposite": h(card.get("opp")),
            "OppositeReading": h(card.get("opp_kana")),
            "OppositeTr": h(card.get("opp_tr")),
            "Notes": h(card.get("notes")),
            "FrontImage": _media_field(card, "front"),
            "BackImage": _media_field(card, "back"),
            "Source": _source_html(card),
            "Reverse": "y" if (card.get("bidirectional", True) or rev_only)
            else "",
            "ReverseOnly": "y" if rev_only else ""}
    return [vals.get(name, "") for name in m["fields"]]


def render_template(tmpl, fields):
    """The tiny mustache subset the card templates use: {{Field}}
    substitution, and {{#Field}}...{{/Field}} sections kept only while the
    field is non-empty.  Sections recurse, because the reversed card nests
    {{#BackImage}} inside {{#Reverse}}.  {{FrontSide}} is just a field the
    caller fills with the rendered question side."""
    def sections(s):
        def repl(m):
            shown = bool(fields.get(m.group(2), ""))
            if m.group(1) == "^":          # inverted: kept while EMPTY
                shown = not shown
            return sections(m.group(3)) if shown else ""
        return re.sub(r"\{\{([#^])(\w+)\}\}(.*?)\{\{/\2\}\}",
                      repl, s, flags=re.S)
    return re.sub(r"\{\{(\w+)\}\}",
                  lambda m: fields.get(m.group(1), ""), sections(tmpl))


def _font_url_for(L, font_url):
    """Where the preview page loads the bundled face from.  `font_url`
    may be None (the server's /lib/fonts/<file>), {code: url}, or one
    URL -- the old calling convention from the Persian-only days, which
    could only ever mean Vazirmatn, so a plain string is honoured for
    the default language alone: applied to any other it would point,
    say, the Arabic sheet's "Noto Naskh Arabic" face at Vazirmatn's
    file."""
    fn = font_file(L)
    if not fn:
        return None
    if isinstance(font_url, dict):
        return font_url.get(L.code) or "/lib/fonts/" + fn
    if isinstance(font_url, str) and font_url and L.code == languages.DEFAULT:
        return font_url
    return "/lib/fonts/" + fn


# a sound tag as Anki writes one; the preview plays it, Anki does itself
SOUND_RE = re.compile(r"\[sound:([^\]\"<>]+)\]")


def _sound_html(m):
    return '<audio controls src="%s"></audio>' % h(m.group(1)).replace('"', "&quot;")


def preview_html(card, night=False, font_url=None, anki_dir=None):
    """One standalone HTML document showing the card exactly as Anki will:
    the answer side of each direction (the question sits above the
    hr#answer rule, just as in a review), with the same templates and CSS
    the .apkg carries.  Meant for the dashboard's preview iframe."""
    opp = kind_of(card) == "opposites"
    mid = model_for(card)
    L = languages.get(MODELS[mid]["lang"])
    # this one card's own gloss language, not a deck's: the preview is
    # asked about the card in the dashboard, which is the card the player
    # is making out of the video open behind it
    G = gloss_of(card)
    gname = "English" if _is_english(G) else G.name
    fields = dict(zip(MODELS[mid]["fields"], note_fields(card)))
    # the preview must show what ANKI will show: the collection's own
    # styling and templates when we have been taught them
    ov = load_overrides(anki_dir) if anki_dir else {}
    css = _css_for(ov, mid, G)
    media, url = font_media_name(L), _font_url_for(L, font_url)
    if media and url:
        css = css.replace('url("%s")' % media, 'url("%s")' % url)
    night_cls = " nightMode" if night else ""
    built = lang_templates(mid, G)
    def pair(ord_):
        return _tmpl_pair(ov, mid, ord_, built[ord_][1], built[ord_][2])
    if opp:
        tmpls = [("opposite of the word",) + pair(0)]
        if card.get("bidirectional", True):
            tmpls.append(("opposite of the answer",) + pair(1))
    elif is_reverse_only(card):
        tmpls = [("%s → %s (the only direction)" % (gname, L.name),) + pair(1)]
    else:
        tmpls = [("%s → %s" % (L.name, gname),) + pair(0)]
        if card.get("bidirectional", True):
            tmpls.append(("%s → %s" % (gname, L.name),) + pair(1))
    parts = []
    for name, qfmt, afmt in tmpls:
        f = dict(fields)
        f["FrontSide"] = render_template(qfmt, f)
        parts.append('<div class="pvlabel">%s</div>\n<div class="card%s">%s'
                     '</div>' % (name, night_cls,
                                 SOUND_RE.sub(_sound_html, render_template(afmt, f))))
    return ('<!doctype html><html lang="%s"><head><meta charset="utf-8">'
            '<style>%s\n'
            'html,body{margin:0;padding:10px;background:%s}\n'
            '.card{padding:16px 12px;border-radius:10px;margin-bottom:16px}\n'
            '.pvlabel{font:11px/1.4 -apple-system,"Segoe UI",Roboto,'
            'sans-serif;letter-spacing:.12em;text-transform:uppercase;'
            'color:%s;margin:8px 2px 6px}\n'
            '</style></head><body>%s</body></html>'
            % (L.code, css, "#14151a" if night else "#faf9f7",
               "#5f5c57" if night else "#a8a8a8", "\n".join(parts)))


def check_shape(ov):
    """Stop a build whose note types have drifted out from under it.

    A note's values are written POSITIONALLY, and Anki matches a note
    type by id: emitting a model whose field list or template count
    disagrees with the collection's would either scramble every note or
    make Anki treat it as a different note type and fork a second copy,
    orphaning the scheduling of everything already studied.  Refusing is
    the only safe answer -- the fix is to teach the code the new shape,
    exactly as the ReverseOnly field was taught (see anki/README.md).
    Every note type in MODELS is checked, whichever language it serves.
    """
    for mid, m in MODELS.items():
        want = m["fields"]
        snap = (ov or {}).get(mid)
        if not snap:
            continue
        got = snap.get("fields")
        if isinstance(got, list) and got and got != list(want):
            raise ValueError(
                "the note type %r in your Anki collection has fields %s, "
                "but this exporter writes %s -- building would fork a "
                "second note type and orphan your review history. Teach "
                "lib/anki_export.py the new shape first (see "
                "anki/README.md, 'a note-type shape change travels "
                "Anki-first')." % (snap.get("name") or mid, got, list(want)))
        tm = snap.get("templates")
        if isinstance(tm, list) and tm and len(tm) != 2:
            raise ValueError(
                "the note type %r in your Anki collection has %d card "
                "templates; this exporter writes 2. Teach "
                "lib/anki_export.py the new shape first."
                % (snap.get("name") or mid, len(tm)))


def load_cards(deck_dir):
    cdir = os.path.join(deck_dir, "cards")
    if not os.path.isdir(cdir):
        return []
    out = []
    for fn in sorted(os.listdir(cdir)):
        if fn.endswith(".json"):
            with open(os.path.join(cdir, fn), encoding="utf-8") as f:
                out.append(json.load(f))
    return out


def collection_dir(deck_dir):
    """The anki/ directory a deck directory belongs to.

    A deck lives at anki/<language folder>/<slug>/, so the collection is
    two levels up -- except for a legacy deck lying directly under anki/,
    where it is one.  This is what tells notetypes.json and build/ apart
    from a deck: they are collection-level and there is one of each, not
    one per language (a note type is collection-global in Anki too).
    """
    parent = os.path.dirname(deck_dir)
    return (os.path.dirname(parent)
            if languages.by_folder(os.path.basename(parent)) else parent)


def deck_folder(deck_dir, cards=None):
    """The language folder a deck's package is named after: the folder it
    lies in, or -- for a legacy deck directly under anki/ -- the folder of
    the language its cards say they are (Persian when they say nothing)."""
    parent = os.path.basename(os.path.dirname(deck_dir))
    L = languages.by_folder(parent)
    if L:
        return L.folder
    for c in (cards or []):
        try:
            return lang_of(c).folder
        except ValueError:
            continue
    return languages.get(languages.DEFAULT).folder


def deck_gloss(cards):
    """The gloss language this build's note types are written for.

    A note type is ONE template and ONE stylesheet for the whole
    collection, so the answer has to be one language for the package and
    not one per card.  It is what the cards agree on -- a deck is filled
    from videos and books glossed one way, because a gloss language is a
    fact about the reader, not about the word.  When they do not agree the
    answer is English, which is the unmarked template every note type in
    this toolbox has carried until now: a template can only tell the truth
    about one of two languages, and saying nothing leaves Anki to lay each
    field out by its own content instead of swearing that half of them are
    in a language they are not.
    """
    seen = {G.code: G for G in (gloss_of(c) for c in cards)}
    if len(seen) == 1:
        return next(iter(seen.values()))
    return languages.gloss(None)


# the card keys naming a file in the deck's media/: one picture and one
# recording a side (the importers and the sync read the same four)
MEDIA_KEYS = ("img_front", "img_back", "snd_front", "snd_back")

# what Anki never lets into a media file's name (rslib's normalize_filename)
_MEDIA_BAD_RE = re.compile(r"[\[\]<>:\"/?*\\|\x00-\x1f]")


def media_name(name):
    """`name` when it can only be a file lying directly in a deck's media/,
    else None.

    A card's picture and recording names come out of a note's fields, and a
    package can come from anyone: `[sound:/home/me/.ssh/id_rsa]` or
    `<img src="../../secret">` joined to media/ would name a file outside it,
    and a build would pack that file into the deck.  So only a bare file name
    counts -- no folder, no drive, nothing Anki itself refuses in a media
    name -- and anything else is no media at all."""
    if not isinstance(name, str) or name in ("", ".", ".."):
        return None
    if _MEDIA_BAD_RE.search(name) or os.path.basename(name) != name \
            or os.path.isabs(name):
        return None
    return name


def build_deck(deck_dir, out_path=None):
    deck_dir = os.path.abspath(deck_dir)
    with open(os.path.join(deck_dir, "deck.json"), encoding="utf-8") as f:
        meta = json.load(f)
    cards = load_cards(deck_dir)
    # an "anki-owned" card is one whose note was taken over inside Anki
    # (its note type changed there -- see lib/sync_apkg.py): the note's
    # live content is in Anki alone, so it must never be exported, or the
    # import would fight the user's own version of it
    cards = [c for c in cards if c.get("anki") != "owned"]
    if not cards:
        raise ValueError("deck %r has no exportable cards" % meta.get("name"))
    slug = os.path.basename(deck_dir)
    # what the live collection says these note types look like
    ov = load_overrides(collection_dir(deck_dir))
    check_shape(ov)
    if out_path is None:
        bdir = os.path.join(collection_dir(deck_dir), "build")
        os.makedirs(bdir, exist_ok=True)
        # <folder>-<slug>.apkg: two languages may hold a deck of the same
        # name and so of the same slug, and the older naming had the
        # second build silently overwrite the first in build/
        out_path = os.path.join(
            bdir, "%s-%s.apkg" % (deck_folder(deck_dir, cards), slug))

    # the note types this deck uses -- only those, so a Persian deck's
    # package is what it always was and carries nothing of the others --
    # and the language their meanings are written in, which decides the
    # templates and the sheet but nothing Anki matches them by
    mids = sorted({model_for(c) for c in cards})
    G = deck_gloss(cards)
    # media: each used language's bundled face, then every screenshot and
    # every recording a card still references
    media, seen = [], set()
    for mid in mids:
        L = languages.get(MODELS[mid]["lang"])
        name, path = font_media_name(L), font_path(L)
        if name and path and name not in seen:
            media.append((name, path))
            seen.add(name)
    mdir = os.path.join(deck_dir, "media")
    for c in cards:
        for side in MEDIA_KEYS:
            fn = c.get(side)
            if not fn:
                continue
            if media_name(fn) is None:
                # a name that reaches outside media/ (a card written by an
                # older import of a hostile package): never read, never named
                c[side] = None
                continue
            path = os.path.join(mdir, fn)
            if not os.path.isfile(path):
                c[side] = None          # a deleted screenshot or recording: drop quietly
            elif fn not in seen:
                media.append((fn, path))
                seen.add(fn)

    now = int(time.time())
    now_ms = now * 1000
    did = int(meta.get("id") or 1998880001)
    tmp = tempfile.mkdtemp(prefix="apkg-")
    try:
        db = os.path.join(tmp, "collection.anki2")
        con = sqlite3.connect(db)
        con.executescript(SCHEMA)
        models = {str(mid): model_json(mid, now, ov, gloss=G) for mid in mids}
        decks = {"1": deck_dict(1, "Default", now),
                 str(did): deck_dict(did, meta.get("name") or slug, now)}
        # Stamp the package as OURS.  This file is a valid .apkg sitting in
        # the same download folder as a real export, and syncing it would
        # tell the store "Anki has seen every one of these notes" -- after
        # which the next genuine export, lacking the ones never imported,
        # would look like a mass deletion.  col.conf is not merged into a
        # collection by an Anki import, so this can never come back.
        conf = dict(CONF, curModel=next(iter(models)),
                    frankStoreBuild=slug)
        con.execute(
            "insert into col values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, now - 86400, now_ms, now_ms, 11, 0, 0, 0,
             json.dumps(conf), json.dumps(models, ensure_ascii=False),
             json.dumps(decks, ensure_ascii=False), json.dumps(DCONF), "{}"))
        nid, cid = now_ms, now_ms + 900000
        for i, card in enumerate(cards):
            flds = note_fields(card)
            sfld = card.get("fa") or ""
            csum = int(hashlib.sha1(sfld.encode("utf-8")).hexdigest()[:8], 16)
            tags = card.get("tags") or []
            guid = card.get("guid") or hashlib.sha1(
                (card.get("id") or sfld).encode("utf-8")).hexdigest()[:10]
            mid = model_for(card)
            con.execute(
                "insert into notes values (?,?,?,?,?,?,?,?,?,?,?)",
                (nid + i, guid, mid, now, -1,
                 " %s " % " ".join(tags) if tags else "",
                 "\x1f".join(flds), sfld, csum, 0, ""))
            if is_reverse_only(card):
                orders = [1]               # English -> Persian alone
            elif card.get("bidirectional", True):
                orders = [0, 1]
            else:
                orders = [0]
            for order in orders:
                con.execute(
                    "insert into cards values "
                    "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, nid + i, did, order, now, -1,
                     0, 0, i + 1, 0, 0, 0, 0, 0, 0, 0, 0, ""))
                cid += 1
        con.commit()
        con.close()

        # write to a sibling temp file and rename: two builds of the same
        # deck (the two servers, or a double click) must never interleave
        # into one corrupt .apkg
        out_tmp = out_path + "." + os.path.basename(tmp)   # unique per call
        with zipfile.ZipFile(out_tmp, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(db, "collection.anki2")
            z.writestr("media", json.dumps(
                {str(i): name for i, (name, _) in enumerate(media)}))
            for i, (_, path) in enumerate(media):
                z.write(path, str(i))
        os.replace(out_tmp, out_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out_path


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    out = build_deck(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
    # count what was SHIPPED, not what is on disk: an anki-owned card is
    # deliberately left out of the package (see build_deck)
    n = len([c for c in load_cards(os.path.abspath(sys.argv[1]))
             if c.get("anki") != "owned"])
    print("wrote %s  (%d note%s)" % (out, n, "" if n == 1 else "s"))


if __name__ == "__main__":
    main()
