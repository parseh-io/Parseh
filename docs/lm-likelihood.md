# LM likelihood

This and the suspect-word, whole-text and reasoning-workspace correction
methods are labeled **experimental** in the browser interface.

This browser review method uses a causal model as a numerical engine. It does
not use system/user messages, a chat template, completion APIs, prompts,
reasoning, assistant text, JSON generation or agent tools. JSON lines between
Parseh and its worker are an application protocol only.

## Configure and run

Open **Settings → LM likelihood**. Its saved configuration is
`config/lm-likelihood.json`, format version 1.
Missing or malformed settings load unconfigured. Source/path/executable/backend
changes are host-only; any admitted browser can refresh the saved source’s
inventory and select one of those installed models by its opaque inventory ID.
A review request cannot override the model, path, context or executable.

Choose one source:

* **Installed Unsloth GGUF** reads Studio's local installation manifests under
  `~/.unsloth/studio/cache/hub-state/manifests`, including their Hub location,
  expected filename and size. It resolves a pinned snapshot when present or an
  unambiguous installed snapshot when the manifest omits its revision. It does
  not ask Studio to load a model. Install through Studio first. Installations
  without this metadata use the explicit-path fallback.
  A complete standalone text decoder accompanied by separately validated CLIP
  vision-projector GGUFs is explicitly offered as **text only**. The worker
  never loads those optional vision projectors; this is a complete plain-text
  configuration. Multiple text models, split weights and required adapters
  remain unsupported.
* **Installed Ollama model** uses GET `/api/tags` and POST `/api/show` only.
  The generated Modelfile must expose one absolute `FROM` backing-file path
  and no `ADAPTER`. Content-addressed blobs need no `.gguf` suffix. Install
  through Ollama first. Manager paths must be readable on the worker's host;
  an inventory from another computer does not make its weights local.
* **Explicit local GGUF path** is the fallback. Select a complete standalone
  causal decoder GGUF. No weights are downloaded, copied, converted, renamed
  or modified. Split weights, adapters and encoder-only models are refused.

Validation supports little-endian GGUF v2/v3 and checks actual magic/version, metadata, tensor shapes, supported
quantized sizes, alignment, duplicate entries and completeness against file
size. Native loading checks architecture/runtime compatibility. Saved identity
includes canonical location, device/inode, size, nanosecond mtime and a SHA-256
of the first 64 KiB. The original discovery path is also retained, so deleting
or repointing a selected symlink invalidates it even if its old blob remains.
Identity is checked before loading, during review and at
final application. This is a replacement/change guard, not a full-weight
cryptographic integrity audit; edits that deliberately preserve file identity,
mtime and the header are outside that guard.

Press **Install / rebuild isolated runtime** after saving the desired backend.
This explicitly installs runtime code only in `llm-scoring/runtime/`, never
into Parseh's Python environment. The package pins are in
`lib/lm-scoring-requirements.txt`. The compatible binding version is
**llama-cpp-python 0.3.35**, with its bundled llama.cpp, plus NumPy 2.2.6.
Python versions/platforms need compatible wheels or a working source build.
Changing that pin requires rechecking the low-level C interface and scores.

CPU builds need a C/C++ compiler and CMake (pip's build environment supplies
CMake when needed). GPU builds additionally need CUDA, Apple Metal or Vulkan
build dependencies. Parseh supplies the build flags `GGML_CUDA`, `GGML_METAL`
or `GGML_VULKAN`; it does not install a hardware SDK. Choose **CPU / 0 GPU
layers**, or a matching GPU build and **−1** for all layers (a positive number
requests partial offload). The **GPU device index** selects a device within
that backend; Settings reports devices and free/total memory discovered by the
isolated runtime. The model loader receives only that selected device. Zero
GPU layers supplies an empty device list and disables context/operator offload,
even in a GPU-capable binary. Missing devices and incomplete requested offload
fail explicitly; no silent GPU-to-CPU fallback occurs.
CPU threads, context tokens, load timeout and per-target scoring timeout are
explicit settings. Metal and Vulkan require validation on the target computer.

