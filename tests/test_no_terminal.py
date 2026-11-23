# SPDX-License-Identifier: GPL-3.0-or-later
"""No page tells anyone to type a command (TO-DO §5, "GUI first", a0.6.3 lane J1).

    python3 -m unittest tests.test_no_terminal

Each test reads what a page says -- the reader's script, the library page, the
add-a-book page, the studio's refusals, the video pages -- and holds it to the
rule: where a step is needed a button does it, where something must be
installed a Settings door is named, and never a command.  The buttons
themselves are driven in tests/no_terminal.mjs."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app",
               ROOT / "lib", ROOT / "youtube" / "lib", ROOT):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

# what a terminal instruction looks like, in a page's words
COMMAND = re.compile(r"python3? [\w/.-]+\.py|\./(?:serve|build)\.sh|pip install|conda run")


def _source(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class TheReader(unittest.TestCase):
    """5.2: the reader's script (lib/tex2html.py) names no serve.py to run."""

    def test_no_serve_py_on_the_reader(self):
        src = _source("lib/tex2html.py")
        for said in ("served by python3 serve.py", "restart python3 serve.py",
                     "serve it with ' +\n      '<code>python3 serve.py</code>",
                     "is this page served by serve.py?", "needs the page served by serve.py"):
            self.assertNotIn(said, src)

    def test_says_what_to_do_from_the_pages(self):
        src = _source("lib/tex2html.py")
        self.assertIn("needs this page opened from Parseh while it runs; nothing was written", src)
        self.assertIn("start Parseh again the way you started it before and reload this page", src)
        self.assertIn("open this book from ' +\n      'Parseh’s library", src)


class MissingPackages(unittest.TestCase):
    """5.3, 5.13: a missing rapidfuzz or zstandard points at Settings > Updating
    Parseh, whose section lists what is missing and has the button that adds it."""

    def test_both_are_in_the_lists_the_installers_read(self):
        import runtime
        names = {n for _m, n, _w in runtime.PACKAGES}
        self.assertIn("rapidfuzz", names)
        self.assertIn("zstandard", names)
        spec = {name for name, _s in runtime.env_spec()["pip"]}
        self.assertIn("rapidfuzz", spec)
        self.assertIn("zstandard", spec)

    def test_the_narration_panel_points_at_the_door(self):
        src = _source("lib/tex2html.py")
        self.assertNotIn("pip install rapidfuzz", src)
        self.assertIn('href="/settings/update/#packages"', src)

    def test_the_anki_page_points_at_the_door(self):
        import ytpages
        said = ytpages._explain(ModuleNotFoundError("No module named 'zstandard'"))
        self.assertNotRegex(said, COMMAND)
        self.assertNotIn("conda", said)
        self.assertIn("/settings/update/#packages", said)

    def test_the_update_page_lists_them_with_a_button(self):
        import updatepage
        pk = {"missing": [{"name": "rapidfuzz", "what": "aligning a narration"}], "job": {}}
        html = updatepage._packages_section(pk, True)
        self.assertIn('id="packages"', html)
        self.assertIn("<b>rapidfuzz</b>", html)
        self.assertIn("data-pk-add", html)
        # another device sees the list and no button it would be refused
        self.assertNotIn("data-pk-add", updatepage._packages_section(pk, False))
        # nothing missing, nothing running: no section at all
        self.assertEqual(updatepage._packages_section({"missing": [], "job": {}}, True), "")

    def test_the_route_is_the_computers_alone(self):
        import settingspage
        self.assertEqual(settingspage.ROUTES["/settings/api/update/packages"], ("parseh.update",))

    def test_start_refuses_without_an_environment_and_adds_with_one(self):
        from unittest import mock
        import envpackages
        import runtime
        with mock.patch.object(runtime, "find_env", lambda: (None, None)):
            answer, status = envpackages.start()
        self.assertEqual(status, 409)
        self.assertNotRegex(answer["error"], COMMAND)
        added = []
        state = {"have": False}

        def status_now():
            return {"packages": [{"name": "rapidfuzz", "what": "x", "have": state["have"]}]}

        def complete(prefix, python, report):
            added.append((prefix, python))
            report.log("pip says it installed rapidfuzz")
            state["have"] = True
            return True
        with mock.patch.object(runtime, "find_env", lambda: ("/env", "/env/bin/python")), \
                mock.patch.object(runtime, "status", status_now), \
                mock.patch.object(runtime, "complete_env", complete):
            answer, status = envpackages.start()
            self.assertEqual((status, answer.get("running")), (200, True))
            import time
            for _ in range(100):
                if not envpackages.job().get("running"):
                    break
                time.sleep(0.02)
            job = envpackages.job()
            self.assertTrue(job["ok"], job)
            self.assertEqual(job["log"], ["pip says it installed rapidfuzz"])
            self.assertEqual(added, [("/env", "/env/bin/python")])
            self.assertEqual(envpackages.start()[0].get("nothing"), True)


