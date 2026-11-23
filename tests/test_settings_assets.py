# SPDX-License-Identifier: GPL-3.0-or-later
"""Every page of Settings finds the stylesheets, scripts and pages it names.

    python3 -m unittest tests/test_settings_assets.py

A page that names `/lib/settings-tools.css` and a server that does not send it
is a page drawn with the browser's own controls: no spacing between the links
of its foot, white boxes in its forms (a0.4.3's LLM Integration, LM likelihood
and About, found by the owner on 2026-10-05).  The file was in the tree and in
git; only the list of what the server may send (serve.STATIC_FILES) did not
name it.  The same for a link: the two "Setup help" links of LLM Integration and
LM likelihood went to /guide/lookup-and-languages/..., and the guide's pages are
under /guide/site/.  So this asks the way a browser does: the real server, over
http, for every Settings page and then for every address on this computer that
each one names (a stylesheet, a script, a link; never an API route, which is
asked by a POST and not by a click).
"""
import http.client
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    sys.path.insert(0, str(ROOT / p))
import network                                                 # noqa: E402
import settingspage                                            # noqa: E402

NAMED = re.compile(r'''(?:href|src)="(/[^"]*)"''')


def names(html):
    """Every address on this computer a page names, without its #fragment or ?query."""
    found = set()
    for raw in NAMED.findall(html):
        path = re.split(r"[#?]", raw, 1)[0]
        if path and not path.startswith("//") and not path.startswith("/settings/api/") \
                and not path.endswith(("/__backup", "/api/backup", "/api/export")):
            # nor a shelf's Backup, which Settings -> Backups names: it packs the whole shelf
            found.add(path)
    return sorted(found)


class TheFilesAPageNames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import serve
        import prefs
        import prompts
        cls._td = tempfile.TemporaryDirectory()
        tmp = Path(cls._td.name)
        cls.patches = [
            patch.object(serve.Handler, "log_request", lambda *a, **k: None),
            patch.object(network, "STORE", str(tmp / "config" / "network.json")),
            patch.object(prompts, "STORE", str(tmp / "config" / "prompts.json")),
            patch.object(prefs, "STORE", str(tmp / "config" / "prefs.json")),
        ]
        for p in cls.patches:
            p.start()
        network._CACHE.update({"key": None, "doc": None})
        cls.srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        for p in reversed(cls.patches):
            p.stop()
        network._CACHE.update({"key": None, "doc": None})
        cls._td.cleanup()

    def get(self, path):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=60)
        c.request("GET", path)
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, body.decode("utf-8", "replace")

    def test_every_door_and_what_it_names_is_sent(self):
        pages = ["/settings/"] + [d[0] for d in settingspage.DOORS]
        self.assertGreater(len(pages), 8, pages)
        missed = []
        for page in pages:
            status, html = self.get(page)
            self.assertEqual(status, 200, page)
            for name in names(html):
                got, _ = self.get(name)
                if got != 200:
                    missed.append("%s names %s and the server answers %s" % (page, name, got))
        self.assertEqual(missed, [], "\n".join(missed))

    def test_the_tools_stylesheet_is_one_of_them(self):
        # the three pages of a0.4.3 and the speech door load it: if none did, the test above would say nothing of it.
        # (and the guide's pages are one of them too: the two links that went astray)
        for page in ("/settings/lm-likelihood/", "/settings/about/", "/settings/speech/"):
            _, html = self.get(page)
            self.assertIn("/lib/settings-tools.css", html, page)
        for page, guide in ((("/settings/lm-likelihood/", "/guide/site/lookup-and-languages/lm-likelihood.html"),)):
            self.assertIn(guide, names(self.get(page)[1]), page)


if __name__ == "__main__":
    unittest.main()
