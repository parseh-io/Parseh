#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""How often the dictionary panel puts the right entry first for a text in an Arabic dialect, and how the dialects'
sentences are cut into phrases.  For a person to read; writes nothing.

    python3 tests/dialect_bench.py [--dict FOLDER] [--analysis FOLDER] [SET ...] [--misses] [--order] [--chunks]

SET is msa, egy, lev, gulf, mor (written on while the rules were made) or holdout-egy, holdout-lev, holdout-gulf,
holdout-mor (written after, and never looked at while a rule was written: the only figures that say anything about a
new text).  No SET = every one.  The dictionaries are the ones installed through Settings -> Reading help (dict/), or
those in --dict; a set whose dictionaries are missing is skipped with a line that says which.  --analysis names a
folder of analyzers (Settings -> Linguistic analysis) for the standard set's "as built" line; without one that line
is left out.

The sentences and what each word should be read as are in tests/fixtures/arabic-dialects/, one person's judgement of
a small sample: a difference of a word or two means nothing.  Each word is marked s (written as standard Arabic writes
it), m (a dialect's morphology on a word standard Arabic has) or d (a word only the dialect has).

    first   the right headword is the panel's first hit        found   it is anywhere on the panel
    --order  why, where the right entry is on the panel but not first (the dialect's entries come before the
             standard's: lib/lookup.py _with_variety), and what "first" would be with the standard dictionary's first
    --misses every word whose right entry is not first
    --chunks the dialect's phrase set (phrases/ar-<v>.txt: longer sentences cut by hand, since the word sets'
             sentences are each one phrase) cut with standard Arabic's rules and with the dialect's word lists
             (lib/lang/ar.<v>.chunk.json) and its dictionary's word classes (dict/ar.<v>.db read before dict/ar.db,
             lib/chunker.py _dictionary_classes, and the verb prefixes of ar.<v>.lookup.json): the seams that fall where the hand put them, and how many of the words
             the dialect's list names were read as no class at all without it
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
import analysis_bench as B   # noqa: E402  (_plain, _keys, _clean: the same comparison as the other bench)
import chunker               # noqa: E402
import languages             # noqa: E402
import lookup                # noqa: E402

SETS = os.path.join(HERE, "fixtures", "arabic-dialects")
VARIETIES = ("egy", "lev", "gulf", "mor")
ALL = ["msa"] + list(VARIETIES) + ["holdout-" + v for v in VARIETIES]


def load(name):
    """[(sentence, {word: ({headword, ...}, kind)})] of one set."""
    path = os.path.join(SETS, "holdout", "ar-%s.txt" % name[8:]) if name.startswith("holdout-") \
        else os.path.join(SETS, "ar-%s.txt" % name)
    rows, sentence = [], None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if sentence is None:
                sentence = line
                continue
            gold = {}
            for part in line.split():
                word, rest = part.split("=", 1)
                heads, kind = rest.rsplit("#", 1)
                gold[word] = (set(map(B._plain, heads.split("|"))), kind)
            rows.append((sentence, gold))
            sentence = None
    return rows


def variety_of(name):
    return None if name == "msa" else name.split("-")[-1]


def missing(variety):
    """The dictionaries this set needs that are not installed, as their file names."""
    keys = ["ar"] + (["ar." + variety] if variety else [])
    return [os.path.basename(lookup.path_for(k)) for k in keys if not os.path.isfile(lookup.path_for(k))]


def score(rows, variety, assist=None, misses=None, order=None):
    """{kind: [words, first, found, first-with-the-standard-dictionary's-first]} and the reasons, in `order`."""
    n = {}
    for sentence, gold in rows:
        got = lookup.look_up("ar", sentence, variety=variety)
        if assist:
            assist(got, sentence)
        for row in got.get("words") or []:
            w = B._clean(row.get("word") or "")
            if w not in gold:
                continue
            want, kind = gold[w]
            hits = row.get("hits") or []
            at = next((i for i, h in enumerate(hits) if B._keys(h) & want), None)
            # the same hits with the standard dictionary's before the dialect's: is the merge's order the right one?
            swapped = [h for h in hits if not h.get("variety")] + [h for h in hits if h.get("variety")]
            at2 = next((i for i, h in enumerate(swapped) if B._keys(h) & want), None)
            for k in (kind, "all"):
                c = n.setdefault(k, [0, 0, 0, 0])
                c[0] += 1
                c[1] += at == 0
                c[2] += at is not None
                c[3] += at2 == 0
            if at and order is not None:
                right, before = hits[at], hits[:at]
                if right.get("variety"):
                    why = "another entry of the dialect's dictionary first"
                elif all(h.get("variety") for h in before):
                    why = "the dialect's entry first, the right one standard"
                else:
                    why = "another standard entry first"
                order.setdefault(why, []).append(_said(w, kind, want, hits))
            if at != 0 and misses is not None:
                misses.append(_said(w, kind, want, hits))
    return n


def _said(w, kind, want, hits):
    return "%s#%s  want %s  got %s" % (w, kind, "|".join(sorted(want)), " ".join(
        (h.get("headword") or "") + ("ᵛ" if h.get("variety") else "") + ("*" if h.get("fits") else "")
        for h in hits[:5]) or "-")


