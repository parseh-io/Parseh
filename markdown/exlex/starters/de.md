---
title: New German note
subtitle: [Herzlich willkommen]{tl}: a guided tour of everything a note can hold
note: A demo page: keep what you need and delete the rest
lang: en
target: de
---

> **This page is a demo.** It shows everything a studio note can contain, one feature per
> section, with German examples. Keep what you need, delete the rest, and write your own note
> in its place: the editor shows the source of every example beside its preview.
>
> German is written in the same alphabet as English, so nothing on the page can tell a German
> word from an English one. **Every German word is therefore marked**: it stands in square
> brackets followed by `{tl}` (for *target language*), like [Guten Tag]{tl}. The **tl** button
> in the toolbar writes the mark around the selected text.

## Writing prose

### Emphasis and code

Two asterisks on each side make **bold** text, one on each side makes *italic* text, and a
backquote on each side makes `inline code`, which suits a file name or a key such as `title:`.
Bold works on German too: **[Achtung!]{tl}** = *look out!*

An equals sign after a German word, followed by a translation in italics, is a gloss:
[Guten Morgen]{tl} = *good morning*. The page greys the equals sign, and every gloss goes into
the document's glossary.

### Lists

Three things to learn with every German noun; a line indented by two spaces sits one level down:

- its article: [der]{tl}, [die]{tl} or [das]{tl}
- its plural, often with a change inside: [das Haus]{tl} → [die Häuser]{tl}
  - and sometimes with no change at all: [das Zimmer]{tl} → [die Zimmer]{tl}
- the capital letter it always starts with: [der Tisch]{tl}, [die Liebe]{tl}, [das Essen]{tl}

A numbered list starts each line with a number and a full stop; the page numbers it for you.

1. In a statement the conjugated verb comes second: [Heute gehe ich ins Kino.]{tl}
2. In a yes-or-no question it comes first: [Gehst du heute ins Kino?]{tl}
3. After [weil]{tl}, *because*, it goes to the very end: […, weil ich müde bin.]{tl}

When every item of a list starts with a bold label, the labels are set apart as terms:

- **Nominative** the subject: [der Hund]{tl} = *the dog*
- **Accusative** the direct object: [den Hund]{tl}
- **Dative** the indirect object: [dem Hund]{tl}
- **Genitive** the owner: [des Hundes]{tl}

### Arrows, wrong forms and line breaks

An arrow shows a change or a derivation: [gehen]{tl} → [ging]{tl} → [gegangen]{tl}. The arrow
button in the toolbar types it, and a hyphen and a greater-than sign make the same arrow:
[sehen]{tl} -> [sah]{tl} -> [gesehen]{tl}.

A cross straight before a form paints it red as a mistake, and a green tick marks the right
form; both have a button in the toolbar. ✗[der Mädchen]{tl} ✅ [das Mädchen]{tl}

Lines of the source join into one paragraph. The return-sign button in the toolbar forces a
break inside a paragraph, as in this week:⏎
[Montag: Deutschkurs]{tl}⏎
[Dienstag: Schwimmen]{tl}⏎
[Mittwoch: frei]{tl}

## German on the page

### Whole paragraphs and blocks

A paragraph that is one single mark becomes a German block, set in the German face:

[Im Sommer fahren wir jedes Jahr an die Ostsee. Das Wasser ist kalt, aber die Luft ist herrlich.]{tl}

A block may run over several lines: an opening square bracket on a line of its own, the text,
and the closing bracket with its braces on the last line. Each return sign keeps a line break.
Inside the braces, `bg=` tints the block with one of five backgrounds: `quote`, `sand`, `rose`,
`sage` or `lilac`. Here is a poem by Goethe (1780), tinted as a quotation:

[
Über allen Gipfeln⏎
Ist Ruh,⏎
In allen Wipfeln⏎
Spürest du⏎
Kaum einen Hauch;⏎
Die Vögelein schweigen im Walde.⏎
Warte nur, balde⏎
Ruhest du auch.
]{tl bg=quote}

And a short dialogue on sand:

