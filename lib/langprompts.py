# SPDX-License-Identifier: GPL-3.0-or-later
"""The prose a new language needs, written by a chatbot: one prompt per piece,
and the intake that checks the answer and puts it where Parseh reads it.

lib/newlang.py writes a language's shape -- the row, the .tex, the template of
its conventions, the folders -- and leaves the prose, which is most of the
work: the annotation conventions every prompt carries, the "How to read this"
page of a printed book, the studio's starter document, the examples the lookup
page and the gloss buttons show, the rules that take an attached or elided
form apart, the rules that say how its phrases hold together.  Each of those
already exists for a related language, and a chatbot that is shown the
related language's file and told what is different writes a good first
draft of the new one.  So every piece here is a PROMPT (the related
language's file as the model, the new language's row as the facts, the format
spelled out) and an INTAKE (the answer, pasted back, checked for the shape
Parseh reads, and written).  Parseh never sends anything anywhere: the person
copies the prompt to the chatbot of their choice, as with every other prompt.

The intake refuses what Parseh could not read -- a JSON file that does not
parse, conventions without their seven sections, a starter without its
`target:` -- and never what it cannot judge: whether the Catalan of an
example is good Catalan is the person's to read before they paste it.

    PIECES                          key -> (name, the file it writes)
    like_for(code)                  the related language a prompt shows by default
    prompt(code, piece, like=None)  -> the prompt's text
    intake(code, piece, text)       -> the path written (raises Refused)

    python3 lib/langprompts.py ca conventions [--like es]      print a prompt
    python3 lib/langprompts.py ca conventions --answer FILE    take an answer in
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import languages                                               # noqa: E402

LANG_FILES = os.path.join(HERE, "lang")
LANG_DOCS = os.path.join(ROOT, "docs", "lang")
STARTERS = os.path.join(ROOT, "markdown", "exlex", "starters")
REGISTRY = os.path.join(HERE, "languages.json")

# the sections every docs/lang/<code>.md has, in order (docs/lang/_template.md)
SECTIONS = ("The text field", "Reading", "Transliteration", "Vocabulary", "Never gloss", "Chunking", "Example")

PIECES = {
    "conventions": ("Annotation conventions", "docs/lang/{code}.md"),
    "howto": ("\"How to read this\" page", "lib/lang/{code}.tex"),
    "starter": ("Studio starter document", "markdown/exlex/starters/{code}.md"),
    "examples": ("Examples", "the language's row (\"examples\")"),
    "lookup-rules": ("Lookup rules", "lib/lang/{code}.lookup.json"),
    "chunk-rules": ("Chunking rules", "lib/lang/{code}.chunk.json"),
}


class Refused(ValueError):
    """An answer Parseh cannot read, in a sentence a person can act on."""


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    return path


def like_for(code):
    """The related language a prompt shows when nobody names one: the row's
    own `like` (newlang.py --like), else the one whose files fit the script --
    Italian for a Latin script, Arabic for one written right to left, Hindi for
    another script of its own, Japanese for one without spaces."""
    L = languages.LANGS.get(code)
    own = getattr(L, "like", None)
    if own and own != code and languages.LANGS.get(own):
        return own
    if L.script == "latin":
        return "it"
    if L.dir == "rtl":
        return "ar"
    if not L.word_sep:
        return "ja"
    return "hi"


def _row_facts(L):
    keep = ("name", "native", "script", "dir", "word_sep", "reading", "words", "require_tr",
            "translit_label", "vb_forms", "vb_labels", "compounds")
    facts = {k: getattr(L, k, None) for k in keep}
    facts["code"] = L.code
    facts["marks_to_strip"] = L.strip_range
    facts["passes"] = [{"key": p["key"], "name": p.get("name"), "title": p.get("title")} for p in L.passes]
    return json.dumps(facts, ensure_ascii=False, indent=1)


def _js_macros(code):
    """The gloss-button examples lib/vocbuttons.js holds for one of the eleven."""
    try:
        src = _read(os.path.join(HERE, "vocbuttons.js"))
    except OSError:
        return {}
    m = re.search(r"\n    %s: \{(.*?')\}" % re.escape(code), src, re.S)
    if not m:
        return {}
    out = {}
    for k, v in re.findall(r"(dw|vb|bw|pw): '((?:[^'\\]|\\.)*)'", m.group(1)):
        out[k] = v.encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")
    return out


def _model(piece, like):
    """The related language's own file for this piece, as the prompt shows it."""
    if piece == "conventions":
        return _read(os.path.join(LANG_DOCS, like + ".md"))
    if piece == "howto":
        tex = _read(os.path.join(LANG_FILES, like + ".tex"))
        i = tex.find("\\newcommand{\\FrankHowTo}")
        return tex[i:] if i >= 0 else tex
    if piece == "starter":
        return _read(os.path.join(STARTERS, like + ".md"))
    if piece == "examples":
        L = languages.LANGS.get(like)
        ex = {k: v for k, v in (L.examples or {}).items() if k in ("dict", "corpus", "model")}
        ex["macros"] = (L.examples or {}).get("macros") or _js_macros(like)
        return json.dumps(ex, ensure_ascii=False, indent=1)
    path = os.path.join(LANG_FILES, "%s.%s.json" % (like, piece.split("-")[0]))
    return _read(path) if os.path.exists(path) else ""