CUDA builds also expose a **CUDA host C++ compiler** path and build
architectures (`native`, or a list such as `75;86`). Match the compiler to the
toolkit: use a supported installed compiler or enter its absolute path. An
isolated toolchain under `llm-scoring/toolchain/` is used when present and no
override is set. Parseh's
Settings installer does not install a compiler/SDK itself. Builds target this
computer's CPU and the configured CUDA architecture; rebuild on a different
host. The Settings button builds from source. **Force CUDA quantized matrix
kernels (MMQ)** is available for supported devices; follow the installed
runtime's device diagnostics and the toolkit's architecture support. Do not
set obsolete architectures for an incompatible toolkit.
Quantized CPU/GPU arithmetic and cache precision can produce different raw
scores and additional candidate sets. Repeats within one backend must agree;
scores from different execution backends are not assumed bit-identical.

An already installed, separate compatible interpreter may be entered instead.
For development, the equivalent CPU setup is:

```sh
python3 -m venv llm-scoring/runtime
llm-scoring/runtime/bin/python -m pip install -r lib/lm-scoring-requirements.txt
llm-scoring/runtime/bin/python -I lib/lmlikelihoodworker.py --probe
```

GPU installation uses the same command with the appropriate `CMAKE_ARGS`, e.g.
`CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=75 -DCMAKE_CUDA_HOST_COMPILER=/absolute/path/to/g++" FORCE_CMAKE=1`
before pip. Use `--no-binary=llama-cpp-python --no-cache-dir --force-reinstall`
to force a source rebuild. An optional CPU wheel index
is documented by [llama-cpp-python](https://llama-cpp-python.readthedocs.io/en/latest/).
The Settings button uses a source build so the selected hardware flags take
effect. No packages or weights are installed by opening settings or starting
Whisper.

After Whisper finishes, explicitly choose **LM likelihood**.
The worker loads once for that review, evaluates suspects sequentially, and
unloads when it finishes. **Cancel** kills the worker even during native loading
or decoding; **Cancel scoring and unload worker** is also available in Settings.
It has its own RAM/GPU allocation. Sharing a file saves duplicate weights on
disk, not model memory. Parseh never unloads another application’s model.

## Exact scoring rule

For immutable preceding text `L`, replacement `c` and fixed following text `R`:

`S(c) = log P(c + R | L)`.

Every reconstructed `L + c + R` is tokenized as a complete string, with the
model's actual BOS convention and special-token interpretation disabled.
Independently tokenizing three pieces and joining their IDs is not used for
scoring. The evaluator finds an identical token prefix bounded by `L`, whose
decoded bytes end before the replacement region. It excludes that constant
prefix and scores the entire remaining token suffix, including **all following
context**. A boundary token that merges preceding whitespace with the
replacement remains in the scored suffix. Diagnostics show this preceding
boundary backoff. It is a common-prefix-conditioned token score; when a boundary
retokenizes `L`, the residual `L` bytes necessarily participate in the suffix.

Tokenizers such as PersianMind's SentencePiece can add
an artificial initial space. The worker detects that convention with a fixed
tokenizer round trip and removes only that space when comparing complete
prefixes. Raw continuation decoding retains its leading spaces and partial
Unicode bytes. Real source whitespace is preserved.

For each supplied token `t_i`, the previous position's full-vocabulary raw
logits determine its score:

`log p(t_i) = logits[t_i] − max(logits) − log(sum(exp(logits − max(logits))))`.

The baseline rank uses the **raw sum** of those log probabilities. There is no
temperature, sampling, repetition penalty, top-N renormalization, mean
perplexity or length correction. Token counts and differences from the original
are shown explicitly. Numerical ties within `1e-9` share a rank. If the original
wins it is retained as the highest-ranked candidate, with a zero difference.
If the model supplies no BOS and no safe preceding token, a first-token score
is unavailable and that candidate is explicitly unscored. No implicit BOS or
unconditional score is invented.

Each candidate evaluation clears all inference memory and evaluates an
independent prefix. Native GPU work is synchronized before reading logits,
clearing memory or freeing a context. The final target token needs only the
preceding logits, so no unused final decode is queued. There is no shared-prefix
cache. Any future caching must prove score equivalence and isolation.

## Candidates and review

The original source span and **every genuine supplied Whisper alternative** are
mandatory. Evidence collection no longer caps their count at ten or shortens
their text; the chat methods retain their separate short-prompt hint limits.
Missing alternatives remain missing, with no invented acoustic scores.

Additional candidates come from deterministic beam search over raw next-token
probabilities after the original preceding context. Beam width, candidate count,
replacement token length and character length bound only this extra search.
Unicode bytes may span model tokens; a decoded lexical string is admitted only
after an observed boundary or end-of-generation token. A token fragment at the
length limit is not a complete word. Apostrophes/hyphens are allowed internally;
attached original punctuation is preserved. Identical replacement strings are
deduplicated while retaining all origins and Whisper evidence.
Recognizer separator spaces outside the mapped word span are kept in the
fixed context, rather than duplicated inside the replacement; the exact ASR
alternative and its removed boundary-space counts remain in its origin evidence.

The same outside whitespace, punctuation and following text are used for every
candidate at a target. Targets use the immutable original transcript, including
when an earlier target has an accepted draft edit. Caption timing/boundaries
are changed only through the existing explicit application path, which retains
caption clocks and marks changed word timing as needing review.

Ranked candidates include origins, raw log likelihood, token count and difference
from the original. Diagnostics include model identity, context bounds, elapsed
time, search bounds, ties and coverage failures. **Complete** requires scoring
every mandatory candidate. Unscorable, invalid-boundary, context-overflow and
timed-out candidates retain explicit failure reasons. Partial evaluation claims
a winner among evaluated candidates only. Local failures allow later targets
to continue; retries update selected targets only. Global source/settings/model
changes or cancellation discard in-flight results. All changes stay in the
pending draft until **Use this transcript** with the existing hash, video,
language, Whisper-model and overwrite protections.

Worker messages are limited to 4 MiB; retained candidate reviews to 4 MiB; detailed
job history to 100 entries / 512 KiB. Exceeding storage never silently implies
complete coverage. Transcripts/logit matrices are not written to application
logs; full vocabulary logits never leave the worker. The result and diagnostics
are private pending-review data, not preferences, release content or sync payloads.
Very large reviews can exhaust retained-score storage; those source IDs are
explicitly marked incomplete, including after retries. Their source alternatives
remain available, but new ranked results cannot be retained until there is room.

Bounded beam search is not an exhaustive lexical search. It can miss plausible
words, especially with no whitespace boundaries or chat-tuned models whose raw
continuation probabilities favor something else. One target at a time cannot
resolve interacting errors jointly. Raw sums are sensitive to token count and
context bounds. Whisper confidence and LM scores remain separate; neither the
scores nor a normalized ranking are calibrated probabilities of correctness.

## Search filters and saved drafts

The optional minimum candidate search probability applies only to completed
model-derived search paths. The settings page offers **No cutoff** (0),
**0.1 — suggested by preliminary experiments**, and an editable **Custom cutoff**.
The saved choice is used by the worker. The default is **0.1**, suggested as a
conservative first-pass cutoff from preliminary experiments; it is not a
universal accuracy threshold. It is the product of full-vocabulary next-token
probabilities along that path, including any reproduced prefix-boundary bytes
and the completion-boundary token. It is length-sensitive and is not a
probability of transcription correctness. Search branches already below this
cutoff are pruned because extending them cannot increase path probability.
It does not change supplied-text
scoring, renormalize logits, or filter any mandatory candidate.

The similar-sound filter is on by default, with a 0.55 similarity bound.
Installed dictionary readings are compared by normalized edit distance when
both words have readings. Otherwise modest Latin/Persian/Arabic spelling
folding and kana equivalence are used. Unknown Han pronunciation bypasses
filtering instead of inventing a reading. This is a conservative approximation,
not an acoustic model or a universal multilingual phonetic recognizer.
The review checkbox changes only that run. Unfiltered single-word or selected
second passes retain the same original context and exact application guards.
Turning off the sound filter leaves the saved search-probability cutoff in
place. Lower it with the Candidate cutoff chooser (zero disables it) for a wider search.

Locked stable IDs are excluded on the server for all methods. Selected targets
retain full original bounded context. A single-word likelihood call may also
review a mapped confident word. Bulk acceptance uses the last run's targets,
skips locks, incomplete mandatory coverage and top-score ties, and changes only
the draft. Manual and accepted edits survive switching methods.

Pending reviews are atomically saved under
`youtube/videos/.pending-transcriptions/`, with a versioned format and a 16 MiB
record bound, a 256 MiB total budget and a 100-record limit. Existing drafts
are never deleted to make room; a full store is reported. Only allowlisted source/evidence/review fields, held timing,
waveform peaks and browser draft data are retained, never temporary audio,
credentials, executables or processes. The directory is protected from static
HTTP serving and excluded from Git. At most 100 drafts are listed; each draft
is retained until explicit Use or discard. Four pasted-answer drafts of at most
131072 characters each are retained. There is no transcript text in ordinary
logs or sync preferences. Files and folder request owner-only permissions
(on Windows, access follows the containing user's filesystem permissions).

A restart restores pending state without loading a model or resuming inference.
Interrupted model work is marked incomplete. Source identity is checked on
resume, before review and on Use; changing or deleting the original local film
prevents applying that draft. Save & pause cancels the active worker, releases
its model memory and keeps decisions. A failed disk save is shown explicitly.
Use removes the temporary record while preserving the ordinary word timing and
waveform handoff. Recording must finish before there is a resumable transcript.

## Validation

`python3 -m unittest discover -s tests -p test_lm_likelihood.py` exercises small
numerical models, complete reconstruction and boundary tokenization, preceding
logit alignment, a following-context rank reversal, multi-token words, mandatory
alternatives outside search limits, original winners/ties, deduplication,
partial coverage, missing first-token scores, read-only discovery (including
Ollama blobs without suffixes), GGUF validation, lifecycle cancellation/timeouts,
immutable spans and stale source/model rejection. The browser smoke script is
`tests/lm_likelihood.mjs` (Node + Playwright core and Chrome).

Runtime/scoring integration checks do not establish correction accuracy.
Accuracy requires labeled real errors **and correctly recognized words** across
relevant languages. Keep recordings, reference labels and evaluation reports
outside the source checkout and release artifacts.

The optional reproducible live check is:

```sh
python3 tests/lm_likelihood_real.py --model /absolute/path/to/installed.gguf \
  --modes cpu,cuda-partial,cuda-full --context-tokens 2048 \
  --output /tmp/parseh-likelihood-smoke.json
```

The live check compares CPU, partial GPU and full GPU evaluation, independent
repeats, changed candidate order, mandatory coverage, cancellation and unchanged
model identity. It reports backend score differences and its explicit numerical
tolerance. That example's tolerance is not a general accuracy criterion or an
adjustment to the score. Near-tied candidates can change order across quantized
backends. Hardware validation establishes lifecycle and numerical scoring
behavior, not improved ASR accuracy.

Upstream references: [low-level llama.cpp binding](https://llama-cpp-python.readthedocs.io/en/latest/api-reference/),
[GGUF specification](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md),
[Ollama model metadata API](https://github.com/ollama/ollama/blob/main/docs/api.md#show-model-information).