[
A: Entschuldigung, wo ist der Bahnhof?⏎
B: Gehen Sie geradeaus und dann links.⏎
A: Vielen Dank!⏎
B: Gern geschehen.
]{tl bg=sand}

[Übung macht den Meister.]{tl bg=sage}

That proverb, on sage, means *practice makes perfect*.

### What German does not need

Some features of the studio exist for other scripts and do nothing in a German note:

- **Automatic German** A paragraph in Persian, Arabic, Hindi, Japanese or Chinese is recognised
  by its script alone. German shares its letters with English, so it is always marked.
- **Display lines** A paragraph of nothing but those scripts' letters and spaces becomes a
  large display line. German has none.
- **Other faces** Persian and Japanese have a second typeface for their blocks (`font=`). German
  has one face only.
- **Vertical text** Japanese and Chinese blocks can be set in columns (`vertical`); German
  cannot.
- **Readings** Japanese words carry a kana reading beside the pronunciation; German has no
  reading field.

### Pronunciation

A pronunciation can ride on the mark, after `translit:` inside the braces. Rest the pointer on a
word to see it: [ich]{translit:iç}, [das Buch]{translit:das bu:x}, [die Stadt]{translit:di: schtat}
against [der Staat]{translit:de:r schta:t}. On paper only the German is printed.

