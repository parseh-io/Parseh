#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Whether a language's words can be cut by machine here, and by what.

    segmenter.available("ja")   True when SudachiPy and its dictionary import
    segmenter.about("zh")       {"analyzer", "packages", "have", "python", "models"}
    segmenter.models("zh")      [{"name", "what", "size_mb", "path", "have"}]

Standard library only.  serve.py imports this at startup, and the server may
be running a Python that has none of the analyzers -- serve.sh falls back to
the machine's python3 when the ilya-frank environment is missing -- so this
answers without importing any of them; lib/words.py imports them, and only
when asked to cut.  Every answer names sys.executable, because "not
installed" means "not installed in the Python that is running".
"""
import importlib
import importlib.util
import os
import sys

BACKENDS = {
    "ja": {"analyzer": "SudachiPy", "modules": ("sudachipy", "sudachidict_core"),
           "packages": "sudachipy SudachiDict-core"},
    "zh": {"analyzer": "spacy-pkuseg and pypinyin", "modules": ("spacy_pkuseg", "pypinyin"),
           "packages": "spacy-pkuseg pypinyin"},
}

# THE MODELS AN ANALYZER DOWNLOADS FOR ITSELF the first time one is asked for,
# and where it keeps them: spacy_pkuseg fetches its word model and its
# part-of-speech model into $PKUSEG_HOME (~/.pkuseg).  They are looked for
# here, file by file, so that lib/words.py can ask before it uses one -- a
# request of the server must never be what fetches forty megabytes -- and so
# that an installer or a setup page can say what is missing without
# importing anything.  SudachiPy downloads nothing: its dictionary is a pip
# package of its own.
MODELS = {
    "zh": (
        {"name": "spacy_ontonotes", "what": "the word model", "size_mb": 35,
         "files": ("features.msgpack", "weights.npz")},
        {"name": "postag", "what": "the part-of-speech model", "size_mb": 41,
         "files": ("features.pkl", "weights.npz")},
    ),
}


def pkuseg_home():
    return os.path.expanduser(os.environ.get("PKUSEG_HOME") or "~/.pkuseg")


def models(code):
    """[{name, what, size_mb, path, have}] for the models `code`'s analyzer
    downloads for itself, and [] for an analyzer that downloads nothing."""
    home = pkuseg_home()
    out = []
    for m in MODELS.get(code, ()):
        d = os.path.join(home, m["name"])
        # spacy_pkuseg downloads whenever the zip is missing and unpacks it
        # beside itself: both must be there, or asking for the model fetches
        # it again
        have = (os.path.isfile(os.path.join(home, m["name"] + ".zip"))
                and all(os.path.isfile(os.path.join(d, f)) for f in m["files"]))
        out.append({"name": m["name"], "what": m["what"], "size_mb": m["size_mb"],
                    "path": d, "have": have})
    return out


def model_ready(code, name):
    return any(m["name"] == name and m["have"] for m in models(code))


def available(code):
    """Can this Python cut `code` into words?"""
    b = BACKENDS.get(code)
    if not b:
        return False
    # find_spec remembers a miss; a package installed after startup must be
    # seen, which is the bug lib/lookup.py's connection cache once had
    importlib.invalidate_caches()
    try:
        return all(importlib.util.find_spec(m) is not None for m in b["modules"])
    except (ImportError, ValueError):
        return False


def why_not(code, name=None):
    """Why a page offers no "propose" for this language's word line, and where the analyzers come from, in a
    sentence for the page -> str, or "" when this Python has them (or the language divides into no words).

    NO COMMAND IN IT: a person on Windows reads it, and the analyzers are part of Parseh's own environment
    (lib/runtime.py PACKAGES), which the installers and the Windows start-up wizard complete."""
    b = BACKENDS.get(code)
    if not b or available(code):
        return ""
    n = name or "Parseh"
    if code == "ja":
        said = "SudachiPy, which divides Japanese into words and reads them in kana, is"
        it = "It is part of %s's own environment: %s's installer puts it there" % (n, n)
    else:
        said = "%s, which divide Chinese into words and read them in pinyin, are" % b["analyzer"]
        it = "They are part of %s's own environment: %s's installer puts them there" % (n, n)
    return ("No \u201cpropose\u201d here: %s not installed in the Python %s is running with (%s). %s, and on "
            "Windows starting %s offers to add what the environment lacks. Until then a chunk's words are "
            "divided by hand, and everything else works without them." % (said, n, sys.executable, it, n))


def about(code):
    b = BACKENDS.get(code)
    if not b:
        return {}
    return {"analyzer": b["analyzer"], "packages": b["packages"],
            "have": available(code), "python": sys.executable,
            "models": models(code)}
