---
title: A translation model in the page
linkTitle: A translation model
weight: 5
description: The whole sentence read by a small translation model that runs inside the reader, with your chunk's share of it marked — no prompt, no key, nothing sent anywhere.
---

The dictionary reads the words and the corpus finds a sentence like yours; a
**translation model** reads the sentence itself. Where one is installed for
the pair — the language you read, into the language of your glosses — the
panel under an unglossed chunk opens with the machine's reading of the
whole sentence already in it, and the words of it that seem to be *your
chunk's* marked inside it.

## What it is, and what it is not

- **A translation model, not a chat model.** One job, no prompt, no
  address, no key, no conversation, and the same answer every time for the
  same sentence. There is nothing to configure.
- **It runs inside the page.** The engine is
  [bergamot-translator](https://github.com/browsermt/bergamot-translator) —
  the one Firefox's own translation feature uses — compiled to WebAssembly
  and run in a worker of the reader itself. The sentence being translated
  never leaves the browser you are reading in, and Parseh gains no program
  to run it.
- **Small.** The models are Mozilla's, about 20 MB a pair against the
  gigabytes of a general model. That is what lets them run in a page, and
  it is also their limit: they read a plain sentence well and poetry badly.
  Take what comes back as what the line is *about*, not what it *says* —
  and if that is not enough for the line in front of you, the line wanted a
  gloss anyway.
- **Never a gloss.** It is labelled as a machine's reading, it has no
  button that writes it anywhere, and it is never put into a book or a
  video.

## Getting one

On the [reading-help page](reading-help.md), each language's card has a
**Translation model** row, for the pair its **glossed in** names, with
**Get it**:

- **Only pairs with English exist.** Mozilla trains its models against
  English rather than against each other, so a Persian book glossed in
  English has a model and the same book glossed in Italian has none: that
  row says *No model*, and why. **English**'s card offers the others,
  for an English book glossed in Italian, Persian, Japanese… An English book
  glossed in English has no model either way: a translation is between two
  languages. Not every language has both directions: once Parseh has read
  Mozilla's list (the first time a size is asked or a model is fetched), it
  offers only the pairs that list has.
- **What it costs.** *About 20 MB a pair, plus a 5 MB engine once* — the
  engine is fetched with the first model and shared by every pair after
  it. Measured: Persian to English about 22 MB, Italian or Spanish to
  English about 37, Japanese or Chinese to English about 55 (a writing
  system of thousands of characters makes the largest models). The
  Chinese model is Mozilla's simplified-characters one, which is what
  Parseh's `zh` is.
- **Installed.** The row says its size, with Mozilla Firefox Translations
  models and CC BY-SA 4.0 on its last line, and a **Remove…** button. There
  is no **Rebuild**: a model is a fixed version and would come back byte for
  byte the same. To get it again, remove it and press **Get it**.

The engine is pinned to one version (0.4.9, under the MPL 2.0), and more
than by its number: its three files must match fingerprints (SHA-256)
written into this version of Parseh, and each file of a model must match the
fingerprint Mozilla publishes beside it. A file that does not match is
refused and nothing is installed — so the code that runs inside the reader
is the code your version of Parseh names, and nothing fetched over the
network changes under you without somebody deciding it should.

## In the reader and the player

With the **dictionary** switch on — a model alone is enough for the switch
to appear — open a chunk nobody has written a vocabulary line for. Between
the dictionary's entries and the translated sentences sits a block headed
**a machine's reading of the sentence — not a gloss** (in the player, *of
the caption*):

- **The whole sentence, not the chunk.** A chunk is a fragment by design,
  and a fragment translated on its own comes back as one: مثل ایران با هم
  alone came back as *The parable of Iran with Hem*, three words each
  defensible and a sentence about nothing. So the model reads the sentence
  the chunk sits in — a book's subparagraph, a video's caption — and shows
  all of it.
- **Your chunk's share is marked inside it**, in as many places as its
  meaning landed: coloured and bold where the dictionary accounts for at
  least half of the chunk's words, in ordinary ink under a dotted underline
  where it accounts for fewer.
- **A line under it says what the mark stands on**: *this chunk is likely:
  “short hat” — کوتاه → short · کلاه → hat*, or *part of this chunk is
  likely: …*, or — where no word of the reading matches — *no word of this
  reading matches what the dictionary says of the chunk, so none is marked*.
  (The player says *phrase*.)
- **The model and the engine** are named at the foot.
- Where the chunk **is** the whole sentence, there is nothing to mark: the
  heading is simply **a machine's reading — not a gloss**.

The mark is a guess, and drawn as one. The engine gives no word alignment,
so the reader looks for the chunk's *meaning* in the reading — what the
dictionary says each of its words means, and the chunk translated on its
own — and never for its *place*, because word order is exactly what a
translation changes: امروز صبح opens its Persian sentence and *this morning*
ends the English one. The [synonym table](synonyms.md) helps it find a
word the model chose differently.

### No button, because it is already done

Nothing is pressed. While you read, the next **ten** sentences that still
hold an unglossed chunk are handed to the model in one go — ten Persian
sentences took 74 ms against about 30 ms for one — so the panel usually
opens with the reading in it. A panel that gets there first says *reading
the sentence…* for a moment; one the model could not serve says *the model
could not be run*. A stretch you have finished glossing asks for nothing,
and **with the dictionary switch off no sentence is translated and the
model itself is never loaded**. The one thing a reader fetches whatever the
switch says is the [synonym table](synonyms.md), once, as soon as it learns
that a model exists for its pair — so that it has arrived by the time you
first turn the switch on. The reader keeps the last 400 readings, dropping
the oldest.

### Definitions, translated

For an English book or video, whose dictionary gives definitions in English,
a model from English into your gloss language adds the **Translate the definitions into Italian** (or
**…into Persian**, …) switch under **Show the dictionary's definitions**: each definition put into
that language underneath it, as a machine's reading. See
[Dictionaries](dictionaries.md#english-explained-in-english).

### In the editor

The **⊕ sources** column of the chunk sheet has *a machine's reading* too,
with the same marks, and two buttons: **the marked words → meaning** and
**the whole sentence → meaning**. They fill the meaning box for you to
correct, and nothing is saved until you save. Where no model is installed
for the pair, that block says *no translation model for this pair*.

{{< details summary="For the command line" >}}
```bash
python3 lib/getmt.py                 # which pairs are installed
python3 lib/getmt.py fa en           # Persian to English, into mt/fa-en/
python3 lib/getmt.py --engine        # only the engine, without a model
python3 tests/mtcheck.py             # prove each installed pair runs in a real browser
```

`tests/mtcheck.py` needs Playwright and a Chromium; it opens the reading-help page,
checks the engine is served as WebAssembly, and translates one sentence per
installed pair.
{{< /details >}}
