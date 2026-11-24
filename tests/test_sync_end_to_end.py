#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Two REAL installs, paired over real TLS, syncing through the real exchange.

Lane A (pairing, transport) was tested with a dummy op and lane B (the
exchange) through an in-process fake of the transport.  This is the two
together, with nothing faked: each install is a serve.py process in its own
temporary tree (tests/sync_harness.py), they pair through the Settings ->
Devices routes, and a change made through an ordinary page route on one --
a studio document, the theme -- must arrive on the other by itself: the
change's debounce, the pull, the nudge that makes the partner pull back.
And back the other way: an edit on B reaches A, A's old version kept for a day.
"""
import glob
import http.client
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_sync_pairing import Install  # noqa: E402

WAIT = 60          # seconds for a change to travel: a 5 s debounce, a pull, a nudge


def ask(inst, method, route, body=None):
    c = http.client.HTTPConnection("127.0.0.1", inst.port, timeout=30)
    try:
        origin = "http://localhost:%d" % inst.port
        c.request(method, route, body=json.dumps(body) if body is not None else None,
                  headers={"Content-Type": "application/json", "Origin": origin,
                           "Referer": origin + "/", "Host": "localhost:%d" % inst.port})
        r = c.getresponse()
        raw = r.read()
        try:
            return r.status, json.loads(raw or b"{}")
        except ValueError:
            return r.status, raw[:200]
    finally:
        c.close()


def sources(inst):
    return sorted(glob.glob(os.path.join(inst.tree, "library", "*", "*", "source.md")))


def until(what, test):
    end = time.time() + WAIT
    while time.time() < end:
        got = test()
        if got:
            return got
        time.sleep(0.5)
    raise AssertionError("waited %d s: %s" % (WAIT, what))


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="sync-e2e-")
        cls.A = Install(cls.base, "A")
        cls.B = Install(cls.base, "B")
        try:
            cls.A.wait()
            cls.B.wait()
            st, offer = cls.A.dev("pair-start")
            assert st == 200, offer
            st, out = cls.B.dev("pair-enter", {"code": offer["said"], "address": "127.0.0.1:%d" % cls.A.port,
                                               "fingerprint": offer["fingerprint"]})
            assert st == 200, out
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for i in (getattr(cls, "A", None), getattr(cls, "B", None)):
            if i:
                i.stop()
        if os.environ.get("KEEP_SYNC_E2E"):
            print("trees kept in", cls.base)
        else:
            shutil.rmtree(cls.base, ignore_errors=True)

    def test_1_a_document_made_on_A_arrives_on_B_and_an_edit_on_B_comes_back(self):
        md = "---\ntitle: Sync by itself\nlanguage: italian\n---\n\n# Sync by itself\n\nUna frase.\n"
        st, out = ask(self.A, "POST", "/studio/api/docs", {"markdown": md})
        self.assertIn(st, (200, 201), out)
        made = sources(self.A)
        self.assertEqual(len(made), 1, made)
        rel = os.path.relpath(made[0], self.A.tree)
        there = os.path.join(self.B.tree, rel)
        until("the document on B", lambda: os.path.isfile(there))
        with open(there, encoding="utf-8") as f, open(made[0], encoding="utf-8") as g:
            self.assertEqual(f.read(), g.read())
        # an edit on B, through B's own route, comes back to A
        doc_id = os.path.basename(os.path.dirname(there))
        edited = md.replace("Una frase.", "Una frase, cambiata su B.")
        st, out = ask(self.B, "PUT", "/studio/api/docs/%s" % doc_id, {"markdown": edited})
        if st == 405:
            st, out = ask(self.B, "POST", "/studio/api/docs/%s" % doc_id, {"markdown": edited})
        self.assertEqual(st, 200, out)

        def back():
            with open(made[0], encoding="utf-8") as f:
                return "cambiata su B" in f.read()
        until("B's edit on A", back)
        kept = glob.glob(os.path.join(self.A.tree, "config", "sync", "kept", "**"), recursive=True)
        self.assertTrue([k for k in kept if os.path.isfile(k)], "A's old version is kept for a day")

    def test_2_a_setting_changed_on_A_arrives_on_B(self):
        st, out = ask(self.A, "POST", "/__prefs", {"settings": {"parseh_theme": {"v": "dark"}}, "by": "e2e"})
        self.assertEqual(st, 200, out)

        def theme():
            try:
                with open(os.path.join(self.B.tree, "config", "prefs.json"), encoding="utf-8") as f:
                    return json.load(f).get("settings", {}).get("parseh_theme", {}).get("v") == "dark"
            except (OSError, ValueError):
                return False
        until("the theme on B", theme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