class TheLibraryPage(unittest.TestCase):
    """5.5: the library page names no make_index.py or build.sh; a button writes
    the list again (POST /books/__relist)."""

    def _page(self):
        import tempfile
        from unittest import mock
        import languages
        import make_index
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(make_index, "BOOKS_DIR", tmp), \
                mock.patch.object(make_index, "all_books", lambda: []), \
                mock.patch.object(languages, "write_css", lambda *a, **k: None):
            make_index.main()
            return Path(tmp, "index.html").read_text(encoding="utf-8")

    def test_the_page_has_the_button_and_no_command(self):
        html = self._page()
        self.assertIn("data-relist>write the list again</button>", html)
        self.assertIn("fetch('/books/__relist'", html)
        self.assertNotIn("./build.sh", html)
        self.assertNotIn("make_index.py", html)
        self.assertNotRegex(html, COMMAND)

    def test_the_route_is_named_for_the_activity_list(self):
        import serve
        self.assertEqual(serve.long_work("POST", "/books/__relist", {})[:2],
                         ("build", "Writing the list of books again"))


class TheAddABookPage(unittest.TestCase):
    """5.6: the add-a-book page says the PDF comes from a button, never ./build.sh."""

    def test_no_build_sh(self):
        import newbook
        html = newbook.page()
        self.assertNotIn("build.sh", html)
        self.assertNotIn("serve.sh", html)
        self.assertNotRegex(html, COMMAND)
        self.assertIn("<b>build the PDF now</b> in the answer", html)
        self.assertNotIn("build.sh", newbook.MAIN_TEX)


class TheBundleNote(unittest.TestCase):
    """5.7: a text bundle over a narrated book says a build restores the timings."""

    def test_says_the_build_writes_them_back(self):
        import json
        import tempfile
        import bundle
        with tempfile.TemporaryDirectory() as tmp:
            old, dest = Path(tmp, "old"), Path(tmp, "dest")
            old.mkdir()
            dest.mkdir()
            (old / "book.json").write_text(json.dumps({"audio": "audio/a.m4a"}), encoding="utf-8")
            (dest / "book.json").write_text("{}", encoding="utf-8")
            (dest / "audio").mkdir()
            (dest / "audio" / "a.m4a").write_bytes(b"x")
            (note,) = bundle._reattach(str(dest), str(old), ["audio", "timings.json"])
        self.assertNotRegex(note, COMMAND)
        self.assertNotIn("timestamp.py", note)
        self.assertIn("comments, which is what the reader reads them from: the next build of the book "
                      "(build on its card in the library) writes them back", note)
        self.assertIn("`% @par`", note)


