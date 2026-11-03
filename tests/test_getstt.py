# SPDX-License-Identifier: GPL-3.0-or-later
"""Speech to text's manager (lib/getstt.py, lib/sttprobe.py), a0.4.1.

    python3 -m unittest tests/test_getstt.py

NORMAL CI HAS NO MODEL, NO PROGRAM AND NO CUDA (brief item 11), and every test
here runs so: the program's folder and the models are made in a temporary tree
out of a few bytes (their sizes and hashes patched to match), the hardware
probe is a faked answer, and nothing is downloaded.  What is held:

  * THE PINS AGREE: lib/stt-requirements.txt (every line pinned, hashed, no
    NVIDIA package, one set of lines per computer under its markers), the
    versions in getstt.PIN, the models' revisions, sizes and digests, the
    measured costs;
  * A NORMAL PARSEH NEEDS NONE OF IT (brief tests 1-3): nothing an installer
    reads names it, the server imports and serves with it absent, and no
    module the server imports imports it;
  * ONLY TWO MODELS AND THREE MODES (tests 6, 27, 28): a table of malicious
    names, paths, devices and compute types is refused before any file, folder,
    child or loader is touched;
  * WHAT IS INSTALLED IS READ FROM THE DISK (test 24, the model half): absent,
    ready, older, newer, another Python, broken, unavailable -- and nothing a
    status does makes stt/;
  * THE GRAPHICS CARD IS PROVED, NOT COUNTED (test 25): none, found-not-ready
    (with the piece that is missing) and ready, from a faked probe, and never
    probed where the program has no card support;
  * removal takes one folder and refuses what is in use; a sweep takes what a
    killed server left and nothing else; children end when the server does;
  * git ignores what speech to text puts under stt/ (test 26).

The fetching and the pip step, with a fake pip command and fake downloads, are
in tests/test_download.py (GetsttTests), beside its siblings'.
"""
import ast
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    sys.path.insert(0, str(ROOT / p))
import getstt                                                  # noqa: E402

PY = sys.executable


def sha(b):
    return hashlib.sha256(b).hexdigest()


def requirement_lines():
    """[(name, version, marker text or "", [hashes])] of lib/stt-requirements.txt."""
    text = (ROOT / "lib" / "stt-requirements.txt").read_text(encoding="utf-8")
    logical, cur = [], ""
    for line in text.splitlines():
        if line.lstrip().startswith("#") or not line.strip():
            continue
        cur += line.rstrip("\\").rstrip() + " "
        if not line.rstrip().endswith("\\"):
            logical.append(cur.strip())
            cur = ""
    out = []
    for l in logical:
        head = l.split(" --hash=")[0]
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([\w.]+)\s*(?:;\s*(.*))?$", head)
        assert m, head
        out.append((m.group(1), m.group(2), (m.group(3) or "").strip(),
                    re.findall(r"--hash=sha256:([0-9a-f]{64})", l)))
    return out


