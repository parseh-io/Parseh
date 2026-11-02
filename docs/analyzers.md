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

**Lookup** (`off`, `show`, `assist`) runs after `look_up` and only adds. It does not use
`pieces=`, which would turn off the joins of a prefix written apart. A word the dictionary did
not find is looked for under the analyzer's lemmas, and only a real entry counts; the row says
`kind: "analyzer"` and `via`. Where the sentence chose a lemma and a word has several entries,
that lemma's come first and none is dropped. A person's word line never comes here.

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
