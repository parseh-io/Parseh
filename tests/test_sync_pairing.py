# SPDX-License-Identifier: GPL-3.0-or-later
"""Pairing and transport between two whole installs (a0.7.0, lane A).

Two REAL serve.py processes (tests/sync_harness.py), each in a temporary tree
of its own and on a port of its own, speaking real TLS to each other:

  * pairing driven through Settings -> Devices' JSON routes, as the page will;
  * a wrong code eight times, a code run out, a protocol spoken by nobody here;
  * a stranger's certificate refused at the handshake, a call with no
    certificate refused, /sync/ refused to a browser's connection;
  * a dummy op (`echo`) round-trip with a body, through syncpeer.call;
  * a partner frozen with SIGSTOP: Unreachable within the call's deadline;
  * a partner removed: refused from then on.

The calling side of syncpeer.call runs in THIS process on install B's own tree
(prefs.STORE pointed at it, so B's identity and peers.json are what it reads):
the real HTTP/TLS path, with B's real keys.  Never the checkout's config/.
"""
import http.client
import json
import os
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIB = os.path.join(ROOT, "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import network          # noqa: E402
import prefs            # noqa: E402
import syncid           # noqa: E402
import synclog          # noqa: E402
import syncpeer         # noqa: E402

LIFE_A = 8              # install A's pairing code lives this many seconds (SYNC_CODE_LIFE)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Install:
    def __init__(self, base, name, env=None, port=None):
        self.tree = os.path.join(base, name)
        os.makedirs(self.tree, exist_ok=True)       # a test may write its config/ first
        self.port = port or free_port()
        self.log = open(os.path.join(base, name + ".log"), "w")
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "sync_harness.py"), "serve", self.tree, str(self.port)],
            stdout=self.log, stderr=subprocess.STDOUT, env=dict(os.environ, **(env or {})))

    def post(self, route, body=None, timeout=30):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            c.request("POST", route, body=json.dumps(body or {}),
                      headers={"Content-Type": "application/json"})
            r = c.getresponse()
            return r.status, json.loads(r.read() or b"{}")
        finally:
            c.close()

    def post_get(self, route, timeout=30):
        """A page, as GET (the name says it is this harness's other verb)."""
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            c.request("GET", route)
            return c.getresponse().read().decode("utf-8")
        finally:
            c.close()

    def dev(self, what, body=None):
        return self.post("/settings/api/devices/" + what, body)

    def wait(self):
        end = time.time() + 90
        while time.time() < end:
            if self.proc.poll() is not None:
                raise RuntimeError("%s stopped: see %s" % (self.tree, self.log.name))
            try:
                st, doc = self.dev("state")
                if st == 200 and doc["this"]["key"]:
                    return doc
            except (OSError, ValueError, http.client.HTTPException):
                pass
            time.sleep(0.3)
        raise RuntimeError("%s never came up" % self.tree)

    def stop(self):
        try:
            os.kill(self.proc.pid, signal.SIGCONT)
        except OSError:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()


