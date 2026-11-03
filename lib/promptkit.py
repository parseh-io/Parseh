#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""One way to assemble every prompt Parseh hands to a chatbot, from three parts.

    assemble(surface, lang, gloss, ...)   -> Assembled: the text and its parts
    parts(surface) / instructions(surface) / contract(surface)
                                          a template's raw parts, marks and all
    language_text(surface, lang)          docs/lang/<code>.md cut to what that prompt needs
    version_line(surface, lang, gloss)    "Parseh prompt · video-region · fa → en · a0.4.2"
    placeholders(surface)                 [(NAME, meaning)]: what a template may name
    blocks(text, flags), flat(text), instructions_of(text)
                                          the {{?flag}}...{{/flag}} blocks of a text
    OPTIONS, resolve(surface, lang, asked, facts), describe(...), header_fields(...)
                                          the choices a person makes for ONE prompt: the
                                          scheme of the transliteration (usual or IPA) and the
                                          short vowels (Persian, Arabic)

docs/prompt-kit.md is the guide; this is what it rests on.

A SURFACE is one place a prompt is handed out from (SURFACES: the studio's
page and its exercise dialog, the video and the book from scratch, a stretch
of either to gloss again, the transcript tidy, Ask LLM).  Each has ONE
readable template, and the file is the whole prompt: nothing a person reads
in a prompt is written anywhere else.

THE THREE PARTS, always in this order:

  1. the INSTRUCTIONS -- how to do the job: the rules, the language's
     conventions, the method.  Parseh's, or a person's own (assemble takes
     them as an argument); in a template, everything outside a mark;
  2. the answer CONTRACT -- the shape of the answer and how to send it: one
     fenced block, the JSON, several messages, a caption given twice taken
     from the later block, the studio's file-or-fence.  Always Parseh's, for
     every prompt whose answer Parseh reads back; marked in the template
     with {{?contract}}...{{/contract}};
  3. the DATA -- the captions, the chunks, the page, the question.  Always
     Parseh's, always last; marked {{?data}}...{{/data}} where the template
     holds a frame for it (the caller may also hand the data in whole).

A person's instructions may replace or extend the first and never touch the
other two: that is what lets Parseh check an answer whatever was asked.

BLOCKS AND PLACEHOLDERS.  {{?flag}}...{{/flag}} is kept where the flag is
true and gone where it is not (blocks may hold blocks); {{NAME}} is filled
from what the caller gives.  Both are the same in every template, in the
language files and in a person's own instructions.  THE KIT NEVER HANDS OUT
A PROMPT THAT STILL CARRIES `{{`: that is a template naming what nothing
fills, a bug, and it is refused in words (PromptError) rather than sent to a
chatbot.  A block whose flag the caller never gave is refused the same way,
because a mistyped flag would otherwise take its text out without a word.
The data, and what a caller marks `verbatim`, are never looked into: a
book's title or a caption may say `{{` and be right.  A flag or a placeholder
given `Open(words)` is the one thing resolved NOT here but by whoever reads the
text (lib/skills.py writes a skill once, for every request): it stays as
`⟦if words⟧ … ⟦end words⟧` or `⟨words⟩`.

WHAT THE MARKS COST.  Taking the marks out of a template gives the file as it
was before it was split (flat() does exactly that, for a page that fills a
template itself), so a mark sits against the words it belongs to and never
adds a character that a reader of the prompt would see.
"""
import io
import os
import re
import sys
from collections import namedtuple

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import languages                                                # noqa: E402
import version                                                  # noqa: E402

LANG_DOCS = os.path.join(ROOT, "docs", "lang")

# The prompts of the toolbox, by where a person gets them.  `ask` is assembled
# in the browser (lib/llm.js); it is named here so that the version line, a
# person's saved prompts and the editor speak of it as they speak of the
# others.  The one that is a file handed over as it is (youtube/PROMPT.md) is
# not a surface: there is nothing to assemble.
SURFACES = ("studio-doc", "studio-exercises", "video-new", "video-region",
            "book-region", "book-new", "transcript-tidy",
            "asr-suspect", "asr-full", "asr-workspace", "ask")
# the ones whose answer Parseh reads back, and which therefore always carry
# its contract (book-new's "answer" is a book, checked by the tools the agent
# runs)
READS_BACK = ("studio-doc", "studio-exercises", "video-new", "video-region",
              "book-region", "transcript-tidy", "asr-suspect", "asr-full", "asr-workspace")
# the words a mode adds to the version line; the default mode says nothing
MODE_WORDS = {"regloss": "re-gloss", "perfield": "per field"}

# the one rule every gloss prompt embeds by {{MEANING_RULE}}: written once, so that the
# prompts and the guide never say two things about what a meaning is
MEANING_RULE = os.path.join(ROOT, "docs", "meaning-rule.md")
# the one rule for what an analyzer's evidence is (lib/evidence.py), in the locked part of a stretch's prompt only
# while a chunk carries some, so that a person's own instructions cannot lose it (a0.6.0)
EVIDENCE_RULE = os.path.join(ROOT, "docs", "analysis-evidence.md")

TEMPLATES = {
    "studio-doc": os.path.join(ROOT, "markdown", "exlex", "PROMPT.md"),
    "studio-exercises": os.path.join(ROOT, "markdown", "exlex", "EXERCISES_PROMPT.md"),
    "video-new": os.path.join(ROOT, "youtube", "docs", "chat-prompt.md"),
    "video-region": os.path.join(ROOT, "docs", "region-prompt.md"),
    "book-region": os.path.join(ROOT, "docs", "region-prompt.md"),
    "book-new": os.path.join(ROOT, "docs", "new-book-prompt.md"),
    "asr-suspect": os.path.join(ROOT, "docs", "asr-suspect-prompt.md"),
    "asr-full": os.path.join(ROOT, "docs", "asr-full-prompt.md"),
    "asr-workspace": os.path.join(ROOT, "docs", "asr-workspace-prompt.md"),
}
# a template that lives in the code that uses it (the transcript tidy's) says
# so with register(), so that parts() finds it without importing that module
_REGISTERED = {}

CONTRACT, DATA = "contract", "data"
_MARKS = (CONTRACT, DATA)
_TAG = re.compile(r"\{\{([?/])([A-Za-z_]\w*)\}\}")
_PLACEHOLDER = re.compile(r"\{\{([A-Za-z_]\w*)\}\}")
_HELD = "\x00%d\x00"
_HELD_AT = re.compile("\x00(\\d+)\x00")

Parts = namedtuple("Parts", "instructions contract data")


class Open(object):
    """WHAT A FLAG OR A PLACEHOLDER IS GIVEN WHEN THE REQUEST, NOT THE CALLER, SAYS WHAT IT IS (lib/skills.py).
    A skill is written once and read for many requests: where the answer is the request's own, the
    block stays in the text between two visible marks, `⟦if <words>⟧ … ⟦end <words>⟧`, and the
    placeholder as `⟨<words>⟩`, and whoever reads the skill settles them from the request's header.
    `words` is how the condition is said to that reader.  Everything else is resolved here as ever."""
    IF, END, SLOT = "⟦if %s⟧", "⟦end %s⟧", "⟨%s⟩"

    def __init__(self, words):
        self.words = words


class PromptError(ValueError):
    """A prompt that cannot be made, and why: a bug in a template or in the code
    that fills it, or a person's text naming what does not exist."""


