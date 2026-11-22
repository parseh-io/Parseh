# Word times through transcript editing

*Implementation design for a0.4.3 — 2026-09-30. This responds to TO-DO §7.26
and the a0.4.3 word-timestamps prompt. The owner approved the choices below:
one Whisper pass, Parseh-created transcriptions only, int8 alignment networks,
no retained audio, a 640 MiB local undo-history ceiling, installed aligners on
by default with a remembered switch, and both tidy cues as an editor choice.*

## Scope and boundaries

The transcript panel remains Parseh's interchange format: a clock line followed
by caption text. The existing checker parser/writer remains the only parser and
writer used by the add flow, the draft, prompts, and the checker. Word times
are additional state behind that panel, not a second subtitle format and not an
editor for a video already added to the library.

Whisper's returned segments remain the captions displayed in the panel. For
Whisper-only capture, rc1 uses one `word_timestamps=True` transcription pass
and accepts that pass's small segment-timing difference from the former
caption-only invocation. Word times are collected independently of caption
boundaries.
When an optional ONNX aligner is installed, Whisper keeps its present
invocation and segment boundaries; the aligner supplies only the word-time
track afterwards. WhisperX is out of scope.

A **word atom** is the smallest timed speech unit: a non-space token for a
spaced language and a grapheme-like character atom for Chinese and Japanese.
Marks stay with their base character and ZWNJ stays inside its word.
Punctuation and whitespace are text decoration, not separately spoken atoms.
A caption boundary is immediately before its first word atom, so its start
comes from that atom unless a person explicitly overrides it. A tag with no
speech atom is the exceptional, visibly marked case.

## One authoritative model

The source of truth is an ordered editable tape of word atoms plus a partition
of that tape into captions. Captions do not own independent copies of word
times.

    {
      "format": "parseh-wordtimes/1",
      "clock": "video",
      "language": "fa",
      "capture": {
        "source": "aligner",
        "model": "parseh/aligner-fa@<commit>",
        "whisper_model": "large-v3-turbo"
      },
      "atoms": [{
        "id": "w:<job>:000042",
        "surface": "می‌گوید",
        "key": "comparison form",
        "start": 12.341,
        "end": 12.782,
        "time_source": "aligner",
        "score": 0.96,
        "origin": "capture"
      }],
      "captions": [{
        "id": "c:<stable-id>",
        "first": 38,
        "last": 45,
        "text": "the exact current caption body",
        "chapter": null,
        "start_pin": null
      }],
      "retired_atoms": [],
      "revision": 17,
      "panel_sha256": "..."
    }

The caption range has an inclusive first and exclusive last index. Captions
partition live atoms in displayed order: no live atom is in two captions or in
neither. Retired atoms were explicitly deleted; they exist only for
undo/history and are never rendered.

Caption text is the person's exact editable panel text. Atom-to-character spans
say which speech atoms occur in it, so punctuation and spacing can change
without inventing or losing speech atoms. A reducer validates every
transaction: canonical caption text must render to the panel, and atom order
must agree with its words.

Atom IDs are identities, not positions or words. Captured atoms get
deterministic IDs from job token and capture order. Atoms introduced in a text
transaction get deterministic IDs from its persisted transaction ID and local
ordinal. Repeated text such as “نه نه نه” is never an identity.

### Caption-start resolver

For a caption whose first atom is a:

1. Its start pin, if present, wins and is **person** provenance.
2. Otherwise a.start wins and is **aligner** or **Whisper** provenance.
3. Otherwise an interpolation attached to a is **worked out** provenance.
4. With no usable neighbour, a supplied panel/LLM time is an explicit
   **guess**.

The first two cases are normal. Tidy, split, LLM output and parser-provided
times must not replace a word-derived start with a proportional-caption guess.

The panel requires strictly rising starts. Import retains full precision and
rejects or explicitly annotates malformed/non-monotonic word tracks. If two
genuine word starts collide after panel precision, serialization may add only
the minimum 0.001-second display epsilon, recorded as display-adjusted; it
must never call that a measured time. A real faster-whisper fixture must show
whether this is needed before approval.

## Rules for every operation

In rc1 the browser keeps an exact local editing projection for the life of the
open editor and sends its current captions, pins and global shift to the pure
server reducer whenever it asks to tidy, accept an LLM answer or finish. The
server returns a fresh canonical projection, so it owns matching and boundary
resolution; the browser does not invent a second matching algorithm. Full
cross-tab revision transactions and resuming uncommitted edits after a reload
remain follow-up work, not an rc1 promise.

