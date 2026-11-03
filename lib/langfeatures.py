# SPDX-License-Identifier: GPL-3.0-or-later
"""What each language has, feature by feature: one answer for the command line
(`python3 lib/newlang.py --features`) and for Settings -> Languages.

A language is a row of the registry and a dozen files and pins around it, each
read only where it exists -- which is what lets a language start small, and what
made "is Catalan finished?" a question nobody could answer without reading the
whole tree.  This walks them all, per language, and says for each feature
whether the language has it, what it is without it, and what adds it.  It
reads files and tables and never the network: what a service answers for a
language (a dictionary at kaikki, a translation model at Mozilla, sentences at
Tatoeba) is said as what Parseh will ask, not as a promise.

Standard library only, and nothing imported that loads a model.

    features(code)      -> [Feature, ...] in the order a page shows them
    table()             -> {code: [Feature, ...]} for every language
    summary(code)       -> (have, of, missing names) for one line of a list
"""
import os
import re
import sys
from dataclasses import dataclass

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import languages                                               # noqa: E402

LANG_FILES = os.path.join(HERE, "lang")
LANG_DOCS = os.path.join(ROOT, "docs", "lang")
VERBS = os.path.join(HERE, "verbs")
STARTERS = os.path.join(ROOT, "markdown", "exlex", "starters")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
GUIDE_LANGS = os.path.join(ROOT, "html-guide", "markdown", "dialect", "languages")

# the kinds of answer: a feature the language has, one it has not and should
# (core: the language is unfinished without it), one it may have (extra:
# nothing is wrong without it), and one decided by a service when asked
HAVE, MISSING, OPTIONAL, ASKED = "have", "missing", "optional", "asked"

# the eleven whose gloss-button examples and level names live in the frozen
# tables of lib/vocbuttons.js and lib/gear-reader.js
_FROZEN_JS = frozenset("fa ar it ja fr de tr en hi es zh".split())


@dataclass(frozen=True)
class Feature:
    key: str          # stable id: "conventions", "lookup-rules", ...
    name: str         # what a person calls it
    state: str        # HAVE, MISSING, OPTIONAL, ASKED
    says: str         # one sentence: what the language has, or what it is without it
    adds: str = ""    # what adds it, where it is missing: a file, a command, a page
    prompt: str = ""  # a piece lib/langprompts.py can have a chatbot write, by its key

    def as_json(self):
        return {"key": self.key, "name": self.name, "state": self.state, "says": self.says,
                "adds": self.adds, "prompt": self.prompt}


def _exists(*parts):
    return os.path.exists(os.path.join(*parts))


def _todo_left(path):
    """True when a file the scaffold wrote still carries one of its TODO
    markers: written by newlang.py and not yet by a person."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return True
    return bool(re.search(r"(^|[\s%({])TODO\b|\{\{[A-Z]+\}\}", text))


def _pins():
    """(UDPipe pins, aligner pins), read lazily so that a page that never asks
    imports neither."""
    try:
        import analysispins
        udpipe = set(analysispins.UDPIPE_MODELS)
    except Exception:           # noqa: BLE001 -- a table that cannot be read is an absent one
        udpipe = set()
    try:
        import alignerpins
        aligner = set(alignerpins.ALIGN_PINS)
    except Exception:           # noqa: BLE001
        aligner = set()
    return udpipe, aligner


def _whisper():
    try:
        import getstt
        return getstt.WHISPER_LANGUAGES
    except Exception:           # noqa: BLE001
        return frozenset()


def _arasaac():
    try:
        import getarasaac
        return getarasaac.LOCALES
    except Exception:           # noqa: BLE001
        return frozenset()


_BACKEND = {"udpipe": "UDPipe", "farahidi": "Farahidi", "starlang": "Starlang",
            "native": "the word line's own analysis"}


def _who(an):
    """'Farahidi reads the word forms, UDPipe the sentence', from the row's analysis."""
    m, s = an.get("morphology"), an.get("syntax")
    if m and s and m == s:
        return "%s reads the word forms and the sentence" % _BACKEND.get(m, m)
    bits = []
    if m:
        bits.append("%s reads the word forms" % _BACKEND.get(m, m))
    if s:
        bits.append("%s the sentence" % _BACKEND.get(s, s) if bits else "%s reads the sentence" % _BACKEND.get(s, s))
    return ", ".join(bits)


