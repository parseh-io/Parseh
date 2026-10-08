# SPDX-License-Identifier: GPL-3.0-or-later
"""Additional two-pass ASR review, with real private files and external tools.

Input files are read-only; agent Python runs under an optional Linux OS sandbox.
Nothing is installed. Only one bounded CSV file is writable. Files are destroyed
on completion/cancellation; provider transport never receives real host paths.
"""
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import unicodedata

import asrcorrection as correction
from llmconfig import LLMError

SKILL_NAME = "parseh-asr-workspace"
FIELDS = ["word_ids", "original", "replacement", "reason", "confidence"]
OLD_FIELDS = FIELDS[:4]       # an answer written before the fifth column is read the same, as unrated
WORD_FIELDS = ["word_id", "segment_id", "original", "slot", "char_start", "char_end", "source_index"]
_STATUS = None
_STATUS_LOCK = threading.Lock()
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


def instructions():
    return (Path(__file__).parent / "asrskill" / SKILL_NAME / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[-1].strip()


def _command(root, worker=True):
    # No /proc, home, /etc, user environment, writable directory or host tools.
    args = [shutil.which("bwrap"), "--unshare-all", "--die-with-parent", "--new-session",
            "--cap-drop", "ALL", "--ro-bind", "/usr", "/usr"]
    for directory in ("/lib", "/lib64"):
        if os.path.exists(directory):
            args += ["--ro-bind", directory, directory]
    args += ["--ro-bind", str(root), "/work", "--bind", str(root / "out" / "result.csv"),
             "/work/out/result.csv", "--ro-bind", str(Path(__file__).with_name("asrworkspaceworker.py")),
             "/runner.py", "--chdir", "/work", "--clearenv", "--setenv", "LANG", "C.UTF-8",
             "--setenv", "PYTHONIOENCODING", "utf-8", "/usr/bin/python3", "-I", "-S", "-B"]
    return args + (["/runner.py"] if worker else ["-c", "print('ready')"])


def sandbox_status():
    global _STATUS
    with _STATUS_LOCK:
        if _STATUS is None:
            ok = False
            if os.name == "posix" and shutil.which("bwrap") and Path("/usr/bin/python3").is_file():
                try:
                    with tempfile.TemporaryDirectory(prefix="parseh-code-probe-") as folder:
                        root = Path(folder); (root / "out").mkdir(); (root / "out/result.csv").touch()
                        r = subprocess.run(_command(root, False), stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL, timeout=3)
                        ok = r.returncode == 0 and r.stdout.strip() == b"ready"
                except (OSError, subprocess.SubprocessError):
                    pass
            _STATUS = {"available": ok, "say": "Isolated Python workspace is available." if ok else
                       "Workspace review needs Linux with working bubblewrap and system Python. Existing review methods remain available."}
        return dict(_STATUS)


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


TOOLS = [{"type": "function", "function": {"name": "read_file", "description": "Read a bounded portion of a workspace input file.",
         "parameters": {"type": "object", "properties": {"path": {"type": "string", "enum": ["input/transcript.txt", "input/active.txt", "input/allowed.txt", "input/targets.txt", "input/required.txt", "input/suspects.csv", "input/words.csv", "input/captions.csv", "input/skim.csv"]},
                          "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 4000}}, "required": ["path"], "additionalProperties": False}}},
         {"type": "function", "function": {"name": "python", "description": "Run short Python code in /work. Read input files; write only out/result.csv. No network or host access.",
          "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"], "additionalProperties": False}}},
         {"type": "function", "function": {"name": "finish_review", "description": "Validate out/result.csv and finish this phase after running Python.",
          "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}]


class Workspace:
    def __init__(self, root, cancel):
        self.root, self.cancel, self.ran = root, cancel, False
        self.kept = []        # the rows of the last valid result.csv that keep Whisper's word (_proposals)
        self.loose = {}       # the words whose row was used but left out how sure the model is (_proposals)
        self.output_bytes = 4000

    def python(self, code):
        if not isinstance(code, str) or len(code.encode("utf-8")) > 12000:
            raise LLMError("invalid-code", "Workspace code exceeds its size limit.")
        self.cancel.check()
        # Child output is a file, not an unbounded PIPE buffered in server RAM.
        with tempfile.TemporaryFile(dir=self.root) as output:
            proc = subprocess.Popen(_command(self.root), stdin=subprocess.PIPE, stdout=output,
                                    stderr=output, start_new_session=True)
            try:
                deadline = time.monotonic() + 8
                pending = code.encode("utf-8")
                while True:
                    self.cancel.check()
                    if time.monotonic() > deadline:
                        raise LLMError("code-timeout", "Workspace code exceeded its time limit.")
                    try:
                        proc.communicate(input=pending, timeout=.1)
                        break
                    except subprocess.TimeoutExpired:
                        pending = None
                output.seek(0); raw = output.read(self.output_bytes + 1)
                text = raw[:self.output_bytes].decode("utf-8", "ignore")
                if len(raw) > self.output_bytes:
                    text += "\nOutput clipped. Inspect fewer rows or shorter excerpts."
                text = text.replace(str(self.root), "/work")
                self.ran = self.ran or proc.returncode == 0
                return ("Python completed.\n" if proc.returncode == 0 else "Python failed; correct the code and try again.\n") + text
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()

    def call(self, name, args):
        if name == "python" and set(args) == {"code"}:
            return self.python(args["code"])
        if name == "read_file" and set(args) <= {"path", "offset", "limit"} and "path" in args:
            allowed = TOOLS[0]["function"]["parameters"]["properties"]["path"]["enum"]
            offset, limit = args.get("offset", 0), args.get("limit", 4000)
            if args["path"] not in allowed or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 4000:
                raise LLMError("invalid-file", "Choose a listed input file and a bounded character range.")
            text = (self.root / args["path"]).read_text(encoding="utf-8")
            fragment = text[offset:offset + limit].encode("utf-8")[:self.output_bytes].decode("utf-8", "ignore")
            return "Characters %d–%d of %d:\n%s" % (offset, offset + len(fragment), len(text), fragment)
        raise LLMError("invalid-tools", "Invalid workspace tool arguments.")


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
    and the rest are used.  Without one the first that does not fit refuses the whole file (the tool loop of the connected
    model needs that, to send the model back to mend its rows).

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


def _replace_kept(old, new, proposed):
    """The rows that keep Whisper's word, with those of the words just answered replaced by the new ones."""
    answered = set(proposed) | {w for k in new for w in k["word_ids"]}
    return [k for k in old if not answered.intersection(k["word_ids"])] + list(new)


def _some(ids, divided):
    """The IDs a message names: all of a region's; for the whole transcript the first few, the rest being in input/required.txt."""
    if divided or len(ids) <= 40:
        return " ".join(ids)
    return "%s and %d more (all in input/required.txt)" % (" ".join(ids[:40]), len(ids) - 40)


def _phase(workspace, request, adapter, phase, allowed, context_tokens, diagnostic, key):
    targets = getattr(workspace, 'targets', allowed)
    divided = getattr(workspace, 'divided', True)
    # A region of a few dozen words puts its IDs in the message.  The WHOLE transcript is one region and its IDs would fill the
    # model's context before it has read anything: they are in the files, where review.show() and review.check() read them.
    ids = ("Phase target IDs: %s. Editable IDs: %s." % (" ".join(sorted(targets)), " ".join(sorted(allowed))) if divided else
           "The whole transcript is one region: the phase target IDs are in input/targets.txt and the editable IDs in input/allowed.txt.")
    initial = [{"role": "system", "content": instructions()}, {"role": "user", "content":
               "Language: %s. Phase: %s. Start with python: import review; review.show(). %s "
               "Next call python: import review; review.save(rows); review.check(). "
               "Correct any structural errors or missing required entries; run review.check(require_complete=True) before finish_review. "
               "%s Each edit must include a phase target; "
               "join adjacent editable words when Whisper split one word." % (request["language"], phase,
               "Resolve every numbered entry: change it, or keep its original (confidence sure if Whisper's word is right, unsure if you cannot tell)." if phase == "resolve" else "Skim unblanked words only; an empty edits list is valid.",
               ids)}]
    history = []
    # one region had 300 seconds and 12 tool calls; a whole transcript is as many regions' worth of work and has as many (correct() sets them)
    deadline = time.monotonic() + getattr(workspace, 'seconds', 300)
    for turn in range(getattr(workspace, 'turns', 12)):
        workspace.cancel.check()
        if time.monotonic() > deadline:
            raise LLMError("workspace-timeout", "This workspace phase reached its time limit; other words can still be reviewed.")
        state = []
        if workspace.ran:
            try:
                _, seen = _proposals(workspace.root, request, allowed, targets)
                state = [{"role": "user", "content": "Python succeeded. The current result.csv contains %d valid entries. %s" %
                          (len(seen), "Call finish_review now if your skim is complete." if phase == "skim" else
                           "Resolve still needs these IDs: " + _some(sorted(targets - seen), divided) + ". If none remain, call finish_review now.")}]
            except LLMError as error:
                state = [{"role": "user", "content": error.say + " Correct result.csv with Python before finishing."}]
        prompt = initial + history + state
        # Conservative byte budget, reserving tool schema and reasoning output.
        output = min(4096, max(1024, context_tokens // 4))
        agent_tools = TOOLS[1:]  # Read files through real Python, in one operation.
        budget = context_tokens - output - len(json.dumps(agent_tools).encode("utf-8")) - 512
        while history and len(json.dumps(initial + history + state, ensure_ascii=False).encode("utf-8")) > budget:
            # Keep assistant tool calls and their results together.
            history = history[1:]
            while history and history[0]["role"] == "tool":
                history.pop(0)
        prompt = initial + history + state
        if len(json.dumps(prompt, ensure_ascii=False).encode("utf-8")) > budget:
            raise LLMError("context-too-large", "This workspace region exceeds the saved model context budget.")
        trace = {"sentence_id": key + ":" + phase, "attempt": turn + 1, "phase": phase,
                 "word_ids": sorted(allowed), "prompt": prompt, "state": "running"}
        trace["source"] = "\n".join(segment["text"] for segment in request["segments"]
                                    if any(word["word_id"] in allowed for word in segment["words"]))[:4000]
        try:
            reply = adapter.agent_turn(prompt, agent_tools, workspace.cancel, max_tokens=output, observe=trace.update)
            history.append(reply)
            outputs, finished = [], None
            for call in reply["tool_calls"]:
                workspace.cancel.check()
                name, args = call["function"]["name"], json.loads(call["function"]["arguments"])
                try:
                    if name == "finish_review":
                        if args or not workspace.ran:
                            raise LLMError("code-required", "Run Python to create the result CSV before finishing.")
                        workspace.kept, workspace.loose = [], {}
                        proposals, seen = _proposals(workspace.root, request, allowed, targets,
                                                     required=targets if phase == "resolve" else (), complete=True, kept=workspace.kept, loose=workspace.loose)
                        if phase == "resolve" and not targets <= seen:
                            raise LLMError("incomplete-entries", "Some numbered entries are missing. Add unchanged originals for uncertain words before finishing.")
                        finished = proposals, seen
                        result = "Phase complete; proposals await human review."
                    else:
                        result = workspace.call(name, args)
                except LLMError as e:
                    if e.code in ("cancelled", "source-changed", "settings-changed"):
                        raise
                    result = e.say
                history.append({"role": "tool", "tool_call_id": call["id"], "content": result})
                outputs.append({"name": name, "output": result[:16000]})
            trace.update(state="complete" if finished else "tool-step", tool_results=outputs)
            if diagnostic:
                diagnostic(trace)
            if finished:
                return finished
        except Exception as error:
            safe = error if isinstance(error, LLMError) else LLMError("workspace-failed", "This workspace phase could not finish. Whisper's text is intact.")
            trace.update(state="failed", code=safe.code, error=safe.say)
            if diagnostic:
                diagnostic(trace)
            raise safe
    raise LLMError("tool-limit", "The model did not finish this phase within its tool-call limit. Retry its remaining words.")


def correct(request, adapter, cancel, progress, context_tokens=8192, diagnostic=None, target_word_ids=None, divide=False):
    """Review a transcript with a connected model that has the workspace to itself.  The whole transcript is ONE region, as a
    workspace is for; `divide` cuts it into small regions of a few dozen words, one tool conversation each (what this used to do
    always), for a model that cannot hold so much.  The whole is given as many tool calls and as much time as its regions would
    have had together."""
    if not sandbox_status()["available"]:
        raise LLMError("workspace-unavailable", sandbox_status()["say"])
    if context_tokens < 8192:
        raise LLMError("workspace-context", "Workspace review needs a saved context budget of at least 8192 tokens.")
    transcript, suspects, originals, captions, slots = _files(request)
    units = correction.sentence_units(request, min(1800, max(256, context_tokens // 6)), "full")
    if target_word_ids is not None:
        selected = set(target_word_ids)
        units = [u for u in units if any(w["word_id"] in selected for w in u["targets"])]
        units = [dict(u, targets=[w for w in u["targets"] if w["word_id"] in selected]) for u in units]
    # Group caption pieces into small multi-caption windows. The full file
    # remains available, while each tool conversation has a bounded target set.
    windows, current, size = [], [], 0
    for unit in units:
        cost = len(unit["text"].encode("utf-8"))
        if current and (sum(len(u["targets"]) for u in current) + len(unit["targets"]) > 80 or size + cost > 2200):
            windows.append(current); current, size = [], 0
        current.append(unit); size += cost
    if current:
        windows.append(current)
    regions = len(windows)
    if not divide and windows:
        windows = [[unit for window in windows for unit in window]]
    total = sum(len(u["targets"]) for u in units)
    suggestions, failed, uncertain, reviewed, done = [], [], [], [], 0
    kept_rows, why, loose = [], {}, {}
    progress(0, total, "Preparing isolated workspace")
    with tempfile.TemporaryDirectory(prefix="parseh-asr-workspace-") as folder:
        root = Path(folder); (root / "input").mkdir(); (root / "out").mkdir()
        shutil.copyfile(Path(__file__).parent / "asrskill" / SKILL_NAME / "scripts/review.py", root / "review.py")
        (root / "input/transcript.txt").write_text(transcript, encoding="utf-8")
        for phase in ("skim", "resolve"):
            skim_rows = [{"word_ids": " ".join(p["word_ids"]), "original": p["original"], "replacement": p["candidates"][0]["text"], "reason": p["reason"]} for p in suggestions]
            (root / "input/skim.csv").write_text(_csv(skim_rows, FIELDS), encoding="utf-8")
            for i, window in enumerate(windows):
                cancel.check()
                ids = {w["word_id"] for unit in window for w in unit["targets"]}
                region = {w["word_id"] for unit in window for w in unit["words"]}
                segment_ids = {w["segment_id"] for unit in window for w in unit["words"]}
                positions = [n for n, segment in enumerate(request["segments"]) if segment["segment_id"] in segment_ids]
                left, right = min(positions), max(positions)
                # Bounded surrounding captions are context, never additional targets.
                lines = transcript.splitlines()
                before = lines[left - 1].encode("utf-8")[-240:].decode("utf-8", "ignore") if left else ""
                after = lines[right + 1].encode("utf-8")[:240].decode("utf-8", "ignore") if right + 1 < len(lines) else ""
                active = "Target region:\n" + "\n".join(lines[left:right + 1]) + "\nBefore (context only): " + before + "\nAfter (context only): " + after
                (root / "input/active.txt").write_text(active, encoding="utf-8")
                rows = [r for r in suspects if r["word_id"] in ids]
                (root / "input/suspects.csv").write_text(_csv(rows, SUSPECT_FIELDS), encoding="utf-8")
                (root / "input/words.csv").write_text(_csv([r for r in originals if r["word_id"] in region], WORD_FIELDS), encoding="utf-8")
                (root / "input/captions.csv").write_text(_csv([r for r in captions if r["segment_id"] in segment_ids], ["segment_id", "text"]), encoding="utf-8")
                phase_ids = ids - set(slots) if phase == "skim" else ids & set(slots)
                # A skim can discover a split word straddling a suspect and a
                # confident neighbor. Do not review that same span a second time.
                covered = {ident for proposal in suggestions for ident in proposal['word_ids']}
                resolved = phase_ids & covered if phase == 'resolve' else set()
                targets = phase_ids - resolved
                if resolved:
                    done += len(resolved); reviewed.extend(sorted(resolved))
                if not targets:
                    progress(done, total, "Reviewing workspace")
                    continue
                protected = {ident for proposal in suggestions if resolved.intersection(proposal['word_ids'])
                             for ident in proposal['word_ids']}
                allowed = ids - protected
                (root / "input/allowed.txt").write_text(" ".join(r["word_id"] for r in originals if r["word_id"] in allowed), encoding="utf-8")
                (root / "input/targets.txt").write_text(" ".join(r["word_id"] for r in originals if r["word_id"] in targets), encoding="utf-8")
                (root / "input/required.txt").write_text(" ".join(r["word_id"] for r in originals if phase == "resolve" and r["word_id"] in targets), encoding="utf-8")
                progress(done, total, "Skimming unblanked words" if phase == "skim" else "Resolving numbered entries")
                (root / "out/result.csv").write_text(_csv([], FIELDS), encoding="utf-8")
                workspace = Workspace(root, cancel)
                workspace.targets = targets
                workspace.divided = divide
                # (a region kept its 300 s and 12 tool calls; the whole has those of every region it replaces, up to an hour and 60 calls)
                workspace.seconds, workspace.turns = (300, 12) if divide else (min(3600, 300 * regions), min(60, 12 * regions))
                workspace.output_bytes = max(1200, min(4000, (context_tokens - 4000) // 2))
                try:
                    proposals, _ = _phase(workspace, request, adapter, phase, allowed, context_tokens, diagnostic, "region%d" % i)
                    new_ids = {word for proposal in proposals for word in proposal['word_ids']}
                    suggestions = [proposal for proposal in suggestions if not new_ids.intersection(proposal['word_ids'])]
                    suggestions.extend(proposals)
                    # (_phase left the rows that keep Whisper's word on the workspace)
                    kept_rows = _replace_kept(kept_rows, workspace.kept, new_ids)
                    for ident in new_ids | {w for k in workspace.kept for w in k["word_ids"]}:
                        loose.pop(ident, None)
                    for ident, says in workspace.loose.items():
                        loose.setdefault(ident, []).extend(says)
                    proposed = {w for s in proposals for w in s["word_ids"]}
                    uncertain.extend(sorted(targets - proposed))
                except Exception as error:
                    safe = error if isinstance(error, LLMError) else LLMError("workspace-failed", "This workspace region could not be reviewed.")
                    if safe.code in ("cancelled", "source-changed", "settings-changed"):
                        raise safe
                    # Preserve already validated entries even if a later tool/HTTP
                    # step failed. Unseen entries alone remain failed/retryable.
                    proposals, seen, workspace.kept, workspace.loose = [], set(), [], {}
                    if workspace.ran:
                        try:
                            proposals, seen = _proposals(root, request, allowed, targets, kept=workspace.kept, loose=workspace.loose)
                        except LLMError:
                            workspace.kept, workspace.loose = [], {}
                    kept_rows = _replace_kept(kept_rows, workspace.kept, {w for p in proposals for w in p["word_ids"]})
                    # the rows that were written before the run broke are used as they stood: a leniency, told on their words
                    for ident in seen:
                        loose.setdefault(ident, []).extend(workspace.loose.get(ident, []))
                        loose[ident].append("the run ended with an error (%s) after this row was written; the row was used as it stood" % safe.say.rstrip("."))
                    new_ids = {word for proposal in proposals for word in proposal['word_ids']}
                    suggestions = [proposal for proposal in suggestions if not new_ids.intersection(proposal['word_ids'])]
                    suggestions.extend(proposals)
                    failed.extend(sorted(targets - seen))
                    why.update((ident, safe.say) for ident in targets - seen)
                    proposed = {word for proposal in proposals for word in proposal["word_ids"]}
                    uncertain.extend(sorted(targets - proposed))
                    if diagnostic:
                        diagnostic({"sentence_id": "region%d:%s" % (i, phase), "attempt": 13, "phase": phase,
                                    "word_ids": sorted(allowed), "state": "failed", "code": safe.code, "error": safe.say})
                done += len(targets); reviewed.extend(sorted(targets)); progress(done, total, "Reviewing workspace")
    cancel.check()
    proposed_ids = {ident for proposal in suggestions for ident in proposal['word_ids']}
    uncertain = sorted(set(uncertain) - proposed_ids)
    failed = sorted(set(failed) - proposed_ids)
    return {"schema_version": 1, "suggestions": suggestions, "uncertain_word_ids": uncertain, "failed_word_ids": failed,
            "kept": [k for k in kept_rows if not proposed_ids.intersection(k["word_ids"])],
            "failed_reasons": {ident: say for ident, say in why.items() if ident in failed},
            "allowances": {ident: says for ident, says in loose.items() if ident in proposed_ids | {w for k in kept_rows for w in k["word_ids"]}},
            "assessment": "partial" if failed else "suggestions" if suggestions else "kept_original",
            "method": "workspace-code", "task": "workspace", "reviewed_word_ids": reviewed,
            "words_reviewed": done, "words_total": total,
            "workspace": {"files": ["transcript.txt", "active.txt", "allowed.txt", "targets.txt", "required.txt", "suspects.csv", "words.csv", "captions.csv", "skim.csv", "review.py"],
                          "reasoning_requested": True, "isolated_python": True, "removed": True}}
