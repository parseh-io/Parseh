---
title: New Italian note
subtitle: a guided tour of everything a note can hold
note: the prose is English, every Italian word is marked
lang: en
target: it
---

> **This page is a demo.** It shows, by using them, all the things a note can contain: text,
> Italian words and sentences, pronunciations, colours, vocabulary entries, tables, footnotes,
> links, pictures, a recording, a video, formulas and every kind of exercise. The source is in
> the editor beside the preview. Keep what you need and delete the rest.

Italian is written in the same alphabet as the English around it, so nothing can tell the two
apart by itself. **Every Italian word on this page is marked**: a word in square brackets followed
by `{tl}` (for *target language*) is Italian, as in [buongiorno]{tl} = *good morning*. The
language's own code works too: [buonasera]{it} = *good evening*. Nothing Italian is ever
detected automatically; an unmarked word is simply English.

## Writing prose

Ordinary text takes the usual Markdown: **bold**, *italic* and `inline code`. A new line in the
source just carries on the same paragraph; a return sign forces a line break inside it,⏎so this
sentence starts on a line of its own. A blank line starts a new paragraph.

### Lists

A bullet list is made of lines starting with a dash, and a line indented by two spaces sits one
level down:

- [il pane]{tl} = *bread*
- [il latte]{tl} = *milk*
- [lo zucchero]{tl} = *sugar*
  - [lo]{tl}, not [il]{tl}, because the word starts with a *z*

A numbered list starts with a number and a full stop, and the numbering is done for you. Here
is how to have a coffee in an Italian bar:

1. Pay at the till first and keep the receipt, [lo scontrino]{tl}.
2. Hand it to the barista and order: [un caffè, per favore]{tl}.
3. Drink it standing at the counter, [al banco]{tl}: it costs less than at a table.

When every item starts with a bold label, the list is laid out as a list of terms:

- **[un caffè]{tl}** a short, strong espresso: the coffee you get unless you say otherwise
- **[un cappuccino]{tl}** espresso with foamed milk, a breakfast drink
- **[un caffè macchiato]{tl}** an espresso “stained” with a spoonful of milk foam
- **[un caffè corretto]{tl}** an espresso “corrected” with a dash of grappa

### Right and wrong

A cross written right against a word marks it as a wrong form, a tick marks the right one, and
an arrow leads from one to the other:

- ✗[un'amico]{tl} → ✅ [un amico]{tl}: the apostrophe is for the feminine, [un'amica]{tl}
- ✗[la problema]{tl} → ✅ [il problema]{tl}: most nouns in [-ma]{tl} that come from Greek are
  masculine
- ✗[ho andato]{tl} → ✅ [sono andato]{tl}: [andare]{tl} makes its past with [essere]{tl}

The arrow can also be typed as a hyphen and a greater-than sign, and it comes out the same:
[di]{tl} + [il]{tl} -> [del]{tl}.

## Italian in the text

### Words, phrases and glosses

