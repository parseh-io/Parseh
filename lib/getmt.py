#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fetch a translation model that runs in the reader's own browser.

    python3 lib/getmt.py                 what is installed
    python3 lib/getmt.py fa en           Persian to English
    python3 lib/getmt.py --engine        just the engine, without a model

WHAT THIS IS, AND WHAT IT IS NOT.  It is a TRANSLATION model: one job, no
prompt, no endpoint, no key, no conversation, and the same answer every time
for the same sentence.  It is not a chat model and there is no server to talk
to -- the engine is WebAssembly and it runs inside the page, so a chunk being
translated never leaves the machine, and the toolbox gains no Python
dependency at all.

THE ENGINE is bergamot-translator, the same one Firefox's own translations
feature uses, under the MPL 2.0.  THE MODELS are Mozilla's, distributed
through the service Firefox itself fetches them from, and they are tiny:
around 20 MB for a language pair, against gigabytes for a general model.

NOTHING IS COMMITTED.  Engine and models are downloaded into `mt/`, which is
gitignored for the reason `dict/` is: somebody else's work, under somebody
else's licence, and megabytes of it.  A pair with no model installed is read
exactly as it is read today -- the button simply is not offered.

ONLY TO AND FROM ENGLISH.  Mozilla trains its pairs against English and not
against each other, so a book in Persian glossed in English has a model and
the same book glossed in Italian has none -- there is no fa-it model to
fetch, and `trainable()` below is what the page asks before it offers the
choice.

AND NOT ALWAYS UNDER THE CODE THE REGISTRY USES.  The service names Chinese
by its script -- `zh-Hans` for the simplified characters Parseh's `zh`
teaches, `zh-Hant` for the traditional ones -- so the code is translated on
the way out.  That is a fact about the service's spelling and not about the
language, which is why it lives here and not in the registry.
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import languages                                              # noqa: E402
import version                                                # noqa: E402  who is asking: UA
import project        # noqa: E402  where Parseh lives, for the line a download introduces itself with: UA
import download       # noqa: E402  resumable, stoppable, and says how far

MT_DIR = os.path.join(ROOT, "mt")
ENGINE_DIR = os.path.join(MT_DIR, "engine")

# The engine, pinned.  An unpinned dependency that reaches over the network is
# a dependency that changes under a reader without anybody deciding to change
# it, so the version is written here and moved by hand.
ENGINE_VERSION = "0.4.9"
ENGINE_BASE = ("https://cdn.jsdelivr.net/npm/@browsermt/bergamot-translator@%s/worker"
               % ENGINE_VERSION)
ENGINE_FILES = ("translator-worker.js", "bergamot-translator-worker.js",
                "bergamot-translator-worker.wasm")
ENGINE_LICENCE = "MPL 2.0"
ENGINE_SOURCE = "bergamot-translator %s (%s)" % (ENGINE_VERSION, ENGINE_LICENCE)

# ...AND ITS BYTES PINNED WITH IT: (SHA-256, size) of each file of
# ENGINE_VERSION, and a download that does not match is refused and deleted
# (download.Mismatch).  The engine is code -- it runs in every reader that
# translates -- and the version number alone trusted a CDN to hand over the
# same bytes for it forever.  With the digests written here, what may run is
# fixed by the Parseh release the person installed, so fetching it from a page
# adds nothing they did not already choose (the owner, 2026-09-24).  Taken
# from the pinned files downloaded on 2026-09-25, and the same as the engine
# installed on 2026-09-24.  Moving ENGINE_VERSION means moving these with it:
# a new version with the old digests is refused, which is the point.
ENGINE_SHA256 = {
    "translator-worker.js": (
        "90257af9ee0758983501bdce77ca7ec168cd7360d4689298c20a81b0251d6b62",
        17191),
    "bergamot-translator-worker.js": (
        "748b2418418a2ffc6e70721aeb10098d8e6fb589ea156b91f4ae8bc3490d8f7a",
        80474),
    "bergamot-translator-worker.wasm": (
        "95a2b58dd6773bf1b3f345d71f9149928b9f75f4ec9c9064c0b3e42c298671b2",
        5174294),
}

