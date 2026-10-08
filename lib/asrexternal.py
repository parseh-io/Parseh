# SPDX-License-Identifier: GPL-3.0-or-later
"""Copy/paste review for all three ASR tasks. No endpoint or code execution."""
import io
import re
import tempfile
from pathlib import Path
import zipfile

import asrcorrection as correction
import asrworkspace
from llmconfig import LLMError
import promptkit

TASKS = ("suspect", "full", "workspace")
MAX_ANSWER = 128 * 1024
MAX_BUNDLE = 8 * 1024 * 1024
MAX_PROMPT = 64 * 1024


def batches(request, task, word_ids=None, divide=False):
    """The prompts of a review, each a list of units.  A reasoning workspace is not divided unless
    asked (`divide`): its files hold the whole transcript, which is what a workspace is for, so the
    chatbot is handed all of it in one prompt and reads what it needs.  Dividing it is for a chatbot
    that cannot open files and needs the evidence in the prompt itself, in pieces that fit; the
    other two methods put their evidence in the prompt and are always divided."""
    if task not in TASKS:
        raise LLMError("bad-review", "Choose a transcript review method.")
    units = correction.sentence_units(request, 1200, "full" if task == "workspace" else task)
    if word_ids is not None:
        selected = set(word_ids)
        units = [dict(unit, targets=[w for w in unit["targets"] if w["word_id"] in selected]) for unit in units]
        units = [unit for unit in units if unit["targets"]]
    # Large collections of alternative hints must not turn one short caption
    # into an unbounded prompt. Each source target belongs to one batch.
    bounded = []
    for unit in units:
        targets, size = [], len(unit["text"].encode("utf-8"))
        for word in unit["targets"]:
            cost = len(correction.hint(word, 10).encode("utf-8")) if correction.suspect(word) else 0
            if targets and size + cost > 5000:
                bounded.append(dict(unit, targets=targets)); targets, size = [], len(unit["text"].encode("utf-8"))
            targets.append(word); size += cost
        if targets:
            bounded.append(dict(unit, targets=targets))
    if task == "workspace" and not divide:
        for number, unit in enumerate(bounded):
            unit["sentence_id"] = "sentence%d" % number
        return [bounded] if bounded else []
    out, window, size = [], [], 0
    for number, unit in enumerate(bounded):
        unit["sentence_id"] = "sentence%d" % number
        cost = len(unit["text"].encode("utf-8")) + sum(len(correction.hint(w, 10).encode("utf-8")) for w in unit["targets"] if correction.suspect(w))
        if window and (size + cost > 5000 or len(window) >= 12):
            out.append(window); window, size = [], 0
        window.append(unit); size += cost
    if window:
        out.append(window)
    return out


def ids(units):
    return {word["word_id"] for unit in units for word in unit["targets"]}


