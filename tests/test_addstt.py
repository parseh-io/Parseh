#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""THE ADD PAGE'S SPEECH TO TEXT, as the files and the doors say it.

    python3 -m unittest discover -s tests -p test_addstt.py

What the block DOES in a browser -- the pickers, a film transcribed, the
locks, the confirmations, a YouTube video recorded -- is driven in real Chrome
by tests/add_stt.mjs and tests/youtube_capture.mjs (section n).  What is held
here is what only the files and the server's doors can say:

  * THE PAGE IS USABLE WITHOUT SPEECH TO TEXT (brief test 4): the page a
    server sends holds no control of it -- only the place it will be drawn, empty
    and hidden -- names none of its endpoints (the module does), loads no card
    kit, and a server that has no speech to text still adds a video from a
    pasted transcript;
  * NOTHING OF IT IN AN ADDED VIDEO'S PLAYER (brief test 5): the player page and
    every script it loads say nothing of speech to text;
  * A WHISPER RESULT IS A PANEL THE PAGE'S OWN DOORS ACCEPT (brief test 16, the
    field's half): read by the editor's door, by "prepare", and by the checker;
  * THE WAVEFORM A TRANSCRIPTION HELD comes in beside the video api_add makes,
    only a YouTube video's, only when the video is made, and never fails it;
  * the stand-in for the computer's status (tests/addstt_fakes.py) keeps the
    real slice's shape, so the browser suites cannot drift from what lib/getstt.py
    says.
