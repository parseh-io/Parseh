#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the reading edition's .tex files as data.

Shared by timestamp.py (which writes % @t comments back) and tex2html.py
(which renders the reader).  The .tex is the single source of truth; nothing
here ever writes the text, transliteration, vocabulary or English anywhere
else.

Structures
    Book -> Chapter -> Paragraph -> Sub (one `frank` environment) -> Chunk
`\\parnum{۳.۱}` labels a Sub: paragraph 3, subparagraph 1.  A Paragraph ends at
`\\parend`, a Chapter at `\\chapend`.

Every Chunk and Sub carries the book's language (a languages.Lang, default
Persian): what the bare pass strips, how a label's digits are read and how a
chunk splits into words are the language's business, not this file's.  The
chunk's text is Chunk.fa whatever the language -- the key is named after
Persian, the toolbox's first language, and kept because every tool and every
stored file uses it.
"""
import hashlib
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import languages  # noqa: E402

# --- the passes are built from the same chunks, exactly as in LaTeX ----------
# frank_strip in the preamble drops the language's marks (Persian: U+064B..
# U+0652); the bare and alternate passes use that copy.  strip_harakat is the
# Persian range, kept under its old name for the Persian and Arabic callers;
# strip(s, lang) is the same thing for any language.  The range comes from the
# registry rather than being written here, so the two cannot disagree.
HARAKAT = re.compile("[%s]" % languages.get(languages.DEFAULT).strip_range)


def strip_harakat(s):
    return HARAKAT.sub("", s)


def strip(s, lang=None):
    """The bare form of s in the given language (a Lang or a code; default
    Persian): the marks its vowelled pass carries taken off."""
    if lang is None:
        return strip_harakat(s)
    if isinstance(lang, str):
        lang = languages.get_or_default(lang)
    return lang.strip(s)


# kept for the callers that translate Persian digits themselves
FA_DIGITS = str.maketrans(languages.get(languages.DEFAULT).digits, "0123456789")


def latin_digits(s):
    """Any language's digits -> Latin, so a label reads as a number whoever
    wrote it: ۳.۱ (Persian), ٣.١ (Arabic) and 3.1 all give '3.1'."""
    return languages.any_to_latin_digits(s)


# --- brace-aware argument reading -------------------------------------------
def read_group(s, i):
    """s[i] must be '{'.  Returns (contents, index just past the matching '}')."""
    assert s[i] == "{", "expected a group at %d: %r" % (i, s[i:i + 20])
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces from %d" % i)


def read_args(s, i, n):
    """Read n brace groups starting at i (skipping whitespace between them)."""
    args = []
    for _ in range(n):
        while i < len(s) and s[i] in " \t\r\n":
            i += 1
        a, i = read_group(s, i)
        args.append(a)
    return args, i


# --- the vocabulary field ----------------------------------------------------
# assemble.py's allowlist: dw vb bw pw textit emph nobreak.  Everything else in
# the field is literal text.  These render to (target, italic) inline runs so
# the HTML can isolate each word of the target language the way
# \babelsublr{\mbox{}} does.
VOC_MACROS = {"dw": 2, "vb": 7, "bw": 3, "pw": 1, "textit": 1, "emph": 1}

# The language whose .tex is being read.  A \vb prints two labels before its
# stems and they are the language's own (lib/lang/<code>.tex sets them as
# \FrankVbPres / \FrankVbPast, the registry holds the same pair) -- but
# parse_voc is handed the field alone, without the chunk it came from, so the
# parser remembers the language parse_book was given, the way tex2html
# remembers its own LANG.  Persian until a book says otherwise.
_LANG = languages.get(languages.DEFAULT)


def set_lang(lang):
    """The language the fields parsed from here on are in (a Lang or a code).
    parse_book and parse_chapter call it with the book's; a caller that has a
    field and no book may call it too."""
    global _LANG
    if isinstance(lang, str):
        lang = languages.get_or_default(lang)
    _LANG = lang or languages.get(languages.DEFAULT)
    return _LANG


def parse_voc(s, lang=None):
    """-> list of ('fa'|'em'|'txt', text) runs, in reading order.

    'fa' is a run of the book's own language (the key named after Persian,
    like everywhere else) and 'em' the italic romanisation beside it.  'em'
    was called 'it' for "italic" until Italian took that code: the two
    namespaces were never mixed, but a reader of this file could no longer
    tell which one was meant.

    `lang` is the book's, and defaults to the one last parsed: the labels a
    \\vb prints are the language's, and the field itself does not say which
    language wrote it."""
    if lang is None:
        lang = _LANG
    elif isinstance(lang, str):
        lang = languages.get_or_default(lang)
    # tidy the literal runs
    return [(k, re.sub(r"\s+", " ", t)) for k, t in _voc_runs(s, lang)
            if re.sub(r"\s+", "", t)]


def voc_text(s, lang=None):
    """A vocabulary field -- or any other \\ch argument -- as the plain text a
    video stores: the runs parse_voc reads, joined with a space wherever the
    PDF would have one, and the few escapes the field may carry undone.

        \\vb{andare}{}{vado}{}{andato}{}{to go (aux. \\pw{essere})}
        -> andare · pres. vado · p.p. andato · to go (aux. essere)

    It lived in youtube/lib/import_old_video.py, which flattens the older
    video format's script.tex with it, and moved here when a second writer
    needed the same string: the vocabulary entry the server builds for a verb
    carries its TeX for a book and its plain text for a video, and the one
    way to be sure the two say the same thing is that the plain text IS this
    function's reading of the TeX, blank pairs and all (_voc_runs).

    `lang` as in parse_voc: the labels are the language's own."""
    s = (s or "").replace("\\&", "&").replace("\\%", "%").replace("\\#", "#") \
                 .replace("\\_", "_").replace("~", " ").replace("---", "—") \
                 .replace("--", "–")
    out, prev = [], ""
    for kind, text in parse_voc(s, lang):
        # a space between two runs unless one side already brings it or the
        # second opens with the punctuation that closes a phrase: 'to go
        # (aux. ' + 'essere' + ')' is "to go (aux. essere)", not "( essere )".
        # NOR ROUND A SLASH THAT TOUCHES A MACRO: `aux. \pw{avere}/\pw{essere}`
        # is "avere/essere" in the PDF, and read "avere / essere" here and in
        # every video line lib/verbs writes -- which is held equal to this
        # (its _flatten), so the two change together.
        if out and not prev.endswith((" ", "(", "\u2018", "/")) and \
           not text.startswith((" ", ",", ";", ")", ".", "\u2019", ":", "/")):
            out.append(" ")
        out.append(text)
        prev = text
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _voc_runs(s, lang):
    """The walk parse_voc tidies.  Called again on the free-text slots -- the
    meaning of a \\vb, the phrase of a \\bw -- because those carry the same
    macros as the rest of the line (\\textit for a form the conventions name,
    \\pw for a word of the language) and the reader must show what they say,
    not their source."""
    out, i = [], 0
    def push(kind, text):
        if text:
            out.append((kind, text))
    def quoted(text):
        """A \\bw's phrase, in the single quotes the PDF prints round it."""
        push("txt", " \u2018")
        out.extend(_voc_runs(text, lang))
        push("txt", "\u2019")
    buf = ""
    while i < len(s):
        c = s[i]
        if c != "\\":
            buf += c
            i += 1
            continue
        m = re.match(r"\\([a-zA-Z]+)", s[i:])
        if not m:                      # \, \  and friends: thin spaces
            buf += " " if s[i:i + 2] in ("\\,", "\\ ") else ""
            i += 2
            continue
        name = m.group(1)
        i += m.end()
        if name == "nobreak":
            continue
        if name not in VOC_MACROS:     # unknown control word: drop it, keep text
            continue
        n_args = VOC_MACROS[name]
        if name == "bw":
            # Tolerate \bw{x}{y} meaning...  (two braced args, meaning as loose
            # text).  LaTeX would silently swallow the next CHARACTER as the
            # third argument and print 'j'olt; accept it here and recover the
            # phrase, so the reader shows what was meant.
            probe, k = read_args(s, i, 2)
            j = k
            while j < len(s) and s[j] in " \t":
                j += 1
            if j < len(s) and s[j] != "{":
                end = s.find(";", j)
                end = end if end >= 0 else len(s)
                args = [probe[0], probe[1], s[j:end].strip()]
                i = end
                push("txt", buf); buf = ""
                push("txt", " \u00b7 "); push("fa", args[0]); push("em", args[1])
                quoted(args[2])
                continue
        args, i = read_args(s, i, n_args)
        push("txt", buf); buf = ""
        if name == "pw":
            push("fa", args[0])
        elif name == "dw":
            push("fa", args[0]); push("em", args[1])
        elif name == "bw":
            push("txt", " \u00b7 "); push("fa", args[0]); push("em", args[1])
            quoted(args[2])
        elif name == "vb":
            # The preamble's \vb prints its second and third pairs only when
            # their FORM is not blank (\ifblank{#3}, \ifblank{#5}), and this is
            # the same test made the same way: a pair without a form loses its
            # label and its dot with it.  That is how a Chinese verb gives its
            # split and no "can't" form -- \vb{睡觉}{shuìjiào}{睡了觉}{shuìle
            # jiào}{}{}{to sleep} is "睡觉 shuìjiào · split 睡了觉 shuìle jiào ·
            # to sleep" in both the PDF and here -- and an Arabic verb with no
            # masdar in use leaves the third pair out.  The sound alone is
            # never tested: a Turkish \vb has none in any slot and still prints
            # every pair.  \ifblank counts spaces as blank, so .strip() does.
            pres, past = lang.vb_labels
            push("fa", args[0]); push("em", args[1])
            if args[2].strip():
                push("txt", " \u00b7 %s " % pres); push("fa", args[2]); push("em", args[3])
            if args[4].strip():
                push("txt", " \u00b7 %s " % past); push("fa", args[4]); push("em", args[5])
            if args[6].strip():
                push("txt", " \u00b7 ")
                out.extend(_voc_runs(args[6], lang))
        elif name in ("textit", "emph"):
            push("em", args[0])
    push("txt", buf)
    return out


