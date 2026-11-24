# SPDX-License-Identifier: GPL-3.0-or-later
"""A stand-in for lane C's lib/syncrules.py (a0.7.0), with its interface exactly,
for Settings -> Devices' tests (tests/test_devices_page.py, tests/devices_page.mjs)
until the real module is merged.  Put in sys.modules["syncrules"] by the tests.

    seed(folder, doc=uid, book=uid)   the questions, kept versions, diffs and builds the tests look at
    CALLS                             every answer given, for the tests to read

Each answer does what lane C promises the page and nothing more: the question
goes, and a choice writes the diff of what it threw away.
"""
import os
import time

DIR = None
QUESTIONS, KEPT, DIFFS, OOD, CALLS = [], [], {}, [], []
SUMMARY = {}


def _diff(unit, title, text):
    n = "d%03d-%s.diff" % (len(DIFFS) + 1, unit.replace(":", "-").replace("/", "-"))
    path = os.path.join(DIR, n)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    DIFFS[n] = {"id": n, "unit": unit, "title": title, "at": time.time(), "size": len(text.encode())}
    return n


def seed(folder, doc, book, partner="p-laptop", partner_name="laptop"):
    global DIR
    DIR = folder
    os.makedirs(DIR, exist_ok=True)
    del QUESTIONS[:], KEPT[:], OOD[:], CALLS[:]
    DIFFS.clear()
    now = time.time()
    mine = "--- this computer\n+++ laptop\n@@ -1,2 +1,2 @@\n Hello.\n-The bell rang twice.\n+The bell rang once.\n"
    theirs = "--- laptop\n+++ this computer\n@@ -1,2 +1,2 @@\n Hello.\n-The bell rang once.\n+The bell rang twice.\n"
    QUESTIONS.extend([
        {"id": "q1", "kind": "choice", "units": [{"unit": doc, "kind": "doc", "title": "The bell"}],
         "partner": partner, "partner_name": partner_name,
         "mine": {"at": now - 600, "summary": "edited here: 1 line"},
         "theirs": {"at": now - 300, "summary": "edited on laptop: 1 line"},
         "discard_preview": {"mine": mine, "theirs": theirs}},
        {"id": "q2", "kind": "deletion", "units": [{"unit": book, "kind": "book", "title": "Demo book"}],
         "partner": partner, "partner_name": partner_name, "mine": {"at": now - 900, "summary": ""},
         "theirs": {"at": now - 100, "summary": "deleted"}, "discard_preview": {}},
        {"id": "q3", "kind": "deletion",
         "units": [{"unit": "clip:c%d" % i, "kind": "clip", "title": "Clip %d" % i} for i in (1, 2, 3)],
         "partner": partner, "partner_name": partner_name, "mine": {"at": now - 900, "summary": ""},
         "theirs": {"at": now - 50, "summary": "3 deleted"}, "discard_preview": {}},
        {"id": "q4", "kind": "deletion-edited", "units": [{"unit": "doc:persian/old-notes", "kind": "doc",
                                                          "title": "Old notes"}],
         "partner": partner, "partner_name": partner_name, "mine": {"at": now - 20, "summary": "edited here"},
         "theirs": {"at": now - 40, "summary": "deleted"}, "discard_preview": {}},
    ])
    KEPT.append({"id": "k1", "unit": "doc:persian/grammar", "title": "Grammar", "why": "incoming",
                 "partner": partner, "at": now - 3600, "until": now + 82800})
    _diff("doc:persian/earlier", "Earlier", "--- a\n+++ b\n-old\n+new\n")
    OOD.append({"unit": doc, "title": "The bell", "what": "its PDF was built"})
    SUMMARY.update({"replace": 4, "add": 2, "delete": 1, "lost": [{"unit": doc, "title": "The bell"}],
                    "questions": 4, "jobs": [{"id": "j1", "title": "Transcribe the interview"}]})


def questions():
    return [dict(q) for q in QUESTIONS]


def question_for(uid):
    return next((dict(q) for q in QUESTIONS if any(u["unit"] == uid for u in q["units"])), None)


def answer(qid, choice, unit=None):
    # as lib/syncrules.py: one unit of a grouped deletion per call
    units = [unit] if unit else None
    CALLS.append((qid, choice, units))
    q = next((q for q in QUESTIONS if q["id"] == qid), None)
    if q is None:
        raise KeyError(qid)
    diff_id = None
    if units:
        q["units"] = [u for u in q["units"] if u["unit"] not in units]
        if not q["units"]:
            QUESTIONS.remove(q)
    else:
        QUESTIONS.remove(q)
    if q["kind"] == "choice":
        u = q["units"][0]
        diff_id = _diff(u["unit"], u["title"], q["discard_preview"][choice])
        KEPT.insert(0, {"id": "k%d" % (len(KEPT) + 1), "unit": u["unit"], "title": u["title"], "why": "choice",
                        "partner": q["partner"], "at": time.time(), "until": time.time() + 86400})
    return {"ok": True, "diff_id": diff_id}


def identical_summary(partner_id):
    return dict(SUMMARY)


def make_identical(partner_id):
    CALLS.append(("identical", partner_id, None))
    del QUESTIONS[:]
    return {"ok": True, "diff_id": _diff("identical", "Lost making this identical", "-lost line\n")}


def kept():
    return [dict(k) for k in KEPT]


def put_back(kept_id):
    CALLS.append(("put-back", kept_id, None))
    KEPT[:] = [k for k in KEPT if k["id"] != kept_id]
    return {"ok": True}


def diffs():
    return sorted((dict(d) for d in DIFFS.values()), key=lambda d: -d["at"])


def diff_path(diff_id):
    return os.path.join(DIR, diff_id) if diff_id in DIFFS else None


def delete_diff(diff_id):
    if diff_id in DIFFS:
        os.unlink(os.path.join(DIR, diff_id))
        del DIFFS[diff_id]


def out_of_date():
    return [dict(o) for o in OOD]


def is_out_of_date(uid):
    return any(o["unit"] == uid for o in OOD)
