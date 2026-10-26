---
title: New Spanish note
subtitle: A guided tour of everything a note can hold, in Spanish
note: A demo page: keep what you need, delete the rest
lang: en
target: es
---

> **This is a demo note.** It shows, on real Spanish, everything a studio note can contain: text,
> marks, tables, notes, links, pictures, recordings, a video and every kind of exercise. Keep what
> you need and delete the rest; the editor beside the preview shows how each thing is written.
>
> Spanish is written in the same alphabet as the English around it, so the studio cannot tell
> the two apart on its own: **every Spanish word on this page is marked**. A word or a sentence
> in square brackets followed by `{tl}` (for *target language*) is Spanish, as in
> [¡Bienvenidos!]{tl}; a colour or a pronunciation mark counts as the mark too.

## Ordinary prose

A paragraph is plain text, and a blank line starts a new one. **Two asterisks** make bold, *one*
makes italics, and **bold can hold *italics* inside it**. Backticks set `a few characters` apart
as code. A line break inside a paragraph is written with the return sign, ⏎ and the text goes on
from the next line, as it does here.

A list starts each line with a dash, and a line indented by two spaces sits one level down:

- [hola]{tl} = *hello*
- [buenos días]{tl} = *good morning*
- [buenas tardes]{tl} = *good afternoon*
- [buenas noches]{tl} = *good evening, good night*
  - said on arriving as well as on leaving: [¡Buenas noches, señora!]{tl}

A numbered list starts each line with a number and a full stop; the numbers are counted for you.
Ordering a coffee:

1. greet: [Buenos días.]{tl} = *Good morning.*
2. ask: [Un café con leche, por favor.]{tl} = *A white coffee, please.*
3. thank: [Muchas gracias.]{tl} = *Thank you very much.*

When every item starts with a **bold label**, the list becomes a list of definitions. Spanish has
two verbs for *to be*:

- **[ser]{tl}** what a thing *is*: identity, origin, material, what it is like always.
  [Soy de Chile.]{tl} = *I am from Chile.*
- **[estar]{tl}** where and how it is *right now*: place, state, the result of a change.
  [Estoy cansado.]{tl} = *I am tired.*

The arrow shows a change of form: [la casa]{tl} → [las casas]{tl},
[el lápiz]{tl} → [los lápices]{tl}, and a hyphen and a greater-than sign make the same arrow:
[el pez]{tl} -> [los peces]{tl}. A cross before a form marks it wrong and a tick marks the right
one: a question opens with an inverted mark, so ✗[Cómo estás?]{tl} is wrong and
✅ [¿Cómo estás?]{tl} is right.

## Spanish in the text

### Words and phrases

A Spanish run is marked with `{tl}`: [la ciudad]{tl}, [el mercado]{tl}. The language's own code
works as well as `{tl}`, so [adiós]{es} is marked too. A run inside two asterisks is set in bold,
as **[¡Qué bonito!]{tl}** is here. An equals sign and an italic translation after a run make a
gloss, [la ciudad]{tl} = *the city*, and every gloss written this way goes into the note's
glossary.

### Whole paragraphs and poems

A paragraph that is nothing but one marked stretch becomes a Spanish block of its own:

[Me llamo Carmen, vivo en Valencia y trabajo en una escuela cerca del mar.]{tl}

A longer block can be spread over several lines: an opening square bracket alone on the first line,
the closing one with its `{tl}` alone on the last. Lines are joined into one paragraph, so each
line that should stay a line ends with the return sign. A block may be tinted with `bg=` (`quote`,
`sand`, `rose`, `sage` or `lilac`); here is a short dialogue on sand:

[
—Buenos días. ¿Cómo te llamas? ⏎
—Me llamo Lucía. ¿Y tú? ⏎
—Yo me llamo Pablo. Encantado. ⏎
—Encantada.
]{tl bg=sand}

And a poem by Gustavo Adolfo Bécquer (*Rimas*, XXI), tinted as a quotation:

[
¿Qué es poesía?, dices mientras clavas ⏎
en mi pupila tu pupila azul. ⏎
¡Qué es poesía! ¿Y tú me lo preguntas? ⏎
Poesía... eres tú.
]{tl bg=quote}

