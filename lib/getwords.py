# SPDX-License-Identifier: GPL-3.0-or-later
"""The models a word analyzer downloads for itself, fetched from Settings >
Reading help (TO-DO §5.10, a0.6.3) -- lib/download.py's interface (plan,
build), so serve.py runs it as one more kind of reading download, with its
bar, its Stop and its place on the activity list.

Chinese is cut into words by spacy-pkuseg, which fetches its word model and
its part-of-speech model (some 75 MB, lib/segmenter.py MODELS) the first time
one is asked for.  A request of the server must never be what waits for them,
so they are fetched ahead: by the installers (runtime.fetch_models) and, for
a computer whose models are missing, by this -- the page's *Get it*, where
there used to be `python3 lib/words.py --fetch zh` to type.  SudachiPy
(Japanese) downloads nothing: its dictionary is a package of its own.
"""
import segmenter


def languages():
    """The languages whose analyzer downloads models of its own."""
    return sorted(segmenter.MODELS)


def _size(code):
    return sum(m["size_mb"] for m in segmenter.models(code)) * 1_000_000


def plan(code, *, probe=True):
    """What getting `code`'s models costs: the sizes segmenter.MODELS gives,
    measured, kept as they come."""
    import download
    lacking = [m for m in segmenter.models(code) if not m["have"]]
    whole = _size(code)
    rest = sum(m["size_mb"] for m in lacking) * 1_000_000
    return download.plan(whole, measured=True, kept=whole, have=whole - rest,
                         peak=rest * 2)


def build(code, say=print, progress=None, cancel=None):
    """Fetch what `code`'s analyzer lacks.  The analyzer fetches for itself
    and says nothing of bytes, so the bar is the models done of the models
    wanted; a Stop asked for is honoured before it starts."""
    import download
    import words
    if code not in segmenter.MODELS:
        raise SystemExit("there are no word models to fetch for this language")
    if not segmenter.available(code):
        raise SystemExit("the word analyzer for this language (%s) is not installed: "
                         "Settings > Updating Parseh adds it"
                         % segmenter.about(code).get("packages", ""))
    if cancel is not None and cancel.is_set():
        raise download.Cancelled()
    total = _size(code)
    if progress:
        progress(total - sum(m["size_mb"] for m in segmenter.models(code) if not m["have"]) * 1_000_000,
                 total, "download")
    lines = []
    ok = words.fetch_models(code, say=lambda m: (lines.append(str(m)), say(m)))
    if not ok:
        raise SystemExit(lines[-1] if lines else "the models could not be fetched")
    if progress:
        progress(total, total, "download")