def register(surface, template):
    """Say where a surface's template lives when it is not a file."""
    _REGISTERED[surface] = template


def _known(surface):
    if surface not in SURFACES:
        raise PromptError("%r is not a surface of Parseh's prompts (they are: %s)"
                          % (surface, ", ".join(SURFACES)))


# --- the marks ---------------------------------------------------------
class _Block(object):
    def __init__(self, name):
        self.name, self.kids = name, []


def _tree(text):
    """The text as a tree: strings, and blocks holding strings and blocks."""
    top = _Block(None)
    stack, at = [top], 0
    for m in _TAG.finditer(text):
        if m.start() > at:
            stack[-1].kids.append(text[at:m.start()])
        at = m.end()
        kind, name = m.groups()
        if kind == "?":
            block = _Block(name)
            stack[-1].kids.append(block)
            stack.append(block)
        elif len(stack) == 1:
            raise PromptError("{{/%s}} closes a block that was never opened" % name)
        elif stack[-1].name != name:
            raise PromptError("{{/%s}} comes where {{/%s}} was due" % (name, stack[-1].name))
        else:
            stack.pop()
    if len(stack) > 1:
        raise PromptError("{{?%s}} is opened and never closed" % stack[-1].name)
    if at < len(text):
        top.kids.append(text[at:])
    return top


def _walk(block, flags, want, inside=None):
    """The text of a block with its flags resolved.  `want` is the part to take
    (None takes them all, in the order the file has them); `inside` the part
    the block is in, None being the instructions."""
    out = []
    for kid in block.kids:
        if isinstance(kid, str):
            if want is None or (inside or "instructions") == want:
                out.append(kid)
        elif kid.name in _MARKS:
            if inside:
                raise PromptError("{{?%s}} inside {{?%s}}: the parts do not nest"
                                  % (kid.name, inside))
            out.append(_walk(kid, flags, want, kid.name))
        elif kid.name not in flags:
            raise PromptError("{{?%s}} is a block this prompt does not know (it knows: %s)"
                              % (kid.name, ", ".join(sorted(flags)) or "none"))
        elif isinstance(flags[kid.name], Open):
            inner = _walk(kid, flags, want, inside)
            if inner.strip():
                out.append(Open.IF % flags[kid.name].words + inner + Open.END % flags[kid.name].words)
        elif flags[kid.name]:
            out.append(_walk(kid, flags, want, inside))
    return "".join(out)


def blocks(text, flags):
    """{{?flag}}...{{/flag}}: kept where the flag is true, gone where it is not.
    A block may hold another.  The marks of the parts (contract, data) are not
    flags: their words are kept, where they stand."""
    return _walk(_tree(text), dict(flags or {}), None)


def flat(text, flags=None):
    """The text as it read before it was split into parts.  For whoever fills a
    template itself (the new-book page does, in the browser) and for the
    studio's editable text."""
    return blocks(text, flags)


def instructions_of(text, flags=None):
    """The instructions of a text that may carry the marks of the parts: the
    text without its contract and its data."""
    return _walk(_tree(text), dict(flags or {}), "instructions")


def _spaces(text):
    """A block taken out leaves its line behind, blank or holding only the
    indent; three or more newlines collapse to a paragraph break."""
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+\n", "\n", text))


def squeeze(text):
    """What assemble() does to each of its parts once the blocks are resolved."""
    return _spaces(text).strip()


def render(text, flags=None, values=None, includes=None, what="text"):
    """A piece of text with its blocks and placeholders resolved and nothing else done to it: its
    whitespace is its own, so that lib/skills.py can write a skill's files from the pieces of a
    template and a reader can put them back together.  `{{` left in it is refused, as assemble()
    refuses it."""
    fill = _Fill(dict(flags or {}), dict(values or {}), dict(includes or {}), {})
    out = fill.render(text)
    check(out, what)
    return out


def take_out(text, names):
    """(text, pieces): `text` with each block named in `names` that stands at its top level (not inside
    another block) kept as it is but for what is inside it -- one placeholder, {{BLOCK_<name>}} -- and
    `pieces`, {name: the raw text that was inside}.  What a skill's SKILL.md keeps in its place and what
    it sends to a file of its own."""
    tree = _tree(text)
    pieces = {}
    for i, kid in enumerate(tree.kids):
        if isinstance(kid, _Block) and kid.name in names:
            if kid.name in pieces:
                raise PromptError("{{?%s}} stands twice at the top level of the text" % kid.name)
            pieces[kid.name] = _serial(kid, False)
            tree.kids[i] = "{{?%s}}{{BLOCK_%s}}{{/%s}}" % (kid.name, kid.name, kid.name)
    return _serial(tree, False), pieces


def _serial(block, inside):
    """A block written out again with its flag blocks still marked: the
    instructions (`inside` False: the marks of the parts, and what is in them,
    left out) or what stands inside one part (`inside` True: another part in
    it is refused)."""
    out = []
    for kid in block.kids:
        if isinstance(kid, str):
            out.append(kid)
        elif kid.name in _MARKS:
            if inside:
                raise PromptError("{{?%s}} inside {{?%s}}: the parts do not nest"
                                  % (kid.name, block.name))
        else:
            inner = _serial(kid, inside)
            if inner.strip():
                out.append("{{?%s}}%s{{/%s}}" % (kid.name, inner, kid.name))
    return "".join(out)


def _pieces(block, part, around=()):
    """The blocks of one part, each written out again and wrapped in the flag
    blocks it stands in: a flag block that holds words of two parts is kept
    around the words of each."""
    out = []
    for kid in block.kids:
        if isinstance(kid, str):
            continue
        if kid.name == part:
            text = _serial(kid, True)
            for flag in reversed(around):
                text = "{{?%s}}%s{{/%s}}" % (flag, text, flag)
            out.append(text)
        elif kid.name not in _MARKS:
            out += _pieces(kid, part, around + (kid.name,))
    return out


def _template(surface):
    if surface in _REGISTERED:
        return _REGISTERED[surface]
    if surface not in TEMPLATES:
        raise PromptError("%s has no template here: %s" % (
            surface, "it is assembled in the browser (lib/llm.js)" if surface == "ask" else
            "hand it in with template=, or import the module that registers it"))
    with io.open(TEMPLATES[surface], encoding="utf-8") as f:
        text = f.read()
    if surface != "studio-doc":
        return text
    # THE STUDIO'S PROMPT IS EVERYTHING AFTER THE FIRST `---` OF ITS FILE: what
    # is above it is the note to whoever opens the file.  store.default_prompt
    # reads it the same way, and a test holds the two to each other.
    lines = text.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "---":
            return "\n".join(lines[i + 1:]).strip() + "\n"
    return text


