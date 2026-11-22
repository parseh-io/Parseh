# SPDX-License-Identifier: GPL-3.0-or-later
"""Who may change what, and the reading help's home in Settings (TO-DO §11.10).

    python3 -m unittest tests/test_settings_risk.py

WHO MAY SAVE IS A PROPERTY OF THE SETTING (the owner, 2026-09-24): one table
in lib/settingspage.py names every setting, and for each risky one the part
of the sentence it trips -- "a setting is risky when it changes who may
reach Parseh, what Parseh exposes, or what Parseh will run".  Here, as tests:

  * the table is complete: every route serve.py answers under /settings/api/
    and /lookup/api/ is in it, and every route in it is answered -- a route
    somebody adds without writing it down fails this file, and is refused
    at run time for everybody;
  * a phone let in over the Wi-Fi is refused a Network change, in the words
    of the setting's own entry, and may get and remove a download;
  * the live pairing code is on the computer's page and not on a phone's;
  * /lookup/ answers with a redirect that keeps the fragment, forever, and
    the API stays where it was;
  * a download reports how far it has got, can be stopped, says what it
    costs before it starts, is refused when the disk has no room, and "get
    everything" runs one step at a time on the server -- all through the job
    tables, with the downloaders stubbed (lib/download.py's interface: build
    and plan, with say, progress and cancel).

The real server, over plain http on a free port, with the dictionaries,
corpora, models and packs pointed at a temporary folder and the network
settings with them: nothing here writes the checkout's dict/ or config/.
"""
import ast
import http.client
import json
import os
import shutil
import re
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    sys.path.insert(0, str(ROOT / p))
import network                                                 # noqa: E402
import settingspage                                            # noqa: E402


