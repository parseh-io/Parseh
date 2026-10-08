#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The reading help: what this computer has fetched to help you read a book
nobody has glossed, at /settings/reading-help/ (TO-DO §11.10).

It used to be its own page, /lookup/, five sections by kind -- dictionaries,
character components, translated sentences, translation models, synonyms --
each a table of rows.  It is a page of Settings now, beside Network, because
it is the same kind of thing as the port and the doors: what this machine
has, set once, from a page.  /lookup/ answers with a redirect to it for good
(serve.py), since every reader built before the move carries that address.

LANGUAGE FIRST.  Nobody wants "a dictionary"; they want to read their
Persian book.  So the page is a card per language -- the ones on your shelf
first, the others one line each until opened -- saying what the language has
and what it could have, with one *get everything* and what that costs.  What
is shared by every language (the translation engine, the English synonyms,
the fallback component pack) has a card of its own.

SHOWN RATHER THAN TOLD.  A row not yet installed carries a small example of
what it adds, drawn the way the reader draws it, in the card's own language:
a dictionary entry, a sentence somebody translated, a machine's reading, a
character taken apart.  EXAMPLES below holds one per kind for every language
the toolbox teaches; a language added later borrows Persian's.

SIZES BEFORE ANYTHING IS FETCHED.  Turkish's extract is 431 MB.  Where a size
has been measured, each downloader ships it (its MEASURED table, read through
its plan(..., probe=False), which sends nothing anywhere) and the row says it
on sight; where it has not, the row says "Parseh says how big before it
starts", and pressing *get it* asks the source for the size, says it, and
asks.  Nothing starts that the disk has no room for (serve.py).

SIX STATES, each a glyph, a word and a colour -- never the colour alone:
installed, built by an older Parseh (a dictionary without the index a newer
one writes, §11.6), downloading or building (a bar that moves, and the time
left), not yet, stopped (with the reason, in words), not available (with
why).  And each row's licence on the row, from the downloaders' own
constants through lib/notices.py, so the row and the Licences page cannot
disagree.

The long explanations this page used to carry -- why a dictionary cannot say
which sense a sentence means, why the model reads the whole sentence -- are
in the guide now ("How the reading help works"), linked from the foot.

Nothing here is required: Parseh gains no dependency and sends nothing
anywhere but the downloads themselves, and a language with nothing installed
is read exactly as it always was.