class Tree(unittest.TestCase):
    """A temporary stt/, wired into getstt for one test, and torn down with it."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.stt = self.tmp / "stt"
        self.patches = [mock.patch.object(getstt, "STT_DIR", str(self.stt))]
        for p in self.patches:
            p.start()
        getstt._SIZES.clear()
        getstt.forget_hardware()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        getstt.forget_hardware()
        self._td.cleanup()

    # ---- what the disk can be made to hold
    def make_runtime(self, generation=None, tag=None, dists=None):
        generation = getstt.PIN["generation"] if generation is None else generation
        tag = tag or getstt.PYTAG
        folder = self.stt / "runtime" / ("%d-%s" % (generation, tag))
        for name, ver in (dists if dists is not None else
                          [(d, v or "1.0") for d, v in getstt.REQUIRED]):
            (folder / ("%s-%s.dist-info" % (name, ver))).mkdir(parents=True)
        return folder

    def tiny_pins(self):
        """The two models, as a few bytes each: their pins patched to match."""
        pins, made = dict(getstt.MODEL_PINS), {}
        for key in getstt.speechmodels.STANDARD_MODELS:
            made[key] = {n: (key + "/" + n).encode() * 2 for n in getstt.MODEL_PINS[key]["files"]}
            pins[key] = {"repo": "example/" + key, "revision": "b" * 40,
                         "files": {n: (sha(b), len(b)) for n, b in made[key].items()}}
        patches = [mock.patch.object(getstt, "MODEL_PINS", pins),
                   mock.patch.dict(getstt.MEASURED, {k: sum(len(b) for b in made[k].values())
                                                     for k in made})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return pins, made

    def make_model(self, key, made, revision=None, break_it=False):
        folder = self.stt / "models" / key
        folder.mkdir(parents=True)
        for name, body in made[key].items():
            (folder / name).write_bytes(body[:-1] if break_it and name == "model.bin" else body)
        (folder / "meta.json").write_text(json.dumps(
            {"model": key, "revision": revision or getstt.MODEL_PINS[key]["revision"],
             "pin": getstt.PIN["generation"], "built": "2026-09-28"}))
        return folder


# ------------------------------------------------------------------ the pins
class Pins(unittest.TestCase):
    def test_every_requirement_is_pinned_hashed_and_none_is_a_graphics_library(self):
        rows = requirement_lines()
        self.assertGreater(len(rows), 25)
        for name, ver, _marker, hashes in rows:
            self.assertRegex(ver, r"^\d[\w.]*$", name)
            self.assertGreaterEqual(len(hashes), 1, "%s has no hash: pip's hash-checking mode would refuse "
                                    "the whole file" % name)
            self.assertEqual(len(set(hashes)), len(hashes), name + " lists a hash twice")
            self.assertFalse(name.lower().startswith("nvidia"),
                             "Parseh never installs the graphics card's software (%s)" % name)
            self.assertNotIn("cuda", name.lower())

    def test_the_pin_and_the_list_say_the_same_versions(self):
        by = {}
        for name, ver, marker, _h in requirement_lines():
            by.setdefault(name.lower(), []).append((ver, marker))
        for name in ("faster-whisper", "ctranslate2", "av", "tokenizers", "huggingface-hub"):
            self.assertEqual([v for v, _m in by[name]], [getstt.PIN[name]], name)
        # onnxruntime is two lines: the pin, and the one an Intel Mac takes
        ort = {m: v for v, m in by["onnxruntime"]}
        self.assertEqual(len(ort), 2)
        self.assertIn(getstt.PIN["onnxruntime"], ort.values())
        self.assertEqual(getstt.PIN["python"], "cp312")
        self.assertEqual(getstt.RUNTIME_PYTHON, "3.12")
        for dist, ver in getstt.REQUIRED:
            if ver:
                self.assertIn(ver, [v for v, _m in by[dist.replace("_", "-")]], dist)

    @unittest.skipUnless(__import__("importlib.util").util.find_spec("packaging"), "no packaging here")
    def test_the_markers_choose_one_set_of_lines_for_each_kind_of_computer(self):
        from packaging.markers import Marker
        rows = requirement_lines()
        kinds = {"linux x86_64": ("linux", "x86_64", 23), "linux aarch64": ("linux", "aarch64", 23),
                 "macOS arm64": ("darwin", "arm64", 23), "macOS x86_64": ("darwin", "x86_64", 27),
                 "windows amd64": ("win32", "AMD64", 24)}
        for kind, (plat, machine, want) in kinds.items():
            env = {"sys_platform": plat, "platform_machine": machine, "python_version": "3.12",
                   "os_name": "nt" if plat == "win32" else "posix", "implementation_name": "cpython",
                   "platform_system": {"linux": "Linux", "darwin": "Darwin", "win32": "Windows"}[plat]}
            chosen = [n.lower() for n, _v, m, _h in rows if not m or Marker(m).evaluate(env)]
            self.assertEqual(len(chosen), want, kind)
            self.assertEqual(sorted(set(chosen) & {n for n in chosen if chosen.count(n) > 1}), [],
                             "a package chosen twice on " + kind)
            self.assertEqual(chosen.count("onnxruntime"), 1, kind)
        # and the one kind that needs the older onnxruntime, and what it brings
        intel = {"sys_platform": "darwin", "platform_machine": "x86_64"}
        got = {n: v for n, v, m, _h in rows if not m or Marker(m).evaluate(dict(intel, python_version="3.12"))}
        self.assertEqual(got["onnxruntime"], getstt.ONNXRUNTIME_INTEL_MAC)
        for extra in ("coloredlogs", "humanfriendly", "sympy", "mpmath"):
            self.assertIn(extra, got)

    def test_each_model_is_a_commit_and_five_checked_files(self):
        for key, pin in getstt.MODEL_PINS.items():
            self.assertRegex(pin["revision"], r"^[0-9a-f]{40}$", key + ": a commit, never `main`")
            required = {"config.json", "model.bin", "preprocessor_config.json", "tokenizer.json", "vocabulary.json"}
            self.assertTrue(required.issubset(pin["files"]), key)
            if key in getstt.speechmodels.STANDARD_MODELS:
                self.assertEqual(set(pin['files']), required, 'standard pins remain unchanged')
            for name, (digest, size) in pin["files"].items():
                self.assertRegex(digest, r"^[0-9a-f]{64}$", key + "/" + name)
                self.assertIsInstance(size, int)
                self.assertGreater(size, 0)
            self.assertEqual(getstt.MEASURED[key], sum(s for _h, s in pin["files"].values()))
        self.assertEqual(set(getstt.MODEL_PINS), set(getstt.MODELS))
        self.assertEqual(getstt.MEASURED["large-v3-turbo"], 1621665983)
        self.assertEqual(getstt.MEASURED["large-v3"], 3090835702)
        # the two conversions share no file that differs: nothing is shared between folders
        a, b = (getstt.MODEL_PINS[k]["files"] for k in getstt.speechmodels.STANDARD_MODELS)
        self.assertNotEqual(a["tokenizer.json"], b["tokenizer.json"])

    def test_each_exact_word_times_network_is_public_pinned_and_checked(self):
        self.assertEqual(set(getstt.ALIGNERS), {"zh", "ja", "hi", "ar", "fa", "tr", "es", "de", "fr", "it", "en", "ca"})
        self.assertEqual(set(getstt.ALIGN_PARTS), {"align-" + c for c in getstt.ALIGNERS})
        for code, pin in getstt.ALIGN_PINS.items():
            with self.subTest(code=code):
                self.assertEqual(pin["repo"], "parseh/aligner-" + code)
                self.assertRegex(pin["revision"], r"^[0-9a-f]{40}$")
                self.assertEqual(set(pin["files"]), {"model.int8.onnx", "vocab.json",
                                                       "preprocessor_config.json", "meta.json",
                                                       "LICENSE", "NOTICE"})
                for digest, size in pin["files"].values():
                    self.assertRegex(digest, r"^[0-9a-f]{64}$")
                    self.assertTrue(size is None or size > 0)
                self.assertGreater(getstt.MEASURED["align-" + code], 300_000_000)

    def test_the_costs_are_measured_for_every_kind_of_computer(self):
        kinds = {"linux x86_64", "linux aarch64", "macOS arm64", "macOS x86_64", "windows amd64"}
        self.assertEqual(set(getstt.MEASURED["runtime"]), kinds)
        self.assertEqual(set(getstt.MEASURED["runtime kept"]), kinds)
        for k in kinds:
            self.assertGreater(getstt.MEASURED["runtime kept"][k], getstt.MEASURED["runtime"][k], k)
        self.assertEqual(getstt.MEASURED["runtime"]["linux x86_64"], 127879938)

    def test_the_graphics_card_needs_are_one_table_and_the_words_come_from_it(self):
        self.assertEqual(getstt.GPU_NEEDS, {"driver": True, "cublas": "12", "cudnn": None})
        text = " ".join(w for w, _l in getstt.gpu_needs_text())
        self.assertIn("cuBLAS for CUDA 12", text)
        self.assertIn("libcublas.so.12", text)
        self.assertIn("cublas64_12.dll", text)
        self.assertNotIn("cuDNN", text, "cuDNN is not needed at the pinned CTranslate2")
        self.assertIn("cuDNN is not needed", getstt.gpu_note())
        # a later pin that DOES need it changes one table and the page follows
        with mock.patch.object(getstt, "GPU_NEEDS", {"driver": True, "cublas": "13", "cudnn": "9"}):
            later = " ".join(w for w, _l in getstt.gpu_needs_text())
            self.assertIn("cuBLAS for CUDA 13", later)
            self.assertIn("cuDNN 9 for CUDA 13", later)
            self.assertEqual(getstt.gpu_note(), "")

    def test_whisper_knows_every_parseh_language_and_a_code_it_does_not_is_said(self):
        import languages
        shipped = json.loads((ROOT / "lib" / "languages.json").read_text(encoding="utf-8"))["_shipped"]
        self.assertGreaterEqual(len(shipped), 11)
        for code in shipped:
            self.assertEqual(getstt.whisper_code(code), code, "a Parseh code IS the Whisper code")
        self.assertEqual(len(getstt.WHISPER_LANGUAGES), 100)
        self.assertEqual(getstt.whisper_code(" FA "), "fa")
        for bad in ("jv", "zz", "", None, "persian", "fa-IR"):
            with self.assertRaises(getstt.SpeechError) as caught:
                getstt.whisper_code(bad)
            self.assertEqual(caught.exception.code, "unsupported-language")
            self.assertIn("Whisper does not list", caught.exception.say)
        table = getstt.speech_languages()
        self.assertEqual(set(table), set(languages.LANGS))
        self.assertTrue(all(table[c] for c in shipped))

    @unittest.skipUnless(os.environ.get("PARSEH_STT_REAL"), "opt-in: needs a really installed program")
    def test_the_language_list_is_the_installed_programs_own(self):
        # PARSEH_STT_REAL=<a real stt/ folder>: asks the program itself, in a child
        folder = os.path.join(os.environ["PARSEH_STT_REAL"], "runtime", "%d-%s" % (
            getstt.PIN["generation"], getstt.PYTAG))
        out = subprocess.run([PY, "-B", "-c",
                              "import json, faster_whisper.tokenizer as t; print(json.dumps(sorted(t._LANGUAGE_CODES)))"],
                             env=dict(os.environ, PYTHONPATH=folder, PYTHONNOUSERSITE="1"),
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(set(json.loads(out.stdout)), set(getstt.WHISPER_LANGUAGES))


# ------------------------------------------------- normal Parseh needs none of it
class NormalParseh(unittest.TestCase):
    NAMES = re.compile(r"whisper|ctranslate2|onnxruntime|faster[-_]", re.I)

    def test_no_installer_and_no_list_of_packages_names_it(self):
        # tests 1-3 at the root: the installers, the environment and the launchers
        for name in ("environment.yml", "install.sh", "install.bat", "Parseh.command", "serve.sh",
                     "serve.bat", "build.sh", "lib/env.sh", "lib/launcher.py", "lib/runtime.py"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIsNone(self.NAMES.search(text), "%s names speech to text" % name)
        import runtime
        self.assertEqual([r for r in runtime.PACKAGES if self.NAMES.search(" ".join(r))], [])
        self.assertEqual([r for r in runtime.ENV_TOOLS if self.NAMES.search(" ".join(r))], [])
        yml = (ROOT / "environment.yml").read_text(encoding="utf-8")
        self.assertIn("python=3.12", yml, "a changed Python would make every update refuse")

    BANNED = {"faster_whisper", "ctranslate2", "av", "onnxruntime"}

    def imports_of_the_program(self, source):
        """The lines of a module's source that import the program, at any depth: an `import`
        inside a function counts, and so does importlib.import_module / __import__ of one of
        the four names as a string.  (A name that is a variable is not judged: the server has a
        few such, for its own modules.)"""
        found = []
        for node in ast.walk(ast.parse(source)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module.split(".")[0]]
            elif isinstance(node, ast.Call):
                f = node.func
                called = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                first = node.args[0] if node.args else None
                if called in ("import_module", "__import__") and isinstance(first, ast.Constant) \
                        and isinstance(first.value, str):
                    mods = [first.value.split(".")[0]]
            if set(mods) & self.BANNED:
                found.append(node.lineno)
        return found

    def test_the_guard_sees_a_lazy_and_a_dynamic_import_too(self):
        # a guard that is only a list of six files, read for top-of-file imports, passes these
        for source in ("import faster_whisper", "def f():\n    import ctranslate2\n",
                       "def f():\n    from av import open\n", "class A:\n    def f(self):\n        import onnxruntime as o\n",
                       "import importlib\nimportlib.import_module('ctranslate2')",
                       "from importlib import import_module\nimport_module('faster_whisper.transcribe')",
                       "__import__('onnxruntime')"):
            self.assertTrue(self.imports_of_the_program(source), source)
        for source in ("import json", "def f(name):\n    return __import__(name)",
                       "import importlib\nimportlib.import_module('languages')", "avoid = 'av'"):
            self.assertEqual(self.imports_of_the_program(source), [], source)

    def test_nothing_the_server_imports_imports_the_program(self):
        # AN IMPORT OF faster_whisper, ctranslate2, av OR onnxruntime WOULD PUT A SECOND
        # numpy IN THE SERVER: only the two children (the probe and the worker) may.  Every
        # module the server can load is read, and not a list of the few it is known to load
        children = {ROOT / "lib" / "sttworker.py", ROOT / "lib" / "sttprobe.py",
                    ROOT / "lib" / "ctcalign.py"}
        files = [ROOT / "serve.py"] + [p for d in ("lib", "youtube/lib", "markdown", "html-guide/engine")
                                       for p in sorted((ROOT / d).rglob("*.py"))]
        self.assertGreater(len(files), 100, "the scan found the server's modules")
        for path in files:
            if path in children:
                continue
            self.assertEqual(self.imports_of_the_program(path.read_text(encoding="utf-8")), [],
                             "%s imports the program" % path.relative_to(ROOT))
        for path in children:
            self.assertTrue(self.imports_of_the_program(path.read_text(encoding="utf-8")),
                            "%s is where the program is imported, and the scan sees it" % path.name)

    def test_the_server_imports_and_serves_with_the_program_absent(self):
        # a child whose import of the four names FAILS, importing everything the server does
        code = ("import sys\n"
                "for n in ('faster_whisper', 'ctranslate2', 'av', 'onnxruntime'):\n"
                "    sys.modules[n] = None\n"
                "sys.path[:0] = %r\n"
                "import serve, getstt, speechpage, lookuppage, notices, settingspage\n"
                "import json\n"
                "print(json.dumps({'kinds': list(serve.READING_KINDS), 'state': getstt.runtime()['state'],\n"
                "                  'slim': sorted(getstt.summary()), 'page': len(speechpage.page({}, 'self', 'x')),\n"
                "                  'door': [d[0] for d in settingspage.DOORS if 'speech' in d[0]],\n"
                "                  'loaded': [n for n in ('faster_whisper', 'ctranslate2', 'av', 'onnxruntime')\n"
                "                             if sys.modules.get(n) is not None]}))\n"
                % ([str(ROOT / p) for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", ".")],))
        with tempfile.TemporaryDirectory() as td:
            out = subprocess.run([PY, "-c", code], cwd=td, capture_output=True, text=True, timeout=180,
                                 env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        got = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertIn("speech", got["kinds"])
        self.assertEqual(got["loaded"], [])
        self.assertEqual(got["door"], ["/settings/speech/"])
        self.assertGreater(got["page"], 5000)
        self.assertIn("installed", got["slim"])

    def test_no_cuda_and_no_card_is_the_ordinary_case(self):
        # test 3: a computer with no NVIDIA card gets the CPU, Automatic says so, and the
        # card's option says why not -- and nothing is broken or refused for it
        nothing = {"python": "3.12", "ct2": None, "cublas": {"loads": False, "name": "libcublas.so.12"},
                   "smi": None}
        with mock.patch.object(getstt, "_run_probe", return_value=nothing):
            getstt.forget_hardware()
            hw = getstt.hardware(refresh=True)
            self.assertEqual(hw["cuda"]["state"], "none")
            self.assertFalse(hw["cuda"]["ready"])
            self.assertEqual(hw["auto"], "cpu")
            self.assertTrue(hw["cpu"]["available"])
            self.assertEqual(getstt.resolve("auto")[0], "cpu")
            self.assertEqual(getstt.resolve("cpu")[0], "cpu")
            with self.assertRaises(getstt.SpeechError) as caught:
                getstt.resolve("cuda")
            self.assertEqual(caught.exception.code, "gpu-unavailable")
            modes = {m["id"]: m for m in getstt.processing(hw)}
            self.assertTrue(modes["auto"]["ready"] and modes["cpu"]["ready"])
            self.assertEqual(modes["auto"]["now"], "cpu")
            self.assertFalse(modes["cuda"]["ready"])
            self.assertIn("CPU transcription works", modes["cuda"]["why"])
        getstt.forget_hardware()


# ------------------------------------------ only two models, only three modes
class Security(Tree):
    MODEL_TABLE = ["", " ", "large-v3/", "/large-v3", "../large-v3", "large-v3/../../x", "large-v3/../..",
                   "..", ".", "large-v3\x00", "large-v3\n", "large-v3 ", " large-v3", "LARGE-V3", "Large-V3-Turbo",
                   "large_v3", "large-v3.bin", "large-v3-turbo/model.bin", "large-v3;rm -rf /",
                   "large-v3&&id", "$(id)", "`id`", "/etc/passwd", "C:\\Windows\\System32", "\\\\host\\share",
                   "small", "medium", "distil-large-v3", "whisper.cpp", "openai/whisper-large-v3",
                   "Systran/faster-whisper-large-v3", "https://example.com/model", "file:///etc/passwd",
                   "large-v3\u202e", "l\u0430rge-v3", "runtime", "models", "tmp", None, 3, 3.5, True, b"large-v3",
                   ["large-v3"], ("large-v3",), {"large-v3": 1}, object()]
    MODE_TABLE = ["", " ", "gpu", "GPU", "CUDA", "Cuda", "cuda:0", "cuda:1", "cuda ", "auto ", "AUTO", "cpu ",
                  "cpu;id", "mps", "rocm", "hip", "directml", "opencl", "metal", "float16", "int8", "int8_float16",
                  "auto/../cpu", "cuda\x00", None, 0, 1, True, b"cpu", ["cpu"], {"cpu": 1}]

    @contextlib.contextmanager
    def watch_everything(self):
        """Every way to reach a disk, a child or the network patched so that a call that gets that
        far fails -- for the length of the `with`, and no longer (the tree is torn down after it)."""
        boom = AssertionError("a refused name reached the disk, a child or the network")

        def refuse(*a, **k):
            raise boom
        with contextlib.ExitStack() as stack:
            for target, name in ((os, "makedirs"), (os, "listdir"), (os, "replace"), (os, "unlink"),
                                 (os, "rmdir"), (os, "walk"), (os.path, "isdir"), (os.path, "isfile"),
                                 (os.path, "exists"), (shutil, "rmtree"), (subprocess, "Popen"),
                                 (subprocess, "run"), (getstt.download, "fetch"),
                                 (getstt, "_run_probe")):
                stack.enter_context(mock.patch.object(target, name, refuse))
            yield

    def test_only_the_catalogue_identifiers_are_accepted(self):
        for ok in getstt.MODELS:
            self.assertTrue(getstt.model_dir(ok).endswith(os.path.join("models", ok)))
            self.assertEqual(getstt.check_model(ok), ok)
        self.assertEqual(getstt.MODELS, getstt.speechmodels.MODELS)
        self.assertEqual(getstt.MODELS[:2], ('large-v3-turbo', 'large-v3'))
        self.assertEqual(getstt.ALLOWED_MODELS, frozenset(getstt.MODELS))
        self.assertEqual(getstt.DEFAULT_MODEL, "large-v3-turbo")
        self.assertEqual(getstt.MODES, ("auto", "cpu", "cuda"))

    def test_a_table_of_malicious_models_is_refused_before_anything_is_touched(self):
        with self.watch_everything():
            for bad in self.MODEL_TABLE:
                label = repr(bad)
                with self.assertRaises(ValueError, msg="model_dir(%s)" % label):
                    getstt.model_dir(bad)
                with self.assertRaises(getstt.SpeechError, msg="check_model(%s)" % label) as caught:
                    getstt.check_model(bad)
                self.assertEqual(caught.exception.code, "bad-model")
                self.assertFalse(getstt.model_ready(bad), label)
                if bad != "runtime":
                    for call in (getstt.plan, getstt.build):
                        with self.assertRaises(ValueError, msg="%s(%s)" % (call.__name__, label)):
                            call(bad)
                    with self.assertRaises((getstt.SpeechError, ValueError), msg="remove(%s)" % label):
                        getstt.remove(bad)
                    with self.assertRaises((getstt.SpeechError, ValueError), msg="discard(%s)" % label):
                        getstt.discard(bad)

    def test_a_table_of_malicious_modes_and_devices_is_refused_before_a_look_at_the_card(self):
        for ok in getstt.MODES:
            self.assertEqual(getstt.check_mode(ok), ok)
        with self.watch_everything():    # the probe among them: a refused mode never gets that far
            for bad in self.MODE_TABLE:
                with self.assertRaises(getstt.SpeechError, msg=repr(bad)) as caught:
                    getstt.check_mode(bad)
                self.assertEqual(caught.exception.code, "bad-processing")
                with self.assertRaises(getstt.SpeechError, msg="resolve(%r)" % (bad,)):
                    getstt.resolve(bad)

    def test_only_two_devices_and_two_compute_types_can_reach_the_program(self):
        # the device resolve() returns, and the compute types Lane C's worker is given,
        # are constants of this module: nothing a client sent is ever one of them
        ready = {"state": "ready", "ready": True, "name": "NVIDIA Test", "detected": True}
        self.assertEqual(getstt.COMPUTE, {"cpu": "int8", "cuda": ("int8_float16", "float16")})
        for mode in getstt.MODES:
            with mock.patch.object(getstt, "hardware",
                                   return_value={"cuda": ready, "cpu": {}, "auto": "cuda"}):
                device, said = getstt.resolve(mode)
            self.assertIn(device, ("cpu", "cuda"))
            self.assertIsInstance(said, str)

    def test_the_worker_environment_holds_the_program_and_nothing_a_client_chose(self):
        self.make_runtime()
        env = getstt.worker_env()
        self.assertEqual(env["PYTHONPATH"], str(self.stt / "runtime" / ("%d-%s" % (
            getstt.PIN["generation"], getstt.PYTAG))))
        for key, want in (("HF_HUB_OFFLINE", "1"), ("TRANSFORMERS_OFFLINE", "1"),
                          ("ORT_DISABLE_TELEMETRY", "1"),
                          ("PYTHONNOUSERSITE", "1"), ("PYTHONDONTWRITEBYTECODE", "1"),
                          ("PYTHONSAFEPATH", "1")):
            self.assertEqual(env[key], want, key)
        self.assertTrue(env["HF_HOME"].startswith(str(self.stt)), "a stray cache stays inside stt/")
        self.assertEqual(sorted(k for k in env if k in ("LD_LIBRARY_PATH", "PATH")), [])
        # where the last look found cuBLAS off the loader's path, the worker is told the same place
        getstt._HW.update(data={"cublas_dir": "/opt/cuda-12.4/lib64", "ready": True}, at=time.time())
        var = "PATH" if os.name == "nt" else "LD_LIBRARY_PATH"
        self.assertEqual(getstt.worker_env()[var].split(os.pathsep)[0], "/opt/cuda-12.4/lib64")

    def test_there_is_no_worker_environment_without_the_program(self):
        with self.assertRaises(getstt.SpeechError) as caught:
            getstt.worker_env()
        self.assertEqual(caught.exception.code, "not-installed")
        self.assertFalse(self.stt.exists(), "asking made nothing")


# ------------------------------------------------- what is installed, from the disk
class StatusFromTheDisk(Tree):
    def test_nothing_installed_is_absent_and_a_status_makes_no_folder(self):
        st = getstt.status()
        self.assertEqual(st["runtime"]["state"], "absent")
        self.assertFalse(st["runtime"]["have"])
        self.assertEqual({k: m["state"] for k, m in st["models"].items()},
                         {key: 'absent' if key in getstt.MODEL_PINS else 'unavailable'
                          for key in getstt.MODELS})
        s = getstt.summary()
        self.assertFalse(s["installed"])
        self.assertIsNone(s["default_model"])
        self.assertEqual(getstt.installed(), [])
        self.assertIsNone(getstt.runtime_dir())
        self.assertFalse(self.stt.exists(), "status and summary made no stt/")
        getstt.sweep()
        self.assertFalse(self.stt.exists(), "and neither did a sweep")

    def test_the_program_ready(self):
        self.make_runtime()
        rt = getstt.runtime()
        self.assertEqual((rt["state"], rt["ready"], rt["have"]), ("ready", True, True))
        self.assertEqual(rt["generation"], getstt.PIN["generation"])
        self.assertEqual(rt["python"], getstt.PYTAG)
        self.assertEqual(rt["version"], getstt.PIN["faster-whisper"])
        self.assertEqual(rt["ctranslate2"], getstt.PIN["ctranslate2"])
        self.assertEqual(getstt.runtime_dir(), str(self.stt / "runtime" / ("%d-%s" % (
            getstt.PIN["generation"], getstt.PYTAG))))
        self.assertTrue(getstt.runtime_ready())

    def test_every_other_state_of_the_program_says_what_it_is_and_why(self):
        # an older Parseh made it: a lower generation
        self.make_runtime(generation=getstt.PIN["generation"] - 1)
        rt = getstt.runtime()
        self.assertEqual((rt["state"], rt["ready"], rt["have"]), ("older", False, True))
        self.assertIn("older Parseh", rt["why"])
        self.assertIsNone(getstt.runtime_dir(), "a program this Parseh did not make is not run")
        shutil.rmtree(self.stt)
        # a newer one
        self.make_runtime(generation=getstt.PIN["generation"] + 1)
        rt = getstt.runtime()
        self.assertEqual((rt["state"], rt["ready"]), ("newer", False))
        self.assertIn("newer Parseh", rt["why"])
        shutil.rmtree(self.stt)
        # for another Python
        other = "cp311" if getstt.PYTAG != "cp311" else "cp310"
        self.make_runtime(tag=other)
        rt = getstt.runtime()
        self.assertEqual((rt["state"], rt["ready"], rt["python"]), ("other_python", False, other))
        self.assertIn("installed for Python", rt["why"])
        shutil.rmtree(self.stt)
        # its own folder, with the pinned files gone
        self.make_runtime(dists=[("faster_whisper", getstt.PIN["faster-whisper"])])
        rt = getstt.runtime()
        self.assertEqual((rt["state"], rt["ready"]), ("broken", False))
        self.assertIn("incomplete", rt["why"])
        shutil.rmtree(self.stt)
        # a version that is not the pin
        self.make_runtime(dists=[(d, "0.0.1" if v else "1.0") for d, v in getstt.REQUIRED])
        self.assertEqual(getstt.runtime()["state"], "broken")
        shutil.rmtree(self.stt)
        # and a computer that cannot run it at all
        folder = self.make_runtime()
        (folder / "libctranslate2.so").write_bytes(b"x" * 5000)
        getstt._SIZES.clear()
        with mock.patch.object(getstt, "cannot_run", return_value="This Parseh runs on Python 3.11."):
            rt = getstt.runtime()
            self.assertEqual((rt["state"], rt["ready"], rt["can_install"]), ("unavailable", False, False))
            self.assertEqual(rt["why"], "This Parseh runs on Python 3.11.")
            # what is here still takes room, and the page says how much taking it away gives back
            self.assertEqual((rt["have"], rt["size"]), (True, 5000))
        with mock.patch.object(getstt, "cannot_run", return_value=""), \
                mock.patch.object(getstt, "has_pip", return_value=False):
            self.assertIn("no pip", getstt.runtime()["why"] or getstt.unavailable_reason())
            for said in ("install.bat", "Parseh.command", "install.sh", "then start Parseh again"):
                self.assertIn(said, getstt.unavailable_reason())
            self.assertTrue(getstt.runtime()["ready"], "no pip stops an INSTALL, not a program that is here")
            self.assertFalse(getstt.runtime()["can_install"])

    def test_the_reasons_a_computer_cannot_have_it(self):
        with mock.patch.object(sys, "version_info", (3, 11, 4, "final", 0)):
            self.assertIn("Python 3.11", getstt.cannot_run())
            self.assertIn("Python 3.12", getstt.cannot_run())
            # a person without a terminal is told what to do, and by which file of Parseh's own
            for said in ("install.bat", "Parseh.command", "install.sh", "then start Parseh again"):
                self.assertIn(said, getstt.cannot_run())
        with mock.patch.object(getstt, "platform_key", return_value=None):
            self.assertIn("no speech program for this kind of computer", getstt.cannot_run())
        with mock.patch.object(getstt, "platform_key", return_value="macOS arm64"), \
                mock.patch.object(getstt, "_mac_major", return_value=13):
            self.assertIn("macOS 14", getstt.cannot_run())
        with mock.patch.object(getstt, "platform_key", return_value="macOS x86_64"), \
                mock.patch.object(getstt, "_mac_major", return_value=13):
            self.assertEqual(getstt.cannot_run(), "")
        with mock.patch.object(getstt, "platform_key", return_value="linux x86_64"), \
                mock.patch.object(getstt, "_glibc", return_value=("glibc", "2.17")):
            self.assertIn("glibc 2.28", getstt.cannot_run())
        with mock.patch.object(getstt, "platform_key", return_value="linux x86_64"), \
                mock.patch.object(getstt, "_glibc", return_value=("", "")):
            self.assertIn("GNU C library", getstt.cannot_run())

    def test_windows_says_when_the_folder_is_too_deep_for_the_longest_file_name(self):
        deep = str(self.tmp / ("d" * 150) / "stt")
        with mock.patch.object(getstt.os, "name", "nt"), mock.patch.object(getstt, "STT_DIR", deep), \
                mock.patch.object(getstt, "_long_paths_on", return_value=False):
            why = getstt._too_deep()
            self.assertIn("too deep for Windows", why)
            self.assertIn(str(getstt.LONGEST_TREE_PATH), why)
            self.assertIn("turn on long paths in Windows (the guide's page on speech to text shows how)", why)
        with mock.patch.object(getstt.os, "name", "nt"), mock.patch.object(getstt, "STT_DIR", deep), \
                mock.patch.object(getstt, "_long_paths_on", return_value=True):
            self.assertEqual(getstt._too_deep(), "", "long paths turned on: no such limit")
        with mock.patch.object(getstt.os, "name", "nt"), \
                mock.patch.object(getstt, "STT_DIR", "C:\\Parseh\\stt"), \
                mock.patch.object(getstt.os.path, "abspath", lambda p: p):
            self.assertEqual(getstt._too_deep(), "", "a folder near the top has room")
        self.assertEqual(getstt._too_deep(), "", "and it is a Windows question only")

    def test_a_model_ready_older_newer_broken_and_absent(self):
        pins, made = self.tiny_pins()
        self.make_runtime()
        self.make_model("large-v3", made)
        m = getstt.model_info("large-v3")
        self.assertEqual((m["state"], m["ready"], m["have"]), ("ready", True, True))
        self.assertEqual(m["size"], sum(len(b) for b in made["large-v3"].values()))
        self.assertTrue(getstt.model_ready("large-v3"))
        self.assertFalse(getstt.model_ready("large-v3-turbo"))
        self.assertEqual(getstt.installed(), ["large-v3"])
        # fetched at another revision, by an older Parseh
        shutil.rmtree(self.stt / "models")
        self.make_model("large-v3", made, revision="c" * 40)
        m = getstt.model_info("large-v3")
        self.assertEqual((m["state"], m["ready"]), ("older", False))
        self.assertIn("older Parseh", m["why"])
        # ...or by a newer one (its generation is above this Parseh's)
        meta = self.stt / "models" / "large-v3" / "meta.json"
        meta.write_text(json.dumps({"revision": "c" * 40, "pin": getstt.PIN["generation"] + 3}))
        self.assertEqual(getstt.model_info("large-v3")["state"], "newer")
        # a file cut short
        shutil.rmtree(self.stt / "models")
        self.make_model("large-v3", made, break_it=True)
        m = getstt.model_info("large-v3")
        self.assertEqual((m["state"], m["ready"]), ("broken", False))
        self.assertIn("model.bin", m["why"])
        # no meta.json at all
        (self.stt / "models" / "large-v3" / "meta.json").unlink()
        self.assertEqual(getstt.model_info("large-v3")["state"], "broken")
        self.assertEqual(getstt.model_info("large-v3-turbo")["state"], "absent")

    def test_a_model_is_usable_only_with_the_program_and_the_slim_slice_says_so(self):
        pins, made = self.tiny_pins()
        self.make_model("large-v3-turbo", made)
        with mock.patch.object(getstt, "_run_probe", return_value={"ct2": None, "cublas": {}, "smi": None}):
            s = getstt.summary()
        self.assertFalse(s["installed"], "a model with no program is not speech to text")
        by = {m["id"]: m for m in s["models"]}
        self.assertTrue(by["large-v3-turbo"]["have"])
        self.assertFalse(by["large-v3-turbo"]["ready"])
        self.assertIsNone(s["default_model"])
        self.make_runtime()
        with mock.patch.object(getstt, "_run_probe", return_value={"ct2": "4.8.2", "cublas": {}, "smi": None}):
            s = getstt.summary()
        self.assertTrue(s["installed"])
        self.assertEqual(s["default_model"], "large-v3-turbo")
        self.assertEqual(s["settings"], "/settings/speech/")
        self.assertTrue(s["ok"])
        self.assertEqual(s["runtime"]["state"], "ready")
        self.assertEqual([m["id"] for m in s["models"]], list(getstt.MODELS))
        self.assertEqual(s["models"][0]["tag"], "Recommended · faster and lighter")
        self.assertEqual(s["models"][1]["tag"], "Higher accuracy · larger and slower")
        self.assertEqual(s["models"][0]["label"], "faster-whisper / large-v3-turbo")
        self.assertEqual(s["models"][1]["label"], "faster-whisper / large-v3")
        # the larger is the default only when the turbo one is not there
        shutil.rmtree(self.stt / "models")
        self.make_model("large-v3", made)
        with mock.patch.object(getstt, "_run_probe", return_value={"ct2": "4.8.2", "cublas": {}, "smi": None}):
            self.assertEqual(getstt.summary()["default_model"], "large-v3")
        self.assertEqual(set(s["languages"]), set(getstt.speech_languages()))

    def test_the_plan_of_a_model_counts_the_program_until_it_is_there(self):
        pins, made = self.tiny_pins()
        rt_dl, rt_kept = getstt._runtime_plan()
        model = getstt.MEASURED["large-v3"]
        p = getstt.plan("large-v3")
        self.assertEqual((p["download"], p["kept"], p["measured"]), (rt_dl + model, model + rt_kept, True))
        self.assertGreaterEqual(p["disk_peak"], rt_dl + rt_kept, "the program's own peak: wheels and what they unpack to")
        self.make_runtime()
        p = getstt.plan("large-v3")
        self.assertEqual((p["download"], p["kept"], p["disk_peak"]), (model, model, model))
        pr = getstt.plan("runtime")
        self.assertEqual((pr["download"], pr["kept"], pr["have"]), (rt_dl, rt_kept, 0),
                         "pip cannot resume a wheel: nothing of the program is ever 'had'")
        # a stopped model download is counted, and only once
        part = self.stt / "models" / "large-v3.part"
        part.mkdir(parents=True)
        (part / "model.bin.part").write_bytes(b"x" * 7)
        (part / "model.bin.part.json").write_text("{}")
        self.assertEqual(getstt.plan("large-v3")["have"], 7)
        with self.assertRaises(ValueError):
            getstt.plan("large-v2")

    def test_the_status_is_cheap_and_never_loads_or_runs_anything(self):
        with mock.patch.object(getstt, "_run_probe", side_effect=AssertionError("a status ran the probe")):
            st = getstt.status()
        self.assertEqual(st["hardware"]["cuda"]["state"], "unchecked")
        self.assertFalse(st["hardware"]["checked"])
        self.assertTrue(st["hardware"]["cpu"]["available"])
        self.assertEqual(st["pin"]["gpu"], getstt.GPU_NEEDS)
        self.assertEqual(st["dir"], "stt/")
        self.assertEqual(st["modes"], ["auto", "cpu", "cuda"])
        self.assertEqual([r["what"] for r in st["requirements"]][1][:6], "cuBLAS")
        self.assertIn("cuDNN is not needed", st["requirements_note"])
        json.dumps(st)


# -------------------------------------------------------- the graphics card
def probe_answer(**over):
    base = {"python": "3.12", "platform": "linux", "ct2": "4.8.2", "cuda_devices": 1,
            "cuda_types": ["float16", "float32", "int8", "int8_float16", "int8_float32"],
            "cpu_types": ["float32", "int16", "int8", "int8_float32"],
            "cublas": {"loads": True, "name": "libcublas.so.12", "dir": None},
            "smi": {"name": "NVIDIA GeForce GTX 1650", "memory": 4294967296, "driver": "595.91.07",
                    "compute_cap": "7.5"}, "seconds": 0.2}
    base.update(over)
    return base


class TheGraphicsCard(Tree):
    def look(self, answer, kind="linux x86_64"):
        with mock.patch.object(getstt, "platform_key", return_value=kind), \
                mock.patch.object(getstt, "_run_probe", return_value=answer) as probe:
            getstt.forget_hardware()
            hw = getstt.hardware(refresh=True)
        return hw, probe

    def test_none_no_card_at_all(self):
        hw, _ = self.look(probe_answer(ct2="4.8.2", cuda_devices=0, cuda_types=[], smi=None,
                                       cublas={"loads": False, "name": "libcublas.so.12"}))
        c = hw["cuda"]
        self.assertEqual((c["state"], c["detected"], c["ready"]), ("none", False, False))
        self.assertIn("No NVIDIA graphics card", c["why"])
        self.assertEqual(hw["auto"], "cpu")
        with mock.patch.object(getstt, "platform_key", return_value="linux x86_64"):
            self.assertEqual(getstt.resolve("auto"), ("cpu", "Automatic: on the CPU."))

    def test_found_not_ready_names_the_piece_that_is_missing(self):
        # the real state of the owner's machine: a GTX 1650, a driver, no cuBLAS
        hw, _ = self.look(probe_answer(cublas={"loads": False, "name": "libcublas.so.12",
                                               "error": "cannot open shared object file"}))
        c = hw["cuda"]
        self.assertEqual((c["state"], c["detected"], c["ready"]), ("found-not-ready", True, False))
        self.assertEqual(c["name"], "NVIDIA GeForce GTX 1650")
        self.assertEqual(c["memory"], 4294967296)
        self.assertEqual(len(c["missing"]), 1)
        self.assertIn("cuBLAS for CUDA 12", c["missing"][0])
        self.assertIn("libcublas.so.12 was not found", c["missing"][0])
        self.assertEqual(hw["auto"], "cpu", "Automatic never picks a card that is not proved")
        # a counted device, a listed type -- and still not ready: that was the trap
        self.assertEqual(hw["cuda"]["ready"], False)
        # and the rule is the one a JOB is planned by (sttjobs asks resolve, not the record): a
        # resolve that went by "detected" would start it on the owner's card, unproved
        with mock.patch.object(getstt, "platform_key", return_value="linux x86_64"):
            self.assertEqual(getstt.resolve("auto"), ("cpu", "Automatic: on the CPU."),
                             "Automatic never picks a card that is found but not proved")

    def test_found_not_ready_for_every_other_reason_too(self):
        hw, _ = self.look(probe_answer(ct2=None, cuda_devices=None, cuda_types=None,
                                       cublas={"loads": True, "name": "x"}))
        self.assertEqual(hw["cuda"]["state"], "found-not-ready")
        self.assertIn("the speech program itself", hw["cuda"]["missing"][0])
        hw, _ = self.look(probe_answer(cuda_devices=0, cuda_types=[]))
        self.assertIn("CUDA support", hw["cuda"]["missing"][0])
        hw, _ = self.look(probe_answer(cuda_types=["float32", "int8_float32"]))
        self.assertIn("half-precision", hw["cuda"]["missing"][0])
        self.assertIn("int8_float32", hw["cuda"]["missing"][0])
        hw, _ = self.look(probe_answer(cuda_types=["float32"], cublas={"loads": False, "name": "libcublas.so.12"}))
        self.assertEqual(len(hw["cuda"]["missing"]), 2, "both things that are missing are said")

    def test_a_program_that_is_installed_and_will_not_load_is_not_sent_to_be_got_above(self):
        # on Windows a library the program needs and the computer lacks is an OSError when it
        # is imported: the probe keeps the words, and the page must not say "get it above"
        # about a program its own row says is installed
        answer = probe_answer(ct2=None, ct2_error="OSError: [WinError 126] The specified module "
                              "could not be found: ctranslate2.dll", cuda_devices=None,
                              cuda_types=None)
        self.make_runtime()
        hw, _ = self.look(answer)
        missing = hw["cuda"]["missing"][0]
        self.assertIn("installed but does not start on this computer", missing)
        self.assertNotIn("get it above", missing)
        self.assertEqual(hw["cuda"]["state"], "found-not-ready")
        # where the program is not there, "get it above" is the truth
        shutil.rmtree(self.stt / "runtime")
        hw, _ = self.look(answer)
        self.assertIn("get it above", hw["cuda"]["missing"][0])

    def test_ready_only_when_everything_is_proved_and_the_compute_type_is_chosen(self):
        hw, _ = self.look(probe_answer())
        c = hw["cuda"]
        self.assertEqual((c["state"], c["ready"], c["detected"]), ("ready", True, True))
        self.assertEqual(c["compute"], "int8_float16", "chosen for the person, never asked")
        self.assertEqual(hw["auto"], "cuda")
        hw, _ = self.look(probe_answer(cuda_types=["float16", "float32"]))
        self.assertEqual(hw["cuda"]["compute"], "float16")
        hw, _ = self.look(probe_answer(cublas={"loads": True, "name": "libcublas.so.12",
                                               "dir": "/opt/cuda-12.4/lib64"}))
        self.assertEqual(hw["cuda"]["cublas_dir"], "/opt/cuda-12.4/lib64")

    def test_the_states_reach_the_status_and_the_slim_slice(self):
        for answer, state, now, why_has in (
                (probe_answer(cuda_devices=0, cuda_types=[], smi=None,
                              cublas={"loads": False}), "none", "cpu", "No NVIDIA"),
                (probe_answer(cublas={"loads": False, "name": "libcublas.so.12"}), "found-not-ready", "cpu",
                 "cuBLAS for CUDA 12"),
                (probe_answer(), "ready", "cuda", "")):
            hw, _ = self.look(answer)
            st = getstt.status()
            self.assertEqual(st["hardware"]["cuda"]["state"], state)
            self.assertTrue(st["hardware"]["checked"])
            self.assertEqual(st["hardware"]["auto"], now)
            with mock.patch.object(getstt, "platform_key", return_value="linux x86_64"):
                modes = {m["id"]: m for m in getstt.summary()["processing"]}
            self.assertEqual(modes["auto"]["now"], now)
            self.assertTrue(modes["cpu"]["ready"], "the CPU is always a choice, whatever the card is")
            self.assertEqual(modes["cuda"]["ready"], state == "ready")
            self.assertIn(why_has, modes["cuda"]["why"])
            if state == "ready":
                self.assertEqual(modes["cuda"]["name"], "NVIDIA GeForce GTX 1650")
                self.assertEqual(modes["cuda"]["memory"], 4294967296)

    def test_explicit_gpu_says_why_when_it_is_not_ready(self):
        self.look(probe_answer(cublas={"loads": False, "name": "libcublas.so.12"}))
        with mock.patch.object(getstt, "platform_key", return_value="linux x86_64"):
            self.assertEqual(getstt.resolve("auto")[0], "cpu", "found, not ready: not the card")
        with mock.patch.object(getstt, "platform_key", return_value="linux x86_64"), \
                self.assertRaises(getstt.SpeechError) as caught:
            getstt.resolve("cuda")
        self.assertEqual(caught.exception.code, "gpu-unavailable")
        self.assertIn("cuBLAS for CUDA 12", caught.exception.say)
        self.assertIn("CPU transcription still works", caught.exception.say)
        self.look(probe_answer())
        with mock.patch.object(getstt, "platform_key", return_value="linux x86_64"):
            self.assertEqual(getstt.resolve("cuda")[0], "cuda")
            self.assertEqual(getstt.resolve("auto")[0], "cuda")
            self.assertEqual(getstt.resolve("cpu")[0], "cpu")

    def test_a_computer_whose_program_has_no_card_support_is_never_probed(self):
        for kind in ("macOS arm64", "macOS x86_64", "linux aarch64"):
            hw, probe = self.look(probe_answer(), kind=kind)
            probe.assert_not_called()
            self.assertEqual(hw["cuda"]["state"], "none", kind)
            self.assertFalse(hw["cuda"]["supported_build"], kind)
            self.assertIn("no graphics-card support", hw["cuda"]["why"])
            with mock.patch.object(getstt, "platform_key", return_value=kind), \
                    mock.patch.object(getstt, "_run_probe", side_effect=AssertionError("probed")):
                self.assertEqual(getstt.resolve("auto")[0], "cpu")
                self.assertEqual(getstt.cached_hardware()["cuda"]["state"], "none")

    def test_a_look_is_kept_a_while_and_taken_again_when_asked_or_old(self):
        with mock.patch.object(getstt, "platform_key", return_value="linux x86_64"), \
                mock.patch.object(getstt, "_run_probe", return_value=probe_answer()) as probe:
            getstt.forget_hardware()
            getstt.hardware()
            getstt.hardware()
            self.assertEqual(probe.call_count, 1, "kept")
            getstt.hardware(refresh=True)
            self.assertEqual(probe.call_count, 2, "check again")
            getstt._HW["at"] -= getstt.HARDWARE_TTL + 5
            getstt.hardware()
            self.assertEqual(probe.call_count, 3, "old")
            getstt.cached_hardware()
            self.assertEqual(probe.call_count, 3, "cached_hardware never looks")

    def test_a_probe_that_fails_is_a_card_that_is_not_proved(self):
        hw, _ = self.look({"error": "looking at the graphics card took more than 30 seconds"})
        self.assertEqual((hw["cuda"]["state"], hw["cuda"]["ready"]), ("none", False))
        self.assertIn("30 seconds", hw["cuda"]["why"])
        self.assertEqual(hw["auto"], "cpu")

    def test_the_cpu_is_always_there_and_its_threads_are_bounded(self):
        with mock.patch.object(getstt, "cannot_run", return_value=""):    # (whatever Python runs this)
            cpu = getstt.cached_hardware()["cpu"]
        self.assertTrue(cpu["available"])
        self.assertEqual(cpu["compute"], "int8")
        self.assertIn("Speech to text will work here", cpu["said"])
        for phys, logical, want in ((1, 2, 1), (4, 8, 4), (8, 16, 8), (16, 24, 8), (64, 128, 8), (None, 24, 8),
                                    (None, 2, 1), (None, 1, 1), (12, 8, 8)):
            with mock.patch.object(getstt, "physical_cores", return_value=phys), \
                    mock.patch.object(getstt, "_logical_cores", return_value=logical):
                self.assertEqual(getstt.cpu_threads(), want, (phys, logical))
        self.assertGreaterEqual(getstt.cpu_threads(), 1)
        self.assertLessEqual(getstt.cpu_threads(), 8)

    def test_the_cpu_promises_nothing_where_the_program_cannot_run(self):
        with mock.patch.object(getstt, "cannot_run", return_value=""):
            cpu = getstt._cpu()
        self.assertTrue(cpu["available"])
        self.assertIn("Speech to text will work here", cpu["said"])
        # the page draws the program's row "Not available" from the same reason: the
        # processor's row beside it must not say that speech to text will work
        why = "This Parseh runs on Python 3.13, and the speech program is built for Python 3.12 only."
        with mock.patch.object(getstt, "cannot_run", return_value=why):
            cpu = getstt._cpu()
        self.assertFalse(cpu["available"])
        self.assertNotIn("will work", cpu["said"])
        self.assertRegex(cpu["said"], r"^\d+ cores? available\.$")

    def test_windows_says_its_physical_cores_and_not_its_logical_processors(self):
        import struct
        # GetLogicalProcessorInformation: a record for each core (relationship 0), each cache
        # (2), each NUMA node (1) and each package (3); a pointer-sized mask, a 4-byte
        # relationship and 16 bytes more, padded to 32 bytes where a pointer is 8 (24 where 4)
        def records(pointer):
            pad = b"\0\0\0\0" if pointer == 8 else b""
            fmt = "<Q" if pointer == 8 else "<I"
            out = b""
            for rel in [0] * 8 + [2] * 16 + [1, 3]:
                out += struct.pack(fmt, 0xFF) + struct.pack("<I", rel) + pad + b"\0" * 16
            return out
        for pointer in (8, 4):
            self.assertEqual(getstt._cores_in(records(pointer), pointer), 8, pointer)
        self.assertEqual(getstt._cores_in(b"", 8), 0)
        self.assertEqual(getstt._cores_in(records(8)[:-5], 8), 8, "a short tail is not a record")
        # and a Windows computer that has said 8 of 16 is 8 cores, and its threads agree
        getstt.physical_cores.cache_clear()
        self.addCleanup(getstt.physical_cores.cache_clear)
        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(getstt, "_windows_cores", return_value=8), \
                mock.patch.object(getstt, "_logical_cores", return_value=16):
            cpu = getstt._cpu()
            getstt.physical_cores.cache_clear()
        self.assertEqual((cpu["cores"], cpu["logical"], cpu["threads"]), (8, 16, 8))
        # a reader that could not say is no reason for a made-up number
        getstt.physical_cores.cache_clear()
        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(getstt, "_windows_cores", return_value=0):
            self.assertIsNone(getstt.physical_cores())
        getstt.physical_cores.cache_clear()


class TheProbeChild(unittest.TestCase):
    def run_probe(self, *extra):
        out = subprocess.run([PY, "-B", str(ROOT / "lib" / "sttprobe.py"), *extra], capture_output=True,
                             text=True, timeout=60, env=dict(os.environ, PYTHONNOUSERSITE="1"))
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout.strip().splitlines()[-1])

    def test_it_prints_one_line_of_json_and_never_needs_the_program(self):
        got = self.run_probe()
        self.assertEqual(got["python"], "%d.%d" % sys.version_info[:2])
        for key in ("ct2", "cublas", "smi", "seconds"):
            self.assertIn(key, got)
        self.assertIn("loads", got["cublas"])
        self.assertLess(got["seconds"], 20)
        self.assertNotIn("model", " ".join(got))
        self.assertTrue(got["smi"] is None or {"name", "memory", "driver"} <= set(got["smi"]))

    def test_it_can_be_told_not_to_look_in_the_usual_places(self):
        got = self.run_probe("--no-scan")
        self.assertIsNone(got["cublas"].get("dir"))

    def test_the_real_probe_through_the_manager_answers_a_card_or_none(self):
        with mock.patch.object(getstt, "platform_key", return_value="linux x86_64"):
            answer = getstt._run_probe()
        self.assertNotIn("error", answer, answer)
        cuda = getstt._cuda_from(answer)
        self.assertIn(cuda["state"], ("none", "found-not-ready", "ready"))
        if cuda["state"] == "found-not-ready":
            self.assertTrue(cuda["missing"])

    def test_it_is_standard_library_only_and_says_its_licence(self):
        src = (ROOT / "lib" / "sttprobe.py").read_text(encoding="utf-8")
        self.assertIn("SPDX-License-Identifier: GPL-3.0-or-later", src.splitlines()[1])
        tree = ast.parse(src)
        top = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                top |= {a.name.split(".")[0] for a in node.names}
        self.assertEqual(top, {"ctypes", "glob", "json", "os", "subprocess", "sys", "time"})


# --------------------------------------------- taking away, sweeping, children
class Keeping(Tree):
    def test_removing_the_program_takes_only_its_folder(self):
        folder = self.make_runtime()
        (folder / "ctranslate2").mkdir()
        (folder / "ctranslate2" / "_ext.so").write_bytes(b"x" * 500)
        pins, made = self.tiny_pins()
        self.make_model("large-v3", made)
        (self.tmp / "dict").mkdir()
        (self.tmp / "dict" / "fa.db").write_bytes(b"a dictionary")
        (self.tmp / "config").mkdir()
        (self.tmp / "config" / "prefs.json").write_bytes(b"{}")
        freed = getstt.remove("runtime")
        self.assertEqual(freed, 500)
        self.assertFalse((self.stt / "runtime").exists())
        self.assertTrue((self.stt / "models" / "large-v3" / "model.bin").is_file(), "a model is not the program")
        self.assertEqual((self.tmp / "dict" / "fa.db").read_bytes(), b"a dictionary")
        self.assertEqual((self.tmp / "config" / "prefs.json").read_bytes(), b"{}")
        self.assertEqual(getstt.runtime()["state"], "absent")

    def test_removing_a_model_takes_only_that_model(self):
        pins, made = self.tiny_pins()
        self.make_runtime()
        self.make_model("large-v3", made)
        self.make_model("large-v3-turbo", made)
        part = self.stt / "models" / "large-v3.part"
        part.mkdir()
        (part / "model.bin.part").write_bytes(b"half")
        getstt.remove("large-v3")
        self.assertFalse((self.stt / "models" / "large-v3").exists())
        self.assertFalse(part.exists(), "and the stopped download of the same model with it")
        self.assertTrue((self.stt / "models" / "large-v3-turbo" / "model.bin").is_file())
        self.assertTrue((self.stt / "runtime").is_dir())
        self.assertEqual(sorted(p.name for p in (self.stt / "models").iterdir()), ["large-v3-turbo"],
                         "no trash left beside it")

    def test_a_part_in_use_cannot_be_removed(self):
        pins, made = self.tiny_pins()
        self.make_runtime()
        self.make_model("large-v3", made)
        self.make_model("large-v3-turbo", made)
        with getstt.using("large-v3"):
            self.assertTrue(getstt.in_use("large-v3"))
            self.assertFalse(getstt.in_use("large-v3-turbo"))
            self.assertTrue(getstt.in_use("runtime"), "a transcription holds the program too")
            for key in ("large-v3", "runtime"):
                with self.assertRaises(getstt.SpeechError, msg=key) as caught:
                    getstt.remove(key)
                self.assertEqual(caught.exception.code, "in-use")
            getstt.remove("large-v3-turbo")            # another model is nobody's business
        self.assertTrue((self.stt / "models" / "large-v3" / "model.bin").is_file())
        self.assertFalse(getstt.in_use())
        getstt.remove("large-v3")
        with self.assertRaises(getstt.SpeechError) as caught:
            getstt.remove("nothing")
        self.assertEqual(caught.exception.code, "bad-part")

    def test_the_sweep_takes_what_a_killed_server_left_and_nothing_else(self):
        for rel in ("tmp/job-1.pcm", "tmp/pip-123/wheel.whl", "tmp/hf/cache", "runtime.part-99/numpy/x.so",
                    ".trash-5-runtime/a", "runtime/.trash-1-old/a", "runtime/.old-1/a", "models/.trash-2-large-v3/model.bin",
                    "models/large-v3-turbo.part/model.bin.part", "models/large-v3-turbo.part/model.bin.part.json",
                    "runtime/1-cp312/ctranslate2/x.so", "models/large-v3/model.bin"):
            path = self.stt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")
        getstt.sweep()
        left = sorted(str(p.relative_to(self.stt)) for p in self.stt.rglob("*") if p.is_file())
        self.assertEqual(left, ["models/large-v3-turbo.part/model.bin.part",
                                "models/large-v3-turbo.part/model.bin.part.json",
                                "models/large-v3/model.bin",
                                "runtime/1-cp312/ctranslate2/x.so"],
                         "the temporary audio, the staging folders and what was being taken away go; "
                         "a stopped model download waits for the next press, and what is installed stays")
        self.assertTrue((self.stt / "tmp").is_dir(), "the folder itself stays (a job may be about to use it)")

    def test_the_sweep_is_not_run_by_importing_serve(self):
        # serve.main() starts sttjobs.startup on a thread, and that is what
        # calls getstt.sweep (then the held waveforms'): one start-up call, in
        # main(), never at import
        src = (ROOT / "serve.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "startup"
                 and isinstance(n.value, ast.Name) and n.value.id == "sttjobs"]
        self.assertEqual(len(calls), 1)
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        self.assertIn(calls[0], list(ast.walk(main)), "in main(), never at import")
        jobs = ast.parse((ROOT / "lib" / "sttjobs.py").read_text(encoding="utf-8"))
        startup = next(n for n in jobs.body if isinstance(n, ast.FunctionDef) and n.name == "startup")
        self.assertIn("sweep", {n.value for n in ast.walk(startup)
                                if isinstance(n, ast.Constant) and isinstance(n.value, str)},
                      "and startup() sweeps stt/ through getstt")

    def test_a_child_is_ended_when_the_server_stops(self):
        proc = subprocess.Popen([PY, "-c", "import time; time.sleep(60)"], stdin=subprocess.DEVNULL,
                                **getstt.popen_kwargs())
        getstt.track(proc)
        try:
            self.assertIsNone(proc.poll())
            started = time.time()
            getstt.stop_all()
            self.assertLess(time.time() - started, 10)
            self.assertIsNotNone(proc.poll(), "the child was ended")
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            getstt.untrack(proc)
        self.assertEqual(getstt._CHILDREN, set() | {c for c in getstt._CHILDREN if c is not proc})

    def test_a_child_that_ignores_the_first_request_is_killed(self):
        code = "import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nprint('up', flush=True)\ntime.sleep(60)\n"
        if os.name == "nt":
            self.skipTest("SIGTERM is POSIX's")
        proc = subprocess.Popen([PY, "-c", code], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                text=True, **getstt.popen_kwargs())
        getstt.track(proc)
        try:
            proc.stdout.readline()
            getstt.stop_all(wait=0.5)
            proc.wait(timeout=10)
            self.assertLess(proc.returncode, 0, "killed by a signal")
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.stdout.close()
            getstt.untrack(proc)

    def test_the_server_stops_its_children_and_sweeps_on_the_way_in(self):
        src = (ROOT / "serve.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        stop = next(n for n in ast.walk(main) if isinstance(n, ast.FunctionDef) and n.name == "_stop_drawings")
        names = {(c.func.value.id, c.func.attr) for c in ast.walk(stop)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                 and isinstance(c.func.value, ast.Name)}
        self.assertIn(("getstt", "stop_all"), names, "_stop_drawings ends pip and the worker with the drawings")


# --------------------------------------------------------- git, and the folders
@unittest.skipUnless(shutil.which("git"), "no git here")
class GitIgnoresIt(unittest.TestCase):
    def ignored(self, path):
        return subprocess.run(["git", "check-ignore", "-q", path], cwd=str(ROOT),
                              capture_output=True).returncode == 0

    def test_the_program_the_models_and_the_temporary_audio_are_ignored(self):
        # test 26
        for path in ("stt/models/large-v3/model.bin", "stt/models/large-v3-turbo.part/model.bin.part",
                     "stt/runtime/1-cp312/numpy/x.so", "stt/runtime.part-123/x", "stt/tmp/job.pcm",
                     "stt/tmp/", "stt/x"):
            self.assertTrue(self.ignored(path), path)
        for path in ("lib/getstt.py", "lib/sttprobe.py", "lib/stt-requirements.txt", "lib/speechpage.py"):
            self.assertFalse(self.ignored(path), path + " is Parseh's own and travels")

    def test_a_release_ships_nothing_in_it(self):
        import release
        import updater
        self.assertIn("stt/", release.CONTENT)
        self.assertIn("stt/", updater.PERSONAL)
        self.assertNotIn("stt/", release.MUST_HOLD, "made on demand, like mt/")
        self.assertNotIn("stt/.gitkeep", release.MUST_SHIP)


if __name__ == "__main__":
    unittest.main()
