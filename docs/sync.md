# Sync between computers: the contract

From a0.7.0 several Parseh may keep one shelf: every computer with a full install
holds its own copy and works alone, and paired installs bring each other up to date,
peer to peer, when both are on and can reach each other. This page is the contract
that sync is built on. It lists every store Parseh writes, which unit each one
is, which rule each unit follows, and which settings follow the person and which
stay with the device. It also gives the programming interfaces of the foundations
(lane W0) that the other lanes build on: pairing and transport (A), the exchange
(B), the rules (C), jobs (D) and the pages (E).

Parseh has **one user**. Two computers editing the same thing at the same time is a
mistake, not a way of working, so sync never merges two versions. It makes sure
nothing is lost without a word. It asks only when both sides really changed, and it
always leaves a way back to what a choice threw away.

## The rules

| rule | for | what happens |
|---|---|---|
| **choice** | most units | Changed on one side: the change goes everywhere, with no question. Changed on both sides since they last agreed: sync stops for that unit and asks which version to keep, this computer's or the partner's. Nothing is merged. What the choice throws away is given back as a diff file. |
| **progress** | an exercise's schedule | Never asked. Exercises studied on different computers simply combine. When the same exercise was studied on both, the state with the newest latest answer wins, judged by the answers' own times. |
| **latest** | a reading place | Never asked. The place set last wins. The reader already asks whether to jump to another device's place. |
| **additions** | an entry of a list | Each side gets the other's: a clip, a Review-later flag, an Anki card, the notes the Anki store has seen. |
| **immutable** | media nobody edits | Named by the hash of its content and copied whole. It cannot conflict. |

The same three rules apply to every unit, whatever its rule above:

- **Deletions are always asked.** A deletion leaves a tombstone in the change log,
  and the tombstone stays until the question is answered and every partner has it.
- **Every version sync replaces or deletes is kept for one day.** This covers an
  incoming change, a choice, an answered deletion and "make identical".
- **A unit open in an editor is never written by sync,** and a unit that sync is
  writing cannot be opened in an editor.

**Never synced:** caches, `.tmp`, built pages and PDFs, runtimes, models,
dictionaries, anything a device can fetch or build again, and this device's own
settings.

## The inventory

The rows below were found by reading the code's write paths (`os.replace`,
`open(…, "w")`, `storeguard`, `pathlock`, `rmtree`, `unlink`) on 2026-11-24, at
a0.7.0's opening (`c21ca0f`). The column "kind · id" is the unit's kind and its
id in `lib/syncunits.py`. Ids name a unit by its place on the shelf and never by
a path on one disk, so two installs call the same thing by the same name.

### Books: `books/<language folder>/<slug>/`

