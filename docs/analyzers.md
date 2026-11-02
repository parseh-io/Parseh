# The optional linguistic analyzers (a0.6.0)

UDPipe, Farahidi and Starlang, on this computer, as evidence for three things: the
dictionary panel, the phrases of new text, and the gloss prompts. All are optional and
each is off until somebody turns it on. Parseh's own source spans, a person's edited
chunks, the dictionaries and the verb machinery stay what they were, and stay in charge.

| Language | Morphology | Syntax |
|---|---|---|
| en de es fr it hi fa | UDPipe | UDPipe |
| ar | Farahidi: every analysis, the lemma its sentence chooses | UDPipe, kept apart |
| tr | Starlang: every parse, none chosen | UDPipe, kept apart |
| ja zh | what lib/words.py already has | none |
| a language added later | none: everything goes on as before | |

## The pieces

| File | What it is |
|---|---|
| `lib/analyzer.py` | The records, validation, registry, cache, composition. Stdlib, imports no analyzer. |
| `lib/analyzer_udpipe.py`, `_farahidi.py`, `_starlang.py` | The three adapters. |
| `lib/analyzer_native.py` | Japanese and Chinese, from `lib/words.py`, in the same records. |
| `lib/analyzerworker.py` | The one program that imports them; JSON lines over its pipes. |
| `lib/getanalysis.py` | Getting them, what is here, and talking to the worker. |
| `lib/analysispins.py`, `lib/analysis-*-requirements.txt` | Exact versions, addresses and hashes. |
| `lib/analysisconfig.py` | `config/analysis.json`: the three choices. |
| `lib/analysispage.py` | Settings -> Linguistic analysis, with its Try it. |
| `lib/lookupassist.py` | What an analysis may add to a lookup. |
| `lib/chunker.py` `assist=` | What an analysis may say of a seam, new text only. |
| `lib/evidence.py` | The budgeted `analysis` of a prompt, and the read-only helper. |
| `docs/analysis-evidence.md` | The one rule about evidence. |

`analysis/` holds `runtime/` (a venv made with the serving Python) and `models/`. It is in
`.gitignore`, in the updater's `PERSONAL` and in the release's left-out list.

## The contract

`analyzer.analyze(code, text, syntax=False, backend=None, context="")` always returns a
`Result`, whose `outcome` is `ok`, `empty`, `unavailable`, `unsupported` or `failed`.
Consumers check `.ok` and otherwise do what they did before. Only a programming error raises.

- A `Token` is `text[start:end] == surface`, exactly: `validate` holds every result to that,
  whichever process it came from, including after the pipe.
- A `Word` is a syntactic word. It has a span only if it is a literal piece of the text
  (`Zum` is one token and two words without spans). Its head is an id in its own sentence
  from its own source, or None for the root.
- `Token.candidates` keeps every analysis; `rank` is the backend's order, no more.
- `Selection` keeps the lemma's and the analysis's status apart, because Farahidi chooses
  only the lemma by context.
- `compose` pairs two backends only on an identical span and keeps both voices
  (`Token.words`, `Token.syntax`). `Token.parsed()` is the words with dependencies.

A backend needs `name`, `languages()`, `status(code)` and `analyze(code, text, syntax, context)`,
and `status` may not import anything heavy, load a model or ask a network. Consumers need nothing
but this file, so adding or repairing a backend changes none of them: add its adapter and its row
in `MORPHOLOGY`/`SYNTAX`, and it goes through the worker (`getanalysis.backends`, `analyzerworker.serve`).

The cache holds 256 results by exact text, context, syntax, backend, version and resource.
A failure is not cached. `clear_cache()` also stops a running request from storing its answer.

## What each consumer may do

**Lookup** (`off`, `show`, `assist`) is the point of the version: the part of speech. It runs after `look_up` and only
adds, and does not use `pieces=`, which would turn off the joins of a prefix written apart. A row gets `machine`: the
part of speech read in the sentence (a chip in both panels), lemma, grammar in plain words. `ENTRY_POS` maps it to the
dictionary's parts of speech; an entry of that part of speech gets `fits` (the marker) where that tells entries apart, narrowed
by the lemma where the lemma names one of them. A lemma alone never marks: on `كتابا`, all nouns, it chose `كاتب`.
`assist` moves what fits to the front (a word read by the spoken pass keeps its numbered order), adds the lemma's entry if only
other parts of speech were found, and looks a word nothing found up under its lemmas, saying so (`kind: "analyzer"`, `via`). A
separable verb's particle (`compound:prt`) asks for nothing. For a row of several tokens or a token of several
words, the word of content speaks. Where a backend holds the morphology, the sentence chooses among its readings only:
a UDPipe lemma none of Starlang's readings has is shown beside them, not as chosen. A person's word line never comes here.

