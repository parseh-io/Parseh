# SPDX-License-Identifier: GPL-3.0-or-later
"""Updating Parseh in place, from Settings (TO-DO §13.16; lib/updater.py).

    python3 -m unittest tests/test_updater.py

Small releases are made here, in memory, by the release builder's own
manifest and zip writers (lib/release.py manifest_of, zip_bytes), and
installed into temporary folders with a person's things beside them.  Then:

  * what an update may never touch (guard), and what it refuses to start
    from: a git checkout, an install with no list of its files;
  * a zip held to its own manifest before it becomes the candidate: not a
    zip, no manifest, a file changed after the build, a path into the
    person's things;
  * the plan, file by file -- new, as installed, changed by hand, not
    Parseh's, retired -- and the direction, said, never refused;
  * the environment and the data formats: what is installed, kept, refused,
    and insisting;
  * THE HELPER ITSELF, as a process of its own: an update applied (every
    file as the new release has it, the retired one gone, the changed one
    replaced and kept, the person's things byte for byte); a step back with
    a lowered format, the content's small files copied first; the helper
    KILLED half way and the next start carrying it on, or undoing it when
    its zip is gone; an update undone on request;
  * the progress page the helper answers on the server's port;
  * GitHub's newest release, and its download checked against its .sha256
    (a local server stands in for GitHub; nothing here reaches the network);
  * the routes, through the real server: the page for the computer and for
    a phone, the zip sent in, the phone refused in the table's words;
  * the launchers: serve.bat's one line, lib/launcher.py's exit status.

config/ is never written: every root here is a temporary folder.
"""
import hashlib
import http.client
import http.server
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    sys.path.insert(0, str(ROOT / p))
import network                                                 # noqa: E402
import release                                                 # noqa: E402
import settingspage                                            # noqa: E402
import updater                                                 # noqa: E402

WHEN = 1790000000
FORMATS = {"parseh-schedule": 1, "parseh-prefs": 1}
ENV = {"conda": {"python": "python=3.12", "deno": "deno"}, "pip": {"numpy": "numpy>=1.24"}}
POSIX = os.name != "nt"

# the files of the first release, and what the second changes
A = {"VERSION": (b"a0.3.2\n", 0o644),
     "serve.sh": (b"#!/bin/sh\necho serving\n", 0o755),
     "build.sh": (b"#!/bin/sh\nexit 0\n", 0o755),
     "lib/a.py": (b"A = 1\n", 0o644),
     "lib/retired.py": (b"RETIRED = True\n", 0o644),
     "lib/parseh.css": (b"body { color: black }\n", 0o644),
     "lib/deep/only.py": (b"ONLY = 1\n", 0o644),
     "html-guide/site/index.html": (b"<p>the guide</p>\n", 0o644),
     "books/.gitkeep": (b"", 0o644),
     "config/.gitkeep": (b"", 0o644),
     "clips/README.md": (b"# clips\n", 0o644)}
B = dict(A)
B.update({"VERSION": (b"a0.3.3\n", 0o644), "lib/a.py": (b"A = 2\n", 0o644),
          "lib/new.py": (b"NEW = 1\n", 0o644), "docs/new.md": (b"# new in B\n", 0o644)})
del B["lib/retired.py"]
del B["lib/deep/only.py"]

# a person's things, which no update may touch
MINE = {"books/english/x/book.json": b'{"slug": "x"}',
        "books/english/x/narration.mp3": b"ID3" + b"\x01" * 5000,
        "exercises/english/d/schedule/0123456789ab.json": b'{"history": [{"grade": 4}]}',
        "dict/xx.db": b"SQLite format 3\x00" + b"\x02" * 3000,
        "mt/fa-en/model.bin": b"\x03" * 4000,
        # speech to text (a0.4.1): the program's folder, a model and a job's temporary audio
        "stt/models/large-v3-turbo/model.bin": b"\x04" * 4000,
        "stt/models/large-v3-turbo/meta.json": b'{"model": "large-v3-turbo", "revision": "0a363e91"}',
        "stt/runtime/1-cp312/ctranslate2/_ext.so": b"\x7fELF" + b"\x05" * 3000,
        "stt/runtime/1-cp312/faster_whisper-1.2.1.dist-info/METADATA": b"Name: faster-whisper\n",
        "stt/tmp/job.pcm": b"\x06" * 500,
        # the ARASAAC pictograms (a0.4.2): a picture, a word list and the manifest
        "arasaac/pictograms/6964.png": b"\x89PNG\r\n\x1a\n" + b"\x07" * 3000,
        "arasaac/index.en.json": b'{"format": 1, "locale": "en", "words": {"6964": [{"k": "house"}]}}',
        "arasaac/manifest.json": b'{"format": 1, "resolution": 300, "complete": true}',
        "config/prefs.json": b'{"settings": {"parseh_theme": {"v": "dark"}}}',
        "config/network.json": b'{"port": 7961, "devices": {"tok": {"name": "Pixel"}}}',
        ".tls/key.pem": b"-----BEGIN PRIVATE KEY-----\nxyz\n",
        ".tls/cert.pem": b"-----BEGIN CERTIFICATE-----\nabc\n"}


def make(files, version, formats=None, env=None, commit=None):
    """A release of `files` -> (zip bytes, manifest), made as lib/release.py makes one."""
    listed = [(rel, data, mode) for rel, (data, mode) in sorted(files.items())]
    commit = commit or hashlib.sha1(version.encode()).hexdigest()
    described = {"data_formats": dict(formats or FORMATS), "environment": env or ENV}
    m = release.manifest_of(listed, version, commit, WHEN, described)
    return release.zip_bytes(listed, m, "parseh-%s/" % version, WHEN, commit), m


