---
title: LM likelihood
weight: 10
description: Compare possible transcript words using a model already installed on this computer.
---

**LM likelihood** suggests words by comparing their fit with the surrounding
transcript. It runs locally, using a model you already installed, and is one of
the tools of [the transcript review](transcript-review.md). Whisper has its own
settings.
It is an **experimental** correction method; check suggestions by listening.

## Choose a model

Open **Settings → LM likelihood**, press **Refresh installed models**, choose
a model and press **Use selected model**. Model selection is available from
any admitted browser. The selected model also appears in the review's
**Models, preferences & skills** panel.

The **Candidate cutoff** chooser offers **No cutoff**, **0.1 — suggested by
preliminary experiments**, or **Custom cutoff** between 0 and 1. Press
**Save review options** to keep your choice. The cutoff affects only extra
model suggestions; Whisper's original and genuine alternatives are always
compared. The suggested 0.1 is a starting point, not a proven accuracy setting.

For the first setup, expand **Setup & advanced options** on the Parseh computer.
Choose **Installed Unsloth GGUF**, **Installed Ollama model**, or an explicit
local model path. Save the settings before refreshing the list. Parseh uses
existing weights read-only: install models yourself in Studio, Ollama or
another application. A model on another computer must also be accessible to
this local worker.

The local scoring program is installed separately with **Install / rebuild
isolated runtime**. It needs a C/C++ compiler; GPU builds also need the matching
hardware toolkit. Choose **CPU** with **0 GPU layers**, or a supported GPU
backend with **−1** for all layers. Its memory use is separate from Studio or
Ollama, even when they share the same model file. Parseh does not unload their
models. **Cancel scoring and unload worker** stops Parseh's scoring work.

Complete single-file text-generation GGUF models are supported, including
Ollama backing files without a `.gguf` filename. Split weights and required
adapters are refused. Models labeled **text only** use their complete text
model without optional vision files.

## Review words

After Whisper finishes, choose **LM likelihood**. Click, focus or tap a word
to inspect the alternatives. The original and every genuine Whisper alternative
are compared alongside additional words found by the local model. No chatbot
prompt or assistant response is used.

**Prefer similar-sounding words** starts enabled. Turn it off for a second
pass on unresolved words. The filter uses dictionary readings where available
and otherwise a spelling approximation. When pronunciation cannot be inferred,
such as an unfamiliar Han character, it keeps the candidate available. It
never removes Whisper's original or supplied alternatives.
Turning it off keeps the saved probability cutoff; lower it with the
**Candidate cutoff** chooser if you need a wider search.

Choose **Select a section**, then its first and last word. Methods review only
unlocked targets inside that section while keeping the surrounding context.
For one word, use **Review this word with LM likelihood** in its inspector;
this also works for a word Whisper did not flag.

Accept an alternative or enter a correction yourself. **Select best for all**
chooses the latest method's first choices in the pending draft, skipping locked
words, incomplete comparisons and tied first choices. Listen before trusting
these choices: a fluent word can still be wrong. **I'm sure · lock word** keeps
a checked word through later methods; unlock it to reconsider.

**Save & pause** keeps the pending transcript, decisions, edits and locks on the
Parseh computer. Reopen it with **Continue pending transcription** in Videos,
even after a server restart. Only **Use this transcript** fills the transcript
box. Use or discard removes the saved review. Caption timing stays unchanged;
changed word timing needs review in the existing timing editor.

## When a comparison is incomplete

If a word cannot be fully compared, its original remains available. Other
words can still finish. Retry unresolved words or edit them yourself. The
ordinary inspector shows choices; **Technical details** and **Review diagnostics**
hold the numerical scores, model identity, bounded context and failure reasons.
These scores measure language-model fit, not the probability of having heard
the right word.

Bounded word search can miss useful alternatives, especially in languages
without spaces. Single-word comparison cannot resolve interacting mistakes
jointly. The installation's `docs/lm-likelihood.md` explains the numerical rule and limits.
