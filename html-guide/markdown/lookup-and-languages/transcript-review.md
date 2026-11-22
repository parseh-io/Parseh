---
title: Reviewing a transcript
weight: 9
description: The transcript workspace after speech to text, its review tools, and a review by any chatbot through copy and paste.
---

When [speech to text](speech-to-text.md) finishes on
[Add a video](../videos/adding-a-video.md#speech-to-text), the transcript box
stays unchanged and the transcript workspace opens for editing at once. This
page is about that workspace and the tools that help you check what Whisper
heard.

The review tools are **experimental**: the three methods a chatbot answers
(suspect words, whole text, reasoning workspace) and
[LM likelihood](lm-likelihood.md). They can miss errors and suggest wrong
changes. Check each proposed change before using the transcript.

A model reads the text only through a chatbot you choose, by copy and paste:
Parseh holds no connection to a model service. **Whisper second pass** and
**LM likelihood** run on this computer and send nothing anywhere.

## Review a Whisper result

No tool has to be chosen first. **Whisper second pass** and **LM likelihood**
are buttons under **Review tools**; the three chatbot methods are under **Use an
external chatbot · copy & paste**. Try them in any order on the same draft.
Your own edits and locked words survive later tool runs.

**⚠** marks an available Whisper score below **0.5**, not proof a word is wrong.
Missing scores stay missing. **◇** marks a word with no meaning in the installed
language dictionary, using the readers' normalization, base-form and prefix
rules. A dictionary miss is also a suspect-word target, even with a high ASR
score; names and rare words can be valid. An absent or failing dictionary does
not flag words. The word inspector shows dictionary meanings for Whisper's
original, each native Whisper alternative and each proposed alternative, so you
can compare them before accepting an edit. Meanings use the installed
dictionary's language, normally English, independently of the video's gloss
language.

**✎** marks a proposed substitution, **✔** a word the model checked and says is
right, **?** one it kept without being sure and **✗** one it gave no answer for.
Focus, hover or tap any word to inspect evidence or edit it. Only suspect words'
available alternatives are given to the chatbot as readable hints. The
faster-whisper backend retains up to five native beam hypotheses and exposes
substitutions that map unambiguously to a source word. Their **sequence log
scores** rank complete recognition hypotheses; alternative-word probabilities
stay unavailable. An empty list means no unambiguous word alternative was
returned, not that the word is correct. The model may choose a better word
beyond those hints. Its answer is a complete sentence; Parseh maps only
unambiguous substitutions for suspect words back to their exact spans.
Whole-text review checks every mapped word, including confident words, and can
propose a short contiguous span covering several ASR pieces. Nearby captions
provide bounded read-only context and are never included in the replaceable
target.

**The transcript is yours at any time.** **Use this transcript** is there
whenever no tool is running: while a chatbot review still waits for answers,
with half of the words unanswered, with every proposal skipped. Whatever you
accepted or typed goes in; every other word stays as Whisper wrote it, and
nothing has to be gone through first. If a choice cannot be applied (an edit of
your own with a space in a single word, a suggestion that no longer fits, two
edits over the same words), only that choice is left out, and the page says
which and why after the transcript is in the box.

Accept or reject individual proposals. Even when no proposal or ASR alternative
exists, **Enter the correct word** and **Save word in draft** let you type the
correction yourself. Any reviewable word can be edited, including words without
scores. **Restore Whisper word** undoes its edit. **Preview the complete pending
transcript** shows the pending result. Only **Use this transcript** writes it into the box,
after the existing overwrite confirmation if needed. Cancel leaves the box
untouched. Source, language, Whisper-model or box changes discard a stale
review. Caption boundaries and video clocks stay unchanged; edited word timings
need review in the existing timing editor. Using the transcript deletes any
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
row did not say how sure the model is; a change reached past the word; a
likelihood comparison could not score some of the candidates.* A word whose
answer was clean carries nothing.

A word read loosely may still be right; it is a reason to look, not a verdict.
When it matters, **Ask again for this word** (key **R** on its card) asks for
that word by itself, by the same road you used: a new prompt for the chatbot
with only that word, or the likelihood model again. **≈ N read loosely** in the
summary lists them all, each with its own **Ask again**, and one button asks
again for all of them. The panel of the pasted answer says the same beside its
counts. **Accept the N sure edits** leaves out a sure edit whose answer was read
loosely: you see it on a card first.

A change the model made that Parseh could not use is not shown as "the model
agrees". If the model changed a flagged word in a way that could not be tied to
it (two flagged words turned into one, a replacement that is empty or far too
long), the word has **✗ no answer**, with the model's own words as the reason.
What was left out and touched no flagged word (a change to a word you did not
ask about) is listed in **Review diagnostics** with the answer.

This applies to every method: suspect words, whole text, the reasoning
workspace, the likelihood comparison and Whisper's second look, which says why
when it could not make one.

## Choose a section, keep checked words, or pause

Use **Select a section**, then click its first and last word. Select **Selected
section** to limit any review method to that range. Surrounding text remains
available for context. **All text** restores the full scope.

**Select best for all** chooses the latest method's first alternatives in the
pending draft. Locked words are skipped; incomplete likelihood comparisons and
ties also remain unchanged. Check the choices before using them. **I'm sure ·
lock word** preserves a checked word through later reviews. Unlock to edit it.

**Save & pause** stops a running tool and keeps the original, pending
corrections, locks, section and pasted answer drafts on disk. **Continue pending
transcription** on Videos or Add Video restores them without running anything.
This works across browser and server restarts. **Use this transcript** or
discarding the review removes its temporary disk draft. Audio is not retained; a
local source video must still exist at its original path.

## Use an external chatbot

In the transcript review, expand **Use an external chatbot · copy & paste**,
choose **Suspect words**, **Whole text** or **Reasoning workspace**, and press
**Prepare external prompt**.

Press **Copy review prompt** and paste it into the chatbot you choose. Bring
its answer back to the labelled answer box and press **Import answer into
review**. The sentence methods ask for complete sentences with the supplied
labels; the workspace method asks for a proposals CSV with exact source IDs and
original spans, and for each row whether the chatbot is **sure** or **unsure**.
A pasted answer is read row by row (or, for the sentence methods, line by line,
finding the labelled lines among greetings and notes): a row that does not fit
is left out, with its reason on its words, and the other rows are used. A word
it leaves as Whisper wrote it, marked sure, says that Whisper is right. The
panel shows where you are in five steps (prepare, copy, paste and import, go
through the answers, use), and a pasted answer takes you to **Go through the
answers** at once. Parseh checks the answer before offering edits. A pasted
answer is never executed as code. **Review diagnostics** shows the prompts and
the imported answers for inspection.

For **Reasoning workspace**, **Download transcript & CSV workspace** supplies a
ZIP containing the entire blanked transcript without timestamps, the evidence
for every numbered entry, source IDs, the skill and its Python helper. Suspects
are replaced by numbered blanks; a CSV pairs each number with the original
guess, its Whisper confidence (or "unavailable"), nearby context and genuine
optional ASR alternatives. Attach the ZIP to a chatbot with file and code tools
and use the copied prompt. The chatbot extracts it with `parseh-review` as the
working directory; its `review.py` helper checks edits as work proceeds and,
before the CSV is returned, reports invalid spans, overlapping edits,
punctuation changes and missing required entries. These checks protect the
transcript structure; you still review whether the proposed words are right.
Paste the resulting proposals CSV back. A chatbot without file tools cannot use
the ZIP: tick **Divide into several prompts** (under the method, off unless you
tick it) before **Prepare external prompt**, and the evidence is in the prompts
themselves, a part at a time.

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
or invalid sentences remain unchanged and can be retried with **Retry remaining
suspect words**, which prepares a new prompt for them. **Finish with the answers
received so far** ends the review with what came in, showing the words with no
answer as **✗** for retry or for your own edit. **Cancel external review**
returns to the review with the Whisper result intact. Use **Save & pause** to
keep the pending review on disk and reopen it from Videos, including after a
server restart.

You send the text to an external service yourself when you paste the prompt or
attach the ZIP; choose a destination you are comfortable sharing that text
with. Prompts and downloads contain no audio, host paths, video IDs or
unrelated history. The last four pasted answer drafts are saved with the
pending review on the Parseh computer; they are not stored in browser
preferences or sync.

## Correction skills

Expand **Correction skills**, under **Models, preferences & skills**, to
download the suspect-word skill (`parseh-asr-correction`), the whole-text skill
(`parseh-asr-audit`) or the reasoning workspace skill (`parseh-asr-workspace`).
Each ZIP contains its skill folder with its `SKILL.md`. Add the one of the
method you use to your own chatbot or agent, through that chatbot's own
settings, then use the copy/paste review as above: copy Parseh's prompt into
the chatbot and paste its answer back. The prompt carries the evidence; the
skill carries the instructions and the exact form of the answer Parseh reads
(labelled sentence lines for the two sentence methods, the proposals CSV for
the workspace). The workspace ZIP of a reasoning workspace review already
carries its skill and helper. A skill supplies reusable instructions to the
same model; it does not train it or ensure better accuracy.

## Diagnosis

**Review diagnostics** shows the exact prompts and the answers imported for the
current review, and the likelihood model's numerical comparisons. Long
histories are bounded and may be clipped. These records stay with this review
only; they are never written to logs or synced. A model leaving a word
unchanged does not establish that it is correct.

**Stop current tool** stops a running Whisper second pass or likelihood review
and keeps the Whisper result. Audio, waveforms, host file paths, video IDs,
cookies and unrelated history are never sent.