def workspace_files(request, units):
    transcript, suspects, words, captions, slots = asrworkspace._files(request)
    allowed = ids(units)
    required = allowed.intersection(slots)
    region = {word["word_id"] for unit in units for word in unit["words"]}
    current_words = [dict(row) for row in words if row["word_id"] in region]
    by_caption = {}
    for row in current_words:
        by_caption.setdefault(row["segment_id"], []).append(row)
    current_captions, active = [], []
    # Keep inline evidence bounded even when a recognizer emits one enormous
    # caption. Helper offsets refer to these exact caption excerpts.
    for caption in captions:
        members = by_caption.get(caption["segment_id"], [])
        if not members:
            continue
        start = max(0, min(row["char_start"] for row in members) - 100)
        end = min(len(caption["text"]), max(row["char_end"] for row in members) + 100)
        text = caption["text"][start:end]
        current_captions.append(dict(caption, text=text))
        blanked = text
        for row in reversed(members):
            if row["slot"]:
                a, b = row["char_start"] - start, row["char_end"] - start
                blanked = blanked[:a] + "[" + row["slot"] + "]" + blanked[b:]
            row["char_start"] -= start; row["char_end"] -= start
        active.append(caption["segment_id"] + ": " + blanked)
    text = "\n".join(active)
    files = {"input/transcript.txt": transcript, "input/active.txt": text,
             "input/allowed.txt": " ".join(row["word_id"] for row in words if row["word_id"] in allowed),
             "input/targets.txt": " ".join(row["word_id"] for row in words if row["word_id"] in allowed),
             "input/required.txt": " ".join(row["word_id"] for row in words if row["word_id"] in required),
             "input/suspects.csv": asrworkspace._csv([r for r in suspects if r["word_id"] in allowed],
                 asrworkspace.SUSPECT_FIELDS),
             "input/words.csv": asrworkspace._csv(current_words,
                 asrworkspace.WORD_FIELDS),
             "input/captions.csv": asrworkspace._csv(current_captions, ["segment_id", "text"]),
             "input/skim.csv": asrworkspace._csv([], asrworkspace.FIELDS),
             "out/result.csv": asrworkspace._csv([], asrworkspace.FIELDS),
             "review.py": (Path(asrworkspace.__file__).parent / "asrskill" / asrworkspace.SKILL_NAME / "scripts/review.py").read_text(encoding="utf-8"),
             "SKILL.md": (Path(asrworkspace.__file__).parent / "asrskill" / asrworkspace.SKILL_NAME / "SKILL.md").read_text(encoding="utf-8"),
             "README.txt": "Parseh transcript review workspace\n\n"
                "Run Python from this directory. review.py needs only Python's standard library.\n"
                "Inspect evidence with: python review.py --show\n"
                "Check work in progress with: python review.py --check\n"
                "Before returning out/result.csv, run: python review.py --check --complete\n"
                "For tools using Python directly: import review; review.show(); review.save(rows); review.check()\n"
                "Include every ID in input/required.txt: change the word, or keep the exact original. "
                "Give every row a confidence, sure or unsure (unchanged and sure: Whisper's word is right). "
                "Unchanged unflagged words do not need result rows.\n"
                "This checks source spans, limits, punctuation and required coverage; it cannot decide "
                "whether a transcription is linguistically correct. Parseh independently validates imported edits.\n"
                "Keep input files unchanged. Only out/result.csv contains your proposed edits.\n"}
    if sum(len(value.encode("utf-8")) for value in files.values()) > MAX_BUNDLE:
        raise LLMError("too-large", "This text workspace exceeds the download limit. The sentence review methods remain available.")
    return files


def assembled(request, task, units, divided=False):
    flags = None
    if task == "workspace":
        files = workspace_files(request, units)
        flags = {"divided": divided, "whole": not divided}
        if divided:
            data = "\n\n".join(name + ":\n" + files[name] for name in ("input/active.txt", "input/allowed.txt", "input/targets.txt", "input/required.txt", "input/words.csv", "input/suspects.csv", "input/captions.csv"))
        else:
            # nothing of it is repeated: it is the workspace's, and a prompt that held the whole of a long
            # transcript would be refused for its size
            data = ("input/transcript.txt and input/active.txt are the transcript, the second with its numbered blanks; "
                    "input/required.txt lists the %d numbered entries to answer, input/allowed.txt every ID that may be edited; "
                    "input/words.csv, input/suspects.csv and input/captions.csv hold the evidence. "
                    "None of it is repeated in this prompt: attach the workspace ZIP "
                    "(a chatbot that cannot open files needs the review divided into several prompts)."
                    % len(files["input/required.txt"].split()))
    else:
        regions = []
        for unit in units:
            item = correction.messages(request, unit, task=task)[-1]["content"]
            regions.append("TARGET LABEL: " + unit["sentence_id"] + "\n" + item)
        data = "\n\n".join(regions)
    return promptkit.assemble("asr-" + task, request["language"], data=data, flags=flags)


def prompt(request, task, units, divided=False):
    text = str(assembled(request, task, units, divided))
    if len(text.encode("utf-8")) > MAX_PROMPT:
        raise LLMError("too-large", "This prompt exceeds its size limit. Review received suggestions and edit these words manually.")
    return text


def bundle(request, units, text):
    files = workspace_files(request, units)
    files["PROMPT.txt"] = text
    if sum(len(value.encode("utf-8")) for value in files.values()) > MAX_BUNDLE:
        raise LLMError("too-large", "The text workspace download exceeds its size limit.")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            entry = zipfile.ZipInfo("parseh-review/" + name)
            entry.external_attr = 0o100600 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, content.encode("utf-8"))
    if stream.tell() > MAX_BUNDLE:
        raise LLMError("too-large", "The text workspace download exceeds its size limit.")
    return stream.getvalue()