def parts(surface, template=None):
    """The three parts of a surface's template, raw: the marks of their blocks
    and their placeholders still in them, ready to be shown or edited and to
    be handed back to assemble()."""
    _known(surface)
    tree = _tree(template if template is not None else _template(surface))
    return Parts(_spaces(_serial(tree, False)).strip(),
                 *["\n\n".join(_spaces(p).strip() for p in _pieces(tree, mark))
                   for mark in _MARKS])


def instructions(surface, template=None):
    return parts(surface, template).instructions


def contract(surface, template=None):
    return parts(surface, template).contract


# --- what a template may name ------------------------------------------
_REGION = ("video-region", "book-region")
_GLOSSED = ("video-new", "video-region", "book-region", "book-new")
_WITH_FILE = ("studio-doc", "studio-exercises") + _GLOSSED      # the ones that take a language file
_NEW_VIDEO, _TIDY, _NEW_BOOK = ("video-new",), ("transcript-tidy",), ("book-new",)
_STUDIO = ("studio-doc",)
# THE PROMPTS THAT ASK FOR A TRANSLITERATION, and the ones that write or read a book's or a video's
# own text (where the short vowels of a language have a place): the surfaces of the two OPTIONS below
_TRANSLIT_SURFACES = ("studio-doc", "studio-exercises") + _GLOSSED
_MARKS_SURFACES = _GLOSSED
_PLACEHOLDERS = (
    ("LANGUAGE", "the language's name, in English (Persian)", "*"),
    ("LANGUAGE_NATIVE", "its name in itself", "*"),
    ("LANGUAGE_CODE", "its code in the registry (fa)", "*"),
    ("TR_LABEL", "what its transliteration is called (rōmaji, pinyin ...), or IPA where the "
                 "prompt asks for it", "*"),
    ("TR_SCHEME", "the scheme the transliteration is written in: IPA, or the language's usual one",
     _TRANSLIT_SURFACES),
    ("MARKS_RULE", "what is asked of the short vowels: write them, or leave the text as it is "
                   "(empty if none)", _MARKS_SURFACES),
    ("LANG_CONVENTIONS", "the language's conventions (docs/lang/<code>.md), cut to what "
                         "this prompt needs", _WITH_FILE),
    ("GLOSS_LANGUAGE", "the language the meanings are written in (English)", _GLOSSED),
    ("GLOSS_CODE", "its code (en)", _GLOSSED),
    ("MEANING_RULE", "the rule for what a chunk's meaning says (docs/meaning-rule.md)", _GLOSSED),
    ("EVIDENCE_RULE", "the rule for what an analyzer's `analysis` is (docs/analysis-evidence.md)", _REGION),
    ("EVIDENCE_HELPER", "how to ask the analyzers about a text, where they are in use; nothing where not", _NEW_BOOK),
    # the studio's own prompt (markdown/app/promptboxes.py fills them)
    ("OWN_MARKS", "the target's own punctuation marks, said in words", _STUDIO),
    ("ALT_FONT", "the key of the language's alternate face (nastaliq, gothic)", _STUDIO),
    ("LATEX_THEMES", "the LaTeX themes this machine has, each with what it adds", _STUDIO),
    ("EXERCISE_BLOCKS", "what an exercise is, per type (EXERCISES_PROMPT.md's shared section)", _STUDIO),
    # a stretch of a book or a video (lib/glossregion.py)
    ("A_LANGUAGE", "the language's name with its article: a Persian, an Italian", _REGION),
    ("SURFACE", "what is glossed: a Persian reading edition, the captions of a Persian "
                "video", _REGION),
    ("SURFACE_NOUN", "book or video", _REGION),
    ("OTHER_SURFACE", "video or book: the one this is not", _REGION),
    ("GLOSS_NOTE", "\", not in English\" when the meanings are not written in English, "
                   "else nothing", _REGION),
    ("FIELD_LIST", "the fields a chunk is glossed in, said as a list", _REGION),
    ("TEXT_FIELDS", "the fields that are plain text", _REGION),
    ("REQUIRED", "the fields every glossed chunk must carry", _REGION),
    ("READING_FIELD", "kana where the language has a reading, else tr", _REGION),
    ("UNIT", "sentence or caption", _REGION),
    ("UNITS", "sentences or captions", _REGION),
    ("LIST_KEY", "the key of the list of units in the JSON", _REGION),
    ("ADDRESS", "how a unit is named in the JSON", _REGION),
    ("ABOUT", "the facts of this book or video and of this stretch (its title, its "
              "chunks to gloss)", _REGION),
    ("DATA", "the stretch, as the one JSON document the answer fills in", _REGION),
    # a video from scratch (youtube/lib/ytpages.py)
    ("CONVENTIONS", "the conventions every video follows (youtube/docs/conventions.md)",
     _NEW_VIDEO),
    ("KANA_LINE", "the line about the reading field, where the language has one", _NEW_VIDEO),
    ("WORDS_LINE", "the line about the words field, where the language has one", _NEW_VIDEO),
    ("WORDS_CHECK", "the same, as an item of the check list", _NEW_VIDEO),
    ("WORDS_RECEIVED", "the paragraph about the machine's word division under a caption",
     _NEW_VIDEO),
    ("TR_RULE", "which fields every chunk carries in this language", _NEW_VIDEO),
    ("GLOSSARY", "the word list of a family of videos, when one is asked for", _NEW_VIDEO),
    # the transcript tidy (youtube/lib/tidy.py)
    ("BARE", "a sentence for a transcript that carries almost no punctuation", _TIDY),
    ("MARKS", "the language's full stop and question mark", _TIDY),
    ("EXAMPLE", "what one caption of the answer stands for", _TIDY),
    ("EXAMPLE2", "what the next one stands for", _TIDY),
    ("REP", "a word the transcript says three times running", _TIDY),
    ("PANEL", "the transcript, as the panel shows it", _TIDY),
    # a book made in place (lib/making.py fills them when it writes the folder's AGENTS.md)
    ("TITLE_LATIN", "the book's title in Latin letters", _NEW_BOOK),
    ("TITLE_NOTE", "the title in its own script, in parentheses, when it differs", _NEW_BOOK),
    ("AUTHOR_LATIN", "its author in Latin letters", _NEW_BOOK),
    ("BOOK_DIR", "the book's folder, in full: the only place the agent writes", _NEW_BOOK),
    ("BOOK_REL", "the same, under books/", _NEW_BOOK),
    ("ROOT", "Parseh's own folder", _NEW_BOOK),
    ("LIB", "Parseh's tools: its lib/ folder, in full", _NEW_BOOK),
    ("PYTHON", "Parseh's own Python, by its full path", _NEW_BOOK),
    ("ORIGINAL", "the original text, in full", _NEW_BOOK),
    ("PAGES", "which pages of the original to read, said in words, or nothing", _NEW_BOOK),
    ("PAGE_ARGS", "the same as the options of extract_pdf.py", _NEW_BOOK),
    ("CONVENTIONS", "the language's conventions file, in full", _NEW_BOOK),
    ("REFERENCE", "the line about a finished edition to learn from, or nothing", _NEW_BOOK),
    ("EXAMPLES", "the line about the person's finished books in this language, or nothing",
     _NEW_BOOK),
    ("BATCH", "how many paragraphs make a batch", _NEW_BOOK),
    ("BATCH_LAST", "the same, less one", _NEW_BOOK),
    ("LANG_NAME", "the language's name, in English", _NEW_BOOK),
    ("LANG_NATIVE", "its name in itself", _NEW_BOOK),
    ("LANG", "its code", _NEW_BOOK),
    ("LANG_DIGIT_EXAMPLE", "the digit 3 in the language's own digits", _NEW_BOOK),
    ("LANG_LABEL_EXAMPLE", "the label 3.1 in the language's own digits", _NEW_BOOK),
    ("GLOSS_NAME", "the gloss language's name, in English", _NEW_BOOK),
    ("GLOSS", "its code", _NEW_BOOK),
    ("STRIP_NOTE", "what character for character means for this language's text", _NEW_BOOK),
    ("KANA_RULE", "the rule about the reading and words fields, for a language that has "
                  "them", _NEW_BOOK),
    ("KANA_EXAMPLE", "a chunk with those fields", _NEW_BOOK),
    ("WORDS_STEP", "the step that starts the words from the machine's division", _NEW_BOOK),
)