"""
import http.client
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
for _p in ("lib", "youtube/lib", "tests"):
    if os.path.join(ROOT, _p) not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, _p))
import addstt_fakes                                           # noqa: E402
import stt_fakes                                              # noqa: E402
import speechconfig                                          # noqa: E402
import speechmodels                                          # noqa: E402
import sttpanel                                               # noqa: E402
import wavefile                                               # noqa: E402
import ytpages                                                # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "videos")
ADDSTT_JS = os.path.join(ROOT, "youtube", "lib", "addstt.js")
ADDSTT_CSS = os.path.join(ROOT, "youtube", "lib", "addstt.css")

# what nobody looking at an added video should find anywhere in it
TRACE = re.compile(r"whisper|speech[- ]to[- ]text|transcribe|addstt|ParsehAddStt|api/transcribe|"
                   r"lookup/api/speech", re.I)


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


class Handler:
    """What the add page's doors ask of serve.py's handler, and no more."""

    def __init__(self, body):
        self._raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.query = {}
        self.status = self.sent = None

    def send_json(self, obj, code=200):
        self.status, self.sent = code, obj


class ThePage(unittest.TestCase):
    """The page as the server sends it, and what it loads."""

    @classmethod
    def setUpClass(cls):
        cls.page = ytpages.add_page()

    def test_there_is_only_a_place_for_it(self):
        # brief tests 4: no control of speech to text is in the page a server
        # sends, so none can be dead; the block is drawn by the module, from
        # what the computer says it has
        self.assertIn('<div id="stt" class="stt" hidden></div>', self.page)
        self.assertEqual(re.findall(r'\bid="stt_[a-z]+"', self.page), [],
                         "no button, picker or link of speech to text is written into the page")
        self.assertEqual(re.findall(r"<(?:button|select)[^>]*\bid=\"stt", self.page), [])

    def test_the_page_names_no_endpoint_of_it(self):
        for what in ("/api/transcribe", "lookup/api/speech", "large-v3", "faster-whisper"):
            self.assertNotIn(what, self.page, what + ": the module names it, the page does not")
        self.assertEqual(self.page.count("ParsehAddStt.mount("), 1, "the page mounts the block once")

    def test_the_module_names_them(self):
        js = read(ADDSTT_JS)
        self.assertIn("'/lookup/api/speech'", js)
        self.assertIn("'/api/transcribe/'", js)
        for route in ("start", "audio", "marks", "wave", "status", "cancel", "result"):
            self.assertIn("'%s'" % route, js, route)

    def test_no_card_kit_and_the_recording_is_the_one_module(self):
        self.assertNotIn("cardkit", self.page,
                         "the add page records through tabcapture.js and never loads the card kit")
        scripts = re.findall(r'<script src="([^"]+)"', self.page)
        js = [s for s in scripts if s.startswith("/youtube/lib/")]
        # (addfilm.js, which looks at the path and sends a file, comes after them: it
        # reads the path box and records nothing)
        self.assertEqual(js, ["/youtube/lib/subedit.js", "/youtube/lib/tabcapture.js",
                              "/youtube/lib/asrwalk.js", "/youtube/lib/asrreview.js", "/youtube/lib/addstt.js", "/youtube/lib/addfilm.js"],
                         "the recording is loaded before the block that uses it")
        self.assertIn('href="/youtube/lib/addstt.css"', self.page)
        src = read(ADDSTT_JS)
        code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        code = re.sub(r"(?m)//.*$", "", code)
        for what in ("cardkit", "getUserMedia", "getDisplayMedia", "MediaRecorder"):
            self.assertNotIn(what, code, what + ": the block never records anything itself")

    def test_the_inline_script_did_not_grow_for_it(self):
        # "prefer small reusable components over another very large inline script":
        # what the page's script says of speech to text is the glue, and no more
        glue = [ln for ln in ytpages.ADD_PAGE_JS.splitlines() if "stt" in ln.lower()]
        self.assertLess(len(glue), 45, "\n".join(glue))
        # Review is another reusable file, loaded before the add-flow glue.
        self.assertNotIn('stt_review_likelihood', ytpages.ADD_PAGE_JS)
        self.assertEqual(self.page.count('/youtube/lib/asrreview.js'), 1)
        self.assertEqual(self.page.count('/youtube/lib/asrwalk.js'), 1)
        self.assertLess(self.page.index('/youtube/lib/asrwalk.js'), self.page.index('/youtube/lib/asrreview.js'), "the walk is there when the review is mounted")

    def test_the_server_sends_both_files(self):
        import serve
        for path in ("/youtube/lib/addstt.js", "/youtube/lib/addstt.css", "/youtube/lib/asrwalk.js", "/youtube/lib/asrreview.js"):
            self.assertIn(path, serve.STATIC_FILES, path)
        self.assertTrue(os.path.isfile(ADDSTT_JS) and os.path.isfile(ADDSTT_CSS))

    def test_the_css_keeps_to_the_pages_own_tokens_and_logical_sides(self):
        css = re.sub(r"/\*.*?\*/", "", read(ADDSTT_CSS), flags=re.S)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), ["#0b0b0b", "#fff"],
                         "only the video frame's black and its white overlay are fixed; the three themes carry the rest")
        for what in ("margin-left", "margin-right", "padding-left", "padding-right", "text-align:left",
                     "text-align:right", "float:", "left:", "right:"):
            self.assertNotIn(what, css.replace(" ", ""), what + ": a page turned right to left would break")


class TheModuleDoesNotTouchOtherPages(unittest.TestCase):
    """Nothing of speech to text in an added video's player (brief test 5)."""

    def test_the_player_and_its_scripts_say_nothing_of_it(self):
        with tempfile.TemporaryDirectory() as td:
            videos = os.path.join(td, "videos")
            shutil.copytree(os.path.join(FIX, "italian"), os.path.join(videos, "italian"))
            was = ytpages.VIDEOS
            ytpages.VIDEOS = videos
            try:
                vid = sorted(os.listdir(os.path.join(videos, "italian")))[0]
                html = ytpages.player_page(vid)
            finally:
                ytpages.VIDEOS = was
        self.assertIsNotNone(html)
        self.assertEqual(TRACE.findall(html), [], "the player's page")
        seen = 0
        for src in re.findall(r'<script[^>]*\bsrc="([^"]+)"', html):
            src = src.replace("__BASE__", "/youtube")
            path = None
            if src.startswith("/youtube/lib/"):
                path = os.path.join(ROOT, "youtube", "lib", src[len("/youtube/lib/"):])
            elif src.startswith("/lib/"):
                path = os.path.join(ROOT, "lib", src[len("/lib/"):])
            if path and os.path.isfile(path):
                seen += 1
                body = read(path)
                self.assertEqual(TRACE.findall(body), [], src)
        self.assertGreater(seen, 5, "the scripts the player loads were read")
        self.assertNotIn("addstt", html)


