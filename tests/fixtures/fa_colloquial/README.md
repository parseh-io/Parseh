# The fixture of the Persian colloquial normaliser

What it is: the contract the normaliser (`lib/lookup.py`'s spoken pass, the `spoken`
section of `lib/lang/fa.lookup.json` and its tables) is built against. The
specification is `TODOs/NOTE-fa-colloquial-normaliser.md` (the families, the layers of its
section 12, the traps of its section 14) and the design is
`TODOs/DESIGN-fa-colloquial-normaliser.md`. Everything here was written for the tests and is
Parseh's, under its licence; the sentences are short and made up, the spoken forms are the
note's own examples.

It was written BEFORE the normaliser, on purpose: each layer is built until its rows are
green, and a row that is red says what the next layer has still to do.

## Files

| File | What |
|---|---|
| `verbs.json` | The verbs of the dictionary: infinitive, past stem, present stem, romanisation, sense, and what a verb does its own way. Their FORMAL conjugation is generated (`tests/fa_colloquial_dict.py`). |
| `lexicon.json` | Every other formal entry: the words the rows must reach, and the ordinary words the note's traps also are (خون, نون, بدن, ...). |
| `colloquial.json` | The few pages of the dictionary's own that say `colloquial form of …`. Few on purpose: nothing may be easy because the dictionary holds the spoken word. |
| `rows/*.json` | The sentences, by family. |
| `panel.json` | What the panel shows for each case of the note's section 13: driven in the book reader, the video player, the editor's sources column and the phone's sheet by `tests/fa_colloquial_panel.mjs`, on the real hub. |
| `state.json` | How far the normaliser has got: the layer built, and the rows that already pass and must go on passing. |

`tests/fa_colloquial_dict.py` builds `fa.db` from the three data files; `tests/test_fa_colloquial.py`
reads the rows. The dictionary has FORMAL words only, shaped like Wiktionary's Persian (a
verb carries its whole formal table as form rows). **It proves that a rule reaches a real
entry through a real table; it says nothing of how often a rule would invent an answer in the
real 17,000-headword dictionary**, which is not measured here (the brief leaves it out).

## A row

```
[ text, word, expect, opts ]
```

* `text`: the sentence (or chunk) asked about, as `lookup.look_up("fa", text)` is.
* `word`: the token of it the row is about, as the answer names it (two or three tokens
  with their spaces where the answer is a window: `می کنم`, `دوس دارم`).