SPEECH TO TEXT IS NOT HERE (the owner, 2026-09-28): it has a door of its own,
/settings/speech/ (lib/speechpage.py), and this page carries one line pointing
at it.  It is drawn with this page's rows -- ROW_JS and STYLE below -- because
a row is a row, and its downloads run through the same runner, so the status
this page reads (/lookup/api/status) also carries its `speech`, its sizes and
its jobs; nothing on this page draws them.
"""
import io
import json
import os
import sqlite3
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(LIB)
sys.path.insert(0, LIB)
import languages                                               # noqa: E402
import decomposition                                           # noqa: E402
import corpus                                                  # noqa: E402
import getmt                                                   # noqa: E402
import getstt                                                  # noqa: E402
import getsyn                                                  # noqa: E402
import lookup                                                  # noqa: E402


# ---------------------------------------------------------------- the data
def older(code):
    """Was this language's dictionary built by an older Parseh (TO-DO §11.6)?

    The mark is the index on form(entry_id) that a verb entry's whole table
    is read through (lib/lookup.py, form_entry_ix): a dictionary built before
    it reads correctly, only slower, and cannot be given one because it is
    opened read-only.  A rebuild adds it."""
    path = lookup.path_for(code)
    if not os.path.isfile(path):
        return False
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        try:
            names = {r[1] for r in con.execute("PRAGMA index_list(form)")}
        finally:
            con.close()
    except sqlite3.Error:
        return False
    return "form_entry_ix" not in names


def dictionaries():
    """Every language the toolbox teaches, and what it has to read it with."""
    out = []
    for L in languages.LANGS.values():
        m = lookup.about(L.code) or {}
        row = {"code": L.code, "name": L.name, "native": L.native,
               "have": bool(m), "entries": m.get("entries", ""),
               "source": m.get("source", ""), "licence": m.get("licence", ""),
               "built": m.get("built", ""), "size": 0, "older": False}
        if m:
            try:
                row["size"] = os.path.getsize(lookup.path_for(L.code))
            except OSError:
                row["size"] = 0
            row["older"] = older(L.code)
        out.append(row)
    return out


def corpora():
    """Every language, and which of its parallel corpora are installed.

    One row per language, carrying the pairs it already has -- Persian
    glossed in English and Persian glossed in Italian are two files, because
    a corpus is a pair of languages and not one.
    """
    out = []
    have = {}
    for a, b in corpus.installed():
        have.setdefault(a, []).append(b)
    for L in languages.LANGS.values():
        rows = []
        for g in sorted(have.get(L.code, [])):
            m = corpus.about(L.code, g) or {}
            size = 0
            try:
                size = os.path.getsize(corpus.path_for(L.code, g))
            except OSError:
                pass
            G = languages.get_or_default(g)
            rows.append({"gloss": g, "gloss_name": G.name,
                         "pairs": m.get("pairs", ""), "source": m.get("source", ""),
                         "licence": m.get("licence", ""), "built": m.get("built", ""),
                         "size": size})
        # A LANGUAGE WITH NO WORD SEPARATOR CANNOT BE INDEXED UNTIL ITS
        # DICTIONARY IS HERE.  The corpus index is per word, and finding the
        # words of 我喜欢喝茶 means cutting it, which only the dictionary's
        # own word list can do.  Offering the button first builds a corpus
        # that reports itself built and can never match anything.
        out.append({"code": L.code, "name": L.name, "native": L.native,
                    "have": rows,
                    "needs_dict": bool(not L.spaced
                                       and not lookup.available(L.code))})
    return out


def _folder_size(d):
    try:
        return sum(os.path.getsize(os.path.join(d, n)) for n in os.listdir(d))
    except OSError:
        return 0


def models():
    """Every language, and which translation models are installed for it."""
    out = []
    have = {}
    for a, b in getmt.installed():
        have.setdefault(a, []).append(b)
    for L in languages.LANGS.values():
        rows = []
        for g in sorted(have.get(L.code, [])):
            m = getmt.about(L.code, g) or {}
            G = languages.get_or_default(g)
            rows.append({"gloss": g, "gloss_name": G.name,
                         "size": _folder_size(getmt.path_for(L.code, g)),
                         "source": m.get("source", ""),
                         "licence": m.get("licence", ""),
                         "built": m.get("built", "")})
        out.append({"code": L.code, "name": L.name, "native": L.native,
                    "have": rows,
                    # only the glosses a model could exist for: Mozilla trains
                    # against English and not against other languages, so
                    # offering Italian beside Persian is offering a download
                    # that is not there
                    "can": [g.code for g in languages.LANGS.values()
                            if getmt.trainable(L.code, g.code)]})
    return out


def synonym_table():
    """Is the aligner's synonym table here, and what it is.

    ONE ROW, not one per language: unlike a dictionary or a corpus this is
    not about any one language, it is English words the machine's reading
    is already in, so there is exactly one file and exactly one thing to
    say about it.
    """
    if not getsyn.installed():
        return {"have": False}
    meta, size = {}, 0
    try:
        meta = json.load(io.open(getsyn.OUT, encoding="utf-8"))
    except (OSError, ValueError):
        pass
    try:
        size = os.path.getsize(getsyn.OUT)
    except OSError:
        pass
    return {"have": True, "size": size,
            "entries": len(meta.get("synonyms") or {}),
            "source": meta.get("source", ""), "licence": meta.get("licence", ""),
            "built": meta.get("built", "")}


def engine():
    """The translation engine every model runs in: here or not, and how big."""
    return {"have": bool(getmt.engine_ready()), "version": getmt.ENGINE_VERSION,
            "size": _folder_size(getmt.ENGINE_DIR) if getmt.engine_ready() else 0}


def disk_free(folder):
    """Bytes free on the disk `folder` is (or would be) on: the nearest
    folder of it that exists is asked -- dict/ is not there until the first
    dictionary is."""
    import shutil
    at = os.path.abspath(folder)
    while not os.path.isdir(at) and os.path.dirname(at) != at:
        at = os.path.dirname(at)
    return shutil.disk_usage(at).free


def glosses():
    """What a corpus can be glossed in: every language the toolbox teaches."""
    return [{"code": L.code, "name": L.name} for L in languages.LANGS.values()]


# ------------------------------------------------------ the downloaders
# WHICH DOWNLOADER EACH KIND IS, and how the page's key for one becomes that
# downloader's arguments -- the same for its build() and its plan()
# (lib/download.py's interface).  serve.py starts them through these.
MODULES = {"dict": "getdict", "components": "getdecomposition", "corpus": "getcorpus",
           "model": "getmt", "synonyms": "getsyn", "speech": "getstt"}


def module_for(kind):
    import importlib
    return importlib.import_module(MODULES[kind])


def args_for(kind, key):
    if kind in ("corpus", "model"):
        return tuple(key.split("-", 1))
    return () if kind == "synonyms" else (key,)


def kwargs_for(kind):
    """The keyword arguments beside them: the page's *get it* on the synonym
    table always fetches (getsyn.get(force=True)), and its plan must say
    what that costs, not "nothing to do" because a table is already there."""
    return {"force": True} if kind == "synonyms" else {}


def known_plan(kind, key):
    """What getting (kind, key) costs as far as it is KNOWN without asking
    anybody: the downloader's plan(..., probe=False), which reads its shipped
    table of measured sizes and sends nothing anywhere.  A page that is only
    being looked at must not knock at kaikki.org."""
    try:
        return module_for(kind).plan(*args_for(kind, key), probe=False, **kwargs_for(kind))
    except Exception as e:                    # a size is a courtesy, not a page
        return {"download": None, "measured": False, "disk_peak": None, "kept": None,
                "have": 0, "error": "%s: %s" % (type(e).__name__, e)}


def sizes():
    """Every plan the page can show without asking anybody: "<kind>:<key>"
    -> plan, for each language's dictionary and pack, every pair a corpus
    could be, every pair a model exists for, and the synonym table."""
    out = {}
    codes = list(languages.LANGS)
    for code in codes:
        out["dict:" + code] = known_plan("dict", code)
        for gloss in codes:
            if gloss == code:
                continue
            out["corpus:%s-%s" % (code, gloss)] = known_plan("corpus", "%s-%s" % (code, gloss))
            if getmt.trainable(code, gloss):
                out["model:%s-%s" % (code, gloss)] = known_plan("model", "%s-%s" % (code, gloss))
    for pack in decomposition.PACKS:
        out["components:" + pack] = known_plan("components", pack)
    out["synonyms:"] = known_plan("synonyms", "")
    # speech to text's three parts: the plan says what a model costs WITH the program
    # when it is not there (its page, /settings/speech/, draws them)
    for part in getstt.PARTS:
        out["speech:" + part] = known_plan("speech", part)
    return out


# ---------------------------------------------------------- what it adds
# ONE EXAMPLE PER KIND IN EACH LANGUAGE, drawn on a row not yet installed so
# that a person sees what pressing *get it* would add to the reader.  Words a
# learner meets early, and where the language allows it one that shows why a
# dictionary alone is not enough (a word with two unrelated senses).
#   dict:   (headword, how it is said or "", part of speech, [senses])
#   corpus: (a sentence, its translation) -- <m>…</m> marks the shared word
#   model:  (a sentence, a machine's reading of it)
EXAMPLES = {
    "fa": {"dict": ("شیر", "šir", "noun", ["milk", "lion", "tap, faucet"]),
           "corpus": ("من <m>شیر</m> دوست دارم.", "I like <m>milk</m>."),
           "model": ("دوباره می‌سازمت، وطن", "I will rebuild you, my country")},
    "ar": {"dict": ("كتاب", "kitāb", "noun", ["book", "letter, note"]),
           "corpus": ("هذا <m>كتاب</m> جديد.", "This is a new <m>book</m>."),
           "model": ("سأعود غدًا.", "I will come back tomorrow.")},
    "it": {"dict": ("casa", "", "noun", ["house", "home"]),
           "corpus": ("La <m>casa</m> è grande.", "The <m>house</m> is big."),
           "model": ("Domani pioverà.", "It will rain tomorrow.")},
    "ja": {"dict": ("家", "いえ", "noun", ["house", "home, family"]),
           "corpus": ("<m>猫</m>が好きです。", "I like <m>cats</m>."),
           "model": ("明日は雨が降るでしょう。", "It will probably rain tomorrow.")},
    "fr": {"dict": ("livre", "", "noun", ["book (masculine)", "pound (feminine)"]),
           "corpus": ("J’ai lu ce <m>livre</m>.", "I read this <m>book</m>."),
           "model": ("Il pleuvra demain.", "It will rain tomorrow.")},
    "de": {"dict": ("Bank", "", "noun", ["bench", "bank"]),
           "corpus": ("Die <m>Bank</m> ist geschlossen.", "The <m>bank</m> is closed."),
           "model": ("Morgen wird es regnen.", "It will rain tomorrow.")},
    "tr": {"dict": ("ev", "", "noun", ["house, home", "household, family"]),
           "corpus": ("<m>Ev</m> çok büyük.", "The <m>house</m> is very big."),
           "model": ("Yarın yağmur yağacak.", "It will rain tomorrow.")},
    "en": {"dict": ("bank", "", "noun", ["an institution that keeps money",
                                         "the land along a river"]),
           "corpus": ("The <m>bank</m> is closed.", "La <m>banca</m> è chiusa."),
           "model": ("It will rain tomorrow.", "Domani pioverà.")},
    "hi": {"dict": ("घर", "ghar", "noun", ["house, home", "household"]),
           "corpus": ("यह मेरा <m>घर</m> है।", "This is my <m>house</m>."),
           "model": ("कल बारिश होगी।", "It will rain tomorrow.")},
    "es": {"dict": ("banco", "", "noun", ["bank", "bench"]),
           "corpus": ("El <m>banco</m> está cerrado.", "The <m>bank</m> is closed."),
           "model": ("Mañana lloverá.", "It will rain tomorrow.")},
    "zh": {"dict": ("书", "shū", "noun", ["book", "letter, document"]),
           "corpus": ("我在看<m>书</m>。", "I am reading a <m>book</m>."),
           "model": ("明天会下雨。", "It will rain tomorrow.")},
}
# a character taken apart, per pack: (the character, [its parts], a part
# taken apart in turn, or "")
PARTS = {"kanjivg": ("語", ["言", "吾"], "五 + 口"),
         "makemeahanzi": ("好", ["女", "子"], ""),
         "cjkvi": ("森", ["木", "林"], "木 + 木")}
# the synonym table's: what the machine wrote, and why it still matches
SYNONYM = ("They will <m>begin</m> at noon.",
           "the dictionary said <i>start</i>; a synonym is weaker evidence than the word itself")


def examples():
    """EXAMPLES for every language the page lists: its own where written,
    Persian's where not (a language somebody added since)."""
    return {L.code: EXAMPLES.get(L.code, EXAMPLES["fa"]) for L in languages.LANGS.values()}


