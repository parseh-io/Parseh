#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cut a chunk's text into words, each with a proposed reading.

    words.propose("山へ柴刈りに、", "ja")  -> [("山", "やま"), ("へ", ""), ...]
    words.line("山へ柴刈りに、", "ja")     -> "山(やま) へ 柴刈り(しばかり) に 、"
    words.line("私は", "ja", "わたしは")   -> "私(わたし) は"
    words.lines_all([text, ...], "ja")     -> [line, ...]
    words.parsed(text, "ja")               -> [(word, [(morpheme, pos, lemma)]), ...]
    words.available("zh")                  -> can this Python cut Chinese?

Japanese is cut by SudachiPy and Chinese by spacy-pkuseg, read by pypinyin;
lib/lang/<code>.words.json says how.  What comes back is a PROPOSAL -- the
cut and the readings a person corrects in the word strip -- and nothing more:
a machine's reading is a dictionary's, not the sentence's (私 comes back
わたくし, 很长 zhǎng).  Given the chunk's own reading -- its kana, or its
pinyin -- each word takes its stretch of that instead, wherever the cut can
be laid over it (the section on the chunk's own reading, below).

THE INVARIANT.  Every proposal rejoins its text: the surfaces are slices of
it, whitespace is never a word, and a proposal that fails lib/wordline.py's
reproduction check is thrown away and [] returned rather than written.

Where the analyzers are not installed in the running Python, every function
answers [] or "" and the caller writes no words: a chunk without a word line
is legal forever, and lib/segmenter.py says what is missing.
"""
import functools
import json
import os
import re
import sys
import threading
import unicodedata

HERE = os.path.dirname(os.path.realpath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import languages                                              # noqa: E402
import segmenter                                              # noqa: E402
import wordline                                               # noqa: E402

# SudachiPy refuses more than 49149 bytes in one call; a chunk never nears it,
# a whole transcript might.
_MAX_BYTES = 40000

# ONE PROPOSAL AT A TIME, for the whole process.  The analyzers are built once
# and shared, and SudachiPy's tokenizer is not safe to use from two threads at
# once: the second call raises "Already borrowed", which propose() -- rightly
# treating any analyzer failure as no proposal -- turned into a chunk silently
# drafted without its words.  serve.py answers every request on a thread of
# its own, so two drafts, or a draft and the word strip's propose button, did
# exactly that.  A proposal takes milliseconds; waiting for one is free.
_LOCK = threading.Lock()
_NUMERALS = "〇一二三四五六七八九十百千万"


@functools.lru_cache(maxsize=None)
def rules(code):
    try:
        with open(os.path.join(HERE, "lang", "%s.words.json" % code), encoding="utf-8") as f:
            got = json.load(f)
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def available(code):
    return bool(rules(code)) and segmenter.available(code)


# --- Japanese --------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _sudachi():
    from sudachipy import Dictionary, SplitMode
    return Dictionary().create(), SplitMode


def _hiragana(s):
    return "".join(chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in s)


def _matches(pos, pairs):
    return any((a == "*" or a == pos[0]) and (b == "*" or b == pos[1]) for a, b in pairs)


def _pieces(text):
    """The text in slices Sudachi will take, cut after a full stop or a
    newline where it has to be cut at all."""
    if len(text.encode("utf-8")) <= _MAX_BYTES:
        return [text]
    out, cur = [], ""
    for part in re.split(r"(?<=[。！？\n])", text):
        if cur and len((cur + part).encode("utf-8")) > _MAX_BYTES:
            out.append(cur)
            cur = ""
        cur += part
    return out + ([cur] if cur else [])


def _japanese_words(text, R):
    """SudachiPy's morphemes merged into words: [[surface, reading, has_oov,
    [(morpheme, part_of_speech, dictionary_form), ...]], ...]."""
    tok, SplitMode = _sudachi()
    mode = getattr(SplitMode, R.get("split_mode") or "C")
    forward = set(R.get("attach_forward") or [])
    back = set(R.get("attach_back") or [])
    inflected = set(R.get("inflected") or [])
    tail = [tuple(p) for p in R.get("tail") or []]
    words = []
    head, glue = None, False
    for piece in _pieces(text):
        for m in tok.tokenize(piece, mode):
            s = m.surface()
            if not s.strip():                   # whitespace is never a word,
                head, glue = None, False        # and nothing joins across it
                continue
            pos = m.part_of_speech()
            r = _hiragana(m.reading_form())
            said = (s, tuple(pos), m.dictionary_form())
            joins = words and (glue or pos[0] in back or
                               (head in inflected and _matches(pos, tail)))
            if joins:
                w = words[-1]
                w[0] += s
                w[1] += r
                w[2] = w[2] or m.is_oov()
                w[3].append(said)
            else:
                words.append([s, r, m.is_oov(), [said]])
                head = pos[0]
            glue = pos[0] in forward
    return words


def _japanese(text, R):
    out = []
    for s, r, oov, _said in _japanese_words(text, R):
        has_han = bool(wordline.HAN.search(s))
        keep = has_han and not (oov and not R.get("oov_reading"))
        out.append((s, r if keep else ""))
    return out


# --- Chinese ---------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _pkuseg(model, tagged=False):
    import spacy_pkuseg
    return spacy_pkuseg.pkuseg(model_name=model, postag=tagged)


def tagger_available(code):
    """Can this Python name the parts of speech of `code`'s words, with
    nothing to download first?  Japanese: whenever SudachiPy is here, since it
    names them as it cuts.  Chinese: when pkuseg's part-of-speech model is on
    disk (lib/segmenter.py) -- spacy_pkuseg fetches it, about 41 MB, the first
    time one is asked for, and a request of this server must never be what
    fetches it; the installers and Settings > Reading help (lib/getwords.py) do."""
    if not available(code):
        return False
    analyzer = rules(code).get("analyzer")
    if analyzer == "sudachipy":
        return True
    return analyzer == "spacy_pkuseg" and segmenter.model_ready(code, "postag")


def _chinese_words(text, R, tagged=False):
    """[(word, tag)] as pkuseg cuts `text`, the tag "" without the
    part-of-speech model.  The tagging instance cuts with the same model as
    the plain one, so a Python that has the tagger loads one instance only."""
    seg = _pkuseg(R.get("model") or "spacy_ontonotes", tagged)
    out = []
    for run in text.split():                    # pkuseg drops whitespace itself
        for w in seg.cut(run):
            word, tag = (w, "") if isinstance(w, str) else (w[0], w[1])
            if word:
                out.append((word, tag))
    return out


def _tone(syllable):
    return int(syllable[-1]) if syllable[-1:].isdigit() else 5


def _changed(chars, sylls, i):
    """The tone docs/lang/zh.md writes for 一 or 不 at position i, or None."""
    c, nxt = chars[i], None
    for j in range(i + 1, len(chars)):
        if sylls[j]:
            nxt = sylls[j]
            break
        if not chars[j].isspace():
            break
    if c == "不":
        return "bu2" if nxt and _tone(nxt) == 4 else "bu4"
    if c == "一":
        prev = chars[i - 1] if i else ""
        after = chars[i + 1] if i + 1 < len(chars) else ""
        if not nxt or prev == "第" or after in _NUMERALS:
            return "yi1"
        return "yi2" if _tone(nxt) == 4 else "yi4"
    return None


def _chinese(text, R, tagged=False):
    from pypinyin import Style, pinyin
    from pypinyin.contrib.tone_convert import to_tone
    surfaces = [w for w, _tag in _chinese_words(text, R, tagged)]
    chars = list("".join(surfaces))
    got = pinyin(surfaces, style=Style.TONE3, errors=lambda cs: list(cs)) if surfaces else []
    if len(got) != len(chars):
        return []                               # alignment lost: propose nothing
    sylls = [e[0] if wordline.HAN.search(c) else "" for c, e in zip(chars, got)]
    changes = set(R.get("tone_change") or [])
    for i, c in enumerate(chars):
        if c in changes and sylls[i]:
            sylls[i] = _changed(chars, sylls, i) or sylls[i]
    out, i = [], 0
    for w in surfaces:
        parts = [to_tone(x) for x in sylls[i:i + len(w)] if x]
        reading = ""
        for k, p in enumerate(parts):
            if k and p[:1] in "aoeāáǎàōóǒòēéěè":
                reading += "'"
            reading += p
        out.append((w, reading))
        i += len(w)
    return out


# --- the chunk's own reading, laid over its words ----------------------------
# A machine reads a word the way a dictionary does -- 私 わたくし, 早上
# zǎoshàng, 十 not at all -- and furigana set from that contradict the chunk's
# own kana or pinyin, which somebody wrote for THIS sentence.  So a proposal
# for a chunk that already has its reading cuts that reading into one stretch
# per word and gives each word its own.  What holds the cut in place is what
# the words are written with: in Japanese the kana of a word (okurigana,
# particles, katakana), which the reading must spell at that very place; in
# Chinese the syllables, one to a character, a syllable never running across a
# space or an apostrophe.  Where several cuts fit, the one nearest the
# machine's own readings is taken.  Where none fits -- the reading is of
# another text, or spells a word some way the cut cannot follow -- the
# machine's readings stand, as they do for a chunk not yet read.  Only a word
# with a Han character is given a reading, as before.

def _distance(a, b):
    """The edit distance between two strings: how far a cut's reading of a
    word is from the machine's."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _is_kana(c):
    """Kana a word is written with, and so a reading must spell: not ヵ ヶ,
    which are read か が こ and stand for a character."""
    o = ord(c)
    return (0x3041 <= o <= 0x3096 or o in (0x309D, 0x309E)
            or 0x30A1 <= o <= 0x30F4 or 0x30FC <= o <= 0x30FE)


