#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Sentences somebody has already translated, for the chunk nobody has glossed.

THE DICTIONARY CANNOT CHOOSE.  It lists every sense a word can ever carry --
`شیر` is lion, faucet, tiger and milk -- and the one this sentence means is
exactly what it has no way to say.  A parallel corpus can, without anybody
guessing: here is that word in a whole sentence, and here is what a person
translated that sentence as.  The reader decides, which is the same
arrangement the dictionary panel already has, with better evidence in it.

WHAT THIS IS NOT.  It is not a translation of the chunk in front of the
reader; it is somebody else's sentence that happens to share words with it.
That is why every match is shown with both sides and with the source named,
and why the panel calls it what it is.  Where nothing matches well enough,
nothing is shown -- an honest blank beats a confident irrelevance.

ONE FILE PER PAIR OF LANGUAGES, `corpus/<code>-<gloss>.db`, built by
lib/getcorpus.py from Tatoeba's own exports, downloaded once and kept
nowhere else.  A language with no corpus is read exactly as it is read
today, the way a language with no dictionary is: the panel simply does not
offer this.

THE MATCH IS WEIGHTED BY RARITY, which is the whole reason it works.  A
sentence sharing `و` (and) with the chunk shares nothing; a sentence sharing
`وطن` (homeland) shares the point.  So every word carries the weight of how
FEW sentences hold it -- plain inverse document frequency, counted at build
time over the corpus itself -- and a match made only of common words scores
below the floor and is not shown.
"""
import io
import json
import math
import os
import sqlite3
import sys
import threading

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import languages                                              # noqa: E402

CORPUS_DIR = os.path.join(ROOT, "corpus")

# How many matched sentences a panel is shown.  Three is what fits under a
# dictionary entry without pushing the meaning off the screen.
MAX_PAIRS = 3
# A match has to be worth reading, and the floor CANNOT BE AN ABSOLUTE SCORE.
# Inverse document frequency is measured against the size of the corpus, so a
# number tuned on Persian's 8 454 pairs is above everything a corpus of two
# hundred can produce -- and a small corpus would then match nothing at all,
# silently, forever.  So the floor is a fraction of what the rarest possible
# word is worth: a word appearing in a single sentence scores log(total/2),
# and half of that is the bar.
MIN_SCORE_SHARE = 0.5


def _floor(total):
    """The least a match may score in a corpus of `total` sentences."""
    if total < 4:
        return 0.0                 # too few to say anything about rarity
    return MIN_SCORE_SHARE * math.log(total / 2.0)
# A sentence far longer than the chunk is a worse illustration of it, and the
# corpus has plenty of short ones.
MAX_SRC_CHARS = 220
# How many words of a chunk are carried into the query.  A chunk is two to six
# words and the server caps what it will look up at 400 characters, but this
# module is also a command line, and an unbounded IN clause is somebody's
# whole book arriving as one SQL statement.
MAX_WORDS = 40

# THE SHAPE OF corpus/<code>-<gloss>.db -- SCHEMA below, filled by
# getcorpus.py through create() -- as a number (lib/version.py FORMATS).  The
# database carries none.  RAISE IT when the shape changes so that the Parseh
# before this one would read the sentences wrong; a column an older reader
# never asks for is not such a change.
DB_FORMAT = 1

SCHEMA = """
PRAGMA journal_mode = OFF;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- One human translation each.  `src` is the language being learnt and `dst`
-- is the gloss language, which is the same direction every panel reads in.
CREATE TABLE pair (
  id  INTEGER PRIMARY KEY,
  src TEXT NOT NULL,
  dst TEXT NOT NULL
);
-- Which sentences hold which word, folded the way lib/lookup.py folds one so
-- that a word looked up in the dictionary and the same word looked for here
-- are the same string.
CREATE TABLE tok (
  word    TEXT NOT NULL,
  pair_id INTEGER NOT NULL
);
-- HOW MANY SENTENCES HOLD IT, not how many times it occurs: the weight a
-- match carries is about how many places a word could have come from.
CREATE TABLE df (
  word TEXT PRIMARY KEY,
  n    INTEGER NOT NULL
);
CREATE INDEX tok_ix ON tok(word);
"""


def path_for(code, gloss):
    """corpus/<code>-<gloss>.db -- and for a variety of a language (Arabic's
    dialects, lib/languages.py) its own file under its key: ar.egy-en.db."""
    L = languages.get_or_default(code)
    G = languages.get_or_default(gloss)
    return os.path.join(CORPUS_DIR, "%s-%s.db" % (L.key, G.code))


def create(path):
    """A new, empty corpus.  Used by getcorpus.py and by the tests, which
    build a small one rather than download anything."""
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    if os.path.exists(path):
        os.unlink(path)
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    return c


def available(code, gloss):
    return os.path.isfile(path_for(code, gloss))


class _Conns(threading.local):
    def __init__(self):
        self.map = {}


_CONNS = _Conns()
_STAMPS = {}


def _stamp(path):
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _conn(code, gloss):
    """One connection per thread per pair, reopened when the file changes --
    the same rule lib/lookup.py follows, and for the same reason: the page
    can rebuild a corpus under a running server."""
    path = path_for(code, gloss)
    key = (code, gloss)
    now = _stamp(path)
    if now is None:
        return None
    if _STAMPS.get(key) != now:
        old = _CONNS.map.pop(key, None)
        if old is not None:
            old.close()
        _STAMPS[key] = now
    c = _CONNS.map.get(key)
    if c is None:
        c = sqlite3.connect(path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        _CONNS.map[key] = c
    return c


def about(code, gloss):
    """What the corpus says about itself: where it came from, how big it is,
    when it was built.  Empty for a pair with no corpus installed."""
    c = _conn(code, gloss)
    if c is None:
        return {}
    try:
        return {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM meta")}
    except sqlite3.Error:
        return {}


# ------------------------------------------------------------------ words
def words_of(code, text):
    """The words of a piece of text, folded, THE WAY THE DICTIONARY FOLDS
    THEM.

    This has to agree with lib/lookup.py or the two halves of the panel are
    looking for different strings: a corpus indexed on `کتاب‌ها` and a
    dictionary that folds it to `کتابها` share nothing.  So the folding is
    borrowed rather than reimplemented, and a language whose dictionary is
    not installed simply gets the plainer split -- which is what the corpus
    was indexed with in that case too.
    """
    import lookup                                             # noqa: E402
    L = languages.get_or_default(code)
    text = text or ""
    if L.spaced:
        raw = L.split_words(text)
    else:
        # An unspaced language has to be cut before anything can be matched,
        # and the dictionary's own word list is the only cutter here.  With
        # no dictionary there is nothing to cut with, and the corpus was
        # built with nothing either, so both sides fall back together.
        c = lookup._conn(code) if lookup.available(code) else None
        raw = lookup._segment(c, lookup._bare(text, L), L) if c else []
    out, seen = [], set()
    for w in raw:
        w = lookup._fold(lookup._bare(w, L), L)
        if not w or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


# ------------------------------------------------------------------ asking
def look_up(code, gloss, text, limit=MAX_PAIRS, offset=0):
    """Sentences a person has translated that share the rare words of `text`.

    -> {"available": bool, "source": {...}, "pairs": [{src, dst, matched,
    score}], "more": bool}, best first.  `offset` and `limit` page that stable
    ranking; the reader starts with three and asks for five more at a time.
    `matched` is the words the sentence shares, so the panel can show WHY a
    sentence is being offered rather than asking the reader to spot it.
    """
    L = languages.get_or_default(code)
    G = languages.get_or_default(gloss)
    try:
        limit = max(1, min(50, int(limit)))
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        limit, offset = MAX_PAIRS, 0
    # L.key, not L.code: a variety's corpus is its own file (ar.egy-en.db);
    # its words are folded as its language's (words_of(L.code, ...))
    out = {"available": available(L.key, G.code), "source": {},
           "pairs": [], "more": False}
    if not out["available"]:
        return out
    c = _conn(L.key, G.code)
    if c is None:
        return out
    out["source"] = about(L.key, G.code)
    words = words_of(L.code, text)[:MAX_WORDS]
    if not words:
        return out
    total = int((out["source"].get("pairs") or "0") or 0) or 1
    # what each word is worth: a word in half the corpus is worth nothing, a
    # word in one sentence in ten thousand is worth the whole match
    weight, rows = {}, c.execute(
        "SELECT word, n FROM df WHERE word IN (%s)"
        % ",".join("?" * len(words)), words).fetchall()
    for r in rows:
        weight[r["word"]] = math.log(total / (1.0 + r["n"]))
    known = [w for w in words if weight.get(w, 0) > 0]
    if not known:
        return out
    # NOTHING CAN QUALIFY IF NOTHING IS RARE.  The gate below is on the rarest
    # word a sentence shares, so a chunk holding no word rare enough to clear
    # the floor cannot produce a match however many sentences hold its common
    # ones -- and asking for those sentences first is the slowest query this
    # module makes (164 ms against Italian's 719 192 pairs, for an answer of
    # nothing).
    floor = _floor(total)
    if max(weight.get(w, 0.0) for w in known) < floor:
        return out
    hits = c.execute(
        "SELECT pair_id, word FROM tok WHERE word IN (%s)"
        % ",".join("?" * len(known)), known).fetchall()
    got = {}
    for r in hits:
        got.setdefault(r["pair_id"], set()).add(r["word"])
    if not got:
        return out
    # THE GATE IS ON THE RAREST WORD AND NOT ON THE SUM.  A sum lets common
    # words add up: `این و آن` (this and that) shares three of the commonest
    # words in Persian with half the corpus, scored 8.47 between them, and
    # offered a sentence about nothing to do with it.  One genuinely rare word
    # in common is what makes a sentence worth showing; the sum then decides
    # which of those to show first.
    scored = []
    for pid, ws in got.items():
        each = [weight.get(w, 0.0) for w in ws]
        if each and max(each) >= floor:
            scored.append((sum(each), pid, ws))
    if not scored:
        return out
    scored.sort(key=lambda x: -x[0])
    # A shorter sentence shows the word more plainly, so among equally scored
    # candidates the short ones come first.  Read ranked candidates in a
    # widening window until this page plus one is known to exist.  The first
    # three therefore stay as cheap as before, while a hundred presses do not
    # create one giant SQLite IN clause (SQLite installations differ in their
    # parameter limit).
    need = offset + limit + 1
    take = min(len(scored), max(24, need * 6))
    rich = []
    while take:
        top = scored[:take]
        ids = [pid for _s, pid, _w in top]
        text_of = {}
        for start in range(0, len(ids), 400):
            batch = ids[start:start + 400]
            text_of.update({r["id"]: (r["src"], r["dst"]) for r in c.execute(
                "SELECT id, src, dst FROM pair WHERE id IN (%s)"
                % ",".join("?" * len(batch)), batch)})
        rich = []
        for score, pid, ws in top:
            pair = text_of.get(pid)
            if not pair or len(pair[0]) > MAX_SRC_CHARS:
                continue
            rich.append((score, -len(pair[0]), pid, ws, pair))
        rich.sort(key=lambda x: (-x[0], -x[1], x[2]))
        if len(rich) >= need or take == len(scored):
            break
        take = min(len(scored), take * 2)
    page = rich[offset:offset + limit]
    out["more"] = len(rich) > offset + len(page) or take < len(scored)
    for score, _neg, _pid, ws, (src, dst) in page:
        out["pairs"].append({"src": src, "dst": dst,
                             "matched": sorted(ws), "score": round(score, 2)})
    return out


def df(code, gloss, word):
    """How many sentences of the corpus hold this word -- 0 for a word it
    does not have, and for a pair with no corpus at all.

    This is the one thing lib/lookup.py borrows: given two entries that both
    fit a word on the page, the one the language actually uses is the one
    the corpus has more of, and that is a count rather than a judgement.
    """
    c = _conn(code, gloss)
    if c is None:
        return 0
    try:
        r = c.execute("SELECT n FROM df WHERE word = ?", (word,)).fetchone()
    except sqlite3.Error:
        return 0
    return int(r["n"]) if r else 0


def counts(code, gloss, words):
    """`df` for many words at once: {word: n}, missing words absent."""
    c = _conn(code, gloss)
    if c is None or not words:
        return {}
    words = list(words)
    try:
        rows = c.execute("SELECT word, n FROM df WHERE word IN (%s)"
                         % ",".join("?" * len(words)), words).fetchall()
    except sqlite3.Error:
        return {}
    return {r["word"]: int(r["n"]) for r in rows}


def any_for(code):
    """The gloss language of some corpus installed for `code`, or "".

    How OFTEN a word is used is a fact about the language being learnt and
    not about the language it is glossed in, so for ranking purposes any
    corpus of that language will do -- and asking for one by name would mean
    the dictionary had to know which book it was being opened from.
    """
    for a, b in installed():
        if a == code:
            return b
    return ""


def installed():
    """Every corpus on this machine, as (code, gloss) pairs."""
    out = []
    try:
        names = sorted(os.listdir(CORPUS_DIR))
    except OSError:
        return out
    for n in names:
        if not n.endswith(".db") or "-" not in n:
            continue
        code, _, gloss = n[:-3].partition("-")
        if gloss not in languages.LANGS:
            continue
        if code in languages.LANGS or is_variety(code):
            out.append((code, gloss))
    return out


def is_variety(code):
    """Is `code` the key of a variety the registry knows (ar.egy)?"""
    base, dot, v = (code or "").partition(".")
    return bool(dot and base in languages.LANGS and languages.LANGS[base].variety_of(v))


# ------------------------------------------------------- a variety's sentences
def look_up_variety(code, variety, gloss, text, limit=MAX_PAIRS, offset=0):
    """look_up() for a text written in a variety of `code` (Arabic's `egy`):
    THE VARIETY'S SENTENCES FIRST, then the language's own, as one ranking
    that `offset` and `limit` page as look_up's does.  Each pair says which
    it is: `variety` is the variety's key, or "" for the standard language's.

    A variety's corpus is small (Tatoeba's Egyptian Arabic is about 1 300
    pairs), so all of its matches are read at once and the standard ones are
    paged after them.  With no variety, or one the language has not, this is
    look_up() itself, its pairs marked as the standard language's."""
    try:
        limit = max(1, min(50, int(limit)))
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        limit, offset = MAX_PAIRS, 0
    base = languages.get_or_default(code)
    V = base.with_variety(variety) if variety else base
    if not V.variety:
        out = look_up(code, gloss, text, limit=limit, offset=offset)
        for p in out["pairs"]:
            p["variety"] = ""
        return out
    mine, at, vsource = [], 0, {}
    if available(V.key, gloss):
        while True:
            r = look_up(V.key, gloss, text, limit=50, offset=at)
            vsource = r.get("source") or vsource
            mine += r["pairs"]
            if not r["more"] or not r["pairs"]:
                break
            at += len(r["pairs"])
    for p in mine:
        p["variety"] = V.variety
    page = mine[offset:offset + limit]
    more = len(mine) > offset + len(page)
    std = {"available": False, "source": {}, "pairs": [], "more": False}
    if available(base.code, gloss):
        want = limit - len(page)
        # a page the variety's sentences fill asks the standard ones for one,
        # only to know whether there is a next page
        std = look_up(base.code, gloss, text, limit=max(want, 1),
                      offset=max(0, offset - len(mine)))
        for p in std["pairs"]:
            p["variety"] = ""
        if want > 0:
            page += std["pairs"][:want]
            more = more or std["more"]
        else:
            more = more or bool(std["pairs"])
    return {"available": bool(vsource) or std["available"],
            "source": std.get("source") or vsource, "variety_source": vsource,
            "pairs": page, "more": more}


def _cli(argv):
    if len(argv) < 3:
        print("usage: corpus.py <code> <gloss> \"<phrase>\"")
        print("")
        print("Installed:")
        for code, gloss in installed() or []:
            m = about(code, gloss)
            print("  %s-%s  %s pairs  %s" % (code, gloss, m.get("pairs", "?"),
                                             m.get("source", "")))
        return 0
    code, gloss, text = argv[0], argv[1], " ".join(argv[2:])
    r = look_up(code, gloss, text)
    if not r["available"]:
        print("no corpus for %s-%s -- build one with lib/getcorpus.py" % (code, gloss))
        return 1
    if not r["pairs"]:
        print("nothing in the corpus is about this phrase")
        return 0
    for p in r["pairs"]:
        print("  %s" % p["src"])
        print("  %s" % p["dst"])
        print("      matched %s (%.2f)" % (", ".join(p["matched"]), p["score"]))
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
