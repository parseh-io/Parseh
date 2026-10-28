---
title: The LLM prompt page
linkTitle: LLM prompt
weight: 3
description: The text that makes a language model answer in the studio's dialect, in the parts you choose, with the target language picked and your question added.
---

A language model knows Markdown but not the studio's dialect: it does not
know that `## کتاب | ketâb | …` is a vocabulary entry, that a sentence of
the target language goes in `[…]{tl}`, or that a gloss's translation is
written in italics so that the glossary can find where it ends. The
**LLM prompt** page, `/studio/prompt` — the library's **LLM prompt**
button — holds the text that teaches it all that, ready to copy in front of
your question. The model then answers with a document the studio reads as
it is, typeset and verified.

That text is long, and some chatbots take less at once than the whole of
it, so **you choose what the model is taught**. A short question about one
word needs no lesson in formulas, drawings or exercises. You tick the
features the document may use, and the copy explains those and no others —
and still tells the model, once and in short, which marks the studio reads,
so that it does not write one by accident.

## The workflow

The page says it in one line under the prompt:

1. Tick what the document may use, or pick a preset.
2. Copy the prompt with your question.
3. Ask your LLM: paste the lot into one message.
4. Download the `.md` file it writes, or copy its whole reply.
5. Back in the library, **Upload .md / .zip**, or **Paste LLM answer**.
6. Read it typeset, tag it, build the verified PDF.