def _kana_key(c):
    """c as a Japanese reading is compared: katakana as hiragana, a Latin
    letter in lower case, and "" for what a reading may leave out or put in
    (punctuation, spaces)."""
    if _is_kana(c):
        o = ord(c)
        return chr(o - 0x60) if 0x30A1 <= o <= 0x30F4 or o in (0x30FD, 0x30FE) else c
    return c.lower() if c.isalnum() else ""


# the most kana one character is ever read with (承 うけたまわ), and some over
_KANA_PER_CHAR = 6


def _given_japanese(pairs, reading):
    key = "".join(_kana_key(c) for c in reading)
    shapes = []                                 # per word: its pattern, shortest, longest
    for s, _r in pairs:
        parts, lo, hi, run = [], 0, 0, 0
        for c in s:
            if not _is_kana(c) and _kana_key(c):
                run += 1                        # a character the reading reads
                continue
            if run:
                parts.append("(.{1,%d})" % (run * _KANA_PER_CHAR))
                lo, hi, run = lo + 1, hi + run * _KANA_PER_CHAR, 0
            if _is_kana(c):
                parts.append(re.escape(_kana_key(c)))
                lo, hi = lo + 1, hi + 1
        if run:
            parts.append("(.{1,%d})" % (run * _KANA_PER_CHAR))
            lo, hi = lo + 1, hi + run * _KANA_PER_CHAR
        shapes.append((re.compile("".join(parts)), lo, hi))
    size = len(key)
    best = [{} for _ in range(len(pairs) + 1)]  # best[i][at] = (cost, where word i began)
    best[0][0] = (0, None)
    for i, (s, r) in enumerate(pairs):
        rx, lo, hi = shapes[i]
        han = len(wordline.HAN.findall(s))
        hint = _hiragana(r)
        for at in sorted(best[i]):
            cost = best[i][at][0]
            for end in range(at + lo, min(size, at + hi) + 1):
                span = key[at:end]
                if not rx.fullmatch(span):
                    continue
                if not han:
                    extra = 0
                elif hint:
                    extra = _distance(span, hint)
                else:                           # no machine reading to go by:
                    extra = abs(len(span) - 2 * han) / 100.0   # two kana a character
                if end not in best[i + 1] or cost + extra < best[i + 1][end][0]:
                    best[i + 1][end] = (cost + extra, at)
    if size not in best[-1]:
        return pairs
    cuts, end = [], size
    for i in range(len(pairs), 0, -1):
        at = best[i][end][1]
        cuts.append((at, end))
        end = at
    cuts.reverse()
    return [(s, key[a:b] if wordline.HAN.search(s) else "")
            for (s, _r), (a, b) in zip(pairs, cuts)]