_ASK = {
    "conventions": """\
Write docs/lang/{code}.md: the annotation conventions for {name}. Every prompt Parseh copies for a
chatbot that glosses a book or a video in {name} carries this file, so it is written as instructions
to an annotator. Parseh cuts it per prompt by its {{{{?flag}}}} ... {{{{/flag}}}} blocks ({{{{?book}}}},
{{{{?video}}}}, {{{{?studio}}}}, {{{{?new}}}}, {{{{?classic}}}}, {{{{?ipa}}}} and the like: the text inside goes only into
the prompts that flag names): keep every block the model has, around the same kind of text. Below is the same file for {like_name}: follow its seven sections exactly, with these
headings, in this order: {sections}. Keep every rule that holds for {name} as well, rewrite the ones
that do not, and give every example in {name}. Every sound the Transliteration section shows is written
twice, in the usual scheme and in IPA, as the model does. The Vocabulary section's verb paragraph must
match the row: a \\vb gives {vb_forms}, then the meaning, and prints {vb_labels} before the second and
the third. End with a worked Example in the model's format.""",
    "howto": """\
Write \\FrankHowTo for {name}: the "How to read this" page at the front of every printed book. Below is
the definition for {like_name}. A passage of {name} comes {npasses}: {passes}. Write one paragraph per
pass in the second person, in English, then one on the transliteration scheme (what its marks stand
for) and one on how verbs are given ({vb_forms}, then the meaning). Set a word of {name} inside the
English as the model does. The answer is the whole \\newcommand{{\\FrankHowTo}}{{%...}} definition and
nothing else: no #, no \\def, no \\input and no other definition.""",
    "starter": """\
Write markdown/exlex/starters/{code}.md: the document Parseh's studio opens when somebody presses +New
for {name}. It is a guided tour, in English, of everything a document can hold, with every example in
{name} and one exercise of every kind. Below is the one for {like_name}: keep its structure, its
headings and every feature it shows (lists, tables, footnotes, links, pictures, a recording, a video,
formulas, every exercise), and replace every {like_name} word, sentence and remark about {like_name}
with {name} and what is true of it. Its front matter says `target: {code}` and `title: New {name} note`.
Keep the asset file names the model uses (pictures, the recording): they are the studio's own.""",
    "examples": """\
Write the examples Parseh shows for {name}, as one JSON object with the same keys as {like_name}'s
below:
- "dict": [a headword, how it is said or "" where the spelling says it, its part of speech, [its
  senses]] -- a word a learner meets early, ideally one with two unrelated senses;
- "corpus": [a sentence, its English translation], with the shared word marked <m>…</m> in both;
- "model": [a sentence, an English translation of it];
- "macros": what each gloss button writes, in the conventions of docs/lang/{code}.md: "dw" a word,
  "vb" a verb with all seven groups ({vb_forms}, each followed by its sound in the usual scheme --
  an empty group where the conventions leave it empty -- then the meaning), "bw" a compound, "pw" a
  word inside a meaning.""",
    "lookup-rules": """\
Write lib/lang/{code}.lookup.json: how a word of {name} on the page is turned into something
Wiktionary's {name} dictionary can be asked about. Below is {like_name}'s; keep its keys
and its format ("affixes": a list of {{"prefix" or "suffix", optional "add", optional "after",
optional "prefer", "note"}}, tried longest first; "fold"; "also_peel"). Write the rules {name} needs
and drop the ones it does not: the elided and contracted forms written onto a word, the pronouns
attached after a verb, and the endings the dictionary has no page for. Every "_comment" key says why,
in English.""",
    "chunk-rules": """\
Write lib/lang/{code}.chunk.json: how {name} phrases hold together, for Parseh's offline chunker.
Below is {like_name}'s; keep its keys ("np_head": initial or final, "adposition": before or after,
"bind_forward": regexes of {name}'s own words that are never finished on their own -- not
{like_name}'s -- "min", "max") and say in each "_why"/"_comment" key why, in English.""",
}