The respelling uses German letters in lower case: a colon after a vowel makes it long, an
apostrophe goes before the stressed syllable, `x` is the sound of [Bach]{tl} and `ç` the sound of
[ich]{tl}. A colour and a pronunciation can share the braces:
[die Bäckerei]{teal translit:di: bäke'rai} = *the bakery*.

### Colours

Five named colours can be put on any word: `crimson`, `indigo`, `teal`, `violet` and `amber`.
Colour-coding the genders is an old trick:
[der Löffel]{indigo} for masculine, [die Gabel]{crimson} for feminine, [das Messer]{teal} for
neuter, [die Teller]{violet} for the plural, and amber for the verb that waits at the end:
[Ich habe die Teller]{tl} [gespült]{amber}.

Any other colour is a hash sign and six hexadecimal digits inside the braces:
[das Holz]{#8A4F2A} = *wood*. Hovering a German word offers a palette that writes these marks.

## Dictionary entries

A heading whose parts are separated by vertical bars is a dictionary entry: the headword, its
pronunciation, its origin, and after an equals sign its meaning. The meaning is not shown under
the heading: it puts the headword, with that meaning, into the glossary.

## das Mädchen | das 'mä:tçen | from older [Mägdchen]{tl}, a diminutive of [die Magd]{tl}, *maid* | = *girl*

- **Gender** neuter, like every noun made with the diminutive ending [-chen]{tl}
- **Plural** unchanged: [die Mädchen]{tl} = *girls*
- **Example** [Das Mädchen liest ein Buch.]{tl} = *The girl is reading a book.*

With only two parts before the meaning, the heading has a headword and its pronunciation:

## die Straße | di: 'schtra:se | = *street*

- **Plural** [die Straßen]{tl}
- **In Switzerland** [die Strasse]{tl}, since Swiss spelling has no [ß]{tl}
- **Example** [Wir wohnen in einer ruhigen Straße.]{tl} = *We live on a quiet street.*

The headword may carry a colour, and its pronunciation may ride on its mark, leaving the second
part empty:

## [das Buch]{teal translit:das bu:x} | | Old High German *buoh* | = *book*

- **Plural** with an umlaut: [die Bücher]{translit:di: 'bü:ça}
- **Compound** [das Wörterbuch]{translit:das 'vörtabu:x} = *dictionary*, a book of words
- **Example** [Ich lese ein Buch.]{translit:iç 'le:ze ain bu:x} = *I am reading a book.*

## Tables

A table is a header row, a row of hyphens, and the body. Colons in the hyphen row align a
column to the left, the centre or the right, and a cell holding two hyphens stays empty.

| singular | plural | English |
|:---|:---:|---:|
| [der Tag]{tl} | [die Tage]{tl} | day |
| [das Buch]{tl} | [die Bücher]{tl} | book |
| [die Nacht]{tl} | [die Nächte]{tl} | night |
| -- | [die Eltern]{tl} | parents |
| [die Milch]{tl} | -- | milk |

## Footnotes

German writes every noun with a capital letter.[^1] A footnote is a caret and a name in square
brackets, and its text goes on a line of its own anywhere in the document, starting with the
same bracket and a colon.

German also has a letter all of its own, [ß]{tl}.^[Its name is [das Eszett]{tl}. Swiss
spelling does without it and writes [Strasse]{tl} for [Straße]{tl}.] A caret followed by the
text of the note in square brackets writes the note in place.

[^1]: Every word used as a noun takes one too: [das Essen]{tl}, [etwas Neues]{tl},
  [beim Schwimmen]{tl}. The polite [Sie]{tl} has a capital as well; the familiar [du]{tl} has none.

## Links

A link is its text in square brackets and the address in round brackets:
[a short film on YouTube](https://www.youtube.com/watch?v=aqz-KE-bpKQ).

A link can also point to another note by its title: [another note](doc:My second German note).
With the square brackets left empty it shows that title itself: [](doc:My second German note).
A link to a title that no note has yet is drawn as a dangling link; create a note with that
title and the link starts working. The **Doc link…** button lists the notes you already have.

## Blocks of English

A paragraph wrapped in square brackets and followed by `{la}` is a block of English set apart.
It exists for English inside a right-to-left or vertical document, where it keeps its own
direction. Anywhere, its lines can be centred, and the block tinted, narrowed and shifted like a
picture.

[**Tip.** Learn every noun with its article and its plural: not just [Tisch]{tl}, but [der Tisch, die Tische]{tl}.]{la align=center bg=sand width=80}

[This block is 80% of the column wide and pushed 10% to the right, the way a picture is placed.]{la width=80 offset=10}

## Mathematics

Formulas are written in LaTeX notation: [4 \times (3 + 1) = 16]{math} is the number of slots
in the table of the definite article, four cases times three genders and the plural.

Only six forms fill those sixteen slots: [der]{tl}, [die]{tl}, [das]{tl}, [den]{tl}, [dem]{tl}
and [des]{tl}. A formula on lines of its own goes between an opening line `:::math` and a
closing line `:::`, like this one.

:::math
\frac{\text{distinct forms}}{\text{slots}} = \frac{6}{4 \times (3 + 1)} = \frac{6}{16} = 37.5\,\%
:::

## Pictures, recordings and video

A picture is a line of its own: an exclamation mark, the caption in square brackets, the file
in round brackets, and the layout in braces (width and shift in percent of the column, and the
side it sits on). A caption cannot hold a square-bracket mark, so German there is in italics.

![An apple: *der Apfel*](images/starter-apple.svg){width=40 align=center}

![A house: *das Haus*](images/starter-house.svg){width=35 align=left offset=10}

A recording is written the same way, with its file under `audio/`.

![A short chime](audio/starter-chime.mp3){width=60 align=center}

`start=` and `end=` in the braces, in seconds or in minutes and seconds, play only a stretch of
it, here the chime's first note:

![The chime, its first note only](audio/starter-chime.mp3){width=50 align=center start=0 end=0.4}

A video starts with an at sign instead, and plays only the stretch between `start` and `end`:

@[A short film](https://www.youtube.com/watch?v=aqz-KE-bpKQ){width=70 align=center start=0:10 end=0:40}

The **Image**, **Audio** and **Video** buttons write these lines for you.

## Exercises

> **How the exercises work**
>
> - **Add exercise…**, in the toolbar's **Exercises** menu, opens a form for every type below.
> - In the reading view nothing is scored until **Check exercises**, at the end of the page.
> - **+ Deck** copies an exercise into one of your exercise decks, to study it again later.

### Fill in the blanks

:::exercise fill-blanks
prompt: Complete the sentence.
content-direction: target
text: [Gestern [[aux]] ich mit dem Zug nach Hamburg [[verb]].]{tl}
- [aux] [bin]{tl}
- [verb] [gefahren]{tl}
- [ ] [habe]{tl}
- [ ] [gefahrt]{tl}
explanation-correct: Right: [fahren]{tl}, *to travel*, makes its perfect with [sein]{tl}, and its participle is [gefahren]{tl}.
explanation-incorrect: A verb of going from place to place makes its perfect with [sein]{tl}: [ich bin gefahren]{tl}.
:::

### Put the sentences in order

:::exercise order-sentences
prompt: Put the morning in order.
- [1] [Um sieben Uhr klingelt der Wecker.]{tl}
- [2] [Ich stehe sofort auf.]{tl}
- [3] [Dann dusche ich und ziehe mich an.]{tl}
- [4] [Zum Frühstück trinke ich einen Kaffee.]{tl}
- [5] [Um acht Uhr gehe ich aus dem Haus.]{tl}
:::

### Build the sentence

:::exercise construct-sentence
prompt: Build the sentence: *I can't come today because I have to work.*
- [1] [Ich kann]{tl}
- [2] [heute nicht kommen,]{tl}
- [3] [weil ich]{tl}
- [4] [arbeiten]{tl}
- [5] [muss.]{tl}
explanation-correct: After [weil]{tl} the conjugated verb, here [muss]{tl}, goes to the very end.
:::

### Match the translations

:::exercise match-translations
prompt: Match each picture or word with its German name.
direction: translation-to-target
- [der Apfel]{tl} => ![an apple](images/starter-apple.svg)
- [das Haus]{tl} => ![a house](images/starter-house.svg)
- [die Küche]{tl} => the kitchen
- [der Schlüssel]{tl} => the key
- [das Fenster]{tl} => the window
:::

### Match the opposites

:::exercise match-opposites
prompt: Match each word with its opposite.
- [groß]{tl} => [klein]{tl}
- [hell]{tl} => [dunkel]{tl}
- [schnell]{tl} => [langsam]{tl}
- [teuer]{tl} => [billig]{tl}
- [laut]{tl} => [leise]{tl}
:::

### Match the definitions

:::exercise match-definitions
prompt: Match each word with what it means.
- [der Bahnhof]{tl} => where trains arrive and leave
- [die Bäckerei]{tl} => where bread is baked and sold
- [das Wörterbuch]{tl} => a book that explains words
- [die Bücher]{tl} => the plural of [das Buch]{tl}, with an umlaut: u \=> ü
:::

### Yes or no

:::exercise yes-no
prompt: Listen to the recording, then answer each question.⏎[A German yes-or-no question starts with its verb.]{no-bold}
audio: audio/starter-chime.mp3 {width=50 align=center}
- [Hört man eine Stimme?]{tl} => no
- [Hört man zwei Töne?]{tl} => yes
- [Ist die Aufnahme lang?]{tl} => no
:::

### True or false

:::exercise true-false
prompt: Decide whether each statement is true or false.
- [Der Tisch]{tl}, [die Lampe]{tl} and [das Fenster]{tl} have three different genders. => true
- [Straße]{tl} and [Strasse]{tl} are two different words. => false
- A word used as a noun is written with a capital like any other noun, so the verb [essen]{tl}, *to eat*, becomes [das Essen]{tl} when it means *the meal*, with a capital letter and the neuter article. => true
- The plural of [das Buch]{tl} is [die Buchs]{tl}. => false
explanation-correct: [Strasse]{tl} is the Swiss spelling of [Straße]{tl}, and the plural of [das Buch]{tl} is [die Bücher]{tl}.
:::

### Single choice

:::exercise single-choice
prompt: What is this in German?
image: images/starter-apple.svg {width=30 align=center}
- [ ] [die Birne]{tl}
- [x] [der Apfel]{tl}
- [ ] [die Kirsche]{tl}
explanation-correct: Yes: [der Apfel]{tl}, plural [die Äpfel]{tl}.
explanation-incorrect: Not quite: [die Birne]{tl} is a pear and [die Kirsche]{tl} a cherry; this is [der Apfel]{tl}.
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *house*?
image-answer: images/starter-house.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] [das Haus]{tl}
- [ ] [die Maus]{tl}
- [ ] [der Baum]{tl}
explanation-correct: [das Haus]{tl}, plural [die Häuser]{tl}; [die Maus]{tl} is a mouse and [der Baum]{tl} a tree. The chime stands in for the word said aloud.
:::

### Find the incorrect part

:::exercise incorrect-part
prompt: One part of this sentence is wrong. Which one?
- [ ] [Gestern]{tl}
- [x] [habe ich]{tl}
- [ ] [mit meiner Schwester]{tl}
- [ ] [ins Kino]{tl}
- [ ] [gegangen.]{tl}
explanation-correct: [gehen]{tl} makes its perfect with [sein]{tl}: [Gestern bin ich mit meiner Schwester ins Kino gegangen.]{tl}
:::

### Choose all that apply

:::exercise choose-all
prompt: Which sentences put the verb in the right place?⏎[The conjugated verb is the second element, as in [Morgen fahre ich nach Wien.]{tl}]{no-bold}
- [x] [Heute gehe ich ins Kino.]{tl}
- [ ] [Heute ich gehe ins Kino.]{tl}
- [x] [Ich gehe heute ins Kino.]{tl}
- [ ] [Ich heute gehe ins Kino.]{tl}
- [x] [Ins Kino gehe ich heute.]{tl}
:::

### The odd one out

:::exercise odd-one-out
prompt: Which word does not belong with the others?
- [ ] [der Montag]{tl}
- [ ] [der Freitag]{tl}
- [x] [der Januar]{tl}
- [ ] [der Sonntag]{tl}
explanation-correct: [der Januar]{tl} is a month; the others are days of the week.
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: At the bakery a customer says: [Guten Tag! Ich hätte gern einen Kaffee und ein Brötchen, bitte.]{tl} Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then something to eat.
::::exercise single-choice
prompt: What does the customer want to drink?
- [x] [einen Kaffee]{tl}
- [ ] [ein Brötchen]{tl}
- [ ] [eine Rechnung]{tl}
explanation-correct: [Der Kaffee]{tl}, *the coffee*; the roll is [das Brötchen]{tl}.
::::
::::exercise true-false
prompt: Now decide.
- [Brötchen]{tl} is a neuter noun: [das Brötchen]{tl}, [ein Brötchen]{tl}. => true
- [Bitte]{tl} means *thank you*. => false
explanation-correct: [Bitte]{tl} is *please* (and *you're welcome*); *thank you* is [danke]{tl}.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the words you have just read.
content-direction: target
text: [Guten Tag! Ich hätte gern [[drink]] und [[food]], bitte.]{tl}
- [drink] [einen Kaffee]{tl}
- [food] [ein Brötchen]{tl}
- [ ] [ein Kaffee]{tl}
explanation-correct: [Der Kaffee]{tl} is masculine, and an object in the accusative takes [einen]{tl}.
::::
:::

### Flashcards

A vocabulary card; `direction: reverse` shows the English side first, and `front-audio:` gives the
German side a speaker button (the chime, where the word said aloud would go), which plays without
turning the card.

:::exercise flashcard
card-type: vocab
target: [das Eichhörnchen]{tl}
transliteration: das 'aiçhörnçen
meaning: squirrel
context: [Im Herbst sammelt es Nüsse für den Winter.]{tl}
notes: Neuter, as its diminutive ending [-chen]{tl} says.
front-audio: audio/starter-chime.mp3
direction: reverse
:::

A card of opposites:

:::exercise flashcard
card-type: opposites
target: [früh]{tl}
transliteration: frü:
opposite: [spät]{tl}
opposite-transliteration: schpä:t
notes: [Ich stehe früh auf, aber ich komme spät nach Hause.]{tl}
:::

A free card, whose four fields hold anything a page holds: pictures, recordings, several lines.
The `-size` and `-shade` settings change how large and how dark a field is drawn.

:::exercise flashcard
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=40 align=center}
front-secondary: What is it called, with its article?
back-primary: |
  **[der Apfel]{tl}**, plural **[die Äpfel]{tl}**

  ![A short chime](audio/starter-chime.mp3)
back-secondary: |
  [
  Ein Apfel am Tag⏎
  hält den Doktor fern.
  ]{tl}

  *An apple a day keeps the doctor away.*
front-secondary-size: 90
front-secondary-shade: subdued
back-primary-size: 140
back-primary-shade: accent
:::
