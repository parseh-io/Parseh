# SPDX-License-Identifier: GPL-3.0-or-later
"""Looking for a pictogram, for a PERSON (a0.5.3): the search behind the picker that the Pictograms
door, the studio's editor and its exercise form open (lib/pictograms.js).

lib/getarasaac.py keeps what is installed and lib/arasaacpage.py draws the door.  The model is never
offered a picture through this: the studio's own resolver does that (docs/arasaac.md 5.4), from the same
files.  A person types a word, and wants to SEE what there is and choose, so this answers a word with
the pictograms that name it, best first, each with what the preview shows: the word, what it means, the
other words it has, what ARASAAC says of it.

WHAT IS READ.  Only what lib/getarasaac.py wrote: `index.<locale>.json` (the words of each language
installed), `pictograms.json` (the flags) and the pictures' file names.  Nothing is fetched; nothing a
client sends becomes a path (a language is one of ARASAAC's forty names, a picture is an integer).

THE WORDS ARE FOLDED to be looked for and not to be shown: case, accents, the vowel marks of Arabic,
Persian and Hebrew, the Arabic yeh and kaf that a Persian keyboard writes with its own, the digits of
every script, the zero-width non-joiner between the parts of a Persian word.  A person types "casa",
"Casa", "cása" or "خانه" with either yeh, and finds the same pictures.

HOW A PICTURE IS RANKED, for the words typed (every word must be found, in any order): its keyword
IS what was typed, then its plural is, then a keyword STARTS with it, then a word inside a keyword does
("ice cream" for "cream"), then the text is anywhere in a keyword, then a word of what the pictogram
means begins with it (a meaning is a sentence, and "eat" is not in "great").  Of two at the same step the
shorter keyword comes first, and then the lower number.

A PICTURE THAT IS NOT HERE IS NOT LISTED: a download that has not finished is searched as far as it got,
and the answer says how far that is.  The pictograms ARASAAC marks as about violence or about sex are
left out unless they are asked for, and the answer says how many were left out, so that nobody wonders
why a word they know has no picture.
"""
import os
import re
import sys
import threading
import unicodedata
import urllib.parse