def prompt(code, piece, like=None):
    """The text a person copies to a chatbot to have it write `piece` for `code`."""
    if piece not in PIECES:
        raise Refused("%r is not a piece: %s" % (piece, ", ".join(PIECES)))
    L = languages.LANGS.get(code)
    if L is None:
        raise Refused("%r is not a language of this Parseh" % code)
    like = like or like_for(code)
    M = languages.LANGS.get(like)
    if M is None:
        raise Refused("%r is not a language of this Parseh" % like)
    model = _model(piece, like)
    if not model:
        # A RELATIVE WITHOUT THIS FILE (Spanish has no lookup rules: its dictionary needs none) lends the
        # nearest language that has one, and the prompt says whose it is
        for other in ("it", "fr", "es", "de", "ar", "fa", "ja"):
            if other != code and languages.LANGS.get(other) and _model(piece, other):
                like, M, model = other, languages.LANGS[other], _model(piece, other)
                break
        else:
            raise Refused("No language has %s to show as a model." % PIECES[piece][0].lower())
    ask = _ASK[piece].format(
        code=code, name=L.name, like_name=M.name, sections=", ".join(SECTIONS),
        vb_forms=", ".join(L.vb_forms or []), vb_labels=" / ".join(L.vb_labels or []),
        npasses={1: "once", 2: "twice", 3: "three times", 4: "four times", 5: "five times"}.get(
            len(L.passes), "%d times" % len(L.passes)),
        passes="; ".join(p.get("title", p["key"]) for p in L.passes))
    return ("You are helping to add {name} ({native}, code {code}) to Parseh, a toolbox for reading a "
            "language with every sentence glossed.\n\n{ask}\n\nWhat Parseh knows of {name} (its row):\n"
            "````json\n{facts}\n````\n\n{like_name}'s, as the model (between the lines of four backticks):\n"
            "````\n{model}\n````\n\n"
            "Answer with {what} alone, between a line of four backticks (````) and another: the file may hold "
            "fences of three of its own.\n").format(
                name=L.name, native=L.native, code=code, ask=ask, facts=_row_facts(L),
                like_name=M.name, model=model.rstrip(),
                what={"howto": "the definition", "examples": "the JSON object", "lookup-rules": "the JSON",
                      "chunk-rules": "the JSON"}.get(piece, "the file"))