def clean(answer):
    if (not isinstance(answer, str) or any(0xD800 <= ord(c) <= 0xDFFF for c in answer)
            or len(answer.encode("utf-8")) > MAX_ANSWER):
        raise LLMError("bad-external-answer", "Paste a bounded UTF-8 answer for this batch.")
    answer = answer.strip().replace("\r\n", "\n")
    if answer.startswith("```") and answer.endswith("```"):
        answer = "\n".join(answer.splitlines()[1:-1]).strip()
    if not answer:
        raise LLMError("bad-external-answer", "Paste the model's answer before importing it.")
    return answer


def parse(request, task, units, answer):
    answer = clean(answer)
    allowed = ids(units)
    proposals, failed, ignored, kept, why = [], set(), [], [], {}
    if task == "workspace":
        # Only parse the pasted CSV. Never execute a pasted response or its code.
        with tempfile.TemporaryDirectory(prefix="parseh-pasted-csv-") as folder:
            root = Path(folder); (root / "out").mkdir()
            (root / "out/result.csv").write_text(answer, encoding="utf-8")
            problems = []
            proposals, seen = asrworkspace._proposals(root, request, allowed, kept=kept, problems=problems)
        sources = correction.index(request)
        failed = {ident for ident in allowed - seen if correction.suspect(sources[ident])}
        why = {ident: "the answer has no row for this word" for ident in failed}
        # a row that did not fit is left out and said, with the reason, on its words; the other rows are used
        for problem in problems:
            ignored.append({"original": " ".join(problem["word_ids"]), "replacement": "", "reason": "Row refused: " + problem["why"]})
            for ident in problem["word_ids"]:
                if ident in failed:
                    why[ident] = "its row was refused: " + problem["why"]
    else:
        expected = {unit["sentence_id"]: unit for unit in units}
        lines = {}
        for line in answer.splitlines():
            if not line.strip():
                continue
            # a chatbot says things around the lines that matter: a greeting, a note, the label in bold, a capital letter
            match = re.fullmatch(r"[\s*_`>\-]*(sentence[0-9]+)\s*[:\uff1a]\s*(.*)", line, re.I)
            if not match:
                ignored.append({"original": line[:200], "replacement": "", "reason": "A line without a sentence label was left out."})
                continue
            label = match[1].lower()
            if label not in expected or label in lines:
                ignored.append({"original": line[:200], "replacement": "", "reason": "A line with an unknown or repeated label was left out."})
                continue
            lines[label] = match[2].lstrip("*_` ").rstrip("*_` ") if match[2].startswith(("*", "_", "`")) else match[2]
        if not lines:
            raise LLMError("bad-external-answer", "No line of the answer starts with one of the sentence labels (sentence0:, sentence1:, and so on). Paste the chatbot's answer as it gave it, with the labels.")
        for ident, unit in expected.items():
            if ident not in lines:
                failed.update(word["word_id"] for word in unit["targets"])
                why.update((word["word_id"], "the answer has no line for this sentence") for word in unit["targets"])
                continue
            try:
                edits, extra = (correction.full_sentence_result if task == "full" else correction.sentence_result)(lines[ident], unit)
                ignored.extend(extra)
                for edit in edits:
                    if set(edit.get("word_ids", [edit["word_id"]])) <= allowed:
                        proposals.append(edit)
                    else:
                        ignored.append({"original": edit["original"], "replacement": edit["candidates"][0]["text"], "reason": "Outside the selected retry words."})
            except LLMError as error:
                failed.update(word["word_id"] for word in unit["targets"])
                why.update((word["word_id"], error.say) for word in unit["targets"])
    proposed = {ident for proposal in proposals for ident in proposal.get("word_ids", [proposal["word_id"]])}
    return {"suggestions": proposals, "kept": kept, "failed_word_ids": sorted(failed), "failed_reasons": why, "uncertain_word_ids": sorted(allowed - proposed),
            "reviewed_word_ids": sorted(allowed), "ignored_edits": ignored}
