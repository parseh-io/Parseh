#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The ARASAAC pictograms, optional and local: a picture for a word, kept on
this computer (TO-DO §8.40, W9, a0.4.2).

    python3 lib/getarasaac.py                   what is installed
    python3 lib/getarasaac.py get en fr         the word lists of those languages, and every picture
    python3 lib/getarasaac.py get en --500      ...with the larger pictures (300 pixels is the default)
    python3 lib/getarasaac.py update            only what ARASAAC has added or changed since
    python3 lib/getarasaac.py remove [fr]       one language's word list, or the whole folder

WHAT THIS IS.  ARASAAC (the Aragonese Portal of Augmentative and Alternative
Communication) publishes some fourteen thousand pictograms -- a house, to eat,
nervous -- drawn by Sergio Palao for the Government of Aragon, each with the
words that name it in some forty languages.  Parseh keeps them in `arasaac/`
so that an exercise the studio asks a chatbot to write can carry a picture of
what it is about.  It is optional in every sense: nothing here is imported,
fetched or started until somebody presses *get it* on Settings -> Pictograms
(lib/arasaacpage.py), and a person who never asks for it has the toolbox they
had.

THE LICENCE IS NOT PARSEH'S TO WAIVE.  The pictograms are CC BY-NC-SA 4.0:
the author, the owner and ARASAAC are to be named, nothing made with them is
for commercial use, and what is shared is shared on the same licence.  The
terms are https://arasaac.org/terms-of-use; their two forms of the credit are
CREDIT below, written word for word into `arasaac/LICENSE-ARASAAC.txt` when a
download ends, shown on the page before anybody presses a button, and listed
on /licences/ (lib/notices.py).

TWO HOSTS, AND NOTHING ELSE.  The word lists come from `api.arasaac.org`
(`GET /v1/pictograms/all/<locale>`, no key) and the pictures from
`static.arasaac.org` (`/pictograms/<id>/<id>_<300|500>.png`).  Whoever presses
the button, nothing a client sends becomes a path or an address: a language is
one of the forty names ARASAAC's own API lists (LOCALES), a size is one of two
numbers, and an id is an integer out of the answer the API gave.

WHAT IT TAKES, AND HOW MUCH (MEASURED, 2026-10-02: MEASURED below).  Every
language's answer lists all 13,829 pictograms -- the same ids, with the
language's words where it has any -- at 5 to 8 MB of JSON, of which Parseh keeps
a part only (the words, and a few facts: 2.4 MB of Spanish's 8.2, 0.1 of Turkish's 5.2).  The pictures come
one at a time on one connection, 11 kB each at 300 pixels and 23 kB at 500
(a random 400 of the ids, both sizes): 159 MB and 321 MB for the lot.  A
person is told that before anything is fetched.

WHERE IT GOES.  `arasaac/` beside dict/, mt/ and stt/ -- git-ignored, kept by
every update, outside what a backup copies (lib/release.py CONTENT,
lib/updater.py PERSONAL):

    manifest.json            the shape (ARASAAC_FORMAT), the size the pictures are at, when
    pictograms.json          one record per pictogram: the facts that do not depend on a language
    index.<locale>.json      one language's words, trimmed to what Parseh reads
    pictograms/<id>.png      the pictures, all at the one size the manifest says
    LICENSE-ARASAAC.txt      the credit and the licence, written when a download ends

THE FILES ARE THE RECORD OF HOW FAR IT GOT.  A picture appears at its own name
by one rename, so a file there is a whole one; `pictograms.json` marks each
record whose picture has not been confirmed yet (`p`), and is written every
few hundred pictures and when the run stops, for whatever reason.  A download
that was stopped, killed or cut by a dropped line carries on from there with
nothing fetched twice, and an update is the same walk over the records whose
`lastUpdated` the new list moved.

AN UPDATE ASKS BEFORE IT FETCHES.  A picture that is here is asked for again
with `If-Modified-Since` -- its own modification time is the server's
`Last-Modified` of the file it holds -- and the server answers 304 for the
many whose record changed (a keyword was mended) without the picture changing.

