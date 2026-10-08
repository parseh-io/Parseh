---
title: LLM Integration
weight: 9
description: An OpenAI-compatible connection, remote model selection, installed correction skills and explicit browser transcript review.
---

**Settings → LLM Integration** connects browser features to an endpoint you
already run. It starts unconfigured. Whisper and manual transcript entry work
without it. Parseh installs no model software, downloads no weights and starts
no endpoint.

All four transcript-correction methods are **experimental**: suspect-word
correction, whole-text review, reasoning workspace review and LM likelihood.
They can miss errors and suggest wrong changes. Check each proposed change
before using the transcript.

The additional [LM likelihood](lm-likelihood.md) method has its own installed
GGUF selection and isolated scoring runtime. It uses numerical token scores
instead of a chat request; configure it in its separate Settings door.

## Configure the connection

Choose **Ollama**, **Unsloth** or **Generic OpenAI-compatible**. Presets supply
defaults and share the text adapter. Ollama prefills
`http://127.0.0.1:11434/v1`. For Unsloth use your installation's API address
ending in `/v1`; ports vary. The Parseh host reaches the address, so `localhost`
means that host. Hosted or other-computer HTTP(S) endpoints are also possible.

The **API key** control keeps, replaces or clears the masked key explicitly.
It stays in the host's private `config/llm.json`, outside releases and synced
preferences, and is never returned after saving. Endpoint, credential, adapter
and timeout/context changes are made on the host.

**Model selection is available from any device admitted to Parseh**, in the
Browser interface. **Refresh models** lists advertised models. Choose one or
enter an exact ID, then **Save model selection**. This changes only the model,
retaining the destination and credentials. Listing is advisory: the model may
be unloaded later. A small multilingual Qwen model is a starting point; choose
one that works well for your language and computer.

Set the timeout and context budget to match your endpoint. Parseh reserves
instructions/output space and uses bounded sentences with conservative UTF-8
byte estimates. **Save connection** saves all host controls. **Test saved
connection** asks the saved model for a short synthetic text reply and checks
reachability/authentication. It does not establish correction accuracy.
**Clear connection** leaves all Whisper runtimes and models intact.

## Unsloth share links

**Saved Unsloth model profiles** retains up to eight Studio share links.
Paste a link and profile name, then **Save profile link**. **Load selected
profile** uses Studio's API to load an already installed GGUF variant with
its KV-cache type, optional context length and vision option. Missing files
and unsupported link options are refused without downloading anything.
Vision defaults off when omitted; speculative decoding is off. Sentence reviews
disable thinking. The additional workspace review requests reasoning.
Studio controls hardware placement; Parseh reads the loaded context budget.

Profiles and model selection are available from any admitted browser. Profile
links must use the saved endpoint; changing that destination or its key remains
host-only. A failed or unconfirmed load blocks inference until you retry the
profile or deliberately select a loaded model.

Under **Models for transcript review**, choose separate profiles or exact model
IDs for **suspect-word correction**, **whole-text review** and **reasoning
workspace review**. An empty ID uses
the general selection. Starting a review explicitly loads its assigned installed
Studio profile first. It never loads a model on opening a page. Compatible
servers without Studio's native API use saved model IDs directly.

**Import Unsloth run settings** is a separate host-only convenience for reading
an endpoint/model hint. It does not execute the link. Use saved profiles to apply
options through the API, or open the link in Studio.

Create an Unsloth API key using the avatar's **Settings → API** page. Name it,
press **Create** and copy it while shown; Studio shows the key once.

## Review a Whisper result

