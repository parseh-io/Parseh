---
title: Skills for your chatbot
linkTitle: Skills
weight: 4
description: The prompts as skills a chatbot can keep — downloaded from Settings, installed once in the chatbot, and used with a short request instead of the whole prompt.
---

Every button that copies a prompt puts the whole instructions on the clipboard,
and you paste them into a chatbot each time. Some chatbots can keep instructions
instead, as a **skill**: a folder of files that the chatbot holds, reads only when
a message calls for it, and uses again and again. Parseh makes its prompts as skills
too, so that in such a chatbot a short **request** is enough.

A skill is only text, like a prompt. Downloading one, or copying a request, runs no
model and sends nothing: you carry the file to your chatbot and the request to a
chat yourself, and **Parseh never starts anything** for you.

## What there is

- **parseh-gloss.** Glosses chunks in Parseh's JSON: a stretch of a book or of a
  video (fill what is blank, fill the fields named, or gloss it afresh), and a whole
  video from its captions.
- **parseh-markdown.** Writes a document in the studio's dialect, or exercises for one,
  with only the features you ticked.
- **parseh-book.** The method of a book made by an agent in the book's own folder
  ([Adding a book](../books/adding.md)).

Each is made **when you ask for it**, from the same parts the prompts are made of, with
the languages this computer has — one you added included — and kept nowhere. So a skill
and a prompt never say different things: for the same request they hand the chatbot the
same words.

## Downloading one

Open **Settings → Skills for your chatbot** (`/settings/skills/`). Each skill has a
card with what it does, its size, the version of Parseh that made it and a short
**hash**, and **download (.zip)**. Any device that has been let in may read the page and
download ([From a phone or another computer](../getting-started/other-devices.md)).
There is **no install button**: installing is always your own step, in the chatbot.

The page remembers on this device which skill you downloaded last. When Parseh would
make another one now — you updated Parseh, changed a language, or made, changed or removed a
[LaTeX theme](../dialect/latex-drawings.md#themes), whose name and packages the skill carries — it says *your skill
may be older than this Parseh — download it again*.

## Installing it, tool by tool

What follows is what each tool's own help says, and the page in Settings links that help.
Where something is not known, it says so.

| In | What to do |
|---|---|
| **claude.ai** and the **Claude desktop app** | **Customize → Skills**, **+**, **Create skill**, **Upload a skill**, and the zip. Code execution must be on (**Settings → Capabilities → Code execution and file creation**), and the skill's switch must be on afterwards. On a Team or Enterprise plan an Owner decides whether skills are allowed. Some people still see the older wording, **Settings → Capabilities**. Uploading the same name again may ask you to replace it. |
| **Claude Code** | Unzip it and put the folder in `.claude/skills/` in your home folder (every project) or in a project's folder (that project). A skill you uploaded to claude.ai reaches a signed-in Claude Code, version 2.1.273 or newer, by itself. |
| **Codex, Gemini CLI, Cursor, GitHub Copilot, VS Code** | Unzip it and put the folder in `.agents/skills/`, in your home folder or in a project. Claude Code does **not** read that folder; Copilot, VS Code and Cursor also read `.claude/skills/`. |
| **The Gemini app** | **Settings → Skills → Upload**, on the web or in the Mac app. The mobile app can use a skill once it is uploaded. |
| **ChatGPT** | Only on the workspace plans (Business, Enterprise, Healthcare, Edu): **Plugins → Skills → Create → Upload from your computer**. Nothing in OpenAI's pages names an upload on the Free, Plus or Pro plans. |
| **A phone** | Install on the web or the desktop app: a skill belongs to your account, not to one device. Using one on a phone is documented only for Claude's Cowork sessions; for a plain chat it is not documented, so nothing more is promised. |
| **A chatbot with no skills** | Use **copy the prompt**: the same instructions in one paste. A project or a Gem keeps files but loads them whole, so the files of a skill are not free there. |

Some tools (Microsoft 365 Copilot's Cowork and Agent Builder) want `SKILL.md` at the root of
the zip rather than inside a folder: unzip it and zip the folder's contents.

## Using it

Wherever Parseh hands out a prompt for a skill — the video's and the book's **gloss
with an LLM**, the add page's prompt for a video, the studio's LLM prompt page and the
exercises dialog — the row has **copy the request for the skill** beside **copy the
prompt**. The one you used last comes first, and neither is ever hidden. Under them:
*in a chat where the parseh-gloss skill is installed, paste this — 310 characters instead
of 16,400.* Paste the request in a chat where the skill is installed, and the chatbot
answers as it would to the prompt: the same answer, which lands through the same doors.

The transcript tidy and Ask LLM have no skill: their prompts are short already.

### What a request looks like

```
Parseh request · parseh-gloss · a0.4.2 · k7f3 · a stretch of a video · fa → en · re-gloss
```

One line, its fields parted by ` · `: the skill, the version of Parseh, the hash, what
it is for, the language and the language of the meanings, the mode, and any choice made
for the prompt — the scheme of the transliteration (`translit: ipa`) and the short
vowels (`marks: on`). For the studio it also names the boxes you ticked
(`features: vocab, gloss, translit`), the level and the length. The text to work on
follows: the chunks, the captions, your question or the page.

The line ends with a sentence for a chat that has no such skill: it tells the chatbot to
say so and stop, and **copy the prompt** is the way. If the hash in the line is not the
skill's own, the chatbot says in one line that the request is for a newer skill than the
one installed.

A prompt of yours that is *added* to Parseh's ([Your own prompts](your-prompts.md))
goes after the first line, and its name is in it. One *in place of* Parseh's cannot
travel in a request, because the skill carries Parseh's instructions: the row says so
beside the button.

## What was not tried

Parseh could not install a skill in each vendor's product from here: the steps above are
what the vendors' own pages say, read on 2026-09-29, and what a chatbot does with a
skill is its own. If a step no longer matches what you see, the tool's help page linked in
Settings is the authority, and **copy the prompt** always works.