GENTLE ON A HOST THAT IS NOT PARSEH'S.  One connection, one picture at a time,
a short pause between two, a User-Agent that names Parseh, the server's
`Retry-After` obeyed, and a wait that grows after an error.  Standard library
only, like the rest of lib/: this runs inside serve.py's threads and from the
command line alike.
"""
import argparse
import email.utils
import http.client
import json
import os
import shutil
import socket
import sys
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import download       # noqa: E402  resumable, stoppable, and says how far
import version        # noqa: E402  who is asking: UA
import project        # noqa: E402  where Parseh lives, for the line a download introduces itself with: UA

ARASAAC_DIR = os.path.join(ROOT, "arasaac")
# the shape of manifest.json, pictograms.json and index.<locale>.json, as a
# number (lib/version.py FORMATS); the three are written together
ARASAAC_FORMAT = 1

API = "https://api.arasaac.org/v1"
STATIC = "https://static.arasaac.org/pictograms"
HOSTS = ("api.arasaac.org", "static.arasaac.org")
TERMS = "https://arasaac.org/terms-of-use"
UA = project.agent(version.VERSION)
SETTINGS_PAGE = "/settings/arasaac/"
GUIDE = "/guide/site/studio/pictograms.html"

# ---------------------------------------------------------------- the licence
# THE CREDIT, WORD FOR WORD from the terms page as rendered on 2026-10-02
# ("How to cite the ARASAAC license": there are two ways to attribute
# authorship).  The brief's own paraphrase said "Aragon" and "https://": the
# terms say what is written here.
CREDIT = ("The pictographic symbols used are the property of the Government of Aragón and have been "
          "created by Sergio Palao for ARASAAC (http://www.arasaac.org), that distributes them under "
          "Creative Commons License BY-NC-SA.")
CREDIT_SHORT = ("Pictograms author: Sergio Palao. Origin: ARASAAC (http://www.arasaac.org). "
                "License: CC (BY-NC-SA). Owner: Government of Aragon (Spain)")
SOURCE = "ARASAAC pictograms: Sergio Palao for ARASAAC (the Government of Aragon, Spain)"
LICENCE = "CC BY-NC-SA 4.0"
LICENCE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"

# -------------------------------------------------------------- what is asked
RESOLUTIONS = (300, 500)                    # 2500 is a 335 kB poster: never
DEFAULT_RESOLUTION = 300
# THE LANGUAGES ARASAAC'S API ANSWERS FOR, as its own error message lists them
# (a request for any other is a 400): copied on 2026-10-02.  Parseh's `ja` is
# not among them, and its `hi` is, with one word.
LOCALES = frozenset("an ar bg br ca cs da de el en es et eu fa fr gl he hi hr hu it is ko lt lv mk "
                    "nb nl pl pt ro ru sk sq sv sr tr val uk zh".split())
BASE_LOCALE = "en"          # the one the studio always needs: ARASAAC's own words are Spanish, its widest are these
# below this share of the pictograms having a word in a language, ARASAAC "has" the language on paper only
MIN_COVERAGE = 0.02

# THE FACTS KEPT OF EACH PICTOGRAM, and the bit each is.  They are the API's own
# names; `violence` and `sex` are what the studio may leave out of what a model
# is offered, `schematic` the simpler drawing of the same thing, `skin` and `hair` the ones
# whose colours the API can change.
FLAGS = ("schematic", "aac", "aacColor", "skin", "hair", "violence", "sex")

# WHAT EACH COSTS, MEASURED on 2026-10-02 against the real hosts.  `png` is the
# mean size of a random 400 of the ids (seed 20261002, a HEAD on each: all 400
# answered 200 at both sizes), `locales` each language's answer as it came
# (`raw`), what is kept of it (`kept`), its keyword entries and how many
# pictograms have at least one.  Read by plan(), so the page says how big
# before anybody presses a button and never asks a server.
MEASURED = {
    "date": "2026-10-02",
    "pictograms": 13829,
    "png": {300: 11469, 500: 23231},
    # pictograms.json, as getarasaac.trim keeps it: one record each, with the dates and the flags
    "facts": 973762,
    "locales": {
        "en": {"raw": 7604383, "kept": 1846377, "entries": 26578, "covered": 13829},
        "es": {"raw": 8160802, "kept": 2386459, "entries": 21074, "covered": 13829},
        "fa": {"raw": 6728271, "kept": 1089344, "entries": 25037, "covered": 13112},
        "ar": {"raw": 5711114, "kept": 443234, "entries": 11572, "covered": 8609},
        "hi": {"raw": 5028900, "kept": 88, "entries": 1, "covered": 1},
        "zh": {"raw": 5821458, "kept": 484038, "entries": 15203, "covered": 11315},
        "tr": {"raw": 5201971, "kept": 113145, "entries": 2783, "covered": 2656},
        "it": {"raw": 6410490, "kept": 855815, "entries": 22399, "covered": 13799},
        "fr": {"raw": 6849895, "kept": 1150075, "entries": 26020, "covered": 13712},
        "de": {"raw": 6394195, "kept": 805694, "entries": 24484, "covered": 13800},
    },
}
# for a language nobody measured (one a person added, that ARASAAC has): the middle of the others
GUESS = {"raw": 6400000, "kept": 1000000}
INDEX_LIMIT = 40 << 20      # a word list larger than this is not one: refused
PICTURE_LIMIT = 3 << 20     # ...and neither is a picture (the largest of 800 measured was 67 kB)
# a list with fewer pictograms than this is a server's half answer, not ARASAAC's (13,829 today)
MIN_RECORDS = 1000

# --------------------------------------------------------------- the pacing
PAUSE = 0.02                # seconds between two pictures: about twenty a second at most, on one connection
# what the page says the time is, per picture: the pause, and a request on a kept-open connection
# (17 ms measured against the real host, a HEAD of 150 of them), and the bytes of one
SECONDS_PER_PICTURE = 0.05
FLUSH_EVERY = 250           # pictures between two writes of pictograms.json
FLUSH_SECONDS = 5.0
RETRIES = (2, 5, 15, 40)    # seconds waited after each failed try of one picture
RETRY_AFTER_MAX = 120       # ...and the most a server's Retry-After is obeyed for
TIMEOUT = 30
WORDS_PER_ENTRY = 40        # keywords kept for one pictogram, at most
TEXT_MAX = 300              # characters of a keyword, a plural or a meaning

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
PNG_END = b"IEND\xaeB`\x82"


class ArasaacError(Exception):
    """Something a person can be told, in a sentence: `code` for the program,
    `say` for the page.  Never a traceback."""

    def __init__(self, code, say):
        super().__init__(say)
        self.code = code
        self.say = say


# ------------------------------------------------------------ where things are
# EVERY PATH IS A FUNCTION OF ARASAAC_DIR, AT THE MOMENT OF THE CALL: a test that
# points ARASAAC_DIR at a temporary tree must never find this module holding the
# checkout's own arasaac/ (which may be a computer's 160 MB of pictures).
def folder():
    return ARASAAC_DIR


def manifest_path():
    return os.path.join(ARASAAC_DIR, "manifest.json")


def facts_path():
    return os.path.join(ARASAAC_DIR, "pictograms.json")


def licence_path():
    return os.path.join(ARASAAC_DIR, "LICENSE-ARASAAC.txt")


def index_path(locale):
    return os.path.join(ARASAAC_DIR, "index.%s.json" % check_locale(locale))


def pictures_dir():
    return os.path.join(ARASAAC_DIR, "pictograms")


def picture_path(pid):
    """Where pictogram `pid` is kept when it is here: only ever an integer's name."""
    return os.path.join(pictures_dir(), "%d.png" % check_id(pid))


