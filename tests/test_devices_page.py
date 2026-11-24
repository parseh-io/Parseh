#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings -> Devices (a0.7.0, lane E: lib/devicespage.py) route by route, with
lane C's syncrules and lane D's syncjobs as the fakes tests/syncrules_fake.py and
tests/syncjobs_fake.py (put in sys.modules), synclock and syncunits real, every
shelf in a temporary tree:

  * who may: every route that changes sync is the computer's alone, in the
    setting's own words; what a unit's page asks and the leases are open to a
    device let in
  * the answers: a choice writes its diff, a grouped deletion answered whole or
    one unit at a time, an answer the question does not take is refused
  * the unit a page or an editor names, by its id or by its address
  * the lease: open, keep, close; Busy while a sync writes, in words
  * the pages: the door, the choice page with both diffs before, a question gone
  * the QR code of the pairing payload
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "tests", "."):
    sys.path.insert(0, str(ROOT / p))
import network          # noqa: E402
import settingspage     # noqa: E402
import syncrules_fake   # noqa: E402
import syncjobs_fake    # noqa: E402


class Devices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="parseh-devices-test-"))
        cls._mods = {k: sys.modules.get(k) for k in ("syncrules", "syncjobs")}
        sys.modules["syncrules"] = syncrules_fake
        sys.modules["syncjobs"] = syncjobs_fake
        import prefs
        cls._prefs = prefs.STORE
        prefs.STORE = str(cls.tmp / "config" / "prefs.json")
        (cls.tmp / "config").mkdir()
        import syncunits
        cls._shelves = dict(syncunits.SHELVES)
        for k in ("books", "videos", "anki", "library", "exercises", "clips"):
            (cls.tmp / k).mkdir()
        syncunits.configure(**{k: str(cls.tmp / k) for k in ("books", "videos", "anki", "library", "exercises",
                                                             "clips")})
        (cls.tmp / "videos" / "persian" / "abcdefghijk").mkdir(parents=True)
        (cls.tmp / "library" / "persian" / "the-bell-1a2b3c").mkdir(parents=True)
        import devicespage
        cls.D = devicespage

    @classmethod
    def tearDownClass(cls):
        import prefs
        import syncunits
        prefs.STORE = cls._prefs
        syncunits.configure(**cls._shelves)
        for k, v in cls._mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        syncrules_fake.seed(str(self.tmp / "diffs"), doc="doc:persian/the-bell-1a2b3c", book="book:persian/demo")
        syncjobs_fake.seed()

    def api(self, what, body=None, where=network.SELF):
        return self.D.api(what, body or {}, where)

    # ---- who may
    def test_changing_sync_is_the_computers_and_a_page_s_questions_are_open(self):
        mine = [r for r in settingspage.ROUTES if r.startswith("/settings/api/devices/")]
        self.assertGreaterEqual(len(mine), 21)
        for route in mine:
            name = route.rsplit("/", 1)[1]
            ok_self, _ = settingspage.may_post(route, network.SELF)
            ok_lan, why = settingspage.may_post(route, network.LAN)
            self.assertTrue(ok_self, route)
            if name in self.D.OPEN:
                self.assertTrue(ok_lan, route)
            else:
                self.assertFalse(ok_lan, route)
                self.assertIn("computer", why)
                self.assertIn("A computer paired here may bring its changes in", why)

    def test_the_door_is_its_own_and_network_no_longer_carries_sync(self):
        doors = {d[0]: d for d in settingspage.DOORS}
        self.assertEqual(doors["/settings/devices/"][3], ("sync.devices",))
        self.assertNotIn("sync.devices", doors["/settings/network/"][3])
        self.assertIn('href="/settings/devices/"', settingspage.hub())

    # ---- the overview and the answers
    def test_the_overview_carries_every_part_of_the_page(self):
        code, out = self.api("overview")
        self.assertEqual(code, 200)
        self.assertEqual(out["missing"], [])
        self.assertEqual([q["id"] for q in out["questions"]], ["q1", "q2", "q3", "q4"])
        self.assertEqual(out["switches"], {"send": False, "accept": False})
        self.assertEqual(len(out["jobs"]), 2)
        self.assertEqual(out["kept"][0]["id"], "k1")
        self.assertEqual(len(out["diffs"]), 1)
        self.assertEqual(out["out_of_date"][0]["unit"], "doc:persian/the-bell-1a2b3c")
        self.assertIn("persian", [L["folder"] for L in out["languages"]])

    def test_a_choice_writes_the_diff_it_showed(self):
        code, out = self.api("answer", {"id": "q1", "choice": "mine"})
        self.assertEqual(code, 200)
        path = self.D.diff_file(out["diff_id"])[0]
        with open(path, encoding="utf-8") as fh:
            self.assertIn("+The bell rang once.", fh.read())
        self.assertNotIn("q1", [q["id"] for q in self.api("overview")[1]["questions"]])

    def test_an_answer_the_question_does_not_take_is_refused(self):
        code, out = self.api("answer", {"id": "q1", "choice": "delete"})
        self.assertEqual(code, 400)
        self.assertIn("mine, theirs", out["error"])
        code, out = self.api("answer", {"id": "q2", "choice": "mine"})
        self.assertEqual(code, 400)
        code, out = self.api("answer", {"id": "q4", "choice": "restore"})
        self.assertEqual(code, 400)
        code, out = self.api("answer", {"id": "nope", "choice": "mine"})
        self.assertEqual(code, 404)

    def test_a_grouped_deletion_whole_or_one_at_a_time(self):
        code, _ = self.api("answer", {"id": "q3", "choice": "delete", "units": ["clip:c1"]})
        self.assertEqual(code, 200)
        q3 = next(q for q in self.api("overview")[1]["questions"] if q["id"] == "q3")
        self.assertEqual([u["unit"] for u in q3["units"]], ["clip:c2", "clip:c3"])
        self.assertEqual(self.api("answer", {"id": "q3", "choice": "restore"})[0], 200)
        self.assertEqual(syncrules_fake.CALLS[-1], ("q3", "restore", None))
        self.assertNotIn("q3", [q["id"] for q in self.api("overview")[1]["questions"]])

    def test_switches_jobs_kept_diffs_and_identical(self):
        self.assertEqual(self.api("switches", {"send": True})[1]["switches"], {"send": True, "accept": False})
        self.assertEqual(self.api("job-cancel", {"id": "j1"})[0], 200)
        self.assertEqual(syncjobs_fake.JOBS[0]["state"], "cancelled")
        self.assertEqual(self.api("put-back", {"id": "k1"})[0], 200)
        did = syncrules_fake.diffs()[0]["id"]
        self.assertEqual(self.api("diff-delete", {"id": did})[0], 200)
        self.assertEqual(self.api("diff-delete", {"id": "../x"})[0], 400)
        self.assertIsNone(self.D.diff_file("../../etc/passwd"))
        # "make identical" names a partner that is paired here, and nothing else
        self.assertEqual(self.api("identical-summary", {"partner": "nobody"})[0], 400)

    def test_a_part_not_merged_yet_says_so(self):
        sys.modules["syncjobs"] = None                     # import fails, as before lane D lands
        try:
            code, out = self.api("switches", {"send": True})
            self.assertEqual(code, 503)
            self.assertIn("not in this version yet", out["error"])
            self.assertIn("syncjobs", self.api("overview")[1]["missing"])
        finally:
            sys.modules["syncjobs"] = syncjobs_fake

    # ---- the unit a page names
    def test_the_unit_of_a_page_by_its_id_or_its_address(self):
        D = self.D
        self.assertEqual(D.resolve({"unit": "doc:persian/the-bell-1a2b3c"}), "doc:persian/the-bell-1a2b3c")
        self.assertIsNone(D.resolve({"unit": "doc:../../etc"}))
        self.assertEqual(D.resolve({"path": "/books/persian/demo/index.html"}), "book:persian/demo")
        self.assertEqual(D.resolve({"path": "/youtube/v/abcdefghijk/"}), "video:persian/abcdefghijk")
        self.assertIsNone(D.resolve({"path": "/youtube/v/zzzzzzzzzzz/"}))
        self.assertEqual(D.resolve({"path": "/exercises/deck/persian/words/"}), "deck:persian/words")
        self.assertIsNone(D.resolve({"path": "/settings/"}))
        self.assertEqual(D.unit_at(self.tmp / "library" / "persian" / "the-bell-1a2b3c"),
                         "doc:persian/the-bell-1a2b3c")
        code, out = self.api("unit", {"path": "/books/persian/demo/"}, network.LAN)
        self.assertEqual(out["question"]["id"], "q2")
        self.assertFalse(out["may_answer"], "a device let in sees the question, and is told where it is answered")
        out = self.api("unit", {"unit": "doc:persian/the-bell-1a2b3c"})[1]
        self.assertTrue(out["out_of_date"])
        self.assertEqual(out["question"]["page"], "/settings/devices/question/q1")

    # ---- the lease
    def test_an_editor_holds_its_unit_and_is_told_when_sync_writes_it(self):
        import synclock
        uid = "doc:persian/the-bell-1a2b3c"
        code, out = self.api("lease-open", {"unit": uid, "holder": "studio"}, network.LAN)
        self.assertEqual(code, 200)
        tok = out["token"]
        self.assertEqual(synclock.editing(uid), ["studio"])
        with self.assertRaises(synclock.Busy):
            with synclock.sync_write(uid):
                pass
        self.assertTrue(self.api("lease-keep", {"token": tok})[1]["kept"])
        self.assertTrue(self.api("lease-close", {"token": tok})[1]["closed"])
        self.assertEqual(synclock.editing(uid), [])
        self.assertFalse(self.api("lease-keep", {"token": tok})[1]["kept"])
        with synclock.sync_write(uid):
            code, out = self.api("lease-open", {"unit": uid})
        self.assertEqual(code, 409)
        self.assertIn("Sync is writing this", out["error"])
        self.assertEqual(self.api("lease-open", {"path": "/settings/"})[1]["token"], None)

    # ---- the pages
    def test_the_choice_page_shows_both_diffs_before(self):
        page = self.D.question_page("q1", network.SELF)
        self.assertIn("a question from laptop", page)
        self.assertIn("+The bell rang once.", page)        # the data the page draws both diffs from
        self.assertIn("+The bell rang twice.", page)
        self.assertNotIn("lockline", page.split("<main", 1)[1].split("data-say")[0])
        gone = self.D.question_page("q9", network.SELF)
        self.assertIn("answered already", gone)
        phone = self.D.question_page("q1", network.LAN)
        self.assertIn('data-lock="sync.devices"', phone)

    def test_the_door(self):
        page = self.D.page(network.SELF)
        for part in ("data-partners", "data-pair-start", "data-questions", 'data-switch="send"',
                     'data-switch="accept"', "data-langs", "data-kept", "data-diffs", "data-jobs",
                     "several-computers.html", 'class="sdoor on" href="/settings/devices/"'):
            self.assertIn(part, page)
        self.assertIn('data-lock="sync.devices"', self.D.page(network.LAN))

    def test_the_pairing_payload_as_a_qr_code(self):
        import qrsvg
        m = qrsvg.matrix("parseh-pair:1?code=KP4R7M&fp=" + "ab" * 32 + "&at=192.168.1.20:7654")
        self.assertEqual(len(m) % 4, 1)                   # 17 + 4 * version modules a side
        self.assertTrue(all(m[r][c] for r, c in ((0, 0), (0, 6), (6, 0), (6, 6))))   # a finder's corners
        svg = qrsvg.svg("x")
        self.assertTrue(svg.startswith("<svg") and "<path" in svg)


if __name__ == "__main__":
    unittest.main()