class TranslationPairs(unittest.TestCase):
    """5.9: once the service's list has been read, only its pairs are offered."""

    def test_the_list_read_is_what_is_offered(self):
        import io as _io
        import json
        import tempfile
        from unittest import mock
        import getmt
        import lookuppage
        recs = [{"fromLang": a, "toLang": b} for a, b in (
            ("fa", "en"), ("en", "it"), ("it", "en"), ("ja", "en"), ("tr", "en"), ("es", "en"),
            ("en", "es"), ("zh-Hans", "en"), ("de", "en"), ("en", "de"), ("fr", "en"))]
        body = json.dumps({"data": recs}).encode()

        class Answer(_io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(getmt, "MT_DIR", tmp):
            # before the list was ever read: the rule
            self.assertIsNone(getmt.offered())
            self.assertTrue(getmt.trainable("en", "fa"))
            with mock.patch.object(getmt.urllib.request, "urlopen", lambda *a, **k: Answer(body)):
                getmt._records()
            self.assertTrue(getmt.trainable("fa", "en"))
            self.assertTrue(getmt.trainable("zh", "en"))         # the service calls it zh-Hans
            self.assertFalse(getmt.trainable("en", "fa"))        # English to Persian: none
            self.assertFalse(getmt.trainable("fa", "it"))
            can = {m["code"]: m["can"] for m in lookuppage.models()}
            self.assertEqual(can["fa"], ["en"])
            self.assertNotIn("fa", can["en"])
            self.assertIn("it", can["en"])

    def test_a_short_list_is_not_kept(self):
        import tempfile
        from unittest import mock
        import getmt
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(getmt, "MT_DIR", tmp):
            getmt._remember_pairs([{"fromLang": "fa", "toLang": "en"}])
            self.assertIsNone(getmt.offered())


class WordModels(unittest.TestCase):
    """5.10: Chinese's word models are fetched from Settings > Reading help, by
    the reading downloads' own job (kind "words"), never `words.py --fetch`."""

    def setUp(self):
        import os
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.was = os.environ.get("PKUSEG_HOME")
        os.environ["PKUSEG_HOME"] = self.tmp.name

    def tearDown(self):
        import os
        if self.was is None:
            os.environ.pop("PKUSEG_HOME", None)
        else:
            os.environ["PKUSEG_HOME"] = self.was
        self.tmp.cleanup()

    def _fake_fetch(self, code, say=print):
        import os
        import segmenter
        for m in segmenter.MODELS[code]:
            d = os.path.join(self.tmp.name, m["name"])
            os.makedirs(d, exist_ok=True)
            open(d + ".zip", "wb").close()
            for f in m["files"]:
                open(os.path.join(d, f), "wb").close()
        say("fetched")
        return True

    def test_the_row_is_offered_for_chinese_alone(self):
        import lookuppage
        wm = lookuppage.word_models()
        self.assertEqual(sorted(wm), ["zh"])
        self.assertFalse(wm["zh"]["have"])
        self.assertIn("get: 'getwords'", lookuppage.SCRIPT)
        self.assertEqual(lookuppage.sizes()["words:zh"]["download"], 76_000_000)

    def test_get_it_runs_the_job_and_the_models_are_there(self):
        from unittest import mock
        import segmenter
        import serve
        import settingspage
        import words
        self.assertEqual(settingspage.ROUTES["/lookup/api/getwords"], ("reading.get",))
        self.assertEqual(serve.Handler._reading_key("getwords", {"code": "zh"}), ("words", "zh"))
        self.assertEqual(serve.reading_check("words", "ja")[1], 400)
        with mock.patch.object(segmenter, "available", lambda code: True), \
                mock.patch.object(words, "fetch_models", self._fake_fetch):
            self.assertIn(("words", "zh"), serve.queue_steps("zh", "en"))
            answer, status = serve.reading_start("words", "zh", wait=True)
            self.assertEqual(status, 200, answer)
            job = serve.reading_job("words", "zh")
            self.assertEqual((job["error"], job["say"]), ("", "done"))
            self.assertTrue(all(m["have"] for m in segmenter.models("zh")))
            self.assertNotIn(("words", "zh"), serve.queue_steps("zh", "en"))

    def test_without_the_analyzer_it_says_where_it_comes_from(self):
        from unittest import mock
        import getwords
        import segmenter
        with mock.patch.object(segmenter, "available", lambda code: False):
            with self.assertRaises(SystemExit) as e:
                getwords.build("zh", say=lambda m: None)
        self.assertNotRegex(str(e.exception), COMMAND)
        self.assertIn("Settings > Updating Parseh", str(e.exception))


class TheStudiosPdf(unittest.TestCase):
    """5.12: the studio's PDF refusals name no exlex.py setup, and say plainly
    what cannot be installed from the pages."""

    def test_large_print_without_extsizes(self):
        import texgen
        line = texgen.print_class_tex(14)
        self.assertNotIn("package manager", line)
        self.assertIn("Parseh cannot add it from its pages yet: build at Normal print size", line)

    def test_no_setup_command_and_no_bare_install(self):
        src = _source("markdown/app/server.py")
        self.assertNotIn("exlex.py setup", src)
        self.assertNotIn("xelatex not found — install TeX Live", src)
        self.assertIn("not from Parseh's pages; once it is there, build ", src)


if __name__ == "__main__":
    unittest.main()