def tmp_dir():
    return os.path.join(ARASAAC_DIR, "tmp")


def check_locale(locale):
    """`locale` if it is one of the languages ARASAAC lists, else an ArasaacError.  The
    only door from a name to a path or an address: what a client sends never gets
    further unless it is one of forty exact strings."""
    if not isinstance(locale, str) or locale not in LOCALES:
        raise ArasaacError("bad-language", "%r is not a language ARASAAC has." % (locale,))
    return locale


def check_resolution(resolution):
    if type(resolution) is not int or resolution not in RESOLUTIONS:
        raise ArasaacError("bad-size", "Pictures come at %s pixels." % " or ".join(str(r) for r in RESOLUTIONS))
    return resolution


def check_id(pid):
    if type(pid) is not int or not 0 < pid < 10 ** 7:
        raise ArasaacError("bad-id", "%r is not a pictogram's number." % (pid,))
    return pid


def check_locales(locales):
    """The list a request names -> a tuple of locales, each once, in the order given."""
    if isinstance(locales, str) or not isinstance(locales, (list, tuple)):
        raise ArasaacError("bad-language", "Choose the languages from the list.")
    out = []
    for loc in locales:
        check_locale(loc)
        if loc not in out:
            out.append(loc)
    return tuple(out)


def offered(locale):
    """(True, "") when a language's words are worth fetching, else (False, why): it has none
    on ARASAAC's list, or hardly any (Hindi's list holds one word, and it is Spanish)."""
    if locale not in LOCALES:
        return False, "ARASAAC has no words in this language."
    got = MEASURED["locales"].get(locale)
    if got and got["covered"] < MIN_COVERAGE * MEASURED["pictograms"]:
        return False, "ARASAAC has almost no words in this language yet (%d)." % got["entries"]
    return True, ""


# ------------------------------------------------------------------ the files
def _write_json(path, obj):
    """Written beside and moved over, so a reader never meets half a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        return doc if isinstance(doc, dict) else None
    except (OSError, ValueError):
        return None


def manifest():
    """What manifest.json says, or {} -- including when it is of another shape."""
    doc = _read_json(manifest_path())
    return doc if doc and doc.get("format") == ARASAAC_FORMAT else {}


_FACTS = {}                 # path -> (mtime_ns, size, the records): a poll is not a parse of a megabyte


def facts():
    """{id: {"u": lastUpdated, "f": flag bits, "s": [WordNet synsets], "p": 1 if its picture is
    still to be confirmed, "x": 1 if it has none at this size}}, or {}."""
    path = facts_path()
    try:
        st = os.stat(path)
    except OSError:
        return {}
    key = (st.st_mtime_ns, st.st_size)
    if _FACTS.get(path, (None,))[0] == key:
        return _FACTS[path][1]
    doc = _read_json(path)
    if not doc or doc.get("format") != ARASAAC_FORMAT or not isinstance(doc.get("pictograms"), dict):
        return {}
    got = {}
    for k, v in doc["pictograms"].items():
        if k.isdigit() and isinstance(v, dict):
            got[int(k)] = v
    _FACTS[path] = (key, got)
    return got


def _save_facts(records):
    _write_json(facts_path(), {"format": ARASAAC_FORMAT, "pictograms": {str(k): v for k, v in records.items()}})
    _FACTS.pop(facts_path(), None)


def words(locale):
    """{id: [{"k": keyword, "t": type, "p": plural, "m": meaning}, ...]} of a language
    installed here, or {}.  Only the pictograms with a word in it are listed, the first
    keyword being the one ARASAAC puts first."""
    doc = _read_json(index_path(locale))
    if not doc or doc.get("format") != ARASAAC_FORMAT or not isinstance(doc.get("words"), dict):
        return {}
    return {int(k): v for k, v in doc["words"].items() if k.isdigit()}


def locales_here():
    """The languages whose word list is installed, in the order ARASAAC's own list gives them
    for the ones Parseh measured and then the rest."""
    try:
        names = os.listdir(ARASAAC_DIR)
    except OSError:
        return []
    out = [n[len("index."):-len(".json")] for n in names if n.startswith("index.") and n.endswith(".json")]
    return sorted((loc for loc in out if loc in LOCALES),
                  key=lambda loc: (loc != BASE_LOCALE, loc))


def pictures_here():
    """How many pictures are on the disk, and what they weigh: one walk of the folder, at
    most a few hundredths of a second for all of them (the names only when `size` is False)."""
    n = size = 0
    try:
        with os.scandir(pictures_dir()) as it:
            for e in it:
                if e.name.endswith(".png") and e.name[:-4].isdigit():
                    n += 1
                    size += e.stat().st_size
    except OSError:
        pass
    return n, size


def is_png(data):
    """A whole PNG: its signature at the head and its closing chunk at the tail.  A picture
    cut short by a dropped line has the first and not the second."""
    return len(data) > 64 and data.startswith(PNG_MAGIC) and PNG_END in data[-16:]


# ---------------------------------------------------------------- the word lists
def trim(answer):
    """(words, facts) out of one language's `all` answer: the words of the pictograms that
    have any, and the facts that do not depend on a language.  An answer that is not a
    list of records with numbers and dates is refused, never trimmed to nothing -- a
    server's half answer must not replace a whole index."""
    if not isinstance(answer, list):
        raise ArasaacError("bad-list", "ARASAAC's list of pictograms was not a list.")
    out_words, out_facts, junk = {}, {}, 0
    for rec in answer:
        pid = rec.get("_id") if isinstance(rec, dict) else None
        if type(pid) is not int or not 0 < pid < 10 ** 7:
            junk += 1
            continue
        bits = 0
        for i, name in enumerate(FLAGS):
            if rec.get(name) is True:
                bits |= 1 << i
        fact = {"u": str(rec.get("lastUpdated") or "")[:40], "f": bits}
        syn = [s for s in (rec.get("synsets") or []) if isinstance(s, str) and len(s) <= 20][:30]
        if syn:
            fact["s"] = syn
        out_facts[pid] = fact
        entries = []
        for k in (rec.get("keywords") or [])[:WORDS_PER_ENTRY]:
            text = _clean(k.get("keyword")) if isinstance(k, dict) else ""
            if not text:
                continue
            e = {"k": text}
            if type(k.get("type")) is int and 0 < k["type"] < 10:
                e["t"] = k["type"]
            for src, dst in (("plural", "p"), ("meaning", "m")):
                extra = _clean(k.get(src))
                if extra:
                    e[dst] = extra
            entries.append(e)
        if entries:
            out_words[pid] = entries
    if len(out_facts) < MIN_RECORDS or junk > len(answer) // 20:
        raise ArasaacError("bad-list", "ARASAAC's list of pictograms is not the one Parseh expects "
                                       "(%d usable records of %d). Nothing was changed." % (len(out_facts), len(answer)))
    return out_words, out_facts