| Operation | Text rule | Time rule |
| --- | --- | --- |
| Capture/import | Use the segment text and times returned by the one Whisper word-timestamp pass. | Create capture atoms from returned words; remap starts and ends to video time for YouTube. |
| Open/reopen | Parse panel as today. | Reloading before **Use this transcript** starts again from the held capture tape; it does not claim to restore uncommitted pins or undo history. |
| Plain paste/SRT | Keep current parser output. | No capture tape: starts are honest guesses; no adoption unless explicit later alignment creates a tape. |
| Type/paste caption | Preserve canonicalised supplied text. | Order-match new local atoms to old ones; matches retain identity/time, new atoms are flagged interpolation or guesses. |
| ✂ split | Split at a legal atom boundary, refusing an empty speech side. | New caption starts at first moved atom, never halfway to next caption. |
| Join | Concatenate using the current panel rule; concatenate ranges. | Joined caption keeps first start; a pin on former second boundary is a conflict, never silently lost. |
| Delete | Explicitly remove text and retire its atoms. | Makes no new time; undo restores exact atoms, provenance and pins. |
| Add empty | Add empty editable text as now. | Makes no timing claim until it contains speech atoms. |
| Typed start/nudge | Changes no text. | Make a start pin on first atom; do not falsify the recorded times of every word in a caption. |
| Shift all | Changes no text. | Move every live atom start/end and every pin by delta; reject a shift before zero. |
| Tidy | Accept only output passing existing word-order invariant. | Proposed starts resolve from first atoms; pins survive or report conflict before change. |
| LLM answer | Parse by existing panel parser and retain current review. | Returned times are search hints/fallback guesses, never authority over matched atoms or pins. |
| Aligner | Changes no caption text. | Replace eligible captured Whisper times only; never overwrite pins or derived/person atoms. |
| Undo/redo | Restore exact prior/next model state. | Restore exact timing state, not a fresh match. |
| Finish add | Serialize existing panel format. | Adopt only for the matching job and canonical panel hash. |

a0.4.3 has no caption-reordering operation. Reordering captured speech would
put the timeline out of order and is not required. If it is ever added, it is
an explicit content feature, never a timing operation.

### Manual timing work

A typed or nudged start is evidence about one boundary, not evidence that
every word in the caption was heard later. The pin travels with the atom that
was first when it was made.

If an automated operation would make that atom interior to a caption, or a
content edit cannot match/remove it unambiguously, the reducer returns a
conflict. The UI must offer:

* retain it as a caption boundary;
* move the pin to a specifically shown surviving boundary; or
* explicitly discard the pin.

Tidy, LLM output and alignment therefore cannot silently undo a correction.
The same rule applies to changing language or replacing the whole panel: held
state becomes stale and needs an explicit choice.

## Matching after a content edit

Structural operations carry atom IDs directly. Typing, paste, tidy and LLM
output use the same order-preserving matcher.

### Tokenisation and comparison

The reducer owns tokenisation; the browser gets spans/state rather than a
second tokeniser.

* In spaced languages, an atom is a non-space run. Punctuation attaches to an
  adjacent atom for rendering but is absent from its comparison key.
* In unspaced languages, it is a base character with combining marks,
  variation selectors and joiner sequence. Spaces never create atoms; CJK
  punctuation is decoration.
* The normal key applies NFC, Lang.strip, the existing
  check_annotations.norm whitespace rule, and languages.fold for Turkish
  dotted/dotless I.
* The alignment key also drops tatweel, folds Arabic ي/ى to Persian ی and
  Arabic ك to Persian ک, maps configured native digits to Latin digits, and
  treats ZWNJ, normal space and word-joining hyphen as equivalent in a fused
  key. Stored/displayed text is never changed.
* Normal/fused keys can match “می‌گوید” to “می گوید”. Written numbers match
  digits only through tested per-language number tables; unknown spellings are
  not guessed into a match.

Arabic/Persian compatibility and number tables must be test fixtures, not
editor-event conditionals.

### Algorithm and confidence

First find ordered exact/compatible anchors in the changed caption and
immediate time neighbours. Unique anchors bound small gaps. Align each gap with
bounded edit-distance dynamic programming. This supports a local correction,
insertion, deletion, punctuation change and merged/split word without a
quadratic scan of an hour-long transcript.

