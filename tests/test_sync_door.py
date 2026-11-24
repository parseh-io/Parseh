# SPDX-License-Identifier: GPL-3.0-or-later
"""The third door, "Paired computers", between two whole installs (a0.7.0, lane I).

Two REAL serve.py processes (tests/sync_harness.py).  A is started the way a
person runs Parseh -- no fixed address, so the doors decide what it binds --
with the browsers' two doors shut; B is the partner, on 127.0.0.1 as in
tests/test_sync_pairing.py.  B reaches A on this machine's own network
address, never on 127.0.0.1, so "A listens on 127.0.0.1 only" is a fact of
the socket that this test can see: a connect there is refused.

  * nothing paired, all three doors shut: a closed socket;
  * a pairing code shown opens the door (and moves the socket); B pairs;
  * door open: an echo through syncpeer.call; a browser's connection on the
    network address gets nothing;
  * door shut on Settings -> Network: 127.0.0.1 again, partners or not; B gets
    Unreachable; Devices says sync from partners is paused, with a link;
  * door shut with the Wi-Fi door open: the socket is open, the partner is
    still not served;
  * reopened: the echo works again.

The calling side (B) runs in THIS process on B's tree, as test_sync_pairing
does; prefs.STORE and network.STORE point there, never at the checkout's config/.
"""
import http.client
import json
import os
import shutil
import socket
import ssl
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LIB = os.path.join(os.path.dirname(HERE), "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import network          # noqa: E402
import prefs            # noqa: E402
import synclog          # noqa: E402
import syncpeer         # noqa: E402
from test_sync_pairing import Install, free_port   # noqa: E402


def own_address():
    """This machine's address on its network (a UDP connect sends nothing), or None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return ip if network.where(ip) in (network.LAN, network.VPN) else None


def knock(ip, port, timeout=2.0):
    """True when a TCP connect is accepted, False when it is refused."""
    try:
        socket.create_connection((ip, port), timeout=timeout).close()
        return True
    except ConnectionRefusedError:
        return False


IP = own_address()


@unittest.skipUnless(IP, "this machine has no address on a local network or VPN")
class PairedDoor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="sync-door-")
        cls.old = (prefs.STORE, network.STORE, synclog.HOME)
        os.makedirs(os.path.join(cls.base, "A", "config"))
        port = free_port()          # in the file too: a save on Network moves to the file's port
        with open(os.path.join(cls.base, "A", "config", "network.json"), "w") as fh:
            json.dump({"vpn": False, "lan": False, "port": port}, fh)
        cls.A = Install(cls.base, "A", {"SYNC_BIND_FREE": "1"}, port=port)
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
        prefs.STORE, network.STORE, synclog.HOME = cls.old
        syncpeer._CTX["key"] = None
        if not os.environ.get("SYNC_DOOR_KEEP"):        # a failure to look into keeps the two trees and logs
            shutil.rmtree(cls.base, ignore_errors=True)

    def be_b(self):
        prefs.STORE = os.path.join(self.B.tree, "config", "prefs.json")
        network.STORE = os.path.join(self.B.tree, "config", "network.json")
        synclog.HOME = None
        syncpeer._CTX["key"] = None

    def until(self, what, want, secs=20):
        end = time.time() + secs
        while time.time() < end:
            if what() == want:
                return
            time.sleep(0.2)
        self.fail("still not %r after %d s" % (want, secs))

    def save_network(self, body):
        st, out = self.A.post("/settings/api/network", body)
        self.assertEqual(st, 200, out)
        return out

    def echo(self):
        self.be_b()
        out, body = syncpeer.call(self.a["install"], "echo", {"n": 1}, body=b"xyz", timeout=6)
        return out["payload"], body

    def test_the_third_door(self):
        A, port = self.A, self.A.port
        # ---- all three doors shut, nothing paired: the closed socket
        self.assertFalse(A.dev("state")[1]["door"])
        self.assertFalse(knock(IP, port), "A must listen on 127.0.0.1 only")
        self.assertTrue(knock("127.0.0.1", port))

        # ---- a code shown opens the door, and the socket moves to every interface
        st, offer = A.dev("pair-start")
        self.assertEqual(st, 200, offer)
        self.assertTrue(offer["moving"])
        self.until(lambda: knock(IP, port), True)
        self.until(lambda: A.dev("state")[1].get("door"), True)
        st, out = self.B.dev("pair-enter", {"code": offer["code"], "address": "%s:%d" % (IP, port),
                                            "fingerprint": offer["fingerprint"]})
        self.assertEqual(st, 200, out)
        self.assertTrue(self.B.dev("state")[1]["door"], "pairing opened B's door too")
        with open(os.path.join(A.tree, "config", "network.json")) as fh:
            self.assertIs(json.load(fh)["paired"], True)

        # ---- open: the partner is served
        self.assertEqual(self.echo(), ({"n": 1}, b"xyz"))

        # ---- a browser on the network never gets through the third door
        for sni in (None, "localhost"):
            ctx = ssl.create_default_context()
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
            got = b""
            try:
                with socket.create_connection((IP, port), timeout=5) as raw:
                    with ctx.wrap_socket(raw, server_hostname=sni) as tls:
                        tls.sendall(b"GET /settings/ HTTP/1.1\r\nHost: x\r\n\r\n")
                        got = tls.recv(100)
            except (ssl.SSLError, OSError):
                pass
            self.assertEqual(got, b"", "a browser was answered through the third door")
        with socket.create_connection((IP, port), timeout=5) as raw:   # plain http: closed, no redirect
            raw.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
            try:
                got = raw.recv(100)
            except OSError:
                got = b""
            self.assertEqual(got, b"")

        # ---- shut on Settings -> Network: 127.0.0.1 again, partners or not
        out = self.save_network({"paired": False})
        self.assertTrue(out["moving"], out)
        self.until(lambda: knock(IP, port), False)
        self.assertTrue(knock("127.0.0.1", port), "this computer still reaches A")
        st = A.dev("state")[1]
        self.assertFalse(st["door"])
        self.assertEqual(len(st["partners"]), 1, "the partner is kept, only shut out")
        with self.assertRaises(syncpeer.Unreachable):
            self.echo()
        page = A.post_get("/settings/devices/")
        i = page.index("data-door-shut")
        tag = page[page.rindex("<", 0, i):page.index(">", i)]
        self.assertNotIn("hidden", tag, "Devices says sync is paused")
        self.assertIn('href="/settings/network/"', page[i:i + 600])
        net = A.post_get("/settings/network/")
        self.assertIn('data-door="paired"', net)
        self.assertNotIn('data-door="paired" checked', net)

        # ---- shut, with the Wi-Fi door open: the socket is open, the partner still not served
        self.save_network({"lan": True})
        self.until(lambda: knock(IP, port), True)
        with self.assertRaises((syncpeer.Unreachable, syncpeer.Refused)) as cm:
            self.echo()
        self.assertIsInstance(cm.exception, syncpeer.Unreachable,
                              "a shut door reads as silence, never as 'pair them again'")
        self.save_network({"lan": False})
        self.until(lambda: knock(IP, port), False)

        # ---- reopened: works again
        out = self.save_network({"paired": True})
        self.assertTrue(out["moving"], out)
        self.until(lambda: knock(IP, port), True)
        self.assertEqual(self.echo(), ({"n": 1}, b"xyz"))
        self.assertIn('data-door="paired" checked', A.post_get("/settings/network/"))
        page = A.post_get("/settings/devices/")
        i = page.index("data-door-shut")
        self.assertIn("hidden", page[page.rindex("<", 0, i):page.index(">", i)])


if __name__ == "__main__":
    unittest.main()
