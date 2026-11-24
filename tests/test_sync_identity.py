# SPDX-License-Identifier: GPL-3.0-or-later
"""A copied install, what a device says of itself, and a removal told (a0.7.0, lane H).

UNIT (one temporary tree, tests/synctree.py):
  * the identity notes the machine it was made on; another machine -> copied();
    "the same computer" takes the notice away; reset keeps the name and what the
    device says of itself; an identity made before the machine was noted gets it
  * what a device says of itself: False on a computer, set_device, kept per partner
  * remove_telling: an unreachable partner is removed here all the same and the
    answer says it was not told; one that removed this computer is not asked
  * new_identity empties the partners and throws a shown code away

REAL (three serve.py processes, tests/sync_harness.py, as tests/test_sync_pairing.py):
  * B says "send only" and "holds little": A sees it after pairing, and in hello
  * A copied whole to another "machine" (C): C's Devices state says it is a copy;
    pairing C with A is refused as "this very computer"; C's new identity empties
    its partners and C then pairs with A
  * A removes B: B is told, shows A as "removed you" and keeps it until B removes it
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from synctree import SyncTree                   # noqa: E402
import prefs                                    # noqa: E402
import syncid                                   # noqa: E402
import synclog                                  # noqa: E402
import syncpeer                                 # noqa: E402
import syncroutes                               # noqa: E402
from test_sync_pairing import Install, free_port  # noqa: E402


def fake_partner(pid, name, **more):
    rec = {"id": pid, "name": name, "cert": "", "fingerprint": "ab" * 32, "protocol": 1,
           "addresses": ["127.0.0.1:9"], "last_ok": None, "paired": time.time(), "last_seen": None}
    rec.update(more)
    syncpeer._keep(rec)


class Units(SyncTree):
    def setUp(self):
        super().setUp()
        syncid.MINTER = syncid._mint_openssl

    def tearDown(self):
        syncid.MINTER = None
        syncid.MACHINE = None
        syncpeer.stop_offer()
        syncpeer._SEEN.clear()
        syncpeer._CTX["key"] = None
        super().tearDown()

    def test_a_copy_is_told_by_its_machine_and_never_reset_by_itself(self):
        doc = syncid.ensure()
        self.assertEqual(doc["machine"]["id"], syncid.machine()[0])
        self.assertIsNone(syncid.copied())
        syncid.MACHINE = lambda: ("f" * 64, "laptop")
        self.assertEqual(syncid.copied(), {"made_on": syncid.default_name(), "here": "laptop"})
        self.assertEqual(syncid.identity()["install"], doc["install"], "nothing changed by itself")
        syncid.same_computer()
        self.assertIsNone(syncid.copied())
        self.assertEqual(syncid.identity()["install"], doc["install"])

    def test_reset_keeps_the_name_and_the_device_and_takes_this_machine(self):
        syncid.ensure()
        syncid.set_name("Desk")
        syncid.set_device(holds_little=True)
        syncid.MACHINE = lambda: ("e" * 64, "laptop")
        old = syncid.install_id()
        new = syncid.reset()
        self.assertNotEqual(new["install"], old)
        self.assertEqual(new["name"], "Desk")
        self.assertEqual(syncid.device(), {"send_only": False, "holds_little": True})
        self.assertEqual(new["machine"], {"id": "e" * 64, "host": "laptop"})
        self.assertIsNone(syncid.copied())

    def test_an_identity_from_before_gets_its_machine_at_start(self):
        doc = syncid.identity()
        doc.pop("protocol")
        doc.pop("machine")
        syncid._write(doc)
        self.assertIsNone(syncid.copied(), "no machine noted: not called a copy")
        syncid.ensure()
        self.assertEqual(syncid.identity()["machine"]["id"], syncid.machine()[0])

    def test_what_a_device_says_of_itself(self):
        self.assertEqual(syncid.device(), {"send_only": False, "holds_little": False})
        self.assertEqual(syncid.set_device(send_only=True), {"send_only": True, "holds_little": False})
        with self.assertRaises(ValueError):
            syncid.set_device(tiny=True)
        self.assertEqual(syncpeer._me()["device"], {"send_only": True, "holds_little": False})
        fake_partner("a" * 32, "phone")
        self.assertEqual(syncpeer.partners()[0]["device"], {"send_only": False, "holds_little": False})
        syncpeer.note_device("a" * 32, {"holds_little": True, "send_only": "yes"})
        self.assertEqual(syncpeer.partners()[0]["device"], {"send_only": False, "holds_little": True},
                         "only a true True counts")
        # the hello op answers it, and keeps what the caller says
        out, _ = syncroutes._hello("a" * 32, {"device": {"send_only": True}}, None)
        self.assertEqual(out["device"], {"send_only": True, "holds_little": False})
        self.assertEqual(syncpeer.partners()[0]["device"], {"send_only": True, "holds_little": False})

    def test_removing_an_unreachable_partner_says_it_was_not_told(self):
        fake_partner("b" * 32, "laptop")
        t0 = time.monotonic()
        out = syncpeer.remove_telling("b" * 32, timeout=2)
        self.assertLess(time.monotonic() - t0, 5)
        self.assertEqual((out["removed"], out["told"]), (True, False))
        self.assertIn("laptop did not answer", out["why"])
        self.assertEqual(syncpeer.partners(), [])
        self.assertEqual(syncpeer.remove_telling("b" * 32)["removed"], False)

    def test_told_it_was_removed_marks_it_and_keeps_it(self):
        fake_partner("c" * 32, "desk")
        out, _ = syncroutes._removed("c" * 32, {"name": "Desk  upstairs"}, None)
        self.assertTrue(out["ok"])
        p = syncpeer.partners()[0]
        self.assertEqual(p["removed_you"]["by"], "Desk upstairs")
        # removing it here too does not call it back
        called = []
        real = syncpeer.call
        syncpeer.call = lambda *a, **k: called.append(a)
        try:
            out = syncpeer.remove_telling("c" * 32)
        finally:
            syncpeer.call = real
        self.assertEqual((out["removed"], out["told"], called), (True, None, []))

    def test_new_identity_empties_the_partners_and_the_code(self):
        syncid.ensure()
        old = syncid.install_id()
        fake_partner("d" * 32, "desk")
        fake_partner("e" * 32, "laptop")
        syncpeer.code(fresh=True)
        self.assertTrue(syncpeer.code_live())
        out = syncpeer.new_identity()
        self.assertEqual(out["forgot"], 2)
        self.assertNotEqual(out["install"], old)
        self.assertEqual(syncpeer.partners(), [])
        self.assertFalse(syncpeer.code_live())
        self.assertTrue(syncid.identity()["key"])


class Installs(unittest.TestCase):
    """Three whole installs; the tests run in order (test_1 ... test_4)."""

    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="sync-identity-")
        cls.old_store, cls.old_home = prefs.STORE, synclog.HOME
        cls.A = Install(cls.base, "A", {"SYNC_MACHINE": "aaaa:desk"})
        cls.B = Install(cls.base, "B", {"SYNC_DEVICE": '{"send_only": true, "holds_little": true}'})
        cls.C = None
        try:
            cls.a = cls.A.wait()["this"]
            cls.b = cls.B.wait()["this"]
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for i in (getattr(cls, "A", None), getattr(cls, "B", None), getattr(cls, "C", None)):
            if i:
                i.stop()
        prefs.STORE, synclog.HOME = cls.old_store, cls.old_home
        syncpeer._CTX["key"] = None
        shutil.rmtree(cls.base, ignore_errors=True)

    def be(self, tree):
        prefs.STORE = os.path.join(tree, "config", "prefs.json")
        synclog.HOME = None
        syncpeer._CTX["key"] = None

    def at(self, inst):
        return "127.0.0.1:%d" % inst.port

    def pair(self, shows, types):
        st, offer = shows.dev("pair-start")
        self.assertEqual(st, 200, offer)
        return types.dev("pair-enter", {"code": offer["said"], "address": self.at(shows)})

    def restart(self, name, tree, port, env):
        """An install on a tree that is already there (a copy, or the original again)."""
        i = Install.__new__(Install)
        i.tree, i.port = tree, port
        i.log = open(os.path.join(self.base, name + ".log"), "w")
        i.proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "sync_harness.py"), "serve", tree, str(port)],
            stdout=i.log, stderr=subprocess.STDOUT, env=dict(os.environ, **env))
        return i

    def test_1_what_a_device_says_of_itself_reaches_its_partner(self):
        st, out = self.pair(self.A, self.B)
        self.assertEqual(st, 200, out)
        self.assertEqual(out["partner"]["device"], {"send_only": False, "holds_little": False})
        pa = self.A.dev("state")[1]["partners"]
        self.assertEqual(pa[0]["device"], {"send_only": True, "holds_little": True}, "B said it at pairing")
        self.assertIsNone(self.A.dev("state")[1]["this"]["copied"])
        # and in hello, both ways: A asks B, from A's own tree
        self.be(self.A.tree)
        out = syncpeer.hello(self.b["install"], timeout=10)
        self.assertEqual(out["device"], {"send_only": True, "holds_little": True})

    def test_2_a_copy_is_told_refused_as_itself_and_given_its_own_identity(self):
        cls = type(self)
        cls.A.stop()
        copy = os.path.join(self.base, "C")
        shutil.copytree(self.A.tree, copy, symlinks=True)
        cls.A = self.restart("A2", self.A.tree, self.A.port, {"SYNC_MACHINE": "aaaa:desk"})
        cls.C = self.restart("C", copy, free_port(), {"SYNC_MACHINE": "cccc:laptop"})
        self.assertIsNone(self.A.wait()["this"]["copied"], "the original is not a copy")
        c = self.C.wait()["this"]
        self.assertEqual(c["install"], self.a["install"], "a copy carries the original's id")
        self.assertEqual(c["copied"], {"made_on": "desk", "here": "laptop"})
        st, out = self.pair(self.A, self.C)
        self.assertEqual(st, 409)
        self.assertIn("that is this very computer (or a copy of it", out["error"])
        self.A.dev("pair-stop")
        st, out = self.C.dev("new-identity")
        self.assertEqual(st, 200, out)
        self.assertEqual(out["forgot"], 1, "B, the original's partner, is off the copy's list")
        c2 = self.C.dev("state")[1]
        self.assertNotEqual(c2["this"]["install"], self.a["install"])
        self.assertNotEqual(c2["this"]["fingerprint"], self.a["fingerprint"])
        self.assertIsNone(c2["this"]["copied"])
        self.assertEqual(c2["partners"], [])
        st, out = self.pair(self.A, self.C)
        self.assertEqual(st, 200, out)
        self.assertEqual(out["partner"]["id"], self.a["install"])
        ids = sorted(p["id"] for p in self.A.dev("state")[1]["partners"])
        self.assertEqual(ids, sorted([self.b["install"], c2["this"]["install"]]),
                         "the original keeps B and now has the copy as a partner of its own")

    def test_3_a_partner_removed_is_told_and_shows_it(self):
        st, out = self.A.dev("remove", {"id": self.b["install"]})
        self.assertEqual(st, 200, out)
        self.assertEqual((out["removed"], out["told"]), (True, True), out)
        pb = self.B.dev("state")[1]["partners"]
        self.assertEqual([p["id"] for p in pb], [self.a["install"]], "B keeps A until B removes it")
        self.assertEqual(pb[0]["removed_you"]["by"], self.a["name"])
        st, out = self.B.dev("remove", {"id": self.a["install"]})
        self.assertEqual((out["removed"], out["told"]), (True, None), "not asked: it removed B already")
        self.assertEqual(self.B.dev("state")[1]["partners"], [])

    def test_4_a_partner_that_does_not_answer_is_removed_here_all_the_same(self):
        os.kill(self.C.proc.pid, 19)            # SIGSTOP: silence, as a sleeping laptop
        try:
            pa = self.A.dev("state")[1]["partners"]
            cid = pa[0]["id"]
            t0 = time.monotonic()
            st, out = self.A.dev("remove", {"id": cid})
            self.assertLess(time.monotonic() - t0, syncpeer.TELL_WAIT + 4)
            self.assertEqual((out["removed"], out["told"]), (True, False), out)
            self.assertIn("did not answer", out["why"])
            self.assertEqual(self.A.dev("state")[1]["partners"], [])
        finally:
            os.kill(self.C.proc.pid, 18)        # SIGCONT


if __name__ == "__main__":
    unittest.main()