For a whole LLM panel, current captions and provisional starts bound windows.
Rare ordered n-gram anchors divide the work. Repeated words are never global
anchors alone; no fourth “no” may borrow the first one's time. An unanchored
window becomes unmatched rather than a plausible but false association.

Initially accept a non-exact substitution only when compatible anchors enclose
it and bounded alignment has one optimum. Other substitutions, insertions and
deletions remain unmatched. Exact window sizes and substitution threshold must
be measured with fixtures before they are frozen.

### Words not heard

A new/corrected unmatched atom gets time in this order:

1. Between two timed neighbours, allocate interval by atom size: provenance
   interpolated.
2. With one neighbour, use bounded local speech-rate estimate when available:
   provenance estimated.
3. With neither, retain panel/LLM time as guess.

Such atoms are never upgraded to Whisper/aligner just because of a later edit.
Where equivalent seams exist, a captured atom wins over an interpolated one.

## Clock, provenance and visibility

All held words use **video clock**.

* For YouTube, word starts and ends pass through sttpanel.remap with the same
  marks as segments. A word wholly in a dropped stall is dropped with segment.
* A film starts at decoded media start, so its times already are video time.
* Shift all moves the tape and pins on this clock. Nudge/typed start changes
  only its boundary pin.

Atoms carry aligner, whisper, interpolated, estimated or guess and, where
meaningful, a confidence score. A boundary reports person when pinned. The
editor should say: “42 starts from recording (38 aligner, 4 Whisper); 3 worked
out; 2 person-set; 1 guess.” Rows need a source badge and inspectable list of
word start/end/source/score. A guess must say it is a guess.

Silence after a word belongs to no atom. Captions still end at the next caption
start. The editor offers both tidy cues: the existing text-cue heuristic and a
recording-pause cue where held words provide a genuine inter-word gap. Both
derive a resulting boundary from its first word whenever one exists; neither
creates a proportional timestamp in such a stretch.

## Persistence and adoption

There must not be one list in the worker, a differently edited list in the
page, and a third in wordtimes.json.

1. A completed job holds one document in youtube/videos/.words/<job>.json,
   implemented by wordtimes.py beside wavefile.py. It contains raw capture
   tape and editable state together.
2. Browser receives a projection plus job and panel hash. It sends its current
   caption partition, pins and global shift to the same pure reducer. The held
   document remains the raw capture until **Use this transcript** commits the
   matching canonical panel.
3. Reloading the uncommitted editor reprojects the held capture for the current
   panel; rc1 intentionally does not persist its draft pins or undo history.
   A changed textarea/source/language is freshly matched to raw capture tape,
   never silently attached as a different transcript.
4. Add request carries job and hash. Only that exact canonical panel permits
   adoption as wordtimes.json; write/move canonical state, never reconstruct.
   On mismatch add video but say why no word times were adopted.
5. Cancellation, failed/abandoned jobs and startup sweep drop .words holds as
   waveform holds are dropped. Dot directories are never listed, served,
   bundled or backed up. Adopted wordtimes.json is bundled/restored beside
   waveform.json with a FORMAT row and equivalent restore rule.

### After the add: move text (a0.6.3)

The first door after the add that reads and writes an adopted wordtimes.json is
the player's **move text** (`youtube/lib/reflow.py`, TO-DO §7.29). Moving a
boundary between two captions says no new word and loses none, so it is a pure
re-partition of the tape: `wordtimes.repartition` keeps every atom, its id and
its time, re-cuts `captions` to the transcript as written, and counts no
revision, so moving the boundary back (Undo) gives the document back byte for
byte. Where the panel's words are no longer the tape's (an edit made by a door
that does not maintain the tape), it falls back to `sync`, which matches what it
can and marks the rest as not heard.

The caption that now begins with another word starts by this document's own
resolver: the word's pin, else its heard start (`time_source` whisper/aligner; an
interpolated, estimated or guessed time is not heard). The share-of-letters
estimate is kept only for a word with no heard time, a video without the file, a
file that does not line up with the captions, or a heard time outside the two
neighbouring starts (the timings sheet moved them since). `reflow.marks` also
reads the tape for pauses of at least `tidy.AUDIO_PAUSE_LEAST` between heard
words, which the player shows in place of full stops for a transcript that has
none. The timings sheet (`captimes.py`) still leaves the file as it was.

### History