# Where Firefox itself gets its models.  The records carry the pair, the file
# type, a version and an attachment; the attachment's `location` hangs off the
# CDN below.
RECORDS = ("https://firefox.settings.services.mozilla.com/v1/buckets/main"
           "/collections/translations-models/records")
ATTACH = "https://firefox-settings-attachments.cdn.mozilla.net/"
MODEL_SOURCE = "Mozilla Firefox Translations models"
MODEL_LICENCE = "CC BY-SA 4.0"

# WHAT A MODEL COSTS, MEASURED: the pair's files, in bytes, as installed on
# 2026-09-24 (Persian, Italian, Japanese, Turkish to English; English to
# Italian) and as html-guide's translation-model page gives them for Spanish
# and Chinese to English.  A model is not built, so what is downloaded is what
# is kept.  Read by plan(), so the page can say how big before anybody presses
# a button; a pair not here is asked -- the service's own list says each
# file's size, so plan() reads it rather than guessing.  Mozilla publishes new
# versions of a pair now and then, so these are "about".
MEASURED = {
    ("fa", "en"): 21_900_000,
    ("it", "en"): 37_100_000,
    ("ja", "en"): 54_800_000,
    ("tr", "en"): 22_600_000,
    ("en", "it"): 36_500_000,
    ("es", "en"): 37_000_000,
    ("zh", "en"): 55_000_000,
}

# What a pair needs.  `lex` is the shortlist, `vocab` the sentencepiece
# vocabulary; a few pairs split the vocabulary in two and name the halves
# separately, which is why both spellings are looked for.
WANT = ("model", "lex", "vocab", "srcvocab", "trgvocab")
UA = project.agent(version.VERSION)


def _get(url, dest, say=print, progress=None, cancel=None, sha256=None,
         size=None):
    """One file, through lib/download.py: resumed if a try before was cut
    short, refused if `sha256` is given and the bytes do not have it."""
    say("    %s" % os.path.basename(dest))
    try:
        download.fetch(url, dest, say=say, progress=progress, cancel=cancel,
                       sha256=sha256, size=size, headers={"User-Agent": UA},
                       timeout=180)
    except download.Mismatch as e:
        raise SystemExit("getmt: %s" % e)
    except urllib.error.HTTPError as e:
        raise SystemExit("getmt: could not download %s (%s)" % (url, e))
    except OSError as e:
        raise SystemExit("getmt: could not download (%s).  What came is "
                         "kept: the next try carries on from there." % e)


def engine_ready():
    return all(os.path.isfile(os.path.join(ENGINE_DIR, f)) for f in ENGINE_FILES)


def engine_matches():
    """Are the engine's files here, and the very ones ENGINE_SHA256 pins?
    Reads five megabytes, so it is for the Settings page's status, not for
    every request (engine_ready is that)."""
    for f in ENGINE_FILES:
        p = os.path.join(ENGINE_DIR, f)
        try:
            if download.digest(p) != ENGINE_SHA256[f][0]:
                return False
        except OSError:
            return False
    return True


def _engine_wanted():
    """(url, file, sha256, size) of each engine file."""
    return [("%s/%s" % (ENGINE_BASE, f), f) + ENGINE_SHA256[f]
            for f in ENGINE_FILES]


def _fetch_all(files, say, progress, cancel):
    """Several files as ONE bar: [(url, dest, sha256, size)], sizes known
    beforehand (the engine's are pinned, a model's come with its record).
    A file already here whole and matching its digest is not fetched
    again -- which is how a model interrupted after its first two files
    carries on at its third."""
    whole = sum(f[3] for f in files) if all(f[3] for f in files) else None
    before = 0
    for url, dest, sha, size in files:
        if (os.path.isfile(dest) and sha
                and download.digest(dest) == sha.lower()):
            say("    already here: %s" % os.path.basename(dest))
        else:
            _get(url, dest, say, progress=download.shifted(progress, before,
                                                           whole),
                 cancel=cancel, sha256=sha, size=size)
        before += size or 0


def get_engine(say=print, force=False, progress=None, cancel=None):
    """The WebAssembly engine, once, shared by every pair -- each file
    checked against ENGINE_SHA256 before it is put in place.

    `force` fetches every file that is not already the pinned one; a file
    that is would come back byte for byte the same, so it stays, and the
    engine a reader is using is never taken away while its replacement is
    on its way."""
    if engine_ready() and not force:
        return False
    os.makedirs(ENGINE_DIR, exist_ok=True)
    say("  the engine, %s" % ENGINE_SOURCE)
    _fetch_all([(url, os.path.join(ENGINE_DIR, f), sha, size)
                for url, f, sha, size in _engine_wanted()],
               say, progress, cancel)
    _engine_meta()
    return True