# ------------------------------------------------------------ the view
def view(state=None, jobs=None, queues=None):
    """Everything the page draws, in one answer: the page is drawn from it
    when it opens and redrawn from it every time it asks how things stand
    (/lookup/api/status).  `state` is what serve.py knows and this module
    must not find out for itself -- what is on the shelf in each language,
    what it is glossed in, who is asking and what they may change; `jobs`
    and `queues` are the downloads running, waiting or just finished."""
    import notices
    state = state or {}
    shelf = state.get("shelf") or {}
    glossed = state.get("glossed") or {}
    dicts = {d["code"]: d for d in dictionaries()}
    corp = {c["code"]: c for c in corpora()}
    mods = {m["code"]: m for m in models()}
    packs = {p["source"]: p for p in decomposition.packs()}
    syn = synonym_table()
    eng = engine()
    langs = []
    for L in languages.LANGS.values():
        s = shelf.get(L.code) or {}
        gloss = glossed.get(L.code) or "en"
        if gloss not in languages.LANGS:
            gloss = "en"
        langs.append({
            "code": L.code, "name": L.name, "native": L.native,
            "rtl": L.dir == "rtl",
            "books": int(s.get("books") or 0), "videos": int(s.get("videos") or 0),
            "gloss": gloss, "spaced": bool(L.spaced),
            "dict": dicts[L.code], "corpora": corp[L.code]["have"],
            "needs_dict": corp[L.code]["needs_dict"],
            "models": mods[L.code]["have"], "can_model": mods[L.code]["can"],
            "pack": decomposition.PREFERRED.get(L.code)})
    kept = sum(d["size"] for d in dicts.values())
    kept += sum(r["size"] for c in corp.values() for r in c["have"])
    kept += sum(r["size"] for m in mods.values() for r in m["have"])
    kept += sum(p.get("size") or 0 for p in packs.values())
    kept += (syn.get("size") or 0) + (eng.get("size") or 0)
    try:
        free = disk_free(lookup.DICT_DIR)
    except OSError:
        free = None
    who = notices.credits()
    return {"languages": langs, "packs": packs, "syn": syn, "engine": eng,
            "speech": getstt.status(),
            "glosses": glosses(), "examples": examples(),
            "parts": PARTS, "synonym": SYNONYM,
            "credits": {k: {"who": v[0], "licence": v[1]} for k, v in who.items()},
            "sizes": sizes(), "jobs": jobs or {}, "queues": queues or {},
            "kept": kept, "free": free,
            "where": state.get("where") or "", "device": state.get("device") or "",
            "may": state.get("may") or {}}


def page(state=None, jobs=None, queues=None):
    """/settings/reading-help/, the whole page: the view, and the script that
    draws it."""
    import settingspage
    v = view(state, jobs, queues)
    # the bar of Settings' doors first and the page's own name under it, as on
    # every page of Settings (the owner, 2026-09-25)
    main = ('<main class="settings rh">\n%s\n<h1 class="idx">reading help</h1>\n'
            '<div id="rh-band" class="band"></div>\n'
            '<div id="rh"><p class="rh-wait">Reading what is here&hellip;</p></div>\n'
            '<p class="foot pointer">Turning a video\'s sound into a transcript is not here: '
            '<a href="/settings/speech/">speech to text</a> has a page of its own.</p>\n'
            '<p class="foot">What is fetched here lives in the %s folder &mdash; '
            '<code>dict/</code>, <code>corpus/</code>, <code>mt/</code>, '
            '<code>components/</code> &mdash; and nothing else of %s depends on it: a '
            'language with nothing here is read exactly as it always was. Every licence is '
            'also on the <a href="/licences/">licences</a> page. '
            '<a href="%s" data-guide>How the reading help works</a>, in the guide.</p>\n'
            '</main>'
            % (settingspage.settings_doors("/settings/reading-help/"),
               settingspage.NAME, settingspage.NAME, GUIDE + "#how-the-reading-help-works"))
    script = ('<script id="rh-state" type="application/json">%s</script>\n<script>%s</script>'
              % (json.dumps(v, ensure_ascii=False).replace("</", "<\\/"), SCRIPT))
    return settingspage.frame(
        "Reading help &mdash; %s settings" % settingspage.NAME,
        '<a href="/settings/">settings</a> &middot; reading help', "Reading help",
        GUIDE, main, style=STYLE, script=script)


GUIDE = "/guide/site/lookup-and-languages/reading-help.html"

STYLE = r"""
body.index main.settings.rh{max-width:60rem;padding:22px 16px 60px}
.rh .band{display:grid;grid-template-columns:auto auto 1fr;gap:6px 22px;align-items:center;
  background:var(--card);border:1px solid var(--rule);border-radius:12px;padding:12px 16px;margin:0 0 22px}
.rh .band:empty{display:none}
.rh .band .n{font-size:22px;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.1}
.rh .band .l{font-size:12.5px;color:var(--dim)}
.rh .band .who{font-size:13px;color:var(--dim);border-inline-start:1px solid var(--rule);padding-inline-start:18px}
.rh .band .who b{color:var(--ink)}
@media (max-width:720px){
  .rh .band{grid-template-columns:1fr 1fr}
  .rh .band .who{grid-column:1/-1;border:0;border-top:1px solid var(--rule);padding:8px 0 0}
}
.rh h2.part{font:400 13px/1.3 inherit;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);
  margin:26px 0 10px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;border:0;padding:0}
.rh h2.part .aside{letter-spacing:0;text-transform:none;font-size:12.5px}
.rh section.lang,.rh section.shared{background:var(--card);border:1px solid var(--rule);border-radius:14px;
  margin:0 0 16px;overflow:hidden;padding:0}
.rh .lh{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;padding:14px 16px 12px;
  border-bottom:1px solid var(--rule)}
.rh .lname{display:flex;align-items:baseline;gap:10px;min-width:0}
.rh .lname .native{font-size:24px;line-height:1.3;color:var(--accent)}
.rh .lname .en{font-size:17px;font-weight:600}
.rh .lshelf{color:var(--dim);font-size:13px}
.rh select{font:inherit;font-size:13px;padding:2px 6px;border-radius:6px;border:1px solid var(--rule);
  background:var(--bg);color:var(--ink)}
.rh .lh .sp{flex:1}
.rh .ltot{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:13px;color:var(--dim)}
.rh .ltot .cost{font-size:12.5px}
.rh .ask{flex-basis:100%;display:flex;gap:8px 12px;align-items:center;flex-wrap:wrap;font-size:13px;
  background:var(--boxbg);border:1px solid var(--rule);border-radius:8px;padding:8px 10px}
.rh .ask .said{flex:1 1 16rem}
.rh .ask.bad{border-color:var(--danger)}
.rh .it{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:10px 16px;align-items:center;
  padding:12px 16px;border-top:1px solid var(--rule)}
.rh .lh + .it{border-top:0}
.rh .it-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rh .it-name{font-weight:600;font-size:15px}
.rh .it-for{color:var(--dim);font-size:13px;margin-top:1px}
.rh .it-facts{font-size:13px;margin-top:4px;font-variant-numeric:tabular-nums}
.rh .it-facts .q{color:var(--faint)}
.rh .it-lic{font-size:12px;color:var(--faint);margin-top:2px}
.rh .it-lic a{color:var(--dim)}
.rh .it-act{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.rh .it.busy{background:var(--hl)}
.rh .it .note{font-size:12.5px;color:var(--dim);margin-top:4px}
.rh .it .note.bad{color:var(--danger)}
.rh .it .ask{margin-top:8px}
.rh button.big{padding:8px 16px;font-weight:600}
/* status: a glyph and a word, and a colour on top -- never the colour alone */
.rh .st{display:inline-flex;align-items:center;gap:5px;font-size:12px;line-height:1.2;
  padding:2px 9px 2px 7px;border-radius:20px;border:1px solid currentColor;white-space:nowrap;
  background:color-mix(in srgb,currentColor 9%,transparent)}
.rh .st i{font-style:normal;font-weight:700}
.rh .st.ok{color:var(--ok)}
.rh .st.old{color:var(--warn)}
.rh .st.run{color:var(--accent)}
.rh .st.bad{color:var(--danger)}
.rh .st.not{color:var(--dim);border-style:dashed;background:none}
.rh .st.part{color:var(--dim)}
.rh .st.na{color:var(--faint);border-style:dotted;background:none}
.rh .bar{height:6px;background:var(--rule);border-radius:3px;overflow:hidden;margin-top:7px;max-width:28rem}
.rh .bar i{display:block;height:100%;background:var(--accent);border-radius:3px;transition:width .6s}
.rh .bar.loose i{width:30%;animation:rh-slide 1.4s ease-in-out infinite}
@keyframes rh-slide{0%{margin-inline-start:-30%}100%{margin-inline-start:100%}}
/* what it adds, shown: a small cloud in the reader's own manner */
.rh .vig{margin:0;width:15.5rem;max-width:100%;background:var(--boxbg);border:1px solid var(--rule);
  border-radius:10px;padding:8px 10px 9px;font-size:12.5px;line-height:1.45;align-self:start}
.rh .vig .lab{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);margin-bottom:3px}
.rh .vig .t{font-size:17px;color:var(--ink)}
.rh .vig .rd{color:var(--faint);font-size:12px;margin-inline-start:6px}
.rh .vig ol{margin:2px 0 0;padding-inline-start:1.2em;color:var(--dim)}
.rh .vig .tr{color:var(--dim)}
.rh .vig mark{background:var(--hl);color:inherit;border-radius:3px;padding:0 2px;
  box-shadow:inset 0 -2px 0 var(--accentlt)}
.rh .vig .mach{font-style:italic;color:var(--faint);font-size:11px}
.rh .vig .tree{display:flex;align-items:center;gap:6px;flex-wrap:wrap;font-size:18px}
.rh .vig .tree .op{color:var(--faint);font-size:13px}
.rh .vig .tree .sub{font-size:14px;color:var(--dim)}
/* the other languages, one line each until opened */
.rh .others{background:var(--card);border:1px solid var(--rule);border-radius:14px;overflow:hidden;margin:0 0 16px}
.rh .orow{display:grid;grid-template-columns:11rem minmax(0,1fr) auto;gap:6px 14px;align-items:center;
  padding:9px 16px;border-top:1px solid var(--rule);font-size:13.5px}
.rh .orow:first-child{border-top:0}
.rh .orow .on1{font-weight:600;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.rh .orow .on1 .nat{font-weight:400;color:var(--dim)}
.rh .orow .sum{color:var(--dim);font-size:12.5px}
.rh .foot{color:var(--faint);font-size:12.5px;line-height:1.7;margin-top:22px}
.rh .foot a{color:var(--dim)}
.rh .foot code{font-family:ui-monospace,Menlo,monospace;font-size:12px}
.rh .rh-wait{color:var(--dim)}
.rh [lang=ja],.rh [lang=zh]{font-family:'Hiragino Sans','Noto Sans CJK JP','IPAexGothic','Droid Sans Fallback',sans-serif}
/* narrow: one column everywhere, buttons under the words, empty cells take no room */
@media (max-width:620px){
  .rh .it{grid-template-columns:minmax(0,1fr)}
  .rh .it-act{justify-content:flex-start}
  .rh .vig{width:100%}
  .rh .orow{grid-template-columns:minmax(0,1fr) auto}
  .rh .orow .sum{grid-column:1/-1;grid-row:2}
  .rh .lname .native{font-size:21px}
  .rh .it > span:empty,.rh .it-act:empty{display:none}
}
"""