When [speech to text](speech-to-text.md) finishes on
[Add a video](../videos/adding-a-video.md#speech-to-text), the transcript box
stays unchanged and the transcript workspace opens for editing immediately.
No tool selection is required. **Suspect words**, **Whole-text review**,
**Reasoning workspace**, **LM likelihood** and **Whisper second pass** are
tools you can try on the same draft. Manual edits and locked words survive
later tool runs. The saved LLM destination/model are shown before sending;
connected LLM requests start only when you press a tool button.

**⚠** marks an available Whisper score below **0.5**, not proof a word is wrong.
Missing scores stay missing. **◇** marks a word with no meaning in the installed
language dictionary, using the readers' normalization, base-form and prefix
rules. A dictionary miss is also a suspect-word target, even with a high ASR
score; names and rare words can be valid. An absent or failing dictionary does
not flag words. The word inspector shows dictionary meanings for Whisper's
original, each native Whisper alternative and each proposed LLM alternative,
so you can compare them before
accepting an edit. Meanings use the installed dictionary's language, normally
English, independently of the video's gloss language.

**✎** marks a proposed substitution, **✔** a word the model checked and says is
right, **?** one it kept without being sure and **✗** one it gave no answer for.
Focus, hover or tap any word to inspect evidence or edit it. Only suspect words' available alternatives are sent as
readable hints. The same faster-whisper backend now retains up to five native
beam hypotheses and exposes substitutions that map unambiguously to a source
word. Their **sequence log scores** rank complete recognition hypotheses;
alternative-word probabilities stay unavailable. An empty list means no
unambiguous word alternative was returned, not that the word is correct.
There is no extra recognizer or model download. The model may choose a
better word beyond those hints. Its answer is a complete sentence; Parseh maps
only unambiguous substitutions for suspect words back to their exact spans.
Whole-text review checks every mapped word, including confident words, and can
propose a short contiguous span covering several ASR pieces. The two reviews
have separate prompts and skills. Nearby captions provide bounded read-only
context and are never included in the replaceable target.

**The transcript is yours at any time.** **Use this transcript** is there whenever no
tool is running: while a chatbot review still waits for answers, with half of the
words unanswered, with every proposal skipped. Whatever you accepted or typed goes in; every
other word stays as Whisper wrote it, and nothing has to be gone through first. If a choice
cannot be applied (an edit of your own with a space in a single word, a suggestion that no
longer fits, two edits over the same words), only that choice is left out, and the page
says which and why after the transcript is in the box.

Accept or reject individual proposals. Even when no proposal or ASR alternative
exists, **Enter the correct word** and **Save word in draft** lets you type the
correction yourself. Any reviewable word can be edited, including words without
scores. **Restore Whisper word** undoes its edit. **Pending transcript draft**
shows the pending result. Only **Use this transcript** writes it into the box,
after the existing overwrite confirmation if needed. Cancel leaves the box
untouched. Source, language, Whisper-model or box changes discard stale review.
Caption boundaries and video clocks stay unchanged; edited word timings need
review in the existing timing editor. Using the transcript deletes any
privately held capture audio.

## Go through the model's answers

When a review method has answered, **The model's answers** appears above the
transcript. It says how many words were checked and sorts them into four:
**✎ edits proposed**, **✔ agree with Whisper**, **? not sure either way** and
**✗ with no answer**. Press a count to see its words with the model's reason. A
word the model left alone is not silent: its own panel says whether the model
agrees with Whisper's word or could not tell, and why.

**Go through the answers** (it opens by itself when an answer comes in) shows one
word at a time, in the order of the transcript: the caption with the word
marked, what Whisper heard and how sure it was, and what the model proposes and
why. Choose **Accept**, **Keep Whisper's word**, **Write my own**, **Skip** or
**← Back**; the keys are **A**, **K**, **W**, **S**, **←**, and **P** to listen.
It stops at every proposal, every "not sure" and every "no answer"; tick **Also
walk through the words the model agrees with** to see those too. At the end it
lists exactly what will change, and **Use this transcript** puts it in the box.
Words you skipped wait behind **Go back to the skipped**.

To take edits together, **Accept the N sure edits, then look at the rest** takes
what the model said it was sure of and walks you through the others, and
**Accept all N edits the model proposed** takes every edit and ends with what
will change. A chatbot's workspace answer says how sure it is of each word (a
column called confidence, **sure** or **unsure**, which the prompt asks for), and
for LM likelihood a clear winner counts as sure; the sentence methods do not
rate their answers, so only the second button is there for them.

### When an answer had to be read loosely

Parseh reads a chatbot's answer generously, because chatbots are not exact: it
takes the labelled lines out of a reply with a greeting around them, uses the
rows that fit when one does not, and so on. **It tells you where it had to be
generous.** Such a word wears a **≈** in the transcript, the legend names it, and
its card and its own panel say what was forgiven in plain words: *a line was
picked out of a reply of several; the label was given twice and the first line
was used; a line under the sentence that looked like more of it was left out; a
row did not say how sure the model is; a change reached past the word; the
connected model's run ended with an error after the row was written; a
likelihood comparison could not score some of the candidates.* A word whose
answer was clean carries nothing.

A word read loosely may still be right; it is a reason to look, not a verdict.
When it matters, **Ask again for this word** (key **R** on its card) asks the
model for that word by itself, by the same road you used: a new prompt for the
chatbot with only that word, or the connected model again. **≈ N read loosely**
in the summary lists them all, each with its own **Ask again**, and one button
asks again for all of them. The panel of the pasted answer says the same
beside its counts. **Accept the N sure edits** leaves out a sure edit whose
answer was read loosely: you see it on a card first.

A change the model made that Parseh could not use is no longer shown as "the
model agrees". If the model changed a flagged word in a way that could not be
tied to it (two flagged words turned into one, a replacement that is empty or
far too long), the word has **✗ no answer**, with the model's own words as the
reason. What was left out and touched no flagged word (a change to a word you
did not ask about) is listed in **LLM responses** with the answer.