| store | written by | unit (kind · id) | rule |
|---|---|---|---|
| the source: `main.tex`, the chapters' `.tex`, `book.json`, `reading.json`, `timings.json`, `review-corrections.json`, `making.json`, `ASKS.md` / `NOTES.md` / `AGENTS.md` / `CLAUDE.md`, `original/`, `annot/`, `source/`, the recording and transcripts in `audio/` | `lib/texwrite.py` `_write`, `lib/structure.py`, `lib/bookmeta.py`, `lib/draft.py`, `lib/reading.py` `save`, `lib/making.py`, `lib/timestamp.py` (a subprocess), and `serve.py` (`set_book_meta`, `set_variety`, `_subtimes`, `_save`, the narration routes) | **the book's source, together** · `book:<folder>/<slug>` | choice |
| a note: `markdown/<language>/<id>/` (`source.md`, `meta.json`, `images/`, `audio/`) | the studio store, through `markdown/app/notes.py` | `note:book/<folder>/<slug>/<language>/<id>` | choice |
| built: `reader/`, `main.pdf` and LaTeX's other output files at the top, `review.json`, `review.html`, a note's `build/` | tex2html, `lib/bookbuild.py`, `lib/timestamp.py` | — | never (it is rebuilt) |
| hidden: `.reader-key`, `.build-key`, `.claude/`, `.agents/`, the `*.tmp` and `*.part` files | the builds, `lib/making.py` (an agent's skills) | — | never |
| `books/.trash/` | `lib/books.py` `trash` | — | never (a deletion travels as a tombstone) |

### Videos: `youtube/videos/<language folder>/<id>/`

| store | written by | unit | rule |
|---|---|---|---|
| **the video's own edited files, together:** `video.json`, `annotations.json` (the glosses and chunks), `transcript.txt`, `wordtimes.json`, the film `media.<ext>` and `media-orig.<ext>` | `youtube/lib/ytpages.py` `edit_meta` and add, `annwrite.write`, `captimes.move`, `reflow._commit`, `wordtimes._write`, `filmdoor.receive`, `filmkind`, `serve.py` `set_variety` | `video:<folder>/<id>` | choice |
| a note: `markdown/<language>/<id>/` | the studio store; `captimes._move_notes` rewrites a note's `source.md` directly | `note:video/<folder>/<id>/<language>/<id>` | choice |
| `waveform.json`, `parts/` (an older layout) | `wavefile.write` | — | never (it is rebuilt from the media) |
| `<folder>/.pending-transcriptions/`, `.waveforms/`, `.words/`, `.incoming/`, `.staging-*`, `.trash/` | `lib/asrpending.py`, `wavefile`, `wordtimes`, `filmkind`, `ytpages` | — | never (working files of this device) |

### The studio: `markdown/library/<language folder>/<id>/`

| store | written by | unit | rule |
|---|---|---|---|
| **a studio document:** `source.md`, `meta.json`, `images/`, `audio/` (and the older `_prompt.md`) | `markdown/app/store.py`: `_create`, `_save_text`, `_write_source`, `_write_meta`, `save_image`, `save_audio`, `delete_audio`, `_copy_in`, `import_library`, `delete` | `doc:<folder>/<id>` (`doc:<id>` for a document from before languages, sitting directly in `library/`) | choice |
| `build/`, `.seeded-*` | `markdown/app/server.py` `build_pdf`, `seed_example` | — | never |
| `markdown/open/<session>/` (a file opened from the computer) | `markdown/app/openfile.py` | — | never (a working copy of this device) |
| `markdown/latex/` (the drawings of the LaTeX blocks) | `lib/latexdraw.py`, `lib/latexbatch.py` | — | never (rebuilt from the blocks) |

### The decks: `exercises/<language folder>/<deck>/`

| store | written by | unit | rule |
|---|---|---|---|
| `deck.json` | `markdown/app/decks.py` `_write_json` / `_write_bytes` | **a deck's options** · `deck:<folder>/<deck>` | choice |
| `items/<id>.json` **and the pictures and recordings it names** (`images/`, `audio/`) | `decks.add_item`, `update_item`; `_remove` unlinks it | **a deck's exercise** · `item:<folder>/<deck>/<id>` | choice |
| `schedule/<id>.json` | the answers (`srs`, through `decks`) | **an exercise's progress** · `progress:<folder>/<deck>/<id>` | progress |
| a picture or recording that no exercise names | `decks` | `deckfile:<folder>/<deck>/images/<name>` | immutable |
| `checkout.json` | `decks` (the phone's checkout) | — | never (this device's) |
| `exercises/.trash/` | `decks._to_trash` | — | never |

### The clip tray, Review later, the Anki store

| store | written by | unit | rule |
|---|---|---|---|
| `clips/<name>` with `clips/<name>.json` | `lib/clips.py` `_place`, `_write_json`, `delete` | `clip:<name>` | additions (deletions asked) |
| Review later: `later.items.<id>` inside `config/prefs.json` | `lib/later.py` `apply_ops`, through `prefs._write` | `later:<id>` | additions (it already keeps tombstones for 90 days) |
| `youtube/anki/<folder>/<deck>/deck.json` | `youtube/lib/anki_store.py` `write_json` | `ankideck:<folder>/<deck>` | choice |
| `…/cards/<id>.json` | `anki_store.add_card`; `sync_apkg.retire_card` moves a card to `deleted/` and `unretire` moves it back | `card:<folder>/<deck>/<id>` | additions |
| `…/media/<file>` | `import_apkg.extract_media`, the card writers | `ankimedia:<folder>/<deck>/<file>` | immutable |
| `youtube/anki/notetypes.json` | `youtube/lib/notetypes.py` `capture` | `ankinotetypes:` | choice |
| `youtube/anki/seen.json` (the notes ever seen in Anki) | `sync_apkg.save_seen` | `ankiseen:` | additions (a union) |
| `…/deleted/`, `youtube/anki/inbox/`, `youtube/anki/build/` | `sync_apkg`, the upload routes, `anki_export.build_deck` | — | never (a retired card travels as the card's tombstone) |

### Settings: `config/*.json`, key by key

**Personal** settings follow the person, one key at a time, as units. **This
device's** settings never sync. Settings a page keeps in the browser are this
device's by construction, because they never reach the server: the zoom, which
levels are open, the side-by-side layout, a page's own theme switch.

| file | key | label | unit | rule |
|---|---|---|---|---|
| `prefs.json` (`lib/prefs.py`, through `storeguard`) | `settings.bk_rate`, `bk_gap`, `bk_skip`, `bk_stopbnd`, `bk_cont`, `parseh_theme` | personal | `setting:<key>` | choice (only the value is compared, not its `at` or `by`) |
| | `settings.bk_lvl:<language>:<level>` (a level's name) | personal | `setting:bk_lvl:…` | choice |
| | any other key under `settings` | — | — | `prefs` refuses to write such keys |
| | `places.<reader path>` | personal | `place:<path>` | latest |
| | `later.items.<id>` | personal | `later:<id>` | additions |
| `prompts.json` (`lib/prompts.py`) | `prompts[]`, one per `id` | personal | `prompt:<id>` | choice |
| | `moved` | personal | `setting:prompts.moved` | choice |
| | `unread` (rows this install could not read) | this device's | — | never |
| `latex.json` (`lib/latexthemes.py`) | `themes[]`, one per `name` | personal | `latextheme:<name>` | choice |
| | `default`, `timeout` | personal | `setting:latex.default`, `setting:latex.timeout` | choice |
| | `format` | the file's own | — | — |
| `analysis.json` (`lib/analysisconfig.py`) | `lookup`, `chunking`, `evidence` | personal (a choice for an analyzer this computer does not have falls back, as it already does) | `setting:analysis.<key>` | choice |
| `speech.json` (`lib/speechconfig.py`) | `second_pass` | personal | `setting:speech.second_pass` | choice |
| | `models_by_language.<language>` | personal (the models themselves are fetched again on each computer) | `setting:speech.model.<language>` | choice |
| | `format_version` | the file's own | — | — |
| `languages.json` (`lib/languages.py` `write_store`; `lib/newlang.py`, `lib/langprompts.py`) | `<code>`, with that language's own files `lib/lang/<code>.tex` and `<code>.*.json`, `docs/lang/<code>.md` and `markdown/exlex/starters/<code>.md` | personal | `language:<code>` | choice |
| `network.json` (`lib/network.py`) | `port`, `vpn`, `lan`, `extra`, `cert`, `devices` (with their tokens) | this device's | — | never |
| `lm-likelihood.json` (`lib/lmlikelihoodconfig.py`) | every key (interpreter paths, backend, graphics card, …) | this device's | — | never |
| `updates.json` (`lib/updater.py`) | every key | this device's | — | never |
| `backups.json` (`lib/backupdays.py`) | every key | this device's | — | never |
| `digests.json`, `wheres.json` (`lib/offline.py`) | every key (derived, by this disk's paths) | this device's | — | never |
| `llm.json` (the retired LLM connection, which may hold a key) | every key | this device's | — | never |
| `damaged-seen.json`, `*.damaged-*` (`lib/storeguard.py`) | — | this device's | — | never |
| `sync/` (identity, key pair, change log, the versions kept for a day, the diff files) | — | this device's | — | never |
| `peers.json` (lane A: the partners, the job switches, what this device holds) | — | this device's | — | never |

### Everything else Parseh writes (never synced)

| store | written by | why it never syncs |
|---|---|---|
| `dict/`, `corpus/`, `mt/`, `components/`, `stt/`, `analysis/`, `llm-scoring/`, `arasaac/` | `lib/get*.py`, `lib/download.py` | Fetched again on each device. |
| `texmf/` | `lib/texpackages.py` | Fetched again. |
| `.runtime/`, `.parseh-update/`, `.tls/` | `lib/runtime.py`, `lib/updater.py`, `serve.py` | This install's own. |
| `.tmp/` | `lib/scratch.py`, `lib/sttjobs.py` | Temporary files, emptied after a day. |
| `serve.log`, `.setup-done`, `.serve.pid` | `lib/faultlog.py`, `lib/launcher.py`, `serve.sh` | This install's own. |
| `lib/languages.json`, `lib/langs.css`, the studio's static fonts | `languages.migrate`, `write_css`, `server.ensure_web_fonts` | Part of the software, written again at start. |
| the original file of a document opened from the computer | `openfile.write_file` | It belongs to the computer's own folders, not to Parseh's shelf. |

### What the inventory found that the brief did not say

- **Some files are rewritten in place, with no temporary file.** These are
  `timings.json` (`serve.py` `_subtimes` and the `lib/timestamp.py` subprocess),
  a chapter's `.tex` lines written by `timestamp.write_comments`,
  `review-corrections.json`, and a studio document's `source.md` and images
  (`store._create`, `_save_text`, `save_image`). The change log does not depend on
  them going through a chokepoint: the scan catches them. The exchange must still
  never read a unit while it is being written, so it reads a unit only under
  `synclock.sync_write` and checks the hash again after reading.
- **Alignment writes outside the book's lock.** `__narration/align` runs
  `lib/timestamp.py` as a subprocess that writes `timings.json` and the chapters,
  and that route is not among `BOOK_WRITES`. The end of the route's
  `pathlock.held` does not cover it, so the scan does.
- **Several modules write one file.** `book.json` has five writers and
  `video.json` has four. `config/languages.json` is written both by
  `languages.write_store` (its own temporary file) and by `configbackup`
  (`storeguard`). A note's `source.md` is written both by the store and by
  `captimes._move_notes`. Units are made of files, never of writers, so this does
  not matter to sync.
- **A personal language writes into the software's own tree:** `lib/lang/`,
  `docs/lang/`, `markdown/exlex/starters/`. Only the files of languages listed in
  `config/languages.json` are part of a unit. The shipped languages' files never
  are.
- **Some deletions keep no trash:** a studio document (`rmtree`), one exercise, a
  clip, and an Anki deck replaced by a backup. Sync keeps every version it deletes
  for a day. A deletion the person makes here is theirs, as before.
- **Two settings live in the browser, not in config/:** the zoom and the open
  levels. They are this device's by construction. The brief listed "levels per
  language" as personal. What follows the person is a level's *name*
  (`bk_lvl:…`), and that is what syncs.
- **Undecided, so the rules (lane C) should confirm with the owner:**
  - The reading place: here it follows the rule "latest", because the reader
    already asks whether to jump.
  - `youtube/anki/seen.json`: here it is additions (a union of guids), on the
    view that it describes the person's Anki collection.
  - A personal setting: here it follows the rule "choice", as the brief says.
    `configbackup` and `prefs` let the later change win.

## The foundations: modules and interfaces

All of these are standard library only, run no subprocess (except one way of
making a key, which has an alternative), and keep their state in `config/sync/`.
That folder sits beside `prefs.STORE`, so a test harness that points prefs at a
temporary tree points sync there too. Phones will run the same modules.

```
config/sync/identity.json   identity.key   identity.crt     lib/syncid.py
config/sync/log.sqlite                                       lib/synclog.py
config/sync/kept/<id>/                                       lib/synckeep.py
config/sync/diffs/*.diff                                     lib/synckeep.py
```

### `lib/syncunits.py`: what syncs, in code

```python
KINDS                      # kind -> (rule, what it is in words, editor)
CHOICE, PROGRESS, LATEST, ADDITIONS, IMMUTABLE
Unit(id, kind, rule, where, key)   # where: the folder (or config file) on THIS disk; key: the path inside a config file
configure(books=, videos=, anki=, library=, exercises=, clips=)   # serve.py passes its modules' own folders
walk()                     # every unit held now
locate(uid) -> Unit        # where an id lives here, held or not; KeyError for ids that are never synced or climb out
files_of(u) -> {inner: abs path}   # a file-made unit's files ({} for a setting)
path_of(u, inner) -> abs path      # where the exchange writes one of them
value_of(u)                # a setting's value (None when it is not there)
snapshot(u, filehash=…) -> None | {"hash", "files": {inner: sha256}} | {"hash", "value"}
units_for(path)            # the units a write at `path` may have changed (that are still there)
rule_of(uid), kind_of(uid)
```

Inner names are relative to `u.where`, with `/` as the separator. The one
exception is a language, whose inner names are `lang/…`, `docs/…` and
`starters/…`. A unit's hash is the sha256 of its sorted `inner\0sha256` lines, or of
a setting's value as canonical JSON, without the fields that say when and by
whom. Two computers that hold the same content therefore hold the same hash.

### `lib/synctouch.py` and the hooks

`touch(path)` adds one path to a set under a lock, and nothing more. It is
called at these points:

- `lib/storeguard.py` `write_text`, which covers every personal config store;
- `lib/pathlock.py` `tmp` and the end of `held`, which cover every book and video
  route;
- `markdown/app/store.py` `_doc_dir`, `_create` and `delete`, which cover every
  studio document and note;
- `markdown/app/decks.py` `_write_bytes`, `_remove` and `_to_trash`;
- `lib/clips.py` `_write_json` and `delete`;
- `youtube/lib/anki_store.py` `write_json`, and `sync_apkg` `retire_card` /
  `unretire`;
- `lib/books.py` `trash` and `youtube/lib/ytpages.py` `trash_video`.

A touch is a hint: one too many costs a few `stat` calls, and a missing one costs
only time, because the scan finds the change anyway.

### `lib/synclog.py`: the change log

```python
home()                     # config/sync (follows prefs.STORE unless HOME is set)
touch(path)                # = synctouch.touch
flush() -> [change]        # record the units under what was touched (the server's thread does this 2 s after the last write)
scan() -> [change]         # walk everything, compare with the log, tombstone what went: at start and BEFORE EACH SYNC
refresh(uid) -> change|None
get(uid) -> {"unit","kind","rule","place","key","hash","files","vv","deleted","at","seq"} | None
rows(prefix="", deleted=None) -> [row]
changes_since(seq=0, limit=1000) -> [{"seq","unit","op","hash","added","install","vv","at"}]
last_seq()
compare(a, b) -> "same" | "ahead" | "behind" | "both"      # version vectors
merge(a, b), bump(vv, install)
adopt(uid, hash, vv, files=None, deleted=False, by=None, place=None)   # lane B, inside sync_write: a partner's version written here
chosen(uid, other_vv)      # lane C: this computer's version kept; its vector is now ahead of both
forget(uid)                # lane C: drop a tombstone once answered and synced everywhere
start(shelves), stop()     # serve.py
```

The operations are: `put` (changed here), `add` (an additions unit that appeared
here, with `added` = its files or value), `delete` (a tombstone), `adopt` (a
partner's version, with no count of this install's) and `choose`. **Equal hashes
mean agreement, whatever the vectors say.** Two installs that got the same book
from one zip hold `{A:1}` and `{B:1}`. The exchange then adopts the other's vector
instead of asking.

File hashes are cached by size and modification time, so a scan reads only the
files that moved. A unit that `synclock` says sync is writing is skipped by both
`flush` and `scan`, and is looked at again afterwards, so a version brought in by
sync is never recorded as this computer's own change.

### `lib/syncid.py`: who this install is

```python
identity() -> {"install", "name", "created", "key": {"fingerprint", "made"} | None, "protocol"}
install_id(), name(), set_name(new), default_name()
ensure()                   # at start: the key pair made if missing (cryptography, else openssl, else MINTER)
paths() -> {"identity", "key", "cert"}
fingerprint(cert_path)     # sha256 of the certificate's DER, in hex
reset()                    # a new id and key pair (an install copied to another computer), the name kept
PROTOCOL                   # the version of the sync protocol; lane A says it at pairing
MINTER                     # function(key_path, cert_path, common_name), for a platform with neither way
```

The key is EC P-256 with a self-signed certificate, `CN=Parseh <install id>`,
`CA:TRUE, pathlen:0`. Lane A can use it as this install's pinned authority and sign
its TLS certificates for partners with it.

### `lib/synclock.py`: one lock per unit

```python
open_editor(uid, holder) -> token     # Busy(retry_after) while sync writes the unit
keep(token) -> bool                   # renew the lease (LEASE = 120 s); False: it had run out
close_editor(token) -> uid | None
on_close(callback)                    # callback(uid) when the last editor lets go (lane C: a waiting change becomes a choice)
editing(uid) -> [holders], writing(uid) -> bool, state(uid)
with sync_write(uid): ...             # Busy when an editor holds it; for a book or a video it also holds the route's pathlock
```

The editors that take a lease are the studio editor, a transcript's editor, a
note, an exercise's form and a deck's options. The pages and routes that open and
renew leases are lane E's work. The locks are in-process, like `lib/pathlock.py`.

### `lib/synckeep.py`: undo for one day, and the diff files

```python
keep(uid, why, partner=None) -> entry | None    # why: incoming | choice | deletion | identical; BEFORE sync writes
entries() -> [entry]                            # newest first
put_back(entry_id) -> uid                       # becomes this computer's change; Busy while an editor holds it
drop(entry_id), clean(now=None) -> count        # clean: entries older than KEEP_FOR (one day); at start and hourly
text_diff(kept, discarded, kept_label, discarded_label) -> unified diff
fields_diff(kept, discarded) -> ["a.b: old → new"]
write_diff(uid, text) -> {"name", "path"}, diffs(), delete_diff(name)   # never cleaned: the person deletes them
```

## How the lanes use this

- **Lane A (pairing and transport)** reads `syncid.identity()` and the key pair,
  keeps the partners in `config/peers.json`, and says `syncid.PROTOCOL` at
  pairing.
- **Lane B (the exchange)** syncs in these steps:
  1. It calls `synclog.scan()`, then compares its `rows()` with the partner's by
     `compare(vv)` and by hash.
  2. It fetches the files it lacks by their sha256, which lets immutable files
     and media be shared across units.
  3. For each unit it writes inside `synclock.sync_write(uid)`, in this order:
     `synckeep.keep(uid, "incoming")`, then the files written, then
     `synclog.adopt(...)`.
- **Lane C (the rules)** decides on "both" and on tombstones. It uses
  `chosen()`, `forget()`, `synckeep.write_diff()` and `synclock.on_close()`.
- **Lane E (the pages)** shows `syncid.name()` / `set_name()`, `synckeep.entries()`
  / `put_back()` and `synckeep.diffs()`, and makes the editors take and renew
  leases.

<!-- lane B: the exchange -->
## The exchange: `lib/syncexchange.py` (lane B)

Every exchange is a **pull**. This install asks a partner for its rows
(`sync.have`), compares each with its own log and takes what it lacks. "Both
directions" is a pull followed by `sync.nudge`, which makes the partner pull
from here in turn. Only the receiving side ever writes, so every write is under
that side's own locks.

Per unit:

| this side's row against the partner's | what the exchange does |
|---|---|
| equal hashes (or both tombstones) | agreement: the vectors are merged (`adopt`), nothing moves |
| ahead, or the same vector | nothing here; the partner takes it when it pulls |
| behind, the partner's live (or none here) | **taken**, with no question |
| anything else | a **situation**, handed to `RULES[situation]` (lane C) |

**Files travel by content.** A unit's description (`sync.unit`) names each file
by its sha256. A file whose sha this computer already has anywhere on its shelf
is copied locally and never sent. The others come in chunks (`sync.blob`,
`CHUNK` bytes, each chunk's own sha256 checked) into
`config/sync/incoming/<sha>.part`, which the next sync continues from where it
stopped. Only when every file of a unit is here and checked is the unit
written, inside `synclock.sync_write(uid)`, in this order:

1. `synckeep.keep(uid, "incoming" | "deletion", partner)`;
2. the journal `config/sync/applying.json`;
3. the files, each through a temporary file and `os.replace`, and the ones
   the partner's version lacks removed;
4. the hash checked against the partner's, then `synclog.adopt(...)`;
5. the journal removed.

A crash between 2 and 5 is finished by `recover()`, which `serve.py` runs
before the change log's first scan, and which every sync runs first. A sync cut
off at any point therefore leaves each unit either as it was or as the
partner's. A unit that changed here while its files were coming is left for
the next sync. Finished files in `incoming/` are swept after a complete sync,
and a partial one after `PART_DAYS`.

The ops, registered through lane A's `syncroutes.register` and called through
`syncpeer.call`:

```
sync.have   {}                           -> {"ok", "install", "rows": [{"unit","kind","hash","vv","deleted"}]}
sync.unit   {"unit"}                     -> {"ok", "unit", "hash", "vv", "deleted", "files" {inner: sha} | "value", "lang_files"?}
sync.blob   {"sha", "offset", "length"}  -> {"ok", "size", "chunk": sha256 of the bytes}, the bytes
sync.nudge  {}                           -> {"ok", "queued"}   (the partner pulls from the caller)
```

An answer with `"ok": false` carries `"error"` in words. `sync.blob` serves only
a file of a live synced unit, found by its sha.

### The seam for lane C

```python
SITUATIONS = ("both", "setting", "progress", "additions", "latest", "deletion")
RULES = {situation: handler}        # default: hold
HELD = "held"
def handler(case) -> HELD | anything else   # HELD: listed in pending(); else settled
class Case:
    unit, situation, partner        # ids
    mine, theirs                    # log rows {"unit","kind","hash","vv","deleted"}; mine may be None
    info()                          # the partner's version now (as sync.unit answers)
    staged()                        # {inner: local path} of the partner's files, fetched and checked
    take(why="incoming") -> bool    # write the partner's version (or its deletion) here: kept, written, adopted
ON_TAKEN = [callback(uid, partner)] # after a partner's version was written here ("out of date")
pending(partner=None, situation=None) -> [{"unit","kind","rule","situation","partner","mine","theirs","at"}]
clear_pending(uid, partner=None)    # once a case is answered
decide(mine_row, theirs_row) -> None | "adopt" | "take" | a situation
```

- **"both"** is a choice unit changed on both sides. **"setting"** is a personal
  setting changed on both sides. **"progress"**, **"additions"** and **"latest"**
  are those rules' units changed on both sides.
- **"deletion"** covers a tombstone on either side against a live version: deleted
  there and untouched here, or deleted on one side and edited on the other.
- A partner that recreated a unit after its tombstone reached it is ahead, and
  is simply taken.
- The pending list also holds **"editing"**: an editor held the unit here when the
  partner's version came. The exchange asks for a sync with that partner when
  the editor closes (`synclock.on_close`).
- A held case stays listed until a complete sync no longer finds it, or until
  `clear_pending()` is called.
- "Make identical" and "out of date" are lane C's own. They can use `Case.take`,
  `Pull(partner)` with `.info(uid)` and `.take(uid, why="identical", force=True)`,
  and `ON_TAKEN`.

### Holding, and what is elsewhere

```python
holding() -> {"leave_out": {"languages": [language folders], "units": [book|video|deck|doc|ankideck ids]}}
set_holding(languages=None, units=None)   # config/sync/holding.json, this device's
holds(uid), owner_of(uid), language_of(uid)
elsewhere(partner=None) -> [{"unit","kind","owner","partners":[ids]}]   # "on <partner>"
fetch(uid, partner) -> summary            # the whole owner (a book and its notes...), held from then on
```

Leaving something out deletes nothing here. It stops this device from taking
it. "What this device holds" is kept in `config/sync/holding.json` for now. If
lane A keeps it in `config/peers.json`, `holding()` / `set_holding()` are the
only places to change.

### When it runs, and what the pages read

```python
start(tick=None, change_debounce=None), stop()   # serve.py starts it; tests stop it
request(partner=None, why="")       # a sync soon (every partner when None)
sync_now(partner=None, wait=False)  # "sync now"; wait=True -> {partner: summary}
sync_from(partner, only=None, why="", wait=True) -> summary   # one pull
sync_with(partner, why="") -> summary                           # pull, then nudge
status() -> {"running", "partners": {id: {"state","last_ok","last_error","last","why"}}, "pending", "elsewhere"}
```

A summary is `{"partner", "taken", "adopted", "held", "waiting", "elsewhere",
"failed" {uid: reason}, "complete", "error", "blobs" {"chunks", "bytes",
"local"}}`.

A sync runs at start, when a partner becomes reachable, `CHANGE_DEBOUNCE`
seconds after the log recorded a change made here (synclog's flush already
waits for the writes to settle, and an `adopt` does not count), on `request`,
and on a nudge. One lock per partner means never two syncs with the same
partner at once. A request that comes while one runs is queued behind it.

The tests drive two installs in one process: `tests/syncfake.py` stands in for
lane A's `syncpeer` and `syncroutes`, and `tests/test_sync_exchange.py` runs them.
<!-- end lane B -->
