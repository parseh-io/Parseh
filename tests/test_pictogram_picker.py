# SPDX-License-Identifier: GPL-3.0-or-later
"""The pictogram picker as the servers answer it and the pages carry it (lib/pictograms.js, a0.5.3).

    python3 -m unittest tests/test_pictogram_picker.py

THE REAL SERVER (serve.py's, with the studio mounted at /studio) over plain http on a free port, with an INSTALLED
set of pictograms in a temporary arasaac/ (tests/pictogram_world.py) and the network settings in a temporary tree;
nothing here reaches ARASAAC.  What is held:

  * THE SEARCH IS A READ, OPEN TO ANY DEVICE LET IN, and only that: the door's route and the studio's both answer a
    word with the pictograms for it, a request that is not well made is a 400 in a sentence, a device that has not
    been let in gets nothing, and a page on another site cannot ask;
  * A PICTURE IS SERVED BY ITS NUMBER AND NOTHING ELSE: digits, the file's own bytes, kept for good under an address
    that carries its version and asked about each time under one that does not, and a number with no picture is a
    404 -- never a path, whatever is sent;
  * THE STUDIO RUN ON ITS OWN ANSWERS FOR WHAT IT LINKS: the picker's two files (and no other file of lib/), the
    search and the pictures, as the toolbox does under /studio;
  * NO PAGE LINKS THE PICKER'S SCRIPT: the exercise form and the door fetch it when a button is pressed, with a
    deadline, and the script links its own sheet from beside itself.  A tag in a page is a request its `load` waits
    for, and a deck kept on a phone and opened with the computer answering nothing sat on it for thirty seconds
    (tests/mobile_pages.mjs, b2: found by the a0.5.3 loop);
  * THE EDITOR HAS ITS BUTTON, and the door its own, which is drawn only when a picture is here to look at.
"""
import http.client
import json
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", ".", "tests"):
    sys.path.insert(0, str(ROOT / p))
import network                                                     # noqa: E402
import getarasaac as ga                                            # noqa: E402
import arasaacsearch                                               # noqa: E402
import pictogram_world                                             # noqa: E402

TEMPLATES = ROOT / "markdown" / "app" / "templates"
WITH_THE_FORM = ("edit.html", "deck.html", "decks.html", "cram.html", "study.html")