def _unfence(text):
    """The answer without the chatbot's fence and remarks around it.

    THE OUTERMOST FENCE, NOT THE FIRST PAIR: a conventions file holds fences
    of its own (the Example's JSON), and taking the first ``` pair cut every
    such answer short at its first inner fence.  The prompt asks for four
    backticks; a chatbot that used three is read from its first fence line to
    its last bare one."""
    text = (text or "").replace("\r\n", "\n").strip()
    lines = text.split("\n")
    for tick in ("````", "```"):
        opens = [i for i, l in enumerate(lines) if l.strip().startswith(tick)
                 and not l.strip().startswith(tick + "`")]
        if len(opens) >= 2:
            first = opens[0]
            # an answer that is the file itself, unfenced, starts the way the file does before any
            # fence of its own: a heading, front matter, a JSON object, a \newcommand
            if any(l.lstrip().startswith(("#", "---", "{", "\\")) for l in lines[:first]):
                break
            bare = [i for i in opens if lines[i].strip() == tick and i > first]
            if bare:
                return "\n".join(lines[first + 1:bare[-1]]).strip() + "\n"
    return text + "\n"


def _json(text, piece):
    try:
        data = json.loads(text)
    except ValueError as e:
        raise Refused("This is not JSON Parseh can read (%s). Ask the chatbot for the JSON alone." % e) from None
    if not isinstance(data, dict):
        raise Refused("The answer is JSON, but not one object.")
    return data


def _compact(value):
    """A row's value in the registry's own style: a dict one key to a line,
    each value on that line; a list of dicts one to a line; anything else on
    one line."""
    if isinstance(value, dict) and value:
        inner = ",\n".join("      %s: %s" % (json.dumps(k, ensure_ascii=False), json.dumps(v, ensure_ascii=False))
                            for k, v in value.items())
        return "{\n%s\n    }" % inner
    if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
        return "[\n%s\n    ]" % ",\n".join("      " + json.dumps(v, ensure_ascii=False) for v in value)
    return json.dumps(value, ensure_ascii=False)


def _set_row(code, key, value):
    """Put `key` into the language's row: this machine's (config/languages.json),
    or Parseh's own (lib/languages.json), spliced in so that every other byte
    stays as it was."""
    store = languages.read_store()
    if code in store:
        store[code][key] = value
        languages.write_store(store)
        return languages.PERSONAL
    text = _read(REGISTRY)
    m = re.search(r'\n  "%s": \{' % re.escape(code), text)
    if not m:
        raise Refused("%s has no row to write into" % code)
    end = text.index("\n  }", m.end())
    body = _compact(value)
    k = text.find('\n    "%s": ' % key, m.end(), end)
    if k >= 0:                          # replace the value that is there
        start = k + len('\n    "%s": ' % key)
        _, stop = json.JSONDecoder().raw_decode(text, start)
        text = text[:start] + body + text[stop:]
    else:
        text = text[:end] + ',\n    "%s": %s' % (key, body) + text[end:]
    json.loads(text)
    _write(REGISTRY, text)
    return REGISTRY