def install(root, files, version, **kw):
    """`files` unpacked at `root` with the release's manifest, as unzipping does."""
    _zip, m = make(files, version, **kw)
    for rel, (data, mode) in files.items():
        p = Path(root, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        os.chmod(p, mode)
    Path(root, updater.MANIFEST).write_bytes(release.manifest_bytes(m))
    return m


def put_mine(root):
    for rel, data in MINE.items():
        p = Path(root, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def mine_intact(test, root):
    for rel, data in MINE.items():
        test.assertEqual(Path(root, rel).read_bytes(), data, rel)


def matches(root, manifest):
    """Paths of `manifest` that are not on the disk as it says."""
    bad = []
    for rel, want in manifest["files"].items():
        p = Path(root, rel)
        if not p.is_file() or digest(p) != want["sha256"]:
            bad.append(rel)
        elif POSIX and bool(p.stat().st_mode & 0o111) != bool(int(want["mode"], 8) & 0o111):
            bad.append(rel + " (mode)")
    return bad


class Case(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="parseh-updater-")
        self.root = os.path.realpath(self._td.name)
        self.zips = Path(self.root).parent / ("zips-" + os.path.basename(self.root))
        self.zips.mkdir()

    def tearDown(self):
        # a background post-step (a resume's) may still be writing its report
        end = time.time() + 20
        while time.time() < end and any(
                "helper.py post " + self.root in " ".join(a) for a in _processes()):
            time.sleep(0.1)
        self._td.cleanup()
        shutil.rmtree(self.zips, ignore_errors=True)

    def zip_of(self, files, version, **kw):
        data, m = make(files, version, **kw)
        path = self.zips / ("parseh-%s.zip" % version)
        path.write_bytes(data)
        return str(path), m

    def candidate(self, files, version, **kw):
        path, m = self.zip_of(files, version, **kw)
        copy = self.zips / "sent.zip"
        shutil.copy(path, copy)
        updater.take(self.root, str(copy), "zip", "parseh-%s.zip" % version)
        return m


def _processes():
    out = []
    if not os.path.isdir("/proc"):
        return out
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                out.append(Path("/proc", pid, "cmdline").read_bytes().split(b"\0"))
            except OSError:
                continue
    return [[a.decode("utf-8", "replace") for a in args] for args in out]


# ---------------------------------------------------------------- the rules
class Rules(unittest.TestCase):
    def test_what_no_manifest_may_touch(self):
        for rel in ("../evil", "/etc/passwd", "a\\b", "c:/x", "a//b", "lib/./x", ".tls/key.pem",
                    ".runtime/env/bin/python3", ".git/config", ".parseh-update/helper.py",
                    "config/network.json", "books/english/x/book.json", "dict/fa.db",
                    "mt/fa-en/model.bin", "youtube/videos/en/v/video.json", updater.MANIFEST,
                    "stt/models/large-v3/model.bin", "stt/runtime/1-cp312/ctranslate2/_ext.so",
                    "stt/tmp/job.pcm", "arasaac/pictograms/6964.png", "arasaac/manifest.json",
                    "serve.log", ".serve.pid", ""):
            self.assertTrue(updater.guard(rel), rel)
        for rel in ("lib/a.py", "books/.gitkeep", "config/.gitkeep", "clips/README.md",
                    "exercises/README.md", "html-guide/site/index.html", "serve.bat"):
            self.assertIsNone(updater.guard(rel), rel)

    def test_the_direction_is_said_and_never_refused(self):
        self.assertEqual(updater.direction_of("a0.3.2", "a0.3.10"), "newer")
        self.assertEqual(updater.direction_of("a0.3.10", "a0.3.9"), "older")
        self.assertEqual(updater.direction_of("a0.3.2", "a0.3.2"), "same")
        self.assertEqual(updater.direction_of("a0.9", "b0.1"), "newer")
        import updatepage
        self.assertEqual(updatepage.go_label("newer", "a0.3.3"), "Update to a0.3.3")
        self.assertEqual(updatepage.go_label("older", "a0.3.1"), "Go back to a0.3.1")
        self.assertEqual(updatepage.go_label("same", "a0.3.2"), "Install a0.3.2 again")

    def test_the_environment_changes_only_when_asked(self):
        same = updater.environment_plan(ENV, ENV, "newer", "a0.3.3")
        self.assertEqual((same["install"], same["kept"], same["blocked"]), ([], [], ""))
        self.assertIn("Nothing to install", same["said"])
        more = dict(ENV, pip={"numpy": "numpy>=1.26", "six": "six>=1.16"})
        up = updater.environment_plan(ENV, more, "newer", "a0.3.3")
        self.assertEqual(sorted(i["line"] for i in up["install"]), ["numpy>=1.26", "six>=1.16"])
        # a step back keeps the newer environment, and adds only what is missing
        down = updater.environment_plan(more, dict(ENV, pip={"numpy": "numpy>=1.24",
                                                            "zstd": "zstandard"}),
                                        "older", "a0.3.1")
        self.assertEqual([i["line"] for i in down["install"]], ["zstandard"])
        self.assertEqual([(k["line"], k["wanted"]) for k in down["kept"]],
                         [("numpy>=1.26", "numpy>=1.24")])
        self.assertIn("stays as the newer version made it", down["said"])
        # a Python cannot be changed inside the environment it runs
        py = updater.environment_plan(ENV, dict(ENV, conda={"python": "python=3.13"}),
                                      "newer", "a0.4.0")
        self.assertIn("different Python", py["blocked"])
        back = updater.environment_plan(dict(ENV, conda={"python": "python=3.13"}), ENV,
                                        "older", "a0.3.2")
        self.assertEqual(back["blocked"], "")

    def test_a_failure_is_said_in_words_and_pythons_line_kept_apart(self):
        import errno
        # the one the integration drive met, in the step it met it in
        words, detail = updater.plainly(
            FileNotFoundError(errno.ENOENT, "No such file or directory",
                              "/p/.parseh-update/jobs/j/backup/.parseh-release.json.part"),
            "keeping a copy of Parseh's files as they are")
        self.assertEqual(words, "It stopped while keeping a copy of Parseh's files as they are: a "
                                "file it needed was not there.")
        self.assertTrue(detail.startswith("FileNotFoundError: [Errno 2] No such file"), detail)
        self.assertEqual(updater.plainly(OSError(errno.ENOSPC, "No space left on device"))[0],
                         "The disk is full.")
        self.assertEqual(updater.plainly(PermissionError(errno.EACCES, "Permission denied"))[0],
                         "This computer did not let it change a file.")
        words, detail = updater.plainly(KeyError("files"), "writing down what is installed")
        self.assertIn("did not expect", words)
        self.assertEqual(detail, "KeyError: 'files'")
        # a refusal is in words already, with its own line when it has one
        self.assertEqual(updater.plainly(updater.Refused("Parseh did not stop.")),
                         ("Parseh did not stop.", ""))
        self.assertEqual(updater.plainly(updater.Refused("x.", detail="OSError: y")), ("x.", "OSError: y"))
        # and GitHub out of reach: the words ask a question, the line is the system's
        with patch.dict(os.environ, {"PARSEH_UPDATE_FEED": "http://127.0.0.1:9/latest"}):
            with self.assertRaises(updater.Refused) as e:
                updater.latest(timeout=3)
        self.assertNotIn("Errno", str(e.exception))
        self.assertIn("Errno", e.exception.detail)
        for words in (updater.plainly(OSError(5, "x"), "replacing Parseh's files")[0],
                      str(e.exception)):
            for python in ("Error", "Errno", "Traceback", "<urlopen"):
                self.assertNotIn(python, words)

    def test_the_data_formats_verdict(self):
        up = updater.formats_plan({"data_formats": FORMATS},
                                  {"data_formats": dict(FORMATS, **{"parseh-schedule": 2})}, "x")
        self.assertEqual((up["lowered"], [r["name"] for r in up["raised"]]), ([], ["parseh-schedule"]))
        down = updater.formats_plan({"data_formats": dict(FORMATS, **{"parseh-schedule": 2})},
                                    {"data_formats": FORMATS}, "a0.3.2")
        self.assertEqual([(r["name"], r["from"], r["to"]) for r in down["lowered"]],
                         [("parseh-schedule", 2, 1)])
        self.assertIn("answers so far", down["said"])            # lib/version.py's own words
        # a store the older version has never heard of is lowered too
        gone = updater.formats_plan({"data_formats": dict(FORMATS, **{"parseh-new": 1})},
                                    {"data_formats": FORMATS}, "a0.3.2")
        self.assertEqual([r["name"] for r in gone["lowered"]], ["parseh-new"])


# ---------------------------------------------------------------- what it starts from
class Installed(Case):
    def test_a_git_checkout_is_refused_in_words(self):
        install(self.root, A, "a0.3.2")
        os.mkdir(os.path.join(self.root, ".git"))
        got = updater.installed(self.root)
        self.assertIn("git checkout", got["refused"])
        self.assertIn("releases", got["refused"])
        self.assertTrue(got["git"])

    def test_an_install_with_no_list_of_its_files_is_refused(self):
        Path(self.root, "VERSION").write_text("a0.3.2\n")
        got = updater.installed(self.root)
        self.assertIn("no list of its own files", got["refused"])
        self.assertIn("Install this version fresh from a release", got["refused"])
        self.assertIsNone(got["manifest"])

    def test_a_release_install_can_be_updated(self):
        install(self.root, A, "a0.3.2")
        got = updater.installed(self.root)
        self.assertIsNone(got["refused"])
        self.assertEqual(got["version"], "a0.3.2")

    def test_nothing_says_a_command_to_type(self):
        Path(self.root, "VERSION").write_text("a0.3.2\n")
        said = updater.installed(self.root)["refused"]
        for word in ("python3 ", "./", "git clone", "unzip "):
            self.assertNotIn(word, said)


# ---------------------------------------------------------------- the candidate
class Candidate(Case):
    def setUp(self):
        super().setUp()
        install(self.root, A, "a0.3.2")

    def sent(self, data):
        p = self.zips / "sent.zip"
        p.write_bytes(data)
        return str(p)

    def test_not_a_zip(self):
        with self.assertRaises(updater.Refused) as e:
            updater.take(self.root, self.sent(b"not a zip at all"), "zip", "x.zip")
        self.assertIn("not a zip", str(e.exception))
        self.assertFalse((self.zips / "sent.zip").exists(), "a refused file is not kept")
        self.assertIsNone(updater.candidate(self.root))

    def test_a_zip_with_no_manifest(self):
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("parseh-a0.3.3/VERSION", "a0.3.3\n")
        with self.assertRaises(updater.Refused) as e:
            updater.take(self.root, self.sent(buf.getvalue()), "zip", "x.zip")
        self.assertIn("not a release", str(e.exception))

    def test_a_file_changed_after_the_build(self):
        import io
        import zipfile
        data, _m = make(B, "a0.3.3")
        out = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(out, "w") as zout:
            for zi in zin.infolist():
                body = zin.read(zi)
                if zi.filename.endswith("lib/a.py"):
                    body = b"A = 9  # changed after the build\n"
                zout.writestr(zi, body)
        tampered = out.getvalue()
        with self.assertRaises(updater.Refused) as e:
            updater.take(self.root, self.sent(tampered), "zip", "x.zip")
        self.assertIn("damaged, or was changed", str(e.exception))

    def test_a_zip_that_would_write_into_the_persons_things(self):
        bad = dict(B, **{"config/network.json": (b'{"devices": {}}', 0o644)})
        data, _m = make(bad, "a0.3.3")
        with self.assertRaises(updater.Refused) as e:
            updater.take(self.root, self.sent(data), "zip", "x.zip")
        self.assertIn("config/network.json", str(e.exception))
        # and into speech to text's gigabytes
        bad = dict(B, **{"stt/models/large-v3/model.bin": (b"not a model", 0o644)})
        data, _m = make(bad, "a0.3.3")
        with self.assertRaises(updater.Refused) as e:
            updater.take(self.root, self.sent(data), "zip", "x.zip")
        self.assertIn("stt/models/large-v3/model.bin", str(e.exception))

    def test_a_good_zip_becomes_the_candidate(self):
        m = self.candidate(B, "a0.3.3")
        c = updater.candidate(self.root)
        self.assertEqual((c["version"], c["source"], c["name"]), ("a0.3.3", "zip", "parseh-a0.3.3.zip"))
        self.assertEqual(updater.candidate_manifest(self.root)["files"], m["files"])
        updater.discard(self.root)
        self.assertIsNone(updater.candidate(self.root))


# ---------------------------------------------------------------- the plan
class Plan(Case):
    def test_file_by_file(self):
        install(self.root, A, "a0.3.2")
        put_mine(self.root)
        Path(self.root, "lib/parseh.css").write_bytes(b"body { color: purple }  /* mine */\n")
        Path(self.root, "html-guide/site/index.html").write_bytes(b"<p>compiled here</p>\n")
        Path(self.root, "docs").mkdir()
        Path(self.root, "docs/new.md").write_bytes(b"my own notes\n")
        if POSIX:
            os.chmod(os.path.join(self.root, "serve.sh"), 0o644)        # lost its run bit
            os.chmod(os.path.join(self.root, "lib/a.py"), 0o664)        # only the umask
        self.candidate(B, "a0.3.3")
        p = updater.plan(self.root)
        self.assertIsNone(p["refused"])
        self.assertEqual((p["direction"], p["target"]), ("newer", "a0.3.3"))
        self.assertEqual(sorted(p["delete"]), ["lib/deep/only.py", "lib/retired.py"])
        self.assertEqual(p["edited"], ["lib/parseh.css"])
        self.assertEqual(p["compiled"], ["html-guide/site/index.html"])
        self.assertEqual(p["foreign"], ["docs/new.md"])
        self.assertEqual(p["added"], 1)                                   # lib/new.py
        self.assertEqual(p["modes"], 1 if POSIX else 0)                   # serve.sh, not lib/a.py
        self.assertFalse(p["needs_insist"])
        acts = updater.diff(self.root, updater.installed(self.root)["manifest"],
                            updater.candidate_manifest(self.root))
        touched = {rel for rel, _k in acts["write"] + acts["delete"]} | set(acts["modes"])
        self.assertFalse(touched & set(MINE), "a person's file is never in the plan")

    def test_the_same_version_again_is_accepted(self):
        install(self.root, A, "a0.3.2")
        self.candidate(A, "a0.3.2")
        p = updater.plan(self.root)
        self.assertEqual(p["direction"], "same")
        self.assertIsNone(p["refused"])
        self.assertTrue(p["same_build"])
        self.assertIn("already is", p["said"])

    def test_going_back_is_said_plainly(self):
        install(self.root, B, "a0.3.3")
        self.candidate(A, "a0.3.2")
        p = updater.plan(self.root)
        self.assertEqual(p["direction"], "older")
        self.assertIn("OLDER", p["said"])
        self.assertIn("goes back", p["said"])

    def test_a_lowered_format_needs_insisting(self):
        install(self.root, B, "a0.3.3", formats=dict(FORMATS, **{"parseh-schedule": 2}))
        self.candidate(A, "a0.3.2")
        p = updater.plan(self.root)
        self.assertTrue(p["needs_insist"])
        with self.assertRaises(updater.Refused) as e:
            updater.begin(self.root)
        self.assertTrue(e.exception.insist)
        self.assertIn("Tick the box", str(e.exception))
        self.assertFalse(updater.running(self.root), "nothing is started without insisting")
        self.assertIsNotNone(updater.candidate(self.root), "and the candidate is still there")

    def test_a_python_change_is_refused_before_anything(self):
        install(self.root, A, "a0.3.2")
        self.candidate(B, "a0.3.3", env=dict(ENV, conda={"python": "python=3.13"}))
        p = updater.plan(self.root)
        self.assertIn("different Python", p["refused"])
        with self.assertRaises(updater.Refused):
            updater.begin(self.root)

    def test_begin_writes_the_job_down(self):
        install(self.root, A, "a0.3.2")
        self.candidate(B, "a0.3.3")
        job = updater.begin(self.root, back_to="/books/?x=1", server={"restart": "self"})
        work = Path(self.root, updater.WORK)
        self.assertEqual(updater.running(self.root), job["id"])
        self.assertTrue((work / "helper.py").is_file())
        self.assertEqual((work / "helper.py").read_bytes(), Path(updater.__file__).read_bytes())
        jdir = work / "jobs" / job["id"]
        for f in ("job.json", "release.zip", "manifest.json", "old-manifest.json"):
            self.assertTrue((jdir / f).is_file(), f)
        self.assertIsNone(updater.candidate(self.root))
        self.assertEqual(job["back_to"], "/books/?x=1")
        self.assertEqual(updater.state(self.root)["phase"], "stop")
        with self.assertRaises(updater.Refused):
            updater.begin(self.root)                                      # one at a time
        # an address elsewhere is never where the page goes back to
        self.assertEqual(updater._clean_page("//evil.example/x"), "")
        self.assertEqual(updater._clean_page("https://evil.example/"), "")


# ---------------------------------------------------------------- the helper, as a process
@unittest.skipUnless(POSIX, "the helper's process handling is driven on Linux and macOS here")
class Helper(Case):
    def run_helper(self, verb="run", env=None, wait=True):
        cmd = [sys.executable, os.path.join(self.root, updater.WORK, "helper.py"), verb, self.root]
        p = subprocess.Popen(cmd, cwd=self.root, stderr=subprocess.STDOUT,
                             stdout=subprocess.PIPE if wait else subprocess.DEVNULL,
                             env=dict(os.environ, **(env or {})))
        if wait:
            out = p.communicate(timeout=120)[0].decode("utf-8", "replace")
            return p.returncode, out
        return p

    def report(self):
        return updater.state(self.root).get("report") or {}

    def test_an_update_applied(self):
        mA = install(self.root, A, "a0.3.2")
        put_mine(self.root)
        Path(self.root, "lib/parseh.css").write_bytes(b"/* changed by hand */\n")
        Path(self.root, "docs").mkdir()
        Path(self.root, "docs/new.md").write_bytes(b"my own notes\n")
        self.candidate(B, "a0.3.3")
        mB = updater.candidate_manifest(self.root)
        job = updater.begin(self.root, back_to="/books/")
        rc, out = self.run_helper()
        self.assertEqual(rc, 0, out)
        self.assertEqual(matches(self.root, mB), [])
        self.assertEqual(json.loads(Path(self.root, updater.MANIFEST).read_text())["version"], "a0.3.3")
        for gone in ("lib/retired.py", "lib/deep/only.py"):
            self.assertFalse(Path(self.root, gone).exists(), gone)
        self.assertFalse(Path(self.root, "lib/deep").exists(), "a folder the update emptied goes")
        mine_intact(self, self.root)
        backup = Path(self.root, updater.WORK, "jobs", job["id"], "backup")
        self.assertEqual((backup / "lib/parseh.css").read_bytes(), b"/* changed by hand */\n")
        self.assertEqual((backup / "docs/new.md").read_bytes(), b"my own notes\n")
        self.assertEqual((backup / "lib/retired.py").read_bytes(), A["lib/retired.py"][0])
        self.assertEqual(json.loads((backup / updater.MANIFEST).read_text())["files"], mA["files"])
        r = self.report()
        self.assertTrue(r["ok"])
        self.assertEqual((r["edited"], r["foreign"]), (["lib/parseh.css"], ["docs/new.md"]))
        self.assertEqual(sorted(r["deleted"]), ["lib/deep/only.py", "lib/retired.py"])
        self.assertEqual(r["added"], ["lib/new.py"])
        self.assertEqual(r["back_to"], "/books/")
        st = updater.state(self.root)
        self.assertEqual(st["phase"], "done")
        self.assertEqual({s["id"]: s["state"] for s in st["steps"]}["replace"], "done")
        self.assertFalse(updater.running(self.root))
        self.assertFalse(Path(self.root, updater.WORK, "lock.json").exists())

    def test_the_same_release_again_with_nothing_to_write(self):
        # the very zip installed, chosen again: every file is already as it
        # ships, so there is nothing to back up -- and the old manifest must
        # still be kept, since that is what an undo reads (driven: it once
        # failed here, "No such file or directory: …/backup/.parseh-release.json.part")
        mA = install(self.root, A, "a0.3.2")
        put_mine(self.root)
        self.candidate(A, "a0.3.2")
        job = updater.begin(self.root, back_to="/books/")
        rc, out = self.run_helper()
        self.assertEqual(rc, 0, out)
        r = self.report()
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["direction"], r["written"], r["deleted"]), ("same", 0, []))
        self.assertEqual(matches(self.root, mA), [])
        backup = Path(self.root, updater.WORK, "jobs", job["id"], "backup")
        self.assertEqual(json.loads((backup / updater.MANIFEST).read_text())["files"], mA["files"])
        mine_intact(self, self.root)
        self.assertEqual(updater.state(self.root)["phase"], "done")

    # ---- a file of the person's that an update took, given back
    YOURS = b"# my own notes\n\x00\xff and a few bytes no text editor would write\n"

    def put_yours(self):
        """The person's own docs/new.md -- a name B ships and A does not --
        with a mode and a time of its own."""
        p = Path(self.root, "docs/new.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.YOURS)
        os.chmod(p, 0o600)
        os.utime(p, (1700000000, 1700000000))
        return p

    def update_to(self, files, version, **kw):
        """`files` installed as the next update, by the helper -> (job, report)."""
        self.candidate(files, version, **kw)
        job = updater.begin(self.root)
        rc, out = self.run_helper()
        self.assertEqual(rc, 0, out)
        return job, self.report()

    def page_now(self):
        import updatepage
        return updatepage.page(updater.plan(self.root), updater.settings(self.root),
                               updater.state(self.root), network.SELF)

    def test_going_back_puts_back_a_file_of_yours_an_update_took(self):
        mA = install(self.root, A, "a0.3.2")
        put_mine(self.root)
        p = self.put_yours()
        up, r = self.update_to(B, "a0.3.3")
        self.assertEqual(r["foreign"], ["docs/new.md"])
        self.assertEqual(p.read_bytes(), B["docs/new.md"][0], "B's file took its place")
        # BEFORE: the plan going back says it goes back, and not that it is deleted
        self.candidate(A, "a0.3.2")
        plan = updater.plan(self.root)
        self.assertEqual((plan["back"], plan["gone"], plan["held"]),
                         ([["docs/new.md", "a0.3.3"]], [], []))
        self.assertIn("docs/new.md", plan["delete"], "B's file of that name is Parseh's, and goes")
        page = self.page_now()
        self.assertIn("Yours, put back: a0.3.2 does not ship these names", page)
        self.assertIn("docs/new.md (replaced by the update to a0.3.3)", page)
        deleted = page.split("Deleted, because a0.3.2 does not ship them")[1].split("</details>")[0]
        self.assertNotIn("docs/new.md", deleted, "not listed as deleted as well")
        self.assertIn("1 to delete, ", page)                                # lib/new.py alone
        self.assertIn("and 1 of yours put back.", page)
        # DOWN: the person's file is back, byte for byte, with its mode and time
        down = updater.begin(self.root)
        rc, out = self.run_helper()
        self.assertEqual(rc, 0, out)
        self.assertEqual(p.read_bytes(), self.YOURS)
        self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        self.assertEqual(int(p.stat().st_mtime), 1700000000)
        self.assertEqual(matches(self.root, mA), [])
        mine_intact(self, self.root)
        r = self.report()
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["put_back"], r["put_back_gone"], r["put_back_held"]),
                         ([["docs/new.md", "a0.3.3"]], [], []))
        # B's file of that name is in this update's own backup, for an undo
        backup = Path(self.root, updater.WORK, "jobs", down["id"], "backup")
        self.assertEqual((backup / "docs/new.md").read_bytes(), B["docs/new.md"][0])
        page = self.page_now()
        self.assertIn("Yours again: put back as they were before an update replaced them", page)
        self.assertIn("docs/new.md (replaced by the update to a0.3.3)", page)
        # UP AGAIN: it is the person's once more, so it is taken -- and kept -- again
        again, r = self.update_to(B, "a0.3.3")
        self.assertEqual(r["foreign"], ["docs/new.md"])
        self.assertEqual(Path(self.root, updater.WORK, "jobs", again["id"], "backup",
                              "docs/new.md").read_bytes(), self.YOURS)
        self.assertEqual(updater.yours_taken(self.root)["docs/new.md"]["job"], again["id"])

    def test_going_back_undone_leaves_the_file_waiting_to_go_back(self):
        install(self.root, A, "a0.3.2")
        p = self.put_yours()
        up, _r = self.update_to(B, "a0.3.3")
        self.update_to(A, "a0.3.2")
        self.assertEqual(p.read_bytes(), self.YOURS)
        rc, out = self.run_helper("rollback")          # what the launcher does when A fails to start
        self.assertEqual(rc, 0, out)
        self.assertEqual(p.read_bytes(), B["docs/new.md"][0], "undone: B's file is back")
        self.assertEqual(updater.yours_taken(self.root)["docs/new.md"]["job"], up["id"],
                         "and the person's copy still waits in the update that took it")
        self.candidate(A, "a0.3.2")
        self.assertEqual(updater.plan(self.root)["back"], [["docs/new.md", "a0.3.3"]])

    def test_a_copy_gone_with_its_update_is_said_plainly(self):
        install(self.root, A, "a0.3.2")
        p = self.put_yours()
        up, _r = self.update_to(B, "a0.3.3")
        # three more updates that each ship the name: the one that took the
        # file is removed, with its backup, by the last of them
        for v in ("a0.3.4", "a0.3.5", "a0.3.6"):
            self.update_to(dict(B, VERSION=(v.encode() + b"\n", 0o644)), v)
        jobs = os.listdir(os.path.join(self.root, updater.WORK, "jobs"))
        self.assertEqual(len(jobs), updater.KEEP_JOBS)
        self.assertNotIn(up["id"], jobs)
        taken = json.loads(Path(self.root, updater.WORK, "taken.json").read_text())
        self.assertEqual(taken["format"], updater.TAKEN_FORMAT)
        self.assertEqual(taken["gone"]["docs/new.md"]["to"], "a0.3.3")
        # the plan says so before anything happens
        self.candidate(A, "a0.3.2")
        plan = updater.plan(self.root)
        self.assertEqual((plan["back"], plan["gone"]), ([], [["docs/new.md", "a0.3.3"]]))
        self.assertIn("Yours once, and not put back", self.page_now())
        updater.begin(self.root)
        rc, out = self.run_helper()
        self.assertEqual(rc, 0, out)
        r = self.report()
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["put_back"], r["put_back_gone"]), ([], [["docs/new.md", "a0.3.3"]]))
        self.assertFalse(p.exists(), "nothing to put back, and B's file of that name went")
        page = self.page_now()
        self.assertIn("Yours once, and not put back: the copy kept when an update replaced them "
                      "is gone (only the last three updates keep theirs)", page)
        self.assertIn("docs/new.md (replaced by the update to a0.3.3)", page)
        # SAID ONCE: the name shipped and retired again is Parseh's file
        # coming and going, and nothing more is said about it
        self.update_to(B, "a0.3.3")
        self.candidate(A, "a0.3.2")
        plan = updater.plan(self.root)
        self.assertEqual((plan["back"], plan["gone"]), ([], []))

    def test_a_folder_where_the_file_was_leaves_it_in_its_copy(self):
        install(self.root, A, "a0.3.2")
        p = self.put_yours()
        up, _r = self.update_to(B, "a0.3.3")
        C = dict(A, **{"VERSION": (b"a0.3.4\n", 0o644), "docs/new.md/inside.md": (b"# in\n", 0o644)})
        _job, r = self.update_to(C, "a0.3.4")
        held = os.path.join(self.root, updater.WORK, "jobs", up["id"], "backup", "docs", "new.md")
        self.assertEqual(r["put_back_held"], [["docs/new.md", "a0.3.3", held]])
        self.assertTrue(p.is_dir())
        self.assertEqual(Path(held).read_bytes(), self.YOURS)
        self.assertIn("Yours, still in that update's copy", self.page_now())

    @unittest.skipIf(POSIX and os.geteuid() == 0, "root may change what nobody else may")
    def test_a_failure_is_said_in_words_with_pythons_line_beneath(self):
        install(self.root, A, "a0.3.2")
        put_mine(self.root)
        self.candidate(B, "a0.3.3")
        deep = os.path.join(self.root, "lib", "deep")
        os.chmod(deep, 0o555)             # lib/deep/only.py, which B retires, cannot be deleted
        try:
            updater.begin(self.root)
            rc, out = self.run_helper()
        finally:
            os.chmod(deep, 0o755)
        self.assertEqual(rc, 1, out)
        r = self.report()
        self.assertFalse(r["ok"])
        self.assertTrue(r["rolled_back"])
        self.assertEqual(r["error"], "It stopped while replacing Parseh's files: this computer "
                                     "did not let it change a file.")
        self.assertTrue(r["error_detail"].startswith("PermissionError: [Errno 13]"), r)
        self.assertIn("lib/deep/only.py", r["error_detail"])
        _z, mA = make(A, "a0.3.2")
        self.assertEqual(matches(self.root, mA), [])
        mine_intact(self, self.root)
        st = updater.state(self.root)
        self.assertEqual(st["said"], "The update did not happen. " + r["error"])
        failed = {s["id"]: s for s in st["steps"]}["replace"]
        self.assertEqual((failed["state"], failed["detail"]), ("failed", r["error_detail"]))
        page = self.page_now()
        import html
        self.assertIn(html.escape("The update to a0.3.3 did not happen. " + r["error"]), page)
        self.assertIn('<p class="tech" data-report-detail>PermissionError: [Errno 13]', page)
        head = page.split('data-report=')[1].split("</p>")[0]
        self.assertNotIn("PermissionError", head, "Python's words are beneath, not in the sentence")

    def test_back_again_with_a_lowered_format_copies_the_content_first(self):
        up = dict(FORMATS, **{"parseh-schedule": 2})
        install(self.root, B, "a0.3.3", formats=up)
        put_mine(self.root)
        self.candidate(A, "a0.3.2")
        job = updater.begin(self.root, insist=True)
        rc, out = self.run_helper()
        self.assertEqual(rc, 0, out)
        _z, mA = make(A, "a0.3.2")
        self.assertEqual(matches(self.root, mA), [])
        self.assertFalse(Path(self.root, "lib/new.py").exists())
        self.assertTrue(Path(self.root, "lib/retired.py").exists(), "the retired file is back")
        mine_intact(self, self.root)
        content = Path(self.root, updater.WORK, "jobs", job["id"], "content")
        self.assertEqual((content / "exercises/english/d/schedule/0123456789ab.json").read_bytes(),
                         MINE["exercises/english/d/schedule/0123456789ab.json"])
        self.assertTrue((content / "config/prefs.json").is_file())
        self.assertFalse((content / "books/english/x/narration.mp3").exists(), "no narration")
        self.assertFalse((content / "stt").exists(), "and no speech model: gigabytes, and no format of Parseh's in them")
        self.assertFalse((content / "arasaac").exists(), "and no ARASAAC picture: fetched again by a button")
        journal = Path(self.root, updater.WORK, "jobs", job["id"], "journal.jsonl").read_text()
        self.assertLess(journal.index('"content"'), journal.index('"backup"'),
                        "the content is copied before anything else is done")

    def test_a_raised_format_copies_the_content_first_and_it_can_be_put_back(self):
        # TO-DO §13.20: a faulty migration on the way UP must find the old
        # small files kept with the job, and Settings must be able to put them back
        install(self.root, A, "a0.3.2")
        put_mine(self.root)
        up = dict(FORMATS, **{"parseh-schedule": 2})
        job, r = self.update_to(B, "a0.3.3", formats=up)
        self.assertTrue(r["ok"], r)
        self.assertEqual(job["raised"], ["parseh-schedule"])
        content = Path(self.root, updater.WORK, "jobs", job["id"], "content")
        self.assertEqual(r["content_copy"], str(content))
        self.assertEqual((content / "config/prefs.json").read_bytes(), MINE["config/prefs.json"])
        self.assertEqual((content / "exercises/english/d/schedule/0123456789ab.json").read_bytes(),
                         MINE["exercises/english/d/schedule/0123456789ab.json"])
        self.assertFalse((content / "books/english/x/narration.mp3").exists(), "no narration")
        journal = Path(self.root, updater.WORK, "jobs", job["id"], "journal.jsonl").read_text()
        self.assertLess(journal.index('"content"'), journal.index('"backup"'),
                        "the content is copied before anything else is done")
        # the new version's migration goes wrong: two files rewritten badly
        sched = Path(self.root, "exercises/english/d/schedule/0123456789ab.json")
        prefs_file = Path(self.root, "config/prefs.json")
        sched.write_bytes(b'{"migrated": "badly"}')
        prefs_file.write_bytes(b'{"settings": {}}')
        Path(self.root, "exercises/english/d/schedule/made-since.json").write_bytes(b"{}")
        copies = updater.content_copies(self.root)
        self.assertEqual([(c["id"], c["from"], c["to"]) for c in copies],
                         [(job["id"], "a0.3.2", "a0.3.3")])
        self.assertIn("raised", copies[0]["why"])
        page = self.page_now_with_copies()
        self.assertIn('data-put-back="%s"' % job["id"], page)
        self.assertIn("Copies of your small files", page)
        got = updater.put_back_content(self.root, job["id"])
        self.assertEqual(got["kept"], 2)
        self.assertEqual(sched.read_bytes(), MINE["exercises/english/d/schedule/0123456789ab.json"])
        self.assertEqual(prefs_file.read_bytes(), MINE["config/prefs.json"])
        self.assertTrue(Path(self.root, "exercises/english/d/schedule/made-since.json").exists(),
                        "a file made since the update is left as it is")
        aside = Path(got["aside"])
        self.assertEqual((aside / "exercises/english/d/schedule/0123456789ab.json").read_bytes(),
                         b'{"migrated": "badly"}', "what was written over is kept first")
        self.assertEqual((aside / "config/prefs.json").read_bytes(), b'{"settings": {}}')
        self.assertIn("Put back", self.page_now_with_copies())
        with self.assertRaises(updater.Refused):
            updater.put_back_content(self.root, "no-such-job")

    def test_an_update_that_changes_no_format_copies_nothing(self):
        install(self.root, A, "a0.3.2")
        put_mine(self.root)
        job, r = self.update_to(B, "a0.3.3")
        self.assertTrue(r["ok"], r)
        self.assertFalse(Path(self.root, updater.WORK, "jobs", job["id"], "content").exists())
        self.assertEqual(updater.content_copies(self.root), [])

    def page_now_with_copies(self):
        import updatepage
        return updatepage.page(updater.plan(self.root), updater.settings(self.root),
                               updater.state(self.root), network.SELF,
                               copies=updater.content_copies(self.root))

    def test_speech_to_text_is_left_as_it_is_both_ways(self):
        # WHAT AN UPDATE INTO a0.4.1, AND THE STEP BACK, DO TO SPEECH TO TEXT (the brief's
        # item 13, driven with the real helper): nothing.  stt/ is in no release's manifest,
        # so neither direction ever opens a file in it -- the program, a model and a job's
        # temporary audio stay byte for byte, with their modes and their times.
        install(self.root, A, "a0.3.2")
        put_mine(self.root)
        speech = sorted(rel for rel in MINE if rel.startswith("stt/"))
        self.assertGreaterEqual(len(speech), 5)
        for n, rel in enumerate(speech):
            os.utime(Path(self.root, rel), (1700000000 + n, 1700000000 + n))
        before = {rel: (Path(self.root, rel).stat().st_mtime_ns, Path(self.root, rel).stat().st_mode)
                  for rel in speech}

        def untouched(where):
            for rel in speech:
                p = Path(self.root, rel)
                self.assertEqual(p.read_bytes(), MINE[rel], where + ": " + rel)
                st = p.stat()
                self.assertEqual((st.st_mtime_ns, st.st_mode), before[rel], where + ": " + rel + " was not opened")
            self.assertEqual(sorted(str(p.relative_to(self.root)) for p in Path(self.root, "stt").rglob("*")
                                    if p.is_file()), speech, where + ": nothing added, nothing taken")
        # INTO the next version
        up, r = self.update_to(B, "a0.3.3")
        self.assertTrue(r["ok"], r)
        untouched("after the update")
        self.assertNotIn("stt/", json.dumps(r), "and the report of the update does not name it")
        # and BACK, as the plan puts it: no box, no small files copied
        self.candidate(A, "a0.3.2")
        plan = updater.plan(self.root)
        self.assertFalse(plan["needs_insist"], "nothing about speech to text has to be understood first")
        self.assertNotIn("stt/", json.dumps(plan))
        job = updater.begin(self.root)
        rc, out = self.run_helper()
        self.assertEqual(rc, 0, out)
        untouched("after the step back")
        r = self.report()
        self.assertTrue(r["ok"], r)
        self.assertNotIn("stt/", json.dumps(r))
        # and forward again
        self.update_to(B, "a0.3.3")
        untouched("and forward again")

    def kill_half_way(self):
        install(self.root, A, "a0.3.2")
        put_mine(self.root)
        self.candidate(B, "a0.3.3")
        job = updater.begin(self.root)
        p = self.run_helper(env={"PARSEH_UPDATE_TEST_DELAY": "0.4"}, wait=False)
        end = time.time() + 60
        while time.time() < end:
            st = updater.state(self.root)
            if st.get("phase") == "replace" and (st.get("done") or 0) >= 3:
                break
            time.sleep(0.05)
        os.kill(p.pid, signal.SIGKILL)
        p.wait()
        self.assertTrue(updater.running(self.root), "an update killed half way is still pending")
        return job

    def test_killed_half_way_then_carried_on_at_the_next_start(self):
        job = self.kill_half_way()
        _z, mB = make(B, "a0.3.3")
        _z, mA = make(A, "a0.3.2")
        self.assertTrue(matches(self.root, mB), "half way: not yet the new version")
        self.assertTrue(matches(self.root, mA), "half way: no longer the old one")
        # what serve.py and lib/launcher.py ask first thing
        self.assertTrue(updater.finish_first(self.root))
        self.assertEqual(matches(self.root, mB), [])
        self.assertFalse(updater.running(self.root))
        mine_intact(self, self.root)
        r = self.report()
        self.assertTrue(r["ok"] and r["resumed"])
        self.wait_post(job["id"])

    def test_killed_half_way_with_its_zip_gone_then_undone(self):
        job = self.kill_half_way()
        os.unlink(os.path.join(self.root, updater.WORK, "jobs", job["id"], "release.zip"))
        self.assertTrue(updater.finish_first(self.root))
        _z, mA = make(A, "a0.3.2")
        self.assertEqual(matches(self.root, mA), [])
        self.assertFalse(Path(self.root, "lib/new.py").exists(), "what it created is taken away")
        mine_intact(self, self.root)
        r = self.report()
        self.assertFalse(r["ok"])
        self.assertTrue(r["rolled_back"])
        self.assertEqual(updater.state(self.root)["phase"], "rolled-back")

    def test_undone_on_request(self):
        install(self.root, A, "a0.3.2")
        put_mine(self.root)
        self.candidate(B, "a0.3.3")
        updater.begin(self.root)
        self.assertEqual(self.run_helper()[0], 0)
        rc, out = self.run_helper("rollback")
        self.assertEqual(rc, 0, out)
        _z, mA = make(A, "a0.3.2")
        self.assertEqual(matches(self.root, mA), [])
        mine_intact(self, self.root)

    def test_the_helpers_own_server_is_not_kept_waiting(self):
        install(self.root, A, "a0.3.2")
        self.candidate(B, "a0.3.3")
        job = updater.begin(self.root)
        with patch.dict(os.environ, {"PARSEH_UPDATE_JOB": job["id"]}):
            self.assertFalse(updater.finish_first(self.root))
            self.assertNotIn("PARSEH_UPDATE_JOB", os.environ, "and it is not handed on")
        self.assertTrue(updater.running(self.root))

    def wait_post(self, jid):
        path = Path(self.root, updater.WORK, "jobs", jid, "journal.jsonl")
        end = time.time() + 30
        while time.time() < end and '"post"' not in path.read_text():
            time.sleep(0.1)


