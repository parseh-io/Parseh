# SPDX-License-Identifier: GPL-3.0-or-later
"""The ARASAAC pictograms' downloader (lib/getarasaac.py), a0.4.2 (W9, brief 9C.2).

    python3 -m unittest tests/test_getarasaac.py

THE TWO HOSTS ARE STOOD IN FOR (tests/arasaac_fake.py), on 127.0.0.1: the API's word lists and the
static host's pictures, with a clock of their own, 304s, a busy server, a connection that drops and a
picture cut short.  Nothing here reaches ARASAAC, and nothing is written outside a temporary
arasaac/ -- the checkout's own is never touched.  What is held:

  * NOTHING A CLIENT SENDS BECOMES A PATH OR AN ADDRESS: a language is one of ARASAAC's forty, a size
    one of two numbers, an id an integer; the two hosts are the only two there are;
  * THE FILES ARE WHAT THEY SAY: every picture is a whole PNG, the index's ids are the files'
    (less the ones the host has no picture of), the manifest says it is complete, and the credit is
    written word for word beside them;
  * IT IS GENTLE: one connection kept open, one request at a time, a User-Agent that names Parseh and
    is written the way lib/getstt.py writes its own, a busy server waited out and its Retry-After
    obeyed;
  * IT CARRIES ON: stopped, killed or cut, the next press fetches exactly what is left -- no picture
    twice -- and a body that is not a whole picture never lands under its name;
  * AN UPDATE FETCHES WHAT CHANGED and asks before it fetches (If-Modified-Since); a number ARASAAC
    no longer lists is let go; a change of size replaces the pictures;
  * the sizes said before a button is pressed are the measured ones, and a word list that is not
    ARASAAC's is refused without touching the one that is here.
"""
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", ".", "tests"):
    sys.path.insert(0, str(ROOT / p))
import download                                                    # noqa: E402
import getarasaac as ga                                            # noqa: E402
import getstt                                                      # noqa: E402
import arasaac_fake                                                # noqa: E402


class Tree(unittest.TestCase):
    """A temporary arasaac/ and a fake pair of hosts, wired into getarasaac for one test."""

    n = 12
    locales = ("en", "fr")

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.dir = self.tmp / "arasaac"
        self.fake = arasaac_fake.Fake(arasaac_fake.World(self.n, self.locales))
        self.world = self.fake.world
        self.patches = [
            mock.patch.object(ga, "ARASAAC_DIR", str(self.dir)),
            mock.patch.object(ga, "API", self.fake.api),
            mock.patch.object(ga, "STATIC", self.fake.static),
            mock.patch.object(ga, "MIN_RECORDS", 5),
            mock.patch.object(ga, "PAUSE", 0.0),
            mock.patch.object(ga, "RETRIES", (0, 0, 0)),
        ]
        for p in self.patches:
            p.start()
        ga._FACTS.clear()
        ga.JOB.clear()
        self.said = []

    def tearDown(self):
        ga.stop_all(3)
        for p in reversed(self.patches):
            p.stop()
        self.fake.stop()
        ga._FACTS.clear()
        ga.JOB.clear()
        self._td.cleanup()

    def say(self, text):
        self.said.append(text)

    def build(self, locales=("en",), resolution=300, **kw):
        return ga.build(locales, resolution, say=self.say, **kw)

    def files(self):
        folder = self.dir / "pictograms"
        return sorted(int(p.stem) for p in folder.glob("*.png")) if folder.is_dir() else []

    def wait(self, what, ms=15000):
        end = time.time() + ms / 1000
        while time.time() < end:
            if what():
                return True
            time.sleep(0.02)
        self.fail("timed out waiting for " + what.__doc__ if what.__doc__ else "a condition")