Three things that other languages have do not apply to Spanish. There is no *display line*: a
paragraph of Persian, Arabic, Hindi, Japanese or Chinese script is recognised and set large on its
own, but Spanish is never recognised, only marked. There is no alternative typeface (`font=`),
which only Persian and Japanese have. And there is no vertical writing (`vertical`), which only
Japanese and Chinese have.

## Pronunciation

Spanish spelling is very nearly a map of its sounds, so most words need no pronunciation line and
the stress needs none at all: a written accent already marks it. Where the spelling does not show
the sound, add `translit:` inside the braces, as in [hola]{translit:ola} (the *h* is silent),
[hijo]{translit:ixo} and [gente]{translit:xente} (the *j*, and the *g* before *e* or *i*, are the
*ch* of Scottish *loch*), [calle]{translit:kaʝe} and [yo]{translit:ʝo} (*ll* and *y* are one
sound), [queso]{translit:keso} (*qu* is a plain *k*), [rojo]{translit:rroxo} with its rolled *r*,
[año]{translit:aɲo} (*ñ* is the *ny* of *canyon*) and [pingüino]{translit:pingwino} (the two dots
bring the *u* back). Point at a word to see its pronunciation. The glossary shows it too, beside
the meaning of any word glossed on the page; the PDF leaves it out.

A colour and a pronunciation can share the braces: [jamón]{teal translit:xamón}. This page gives
the pronunciation of Latin America, where [cinco]{translit:sinko} begins with an *s*^[In most of
Spain the *c* before *e* or *i* and the *z* are said like the *th* of *thin*: [cinco]{tl} is
*θinko* there. Both are correct; keep one throughout a note.]. Spanish has no separate reading
field: that one is for Japanese kana.

## Colours

Five colours have names: `crimson`, `indigo`, `teal`, `violet` and `amber`. Here they sort the words
of a sentence by what they do, with a sixth colour given as a hex code for the adverb:

[Hoy]{#2E7D32} [mi]{violet} [hermana]{crimson} [come]{teal}
[una]{indigo} [manzana]{crimson} [roja]{amber}.

*Today my sister is eating a red apple*: violet for the possessive, crimson for the nouns, teal for
the verb, indigo for the article, amber for the adjective and green for the adverb.

## Dictionary entries

A heading whose parts are separated by vertical bars is a dictionary entry: the headword, its
pronunciation, where it comes from, and after an equals sign its meaning. The meaning is not
printed; it puts the word into the glossary. With Spanish every heading with two or more parts is
an entry, so an ordinary heading cannot contain a vertical bar.

## hijo | ixo | from Latin *filius* | = *son*

- **History** the Latin *f* became an *h*, which is now silent
- **Feminine** [hija]{tl} = *daughter*
- **Plural** [hijos]{tl} = *sons*, and also *children*, sons and daughters together
- **Example** [Tengo dos hijos.]{tl} = *I have two children.*

A shorter entry leaves out where the word comes from:

## calle | kaʝe | = *street*

- **Gender** feminine: [la calle]{tl}
- **Example** [Vivo en esta calle.]{tl} = *I live on this street.*

The headword itself can carry a colour and its pronunciation. Here the pronunciation part of the
heading is left empty, so the one in the headword's braces fills it:

## [gente]{teal translit:xente} | | from Latin *gens*, *gentis* | = *people*

- **Grammar** a singular noun, so its verb is singular too:
  [la gente es amable]{tl} = *people are kind*
- **Example** [Hay mucha gente en la plaza.]{tl} = *There are a lot of people in the square.*

## Tables

A table is a row of headers, a row of dashes, then the rows. A colon on the left of the dashes
aligns a column to the left, colons on both sides centre it, a colon on the right aligns it to the
right; one dash in each cell of that row is enough. Below it, a cell holding only two dashes is
left empty.

| Figure | Number | Ordinal |
|---:|:---|:---:|
| 0 | [cero]{tl} | -- |
| 1 | [uno]{tl} | [primero]{tl} |
| 2 | [dos]{tl} | [segundo]{tl} |
| 3 | [tres]{tl} | [tercero]{tl} |
| 4 | [cuatro]{tl} | [cuarto]{tl} |
| 5 | [cinco]{tl} | [quinto]{tl} |

## Boxes

Every line of a box starts with `>`, and a box can hold anything a note can, a list included:

> **Three things the Spanish spelling tells you**
>
> - The written accent marks the stress: [corazón]{tl}, [fácil]{tl}, [estábamos]{tl}.
> - On short words it tells two words apart: [el]{tl} = *the* and [él]{tl} = *he*,
>   [tu]{tl} = *your* and [tú]{tl} = *you*.
> - A question or an exclamation opens with its own mark: [¿Dónde está la estación?]{tl} =
>   *Where is the station?*

## Notes and links

A footnote is called with a caret and a name in square brackets, and written anywhere in the note
on a line of its own; its further lines are indented by two spaces. Every Spanish noun is masculine
or feminine[^1]. A short note can also be written where it is called, with a caret before the
square brackets^[The word for *note* is [la nota]{tl}.].

[^1]: Most nouns ending in *-o* are masculine and most ending in *-a* feminine, but not all:
  [el día]{tl} = *the day* is masculine and [la mano]{tl} = *the hand* is feminine.

A link to a web page is its text in square brackets followed by the address in round ones: a
[short animated film](https://www.youtube.com/watch?v=aqz-KE-bpKQ) with no words at all.

A link to another note gives that note's name (its title) after `doc:`, as in this link to
[another note](doc:My second Spanish note). Leave the square brackets empty and the link shows the
note's title as its text: [](doc:My second Spanish note). A link to a name that no note has yet is
shown as a dangling link; create a note with that title and the link starts to work.

## Latin blocks

A paragraph of English in square brackets followed by `{la}` (Latin as in the Latin alphabet) is
set apart as a block of its own. It is meant for the prose language inside a right-to-left or
vertical page, but it works on any page to centre a passage's lines, tint it, or narrow and
indent it as a picture is. The Bécquer poem above, translated, its lines centred, on sand, at 80%
of the width:

[*What is poetry?* you say, as you fix ⏎
your blue eyes on mine. ⏎
What is poetry! And you are asking *me*? ⏎
Poetry... is you.]{la align=center bg=sand width=80}

[**A tip.** Read the poem aloud. The accent on the *í* keeps it apart from the *a*, so
[poesía]{tl} has four syllables: *po-e-sí-a*.]{la bg=quote width=80 offset=10}

## Mathematics

A formula in LaTeX notation between square brackets, followed by `{math}`, sits inside the line:
[\tfrac{1}{2}]{math} is [un medio]{tl} and a third is [un tercio]{tl}. On a line of its own
between `:::math` and `:::` it is set apart. Spain and most of South America write a decimal
comma, so three coffees at one euro fifty cost:

:::math
3 \times 1{,}50 = 4{,}50
:::

[Tres cafés son cuatro euros con cincuenta.]{tl}

## Pictures, recordings and a video

A picture is a line of its own: an exclamation mark, a caption in square brackets, the file under
`images/` in round brackets, and its layout in braces (`width` and `offset` in per cent of the
column, `align` left, center or right). A caption cannot hold square brackets, so it cannot mark a
Spanish word; name the word in the text. Here is [una manzana]{tl} = *an apple*, centred:

![An apple, centred at 40% of the width](images/starter-apple.svg){width=40 align=center}

and [una casa]{tl} = *a house*, on the left and indented a little:

![A house, on the left](images/starter-house.svg){width=30 align=left offset=10}

A recording is written the same way, with its file under `audio/`. This one rings like
[una campanilla]{tl} = *a little bell*:

![A short chime](audio/starter-chime.mp3){width=60 align=center}

`start=` and `end=` in the braces, in seconds or in minutes and seconds, play only a stretch of
it, here the bell's first note:

![The chime, its first note only](audio/starter-chime.mp3){width=50 align=center start=0 end=0.4}

A YouTube video starts with `@` instead of `!`, and `start` and `end` play only a clip:

@[A short animated film, from 0:10 to 0:40](https://www.youtube.com/watch?v=aqz-KE-bpKQ){width=70 align=center start=0:10 end=0:40}

## Exercises

An exercise sits between a `:::exercise` line and a `:::` line. The page shows it unsolved, with
a **Check exercises** button at the end; the editor's preview shows it solved. In the editor, the
**Exercises** menu's **Add exercise…** writes any of them through a form.

### Filling in and putting in order

Fill in the blanks: each blank is a name in double square brackets, answered by a row with that
name; rows with empty brackets are wrong choices. `content-direction: target` lays the activity out
in Spanish's own direction, which is left to right.

:::exercise fill-blanks
prompt: Complete the sentence with the right form of [ser]{tl} or [estar]{tl}.
content-direction: target
text: [Mi hermana [[job]] médica y hoy [[place]] en el hospital.]{tl}
- [job] [es]{tl}
- [place] [está]{tl}
- [ ] [son]{tl}
- [ ] [estoy]{tl}
explanation-correct: Right: [ser]{tl} for what she is, [estar]{tl} for where she is today.
explanation-incorrect: A profession takes [ser]{tl}, a place right now takes [estar]{tl}: [es médica]{tl}, [está en el hospital]{tl}.
:::

Put the lines in order; the rows are written in the right order and shuffled on the page.

:::exercise order-sentences
prompt: Put the conversation in the café in order.
- [1] [Buenos días. ¿Qué desea?]{tl}
- [2] [Un café con leche, por favor.]{tl}
- [3] [Aquí tiene. Son dos euros.]{tl}
- [4] [Gracias. ¡Hasta luego!]{tl}
:::

Build a sentence from its pieces:

:::exercise construct-sentence
prompt: Build the sentence: On Sundays my grandmother cooks paella for the whole family.
- [1] [Los domingos]{tl}
- [2] [mi abuela]{tl}
- [3] [cocina]{tl}
- [4] [paella]{tl}
- [5] [para toda la familia.]{tl}
:::

### Matching

Each row is a pair, left and right of `=>`; a picture can stand on either side.

:::exercise match-translations
prompt: Match each picture or English word with its Spanish name.
- ![An apple](images/starter-apple.svg) => [la manzana]{tl}
- ![A house](images/starter-house.svg) => [la casa]{tl}
- the street => [la calle]{tl}
- the son => [el hijo]{tl}
:::

:::exercise match-opposites
prompt: Match each word with its opposite.
- [grande]{tl} => [pequeño]{tl}
- [siempre]{tl} => [nunca]{tl}
- [caliente]{tl} => [frío]{tl}
- [mucho]{tl} => [poco]{tl}
:::

The rows below are written word first; `direction: definition-to-word` shows the definitions and
asks for the words.

:::exercise match-definitions
prompt: Match each definition with the word it defines. Careful: a [librería]{tl} is not a library.
direction: definition-to-word
- [la panadería]{tl} => [la tienda donde se vende pan]{tl}
- [la librería]{tl} => [la tienda donde se venden libros]{tl}
- [la biblioteca]{tl} => [el lugar donde se prestan libros]{tl}
- [el cartero]{tl} => [la persona que reparte las cartas]{tl}
:::

### Choosing

A row whose own text needs an arrow writes it `\=>`, so that it is not read as the answer's arrow.

:::exercise yes-no
prompt: Answer each question about Spanish.
- Is the *h* of [hola]{tl} pronounced? => no
- Is [agua]{tl} feminine, although we say [el agua]{tl}? => yes
- Is a [librería]{tl} a place to borrow books? => no
- Is [hablar]{tl} \=> [habló]{tl}, *to speak* and *he spoke*, a regular change? => yes
:::

Only the Spanish passage of the next prompt is in regular weight; the rest of a prompt is bold.

:::exercise true-false
prompt: Read the text, then decide whether each statement is true or false. ⏎ [[Ana vive en Sevilla con sus dos hijos. Por las mañanas trabaja en una librería del centro y por las tardes estudia inglés en una academia cerca de su casa.]{tl}]{no-bold}
- Ana lives in Seville with her two children. => true
- Ana works in a library. => false
- Ana has three children. => false
- In the mornings Ana works in a bookshop in the centre of the city, and in the afternoons she studies English at a language school near her home. => true
:::

:::exercise single-choice
prompt: Listen. What is making this sound?
audio: audio/starter-chime.mp3 {width=50 align=center}
- [x] [una campanilla]{tl}
- [ ] [un perro]{tl}
- [ ] [la lluvia]{tl}
explanation-correct: Yes: [una campanilla]{tl}, a little bell, is ringing.
explanation-incorrect: Listen again: it rings, so it is [una campanilla]{tl}, a little bell. A dog barks and the rain patters.
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *apple*?
image-answer: images/starter-apple.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] [la manzana]{tl}
- [ ] [la naranja]{tl}
- [ ] [el pan]{tl}
explanation-correct: [la manzana]{tl} is an apple; [la naranja]{tl} is an orange and [el pan]{tl} bread. The chime stands in for the word said aloud.
:::

:::exercise incorrect-part
prompt: Which part of the sentence is wrong?
- [ ] [La gente]{tl}
- [x] [son]{tl}
- [ ] [muy amable]{tl}
- [ ] [en este pueblo.]{tl}
explanation-correct: Right: [gente]{tl} is singular, so [La gente es muy amable en este pueblo.]{tl}
explanation-incorrect: The verb is the problem: [gente]{tl} is singular and takes [es]{tl}, not [son]{tl}.
:::

:::exercise choose-all
prompt: Which of these nouns are feminine?
- [x] [mano]{tl}
- [ ] [día]{tl}
- [x] [agua]{tl}
- [x] [calle]{tl}
- [ ] [problema]{tl}
explanation-correct: [la mano]{tl}, [el agua]{tl} and [la calle]{tl} are feminine; [el día]{tl} and [el problema]{tl} are masculine.
:::

:::exercise odd-one-out
prompt: Look at the house. Which word does not name a part of it?
image: images/starter-house.svg {width=30 align=center}
- [ ] [el tejado]{tl}
- [ ] [la puerta]{tl}
- [ ] [la ventana]{tl}
- [x] [el río]{tl}
explanation-correct: [el río]{tl} is a river; the roof, the door and the window belong to the house.
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: At a café a customer says: [Buenos días. Quiero un café y una tostada, por favor.]{tl} Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then something to eat.
::::exercise single-choice
prompt: What does the customer want to drink?
- [x] [un café]{tl}
- [ ] [una tostada]{tl}
- [ ] [un zumo]{tl}
explanation-correct: [Un café]{tl}, *a coffee*; the toast is [una tostada]{tl}.
::::
::::exercise true-false
prompt: Now decide.
- [Tostada]{tl} is a feminine noun, so it takes [una]{tl}. => true
- [Por favor]{tl} means *excuse me*. => false
explanation-correct: [Por favor]{tl} is *please*; *excuse me* is [perdón]{tl}.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the words you have just read.
content-direction: target
text: [Buenos días. Quiero [[drink]] y [[food]], por favor.]{tl}
- [drink] [un café]{tl}
- [food] [una tostada]{tl}
- [ ] [un tostada]{tl}
explanation-correct: [Café]{tl} is masculine and [tostada]{tl} feminine.
::::
:::

### Flashcards

A flashcard turns over when it is clicked and is never scored. A vocabulary card, whose speaker
button plays the recording its `back-audio:` names (the chime, where the word said aloud would go)
without turning the card:

:::exercise flashcard
card-type: vocab
target: [la manzana]{tl}
transliteration: la mansana
meaning: the apple
context: [Cada mañana como una manzana.]{tl} = *Every morning I eat an apple.*
notes: feminine; the plural is [las manzanas]{tl}
back-audio: audio/starter-chime.mp3
:::

A card of opposites:

:::exercise flashcard
card-type: opposites
target: [abrir]{tl}
opposite: [cerrar]{tl}
notes: [cerrar]{tl} changes its stem: [cierro la puerta]{tl} = *I close the door.*
:::

A free card has two fields on each side, and each field may hold several lines of anything a note
holds: a picture, a recording, paragraphs. `-size` and `-shade` change how a field is drawn.

:::exercise flashcard
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=40 align=center}
front-secondary: What is this, and what colours can it be?
back-primary: |
  **[una manzana]{tl}** = *an apple*

  [Las manzanas pueden ser rojas, verdes o amarillas.]{tl}
back-secondary: |
  ![A chime for a right answer](audio/starter-chime.mp3)

  [¡Muy bien!]{tl}
front-secondary-size: 90
front-secondary-shade: muted
back-primary-size: 110
back-primary-shade: accent
:::