def _engine_meta():
    with io.open(os.path.join(ENGINE_DIR, "meta.json"), "w",
                 encoding="utf-8") as f:
        f.write(json.dumps({"source": ENGINE_SOURCE, "version": ENGINE_VERSION,
                            "built": time.strftime("%Y-%m-%d")}, indent=1))


# What the service calls a language, where that is not what the registry
# calls it.  Simplified characters are what `zh` teaches (lib/lang/zh.chunk.json
# and docs/lang/zh.md say so), so `zh-Hans` is the pair to fetch.
_SERVICE = {"zh": "zh-Hans"}


def service_code(code):
    """The name the model service knows this language by."""
    return _SERVICE.get(code, code)


# THE PAIRS THE SERVICE REALLY HAS (TO-DO §5.9, §11.2), remembered from the
# last time its list was read -- a plan's size probe, a download, `--pairs` --
# so the Reading help page can offer only those, without a request of its
# own.  Until the list has been read once, the rule below stands in for it.
# A list too short to be the service's (a test's two records) is not kept.
PAIRS_FILE = "pairs.json"
PAIRS_FLOOR = 10


def _pairs_path():
    return os.path.join(MT_DIR, PAIRS_FILE)


def _remember_pairs(recs):
    got = sorted({(r.get("fromLang"), r.get("toLang")) for r in recs
                  if isinstance(r, dict) and r.get("fromLang") and r.get("toLang")})
    if len(got) < PAIRS_FLOOR:
        return
    try:
        os.makedirs(MT_DIR, exist_ok=True)
        tmp = _pairs_path() + ".part"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump({"read": time.strftime("%Y-%m-%d"), "pairs": [list(p) for p in got]}, f)
        os.replace(tmp, _pairs_path())
    except OSError:
        pass                              # remembered next time; the rule stands in


def offered():
    """{(from, to)} in the service's own codes, as its list last said -- or
    None when it has never been read on this computer."""
    try:
        with io.open(_pairs_path(), encoding="utf-8") as f:
            pairs = json.load(f).get("pairs") or []
        return {tuple(p) for p in pairs if isinstance(p, list) and len(p) == 2} or None
    except (OSError, ValueError, AttributeError):
        return None


def trainable(a, b):
    """Could a model for this pair exist at all?

    Mozilla trains every pair against English rather than against each other,
    so `fa-en` and `en-it` exist and `fa-it` does not, and no amount of
    asking will produce one -- and not every language has both directions.
    Where the service's list has been read (offered()), it is the answer;
    before that, the rule.  The Reading help page asks this before it offers a
    gloss, because a choice that can only fail is worse than no choice.
    """
    if a == b:
        return False
    known = offered()
    if known:
        return (service_code(a), service_code(b)) in known
    return "en" in (a, b)


def path_for(a, b):
    return os.path.join(MT_DIR, "%s-%s" % (a, b))


def available(a, b):
    """A pair is usable when the engine and its three files are all here."""
    d = path_for(a, b)
    if not engine_ready() or not os.path.isdir(d):
        return False
    have = set(os.listdir(d))
    return "meta.json" in have and any(n.startswith("model.") for n in have)