class TheSlice(unittest.TestCase):
    """The stand-in keeps the shape of lib/getstt.py's slim slice."""

    def test_the_stand_in_says_what_the_real_one_says(self):
        real_module = stt_fakes._real()
        with tempfile.TemporaryDirectory() as td, \
                patch.object(speechconfig, 'CONFIG', Path(td) / 'speech.json'), \
                patch.object(real_module, 'STT_DIR', os.path.join(td, 'real-stt')):
            fake = addstt_fakes.make(td).summary()
            real = real_module.summary()
        json.dumps(fake)
        json.dumps(real)
        self.assertEqual(sorted(fake), sorted(real))
        self.assertEqual(sorted(fake["runtime"]), sorted(real["runtime"]))
        self.assertEqual([sorted(m) for m in fake["models"]], [sorted(m) for m in real["models"]])
        self.assertEqual([m["id"] for m in fake["models"]], [m["id"] for m in real["models"]])
        self.assertEqual(tuple(m['id'] for m in fake['models']), speechmodels.MODELS)
        for a, b in zip(fake["models"], real["models"]):
            for key in ('label', 'tag', 'hint', 'languages', 'language', 'option', 'available',
                        'availability_reason', 'compatibility', 'source',
                        'package_revision', 'licence', 'fully_compatible', 'distribution',
                        'package', 'download'):
                self.assertEqual(a[key], b[key], key + ': catalogue metadata matches the real module')
            provenance = speechmodels.provenance(a['id'])
            self.assertEqual(a['source'], provenance['source'])
            self.assertEqual(a['package_revision'], provenance['package_revision'])
            self.assertEqual(a['revision'],
                             provenance['package_revision'] if a['ready'] else '')
        self.assertEqual(fake['preferences'], real['preferences'])
        self.assertEqual([p["id"] for p in fake["processing"]], [p["id"] for p in real["processing"]])
        self.assertEqual([sorted(p) for p in fake["processing"]], [sorted(p) for p in real["processing"]])
        self.assertEqual(sorted(fake["languages"]), sorted(real["languages"]))

    def test_the_stand_in_follows_its_state_file(self):
        with tempfile.TemporaryDirectory() as td:
            fake = addstt_fakes.make(td)
            self.assertTrue(fake.summary()["installed"])
            self.assertEqual(fake.summary()["default_model"], "large-v3-turbo")
            addstt_fakes.configure(td, models=["large-v3"], cuda={"ready": True, "name": "A card"})
            s = fake.summary()
            self.assertEqual({m['id']: m['ready'] for m in s['models']},
                             {model: model == 'large-v3' for model in speechmodels.MODELS})
            self.assertEqual(s["default_model"], "large-v3")
            self.assertEqual([p["ready"] for p in s["processing"]], [True, True, True])
            addstt_fakes.configure(td, runtime=False)
            self.assertFalse(fake.summary()["installed"])
            addstt_fakes.configure(td, runtime=True, no_lang=["hi"])
            self.assertFalse(fake.summary()["languages"]["hi"])
            self.assertTrue(fake.summary()["languages"]["fa"])

    def test_the_stand_in_follows_language_selection_and_second_pass_preferences(self):
        with tempfile.TemporaryDirectory() as td, \
                patch.object(speechconfig, 'CONFIG', Path(td) / 'speech.json'):
            fake = addstt_fakes.make(td)
            self.assertEqual(fake.summary()['preferences'], speechconfig.load())
            speechconfig.save({'second_pass': False, 'models_by_language': {'fa': 'fa-fast'}})
            self.assertEqual(fake.summary()['preferences'], {
                'format_version': 1, 'second_pass': False, 'models_by_language': {'fa': 'fa-fast'}})
            addstt_fakes.configure(td, models=['fa-fast'])
            self.assertEqual([m['id'] for m in fake.summary()['models'] if m['ready']], ['fa-fast'])

    def test_the_stand_in_does_not_read_the_hosts_preferences(self):
        with tempfile.TemporaryDirectory() as td, \
                patch.object(speechconfig, 'CONFIG', Path(td) / 'host-speech.json'):
            speechconfig.save({'second_pass': False, 'models_by_language': {'fa': 'fa-fast'}})
            fake = addstt_fakes.make(os.path.join(td, 'fixture'))
            self.assertEqual(fake.summary()['preferences'], {
                'format_version': 1, 'second_pass': True, 'models_by_language': {}})


