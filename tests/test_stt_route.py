# SPDX-License-Identifier: GPL-3.0-or-later
"""The transcription job over HTTP: a real serve.py, a stand-in runtime, a real child.

    python3 -m unittest tests/test_stt_route.py

serve.py is booted as a child process of the test, over a temporary tree: its
`getstt` is tests/stt_fakes.py's stand-in (INTERFACE 1), the worker it starts
is the real lib/sttworker.py against the stand-in faster-whisper, and every
store it writes (videos, prefs, the network) is redirected into the test's own
folder.  What is asserted is read off real answers and off what the real child
did:

  * a film is transcribed with no browser and the panel it gives is taken by
    the add flow's own door (/youtube/api/local);
  * a YouTube recording is sent in pieces, with its marks and its waveform,
    and the video made from it is given the waveform (/youtube/api/empty);
  * one job at a time (409 busy), Cancel, and the disk;
  * every hostile body and query answers a sentence and a slug, never a
    traceback, and never reaches the model loader or the disk;
  * a page on another site cannot start one;
  * a server stopped (SIGTERM) or killed outright (SIGKILL) leaves no worker.

Any device let in may start a job: the requests of `Route` carry no device at all (they are this
computer's own), and `AnotherDevice` sends the same ones as a device let in over the Wi-Fi.
"""
import http.client
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, os.path.join(ROOT, "lib"), os.path.join(ROOT, "youtube", "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import stt_fakes                                              # noqa: E402
import ytpages                                                # noqa: E402

TURBO = "large-v3-turbo"
YT = "dQw4w9WgXcQ"
PERSIAN = [[0.0, 2.0, " سلام دنیا"], [2.5, 4.0, " خداحافظ"]]
POSIX = os.name != "nt"

BOOT = """
import os, runpy, sys
root, work = os.environ["PARSEH_TEST_ROOT"], os.environ["STT_ROUTE_WORK"]
sys.path[:0] = [os.path.join(root, "lib"), os.path.join(root, "youtube", "lib"),
                os.path.join(root, "tests")]
import stt_fakes, prefs, network, offline, ytpages
sys.modules["getstt"] = stt_fakes.make(os.path.join(work, "fake"))
ytpages.VIDEOS = os.path.join(work, "videos")
# "Start it empty" asks YouTube for the title and the channel (TO-DO 7.6): never from a test
ytpages.oembed_why = lambda vid: ({"title": "A video", "channel": "A channel"}, "")
prefs.STORE = os.path.join(work, "config", "prefs.json")
network.STORE = os.path.join(work, "config", "network.json")
offline.DIGESTS = os.path.join(work, "config", "digests.json")
offline.WHERES = os.path.join(work, "config", "wheres.json")
if os.environ.get("STT_ROUTE_DEVICE") == "lan":
    # every request of this child is another device's, let in over the Wi-Fi: judged the Wi-Fi's,
    # the door open (what tests/test_settings_risk.py's as_phone() does for the Settings routes)
    network.where = lambda ip, doc=None: network.LAN
    network.may_connect = lambda ip, doc=None: True
    network.let_in = lambda *a, **k: True
sys.argv = ["serve.py", "--http", "--local", sys.argv[1]]
runpy.run_path("serve.py", run_name="__main__")
"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def alive(pid):
    try:
        with open("/proc/%d/stat" % pid, encoding="ascii", errors="replace") as f:
            return f.read().rsplit(")", 1)[-1].split()[0] != "Z"
    except OSError:
        return False


class Server:
    """serve.py in a child process, with its own working folder `work`."""

    def __init__(self, device=""):
        self._td = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.work = self._td.name
        self.fake_root = os.path.join(self.work, "fake")
        self.videos = os.path.join(self.work, "videos")
        os.makedirs(self.videos)
        self.port = free_port()
        self.log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False,
                                               dir=os.environ.get("TMPDIR"))
        stt_fakes.configure(self.fake_root)
        env = dict(os.environ, PARSEH_TEST_ROOT=ROOT, STT_ROUTE_WORK=self.work,
                   STT_ROUTE_DEVICE=device)
        self.proc = subprocess.Popen([sys.executable, "-u", "-c", BOOT, str(self.port)],
                                     cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 90
        while True:
            if self.proc.poll() is not None:
                raise RuntimeError("serve.py exited: " + self.text())
            try:
                c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
                c.request("GET", "/")
                r = c.getresponse()
                r.read()
                c.close()
                if r.status == 200:
                    return
            except OSError:
                pass
            if time.time() > deadline:
                self.stop()
                raise RuntimeError("serve.py did not answer: " + self.text())
            time.sleep(0.25)

    def text(self):
        self.log.flush()
        with open(self.log.name, encoding="utf-8", errors="replace") as f:
            return f.read()

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.log.close()
        try:
            os.unlink(self.log.name)
        except OSError:
            pass
        self._td.cleanup()

    # ----- requests
    def ask(self, method, path, data=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        try:
            h = dict(headers or {})
            h["Content-Length"] = str(len(data or b""))
            c.request(method, path, data, h)
            r = c.getresponse()
            raw = r.read()
            try:
                return r.status, json.loads(raw.decode("utf-8"))
            except ValueError:
                return r.status, raw.decode("utf-8", "replace")
        finally:
            c.close()

    def post(self, path, body=None, headers=None):
        data = json.dumps(body).encode("utf-8") if body is not None else b""
        return self.ask("POST", "/youtube/api/transcribe/" + path, data,
                        dict({"Content-Type": "application/json"}, **(headers or {})))

    def audio(self, job, offset, data, last=False, query=None):
        q = "job=%s&offset=%s%s" % (job, offset, "&last=1" if last else "")
        return self.ask("POST", "/youtube/api/transcribe/audio?" + (query if query is not None else q),
                        data, {"Content-Type": "application/octet-stream"})

    def door(self, path, body):
        return self.ask("POST", "/youtube/api/" + path, json.dumps(body).encode("utf-8"),
                        {"Content-Type": "application/json"})

    def status(self, job):
        return self.post("status", {"job": job})

    def wait(self, job, states, timeout=60):
        end = time.time() + timeout
        s = None
        while time.time() < end:
            code, s = self.status(job)
            if code == 200 and s["state"] == "awaiting-review-choice" and "done" in states:
                _, pending = self.post("result", {"job": job})
                self.post("review", {"job": job, "mode": "whisper",
                                    "source_sha256": pending["review"]["evidence"]["source_sha256"]})
                continue
            if code == 200 and s["state"] in states:
                return s
            time.sleep(0.05)
        raise AssertionError("still %r, wanted %r\n%s" % (s, states, self.text()[-2000:]))

    def film(self, seconds=3, name="film.mp4"):
        return stt_fakes.write_wav(os.path.join(self.work, name), seconds)

    def start_film(self, **kw):
        body = dict(source="film", lang="fa", model=TURBO, processing="cpu")
        body["path"] = kw.pop("path", None) or self.film()
        body.update(kw)
        return self.post("start", body)

    def start_yt(self, **kw):
        body = dict(source="youtube", url=YT, lang="fa", model=TURBO, processing="cpu")
        body.update(kw)
        return self.post("start", body)

    def fake(self, **cfg):
        stt_fakes.configure(self.fake_root, fake=cfg)

    def records(self, kind=None):
        return stt_fakes.records(self.fake_root, kind)

    def tmp(self):
        try:
            return sorted(os.listdir(os.path.join(self.fake_root, "stt", "tmp")))
        except OSError:
            return []


class Route(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Server()
        cls.addClassCleanup(cls.s.stop)

    def setUp(self):
        self.s.fake()
        stt_fakes.configure(self.s.fake_root, runtime=True, models=list(stt_fakes.MODELS),
                            cuda_ready=False)
        open(os.path.join(self.s.fake_root, "fake.log"), "w").close()
        self.jobs = []
        self.addCleanup(self.cancel_all)

    def cancel_all(self):
        for job in self.jobs:
            self.s.post("cancel", {"job": job})

    def started(self, code_body):
        code, body = code_body
        self.assertEqual(code, 200, body)
        self.jobs.append(body["job"])
        return body

    # ----------------------------------------------------------------- a film
    def test_a_film_is_transcribed_with_no_browser_and_the_add_flow_takes_the_panel(self):
        s = self.s
        s.fake(segments=PERSIAN)
        got = self.started(s.start_film())
        self.assertEqual((got["need"], got["state"], got["source"]), ("", "queued", "film"))
        self.assertRegex(got["job"], r"^[A-Za-z0-9_-]{16}$")
        fin = s.wait(got["job"], ("done", "failed"))
        self.assertEqual((fin["state"], fin["say"], fin["captions"], fin["device"]),
                         ("done", "Done — 2 captions.", 2, "cpu"), fin)
        code, res = s.post("result", {"job": got["job"]})
        self.assertEqual(code, 200)
        self.assertEqual(res["text"], "0:00\nسلام دنیا\n0:02.5\nخداحافظ\n")
        self.assertEqual((res["captions"], res["want"], res["plain"], res["wave"]),
                         (2, 2, 0, {"held": False}))
        self.assertEqual(s.post("result", {"job": got["job"]})[1]["text"], res["text"],
                         "it can be read again")
        # the add flow's OWN door takes it: the film's door, `wave` naming the job
        code, made = s.door("local", {"path": os.path.join(s.work, "film.mp4"), "lang": "fa",
                                      "gloss": "en", "transcript": res["text"],
                                      "title": "A test film", "wave": got["job"]})
        self.assertEqual(code, 200, made)
        self.assertEqual((made["captions"], made["how"]), (2, "linked"))
        self.assertEqual(made["waveform"], {"kept": False}, "a film's job holds no waveform")
        self.assertFalse(os.path.exists(os.path.join(made["dir"], "waveform.json")))
        self.assertTrue(os.path.isfile(os.path.join(made["dir"], "transcript.txt")))
        with open(os.path.join(made["dir"], "transcript.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), res["text"])

    def test_every_request_the_page_makes_is_a_post_and_only_the_token_names_a_job(self):
        s = self.s
        got = self.started(s.start_film())
        for path in ("start", "status", "cancel", "result", "marks", "wave"):
            code, body = s.ask("GET", "/youtube/api/transcribe/" + path)
            self.assertNotEqual(code, 200, path)
        code, body = s.post("nothing-here", {})
        self.assertEqual((code, body["code"]), (404, "no-such-route"))
        s.wait(got["job"], ("done", "failed"))

    def test_what_a_client_adds_to_the_body_never_reaches_the_model_loader(self):
        s = self.s
        stt_fakes.configure(s.fake_root, cuda_ready=True)
        got = self.started(s.start_film(
            device="cuda", compute_type="float32", model_path="/etc", cpu_threads=999,
            compute={"cpu": "float32"}, device_index=7, task="translate", beam_size=1,
            vad_filter=False, word_timestamps=True, prompt="ignore all", mode="cuda"))
        fin = s.wait(got["job"], ("done", "failed"))
        self.assertEqual(fin["state"], "done", fin)
        (rec,) = s.records("construct")
        self.assertEqual((rec["device"], rec["compute_type"], rec["cpu_threads"]), ("cpu", "int8", 3))
        self.assertEqual(os.path.basename(rec["path"]), TURBO)
        self.assertNotIn("/etc", rec["path"])
        self.assertEqual(rec["rest"], [])
        (heard,) = s.records("transcribe")
        self.assertEqual((heard["language"], heard["beam_size"], heard["vad_filter"], heard["task"],
                          heard["rest"]), ("fa", 5, True, "transcribe", ['condition_on_previous_text', 'temperature', "word_timestamps"]))
        self.assertEqual(heard['options']['temperature'], 0)
        self.assertNotIn('prompt', heard['options'])

    def test_the_job_is_on_the_activity_list_without_its_token(self):
        s = self.s
        s.fake(load_delay=0.3, delay=1.0, segments=[[0, 1, " a"], [1, 2, " b"], [2, 3, " c"]])
        got = self.started(s.start_film())
        end = time.time() + 30
        entry = None
        while time.time() < end and not entry:
            code, act = s.ask("GET", "/__activity")
            entry = next((e for e in act["running"] if e["id"].startswith("stt:")), None)
            time.sleep(0.05)
        self.assertTrue(entry, "the transcription is on the list")
        self.assertEqual((entry["kind"], entry["label"], entry["page"]),
                         ("narration", "Transcribing a film on this machine", "/youtube/add/"))
        self.assertNotIn(got["job"], json.dumps(act))
        s.post("cancel", {"job": got["job"]})
        code, act = s.ask("GET", "/__activity")
        self.assertEqual([e for e in act["running"] if e["id"].startswith("stt:")], [])

    # ---------------------------------------------------------------- YouTube
    def test_a_recording_is_sent_in_pieces_and_the_video_made_from_it_is_given_the_waveform(self):
        s = self.s
        s.fake(segments=[[3.0, 5.0, " سلام دنیا"], [8.0, 9.5, " خداحافظ"]])
        got = self.started(s.start_yt(duration=10))
        self.assertEqual((got["need"], got["state"], got["video_id"]), ("audio", "awaiting-audio", YT))
        pcm = stt_fakes.pcm(10)
        half = len(pcm) // 2
        code, r = s.audio(got["job"], 0, pcm[:half])
        self.assertEqual((code, r["have"]), (200, 80000), r)
        self.assertEqual(s.audio(got["job"], 0, pcm[:half])[1]["have"], 80000, "sent twice")
        code, r = s.audio(got["job"], 120000, pcm[half:])
        self.assertEqual((code, r["code"], r["have"]), (409, "gap", 80000))
        self.assertEqual(s.status(got["job"])[1]["say"], "Recording 0:05 / 0:10…")
        code, r = s.audio(got["job"], 80000, pcm[half:])
        self.assertEqual((code, r["have"]), (200, 160000))
        # the video's clock lags the recording by a second
        marks = [[16000 * k, k - 1.0] for k in range(2, 10)]
        self.assertEqual(s.post("marks", {"job": got["job"], "marks": marks}), (200, {"ok": True, "marks": 8}))
        peaks = [round(i / 200.0, 3) for i in range(201)]
        code, r = s.post("wave", {"job": got["job"], "rate": 20, "peaks": peaks})
        self.assertEqual((code, r["buckets"]), (200, 201))
        code, r = s.audio(got["job"], 160000, b"", last=True)
        self.assertEqual((code, r["state"]), (200, "queued"))
        fin = s.wait(got["job"], ("done", "failed"))
        self.assertEqual(fin["state"], "done", fin)
        code, res = s.post("result", {"job": got["job"]})
        self.assertEqual(res["text"], "0:02\nسلام دنیا\n0:07\nخداحافظ\n", "on the video's own clock")
        self.assertEqual(res["wave"], {"held": True})
        (heard,) = s.records("transcribe")
        self.assertEqual(heard["samples"], 160000)
        for _ in range(100):
            if not s.tmp():
                break
            time.sleep(0.05)
        self.assertEqual(s.tmp(), [], "the temporary recording is deleted")
        # the add flow's own door for a video with no film, told which job's waveform
        code, made = s.door("empty", {"url": YT, "lang": "fa", "gloss": "en",
                                      "transcript": res["text"], "wave": got["job"]})
        self.assertEqual(code, 200, made)
        self.assertEqual(made["waveform"], {"kept": True, "buckets": 201})
        wave = os.path.join(s.videos, "persian", YT, "waveform.json")
        with open(wave, encoding="utf-8") as f:
            self.assertEqual(f.read(), json.dumps({"rate": 20.0, "peaks": peaks}, ensure_ascii=False))
        self.assertFalse(os.path.exists(os.path.join(s.videos, ".waveforms", got["job"] + ".json")))
        self.assertEqual(s.post("result", {"job": got["job"]})[1]["wave"], {"held": False})
        # and that same door still says what it always said about a waveform
        code, bad = s.door("waveform", {"video": YT, "rate": 0, "peaks": [0.5]})
        self.assertEqual((code, bad["error"]), (400, "a waveform carries between 1 and 200 numbers a second"))
        code, bad = s.door("waveform", {"video": YT, "rate": 20, "peaks": []})
        self.assertEqual((code, bad["error"]), (400, "no waveform was sent"))
        self.assertEqual(s.door("waveform", {"video": YT, "rate": 10, "peaks": [0.2, 3]})[1],
                         {"ok": True, "rate": 10.0, "buckets": 2})

    def test_a_token_that_is_not_a_job_is_ignored_by_the_doors_that_make_a_video(self):
        s = self.s
        held = os.path.join(s.videos, ".waveforms")
        before = sorted(os.listdir(held)) if os.path.isdir(held) else []
        for token in ("A" * 16, "../../../etc/passwd", None, 5, ["x"], "", "A" * 17):
            code, made = s.door("empty", {"url": "abcdefghijk", "lang": "fa", "gloss": "en",
                                          "transcript": "0:00\nسلام\n", "wave": token})
            self.assertEqual(code, 200, made)
            self.assertEqual(made["waveform"], {"kept": False})
            self.assertFalse(os.path.exists(os.path.join(made["dir"], "waveform.json")))
            shutil.rmtree(made["dir"])
        after = sorted(os.listdir(held)) if os.path.isdir(held) else []
        self.assertEqual(after, before, "no hold was made, moved or read for any of them")

    def test_a_second_start_is_busy_and_cancel_makes_room(self):
        s = self.s
        first = self.started(s.start_yt())
        code, body = s.start_film()
        self.assertEqual((code, body["code"], body["error"]),
                         (409, "busy", "Another transcription is running."))
        self.assertNotIn(first["job"], json.dumps(body))
        code, body = s.post("cancel", {"job": first["job"]})
        self.assertEqual((code, body), (200, {"ok": True, "cancelled": True}))
        second = self.started(s.start_film())
        self.assertNotEqual(first["job"], second["job"])
        code, st = s.status(first["job"])
        self.assertEqual((code, st["state"], st["stopped"]), (200, "cancelled", True))
        s.wait(second["job"], ("done", "failed"))

    def test_cancel_deletes_the_recording_and_the_held_waveform(self):
        s = self.s
        got = self.started(s.start_yt())
        s.audio(got["job"], 0, stt_fakes.pcm(1))
        s.post("wave", {"job": got["job"], "rate": 20, "peaks": [0.5, 1]})
        self.assertTrue(s.tmp())
        self.assertTrue(os.path.isfile(os.path.join(s.videos, ".waveforms", got["job"] + ".json")))
        self.assertEqual(s.post("cancel", {"job": got["job"]})[1]["cancelled"], True)
        self.assertEqual(s.tmp(), [])
        self.assertFalse(os.path.exists(os.path.join(s.videos, ".waveforms", got["job"] + ".json")))
        code, body = s.audio(got["job"], 16000, stt_fakes.pcm(1))
        self.assertEqual((code, body["code"], body["error"]),
                         (409, "cancelled", "Recording was cancelled."))
        self.assertEqual(s.audio("Z" * 16, 0, stt_fakes.pcm(1))[1]["code"], "no-such-job",
                         "a job nobody made is another answer")

    def test_a_beacon_on_pagehide_cancels_it_too(self):
        # navigator.sendBeacon sends its string as text/plain, with no JSON header
        s = self.s
        got = self.started(s.start_yt())
        code, body = s.ask("POST", "/youtube/api/transcribe/cancel",
                           json.dumps({"job": got["job"]}).encode("utf-8"),
                           {"Content-Type": "text/plain;charset=UTF-8"})
        self.assertEqual((code, body["cancelled"]), (200, True))
        self.assertEqual(s.status(got["job"])[1]["state"], "cancelled")

    # ------------------------------------------------------------- the audio door
    def test_the_audio_door_refuses_what_it_should_in_words(self):
        s = self.s
        got = self.started(s.start_yt())
        job = got["job"]
        one = stt_fakes.pcm(1)
        table = [
            ("no job", "offset=0", 404, "no-such-job"),
            ("no offset", "job=%s" % job, 400, "bad-offset"),
            ("offset text", "job=%s&offset=abc" % job, 400, "bad-offset"),
            ("offset negative", "job=%s&offset=-1" % job, 400, "bad-offset"),
            ("offset float", "job=%s&offset=1.5" % job, 400, "bad-offset"),
            ("offset exponent", "job=%s&offset=1e3" % job, 400, "bad-offset"),
            ("offset spaces", "job=%s&offset=%%200" % job, 400, "bad-offset"),
            ("offset huge", "job=%s&offset=%s" % (job, "9" * 30), 400, "bad-offset"),
            ("job path", "job=../../x&offset=0", 404, "no-such-job"),
            ("job absolute", "job=/etc/passwd&offset=0", 404, "no-such-job"),
            ("job unknown", "job=%s&offset=0" % ("Z" * 16), 404, "no-such-job"),
            ("job doubled", "job=%s&job=%s&offset=0" % (job, "Z" * 16), 200, None),
        ]
        for what, query, status, code in table:
            with self.subTest(what):
                got_status, body = s.audio(job, 0, one[:1600], query=query)
                self.assertEqual(got_status, status, body)
                if code:
                    self.assertEqual(body["code"], code)
                    self.assertTrue(body["error"])
        # (the "doubled" row wrote the first 800 samples: this one goes on from there)
        self.assertEqual(s.audio(job, 800, one[:1600])[0], 200)
        status, body = s.audio(job, 1600, b"\0\0\0")
        self.assertEqual((status, body["code"]), (400, "bad-audio"))
        status, body = s.audio(job, 1600, b"")
        self.assertEqual((status, body["code"]), (400, "bad-audio"))
        status, body = s.audio(job, 1600, b"\0" * (1 << 20) + b"\0\0")
        self.assertEqual((status, body["code"]), (413, "too-big"))
        self.assertEqual(s.status(job)[1]["say"], "Recording 0:00…")

    def test_a_body_bigger_than_the_server_takes_is_refused_and_writes_nothing(self):
        s = self.s
        got = self.started(s.start_yt())
        # the server reads the DECLARED length before the body: 33 MiB is refused
        # without one of them being sent (which a server that then closes the
        # connection could not be answered from, by the client's own stack)
        c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=60)
        try:
            c.putrequest("POST", "/youtube/api/transcribe/audio?job=%s&offset=0" % got["job"])
            c.putheader("Content-Type", "application/octet-stream")
            c.putheader("Content-Length", str(33 * 1024 * 1024))
            c.endheaders()
            r = c.getresponse()
            code, raw = r.status, r.read()
        finally:
            c.close()
        self.assertEqual(code, 413, raw)
        self.assertEqual(s.status(got["job"])[1]["state"], "awaiting-audio")
        self.assertEqual(s.tmp(), [], "not one byte of it was kept")

    # ------------------------------------------------ hostile requests, all routes
    def test_hostile_requests_get_a_sentence_and_a_slug_and_never_a_traceback(self):
        s = self.s
        logged = len(s.text())
        self.started(s.start_yt())                        # a job holds the slot
        hostile = [
            None, [], "text", 5, [1, 2], {"source": 5}, {"source": None}, {"source": "film"},
            {"source": "film", "path": {"a": 1}}, {"source": "film", "path": "\0"},
            {"source": "film", "path": "/etc/passwd"}, {"source": "film", "path": "../../x.mp4"},
            {"source": "youtube", "url": ["x"]}, {"source": "youtube", "url": "x" * 100000},
            {"source": "youtube", "url": YT, "path": "/x", "lang": "fa"},
            {"source": "youtube", "url": YT, "lang": "fa", "model": "small", "processing": "cpu"},
            {"source": "youtube", "url": YT, "lang": "fa", "model": TURBO, "processing": "gpu"},
            {"source": "youtube", "url": YT, "lang": "fa", "model": TURBO, "processing": "cpu",
             "duration": "long"},
            {"source": "youtube", "url": YT, "lang": "../..", "model": TURBO, "processing": "cpu"},
            {"job": None}, {"job": ["x"]}, {"job": "../x"}, {"job": "A" * 16}, {"job": 5},
            {"job": "A" * 16, "marks": "x"}, {"job": "A" * 16, "rate": "x", "peaks": 5},
        ]
        seen = []
        for path in ("start", "status", "cancel", "result", "marks", "wave"):
            for body in hostile:
                with self.subTest(route=path, body=repr(body)[:60]):
                    code, out = s.post(path, body)
                    if isinstance(out, dict) and out.get("ok"):
                        continue
                    self.assertGreaterEqual(code, 400)
                    self.assertLess(code, 500, out)
                    self.assertIsInstance(out, dict)
                    self.assertFalse(out["ok"])
                    self.assertTrue(out["error"].strip() and out["code"].strip(), out)
                    seen.append(out)
        # bodies that are not JSON at all
        for raw in (b"{", b"[1,2", b"\xff\xfe", b"nul\0l", b"\x00" * 10, b"[" * 5000,
                    '{"job": "\\ud800"}'.encode()):
            code, out = s.ask("POST", "/youtube/api/transcribe/status", raw,
                              {"Content-Type": "application/json"})
            self.assertEqual(code, 400, raw[:20])
            self.assertEqual(out["code"], "bad-request")
            seen.append(out)
        text = json.dumps(seen)
        for word in ("Traceback", 'File "', ".py\"", "line ", "Error:", "Exception", "0x"):
            self.assertNotIn(word, text)
        self.assertEqual(s.records(), [], "no model was built for any of it")
        self.assertNotIn("Traceback", s.text()[logged:], "and the server's own log has none either")

    def test_a_page_on_another_site_cannot_start_a_job(self):
        s = self.s
        body = json.dumps(dict(source="film", path=s.film(), lang="fa", model=TURBO,
                               processing="cpu")).encode("utf-8")
        for headers in ({"Sec-Fetch-Site": "cross-site"},
                        {"Origin": "https://evil.example"},
                        {"Sec-Fetch-Site": "same-site", "Origin": "http://127.0.0.1:1"}):
            code, out = s.ask("POST", "/youtube/api/transcribe/start", body,
                              dict({"Content-Type": "application/json"}, **headers))
            self.assertEqual(code, 403, headers)
            self.assertIn("only Parseh's own pages may change anything", out["error"])
        self.assertEqual(s.records(), [])
        code, out = s.ask("POST", "/youtube/api/transcribe/start", body,
                          {"Content-Type": "application/json", "Sec-Fetch-Site": "same-origin",
                           "Origin": "http://127.0.0.1:%d" % s.port})
        self.assertEqual(code, 200, out)
        self.jobs.append(out["job"])

    def test_it_is_not_installed_until_it_is(self):
        s = self.s
        stt_fakes.configure(s.fake_root, runtime=False)
        code, out = s.start_film()
        self.assertEqual((code, out["code"], out["error"]),
                         (409, "not-installed", "Speech to text is not installed."))
        stt_fakes.configure(s.fake_root, runtime=True, models=["large-v3"])
        code, out = s.start_film()
        self.assertEqual((code, out["code"]), (409, "no-model"))
        code, out = s.start_film(processing="cuda", model="large-v3")
        self.assertEqual((code, out["code"]), (409, "gpu-unavailable"))


class AnotherDevice(unittest.TestCase):
    """ANY DEVICE THAT HAS BEEN LET IN MAY START, FEED, ASK AFTER AND CANCEL A JOB (the owner: a
    phone, a tablet, another computer): there is no device gate on these routes.  The server here
    judges every request to be another device's, and a computer-only route proves it."""

    @classmethod
    def setUpClass(cls):
        cls.s = Server(device="lan")
        cls.addClassCleanup(cls.s.stop)

    def setUp(self):
        self.s.fake(segments=PERSIAN)
        stt_fakes.configure(self.s.fake_root, runtime=True, models=list(stt_fakes.MODELS),
                            cuda_ready=False)
        open(os.path.join(self.s.fake_root, "fake.log"), "w").close()

    def test_the_server_really_takes_these_requests_for_another_devices(self):
        # what only this computer may do is refused: so the requests below are not this computer's
        code, body = self.s.ask("POST", "/settings/api/network", b'{"lan": true}',
                                {"Content-Type": "application/json"})
        self.assertEqual(code, 403, body)

    def test_another_device_may_start_feed_ask_after_and_cancel_a_job(self):
        s = self.s
        # a film: named by a path on the computer, whoever names it
        code, got = s.start_film()
        self.assertEqual((code, got.get("state")), (200, "queued"), got)
        fin = s.wait(got["job"], ("done", "failed"))
        self.assertEqual(fin["state"], "done", fin)
        code, res = s.post("result", {"job": got["job"]})
        self.assertEqual((code, res["captions"]), (200, 2), res)
        # a recording: started, fed in pieces, marked, asked after, cancelled
        code, got = s.start_yt(duration=10)
        self.assertEqual((code, got.get("state")), (200, "awaiting-audio"), got)
        job = got["job"]
        code, r = s.audio(job, 0, stt_fakes.pcm(2))
        self.assertEqual((code, r.get("have")), (200, 32000), r)
        self.assertEqual(s.post("marks", {"job": job, "marks": [[16000, 1.0]]})[0], 200)
        self.assertEqual(s.post("wave", {"job": job, "rate": 20, "peaks": [0.5, 1.0]})[0], 200)
        code, st = s.status(job)
        self.assertEqual((code, st["state"]), (200, "receiving"), st)
        self.assertEqual(s.post("cancel", {"job": job})[0], 200)
        code, st = s.status(job)
        self.assertEqual((code, st["state"]), (200, "cancelled"), st)


class Stopped(unittest.TestCase):
    """A server that is stopped, or killed outright, leaves no worker behind."""

    def slow_job(self, s):
        s.fake(load_delay=0.2, delay=1.0, segments=[[i, i + 1, " w%d" % i] for i in range(20)])
        code, got = s.start_film(path=s.film(20))
        self.assertEqual(code, 200, got)
        end = time.time() + 30
        while time.time() < end and not s.records("construct"):
            time.sleep(0.05)
        recs = s.records("construct")
        self.assertTrue(recs, "the worker never began\n" + s.text()[-2000:])
        pid = recs[0]["pid"]
        self.assertTrue(alive(pid))
        self.assertEqual(s.status(got["job"])[1]["state"] in ("loading", "transcribing"), True)
        return got["job"], pid

    def gone(self, pid, what):
        end = time.time() + 15
        while time.time() < end and alive(pid):
            time.sleep(0.1)
        self.assertFalse(alive(pid), what)

    @unittest.skipUnless(POSIX, "the worker is found by its pid in /proc")
    def test_stopping_the_server_ends_the_worker_and_deletes_the_recording(self):
        s = Server()
        try:
            job, pid = self.slow_job(s)
            self.assertTrue(s.tmp())
            s.proc.send_signal(signal.SIGTERM)             # what serve.sh stop and the launcher do
            s.proc.wait(30)
            self.gone(pid, "the worker outlived a server that was stopped")
            self.assertEqual(s.tmp(), [], "and no recording is left")
        finally:
            s.stop()

    @unittest.skipUnless(POSIX and sys.platform.startswith("linux"),
                         "the kernel's word (PR_SET_PDEATHSIG) is Linux's; the worker's own look "
                         "for its parent is tested with the worker")
    def test_a_server_killed_outright_takes_the_worker_with_it(self):
        s = Server()
        try:
            job, pid = self.slow_job(s)
            s.proc.send_signal(signal.SIGKILL)             # no hook can run
            s.proc.wait(30)
            self.gone(pid, "the worker outlived a server that was killed")
        finally:
            s.stop()


if __name__ == "__main__":
    unittest.main()