class StatusServer(Case):
    def test_the_progress_page_while_the_server_is_down(self):
        s = socket_free()
        fake = type("A", (), {"st": {"id": "j", "phase": "replace", "said": "Replacing: 3 of 9",
                                     "done": 3, "total": 9},
                              "job": {"from": "a0.3.2", "to": "a0.3.3"}})()
        srv = updater._StatusServer(fake, "127.0.0.1", s, "http", None)
        try:
            c = http.client.HTTPConnection("127.0.0.1", s, timeout=10)
            c.request("GET", "/settings/api/update/state")
            r = c.getresponse()
            got = json.loads(r.read())
            self.assertEqual((r.status, got["helper"], got["update"]["done"]), (200, True, 3))
            c = http.client.HTTPConnection("127.0.0.1", s, timeout=10)
            c.request("GET", "/books/")
            r = c.getresponse()
            page = r.read().decode()
            self.assertEqual(r.status, 503)
            self.assertIn("being updated", page)
            self.assertIn("a0.3.3", page)
            self.assertIn('http-equiv=refresh', page)
            c = http.client.HTTPConnection("127.0.0.1", s, timeout=10)
            c.request("POST", "/__prefs", body=b"{}")
            self.assertEqual(c.getresponse().status, 503)
        finally:
            srv.stop()