# --- the vocabulary line as ENTRIES (TO-DO 11.14) ----------------------------
# The vocabulary of a chapter, a book or a video as a list needs the line cut
# into words, each with its meaning.  The cut, made on top of the same reading
# as parse_voc (and made again in lib/vocline.js, held equal to this by
# tests/fixtures/vocline.json):
#   - each \dw, \vb and \bw at the top of the line starts an entry;
#   - so does a \pw that OPENS a stretch of the line (at its start or after a
#     `;`) -- `\pw{que} who, which` is a word of its own -- but a \pw after
#     other text is a word inside a meaning (`fox, pl. \pw{ثعالب}`), which is
#     what its button says it is, and it stays in that meaning;
#   - an entry's meaning is the text after it up to the next `;` or the next
#     entry, read as plain text (voc_text); a \vb's meaning starts with its own
#     last group, a \bw's with its phrase.  The punctuation that only joins it
#     to the word (`, ` `: ` ` — `) is taken off its front;
#   - a macro inside a group is part of that group, never an entry.
# Text before the first entry of a stretch (`here \pw{vivia}, imperf.`) is in
# no entry.  A line parse_voc cannot read raises as parse_voc does.
ENTRY_MACROS = ("dw", "vb", "bw", "pw")
_LEAD = " ,:;·—–"