def placeholders(surface=None):
    """[(NAME, meaning)]: every placeholder a template of this surface may name
    (every one, for None).  A prompt naming any other is refused."""
    if surface is not None:
        _known(surface)
    return [(n, m) for n, m, s in _PLACEHOLDERS
            if surface is None or s == "*" or surface in s]


# --- the options of a prompt -----------------------------------------------
# AN OPTION IS A CHOICE A PERSON MAKES FOR ONE PROMPT, explicitly (brief 3.9, 3.10): the scheme
# a transliteration is written in -- the language's usual one, or IPA -- and whether a Persian or
# an Arabic text is given its short vowels.  Both are rows of ONE table, so that the row of
# controls beside a prompt, the routes that make it, the flags a text may use, the version line,
# the header of a skill's request and a person's own prompts all say the same thing about each,
# and a third option is another row here and nothing more.  Where an option is asked is DATA
# (`surfaces`, `offered`), and the condition is the language's record in the registry and never
# its code: a language added later gets the options its record earns.
class OptionError(PromptError):
    """A request that names a value no option has, said to whoever asked; and an option that is
    not one."""


class Option(object):
    """What the kit knows of one option.  `values` are its ids, in the order the row shows them, and
    each is the NAME OF A FLAG that is true while it is chosen (`{{?ipa}}...{{/ipa}}`)."""
    name = ""
    noun = ""                # what it is, for a sentence refusing a value of it
    values = ()
    surfaces = ()            # the prompts that ask it
    aliases = {}             # other spellings of a value a request may use (lower case)
    inactive = None          # the value whose flag stays true where the option does not apply; None: none
    memory = "surface"       # what a device keeps a choice for: "lang" or "surface"
    meaning = {}             # value -> what its flag is for, one line (the editor of a person's own prompt)

    def default(self, surface):
        return self.values[0]

    def offered(self, L):
        """Whether this language has the option at all."""
        return True

    def records(self, L):
        """Whether a book's or a video's own record can hold this option in this language, so that a
        prompt asking for the other value is told that the book would mix the two.  An option that
        is a choice of the moment (the short vowels) is held by none."""
        return False

    def applies(self, surface, L):
        return surface in self.surfaces and L is not None and self.offered(L)

    def label(self, L):
        raise NotImplementedError

    def choices(self, L):
        """[(id, what the row says)] for this language."""
        raise NotImplementedError

    def sentence(self, L):
        """{id: how a sentence names the choice} for the ids the row's words do not fit into one
        ("usual scheme" is "the usual scheme" in a sentence); the others are said as the row says them."""
        return {}

    def suffix(self, value):
        """What the version line ends with for this value ('' says nothing)."""
        return ""

    def header(self, value):
        """The field a skill's request carries for this value ('' says nothing)."""
        return ""

    def parse(self, value):
        """The id a request's value stands for; None where it says none.  OptionError for anything else."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        said = str(value).strip().lower()
        if said in self.values:
            return said
        if said in self.aliases:
            return self.aliases[said]
        raise OptionError("%r is not %s: it is %s" % (value, self.noun, " or ".join(self.values)))


class _Translit(Option):
    """The scheme of a transliteration: the language's usual one, or IPA.  Asked wherever a prompt asks
    for a transliteration -- not on the transcript tidy, and not on Ask LLM, which asks for none."""
    name, noun = "translit", "a way to write the transliteration"
    values = ("classic", "ipa")
    surfaces = _TRANSLIT_SURFACES
    aliases = {"usual": "classic", "default": "classic"}
    inactive = "classic"
    memory = "lang"
    meaning = {"classic": "kept while the transliteration is written in the language's usual scheme",
               "ipa": "kept while the prompt asks for IPA in place of the usual scheme"}

    def offered(self, L):
        return L.ipa != "none"

    def records(self, L):
        # WHERE THE USUAL SCHEME IS IPA (English) THE TWO ARE ONE, and a book cannot mix them
        return L.ipa == "offered"

    def label(self, L):
        return L.translit_label

    def choices(self, L):
        return [("classic", "IPA (already the usual)" if L.ipa == "usual" else "usual scheme"),
                ("ipa", "IPA")]

    def sentence(self, L):
        """{id: how a sentence names the choice}, where that is not what the row says."""
        return {"classic": "the usual scheme"}

    def suffix(self, value):
        return "IPA" if value == "ipa" else ""

    def header(self, value):
        return "translit: ipa" if value == "ipa" else ""


class _Marks(Option):
    """Whether the short vowels are written: for a language whose record has `strip` (Persian and Arabic
    today), on the prompts that write or read a book's or a video's own text."""
    name, noun = "marks", "a setting for the short vowels"
    values = ("nomarks", "marks")
    surfaces = _MARKS_SURFACES
    aliases = {"0": "nomarks", "off": "nomarks", "no": "nomarks", "false": "nomarks",
               "1": "marks", "on": "marks", "yes": "marks", "true": "marks"}
    memory = "surface"
    meaning = {"marks": "kept while the prompt asks for the short vowels to be written",
               "nomarks": "kept while the prompt leaves the text as it is, with no short vowels added"}

    def default(self, surface):
        # THE DEFAULTS KEEP TODAY'S BEHAVIOUR: a book made in place asks for the marks (a reading
        # edition's first pass is the vowelled attempt), and a stretch of a book or a video, or a
        # video from scratch, never changes the text
        return "marks" if surface == "book-new" else "nomarks"

    def offered(self, L):
        return bool(L.strip_range)

    def label(self, L):
        return "short vowels"

    def choices(self, L):
        return [("nomarks", "as they are"), ("marks", "write them")]

    def suffix(self, value):
        return "marks" if value == "marks" else "no marks"

    def header(self, value):
        return "marks: on" if value == "marks" else "marks: off"


OPTIONS = (_Translit(), _Marks())
OPTION_BY_NAME = {o.name: o for o in OPTIONS}


def given(source):
    """The options a request names, as it said them -> {name: value}: from a body, or from a parsed
    query (a value that is a list, as a query holds it, is its first); nothing for what is left out
    or blank.  resolve() reads the values."""
    out = {}
    for opt in OPTIONS:
        value = source.get(opt.name) if hasattr(source, "get") else None
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value is not None and value != "":
            out[opt.name] = value
    return out


def resolve(surface, lang=None, asked=None, facts=None):
    """The options of a prompt as they stand -> {name: id}, only for those that APPLY to this surface
    in this language: what the request asked, else what the book's or the video's own record says
    (`facts`, {name: value}), else the surface's default.

    A value that is none of the option's is refused in words (OptionError), whether the option
    applies or not: a typo is never hidden.  An option that does not apply -- the short vowels of
    Italian, a transliteration on the tidy, IPA for a language whose record offers none -- is left out
    of the answer rather than refused: what a device remembers of one prompt must not stop another,
    and the answer says what was applied.  A fact that cannot be read is data and not a request, and
    is passed over."""
    asked = dict(asked or {})
    stray = sorted(set(asked) - set(OPTION_BY_NAME))
    if stray:
        raise OptionError("%s is not an option of a prompt (they are: %s)"
                          % (", ".join(repr(n) for n in stray), ", ".join(OPTION_BY_NAME)))
    L = _language(lang) if lang is not None else None
    out = {}
    for opt in OPTIONS:
        value = opt.parse(asked.get(opt.name))
        if not opt.applies(surface, L):
            continue
        if value is None:
            try:
                value = opt.parse((facts or {}).get(opt.name))
            except OptionError:
                value = None
        out[opt.name] = value or opt.default(surface)
    return out


def option_flags(surface, lang=None, options=None):
    """The flags the options give a text -> {flag: bool}: one per value, true for the value in force.
    Where an option does not apply its `inactive` value stands (the usual scheme), or none of them
    does (no short-vowel paragraph of a language file is kept for a language that has no marks)."""
    chosen = resolve(surface, lang, options)
    out = {}
    for opt in OPTIONS:
        now = chosen.get(opt.name, opt.inactive)
        for value in opt.values:
            out[value] = value == now
    return out


def option_words(surface, lang, options=None):
    """What the options add to the version line, in the order of the table: ['IPA', 'no marks']."""
    chosen = resolve(surface, lang, options)
    return [w for opt in OPTIONS if opt.name in chosen for w in [opt.suffix(chosen[opt.name])] if w]


def header_fields(surface, lang, options=None):
    """What the options add to the header of a skill's request -> ['translit: ipa', 'marks: on']:
    the usual scheme says nothing, as it does in the version line.  The seam lane G builds the
    request on: every text that says which options a prompt had is this, so that a skill and a
    prompt cannot say two things."""
    chosen = resolve(surface, lang, options)
    return [h for opt in OPTIONS if opt.name in chosen for h in [opt.header(chosen[opt.name])] if h]


def describe(surface, lang, options=None, facts=None):
    """The options a page offers for this prompt -> [{name, label, value, default, fact, record,
    choices, remember}], those that apply and no others: `label` is the language's own word
    (rōmaji, pinyin, transliteration, pronunciation) or the option's, `value` what stands now (the
    request's, else the record's `facts`, else the default), `fact` whether that value is the book's
    or the video's own, `record` whether the book or the video this is asked for holds the option at
    all (it does where `facts` has its key, and the language's scheme can differ from the usual's:
    a prompt that asks for the other value is then told that the book would mix the two, and offered
    to change the book), `remember` what the row keeps the person's choice under on this device.  A
    choice whose name in a sentence is not the row's word has it in `as`."""
    L = _language(lang)
    chosen = resolve(surface, L, options, facts)
    out = []
    for opt in OPTIONS:
        if opt.name not in chosen:
            continue
        try:
            own = opt.parse((facts or {}).get(opt.name))
        except OptionError:
            own = None
        said = opt.sentence(L)
        choices = []
        for i, t in opt.choices(L):
            choice = {"id": i, "label": t}
            if i in said:
                choice["as"] = said[i]
            choices.append(choice)
        out.append({"name": opt.name, "label": opt.label(L), "value": chosen[opt.name],
                    "default": opt.default(surface), "fact": own is not None and chosen[opt.name] == own,
                    "record": opt.name in (facts or {}) and opt.records(L),
                    "choices": choices, "remember": L.code if opt.memory == "lang" else surface})
    return out