# ------------------------------------------------------------ a Whisper result
SEGMENTS = [
    {"start": 0.0, "end": 2.0, "text": " سلام دنیا"},
    {"start": 2.0, "end": 4.0, "text": " "},                      # a segment with no words
    {"start": 2.5, "end": 4.0, "text": " خداحافظ"},
    {"start": 4.0, "end": 5.0, "text": " ۱۲:۳۰"},                  # reads as a clock
    {"start": 65.4, "end": 69.0, "text": " تا فردا"},
    {"start": 65.4, "end": 70.0, "text": " و بعد"},                # starts with the one before
]


class AWhisperResult(unittest.TestCase):
    """A timed Whisper result, in the panel the page reads (brief test 16)."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.videos = os.path.join(td.name, "videos")
        os.makedirs(self.videos)
        for name, value in (("VIDEOS", self.videos), ("oembed", lambda vid: {})):
            self.addCleanup(setattr, ytpages, name, getattr(ytpages, name))
            setattr(ytpages, name, value)
        self.panel, self.notes = sttpanel.segments_to_panel(SEGMENTS)

    def test_the_editors_door_reads_it_back_as_it_was_written(self):
        h = Handler({"transcript": self.panel, "lang": "fa"})
        ytpages.api_transcript(h)
        self.assertEqual(h.status, 200, h.sent)
        self.assertEqual(h.sent["text"], self.panel, "the editor opens what speech to text wrote, unchanged")
        starts = [c["start"] for c in h.sent["captions"]]
        self.assertEqual(starts, sorted(set(starts)), "each caption starts after the one before")
        self.assertEqual(h.sent["captions"][0]["text"], "سلام دنیا")

    def test_prepare_accepts_it(self):
        h = Handler({"url": "aB3dE5fG7hJ", "lang": "fa", "gloss": "en", "transcript": self.panel})
        ytpages.api_prepare(h)
        self.assertEqual(h.status, 200, h.sent)
        self.assertTrue(h.sent["ok"])
        self.assertGreaterEqual(h.sent["captions"], 3)
        self.assertIn("سلام دنیا", h.sent["prompt"])

    def test_the_checker_passes_the_video_made_from_it(self):
        from draft import video_from_transcript
        r = video_from_transcript(self.panel, "fa", video_id="aB3dE5fG7hJ", into=self.videos)
        done = subprocess.run([sys.executable, os.path.join(ROOT, "youtube", "lib", "check_annotations.py"), r["dir"]],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_the_hazards_are_said(self):
        self.assertTrue(any("12:30" in n or "۱۲:۳۰" in n for n in self.notes),
                        "a segment that reads as a clock was joined to its neighbour, and says so: " + repr(self.notes))


# ---------------------------------------------------------------- the waveform
class Shelf(unittest.TestCase):
    """A temporary videos/, an answer the fixture's own parts give, and a held waveform."""
    FOLDER, ID, CODE = "japanese", "aB3dE5fG7hI", "ja"
    TOKEN = "Zk3xQ9wLm2Vb7RtY"          # a token as sttjobs makes one: 16 of [A-Za-z0-9_-]

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = td.name
        self.videos = os.path.join(td.name, "videos")
        os.makedirs(self.videos)
        for name, value in (("VIDEOS", self.videos), ("oembed", lambda vid: {})):
            self.addCleanup(setattr, ytpages, name, getattr(ytpages, name))
            setattr(ytpages, name, value)
        self.src = os.path.join(FIX, self.FOLDER, self.ID)
        self.dest = os.path.join(self.videos, self.FOLDER, self.ID)
        self.peaks = [round((i % 20) / 20.0, 3) for i in range(241)]
        self.peaks[7] = 1.0

    def hold(self, token=None):
        wavefile.hold(token or self.TOKEN, 20.0, self.peaks, videos=self.videos)

    def held(self, token=None):
        return wavefile.held(token or self.TOKEN, videos=self.videos)

    def add(self, **extra):
        parts = json.loads(read(os.path.join(self.src, "parts", "01.json")))
        caps = [{"i": i, "start": p["start"], "chunks": p["chunks"]} for i, p in enumerate(parts)]
        body = {"url": self.ID, "lang": self.CODE, "gloss": "en",
                "transcript": read(os.path.join(self.src, "transcript.txt")),
                "answer": "```json\n%s\n```" % json.dumps(
                    {"video": {"level": "beginner"}, "captions": caps}, ensure_ascii=False)}
        body.update(extra)
        h = Handler(body)
        ytpages.api_add(h)
        return h.status, h.sent

    def waveform(self, where=None):
        path = os.path.join(where or self.dest, "waveform.json")
        return json.loads(read(path)) if os.path.isfile(path) else None