def socket_free():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ---------------------------------------------------------------- GitHub, stood in for
class Feed:
    """A local server standing in for GitHub: the release list and its assets."""

    def __init__(self, files):
        self.files = files                      # path -> (status, bytes)
        feed = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                status, data = feed.files.get(self.path, (404, b'{"message": "Not Found"}'))
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class GitHub(Case):
    def feed(self, zip_bytes, sha=None, tag="a0.3.3", assets=True):
        name = "parseh-%s.zip" % tag
        doc = {"tag_name": tag, "name": "Parseh " + tag, "published_at": "2026-09-26T09:00:00Z",
               "html_url": "https://example.invalid/r", "body": "### Changed\n- things\n",
               "assets": []}
        f = Feed({})
        if assets:
            doc["assets"] = [
                {"name": name, "size": len(zip_bytes), "browser_download_url": f.url + "/a/" + name},
                {"name": name + ".sha256", "size": 90,
                 "browser_download_url": f.url + "/a/" + name + ".sha256"}]
        f.files.update({"/latest": (200, json.dumps(doc).encode()),
                        "/a/" + name: (200, zip_bytes),
                        "/a/" + name + ".sha256": (200, ("%s  %s\n" % (
                            sha or hashlib.sha256(zip_bytes).hexdigest(), name)).encode())})
        self.addCleanup(f.close)
        return f

    def test_the_newest_release_is_asked_and_kept(self):
        install(self.root, A, "a0.3.2")
        data, _m = make(B, "a0.3.3")
        f = self.feed(data)
        with patch.dict(os.environ, {"PARSEH_UPDATE_FEED": f.url + "/latest"}):
            s = updater.check(self.root)
        self.assertEqual(s["error"], "")
        self.assertEqual((s["latest"]["version"], s["latest"]["size"]), ("a0.3.3", len(data)))
        kept = json.loads(Path(self.root, "config", "updates.json").read_text())
        self.assertEqual((kept["_format"], kept["daily"]), (updater.STORE_FORMAT, False))
        # downloaded, checked against its .sha256, made the candidate
        updater.fetch(self.root, s["latest"])
        c = updater.candidate(self.root)
        self.assertEqual((c["version"], c["source"]), ("a0.3.3", "github"))
        self.assertEqual(c["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(updater.plan(self.root)["direction"], "newer")

    def test_a_download_that_is_not_the_published_file_is_refused(self):
        install(self.root, A, "a0.3.2")
        data, _m = make(B, "a0.3.3")
        f = self.feed(data, sha="0" * 64)
        with patch.dict(os.environ, {"PARSEH_UPDATE_FEED": f.url + "/latest"}):
            info = updater.latest()
        with self.assertRaises(updater.Refused) as e:
            updater.fetch(self.root, info)
        self.assertIn("not the file Parseh expects", str(e.exception))
        self.assertIsNone(updater.candidate(self.root))

    def test_what_github_may_answer(self):
        f = Feed({})
        self.addCleanup(f.close)
        with patch.dict(os.environ, {"PARSEH_UPDATE_FEED": f.url + "/latest"}):
            with self.assertRaises(updater.Refused) as e:
                updater.latest()
        self.assertIn("No release of Parseh has been published", str(e.exception))
        g = self.feed(b"x", assets=False)
        with patch.dict(os.environ, {"PARSEH_UPDATE_FEED": g.url + "/latest"}):
            with self.assertRaises(updater.Refused) as e:
                updater.latest()
        self.assertIn("checksum", str(e.exception))
        h = self.feed(b"x", tag="v1.0-beta")
        with patch.dict(os.environ, {"PARSEH_UPDATE_FEED": h.url + "/latest"}):
            with self.assertRaises(updater.Refused) as e:
                updater.latest()
        self.assertIn("not a version", str(e.exception))
        with patch.dict(os.environ, {"PARSEH_UPDATE_FEED": "http://127.0.0.1:9/latest"}):
            with self.assertRaises(updater.Refused) as e:
                updater.latest(timeout=3)
        self.assertIn("could not be reached", str(e.exception))

    def test_the_daily_look_is_off_until_ticked(self):
        self.assertFalse(updater.settings(self.root)["daily"])
        self.assertFalse(updater.due(self.root))
        updater.save_settings(self.root, daily=True)
        self.assertTrue(updater.due(self.root))
        updater.save_settings(self.root, checked=time.time())
        self.assertFalse(updater.due(self.root))
        self.assertTrue(updater.due(self.root, now=time.time() + updater.DAY))


# ---------------------------------------------------------------- the routes, through the server
class Served(Case):
    @classmethod
    def setUpClass(cls):
        import serve
        cls.serve = serve
        cls.srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
        cls.quiet = patch.object(serve.Handler, "log_request", lambda *a, **k: None)
        cls.quiet.start()
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.quiet.stop()

    def setUp(self):
        super().setUp()
        install(self.root, A, "a0.3.2")
        p = patch.object(self.serve, "ROOT", self.root)
        p.start()
        self.addCleanup(p.stop)

    def ask(self, method, path, body=None, ctype="application/json"):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=60)
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
        c.request(method, path, body=data, headers={"Content-Type": ctype} if data is not None else {})
        r = c.getresponse()
        raw = r.read()
        c.close()
        try:
            return r.status, json.loads(raw)
        except ValueError:
            return r.status, raw.decode("utf-8", "replace")

    def as_phone(self):
        ps = [patch.object(network, "where", lambda ip, doc=None: network.LAN),
              patch.object(network, "may_connect", lambda ip, doc=None: True),
              patch.object(network, "let_in", lambda *a, **k: True),
              patch.object(network, "needs_code", lambda ip, doc=None: False)]
        for p in ps:
            p.start()
            self.addCleanup(p.stop)

    def test_a_zip_sent_in_and_the_page_that_says_what_it_would_do(self):
        data, _m = make(B, "a0.3.3")
        status, got = self.ask("POST", "/settings/api/update/upload?name=parseh-a0.3.3.zip",
                               data, "application/zip")
        self.assertEqual((status, got["ok"], got["candidate"]["version"]), (200, True, "a0.3.3"))
        status, plan = self.ask("GET", "/settings/api/update/plan")
        self.assertEqual((status, plan["direction"]), (200, "newer"))
        status, page = self.ask("GET", "/settings/update/")
        self.assertEqual(status, 200)
        self.assertIn("Update to a0.3.3", page)
        self.assertIn("data-yes", page)
        self.assertIn("lib/retired.py", page)
        status, st = self.ask("GET", "/settings/api/update/state")
        self.assertEqual((st["helper"], st["candidate"]["version"]), (False, "a0.3.3"))
        # a server a test holds, not main's, cannot stop and start again
        status, got = self.ask("POST", "/settings/api/update/apply", {})
        self.assertEqual(status, 409)
        self.assertIn("cannot stop and start again", got["error"])
        self.assertFalse(updater.running(self.root))

    def test_a_broken_zip_is_refused_in_words(self):
        status, got = self.ask("POST", "/settings/api/update/upload?name=x.zip", b"PK\x03\x04no",
                               "application/zip")
        self.assertEqual(status, 400)
        self.assertIn("not a zip", got["error"])

    def test_a_phone_sees_why_and_may_not(self):
        self.candidate(B, "a0.3.3")
        self.as_phone()
        for route in ("apply", "upload", "fetch", "discard", "stop"):
            status, got = self.ask("POST", "/settings/api/update/" + route, {})
            self.assertEqual((status, got["error"]), (403, settingspage.refusal("parseh.update")),
                             route)
        status, got = self.ask("POST", "/settings/api/update/daily", {"on": True})
        self.assertEqual((status, got["daily"]), (200, True))
        status, page = self.ask("GET", "/settings/update/")
        self.assertIn('data-lock="parseh.update"', page)
        self.assertNotIn("<button type=\"button\" class=\"go newer\" data-go", page)
        self.assertNotIn("data-zip aria-label", page)
        self.assertIn("An update replaces Parseh itself.", page)
        self.assertIsNotNone(updater.candidate(self.root), "the candidate is still there")

    def test_only_parsehs_own_page_may_ask(self):
        data, _m = make(B, "a0.3.3")
        port = self.srv.server_address[1]

        def send(path, body, headers):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
            c.request("POST", path, body=body, headers=headers)
            r = c.getresponse()
            got = json.loads(r.read())
            c.close()
            return r.status, got
        up = "/settings/api/update/upload?name=x.zip"
        # what a page elsewhere can send without asking first: text/plain
        status, got = send(up, data, {"Content-Type": "text/plain"})
        self.assertEqual(status, 403)
        self.assertIn("application/zip", got["error"])
        status, got = send("/settings/api/update/apply", b'{"insist": true}',
                           {"Content-Type": "text/plain;charset=UTF-8"})
        self.assertEqual(status, 403)
        # the browser saying where it comes from
        status, got = send(up, data, {"Content-Type": "application/zip",
                                      "Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)
        self.assertIn("another site", got["error"])
        status, got = send(up, data, {"Content-Type": "application/zip", "Origin": "null"})
        self.assertEqual(status, 403)
        self.assertIsNone(updater.candidate(self.root), "nothing refused was kept")
        # Parseh's own page
        status, got = send(up, data, {"Content-Type": "application/zip", "Sec-Fetch-Site": "same-origin",
                                      "Origin": "http://127.0.0.1:%d" % port,
                                      "Host": "127.0.0.1:%d" % port})
        self.assertEqual((status, got["candidate"]["version"]), (200, "a0.3.3"))

    def test_what_fails_is_said_in_words_and_pythons_line_sent_apart(self):
        # GitHub out of reach: Check now answers in words, the line beside them
        with patch.dict(os.environ, {"PARSEH_UPDATE_FEED": "http://127.0.0.1:9/latest"}):
            status, got = self.ask("POST", "/settings/api/update/check", {})
        self.assertEqual(status, 502)
        self.assertNotIn("Errno", got["error"])
        self.assertIn("Errno", got["detail"])
        import updatepage
        page = updatepage.page(updater.plan(self.root), updater.settings(self.root),
                               updater.state(self.root), network.SELF)
        self.assertIn('<span class="tech">ConnectionRefusedError', page)
        # a release whose zip is not there: the download, stopped, said the same way
        name = "parseh-a0.3.3.zip"
        f = Feed({})
        self.addCleanup(f.close)
        f.files["/latest"] = (200, json.dumps({"tag_name": "a0.3.3", "assets": [
            {"name": name, "size": 1000, "browser_download_url": f.url + "/gone/" + name},
            {"name": name + ".sha256", "size": 90,
             "browser_download_url": f.url + "/a/" + name + ".sha256"}]}).encode())
        f.files["/a/" + name + ".sha256"] = (200, ("%s  %s\n" % ("0" * 64, name)).encode())
        with patch.dict(os.environ, {"PARSEH_UPDATE_FEED": f.url + "/latest"}):
            self.assertEqual(self.ask("POST", "/settings/api/update/check", {})[0], 200)
        self.assertEqual(self.ask("POST", "/settings/api/update/fetch", {})[0], 200)
        end = time.time() + 30
        while time.time() < end:
            st = self.ask("GET", "/settings/api/update/state")[1]
            if not st["fetch"].get("running"):
                break
            time.sleep(0.1)
        self.assertEqual(st["fetch"]["error"], "The release could not be downloaded to the end. "
                         "What came is kept, and getting it again carries on from there.")
        self.assertIn("404", st["fetch"]["detail"])

    def test_settings_has_the_door(self):
        status, page = self.ask("GET", "/settings/")
        self.assertIn('href="/settings/update/"', page)
        self.assertIn("Updating Parseh", page)


class Launchers(unittest.TestCase):
    def test_serve_bat_runs_the_launcher_and_its_exit_on_one_line(self):
        raw = (ROOT / "serve.bat").read_bytes()
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "serve.bat stays CRLF")
        lines = [ln for ln in raw.decode().split("\r\n") if "lib\\launcher.py %*" in ln
                 and not ln.startswith("rem")]
        self.assertEqual(len(lines), 1)
        self.assertIn("exit /b", lines[0], "the exit is read with the launcher's own line")

    def test_the_launcher_runs_an_update_when_its_server_asks(self):
        src = (ROOT / "lib" / "launcher.py").read_text(encoding="utf-8")
        self.assertIn("updater.LAUNCHER_EXIT", src)
        self.assertIn('PARSEH_LAUNCHER="1"', src)
        self.assertIn("updater.finish_first(ROOT)", src)
        serve_src = (ROOT / "serve.py").read_text(encoding="utf-8")
        self.assertIn("sys.exit(updater.LAUNCHER_EXIT)", serve_src)
        # an unfinished update is finished before the rest of Parseh is imported
        self.assertLess(serve_src.index("updater.finish_first("), serve_src.index("import books as booklib"))

    def test_the_helper_needs_nothing_but_the_standard_library(self):
        import ast
        tree = ast.parse((ROOT / "lib" / "updater.py").read_text(encoding="utf-8"))
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = {a.name.split(".")[0] for n in top for a in n.names}
        self.assertLessEqual(names, set(sys.stdlib_module_names), names - set(sys.stdlib_module_names))


if __name__ == "__main__":
    unittest.main()