def _tidy(s):
    return re.sub(r"\s+", " ", s).strip()


def voc_entries(s, lang=None):
    """-> [{kind, word, rom, head, meaning, key}] in the order the line has them.

    `word` is the form the entry is listed under (a \\vb's first form), `rom`
    its romanisation, `head` the runs the reader prints for the word itself
    (a \\vb with its stems and the language's labels: parse_voc's runs of the
    macro with its meaning left blank), `meaning` the plain text of the
    meaning, and `key` the word's comparison form (vocab_key)."""
    if lang is None:
        lang = _LANG
    elif isinstance(lang, str):
        lang = languages.get_or_default(lang)
    s = s or ""
    parse_voc(s, lang)              # a line that cannot be read raises here, as parse_voc does
    out, cur, i, stretch = [], None, 0, 0

    def close(end):
        if cur is None:
            return
        tail = s[cur["tail"]:end]
        src = cur.pop("lead") + tail
        cur.pop("tail")
        cur["meaning"] = voc_text(src, lang).lstrip(_LEAD).rstrip(" ,")
        out.append(cur)

    while i < len(s):
        c = s[i]
        if c == ";":
            close(i)
            cur = None
            i += 1
            stretch = i
            continue
        if c != "\\":
            i += 1
            continue
        m = re.match(r"\\([a-zA-Z]+)", s[i:])
        if not m:
            i += 2
            continue
        name, at = m.group(1), i
        i += m.end()
        if name not in VOC_MACROS:
            continue
        starts = name in ("dw", "vb", "bw") or (name == "pw" and not s[stretch:at].strip())
        if name == "bw":
            probe, k = read_args(s, i, 2)
            j = k
            while j < len(s) and s[j] in " \t":
                j += 1
            if j < len(s) and s[j] != "{":          # \bw{x}{y} meaning: the meaning as loose text
                end = s.find(";", j)
                end = end if end >= 0 else len(s)
                close(at)
                cur = _entry("bw", probe[0], probe[1], lang, lead=s[j:end], tail=end)
                i = end
                continue
        args, i = read_args(s, i, VOC_MACROS[name])
        if not starts:
            continue
        close(at)
        if name == "vb":
            cur = _entry("vb", args[0], args[1], lang, lead=args[6], tail=i,
                         head="\\vb{%s}{%s}{%s}{%s}{%s}{%s}{}" % tuple(args[:6]))
        elif name == "bw":
            cur = _entry("bw", args[0], args[1], lang, lead=args[2], tail=i)
        elif name == "dw":
            cur = _entry("dw", args[0], args[1], lang, lead="", tail=i)
        else:
            cur = _entry("pw", args[0], "", lang, lead="", tail=i)
    close(len(s))
    return out