* `expect`: the headwords the answer's hits for that word must begin with, in order. A
  string is one of three things by its first character:
  * none: a hit that carries a `spoken` object (the normaliser's reading);
  * `=`: a DIRECT hit, one with no `spoken` object (what the dictionary said before);
  * `~`: a direct hit that also carries a second spoken line (`spoken.same`): the same lemma
    read two ways (رفتن, the infinitive and "they went");
  * `!`: there must be NO hit of that headword.
* `opts` (all optional):
  * `layer`: the layer (1–9, §12 of the note) the row is due at, where it is not its family's;
  * `reg`: `"spoken"`: the page's register hint (the player sends it);
  * `as`: `spoken.as` of the first spoken hit, the formal word it was read as;
  * `why`: a substring `spoken.why` must hold (the reason in words);
  * `kind`: `spoken.kind`: `entry` (the dictionary's own colloquial page), `table`, `rule`;
  * `pieces`: roles that `spoken.pieces` names (`emphatic`, `copula`, `progressive`, ...);
  * `readings`: the readings (`spoken.readings[*].as`) that must all be offered;
  * `sound`: `spoken.sound`, the spoken pronunciation of the word on the page;
  * `table`: the expected head is NOT a dictionary entry (a word only the table knows);
  * `loose`: the listed hits must be present, in any order;
  * `strict`: `false` lets other spoken hits follow; by default a row that expects only direct
    hits allows none, and a row that expects a spoken hit allows others after it;
  * `noise`: laughter, a link, a name: nothing may be invented for it;
  * `neutral`, `stretch`: documentation only (the chunk has no spoken evidence; a row for later).

Row ids are `FAMILY:index`; **rows are appended, never reordered**, so that `state.json`'s
list of pinned rows stays right.

## What the normaliser's answer looks like (the contract the rows read)

A hit is what `look_up` returns today (`headword`, `pos`, `senses`, `note`, `translit`, ...)
and, where it was reached by the spoken pass or is also read that way, one more key:

```
"spoken": {
  "kind":    "entry" | "table" | "rule",
  "as":      "می‌گویند",              # the formal form it was read as
  "why":     "spoken for ...",        # the reason, in words the panel shows
  "parts":   ["خانه", "شان", "است"],  # a composed answer's pieces
  "pieces":  [{"text": "ـا", "role": "emphatic", "note": "..."}],   # a piece with no formal equivalent
  "same":    true,                    # a second line on a DIRECT hit (the `~` rows)
  "readings": [{"as": "...", "why": "..."}],                        # more readings of the same headword
  "sound":   "xune", "sound_kind": "spoken" | "formal"
}
```

Direct hits keep their own order and content; the spoken hits stand after them unless the
register puts them first (design §3). The three decisions of 2026-10-12 are in the rows:

1. a second, different-lemma reading in a book only for the trap words (`T1`–`T3` say which
   words, and when: with spoken neighbours or the page's hint, or always);
2. `reg: "spoken"` is a tie-breaker and an adder, never an override (`N`: میان goes to
   آمدن first on a spoken page, خون keeps `=خون` first on every page);
3. the pronunciation is the spoken one where a table or a regular rule gives it (`sound`),
   otherwise the formal one labelled `formal`.

## Families

`A` writing level (layer 1; A5 tables, layer 2) · `B` sound changes (8) · `C` the verb
(C9 and C6/C8/C1 at 2/4, C7 at 5, C2–C5 at 7) · `D` nouns and what attaches (D3 at 3, D2 at 5,
D1/D4–D7 at 6) · `E` closed sets, `F` the word table, `G1`–`G6`, `H` (2–3) · `T1`–`T4` the traps
of §14 · `N` register · `I` syntax the normaliser must not be fooled by · `HAS` what already
works. A family's `layer` is the layer of the note's section 12 where its rows become due.

## How far the normaliser has got

`state.json`'s `built_layer` is **9**: layers 1 (the writing level), 2 (the dictionary's own colloquial
pages, the whole-word tables, the windows of two or three words), 3 to 6 (outer clitics, copula and personal
endings, pronominal clitics, the definite -e and the plural: `lib/spokenpeel.py`), 7 (the verb: its stems in
`lib/lang/fa.spoken.verbs.tsv`, `lib/spokenverb.py`), 8 (the sound changes of B read one step back:
`lib/spokensound.py`) and 9 (the spellings by ear of A4 as the second stage of the same engine, the one-letter words, spaced letters, words run together) are built and green, and the rows of every layer that already pass are pinned. `python3 tests/test_fa_colloquial.py --report` says how many are left, by
layer; `--record` pins what passes. The engine is `lib/spoken.py`, its rules the `spoken` section of
`lib/lang/fa.lookup.json`, its words `lib/lang/fa.spoken.words.tsv` (Hazm's reviewed pairs and the note's own
closed sets; each row's last column says which).

Three rows were moved to layer 7 when layer 2 was built, and say why here: G4's `نیگا کن`, `جم کن` and `صب کن`
end in the bare imperative `کن`, which is no form of کردن in a Wiktionary-shaped table (it lists بکن) and which
the note puts in C4 (the imperative without ب, layer 7). The first parts of those compounds are read at layer 2:
`فک میکنم` and `دوس دارم` pass there, with verb forms the dictionary has.

`TheSuiteCanFail` also switches the engine's stages off one at a time and requires the rows of that stage to turn
red: a row that stays green while its stage is gone was reading the fixture dictionary and not the engine.

Rows moved while layers 3 to 6 were built (the reasons are in `TODOs/DESIGN-fa-colloquial-normaliser.md` §7): C1:4 5 11–20, C7:11 13 15, C8:11 12, T1:6 8 10
12 14 15 16 and G3:0 to layer 7 (they need contracted, vowel or bare stems); C7:20, C9:2 and T1:19 to layer 9 (the sentence, a gloss, the neighbours decide);
C7:0 1 3 4 18 19 are expected DIRECT (a formal clitic on a verb form is what the old affix rules already answer: the note marks it [has] and HAS:8/9 pin it);
G2:0 is `loose`. A row's `policy` words are the table rows that say when a second reading of a word the dictionary knows is shown (kind `policy`).

Rows changed while layers 7 and 8 were built (`TODOs/DESIGN-fa-colloquial-normaliser.md` §8): a compound verb's first part beside its light verb is ONE
window (G4's rows pin it), so the B rows that stood it beside one were given a sentence of their own (B2:2 دوس, B3:5 فک, B3:6 صب, B4:0 نگا, B4:10 جم) and
B6:8 and B6:9 ask for the window (وا کن, ور دار); C6:30 is `loose` (it is B2:1's sentence, which wants the entry نیست first); T2:24 and the page-hint test have
sentences with no word of a spoken verb and no trap word; C5:1 asks for `readings` of رفته‌اند (the plural infinitive is رفتند and رفته‌اند).


Rows changed while layer 9 was built (`TODOs/DESIGN-fa-colloquial-normaliser.md` §9): A3:39 (`stretch`) expects the four pieces تو, را, دوست, داشتن (the compound verb is not
put together again); C9:2 expects `شدن` with the `readings` ممکن است (the dictionary has no میشه, so there is no direct hit to put a second line on).