def _clean(text):
    """A word as it is kept: a string, without control characters, at most TEXT_MAX long."""
    if not isinstance(text, str):
        return ""
    return "".join(c for c in text if c >= " " and c != "\x7f").strip()[:TEXT_MAX]


def _fetch_words(locale, say, progress, cancel):
    """One language's answer, through lib/download.py (resumed if it was cut, stopped between two
    blocks) into tmp/, trimmed and put in place; -> (words, facts, bytes fetched)."""
    got = MEASURED["locales"].get(locale) or GUESS
    raw = os.path.join(tmp_dir(), "all.%s.json" % locale)
    url = "%s/pictograms/all/%s" % (API, locale)
    say("fetching the %s word list" % locale)
    download.fetch(url, raw, say=say, progress=progress, cancel=cancel, headers={"User-Agent": UA},
                   size=got["raw"], limit=INDEX_LIMIT, timeout=120)
    try:
        with open(raw, encoding="utf-8") as f:
            answer = json.load(f)
    except (OSError, ValueError):
        download.discard(raw)
        _unlink(raw)
        raise ArasaacError("bad-list", "ARASAAC's word list for %s could not be read. Nothing was changed." % locale)
    size = os.path.getsize(raw)
    try:
        new_words, new_facts = trim(answer)
    finally:
        del answer
    _unlink(raw)
    return new_words, new_facts, size


