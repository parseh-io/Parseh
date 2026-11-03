# SPDX-License-Identifier: GPL-3.0-or-later
"""What Parseh is under, and what it carries and fetches under other licences.

    python3 -m unittest discover -s tests -p test_licences.py

Parseh is GPL-3.0-or-later, and every source file of its own says so in an
SPDX line; a file that is somebody else's work does not.  The fonts travel
with their licence: every font in lib/fonts/ is named in its README, in
OFL.txt with its copyright notice, and in lib/notices.py, which draws the
app's Licences page (/licences/) -- linked from the hub in both layouts, and
naming, for each download of the reading help, the licence its downloader
writes into the file.  The guide's compile copies the licences beside the
fonts.  And the old duplicates are gone: the video player's copies of three
fonts, and the PDF manual, whose address now opens the guide.
"""
import json
import http.client
import re
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "html-guide", "."):
    sys.path.insert(0, str(ROOT / p))
FONTS = ROOT / "lib" / "fonts"
SPDX = "SPDX-License-Identifier: GPL-3.0-or-later"

# What is Parseh's own source: these kinds of file, anywhere in the checkout...
SOURCE = re.compile(r"\.(py|js|mjs|css|sh|bat|lua|tex|html)$|(^|/)Parseh\.command$")
# ...but for somebody else's work, what a compile makes, and the tests' data
NOT_OURS = ("lib/mathjax/", "html-guide/site/", "tests/fixtures/")
NOT_OURS_FILES = {
    # hyph-utf8's, under the LPPL or MIT, with its own header
    "markdown/exlex/assets/hyph/hyph-it.tex",
    # copied into every document the studio writes, which is its writer's:
    # a GPL line there would land in somebody's own .tex
    "markdown/exlex/template.tex",
    # the same for a page for a website (markdown/app/webexport.py): the
    # skeleton of the one file a document or a deck is exported as, which
    # is its writer's page on the writer's website
    "markdown/app/templates/export_doc.html",
    "markdown/app/templates/export_deck.html",
}


def own_sources():
    """Parseh's own source files, tracked or about to be (untracked and not
    ignored) -> relative paths; None when this is not a git checkout."""
    try:
        r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                           cwd=ROOT, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode:
        return None
    out = []
    for rel in sorted(set(r.stdout.split("\n"))):
        if not rel or not SOURCE.search(rel) or rel.startswith(NOT_OURS) or rel in NOT_OURS_FILES:
            continue
        if (ROOT / rel).is_file():               # not deleted in the working tree
            out.append(rel)
    return out