class Names(unittest.TestCase):
    """Nothing a client sends becomes a path or an address."""

    def test_a_language_is_one_of_the_forty_the_api_lists(self):
        self.assertEqual(len(ga.LOCALES), 40)
        for good in ("en", "fa", "zh", "val", "nb"):
            self.assertEqual(ga.check_locale(good), good)
        for bad in ("ja", "", "EN", "en/../x", "../en", "en.json", " en", None, 5, ["en"], "english"):
            with self.assertRaises(ga.ArasaacError, msg=repr(bad)) as cm:
                ga.check_locale(bad)
            self.assertEqual(cm.exception.code, "bad-language")

    def test_the_languages_of_a_request_are_a_list_of_those_names_each_once(self):
        self.assertEqual(ga.check_locales(["en", "fr", "en"]), ("en", "fr"))
        for bad in ("en", None, 5, {"en": 1}, ["en", "ja"], ["en", None], [["en"]]):
            with self.assertRaises(ga.ArasaacError, msg=repr(bad)):
                ga.check_locales(bad)

    def test_a_size_is_one_of_two_numbers_and_an_id_an_integer_in_range(self):
        for good in (300, 500):
            self.assertEqual(ga.check_resolution(good), good)
        for bad in (2500, 100, "300", 300.0, True, None, -300, 0):
            with self.assertRaises(ga.ArasaacError, msg=repr(bad)):
                ga.check_resolution(bad)
        self.assertEqual(ga.check_id(6964), 6964)
        for bad in ("6964", 6964.0, 0, -1, 10 ** 7, None, True, "6964/../x"):
            with self.assertRaises(ga.ArasaacError, msg=repr(bad)):
                ga.check_id(bad)

    def test_a_picture_path_is_only_ever_an_integers_name(self):
        with mock.patch.object(ga, "ARASAAC_DIR", "/x/arasaac"):
            self.assertEqual(ga.picture_path(6964), os.path.join("/x/arasaac", "pictograms", "6964.png"))
            self.assertEqual(ga.index_path("fr"), os.path.join("/x/arasaac", "index.fr.json"))
            with self.assertRaises(ga.ArasaacError):
                ga.picture_path("../../etc/passwd")
            with self.assertRaises(ga.ArasaacError):
                ga.index_path("../x")

    def test_there_are_two_hosts_and_the_user_agent_is_written_as_the_speech_downloader_writes_it(self):
        self.assertEqual(ga.HOSTS, ("api.arasaac.org", "static.arasaac.org"))
        self.assertTrue(ga.API.startswith("https://api.arasaac.org/") and ga.STATIC.startswith("https://static.arasaac.org/"))
        self.assertEqual(ga.UA, getstt.UA, "a0.4.4's sweep finds the address by this one shape")
        self.assertRegex(ga.UA, r"^Parseh/a\d+\.\d+\.\d+ \(\+https://github\.com/[^/]+/Parseh\)$")
        # and the line is the same line: the version it names is the one VERSION file's
        src = (ROOT / "lib" / "getarasaac.py").read_text(encoding="utf-8")
        self.assertIn('UA = project.agent(version.VERSION)', src, "the line is lib/project.py's, not a copy of it")

    def test_which_languages_are_offered_is_said_from_what_was_measured(self):
        self.assertEqual(ga.offered("en"), (True, ""))
        self.assertEqual(ga.offered("fr"), (True, ""))
        self.assertTrue(ga.offered("tr")[0], "Turkish has 19% of them: few, and offered")
        ok, why = ga.offered("hi")
        self.assertFalse(ok)
        self.assertIn("almost no words", why)
        ok, why = ga.offered("ja")
        self.assertFalse(ok)
        self.assertIn("no words in this language", why)
        self.assertTrue(ga.offered("nl")[0], "a language nobody measured is offered: it is ARASAAC's")


class Trim(unittest.TestCase):
    def record(self, pid, **kw):
        rec = {"_id": pid, "keywords": [{"keyword": "house", "type": 2, "plural": "houses", "meaning": "a home",
                                         "hasLocution": True}], "schematic": True, "sex": False, "violence": False,
               "aac": True, "aacColor": False, "skin": False, "hair": True, "downloads": 3,
               "categories": ["c"], "tags": ["t"], "synsets": ["03549540-n"], "created": "2009-01-12T10:39:22.000Z",
               "lastUpdated": "2025-10-27T16:03:54.158Z", "desc": ""}
        rec.update(kw)
        return rec

    def test_it_keeps_the_words_and_the_facts_and_nothing_else(self):
        answer = [self.record(6964 + i) for i in range(10)]
        with mock.patch.object(ga, "MIN_RECORDS", 5):
            words, facts = ga.trim(answer)
        self.assertEqual(words[6964], [{"k": "house", "t": 2, "p": "houses", "m": "a home"}])
        fact = facts[6964]
        self.assertEqual(sorted(fact), ["f", "s", "u"])
        self.assertEqual(fact["u"], "2025-10-27T16:03:54.158Z")
        self.assertEqual(fact["s"], ["03549540-n"])
        bits = {name for i, name in enumerate(ga.FLAGS) if fact["f"] >> i & 1}
        self.assertEqual(bits, {"schematic", "aac", "hair"})

    def test_a_pictogram_without_a_word_in_the_language_has_a_fact_and_no_entry(self):
        answer = [self.record(100 + i) for i in range(8)] + [self.record(999, keywords=[])]
        with mock.patch.object(ga, "MIN_RECORDS", 5):
            words, facts = ga.trim(answer)
        self.assertIn(999, facts)
        self.assertNotIn(999, words)

    def test_a_keyword_that_is_empty_or_not_text_is_dropped_and_controls_are_taken_out(self):
        kws = [{"keyword": None}, {"keyword": "  "}, {"keyword": 7}, {"keyword": "a\x00b\x1fc\n d", "type": 99},
               {"keyword": "x" * 1000}, {"keyword": "ok", "plural": None, "meaning": 5}]
        answer = [self.record(100 + i, keywords=kws) for i in range(8)]
        with mock.patch.object(ga, "MIN_RECORDS", 5):
            words, _facts = ga.trim(answer)
        got = words[100]
        self.assertEqual([e["k"][:4] for e in got], ["abc ", "xxxx", "ok"])
        self.assertEqual(got[0]["k"], "abc d")
        self.assertNotIn("t", got[0], "a type that is not one of ARASAAC's is not kept")
        self.assertEqual(len(got[1]["k"]), ga.TEXT_MAX)
        self.assertEqual(got[2], {"k": "ok"})

    def test_a_list_that_is_not_ARASAACs_is_refused_and_not_trimmed_to_nothing(self):
        for bad in ({"error": "x"}, "text", None, [], [self.record(1)] * 3, [{"_id": "6964"}] * 40, [1, 2, 3] * 20):
            with self.assertRaises(ga.ArasaacError, msg=repr(bad)[:60]) as cm:
                ga.trim(bad)
            self.assertEqual(cm.exception.code, "bad-list")

    def test_the_whole_list_of_a_locale_is_kept_at_a_fraction_of_its_size(self):
        # (the answer of the real host is 7.6 MB for English; the shipped table says what is kept)
        kept = ga.MEASURED["locales"]["en"]
        self.assertLess(kept["kept"], kept["raw"] / 3)