**Spoken Persian and the analyzers.** `lookupassist.formal_view` hands the model the normaliser's formal spelling (the spoken hit's `as`) in place of a
spoken word, with a map back to the page's spans; a video's evidence goes the same way (`evidence._carried`). Rivals or not: tried against reading rivals only for a word the
model does not know, and against the raw page, on hand-judged sentences (`tests/analysis_bench.py`), this gave the most (99% right chips against 93%, wrong marks 4 of 61 against 20 of 69). The analyzer then marks among the spoken readings by part of speech, and those may move; its LEMMA chooses nothing on a row the normaliser read, because it is of a word the model was shown instead of the page's, and a treebank invents one for what it has not seen (`میشه`: `میش`). A POS guessed for a
word with no lemma and no backend's readings earns a chip the entries bear out, and marks nothing.

An infinitive is a NOUN to a treebank (`رفتن`, `okumak`): a verb entry spelled as the page spells it fits, unless a noun is spelled so.

Two backends: where morphology lists what a word can be, the sentence chooses among those (`sinemaya`: Starlang's only noun beats UDPipe's verb); an entry none of
its readings names does not fit (`erke` for `erkenden`). A word is judged by what it was before its derivation (`raw["base"]`: `okumak` ends a NOUN and is a verb to look up). Where UDPipe's lemma is one of Starlang's readings, chosen by the sentence's part of speech where one root has two (`kırdım`), the two AGREE and that lemma may tell entries of one part of speech apart (`adamı`: `adam`, not `ada`), the one case a lemma decides. If the panel has no such entry it is added, and none other is marked. A word nothing found is looked up under the chosen lemma, else under every reading that lands, what the sentence allows first and the longest first (`öğretmenimdir`: `öğretmen`).

**How to judge a change here:** `python3 tests/analysis_bench.py <analysis> <dict> [--misses]`, each combination side by side. The `*-holdout` files were written after the rules were tuned and scored as they stood (Persian 79→92% first, 84→97% found; Turkish 84→97%, 89→100%): keep them out of the tuning, or they stop saying anything. Arabic: when Farahidi's sentence and UDPipe disagree nothing is claimed, because each was right about as often.

**Chunking** (`off`, `assist`) is for new text only, through `lib/draft.py`. A dependency can
hold a seam (`_DEP_JOIN`) or open one (`_DEP_OPENS`), and supply a part of speech to a word the
rules call OTHER. It cannot overrule the writer's punctuation or move a token. The result must be
an exact slice (`chunker.exact`, stricter than `reproduces`), otherwise the old suggestion stands.
The list of relations is deliberately short: extend it from a sentence that needs it.

**Evidence** (`off`, `on`) analyzes each sentence once and hands entries to its chunks. A token
across a chunk's seam is left out and counted. It goes on chunks to do, through `glossregion._data`,
so the prompt and the skill's short request carry the same data, and with it the rule goes in the
locked contract (`{{?evidence}}`), so a person's replaced instructions cannot lose it. With nothing
to say, the prompt is byte for byte the old one. Answers cannot bring it back: `glossregion` reads
only a gloss's own fields. `parseh-gloss` carries the rule as `references/analysis-evidence.md`,
read only when a chunk has `analysis`. `parseh-book` gets one line of the method (`EVIDENCE_HELPER`)
naming the read-only helper, and only while evidence is on.

Not in this version: studio prompts, `parseh-markdown`, transcript tidying, Ask LLM, a video from scratch.

## Installing, and moving a pin

`ufal.udpipe` and `farahidi` have wheels and install in seconds. Starlang ships source only, so it
compiles in order, each package against the one before it (`STARLANG_ORDER`), with Cython 3.0.12
(3.1 and later refuse `NlpToolkit-Math-Cy` 1.0.20) and setuptools below 81 (`NlpToolkit-Dictionary-Cy`
imports `pkg_resources` at run time). Its modules are called `Math`, `Util`, `Dictionary`: one more
reason they live in their own process.

LINDAT's old `/xmlui/bitstream/handle/...` addresses now answer an HTML page with status 200, which
is why models are pinned by bitstream id, size and hash; the size and the hash catch that page.

To move a pin: install in a scratch venv, run `tests/analyzer_real.py <folder>`, read it, then change
`lib/analysispins.py` and regenerate the requirements with the hashes PyPI lists.

## Platforms

Checked: Linux x86-64, Python 3.12. Inspected only: PyPI lists `ufal.udpipe` wheels for Windows and
macOS and Farahidi is pure Python, so they should install there. **Untested on Windows and macOS:
above all Starlang, whose compile needs MSVC or Xcode's tools.** Its failure is said in a sentence
on the page, and the other analyzers do not need it.

## Tests

- `tests/test_analyzer.py`: the contract, the adapters on saved output and fakes, each consumer,
  the real appliers on fixture copies. Stdlib, no network.
- `tests/analysis_door.mjs`: the Settings page. `REAL=<folder>` drives the real download.
- `tests/analyzer_real.py <folder>`: the real analyzers on small sentences, for a person to read.