def flag_meanings(surface=None):
    """{flag: what it is for}: the options' flags that a text of this surface may use to some purpose
    (every one for None), for the editor of a person's own prompt."""
    return {value: opt.meaning[value] for opt in OPTIONS for value in opt.values
            if surface is None or surface in opt.surfaces}


def unasked_flags(surface):
    """The options' flags a prompt of this surface never has any use for: the other surfaces' (the
    short vowels on the studio's prompt).  They are still known to every text -- a person's prompt
    that names one is not refused -- and only the editor's list leaves them out."""
    return {value for opt in OPTIONS if surface not in opt.surfaces for value in opt.values}


# --- the language's conventions, cut per prompt -------------------------
ALL, VERBATIM, NOTE = "all", "verbatim", "note"
KINDS = ("studio", "region", "new")
KIND = {"studio-doc": "studio", "studio-exercises": "studio", "video-region": "region",
        "book-region": "region", "video-new": "new", "book-new": "new"}
# how each prompt lays the file out: whether it keeps the file's own title, and
# how many levels its headings go down to sit under the prompt's own
LAYOUT = {"studio-doc": (True, 0), "studio-exercises": (True, 0), "video-region": (False, 1),
          "book-region": (False, 1), "video-new": (False, 0), "book-new": (True, 0)}