def _entry(kind, word, rom, lang, lead, tail, head=None):
    w, r = voc_text(word, lang), voc_text(rom, lang)
    if head is None:
        head = "\\dw{%s}{%s}" % (word, rom)
    return {"kind": kind, "word": w, "rom": r,
            "head": [list(x) for x in parse_voc(head, lang)],
            "key": vocab_key(w, lang), "lead": lead, "tail": tail}


# The comparison form of a word: one word written two ways is one entry.
# What lib/lookup.py's _fold takes off before it looks a word up -- the
# language's own marks (the harakat), the zero-width joiners, the case, and
# Turkish's two i's -- plus the two letters Persian is typed with from an
# Arabic keyboard (ي ى for ی, ك for ک), which the shelf's own intake
# (timestamp.py, extract_pdf.py) folds the same way.  Arabic keeps its ي ى
# apart: there they are two letters (علي, على).
_ZWJ = "‌‍"
_FA_LETTERS = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"})


def vocab_key(word, lang=None):
    """The form two entries are compared by: same key, same word."""
    if lang is None:
        lang = _LANG
    elif isinstance(lang, str):
        lang = languages.get_or_default(lang)
    w = unicodedata.normalize("NFC", word or "")
    w = lang.strip(w)
    for z in _ZWJ:
        w = w.replace(z, "")
    if lang.code == "fa":
        w = w.translate(_FA_LETTERS)
    if lang.code == "tr":
        w = w.replace("İ", "i").replace("I", "ı")
    return re.sub(r"\s+", " ", w.lower()).strip()


