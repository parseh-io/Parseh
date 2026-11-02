---
title: Linguistic analysis
weight: 13
description: Optional analyzers on your computer, UDPipe, Farahidi and Starlang, that Parseh can listen to for the dictionary panel, for the phrases of new text and for the gloss prompts. All of it is off until you turn it on.
---

A dictionary knows what a word can be. An analyzer reads the sentence and says what
the word probably is here: above all **its part of speech**. So `ran` in *They ran home* is
a verb, and the dictionary shows you *run* and not the noun. It can be wrong, so Parseh
shows what it read as a suggestion, and only where you ask.

Everything is on **Settings → Linguistic analysis**. Getting an analyzer changes no
result. You choose what it is used for, one thing at a time.

## What there is to get

| Language | Analyzer | What it takes |
|---|---|---|
| English, German, Spanish, French, Italian, Hindi, Persian | UDPipe, one model per language | the program, a few MB, and a model of 11 to 26 MB |
| Arabic | Farahidi: every reading of a word, and the lemma its sentence chooses | about 12 MB, and half a gigabyte of memory while it works |
| Turkish | Starlang: every reading of a word, without choosing | about 75 MB with what compiling it takes; compiled when installed, so it needs a C compiler |
| Arabic, Turkish | UDPipe as well, for the structure of the sentence | a model of 20 or 8 MB |

Japanese and Chinese keep the analyzers they have: nothing here changes them. A language
you added yourself has none of this, and goes on as before.

Tick what you want, and press **Get it**: the button says how much it is. It fetches only that, from
the addresses Parseh knows, and checks each file against its hash. **Remove…** on a row takes it away again, after
asking, and **Remove all of it**, under *Where it is on this computer*, takes the whole folder. Your books, videos and
dictionaries are never touched.

> **The UDPipe models have a licence of their own.** They are CC BY-NC-SA 4.0: free for
> non-commercial use and shared on the same licence. They are not part of Parseh and are
> fetched only when you ask, so you can use Parseh without them, with nothing of that
> licence on your computer. The page and the
> licences page say whose work they are.

## What they are used for

Each is off until you change it, and each can be set by itself. The page says in which languages each can work.

- **The dictionary panel: part of speech.** *Show the part of speech* puts a chip beside each
  word saying what it is in this sentence, a line under it with its lemma and grammar, and
  **fits this sentence** on the entry of that part of speech. A word's entries are usually one to a
  part of speech, so this is the entry that means what the sentence means. Where all a
  word's entries are the same part of speech, nothing is marked. *Also put what fits first* moves
  that entry to the top, adds it if only other parts of speech had been found, and looks up
  a word the dictionary missed under its lemma, saying that is how it was found. No entry is ever dropped.
  The panel needs the language's own dictionary, from [Reading help](reading-help.md).
- **Cutting new text into phrases.** When a new book or video is cut into phrases, the analyzer's
  reading of the sentence is listened to. Your punctuation still comes first, and the text is
  never changed. Chunks you have edited are never cut again, by this or anything else.
- **The gloss prompts.** Copy prompt and the skill's request, for a stretch of a book or a
  video: each chunk to do carries what the analyzer read in it, with a rule telling the model it
  is fallible, that the sentence wins, and that it is not part of the answer. The sheet says how many chunks carry
  it, or why none does. Nothing of it is ever stored with a gloss. Your own prompts keep the rule too. After turning this on, download
  the `parseh-gloss` skill again, as **Settings → Skills for your chatbot** reminds you.

A book being made in place by an agent can ask too: while the gloss prompts' choice is on, the book's
instructions tell the agent about a helper that reads a sentence and writes nothing.

### Spoken Persian

The analyzers learned Persian from written text, and the dictionary's own reading of spoken Persian knows what a
spoken word stands for, so each helps the other. With the part of speech on, every spoken word goes to the analyzer in its
formal spelling, so `خونشون` reaches it as `خانه‌شان`, a noun, and the sentence around it can be read. Its part of speech then
chooses among the spoken readings: `بده` is "let him give" in `پولو بده` and may be "it is bad" elsewhere. Which spoken reading a
word has is the dictionary's business, not the analyzer's: what the analyzer guesses as a lemma for a word it has never seen
chooses nothing. Your text is not touched: this formal version is only what the analyzer reads.

### What they add, measured

Fresh sentences written for the purpose, judged by hand and looked up on a full dictionary, with nothing tuned to them:
one person's judgement of a small sample, not a promise about your text.

| | right word first | on the panel at all | part of speech right | **fits this sentence** right |
|---|---|---|---|---|
| Spoken Persian, the dictionary alone | 79% | 84% | | |
| Spoken Persian, with its spoken reading | 90% | 97% | | |
| Spoken Persian, with **Also put what fits first** | 92% | 97% | 81 of 81 | 20 of 20 |
| Turkish, the dictionary alone | 84% | 89% | | |
| Turkish, with UDPipe only | 92% | 97% | 81 of 81 | 12 of 12 |
| Turkish, with Starlang only | 92% | 97% | | |
| Turkish, with both, as you get them | 97% | 100% | 85 of 87 | 15 of 16 |

So in these two languages it is worth having both on, and for Turkish both analyzers: Starlang knows what a word can be, UDPipe
which of those the sentence reads, and where the two name the same word (`adamı`: `adam`, not `ada`) that decides it.

## Try it

**Try it** reads a sentence of yours: the phrases with and without the analyzer, what the dictionary finds only with
it where the language has a dictionary, every word with what the analyzer made of it, and what a prompt would
carry. Nothing is kept. It is the way to see whether an analyzer helps your language before you turn it on.

## When it cannot help

If an analyzer is missing, fails, or cannot line its answer up exactly with your text, Parseh does
what it did before and says nothing in the page you are reading. **Try it** says why.

It works on this computer, for whichever device is asking. Nothing is ever sent elsewhere, and a
page you are reading offline never tries to run it.

The first request of a language loads its model, about a second; after that a sentence takes a few
thousandths of a second. The program goes away after ten idle minutes, with its memory.

## Is it any good?

It depends on the language and on the sentence, which is why it stays optional. On a set of test sentences in ten
languages the marked entry was nearly always the right one, and clearly best on verbs, adjectives and function words.
Arabic was the weakest: an unvowelled `ضرب` was read as a noun in *the boy hit the ball*, and the noun then
comes first. The models are small and make mistakes a reader would not, and Starlang never chooses among the readings of a
Turkish word: there it is UDPipe that chooses, among Starlang's readings. On Linux all of this has been installed
and run. **On Windows and macOS it has not been tried yet**, Starlang's compile above all.