_TONE_MARKS = frozenset("\u0304\u0301\u030c\u0300")   # the four tone marks, combining


@functools.lru_cache(maxsize=None)
def _syllables():
    """Every toneless syllable pypinyin reads a character with, ü as ü."""
    from pypinyin import pinyin_dict
    out = set()
    for v in pinyin_dict.pinyin_dict.values():
        for p in v.split(","):
            bare = "".join(c for c in unicodedata.normalize("NFD", p) if c not in _TONE_MARKS)
            out.add(unicodedata.normalize("NFC", bare).lower())
    return frozenset(out)


def _pinyin_letters(reading):
    """A pinyin text as ([(key, text)], walls): a letter's key is the letter
    toneless and in lower case (ü as ü) and its text is as written, tone mark
    and capital and all; walls are the letter positions a syllable may not
    run across -- after a space, an apostrophe, a mark."""
    letters, walls, gap = [], set(), False
    clusters = []
    for c in unicodedata.normalize("NFD", reading or ""):
        if clusters and unicodedata.combining(c):
            clusters[-1] += c
        else:
            clusters.append(c)
    for cl in clusters:
        if cl[0].isalnum() and not wordline.HAN.search(cl[0]):
            if gap and letters:
                walls.add(len(letters))
            gap = False
            bare = "".join(c for c in cl if c not in _TONE_MARKS)
            letters.append((unicodedata.normalize("NFC", bare).lower(),
                            unicodedata.normalize("NFC", cl)))
        else:
            gap = True
    return letters, walls


