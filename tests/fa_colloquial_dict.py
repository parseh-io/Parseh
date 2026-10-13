# SPDX-License-Identifier: GPL-3.0-or-later
"""The small Persian dictionary the colloquial normaliser's fixture is read against
(tests/fixtures/fa_colloquial/).

    import fa_colloquial_dict
    fa_colloquial_dict.build("/tmp/x/fa.db")         # -> the number of entries

It is built here and not downloaded, as every dictionary the tests use is, and it is SHAPED
LIKE WIKTIONARY'S PERSIAN, which is what the normaliser has to work against and what it must
not be given an easier world than:

  * FORMAL words only.  A spoken form (خونه, میگه) is not an entry; it is what the normaliser
    has to reach.  The only exceptions are the few entries `colloquial.json` lists, which stand
    for the dictionary's own "colloquial form of ..." pages (the note's principle: those come
    before any rule) -- and they are few on purpose, so that nothing here is easy because the
    dictionary happens to hold the spoken word.
  * A verb carries its whole formal conjugation as form rows, the way Wiktionary's tables give
    it (می‌کنم, نکردیم, بروید, رفته‌اند, ...) -- generated here from three stems, so that the
    fixture lists a verb once.  The generated rows are written with the ZWNJ and the builder
    adds the joinerless and mark-less spelling of every form, as lib/getdict.py's `_folded`
    does for the real one.
  * Every word has the part of speech Wiktionary files it under, and the homographs the note's
    section 14 lists (خون, نون, رفتن, ...) are there as the ORDINARY words they also are.

What this proves is that the rules reach a real entry through a real table.  It says nothing
of how much of the real 17,000-headword dictionary a rule would invent an answer in: that is
not measured here (the brief leaves it out) and `dict/` is empty in a checkout.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _folder in (ROOT / "lib",):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

FIXTURES = ROOT / "tests" / "fixtures" / "fa_colloquial"
ZW = "‌"
# a stem takes the same six endings in the present, and the past takes them with no ending in the third person singular
PRESENT = ["م", "ی", "د", "یم", "ید", "ند"]
PAST = ["م", "ی", "", "یم", "ید", "ند"]
PERSON = ["first-person singular", "second-person singular", "third-person singular",
          "first-person plural", "second-person plural", "third-person plural"]
PERFECT = [ZW + "ام", ZW + "ای", " است", ZW + "ایم", ZW + "اید", ZW + "اند"]


def load(name):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def verb_forms(past, pres, o=None):
    """The formal conjugation of one verb as [(form, note)], the way Wiktionary's table lists it.

    `o` carries the few things a verb does its own way: `subj` (the subjunctive stem with its
    prefix, بیا- for آمدن), `neg` (the negative subjunctive's), `neg_past` (نی- for آمدن),
    `imp` (the imperative singular, بیا), `bare` (a present with no می-: داشتن), and `pre`, a
    preverb the stems stand behind (بر- of برگشتن: برمی‌گردم, برنگشتم, برگردم -- no ب-)."""
    o = o or {}
    pre = o.get("pre", "")
    subj = o.get("subj", pre + (pres if pre else "ب" + pres))
    neg = o.get("neg", pre + "ن" + pres)
    neg_past = o.get("neg_past", pre + "ن" + past)
    mi, nemi = pre + "می" + ZW, pre + "نمی" + ZW
    out = [(pre + past + "ه", "past participle")]
    for i, who in enumerate(PERSON):
        out += [
            (pre + past + PAST[i], who + " past indicative"),
            (mi + past + PAST[i], who + " past progressive"),
            (neg_past + PAST[i], who + " negative past indicative"),
            (nemi + past + PAST[i], who + " negative past progressive"),
            (mi + pres + PRESENT[i], who + " present indicative"),
            (nemi + pres + PRESENT[i], who + " negative present indicative"),
            (subj + PRESENT[i], who + " present subjunctive"),
            (neg + PRESENT[i], who + " negative present subjunctive"),
            (pre + past + "ه" + PERFECT[i], who + " present perfect"),
            (neg_past + "ه" + PERFECT[i], who + " negative present perfect"),
        ]
        if o.get("bare"):
            out += [(pre + pres + PRESENT[i], who + " present indicative"),
                    ("ن" + pres + PRESENT[i], who + " negative present indicative")]
    out += [(o.get("imp", subj), "imperative singular"), (subj + "ید", "imperative plural"),
            (o.get("negimp", neg), "negative imperative singular"), (neg + "ید", "negative imperative plural")]
    if pres.endswith("وی") and len(pres) > 2:
        # the imperative of a stem in -avy drops the yeh, as the tables of Wiktionary list it: بگو, نگو (not بگوی)
        out += [(subj[:-1], "imperative singular"), (neg[:-1], "negative imperative singular")]
    return out


def be_forms():
    """بودن, which has its own present (هستم, نیستم) and no می- forms."""
    out = [("بوده", "past participle")]
    for i, who in enumerate(PERSON):
        out += [("بود" + PAST[i], who + " past indicative"), ("نبود" + PAST[i], who + " negative past indicative"),
                ("هست" + ["م", "ی", "", "یم", "ید", "ند"][i], who + " present indicative"),
                ("نیست" + ["م", "ی", "", "یم", "ید", "ند"][i], who + " negative present indicative"),
                ("باش" + PRESENT[i], who + " present subjunctive"), ("نباش" + PRESENT[i], who + " negative present subjunctive"),
                ("بوده" + PERFECT[i], who + " present perfect")]
    return out + [("باش", "imperative singular"), ("باشید", "imperative plural"), ("نباش", "negative imperative singular")]


def rows_of_verbs():
    """[(headword, pos, translit, sense, forms)] for every verb of verbs.json, compounds included."""
    spec = load("verbs.json")
    out, formal = [], {}
    for inf, past, pres, tr, sense, *rest in spec["verbs"]:
        o = rest[0] if rest else {}
        forms = be_forms() if inf == "بودن" else verb_forms(past, pres, o)
        formal[inf] = forms
        out.append((inf, "verb", tr, sense, forms))
    for noun, inf, tr, sense in spec["compounds"]:
        out.append((noun + " " + inf, "verb", tr, sense,
                    [(noun + " " + form, note) for form, note in formal[inf]]))
    return out


def build(path):
    """Write the dictionary at `path` (a `fa.db`).  -> how many entries it has."""
    import lookup as lk
    L = lk.languages.get_or_default("fa")
    rows = list(rows_of_verbs())
    for head, pos, tr, sense, *rest in load("lexicon.json")["entries"]:
        rows.append((head, pos, tr, sense, (rest[0] if rest else {}).get("forms", []), (rest[0] if rest else {})))
    for head, pos, tr, sense, tags in load("colloquial.json")["entries"]:
        rows.append((head, pos, tr, sense, [], {"tags": tags}))
    c = lk.create(path)
    for row in rows:
        head, pos, tr, sense, forms = row[:5]
        extra = row[5] if len(row) > 5 else {}
        senses = sense if isinstance(sense, list) else [s.strip() for s in sense.split(";") if s.strip()]
        tags = extra.get("tags", "")
        cur = c.execute("INSERT INTO entry (headword, translit, ipa, pos, sense, sense_tags) VALUES (?,?,?,?,?,?)",
                        (head, tr, extra.get("ipa", ""), pos, "\n".join(senses), "\n".join([tags] * len(senses))))
        seen = set()
        for form, note in [(head, "")] + [tuple(f) for f in forms]:
            for variant in (form, lk._fold(form, L)):
                if (variant, note) not in seen:
                    seen.add((variant, note))
                    c.execute("INSERT INTO form (form, entry_id, note) VALUES (?,?,?)", (variant, cur.lastrowid, note))
    c.executemany("INSERT INTO meta (key, value) VALUES (?,?)",
                  [("lang", "fa"), ("source", "the colloquial fixture"), ("licence", "none"),
                   ("built", "2026-10-12"), ("entries", str(len(rows)))])
    c.commit()
    c.close()
    return len(rows)


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        print(build(os.path.join(folder, "fa.db")), "entries")