FIELD = "The text field"
# WHICH SECTION OF docs/lang/<code>.md GOES TO WHICH PROMPT.  The file is the
# ANNOTATOR's and was pasted whole: most of the studio prompt was rules for a
# reading edition's marks that a document never carries, and a region prompt,
# whose chunks are given, carried Chunking.  One row a section, one column a
# kind of prompt; a section nobody lists goes everywhere, so a language that
# adds one is never silently cut.  "" is the file's opening, before its first
# heading.  ALL is the whole section, None nothing; The text field is cut finer:
# the studio takes the note on writing the script and a region prompt the
# paragraph that says the text is verbatim (below).
SECTIONS = {
    #                   studio  region    new
    "":                (None,   ALL,      ALL),
    FIELD:             (NOTE,   VERBATIM, ALL),
    "Reading":         (ALL,    ALL,      ALL),
    "Words":           (None,   ALL,      ALL),
    "Transliteration": (ALL,    ALL,      ALL),
    "Vocabulary":      (None,   ALL,      ALL),
    "Never gloss":     (None,   ALL,      ALL),
    "Chunking":        (None,   None,     ALL),
    "Example":         (None,   ALL,      ALL),
}
# THE NOTE ON WRITING THE SCRIPT is the paragraph that names the studio's mark
# for a run of the target language, `[…]{tl}`.  It stands in The text field of
# the Latin-script languages that have one and at the end of Chunking in
# Turkish and in every language newlang.py adds, so it is found by what it says
# and not by where it sits.  It goes to the studio's prompts, to no other
# prompt that cuts, and stays where it is in the ones that take everything.
# The paragraph a region prompt keeps of The text field is its FIRST, which is
# where every file says the text is verbatim, whatever words it says it in.
_NOTE = re.compile(r"\{tl\}")
# what each prompt has always said where the language has no file yet
_MISSING = {
    "studio-doc": "", "studio-exercises": "",
    "video-region": "(The %s conventions -- transliteration scheme, what to gloss -- are "
                    "not written yet: docs/lang/%s.md is missing. Use a standard, "
                    "consistent romanisation.)",
    "video-new": "(The %s conventions -- transliteration scheme, what to gloss -- are not "
                 "written yet: docs/lang/%s.md is missing. Use a standard, consistent "
                 "romanisation and say which in a note.)",
    "book-new": "(The conventions of %s -- docs/lang/%s.md -- are not written yet: the file "
                "is missing. Ask for them before annotating.)",
}
_MISSING["book-region"] = _MISSING["video-region"]


def surface_flags(surface, lang=None, options=None):
    """The flags every text of a surface may use -- its template, the language's
    file, a person's instructions: book and video, and the kind of prompt it
    is (studio, region, new: what cuts the language's file and what takes it
    all).  `note` is never true: {{?note}}...{{/note}} is a word to whoever
    maintains the file, and no prompt carries it.  With a language, and the
    options a request chose (resolve()), the options' flags too: ipa or
    classic, marks or nomarks -- the last pair false for a language that has no
    short vowels; without a language, the usual scheme and neither of them."""
    flags = {"book": surface.startswith("book-"), "video": surface.startswith("video-"),
             "studio": surface.startswith("studio-"), "region": surface.endswith("-region"),
             "new": surface.endswith("-new"), "note": False}
    if surface in _REGION:
        flags["evidence"] = False       # true only where a chunk carries an analyzer's reading (lib/glossregion.py)
    flags.update(option_flags(surface, lang, options))
    return flags


def _outline(lines):
    """(title, sections): the line of the file's own H1, and for the opening
    lines ("") and every `## ` heading outside a code fence, (name, its line,
    first line of its body, end of its body)."""
    fenced, title, heads = False, None, []
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and title is None and not heads and line.startswith("# "):
            title = i
        elif not fenced and line.startswith("## "):
            heads.append((line[3:].strip(), i))
    ends = [i for _, i in heads] + [len(lines)]
    secs = [("", None, 0 if title is None else title + 1, ends[0])]
    secs += [(name, i, i + 1, ends[k + 1]) for k, (name, i) in enumerate(heads)]
    return title, secs


def _paragraphs(lines, lo, end):
    """[(first, end)]: the blank-line separated blocks of lines[lo:end], a code
    fence being one block, the blank lines inside it and all."""
    out, start, fenced = [], None, False
    for i in range(lo, end):
        if lines[i].lstrip().startswith("```"):
            fenced = not fenced
        if not lines[i].strip() and not fenced:
            if start is not None:
                out.append((start, i))
                start = None
        elif start is None:
            start = i
    if start is not None:
        out.append((start, end))
    return out


def _cut(text, kind, keep_title):
    """[(name, text)]: the file's title and the sections a kind of prompt
    takes of it, in the file's order."""
    lines = text.split("\n")
    title, secs = _outline(lines)
    paras = [_paragraphs(lines, lo, end) for _, _, lo, end in secs]
    said = lambda a, b: bool(_NOTE.search("\n".join(lines[a:b])))
    notes = [(a, b) for ps in paras for a, b in ps if said(a, b)]
    text_of = lambda a, b: "\n".join(lines[a:b])
    out = []
    if keep_title and title is not None:
        out.append(("(title)", lines[title]))
    for (name, head, lo, end), ps in zip(secs, paras):
        how = SECTIONS.get(name, (ALL,) * 3)[KINDS.index(kind)]
        own = [] if kind == "new" else [p for p in ps if p in notes]
        if how is None:
            continue
        if how == NOTE:
            if notes:
                out.append((name, "\n\n".join([lines[head]] + [text_of(a, b) for a, b in notes])))
        elif how == VERBATIM:
            first = [p for p in ps if p not in notes][:1]
            if first:
                out.append((name, lines[head] + "\n\n" + text_of(*first[0])))
        else:
            kept = [i for i in range(lo if head is None else head, end)
                    if not any(a <= i < b for a, b in own)]
            piece = re.sub(r"\n{3,}", "\n\n", "\n".join(lines[i] for i in kept)).strip()
            if piece and piece != (lines[head] if head is not None else ""):
                out.append((name or "(opening)", piece))
    if kind == "studio" and notes and not any(n == FIELD for n, _ in out):
        # a file with no "The text field" of its own has the note all the same
        after_title = 1 if out and out[0][0] == "(title)" else 0
        out.insert(after_title,
                   (FIELD, "\n\n".join(["## " + FIELD] + [text_of(a, b) for a, b in notes])))
    return out


def _language(lang):
    if isinstance(lang, languages.Lang):
        return lang
    return languages.get_or_default(lang if isinstance(lang, str) else None)


def _gloss(gloss):
    if gloss is None or isinstance(gloss, languages.Gloss):
        return gloss
    return languages.gloss_or_default(gloss)