class Served(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import serve
        cls.serve = serve
        cls._td = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._td.name)
        cls.patches = [
            patch.object(serve.Handler, "log_request", lambda *a, **k: None),
            patch.object(network, "STORE", str(cls.tmp / "config" / "network.json")),
            patch.object(ga, "ARASAAC_DIR", str(cls.tmp / "arasaac")),
        ]
        for p in cls.patches:
            p.start()
        network._CACHE.update({"key": None, "doc": None})
        ga._FACTS.clear()
        arasaacsearch.forget()
        cls.world = pictogram_world.install(ga.ARASAAC_DIR)
        cls.srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        for p in reversed(cls.patches):
            p.stop()
        ga._FACTS.clear()
        arasaacsearch.forget()
        network._CACHE.update({"key": None, "doc": None})
        cls._td.cleanup()

    def ask(self, method, path, body=None, headers=None, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=60)
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
        h = {"Content-Type": "application/json"} if data is not None else {}
        h.update(headers or {})
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        got = r.read()
        c.close()
        try:
            out = json.loads(got.decode("utf-8"))
        except ValueError:
            out = got
        return r.status, r, out

    def phone(self):
        return [patch.object(network, "where", lambda ip, doc=None: network.LAN),
                patch.object(network, "may_connect", lambda ip, doc=None: True),
                patch.object(network, "let_in", lambda *a, **k: True)]

    def ids(self, answer):
        return [r["id"] for r in answer["results"]]

    # ---- the search, in the toolbox's own settings and in the studio it mounts
    def test_the_door_and_the_studio_answer_a_word_with_the_same_pictures(self):
        for path in ("/settings/api/arasaac/search", "/studio/api/arasaac/search"):
            status, _, got = self.ask("POST", path, {"q": "casa", "display": "es"})
            self.assertEqual(status, 200, path)
            self.assertEqual(self.ids(got), [2317, 2319, 2318], path)
            self.assertEqual([r["word"] for r in got["results"]], ["casa", "casa", "casa unifamiliar"], path)
            self.assertTrue(got["ready"] and got["credit"].startswith("Pictograms author"), path)

    def test_a_request_that_is_not_well_made_is_a_400_with_its_sentence(self):
        for path in ("/settings/api/arasaac/search", "/studio/api/arasaac/search"):
            for body in ({"q": "x", "limit": 0}, {"q": "x", "limit": "many"}, {"q": "x", "offset": -3},
                         {"q": "x", "locales": ["klingon"]}, {"q": "x", "locales": "en"}, {"q": 7},
                         {"q": "x", "display": ["en"]}):
                status, _, got = self.ask("POST", path, body)
                self.assertEqual(status, 400, (path, body))
                self.assertFalse(got["ok"], (path, body))
                self.assertTrue(got["error"] and got["code"], (path, body))

    def test_a_body_that_is_not_an_object_searches_for_nothing_and_does_not_break(self):
        for raw in (b"[]", b"7", b"null", b"not json"):
            status, _, got = self.ask("POST", "/settings/api/arasaac/search", raw=raw)
            self.assertIn(status, (200, 400), raw)
            if status == 200:
                self.assertTrue(got["ok"], raw)

    def test_the_search_is_a_post_and_not_a_get(self):
        self.assertEqual(self.ask("GET", "/settings/api/arasaac/search")[0], 405)

    def test_nothing_the_client_sends_is_a_path(self):
        status, _, got = self.ask("POST", "/settings/api/arasaac/search", {"q": "../../etc/passwd", "locales": ["../en"]})
        self.assertEqual(status, 400)
        status, _, got = self.ask("POST", "/settings/api/arasaac/search", {"q": "../../etc/passwd"})
        self.assertEqual((status, got["total"]), (200, 0))

    def test_a_page_on_another_site_cannot_ask(self):
        status, _, got = self.ask("POST", "/settings/api/arasaac/search", {"q": "casa"},
                                  headers={"Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)

    def test_a_device_let_in_may_search_and_one_that_is_not_may_not(self):
        ps = self.phone()
        for p in ps:
            p.start()
        try:
            status, _, got = self.ask("POST", "/settings/api/arasaac/search", {"q": "casa"})
            self.assertEqual(status, 200, "a phone that has been let in")
            self.assertEqual(self.ids(got), [2317, 2319, 2318])
        finally:
            for p in reversed(ps):
                p.stop()
        with patch.object(network, "may_connect", lambda ip, doc=None: False):
            try:
                status, _, got = self.ask("POST", "/settings/api/arasaac/search", {"q": "casa"})
            except (http.client.RemoteDisconnected, ConnectionError):
                return                      # the server did not answer a device that has not been let in: nothing came back
            self.assertNotEqual(status, 200, "a device that has not been let in gets nothing")
            self.assertNotIn("results", got if isinstance(got, dict) else {})

    def test_the_table_names_the_route_as_a_read(self):
        import settingspage
        self.assertEqual(settingspage.ROUTES["/settings/api/arasaac/search"], settingspage.READ)
        self.assertEqual(self.serve.ARASAAC_ROUTES["/settings/api/arasaac/search"], "search")

    # ---- the pictures
    def test_a_picture_is_the_files_own_bytes_under_its_number(self):
        want = (Path(ga.ARASAAC_DIR) / "pictograms" / "2317.png").read_bytes()
        for path in ("/settings/arasaac/picture/2317.png", "/studio/arasaac/2317.png"):
            status, r, got = self.ask("GET", path)
            self.assertEqual(status, 200, path)
            self.assertEqual(r.getheader("Content-Type"), "image/png", path)
            self.assertEqual(got, want, path)

    def test_a_picture_asked_for_with_its_version_is_kept_for_good_and_without_one_is_asked_about_each_time(self):
        for base in ("/settings/arasaac/picture/2317.png", "/studio/arasaac/2317.png"):
            _, r, _ = self.ask("GET", base + "?v=20240101100000000-300")
            self.assertEqual(r.getheader("Cache-Control"), "max-age=31536000, immutable", base)
            _, r, _ = self.ask("GET", base)
            self.assertEqual(r.getheader("Cache-Control"), "no-cache", base)

    def test_a_number_with_no_picture_is_a_404_and_a_name_that_is_not_a_number_is_not_a_route(self):
        for path in ("/settings/arasaac/picture/9999999.png", "/studio/arasaac/9999999.png",
                     "/settings/arasaac/picture/1.png", "/studio/arasaac/1.png"):
            self.assertEqual(self.ask("GET", path)[0], 404, path)
        for path in ("/settings/arasaac/picture/..%2f..%2fconfig%2fnetwork.json", "/settings/arasaac/picture/2317.png/x",
                     "/settings/arasaac/picture/abc.png", "/settings/arasaac/picture/2317.PNG",
                     "/studio/arasaac/%2e%2e/x.png", "/studio/arasaac/2317.png.zip", "/studio/arasaac/-5.png",
                     "/settings/arasaac/picture/12345678.png"):
            status, _, got = self.ask("GET", path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"PNG", got if isinstance(got, bytes) else b"", path)

    def test_a_picture_is_read_only(self):
        for method in ("POST", "PUT", "DELETE"):
            self.assertNotEqual(self.ask(method, "/settings/arasaac/picture/2317.png", {})[0], 200, method)

    def test_what_the_search_says_a_picture_is_at_is_where_it_is(self):
        _, _, got = self.ask("POST", "/settings/api/arasaac/search", {"q": "tree"})
        r = got["results"][0]
        self.assertEqual(r["id"], 2400)
        status, _, body = self.ask("GET", "/settings/arasaac/picture/%d.png?v=%s" % (r["id"], r["v"]))
        self.assertEqual(status, 200)
        self.assertTrue(ga.is_png(body))

    # ---- the files, served by the toolbox and by the studio run alone
    def test_the_toolbox_serves_the_two_files(self):
        for f in ("/lib/pictograms.js", "/lib/pictograms.css"):
            self.assertIn(f, self.serve.STATIC_FILES)
            self.assertTrue(self.serve.static_ok(f), f)
            status, r, got = self.ask("GET", f)
            self.assertEqual(status, 200, f)
            self.assertEqual(got, (ROOT / "lib" / Path(f).name).read_bytes(), f)

    def test_the_studio_run_alone_answers_for_the_two_files_and_for_nothing_else_of_lib(self):
        import server
        picker = [(m, rx, fn) for m, rx, fn in server.ROUTES if fn is server.serve_picker_file]
        self.assertEqual(len(picker), 1)
        for f in ("/lib/pictograms.js", "/lib/pictograms.css"):
            self.assertTrue(re.match(picker[0][1], f), f)
        for f in ("/lib/pictograms.py", "/lib/pictograms.js.map", "/lib/pictograms.jsx", "/lib/arasaacsearch.py",
                  "/lib/getarasaac.py", "/lib/../serve.py"):
            self.assertFalse(re.match(picker[0][1], f), f)
        names = {fn.__name__: rx for m, rx, fn in server.ROUTES}
        self.assertTrue(re.match(names["api_arasaac_search"], "/api/arasaac/search"))
        self.assertTrue(re.match(names["serve_arasaac_picture"], "/arasaac/2317.png"))
        self.assertFalse(re.match(names["serve_arasaac_picture"], "/arasaac/x.png"))

    def test_the_script_links_its_own_sheet_from_beside_itself(self):
        src = (ROOT / "lib" / "pictograms.js").read_text(encoding="utf-8")
        self.assertIn("document.currentScript", src)
        self.assertIn("pictograms\\.js(?=[?#]|$)", src)
        self.assertIn('"pictograms.css"', src)
        self.assertTrue((ROOT / "lib" / "pictograms.css").is_file())

    # ---- the pages
    def test_no_page_links_the_picker_it_is_fetched_when_a_button_is_pressed(self):
        for name in WITH_THE_FORM:
            html = (TEMPLATES / name).read_text(encoding="utf-8")
            self.assertIn("{{STUDIO}}/static/exform.js", html, name)
            self.assertNotIn("/lib/pictograms", html, name + ": a tag is a request the page's load waits for")
        form = (ROOT / "markdown" / "app" / "static" / "exform.js").read_text(encoding="utf-8")
        self.assertIn('tag.src = "/lib/pictograms.js"', form, "the form fetches it itself")
        self.assertIn("10000", form, "with a deadline: a computer that answers nothing does not hold the button for ever")
        self.assertIn("pictogramsNamed", form, "and a question that needs no script (does a text name a pictogram?) is asked without it")
        import offline
        self.assertNotIn("/lib/pictograms.js", offline.SHARED, "a phone does not keep a file that only a search needs")

    def test_the_editor_has_its_button_next_to_the_images(self):
        html = (TEMPLATES / "edit.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'id="btn-images".*\n.*id="btn-pictograms"')
        code = (ROOT / "markdown" / "app" / "static" / "editor.js").read_text(encoding="utf-8")
        self.assertIn('$("#btn-pictograms")', code)

    def test_the_door_draws_its_button_only_where_a_picture_is_to_be_looked_at(self):
        import arasaacpage
        page = arasaacpage.page()
        self.assertNotIn('<script src="/lib/pictograms.js"', page, "the door fetches it when the button is pressed, as the form does")
        self.assertIn("loadPicker", page)
        self.assertIn("data-look", page)                       # the script of the page, which draws the button
        self.assertIn("Look through the pictograms", page)
        self.assertIn("/settings/api/arasaac/search", page)
        self.assertIn("/settings/arasaac/picture/", page)


if __name__ == "__main__":
    unittest.main()
