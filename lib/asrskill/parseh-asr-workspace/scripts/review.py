# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone workspace editor/checker. It checks structure, never accuracy.

All dependencies are from the standard library. Only save() writes a file:
it validates the entire CSV in memory before opening the existing result.csv.
Importing this module performs no file reads, so Parseh can reuse its validator.
"""
import argparse
import csv
import io
from pathlib import Path
import unicodedata

FIELDS = ["word_ids", "original", "replacement", "reason"]
# The fifth column says how sure the model is of the row, whether it changes the word or keeps Whisper's:
# "sure" or "unsure".  Answers without it are still read (older skills write four columns).
RATED = FIELDS + ["confidence"]
CONFIDENCE = ("sure", "unsure")
MAX_BYTES = 65536
PREVIEW_BYTES = 1200


def _unsafe(text):
    # Format characters such as Persian ZWNJ are valid source/replacement text.
    return any(unicodedata.category(char) in ("Cc", "Cs") for char in text)


def _csv(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=RATED)
    try:
        writer.writeheader(); writer.writerows(rows)
        text = stream.getvalue()
        size = len(text.encode("utf-8"))
    except (UnicodeError, csv.Error):
        raise ValueError("Result CSV contains invalid Unicode or fields.") from None
    if size > MAX_BYTES:
        raise ValueError("Result CSV exceeds the 64 KiB limit.")
    return text


def parse_csv(text):
    """Parse a bounded UTF-8 result with the exact required CSV header."""
    if not isinstance(text, str):
        raise ValueError("Result CSV must be UTF-8 text.")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeError:
        raise ValueError("Result CSV contains invalid Unicode.") from None
    if size > MAX_BYTES:
        raise ValueError("Result CSV exceeds the 64 KiB limit.")
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if reader.fieldnames not in (FIELDS, RATED):
            raise ValueError("Use the header word_ids,original,replacement,reason,confidence exactly.")
        rows = list(reader)
    except csv.Error:
        raise ValueError("Result CSV is malformed; check quoting and columns.") from None
    return rows


def _span(ids, words, captions, allowed, targets):
    if (not ids or len(ids) > 8 or len(set(ids)) != len(ids)
            or any(ident not in allowed or ident not in words for ident in ids)
            or targets is not None and not set(ids).intersection(targets)):
        raise ValueError("Use up to eight editable source IDs including a phase target.")
    members = [words[ident] for ident in ids]
    segment = members[0]["segment_id"]
    if segment not in captions or any(word["segment_id"] != segment for word in members):
        raise ValueError("An edit cannot cross caption boundaries.")
    ordered = [ident for ident, word in words.items() if word["segment_id"] == segment]
    first = ordered.index(ids[0])
    if ordered[first:first + len(ids)] != ids:
        raise ValueError("Use consecutive source IDs in their original order.")
    try:
        if any("source_index" in member for member in members):
            positions = [int(member["source_index"]) for member in members]
            if positions != list(range(positions[0], positions[0] + len(ids))):
                raise ValueError()
        text = captions[segment]
        bounds = [(int(word["char_start"]), int(word["char_end"])) for word in members]
        if any(not 0 <= start < end <= len(text) or text[start:end] != word["original"]
               for (start, end), word in zip(bounds, members)):
            raise ValueError()
        if any(bounds[i][1] > bounds[i + 1][0] for i in range(len(bounds) - 1)):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError("Source offsets or adjacency do not match the read-only caption.") from None
    return segment, bounds[0][0], bounds[-1][1], text[bounds[0][0]:bounds[-1][1]]


def validate_rows(rows, words, captions, allowed, targets=None, required=(), complete=False):
    """Return (checked_rows, seen_IDs), or raise ValueError. No file access.

    Word/caption mappings are immutable source evidence. required controls only
    completeness; targets controls which editable spans belong to this phase.
    """
    allowed, required = set(allowed), set(required)
    targets = None if targets is None else set(targets)
    if type(complete) is not bool or not required <= allowed:
        raise ValueError("Required-entry metadata is invalid.")
    checked, seen = [], set()
    for number, row in enumerate(rows, 1):
        try:
            if number > len(allowed):
                raise ValueError("Too many result rows for these editable words.")
            if (not isinstance(row, dict) or set(row) not in (set(FIELDS), set(RATED))
                    or any(not isinstance(value, str) for value in row.values())):
                raise ValueError("Every row must contain the required text fields: word_ids, original, replacement, reason and confidence.")
            if any(_unsafe(value) for value in row.values()):
                raise ValueError("Fields cannot contain control characters or invalid Unicode.")
            ids = row["word_ids"].split()
            _, _, _, original = _span(ids, words, captions, allowed, targets)
            if seen.intersection(ids):
                raise ValueError("Source IDs cannot repeat or overlap another result row.")
            if row["original"] != original:
                raise ValueError("Original text must match its exact source span.")
            replacement, reason = row["replacement"], row["reason"]
            if not replacement.strip() or len(replacement) > min(200, max(24, 3 * len(original))):
                raise ValueError("Replacement must be nonempty and fit the short-span limit.")
            if len(reason) > 500:
                raise ValueError("Reason must be no longer than 500 characters.")
            rating = row.get("confidence", "").strip().lower()
            if rating not in ("",) + CONFIDENCE:
                raise ValueError("Confidence must be sure or unsure.")
            punct = lambda text: "".join(char for char in text if unicodedata.category(char).startswith("P"))
            if punct(original) != punct(replacement):
                raise ValueError("Keep the original punctuation in the replacement.")
            seen.update(ids)
            checked.append(dict(row, word_ids=" ".join(ids), **({"confidence": rating} if "confidence" in row else {})))
        except (KeyError, TypeError):
            raise ValueError("Row %d: Read-only source metadata is invalid." % number) from None
        except ValueError as error:
            raise ValueError("Row %d: %s" % (number, error)) from None
    _csv(checked)  # Enforce the same limit for save() and server validation.
    if complete and not required <= seen:
        raise ValueError("Required entries are missing; include unchanged originals when uncertain.")
    return checked, seen


def read(name):
    with Path("input", name + ".csv").open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _context():
    source_words = read("words")
    words = {row["word_id"]: row for row in source_words}
    if len(words) != len(source_words):
        raise ValueError("Read-only source IDs are duplicated.")
    suspects = {row["word_id"]: row for row in read("suspects")}
    captions = {row["segment_id"]: row["text"] for row in read("captions")}
    allowed = Path("input/allowed.txt").read_text(encoding="utf-8").split()
    target_file, required_file = Path("input/targets.txt"), Path("input/required.txt")
    targets = target_file.read_text(encoding="utf-8").split() if target_file.exists() else allowed
    required = required_file.read_text(encoding="utf-8").split() if required_file.exists() else []
    return words, suspects, captions, allowed, targets, required, required_file.exists()


def show(offset=0, count=20):
    """Print bounded source evidence in order; this does not judge accuracy."""
    if type(offset) is not int or offset < 0 or type(count) is not int or not 1 <= count <= 20:
        raise ValueError("Use offset >= 0 and count from 1 to 20.")
    words, suspects, _, allowed, targets, _, _ = _context()
    print("Active text:")
    active = Path("input/active.txt").read_text(encoding="utf-8")
    print(active.encode("utf-8")[:1200].decode("utf-8", "ignore"))
    if len(active.encode("utf-8")) > 1200:
        print("Context clipped; the complete region is in input/active.txt.")
    print("Allowed words %d–%d of %d:" % (offset, min(offset + count, len(allowed)), len(allowed)))
    for ident in allowed[offset:offset + count]:
        word = words[ident]
        print(ident + " | " + word["original"] + (" | phase target" if ident in targets else " | adjacent context"))
        hint = suspects.get(ident)
        if hint:
            print("Blank " + hint["slot"] + " | " + hint["whisper_hints"])
            print("Context: " + hint["context"])
    skim = read("skim")
    if skim:
        print("Tentative first-pass edits in these captions:")
        for row in skim:
            if any(ident in words for ident in row["word_ids"].split()):
                print(row["original"] + " -> " + row["replacement"])


def _preview(rows, words, captions):
    edits = {}
    for row in rows:
        if row["original"] == row["replacement"]:
            continue
        segment, start, end, _ = _span(row["word_ids"].split(), words, captions, words, None)
        edits.setdefault(segment, []).append((start, end, row["replacement"]))
    preview, remaining = [], PREVIEW_BYTES
    for segment, changes in edits.items():
        text = captions[segment]
        for start, end, replacement in sorted(changes, reverse=True):
            text = text[:start] + replacement + text[end:]
        raw = text.encode("utf-8")
        fragment = raw[:remaining].decode("utf-8", "ignore")
        preview.append({"segment_id": segment, "text": fragment, "clipped": len(raw) > remaining})
        remaining -= len(fragment.encode("utf-8"))
        if remaining <= 0 or len(raw) > remaining + len(fragment.encode("utf-8")):
            break
    return preview


def check(require_complete=False):
    """Print/return a bounded report for result.csv without changing any file."""
    report = {"structurally_valid": False, "valid": False, "complete": False,
              "missing_required_ids": [], "errors": [], "rows": 0, "changed_rows": 0, "unrated_rows": 0, "unsure_rows": 0, "preview": []}
    try:
        if type(require_complete) is not bool:
            raise ValueError("require_complete must be True or False.")
        words, _, captions, allowed, targets, required, has_required = _context()
        path = Path("out/result.csv")
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Result CSV exceeds the 64 KiB limit.")
        rows = parse_csv(path.read_text(encoding="utf-8"))
        rows, seen = validate_rows(rows, words, captions, allowed, targets, required)
        report.update(structurally_valid=True, rows=len(rows), changed_rows=sum(row['original'] != row['replacement'] for row in rows),
                      unrated_rows=sum(not row.get('confidence') for row in rows), unsure_rows=sum(row.get('confidence') == 'unsure' for row in rows),
                      missing_required_ids=[ident for ident in required if ident not in seen], preview=_preview(rows, words, captions))
        report['complete'] = has_required and not report['missing_required_ids']
        if require_complete and not has_required:
            report['errors'].append('Required-entry metadata is missing; completeness cannot be checked.')
        elif require_complete and not report['complete']:
            report['errors'].append('Required entries are missing; include unchanged originals when uncertain.')
        report['valid'] = not report['errors']
    except (OSError, UnicodeError, csv.Error, KeyError, TypeError):
        report['errors'] = ['Workspace input or result files are missing, unreadable or invalid.']
    except ValueError as error:
        report['errors'] = [str(error)]
    print('CSV structure: %s; required entries: %s. This does not judge linguistic accuracy.' % (
        'valid' if report['structurally_valid'] else 'invalid', 'complete' if report['complete'] else 'incomplete'))
    print('%d rows; %d proposed changes; %d marked unsure.' % (report['rows'], report['changed_rows'], report['unsure_rows']))
    if report['unrated_rows']:
        print('%d rows have no confidence: give every row sure or unsure (unchanged rows too: sure says Whisper\'s word is right).' % report['unrated_rows'])
    if report['missing_required_ids']:
        print('Missing required IDs: ' + ' '.join(report['missing_required_ids'][:80]))
    for message in report['errors']:
        print(message)
    for item in report['preview']:
        print('Preview ' + item['segment_id'] + ': ' + item['text'] + (' [clipped]' if item['clipped'] else ''))
    return report


def save(rows, require_complete=False):
    """Save [(word_ids, replacement, reason, confidence), ...] only after full validation.  The confidence,
    "sure" or "unsure", may be left out of a row."""
    words, _, captions, allowed, targets, required, has_required = _context()
    if require_complete and not has_required:
        raise ValueError('Required-entry metadata is missing; completeness cannot be checked.')
    prepared = []
    for number, entry in enumerate(rows, 1):
        if number > len(allowed) or not isinstance(entry, (list, tuple)) or len(entry) not in (3, 4) or any(not isinstance(value, str) for value in entry):
            raise ValueError('Use bounded (word_ids, replacement, reason, confidence) text tuples.')
        id_text, replacement, reason = entry[:3]
        _, _, _, original = _span(id_text.split(), words, captions, set(allowed), set(targets))
        prepared.append(dict(word_ids=id_text, original=original, replacement=replacement, reason=reason, **({"confidence": entry[3]} if len(entry) == 4 else {})))
    prepared, _ = validate_rows(prepared, words, captions, allowed, targets, required, complete=require_complete)
    text = _csv(prepared)
    # No rename/temp file: the isolated runtime permits writing only this file.
    with Path('out/result.csv').open('w', encoding='utf-8', newline='') as file:
        file.write(text)
    print('Result CSV saved after validation.')
    return check(require_complete=require_complete)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check workspace CSV structure/source spans, not linguistic accuracy.')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--show', action='store_true', help='Show bounded immutable source evidence.')
    action.add_argument('--check', action='store_true', help='Check the current out/result.csv without modifying it.')
    parser.add_argument('--complete', action='store_true', help='Also require every ID in input/required.txt.')
    args = parser.parse_args()
    if args.complete and not args.check:
        parser.error('--complete requires --check')
    if args.show:
        show()
    else:
        raise SystemExit(0 if check(require_complete=args.complete)['valid'] else 1)