class Pairing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="sync-pairing-")
        cls.old_store, cls.old_home, cls.old_net = prefs.STORE, synclog.HOME, network.STORE
        cls.A = Install(cls.base, "A", {"SYNC_CODE_LIFE": str(LIFE_A)})
        cls.B = Install(cls.base, "B")
        try:
            cls.a = cls.A.wait()["this"]
            cls.b = cls.B.wait()["this"]
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for i in (getattr(cls, "A", None), getattr(cls, "B", None)):
            if i:
                i.stop()
        prefs.STORE, synclog.HOME = cls.old_store, cls.old_home
        network.STORE = cls.old_net
        syncpeer._PROTOCOL_TEST = None
        shutil.rmtree(cls.base, ignore_errors=True)

    def tearDown(self):
        syncpeer._PROTOCOL_TEST = None

    def be(self, tree):
        """Calls from this process are made as the install whose tree this is."""
        prefs.STORE = os.path.join(tree, "config", "prefs.json")
        network.STORE = os.path.join(tree, "config", "network.json")   # pairing opens the third door there
        synclog.HOME = None
        syncpeer._CTX["key"] = None

    def at(self, inst):
        return "127.0.0.1:%d" % inst.port

    # ------------------------------------------------------------- pairing
    def test_1_a_wrong_code_eight_times_throws_it_away(self):
        st, offer = self.A.dev("pair-start")
        self.assertEqual(st, 200, offer)
        self.assertEqual(len(offer["code"]), 6)
        self.assertIn("parseh-pair:1?code=%s&fp=%s" % (offer["code"], self.a["fingerprint"]), offer["qr"])
        wrong = "ZZZZZZ" if offer["code"] != "ZZZZZZ" else "YYYYYY"
        for n in range(1, 8):
            st, out = self.B.dev("pair-enter", {"code": wrong, "address": self.at(self.A)})
            self.assertEqual(st, 409, out)
            self.assertIn("wrong (%d tries left)" % (8 - n), out["error"])
        st, out = self.B.dev("pair-enter", {"code": wrong, "address": self.at(self.A)})
        self.assertIn("tried too often", out["error"])
        # thrown away: even the right one is no good now
        st, out = self.B.dev("pair-enter", {"code": offer["code"], "address": self.at(self.A)})
        self.assertEqual(st, 409)
        self.assertIn("run out", out["error"])
        self.assertEqual(self.A.dev("state")[1]["partners"], [])

    def test_2_a_code_that_ran_out(self):
        st, offer = self.A.dev("pair-start")
        time.sleep(LIFE_A + 1)
        st, out = self.B.dev("pair-enter", {"code": offer["said"], "address": self.at(self.A)})
        self.assertEqual(st, 409, out)
        self.assertIn("run out", out["error"])

    def test_3_another_protocol_is_told_so_in_words(self):
        c = os.path.join(self.base, "C-proto")
        os.makedirs(os.path.join(c, "config"))
        self.be(c)
        syncid.ensure()
        st, offer = self.A.dev("pair-start")
        syncpeer._PROTOCOL_TEST = 2
        with self.assertRaises(syncpeer.Refused) as cm:
            syncpeer.pair_with(self.at(self.A), offer["code"], timeout=10)
        said = cm.exception.reason
        self.assertIn("version 1 of the sync protocol", said)
        self.assertIn("version 2", said)
        self.assertIn("Update", said)
        syncpeer._PROTOCOL_TEST = None
        self.assertEqual(syncpeer.partners(), [])
        # the code was not spent by a partner it could never sync with
        self.assertTrue(self.A.dev("state")[1]["pairing"] > 0)

    def test_4_pairing_both_ways(self):
        st, offer = self.A.dev("pair-start")
        self.assertEqual(st, 200)
        st, out = self.B.dev("pair-enter", {"code": offer["said"].lower(), "address": self.at(self.A),
                                            "fingerprint": offer["fingerprint"]})
        self.assertEqual(st, 200, out)
        self.assertEqual(out["partner"]["id"], self.a["install"])
        self.assertEqual(out["partner"]["fingerprint"], self.a["fingerprint"])
        self.assertEqual(out["partner"]["last_ok"], self.at(self.A))
        pa = self.A.dev("state")[1]
        self.assertEqual([p["id"] for p in pa["partners"]], [self.b["install"]])
        self.assertEqual(pa["partners"][0]["fingerprint"], self.b["fingerprint"])
        self.assertIn(self.at(self.B), pa["partners"][0]["addresses"])
        self.assertEqual(pa["pairing"], 0, "the code is spent when used")
        # both config/peers.json, in each tree, and nothing in the checkout
        for t in (self.A.tree, self.B.tree):
            self.assertTrue(os.path.isfile(os.path.join(t, "config", "peers.json")))
        # rename: the name this install gives itself
        st, out = self.B.dev("rename", {"name": "  laptop  "})
        self.assertEqual(out["name"], "laptop")

    def test_5_an_op_round_trip_with_a_body_both_ways(self):
        self.be(self.B.tree)
        blob = os.urandom(300_000) + b"\x00end"
        t = time.monotonic()
        out, body = syncpeer.call(self.a["install"], "echo", {"x": "سلام", "n": 3}, body=blob, timeout=10)
        self.assertLess(time.monotonic() - t, 10)
        self.assertEqual(out["payload"], {"x": "سلام", "n": 3})
        self.assertEqual(out["partner"], self.b["install"])
        self.assertEqual(body, blob)
        out, body = syncpeer.call(self.a["install"], "hello", {}, timeout=10)
        self.assertEqual(out["install"], self.a["install"])
        self.assertIsNone(body)
        p = [p for p in syncpeer.partners() if p["id"] == self.a["install"]][0]
        self.assertTrue(p["reachable"])
        self.assertTrue(p["last_seen"])
        # an op nobody registered is said in words
        with self.assertRaises(syncpeer.Refused) as cm:
            syncpeer.call(self.a["install"], "nosuchstep", {}, timeout=10)
        self.assertIn("does not know the sync step", cm.exception.reason)
        # and the other way: A calls B
        self.be(self.A.tree)
        out, body = syncpeer.call(self.b["install"], "echo", {"back": True}, body=b"abc", timeout=10)
        self.assertEqual((out["payload"], body), ({"back": True}, b"abc"))
        # a protocol spoken by nobody here, on an op: refused, in words
        self.be(self.B.tree)
        syncpeer._PROTOCOL_TEST = 2
        with self.assertRaises(syncpeer.Refused) as cm:
            syncpeer.call(self.a["install"], "hello", {}, timeout=10)
        self.assertIn("version 2 of the sync protocol", cm.exception.reason)

    def test_6_a_stranger_is_refused_before_any_handler(self):
        # C: a whole identity of its own, which pinned A by hand -- A never paired it
        c = os.path.join(self.base, "C-stranger")
        os.makedirs(os.path.join(c, "config"))
        self.be(c)
        syncid.ensure()
        with open(os.path.join(self.A.tree, "config", "sync", "identity.crt")) as fh:
            a_pem = fh.read()
        syncpeer._keep({"id": self.a["install"], "name": "A", "cert": a_pem,
                        "fingerprint": self.a["fingerprint"], "protocol": 1,
                        "addresses": [self.at(self.A)], "last_ok": None, "paired": 0, "last_seen": None})
        with self.assertRaises(syncpeer.Refused) as cm:
            syncpeer.call(self.a["install"], "echo", {}, timeout=10)
        self.assertIn("no longer counts this computer as a partner", cm.exception.reason)
        # the handshake itself is refused at A: a stranger's certificate never reaches a handler
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        p = syncid.paths()
        ctx.load_cert_chain(p["cert"], p["key"])
        s = ctx.wrap_socket(socket.create_connection(("127.0.0.1", self.A.port), timeout=10),
                            server_hostname=syncpeer.SNI)
        with self.assertRaises((ssl.SSLError, ConnectionError)):
            s.sendall(b"POST /sync/api/echo HTTP/1.1\r\nHost: x\r\nContent-Length: 0\r\n\r\n")
            if not s.recv(100):
                raise ConnectionResetError("closed")
        s.close()
        # no certificate at all: the pairing request only
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        conn = syncpeer._Conn("127.0.0.1", self.A.port, ctx, 10)
        conn.request("POST", "/sync/api/echo", body=b"{}", headers={"X-Parseh-Protocol": "1"})
        r = conn.getresponse()
        self.assertEqual(r.status, 403)
        self.assertIn(b"not paired", r.read())
        conn.close()
        # a browser's connections -- plain http here, TLS without the partners' name -- never reach /sync/
        st, out = self.A.post("/sync/api/echo")
        self.assertEqual(st, 403)
        self.assertIn("paired partner only", out["error"])
        bc = http.client.HTTPSConnection("localhost", self.A.port, timeout=10,
                                         context=ssl._create_unverified_context())
        bc.request("POST", "/sync/api/echo", body=b"{}")
        r = bc.getresponse()
        self.assertEqual(r.status, 403)
        bc.close()

    def test_7_a_frozen_partner_is_unreachable_within_its_deadline(self):
        self.be(self.B.tree)
        os.kill(self.A.proc.pid, signal.SIGSTOP)
        try:
            t = time.monotonic()
            with self.assertRaises(syncpeer.Unreachable) as cm:
                syncpeer.call(self.a["install"], "hello", {}, timeout=2.5)
            took = time.monotonic() - t
            self.assertLess(took, 3.5, "silence is not waited on past the deadline")
            self.assertIn("did not answer", str(cm.exception))
            p = [p for p in syncpeer.partners() if p["id"] == self.a["install"]][0]
            self.assertIs(p["reachable"], False)
        finally:
            os.kill(self.A.proc.pid, signal.SIGCONT)
        out, _ = syncpeer.call(self.a["install"], "hello", {}, timeout=10)
        self.assertEqual(out["install"], self.a["install"])

    def test_8_a_partner_removed_is_refused(self):
        st, out = self.A.dev("remove", {"id": self.b["install"]})
        self.assertEqual((st, out["removed"]), (200, True))
        self.be(self.B.tree)
        with self.assertRaises(syncpeer.Refused) as cm:
            syncpeer.call(self.a["install"], "hello", {}, timeout=10)
        self.assertIn("no longer counts this computer as a partner", cm.exception.reason)
        # B still pins A; removing it there too
        st, out = self.B.dev("remove", {"id": self.a["install"]})
        self.assertTrue(out["removed"])
        with self.assertRaises(syncpeer.Refused):
            syncpeer.call(self.a["install"], "hello", {}, timeout=10)


if __name__ == "__main__":
    unittest.main()