def features(code):
    """Every feature of one language, in the order a page lists them."""
    L = languages.LANGS.get(code)
    udpipe, aligner = _pins()
    out = []

    def add(key, name, state, says, adds="", prompt=""):
        out.append(Feature(key, name, state, says, adds, prompt))

    # ---- what the annotator and the printed book are told
    doc = os.path.join(LANG_DOCS, code + ".md")
    if not os.path.exists(doc):
        add("conventions", "Annotation conventions", MISSING,
            "No conventions: the prompts cannot tell a chatbot how to gloss %s." % L.name,
            "docs/lang/%s.md (python3 lib/newlang.py writes its template)" % code, "conventions")
    elif _todo_left(doc):
        add("conventions", "Annotation conventions", MISSING,
            "The conventions are still the template: every prompt carries its TODOs.",
            "docs/lang/%s.md: write the seven sections" % code, "conventions")
    else:
        add("conventions", "Annotation conventions", HAVE,
            "Every prompt carries docs/lang/%s.md." % code)
    tex = os.path.join(LANG_FILES, code + ".tex")
    if not os.path.exists(tex):
        add("howto", "Printed books", MISSING, "No lib/lang/%s.tex: a book in %s cannot be built." % (code, L.name),
            "python3 lib/newlang.py writes it")
    elif _todo_left(tex):
        add("howto", "Printed books", MISSING,
            "Books build, but their \"How to read this\" page is still the placeholder.",
            "\\FrankHowTo in lib/lang/%s.tex" % code, "howto")
    else:
        add("howto", "Printed books", HAVE, "Books build, with their own \"How to read this\" page.")
    hy = (L.tex or {}).get("hyphen")
    if L.script == "latin" and not hy:
        add("hyphen", "Hyphenation", MISSING, "LaTeX would break %s words at English points." % L.name,
            "\"hyphen\" in the row's tex (and the TeX hyphenation package)")
    else:
        add("hyphen", "Hyphenation", HAVE,
            "LaTeX hyphenates with its %s patterns." % hy if hy else "Not a script LaTeX hyphenates.")

    # ---- the studio
    if os.path.exists(os.path.join(STARTERS, code + ".md")):
        add("starter", "Studio starter document", HAVE, "+New opens on a guided tour in %s." % L.name)
    else:
        add("starter", "Studio starter document", OPTIONAL,
            "+New opens on a short document built from the row.",
            "markdown/exlex/starters/%s.md" % code, "starter")
    ex = L.examples or {}
    macros = ex.get("macros") or (code in _FROZEN_JS)
    if all(ex.get(k) for k in ("dict", "corpus", "model")) and macros:
        add("examples", "Examples", HAVE, "The lookup page and the gloss buttons show words of %s." % L.name)
    else:
        add("examples", "Examples", OPTIONAL,
            "The lookup page and the gloss buttons explain themselves without an example.",
            "\"examples\" in the row", "examples")

    # ---- reading what nobody glossed
    add("dictionary", "Dictionary", ASKED,
        "Wiktionary's %s, through kaikki.org, fetched from Settings → Reading help." % L.name)
    if os.path.exists(os.path.join(LANG_FILES, code + ".lookup.json")):
        add("lookup-rules", "Lookup rules", HAVE,
            "Forms the dictionary has no page for are taken apart (lib/lang/%s.lookup.json)." % code)
    else:
        add("lookup-rules", "Lookup rules", OPTIONAL,
            "A word is looked up as written: an elided or attached form finds nothing.",
            "lib/lang/%s.lookup.json" % code, "lookup-rules")
    if os.path.exists(os.path.join(VERBS, code + ".py")):
        fx = os.path.exists(os.path.join(FIXTURES, "verbs", code + ".json"))
        add("verbs", "Verb entries", HAVE,
            "Verbs are offered as \\vb%s." % ("" if fx else " (no fixture tries the recipe)"))
    else:
        add("verbs", "Verb entries", OPTIONAL, "Verbs are offered as plain words (\\dw).",
            "lib/verbs/%s.py and tests/fixtures/verbs/%s.json" % (code, code))
    if os.path.exists(os.path.join(LANG_FILES, code + ".chunk.json")):
        add("chunk-rules", "Chunking rules", HAVE, "The offline cut knows how %s phrases hold together." % L.name)
    else:
        add("chunk-rules", "Chunking rules", OPTIONAL, "The offline cut uses the general rules.",
            "lib/lang/%s.chunk.json (newlang.py --like copies a relative's)" % code, "chunk-rules")
    an = L.analysis
    said = _who(an)
    if an["morphology"] == "udpipe" or an["syntax"] == "udpipe":
        if code in udpipe:
            add("analysis", "Linguistic analysis", HAVE,
                "%s (Settings → Linguistic analysis)." % said)
        else:
            add("analysis", "Linguistic analysis", MISSING,
                "The row names UDPipe, and no model of it is pinned.",
                "python3 lib/analysispins.py --measure <treebank>, then a line in UDPIPE_MODELS")
    elif an["morphology"] or an["syntax"]:
        add("analysis", "Linguistic analysis", HAVE, said + ".")
    else:
        add("analysis", "Linguistic analysis", OPTIONAL, "No analyzer: words are not read in their sentence.",
            "\"analysis\" in the row, and a pinned model (a UDPipe 2.5 treebank, if there is one)")
    add("translation", "Translation models", ASKED,
        "Mozilla's models, where Firefox has %s ↔ English (Settings → Reading help)." % L.name)
    if L.iso3:
        add("corpus", "Translated sentences", ASKED,
            "Tatoeba's sentences filed under %s (Settings → Reading help)." % L.iso3)
    else:
        add("corpus", "Translated sentences", MISSING, "No ISO 639-3 code: no corpus can be asked for.",
            "\"iso3\" in the row")
    if os.path.exists(os.path.join(LANG_FILES, code + ".ipa.json")):
        add("ipa", "IPA from the spelling", HAVE, "Words without IPA in the dictionary get it from the spelling.")
    else:
        add("ipa", "IPA from the spelling", OPTIONAL, "IPA only where the dictionary gives it.",
            "lib/lang/%s.ipa.json" % code)

    # ---- sound
    if code in _whisper():
        add("speech", "Speech to text", HAVE, "Whisper transcribes %s (Settings → Speech to text)." % L.name)
    else:
        add("speech", "Speech to text", OPTIONAL, "Whisper has no %s: transcripts are written by hand." % L.name)
    if code in aligner:
        add("aligner", "Exact word times", HAVE, "A pinned aligner network times each word.")
    else:
        add("aligner", "Exact word times", OPTIONAL,
            "Word times come from Whisper alone; no aligner network is pinned.",
            "a converted network on Hugging Face, pinned in lib/alignerpins.py")

    # ---- pictures
    if code in _arasaac():
        add("pictograms", "Pictograms", HAVE, "ARASAAC has words in %s." % L.name)
    else:
        add("pictograms", "Pictograms", OPTIONAL, "ARASAAC has no words in %s: pictograms are searched in English."
            % L.name)

    # ---- what proves it (a developer's concern, said on the command line)
    fixtures = [p for p in ("books", "videos") if _exists(FIXTURES, p, L.folder)]
    if len(fixtures) == 2:
        add("fixtures", "Test fixtures", HAVE, "The smoke test builds a book and a video in %s." % L.name)
    else:
        add("fixtures", "Test fixtures", OPTIONAL, "The smoke test skips %s." % L.name,
            "tests/fixtures/books/%s/ and tests/fixtures/videos/%s/" % (L.folder, L.folder))
    if os.path.exists(os.path.join(GUIDE_LANGS, L.folder + ".md")):
        add("guide", "Guide page", HAVE, "The guide has a page for %s." % L.name)
    else:
        add("guide", "Guide page", OPTIONAL, "The guide does not name %s." % L.name,
            "html-guide/markdown/dialect/languages/%s.md" % L.folder)
    return out


def table():
    return {code: features(code) for code in languages.LANGS}


def summary(code):
    fs = features(code)
    have = [f for f in fs if f.state in (HAVE, ASKED)]
    missing = [f.name for f in fs if f.state == MISSING]
    return len(have), len(fs), missing


def render(codes=None):
    """The text newlang.py --features prints."""
    codes = codes or list(languages.LANGS)
    mark = {HAVE: "✓", ASKED: "~", OPTIONAL: "·", MISSING: "✗"}
    lines = []
    for code in codes:
        L = languages.LANGS.get(code)
        have, of, missing = summary(code)
        lines.append("%s  %s (%s)  %d of %d%s" % (code, L.name, L.native, have, of,
                                               ("  -- MISSING: " + ", ".join(missing)) if missing else ""))
        for f in features(code):
            lines.append("    %s %-26s %s%s" % (mark[f.state], f.name, f.says,
                                              ("\n%32s→ %s" % ("", f.adds)) if f.adds and f.state != HAVE else ""))
        lines.append("")
    lines.append("✓ has it   ~ a service is asked when it is fetched   · optional, not there   ✗ missing")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render(sys.argv[1:] or None))