This applies to every method: suspect words, whole text, the reasoning workspace
(pasted or connected), the likelihood comparison and Whisper's second look,
which now says why when it could not make one.

## Choose a section, keep checked words, or pause

Use **Select a section**, then click its first and last word. Select **Selected
section** to limit any review method to that range. Surrounding text remains
available for context. **All text** restores the full scope.

**Select best for all** chooses the latest method's first alternatives in the
pending draft. Locked words are skipped; incomplete likelihood comparisons and
ties also remain unchanged. Check the choices before using them. **I'm sure ·
lock word** preserves a checked word through later reviews. Unlock to edit it.

**Save & pause** stops model work and keeps the original, pending corrections,
locks, section and pasted answer drafts on disk. **Continue pending
transcription** on Videos or Add Video restores them without automatically
calling a model. This works across browser and server restarts. **Use this
transcript** or discarding the review removes its temporary disk draft. Audio
is not retained; a local source video must still exist at its original path.

## Reasoning workspace review

This is an additional tool; sentence reviews and direct manual editing
remain available. Choose a model supporting reasoning and external tool calls
under **Models for transcript review → Reasoning workspace profile**. For
Unsloth, save its Studio share link and select that profile. It loads only when
you explicitly start its review. Use the endpoint's actual context length;
workspace review requires at least 8192 tokens.

Parseh creates a private temporary workspace containing the entire transcript
without timestamps. Suspects are replaced by numbered blanks. The Whisper
threshold remains **0.5**; installed-dictionary misses are a separate cue.
A CSV pairs each number with the original guess, unchanged Whisper confidence
(or “unavailable”), nearby context and genuine optional ASR alternatives.
Additional CSV files supply stable source IDs and exact caption spacing.

The model first skims unblanked text for missed errors, then processes numbered
entries. By default the whole transcript is one region, as a workspace is for,
in real files the model reads with Python; it is given as many tool calls and as
much time as the small regions below would have had together. Under the review
tools, **Divide the reasoning workspace into regions** (off) cuts it into
regions of a few dozen words, one after the other, for a model that cannot hold
so much; it applies to the next review you start. Tentative first-pass proposals
provide context to the second pass. The bundled skill supplies a small CSV helper so the model can inspect evidence
and save proposals with short Python calls. It still has real file/code tools.
The model runs Python to read files and produce a small proposals CSV;
Parseh checks IDs, exact original spans, duplicates and local substitutions.
These are proposals, not a replacement transcript. All still need your approval.

Python runs on the Parseh host under **Linux bubblewrap**, with no host home,
credentials, network or other processes. Inputs are read-only; only one bounded
CSV is writable. CPU, memory, output and execution time are limited. Nothing is
installed automatically. If working isolation is unavailable, choose another
review method. The endpoint still owns LLM hardware and inference. Temporary
files are removed on completion or cancellation.

Progress counts each mapped source word once across the two passes. A failed
region (or the whole, when it is not divided) leaves unseen words unchanged,
preserves validated entries and continues with later regions. Retry remaining suspect/failed words or edit them manually.
**LLM responses** also shows the actual code/tool calls, bounded tool output and
reasoning supplied by the endpoint. Reasoning support is requested through
Unsloth's API; other compatible endpoints use their model's default reasoning.
This may be slower than sentence review and does not guarantee better accuracy.

## Use an external chatbot

All three review methods also work by copy and paste, without configuring an
endpoint. In the Browser transcript review, expand **Use an external chatbot ·
copy & paste**, choose **Suspect words**, **Whole text** or **Reasoning
workspace**, and press **Prepare external prompt**.

Press **Copy review prompt** and paste it into the chatbot you choose. Bring
its answer back to the labeled answer box and press **Import answer into
review**. Sentence methods ask for complete sentences with the supplied labels;
the workspace method asks for proposals CSV with exact source IDs and original
spans, and for each row whether the chatbot is **sure** or **unsure**. A pasted answer is
read row by row (or, for the sentence methods, line by line, finding the labelled lines
among greetings and notes): a row that does not fit is left out, with its reason on its
words, and the other rows are used. A word it
leaves as Whisper wrote it, marked sure, says that Whisper is right. The panel
shows where you are in five steps (prepare, copy, paste and import, go through
the answers, use), and a pasted answer takes you to **Go through the answers**
at once. Parseh checks the answer before offering edits. A pasted answer is never
executed as code. **LLM responses** also shows imported answers for inspection.