def routes_in_serve():
    """Every route serve.py answers under /settings/api/ and /lookup/api/,
    read from its source: the /settings/api/ addresses it names anywhere,
    and each name _lookup_api compares `what` with or _reading_key maps."""
    tree = ast.parse((ROOT / "serve.py").read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value.startswith("/settings/api/") and len(node.value) > 14 and not node.value.endswith('/'):
            found.add(node.value)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name in ("_lookup_api", "_likelihood_api"):
            prefix = {"_lookup_api": "/lookup/api/", "_likelihood_api": "/settings/api/lm-likelihood/"}[node.name]
            for c in ast.walk(node):
                if isinstance(c, ast.Compare) and isinstance(c.left, ast.Name) \
                        and c.left.id == "what":
                    for comp in c.comparators:
                        values = comp.elts if isinstance(comp, (ast.Tuple, ast.List, ast.Set)) else [comp]
                        for v in values:
                            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                                found.add(prefix + v.value)
        if node.name == "_reading_key":
            for c in ast.walk(node):
                if isinstance(c, ast.Tuple) and len(c.elts) == 3 \
                        and all(isinstance(e, ast.Constant) for e in c.elts):
                    found.add("/lookup/api/" + c.elts[1].value)
                    found.add("/lookup/api/" + c.elts[2].value)
    return found


class Table(unittest.TestCase):
    def test_every_route_serve_answers_is_in_the_table(self):
        found = routes_in_serve()
        self.assertGreater(len(found), 20, "the reading help's and Network's routes were found")
        missing = sorted(found - set(settingspage.ROUTES))
        self.assertEqual(missing, [], "a route serve.py answers must be written into "
                                      "lib/settingspage.py ROUTES, with who may use it")
        # and the table names nothing serve.py has stopped answering
        self.assertEqual(sorted(set(settingspage.ROUTES) - found), [])

    def test_every_setting_a_route_names_is_a_setting(self):
        for route, what in settingspage.ROUTES.items():
            if what in (settingspage.READ, settingspage.KNOCK):
                continue
            for setting in what:
                self.assertIn(setting, settingspage.SETTINGS, route)

    def test_what_is_risky_is_decided_by_the_sentence(self):
        S = settingspage.SETTINGS
        for key in ("network.doors", "network.extra", "network.port", "network.code",
                    "network.forget"):
            self.assertEqual(S[key][0], settingspage.REACH, key)
        self.assertEqual(S["network.cert"][0], settingspage.EXPOSE)
        self.assertEqual(S["parseh.update"][0], settingspage.RUN)
        for key in ("reading.get", "reading.remove", "reading.stop"):
            self.assertIsNone(S[key][0], key)
        # the LaTeX drawings (TO-DO §8.39) are NOT risky (the owner, 2026-09-26; he
        # had made them the computer's alone on 2026-09-24): a theme, a rename,
        # an import, a package, how long TeX may run and forgetting the drawings
        # nothing uses are open to any device that has been let in
        for key in ("latex.theme", "latex.rename", "latex.import", "latex.packages",
                    "latex.limit", "latex.forget"):
            self.assertIsNone(S[key][0], key)
        self.assertEqual(settingspage.ROUTES["/settings/api/latex/export"], settingspage.READ)
        self.assertEqual(settingspage.ROUTES["/settings/api/latex/state"], settingspage.READ)
        # SPEECH TO TEXT (TO-DO §7.23, a0.4.1) is NOT risky either, and the OWNER decided it
        # on 2026-09-28 -- against the brief's own draft, which had the program's install as
        # the computer's alone (RUN): getting it, taking it away and stopping either are open
        # to any device that has been let in, and it has a door of its own.  Nothing a device
        # sends becomes anything that is fetched: the only bytes that can arrive are the
        # hash-checked wheels of lib/stt-requirements.txt and the files of two models at a
        # pinned revision (lib/getstt.py), so whoever presses the button gets the same files.
        for key in ("speech.get", "speech.remove", "speech.stop"):
            self.assertIsNone(S[key][0], key)
        for route in ("speech", "speechcheck"):
            self.assertEqual(settingspage.ROUTES["/lookup/api/" + route], settingspage.READ)
        for route, key in (("getspeech", "speech.get"), ("dropspeech", "speech.remove"),
                           ("stopspeech", "speech.stop")):
            self.assertEqual(settingspage.ROUTES["/lookup/api/" + route], (key,))
        # A BOOK MADE BY AN AGENT, IN PLACE (TO-DO §8.40, a0.4.2) HAS NO SETTING any more: it had two,
        # making the folder and Finish, both the computer's alone, and the owner took that back on
        # 2026-09-29 ("there is no actual reason to restrict the operations of W7 to the local").
        # Making the folder, giving it text a part at a time, the panel, an ask, Finish and reopening
        # are any device's; opening the folder is the computer's as a FACT about the request, and no key
        for key in ("making.folder", "making.finish"):
            self.assertNotIn(key, S, "a key nobody is refused by is a key nobody needs")
        self.assertEqual(settingspage.ELSEWHERE, (), "no setting is left whose control is on another page")
        # YOUR OWN PROMPTS (brief §8.4, a0.4.2) are NOT risky: a prompt is text a person
        # copies into a chatbot -- keeping, importing and deleting one decides nothing
        # Parseh will run -- so both keys are open to any device that has been let in
        for key in ("prompts.save", "prompts.delete"):
            self.assertIsNone(S[key][0], key)
        for route in ("state", "list", "get", "parseh", "export"):
            self.assertEqual(settingspage.ROUTES["/settings/api/prompts/" + route], settingspage.READ)
        for route, key in (("save", "prompts.save"), ("uptodate", "prompts.save"),
                           ("import", "prompts.save"), ("delete", "prompts.delete")):
            self.assertEqual(settingspage.ROUTES["/settings/api/prompts/" + route], (key,))
        # THE ARASAAC PICTOGRAMS (brief §9C.2, a0.4.2) are NOT risky, for speech to text's reason:
        # nothing a device sends becomes anything that is fetched -- the only bytes that can arrive
        # are ARASAAC's own word lists and pictures, from the two hosts lib/getarasaac.py names
        for key in ("arasaac.get", "arasaac.remove", "arasaac.stop"):
            self.assertIsNone(S[key][0], key)
        for route in ("state", "plan"):
            self.assertEqual(settingspage.ROUTES["/settings/api/arasaac/" + route], settingspage.READ)
        for route, key in (("get", "arasaac.get"), ("update", "arasaac.get"), ("stop", "arasaac.stop"),
                           ("remove", "arasaac.remove")):
            self.assertEqual(settingspage.ROUTES["/settings/api/arasaac/" + route], (key,))

    def test_pictograms_is_a_door_of_its_own_open_to_any_device_let_in(self):
        doors = {d[0]: d for d in settingspage.DOORS}
        href, name, what, keys = doors["/settings/arasaac/"]
        self.assertEqual((name, keys), ("Pictograms (ARASAAC)", ("arasaac.get", "arasaac.remove", "arasaac.stop")))
        self.assertTrue(settingspage.open_to_all(keys))
        self.assertIn("any device let in", settingspage.gate(keys))
        self.assertIn('href="/settings/arasaac/"', settingspage.settings_doors("/settings/"))
        hub = settingspage.hub(arasaac_tags='<span class="tag on">13,829 pictograms</span>')
        card = re.search(r'<a class="door" href="/settings/arasaac/">.*?</a>', hub, re.S).group(0)
        self.assertIn("Pictograms (ARASAAC)", card)
        self.assertIn("any device let in", card, "the card's pill is its own door's, found by its address")
        self.assertIn("13,829 pictograms", card, "and what the page says it has")
        self.assertEqual(settingspage.door_keys("/settings/arasaac/"), keys)
        # a door of its own: no other door lists its keys, and it lists nobody else's
        listed = [k for d in settingspage.DOORS if d[0] != "/settings/arasaac/" for k in d[3]]
        self.assertFalse([k for k in keys if k in listed])

    def test_the_route_finder_sees_every_pictogram_route(self):
        found = routes_in_serve()
        for route in ("state", "plan", "get", "update", "stop", "remove"):
            self.assertIn("/settings/api/arasaac/" + route, found)

    def test_your_prompts_is_a_door_of_its_own_open_to_any_device_let_in(self):
        doors = {d[0]: d for d in settingspage.DOORS}
        href, name, what, keys = doors["/settings/prompts/"]
        self.assertEqual((name, keys), ("Your prompts", ("prompts.save", "prompts.delete")))
        self.assertTrue(settingspage.open_to_all(keys))
        self.assertIn("any device let in", settingspage.gate(keys))
        self.assertIn('href="/settings/prompts/"', settingspage.settings_doors("/settings/"))
        hub = settingspage.hub()
        card = re.search(r'<a class="door" href="/settings/prompts/">.*?</a>', hub, re.S).group(0)
        self.assertIn("Your prompts", card)
        self.assertIn("any device let in", card, "the card's pill is its own door's, found by its address")
        self.assertEqual(settingspage.door_keys("/settings/prompts/"), ("prompts.save", "prompts.delete"))

    def test_speech_to_text_is_a_door_of_its_own_and_the_only_one_that_lists_its_keys(self):
        doors = {d[0]: d for d in settingspage.DOORS}
        self.assertEqual(len(settingspage.DOORS), len(doors), "a door has an address of its own")
        self.assertNotIn('/settings/llm/', doors, 'the connection to a model service went with a0.6.3')
        self.assertIn('/settings/lm-likelihood/', doors)
        href, name, what, keys = doors["/settings/speech/"]
        self.assertEqual((name, keys), ("Speech to text", ("speech.get", "speech.remove", "speech.stop", "speech.preferences")))
        self.assertTrue(settingspage.open_to_all(keys))
        self.assertIn("any device let in", settingspage.gate(keys))
        # ...and it is NOT on the reading help's door (the owner: not a section of that page)
        self.assertFalse([k for k in doors["/settings/reading-help/"][3] if k.startswith("speech")])
        listed = [k for d in settingspage.DOORS for k in d[3]]
        self.assertEqual(len(listed), len(set(listed)), "a key is on one door")
        # a setting is on a door of Settings, or says its control is on the page of the thing it
        # acts on (the add-a-book page, a book's reader) -- and never both
        self.assertEqual(sorted(set(settingspage.SETTINGS) - set(listed) - set(settingspage.ELSEWHERE)), [],
                         "every setting is on some door")
        self.assertEqual(sorted(set(settingspage.ELSEWHERE) & set(listed)), [])
        row = settingspage.settings_doors("/settings/speech/")
        # every door but LM likelihood's, which opens only in the browser layout (data-layout comes before its class)
        self.assertEqual(row.count('<a class="sdoor'), len(settingspage.DOORS) - 1)
        self.assertIn('class="sdoor on" href="/settings/speech/" aria-current="page"', row)

    def test_the_route_finder_sees_every_speech_route(self):
        found = routes_in_serve()
        for route in ("speech", "speechcheck", "getspeech", "dropspeech", "stopspeech"):
            self.assertIn("/lookup/api/" + route, found)

    def test_a_phone_may_what_is_not_risky_and_the_computer_everything(self):
        for key in settingspage.SETTINGS:
            self.assertTrue(settingspage.may(key, network.SELF), key)
            risky = settingspage.SETTINGS[key][0] is not None
            for where in (network.LAN, network.VPN):
                self.assertEqual(settingspage.may(key, where), not risky, (key, where))
        self.assertFalse(settingspage.may("network.nothing", network.SELF),
                         "a setting nobody wrote down is refused, even to the computer")

    def test_a_route_nobody_wrote_down_is_refused(self):
        ok, why = settingspage.may_post("/lookup/api/getsomethingnew", network.SELF)
        self.assertFalse(ok)
        self.assertIn("not in the table", why)

    def test_the_refusal_names_the_part_of_the_sentence(self):
        said = settingspage.refusal("network.port")
        self.assertIn("changed on the computer Parseh runs on", said)
        self.assertIn(settingspage.REACH, said)
        self.assertIn(settingspage.SETTINGS["network.port"][1], said)


class SharedControlStyles(unittest.TestCase):
    """Settings' affirmative/quiet controls and native choice colours live once."""

    def test_go_plain_and_choice_controls_are_shared(self):
        self.assertIn(".settings :is(button, a).go, .settings :is(button, a).plain", settingspage.STYLE)
        self.assertIn("accent-color: var(--accent)", settingspage.STYLE)
        self.assertIn("input[type=radio]", settingspage.STYLE)
        # the Network page's buttons are still the top bar's chip
        self.assertIn(".settings .parseh-btn:focus-visible", settingspage.STYLE)
        # and a link that looks like a quiet action (LaTeX's Export) is one of them
        self.assertIn(".settings a.plain:focus-visible", settingspage.STYLE)
        self.assertIn(".settings button.go, .settings button.plain, .settings a.plain, "
                      ".settings button.danger { min-height: 44px; }", settingspage.STYLE)
        self.assertIn("text-decoration: none; display: inline-flex; align-items: center;",
                      settingspage.STYLE)
        read = (ROOT / "lib" / "lookuppage.py").read_text(encoding="utf-8")
        update = (ROOT / "lib" / "updatepage.py").read_text(encoding="utf-8")
        self.assertNotIn(".rh button.go,.rh button.plain", read)
        self.assertNotIn(".upd button.go,.upd button.plain", update)
        self.assertIn(".rh button.big", read)
        self.assertIn(".upd button.go.older", update)

    def test_latex_actions_use_the_shared_controls(self):
        latex = (ROOT / "lib" / "latexpage.py").read_text(encoding="utf-8")
        for action in ("data-install=", "data-edit=", "data-rename=", "data-default=",
                       "data-delete=", "data-draw-sample", "data-cancel", "data-remove=",
                       "data-package-stop=", "data-new", "data-package-plan", "data-forget"):
            self.assertIn('class="plain" ' + action, latex, action)
        for action in ("data-save>", "data-save-limit", "data-import-go", "data-package-get=",
                       "data-package-retry=", "data-package-get-all="):
            self.assertIn('class="go" ' + action, latex, action)
        self.assertIn('class="danger" data-remove-yes=', latex)
        self.assertIn('class="plain" data-import-open', latex)
        self.assertIn("picker.click()", latex, "the keyboard-focusable Import button opens its picker")
        # L13: Export is a link, and is drawn as the quiet action it is
        self.assertIn('<a class="plain" href="', latex)
        self.assertNotIn('<a class="parseh-btn"', latex)
        self.assertIn('class="plain" data-package-review=', latex)

    def test_package_review_is_explicit_and_reaches_its_result(self):
        latex = (ROOT / "lib" / "latexpage.py").read_text(encoding="utf-8")
        self.assertIn(">Review packages…</button>", latex)
        self.assertIn('data-package-panel', latex)
        self.assertIn('data-pkg-said aria-live="polite" aria-atomic="true" tabindex="-1"', latex)
        self.assertIn("panel.scrollIntoView({block: 'center', behavior:", latex)
        self.assertIn("Nothing has been downloaded.", latex)
        self.assertIn("revealPackages(root.querySelector('[data-package-get]')", latex)
        self.assertIn("var packageSerial = 0", latex)
        self.assertIn("packageRequest[row.name] !== serial", latex, "a late quote never replaces a newer ask")
        self.assertIn("Could not ask what ", latex)
        self.assertIn('aria-label="Review packages needed by ', latex)
        self.assertIn('aria-label="Get ', latex)
        for label in ('aria-label="Edit theme ', 'aria-label="Rename theme ',
                      'aria-label="Make ', 'aria-label="Export theme ',
                      'aria-label="Delete theme ', 'aria-label="Remove ',
                      'aria-label="Stop getting '):
            self.assertIn(label, latex, label)

    def test_a_missing_package_is_quoted_by_itself_and_marked_where_it_is_ticked(self):
        latex = (ROOT / "lib" / "latexpage.py").read_text(encoding="utf-8")
        # L14: asked when the page opens, after a Save, and as boxes are ticked
        for piece in ("function askQuotes(", "function wantedQuotes(", "function syncDraft(",
                      "function scheduleDraft(", "function draftNeeds(", "data-edit-missing",
                      'data-see-table', "Not installed here:", "for the theme being edited (unsaved)",
                      'aria-label="Ask again what ', "sessionStorage", "post('package-plan', {packages: names}, ASK_MS)"):
            self.assertIn(piece, latex, piece)
        self.assertIn("root.addEventListener('change'", latex)
        self.assertNotIn(">not installed</span>", latex, "the 12px marker beside each box is gone")
        self.assertIn("installed_many(", latex, "the page's files are checked by one kpsewhich")
        # the table is kept and its rows changed one by one, so nothing typed or focused is taken away
        self.assertIn("data-pkg-rows", latex)
        self.assertIn("function focusToken(", latex)

    def test_forgetting_drawings_shows_it_is_working(self):
        latex = (ROOT / "lib" / "latexpage.py").read_text(encoding="utf-8")
        # L15: the same loose bar as Updating Parseh, a disabled button, a deadline
        for piece in ('<div class="bar loose" role="progressbar"', "data-forget-bar", ".lx .bar.loose i",
                      "@keyframes lx-slide", "function forgetDrawings(", "post('forget', {}, 60000)",
                      "Looking through every document, deck and note", "reload().then(function () { say('[data-forget-said]'"):
            self.assertIn(piece, latex, piece)

    def test_compiler_facts_are_a_status_list_but_packages_stay_a_table(self):
        latex = (ROOT / "lib" / "latexpage.py").read_text(encoding="utf-8")
        self.assertIn('<dl class="tex-status">', latex)
        self.assertIn('data-compiler="', latex)
        self.assertIn('class="st ok"', latex)
        self.assertIn('Not on this computer', latex)
        self.assertIn('<h3 id="tex-packages">TeX packages</h3>', latex)
        self.assertIn('<table class="pkg-table">', latex)
        self.assertIn('data-package-row=', latex)
        self.assertIn('@media (max-width:40rem){.lx .tex-status>div{grid-template-columns:1fr;gap:4px}}', latex)


# ---------------------------------------------------------------- a server
def fake_downloader(name, plan, steps=20, pause=0.02, log=None, write=None):
    """A stand-in for one of lib/getdict.py and its siblings, with the
    interface lib/download.py gives them: build(..., say, progress, cancel)
    reporting its download and then its build, raising download.Cancelled
    when asked to stop; plan(..., probe) answering `plan`."""
    import download
    import importlib
    mod = types.ModuleType(name)
    # its constants are the real downloader's -- the page names the source
    # and the licence of each row from them (lib/notices.py credits)
    real = importlib.import_module(name)
    for attr in dir(real):
        if attr.isupper():
            setattr(mod, attr, getattr(real, attr))

    def run(args, say, progress, cancel):
        if log is not None:
            log.append(("start", name, args, time.time()))
        total = 100 * steps
        for i in range(steps + 1):
            if cancel is not None and (cancel.is_set() if hasattr(cancel, "is_set") else cancel()):
                raise download.Cancelled()
            if progress:
                progress(i * 100, total, "download")
            if say:
                say("%d of %d" % (i * 100, total))
            time.sleep(pause)
        if progress:
            progress(1, 1, "build")
        if write:
            write(*args)
        if log is not None:
            log.append(("end", name, args, time.time()))

    def build(*args, say=None, progress=None, cancel=None, **kw):
        run(args, say, progress, cancel)

    def get(say=None, force=False, progress=None, cancel=None):
        run((), say, progress, cancel)

    mod.build = build
    mod.get = get
    mod.plan = lambda *args, probe=True, **kw: dict(plan)
    return mod


class Served(unittest.TestCase):
    """The real server, with the reading help's folders and the network
    settings in a temporary tree."""

    @classmethod
    def setUpClass(cls):
        import serve
        import lookup
        import corpus
        import getmt
        import getstt
        import decomposition
        import prompts
        import getarasaac
        cls.serve = serve
        cls._td = tempfile.TemporaryDirectory()
        tmp = Path(cls._td.name)
        cls.tmp = tmp
        cls.patches = [
            patch.object(serve.Handler, "log_request", lambda *a, **k: None),
            patch.object(network, "STORE", str(tmp / "config" / "network.json")),
            patch.object(prompts, "STORE", str(tmp / "config" / "prompts.json")),
            patch.object(getarasaac, "ARASAAC_DIR", str(tmp / "arasaac")),
            patch.object(lookup, "DICT_DIR", str(tmp / "dict")),
            patch.object(corpus, "CORPUS_DIR", str(tmp / "corpus")),
            patch.object(getmt, "MT_DIR", str(tmp / "mt")),
            patch.object(getmt, "ENGINE_DIR", str(tmp / "mt" / "engine")),
            patch.object(decomposition, "DATA_DIR", tmp / "components"),
            patch.object(getstt, "STT_DIR", str(tmp / "stt")),
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

    def setUp(self):
        s = self.serve
        for table in (s.DICT_JOBS, s.CORPUS_JOBS, s.MT_JOBS, s.DECOMPOSITION_JOBS, s.SYN_JOB,
                      s.STT_JOBS, s.PLANS, s.QUEUES, s.CANCELS):
            table.clear()
        del s.QUEUE[:]

    def ask(self, method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=60)
        data = None if body is None else json.dumps(body).encode("utf-8")
        c.request(method, path, body=data,
                  headers={"Content-Type": "application/json"} if data is not None else {})
        r = c.getresponse()
        raw = r.read()
        c.close()
        try:
            got = json.loads(raw.decode("utf-8"))
        except ValueError:
            got = raw.decode("utf-8", "replace")
        return r.status, r.getheader("Location") or "", got

    def as_phone(self):
        """This test's requests come from a phone let in over the Wi-Fi: the
        address is judged the Wi-Fi's, the door is open, and the device's
        cookie is one the computer gave it."""
        return [patch.object(network, "where", lambda ip, doc=None: network.LAN),
                patch.object(network, "may_connect", lambda ip, doc=None: True),
                patch.object(network, "let_in", lambda *a, **k: True)]

    def test_likelihood_worker_host_only_model_choice_remote_and_status_redacted(self):
        import contextlib
        import lmlikelihoodconfig as lc
        from test_lm_likelihood import write_gguf
        import lmgguf
        model_path = self.tmp / 'installed-model-blob'
        write_gguf(model_path)
        model = dict(lmgguf.inspect(model_path), model_id='installed-model', source='unsloth')
        with patch.object(lc, 'CONFIG', self.tmp / 'likelihood-settings.json'), \
                patch.object(lc, 'runtime_status', return_value={'available': False, 'say': 'Not installed.'}), \
                patch.object(lc, 'discover', return_value=([model], [])):
            status, _, response = self.ask('POST', '/settings/api/lm-likelihood/save', {'source': 'unsloth'})
            self.assertEqual(status, 200)
            with contextlib.ExitStack() as stack:
                for p in self.as_phone():
                    stack.enter_context(p)
                self.assertEqual(self.ask('POST', '/settings/api/lm-likelihood/save', {'path': str(model_path)})[0], 403)
                self.assertEqual(self.ask('POST', '/settings/api/lm-likelihood/install', {})[0], 403)
                status, _, inventory = self.ask('POST', '/settings/api/lm-likelihood/models', {})
                self.assertEqual(status, 200)
                self.assertNotIn('path', inventory['models'][0])
                status, _, chosen = self.ask('POST', '/settings/api/lm-likelihood/select', {'id': inventory['models'][0]['id']})
                self.assertEqual(status, 200)
                self.assertEqual(chosen['model'], 'installed-model')
                self.assertNotIn('settings', chosen)
                self.assertNotIn(str(model_path), json.dumps(chosen))
                status, _, page = self.ask('GET', '/settings/lm-likelihood/')
                self.assertEqual(status, 200)
                self.assertIn('<fieldset disabled>', page)
                self.assertNotIn(str(model_path), page)
                self.assertIn('id="lm_models"', page)

    def test_likelihood_feature_request_cannot_override_model_or_worker(self):
        for key in ('path', 'python', 'model', 'base_url', 'gpu_layers'):
            status, _, response = self.ask('POST', '/youtube/api/transcribe/review-likelihood',
                                           {'job': 'ABCDEFGHIJKLMNOP', 'source_sha256': 'source', 'revision': 'rev', key: 'override'})
            self.assertEqual(status, 400)
            self.assertEqual(response['code'], 'bad-review')

    def stubbed(self, **mods):
        return patch.dict(sys.modules, mods)

    def wait(self, test, what, limit=10):
        end = time.time() + limit
        while time.time() < end:
            if test():
                return
            time.sleep(0.02)
        self.fail("gave up waiting for " + what)

    # ---- the move
    def test_the_old_address_answers_with_a_redirect_forever(self):
        for path in ("/lookup/", "/lookup", "/lookup/index.html"):
            status, to, _ = self.ask("GET", path)
            self.assertEqual(status, 302, path)
            self.assertTrue(to.endswith("/settings/reading-help/"), (path, to))
            # NO FRAGMENT IN THE LOCATION: the browser then keeps the one it
            # was asked for, so /lookup/#character-components lands on that
            # section of the new page (RFC 9110 10.2.2)
            self.assertNotIn("#", to)
        status, to, _ = self.ask("GET", "/lookup/?from=old")
        self.assertEqual((status, to.rsplit("/settings/", 1)[-1]), (302, "reading-help/?from=old"))
        self.assertEqual(self.ask("POST", "/lookup/", {})[0], 405, "a page is not posted to")

    def test_the_new_page_and_the_api_where_it_was(self):
        status, _, page = self.ask("GET", "/settings/reading-help/")
        self.assertEqual(status, 200)
        self.assertIn('id="rh-state"', page)
        self.assertIn("/lookup/api/", page, "its buttons post where the API has always been")
        self.assertIn('data-mobile-page', page)
        self.assertIn('data-layout="mobile"', page, "the phone's bar, like its sibling Network")
        self.assertIn('href="/settings/network/"', page, "Settings' doors, in a row")
        self.assertIn("#how-the-reading-help-works", page, "the long prose is in the guide")
        status, to, _ = self.ask("GET", "/settings/reading-help")
        self.assertEqual((status, to.rsplit(":%d" % self.srv.server_address[1], 1)[-1]),
                         (302, "/settings/reading-help/"))
        status, _, got = self.ask("POST", "/lookup/api/status", {})
        self.assertEqual(status, 200)
        self.assertEqual(len(got["languages"]), len(__import__("languages").LANGS))
        self.assertIn("dict:tr", got["sizes"])

    def test_settings_shows_the_version_and_both_doors(self):
        import version
        status, _, page = self.ask("GET", "/settings/")
        self.assertEqual(status, 200)
        self.assertIn(version.VERSION, page)
        self.assertIn('href="/settings/reading-help/"', page)
        self.assertIn("any device let in", page)
        self.assertIn("changed on the computer only", page)

    # ---- who may
    def test_a_phone_is_refused_a_network_change_in_the_entry_s_words(self):
        ps = self.as_phone()
        for p in ps:
            p.start()
        try:
            status, _, got = self.ask("POST", "/settings/api/network", {"lan": True})
            self.assertEqual(status, 403)
            self.assertEqual(got["error"], settingspage.refusal("network.doors"))
            self.assertIn(settingspage.REACH, got["error"])
            status, _, got = self.ask("POST", "/settings/api/code", {})
            self.assertEqual((status, got["error"]), (403, settingspage.refusal("network.code")))
            status, _, got = self.ask("POST", "/settings/api/forget", {"all": True})
            self.assertEqual((status, got["error"]), (403, settingspage.refusal("network.forget")))
            # a route nobody wrote down is refused whoever asks
            status, _, got = self.ask("POST", "/lookup/api/getsomethingnew", {})
            self.assertEqual(status, 404)
        finally:
            for p in reversed(ps):
                p.stop()
        # the computer itself may
        status, _, got = self.ask("POST", "/settings/api/code", {})
        self.assertEqual(status, 200)
        self.assertTrue(got["ok"])

    def making_tree(self):
        """A temporary toolbox with one book being made in it, for the doors of a book made by an
        agent: the server is told the tree is its root for the length of one test, so that nothing
        a door does can land in the owner's books/."""
        import making
        root = Path(tempfile.mkdtemp(prefix="making-doors-", dir=os.environ.get("TMPDIR") or None))
        self.addCleanup(shutil.rmtree, str(root), True)
        (root / "books").mkdir()
        made = making.make({"lang": "it", "gloss": "en", "title": "Il gatto", "title_latin": "Il gatto"},
                           {"name": "a.txt", "data": b"Il gatto dorme.\n"}, into=str(root / "books"))
        patches = [patch.object(self.serve, "ROOT", str(root)),
                   patch.object(self.serve._AtRoot, "directory", str(root))]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return root, made

    def ask_raw(self, method, path, data, content_type="application/octet-stream"):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=60)
        c.request(method, path, body=data, headers={"Content-Type": content_type})
        r = c.getresponse()
        raw = r.read()
        c.close()
        return r.status, json.loads(raw.decode("utf-8"))

    def test_a_phone_does_everything_a_book_made_by_an_agent_has_but_open_the_folder(self):
        """A book made by an agent (TO-DO §8.40) is open to every device let in (the owner, 2026-09-29):
        the folder, the instructions, the panel, an ask, the text a part at a time, 'this is all the
        text', Finish and reopening -- from a phone as from the computer.  Only opening the folder is the
        computer's, as a fact about the request: the panel is told, and given the path to copy."""
        import books as booklib
        import making
        root, made = self.making_tree()
        # nothing a door does may land in the checkout: the shelf is the temporary one, and the library page
        # (a file make_index writes) is stood in for
        for p in (patch.object(booklib, "BOOKS_DIR", str(root / "books")), patch.object(making, "_library_again", lambda: None),
                  patch.object(self.serve.Handler, "_write_library", lambda s: {"ok": True, "error": ""})):
            p.start()
            self.addCleanup(p.stop)
        shelf_before = sorted(os.listdir(root / "books" / "italian"))
        book = "/books/italian/il-gatto"
        facts = '%7B%22lang%22%3A%22it%22%2C%22gloss%22%3A%22en%22%2C%22title%22%3A%22Il%20cane%22%7D'
        ps = self.as_phone()
        for p in ps:
            p.start()
        try:
            status, _, got = self.ask("POST", "/books/__making/instructions", {"book": {"lang": "fa", "gloss": "en"}})
            self.assertEqual((status, got["ok"]), (200, True), "the instructions are shown to a phone too")
            self.assertTrue(got["skill"]["available"] and got["skill"]["text"].startswith("Parseh request · parseh-book · "),
                            "and so is the request for the book's skill, beside them")
            status, got = self.ask_raw("POST", "/books/__make?name=cane.txt&book=" + facts, b"Il cane corre.\n")
            self.assertEqual((status, got["ok"], got["here"], got["open_said"]), (200, True, False, making.OPEN_SAID), got)
            self.assertTrue((root / "books" / "italian" / "il-cane" / "original" / "cane.txt").is_file(), "a phone made a folder")
            status, _, got = self.ask("GET", book + "/__making")
            self.assertEqual((status, got["making"], got["here"], got["path"]), (200, True, False, made["path"]))
            self.assertEqual(got["open_said"], making.OPEN_SAID)
            self.assertNotIn("may", got)
            self.assertEqual(got["name"], "Il gatto")
            status, _, got = self.ask("GET", book + "/reader/__making")
            self.assertEqual((status, got["making"]), (200, True), "the reader asks relative to itself")
            status, _, got = self.ask("POST", book + "/__making/ask", {"line": "shorter glosses"})
            self.assertEqual((status, got["ok"], got["count"]), (200, True, 1))
            # what the agent reads, written again: from a phone as from the computer, a book being made only
            status, _, got = self.ask("POST", book + "/__making/instructions", {})
            self.assertEqual((status, got["ok"], got["written"][:2], got["said"]),
                             (200, True, ["AGENTS.md", "CLAUDE.md"], making.INSTRUCTIONS_AGAIN_SAID), got)
            # the text, a part at a time: pasted, and as a file that is the body of the request
            status, _, got = self.ask("POST", book + "/__making/part", {"text": "Il gatto torna.", "chapter": "new", "label": "p2"})
            self.assertEqual((status, got["ok"], got["part"]["n"], got["part"]["chapter"]), (200, True, 2, "new"), got)
            status, got = self.ask_raw("POST", book + "/__making/part?name=due.txt&chapter=last&join=paragraph&label=from+a+phone", b"E poi dorme.\n")
            self.assertEqual((status, got["ok"], got["part"]["file"], got["part"]["join"]), (200, True, "original/part-003-due.txt", "paragraph"), got)
            status, _, got = self.ask("POST", book + "/__making/more", {})
            self.assertEqual(status, 400, "a body that does not say which is not taken to mean 'this is all the text'")
            status, _, got = self.ask("POST", book + "/__making/more", {"more_coming": False})
            self.assertEqual((status, got), (200, {"ok": True, "more_coming": False}))
            status, _, got = self.ask("GET", book + "/__making")
            self.assertEqual([(p["n"], p["state"]) for p in got["parts"]], [(1, "added"), (2, "added"), (3, "added")])
            self.assertEqual(got["more_coming"], False)
            status, _, got = self.ask("POST", book + "/__build", {"what": "draft"})
            self.assertEqual(status, 409)
            self.assertIn("no chapter", got["error"])
            # opening the folder is the computer's own act: refused in words, and no file manager was started
            status, _, got = self.ask("POST", book + "/__making/open", {})
            self.assertEqual((status, got["ok"], got["error"], got["path"]), (403, False, making.OPEN_SAID, made["path"]))
            self.assertFalse((root / "opened.txt").exists())
            # Finish: the first press answers with what it waits for, and a second one starts it
            status, _, got = self.ask("POST", book + "/__making/finish", {})
            self.assertEqual((status, got["ok"], got["confirm"]), (409, False, True))
            self.assertTrue(any("part 1 has not been taken" in s for s in got["blockers"]), got)
            self.assertEqual(self.ask("GET", book + "/__making")[2]["finish"]["state"], "idle", "nothing started on the first press")
            # the second press, which says it knows, goes through: here to the check, which finds no chapter to finish
            status, _, got = self.ask("POST", book + "/__making/finish", {"confirm": True})
            self.assertEqual((status, got["ok"], got["started"]), (200, True, True), got)
            self.wait(lambda: making.finish_status(made["path"])["state"] != "running", "the check", limit=60)
            job = making.finish_status(made["path"])
            self.assertEqual(job["state"], "failed")
            self.assertIn("no chapter", job["steps"][0]["said"])
            self.assertEqual(making.state(made["path"]), "making", "a Finish that found nothing to finish ends nothing")
        finally:
            for p in reversed(ps):
                p.stop()
        self.assertEqual(sorted(os.listdir(root / "books" / "italian")), sorted(shelf_before + ["il-cane"]))
        self.assertIn("shorter glosses", (Path(made["path"]) / "ASKS.md").read_text(encoding="utf-8"))
        # the computer opens it, and is told it may
        with patch.object(making, "open_folder", lambda path: None):
            status, _, got = self.ask("POST", book + "/__making/open", {})
        self.assertEqual((status, got["ok"], got["path"]), (200, True, made["path"]))
        status, _, got = self.ask("GET", book + "/__making")
        self.assertEqual((got["here"], got["path"]), (True, made["path"]))
        # and a finished book is reopened from a phone
        making._end_making(made["path"])
        for p in ps:
            p.start()
        try:
            status, _, got = self.ask("POST", book + "/__making/part", {"text": "x"})
            self.assertEqual((status, got["ok"]), (409, False), "a finished book takes no part until it is reopened")
            self.assertIn("reopen the making", got["error"])
            status, _, got = self.ask("POST", book + "/__making/reopen", {})
            self.assertEqual((status, got["ok"], got["state"]), (200, True, "making"))
            self.assertEqual(self.ask("POST", book + "/__making/reopen", {})[0], 409, "only a finished book is reopened")
        finally:
            for p in reversed(ps):
                p.stop()

    def test_the_doors_that_write_a_book_being_made_are_shut_and_say_why_until_it_is_finished(self):
        import making
        root, made = self.making_tree()
        book = "/books/italian/il-gatto"
        locked = [("POST", book + "/reader/" + door, {}) for door in
                  ("__edit/chunk", "__edit/meta", "__divide/chunk", "__struct/section",
                   "__struct/chapter", "__region/apply", "__reading/free")]
        for method, path, body in locked:
            status, _, got = self.ask(method, path, body)
            self.assertEqual((status, got.get("making"), got["error"]), (409, True, making.LOCK_SAID), path)
        # text added to it by hand (blank chunks) would be erased by the next assembly, so it is not written:
        # it becomes a PART, which the agent takes -- not the lock's refusal, and no chunk was touched
        before = (Path(made["path"]) / "main.tex").read_bytes()
        status, _, got = self.ask("POST", book + "/__append", {"text": "Il cane corre.", "chapter": "last"})
        self.assertEqual((status, got["ok"], got["making"], got["part"]["n"], got["part"]["chapter"]), (200, True, True, 2, "last"), got)
        self.assertEqual((Path(made["path"]) / "main.tex").read_bytes(), before)
        status, _, got = self.ask("POST", book + "/__append", {"text": "Ancora."})
        self.assertEqual((status, got["part"]["chapter"]), (200, "new"), "the door's own default, as it always was")
        # the doors that do not write what an agent writes are not shut: the reading place, folding a
        # run away, the builds -- each answers as it always did (here: it has nothing to act on)
        status, _, got = self.ask("POST", book + "/reader/__reading/fold", {})
        self.assertNotEqual(status, 409, got)
        # the moment the making is over the same doors answer as they do for any book
        making._end_making(made["path"])
        # ... and so does the door that adds text by hand, which is the add page's way 2 as it always was
        # (answered here for want of a chapter to add to, which is not the lock)
        for method, path, body in locked + [("POST", book + "/__append", {"text": "more"})]:
            status, _, got = self.ask(method, path, body)
            self.assertNotEqual(status, 409, (path, got))
        self.assertEqual(self.ask("POST", book + "/__append", {"text": "more"})[2]["error"],
                         "this book has no chapters to add to (no chN.tex)")
        self.assertEqual(self.ask("GET", book + "/__making")[2]["making"], False)

    def test_every_device_is_shown_the_same_add_page_and_the_book_being_made_is_one_to_add_to(self):
        ps = self.as_phone()
        for p in ps:
            p.start()
        try:
            _, _, phone = self.ask("GET", "/books/add/")
        finally:
            for p in reversed(ps):
                p.stop()
        _, _, computer = self.ask("GET", "/books/add/")
        self.assertEqual(phone, computer, "no part of the page is shut by who is asking")
        for page in (phone, computer):
            data = json.loads(page.split('<script id="data" type="application/json">', 1)[1].split("</script>", 1)[0])
            self.assertNotIn("may_make", data)
            self.assertNotIn("may_said", data)
            self.assertNotIn("computer only", page.lower())
            self.assertIn('id="apfile"', page, "text may be sent as a file, with its PDF pages")
            self.assertIn('id="alltext"', page, "this is all the text, said where the folder is made")

    def test_a_phone_may_get_and_remove_a_download(self):
        import download
        import lookup
        made = []

        def write(code):
            os.makedirs(lookup.DICT_DIR, exist_ok=True)
            Path(lookup.path_for(code)).write_bytes(b"not really a dictionary")
            made.append(code)
        fake = fake_downloader("getdict", download.plan(download=2000, measured=True, kept=100),
                               steps=3, write=write)
        ps = self.as_phone()
        for p in ps:
            p.start()
        try:
            with self.stubbed(getdict=fake):
                status, _, got = self.ask("POST", "/lookup/api/getdict", {"code": "tr"})
                self.assertEqual((status, got.get("ok")), (200, True), got)
                self.wait(lambda: not self.serve.DICT_JOBS["tr"].get("running"), "the build")
                self.assertEqual(made, ["tr"])
                self.assertTrue(os.path.isfile(lookup.path_for("tr")))
                status, _, got = self.ask("POST", "/lookup/api/dropdict", {"code": "tr"})
                self.assertEqual((status, got.get("ok")), (200, True), got)
                self.assertFalse(os.path.exists(lookup.path_for("tr")))
        finally:
            for p in reversed(ps):
                p.stop()

    def test_a_phone_may_keep_import_and_delete_its_own_prompts_and_nothing_riskier(self):
        # brief §8.4: writing a prompt changes nothing Parseh will run, so a device let in
        # over the Wi-Fi does all of it -- and the same origin is still refused what does
        # (the update), which proves the phone is really being judged a phone
        import prompts
        body = {"surface": "video-region", "name": "British spellings",
                "text": "Prefer British spellings in {{GLOSS_LANGUAGE}}."}
        ps = self.as_phone()
        for p in ps:
            p.start()
        try:
            status, _, got = self.ask("POST", "/settings/api/prompts/save", body)
            self.assertEqual((status, got.get("ok")), (200, True), got)
            pid = got["prompt"]["id"]
            status, _, got = self.ask("POST", "/settings/api/prompts/list",
                                      {"surface": "video-region", "lang": "fa"})
            self.assertEqual([p["name"] for p in got["prompts"]], ["British spellings"])
            status, _, got = self.ask("POST", "/settings/api/prompts/save", dict(body, id=pid, name="UK"))
            self.assertEqual((status, got["prompt"]["name"]), (200, "UK"))
            status, _, raw = self.ask("GET", "/settings/api/prompts/export?id=" + pid)
            self.assertEqual((status, raw["format"]), (200, prompts.EXPORT_FORMAT))
            status, _, got = self.ask("POST", "/settings/api/prompts/import", {"data": json.dumps(raw)})
            self.assertEqual((status, got["prompt"]["name"], got["renamed_from"]), (200, "UK (2)", "UK"))
            status, _, got = self.ask("POST", "/settings/api/prompts/delete", {"id": pid})
            self.assertEqual((status, got.get("ok")), (200, True), got)
            status, _, page = self.ask("GET", "/settings/prompts/")
            self.assertEqual(status, 200)
            self.assertIn('id="pr-state"', page)
            self.assertIn("any device let in", page)
            self.assertNotIn('class="lockline"', page, "no lock line on this door, for a phone either")
            status, _, got = self.ask("POST", "/settings/api/update/apply", {})
            self.assertEqual(status, 403, "an update is still the computer's alone")
        finally:
            for p in reversed(ps):
                p.stop()
        self.assertEqual([p["name"] for p in prompts.all_of()], ["UK (2)"])

    def test_the_pairing_code_is_on_the_computer_only(self):
        live = network.say_code(network.code()["code"])
        status, _, page = self.ask("GET", "/settings/network/")
        self.assertEqual(status, 200)
        self.assertIn(live, page, "the computer sees the code")
        self.assertIn("data-fresh-code", page)
        ps = self.as_phone()
        for p in ps:
            p.start()
        try:
            status, _, page = self.ask("GET", "/settings/network/")
        finally:
            for p in reversed(ps):
                p.stop()
        self.assertEqual(status, 200)
        self.assertFalse(live in page, "a phone is never shown the live code")
        self.assertFalse('<div class="code" data-code>' in page)
        self.assertFalse('data-fresh-code>' in page)
        self.assertIn("The code is shown on the computer only.", page)
        self.assertFalse("data-save>" in page, "no dead Save button: the lock lines say why")
        self.assertIn(settingspage.SETTINGS["network.port"][1].replace("'", "&#x27;"), page)

    # ---- how far, and stopping
    def test_a_download_says_how_far_it_has_got_and_can_be_stopped(self):
        import download
        fake = fake_downloader("getdict", download.plan(download=4000, measured=True, kept=10),
                               steps=400, pause=0.01)
        with self.stubbed(getdict=fake):
            self.assertEqual(self.ask("POST", "/lookup/api/getdict", {"code": "de"})[0], 200)
            job = self.serve.DICT_JOBS["de"]
            self.wait(lambda: job.get("done", 0) >= 500, "some progress")
            self.assertEqual((job["phase"], job["total"]), ("download", 40000))
            self.assertTrue(job["running"])
            # the page's own view says the same
            _, _, got = self.ask("POST", "/lookup/api/status", {})
            self.assertTrue(got["jobs"]["dict"]["de"]["running"])
            self.assertGreater(got["jobs"]["dict"]["de"]["done"], 0)
            # and so does the activity list, with the bytes
            entry = [e for e in self.serve.activity_now()["running"]
                     if e["id"].startswith("lookup:dict:de@")]
            self.assertEqual(len(entry), 1)
            self.assertEqual(entry[0]["total"], 40000)
            status, _, got = self.ask("POST", "/lookup/api/stop", {"kind": "dict", "key": "de"})
            self.assertEqual((status, got["stopped"]), (200, True))
            self.wait(lambda: not job.get("running"), "the stop")
        self.assertTrue(job["stopped"])
        self.assertEqual(job["error"], "", "stopping is not failing")
        self.assertLess(job["done"], 40000)

    def test_what_it_costs_is_said_before_it_starts(self):
        import download
        fake = fake_downloader("getcorpus", download.plan(download=5_000_000, measured=False,
                                                          kept=2_000_000, have=1_000_000))
        with self.stubbed(getcorpus=fake):
            status, _, got = self.ask("POST", "/lookup/api/plan", {"kind": "corpus", "key": "fa-en"})
        self.assertEqual(status, 200, got)
        self.assertEqual((got["download"], got["kept"], got["have"]), (5_000_000, 2_000_000, 1_000_000))
        self.assertFalse(got["measured"])
        self.assertEqual(got["room"], "")
        self.assertGreater(got["free"], 0)
        self.assertEqual(got["named"], "the Persian–English translated sentences")
        status, _, got = self.ask("POST", "/lookup/api/plan", {"kind": "corpus", "key": "fa-fa"})
        self.assertEqual(status, 400)

    def test_nothing_starts_that_the_disk_has_no_room_for(self):
        import download
        fake = fake_downloader("getmt", download.plan(download=10, measured=True, kept=10,
                                                      peak=10 ** 18))
        with self.stubbed(getmt=fake):
            status, _, got = self.ask("POST", "/lookup/api/getmodel", {"code": "fa", "gloss": "en"})
        self.assertEqual(status, 507)
        self.assertIn("not enough room", got["error"])
        self.assertIn("free", got["error"])
        self.assertNotIn("fa-en", self.serve.MT_JOBS, "nothing was started")

    def test_get_everything_runs_on_the_server_one_step_at_a_time(self):
        import download
        import lookup
        log, made = [], []
        plan = download.plan(download=1000, measured=True, kept=500)
        mods = {name: fake_downloader(name, plan, steps=5, log=log)
                for name in ("getdict", "getdecomposition", "getcorpus", "getmt")}
        # the stand-in dictionary is "there" once its step has run: Japanese's
        # sentences are refused until it is
        mods["getdict"] = fake_downloader("getdict", plan, steps=5, log=log,
                                          write=lambda code: made.append(code))
        with self.stubbed(**mods), patch.object(lookup, "available", lambda code: code in made):
            status, _, got = self.ask("POST", "/lookup/api/plan", {"all": "ja", "gloss": "en"})
            self.assertEqual(status, 200)
            self.assertEqual([s["kind"] for s in got["steps"]],
                             ["dict", "components", "corpus", "model"],
                             "the dictionary first: Japanese's sentences are cut into words with it")
            self.assertEqual(got["download"], 4000)
            status, _, got = self.ask("POST", "/lookup/api/getall", {"code": "ja", "gloss": "en"})
            self.assertEqual((status, got["ok"]), (200, True), got)
            entry = [e for e in self.serve.activity_now()["running"]
                     if e["id"].startswith("lookup:all:ja@")]
            self.assertEqual([e["label"] for e in entry], ["Getting everything for Japanese"])
            self.wait(lambda: not self.serve.QUEUE_WORKER["running"], "the queue", 20)
        starts = [x for x in log if x[0] == "start"]
        self.assertEqual([x[1] for x in starts], ["getdict", "getdecomposition", "getcorpus", "getmt"])
        # ONE AT A TIME: each step started after the one before it ended
        ends = [x for x in log if x[0] == "end"]
        for before, after in zip(ends, starts[1:]):
            self.assertLessEqual(before[3], after[3])
        self.assertFalse(self.serve.QUEUES["ja"]["running"])


    # ---- SPEECH TO TEXT: a door of its own, open to any device let in (the owner, 2026-09-28)
    def stt_fake(self, plan=None, steps=20, pause=0.02, write=None, log=None):
        import download
        return fake_downloader("getstt", plan or download.plan(download=2000, measured=True, kept=100),
                               steps=steps, pause=pause, write=write, log=log)

    def no_card(self):
        """A look at the graphics card that finds none, so that asking never starts a child here."""
        return patch.object(self.serve.getstt, "_run_probe",
                            lambda timeout=30: {"ct2": None, "cublas": {"loads": False}, "smi": None})

    def speech_ok(self):
        """The computer's own machine may run the program: what a test of this door needs to be true anywhere."""
        return patch.object(self.serve.getstt, "unavailable_reason", lambda: "")

    def test_speech_to_text_is_open_to_the_computer_and_to_any_device_let_in(self):
        import getstt
        made = []
        fake = self.stt_fake(steps=3, write=lambda key: made.append(key))
        for phone in (False, True):
            ps = self.as_phone() if phone else []
            for p in ps:
                p.start()
            try:
                with self.stubbed(getstt=fake), self.speech_ok(), self.no_card():
                    for key in getstt.PARTS:
                        status, _, got = self.ask("POST", "/lookup/api/getspeech", {"key": key})
                        self.assertEqual((status, got.get("ok")), (200, True), (phone, key, got))
                        self.wait(lambda: not self.serve.STT_JOBS[key].get("running"), "the install of " + key)
                        self.assertEqual(self.serve.STT_JOBS[key]["error"], "")
                    self.assertEqual(sorted(made), sorted(getstt.PARTS * (2 if phone else 1)))
                    for key in getstt.PARTS:
                        # nothing to remove was made (the stand-in makes no files): a refusal would be 403
                        status, _, got = self.ask("POST", "/lookup/api/dropspeech", {"key": key})
                        self.assertEqual(status, 200, (phone, key, got))
                    status, _, got = self.ask("POST", "/lookup/api/stopspeech", {"key": "runtime"})
                    self.assertEqual((status, got["ok"]), (200, True))
                    for what in ("speech", "speechcheck"):
                        status, _, got = self.ask("POST", "/lookup/api/" + what, {})
                        self.assertEqual((status, got.get("ok")), (200, True), (what, phone))
            finally:
                for p in reversed(ps):
                    p.stop()

    def test_the_table_says_the_same_and_says_who_decided(self):
        S = settingspage.SETTINGS
        for key in ("speech.get", "speech.remove", "speech.stop"):
            self.assertIsNone(S[key][0], key)
            for where in (network.SELF, network.LAN, network.VPN):
                self.assertTrue(settingspage.may(key, where), (key, where))
        for route, key in (("getspeech", "speech.get"), ("dropspeech", "speech.remove"),
                           ("stopspeech", "speech.stop")):
            self.assertEqual(settingspage.ROUTES["/lookup/api/" + route], (key,))
        for route in ("speech", "speechcheck"):
            self.assertEqual(settingspage.ROUTES["/lookup/api/" + route], settingspage.READ)
        # the sentence says what makes it safe for any device: only what Parseh pins can be fetched
        said = S["speech.get"][1]
        self.assertIn("Whoever presses the button", said)
        self.assertIn("pins", said)
        self.assertIn("hash", said)
        # and the source records who decided it, and why, as the LaTeX drawings' does
        src = (ROOT / "lib" / "settingspage.py").read_text(encoding="utf-8")
        self.assertIn("SPEECH TO TEXT IS NOT RISKY (the owner, 2026-09-28", src)

    def test_a_phone_is_given_no_lock_line_and_no_dead_button_on_the_speech_door(self):
        status, _, page = self.ask("GET", "/settings/speech/")
        self.assertEqual(status, 200)
        ps = self.as_phone()
        for p in ps:
            p.start()
        try:
            status2, _, phone = self.ask("GET", "/settings/speech/")
            _, _, hub = self.ask("GET", "/settings/")
        finally:
            for p in reversed(ps):
                p.stop()
        self.assertEqual(status2, 200)
        for text in (page, phone):
            self.assertIn('id="sp-state"', text)
            self.assertIn("any device let in", text, "the door's pill says so")
            self.assertNotIn("data-lock=", text, "no lock line: nothing on it is the computer's alone")
            self.assertNotIn("changed on the computer only", text.split('<div id="sp">')[0].split("</nav>")[1],
                             "and no pill of that kind on the page itself")
            self.assertIn('data-mobile-page', text)
            self.assertIn('href="/settings/reading-help/"', text, "Settings' doors, in a row")
            self.assertIn('aria-current="page"', text)
        state = json.loads(phone.split('<script id="sp-state" type="application/json">', 1)[1].split("</script>", 1)[0])
        self.assertEqual(state["may"], {"speech.get": True, "speech.remove": True, "speech.stop": True, "speech.preferences": True})
        self.assertEqual(state["where"], network.LAN)
        card = hub.split('href="/settings/speech/"', 1)[1].split("</a>", 1)[0]
        self.assertIn("Speech to text", card)
        self.assertIn('gate open', card, "the hub's card says any device let in")

    def test_the_reading_help_points_to_the_door_and_does_not_carry_the_section(self):
        _, _, page = self.ask("GET", "/settings/reading-help/")
        self.assertIn('<a href="/settings/speech/">speech to text</a> has a page of its own', page)
        self.assertNotIn('data-get="speech', page)
        self.assertNotIn("Speech to text</h2>", page)
        status, to, _ = self.ask("GET", "/settings/speech")
        self.assertEqual((status, to.rsplit(":%d" % self.srv.server_address[1], 1)[-1]), (302, "/settings/speech/"))
        self.assertEqual(self.ask("POST", "/settings/speech/", {})[0], 405, "a page is not posted to")

    def test_the_status_carries_speech_its_jobs_its_sizes_and_its_credits(self):
        status, _, got = self.ask("POST", "/lookup/api/status", {})
        self.assertEqual(status, 200)
        self.assertEqual(got["speech"]["runtime"]["state"], "absent")
        import getstt
        self.assertEqual(sorted(got["speech"]["models"]), sorted(getstt.MODELS))
        self.assertTrue({'large-v3', 'large-v3-turbo'}.issubset(got['speech']['models']))
        self.assertEqual(got["jobs"]["speech"], {})
        for part in ("runtime", "large-v3-turbo", "large-v3"):
            self.assertIn("speech:" + part, got["sizes"])
            self.assertIn("speech:" + part, got["credits"])
        self.assertTrue(got["sizes"]["speech:large-v3-turbo"]["measured"])
        self.assertEqual({"speech.get", "speech.remove", "speech.stop"} - set(got["may"]), set())
        self.assertIn("MIT", got["credits"]["speech:large-v3-turbo"]["licence"])
        self.assertIn("BSD-3-Clause", got["credits"]["speech:runtime"]["licence"])

    def test_the_slim_slice_and_the_doors_own_read(self):
        with self.no_card():
            status, _, got = self.ask("POST", "/lookup/api/speech", {})
        self.assertEqual(status, 200)
        self.assertEqual({"ok", "installed", "runtime", "models", "default_model", "processing", "languages",
                          "busy", "settings"} - set(got), set())
        self.assertFalse(got["installed"])
        self.assertEqual(got["settings"], "/settings/speech/")
        import getstt
        self.assertEqual([m["id"] for m in got["models"]], list(getstt.MODELS))
        self.assertEqual([m['id'] for m in got['models'][:2]], ['large-v3-turbo', 'large-v3'])
        self.assertEqual([m["id"] for m in got["processing"]], ["auto", "cpu", "cuda"])
        status, _, full = self.ask("POST", "/lookup/api/speech", {"full": True})
        self.assertEqual({"ok", "speech", "jobs", "sizes", "credits", "languages", "kept", "free", "may"}
                         - set(full), set())
        self.assertEqual(len(full["languages"]), len(__import__("languages").LANGS))
        fa = [l for l in full["languages"] if l["code"] == "fa"][0]
        self.assertEqual((fa["rtl"], fa["whisper"]), (True, True))

    def test_the_card_is_looked_at_again_on_request_and_never_by_asking_the_status(self):
        import getstt
        with patch.object(getstt, "platform_key", return_value="linux x86_64"), \
                patch.object(getstt, "_run_probe", return_value={
                    "ct2": "4.8.2", "cuda_devices": 1, "cuda_types": ["float16", "int8_float16"],
                    "cublas": {"loads": False, "name": "libcublas.so.12"},
                    "smi": {"name": "NVIDIA GeForce GTX 1650", "memory": 4294967296, "driver": "1"}}) as probe:
            getstt.forget_hardware()
            self.ask("POST", "/lookup/api/status", {})
            self.ask("POST", "/lookup/api/speech", {"full": True})
            probe.assert_not_called()
            status, _, got = self.ask("POST", "/lookup/api/speechcheck", {})
            self.assertEqual(status, 200)
            cuda = got["speech"]["hardware"]["cuda"]
            self.assertEqual((cuda["state"], cuda["ready"]), ("found-not-ready", False))
            self.assertIn("cuBLAS for CUDA 12", cuda["missing"][0])
            self.assertTrue(got["speech"]["hardware"]["checked"])
            self.assertEqual(probe.call_count, 1)
        getstt.forget_hardware()

    def test_a_speech_install_says_how_far_it_has_got_and_can_be_stopped(self):
        import getstt
        fake = self.stt_fake(steps=400, pause=0.01)
        with self.stubbed(getstt=fake), self.speech_ok():
            self.assertEqual(self.ask("POST", "/lookup/api/getspeech", {"key": "large-v3"})[0], 200)
            job = self.serve.STT_JOBS["large-v3"]
            self.wait(lambda: job.get("done", 0) >= 500, "some progress")
            self.assertEqual((job["phase"], job["total"]), ("download", 40000))
            _, _, got = self.ask("POST", "/lookup/api/status", {})
            self.assertTrue(got["jobs"]["speech"]["large-v3"]["running"])
            _, _, door = self.ask("POST", "/lookup/api/speech", {"full": True})
            self.assertTrue(door["jobs"]["speech"]["large-v3"]["running"], "the door reads it too")
            entry = [e for e in self.serve.activity_now()["running"] if e["id"].startswith("lookup:speech:large-v3@")]
            self.assertEqual(len(entry), 1)
            self.assertEqual(entry[0]["label"], "Getting the large-v3 speech model")
            self.assertEqual(entry[0]["page"], "/settings/speech/", "the list links to the door, not the reading help")
            self.assertEqual(entry[0]["total"], 40000)
            # the generic stop is the reading help's, and refuses speech: its own route is its own setting
            status, _, got = self.ask("POST", "/lookup/api/stop", {"kind": "speech", "key": "large-v3"})
            self.assertEqual(status, 400)
            self.assertTrue(job["running"])
            status, _, got = self.ask("POST", "/lookup/api/stopspeech", {"key": "large-v3"})
            self.assertEqual((status, got["stopped"]), (200, True))
            self.wait(lambda: not job.get("running"), "the stop")
        self.assertTrue(job["stopped"])
        self.assertEqual(job["error"], "", "stopping is not failing")
        self.assertLess(job["done"], 40000)
        self.assertEqual([k for k in self.serve.CANCELS if k[0] == "speech"], [])

    def test_what_a_speech_part_costs_is_said_before_it_starts(self):
        import download
        fake = self.stt_fake(plan=download.plan(download=1_749_545_921, measured=True, kept=2_041_665_983))
        with self.stubbed(getstt=fake):
            status, _, got = self.ask("POST", "/lookup/api/plan", {"kind": "speech", "key": "large-v3-turbo"})
        self.assertEqual(status, 200, got)
        self.assertEqual((got["download"], got["kept"]), (1_749_545_921, 2_041_665_983))
        self.assertTrue(got["measured"])
        self.assertEqual(got["room"], "")
        self.assertEqual(got["named"], "the large-v3-turbo speech model")
        status, _, got = self.ask("POST", "/lookup/api/plan", {"kind": "speech", "key": "small"})
        self.assertEqual(status, 400)

    def test_no_speech_part_starts_that_the_disk_has_no_room_for(self):
        import download
        fake = self.stt_fake(plan=download.plan(download=10, measured=True, kept=10, peak=10 ** 18))
        with self.stubbed(getstt=fake), self.speech_ok():
            status, _, got = self.ask("POST", "/lookup/api/getspeech", {"key": "large-v3"})
        self.assertEqual(status, 507)
        self.assertIn("not enough room", got["error"])
        self.assertIn("the large-v3 speech model", got["error"])
        self.assertNotIn("large-v3", self.serve.STT_JOBS, "nothing was started")

    def test_a_computer_that_cannot_run_the_program_is_told_why_and_nothing_starts(self):
        import getstt
        with patch.object(getstt, "unavailable_reason", lambda: "This Parseh runs on Python 3.11, and the "
                                                                "speech program is built for Python 3.12 only."), \
                patch.object(self.serve, "reading_plan") as plan:
            for key in getstt.PARTS:
                with self.subTest(key=key):
                    status, _, got = self.ask("POST", "/lookup/api/getspeech", {"key": key})
                    self.assertEqual(status, 409)
                    self.assertIn("Python 3.12", got["error"])
            plan.assert_not_called()
        self.assertEqual(self.serve.STT_JOBS, {})

    def test_a_name_that_is_not_a_part_never_reaches_a_folder(self):
        import getstt
        keep = Path(getstt.STT_DIR) / "models" / "sentinel"
        keep.mkdir(parents=True, exist_ok=True)
        (keep / "x").write_bytes(b"still here")
        outside = self.tmp / "dict"
        outside.mkdir(exist_ok=True)
        (outside / "fa.db").write_bytes(b"a dictionary")
        bad = ["../dict", "large-v3/../../dict", "..", "", "large-v3 ", "LARGE-V3", "sentinel", "/etc",
               "runtime/..", 5, None, ["large-v3"], {"large-v3": 1}, "large-v3\x00"]
        with self.speech_ok():
            for key in bad:
                body = {} if key is None else {"key": key}
                for route in ("getspeech", "dropspeech", "stopspeech"):
                    status, _, got = self.ask("POST", "/lookup/api/" + route, body)
                    self.assertEqual(status, 400, (route, key, got))
                    self.assertFalse(got["ok"])
                status, _, got = self.ask("POST", "/lookup/api/plan", {"kind": "speech", "key": key})
                self.assertEqual(status, 400, ("plan", key))
        self.assertEqual((keep / "x").read_bytes(), b"still here")
        self.assertEqual((outside / "fa.db").read_bytes(), b"a dictionary")
        self.assertEqual(self.serve.STT_JOBS, {})

    def test_a_part_cannot_be_removed_while_it_is_being_fetched_or_used(self):
        import getstt
        fake = self.stt_fake(steps=300, pause=0.01)
        with self.stubbed(getstt=fake), self.speech_ok():
            self.assertEqual(self.ask("POST", "/lookup/api/getspeech", {"key": "large-v3"})[0], 200)
            self.wait(lambda: self.serve.STT_JOBS["large-v3"].get("done", 0) > 0, "it has started")
            status, _, got = self.ask("POST", "/lookup/api/dropspeech", {"key": "large-v3"})
            self.assertEqual(status, 409)
            self.assertIn("being fetched", got["error"])
            # a model being fetched may be installing the program: the program is not removed either
            status, _, got = self.ask("POST", "/lookup/api/dropspeech", {"key": "runtime"})
            self.assertEqual(status, 409)
            self.ask("POST", "/lookup/api/stopspeech", {"key": "large-v3"})
            self.wait(lambda: not self.serve.STT_JOBS["large-v3"].get("running"), "the stop")
        # and what a transcription holds
        with getstt.using("large-v3-turbo"):
            for key in ("large-v3-turbo", "runtime"):
                status, _, got = self.ask("POST", "/lookup/api/dropspeech", {"key": key})
                self.assertEqual((status, got.get("code")), (409, "in-use"), key)
                self.assertIn("being used", got["error"])

    def test_a_part_is_not_removed_under_a_capture_that_is_still_being_recorded(self):
        # THE WORKER'S HOLD BEGINS AFTER THE LAST PIECE, and a capture lasts as long as the
        # video plays: the job itself holds its part from its start (lib/sttjobs.py), and a
        # device let in that presses Remove meanwhile is told why, and loses nothing.  This is
        # the real getstt (its own `using` and `remove`) under the real server; only "the
        # program and the model are there" is said by the test.
        import getstt
        import sttjobs
        import ytpages
        stt = Path(getstt.STT_DIR)
        for part in ("runtime/1-cp312", "models/large-v3-turbo", "models/large-v3"):
            (stt / part).mkdir(parents=True, exist_ok=True)
            (stt / part / "file").write_bytes(b"x")
        keep = [patch.object(getstt, "runtime_ready", lambda: True),
                patch.object(getstt, "model_ready", lambda key: True),
                patch.object(getstt, "TMP_DIR", str(stt / "tmp")),
                patch.object(ytpages, "VIDEOS", str(self.tmp / "videos"))] + self.as_phone()
        for p in keep:
            p.start()
        job = None
        try:
            with self.speech_ok(), self.no_card():
                job = sttjobs.start({"kind": "youtube", "id": "dQw4w9WgXcQ"}, "fa",
                                    "large-v3-turbo", "cpu")["job"]
                sttjobs.audio(job, 0, b"\0\0" * 16000, False)
                for key in ("large-v3-turbo", "runtime"):
                    status, _, got = self.ask("POST", "/lookup/api/dropspeech", {"key": key})
                    self.assertEqual((status, got.get("code")), (409, "in-use"), key)
                    self.assertIn("being used", got["error"])
                self.assertTrue((stt / "models" / "large-v3-turbo" / "file").exists())
                self.assertTrue((stt / "runtime" / "1-cp312" / "file").exists())
                # the page's own question says the same: something is using speech to text
                status, _, got = self.ask("POST", "/lookup/api/speech", {})
                self.assertTrue(got["busy"], "a recording is a transcription that is under way")
                # the model it does not use may go
                status, _, got = self.ask("POST", "/lookup/api/dropspeech", {"key": "large-v3"})
                self.assertEqual((status, got.get("ok")), (200, True), got)
                self.assertFalse((stt / "models" / "large-v3").exists())
                # and once it is over, the removal goes through
                sttjobs.cancel(job)
                status, _, got = self.ask("POST", "/lookup/api/speech", {})
                self.assertFalse(got["busy"])
                for key in ("large-v3-turbo", "runtime"):
                    status, _, got = self.ask("POST", "/lookup/api/dropspeech", {"key": key})
                    self.assertEqual((status, got.get("ok")), (200, True), (key, got))
                self.assertFalse((stt / "models" / "large-v3-turbo").exists())
                self.assertFalse((stt / "runtime").exists())
        finally:
            if job:
                sttjobs.cancel(job)
            sttjobs.JOBS.clear()
            sttjobs.TOMBS.clear()
            for p in reversed(keep):
                p.stop()

    def test_stopping_everything_empties_the_queue(self):
        import download
        plan = download.plan(download=1000, measured=True, kept=500)
        mods = {name: fake_downloader(name, plan, steps=300, pause=0.01)
                for name in ("getdict", "getcorpus", "getmt")}
        with self.stubbed(**mods):
            self.assertEqual(self.ask("POST", "/lookup/api/getall", {"code": "it", "gloss": "en"})[0], 200)
            self.wait(lambda: self.serve.DICT_JOBS.get("it", {}).get("running"), "the first step")
            self.assertEqual(self.serve.CORPUS_JOBS["it-en"]["waiting"], True)
            self.ask("POST", "/lookup/api/stop", {"all": "it"})
            self.wait(lambda: not self.serve.QUEUE_WORKER["running"], "the queue", 20)
        self.assertTrue(self.serve.DICT_JOBS["it"]["stopped"])
        self.assertNotIn("it-en", self.serve.CORPUS_JOBS, "a step that never ran is not a job")
        self.assertEqual(self.serve.QUEUE, [])


if __name__ == "__main__":
    unittest.main()