class Spdx(unittest.TestCase):
    def test_every_source_file_of_parseh_says_its_licence(self):
        files = own_sources()
        if files is None:
            self.skipTest("not a git checkout")
        self.assertGreater(len(files), 200)
        missing = []
        for rel in files:
            head = (ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines()[:3]
            if not any(SPDX in line for line in head):
                missing.append(rel)
        self.assertEqual(missing, [], "each needs `%s` in its first lines, in its own comment "
                                      "syntax (after a shebang or a doctype)" % SPDX)

    def test_somebody_else_s_work_does_not_say_it_is_parseh_s(self):
        for rel in ("lib/mathjax/tex-svg.js", "markdown/exlex/assets/hyph/hyph-it.tex",
                    "markdown/exlex/template.tex", "markdown/app/templates/export_doc.html",
                    "markdown/app/templates/export_deck.html"):
            self.assertNotIn("GPL-3.0-or-later", (ROOT / rel).read_text(encoding="utf-8"), rel)

    def test_a_shebang_stays_first(self):
        files = own_sources()
        if files is None:
            self.skipTest("not a git checkout")
        for rel in files:
            lines = (ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            self.assertFalse(len(lines) > 1 and lines[1].startswith("#!"), rel)

    def test_the_readmes_say_the_same(self):
        top = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("GPL-3.0-or-later", top)
        # the copyright line, and the author's two links, in the License section
        import author
        licence = top[top.index("\n## License"):]
        self.assertIn("Copyright © 2026 Bruno Ursino, the author of Parseh", licence)
        self.assertIn("[GitHub](%s)" % author.GITHUB_URL, licence)
        self.assertIn("[imbrunoursino.net](%s)" % author.SITE_URL, licence)
        studio = (ROOT / "markdown" / "README.md").read_text(encoding="utf-8")
        self.assertIn("GPL-3.0-or-later", studio)
        self.assertNotIn("Code: MIT", studio)
        self.assertIn("GNU GENERAL PUBLIC LICENSE", (ROOT / "LICENSE").read_text(encoding="utf-8"))


class Fonts(unittest.TestCase):
    def fonts_on_disk(self):
        return sorted(p.name for p in FONTS.iterdir() if p.suffix in (".ttf", ".otf", ".woff2"))

    def test_every_font_is_named_everywhere_it_must_be(self):
        import notices
        # two families of faces, under two licences: the Noto/Vazirmatn ones
        # under the OFL, which carries a copyright line per font, and the TeX
        # Gyre ones under the GUST licence, which carries one text for the
        # whole family (TO-DO §2.23 put them in lib/fonts/ so that a machine
        # without TeX keeps them)
        named = sorted(f for fam in notices.FONTS + notices.GUST_FONTS for f in fam[3])
        self.assertEqual(named, self.fonts_on_disk(),
                         "lib/notices.py FONTS + GUST_FONTS and lib/fonts/")
        readme = (FONTS / "README.md").read_text(encoding="utf-8")
        ofl = (FONTS / "OFL.txt").read_text(encoding="utf-8")
        gust = (FONTS / "GUST-FONT-LICENSE.txt").read_text(encoding="utf-8")
        page = notices.page()
        for family, version, notice, files, home in notices.GUST_FONTS:
            for f in files:
                self.assertIn("`%s`" % f, readme, "lib/fonts/README.md names " + f)
                self.assertIn(f, page, "the licences page names " + f)
            self.assertIn(family, readme)
            self.assertIn(version, readme, family)
            self.assertTrue(home.startswith("https://"), home)
        self.assertIn("LaTeX Project Public License", gust,
                      "GUST-FONT-LICENSE.txt is the licence those faces are under")
        for family, version, notice, files, home in notices.FONTS:
            for f in files:
                self.assertIn("`%s`" % f, readme, "lib/fonts/README.md names " + f)
            self.assertIn(family, readme)
            self.assertIn(version, readme, family)
            self.assertIn(notice, ofl, "OFL.txt carries the copyright notice of " + family)
            self.assertTrue(home.startswith("https://"), home)

    def test_what_is_said_of_chorus_is_where_it_is_used(self):
        # TeX Gyre Chorus sets no document: it sets the NAME Parseh, in the bar of every page of Parseh and in
        # the hub's big title (a0.5.0; before, only in the bar of the guide published on the web).  The three
        # places that say where it goes say that, and none says it "goes only into that layout" any more.
        import notices
        page = notices.page()
        para = page[page.index("TeX Gyre Pagella, TeX Gyre Heros and TeX Gyre Chorus"):]
        para = para[:para.index("</div>")] if "</div>" in para else para[:2000]
        self.assertIn("Chorus is the odd one out: no document is set in it, only the name Parseh, in the bar of "
                      "every page of Parseh and in the hub&rsquo;s title", para)
        self.assertNotIn("goes only into that layout", page)
        readme = (FONTS / "README.md").read_text(encoding="utf-8")
        chorus = readme[readme.index("**TeX Gyre Chorus**"):readme.index("## Adding a face")]
        for said in ("no document is set in it", "the bar of every page of Parseh", "the big title at the top of the hub",
                     "the studio's bars", "*Parseh guide*"):
            self.assertIn(said, chorus.replace("\n", " "), said)
        self.assertNotIn("not into the studio", readme)
        self.assertNotIn("only into that layout", readme)
        guide = (ROOT / "html-guide" / "markdown" / "reference" / "licences.md").read_text(encoding="utf-8")
        self.assertIn("Chorus sets no document, only the name Parseh, in the bar of every page of Parseh", guide)
        self.assertNotIn("only into the guide published on the web", guide)
        top = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("Chorus only in the guide published on the web", top)

    def test_the_studio_provisions_the_face_its_bar_sets_the_name_in(self):
        # app.css names TeX Gyre Chorus for the name in the studio's bar (.hublink); like the faces its sheet is set in,
        # server.py copies it from lib/fonts into static/fonts when it starts, and a phone keeps it with the others
        import tempfile
        import server
        import offline
        name = "texgyrechorus-mediumitalic.otf"
        self.assertIn((name, None), server.WEB_FONTS)
        css = (ROOT / "markdown" / "app" / "static" / "app.css").read_text(encoding="utf-8")
        self.assertIn("url(fonts/%s)" % name, css)
        with tempfile.TemporaryDirectory() as td, patch.object(server, "STATIC", Path(td)):
            server.ensure_web_fonts()
            self.assertEqual((Path(td) / "fonts" / name).read_bytes(), (FONTS / name).read_bytes())
            # and the walk the phone's list is made by finds it where it was put (its memory of file
            # checksums is the temporary tree's too, never config/)
            with patch.object(offline, "STUDIO_STATIC", td), \
                    patch.object(offline, "DIGESTS", str(Path(td) / "digests.json")):
                self.assertIn("/studio/static/fonts/" + name, [x["url"] for x in offline.studio_faces("/studio")])
        # the toolbox's own pages load it from /lib/fonts/, and the phone keeps that copy in the shared list
        self.assertIn("/lib/fonts/" + name, offline.SHARED)
        self.assertIn("url(fonts/%s)" % name, (ROOT / "lib" / "parseh.css").read_text(encoding="utf-8"))

    def test_the_licence_texts_are_there_whole(self):
        ofl = (FONTS / "OFL.txt").read_text(encoding="utf-8")
        for part in ("SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007", "PREAMBLE", "DEFINITIONS",
                     "PERMISSION & CONDITIONS", "TERMINATION", "DISCLAIMER",
                     "OTHER DEALINGS IN THE FONT SOFTWARE."):
            self.assertIn(part, ofl)
        gust = (FONTS / "GUST-FONT-LICENSE.txt").read_text(encoding="utf-8")
        self.assertIn("GUST Font License", gust)
        self.assertIn("LaTeX Project Public License", gust)

    def test_each_font_says_the_same_of_itself(self):
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            self.skipTest("fontTools is not installed (environment.yml has it)")
        import notices
        for family, version, notice, files, home in notices.FONTS:
            for f in files:
                with TTFont(str(FONTS / f), lazy=True) as font:
                    name = font["name"]
                    got = lambda i: str(name.getName(i, 3, 1, 0x409) or name.getName(i, 1, 0, 0) or "")  # noqa: E731
                    self.assertEqual(got(1), family, f)
                    self.assertEqual(got(0), notice, f)
                    self.assertIn(version, got(5), f)
                    # the licence's name in the font itself: it travels in
                    # an Anki deck that packs the face
                    self.assertIn("SIL Open Font License", got(13), f)

    def test_the_guide_copies_the_licences_beside_the_fonts(self):
        from engine import manifest
        for name in manifest.FONT_LICENCES:
            self.assertTrue((FONTS / name).is_file(), name)
            self.assertIn("lib/fonts/" + name, manifest.RUNTIME_FILES)
        self.assertFalse(hasattr(manifest, "MANUAL"), "there is no PDF manual to copy")

    def test_the_video_player_s_copies_are_gone(self):
        self.assertFalse((ROOT / "youtube" / "lib" / "fonts").exists())
        import anki_export
        import serve
        self.assertEqual(anki_export.FONT_DIRS, (str(FONTS),))
        self.assertFalse(hasattr(anki_export, "FONT"))
        self.assertNotIn("/youtube/lib/fonts/", serve.STATIC_PREFIXES)
        self.assertFalse(serve.static_ok("/youtube/lib/fonts/Vazirmatn.woff2"))


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import notices
        cls.html = notices.page()

    def test_the_notices_the_gpl_asks_for(self):
        self.assertIn("GPL-3.0-or-later", self.html)
        # the copyright is the author's, by name (the owner, 2026-09-28: the
        # page said "the Parseh authors" before); his two links are lib/author.py's
        import author
        self.assertIn('<p class="by">Copyright &copy; 2026 Bruno Ursino, the author of Parseh &mdash; %s</p>'
                      % author.links(), self.html)
        self.assertNotIn("the Parseh authors", self.html)
        self.assertIn("either\nversion 3 of the License, or (at your option) any later version", self.html)
        self.assertIn("without any\nwarranty", self.html)
        self.assertIn('href="/licences/LICENSE"', self.html)

    def test_both_layouts_and_nothing_that_edits(self):
        self.assertIn("<body class=\"index\" data-mobile-page>", self.html)
        self.assertIn('<div class="parseh-bar" data-layout="browser">', self.html)
        self.assertIn('<div class="parseh-bar m-bar" data-layout="mobile">', self.html)
        for word in ("<form", "<input", "<textarea", "data-parseh-stop", "data-del"):
            self.assertNotIn(word, self.html)
        # registered as its own mobile version, as the hub is
        js = (ROOT / "lib" / "parseh.js").read_text(encoding="utf-8")
        self.assertIn("{ match: /^\\/licences\\/$/, to: '/licences/' }", js)

    def test_what_it_carries(self):
        import notices
        for family, version, notice, files, home in notices.FONTS:
            self.assertIn("%s %s" % (family, version), self.html)
            self.assertIn(notice.replace("&", "&amp;"), self.html)
        for said in ("TeX Gyre Pagella", "GUST Font License", "MathJax 3.2.2", "Apache License 2.0",
                     "hyph-it.tex", "Claudio Beccari", "tests/fixtures/README.md"):
            self.assertIn(said, self.html)
        # MathJax is the version the checkout holds
        self.assertIn("MathJax 3.2.2", (ROOT / "lib" / "mathjax" / "README.md").read_text(encoding="utf-8"))

    def test_what_it_fetches_is_what_the_downloaders_write(self):
        import html
        import decomposition
        import getcorpus
        import getdict
        import getmt
        import getstt
        import getsyn
        import getarasaac
        import notices
        text = html.unescape(self.html)
        for source, licence in ((getdict.SOURCE, getdict.LICENCE), (getcorpus.SOURCE, getcorpus.LICENCE),
                                (getmt.MODEL_SOURCE, getmt.MODEL_LICENCE),
                                ("bergamot-translator " + getmt.ENGINE_VERSION, getmt.ENGINE_LICENCE),
                                (getsyn.SOURCE, getsyn.LICENCE),
                                # Speech to text's program; model sources now come
                                # from the shared catalogue, rather than one old line.
                                (getstt.SOURCE, getstt.LICENCE),
                                # the ARASAAC pictograms: the credit ARASAAC's terms give, word for word
                                (getarasaac.CREDIT, getarasaac.LICENCE)):
            self.assertIn(source, text)
            self.assertIn(licence, text)
        self.assertIn('OpenAI Whisper large-v3-turbo and large-v3', text)
        for model in getstt.MODELS:
            info = getstt.MODEL_INFO[model]
            self.assertIn(info['label'], text)
            self.assertIn(info['source'], text)
            self.assertIn(info['licence'], text)
            self.assertIn(info['licence'], notices.LICENCE_URLS)
            package = getstt.MODEL_PINS.get(model)
            if package:
                self.assertIn(package['repo'], text)
                package_licence = info.get('package_licence') or info['licence']
                self.assertIn(package_licence, text)
                self.assertIn(package_licence, notices.LICENCE_URLS)
        # the program carries more than one licence, each said with what carries it
        for what, licence in getstt.RUNTIME_LICENCES:
            self.assertIn(what, text)
            self.assertIn(licence, text)
            self.assertIn(licence, notices.LICENCE_URLS)
        self.assertIn("the codecs inside those libraries keep their own", text)
        # the packages the list names besides, and what CTranslate2's wheels bundle, in one sentence:
        # the guide's page on speech to text says the same
        self.assertIn(getstt.RUNTIME_REST, text)
        self.assertIn("Intel MKL and oneDNN", text)
        self.assertIn("on an Intel Mac", text, "the older onnxruntime that computer takes")
        self.assertIn(getstt.ONNXRUNTIME_INTEL_MAC, text)
        for said in ("Speech to text: the program", "Speech to text: the models", "stt/runtime/", "stt/models/"):
            self.assertIn(said, text)
        self.assertIn(getmt.ENGINE_LICENCE, getmt.ENGINE_SOURCE)
        for pack in decomposition.PACKS.values():
            self.assertIn(pack["name"], text)
            self.assertIn(pack["attribution"], text)
            self.assertIn(pack["licence"], text)
        # and every licence named has somewhere to be read
        named = [getdict.LICENCE, getcorpus.LICENCE, getmt.MODEL_LICENCE, getmt.ENGINE_LICENCE,
                 getstt.LICENCE, getstt.MODEL_LICENCE, getarasaac.LICENCE]
        # the pictograms' licence asks something of what is made with them, and says so here
        for said in ("ARASAAC pictograms", "arasaac/LICENSE-ARASAAC.txt", "never for commercial use",
                     "shared on the same licence", "api.arasaac.org", "static.arasaac.org"):
            self.assertIn(said, text)
        named += [p["licence"] for p in decomposition.PACKS.values()]
        for licence in named:
            self.assertIn(licence, notices.LICENCE_URLS, licence)

    def test_speech_model_credits_distinguish_source_and_package_licences(self):
        import getstt
        import notices
        credits = notices.speech_credits()
        for model in getstt.MODELS:
            info = getstt.MODEL_INFO[model]
            source, licence = credits['speech:' + model]
            self.assertIn(info['source'], source)
            self.assertIn(notices.licence_link(info['licence']), licence)
            package_licence = info.get('package_licence')
            if package_licence and package_licence != info['licence']:
                self.assertIn('(source)', licence)
                self.assertIn(notices.licence_link(package_licence) + ' (CTranslate2 package)', licence)


def hub_html():
    import serve
    with patch.object(serve, "book_stats", lambda: []), \
            patch.object(serve.studio.store, "list_docs", lambda: []), \
            patch.object(serve.ytpages, "stats", lambda: {"channels": 0, "videos": 0, "decks": 0,
                                                          "cards": 0, "by_lang": {}}), \
            patch.object(serve.studio.decks, "hub_stats", lambda *a, **k: {"decks": 0, "due": 0,
                                                                            "by_lang": {}}):
        return serve.hub_page()


class Served(unittest.TestCase):
    """The real server, over plain http on a free port."""

    @classmethod
    def setUpClass(cls):
        import serve
        cls.patch = patch.object(serve.Handler, "log_request", lambda *a, **k: None)
        cls.patch.start()
        cls.srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.patch.stop()

    def get(self, path):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=60)
        c.request("GET", path)
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, r.getheader("Content-Type") or "", r.getheader("Location") or "", body

    def test_the_page_and_the_licence_s_text(self):
        status, ctype, _, body = self.get("/licences/")
        self.assertEqual((status, ctype), (200, "text/html; charset=utf-8"))
        self.assertIn(b"GPL-3.0-or-later", body)
        status, ctype, _, body = self.get("/licences/LICENSE")
        self.assertEqual((status, ctype), (200, "text/plain; charset=utf-8"))
        self.assertEqual(body, (ROOT / "LICENSE").read_bytes())
        for path in ("/licences", "/licenses/", "/licences/index.html"):
            status, _, to, _ = self.get(path)
            self.assertEqual((status, to.rsplit(":%d" % self.srv.server_address[1], 1)[-1]),
                             (302, "/licences/"), path)
        # nothing else of the checkout is under /licences/
        for path in ("/licences/../serve.py", "/licences/README.md", "/licences/x"):
            self.assertEqual(self.get(path)[0], 404, path)

    def test_every_link_of_the_page_is_answered(self):
        import notices
        html = notices.page()
        main = html[html.index('<main class="notices">'):html.index("</main>")]
        local = sorted(set(re.findall(r'href="(/[^"]*)"', main)))
        self.assertEqual(local, ["/lib/fonts/GUST-FONT-LICENSE.txt", "/lib/fonts/OFL.txt",
                                 "/lib/mathjax/LICENSE", "/licences/LICENSE",
                                 "/settings/analysis/", "/settings/arasaac/", "/settings/reading-help/", "/settings/speech/"])
        for href in local:
            self.assertEqual(self.get(href)[0], 200, href)
        # and the ones to the licences' own pages are the web's, opened apart.
        # WIDENED for the author's two links (a0.4.1, lib/author.py), which are
        # written the way the exports' footer and the guide write theirs:
        # target first, and `noreferrer` too, so that a Parseh reached by a
        # LAN or VPN address does not tell GitHub or his site where it lives.
        # The licences' own links keep `rel="noopener" target="_blank"`.
        import author
        theirs = [author.GITHUB_URL, author.SITE_URL]
        for a in re.findall(r'<a href="https?://[^"]*"[^>]*>', main):
            if re.match(r'<a href="(%s)"' % "|".join(re.escape(u) for u in theirs), a):
                self.assertIn('target="_blank" rel="noopener noreferrer"', a)
            else:
                self.assertIn('rel="noopener" target="_blank"', a)
        self.assertEqual([re.search(r'href="([^"]*)"', a).group(1)
                          for a in re.findall(r'<a href="https?://[^"]*"[^>]*>', main)
                          if 'rel="noopener noreferrer"' in a], theirs)

    def test_the_licence_files_are_read_not_downloaded(self):
        for path in ("/lib/fonts/OFL.txt", "/lib/fonts/GUST-FONT-LICENSE.txt", "/lib/mathjax/LICENSE"):
            status, ctype, _, body = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertTrue(ctype.startswith("text/plain"), (path, ctype))
            self.assertEqual(body, (ROOT / path.lstrip("/")).read_bytes(), path)

    def test_the_pdf_manual_s_old_address_opens_the_guide(self):
        self.assertFalse((ROOT / "HOW TO USE THIS TOOLBOX.pdf").exists())
        self.assertFalse((ROOT / "guide").exists())
        status, _, to, _ = self.get("/guide.pdf")
        self.assertEqual((status, to.rsplit(":%d" % self.srv.server_address[1], 1)[-1]), (302, "/guide/"))

    def test_the_hub_leads_to_it_in_both_layouts(self):
        html = hub_html()
        browser = html[html.index('class="hub-browser"'):html.index('class="hub-mobile"')]
        mobile = html[html.index('class="hub-mobile"'):]
        self.assertIn('<a href="/licences/">licences</a>', browser)
        self.assertIn('<p class="m-foot">Free software, GPL 3 or later &middot; '
                      '<a href="/licences/">Licences</a></p>', mobile)


class FixtureProvenance(unittest.TestCase):
    def test_every_fixture_book_says_where_its_text_comes_from(self):
        readme = (ROOT / "tests" / "fixtures" / "README.md").read_text(encoding="utf-8")
        books = sorted(p.name for p in (ROOT / "tests" / "fixtures" / "books").glob("*/*") if p.is_dir())
        # one fixture book per language Parseh ships (tests/smoke.py builds each)
        shipped = json.loads((ROOT / "lib" / "languages.json").read_text(encoding="utf-8"))["_shipped"]
        self.assertEqual(len(books), len(shipped))
        for slug in books:
            self.assertIn("| `%s` |" % slug, readme, slug)
        for part in ("verbs/", "align/cases.json", "wordline.json", "Videos", "Anki decks", "Studio documents"):
            self.assertIn(part, readme)


if __name__ == "__main__":
    unittest.main()
