# SPDX-License-Identifier: GPL-3.0-or-later
"""A file from the computer, open in the studio, over HTTP (a0.5.2): the studio's own routes under /open/<sid>/, the
doors about the computer's files, and who may use them.  The file's logic (what is read, what makes it unsaved, what
is written) is tests/test_openfile.py; the pages as a person uses them are tests/openfile.mjs.

    python3 -m unittest discover -s tests -p test_openfile_server.py

A real studio server on a free port, in temporary folders: its library, its working copies, its clip tray and the
person's own files.  The real ones are never touched."""
import http.client
import json
import re
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app", ROOT / "lib", ROOT / "youtube" / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import deckroutes  # noqa: E402
import network     # noqa: E402
import openfile    # noqa: E402
import server      # noqa: E402
import store       # noqa: E402

LESSON = "---\ntitle: Lesson\nlang: en\ntarget: fa\n---\n\nHello.\n\n## Part\n\nMore.\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"cat" * 40


class OverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.td.name).resolve()
        cls.saved = [(store, "LIB", store.LIB), (openfile, "OPEN_DIR", openfile.OPEN_DIR),
                     (store, "CLIPS_DIR", store.CLIPS_DIR)]
        store.LIB = root / "library"
        store.LIB.mkdir()
        openfile.OPEN_DIR = root / "open"
        store.CLIPS_DIR = root / "clips"
        cls.quiet = mock.patch.object(server.Handler, "log_message", lambda *a: None)
        cls.quiet.start()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.srv.daemon_threads = True
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.port = cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.quiet.stop()
        for obj, name, value in cls.saved:
            setattr(obj, name, value)
        cls.td.cleanup()

    def setUp(self):
        # the person's own folder, new for each test
        self.mine = Path(tempfile.mkdtemp(dir=str(self.root)))
        openfile._SESSIONS.clear()
        self.addCleanup(openfile._SESSIONS.clear)
        was = store.use_library(None)
        self.addCleanup(store.use_library, was)
        self.addCleanup(self.close_all)

    def close_all(self):
        for s in openfile.live():
            s.close(discard=True)

    # ---- helpers
    def ask(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        self.addCleanup(c.close)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()

    def post(self, path, obj=None, expect=None):
        status, _h, data = self.ask("POST", path, json.dumps(obj if obj is not None else {}).encode(),
                                    {"Content-Type": "application/json"})
        answer = json.loads(data)
        if expect is not None:
            self.assertEqual(status, expect, answer)
        return status, answer

    def write(self, name, data):
        path = self.mine / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path

    def open(self, path):
        status, answer = self.post("/api/file/open", {"path": str(path)}, 200)
        self.assertTrue(answer["ok"], answer)
        m = re.match(r"^(/open/[0-9a-f]{12})/doc/([a-z0-9\-]+)$", answer["url"])
        self.assertTrue(m, answer["url"])
        return m.group(1), m.group(2), answer

    # ---- the doors in
    def test_browse_and_open(self):
        self.write("lesson.md", LESSON)
        self.write("picture.png", PNG)
        (self.mine / "folder").mkdir(exist_ok=True)
        status, got = self.post("/api/file/list", {"path": str(self.mine)}, 200)
        self.assertEqual([e["name"] for e in got["entries"]], ["folder", "lesson.md"])
        self.assertTrue(got["places"])
        status, got = self.post("/api/file/list", {"path": str(self.mine / "nowhere")}, 200)
        self.assertEqual((got["ok"], got["code"]), (False, "gone"))
        prefix, doc, answer = self.open(self.mine / "lesson.md")
        self.assertEqual((answer["kind"], answer["dirty"], answer["name"], answer["again"]), ("md", False, "lesson.md", False))
        self.assertEqual(answer["edit"], "%s/doc/%s/edit" % (prefix, doc))
        # the same file again is the same session
        prefix2, doc2, again = self.open(self.mine / "lesson.md")
        self.assertEqual((prefix2, doc2, again["again"]), (prefix, doc, True))
        status, got = self.post("/api/file/sessions", {}, 200)
        self.assertEqual([s["sid"] for s in got["sessions"]], [prefix.rsplit("/", 1)[1]])

    def test_refusals_say_why(self):
        status, got = self.post("/api/file/open", {"path": str(self.mine / "missing.md")}, 400)
        self.assertEqual((got["ok"], got["code"]), (False, "gone"))
        self.assertIn("not there", got["error"])
        status, got = self.post("/api/file/open", {"path": "relative.md"}, 400)
        self.assertEqual(got["code"], "path")
        status, got = self.post("/api/file/open", {"path": str(self.write("x.png", PNG))}, 400)
        self.assertEqual(got["code"], "kind")

    def test_a_zip_with_several_documents_is_chosen_from(self):
        path = self.mine / "two.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("a.md", "# A\n\nA.\n")
            zf.writestr("b.md", "# B\n\nB.\n")
        status, got = self.post("/api/file/open", {"path": str(path)}, 200)
        self.assertEqual([c["path"] for c in got["choose"]], ["a.md", "b.md"])
        status, got = self.post("/api/file/open", {"path": str(path), "entry": "b.md"}, 200)
        self.assertEqual(got["entry"], "b.md")
        status, got = self.post("/api/file/open", {"path": str(path), "entry": "a.md"}, 409)
        self.assertEqual(got["code"], "busy")

    # ---- the pages
    def test_the_pages_are_the_studios_own_on_the_working_copy(self):
        path = self.write("lesson.md", LESSON)
        prefix, doc, _answer = self.open(path)
        status, headers, page = self.ask("GET", "%s/doc/%s" % (prefix, doc))
        html = page.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("Lesson", html)
        self.assertIn('data-open-sid="%s"' % prefix.rsplit("/", 1)[1], html)
        self.assertIn('data-open-kind="md"', html)
        self.assertIn('data-base="%s"' % prefix, html)
        self.assertIn("/static/openfile.js", html)
        self.assertIn('href="/">← Library', html, "the way back is the studio's library, not this one document")
        self.assertNotIn('href="%s/">← Library' % prefix, html)
        self.assertNotIn("{{", html)
        status, headers, page = self.ask("GET", "%s/doc/%s/edit" % (prefix, doc))
        edit = page.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("Hello.", edit)
        self.assertIn("/static/openfile.js", edit)
        self.assertIn('data-open-sid="', edit)
        # the root of the mount is the document: it is where the editor's "Back" and the old address land
        status, headers, _page = self.ask("GET", prefix + "/")
        self.assertEqual((status, headers["location"]), (302, "%s/doc/%s" % (prefix, doc)))
        # the library page does not show this file, and offers the button
        status, _h, page = self.ask("GET", "/")
        self.assertIn('id="btn-open-file"', page.decode("utf-8"))
        self.assertNotIn(doc, page.decode("utf-8"))

    def test_the_library_is_not_the_files(self):
        path = self.write("lesson.md", LESSON)
        prefix, doc, _answer = self.open(path)
        self.assertEqual(json.loads(self.ask("GET", "/api/docs")[2])["docs"], [], "the studio's library holds nothing")
        status, _h, data = self.ask("GET", prefix + "/api/docs")
        self.assertEqual([d["id"] for d in json.loads(data)["docs"]], [doc])
        self.assertEqual(self.ask("GET", "/api/docs/%s" % doc)[0], 404)
        self.assertEqual(list(store.LIB.iterdir()), [])

    def test_the_library_things_are_refused_in_a_file(self):
        prefix, doc, _answer = self.open(self.write("lesson.md", LESSON))
        for method, sub in (("POST", "/api/docs"), ("POST", "/api/docs/zip"), ("POST", "/api/library/zip"),
                            ("POST", "/api/docs/%s/duplicate" % doc), ("DELETE", "/api/docs/%s" % doc),
                            ("GET", "/api/export"), ("POST", "/api/download"), ("GET", "/new")):
            status, _h, data = self.ask(method, prefix + sub, b"{}" if method == "POST" else None)
            self.assertEqual(status, 404, (method, sub))
            self.assertIn("studio's library", json.loads(data)["error"])
        status, _h, page = self.ask("GET", prefix + "/doc/%s" % doc)
        self.assertEqual(status, 200, "and the document is still there")
        # stopping the server is not the library's business: the page's Stop button works from a file's page
        status, _h, data = self.ask("POST", prefix + "/api/shutdown", b"{}")
        self.assertEqual((status, json.loads(data)["ok"]), (200, True))

    def test_an_unknown_file_is_not_found(self):
        self.assertEqual(self.ask("GET", "/open/0123456789ab/doc/x")[0], 404)
        status, _h, data = self.ask("POST", "/open/0123456789ab/api/file/state", b"{}")
        self.assertEqual(status, 404)
        self.assertIn("not open any more", json.loads(data)["error"])
        self.assertEqual(self.post("/api/file/state", {})[0], 404, "state of nothing")

    # ---- editing, saving, closing
    def test_edit_save_close(self):
        path = self.write("lesson.md", LESSON)
        prefix, doc, _answer = self.open(path)
        status, answer = self.post(prefix + "/api/file/state", {}, 200)
        self.assertEqual((answer["state"]["dirty"], answer["state"]["changed_on_disk"]), (False, False))
        self.assertEqual(answer["library"], "/")
        # the editor's save lands in the working copy only
        edited = LESSON + "\nNew words.\n"
        status, _h, data = self.ask("PUT", "%s/api/docs/%s" % (prefix, doc), json.dumps({"markdown": edited}).encode(),
                                    {"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON, "the file has not moved")
        status, answer = self.post(prefix + "/api/file/state", {}, 200)
        self.assertTrue(answer["state"]["dirty"])
        # closing asks first
        status, answer = self.post(prefix + "/api/file/close", {}, 200)
        self.assertEqual((answer["ok"], answer["need"]), (False, "unsaved"))
        # saving is the one moment the file changes
        status, answer = self.post(prefix + "/api/file/save", {}, 200)
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(path.read_text(encoding="utf-8"), edited)
        self.assertFalse(answer["state"]["dirty"])
        status, answer = self.post(prefix + "/api/file/save", {}, 200)
        self.assertEqual(answer.get("unchanged"), True)
        status, answer = self.post(prefix + "/api/file/close", {}, 200)
        self.assertEqual((answer["ok"], answer["library"]), (True, "/"))
        self.assertEqual(list(openfile.OPEN_DIR.iterdir()), [], "the working copy is deleted")
        self.assertEqual(self.ask("GET", "%s/doc/%s" % (prefix, doc))[0], 404)

    def test_a_picture_goes_through_the_studios_own_upload_and_makes_the_save_ask(self):
        path = self.write("lesson.md", LESSON)
        prefix, doc, _answer = self.open(path)
        status, _h, data = self.ask("POST", "%s/api/docs/%s/images?name=cat.png" % (prefix, doc), PNG)
        self.assertEqual(status, 201, data)
        url = json.loads(data)["url"]
        self.assertEqual(url, "%s/media/%s/images/cat.png" % (prefix, doc))
        status, _h, body = self.ask("GET", url)
        self.assertEqual((status, body), (200, PNG))
        edited = LESSON + "\nimages/cat.png\n"
        self.ask("PUT", "%s/api/docs/%s" % (prefix, doc), json.dumps({"markdown": edited}).encode(),
                 {"Content-Type": "application/json"})
        status, answer = self.post(prefix + "/api/file/save", {}, 200)
        self.assertEqual((answer["ok"], answer["need"]), (False, "format"))
        self.assertEqual(answer["reasons"], [{"what": "media", "names": ["images/cat.png"]}])
        self.assertEqual(answer["suggest"], str(self.mine / "lesson.zip"))
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON)
        # as a zip
        status, answer = self.post(prefix + "/api/file/save", {"target": answer["suggest"]}, 200)
        self.assertTrue(answer["ok"], answer)
        with zipfile.ZipFile(self.mine / "lesson.zip") as zf:
            self.assertEqual(sorted(zf.namelist()), ["images/cat.png", "lesson.md"])
            self.assertEqual(zf.read("images/cat.png"), PNG)
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON, "the Markdown file is as it was")
        self.assertEqual(answer["state"]["kind"], "zip")

    def test_a_refusal_in_words_over_the_wire(self):
        prefix, doc, _answer = self.open(self.write("lesson.md", LESSON))
        status, answer = self.post(prefix + "/api/file/save", {"target": "relative.md"}, 400)
        self.assertEqual((answer["ok"], answer["code"]), (False, "path"))
        status, answer = self.post(prefix + "/api/file/save", {"target": str(store.LIB / "x.md")}, 400)
        self.assertEqual(answer["code"], "protected")

    def test_what_a_stopped_parseh_left_is_offered_back(self):
        path = self.write("lesson.md", LESSON)
        prefix, doc, _answer = self.open(path)
        self.ask("PUT", "%s/api/docs/%s" % (prefix, doc), json.dumps({"markdown": LESSON + "\nunsaved\n"}).encode(),
                 {"Content-Type": "application/json"})
        clean = self.write("clean.md", LESSON)
        clean_prefix, _doc2, _a2 = self.open(clean)
        openfile._SESSIONS.clear()                       # Parseh stopped, and started again
        left = openfile.sweep()
        self.assertEqual(left["kept"], [prefix.rsplit("/", 1)[1]])
        status, got = self.post("/api/file/sessions", {}, 200)
        self.assertEqual([(s["name"], s["dirty"], s["recovered"]) for s in got["sessions"]], [("lesson.md", True, True)])
        status, _h, page = self.ask("GET", "%s/doc/%s/edit" % (prefix, doc))
        self.assertIn("unsaved", page.decode("utf-8"), "the unsaved text is in the editor")
        status, answer = self.post(prefix + "/api/file/save", {}, 200)
        self.assertTrue(answer["ok"])
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON + "\nunsaved\n")
        self.assertFalse(answer["state"]["recovered"], "and once saved it is not a recovered one any more")

    # ---- decks
    def test_the_decks_know_the_prefix(self):
        prefix, doc, _answer = self.open(self.write("lesson.md", LESSON))
        library = deckroutes.notes_library(prefix)
        self.assertTrue(library and Path(library).name == "library" and Path(library).parent.name == prefix.rsplit("/", 1)[1])
        self.assertIsNone(deckroutes.notes_library("/open/0123456789ab"))
        status, _h, page = self.ask("GET", "%s/doc/%s" % (prefix, doc))
        self.assertIn('data-notes-source="%s"' % prefix, page.decode("utf-8"))

    # ---- who may
    def test_a_device_that_is_let_in_uses_it_too_and_is_told_whose_disk_it_sees(self):
        # the owner, 2026-10-19: not only the computer Parseh runs on.  Who is let in is serve.py's gate; the file doors
        # answer every device that reaches them -- and say, in each answer that shows a path, whose disk it is
        import socket
        path = self.write("lesson.md", LESSON)
        here = self.post("/api/file/list", {"path": str(self.mine)}, 200)[1]
        self.assertEqual((here["remote"], here["host"]), (False, socket.gethostname()))
        with mock.patch.object(network, "where", return_value=network.LAN):
            status, answer = self.post("/api/file/list", {"path": str(self.mine)}, 200)
            self.assertEqual((answer["ok"], answer["remote"], answer["host"]), (True, True, socket.gethostname()))
            self.assertEqual([e["name"] for e in answer["entries"]], ["lesson.md"])
            self.assertEqual(self.post("/api/file/places", {}, 200)[1]["remote"], True)
            prefix, doc, opened = self.open(path)
            self.assertEqual(opened["name"], "lesson.md")
            self.assertEqual(self.post("/api/file/sessions", {}, 200)[1]["remote"], True)
            status, _h, page = self.ask("GET", "%s/doc/%s" % (prefix, doc))
            self.assertEqual(status, 200)
            status, answer = self.post(prefix + "/api/file/state", {}, 200)
            self.assertEqual((answer["remote"], answer["host"]), (True, socket.gethostname()))
            # and it writes: the edit lands in the working copy, Save in the file on the host's disk
            edited = LESSON + "\nFrom another device.\n"
            self.ask("PUT", "%s/api/docs/%s" % (prefix, doc), json.dumps({"markdown": edited}).encode(),
                     {"Content-Type": "application/json"})
            status, answer = self.post(prefix + "/api/file/save", {}, 200)
            self.assertTrue(answer["ok"] and answer["remote"], answer)
            self.assertEqual(path.read_text(encoding="utf-8"), edited)
            status, answer = self.post(prefix + "/api/file/close", {}, 200)
            self.assertTrue(answer["ok"])

    def test_the_library_page_names_its_script_to_every_device(self):
        script, sheet = '<script src="/static/openfile.js"></script>', '<link rel="stylesheet" href="/static/openfile.css">'
        for where in (network.SELF, network.LAN, network.VPN):
            with mock.patch.object(network, "where", return_value=where):
                status, _h, page = self.ask("GET", "/")
            html = page.decode("utf-8")
            self.assertEqual(status, 200)
            self.assertIn(script, html, where)
            self.assertIn(sheet, html, where)
            self.assertIn('id="btn-open-file"', html)
            self.assertNotIn("{{", html)

    def test_another_site_cannot_ask(self):
        prefix, doc, _answer = self.open(self.write("lesson.md", LESSON))
        for path in ("/api/file/open", "%s/api/file/save" % prefix):
            status, _h, data = self.ask("POST", path, json.dumps({"path": str(self.mine / "lesson.md")}).encode(),
                                        {"Content-Type": "application/json", "Sec-Fetch-Site": "cross-site"})
            self.assertEqual(status, 403, path)

    def test_a_browser_that_resets_a_kept_connection_is_not_a_fault(self):
        # the studio run on its own printed a traceback each time a page was closed (the reset comes out of the next
        # read on a connection kept open): the hub's server says nothing of its clients going away, and so does this
        import socket
        import struct
        import time
        seen = mock.Mock()
        with mock.patch.object(self.srv, "handle_error", seen):
            for _ in range(3):
                c = socket.create_connection(("127.0.0.1", self.port), timeout=10)
                c.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))   # close with a reset
                c.close()
            time.sleep(0.5)
            self.assertEqual(self.ask("GET", "/api/status")[0], 200, "and the server goes on")
        seen.assert_not_called()

    def test_the_mount_does_not_leak_into_the_next_request(self):
        self.open(self.write("lesson.md", LESSON))
        # a connection that has just served a session serves the library next: its library is the studio's
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        self.addCleanup(c.close)
        for path in ("/api/docs", "/api/status"):
            c.request("GET", path)
            r = c.getresponse()
            r.read()
            self.assertEqual(r.status, 200, path)
        self.assertEqual(server.current_session(), None)
        self.assertEqual(store.lib(), store.LIB)


if __name__ == "__main__":
    unittest.main()