def line(label, n, swapped=False):
    out = []
    for k in ("all", "s", "m", "d"):
        if k in n:
            t, f, fd, f2 = n[k]
            out.append("%s %2d/%-2d first %3d%% found %3d%%" % (k, f, t, 100 * f / t, 100 * fd / t)
                       + (" (standard first: %3d%%)" % (100 * f2 / t) if swapped else ""))
    return "  %-34s %s" % (label, " | ".join(out))


def _seams(groups):
    """The word positions a cut falls before, of a sentence cut into groups."""
    out, at = set(), 0
    for g in groups[:-1]:
        at += len(g.split())
        out.add(at)
    return out


def phrases(variety):
    """[(sentence, gold groups)] of the variety's phrase set (tests/fixtures/arabic-dialects/phrases/)."""
    rows = []
    with open(os.path.join(SETS, "phrases", "ar-%s.txt" % variety), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                groups = [g.strip() for g in line.split("|")]
                rows.append((" ".join(groups), groups))
    return rows


def chunks(rows, variety):
    """The variety's phrase set cut by the standard rules and by the variety's (lib/lang/ar.<v>.chunk.json read
    first) -> lines to print, {"standard"|"dialect": [seams right, seams cut, seams wanted]}, and over the word set's
    sentences and the phrase set's, (words the variety lists, of them read as no class before, after)."""
    key = "ar.%s" % variety
    lex = chunker._lexicon(key)
    L = languages.get(key)
    out, n, other = [], {"standard": [0, 0, 0], "dialect": [0, 0, 0]}, [0, 0, 0]
    gold = phrases(variety)
    for sentence, want in gold:
        a = chunker.chunk(sentence, "ar", "phrase")
        b = chunker.chunk(sentence, key, "phrase")
        w = _seams(want)
        for label, got in (("standard", a), ("dialect", b)):
            s = _seams(got)
            n[label][0] += len(s & w)
            n[label][1] += len(s)
            n[label][2] += len(w)
        out.append("    want      %s" % " | ".join(want))
        out.append("    %-9s %s" % ("both" if a == b else "standard", " | ".join(a)))
        if a != b:
            out.append("    dialect   %s" % " | ".join(b))
    for sentence in [r[0] for r in rows] + [g[0] for g in gold]:
        for tok in sentence.split():
            k = chunker._key(lookup._bare(tok, L), L)
            if k in lex:
                other[0] += 1
                other[1] += chunker._class(tok, "ar") == "OTHER"
                other[2] += chunker._class(tok, key) == "OTHER"
    return out, n, other


def _prf(c):
    right, cut, wanted = c
    return "seams right %2d of %2d cut (%3d%%), of %2d wanted (%3d%%)" % (
        right, cut, 100 * right / cut if cut else 0, wanted, 100 * right / wanted if wanted else 0)


def main(argv):
    args = list(argv)
    for flag in ("--dict", "--analysis"):
        if flag in args:
            i = args.index(flag)
            folder = os.path.abspath(os.path.expanduser(args[i + 1]))
            del args[i:i + 2]
            if flag == "--dict":
                lookup.DICT_DIR = folder
            else:
                import getanalysis
                getanalysis.FOLDER = folder
    want_misses, want_order, want_chunks = "--misses" in args, "--order" in args, "--chunks" in args
    names = [a for a in args if not a.startswith("--")] or ALL
    bad = [x for x in names if x not in ALL]
    if bad:
        raise SystemExit("dialect_bench: no set %s (the sets: %s)" % (", ".join(bad), " ".join(ALL)))
    print("Dictionaries in %s" % lookup.DICT_DIR)
    assist = _assist()
    try:
        for name in names:
            variety = variety_of(name)
            rows = load(name)
            gone = missing(variety)
            print("%s, %d sentences" % (name, len(rows)))
            if gone:
                print("  skipped: %s not installed (Settings -> Reading help, Arabic%s)"
                      % (" and ".join(gone), " and its dialect" if variety else ""))
                continue
            if variety:
                print(line("read as standard Arabic", score(rows, None)))
                misses, order = [] if want_misses else None, {} if want_order else None
                print(line("as built (its dialect's rules)", score(rows, variety, None, misses, order), swapped=want_order))
                for why, words in sorted((order or {}).items()):
                    print("    %s: %d" % (why, len(words)))
                    for w in words:
                        print("        " + w)
            else:
                misses = [] if want_misses else None
                print(line("dictionary alone", score(rows, None, None, misses)))
                if assist:
                    print(line("dictionary + analysis (as built)", score(rows, None, assist)))
            for m in misses or []:
                print("    miss " + m)
            if want_chunks and variety and not name.startswith("holdout-"):
                out, n, (listed, before, after) = chunks(rows, variety)
                print("  phrases (tests/fixtures/arabic-dialects/phrases/ar-%s.txt):" % variety)
                print("    standard Arabic's rules        " + _prf(n["standard"]))
                print("    with the dialect's lists, dict " + _prf(n["dialect"]))
                print("    words the dialect's list names: %d in both sets, %d read as no class without it, %d with it"
                      % (listed, before, after))
                print("\n".join(out))
    finally:
        if assist:
            import getanalysis
            getanalysis.stop_worker()


def _assist():
    """lookupassist as Settings -> Linguistic analysis has it, where an analyzer for Arabic is installed; else None."""
    try:
        import analyzer
        import lookupassist
        if not analyzer.available("ar"):
            return None
    except Exception:
        return None
    return lambda got, s: lookupassist.apply("ar", got, s, s, "assist", None)


if __name__ == "__main__":
    main(sys.argv[1:])