# --- model ------------------------------------------------------------------
class Chunk:
    __slots__ = ("col", "fa", "kana", "tr", "voc", "en", "glossed", "t0", "t1",
                 "conf", "src", "line", "sub", "lang", "wordline")

    def __init__(self, fa, tr, voc, en, glossed, line, col="", kana="", lang=None,
                 wordline=""):
        self.fa, self.tr, self.voc, self.en = fa, tr, voc, en
        # \chr's reading of the whole chunk (Japanese kana); "" for \ch and
        # for every language without a reading
        self.kana = kana
        # \chw's and \chrw's last argument, the word line as written
        # (lib/wordline.py reads it); "" for a chunk without words.  Not
        # `words`, which is the chunk's text split the language's way and
        # older than the word line by a long way.
        self.wordline = wordline
        # \ch's first argument: empty, or one of \Cred \Cblue \Corange \Cgreen.
        # It reaches pass 1 only -- see the preamble.
        self.col = col.strip()
        self.glossed = glossed          # False for \chp
        self.line = line                # 0-based line index of the \ch in the file
        self.t0 = self.t1 = self.conf = None
        self.src = None                 # 'anchor' | 'interp' | 'forced' | 'manual'
        self.sub = None
        self.lang = lang or languages.get(languages.DEFAULT)

    @property
    def plain(self):
        """The bare form: what passes 3 and 4 show, and what the key hashes."""
        return self.lang.strip(self.fa)

    @property
    def key(self):
        """Stable id: hash of the stripped text, so timings survive
        regeneration (and re-vowelling)."""
        return hashlib.sha1(self.plain.encode("utf-8")).hexdigest()[:16]

    @property
    def words(self):
        return self.lang.split_words(self.fa)


class Sub:
    def __init__(self, label, line, lang=None):
        self.label = label              # '۳.۱'
        self.line = line                # line of \parnum
        self.begin_line = None          # line of \begin{frank}
        self.chunks = []
        self.t0 = self.t1 = None
        self.lang = lang or languages.get(languages.DEFAULT)

    @property
    def num(self):
        return latin_digits(self.label)

    @property
    def para_no(self):
        return int(self.num.split(".")[0])

    @property
    def fa(self):
        return " ".join(c.fa for c in self.chunks)


class Paragraph:
    def __init__(self, no):
        self.no = no
        self.subs = []
        # The title of a \secmark standing immediately before this paragraph,
        # or None.  A SECTION IS A PLACE, not a container: it is remembered on
        # the paragraph it opens at, so nothing about the paragraph's own
        # number -- which is \parnum's and only \parnum's -- can depend on it.
        self.section = None


class Chapter:
    def __init__(self, label, path):
        self.label = label              # '۱'
        self.path = path
        self.paragraphs = []
        # \chapname{...}: what this chapter is called, or None.  A chapter
        # that has none is every chapter written before names existed, and
        # both the PDF and the reader fall back to its number alone.
        self.name = None

    @property
    def subs(self):
        return [s for p in self.paragraphs for s in p.subs]


