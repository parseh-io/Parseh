# SPDX-License-Identifier: GPL-3.0-or-later
"""Where the optional analyzers are used: config/analysis.json.

    analysisconfig.choice("lookup")           "off", "show" or "assist"
    analysisconfig.save({"chunking": "assist"})

Three choices and three only, one for each thing that can use an analysis, each
off until somebody changes it.  Installing an analyzer is not consent to change
a result; this file is.  A choice for a thing that cannot run falls back to what
Parseh did before, at the place that asks (analyzer.Result.outcome).
"""
import json
import os
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "config", "analysis.json")
STORE_FORMAT = 1
CHOICES = {
    "lookup": ("off", "show", "assist"),       # show: a line beside the word; assist: it may also find the word
    "chunking": ("off", "assist"),             # new text only
    "evidence": ("off", "on"),                 # the gloss prompts
}
LOCK = threading.RLock()


def load():
    out = {k: v[0] for k, v in CHOICES.items()}
    try:
        with open(STORE, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return out
    if isinstance(doc, dict) and doc.get("format") == STORE_FORMAT:
        for k, allowed in CHOICES.items():
            if doc.get(k) in allowed:
                out[k] = doc[k]
    return out


def choice(what):
    return load()[what]


def save(changes):
    """Write these choices -> the whole set.  ValueError names what it refused."""
    if not isinstance(changes, dict):
        raise ValueError("Say what to change.")
    for k, v in changes.items():
        if k not in CHOICES or v not in CHOICES[k]:
            raise ValueError("No such choice: %s" % str(k)[:30])
    with LOCK:
        doc = dict(load(), **changes)
        os.makedirs(os.path.dirname(STORE), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(STORE), prefix=".analysis-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dict(doc, format=STORE_FORMAT), f, indent=1)
        os.replace(tmp, STORE)
    return doc