# THE ROW HELPERS both pages' scripts share: the time left (worked out from how fast the
# bytes have been coming), a state's pill, sizes, escaping.  A row is drawn on this page
# (the dictionaries, the corpora, the models) and on Settings -> Speech to text
# (lib/speechpage.py) the same way, and a person reads one as the other.
ROW_JS = r"""
  var samples = {};        // how far each job was, and when: the time left is worked out from these
  var esc = function (s) { return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
    return {'<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;'}[c]; }); };
  function MB(n) {
    if (n == null) return '';
    if (n >= 1e9) return (n / 1e9).toFixed(1) + ' GB';
    return Math.max(1, Math.round(n / 1e6)) + ' MB';
  }
  /* ---- the time left: from how fast the bytes have been coming, smoothed,
     rounded so it does not jitter, and not said until there is a rate */
  function sample(id, j) {
    var now = Date.now() / 1000, s = samples[id];
    if (!s || s.phase !== j.phase || j.done < s.done) {
      samples[id] = {phase: j.phase, done: j.done, at: now, rate: null};
      return;
    }
    if (now - s.at >= 2 && j.done > s.done) {
      var r = (j.done - s.done) / (now - s.at);
      s.rate = s.rate == null ? r : s.rate * 0.7 + r * 0.3;
      s.done = j.done; s.at = now;
    }
  }
  function left(id, j) {
    var s = samples[id];
    if (!j.total || !s || !s.rate) return '';
    var t = Math.max(0, (j.total - j.done) / s.rate);
    if (t < 50) return 'about ' + Math.max(10, Math.round(t / 10) * 10) + ' seconds left';
    if (t < 90) return 'about a minute left';
    if (t < 3600) return 'about ' + Math.round(t / 60) + ' minutes left';
    return 'about ' + (t / 3600).toFixed(1).replace(/\.0$/, '') + ' hours left';
  }

  function pill(cls, glyph, word) {
    return '<span class="st ' + cls + '"><i>' + glyph + '</i> ' + esc(word) + '</span>';
  }
"""


