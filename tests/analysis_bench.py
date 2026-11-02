# SPDX-License-Identifier: GPL-3.0-or-later
"""How often the dictionary's panel puts the right word first, with each combination of what a0.6.0 has: for a person
to read, and to choose the combination by.  Reads a folder of analyzers and a folder of dictionaries, writes nothing.

    python3 tests/analysis_bench.py <analysis folder> <dict folder> [fa-spoken|fa-formal|fa-holdout|tr|tr-holdout] [--misses]

The sentences and what each word should be read as were written and judged by hand, in tests/fixtures/analysis_bench/:
they are one person's judgement of a small sample, and a difference of a word or two means nothing.  The *-holdout files were
written after the rules were tuned on the others, and are the ones whose numbers say anything about a new sentence.  first = the right
headword is the panel's first hit, top3 = among the first three, found = anywhere; chip = of the words whose right
headword is on the panel and that carry a part of speech, how many name that headword's; mark = the same of the
"fits this sentence" marker, wrong = it marks only other headwords.
"""
import os
import re
import sys
import unicodedata
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import analyzer        # noqa: E402
import getanalysis     # noqa: E402
import lookup          # noqa: E402
import lookupassist    # noqa: E402
import spoken          # noqa: E402

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "analysis_bench")
_MARKS = re.compile("[ً-ْٰـ]")


def _plain(s):
    return _MARKS.sub("", unicodedata.normalize("NFC", s)).replace("‌", "").replace(" ", "").casefold()


def load(name):
    rows, sentence = [], None
    with open(os.path.join(HERE, name + ".txt"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if sentence is None:
                sentence = line
            else:
                rows.append((sentence, {w: set(map(_plain, t.split("|"))) for w, t in (p.split("=", 1) for p in line.split())}))
                sentence = None
    return rows


def _keys(hit):
    said = hit.get("spoken") or {}
    return {_plain(k) for k in [hit.get("headword") or "", said.get("as") or ""] +
            [r.get("as") or "" for r in said.get("readings") or []] + list(said.get("parts") or []) if k}


def _clean(word):
    return word.strip(".,!?؟،؛:…»«)(\"'")


def score(code, rows, register, mode, misses=None):
    n = dict(words=0, first=0, top3=0, found=0, chip=0, chip_ok=0, mark=0, mark_ok=0)
    for sentence, gold in rows:
        got = lookup.look_up(code, sentence, register=register)
        if mode:
            lookupassist.apply(code, got, sentence, sentence, mode, register)
        for row in got.get("words") or []:
            want = gold.get(_clean(row.get("word") or ""))
            if want is None:
                continue
            n["words"] += 1
            hits = row.get("hits") or []
            at = next((i for i, h in enumerate(hits) if _keys(h) & want), None)
            n["first"] += at == 0
            n["top3"] += at is not None and at < 3
            n["found"] += at is not None
            if misses is not None and at != 0:
                misses.append("%s  want %s  got %s" % (row.get("word"), "|".join(sorted(want)),
                              " ".join((h.get("headword") or "") + ("*" if h.get("fits") else "") for h in hits[:4]) or "-"))
            said = row.get("machine") or {}
            if at is not None and said.get("upos") and said.get("here", True):
                n["chip"] += 1
                n["chip_ok"] += hits[at].get("pos") in lookupassist.ENTRY_POS.get(said["upos"], ())
            marked = [h for h in hits if h.get("fits")]
            if marked:
                n["mark"] += 1
                n["mark_ok"] += any(_keys(h) & want for h in marked)
    return n


def _line(label, n):
    w = max(n["words"], 1)
    return "  %-34s first %3d %3d%%   top3 %3d%%   found %3d%%   chip %3d/%-3d   mark %3d/%-3d (wrong %d)" % (
        label, n["first"], 100 * n["first"] / w, 100 * n["top3"] / w, 100 * n["found"] / w,
        n["chip_ok"], n["chip"], n["mark_ok"], n["mark"], n["mark"] - n["mark_ok"])


def _no_pass():
    return mock.patch.object(spoken, "rules", return_value=None)


def _no_view():
    return mock.patch.object(lookupassist, "formal_view", side_effect=lambda code, text, register=None: (text, None))


def _tables(morph, syn):
    return mock.patch.multiple(analyzer, MORPHOLOGY={**analyzer.MORPHOLOGY, "tr": morph},
                               SYNTAX={k: v for k, v in analyzer.SYNTAX.items() if k != "tr" or syn})


def run_fa(name, register, show):
    rows = load(name)
    print("%s, %d sentences, register %s" % (name, len(rows), register))
    with _no_pass():
        show("dictionary alone", "fa", rows, register, None)
        analyzer.clear_cache()
        show("analyzer alone (assist)", "fa", rows, register, "assist")
    analyzer.clear_cache()
    show("normaliser", "fa", rows, register, None)
    show("normaliser + analyzer shown", "fa", rows, register, "show")
    with _no_view():
        analyzer.clear_cache()
        show("normaliser + assist, raw text", "fa", rows, register, "assist")
    analyzer.clear_cache()
    show("normaliser + assist (as built)", "fa", rows, register, "assist")


def run_tr(show, name="tr"):
    rows = load(name)
    print("%s, %d sentences" % (name, len(rows)))
    show("dictionary alone", "tr", rows, None, None)
    for label, morph, syn in (("UDPipe alone (assist)", "udpipe", True), ("Starlang alone (assist)", "starlang", False),
                              ("Starlang + UDPipe (as built)", "starlang", True)):
        with _tables(morph, syn):
            analyzer.clear_cache()
            show(label, "tr", rows, None, "assist")


def main(argv):
    getanalysis.FOLDER, lookup.DICT_DIR = argv[0], argv[1]
    want_misses = "--misses" in argv
    which = [a for a in argv[2:] if not a.startswith("--")] or ["fa-spoken", "fa-formal", "fa-holdout", "tr", "tr-holdout"]

    def show(label, code, rows, register, mode):
        misses = [] if want_misses else None
        print(_line(label, score(code, rows, register, mode, misses)))
        for m in misses or ():
            print("      ", m)

    try:
        if "fa-spoken" in which:
            run_fa("fa-spoken", "spoken", show)
        if "fa-formal" in which:
            run_fa("fa-formal", None, show)
        if "fa-holdout" in which:
            run_fa("fa-holdout", "spoken", show)
        if "tr" in which:
            run_tr(show)
        if "tr-holdout" in which:
            run_tr(show, "tr-holdout")
    finally:
        getanalysis.stop_worker()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