def _elements(surface):
    """What a Chinese word is read with, in order: "syl" a syllable for a
    character, "er" for an 儿 that may be its own syllable or an r on the one
    before, ("lit", text) for a Latin word or a figure spelled as it stands."""
    out, run = [], ""
    for c in surface:
        if wordline.HAN.search(c):
            if run:
                out.append(("lit", run.lower()))
                run = ""
            out.append(("er", None) if c == "儿" and out else ("syl", None))
        elif c.isalnum():
            run += c
        elif run:
            out.append(("lit", run.lower()))
            run = ""
    if run:
        out.append(("lit", run.lower()))
    return out


def _word_cuts(elements, keys, walls, at, syllables):
    """Every way a word's elements can be read off keys from at: [(end, pieces)],
    a piece (start, end, kind)."""
    states = [(at, [])]
    for kind, lit in elements:
        nxt = []
        for pos, got in states:
            if kind == "lit":
                if "".join(keys[pos:pos + len(lit)]) == lit:
                    nxt.append((pos + len(lit), got + [(pos, pos + len(lit), "lit")]))
                continue
            if kind == "er" and got and pos < len(keys) and keys[pos] == "r" and pos not in walls:
                nxt.append((pos + 1, got + [(pos, pos + 1, "r")]))
            for end in range(pos + 1, min(len(keys), pos + 6) + 1):
                if end - 1 > pos and (end - 1) in walls:
                    break
                if "".join(keys[pos:end]) in syllables:
                    nxt.append((end, got + [(pos, end, "syl")]))
        states = nxt
        if not states:
            break
    return states


def _given_chinese(pairs, reading):
    letters, walls = _pinyin_letters(reading)
    keys = [k for k, _ in letters]
    syllables = _syllables()
    size = len(keys)
    best = [{} for _ in range(len(pairs) + 1)]  # best[i][at] = (cost, began, pieces)
    best[0][0] = (0, None, None)
    for i, (s, r) in enumerate(pairs):
        elements = _elements(s)
        hint = "".join(k for k, _ in _pinyin_letters(r)[0])
        for at in sorted(best[i]):
            cost = best[i][at][0]
            for end, pieces in _word_cuts(elements, keys, walls, at, syllables):
                said = "".join("".join(keys[a:b]) for a, b, kind in pieces if kind != "lit")
                extra = _distance(said, hint) if hint else 0
                if end not in best[i + 1] or cost + extra < best[i + 1][end][0]:
                    best[i + 1][end] = (cost + extra, at, pieces)
    if size not in best[-1]:
        return pairs
    out, end = [], size
    for i in range(len(pairs), 0, -1):
        _cost, at, pieces = best[i][end]
        s = pairs[i - 1][0]
        text = ""
        for a, b, kind in pieces:
            if kind == "lit":
                continue
            if kind == "syl" and text and keys[a] in ("a", "o", "e"):
                text += "'"
            text += "".join(t for _k, t in letters[a:b])
        out.append((s, text if wordline.HAN.search(s) else ""))
        end = at
    out.reverse()
    return out


