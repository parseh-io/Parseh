Parseh transcript-review skills

The suspect-word package is parseh-asr-correction; the whole-text package is
parseh-asr-audit. Add the chosen skill to a chatbot that supports Agent Skills,
through that chatbot's own settings (most take the ZIP as it is, or the folder
with its SKILL.md). Then use the copy/paste review: the prompt Parseh prepares
carries the evidence, the skill the instructions.

Skills provide instructions. They do not train weights, improve the model's
base language competence, or guarantee that a correction is right.

The parseh-asr-workspace skill describes a two-pass file-and-code review. It is
already inside each downloaded text/CSV workspace (the reasoning workspace
method of the copy/paste review); the chatbot must provide its own file and
code environment.

The workspace package includes scripts/review.py, supplied as review.py in each
downloaded text/CSV workspace. It needs only Python's standard library. Use
review.check() while editing and review.check(require_complete=True), or
python review.py --check --complete, before returning the result CSV. These
checks preserve source spans and required coverage, not linguistic accuracy.
