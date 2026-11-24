# SPDX-License-Identifier: GPL-3.0-or-later
"""This computer on plain http://localhost (a0.7.0, W5; lib/localhttp.py).

Driven against serve.py's own Server and Handler, with a certificate made in
a temporary .tls/ and every STORE pointed at a temporary tree:

  * one port speaks both: TLS to whoever starts a handshake, plain http to
    this computer;
  * plain http from any other address gets a redirect to https and nothing
    else (the connection is handed to the real finish_request with a peer
    address that is not loopback);
  * plain http naming another site in its Host (DNS rebinding) is refused;
  * the old origin's navigation is handed over, the record taken once, and
    later navigations redirected;
  * the addresses Parseh writes for itself on this computer are
    http://localhost:<port>/ -- the launcher, the scripts, the printed lines,
    the guide's pages;
  * the updater's progress page answers both ways on the same port.

    python3 tests/test_localhttp.py
"""
import http.client
import json
import os
import re
import socket
import ssl
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT))

import localhttp                                               # noqa: E402
import network                                                 # noqa: E402
import prefs                                                   # noqa: E402


class Running(unittest.TestCase):
    """serve.py's Server on 127.0.0.1:<free port>, TLS context loaded."""

    @classmethod
    def setUpClass(cls):
        import serve
        cls.serve = serve
        cls.td = tempfile.TemporaryDirectory()
        tree = Path(cls.td.name)
        (tree / "config").mkdir()
        (tree / "tls").mkdir()
        cls.patches = [patch.object(serve, "TLS_DIR", str(tree / "tls")),
                       patch.object(network, "STORE", str(tree / "config" / "network.json")),
                       patch.object(prefs, "STORE", str(tree / "config" / "prefs.json")),
                       patch.object(serve.Handler, "log_request", lambda *a, **k: None),
                       patch("builtins.print")]
        for p in cls.patches:
            p.start()
        cert, key = serve.make_cert()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        cls.srv = serve.Server(("127.0.0.1", 0), serve.Handler, ctx)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        for p in reversed(cls.patches):
            p.stop()
        cls.td.cleanup()

    def plain(self, method, path, headers=None, body=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = dict(headers or {})
        if host is not None:
            c.putrequest(method, path, skip_host=True)
            c.putheader("Host", host)
            for k, v in h.items():
                c.putheader(k, v)
            c.endheaders(body)
        else:
            c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        out = (r.status, dict(r.getheaders()), r.read())
        c.close()
        return out

    def tls(self, method, path, headers=None, body=None):
        c = http.client.HTTPSConnection("localhost", self.port, timeout=20,
                                        context=ssl._create_unverified_context())
        c.request(method, path, body=body, headers=dict(headers or {}))
        r = c.getresponse()
        out = (r.status, dict(r.getheaders()), r.read())
        c.close()
        return out

    NAV = {"Accept": "text/html", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
           "Sec-Fetch-Site": "none"}

    # ---- one port, two ways in
    def test_this_computer_is_served_plain_http(self):
        st, _, body = self.plain("GET", "/settings/api/ping")
        self.assertEqual(st, 200, body[:200])
        st, hd, body = self.plain("GET", "/", self.NAV)
        self.assertEqual(st, 200)
        self.assertTrue(b"opens Parseh at <code>http://localhost:" in body,
                        "the hub names this computer's own address")

    def test_tls_still_answers_on_the_same_port(self):
        st, _, body = self.tls("GET", "/settings/api/ping")
        self.assertEqual(st, 200, body[:200])

    def test_plain_http_from_another_address_gets_only_a_redirect(self):
        a, b = socket.socketpair()
        try:
            a.sendall(b"GET /settings/api/ping HTTP/1.1\r\nHost: 192.168.1.20:%d\r\n\r\n" % self.port)
            t = threading.Thread(target=self.srv.finish_request, args=(b, ("192.168.1.20", 40000)))
            t.start()
            t.join(20)
            a.settimeout(5)
            got = b""
            while True:
                piece = a.recv(65536)
                if not piece:
                    break
                got += piece
        finally:
            a.close()
            b.close()
        head = got.split(b"\r\n\r\n", 1)[0].decode("latin-1")
        self.assertTrue(head.startswith("HTTP/1.1 301"), head)
        self.assertIn("Location: https://192.168.1.20:%d/settings/api/ping" % self.port, head)
        self.assertNotIn(b'"ok"', got, "nothing of the route itself went out")

    def test_plain_http_naming_another_site_is_refused(self):
        st, _, body = self.plain("GET", "/settings/api/ping", host="evil.example:%d" % self.port)
        self.assertEqual(st, 421, body[:200])
        self.assertNotIn(b'"updating"', body)
        for ok in ("localhost:%d" % self.port, "127.0.0.1:%d" % self.port, "127.1.2.3"):
            st, _, _ = self.plain("GET", "/settings/api/ping", host=ok)
            self.assertEqual(st, 200, ok)

    # ---- the move of origin
    def test_the_old_origin_hands_over_once_then_redirects(self):
        st, hd, body = self.tls("GET", "/books/?x=1", self.NAV)
        self.assertEqual(st, 200)
        page = body.decode("utf-8")
        self.assertIn("http://localhost:%d" % self.port, page)
        self.assertIn("localStorage", page)
        self.assertIn('"/books/?x=1"', page, "it goes on to the page that was asked for")
        # a script of an old tab is still answered, not handed a page
        st, _, body = self.tls("GET", "/settings/api/ping", {"Accept": "*/*"})
        self.assertEqual(st, 200)
        self.assertIn(b"ok", body)
        # the page posts what it kept
        rec = {"ls": {"bk_rate": "1.25", "bk_edits:/books/fa/x/": "{\"a\":1}", "bad": 3},
               "app": True, "worker": True}
        st, hd, body = self.tls("POST", localhttp.MOVE, {"Content-Type": "application/json",
                                                       "Sec-Fetch-Site": "same-origin"},
                                json.dumps(rec).encode())
        self.assertEqual(st, 200, body)
        token = json.loads(body)["token"]
        cookie = hd.get("Set-Cookie", "")
        self.assertIn("parseh_moved_%d=1" % self.port, cookie)
        self.assertIn("Secure", cookie)
        # the new origin takes it, once
        st, _, body = self.plain("GET", localhttp.MOVE_TAKE + "?t=" + token)
        got = json.loads(body)
        self.assertEqual(got["ls"], {"bk_rate": "1.25", "bk_edits:/books/fa/x/": "{\"a\":1}"})
        self.assertTrue(got["app"])
        st, _, body = self.plain("GET", localhttp.MOVE_TAKE + "?t=" + token)
        self.assertEqual(json.loads(body), {})
        st, _, body = self.plain("GET", localhttp.MOVE + "?t=x&next=/books/", self.NAV)
        self.assertEqual(st, 200)
        self.assertIn(b"install it", body.lower())
        # and from then on the old address is a redirect
        st, hd, _ = self.tls("GET", "/youtube/?a=b", dict(self.NAV, Cookie="parseh_moved_%d=1" % self.port))
        self.assertEqual(st, 302)
        self.assertEqual(hd["Location"], "http://localhost:%d/youtube/?a=b" % self.port)

    def test_where_to_go_after_a_move_cannot_leave_the_server(self):
        for bad in ("//evil.example/", "https://evil.example/", "/\\evil", localhttp.MOVE):
            self.assertEqual(localhttp.safe_next(bad), "/", bad)
        self.assertEqual(localhttp.safe_next("/books/?a=1"), "/books/?a=1")

    def test_a_post_from_another_site_to_the_hand_over_is_refused(self):
        st, _, _ = self.tls("POST", localhttp.MOVE, {"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(st, 403)

    # ---- the addresses Parseh writes
    def test_the_addresses_it_prints_and_offers(self):
        serve = self.serve
        with patch.dict(serve.RUN, {"host": "127.0.0.1", "port": self.port, "scheme": "https"}):
            serve._announce(None, False)
            self.assertEqual(serve.ADDRESSES, ["http://localhost:%d/" % self.port])
            self.assertEqual(serve._where_to_go({"port": 7654, "vpn": True, "lan": False,
                                                 "extra": []})[0], "http://localhost:7654/")
        with patch.dict(serve.RUN, {"host": "0.0.0.0", "port": 7654, "scheme": "https"}), \
                patch.object(serve, "addresses", lambda: [("100.1.2.3", "tailscale"),
                                                          ("localhost", "this machine")]):
            serve._announce(None, False)
            self.assertEqual(serve.ADDRESSES, ["https://100.1.2.3:7654/", "http://localhost:7654/"])

    def test_the_launcher_finds_it_at_http_localhost(self):
        import launcher
        self.assertEqual(launcher.server_url(self.port), "http://localhost:%d/" % self.port)


class Written(unittest.TestCase):
    """Every address Parseh writes for itself on this computer."""

    def test_the_scripts(self):
        for name in ("serve.sh", "serve.bat", "Parseh.command", "README.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("https://localhost", text, name)
            self.assertNotIn("https://127.0.0.1", text, name)
        self.assertIn('open "http://localhost:$PORT/"', (ROOT / "Parseh.command").read_text())

    def test_the_guide_and_the_docs(self):
        found = []
        for d in ("html-guide/markdown", "docs"):
            for p in (ROOT / d).rglob("*.md"):
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    # the old address is named only where the move is told
                    old = re.search(r"\bold\b|Before a0\.7\.0|move of origin", line)
                    if ("https://localhost" in line or "https://127.0.0.1" in line) and not old:
                        found.append("%s:%d" % (p.relative_to(ROOT), n))
        self.assertEqual(found, [])

    def test_no_page_says_every_browser_warns(self):
        bad = []
        for d in ("html-guide/markdown",):
            for p in (ROOT / d).rglob("*.md"):
                t = p.read_text(encoding="utf-8")
                if re.search(r"every browser warns(?! you\s+about it once\*\*, on each device other)", t):
                    bad.append(str(p.relative_to(ROOT)))
        self.assertEqual(bad, [])

    def test_the_address_helpers(self):
        self.assertEqual(localhttp.home(7654), "http://localhost:7654/")
        self.assertEqual(localhttp.address_for("https", "127.0.0.1", 9), "http://localhost:9/")
        self.assertEqual(localhttp.address_for("https", "localhost", 9), "http://localhost:9/")
        self.assertEqual(localhttp.address_for("https", "100.1.2.3", 9), "https://100.1.2.3:9/")
        for ok in ("localhost", "localhost:1", "127.0.0.1:7654", "[::1]:7654", "LOCALHOST."):
            self.assertTrue(localhttp.host_is_loopback(ok), ok)
        for bad in ("", "evil.example", "localhost.evil.example", "192.168.1.2:7654", "[::2]"):
            self.assertFalse(localhttp.host_is_loopback(bad), bad)
        for ok in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
            self.assertTrue(localhttp.is_loopback(ok), ok)
        self.assertFalse(localhttp.is_loopback("192.168.1.20"))


class UpdaterPage(unittest.TestCase):
    """The progress page the updater holds the port with answers both ways."""

    def test_both_ways_on_one_port(self):
        import updater
        import serve
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        with patch.object(serve, "TLS_DIR", td.name), patch("builtins.print"):
            cert, key = serve.make_cert()
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        class Apply:
            st = {"said": "copying"}
            job = {"from": "a0.6.4", "to": "a0.7.0"}
        page = updater._StatusServer(Apply(), "127.0.0.1", port, "https", [cert, key])
        self.addCleanup(page.stop)
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("GET", "/settings/api/update/state")
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        self.assertTrue(json.loads(r.read())["helper"])
        c.close()
        c = http.client.HTTPSConnection("127.0.0.1", port, timeout=10,
                                        context=ssl._create_unverified_context())
        c.request("GET", "/settings/api/ping")
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        self.assertIn(b"updating", r.read())
        c.close()


if __name__ == "__main__":
    unittest.main()