class Plan(Tree):
    def test_the_size_is_said_from_the_measured_table_before_anything_is_fetched(self):
        a = ga.plan(("en",), 300)
        m = ga.MEASURED
        self.assertEqual(a["pictures"]["files"], m["pictograms"])
        self.assertEqual(a["pictures"]["bytes"], m["pictograms"] * m["png"][300])
        self.assertEqual(a["download"], m["locales"]["en"]["raw"] + m["pictograms"] * m["png"][300])
        self.assertEqual(a["words"], {"en": {"raw": m["locales"]["en"]["raw"], "kept": m["locales"]["en"]["kept"]}})
        self.assertTrue(a["measured"])
        self.assertEqual(a["have"], 0)
        # 159 MB and 321 MB for the pictures, as the guide says
        self.assertAlmostEqual(a["pictures"]["bytes"] / 1e6, 158.6, delta=0.2)
        self.assertAlmostEqual(ga.plan(("en",), 500)["pictures"]["bytes"] / 1e6, 321.3, delta=0.2)
        # the room it needs at once is the pictures, what is kept of the lists (and of pictograms.json, which
        # the first list makes), and the biggest raw list
        self.assertEqual(a["disk_peak"], a["pictures"]["bytes"] + m["locales"]["en"]["kept"] + m["facts"] + m["locales"]["en"]["raw"])
        self.assertEqual(a["kept"], a["pictures"]["bytes"] + m["locales"]["en"]["kept"] + m["facts"])
        self.assertNotIn(ga.TERMS, json.dumps(a), "a plan is numbers")

    def test_more_languages_cost_their_lists_and_no_more_pictures(self):
        one, two = ga.plan(("en",), 300), ga.plan(("en", "fr"), 300)
        self.assertEqual(two["pictures"], one["pictures"])
        self.assertEqual(two["download"] - one["download"], ga.MEASURED["locales"]["fr"]["raw"])

    def test_a_language_nobody_measured_is_guessed_and_says_so(self):
        a = ga.plan(("en", "nl"), 300)
        self.assertFalse(a["measured"])
        self.assertEqual(a["words"]["nl"], {"raw": ga.GUESS["raw"], "kept": ga.GUESS["kept"]})

    def test_what_is_here_is_not_asked_for_again_and_a_change_of_size_asks_for_all(self):
        self.build(("en",), 300)
        ga.MEASURED["pictograms"]                      # (the table says 13,829: the fake world has 12)
        a = ga.plan(("en",), 300)
        self.assertEqual(a["pictures"]["files"], 0)
        self.assertEqual(a["words"], {})
        self.assertEqual(a["have"], sum(os.path.getsize(self.dir / "pictograms" / ("%d.png" % i)) for i in self.files()))
        self.assertFalse(a["replaces"])
        b = ga.plan(("en",), 500)
        self.assertTrue(b["replaces"], "the pictures are all fetched again at the other size")
        self.assertEqual(b["pictures"]["files"], self.n)
        self.assertEqual(b["have"], 0)

    def test_an_update_promises_the_lists_and_no_pictures(self):
        self.build(("en",), 300)
        a = ga.plan(("en",), 300, update=True)
        self.assertEqual(a["pictures"]["files"], 0)
        self.assertEqual(set(a["words"]), {"en"})

    def test_a_plan_asks_nobody_and_writes_nothing(self):
        before = self.fake.requests[:]
        ga.plan(("en", "fr"), 500)
        self.assertEqual(self.fake.requests, before)
        self.assertFalse(self.dir.exists())

    def test_nothing_starts_that_the_disk_has_no_room_for(self):
        with mock.patch.object(ga, "disk_free", lambda p: 10 * 1000 * 1000):
            answer, status = ga.start(["en"], 300)
        self.assertEqual(status, 507)
        self.assertIn("not enough room", answer["error"])
        self.assertIn("pictograms", answer["error"])
        self.assertFalse(ga.running())
        self.assertFalse(self.dir.exists())
        self.assertEqual(self.fake.requests, [])