For **Reasoning workspace**, **Download transcript & CSV workspace** supplies a
ZIP containing the entire blanked transcript without timestamps, the evidence
for every numbered entry, source IDs, the skill and Python helper. Attach it to a chatbot with
file/code tools and use the copied prompt. Extract it with `parseh-review` as
the working directory. Its `review.py` helper can check edits as work proceeds
with `review.check()`. Before returning the CSV, run
`python review.py --check --complete`: it reports invalid spans, overlapping
edits, punctuation changes and missing required entries. These checks protect
the transcript structure; you still review whether the proposed words are right.
Paste the resulting proposals CSV back. A chatbot
without file tools cannot use the ZIP: tick **Divide into several prompts**
(under the method, off unless you tick it) before **Prepare external prompt**,
and the evidence is in the prompts themselves, a part at a time.
This external route does not require bubblewrap on the Parseh host: any code
tools run in the external service's environment.

**Suspect words** and **Whole text** use several bounded prompts for a long
transcript. **Reasoning workspace** uses one, however long: its ZIP holds the
whole transcript, which is what a workspace is for, and the prompt only says
where everything is and what to answer; **Divide into several prompts** gives
it parts like the others. Progress counts source words in imported batches.
When a prompt's answer is imported the page says what it came to, shows the next
prompt and offers **Go through these answers** at once; the decisions of every
prompt end up in one draft. **Previous prompt** and **Next prompt** let you
revisit a batch; importing it again replaces that batch's proposals. A malformed
answer leaves previously imported batches and the answer box intact. Missing
or invalid sentences remain unchanged and can be retried. **Finish with the
answers received so far** ends the review with what came in, showing the words
with no answer as **✗** for retry or for your own edit. **Cancel external review** returns to the
review choice with the Whisper result intact. Use **Save & pause** to retain the pending review on disk and reopen it from
Videos, including after a server restart.

Accept/reject and manual edits use the same pending draft as API review. Only
**Use this transcript** fills the existing transcript box, with the same
overwrite and stale-source guards. Endpoint calls and model loading do not
occur in this route. You send the text to an external service yourself when
you paste the prompt or attach the ZIP; choose a destination you are comfortable
sharing that text with. Prompts and downloads contain no audio, host paths,
video IDs, endpoint credentials or unrelated history. The last four pasted answer drafts are saved with the pending review on the
Parseh host; they are not stored in browser preferences or sync.

## Correction skill

Expand **Correction skill** in the review page to download the suspect-word
skill (`parseh-asr-correction`), whole-text skill (`parseh-asr-audit`), or the
reasoning workspace skill (`parseh-asr-workspace`). Each zip
contains its skill folder and `SKILL.md`. In Unsloth, extract the folder under the endpoint user's
`.agents/skills/`, or create the skill in Studio and enable it. It can then be
selected with `@parseh-asr-correction` in a Studio chat.

For API review, select **Unsloth Agent Skills + compatible text** as the saved
adapter on the host. **Install in saved endpoint** creates this exact skill
through Unsloth's authenticated Skills API; it never overwrites an existing
skill. **Check installed skill** checks whether it is enabled and valid.
Choose which skill to check/install and enable **Use installed skill for the
chosen review** before starting LLM review. Parseh
sends the skill invocation and sentence evidence; Unsloth loads the installed
instructions with its `read_skill` tool. Other tools and MCP are disabled.

Workspace review always loads its bundled workspace skill and supplies Python
tools; the installed-skill checkbox applies to the two sentence methods. A
downloaded workspace skill also needs its own file/code tools when used outside
Parseh.

Other software needs its own skill-capable API to invoke installed skills.
Generic compatible endpoints use Parseh's short prompt. A skill supplies reusable
instructions to the same model; it does not train it or ensure better accuracy.

## Progress, failures and diagnosis

Progress counts ASR words processed, including failed attempts, rather than
sentences. Whole-text review counts every mapped word; suspect review counts
selected low-score words and dictionary misses. If one request times out or returns an invalid answer, its words stay
unchanged and the remaining sentences continue. Failed and unresolved words can
be edited manually or sent again with **Retry all remaining suspect words**.
Manual edits remain in the draft. Suspect-word retry excludes accepted words.
Whole-text retry rechecks the affected captions; an acceptance is retained only
when its exact proposal is unchanged. Neither route changes the transcript box.

**LLM responses** shows actual prompts, raw/final answers, supplied reasoning,
finish status and elapsed time. Output-limit failures are visible here. Long
outputs/history are bounded and may be clipped. These records remain temporary
with this job; they are never written to logs or synced. A model leaving a word
unchanged does not establish that it is correct.

**Cancel LLM review** aborts the HTTP work and retains the Whisper result.
Audio, waveforms, host file paths, video IDs, cookies and unrelated history are never sent.
ASR hardware remains in Speech to text; LLM hardware belongs to the endpoint.
This feature adds no mobile reader or mobile app behavior.