def parse_chapter(path, lang=None):
    """Parse one ch*.tex into Paragraphs of Subs of Chunks, each carrying
    the book's language (default Persian)."""
    lang = set_lang(lang)
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    # index of each line's start offset, to map positions back to line numbers
    starts, off = [], 0
    for ln in lines:
        starts.append(off)
        off += len(ln) + 1
    def line_of(pos):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo

    chapter = Chapter(None, path)
    para = None
    sub = None
    # a \secmark read but not yet given away: it belongs to the next paragraph
    # to open, which is the one it stands before
    pending_sec = None
    i = 0
    while i < len(text):
        if text.startswith("%", i) and (i == 0 or text[i - 1] == "\n"):
            i = text.find("\n", i)                     # skip comment lines whole
            if i < 0:
                break
            continue
        # \chr must be listed: with the \b, "ch" does not match at "\chr",
        # and the chunk would be skipped without a word.  So must \chrw and
        # \chw.  They come before the names they begin with as in every list
        # of these names: the \b here would rescue the other order, but a
        # pattern with nothing after the name would not
        # \chapname and \secmark come before "ch" for the same reason \chrw
        # does, and each takes one group, which is read here rather than
        # stepped over: a title is ordinary text and may hold a brace or a
        # macro of its own, and walking into it would read that as the book's.
        m = re.compile(r"\\(chapopen|chapname|secmark|parnum|chrw|chw|chr|chp|ch"
                       r"|parend|chapend)\b").match(text, i)
        if not m:
            i += 1
            continue
        name = m.group(1)
        j = m.end()
        if name == "chapopen":
            (lab,), j = read_args(text, j, 1)
            chapter.label = lab.strip()
        elif name == "chapname":
            (nm,), j = read_args(text, j, 1)
            chapter.name = nm.strip() or None
        elif name == "secmark":
            (nm,), j = read_args(text, j, 1)
            pending_sec = nm.strip() or None
        elif name == "parnum":
            (lab,), j = read_args(text, j, 1)
            lab = lab.strip()
            sub = Sub(lab, line_of(m.start()), lang)
            # the chapter it is in, read when it is asked for: a file that
            # only continues a chapter is given the chapter's number by
            # parse_book, after this file is parsed (chapter_of)
            sub.chapter = chapter
            no = sub.para_no
            if para is None or para.no != no:
                para = Paragraph(no)
                # the \secmark just passed, if any, opens here
                para.section = pending_sec
                pending_sec = None
                chapter.paragraphs.append(para)
            para.subs.append(sub)
        elif name in ("ch", "chr", "chp", "chw", "chrw"):
            # \ch{colour}{fa}{tr}{voc}{en}   \chr{colour}{fa}{kana}{tr}{voc}{en}
            # \chp{colour}{fa} -- the arity is in the name, never guessed.
            # \chw and \chrw are \ch and \chr with the word line added LAST,
            # so every argument before it keeps the number it always had
            n = {"ch": 5, "chr": 6, "chp": 2, "chw": 6, "chrw": 7}[name]
            args, j = read_args(text, j, n)
            if name in ("chr", "chrw"):
                fa_, kana, tr, voc, en = args[1], args[2], args[3], args[4], args[5]
            elif name in ("ch", "chw"):
                fa_, kana, tr, voc, en = args[1], "", args[2], args[3], args[4]
            else:
                fa_, kana, tr, voc, en = args[1], "", "", "", ""
            wordline = args[-1] if name.endswith("w") else ""
            if name.endswith("w") and not wordline.strip():
                # the PDF refuses it too: a chunk without words has a name
                raise ValueError("%s line %d: \\%s with a blank word line -- use "
                                 "\\%s, which is this chunk without words"
                                 % (os.path.basename(path), line_of(m.start()) + 1,
                                    name, name[:-1]))
            c = Chunk(fa_, tr, voc, en, name != "chp", line_of(m.start()),
                      args[0], kana, lang, wordline)
            if sub is None:                            # defensive: chunk before any label
                para = para or Paragraph(0)
                if para not in chapter.paragraphs:
                    chapter.paragraphs.append(para)
                sub = Sub("0.0", line_of(m.start()), lang)
                para.subs.append(sub)
            c.sub = sub
            sub.chunks.append(c)
        elif name in ("parend", "chapend"):
            para = None
            sub = None
        i = j
    # record where each sub's \begin{frank} sits, for the % @par comment
    for s in chapter.subs:
        k = text.find(r"\begin{frank}", starts[s.line])
        s.begin_line = line_of(k) if k >= 0 else s.line + 1
    return chapter


def parse_book(main="main.tex", lang=None):
    """Chapter order comes from the \\input lines of the main file, nowhere else.

    `lang` is the book's language (a Lang or a code) and is stored on every
    Chunk and Sub; None means Persian, as every book was before languages
    were declared.  Callers that have a books.Book pass book.lang.
    """
    lang = set_lang(lang)                  # and what parse_voc reads it as
    base = os.path.dirname(os.path.abspath(main))
    src = open(main, encoding="utf-8").read()
    chapters = []
    for line in src.split("\n"):
        if line.lstrip().startswith("%"):
            continue
        m = re.search(r"\\input\{([^}]+)\}", line)
        if not m:
            continue
        path = os.path.join(base, m.group(1))
        if not os.path.exists(path):
            continue
        # main.tex also inputs the shared preamble and front matter; a chapter
        # file is one that actually carries text, so test for that rather than
        # keeping a list of filenames to skip
        head = open(path, encoding="utf-8").read()
        # \begin{frank} appears only in a chapter file; the preamble merely
        # DEFINES the environment, and its comments mention \ch and \parnum,
        # so testing for those matched the preamble's own documentation.
        if "\\begin{frank}" not in head:
            continue
        ch = parse_chapter(path, lang)
        if ch.subs:
            chapters.append(ch)
    # a chapter file that only continues the previous one carries no \chapopen
    last = None
    for ch in chapters:
        if ch.label is None:
            ch.label = last
        else:
            last = ch.label
    return chapters


