#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Local CTC forced alignment for Parseh's published ONNX networks.

The trellis approach is informed by the BSD-licensed torchaudio forced
alignment tutorial and WhisperX's alignment module.  This implementation uses
only NumPy and ONNX Runtime already installed in Parseh's isolated speech
runtime; it imports neither PyTorch nor a network client.
"""
import json
import math
import os


class AlignmentError(ValueError):
    pass


def _softmax_logs(np, values):
    values = np.asarray(values, dtype=np.float64)
    top = values.max(axis=-1, keepdims=True)
    return values - top - np.log(np.exp(values - top).sum(axis=-1, keepdims=True))


def _path(np, logits, tokens, blank):
    logs = _softmax_logs(np, logits)
    if not len(tokens) or not len(logs):
        raise AlignmentError("no text or no audio frames")
    labels = [blank]
    for token in tokens:
        labels.extend((token, blank))
    scores = np.full((len(logs), len(labels)), -np.inf, dtype=np.float64)
    back = np.full((len(logs), len(labels)), -1, dtype=np.int32)
    scores[0, 0] = logs[0, blank]
    scores[0, 1] = logs[0, labels[1]]
    for frame in range(1, len(logs)):
        for state, label in enumerate(labels):
            choices = [state]
            if state:
                choices.append(state - 1)
            if state > 1 and label != blank and label != labels[state - 2]:
                choices.append(state - 2)
            prior = max(choices, key=lambda n: scores[frame - 1, n])
            scores[frame, state] = scores[frame - 1, prior] + logs[frame, label]
            back[frame, state] = prior
    final = len(labels) - 1
    if scores[-1, final - 1] > scores[-1, final]:
        final -= 1
    if not np.isfinite(scores[-1, final]):
        raise AlignmentError("no monotonic CTC path")
    path = np.empty(len(logs), dtype=np.int32); path[-1] = final
    for frame in range(len(logs) - 1, 0, -1):
        path[frame - 1] = back[frame, path[frame]]
    return logs, path, labels


# a character a text writes for one the networks' vocabularies hold
_SAME = {"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u2027": "\u00b7", "\u0387": "\u00b7", "\u2022": "\u00b7"}


def _spans(np, logits, text, vocab, meta):
    blank = int(meta["model"]["blank_id"])
    delimiter = meta["model"].get("word_delimiter")
    spaced = bool(meta["text"].get("spaces_separate_words"))
    wanted, chars, wildcard = [], [], None
    for char in text:
        lookup = delimiter if spaced and char == " " else char
        token = vocab.get(lookup)
        if token is None and lookup != delimiter:
            # the same letter as the network spells it: its lower case (a caption's capitals), or the one
            # sign of several a text may write for it (’ for ', the dots a Catalan l·l is typed with)
            token = vocab.get(lookup.lower())
            if token is None and lookup in _SAME:
                token = vocab.get(_SAME[lookup])
        if token is None:
            # One synthetic wildcard uses the strongest non-blank emission at
            # each frame, preserving monotonicity without inventing vocabulary.
            if wildcard is None:
                wildcard = logits.shape[1]
                nonblank = np.delete(logits, blank, axis=1)
                logits = np.concatenate((logits, nonblank.max(axis=1, keepdims=True)), axis=1)
            token = wildcard
        wanted.append(int(token)); chars.append(char)
    logs, path, labels = _path(np, logits, wanted, blank)
    frames, scores = [[] for _ in chars], [[] for _ in chars]
    for frame, state in enumerate(path):
        if state % 2:
            index = (state - 1) // 2
            frames[index].append(frame); scores[index].append(float(logs[frame, labels[state]]))
    chars = [(char, min(used), max(used) + 1, sum(sc) / len(sc))
             for char, used, sc in zip(chars, frames, scores) if used]
    if len(chars) != len(wanted):
        raise AlignmentError("a CTC character received no frame")
    if not spaced:
        return chars
    out, current = [], []
    for span in chars:
        if span[0].isspace():
            if current:
                out.append(("".join(p[0] for p in current), current[0][1], current[-1][2],
                            sum(p[3] for p in current) / len(current))); current = []
        else:
            current.append(span)
    if current:
        out.append(("".join(p[0] for p in current), current[0][1], current[-1][2],
                    sum(p[3] for p in current) / len(current)))
    return out


def _load(folder):
    try:
        with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(folder, "vocab.json"), encoding="utf-8") as f:
            vocab = json.load(f)
        with open(os.path.join(folder, "preprocessor_config.json"), encoding="utf-8") as f:
            preprocessor = json.load(f)
    except (OSError, ValueError) as e:
        raise AlignmentError("the aligner metadata could not be read") from e
    if not isinstance(meta, dict) or not isinstance(vocab, dict) or not isinstance(preprocessor, dict):
        raise AlignmentError("the aligner metadata is invalid")
    return meta, {str(k): int(v) for k, v in vocab.items()}, preprocessor


def align_segments(audio, segments, folder, progress=None):
    """Replace alignable segment words -> (segments, made, missed).

    The caller owns a float32, 16 kHz mono array (the exact audio Whisper was
    given) and calls this only after releasing the Whisper model.
    """
    # Set before importing ORT: disabling events afterwards cannot prevent
    # native telemetry initialization or its :memory:.ses fallback sidecar.
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"
    import numpy as np
    import onnxruntime as ort
    meta, vocab, preprocessor = _load(folder)
    model = meta.get("model") or {}
    if (model.get("sample_rate") != 16000 or preprocessor.get("sampling_rate") != 16000
            or model.get("file") != "model.int8.onnx"):
        raise AlignmentError("this aligner is not a Parseh 16 kHz int8 network")
    session = ort.InferenceSession(os.path.join(folder, model["file"]), providers=["CPUExecutionProvider"])
    frame_samples = int(model.get("frame_samples") or 320)
    out, made, missed = [], 0, 0
    for number, seg in enumerate(segments or []):
        row = dict(seg)
        try:
            start, end = float(row["start"]), float(row["end"])
            text = " ".join(str(row.get("text") or "").split())
            first, last = max(0, int(start * 16000)), min(len(audio), int(end * 16000))
            wave = np.asarray(audio[first:last], dtype=np.float32)
            if len(wave) < int(model.get("min_samples") or 400) or not text:
                raise AlignmentError("caption has no alignable audio")
            if preprocessor.get("do_normalize"):
                wave = (wave - wave.mean()) / max(float(wave.std()), 1e-7)
            logits = session.run([model.get("output", "logits")],
                                 {model.get("input", "input_values"): wave[None, :]})[0][0]
            spans = _spans(np, np.asarray(logits), text, vocab, meta)
            words = []
            for surface, a, b, score in spans:
                words.append({"text": surface, "start": round(start + a * frame_samples / 16000.0, 3),
                              "end": round(min(end, start + b * frame_samples / 16000.0), 3),
                              "score": round(math.exp(min(0.0, score)), 4)})
            if not words:
                raise AlignmentError("caption produced no aligned words")
            row["words"] = words; made += len(words)
        except (AlignmentError, ValueError, IndexError, RuntimeError):
            missed += 1
        out.append(row)
        if progress:
            progress(number + 1, len(segments or []))
    return out, made, missed