The editor retains exact in-memory snapshots for undo/redo, including timing
projection and pins. The owner chose a **640 MiB per-editor** ceiling, with no
arbitrary transaction count; the oldest undo snapshots are discarded once that
ceiling is reached. Capture state remains held on disk, while draft history and
pins become durable only when the editor accepts its panel.

## Optional aligner

Published namespaces are parseh/aligner-zh, -ja, -hi, -ar, -fa, -tr, -es, -de,
-fr, -it and -en. Rc1 records their immutable commits, hashes and sizes in
`lib/alignerpins.py`; it fetches every file through that immutable URL and
checks each hash before installing it. A namespace alone is not a reproducible
pin.

An installed aligner runs in the current worker after Whisper releases its
model. It uses published metadata/preprocessing, never hard-coded blank IDs or
delimiters, and writes capture atom times before job completion. It never
changes Whisper captions or panel text. It replaces only unpinned atoms still
identifiable as capture atoms. Aligner evidence is preferred to Whisper
evidence, but neither outranks a person pin.

The published distribution contains `model.int8.onnx`, not an fp32 runtime
artifact. Its conversion tooling tests int8 against fp32 before publication;
that is a synthetic parity check, not a human-speech accuracy guarantee. The
default proposed for rc1 is therefore installed **int8 only**, with no
unimplemented fp32 selector.

## Answers to Q1–Q12

| Question | Decision |
| --- | --- |
| Q1 | Capture tape plus current caption partition is authoritative; stable atom IDs carry identity; panel is a hash-bound projection; acceptance persists one adopted document. |
| Q2 | Structural changes carry ranges; content changes use one matcher. Broader differential/property testing remains a follow-up after rc1. |
| Q3 | Language-aware atoms, conservative ordered anchors, bounded local alignment, and honest provenance for unmatched content. |
| Q4 | Live interpolated, estimated or guess atoms; never represented as audio evidence. |
| Q5 | Boundary pins; shift all moves tape/pins; orphaning operation stops for a choice. |
| Q6 | Persist source/score. Resolver preference: person, aligner, Whisper, interpolation, estimate/guess; display category counts. |
| Q7 | Video time only; remap YouTube words through marks; films need no remap; shift all deliberately moves stored times. |
| Q8 | A held capture document is matched to language and canonical panel hash, then adopted only on that exact final hash. Draft edits persist for the open editor, not across reload. |
| Q9 | Do not keep capture PCM after initial job in rc1. Aligner runs before edit; later edits match existing tape. Audio re-alignment needs new privacy/retention decision. |
| Q10 | Persist word ends for inspection/future use; caption end is next start; text-cue and recording-pause tidy modes are both available. |
| Q11 | Exact browser undo/redo snapshots, transparently capped at the owner-selected 640 MiB with no arbitrary transaction count. |
| Q12 | Pure-module and route/browser tests cover the shipped rules. Generated operation sequences, differential matching and cross-tab trials are retained as the next verification target. |

## Proof plan before wiring

Build the pure module before storage, routes or editor changes. Generate valid
states and random sequences of split, join, delete, nudge, typed start, shift,
tidy-shaped regrouping, content replacement, undo and redo across all eleven
language forms: spaced, CJK character atoms, RTL marks, ZWNJ, repeated words
and tags.

Prove:

1. Structural operations preserve live atom order and multiplicity.
2. Caption beginning on timed atom resolves from it unless pinned.
3. Pins are never removed/reassigned without conflict and explicit choice.
4. Starts rise strictly or operation is refused/explicitly display-adjusted.
5. Undo→redo, redo→undo and serialize→reopen restore byte-identical state.
6. Replaying same transaction/revision is idempotent.
7. Direct structural carrying equals matching its output text to prior tape.
8. Final panel hash, parsed captions and adopted state agree.

Fixtures need real faster-whisper words, failed word pass, words remapped around
YouTube stalls, unaligned captions, Persian/Arabic keyboard variants, CJK
punctuation and controlled LLM rewrites. Browser trials then cover every editor
action, reload/reopen, two tabs, pin conflicts, provenance, cancellation/sweep
and adoption.

## Confirmed owner decisions

Whisper uses one word-timestamp pass where no aligner is selected; only
Parseh-created transcriptions carry a tape; published int8 aligners are the
only download; an installed one is on by default but may be switched off and
remembered on this browser; capture PCM is deleted after the job; and the
editor exposes both text-cue and recorded-pause tidy modes. Future re-alignment
of a changed transcript against retained sound remains deliberately out of
scope.
