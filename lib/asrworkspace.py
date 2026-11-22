# SPDX-License-Identifier: GPL-3.0-or-later
"""The text workspace of the copy/paste review: its files, and the reading of its result CSV.

asrexternal writes these files into the workspace ZIP a person hands to a chatbot, and reads
the out/result.csv the chatbot gives back.  Nothing here runs code: the shipped checker
(asrskill/parseh-asr-workspace/scripts/review.py) is imported to validate rows against the
server's own evidence, never an uploaded script.
"""
import csv
import importlib.util
import io
from pathlib import Path
import unicodedata

import asrcorrection as correction
from reviewerror import LLMError

SKILL_NAME = "parseh-asr-workspace"
FIELDS = ["word_ids", "original", "replacement", "reason", "confidence"]
OLD_FIELDS = FIELDS[:4]       # an answer written before the fifth column is read the same, as unrated
WORD_FIELDS = ["word_id", "segment_id", "original", "slot", "char_start", "char_end", "source_index"]
_CHECKER = None


def checker():
    """Use the shipped checker against server-owned evidence, never uploaded code."""
    global _CHECKER
    if _CHECKER is None:
        path = Path(__file__).parent / "asrskill" / SKILL_NAME / "scripts/review.py"
        spec = importlib.util.spec_from_file_location("parseh_workspace_checker", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CHECKER = module
    return _CHECKER



def _csv(rows, fields):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader(); writer.writerows(rows)
    return out.getvalue()


SUSPECT_FIELDS = ['slot', 'word_id', 'guess', 'whisper_score', 'low_asr_score',
                  'dictionary_miss', 'alternatives_available', 'context', 'whisper_hints']


def _files(request):
    transcript, rows, originals, captions, slots = [], [], [], [], {}
    for segment_at, segment in enumerate(request["segments"]):
        text, local, patches = segment["text"], 0, []
        captions.append({"segment_id": segment["segment_id"], "text": text})
        for source_index, word in enumerate(segment["words"]):
            at = text.find(word["text"], local) if word["text"] else -1
            if at >= 0:
                local = at + len(word["text"])
            if not word["reviewable"] or at < 0:
                continue
            slot = ""
            if correction.suspect(word):
                slot = str(len(slots) + 1); slots[word["word_id"]] = slot
                patches.append((at, local, "[" + slot + "]"))
                rows.append({"slot": slot, "word_id": word["word_id"], "guess": word["text"],
                             "whisper_score": word["asr_confidence"] if word["asr_confidence"] is not None else "unavailable",
                             "low_asr_score": word["low_asr_score"], "dictionary_miss": word.get("dictionary_miss", False),
                             "alternatives_available": word["alternatives_available"],
                             "context": " ".join([request["segments"][segment_at - 1]["text"][-100:] if segment_at else "", text[max(0, at - 150):min(len(text), local + 150)], request["segments"][segment_at + 1]["text"][:100] if segment_at + 1 < len(request["segments"]) else ""]).strip(),
                             "whisper_hints": correction.hint(word, 10)})
            originals.append({"word_id": word["word_id"], "segment_id": word["segment_id"],
                              "original": word["text"], "slot": slot, "char_start": at, "char_end": local,
                              "source_index": source_index})
        for a, b, replacement in reversed(patches):
            text = text[:a] + replacement + text[b:]
        transcript.append(segment["segment_id"] + ": " + text)
    return "\n".join(transcript), rows, originals, captions, slots



def _readable_rows(rows, words, captions, allowed, targets, problems):
    """The rows of a pasted answer that stand on their own, each checked alone: one that does not is told in `problems`
    ({"word_ids", "why"}) and left out, and the others are kept.  A person who pastes 200 rows should not lose them for one."""
    good, taken = [], set()
    for n, row in enumerate(rows):
        ids = str(row.get("word_ids", "")).split() if isinstance(row, dict) else []
        try:
            if n >= len(allowed):
                raise ValueError("Too many result rows for these editable words.")
            one, _ = checker().validate_rows([row], words, captions, allowed, targets)
            if taken.intersection(one[0]["word_ids"].split()):
                raise ValueError("Source IDs cannot repeat or overlap another result row.")
        except (ValueError, KeyError, TypeError) as error:
            problems.append({"word_ids": ids[:8], "why": str(error)[:300]})
            continue
        taken.update(one[0]["word_ids"].split())
        good.append(one[0])
    return good


def _proposals(root, request, allowed, targets=None, required=(), complete=False, kept=None, problems=None, loose=None):
    """The edits of out/result.csv, and the IDs it answered.  A row that leaves Whisper's word as it is is
    no edit but it is an answer: it goes into `kept`, where the caller gives one, with the model's reason and
    how sure it said it was -- so that the review says "the model agrees with Whisper here" and not nothing.

    With a list for `problems` the rows are read ONE BY ONE, as a person's pasted answer is: a row that does not fit is told there
    and the rest are used.  Without one the first that does not fit refuses the whole file.

    With a dict for `loose` a row that was used but left something out that was asked -- how sure the model is -- is told there,
    {word_id: [say]}: a leniency, and the words it touches are marked so that they can be asked again."""
    path = root / "out/result.csv"
    if path.stat().st_size > 65536:
        raise LLMError("too-large", "The workspace CSV exceeds its size limit.")
    sources = correction.index(request)
    proposals, seen = [], set()
    try:
        # The downloadable checker is also Parseh's first validation layer.
        # Its input here is rebuilt from the immutable ASR request; uploaded or
        # model-edited evidence files are never trusted by the server.
        _, _, words, captions, _ = _files(request)
        try:
            parsed = checker().parse_csv(path.read_text(encoding="utf-8"))
            by_word, by_caption = {word["word_id"]: word for word in words}, {caption["segment_id"]: caption["text"] for caption in captions}
            if problems is None:
                rows, _ = checker().validate_rows(parsed, by_word, by_caption, allowed, targets, required=required, complete=complete)
            else:
                rows = _readable_rows(parsed, by_word, by_caption, allowed, targets, problems)
        except ValueError as error:
            # The trusted helper uses bounded structural errors, never source
            # or replacement text. Give the model enough detail to repair a row.
            raise LLMError("invalid-workspace-csv", "The workspace CSV needs correction: " + str(error)[:600]) from None
        for n, row in enumerate(rows):
            try:
                if n > len(allowed) or set(row) not in (set(FIELDS), set(OLD_FIELDS)) or any(not isinstance(v, str) for v in row.values()):
                    raise ValueError("the row has too many or too few columns")
                ids = row["word_ids"].split()
                if (not ids or not set(ids) <= allowed or seen.intersection(ids)
                        or targets is not None and not set(ids).intersection(targets)):
                    raise ValueError("its word IDs are not editable words of this prompt, or repeat another row's")
                p = {"word_id": ids[0], "word_ids": ids, "original": row["original"]}
                a, b, original = correction.proposal_span(p, sources)
                members = [sources[i] for i in ids]
                segment = next(s for s in request["segments"] if s["segment_id"] == members[0]["segment_id"])
                # Source panel offsets are absolute; reconstruct only the caption's
                # exact mapped span, preserving inter-word spacing and CJK pieces.
                cursor = 0
                for source_word in segment["words"]:
                    position = segment["text"].find(source_word["text"], cursor) if source_word["text"] else -1
                    if position >= 0:
                        cursor = position + len(source_word["text"])
                    if source_word["reviewable"]:
                        base = source_word["span_start"] - position
                        break
                if segment["text"][a - base:b - base] != original:
                    raise ValueError("its original text is not the transcript's text at those words")
                replacement = row["replacement"]
                punct = lambda t: "".join(c for c in t if unicodedata.category(c).startswith("P"))
                if (not replacement.strip() or len(replacement) > min(200, max(24, 3 * len(original)))
                        or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in replacement)
                        or punct(original) != punct(replacement) or len(row["reason"]) > 500):
                    raise ValueError("its replacement is empty, too long, has a control character, or changes the punctuation")
                seen.update(ids)
                rating = row.get("confidence") or None
                if loose is not None and "confidence" in row and rating is None:
                    for i in ids:
                        loose.setdefault(i, []).append("the row did not say how sure the model is (sure or unsure), and was used anyway")
                if replacement == original:
                    if kept is not None:
                        kept.append({"word_ids": ids, "original": original, "rating": rating, "reason": row["reason"]})
                    continue
                word = members[0]
                p.update({k: v for k, v in correction.public_word(word).items() if k != "text"})
                p.update(span_start=a, span_end=b, end=members[-1]["end"], asr_evidence=[correction.public_word(w) for w in members],
                         candidates=[{"text": replacement, "confidence": None, "reason": row["reason"]}],
                         error_likelihood=None, reason=row["reason"], rating=rating, method="workspace-code")
                proposals.append(p)
            except (ValueError, StopIteration, KeyError) as error:
                if problems is None:
                    raise
                problems.append({"word_ids": str(row.get("word_ids", "")).split()[:8],
                                 "why": str(error) or "the row does not match the words or spans of the transcript"})
    except LLMError as error:
        if error.code == "invalid-workspace-csv":
            raise
        raise LLMError("invalid-workspace-csv", "The workspace CSV has invalid IDs, duplicate entries or mismatched source spans. Its proposals were not applied.") from None
    except (OSError, UnicodeError, ValueError, csv.Error, StopIteration):
        raise LLMError("invalid-workspace-csv", "The workspace CSV has invalid IDs, duplicate entries or mismatched source spans. Its proposals were not applied.")
    return proposals, seen