SCRIPT = r"""
(function () {
  'use strict';
  var S = JSON.parse(document.getElementById('rh-state').textContent);
  var root = document.getElementById('rh');
  var band = document.getElementById('rh-band');
  var gloss = {};          // the pair each card shows, as its picker says
  var opened = {};         // the other languages opened from their one line
  var asking = {};         // a row's or a card's question: {kind: 'get'|'remove'|'all', ...}
  var polling = null;
  /*ROW_JS*/

  function num(n) { return Number(n || 0).toLocaleString('en'); }
  function built(s) {
    if (!s) return '';
    var d = new Date(String(s).slice(0, 10) + 'T12:00:00');
    return 'built ' + (isNaN(d) ? esc(s) : d.toLocaleDateString('en-GB', {day: 'numeric', month: 'long', year: 'numeric'}));
  }
  // an example's <m>word</m> is the word it shares; everything else is text
  function marked(s) { return esc(s).replace(/&lt;m&gt;/g, '<mark>').replace(/&lt;\/m&gt;/g, '</mark>')
                                    .replace(/&lt;i&gt;/g, '<i>').replace(/&lt;\/i&gt;/g, '</i>'); }
  function langOf(code) { return S.languages.filter(function (l) { return l.code === code; })[0]; }
  function nameOf(code) { var l = langOf(code); return l ? l.name : code; }
  function dirOf(code) { var l = langOf(code); return l && l.rtl ? ' dir="rtl"' : ''; }
  function job(kind, key) { return ((S.jobs || {})[kind] || {})[key] || null; }
  function size(kind, key) { return (S.sizes || {})[kind + ':' + key] || {}; }
  function may(setting) { return !S.may || S.may[setting] !== false; }

  /* ---- a row's state: a glyph, a word and a colour, never the colour alone */
  function stateOf(r) {
    var j = r.job;
    if (j && j.running) {
      var pc = j.total ? Math.min(99, Math.floor(100 * j.done / j.total)) : null;
      return {cls: 'run', glyph: j.phase === 'build' ? '↻' : '↓',
              word: (j.phase === 'build' ? 'Building' : 'Downloading') + (pc != null ? ' · ' + pc + '%' : '')};
    }
    if (j && j.waiting) return {cls: 'run', glyph: '…', word: 'Waiting its turn'};
    if (r.na) return {cls: 'na', glyph: '–', word: r.naWord || 'Not available'};
    if (j && (j.error || j.stopped) && !r.have) return {cls: 'bad', glyph: '!', word: 'Stopped'};
    if (r.have && r.older) return {cls: 'old', glyph: '↻', word: 'Built by an older Parseh'};
    if (r.have) return {cls: 'ok', glyph: '✓', word: 'Installed'};
    return {cls: 'not', glyph: '○', word: 'Not yet'};
  }

  /* ---- the rows of a language, for the pair its picker names */
  function rowsOf(L) {
    var g = gloss[L.code] || L.gloss, rows = [], lic = S.credits;
    var d = L.dict;
    rows.push({kind: 'dict', key: L.code, name: 'Dictionary', lang: L.code,
               'for': 'What the words of a chunk nobody has glossed mean.',
               have: d.have, older: d.older, credit: lic.dict,
               facts: d.have ? num(d.entries) + ' entries · ' + MB(d.size) + ' · ' + built(d.built) : '',
               kept: d.size, get: 'getdict', drop: 'dropdict', body: {code: L.code}, ex: 'dict'});
    if (L.pack) {
      var p = S.packs[L.pack] || {};
      rows.push({kind: 'components', key: L.pack, name: 'Character components · ' + p.name,
                 lang: L.code, anchor: true,
                 'for': L.code === 'ja' ? 'A kanji taken apart into the pieces it is written with.'
                                        : 'A hanzi taken apart into the pieces it is written with.',
                 have: p.have, credit: lic['components:' + L.pack],
                 facts: p.have ? num(p.entries) + ' characters · ' + MB(p.size) + ' · ' + built(p.built) : '',
                 kept: p.size, get: 'getdecomposition', drop: 'dropdecomposition', body: {source: L.pack},
                 ex: 'parts'});
    }
    var pairs = [g];
    L.corpora.forEach(function (c) { if (pairs.indexOf(c.gloss) < 0) pairs.push(c.gloss); });
    pairs.forEach(function (gl) {
      var c = L.corpora.filter(function (x) { return x.gloss === gl; })[0];
      var pair = nameOf(L.code) + '–' + nameOf(gl);
      var r = {kind: 'corpus', key: L.code + '-' + gl, name: 'Sentences people translated', lang: L.code,
               'for': 'A real sentence and a person’s translation, sharing the chunk’s rare words.',
               have: !!c, credit: lic.corpus, pair: pair,
               facts: c ? pair + ' · ' + num(c.pairs) + ' sentence pairs · ' + MB(c.size) + ' · ' + built(c.built) : '',
               kept: c ? c.size : 0, get: 'getcorpus', drop: 'dropcorpus', body: {code: L.code, gloss: gl},
               ex: 'corpus'};
      if (!c && gl === L.code) { r.na = true; r.naWord = 'Not available';
        r.why = 'A language glossed in itself has nothing to translate: pick what its glosses are written in above.'; }
      else if (!c && L.needs_dict) { r.after = true;
        r.why = L.name + ' is written without spaces between its words, so its dictionary comes first: the sentences are cut into words with it.'; }
      rows.push(r);
    });
    var mpairs = [g];
    L.models.forEach(function (m) { if (mpairs.indexOf(m.gloss) < 0) mpairs.push(m.gloss); });
    mpairs.forEach(function (gl) {
      var m = L.models.filter(function (x) { return x.gloss === gl; })[0];
      var arrow = nameOf(L.code) + ' → ' + nameOf(gl);
      var r = {kind: 'model', key: L.code + '-' + gl, name: 'Translation model', lang: L.code,
               'for': 'The whole sentence read by a machine, inside the reader. Nothing leaves this computer.',
               have: !!m, credit: lic.model, pair: arrow, norebuild: true,
               facts: m ? arrow + ' · ' + MB(m.size) + ' · a fixed version: nothing to rebuild' : '',
               kept: m ? m.size : 0, get: 'getmodel', drop: 'dropmodel', body: {code: L.code, gloss: gl},
               ex: 'model'};
      if (!m && L.can_model.indexOf(gl) < 0) {
        r.na = true; r.naWord = 'No model';
        r.why = gl === L.code ? 'A translation is between two languages.'
          : 'Mozilla trains its models to and from English, and ' + arrow + ' is not among them.';
      }
      rows.push(r);
    });
    rows.forEach(function (r) { r.job = job(r.kind, r.key); });
    return rows;
  }

  /* ---- what a row not yet installed would add, drawn the reader's way */
  function vignette(r) {
    var X = S.examples[r.lang] || S.examples.fa, dir = dirOf(r.lang);
    if (r.ex === 'dict') {
      var e = X.dict;
      return '<figure class="vig" aria-label="what it adds"><div class="lab">dictionary</div>' +
        '<div><span class="t" lang="' + r.lang + '"' + dir + '>' + esc(e[0]) + '</span>' +
        (e[1] ? '<span class="rd">' + esc(e[1]) + '</span>' : '') + '<span class="rd">' + esc(e[2]) + '</span></div>' +
        '<ol>' + e[3].map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('') + '</ol></figure>';
    }
    if (r.ex === 'corpus') {
      return '<figure class="vig" aria-label="what it adds"><div class="lab">a sentence somebody translated</div>' +
        '<div class="t" lang="' + r.lang + '"' + dir + '>' + marked(X.corpus[0]) + '</div>' +
        '<div class="tr">' + marked(X.corpus[1]) + '</div></figure>';
    }
    if (r.ex === 'model') {
      return '<figure class="vig" aria-label="what it adds"><div class="lab">a machine’s reading</div>' +
        '<div class="t" lang="' + r.lang + '"' + dir + '>' + esc(X.model[0]) + '</div>' +
        '<div class="tr">' + esc(X.model[1]) + ' <span class="mach">— a guess, never a gloss</span></div></figure>';
    }
    if (r.ex === 'parts') {
      var t = S.parts[r.key] || S.parts.kanjivg;
      return '<figure class="vig" aria-label="what it adds"><div class="lab">a character taken apart</div>' +
        '<div class="tree" lang="' + (r.key === 'makemeahanzi' ? 'zh' : 'ja') + '"><span>' + esc(t[0]) +
        '</span><span class="op">=</span>' + t[1].map(function (c) { return '<span>' + esc(c) + '</span>'; })
          .join('<span class="op">+</span>') + (t[2] ? ' <span class="sub">(' + esc(t[2]) + ')</span>' : '') +
        '</div></figure>';
    }
    if (r.ex === 'synonyms') {
      return '<figure class="vig" aria-label="what it adds"><div class="lab">a machine’s reading, matched</div>' +
        '<div class="tr">' + marked(S.synonym[0]) + '</div><div class="mach">' + marked(S.synonym[1]) + '</div></figure>';
    }
    return '';
  }

  /* ---- the size line of a row not installed: measured, or said before it starts */
  function sizeLine(r) {
    var p = size(r.kind, r.key), bits = [];
    if (r.pair) bits.push(esc(r.pair));
    if (p.download != null && p.measured) {
      var dl = '<b>' + MB(p.download) + '</b> to download';
      if (p.kept != null) dl += ', ' + (r.kind === 'model' || r.kind === 'synonyms' ? 'kept as' : 'built into') +
                              ' about <b>' + MB(p.kept) + '</b>';
      bits.push(dl);
      if (p.disk_peak != null && p.disk_peak > (p.download || 0) * 1.1)
        bits.push('needs about ' + MB(p.disk_peak) + ' free while it builds');
    } else {
      bits.push('<span class="q">size not measured: Parseh says how big before it starts</span>');
    }
    if (p.have) bits.push(MB(p.have) + ' of it already here, from a download that was stopped');
    return bits.join(' · ');
  }

  /* ---- one row */
  function row(r) {
    var st = stateOf(r), j = r.job || {}, id = r.kind + ':' + r.key, facts, note = '', act = '';
    var q = asking[id];
    if (j.running) {
      sample(id, j);
      var bits = [];
      if (r.pair) bits.push(esc(r.pair));
      if (j.phase === 'build') bits.push(j.total ? 'building' : 'building: ' + esc(j.say || ''));
      else bits.push(j.total ? MB(j.done) + ' of ' + MB(j.total) : MB(j.done || 0) + ' so far');
      var lt = left(id, j);
      if (lt) bits.push('<b>' + lt + '</b>');
      else if (j.total) bits.push('<span class="q">working out the time left</span>');
      facts = bits.join(' · ');
      var pc = j.total ? Math.min(100, 100 * j.done / j.total) : null;
      note = '<div class="bar' + (pc == null ? ' loose' : '') + '" role="progressbar" aria-label="' + esc(r.name) + '"' +
        (pc != null ? ' aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + Math.round(pc) + '"><i style="width:' + pc.toFixed(1) + '%"></i>' : '><i></i>') + '</div>' +
        // what the downloader last said, where the bar and the bytes do not
        // already say it: the build's steps, or a download of no known size
        (j.say && (j.phase === 'build' || !j.total) ? '<div class="note">' + esc(j.say) + '</div>' : '');
      act = may('reading.stop') ? '<button class="plain" type="button" data-stop="' + esc(id) + '">Stop</button>' : '';
    } else if (j.waiting) {
      facts = r.have ? esc(r.facts) : sizeLine(r);
      note = '<div class="note">Waiting for the downloads before it, one at a time.</div>';
      act = may('reading.stop') ? '<button class="plain" type="button" data-stop="' + esc(id) + '">Leave it out</button>' : '';
    } else if (r.have) {
      facts = r.facts;
      if (r.older) note = '<div class="note">It reads correctly, only more slowly: a rebuild adds the index a newer ' +
        'Parseh writes. The download is taken again; the old one stays until the new one is whole.</div>';
      if (j.error) note += '<div class="note bad">The last rebuild stopped: ' + esc(j.error) + ' The one here still works.</div>';
      else if (j.stopped) note += '<div class="note">You stopped the rebuild; the one here still works.</div>';
      if (!r.norebuild) act += '<button class="' + (r.older ? 'go' : 'plain') + '" type="button" data-get="' + esc(id) + '">Rebuild</button>';
      act += '<button class="plain" type="button" data-remove="' + esc(id) + '">Remove…</button>';
    } else if (r.na) {
      facts = r.pair ? esc(r.pair) : '';
      note = '<div class="note">' + esc(r.why) + '</div>';
    } else {
      facts = sizeLine(r);
      if (r.after) {
        note = '<div class="note">' + esc(r.why) + '</div>';
      } else if (j.stopped) {
        note = '<div class="note bad">You stopped it' + (j.done ? ' at ' + MB(j.done) : '') +
          '. Getting it again carries on from there, where the source allows it.</div>';
        act = '<button class="go" type="button" data-get="' + esc(id) + '">Carry on</button>';
      } else if (j.error) {
        note = '<div class="note bad">' + esc(j.error) + '</div>';
        act = '<button class="go" type="button" data-get="' + esc(id) + '">Try again</button>';
      } else {
        act = '<button class="go" type="button" data-get="' + esc(id) + '">Get it</button>';
      }
      if (!may('reading.get')) act = '';
    }
    if (q) note += ask(q, id);
    var fig = (!r.have && !r.na && !j.running && !j.waiting) ? vignette(r) : '';
    var credit = r.credit ? '<div class="it-lic">' + r.credit.who + ' · ' + r.credit.licence + '</div>' : '';
    return '<div class="it' + (j.running ? ' busy' : '') + '" data-row="' + esc(id) + '"' +
      (r.anchor && r.lang && r.key !== 'cjkvi' ? ' id="character-components-' + r.lang + '"' : '') + '>' +
      (anchorRow === id ? '<span id="character-components"></span>' : '') +
      '<div class="it-main"><div class="it-head"><span class="it-name">' + esc(r.name) + '</span>' +
      pill(st.cls, st.glyph, st.word) + '</div>' +
      '<div class="it-for">' + esc(r['for']) + '</div>' +
      (facts ? '<div class="it-facts">' + facts + '</div>' : '') + note + credit + '</div>' +
      (fig || '<span></span>') + '<div class="it-act">' + (q ? '' : act) + '</div></div>';
  }

  /* ---- a question asked in the row or the card, never in a dialog box */
  function ask(q, id) {
    if (q.kind === 'wait') return '<div class="ask"><span class="said">' + esc(q.said) + '</span></div>';
    if (q.kind === 'bad') return '<div class="ask bad"><span class="said">' + esc(q.said) + '</span>' +
      '<button class="plain" type="button" data-cancel="' + esc(id) + '">All right</button></div>';
    var yes = q.kind === 'remove' ? 'Remove' : q.kind === 'all' ? 'Get everything' : 'Get it';
    var no = q.kind === 'remove' ? 'Keep it' : 'Not now';
    return '<div class="ask' + (q.room ? ' bad' : '') + '"><span class="said">' + q.said + '</span>' +
      (q.room ? '' : '<button class="go" type="button" data-yes="' + esc(id) + '">' + yes + '</button>') +
      '<button class="plain" type="button" data-cancel="' + esc(id) + '">' + no + '</button></div>';
  }

  /* ---- a language's card */
  function counts(rows) {
    var can = rows.filter(function (r) { return !r.na; });
    var have = can.filter(function (r) { return r.have; }).length;
    var busy = can.filter(function (r) { return r.job && (r.job.running || r.job.waiting); }).length;
    return {all: can.length, have: have, busy: busy,
            missing: can.filter(function (r) { return !r.have && !(r.job && (r.job.running || r.job.waiting)); })};
  }
  function cost(missing, L) {
    var dl = 0, kept = 0, unknown = false;
    missing.forEach(function (r) {
        var p = size(r.kind, r.key);
        if (p.download != null && p.measured) { dl += p.download - (p.have || 0); kept += p.kept || 0; }
        else unknown = true;
      });
    if (!dl) return unknown ? 'Parseh says how big before it starts' : '';
    return (unknown ? 'at least ' : '') + '<b>' + MB(dl) + '</b> to download' + (kept ? ' · about ' + MB(kept) + ' kept' : '');
  }
  function card(L, closable) {
    var rows = rowsOf(L), c = counts(rows), g = gloss[L.code] || L.gloss;
    var kept = rows.reduce(function (t, r) { return t + (r.have ? r.kept || 0 : 0); }, 0);
    var qq = (S.queues || {})[L.code], queued = qq && qq.running;
    var st = c.have === c.all ? pill('ok', '✓', 'Everything ' + L.name + ' can have')
      : c.have || c.busy ? pill('part', '◐', 'Partly: ' + c.have + ' of ' + c.all + (c.busy ? ', ' + c.busy + ' on its way' : ''))
      : pill('not', '○', 'Nothing yet');
    var shelf = [];
    if (L.books) shelf.push(L.books + (L.books === 1 ? ' book' : ' books'));
    if (L.videos) shelf.push(L.videos + (L.videos === 1 ? ' video' : ' videos'));
    var opts = S.glosses.map(function (x) {
      return '<option value="' + x.code + '"' + (x.code === g ? ' selected' : '') + '>' + esc(x.name) + '</option>';
    }).join('');
    var btn = '', said = '';
    if (queued) {
      said = '<span class="cost">' + esc((qq.done || 0) + 1 > (qq.steps || 1) ? 'finishing' :
             ((qq.done || 0) + 1) + ' of ' + (qq.steps || 1) + ': ' + (qq.now || '')) + '</span>';
      btn = may('reading.stop') ? '<button class="plain" type="button" data-stopall="' + L.code + '">Stop getting everything</button>' : '';
    } else if (c.missing.length && may('reading.get')) {
      said = '<span class="cost">' + cost(c.missing, L) + '</span>';
      btn = '<button class="go' + (c.have ? '' : ' big') + '" type="button" data-all="' + L.code + '">' +
        (c.have ? 'Get the rest' : 'Get everything for ' + esc(L.name)) + '</button>';
    }
    var q = asking['all:' + L.code];
    return '<section class="lang" id="lang-' + L.code + '" data-lang-card="' + L.code + '">' +
      '<div class="lh"><div class="lname"><span class="native" lang="' + L.code + '"' + dirOf(L.code) + '>' +
      esc(L.native) + '</span><span class="en">' + esc(L.name) + '</span></div>' +
      '<div class="lshelf">' + (shelf.length ? shelf.join(' · ') + ' · ' : '') +
      'glossed in <select aria-label="glossed in" data-gloss="' + L.code + '">' + opts + '</select></div>' +
      '<span class="sp"></span><div class="ltot">' + st + (kept ? '<span>' + MB(kept) + ' kept</span>' : '') +
      (q ? '' : said + btn) + (closable ? '<button class="plain" type="button" data-close="' + L.code + '">Close</button>' : '') +
      '</div>' + (q ? ask(q, 'all:' + L.code) : '') + '</div>' +
      rows.map(row).join('') + '</section>';
  }
  function oneLine(L) {
    var rows = rowsOf(L), c = counts(rows), bits = [];
    var running = rows.filter(function (r) { return r.job && r.job.running; })[0];
    var failed = rows.filter(function (r) { return r.job && r.job.error && !r.have; })[0];
    var st = running ? pill('run', '↓', 'Downloading') : failed ? pill('bad', '!', 'Stopped')
      : c.have === c.all ? pill('ok', '✓', 'Everything') : c.have ? pill('part', '◐', 'Partly: ' + c.have + ' of ' + c.all)
      : pill('not', '○', 'Nothing yet');
    if (failed) bits.push(esc(failed.name.toLowerCase()) + ': ' + esc(failed.job.error));
    else rows.forEach(function (r) {
      var p = size(r.kind, r.key);
      if (!r.have && !r.na && p.measured && p.download != null)
        bits.push(esc({dict: 'dictionary', components: 'components', corpus: 'sentences', model: 'model'}[r.kind]) + ' ' + MB(p.download));
    });
    return '<div class="orow" data-other="' + L.code + '"><div class="on1">' + esc(L.name) +
      '<span class="nat" lang="' + L.code + '"' + dirOf(L.code) + '>' + esc(L.native) + '</span></div>' +
      '<div class="sum">' + st + (bits.length ? ' &nbsp;' + bits.join(' · ') : '') + '</div>' +
      '<button class="plain" type="button" data-open="' + L.code + '">Open</button></div>';
  }

  /* ---- what every language shares */
  function shared() {
    var e = S.engine, s = S.syn, cj = S.packs.cjkvi || {}, lic = S.credits;
    var eng = {kind: 'engine', key: '', name: 'The translation engine', have: e.have, norebuild: true,
               'for': 'What runs every translation model, inside the reader. Fetched with the first model.',
               facts: 'version ' + esc(e.version) + (e.have ? ' · ' + MB(e.size) : ' · about 5 MB'),
               credit: lic.engine, job: null};
    var engRow = '<div class="it"><div class="it-main"><div class="it-head"><span class="it-name">' + esc(eng.name) +
      '</span>' + (e.have ? pill('ok', '✓', 'Installed') : pill('not', '○', 'Comes with the first model')) +
      '</div><div class="it-for">' + esc(eng['for']) + '</div><div class="it-facts">' + eng.facts + '</div>' +
      '<div class="it-lic">' + lic.engine.who + ' · ' + lic.engine.licence + '</div></div><span></span><div class="it-act"></div></div>';
    var syn = {kind: 'synonyms', key: '', name: 'English synonyms', lang: 'en', have: s.have,
               'for': 'Lets a machine’s reading be matched to the chunk even where it chose another word.',
               facts: s.have ? num(s.entries) + ' words · ' + MB(s.size) + ' · ' + built(s.built) : '',
               kept: s.size, credit: lic.synonyms, get: 'getsyn', drop: 'dropsyn', body: {}, ex: 'synonyms'};
    syn.job = job('synonyms', '');
    var ids = {kind: 'components', key: 'cjkvi', name: 'Character components · ' + (cj.name || 'CJKVI-IDS'),
               lang: 'ja', have: cj.have, anchor: true,
               'for': 'For Japanese and Chinese, where the preferred pack has no entry for a character.',
               facts: cj.have ? num(cj.entries) + ' characters · ' + MB(cj.size) + ' · ' + built(cj.built) : '',
               kept: cj.size, credit: lic['components:cjkvi'], get: 'getdecomposition', drop: 'dropdecomposition',
               body: {source: 'cjkvi'}, ex: 'parts'};
    ids.job = job('components', 'cjkvi');
    return '<h2 class="part">Shared by every language</h2><section class="shared">' + engRow + row(syn) + row(ids) + '</section>';
  }

  /* ---- the whole page */
  var ROWS = {};            // "kind:key" -> the row as last drawn, for the buttons
  var anchorRow = null;     // which row #character-components names
  function mine(L) { return L.books + L.videos > 0; }
  function draw() {
    if (document.activeElement && document.activeElement.tagName === 'SELECT' && root.contains(document.activeElement)) {
      setTimeout(draw, 700);    // a picker being chosen from is not redrawn under the hand
      return;
    }
    ROWS = {};
    var yours = S.languages.filter(mine).sort(function (a, b) { return (b.books + b.videos) - (a.books + a.videos); });
    var others = S.languages.filter(function (L) { return !mine(L); });
    var out = '';
    if (yours.length) {
      out += '<h2 class="part">Your languages <span class="aside">— the ones on your shelf, first</span></h2>';
      out += yours.map(function (L) { return card(L, false); }).join('');
    }
    out += '<h2 class="part">' + (yours.length ? 'Other languages <span class="aside">— nothing on your shelf yet</span>'
                                             : 'Every language <span class="aside">— nothing on your shelf yet</span>') + '</h2>';
    var list = others.filter(function (L) { return !opened[L.code]; });
    if (list.length) out += '<div class="others">' + list.map(oneLine).join('') + '</div>';
    out += others.filter(function (L) { return opened[L.code]; }).map(function (L) { return card(L, true); }).join('');
    out += shared();
    root.innerHTML = out;
    S.languages.forEach(function (L) { rowsOf(L).forEach(function (r) { ROWS[r.kind + ':' + r.key] = r; }); });
    ROWS['synonyms:'] = {kind: 'synonyms', key: '', name: 'the synonym table', get: 'getsyn', drop: 'dropsyn', body: {},
                         kept: S.syn.size, have: S.syn.have};
    ROWS['components:cjkvi'] = {kind: 'components', key: 'cjkvi', name: 'the CJKVI-IDS component pack',
                                get: 'getdecomposition', drop: 'dropdecomposition', body: {source: 'cjkvi'},
                                kept: (S.packs.cjkvi || {}).size, have: (S.packs.cjkvi || {}).have};
    drawBand();
  }
  function drawBand() {
    var who;
    if (S.where === 'self') who = 'You are on <b>the computer Parseh runs on</b>. A phone that has been let in may get ' +
      'and remove these too; it may not change the Network settings.';
    else who = 'You are on <b>' + esc(S.device || 'another device') + '</b>, ' +
      (S.where === 'vpn' ? 'on a VPN' : 'let in over the Wi-Fi') + '. ' +
      (may('reading.get') && may('reading.remove') ? 'You may get and remove anything on this page: none of it changes ' +
        'who may reach Parseh, what it exposes, or what it runs.' : 'This page is changed on the computer Parseh runs on.');
    band.innerHTML = '<div><div class="n">' + (MB(S.kept) || '0 MB') + '</div><div class="l">kept for reading help</div></div>' +
      (S.free != null ? '<div><div class="n">' + MB(S.free) + '</div><div class="l">free on this computer</div></div>' : '<div></div>') +
      '<div class="who">' + who + '</div>';
  }

  /* ---- asking the server */
  function post(what, body) {
    return fetch('/lookup/api/' + what, {method: 'POST', headers: {'Content-Type': 'application/json'},
                                         body: JSON.stringify(body || {})})
      .then(function (r) { return r.json().then(function (j) { j.status = r.status; return j; }); });
  }
  function busy() {
    var any = false;
    Object.keys(S.jobs || {}).forEach(function (k) {
      Object.keys(S.jobs[k]).forEach(function (key) { var j = S.jobs[k][key]; if (j.running || j.waiting) any = true; });
    });
    Object.keys(S.queues || {}).forEach(function (k) { if (S.queues[k].running) any = true; });
    return any;
  }
  function refresh() {
    return post('status', {}).then(function (j) {
      if (!j || !j.ok) return;
      var was = busy();
      S = j;
      draw();
      if (busy() || was) schedule(busy() ? 1000 : 0);
      if (was && !busy() && window.ParsehActivity) ParsehActivity.poke(200);
    }).catch(function () {});
  }
  function schedule(ms) {
    clearTimeout(polling);
    if (ms) polling = setTimeout(refresh, ms);
  }
  function kick() {
    if (window.ParsehActivity) ParsehActivity.poke(200);
    refresh().then(function () { schedule(1000); });
  }

  /* ---- the buttons */
  function start(r) {
    delete asking[r.kind + ':' + r.key];
    return post(r.get, r.body).then(function (j) {
      if (!j.ok) { asking[r.kind + ':' + r.key] = {kind: 'bad', said: j.error || 'That was refused.'}; draw(); return; }
      kick();
    });
  }
  function getRow(id) {
    var r = ROWS[id];
    if (!r) return;
    var p = size(r.kind, r.key);
    if (p.measured && p.download != null) {
      // the size was on the row already: pressing is the answer.  The
      // server still checks the room and refuses in words
      return start(r);
    }
    asking[id] = {kind: 'wait', said: 'Asking how big it is…'};
    draw();
    post('plan', {kind: r.kind, key: r.key}).then(function (j) {
      if (!j.ok) { asking[id] = {kind: 'bad', said: j.error || 'Parseh could not find out.'}; draw(); return; }
      var said;
      if (j.download != null) {
        said = 'It is a <b>' + MB(Math.max(0, j.download - (j.have || 0))) + '</b> download' +
          (j.have ? ' still to come (' + MB(j.have) + ' is here already)' : '') +
          (j.kept != null ? ', kept as about ' + MB(j.kept) : '') + '; ' + MB(j.free) + ' free on this computer. Get it?';
      } else {
        said = 'The source does not say how big it is. ' + MB(j.free) + ' free on this computer. Get it anyway?';
      }
      asking[id] = j.room ? {kind: 'get', room: true, said: esc(j.room)} : {kind: 'get', said: said};
      draw();
    }).catch(function () { asking[id] = {kind: 'bad', said: 'The server did not answer.'}; draw(); });
  }
  function removeRow(id) {
    var r = ROWS[id];
    if (!r) return;
    var p = size(r.kind, r.key), what = r.kind === 'dict' ? 'the ' + nameOf(r.key) + ' dictionary'
      : r.kind === 'corpus' ? 'the ' + r.pair + ' sentences' : r.kind === 'model' ? 'the ' + r.pair + ' model' : r.name;
    var back = p.download != null && p.measured ? 'getting it back is a ' + MB(p.download) + ' download'
      : 'getting it back means downloading it again';
    asking[id] = {kind: 'remove', said: 'Remove ' + esc(what) + '? It frees ' + (MB(r.kept) || 'a little room') + '; ' + back + '.'};
    draw();
  }
  function getAll(code) {
    var L = langOf(code), g = gloss[code] || L.gloss, id = 'all:' + code;
    asking[id] = {kind: 'wait', said: 'Working out what it costs…'};
    draw();
    post('plan', {all: code, gloss: g}).then(function (j) {
      if (!j.ok) { asking[id] = {kind: 'bad', said: j.error || 'Parseh could not find out.'}; draw(); return; }
      var names = j.steps.map(function (s) { return s.named; });
      var said = 'Getting everything for ' + esc(L.name) + ': ' + esc(names.join(', ')) + ', one after another. ' +
        (j.download ? (j.at_least ? 'At least ' : '') + '<b>' + MB(j.download) + '</b> to download' +
          (j.kept ? ', about ' + MB(j.kept) + ' kept' : '') : 'Parseh says each one’s size as it starts') +
        '; ' + MB(j.free) + ' free on this computer.';
      asking[id] = j.room ? {kind: 'all', room: true, said: esc(j.room)} : {kind: 'all', said: said, gloss: g};
      draw();
    }).catch(function () { asking[id] = {kind: 'bad', said: 'The server did not answer.'}; draw(); });
  }
  root.addEventListener('change', function (e) {
    var sel = e.target.closest('[data-gloss]');
    if (!sel) return;
    gloss[sel.getAttribute('data-gloss')] = sel.value;
    sel.blur();
    draw();
  });
  root.addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (!b || b.disabled) return;
    var id;
    if ((id = b.getAttribute('data-open'))) { opened[id] = true; draw(); return; }
    if ((id = b.getAttribute('data-close'))) { delete opened[id]; draw(); return; }
    if ((id = b.getAttribute('data-get'))) { b.disabled = true; getRow(id); return; }
    if ((id = b.getAttribute('data-remove'))) { removeRow(id); return; }
    if ((id = b.getAttribute('data-all'))) { getAll(id); return; }
    if ((id = b.getAttribute('data-cancel'))) { delete asking[id]; draw(); return; }
    if ((id = b.getAttribute('data-stop'))) {
      var r = ROWS[id] || {kind: id.split(':')[0], key: id.split(':').slice(1).join(':')};
      b.disabled = true;
      post('stop', {kind: r.kind, key: r.key}).then(kick);
      return;
    }
    if ((id = b.getAttribute('data-stopall'))) { b.disabled = true; post('stop', {all: id}).then(kick); return; }
    if ((id = b.getAttribute('data-yes'))) {
      var q = asking[id];
      b.disabled = true;
      if (id.indexOf('all:') === 0) {
        var code = id.slice(4);
        delete asking[id];
        post('getall', {code: code, gloss: q.gloss}).then(function (j) {
          if (!j.ok) { asking[id] = {kind: 'bad', said: j.error || 'That was refused.'}; draw(); return; }
          kick();
        });
        return;
      }
      var r2 = ROWS[id];
      if (q && q.kind === 'remove') {
        delete asking[id];
        post(r2.drop, r2.body).then(function (j) {
          if (!j.ok) { asking[id] = {kind: 'bad', said: j.error || 'That was refused.'}; draw(); return; }
          refresh();
        });
        return;
      }
      start(r2);
    }
  });
  document.addEventListener('visibilitychange', function () { if (!document.hidden) refresh(); });

  /* THE CHARACTER COMPONENTS, FROM THE KANJI AND HANZI DIALOG.  Its setup
     links name the language (#character-components-ja, -zh).  The old
     address's fragment, /lookup/#character-components -- baked into readers
     built before the move, and kept by serve.py's redirect -- names none:
     it lands on whichever of Japanese and Chinese is on the shelf, or on
     Japanese.  Either way that card is opened if it is one line, and the
     row scrolled to. */
  var asked = /^#character-components(?:-(ja|zh))?$/.exec(location.hash);
  if (asked) {
    var ja = langOf('ja') || {}, zh = langOf('zh') || {};
    var L = asked[1] ? langOf(asked[1]) || ja : (ja.books + ja.videos) ? ja : (zh.books + zh.videos) ? zh : ja;
    if (L.code) { anchorRow = 'components:' + L.pack; if (!mine(L)) opened[L.code] = true; }
  }
  draw();
  if (location.hash) {
    var at = anchorRow ? root.querySelector('[data-row="' + anchorRow + '"]')
                       : document.getElementById(location.hash.slice(1));
    if (at) at.scrollIntoView();
  }
  if (busy()) schedule(1000);
})();
""".replace("/*ROW_JS*/", ROW_JS)
