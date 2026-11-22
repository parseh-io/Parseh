# SPDX-License-Identifier: GPL-3.0-or-later
"""The transcript-review skills say how they are used now, and their ZIPs are what their folders build (a0.6.3 G3).

    python3 -m unittest tests.test_asr_skill_zips

The connected agent (finish_review, the skim and resolve phases) was removed; the skills are now added by a
person to their own chatbot and used with the copy/paste review.  On the old files every test here fails: the
workspace skill told the model to "call finish_review", and the ZIPs held an older SKILL.md and review.py.
"""
import io
import re
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "lib" / "asrskill"
sys.path[:0] = [str(ROOT / "lib"), str(ROOT / "youtube/lib")]
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("asrskill_build", HERE / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)
import asrexternal  # noqa: E402
import asrworkspace  # noqa: E402
from tests.test_asr_external import source  # noqa: E402


class Skills(unittest.TestCase):
    def test_the_zips_are_what_their_folders_build(self):
        for skill in build.SKILLS:
            with self.subTest(skill=skill):
                self.assertEqual((HERE / (skill + ".zip")).read_bytes(), build.build(skill),
                                 "run python3 lib/asrskill/build.py")
                names = zipfile.ZipFile(io.BytesIO(build.build(skill))).namelist()
                self.assertEqual(names[0], skill + "/SKILL.md")
        r = subprocess.run([sys.executable, str(HERE / "build.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_skill_describes_the_removed_agent(self):
        for skill in build.SKILLS + ("README.txt",):
            path = HERE / skill / "SKILL.md" if skill != "README.txt" else HERE / skill
            text = path.read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                for gone in ("finish_review", "skim phase", "resolve phase", "Resolve must", "Unsloth", "read_skill"):
                    self.assertNotIn(gone, text)
                self.assertIn("paste", text.lower())
                if skill != "README.txt":
                    front = re.match(r"---\nname: (.+)\ndescription: (.+)\nlicense: GPL-3.0-or-later\n---\n", text)
                    self.assertIsNotNone(front, "front matter")
                    self.assertEqual(front[1], skill)

    def test_each_skill_names_the_answer_parseh_reads(self):
        for skill in ("parseh-asr-correction", "parseh-asr-audit"):
            self.assertIn("sentence0: ", (HERE / skill / "SKILL.md").read_text(encoding="utf-8"))
        workspace = (HERE / "parseh-asr-workspace" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(",".join(asrworkspace.FIELDS), workspace)
        self.assertIn("review.check(require_complete=True)", workspace)

    def test_the_skills_example_answers_are_read_as_their_examples_say(self):
        # the very lines the sentence skills show, pasted as an answer to a real prompt
        _, request = source()
        units = asrexternal.batches(request, "suspect")[0]
        got = asrexternal.parse(request, "suspect", units, "sentence0: Loro hanno detto ciao.")
        self.assertEqual([s["candidates"][0]["text"] for s in got["suggestions"]], ["hanno"])
        # and the CSV rows of the workspace skill, its header and quoting
        units = asrexternal.batches(request, "workspace")[0]
        answer = ("word_ids,original,replacement,reason,confidence\n"
                  "s0w1,anno,hanno,The sentence needs this verb.,sure\n"
                  "s0w3,ciao.,ciao.,\"The greeting fits, Whisper's word is right.\",sure\n")
        got = asrexternal.parse(request, "workspace", units, answer)
        self.assertEqual([s["candidates"][0]["text"] for s in got["suggestions"]], ["hanno"])
        self.assertEqual([k["word_ids"] for k in got["kept"]], [["s0w3"]])
        self.assertEqual(got["ignored_edits"], [])


if __name__ == "__main__":
    unittest.main()