A model that cannot make a file answers in the chat instead: see
[a file, or one fenced block](#a-file-or-one-fenced-block), and
[Bringing documents in and out](documents-in-and-out.md).

## The page

- **target language** is a menu at the top, above the boxes: the language
  the document will be *about*. It starts on the language the toolbox is set
  to. What it changes is what is copied: a first line stating the target
  (*target: fa — this document is about Persian: write `target: fa` in the
  front matter*), the boxes the language can use, the rules that are
  written differently for a script of its own than for a Latin-script
  language, and, under the rules, that language's own conventions — its
  transliteration scheme, its reading rule, what to hyphenate.
- **Teach the model to write:** is the set of boxes below. A line above
  them says that whatever you leave unticked is still named in the prompt as
  reserved. Each box has its name, one line on what it lets the model
  write, and how many characters it adds. Ticking or unticking one changes
  the prompt and the size at once, and a total stays in view at the foot of
  the window while you tick: the prompt without your question, and how much
  of it is there whatever you tick. See [the boxes](#the-boxes).
- **The presets** tick a set in one press. See [presets](#presets).
- **The prompt box** shows what will be copied, and its size: *about N
  characters (about M tokens)*. A chatbot counts about four characters to a
  token in Latin script and about two in Arabic script, Chinese, Japanese
  and Devanagari. Past about eight thousand tokens the page says that some
  chatbots take less at once, and that you can ask for less or send the rules
  and the question in two messages.
- **Your question** is the box under the prompt, for what you want to know:
  *the Persian words for hot and cold: uses, registers, opposites,
  compounds.*
- **For a learner at** and **length** are two choices under the question,
  each copied as one line at the end of the prompt. See
  [level and length](#level-and-length). A third choice stands with them
  where the language has one: the scheme of its transliteration, labelled
  with the language's own word for it (*transliteration*, *rōmaji*,
  *pronunciation*), **usual scheme** or **IPA**. With IPA the prompt's first
  line ends **· IPA**, and the choice is remembered on this device, one for
  each language. Chinese has none yet.

The ticked boxes, the level and the length are remembered on this device,
one set for every language: change the target language and the same boxes
stay ticked (a box the new language cannot use is hidden until you come
back to a language that can).

The prompt is written in no particular prose language: it tells the model
to answer in the language of your question, so a question asked in Italian
gets a document written in Italian about Persian.

## What is always in the prompt

Whatever is ticked, the copy has the same first and last parts:

- **The task**, and what the file must be: the front matter (`title`,
  `subtitle`, `note`, `lang`, `target`), `##` for sections and `###` for
  subsections and nothing deeper, and no numbers typed into titles.
- **How the target language is written.** A script of its own is found by the
  studio without a mark, and a Latin-script target — Italian, French,
  German, Turkish, English, Spanish — has every run of it marked `[…]{tl}`,
  which the copy says for those languages only.
- **One paragraph, one line.** The studio joins the lines of a paragraph
  with a space and reads certain marks at the start of *any* line, so a
  paragraph a chatbot wrapped can be cut in the middle: a wrapped line that
  starts with `- `, `* `, `+ `, `> `, `## `, `### `, a number and a full
  stop (a year, `1921. `), `:::exercise`, `:::math` or `::::latex` starts a
  list, a box, a section, a numbered list or a fence there, and a line that is
  only a picture or a video does the same. The model is told to write each
  paragraph as one line, however long.
- **The features are tools, not tasks.** A document uses the few features it
  needs, never uses one to show that it can, never colours a word for the
  sake of it, and never describes its own markup.
- **Pictures, recordings, videos and links to other documents are never the
  model's to write.** They are yours to add in the studio, and a model that
  invents one points at a file that is not there.
- **The reserved marks**: every mark the studio reads, with what it does, and
  the rule *write one only for a feature you were taught; otherwise write the
  sentence without it*. An unticked feature is therefore forbidden by name
  and not just left unexplained: a model that was not taught the footnote
  does not write `x[^2]` for a square, and one that was not taught the
  bold does not write `5 * 3` and italicise everything between the two
  stars. The list also names what the studio does **not** read at all — code
  fences, `_x_`, `~~x~~`, `$x$`, HTML — so that a model does not write them.
  It grows shorter as you tick boxes: a ticked box explains its marks
  itself. [What the studio leaves out](../dialect/left-out.md) is the same list
  for people.
- **The answer contract**, last: how to send the document (see below).

## The boxes

Each box explains one feature, in full, in a few hundred characters. A box
that a language cannot use is not shown.

| Box | The model is taught | Shown for |
|---|---|---|
| **vocabulary entries** | `## word \| transliteration \| origin \| = *meaning*` | every language |
| **glosses** | `word = *meaning*`, with the italics on the meaning only | every language |
| **transliteration on a word or short phrase** | `[word]{translit:…}`, never on a whole example sentence | every language (optional in a Latin-script one) |
| **reading marks** | `[word]{kana:…}` | a language with a reading (Japanese) |
| **the target language's own punctuation** | the Latin mark almost everywhere, the language's own inside its own sentence | a language with a script of its own |
| **right-to-left sequences** | the order of separately marked right-to-left boxes in a left-to-right line | Persian and Arabic |
| **passages and display lines** | `[…]{tl}` blocks, `⏎`, tinted blocks, `font=` and `vertical` where the language has them, display lines | every language |
| **Latin blocks** | `[…]{la}` | every language |
| **wrong and right forms** | `✗form`, `✅` | every language |
| **lists** | bullet, numbered and labelled lists | every language |
| **tables** | pipe tables | every language |
| **highlight boxes** | `>` | every language |
| **bold and italic** | `**bold**`, `*italic*` | every language |
| **footnotes** | `[^x]`, `^[…]` | every language |
| **links** | `[words](https://…)` | every language |
| **colour marks** | the five named colours and a hex value | every language |
| **colour inside a word** | `[[ab[cd]{teal}ef]]`: part of one word in colour, its stem against its ending | every language |
| **formulas** | `[…]{math}`, `:::math` | every language |
| **LaTeX drawings** | `::::latex`, `[…]{latex}`, and the themes this computer has, each with what its packages are for | every language |
| **exercises** | the `:::exercise` blocks, of every type | every language |
| **keep what a pasted document has** | marks a reader wrote, pictures, recordings and links a document you paste already holds | every language |

**Colour inside a word** teaches the model to colour only a part of one
word — its stem against its ending, a root's letters — in a way the studio
still reads as one word ([Colours, pronunciation and
glosses](../dialect/colours-and-pronunciation.md) shows what a reader sees).
The model is told to reach for it only when a lesson is about how a word is
built, to keep the word whole and on one line, and not to write it in a
note written in place.

**LaTeX drawings** teaches the model the themes this computer has — each with the packages it
adds, the ones ticked in it and the ones its own lines load, and what each package is for
(*xskak: chess moves and boards*) — and to **choose the theme by the commands a drawing needs**:
`\ce` is mhchem's, a `tikzpicture` is TikZ's, so the drawing names the theme that has the
package, writes no `\usepackage` of its own and uses no command that none of the themes has. In
the prompt that adds exercises, it also says where a drawing may stand in an exercise (a mark
anywhere prose goes, a block in a prompt written `prompt: |` or on a Jolly card) and, when a
follow-up is asked for, that a drawing in one of its steps has [one colon
more](../dialect-exercises/follow-up.md#how-it-is-written).

Where two features say something to each other — a colour beside a
transliteration, a list inside a vocabulary entry, a formula in an
exercise — the copy says it only when both are ticked, so that no box points
at a rule that is not there.

## Presets

A preset ticks a set of boxes in one press, and shows as chosen only while
the ticked boxes are exactly its set.

- **a short answer.** Glosses, transliteration, lists, bold and italic.
- **a lesson.** A short answer's, plus vocabulary entries, tables,
  highlight boxes, footnotes, links and wrong and right forms. It is the set
  ticked when the page first opens.
- **a vocabulary study.** Vocabulary entries, glosses, transliteration,
  reading marks where the language has them, tables and lists.
- **a lesson with exercises.** A lesson's, plus exercises.
- **all.** Every box the language can use.
- **none.** Only what is always in the prompt.

No preset ticks colours, colour inside a word, formulas or drawings, and only
the fourth ticks exercises: tick those yourself when the document is about
them. The page
shows what each choice costs, in characters, before you copy it.

## Level and length

Two choices under the question, each copied as **one line** at the end of the
prompt, after the answer contract:

- **for a learner at** — *not said* (the default), beginner,
  lower-intermediate, intermediate, upper-intermediate, advanced. The line
  says *Write for a learner at the … level.*
- **length** — *not said* (the default), short, about a page, exhaustive.
  The line asks to keep it short, to make it about a page long, or to be
  exhaustive and invent nothing.

A choice left on *not said* adds nothing. The prompt itself never asks for a
length: how long the answer is, is what you choose.

## A file, or one fenced block

The prompt asks the model to answer the question **by creating a Markdown
file**, if it can make files: download it and **Upload .md / .zip**. Most
chatbots cannot save a file, so the prompt says what to do instead: give the
whole document in **one fenced block**, opened with four backticks and the
word `markdown` and closed with four backticks, and nothing else inside it.
Copy the whole reply — the chatter round the block too — and **Paste LLM
answer**: the studio takes the document out of the block, whether the fence
is of three backticks or of four, with words before it and after it, and even
when the document itself holds a fence of three.

An answer with no fence at all is taken as it stands, chatter and all, which
is why the fence is asked for: a document that starts with *Sure! Here is
your document* has that line in it.

## Your own prompt

The menu in front of **copy the prompt**, **prompt: Parseh's ▾**, chooses
which prompt this page makes: Parseh's own, or one of [your own
prompts](your-prompts.md), written, changed, kept under another name and
deleted with **new**, **edit** and **delete** beside it. The badge over the
prompt says which is shown (*your prompt: British spellings · Persian*), and
the first line of the prompt says it too (`· custom: British spellings`).

- **Added to Parseh's** goes after Parseh's instructions and takes the boxes
  exactly as Parseh's own does: tick a box, and what it says is there, before
  your text.
- **In place of Parseh's** is your text as you wrote it. It begins as a copy
  of Parseh's own words, with the boxes' blocks in it
  (`{{?vocab}}…{{/vocab}}`): leave them and the boxes work on it. Take them out
  and the prompt is **copied whole**: the boxes are greyed, with one sentence
  that says why, and what you tick changes nothing in it. The level and the
  length are still added, under the contract, which is Parseh's.

Either way the answer contract is added after your text, so that the model's
answer lands the same way. Your prompts are kept in `config/prompts.json` and
not in the library, so the library's **Backup** does not carry them: export
them from **Settings → Your prompts** if you want a copy. The editor's **Exercises ▾ → Generate with LLM…** has its own boxes
and does not use it: see [Exercises in the
editor](editor-exercises.md#generate-with-llm).

## A skill, for a chatbot that keeps them

If your chatbot can keep a skill, **copy the request for the skill** beside **copy the
prompt** puts a short request on the clipboard instead of the whole prompt: one line that
names the language, the boxes you ticked, the level and the length, and then your question.
The skill itself is downloaded from **Settings → Skills for your chatbot** and installed once
in the chatbot: see [Skills for your chatbot](skills.md).