def _unlink(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


# --------------------------------------------------------------- the pictures
class _Session:
    """One connection to the pictures' host, kept open from one picture to the next: a request
    on it takes a few hundredths of a second, one that opens its own takes four times that,
    and a host that is not Parseh's is asked least by the one connection."""

    def __init__(self, base, headers, timeout=TIMEOUT):
        parts = urllib.parse.urlsplit(base)
        self.https = parts.scheme == "https"
        self.netloc = parts.netloc
        self.prefix = parts.path.rstrip("/")
        self.headers = dict(headers)
        self.timeout = timeout
        self.conn = None

    def close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except OSError:
                pass
            self.conn = None

    def get(self, path, extra=None):
        """-> (status, headers, body).  A connection the server closed while it sat idle is made
        again once, silently: that is how a kept-open connection ends, not a failure."""
        for fresh in (False, True):
            if self.conn is None:
                cls = http.client.HTTPSConnection if self.https else http.client.HTTPConnection
                self.conn = cls(self.netloc, timeout=self.timeout)
            try:
                self.conn.request("GET", self.prefix + path, headers=dict(self.headers, **(extra or {})))
                r = self.conn.getresponse()
                length = r.getheader("Content-Length")
                if length and length.isdigit() and int(length) > PICTURE_LIMIT:
                    self.close()
                    raise ArasaacError("too-big", "A picture was larger than ARASAAC's pictures are.")
                body = r.read(PICTURE_LIMIT + 1)
                if len(body) > PICTURE_LIMIT:
                    self.close()
                    raise ArasaacError("too-big", "A picture was larger than ARASAAC's pictures are.")
                if (r.getheader("Connection") or "").lower() == "close":
                    self.close()
                return r.status, r, body
            except (http.client.RemoteDisconnected, http.client.CannotSendRequest, BrokenPipeError,
                    ConnectionResetError, ConnectionAbortedError):
                self.close()
                if fresh:
                    raise
        raise OSError("unreachable")        # pragma: no cover -- the loop returns or raises


def _sleep(seconds, cancel):
    """Wait, a fifth of a second at a time, so that Stop is heard."""
    end = time.monotonic() + seconds
    while True:
        download.check(cancel)
        left = end - time.monotonic()
        if left <= 0:
            return
        time.sleep(min(0.2, left))


def _retry_after(response):
    """The seconds a busy server asked to be left alone for, as a whole number, or None."""
    value = response.getheader("Retry-After")
    if value and value.strip().isdigit():
        return min(int(value.strip()), RETRY_AFTER_MAX)
    return None


def _fetch_picture(session, pid, resolution, cancel):
    """One picture into pictograms/<id>.png.  -> "new", "same" (the server says it has not
    changed), or "none" (the host has no picture of that number at this size).  Errors that
    mend themselves -- a busy server, a line that dropped -- are waited out; the
    last one is raised as an OSError in words and the next press carries on."""
    dest = picture_path(pid)
    path = "/%d/%d_%d.png" % (pid, pid, resolution)
    extra = {}
    if os.path.isfile(dest):
        # AN UPDATE ASKS BEFORE IT FETCHES: the file's own time is the server's Last-Modified
        extra["If-Modified-Since"] = email.utils.formatdate(os.path.getmtime(dest), usegmt=True)
    last = ""
    for attempt, wait in enumerate((0,) + RETRIES):
        if wait:
            _sleep(wait, cancel)
        download.check(cancel)
        try:
            status, r, body = session.get(path, extra)
        except (OSError, http.client.HTTPException, socket.timeout) as e:
            session.close()
            last = "the pictures' host did not answer (%s)" % (str(e) or type(e).__name__)
            continue
        if status == 304:
            return "same"
        if status in (404, 410):
            return "none"
        if status in (429, 500, 502, 503, 504):
            last = "the pictures' host said it was busy (%d)" % status
            hold = _retry_after(r)
            if hold:
                _sleep(hold, cancel)
            session.close()
            continue
        if status != 200:
            raise OSError("The pictures' host answered %d for pictogram %d: nothing more was fetched." % (status, pid))
        if not is_png(body):
            # A BODY THAT IS NOT A WHOLE PICTURE is never put in place, and is tried again
            last = "what came for pictogram %d was not a whole picture" % pid
            session.close()
            continue
        os.makedirs(pictures_dir(), exist_ok=True)
        part = dest + ".part"
        with open(part, "wb") as f:
            f.write(body)
        stamp = r.getheader("Last-Modified")
        try:
            when = email.utils.parsedate_to_datetime(stamp).timestamp() if stamp else None
        except (TypeError, ValueError):
            when = None
        if when:
            os.utime(part, (when, when))
        os.replace(part, dest)
        return "new"
    raise OSError("%s, after %d tries. What was fetched is kept: press it again to carry on." % (last, len(RETRIES) + 1))


# ------------------------------------------------------------------- the plan
def disk_free(path):
    at = os.path.abspath(path)
    while not os.path.isdir(at) and os.path.dirname(at) != at:
        at = os.path.dirname(at)
    return shutil.disk_usage(at).free


def plan(locales=(BASE_LOCALE,), resolution=DEFAULT_RESOLUTION, update=False):
    """What getting these would cost, said before anything is fetched -- from the shipped table
    of measured sizes and from what is on the disk, asking nobody:

        download   bytes to come, the word lists as they are served and the pictures
        words      {locale: {"raw", "kept"}} for each list still to fetch
        pictures   how many are still to come, and about how many bytes
        kept       what it all weighs once it is here, beside what is here already
        disk_peak  the most room it needs at once
        have       the pictures already here, in bytes (an interrupted run, or an earlier one)

    `measured` is False where a language of the list was never measured (a guess is used)."""
    locales = check_locales(locales)
    resolution = check_resolution(resolution)
    mine = manifest()
    same_size = not mine or mine.get("resolution") == resolution
    have_n, have_bytes = pictures_here() if same_size else (0, 0)
    known = facts()
    total = len(known) or MEASURED["pictograms"]
    mean = MEASURED["png"][resolution]
    here = locales_here()
    todo, measured = {}, True
    for loc in locales:
        if update or loc not in here:
            got = MEASURED["locales"].get(loc)
            measured = measured and bool(got)
            todo[loc] = {"raw": (got or GUESS)["raw"], "kept": (got or GUESS)["kept"]}
    # AN UPDATE PROMISES NO PICTURES: only the ones a changed record names are fetched again,
    # and which they are is not known before the lists have come
    pictures_n = 0 if update else max(total - have_n - sum(1 for r in known.values() if r.get("x")), 0)
    pictures_bytes = pictures_n * mean
    words_raw = sum(v["raw"] for v in todo.values())
    # (pictograms.json is made from the first list that comes, and is not asked for on its own)
    words_kept = sum(v["kept"] for v in todo.values()) + (0 if known else MEASURED["facts"])
    words_here = sum(os.path.getsize(index_path(loc)) for loc in here if loc not in todo)
    answer = download.plan(download=words_raw + pictures_bytes + have_bytes, measured=measured,
                           kept=words_here + words_kept + pictures_bytes + have_bytes, have=have_bytes,
                           peak=pictures_bytes + words_kept + max([v["raw"] for v in todo.values()] or [0]))
    answer.update(words=todo, pictures={"files": pictures_n, "bytes": pictures_bytes, "have": have_n},
                  total=total, resolution=resolution, mean=mean, replaces=bool(mine) and not same_size)
    return answer


def room(answer, folder_=None):
    """The sentence refusing to start for want of room, or "" -- NEVER START WHAT CANNOT FINISH."""
    need = answer.get("disk_peak")
    if not need:
        return ""
    free = disk_free(folder_ or ARASAAC_DIR)
    if free >= need:
        return ""
    return ("There is not enough room on this computer: the pictograms need about %s free while they are "
            "fetched, and %s %s free. Make room and press it again."
            % (download.size_text(need), download.size_text(free), "is" if free < 2e6 else "are"))


# ------------------------------------------------------------------- the job
# ONE JOB AT A TIME, on a thread of its own, reported to the page and to the activity list.
# The server's other downloads each have a table in serve.py; this one has no queue and no
# kinds, so the table is here, with the Event that stops it.
_LOCK = threading.RLock()
JOB = {}
_CANCEL = {"event": None}


def job():
    """The job as the page and the activity list show it: a copy, {} when there has been none
    since the server started."""
    with _LOCK:
        return dict(JOB)


def running():
    with _LOCK:
        return bool(JOB.get("running"))


def _note(**kw):
    with _LOCK:
        JOB.update(kw)


def start(locales, resolution=DEFAULT_RESOLUTION, update=False):
    """Begin fetching on a thread: -> (answer, HTTP status).  The answer carries the sentence
    when it was refused (a language that is not ARASAAC's, a disk with no room, a job already
    running -- that one is the same job, said so, not an error)."""
    try:
        locales = check_locales(locales)
        resolution = check_resolution(resolution)
    except ArasaacError as e:
        return {"ok": False, "error": e.say, "code": e.code}, 400
    if update:
        locales = tuple(locales_here()) or locales
        resolution = manifest().get("resolution") or resolution
    elif not locales and not facts():
        return {"ok": False, "error": "Choose at least one language: the pictures are found by their words.",
                "code": "no-language"}, 400
    for loc in locales:
        ok, why = offered(loc)
        if not ok:
            return {"ok": False, "error": why, "code": "not-offered"}, 400
    with _LOCK:
        if JOB.get("running"):
            return {"ok": True, "already": True}, 200
        try:
            answer = plan(locales, resolution, update=update)
        except ArasaacError as e:
            return {"ok": False, "error": e.say, "code": e.code}, 400
        refuse = room(answer)
        if refuse:
            return {"ok": False, "error": refuse, "plan": answer}, 507
        cancel = threading.Event()
        _CANCEL["event"] = cancel
        JOB.clear()
        JOB.update(running=True, say="starting…", error="", stopped=False, started=time.time(), finished=None,
                   phase="words", done=0, total=None, fetched=0, same=0, missing=0, update=bool(update),
                   locales=list(locales), resolution=resolution)
    threading.Thread(target=_work, args=(locales, resolution, update, cancel), daemon=True).start()
    return {"ok": True}, 200


def _work(locales, resolution, update, cancel):
    def say(text):
        _note(say=str(text).strip())

    def progress(done, total=None, phase="words"):
        # (lib/download.py calls a fetch's own phase "download": here it is the word lists)
        _note(done=done, total=total, phase="words" if phase == "download" else phase)
    try:
        build(locales, resolution, update=update, say=say, progress=progress, cancel=cancel)
        _note(say="done")
    except download.Cancelled:
        _note(stopped=True, say="stopped")
    except ArasaacError as e:
        _note(error=e.say)
    except (OSError, http.client.HTTPException) as e:
        # a line that dropped, a host that answered badly, a disk that filled: in the words
        # the code gave, which name what happened and not the exception's class
        _note(error=str(e) or "the connection or the disk failed")
    except Exception as e:                                   # noqa: BLE001 -- said, never a thread's traceback
        _note(error="%s: %s" % (type(e).__name__, e))
    finally:
        _note(finished=time.time(), running=False)
        _CANCEL["event"] = None


def stop():
    """Ask the running job to stop between two pictures; -> whether there was one.  What was
    fetched is kept, and the next press carries on from there."""
    with _LOCK:
        event = _CANCEL.get("event")
        if event is None or not JOB.get("running"):
            return False
        event.set()
        return True


def stop_all(wait=2.0):
    """For the server's own end: a job must not outlive it."""
    if stop():
        end = time.monotonic() + wait
        while running() and time.monotonic() < end:
            time.sleep(0.05)


def build(locales, resolution=DEFAULT_RESOLUTION, *, update=False, say=print, progress=None, cancel=None):
    """Fetch what is missing: the word list of each language not here (every one, for an
    update), then each picture whose record is not confirmed, then the manifest and the
    credit.  A stop leaves the pictograms.json and manifest.json of the moment, and
    nothing that is half written under its own name."""
    locales = check_locales(locales)
    resolution = check_resolution(resolution)
    os.makedirs(tmp_dir(), exist_ok=True)
    mine = manifest()
    records = dict(facts())
    started = mine.get("started") or time.strftime("%Y-%m-%d")
    resized = bool(mine) and mine.get("resolution") != resolution
    # A WHOLE INSTALL STAYS WHOLE UNTIL SOMETHING IN IT CHANGES: an update pressed with no line, or answered
    # with a list that is refused, has changed nothing, and must not turn "installed" into "part of it"
    whole = bool(mine.get("complete")) and not resized
    # A CHANGE OF SIZE REPLACES THE PICTURES: they sit under one name each, so they are all of
    # one size.  Taken away first, and the manifest says so at once, so that a stop in the
    # middle leaves a record that is true.
    if resized:
        say("the pictures are fetched again, at %d pixels" % resolution)
        shutil.rmtree(pictures_dir(), ignore_errors=True)
        for r in records.values():
            r["p"] = 1
            r.pop("x", None)
        _save_facts(records)
    here = locales_here()
    fetched = {loc: dict((mine.get("locales") or {}).get(loc) or {}) for loc in here}

    def write_manifest(complete):
        _write_json(manifest_path(), {
            "format": ARASAAC_FORMAT, "resolution": resolution, "complete": complete, "started": started,
            "finished": time.strftime("%Y-%m-%dT%H:%M:%S") if complete else None,
            "pictograms": len(records), "locales": fetched, "source": SOURCE, "licence": LICENCE,
            "terms": TERMS, "measured": MEASURED["date"]})

    if not whole:
        write_manifest(False)
    # ---- the word lists, one at a time: each is put in place whole before the next is asked for
    first = True
    for loc in locales:
        if loc in here and not update:
            continue
        download.check(cancel)
        _note_phase("words")
        got_words, got_facts, size = _fetch_words(loc, say, progress, cancel)
        # THE FACTS ARE WRITTEN BEFORE THE WORDS: a run killed between the two finds the list
        # missing and asks for it again, and never a list whose pictograms nobody knows
        records = _merge(records, got_facts, say, drop=first)
        if whole:
            write_manifest(False)
            whole = False
        _save_facts(records)
        today = time.strftime("%Y-%m-%d")
        _write_json(index_path(loc), {"format": ARASAAC_FORMAT, "locale": loc, "fetched": today,
                                      "words": {str(k): v for k, v in got_words.items()}})
        fetched[loc] = {"fetched": today, "words": sum(len(v) for v in got_words.values()),
                        "covered": len(got_words), "bytes": size}
        first = False
        say("%s: %d words for %d pictograms" % (loc, fetched[loc]["words"], fetched[loc]["covered"]))
    if not records:
        raise ArasaacError("no-language", "Choose at least one language: the pictures are found by their words.")
    write_manifest(False)
    # ---- the pictures
    todo = [pid for pid in sorted(records) if _wants(pid, records[pid])]
    total = len(records)
    # A DOWNLOAD COUNTS THE WHOLE SET (a run carried on after a stop goes on from where it was); AN UPDATE
    # COUNTS WHAT IT HAS TO FETCH, since "27 of 30" for three pictures is not a thing anybody can watch
    done0, bar = (0, len(todo)) if update else (total - len(todo), total)
    meter = download.Meter(progress, cancel, total=bar, phase="pictures")
    session = _Session(STATIC, {"User-Agent": UA, "Accept": "image/png"})
    flushed, last_flush = 0, time.monotonic()
    counts = {"new": 0, "same": 0, "none": 0}
    try:
        for i, pid in enumerate(todo):
            meter.at(done0 + i)
            outcome = _fetch_picture(session, pid, resolution, cancel)
            counts[outcome] += 1
            rec = records[pid]
            rec.pop("p", None)
            if outcome == "none":
                rec["x"] = 1
            else:
                rec.pop("x", None)
            _note(fetched=counts["new"], same=counts["same"], missing=counts["none"])
            flushed += 1
            now = time.monotonic()
            if flushed >= FLUSH_EVERY or now - last_flush >= FLUSH_SECONDS:
                _save_facts(records)
                flushed, last_flush = 0, now
            time.sleep(PAUSE)
    finally:
        # A STOP, AN ERROR OR THE END ALIKE: the records of the moment are written, so that what
        # the next press does is exactly what is left
        session.close()
        _save_facts(records)
        _unlink_parts()
    meter.end()
    # ---- the credit, and the record that it is whole
    write_manifest(True)
    write_licence(fetched, resolution)
    none = sum(1 for r in records.values() if r.get("x"))
    say("done: %s pictograms%s" % (format(total, ","), ", %d of them with no picture at %d pixels" % (none, resolution)
                                   if none else ""))
    return total


def _note_phase(phase):
    _note(phase=phase, done=0, total=None)


def _wants(pid, rec):
    """Is this picture still to be fetched?  A record marked `p` says so; one marked `x` says
    the host has none at this size and its record has not moved since; any other wants one
    only if the file is not there."""
    if rec.get("p"):
        return True
    if rec.get("x"):
        return False
    return not os.path.isfile(picture_path(pid))


def _merge(old, new, say, drop=True):
    """The records after a list has come: a new number, or a number whose `lastUpdated` has
    moved, is to be fetched (`p`); with `drop`, a number the list no longer has is let go,
    picture and all (only the first list of a run may say so).  Nothing else about a record
    that is here changes.  A list with far fewer pictograms than are here is a half answer,
    and is refused."""
    if old and len(new) < 0.9 * len(old):
        raise ArasaacError("bad-list", "ARASAAC's list of pictograms came with far fewer than are here "
                                       "(%d against %d). Nothing was changed." % (len(new), len(old)))
    out = dict(old) if not drop else {}
    added = changed = 0
    for pid, fact in new.items():
        was = old.get(pid)
        rec = dict(fact)
        if was is None:
            rec["p"] = 1
            added += 1
        elif was.get("u") != fact.get("u"):
            rec["p"] = 1
            changed += 1
        elif was.get("p"):
            rec["p"] = 1
        elif was.get("x"):
            rec["x"] = 1
        out[pid] = rec
    gone = [pid for pid in old if pid not in new] if drop else []
    for pid in gone:
        _unlink(picture_path(pid))
    if old and (added or changed or gone):
        say("%d new, %d changed, %d gone" % (added, changed, len(gone)))
    return out


def _unlink_parts():
    try:
        for name in os.listdir(pictures_dir()):
            if name.endswith(".part"):
                _unlink(os.path.join(pictures_dir(), name))
    except OSError:
        pass


def write_licence(fetched, resolution):
    """arasaac/LICENSE-ARASAAC.txt: the credit as the terms word it, the licence, where the
    terms are and what they ask, the date, and what is here -- for whoever opens the folder."""
    langs = ", ".join(sorted(fetched)) or "none"
    text = (
        "ARASAAC PICTOGRAMS -- the licence that goes with these files\n"
        "============================================================\n\n"
        "%s\n\n%s\n\n"
        "Licence:  %s -- %s\n"
        "Terms:    %s\n"
        "Fetched:  %s, from api.arasaac.org (the words) and static.arasaac.org (the pictures,\n"
        "          %d pixels), by Parseh, when a person asked it to under Settings.\n"
        "Words:    %s\n\n"
        "What the licence asks, in short (the terms and the licence are what count):\n"
        "  * Attribution: the author (Sergio Palao), the owner (the Government of Aragon), the\n"
        "    origin (ARASAAC) and the licence (CC BY-NC-SA) are to be named wherever the\n"
        "    pictograms are used -- with either of the two sentences above.\n"
        "  * NonCommercial: no use within any product or publication for commercial purposes.\n"
        "  * ShareAlike: anything made from the pictograms is distributed on the same licence.\n"
        "  * The ARASAAC logo goes on signs, posters and plates when the pictograms mark public\n"
        "    areas, services or shops (the terms' own words); a study document is none of those.\n"
        % (CREDIT, CREDIT_SHORT, LICENCE, LICENCE_URL, TERMS, time.strftime("%Y-%m-%d"), resolution, langs))
    os.makedirs(ARASAAC_DIR, exist_ok=True)
    with open(licence_path(), "w", encoding="utf-8") as f:
        f.write(text)


# ------------------------------------------------------------------ what is here
def status():
    """How things stand, read from the disk and the job: what the page draws and what a later
    piece of Parseh asks before it offers a picture.

        state      "absent", "partial" (a download that was stopped or is not finished),
                   "installed", "other" (made by a Parseh with another shape of file)
        resolution the size the pictures are at
        locales    {locale: {"fetched", "words", "covered"}} for each word list here
        pictograms how many are listed; files how many pictures are here and bytes what they weigh
        pending    how many are still to be confirmed
        job        the running (or last) job"""
    # THE JOB IS LOOKED AT FIRST, before a thing is read from the disk.  A job that ends while the folder is being
    # counted (a long look on a busy computer) used to be reported after it: the manifest read before its last write,
    # "partial", beside a job that was over -- and a page that stops asking when the job is over stayed on "Part of it
    # is here" for good.  Looked at first, a job reported as over has finished all it wrote before it is read from;
    # one reported as running is asked about again.
    taken = job()
    mine = manifest()
    odd = os.path.isfile(manifest_path()) and not mine
    n, size = pictures_here()
    known = facts()
    pending = sum(1 for r in known.values() if r.get("p"))
    here = {loc: dict((mine.get("locales") or {}).get(loc) or {}) for loc in locales_here()}
    for loc in here:
        here[loc].setdefault("fetched", "")
    if odd:
        state = "other"
    elif not mine and not here and not n:
        state = "absent"
    elif mine.get("complete") and not pending and known:
        state = "installed"
    else:
        state = "partial"
    words_bytes = 0
    for loc in here:
        try:
            words_bytes += os.path.getsize(index_path(loc))
        except OSError:
            pass
    return {"state": state, "resolution": mine.get("resolution"), "locales": here,
            "pictograms": len(known), "files": n, "bytes": size + words_bytes, "pending": pending,
            "missing": sum(1 for r in known.values() if r.get("x")), "finished": mine.get("finished"),
            "job": taken}


def installed():
    """Are the pictograms here, whole, and readable by this Parseh?  What a prompt asks before it
    says a symbol exists."""
    return status()["state"] == "installed" and BASE_LOCALE in locales_here()


def remove(locale=None):
    """Take one language's word list away (the pictures stay), or the whole folder.  ArasaacError
    while a job is running: deleting a file being written is a half-built one that reports
    itself as whole."""
    if running():
        raise ArasaacError("busy", "The pictograms are being fetched right now: stop that first.")
    if locale is not None:
        path = index_path(locale)
        _unlink(path)
        mine = manifest()
        if mine and isinstance(mine.get("locales"), dict) and locale in mine["locales"]:
            del mine["locales"][locale]
            _write_json(manifest_path(), mine)
        return
    shutil.rmtree(ARASAAC_DIR, ignore_errors=True)
    _FACTS.clear()
    with _LOCK:
        JOB.clear()


def activity_entries(entry, keep, now=None):
    """The job as the activity list has it (lib/activity.py entry()), so that every page's Working
    pill knows the pictograms are being fetched.  Kind `lookup`, like the reading help's downloads."""
    now = time.time() if now is None else now
    j = job()
    if not j.get("started"):
        return []
    over = not j.get("running")
    if over and now - (j.get("finished") or now) > keep:
        return []
    return [entry("arasaac:get@%.3f" % j["started"], "lookup",
                  "Updating the ARASAAC pictograms" if j.get("update") else "Getting the ARASAAC pictograms",
                  j["started"], done=j.get("done") if not over else None, total=j.get("total") if not over else None,
                  stage=None if over else j.get("say") or None, page=SETTINGS_PAGE,
                  finished=j.get("finished") if over else None,
                  ok=not j.get("error") and not j.get("stopped"))]


# --------------------------------------------------------------------- a command
def main(argv=None):
    ap = argparse.ArgumentParser(description="The ARASAAC pictograms (a developer's way in; Settings is a person's).")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    g = sub.add_parser("get")
    g.add_argument("locales", nargs="*", default=[BASE_LOCALE])
    g.add_argument("--500", dest="large", action="store_true", help="the 500 pixel pictures")
    sub.add_parser("update")
    r = sub.add_parser("remove")
    r.add_argument("locale", nargs="?")
    args = ap.parse_args(argv)
    if args.cmd in (None, "status"):
        print(json.dumps(status(), indent=1, ensure_ascii=False))
        return 0
    try:
        if args.cmd == "remove":
            remove(args.locale)
            return 0
        counted = {"at": 0.0}

        def progress(done, total, phase):
            # THE COUNT IS PROGRESS, NOT A SENTENCE: the page draws it as a bar, a command line prints it
            if phase == "pictures" and time.monotonic() - counted["at"] >= 3.0:
                counted["at"] = time.monotonic()
                print("    %s of %s pictures" % (format(done, ","), format(total, ",")))
        if args.cmd == "update":
            build(locales_here() or (BASE_LOCALE,), manifest().get("resolution") or DEFAULT_RESOLUTION,
                  update=True, say=print, progress=progress)
        else:
            build(args.locales, 500 if args.large else DEFAULT_RESOLUTION, say=print, progress=progress)
    except download.Cancelled:
        print("stopped")
        return 1
    except ArasaacError as e:
        print(e.say)
        return 1
    except (OSError, http.client.HTTPException) as e:
        print(str(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
