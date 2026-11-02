---
title: Linguistic analysis
weight: 13
description: Optional analyzers on your computer, UDPipe, Farahidi and Starlang, that Parseh can listen to for the dictionary panel, for the phrases of new text and for the gloss prompts. All of it is off until you turn it on.
---

A dictionary knows what a word can be. An analyzer reads the sentence and says what
the word probably is here: its lemma, its part of speech, its grammar, what it
belongs to. It can be wrong, so Parseh treats what it says as evidence, and only
where you ask.

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

Press **Get** on a row. It fetches only that, from the addresses Parseh knows, and checks
each file against its hash. **Remove** takes it away again, and **Remove all of it** takes
the whole folder. Your books, videos and dictionaries are never touched.

> **The UDPipe models have a licence of their own.** They are CC BY-NC-SA 4.0: free for
> non-commercial use and shared on the same licence. That is why they are not part of
> Parseh and are fetched only when you ask. The page and the
> licences page say whose work they are.

## What they are used for

Each is off until you change it, and each can be set by itself.

- **The dictionary panel.** *Show* adds a line under each word saying what the analyzer
  read it as, and whether its sentence chose that. *Show and find* does that too, and a word
  the dictionary did not find is looked for under the analyzer's lemma. A lemma counts only if
  it lands on a real entry, and the row says that is how it was found. A word the dictionary
  did find keeps everything it found. If the sentence chose one of its entries, that one comes first.
- **Cutting new text into phrases.** When a new book or video is cut into chunks, the analyzer's
  reading of the sentence is listened to. Your punctuation still comes first, and the text is
  never changed. Chunks you have edited are never cut again, by this or anything else.
- **The gloss prompts.** Copy prompt and the skill's request, for a stretch of a book or a
  video: each chunk to do carries what the analyzer read in it, with a rule telling the model it
  is fallible, that the sentence wins, and that it is not part of the answer. Nothing of it is
  ever stored with a gloss. Your own prompts keep the rule too. After turning this on, download
  the `parseh-gloss` skill again, as **Settings → Skills for your chatbot** reminds you.

A book being made in place by an agent can ask too: while the gloss prompts' choice is on, the book's
instructions tell the agent about a helper that reads a sentence and writes nothing.

## Try it

**Try it**, at the foot of the page, reads a sentence of yours: every word with what the analyzer
made of it, the phrases with and without it, and the dictionary with and without it where the language
has one. Nothing is kept. It is the way to see whether an analyzer helps your language before you turn it on.

## When it cannot help

If an analyzer is missing, fails, or cannot line its answer up exactly with your text, Parseh does
what it did before and says nothing in the page you are reading. **Try it** says why.

It works on this computer, for whichever device is asking. Nothing is ever sent elsewhere, and a
page you are reading offline never tries to run it.

The first request of a language loads its model, about a second; after that a sentence takes a few
thousandths of a second. The program goes away after ten idle minutes, with its memory.

## Is it any good?

It depends on the language and on the sentence, which is why it stays optional. The models are small and
make mistakes a reader would not: UDPipe read *wir* in a German sentence as a form of *werden*. Starlang
never chooses among the readings of a Turkish word, and Farahidi's choice of lemma for an unvowelled Arabic word
can be wrong while still being one of the word's real readings. On Linux it has been installed and run. **On
Windows and macOS it has not been tried yet**, Starlang's compile above all.
