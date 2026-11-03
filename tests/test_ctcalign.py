#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small deterministic CTC-trellis checks; ONNX itself stays in the worker."""
import os
import sys
import builtins
import types
import unittest
from unittest.mock import patch

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
import ctcalign  # noqa: E402


class Trellis(unittest.TestCase):
    def test_telemetry_is_disabled_before_onnx_runtime_initializes(self):
        imported = []
        original_import = builtins.__import__
        runtime = types.SimpleNamespace(InferenceSession=lambda *a, **kw: object())

        def guarded_import(name, *args, **kwargs):
            if name == "onnxruntime":
                imported.append(os.environ.get("ORT_DISABLE_TELEMETRY"))
                return runtime
            return original_import(name, *args, **kwargs)

        meta = {"model": {"sample_rate": 16000, "file": "model.int8.onnx"}}
        with patch.dict(os.environ, {"ORT_DISABLE_TELEMETRY": "0"}), \
                patch("builtins.__import__", side_effect=guarded_import), \
                patch.object(ctcalign, "_load", return_value=(meta, {}, {"sampling_rate": 16000})):
            self.assertEqual(ctcalign.align_segments(np.array([], dtype=np.float32), [], "unused"),
                             ([], 0, 0))
        self.assertEqual(imported, ["1"])

    def test_spaced_words_follow_their_highest_monotonic_emissions(self):
        # blank, a, b, delimiter.  The best CTC path says a | b.
        logits = np.array([[7, 0, 0, 0], [0, 9, 0, 0], [7, 0, 0, 0],
                           [0, 0, 0, 9], [7, 0, 0, 0], [0, 0, 9, 0], [7, 0, 0, 0]],
                          dtype=np.float32)
        meta = {"model": {"blank_id": 0, "word_delimiter": "|"},
                "text": {"spaces_separate_words": True}}
        spans = ctcalign._spans(np, logits, "a b", {"a": 1, "b": 2, "|": 3}, meta)
        self.assertEqual([s[0] for s in spans], ["a", "b"])
        self.assertLess(spans[0][1], spans[0][2])
        self.assertLess(spans[0][2], spans[1][1])

    def test_an_unknown_character_remains_monotonic_without_claiming_a_vocab_entry(self):
        logits = np.array([[6, 0], [0, 8], [6, 0], [0, 8], [6, 0]], dtype=np.float32)
        meta = {"model": {"blank_id": 0}, "text": {"spaces_separate_words": False}}
        spans = ctcalign._spans(np, logits, "a?", {"a": 1}, meta)
        self.assertEqual("".join(s[0] for s in spans), "a?")

    def test_a_capital_and_another_sign_for_the_same_letter_find_the_networks_own(self):
        # blank, l, the middle dot, the apostrophe: "L’L·L" and "l'l·l" take the same three tokens, and no wildcard
        logits = np.array([[7, 0, 0, 0], [0, 9, 0, 0], [7, 0, 0, 0], [0, 0, 0, 9], [7, 0, 0, 0],
                           [0, 9, 0, 0], [7, 0, 0, 0], [0, 0, 9, 0], [7, 0, 0, 0], [0, 9, 0, 0]],
                          dtype=np.float32)
        meta = {"model": {"blank_id": 0}, "text": {"spaces_separate_words": False}}
        vocab = {"l": 1, "\u00b7": 2, "'": 3}
        typed = ctcalign._spans(np, logits, "L\u2019L\u2027L", vocab, meta)
        plain = ctcalign._spans(np, logits, "l'l\u00b7l", vocab, meta)
        self.assertEqual([s[1:] for s in typed], [s[1:] for s in plain])


if __name__ == "__main__":
    unittest.main()