def _language_file(L):
    try:
        with io.open(os.path.join(LANG_DOCS, "%s.md" % L.code), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def language_sections(surface, lang, flags=None, options=None):
    """[(section, text)] of docs/lang/<code>.md as this surface takes it, the
    flags of the file (book, video, studio, and the options' ipa, classic,
    marks, nomarks) resolved; None where the file is not there."""
    if surface not in KIND:
        raise PromptError("%s takes no language file" % surface)
    L = _language(lang)
    text = _language_file(L)
    if text is None:
        return None
    return _cut(blocks(text, dict(surface_flags(surface, L, options), **(flags or {}))),
                KIND[surface], LAYOUT[surface][0])


def _meaning_rule():
    with open(MEANING_RULE, encoding="utf-8") as f:
        return f.read()


def _evidence_rule():
    with open(EVIDENCE_RULE, encoding="utf-8") as f:
        return f.read()


def _tr_scheme(L, ipa):
    """TR_SCHEME: the scheme the transliteration is written in."""
    if ipa or L.ipa == "usual":
        return "IPA"
    return "the usual %s scheme for %s" % (L.translit_label, L.name)


def _marks_rule(L, value):
    """MARKS_RULE: what is asked of the short vowels, nothing where the language has none."""
    if not L.strip_range or value not in ("marks", "nomarks"):
        return ""
    return ("write the short vowels in `fa`" if value == "marks"
            else "leave `fa` as it is, with no short vowels added")


def _common(surface, L, G, chosen=None):
    """The placeholders the kit fills in every prompt of a language (and of a
    gloss language, where the prompt has one), the options in force among them:
    what the transliteration is called, and in which scheme, and the rule for
    the short vowels -- each only for the prompts that publish it."""
    chosen = chosen or {}
    ipa = chosen.get("translit") == "ipa"
    values = {"LANGUAGE": L.name, "LANGUAGE_NATIVE": L.native, "LANGUAGE_CODE": L.code,
              "TR_LABEL": "IPA" if ipa else L.translit_label}
    if surface in _TRANSLIT_SURFACES:
        values["TR_SCHEME"] = _tr_scheme(L, ipa)
    if surface in _MARKS_SURFACES:
        values["MARKS_RULE"] = _marks_rule(L, chosen.get("marks"))
    if G is not None:
        values.update(GLOSS_LANGUAGE=G.name, GLOSS_CODE=G.code)
    return values


# WHAT A PROMPT SAYS OF IPA WHEN THE LANGUAGE'S OWN FILE HAS NOT WRITTEN ITS IPA NOTE (`{{?ipa}}` in
# its Transliteration section), so that the setting works for every language a person has -- one
# they added, one whose note is not written yet -- and never leaves a prompt that says IPA in its
# fields and describes the usual scheme in its conventions with nothing between them.  It says only
# what holds for any language; the file's note, where there is one, says which IPA.  It stands where
# the usual scheme is described (the first words of the Transliteration section) and is said again, in
# one line, after the conventions: a stand-in chatbot that was given it only in front, ahead of a long
# section on the usual scheme and its examples, went on writing the usual scheme (Hindi, nine chunks
# in ten).
_IPA_SAYS = {
    "studio": ("**This prompt asks for IPA, not for the scheme below.** Wherever the rules of this section, or an "
               "example of them, spell a sound in the usual %(label)s scheme of %(lang)s -- in the "
               "transliteration of a `##` heading and in `[word]{translit:…}` -- write IPA instead, and keep "
               "of them only what is not the spelling of a sound. Write broad (phonemic) IPA for the standard "
               "pronunciation of %(lang)s, with no slashes or square brackets around it, and the stress mark "
               "ˈ and the length mark ː where %(lang)s has them. The words themselves are not changed."),
    "gloss": ("**This prompt asks for IPA, not for the scheme below.** Wherever the rules of this section or of "
              "the ones after it, or an example in them, spell a sound in the usual %(label)s scheme of "
              "%(lang)s -- in `tr`, in the sound of every vocabulary entry (`\\dw{word}{sound}`, `\\vb{…}`, "
              "`\\bw{base}{sound}{meaning}`) and in every other place a transliteration is asked for -- write "
              "IPA instead, and keep of them only what is not the spelling of a sound (which chunks carry a "
              "`tr`, how words are parted). Write broad (phonemic) IPA for the standard pronunciation of "
              "%(lang)s, with no slashes or square brackets around it, and the stress mark ˈ and the length "
              "mark ː where %(lang)s has them, one scheme from the first chunk to the last. The text itself, "
              "any reading in kana and the language of the meanings are not changed."),
}
_IPA_AGAIN = {
    "studio": "*This prompt asks for IPA: a sound written above in the usual scheme is written in IPA in "
              "your answer.*",
    "gloss": "*This prompt asks for IPA: a sound written above in the usual scheme -- in a rule or in an "
             "example -- is written in IPA in your answer, in `tr` and in every vocabulary entry.*",
}


def _says_ipa(L):
    """What a prompt says of IPA for a language whose file has no IPA note of its own, or None."""
    text = _language_file(L)
    if text is not None and re.search(r"\{\{\?ipa\}\}", text):
        return None
    return {"label": L.translit_label, "lang": L.name}


def _with_ipa(secs, kind, said):
    """The sections of a language's conventions with what a prompt says of IPA put in: after the heading
    of the Transliteration section (in front of everything where there is none), and once more at the
    end."""
    way = "studio" if kind == "studio" else "gloss"
    out, put = [], False
    for name, text in secs:
        if name == "Transliteration" and not put:
            head, _, rest = text.partition("\n")
            text, put = "%s\n\n%s\n\n%s" % (head, _IPA_SAYS[way] % said, rest.lstrip("\n")), True
        out.append((name, text))
    if not put:
        out.insert(0, ("(IPA)", _IPA_SAYS[way] % said))
    out.append(("(IPA again)", _IPA_AGAIN[way]))
    return out


def language_text(surface, lang, flags=None, gloss=None, options=None):
    """The language's conventions as this surface takes them, with the names
    the kit knows (LANGUAGE, and GLOSS_LANGUAGE where a gloss is given) filled
    in; where the file is not there, the one line the prompt has always said
    instead.  With IPA chosen (`options`, as resolve() reads them) a file that
    has no IPA note of its own gets the general paragraph above, where it
    describes the usual scheme and once more at its end."""
    L = _language(lang)
    chosen = resolve(surface, L, options)
    secs = language_sections(surface, L, flags, chosen)
    if secs is None:
        return _MISSING[surface] % (L.name, L.code) if _MISSING[surface] else ""
    if chosen.get("translit") == "ipa" and secs:
        said = _says_ipa(L)
        if said:
            secs = _with_ipa(secs, KIND[surface], said)
    down, fenced, out = LAYOUT[surface][1], False, []
    for line in "\n\n".join(t for _, t in secs).split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif down and not fenced and re.match(r"#{2,5} ", line):
            line = "#" * down + line
        out.append(line)
    known = _common(surface, L, _gloss(gloss), chosen)
    said = _PLACEHOLDER.sub(lambda m: known.get(m.group(1), m.group(0)), "\n".join(out).strip())
    return (_variety_says(L) + said) if L.variety else said


def _variety_says(L):
    """What a prompt says, before the conventions, of a text written in one of the
    language's varieties (Arabic's dialects: the book's or the video's
    `variety`): which, and what that changes; the conventions after it are the
    language's, and hold wherever the variety does not say otherwise."""
    std = L.standard_name or ("standard " + L.name)
    return ("**This text is in %s**, not in %s. Read every word as %s: gloss what it means there, give a "
            "word only %s has as that word (do not replace it with a %s synonym), and write `tr` as it is said "
            "in %s. The conventions below are %s's, and hold wherever %s does not say otherwise.\n\n"
            % (L.variety_name, std, L.variety_name, L.variety_name, std, L.variety_name, L.name, L.variety_name))


# --- the version line ---------------------------------------------------
def version_line(surface, lang=None, gloss=None, mode=None, custom=None, options=None):
    """The one line every copied prompt opens with, so that an answer can be
    traced to what asked for it: which prompt, in which languages, from which
    Parseh; then the mode where there is one, what the options say -- `IPA`
    where the transliteration is in IPA, `marks` or `no marks` where the
    language has short vowels (the defaults where `options` says nothing) --
    and last the name of a person's own prompt, which is free text and so
    stands where nothing can be mistaken for it.  The version is read from
    lib/version.py when the line is made."""
    said = ""
    if lang is not None:
        said = _language(lang).code
        if gloss is not None:
            said += " → " + _gloss(gloss).code
    words = ["Parseh prompt", surface, said, version.VERSION,
             MODE_WORDS.get(mode, mode) if mode and mode != "fill" else ""]
    if lang is not None:
        words += option_words(surface, lang, options)
    words.append("custom: " + custom if isinstance(custom, str) else "custom" if custom else "")
    return " · ".join(w for w in words if w)


# --- the assembled prompt -----------------------------------------------
class Assembled(object):
    """A prompt and the parts it is made of; str() of it is the prompt.  `options` is what the
    options came to for it ({name: id}, resolve()): only those that applied."""

    def __init__(self, surface, header, instructions, contract, data, options=None):
        self.surface, self.header = surface, header
        self.instructions, self.contract, self.data = instructions, contract, data
        self.options = dict(options or {})

    @property
    def text(self):
        return "\n\n".join(x for x in (self.header, self.instructions, self.contract,
                                       self.data) if x) + "\n"

    def __str__(self):
        return self.text

    def sizes(self):
        """Characters of each part, and of the whole."""
        n = {k: len(getattr(self, k)) for k in ("header", "instructions", "contract", "data")}
        n["total"] = len(self.text)
        return n


class _Fill(object):
    """What fills a template: the flags, the short values, the includes (texts
    that are templates in their own right, filled the same way) and what is
    `verbatim`, held aside and put in after every check."""

    def __init__(self, flags, values, includes, verbatim):
        self.flags, self.values, self.includes = flags, values, includes
        self.verbatim, self.held = verbatim, []

    def render(self, text, depth=0):
        return _PLACEHOLDER.sub(lambda m: self._one(m, depth), blocks(text, self.flags))

    def _one(self, m, depth):
        name = m.group(1)
        if name in self.verbatim:
            self.held.append(self.verbatim[name])
            return _HELD % (len(self.held) - 1)
        if name in self.values:
            got = self.values[name]
            return Open.SLOT % got.words if isinstance(got, Open) else got
        if name in self.includes:
            if depth > 5:
                raise PromptError("{{%s}} holds itself" % name)
            got = self.includes[name]
            return _spaces(self.render(got() if callable(got) else got, depth + 1)).strip()
        return m.group(0)

    def close(self, text):
        return _HELD_AT.sub(lambda m: self.held[int(m.group(1))], text)


def check(text, surface):
    """The kit's promise -- nothing that still holds a `{{` is handed out -- for
    whoever puts a piece of Parseh's own text into a prompt by hand: assemble()
    keeps it for the parts it makes."""
    if "{{" in text:
        left = sorted(set(re.findall(r"\{\{[?/]?\w*\}?\}?", text)))
        raise PromptError(
            "the %s prompt still carries %s: a placeholder or block the template names "
            "and nothing fills -- a bug in the template or in the code that fills it"
            % (surface, ", ".join(left[:4])))


def assemble(surface, lang=None, gloss=None, *, flags=None, values=None, verbatim=None,
             includes=None, lead=None, extras=(), data=None, instructions=None,
             mode=None, custom=None, template=None, options=None):
    """The prompt of a surface, from its three parts.

    lang, gloss   Lang / Gloss objects or their codes; the gloss only where the
                  prompt has one (it is in the version line)
    flags         the flags the template's blocks ask for, beside the surface's own
    values        {NAME: text} for the placeholders; the language's names are
                  there already (placeholders() says which)
    verbatim      {NAME: text} put in last and never looked into: data
    includes      {NAME: template text, or a function making it} filled like the
                  template itself; LANG_CONVENTIONS is one already
    lead, extras  final text put before the instructions and after them: what
                  the caller has made (the studio's target line, the RTL rule)
    data          the data part, whole, put after the template's own frame
    instructions  a person's instructions, in place of Parseh's; the contract
                  and the data stay Parseh's and come after them
    mode, custom  what the version line adds
    template      the template's text, where it is not a file's
    options       what a request chose, {name: value} (the options' table, resolve()): the
                  scheme of the transliteration and the short vowels.  What they came to is
                  on the Assembled (`options`); a value that is none of an option's is refused"""
    _known(surface)
    L, G = _language(lang), _gloss(gloss)
    chosen = resolve(surface, L, options)
    flags = dict(surface_flags(surface, L, chosen), **(flags or {}))
    if instructions is not None and any(m.group(2) in _MARKS for m in _TAG.finditer(instructions)):
        raise PromptError("instructions cannot carry the answer contract or the data: "
                          "Parseh adds those itself, after them")
    given = parts(surface, template)
    values = dict(_common(surface, L, G, chosen), **(values or {}))
    includes = dict(includes or {})
    if surface in KIND:
        includes.setdefault("LANG_CONVENTIONS",
                            lambda: language_text(surface, L, flags, options=chosen))
    if surface in _GLOSSED:
        includes.setdefault("MEANING_RULE", _meaning_rule)
        if surface in _REGION:
            includes.setdefault("EVIDENCE_RULE", _evidence_rule)
    fill = _Fill(flags, values, includes, dict(verbatim or {}))
    made = []
    for raw in (given.instructions if instructions is None else instructions,
                given.contract, given.data):
        text = _spaces(fill.render(raw)).strip()
        check(text, surface)
        made.append(text)
    # only the template's own text is searched for what was held aside: a
    # caption that happens to hold the mark of one is data and stays as it is
    lines = [lead, fill.close(made[0])] + list(extras)
    frame = [fill.close(made[2]), data]
    return Assembled(surface, version_line(surface, L, G, mode, custom, chosen),
                     "\n\n".join(x.strip() for x in lines if x and x.strip()),
                     fill.close(made[1]),
                     "\n\n".join(x.strip() for x in frame if x and x.strip()), chosen)