def about(a, b):
    try:
        return json.load(io.open(os.path.join(path_for(a, b), "meta.json"),
                                 encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _records(say=print):
    req = urllib.request.Request(RECORDS, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            recs = json.loads(r.read().decode("utf-8")).get("data") or []
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise SystemExit("getmt: could not read the model list (%s)" % e)
    _remember_pairs(recs)
    return recs


def _stable(version):
    """A version with no letters in it is a release; `1.0a1` is not.

    Sorting on the string alone would prefer `1.0a1` over `1.0`, which is the
    alpha of the very thing it beats.
    """
    return not any(ch.isalpha() for ch in (version or ""))


def _pick(recs, a, b):
    """The newest stable record of each file type this pair needs."""
    best = {}
    for r in recs:
        if r.get("fromLang") != a or r.get("toLang") != b:
            continue
        kind = r.get("fileType")
        if kind not in WANT:
            continue
        att = r.get("attachment") or {}
        if not att.get("location"):
            continue
        key = (_stable(r.get("version")), r.get("version") or "")
        if kind not in best or key > best[kind][0]:
            best[kind] = (key, r)
    return {k: v[1] for k, v in best.items()}


def pairs(say=print):
    """Every pair the service has, as (from, to)."""
    got = set()
    for r in _records(say):
        a, b = r.get("fromLang"), r.get("toLang")
        if a and b:
            got.add((a, b))
    return sorted(got)


def _model_files(A, B, recs):
    """(url, file name, sha256, size) of each file of this pair's newest
    stable model, from the service's records -- or a refusal naming why
    there is none."""
    want = _pick(recs, service_code(A.code), service_code(B.code))
    if "model" not in want:
        raise SystemExit(
            "getmt: there is no %s-to-%s model.\n"
            "  Mozilla trains its pairs against English rather than against\n"
            "  each other, so %s-en and en-%s may exist where %s-%s does not,\n"
            "  and not every language has both."
            % (A.code, B.code, A.code, B.code, A.code, B.code))
    out = []
    for kind, r in sorted(want.items()):
        att = r["attachment"]
        out.append((kind, ATTACH + att["location"],
                    att.get("filename") or "%s.bin" % kind,
                    att.get("hash") or None, att.get("size") or None,
                    r.get("version") or ""))
    return out


def _tidy(part, names):
    """Everything in a pair's .part folder that is not one of `names`, or
    an interrupted download of one, goes: an older version's file, the
    meta.json of a try that stopped at the last step."""
    keep = set()
    for n in names:
        keep.update((n, n + ".part", n + ".part.json"))
    for n in os.listdir(part):
        if n not in keep:
            try:
                os.unlink(os.path.join(part, n))
            except OSError:
                pass


def build(a, b, say=print, progress=None, cancel=None):
    """Download the engine if it is missing, then this pair's model.

    ONE BAR FOR ALL OF IT: the service's records give each model file's
    size (and its SHA-256, which every file is checked against), and the
    engine's are pinned, so the whole download is known before its first
    byte.  `progress(done, total, "download")`; `cancel` is
    download.Cancelled.  WHAT CAME IS KEPT for the next try, in
    mt/<a>-<b>.part/: a whole file is not fetched again and a cut one is
    resumed (discard() throws it away).  Nothing reads that folder; the
    pair appears, as before, only when its last file is in and its
    meta.json written, by one rename.
    """
    A = languages.get_or_default(a)
    B = languages.get_or_default(b)
    if A.code == B.code:
        raise SystemExit("getmt: a language translated into itself is a copy")
    say("  %s to %s, from %s" % (A.name, B.name, MODEL_SOURCE))
    files = _model_files(A, B, _records(say))
    d = path_for(A.code, B.code)
    part = d + ".part"
    os.makedirs(part, exist_ok=True)
    _tidy(part, [name for _k, _u, name, _h, _s, _v in files])
    engine = []
    if not engine_ready():
        say("  the engine, %s" % ENGINE_SOURCE)
        os.makedirs(ENGINE_DIR, exist_ok=True)
        engine = [(url, os.path.join(ENGINE_DIR, f), sha, size)
                  for url, f, sha, size in _engine_wanted()]
    _fetch_all(engine + [(url, os.path.join(part, name), sha, size)
                         for _k, url, name, sha, size, _v in files],
               say, progress, cancel)
    if engine:
        _engine_meta()
    names = {kind: name for kind, _u, name, _h, _s, _v in files}
    meta = {"from": A.code, "to": B.code, "files": names,
            "version": next(v for kind, _u, _n, _h, _s, v in files
                            if kind == "model"),
            "source": MODEL_SOURCE, "licence": MODEL_LICENCE,
            "engine": ENGINE_SOURCE,
            "built": time.strftime("%Y-%m-%d")}
    # closed before the rename: Windows will not move a folder holding an
    # open file
    with io.open(os.path.join(part, "meta.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(meta, indent=1))
    # beside the old one and moved over it, for the reason getdict.py does
    if os.path.isdir(d):
        for n in os.listdir(d):
            os.unlink(os.path.join(d, n))
        os.rmdir(d)
    os.replace(part, d)
    size = sum(os.path.getsize(os.path.join(d, n)) for n in os.listdir(d))
    say("  %s-%s: %.1f MB" % (A.code, B.code, size / 1e6))
    return size


def _part_bytes(part):
    try:
        return sum(os.path.getsize(os.path.join(part, n))
                   for n in os.listdir(part) if not n.endswith(".part.json"))
    except OSError:
        return 0


def plan(a, b, *, probe=True):
    """What getting this pair will cost, before anything is fetched:
    lib/download.py's plan() shape, for the same arguments as build().

    A model is downloaded and kept as it comes, so the download, the peak
    and what is kept are one number -- plus the engine's five megabytes
    when it is not here yet, whose size is pinned.  A pair MEASURED is not
    asked about; any other is read from the service's list (one small
    request) unless `probe` is False."""
    A = languages.get_or_default(a)
    B = languages.get_or_default(b)
    engine = 0 if engine_ready() else sum(sz for _s, sz in ENGINE_SHA256.values())
    have = _part_bytes(path_for(A.code, B.code) + ".part")
    if engine:
        have += sum(download.leftover(os.path.join(ENGINE_DIR, f))
                    for f in ENGINE_FILES)
    model = MEASURED.get((A.code, B.code))
    measured = model is not None
    if model is None and probe:
        try:
            files = _model_files(A, B, _records(lambda _m: None))
            if all(f[4] for f in files):
                model = sum(f[4] for f in files)
        except SystemExit:
            model = None                  # no such pair, or the list is out of reach
    dl = None if model is None else model + engine
    return download.plan(dl, measured=measured, kept=dl, have=have,
                         peak=None if dl is None else max(dl - have, 0))


def discard(a, b):
    """Throw away an interrupted download of this pair (its .part folder).
    Returns the bytes freed.  The installed pair, if any, is untouched."""
    part = path_for(a, b) + ".part"
    freed = _part_bytes(part)
    if os.path.isdir(part):
        for n in os.listdir(part):
            os.unlink(os.path.join(part, n))
        os.rmdir(part)
    return freed


def installed():
    """Every pair on this machine, as (from, to)."""
    out = []
    try:
        names = sorted(os.listdir(MT_DIR))
    except OSError:
        return out
    for n in names:
        if n == "engine" or "-" not in n:
            continue
        a, _, b = n.partition("-")
        if a in languages.LANGS and b in languages.LANGS and available(a, b):
            out.append((a, b))
    return out


def status(say=print):
    say("Translation models, in %s/" % os.path.relpath(MT_DIR, ROOT))
    say("")
    say("  engine: %s" % ("installed" if engine_ready() else "not here yet"))
    have = installed()
    if not have:
        say("  no pair installed")
    for a, b in have:
        m = about(a, b)
        size = sum(os.path.getsize(os.path.join(path_for(a, b), n))
                   for n in os.listdir(path_for(a, b)))
        say("  %s -> %s   %.1f MB  %s  built %s"
            % (a, b, size / 1e6, m.get("source", ""), m.get("built", "?")))
    say("")
    say("  build one:  python3 lib/getmt.py <from> <to>")


def main():
    p = argparse.ArgumentParser(prog="getmt", description=__doc__.splitlines()[0])
    p.add_argument("src", nargs="?", help="the language to translate FROM")
    p.add_argument("dst", nargs="?", default="en", help="and INTO (default en)")
    p.add_argument("--engine", action="store_true", help="just the engine")
    p.add_argument("--pairs", action="store_true", help="every pair on offer")
    a = p.parse_args()
    if a.engine:
        if get_engine():
            print("  the engine is here")
        else:
            print("  the engine was already here")
        return 0
    if a.pairs:
        got = pairs()
        print("%d pairs on offer:" % len(got))
        mine = {L.code for L in languages.LANGS.values()}
        for x, y in got:
            if x in mine or y in mine:
                print("  %s -> %s" % (x, y))
        return 0
    if not a.src:
        status()
        return 0
    if a.src not in languages.LANGS or a.dst not in languages.LANGS:
        raise SystemExit("getmt: %r or %r is not a language in the registry"
                         % (a.src, a.dst))
    build(a.src, a.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