# --- the public shape ------------------------------------------------------
def propose(text, lang, reading=""):
    """[(surface, reading)] for one chunk's text, or [] where nothing can be
    proposed.  Always rejoins the text when it answers at all.  `reading`,
    the chunk's own kana (or pinyin) where it has one, is laid over the words
    (above); it never changes where they are cut."""
    L = languages.get_or_default(lang)
    text = text or ""                           # sliced as given: wordline compares code points
    if not text.strip() or not L.words or not available(L.code):
        return []
    R = rules(L.code)
    try:
        with _LOCK:
            pairs = (_japanese(text, R) if R.get("analyzer") == "sudachipy"
                     else _chinese(text, R, tagger_available(L.code)))
    except Exception as e:                      # an analyzer's own failure is a
        sys.stderr.write("words: %s: %s\n" % (L.code, e))  # proposal not made
        return []
    if wordline.norm("".join(s for s, _ in pairs), L) != wordline.norm(text, L):
        return []
    if isinstance(reading, str) and reading.strip():
        try:
            pairs = (_given_japanese(pairs, reading) if R.get("analyzer") == "sudachipy"
                     else _given_chinese(pairs, reading))
        except Exception as e:                  # a reading that will not lay over
            sys.stderr.write("words: %s: the chunk's reading: %s\n" % (L.code, e))
    return pairs


def parsed(text, lang):
    """The words propose() divides `text` into, each with what the analyzer
    said of its pieces: [(surface, [(morpheme, part_of_speech,
    dictionary_form), ...])].  A part of speech is SudachiPy's six fields for
    Japanese, and for Chinese the one tag pkuseg gives the word (the PKU
    set), as a tuple of one.

    [] where the analyzer here names no parts of speech -- Chinese without
    its part-of-speech model (tagger_available) -- or can say nothing.
    lib/chunker.py cuts a sentence between these words, so a chunk never ends
    inside one."""
    L = languages.get_or_default(lang)
    text = text or ""
    if not text.strip() or not L.words or not tagger_available(L.code):
        return []
    R = rules(L.code)
    try:
        with _LOCK:
            if R.get("analyzer") == "sudachipy":
                got = [(w[0], w[3]) for w in _japanese_words(text, R)]
            else:
                got = [(w, [(w, (tag,), w)]) for w, tag in _chinese_words(text, R, True)]
    except Exception as e:                      # as in propose(): no answer
        sys.stderr.write("words: %s: %s\n" % (L.code, e))
        return []
    if wordline.norm("".join(w for w, _ in got), L) != wordline.norm(text, L):
        return []
    return got


def line(text, lang, reading=""):
    """The word line for one chunk's text, or "" where none is proposed."""
    pairs = propose(text, lang, reading)
    try:
        return wordline.render(pairs) if pairs else ""
    except wordline.WordsError:
        return ""


def lines_all(texts, lang):
    return [line(t, lang) for t in (texts or [])]


def fetch_models(code, say=print):
    """Download what `code`'s analyzer would otherwise fetch for itself the
    first time it is asked (lib/segmenter.py MODELS) -> True when every model
    is on disk afterwards.  The installers call this, so that no request of
    the server is ever the one that waits for forty megabytes."""
    if not available(code):
        say("no analyzer for %s in %s: pip install %s"
            % (code, sys.executable, segmenter.about(code).get("packages", "")))
        return False
    lacking = [m for m in segmenter.models(code) if not m["have"]]
    if not lacking:
        return True
    say("fetching for %s: %s" % (code, ", ".join("%s (%d MB)" % (m["what"], m["size_mb"])
                                                for m in lacking)))
    R = rules(code)
    try:
        with _LOCK:
            if R.get("analyzer") == "spacy_pkuseg":
                _pkuseg(R.get("model") or "spacy_ontonotes", True)
    except Exception as e:                      # the network, most likely
        say("could not fetch them: %s" % e)
        return False
    return all(m["have"] for m in segmenter.models(code))


def _cli(argv):
    if argv[:1] == ["--fetch"]:
        results = [fetch_models(c) for c in (argv[1:] or ["ja", "zh"])]
        return 0 if all(results) else 1
    if len(argv) < 2:
        print(__doc__.strip().split("\n\n")[0])
        print("\n  python3 lib/words.py <ja|zh> <text>")
        print("  python3 lib/words.py --fetch [ja zh]   download the models an analyzer needs")
        return 2
    code, text = argv[0], " ".join(argv[1:])
    if not available(code):
        print("no analyzer for %s in %s: pip install %s"
              % (code, sys.executable, segmenter.about(code).get("packages", "")))
        return 1
    print(line(text, code))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