class TheWaveformAdopted(Shelf):

    def test_a_youtube_video_takes_the_waveform_its_transcription_held(self):
        self.hold()
        status, j = self.add(wave=self.TOKEN)
        self.assertEqual((status, j["ok"]), (200, True), j)
        self.assertEqual(j["waveform"], {"kept": True, "buckets": 241})
        self.assertEqual(self.waveform(), {"rate": 20.0, "peaks": self.peaks},
                         "the canonical shape, in beside the video")
        self.assertFalse(self.held(), "and the hold is let go once it is beside the video")
        self.assertFalse([n for n in os.listdir(self.videos) if n.startswith(".staging-")],
                         "the staging folder is gone")

    def test_a_token_that_names_nothing_is_no_reason_to_refuse_the_video(self):
        for token in ("AAAAAAAAAAAAAAAA", "not a token", "../../etc/passwd", "", 7, None, ["x"]):
            shutil.rmtree(os.path.join(self.videos, self.FOLDER), ignore_errors=True)
            status, j = self.add(wave=token)
            self.assertEqual((status, j["ok"]), (200, True), (token, j))
            self.assertEqual(j["waveform"], {"kept": False}, repr(token))
            self.assertIsNone(self.waveform(), repr(token))

    def test_nothing_is_said_where_nothing_was_asked(self):
        self.hold()
        status, j = self.add()
        self.assertEqual((status, j["ok"]), (200, True))
        self.assertNotIn("waveform", j)
        self.assertIsNone(self.waveform())
        self.assertTrue(self.held(), "a hold nobody asked for is not spent")

    def test_an_answer_that_is_refused_spends_nothing(self):
        self.hold()
        status, j = self.add(wave=self.TOKEN, answer="not the LLM's answer")
        self.assertEqual(status, 400, j)
        self.assertTrue(self.held(), "the hold is kept for the answer that will come")
        self.assertFalse(os.path.isdir(self.dest))

    def test_a_film_takes_none(self):
        # a film's picture is drawn from the film itself: nothing is written for it
        film = os.path.join(self.tmp, "lesson.mp4")
        with open(film, "wb") as f:
            f.write(b"\0" * 64)
        self.hold()
        status, j = self.add(wave=self.TOKEN, url="", path=film)
        self.assertEqual((status, j["ok"]), (200, True), j)
        self.assertNotIn("waveform", j)
        dest = os.path.join(self.videos, self.FOLDER, j["id"])
        self.assertIsNone(self.waveform(dest))
        self.assertTrue(self.held(), "and the hold is still there for the video it belongs to")

    def test_a_replaced_video_has_the_new_waveform_and_the_old_one_is_in_the_trash(self):
        self.hold()
        self.add(wave=self.TOKEN)
        old = self.waveform()
        self.hold(self.TOKEN)
        self.peaks[3] = 0.5
        wavefile.hold(self.TOKEN, 20.0, self.peaks, videos=self.videos)
        status, j = self.add(wave=self.TOKEN, replace=True)
        self.assertEqual((status, j["ok"]), (200, True), j)
        self.assertEqual(self.waveform()["peaks"][3], 0.5)
        self.assertNotEqual(self.waveform(), old)
        trashed = [os.path.join(dp, "waveform.json") for dp, _d, fs in os.walk(os.path.join(self.videos, ".trash"))
                   if "waveform.json" in fs]
        self.assertEqual(len(trashed), 1, "the old video, waveform and all, is under .trash/")

    def test_what_is_adopted_is_read_by_the_player_as_any_other(self):
        # the player reads waveform.json straight off the static route, and the
        # cleaner that wrote it is the one the waveform door has always used
        self.hold()
        self.add(wave=self.TOKEN)
        rate, peaks = wavefile.clean(self.waveform()["rate"], self.waveform()["peaks"])
        self.assertEqual((rate, len(peaks)), (20.0, 241))