A gloss is the Italian, an equals sign and the translation in italics: [il binario]{tl} =
*platform, track*. The sign turns grey and the pair goes into the note's glossary. A mark can
hold a whole phrase, [Dov'è la stazione?]{tl} = *Where is the station?*, and double asterisks
around it make the Italian bold: **[Attenzione!]{tl}** = *Watch out!*

> **Three things to remember about marks**
>
> - A mark cannot hold another mark: two words that need different marks get a pair of brackets
>   each.
> - Any mark on a word makes it Italian: a colour or a pronunciation counts as well as `{tl}`.
> - A mark is plain text inside: no bold, no italics, no gloss within the brackets.

### A whole paragraph in Italian

A paragraph that is nothing but one mark is a paragraph of Italian, set as a block of its own:

[Il treno regionale per Firenze delle ore nove e quindici è in partenza dal binario tre.]{tl}

### Poems and dialogues

A longer passage can open with a bracket on a line of its own and close with the mark on a line
of its own; a return sign ends each line, and `bg=` gives the block a tint. The opening of
Dante's *Inferno*, on the *quote* tint:

[
Nel mezzo del cammin di nostra vita⏎
mi ritrovai per una selva oscura,⏎
ché la diritta via era smarrita.
]{tl bg=quote}

A dialogue in the street, on the *sand* tint:

[
— Scusi, per la stazione?⏎
— Sempre dritto, poi la seconda a destra.⏎
— Grazie mille!⏎
— Si figuri.
]{tl bg=sand}

And a proverb on the *rose* tint; *sage* and *lilac* are the other two:

[Chi va piano va sano e va lontano.]{tl bg=rose}

### What Italian does not need

Some of the dialect's forms exist for other scripts and do nothing in an Italian note: a line of
Persian or Hindi is recognised by its letters alone and set as a display line, Persian and
Japanese blocks can take a second typeface with `font=`, Japanese and Chinese blocks can be set
in vertical columns, and Japanese words carry a kana reading. Italian needs none of these: an
Italian block takes only a tint, and an Italian word only a colour and a pronunciation.

## Pronunciation and colour

### Pronunciation

A pronunciation goes inside the mark after `translit:`. The page shows the plain spelling; the
pronunciation appears when you point at the word, and in the glossary. It adds only what the
spelling does not say: the stress when it is not on the next-to-last syllable, whether an e or an
o is open (è, ò) or closed (é, ó), and the few letters that are not read the way they look.

- [la pesca]{translit:la pèsca} = *peach*, but [la pesca]{translit:la pésca} = *fishing*
- [l'ancora]{translit:l'àncora} = *anchor*, but [ancora]{translit:ancóra} = *still, again*
- [il pesce]{translit:il péʃe} = *fish*, with *sc* before *e* read as in English *shoe*

A colour and a pronunciation can share the braces: [lo zero]{teal translit:lo żèro} = *zero*,
whose *z* is voiced, and [gli gnocchi]{violet translit:ʎi ɲòkki} = *gnocchi*.

### Colours

Five named colours, one per word here, and any other colour written as a hex code:
[rosso]{crimson} = *red*, [blu]{indigo} = *blue*, [verde]{teal} = *green*, [viola]{violet} =
*purple*, [arancione]{amber} = *orange*, and [marrone]{#8B4513} = *brown*.

## Vocabulary entries

A heading with fields split by bars is a vocabulary entry: the word, its pronunciation, its
origin, and after an equals sign its meaning, which is printed nowhere but goes into the
glossary. For Italian a heading becomes an entry as soon as it has two fields, so an ordinary
title never contains a bar.

## pesca | pèsca | Latin *persica*, from *persicum malum*, “Persian apple” | = *peach*

- **Gender** feminine: [la pesca]{tl}, plural [le pesche]{tl}
- **Example** [Queste pesche sono mature.]{tl} = *These peaches are ripe.*
- **Careful** with a closed e, [la pesca]{translit:la pésca} means *fishing*:
  [andare a pesca]{tl} = *to go fishing*

An entry can leave out the origin, as this one does:

## telefono | telèfono | = *telephone*

- **Gender** masculine: [il telefono]{tl}, plural [i telefoni]{tl}
- **The verb** [telefonare]{tl} = *to phone*: *I phone* is spelt and stressed just like the noun,
  [Telefono a mia madre.]{translit:Telèfono a mia madre.} = *I am phoning my mother.*

The entry below has no pronunciation field of its own (two bars side by side): its coloured
headword carries it in the mark.

## [ancora]{teal translit:àncora} | | Latin *ancora*, from Greek *ánkyra* | = *anchor*

- **Gender** feminine: [l'ancora]{tl}, plural [le ancore]{tl}
- **Not to be confused with** the adverb [ancora]{translit:ancóra} = *still, again*:
  [Sei ancora qui?]{tl} = *Are you still here?*

## Tables

Bars split a row into cells, and the line under the header sets each column's alignment with
colons: left, centred, centred and right here. A cell holding only two dashes is an empty cell,
drawn as a long dash.

| Before… | Masculine | Feminine | Examples |
|:---|:---:|:---:|---:|
| a consonant | [il]{tl} · [i]{tl} | [la]{tl} · [le]{tl} | [il libro]{tl}, [le case]{tl} |
| a vowel | [l']{tl} · [gli]{tl} | [l']{tl} · [le]{tl} | [l'amico]{tl}, [gli amici]{tl} |
| s + consonant, z, gn, ps | [lo]{tl} · [gli]{tl} | -- | [lo zaino]{tl}, [gli studenti]{tl} |

The empty cell says that the feminine has no special form there: [la stella]{tl}, [la zia]{tl}.

## Footnotes

Before a vowel, [lo]{tl} and [la]{tl} lose their vowel and take an apostrophe.[^1] The small
number is a footnote: a mark in the text, and the note itself written anywhere in the source,
its following lines indented by two spaces.

A short note can also be written where it belongs, inside the sentence: friends greet each
other with [ciao]{tl}^[It comes from the Venetian *s-ciào*, “(your) slave”, that is *at your
service*: [schiavo]{tl} in Italian.] and say it again when they leave.

[^1]: Today only the singular article is shortened: [l'amica]{tl}, but [le amiche]{tl}.
  Older books also write [gl'Italiani]{tl}, where today [gli]{tl} is written whole.

## Links

A web link puts the words in square brackets and the address in round ones:
[a short film on YouTube](https://www.youtube.com/watch?v=aqz-KE-bpKQ).

A link to another note points at that note's name, its title:
[another note](doc:My second Italian note), or, with nothing in the brackets, the title itself:
[](doc:My second Italian note). No note has that title yet, so both are shown as dangling
links; create a note titled *My second Italian note* and they start working.

## Blocks of English

A block in square brackets followed by `{la}` is a block of the prose language, English here,
set apart with its own alignment, tint, width and offset. It is made for right-to-left and
vertical notes, where a line of English needs a box of its own; in an Italian note it sets a
translation or a remark apart. Longfellow's translation of Dante's lines above, each line
centred, on the *sand* tint and 80% wide:

[Midway upon the journey of our life⏎
I found myself within a forest dark,⏎
For the straightforward pathway had been lost.]{la align=center bg=sand width=80}

The dialogue, 80% wide and moved 10% to the right, on the *lilac* tint:

[Excuse me, which way to the station?⏎
Straight on, then the second on the right.⏎
Thanks a lot!⏎
Don't mention it.]{la width=80 offset=10 bg=lilac}

## Mathematics

A formula in the line is written in LaTeX inside square brackets followed by `{math}`. Italian
has twenty-one letters of its own and five of them are vowels, so vowels are
[\tfrac{5}{21} \approx 24\%]{math} of the alphabet, yet close to half of the letters of an
ordinary Italian text.

A formula on its own is written between a `:::math` line and a `:::` line. The sentence to build
in the exercises below comes in five blocks, and a blind guess puts them in the right order once
in a hundred and twenty:

:::math
P(\text{right by chance}) = \frac{1}{n!} = \frac{1}{5!} = \frac{1}{120}
:::

## Pictures, a recording and a video

A picture sits on a line of its own: its caption goes in the square brackets, and the braces
after it give its width, as a share of the column, and its place. A caption holds no marks, so
the Italian goes in the sentence around it: [una mela]{tl} = *an apple*, centred and 40% wide,
and [una casa]{tl} = *a house*, on the left and moved in by 10%.

![An apple](images/starter-apple.svg){width=40 align=center}

![A house](images/starter-house.svg){width=30 align=left offset=10}

A recording is written the same way, with its file under `audio/`:

![A short chime](audio/starter-chime.mp3){width=50 align=center}

`start=` and `end=` in the braces, in seconds or in minutes and seconds, play only a stretch of
it, here the chime's first note:

![The chime, its first note only](audio/starter-chime.mp3){width=50 align=center start=0 end=0.4}

A YouTube video starts with `@` instead of `!`; this one plays from 0:10 to 0:40:

@[A short film](https://www.youtube.com/watch?v=aqz-KE-bpKQ){width=70 align=center start=0:10 end=0:40}

## Exercises

Each exercise is one block in the source, from a `:::exercise` line naming its type to a line
holding only `:::`. In the reading view they are live: answer them, then press **Check
exercises** at the end of the page. The editor's preview shows them solved, and the PDF prints
them unsolved. The recording on the greeting exercise is the demo chime; in your own notes it
would be the sentence to listen to.

### Placing words and sentences

:::exercise fill-blanks
prompt: Complete the sentence with the right forms of [essere]{tl} and [avere]{tl}.
content-direction: target
text: [Mi chiamo Anna, [[essere]] di Napoli e [[avere]] trent'anni.]{tl}
- [essere] [sono]{tl}
- [avere] [ho]{tl}
- [ ] [è]{tl}
- [ ] [hai]{tl}
explanation-correct: [Sono]{tl} and [ho]{tl}: Italian gives an age with [avere]{tl}, *to have*.
explanation-incorrect: Anna speaks of herself, [io sono]{tl} and [io ho]{tl}; an age is given with [avere]{tl}: [ho trent'anni]{tl}.
:::

:::exercise order-sentences
prompt: Put the lines of this conversation at the bar in order.
- [1] [Buongiorno! Un cappuccino, per favore.]{tl}
- [2] [Subito. Qualcos'altro?]{tl}
- [3] [Sì, anche un cornetto. Quant'è?]{tl}
- [4] [Due euro e cinquanta.]{tl}
:::

:::exercise construct-sentence
prompt: Build the sentence: *Last night we went to the cinema together.*
- [1] [Ieri sera]{tl}
- [2] [siamo]{tl}
- [3] [andati]{tl}
- [4] [al cinema]{tl}
- [5] [insieme.]{tl}
explanation-correct: [Andare]{tl} makes its past with [essere]{tl}, so the participle agrees with the subject: [siamo andati]{tl}, or [siamo andate]{tl} for a group of women.
:::

### Matching

:::exercise match-translations
prompt: Match each meaning with its Italian word.
direction: translation-to-target
- [il pane]{tl} => bread
- [l'acqua]{tl} => water
- [il formaggio]{tl} => cheese
- [la mela]{tl} => ![an apple](images/starter-apple.svg)
:::

:::exercise match-opposites
prompt: Match each word with its opposite.
- [grande]{tl} => [piccolo]{tl}
- [caldo]{tl} => [freddo]{tl}
- [aperto]{tl} => [chiuso]{tl}
- [presto]{tl} => [tardi]{tl}
:::

:::exercise match-definitions
prompt: Match each place with what you do there.
direction: word-to-definition
- [la biblioteca]{tl} => [dove si prendono in prestito i libri]{tl}
- [la libreria]{tl} => [dove si comprano i libri]{tl}
- [la farmacia]{tl} => [dove si comprano le medicine]{tl}
- [la stazione]{tl} => [dove si prende il treno]{tl}
explanation-correct: Watch [la libreria]{tl}: it is a bookshop, not a library.
:::

### Choosing

In a row, `=>` parts a statement from its answer, as it parts the two sides of a pair above. A
backslash before it, `\=>`, keeps it in the text as a plain arrow, as in the first exercise here.

:::exercise yes-no
prompt: Is the plural right?
- [la casa]{tl} \=> [le case]{tl} => yes
- [il libro]{tl} \=> [i libri]{tl} => yes
- [la mano]{tl} \=> [le mane]{tl} => no
- [il problema]{tl} \=> [i problemi]{tl} => yes
- [l'uovo]{tl} \=> [le uove]{tl} => no
explanation-incorrect: Two plurals are irregular: [la mano]{tl} → [le mani]{tl}, and [l'uovo]{tl} → [le uova]{tl}, which turns feminine.
:::

:::exercise true-false
prompt: Read the message, then decide whether each statement is true or false.⏎[[Ciao Luca! Stasera non posso venire a cena, devo lavorare fino a tardi. Ci vediamo sabato? Un abbraccio, Sara]{tl}]{no-bold}
- Sara cannot come to dinner tonight. => true
- She has to work late. => true
- She suggests meeting on Sunday. => false
- Opening with [Ciao]{tl} and closing with [Un abbraccio]{tl}, *a hug*, is how you write to a friend; to an office you would open with [Buongiorno]{tl} and close with [Cordiali saluti]{tl}. => true
:::

:::exercise single-choice
prompt: What is in the picture?
image: images/starter-apple.svg {width=30 align=center}
- [ ] [una pera]{tl}
- [x] [una mela]{tl}
- [ ] [un'arancia]{tl}
- [ ] [una pesca]{tl}
explanation-correct: [Una mela]{tl}, plural [le mele]{tl}.
explanation-incorrect: It is [una mela]{tl}. [Una pera]{tl} is a pear, [un'arancia]{tl} an orange, [una pesca]{tl} a peach.
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *house*?
image-answer: images/starter-house.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] [la casa]{tl}
- [ ] [la chiesa]{tl}
- [ ] [la scuola]{tl}
explanation-correct: [La casa]{tl} is a house; [la chiesa]{tl} is a church and [la scuola]{tl} a school. The chime stands in for the word said aloud.
:::

:::exercise incorrect-part
prompt: One part of this sentence is wrong. Which one?
- [ ] [Ieri]{tl}
- [ ] [ho comprato]{tl}
- [x] [il]{tl}
- [ ] [zaino]{tl}
- [ ] [nuovo.]{tl}
explanation-correct: Before a *z* the article is [lo]{tl}: [Ieri ho comprato lo zaino nuovo.]{tl}
explanation-incorrect: Look at the article: before a *z* it is [lo]{tl}, [Ieri ho comprato lo zaino nuovo.]{tl}
:::

:::exercise choose-all
prompt: Which of these can you say to greet someone you do not know?
audio: audio/starter-chime.mp3 {width=50 align=center}
- [x] [Buongiorno!]{tl}
- [x] [Buonasera!]{tl}
- [ ] [Ciao!]{tl}
- [x] [Salve!]{tl}
- [ ] [Arrivederci!]{tl}
explanation-correct: [Ciao]{tl} is for friends and family, and [arrivederci]{tl} is for leaving, not arriving.
:::

:::exercise odd-one-out
prompt: Which word does not belong with the others?
- [ ] [lunedì]{tl}
- [ ] [mercoledì]{tl}
- [x] [gennaio]{tl}
- [ ] [venerdì]{tl}
explanation-correct: [Gennaio]{tl}, *January*, is a month; the others are days of the week. Italian writes both with a small letter.
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: At the bar a customer says: [Buongiorno! Un cappuccino e un cornetto, per favore.]{tl} Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then a pastry.
::::exercise single-choice
prompt: What does the customer ask for first?
- [x] [un cappuccino]{tl}
- [ ] [un cornetto]{tl}
- [ ] [il conto]{tl}
explanation-correct: [Un cappuccino]{tl}, a coffee with milk; the pastry comes second.
::::
::::exercise true-false
prompt: Now that you know what was ordered, decide.
- [Un cornetto]{tl} is something to eat. => true
- [Per favore]{tl} means *thank you*. => false
explanation-correct: [Per favore]{tl} is *please*; *thank you* is [grazie]{tl}.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the words you have just read.
content-direction: target
text: [Buongiorno! Un [[drink]] e un [[food]], per favore.]{tl}
- [drink] [cappuccino]{tl}
- [food] [cornetto]{tl}
- [ ] [conto]{tl}
explanation-correct: A drink and something to eat, then [per favore]{tl}.
::::
:::

### Flashcards

A flashcard turns over when you click it. A vocabulary card, whose speaker button plays the
recording its `back-audio:` names (the chime, where the word said aloud would go) without turning
the card:

:::exercise flashcard
card-type: vocab
target: [la pesca]{tl}
transliteration: la pèsca
meaning: peach
context: [Queste pesche sono mature.]{tl}
notes: Read with a closed e, [la pesca]{translit:la pésca} is *fishing*.
back-audio: audio/starter-chime.mp3
:::

A card of opposites:

:::exercise flashcard
card-type: opposites
target: [vecchio]{tl}
transliteration: vècchio
opposite: [nuovo]{tl}
opposite-transliteration: nuòvo
notes: Said of a person, the opposite is [giovane]{tl}, *young*.
:::

A free card, whose four fields hold almost anything a page holds: a picture, a recording,
several lines. The size and shade of each field can be set:

:::exercise flashcard
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=35 align=center}
front-secondary: What is it called, and how do you ask for three?
back-primary: |
  **[la mela]{tl}**, plural **[le mele]{tl}**
back-secondary: |
  ![A short chime](audio/starter-chime.mp3)

  [Vorrei tre mele, per favore.]{tl}⏎*I would like three apples, please.*
front-secondary-shade: subdued
back-primary-size: 140
back-primary-shade: accent
:::