HERE = os.path.dirname(os.path.realpath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import getarasaac as ga                                              # noqa: E402
import languages                                                     # noqa: E402

PAGE_SIZE = 48              # pictures in one answer: a screen of thumbnails
PAGE_MAX = 120
QUERY_MAX = 80              # characters of what is typed
WORDS_SHOWN = 8             # keywords of one language that go with a picture
WORD_MAX = 80               # characters of one of them
SENSITIVE = (1 << ga.FLAGS.index("violence")) | (1 << ga.FLAGS.index("sex"))

_ASCII_GAPS = re.compile(r"[^a-z0-9]+")

# Letters one language writes two ways, folded to one, and the few that no decomposition takes apart.
_ALIKE = {
    "ي": "ی", "ى": "ی", "ئ": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "ؤ": "و", "ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا",
    "ı": "i", "ł": "l", "đ": "d", "ð": "d", "ø": "o", "ħ": "h", "æ": "ae", "œ": "oe", "þ": "th",
    "ـ": None, "‌": " ", "​": " ", "‍": None, "‎": None, "‏": None, "؜": None, "﻿": None,
}
for _i in range(10):                                       # Arabic-Indic and Persian digits: 0 to 9
    _ALIKE[chr(0x660 + _i)] = str(_i)
    _ALIKE[chr(0x6F0 + _i)] = str(_i)
_TABLE = str.maketrans({ord(k): v for k, v in _ALIKE.items()})


def fold(text):
    """`text` as it is looked for: lower case, without accents or vowel marks, one kind of every letter
    a keyboard may write two ways, and every run of anything that is not a letter or a digit a single
    space.  A text with nothing in it is ''.  Applied to the words that are kept and to what is typed,
    so that the two meet."""
    if not isinstance(text, str) or not text:
        return ""
    s = text.casefold()
    if s.isascii():
        return _ASCII_GAPS.sub(" ", s).strip()
    s = unicodedata.normalize("NFKC", s)
    s = unicodedata.normalize("NFD", s).translate(_TABLE)
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat == "Mn":
            continue
        out.append(ch if ch.isalnum() or cat[0] == "M" else " ")
    return " ".join("".join(out).split())


class _Index:
    """One language's words, folded once and flat, so that a search is a few passes over lists of strings
    and not a parse of a megabyte: entry i is a keyword of picture pid[i], its plural p[i], its meaning m[i]."""
    __slots__ = ("words", "pid", "k", "p", "m", "_browse")

    def __init__(self, words):
        self.words = words
        self.pid, self.k, self.p, self.m = [], [], [], []
        self._browse = None
        for pid, entries in words.items():
            for e in entries:
                if not isinstance(e, dict):
                    continue
                k = fold(e.get("k"))
                if not k:
                    continue
                self.pid.append(pid)
                self.k.append(k)
                self.p.append(fold(e.get("p")))
                self.m.append(fold(e.get("m")))

    def browse(self):
        """Every picture that has a word here, by its first keyword: what is shown for no words at all."""
        if self._browse is None:
            firsts = {}
            for pid, entries in self.words.items():
                for e in entries:
                    k = fold(e.get("k")) if isinstance(e, dict) else ""
                    if k:
                        firsts[pid] = k
                        break
            self._browse = [pid for pid, _ in sorted(firsts.items(), key=lambda kv: (kv[1], kv[0]))]
        return self._browse


_LOCK = threading.RLock()
_INDEXES = {}               # path -> ((mtime_ns, size), _Index): rebuilt when its file changes
_PICTURES = {}              # path -> (mtime_ns, frozenset of the numbers that have a file)


def _index(locale):
    """The folded words of an installed language, or None.  Cached against the file: an update or a
    removal is seen by the next search."""
    path = ga.index_path(locale)
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    with _LOCK:
        got = _INDEXES.get(path)
        if got and got[0] == key:
            return got[1]
        words = ga.words(locale)
        if not words:
            return None
        idx = _Index(words)
        _INDEXES[path] = (key, idx)
        return idx


def pictured():
    """The numbers of the pictures that are on the disk: one look at the folder, repeated only when the
    folder changed (a download adds files all the time, so a search during one looks again)."""
    path = ga.pictures_dir()
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        return frozenset()
    with _LOCK:
        got = _PICTURES.get(path)
        if got and got[0] == stamp:
            return got[1]
        ids = set()
        try:
            with os.scandir(path) as it:
                for e in it:
                    if e.name.endswith(".png") and e.name[:-4].isdigit():
                        ids.add(int(e.name[:-4]))
        except OSError:
            return frozenset()
        got = (stamp, frozenset(ids))
        _PICTURES[path] = got
        return got[1]


def forget():
    """Let go of everything read (a test that points getarasaac at another folder)."""
    with _LOCK:
        _INDEXES.clear()
        _PICTURES.clear()


def installed_locales():
    """The languages whose words are here and readable, in getarasaac's order (English first)."""
    return [loc for loc in ga.locales_here() if _index(loc) is not None]


def locale_rows(codes):
    """What a language select draws for each: the code, its name, its own name, whether it is written
    right to left.  A code Parseh has no language for is named by its code."""
    out = []
    for code in codes:
        L = languages.LANGS.get(code)
        out.append({"code": code, "name": L.name if L else code, "native": L.native if L else code,
                    "rtl": bool(L and L.dir == "rtl")})
    return out


def flag_names(bits):
    """The names of the flags a pictogram has, in ARASAAC's own words (getarasaac.FLAGS)."""
    return [name for i, name in enumerate(ga.FLAGS) if bits & (1 << i)]


def version(pid, facts=None):
    """A short mark that changes when the picture of `pid` does -- the day ARASAAC last changed it and the
    size the pictures are at -- so that an address carrying it can be kept by a browser for good."""
    rec = (facts if facts is not None else ga.facts()).get(pid) or {}
    day = re.sub(r"\D", "", str(rec.get("u") or ""))[:17] or "0"
    return "%s-%s" % (day, ga.manifest().get("resolution") or 0)


def _tier(q, toks, k, p, m):
    """How well an entry answers the words typed: 0 (it is what was typed) to 5 (only its meaning has
    them), or None when it does not answer."""
    if q == k:
        return 0
    if q == p:
        return 1
    if k.startswith(q) or (p and p.startswith(q)):
        return 2
    wk, wp = " " + k, (" " + p if p else "")
    if all((" " + t) in wk or (wp and (" " + t) in wp) for t in toks):
        return 3
    if all(t in k or (p and t in p) for t in toks):
        return 4
    wm = " " + m if m else ""
    if all(t in k or (p and t in p) or (wm and (" " + t) in wm) for t in toks):
        return 5
    return None


def _match(idx, q, toks, hit):
    """Into `hit` {number: (step, length of the keyword)}, the best any entry of `idx` gets for each picture."""
    first = max(toks, key=len)
    ks, ps, ms = idx.k, idx.p, idx.m
    cand = {i for i, k in enumerate(ks) if first in k}
    cand.update(i for i, p in enumerate(ps) if p and first in p)
    cand.update(i for i, m in enumerate(ms) if m and first in m)
    for i in cand:
        step = _tier(q, toks, ks[i], ps[i], ms[i])
        if step is None:
            continue
        key = (step, len(ks[i]))
        pid = idx.pid[i]
        if pid not in hit or key < hit[pid]:
            hit[pid] = key


def _clip(text):
    return text if len(text) <= WORD_MAX else text[:WORD_MAX - 1] + "…"


def _describe(pid, indexes, display, matched, facts):
    """One picture as the picker draws it and previews it: the word it is shown under (the display
    language's first keyword, else the one that was found, else any), what it means, every language's
    first few keywords (the display language's first), the flags ARASAAC gives it."""
    words, meanings = {}, {}
    for loc, idx in sorted(indexes, key=lambda li: li[0] != display):
        entries = idx.words.get(pid)
        if not entries:
            continue
        seen = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            k = e.get("k")
            if isinstance(k, str) and k and k not in seen:
                seen.append(k)
            if loc not in meanings and isinstance(e.get("m"), str) and e["m"]:
                meanings[loc] = e["m"]
        if seen:
            words[loc] = [_clip(w) for w in seen[:WORDS_SHOWN]]
    lang = display if display in words else matched if matched in words else next(iter(words), "")
    meaning = meanings.get(display) or next(iter(meanings.values()), "")
    bits = (facts.get(pid) or {}).get("f") or 0
    return {"id": pid, "word": words[lang][0] if lang else "", "lang": lang,
            "meaning": _clip(meaning), "words": words, "flags": flag_names(bits), "v": version(pid, facts)}


def _state(here, have, facts):
    """"absent" (no word list and no picture), "partial" (a download not finished, or stopped), or
    "installed" -- read from the manifest and the records, never from a walk of the pictures
    (getarasaac.status() does that, and a search is asked for at every key)."""
    if not here and not have:
        return "absent"
    pending = any(r.get("p") for r in facts.values())
    return "installed" if ga.manifest().get("complete") and not pending and facts else "partial"


def _int(value, name, low, high, default):
    if value is None:
        return default
    if type(value) is not int or not low <= value <= high:
        raise ga.ArasaacError("bad-request", "%s must be a whole number from %d to %d." % (name, low, high))
    return value


def search(query="", locales=None, display=None, offset=0, limit=PAGE_SIZE, sensitive=False):
    """The pictograms for `query`, best first, one page of them.

        query      what was typed (at most QUERY_MAX characters); nothing at all lists every picture
                   that has a word in the display language, by that word
        locales    the languages to look in (a list of ARASAAC's names), else every one that is here
        display    the language the words under the pictures are shown in -- a hint: one that is not here
                   (a document may be in Japanese, which ARASAAC has no words for) is English, else the first
        offset     how many pictures to skip, limit how many to give (at most PAGE_MAX)
        sensitive  True to include the pictograms ARASAAC marks as about violence or sex

    -> {"ok", "ready", "state", "q", "locales" (here), "searched", "display", "total", "hidden",
        "offset", "more", "results", "pictures", "listed", "credit"}.  Nothing here, or not yet: `ready` is
    False and there are no results.  An ArasaacError for a request that is not well made."""
    if query is None:
        query = ""
    if not isinstance(query, str):
        raise ga.ArasaacError("bad-request", "What to look for must be text.")
    if len(query) > QUERY_MAX * 4:
        raise ga.ArasaacError("bad-request", "That is too long to look for: at most %d characters." % QUERY_MAX)
    offset = _int(offset, "offset", 0, 10 ** 6, 0)
    limit = _int(limit, "limit", 1, PAGE_MAX, PAGE_SIZE)
    if display is not None and not isinstance(display, str):
        raise ga.ArasaacError("bad-request", "The language the words are shown in must be a name.")
    asked = ga.check_locales(locales) if locales else ()
    here = installed_locales()
    have = pictured()
    facts = ga.facts()
    out = {"ok": True, "ready": bool(here and have), "state": _state(here, have, facts),
           "fetching": bool(ga.running()), "q": query.strip()[:QUERY_MAX], "locales": locale_rows(here),
           "searched": [], "display": "", "total": 0, "hidden": 0, "offset": offset, "more": False,
           "results": [], "pictures": len(have), "listed": len(facts), "credit": ga.CREDIT_SHORT}
    if not here or not have:
        return out
    searched = [loc for loc in here if loc in asked] or here
    shown = display if display in here else (ga.BASE_LOCALE if ga.BASE_LOCALE in here else here[0])
    indexes = [(loc, _index(loc)) for loc in here]
    indexes = [(loc, idx) for loc, idx in indexes if idx is not None]
    # what is looked in: the languages asked for, the display language's words always the ones shown
    look = [(loc, idx) for loc, idx in indexes if loc in searched]
    out["searched"], out["display"] = [loc for loc, _ in look], shown
    q = fold(out["q"])
    if q:
        toks = q.split()
        hit, found = {}, {}
        for loc, idx in look:
            mine = {}
            _match(idx, q, toks, mine)
            for pid, key in mine.items():
                if pid not in hit or key < hit[pid]:
                    hit[pid], found[pid] = key, loc
        order = [pid for pid, _ in sorted(hit.items(), key=lambda kv: (kv[1], kv[0]))]
    else:
        base = dict(indexes).get(shown)
        order, found = (base.browse() if base is not None else []), {}
    visible = []
    for pid in order:
        if pid not in have:
            continue
        if sensitive is not True and ((facts.get(pid) or {}).get("f") or 0) & SENSITIVE:
            out["hidden"] += 1
            continue
        visible.append(pid)
    out["total"] = len(visible)
    page = visible[offset:offset + limit]
    out["more"] = offset + limit < len(visible)
    out["results"] = [_describe(pid, indexes, shown, found.get(pid), facts) for pid in page]
    return out


def cache_control(query):
    """What a browser is told about a picture.  One asked for with the version `search` gave it (?v=...)
    never changes under that address -- an update moves the version -- so it may be kept for good; one
    asked for bare is asked about each time."""
    return "max-age=31536000, immutable" if "v" in urllib.parse.parse_qs(query or "") else "no-cache"


def picture(pid):
    """The file of picture `pid` -- an integer, or the digits of one -- or None when it is not here."""
    if isinstance(pid, str):
        if not pid.isascii() or not pid.isdigit() or len(pid) > 7:
            return None
        pid = int(pid)
    try:
        path = ga.picture_path(pid)
    except ga.ArasaacError:
        return None
    return path if os.path.isfile(path) else None