# ------------------------------------------------------- a server without it
BOOT = """
import os, runpy, sys
root = os.environ["ADDSTT_ROOT"]
sys.path[:0] = [os.path.join(root, "lib"), os.path.join(root, "youtube", "lib")]
import getstt
getstt.STT_DIR = os.environ["ADDSTT_EMPTY"]          # nothing installed, whatever this machine has
sys.argv = ["serve.py", "--http", "--local", sys.argv[1]]
runpy.run_path("serve.py", run_name="__main__")
"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class AServerWithoutSpeechToText(unittest.TestCase):
    """serve.py over a machine that has none: the add page is a page as before."""

    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        cls.addClassCleanup(cls.td.cleanup)
        cls.log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False, dir=os.environ.get("TMPDIR"))
        cls.addClassCleanup(os.unlink, cls.log.name)
        cls.addClassCleanup(cls.log.close)
        cls.port = free_port()
        env = dict(os.environ, ADDSTT_ROOT=ROOT, ADDSTT_EMPTY=os.path.join(cls.td.name, "stt"))
        cls.proc = subprocess.Popen([sys.executable, "-u", "-c", BOOT, str(cls.port)], cwd=ROOT,
                                    env=env, stdout=cls.log, stderr=subprocess.STDOUT)

        def stop():
            cls.proc.terminate()
            try:
                cls.proc.wait(10)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
                cls.proc.wait()
        cls.addClassCleanup(stop)
        deadline = time.time() + 60
        while True:
            if cls.proc.poll() is not None:
                raise RuntimeError("serve.py exited: " + cls.text())
            try:
                st, _ = cls.ask("GET", "/")
                if st == 200:
                    break
            except OSError:
                pass
            if time.time() > deadline:
                raise RuntimeError("serve.py did not answer: " + cls.text())
            time.sleep(0.25)

    @classmethod
    def text(cls):
        cls.log.flush()
        with open(cls.log.name, encoding="utf-8", errors="replace") as f:
            return f.read()

    @classmethod
    def ask(cls, method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=60)
        try:
            data = json.dumps(body).encode("utf-8") if body is not None else None
            c.request(method, path, data, {"Content-Type": "application/json"} if data else {})
            r = c.getresponse()
            raw = r.read()
            try:
                return r.status, json.loads(raw.decode("utf-8"))
            except ValueError:
                return r.status, raw.decode("utf-8", "replace")
        finally:
            c.close()

    def test_the_computer_says_it_has_none(self):
        st, j = self.ask("POST", "/lookup/api/speech", {})
        self.assertEqual(st, 200)
        self.assertIs(j["installed"], False)
        self.assertEqual(tuple(m['id'] for m in j['models']), speechmodels.MODELS)
        self.assertTrue(all(m['ready'] is False for m in j['models']))
        self.assertIsNone(j["default_model"])
        self.assertEqual(j["settings"], "/settings/speech/")

    def test_the_add_page_is_there_with_no_control_of_it(self):
        st, page = self.ask("GET", "/youtube/add/")
        self.assertEqual(st, 200)
        self.assertIn('id="transcript"', page)
        self.assertIn('id="subedit"', page)
        self.assertIn('<div id="stt" class="stt" hidden></div>', page)
        self.assertEqual(re.findall(r'\bid="stt_', page), [])
        for path in ("/youtube/lib/addstt.js", "/youtube/lib/addstt.css", "/youtube/lib/tabcapture.js"):
            st, body = self.ask("GET", path)
            self.assertEqual(st, 200, path)
            self.assertGreater(len(body), 500, path)

    def test_a_pasted_transcript_is_still_prepared(self):
        st, j = self.ask("POST", "/youtube/api/prepare",
                         {"url": "aB3dE5fG7hJ", "lang": "fa", "gloss": "en",
                          "transcript": "0:01\nسلام دنیا\n0:05\nخداحافظ\n"})
        self.assertEqual(st, 200, j)
        self.assertTrue(j["ok"])
        self.assertEqual(j["captions"], 2)

    def test_a_transcription_is_refused_in_words(self):
        st, j = self.ask("POST", "/youtube/api/transcribe/start",
                         {"source": "youtube", "url": "aB3dE5fG7hJ", "lang": "fa",
                          "model": "large-v3-turbo", "processing": "auto"})
        self.assertEqual((st, j["code"]), (409, "not-installed"), j)
        self.assertEqual(j["error"], "Speech to text is not installed.")

    def test_no_traceback(self):
        self.assertNotIn("Traceback", self.text())


if __name__ == "__main__":
    unittest.main()