class Fresh(Tree):
    def test_every_picture_is_a_png_and_the_index_ids_are_the_files(self):
        self.build(("en", "fr"), 300)
        ids = sorted(self.world.dates)
        self.assertEqual(self.files(), ids)
        for pid in ids:
            data = (self.dir / "pictograms" / ("%d.png" % pid)).read_bytes()
            self.assertTrue(ga.is_png(data), pid)
            self.assertEqual(data, arasaac_fake.png(pid, 300), "the bytes the host sent, whole")
        for loc in ("en", "fr"):
            words = ga.words(loc)
            self.assertEqual(sorted(words), ids, "the index lists the same ids the files are")
            self.assertEqual(words[ids[0]][0]["k"], "%s-word-%d" % (loc, ids[0]))
        self.assertEqual(sorted(ga.facts()), ids)
        self.assertEqual(ga.locales_here(), ["en", "fr"])

    def test_the_manifest_the_licence_and_what_is_left_over(self):
        self.build(("en",), 500)
        m = ga.manifest()
        self.assertEqual((m["format"], m["resolution"], m["complete"], m["pictograms"]), (ga.ARASAAC_FORMAT, 500, True, self.n))
        self.assertEqual(sorted(m["locales"]), ["en"])
        self.assertEqual(m["locales"]["en"]["covered"], self.n)
        self.assertEqual(m["licence"], "CC BY-NC-SA 4.0")
        self.assertTrue(all(not r.get("p") for r in ga.facts().values()), "every picture is confirmed")
        names = sorted(p.name for p in self.dir.iterdir())
        self.assertEqual(names, ["LICENSE-ARASAAC.txt", "index.en.json", "manifest.json", "pictograms", "pictograms.json", "tmp"])
        self.assertEqual(list((self.dir / "tmp").iterdir()), [], "the raw lists are not kept")
        self.assertEqual([p for p in (self.dir / "pictograms").iterdir() if not p.name.endswith(".png")], [])
        self.assertEqual(ga.status()["state"], "installed")
        self.assertTrue(ga.installed())

    def test_the_credit_is_written_word_for_word_beside_the_licence_and_the_terms(self):
        self.build(("en",), 300)
        text = (self.dir / "LICENSE-ARASAAC.txt").read_text(encoding="utf-8")
        for part in (ga.CREDIT, ga.CREDIT_SHORT, "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                     "https://arasaac.org/terms-of-use", "Sergio Palao", "Government of Aragón", "NonCommercial", "ShareAlike"):
            self.assertIn(part, text)
        self.assertIn("Fetched:  %s" % time.strftime("%Y-%m-%d"), text)
        self.assertIn("300 pixels", text)
        # the words the terms page gives, as rendered on 2026-10-02
        self.assertIn("The pictographic symbols used are the property of the Government of Aragón and have been created by "
                      "Sergio Palao for ARASAAC (http://www.arasaac.org), that distributes them under Creative Commons "
                      "License BY-NC-SA.", ga.CREDIT)
        self.assertEqual(ga.CREDIT_SHORT, "Pictograms author: Sergio Palao. Origin: ARASAAC (http://www.arasaac.org). "
                                          "License: CC (BY-NC-SA). Owner: Government of Aragon (Spain)")

    def test_it_is_gentle_one_connection_kept_one_request_at_a_time_and_it_says_who_it_is(self):
        self.n = 12
        self.build(("en",), 300)
        self.assertEqual(self.fake.most_in_flight, 1, "one at a time")
        pictures = self.fake.count(r"/pictograms/\d+/")
        self.assertEqual(pictures, self.n, "each picture once")
        # the lists come through urllib (one connection each); the pictures all on one
        self.assertEqual(self.fake.connections, 1 + 1, "one for the list and ONE for every picture")
        self.assertEqual(self.fake.user_agents, {ga.UA})
        got = {m: h for m, p, h in self.fake.requests if "/pictograms/" in p and "/v1/" not in p}
        self.assertTrue(all(h.get("Accept") == "image/png" for _m, p, h in self.fake.requests if p.startswith("/pictograms/")))
        paths = [p for _m, p, _h in self.fake.requests]
        self.assertTrue(all(re.fullmatch(r"/v1/pictograms/all/en|/pictograms/\d+/\d+_300\.png", p) for p in paths), paths)

    def test_a_second_press_with_everything_here_fetches_nothing(self):
        self.build(("en",), 300)
        asked = len(self.fake.requests)
        self.build(("en",), 300)
        self.assertEqual(len(self.fake.requests), asked)

    def test_adding_a_language_fetches_its_list_and_no_picture(self):
        self.build(("en",), 300)
        before = self.fake.count(r"/pictograms/\d+/")
        self.build(("en", "fr"), 300)
        self.assertEqual(self.fake.count(r"/pictograms/\d+/"), before)
        self.assertEqual(self.fake.count(r"/all/fr"), 1)
        self.assertEqual(ga.locales_here(), ["en", "fr"])
        self.assertEqual(sorted(ga.manifest()["locales"]), ["en", "fr"])

    def test_the_progress_is_the_lists_in_bytes_and_then_the_pictures_by_number(self):
        calls = []
        self.build(("en",), 300, progress=lambda done, total, phase: calls.append((phase, done, total)))
        phases = [c[0] for c in calls]
        self.assertEqual(phases[0], "download", "the list's own bar, in bytes (lib/download.py's word for it)")
        self.assertEqual(phases[-1], "pictures")
        self.assertEqual(calls[-1][1:], (self.n, self.n))
        pic = [c for c in calls if c[0] == "pictures"]
        self.assertEqual([c[2] for c in pic], [self.n] * len(pic))
        self.assertEqual([c[1] for c in pic], sorted(c[1] for c in pic), "it only goes forward")


class Resume(Tree):
    n = 20

    def stop_after(self, k):
        cancel = threading.Event()
        self.fake.after[r"/pictograms/\d+/"] = (k, cancel.set)
        return cancel

    def test_a_stop_keeps_what_came_and_the_next_press_fetches_only_the_rest(self):
        cancel = self.stop_after(8)
        with self.assertRaises(download.Cancelled):
            self.build(("en",), 300, cancel=cancel)
        have = self.files()
        self.assertEqual(len(have), 8, "the eighth was answered and kept: the stop is heard before the ninth is asked for")
        self.assertFalse(ga.manifest()["complete"])
        self.assertEqual(ga.status()["state"], "partial")
        self.assertEqual(ga.status()["pending"], self.n - 8)
        self.assertEqual(ga.locales_here(), ["en"], "the list that came is kept")
        self.fake.after.clear()
        self.fake.requests.clear()
        self.build(("en",), 300)
        self.assertEqual(self.files(), sorted(self.world.dates))
        asked = [int(re.search(r"/(\d+)/", p).group(1)) for _m, p, _h in self.fake.requests if p.startswith("/pictograms/")]
        self.assertEqual(sorted(asked), sorted(set(self.world.dates) - set(have)), "no picture twice, none missed")
        self.assertEqual(self.fake.count(r"/all/"), 0, "the list that was here is not fetched again")
        self.assertTrue(ga.manifest()["complete"])

    def test_a_server_killed_between_two_pictures_leaves_what_the_next_press_can_use(self):
        # a run that died: records written (all pending), some pictures there, a half file, a half list
        self.build(("en",), 300)
        files = self.files()
        for pid in files[10:]:
            os.unlink(self.dir / "pictograms" / ("%d.png" % pid))
        recs = ga.facts()
        for pid in files[10:]:
            recs[pid]["p"] = 1
        ga._save_facts(recs)
        m = ga.manifest()
        m["complete"] = False
        ga._write_json(ga.manifest_path(), m)
        (self.dir / "pictograms" / ("%d.png.part" % files[10])).write_bytes(b"\x89PNG half")
        (self.dir / "tmp" / "all.fr.json").write_text("[{", encoding="utf-8")
        self.fake.requests.clear()
        self.build(("en",), 300)
        self.assertEqual(self.files(), files)
        self.assertEqual(self.fake.count(r"/pictograms/\d+/"), len(files) - 10, "only the missing ones")
        self.assertEqual([p.name for p in (self.dir / "pictograms").iterdir() if p.name.endswith(".part")], [])
        self.assertTrue(ga.manifest()["complete"])

    def test_a_picture_deleted_by_hand_is_fetched_again_and_nothing_else_is(self):
        self.build(("en",), 300)
        gone = self.files()[3]
        os.unlink(self.dir / "pictograms" / ("%d.png" % gone))
        self.fake.requests.clear()
        self.build(("en",), 300)
        self.assertEqual([p for _m, p, _h in self.fake.requests], ["/pictograms/%d/%d_300.png" % (gone, gone)])

    def test_stopped_before_the_first_list_there_is_a_manifest_that_says_it_is_not_whole(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(download.Cancelled):
            self.build(("en",), 300, cancel=cancel)
        self.assertEqual(ga.manifest().get("complete"), False)
        self.assertEqual(self.fake.requests, [])


class Trouble(Tree):
    n = 6

    def test_a_busy_server_is_waited_out_and_its_retry_after_is_obeyed(self):
        pid = sorted(self.world.dates)[2]
        self.world.fail(r"/%d/" % pid, "503-retry", times=2)
        slept = []
        with mock.patch.object(ga, "_sleep", lambda s, c: slept.append(s)):
            self.build(("en",), 300)
        self.assertEqual(self.files(), sorted(self.world.dates))
        self.assertEqual(slept.count(7), 2, "the server's own number of seconds, twice")
        self.assertEqual(self.fake.count(r"/%d/" % pid), 3)

    def test_the_wait_grows_after_an_error_and_the_run_ends_in_a_sentence_when_it_does_not_mend(self):
        pid = sorted(self.world.dates)[1]
        self.world.fail(r"/%d/" % pid, "500", times=99)
        slept = []
        with mock.patch.object(ga, "RETRIES", (2, 5, 15, 40)), mock.patch.object(ga, "_sleep", lambda s, c: slept.append(s)):
            with self.assertRaises(OSError) as cm:
                self.build(("en",), 300)
        self.assertEqual(slept, [2, 5, 15, 40])
        self.assertIn("after 5 tries", str(cm.exception))
        self.assertIn("press it again", str(cm.exception))
        self.assertEqual(self.files(), sorted(self.world.dates)[:1], "what came before is kept")
        self.assertFalse(ga.manifest()["complete"])
        self.assertEqual(ga.status()["pending"], self.n - 1)

    def test_a_connection_that_drops_is_made_again_and_nothing_is_lost(self):
        pid = sorted(self.world.dates)[3]
        self.world.fail(r"/%d/" % pid, "drop", times=1)
        self.build(("en",), 300)
        self.assertEqual(self.files(), sorted(self.world.dates))

    def test_a_picture_cut_short_never_lands_under_its_name_and_is_tried_again(self):
        pid = sorted(self.world.dates)[2]
        self.world.fail(r"/%d/" % pid, "truncate", times=1)
        self.build(("en",), 300)
        data = (self.dir / "pictograms" / ("%d.png" % pid)).read_bytes()
        self.assertEqual(data, arasaac_fake.png(pid, 300))
        self.assertEqual(self.fake.count(r"/%d/" % pid), 2)

    def test_a_body_that_is_not_a_picture_is_never_kept(self):
        pid = sorted(self.world.dates)[0]
        self.world.fail(r"/%d/" % pid, "html", times=99)
        with self.assertRaises(OSError) as cm:
            self.build(("en",), 300)
        self.assertIn("not a whole picture", str(cm.exception))
        self.assertEqual(self.files(), [], "nothing under any name")
        self.assertEqual(list((self.dir / "pictograms").iterdir()) if (self.dir / "pictograms").is_dir() else [], [])

    def test_a_picture_the_host_has_none_of_is_marked_and_not_asked_for_again(self):
        pid = sorted(self.world.dates)[4]
        self.world.no_picture.add(pid)
        self.build(("en",), 300)
        self.assertEqual(self.files(), [i for i in sorted(self.world.dates) if i != pid])
        self.assertEqual(ga.facts()[pid].get("x"), 1)
        self.assertEqual(ga.status()["missing"], 1)
        self.assertEqual(ga.status()["state"], "installed", "one with no picture does not make it unfinished")
        self.fake.requests.clear()
        self.build(("en",), 300)
        self.assertEqual(self.fake.requests, [])
        self.assertTrue(any("1 of them with no picture" in s for s in self.said))

    def test_a_list_that_is_not_ARASAACs_is_refused_and_the_one_here_is_not_touched(self):
        self.build(("en",), 300)
        before = (self.dir / "index.en.json").read_bytes()
        facts_before = (self.dir / "pictograms.json").read_bytes()
        # the next answer is a handful of records: a server's half answer
        small = arasaac_fake.World(1, ("en",))
        with mock.patch.object(ga, "MIN_RECORDS", 5):
            self.fake.world.words["en"] = {k: v for k, v in list(self.world.words["en"].items())[:1]}
            real = self.fake.world.record
            with mock.patch.object(arasaac_fake.World, "record", lambda w, pid, loc: real(pid, loc)):
                for pid in sorted(self.world.dates)[1:]:
                    self.world.drop(pid)
            with self.assertRaises(ga.ArasaacError) as cm:
                self.build(("en",), 300, update=True)
        self.assertEqual(cm.exception.code, "bad-list")
        self.assertEqual((self.dir / "index.en.json").read_bytes(), before)
        self.assertEqual((self.dir / "pictograms.json").read_bytes(), facts_before)
        self.assertEqual(len(self.files()), self.n, "and no picture was let go")

    def test_a_picture_is_written_beside_and_moved_over_never_written_under_its_name(self):
        # A FILE THERE IS A WHOLE ONE (the module's promise): a killed Parseh leaves a .part, never half a picture
        # under a number.  The only way to see it is to watch the rename: the name is free, and what is moved is a .part.
        seen = []
        real = os.replace

        def watch(src, dst):
            if str(dst).endswith(".png"):
                seen.append((os.path.exists(dst), str(src).endswith(".part"), os.path.getsize(src)))
            return real(src, dst)
        with mock.patch.object(os, "replace", watch):
            self.build(("en",), 300)
        self.assertEqual(len(seen), self.n, "every picture arrived by a rename")
        self.assertEqual([s for s in seen if s[0] or not s[1] or s[2] < 64], [], seen)

    def test_a_dead_host_at_update_time_leaves_a_whole_install_whole(self):
        # PRESSING UPDATE WITH NO LINE CHANGES NOTHING: what was installed is still installed, not "part of it"
        self.build(("en",), 300)
        self.assertEqual(ga.status()["state"], "installed")
        self.world.fail(r"/all/en", "500", times=99)
        with self.assertRaises(OSError):
            self.build(("en",), 300, update=True)
        self.assertTrue(ga.manifest()["complete"], "the manifest still says it is whole")
        self.assertEqual(ga.status()["state"], "installed")
        self.assertEqual(self.files(), sorted(self.world.dates))

    def test_a_dead_host_is_said_in_a_sentence_by_the_job_and_nothing_is_raised_on_its_thread(self):
        self.fake.stop()
        with mock.patch.object(ga, "API", "http://127.0.0.1:9/v1"):
            answer, status = ga.start(["en"], 300)
            self.assertEqual((answer["ok"], status), (True, 200))
            self.wait(lambda: not ga.running())
        j = ga.job()
        self.assertTrue(j["error"], j)
        self.assertFalse(j["stopped"])
        self.assertNotIn("Traceback", j["error"])
        self.assertFalse(ga.running())


class Update(Tree):
    n = 10

    def test_an_update_fetches_what_changed_and_asks_before_it_fetches(self):
        self.build(("en",), 300)
        ids = sorted(self.world.dates)
        stamps = {pid: os.path.getmtime(self.dir / "pictograms" / ("%d.png" % pid)) for pid in ids}
        self.assertEqual(stamps[ids[0]], self.world.times[ids[0]], "the file's own time is the server's Last-Modified")
        record_only, picture_too = ids[1], ids[2]
        self.world.touch(record_only)                       # a keyword was mended: the picture is the same
        self.world.touch(picture_too, picture=True)         # and this one was redrawn
        self.world.add(99999)                               # a new pictogram
        gone = ids[3]
        self.world.drop(gone)                               # and one withdrawn
        self.fake.requests.clear()
        self.build(("en",), 300, update=True)
        asked = {p: h for _m, p, h in self.fake.requests if p.startswith("/pictograms/")}
        self.assertEqual(sorted(asked), sorted("/pictograms/%d/%d_300.png" % (i, i) for i in (record_only, picture_too, 99999)),
                         "only the records that moved, and the new one")
        self.assertIn("If-Modified-Since", asked["/pictograms/%d/%d_300.png" % (record_only, record_only)])
        self.assertIn("If-Modified-Since", asked["/pictograms/%d/%d_300.png" % (picture_too, picture_too)])
        self.assertNotIn("If-Modified-Since", asked["/pictograms/99999/99999_300.png"], "a new one is simply asked for")
        self.assertEqual(self.fake.count(r"/all/en"), 1)
        # the one whose picture did not change was told 304 and its file is untouched
        self.assertEqual(os.path.getmtime(self.dir / "pictograms" / ("%d.png" % record_only)), stamps[record_only])
        self.assertEqual(os.path.getmtime(self.dir / "pictograms" / ("%d.png" % picture_too)), self.world.times[picture_too])
        self.assertNotEqual(self.world.times[picture_too], stamps[picture_too])
        self.assertFalse((self.dir / "pictograms" / ("%d.png" % gone)).exists(), "a number ARASAAC no longer lists is let go")
        self.assertNotIn(gone, ga.facts())
        self.assertNotIn(gone, ga.words("en"))
        self.assertIn(99999, ga.facts())
        self.assertEqual(self.files(), sorted((set(ids) - {gone}) | {99999}))
        self.assertEqual(ga.facts()[record_only]["u"], self.world.dates[record_only])
        self.assertTrue(all(not r.get("p") for r in ga.facts().values()))
        self.assertTrue(any("1 new, 2 changed, 1 gone" in s for s in self.said), self.said)
        # and what every other picture had is exactly what it was
        for pid in ids:
            if pid not in (picture_too, gone):
                self.assertEqual(os.path.getmtime(self.dir / "pictograms" / ("%d.png" % pid)), stamps[pid])

    def test_a_list_far_shorter_than_what_is_here_is_a_half_answer_and_changes_nothing(self):
        # SIX OF TEN COME BACK: enough records to be a list (MIN_RECORDS is five here), far too few to be the
        # same set -- a half answer must not let go of four pictures and their words
        self.build(("en",), 300)
        ids = sorted(self.world.dates)
        before = {name: (self.dir / name).read_bytes() for name in ("index.en.json", "pictograms.json", "manifest.json")}
        for pid in ids[:4]:
            self.world.drop(pid)
        with mock.patch.object(ga, "MIN_RECORDS", 5):
            with self.assertRaises(ga.ArasaacError) as cm:
                self.build(("en",), 300, update=True)
        self.assertEqual(cm.exception.code, "bad-list")
        self.assertIn("far fewer", cm.exception.say)
        self.assertIn("Nothing was changed", cm.exception.say)
        for name, data in before.items():
            self.assertEqual((self.dir / name).read_bytes(), data, name + " is as it was")
        self.assertEqual(self.files(), ids, "and no picture was let go")
        self.assertEqual(ga.status()["state"], "installed")

    def test_an_update_with_nothing_changed_asks_for_the_lists_and_nothing_else(self):
        self.build(("en", "fr"), 300)
        self.fake.requests.clear()
        self.build(("en", "fr"), 300, update=True)
        self.assertEqual(sorted(p for _m, p, _h in self.fake.requests), ["/v1/pictograms/all/en", "/v1/pictograms/all/fr"])

    def test_an_update_stopped_half_way_carries_on_with_what_is_left(self):
        self.build(("en",), 300)
        ids = sorted(self.world.dates)
        for pid in ids:
            self.world.touch(pid, picture=True)
        cancel = threading.Event()
        self.fake.after[r"/pictograms/\d+/"] = (4, cancel.set)
        self.fake.requests.clear()
        with self.assertRaises(download.Cancelled):
            self.build(("en",), 300, update=True, cancel=cancel)
        self.assertEqual(ga.status()["pending"], self.n - 4)
        self.fake.after.clear()
        self.fake.requests.clear()
        self.build(("en",), 300, update=True)
        self.assertEqual(self.fake.count(r"/pictograms/\d+/"), self.n - 4, "only the ones it had not got to")
        for pid in ids:
            self.assertEqual(os.path.getmtime(self.dir / "pictograms" / ("%d.png" % pid)), self.world.times[pid])

    def test_a_pictogram_that_had_no_picture_is_looked_for_again_when_its_record_moves(self):
        pid = sorted(self.world.dates)[2]
        self.world.no_picture.add(pid)
        self.build(("en",), 300)
        self.assertEqual(ga.facts()[pid].get("x"), 1)
        self.world.no_picture.discard(pid)
        self.world.touch(pid)
        self.build(("en",), 300, update=True)
        self.assertNotIn("x", ga.facts()[pid])
        self.assertIn(pid, self.files())

    def test_a_change_of_size_takes_the_old_pictures_away_first_and_fetches_every_one_again(self):
        self.build(("en",), 300)
        before = (self.dir / "pictograms" / ("%d.png" % self.files()[0])).read_bytes()
        cancel = threading.Event()
        self.fake.requests.clear()
        self.fake.after[r"/pictograms/\d+/"] = (3, cancel.set)
        with self.assertRaises(download.Cancelled):
            self.build(("en",), 500, cancel=cancel)
        self.assertEqual(ga.manifest()["resolution"], 500, "the record is true the moment it is changed")
        self.assertEqual(len(self.files()), 3, "none of the 300 pixel pictures is left beside the 500 ones")
        for pid in self.files():
            self.assertEqual((self.dir / "pictograms" / ("%d.png" % pid)).read_bytes(), arasaac_fake.png(pid, 500))
        self.fake.after.clear()
        self.build(("en",), 500)
        self.assertEqual(self.files(), sorted(self.world.dates))
        self.assertNotEqual((self.dir / "pictograms" / ("%d.png" % self.files()[0])).read_bytes(), before)
        self.assertEqual(ga.status()["resolution"], 500)


class Remove(Tree):
    def test_one_language_goes_and_the_pictures_stay(self):
        self.build(("en", "fr"), 300)
        ga.remove("fr")
        self.assertEqual(ga.locales_here(), ["en"])
        self.assertEqual(sorted(ga.manifest()["locales"]), ["en"])
        self.assertEqual(self.files(), sorted(self.world.dates))
        self.assertEqual(ga.status()["state"], "installed")

    def test_everything_goes_with_the_folder(self):
        self.build(("en",), 300)
        ga.remove()
        self.assertFalse(self.dir.exists())
        self.assertEqual(ga.status()["state"], "absent")
        self.assertFalse(ga.installed())

    def test_nothing_is_removed_while_it_is_being_fetched(self):
        self.world.delay = 0.05
        answer, status = ga.start(["en"], 300)
        self.assertEqual(status, 200)
        self.wait(lambda: self.fake.count(r"/pictograms/\d+/") >= 2)
        with self.assertRaises(ga.ArasaacError) as cm:
            ga.remove()
        self.assertEqual(cm.exception.code, "busy")
        self.assertTrue(self.dir.exists())
        self.assertTrue(ga.stop())
        self.wait(lambda: not ga.running())

    def test_a_name_that_is_not_a_language_is_never_a_path_to_remove(self):
        self.build(("en",), 300)
        for bad in ("../arasaac", "", "ja", None):
            with self.assertRaises(ga.ArasaacError):
                ga.remove(bad) if bad is not None else ga.index_path(None)
        self.assertTrue(self.dir.exists())

    def test_an_absent_folder_is_read_as_nothing_and_never_made_by_looking(self):
        self.assertEqual(ga.status()["state"], "absent")
        self.assertEqual((ga.locales_here(), ga.facts(), ga.words("en"), ga.pictures_here()), ([], {}, {}, (0, 0)))
        ga.remove()
        self.assertFalse(self.dir.exists())


class Job(Tree):
    n = 14

    def test_a_job_runs_on_a_thread_says_how_far_and_ends_in_done(self):
        self.world.delay = 0.02
        answer, status = ga.start(["en", "fr"], 300)
        self.assertEqual((answer, status), ({"ok": True}, 200))
        self.wait(lambda: ga.job().get("phase") == "pictures" and ga.job().get("done", 0) >= 3)
        j = ga.job()
        self.assertTrue(j["running"])
        self.assertEqual((j["total"], j["resolution"], j["locales"]), (self.n, 300, ["en", "fr"]))
        again, status = ga.start(["en"], 300)
        self.assertEqual((again, status), ({"ok": True, "already": True}, 200), "the same job: not a second one")
        self.wait(lambda: not ga.running())
        j = ga.job()
        self.assertEqual((j["error"], j["stopped"], j["say"]), ("", False, "done"))
        self.assertEqual(j["fetched"], self.n)
        self.assertIsNotNone(j["finished"])
        self.assertEqual(ga.status()["state"], "installed")

    def test_a_job_that_ends_while_the_folder_is_read_is_not_said_over_beside_what_the_folder_held_before(self):
        # The page stops asking once it has been told the job is over.  An answer that said "over" beside the manifest
        # as it was BEFORE the job's last write ("partial") was the last it drew: "Part of it is here" for good, on a
        # computer on which counting the folder took long enough for a job to end in the middle of it
        self.build(("en",), 300)
        ga._note(running=True, finished=None, say="x")           # an update is running ...
        read = ga.manifest

        def manifest_and_then_the_job_ends():
            got = read()
            ga._note(running=False, finished=time.time(), say="done")     # ... and ends just after the manifest is read
            return got
        with mock.patch.object(ga, "manifest", manifest_and_then_the_job_ends):
            answer = ga.status()
        self.assertFalse(ga.running())
        self.assertTrue(answer["job"]["running"],
                        "the job was running when the answer began: it is said to be, and the page asks again")
        self.assertFalse(ga.status()["job"]["running"], "and the next answer says it is over, with the folder as it ends")
        self.assertEqual(ga.status()["state"], "installed")

    def test_stop_ends_the_job_as_stopped_and_not_as_failed(self):
        self.world.delay = 0.05
        ga.start(["en"], 300)
        self.wait(lambda: self.fake.count(r"/pictograms/\d+/") >= 3)
        self.assertTrue(ga.stop())
        self.wait(lambda: not ga.running())
        j = ga.job()
        self.assertTrue(j["stopped"])
        self.assertEqual(j["error"], "")
        self.assertFalse(ga.stop(), "nothing is running to be stopped")
        self.assertEqual(ga.status()["state"], "partial")
        # and Carry on is the same call
        self.world.delay = 0
        ga.start(["en"], 300)
        self.wait(lambda: not ga.running())
        self.assertEqual(ga.status()["state"], "installed")

    def test_a_request_that_is_not_ARASAACs_to_ask_for_is_refused_before_anything_starts(self):
        for body, why in ((["ja"], "bad-language"), (["hi"], "not-offered"), ("en", "bad-language"), ([], "no-language"),
                          (["en/../x"], "bad-language")):
            answer, status = ga.start(body, 300)
            self.assertEqual((answer["ok"], status, answer["code"]), (False, 400, why), body)
        answer, status = ga.start(["en"], 2500)
        self.assertEqual((answer["code"], status), ("bad-size", 400))
        self.assertEqual(self.fake.requests, [])
        self.assertFalse(self.dir.exists())

    def test_the_activity_list_hears_of_it(self):
        entry = lambda *a, **k: dict(zip(("id", "kind", "label", "started"), a), **k)       # noqa: E731
        self.assertEqual(ga.activity_entries(entry, 60), [])
        self.build(("en",), 300)
        ga._note(started=time.time(), running=True, say="x", done=3, total=9)
        got = ga.activity_entries(entry, 60)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["kind"], got[0]["label"], got[0]["page"]), ("lookup", "Getting the ARASAAC pictograms", "/settings/arasaac/"))
        self.assertEqual((got[0]["done"], got[0]["total"]), (3, 9))
        ga._note(running=False, finished=time.time() - 3600, error="")
        self.assertEqual(ga.activity_entries(entry, 60), [], "a job long over is not on the list")
        ga._note(finished=time.time())
        self.assertEqual(ga.activity_entries(entry, 60)[0]["ok"], True)

    def test_the_command_line_is_a_developers_way_and_does_what_the_page_does(self):
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(ga.main(["get", "en", "--500"]), 0)
            self.assertEqual(ga.main(["status"]), 0)
        self.assertEqual(ga.manifest()["resolution"], 500)
        self.assertIn('"state": "installed"', out.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ga.main(["remove", "en"]), 0)
        self.assertEqual(ga.locales_here(), [])


if __name__ == "__main__":
    unittest.main()