def all_chunks(chapters):
    return [c for ch in chapters for p in ch.paragraphs for s in p.subs for c in s.chunks]


# --- naming a stretch of the book: what a recording covers -------------------
def chapter_of(sub):
    """The printed number of the chapter a subparagraph is in, in Latin digits
    ("2"): what makes its label unique, since chapter 1 and chapter 2 both
    have a 4.3."""
    ch = getattr(sub, "chapter", None)
    return latin_digits((ch.label if ch is not None else "") or "").strip()


def qualified(sub):
    """A subparagraph named so that no other one answers to it: its chapter
    and its label, "2:4.3"."""
    return "%s:%s" % (chapter_of(sub), sub.num)


def region_bounds(pairs, first, last):
    """Where a stretch named by its two ends starts and ends -> (i, j),
    indices into `pairs`, the (chapter, label) of every subparagraph of the
    book in reading order (chapter_of, Sub.num).

    An end is a label with its chapter, "2:4.3", which names exactly one
    subparagraph -- what the pickers write -- or a bare label, "4.3", which
    names one only within its chapter: every narration written before the
    chapter was named.  A bare start is the first subparagraph wearing the
    label; a bare end is the first wearing it AT OR AFTER THE START -- the
    narrowest stretch, because a recording is one stretch of the text and
    that is what anybody picking "4.3" meant.  (It used to be the LAST in
    the book: in a book of five chapters that each number from 1, nine
    recordings of chapter 1 stored as "7.1"-"36.1" and the like ran on
    into chapters 2 to 5, and an estimate of their times spread their
    sound over text they never read.)  Either end empty means from the
    beginning / to the end, so a stretch with neither is the whole book.  A
    ValueError says what is wrong, in a sentence meant to be shown."""
    def find(want, start=0):
        ch, colon, lab = want.rpartition(":")
        ch, lab = ch.strip(), lab.strip()
        # an end named with its chapter is that one wherever it is; a bare
        # one is looked for from the start of the stretch on
        for k in range(0 if colon else start, len(pairs)):
            c, l = pairs[k]
            if l == lab and (not colon or c == ch):
                return k
        if not colon and start and any(l == lab for c, l in pairs):
            raise ValueError("that stretch ends (%s) before it begins (%s)" % (want, first))
        where = ("chapter %s" % ch) if colon else "this book"
        raise ValueError("there is no subparagraph %s in %s" % (lab, where))
    first, last = (first or "").strip(), (last or "").strip()
    if not pairs:
        raise ValueError("this book has no subparagraphs")
    i = find(first) if first else 0
    j = find(last, i) if last else len(pairs) - 1
    if j < i:
        raise ValueError("that stretch ends (%s) before it begins (%s)" % (last, first))
    return i, j


if __name__ == "__main__":
    # a book's own language, when the argument is inside a books/<folder>/
    main = sys.argv[1] if len(sys.argv) > 1 else "main.tex"
    chs = parse_book(main, languages.detect_from_path(main))
    tot = 0
    for ch in chs:
        n = sum(len(s.chunks) for s in ch.subs)
        tot += n
        print("%-12s chapter %-3s %3d paragraphs %4d subs %5d chunks"
              % (os.path.basename(ch.path), ch.label, len(ch.paragraphs),
                 len(ch.subs), n))
    print("total: %d chunks" % tot)
    c = all_chunks(chs)[0]
    print("\nfirst chunk:", c.fa, "|", c.kana, "|", c.tr, "|", c.en, "  [%s]" % c.lang.code)
    print("stripped   :", c.plain)
    print("voc runs   :", parse_voc(c.voc)[:4])