def intake(code, piece, text):
    """Check a chatbot's answer for `piece` and write it; the path written."""
    L = languages.LANGS.get(code)
    if L is None:
        raise Refused("%r is not a language of this Parseh" % code)
    body = _unfence(text)
    if len(body.strip()) < 20:
        raise Refused("The answer is empty.")
    if piece == "conventions":
        heads = re.findall(r"(?m)^## +(.+?)\s*$", body)
        missing = [s for s in SECTIONS if s not in heads]
        if missing:
            raise Refused("The conventions lack these sections: %s." % ", ".join(missing))
        if re.search(r"\bTODO\b", body):
            raise Refused("The conventions still say TODO.")
        return _write(os.path.join(LANG_DOCS, code + ".md"), body)
    if piece == "howto":
        m = re.search(r"\\newcommand\{\\FrankHowTo\}\{%.*\}", body, re.S)
        if not m:
            raise Refused("The answer has no \\newcommand{\\FrankHowTo}{%...} definition.")
        if "#" in m.group(0) or body.count("{") != body.count("}"):
            raise Refused("The definition has a # or unbalanced braces, which would stop every book.")
        # a page of prose needs paragraphs, \textbf, \pw and the like, and none of what would let a
        # pasted answer run code or read and write files when a book is built
        bad = re.findall(r"\\(directlua|luaexec|luadirect|latelua|write|immediate|openout|openin|input|include|"
                         r"read|catcode|special|usepackage|RequirePackage|makeatletter|csname|def|edef|gdef|xdef|"
                         r"let|expandafter|scantokens|newcommand|renewcommand|ShellEscape|pdfprimitive)\b",
                         m.group(0)[len("\\newcommand{\\FrankHowTo}"):])
        if bad:
            raise Refused("The page uses \\%s, which a \"How to read this\" page has no need of." % bad[0])
        path = os.path.join(LANG_FILES, code + ".tex")
        tex = _read(path)
        i = tex.find("\\newcommand{\\FrankHowTo}")
        if i < 0:
            raise Refused("lib/lang/%s.tex has no \\FrankHowTo to replace." % code)
        # the definition runs to the brace that closes it: count from its first {
        j, depth = tex.index("{%", i) , 0
        for n in range(j, len(tex)):
            depth += {"{": 1, "}": -1}.get(tex[n], 0)
            if depth == 0:
                break
        head = tex[:i]
        # the placeholder's TODO comment above the definition goes with it
        head = re.sub(r"(?m)^% TODO: this is a placeholder\..*\n(%.*\n)*", "", head)
        head = head.replace("{{TODO}}", "")
        return _write(path, head + m.group(0) + tex[n + 1:])
    if piece == "starter":
        if not re.search(r"(?m)^target: *%s\s*$" % re.escape(code), body):
            raise Refused("The starter's front matter does not say `target: %s`." % code)
        return _write(os.path.join(STARTERS, code + ".md"), body)
    if piece == "examples":
        data = _json(body, piece)
        ex = {}
        for k, n in (("dict", 4), ("corpus", 2), ("model", 2)):
            v = data.get(k)
            if not (isinstance(v, list) and len(v) == n):
                raise Refused("\"%s\" must be a list of %d." % (k, n))
            ex[k] = v
        if not isinstance(ex["dict"][3], list):
            raise Refused("The fourth item of \"dict\" is the list of senses.")
        macros = data.get("macros")
        if macros is not None:
            if not isinstance(macros, dict) or set(macros) - {"dw", "vb", "bw", "pw"}:
                raise Refused("\"macros\" has the keys dw, vb, bw and pw.")
            ex["macros"] = {k: str(v) for k, v in macros.items()}
        return _set_row(code, "examples", ex)
    if piece in ("lookup-rules", "chunk-rules"):
        data = _json(body, piece)
        if piece == "lookup-rules":
            for a in data.get("affixes") or []:
                if not isinstance(a, dict) or not (a.get("prefix") or a.get("suffix")):
                    raise Refused("Every affix needs a \"prefix\" or a \"suffix\": %r" % (a,))
        else:
            if data.get("np_head") not in ("initial", "final") or data.get("adposition") not in ("before", "after"):
                raise Refused("\"np_head\" is initial or final, \"adposition\" before or after.")
            for rx in data.get("bind_forward") or []:
                try:
                    re.compile(rx)
                except re.error as e:
                    raise Refused("%r is not a regular expression (%s)." % (rx, e)) from None
        name = "%s.%s.json" % (code, piece.split("-")[0])
        return _write(os.path.join(LANG_FILES, name), json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    raise Refused("%r is not a piece: %s" % (piece, ", ".join(PIECES)))


def main(argv=None):
    p = argparse.ArgumentParser(prog="langprompts", description=__doc__.split("\n\n")[0])
    p.add_argument("code")
    p.add_argument("piece", choices=tuple(PIECES))
    p.add_argument("--like", help="the related language whose file is the model")
    p.add_argument("--answer", metavar="FILE", help="take the chatbot's answer in from FILE and write it")
    a = p.parse_args(argv)
    try:
        if a.answer:
            print("written: %s" % os.path.relpath(intake(a.code, a.piece, _read(a.answer)), ROOT))
        else:
            sys.stdout.write(prompt(a.code, a.piece, a.like))
    except Refused as e:
        print("langprompts: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
