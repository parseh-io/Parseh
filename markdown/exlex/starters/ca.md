---
title: New Catalan note
subtitle: A guided tour of everything a note can hold, in Catalan
note: A demo page: keep what you need, delete the rest
lang: en
target: ca
---

> **This is a demo note.** It shows, on real Catalan, everything a studio note can contain: text,
> marks, tables, notes, links, pictures, recordings, a video and every kind of exercise. Keep what
> you need and delete the rest; the editor beside the preview shows how each thing is written.
>
> Catalan is written in the same alphabet as the English around it, so the studio cannot tell
> the two apart on its own: **every Catalan word on this page is marked**. A word or a sentence
> in square brackets followed by `{tl}` (for *target language*) is Catalan, as in
> [Benvinguts!]{tl}; a colour or a pronunciation mark counts as the mark too.

## Ordinary prose

A paragraph is plain text, and a blank line starts a new one. **Two asterisks** make bold, *one*
makes italics, and **bold can hold *italics* inside it**. Backticks set `a few characters` apart
as code. A line break inside a paragraph is written with the return sign, ⏎ and the text goes on
from the next line, as it does here.

A list starts each line with a dash, and a line indented by two spaces sits one level down:

- [hola]{tl} = *hello*
- [bon dia]{tl} = *good morning*
- [bona tarda]{tl} = *good afternoon*
- [bona nit]{tl} = *good evening, good night*
  - said on arriving as well as on leaving: [Bona nit, senyora!]{tl}

A numbered list starts each line with a number and a full stop; the numbers are counted for you.
Ordering a coffee:

1. greet: [Bon dia.]{tl} = *Good morning.*
2. ask: [Un cafè amb llet, si us plau.]{tl} = *A white coffee, please.*
3. thank: [Moltes gràcies.]{tl} = *Thank you very much.*

When every item starts with a **bold label**, the list becomes a list of definitions. Catalan has
two verbs for *to be*, and it does not divide them where Spanish does:

- **[ser]{tl}** what a thing *is* — identity, origin, what it is like — and *where* it is.
  [Soc de Girona.]{tl} = *I am from Girona.* [La Maria és a casa.]{tl} = *Maria is at home.*
- **[estar]{tl}** how it is *right now*: a state, the result of a change.
  [Estic cansat.]{tl} = *I am tired.*

The arrow shows a change of form: [la casa]{tl} → [les cases]{tl},
[el peix]{tl} → [els peixos]{tl}, and a hyphen and a greater-than sign make the same arrow:
[la mà]{tl} -> [les mans]{tl}. A cross before a form marks it wrong and a tick marks the right
one: an article loses its vowel before a vowel, so ✗[la escola]{tl} is wrong and
✅ [l'escola]{tl} is right.

## Catalan in the text

### Words and phrases

A Catalan run is marked with `{tl}`: [la ciutat]{tl}, [el mercat]{tl}. The language's own code
works as well as `{tl}`, so [adéu]{ca} is marked too. A run inside two asterisks is set in bold,
as **[Que bonic!]{tl}** is here. An equals sign and an italic translation after a run make a
gloss, [la ciutat]{tl} = *the city*, and every gloss written this way goes into the note's
glossary.

### Whole paragraphs and poems

A paragraph that is nothing but one marked stretch becomes a Catalan block of its own:

[Em dic Montse, visc a Tarragona i treballo en una escola a prop del mar.]{tl}

A longer block can be spread over several lines: an opening square bracket alone on the first line,
the closing one with its `{tl}` alone on the last. Lines are joined into one paragraph, so each
line that should stay a line ends with the return sign. A block may be tinted with `bg=` (`quote`,
`sand`, `rose`, `sage` or `lilac`); here is a short dialogue on sand:

[
—Bon dia. Com et dius? ⏎
—Em dic Laia. I tu? ⏎
—Jo em dic Pau. Molt de gust. ⏎
—Igualment.
]{tl bg=sand}

And a proverb on the *rose* tint — whoever wants no dust should keep away from the threshing floor:

[Qui no vulgui pols, que no vagi a l'era.]{tl bg=rose}

And the opening of a poem by Jacint Verdaguer (*L'emigrant*), tinted as a quotation:

[
Dolça Catalunya, ⏎
pàtria del meu cor, ⏎
quan de tu s'allunya ⏎
d'enyorança es mor.
]{tl bg=quote}

Three things that other languages have do not apply to Catalan. There is no *display line*: a
paragraph of Persian, Arabic, Hindi, Japanese or Chinese script is recognised and set large on its
own, but Catalan is never recognised, only marked. There is no alternative typeface (`font=`),
which only Persian and Japanese have. And there is no vertical writing (`vertical`), which only
Japanese and Chinese have.

## Pronunciation

Catalan spelling says less of its sounds than Spanish or Italian spelling does: it does not show
whether a stressed *e* or *o* is open or closed, unstressed vowels weaken, and some letters are
not said at all. Where the spelling does not show the sound, add `translit:` inside the braces, as
in [porta]{translit:pòrtə} (an open *o*, and the final *a* is the neutral vowel *ə*, the *a* of
*about*), [boca]{translit:bókə} (a closed *o*), [parlar]{translit:pərlá} (the *r* of an
infinitive is silent), [molt]{translit:mól} (so is a *t* after *l*), [llibre]{translit:ʎíbrə}
(*ll* is the *lli* of *million*), [any]{translit:aɲ} (*ny* is the *ny* of *canyon*),
[caixa]{translit:káʃə} (*ix* is *sh*), [cotxe]{translit:kòtʃə} (*tx* is *ch*) and
[col·lecció]{translit:kulləksió} (the middle dot makes a long *l*, not the *ll* of
[llibre]{tl}). Point at a word to see its pronunciation. The glossary shows it too, beside the
meaning of any word glossed on the page; the PDF leaves it out.

A colour and a pronunciation can share the braces: [pernil]{teal translit:pərníl}. This page gives
the pronunciation of Central Catalan, the Catalan of Barcelona, where [casa]{translit:kázə} ends in
the neutral vowel^[In Valencia the unstressed vowels keep their own sounds: [casa]{tl} is *káza*
there, and the *r* of [parlar]{tl} is said. Both are correct; keep one throughout a note.]. Catalan
has no separate reading field: that one is for Japanese kana.

## Colours

Five colours have names: `crimson`, `indigo`, `teal`, `violet` and `amber`. Here they sort the words
of a sentence by what they do, with a sixth colour given as a hex code for the adverb:

[Avui]{#2E7D32} [la meva]{violet} [germana]{crimson} [menja]{teal}
[una]{indigo} [poma]{crimson} [vermella]{amber}.

*Today my sister is eating a red apple*: violet for the possessive, which brings its article with
it, crimson for the nouns, teal for the verb, indigo for the article, amber for the adjective and
green for the adverb.

## Dictionary entries

A heading whose parts are separated by vertical bars is a dictionary entry: the headword, its
pronunciation, where it comes from, and after an equals sign its meaning. The meaning is not
printed; it puts the word into the glossary. With Catalan every heading with two or more parts is
an entry, so an ordinary heading cannot contain a vertical bar.

## fill | fiʎ | from Latin *filius* | = *son*

- **History** the Latin *-li-* became the *ll* that ends the word, the sound of *lli* in *million*
- **Feminine** [filla]{tl} = *daughter*
- **Plural** [fills]{tl} = *sons*, and also *children*, sons and daughters together
- **Example** [Tinc dos fills.]{tl} = *I have two children.*

A shorter entry leaves out where the word comes from:

## carrer | kərré | = *street*

- **Gender** masculine: [el carrer]{tl}, although Spanish *calle* is feminine
- **Example** [Visc en aquest carrer.]{tl} = *I live on this street.*

The headword itself can carry a colour and its pronunciation. Here the pronunciation part of the
heading is left empty, so the one in the headword's braces fills it:

## [gent]{teal translit:ʒén} | | from Latin *gens*, *gentis* | = *people*

- **Grammar** a singular noun, so its verb is singular too:
  [la gent és amable]{tl} = *people are kind*
- **Example** [Hi ha molta gent a la plaça.]{tl} = *There are a lot of people in the square.*

## Tables

A table is a row of headers, a row of dashes, then the rows. A colon on the left of the dashes
aligns a column to the left, colons on both sides centre it, a colon on the right aligns it to the
right; one dash in each cell of that row is enough. Below it, a cell holding only two dashes is
left empty.

| Figure | Number | Ordinal |
|---:|:---|:---:|
| 0 | [zero]{tl} | -- |
| 1 | [un]{tl} | [primer]{tl} |
| 2 | [dos]{tl} | [segon]{tl} |
| 3 | [tres]{tl} | [tercer]{tl} |
| 4 | [quatre]{tl} | [quart]{tl} |
| 5 | [cinc]{tl} | [cinquè]{tl} |

## Boxes

Every line of a box starts with `>`, and a box can hold anything a note can, a list included:

> **Three things the Catalan spelling tells you**
>
> - The written accent marks the stress, and on an *e* or an *o* whether it is open (*è*, *ò*)
>   or closed (*é*, *ó*): [cafè]{tl}, [també]{tl}, [història]{tl}.
> - On a few short words it tells two words apart: [es]{tl} = *himself, herself* and
>   [és]{tl} = *is*, [mes]{tl} = *month* and [més]{tl} = *more*.
> - The middle dot belongs to the word: [col·lecció]{tl}, [il·lusió]{tl} = *hope, illusion*.

## Notes and links

A footnote is called with a caret and a name in square brackets, and written anywhere in the note
on a line of its own; its further lines are indented by two spaces. Every Catalan noun is masculine
or feminine[^1]. A short note can also be written where it is called, with a caret before the
square brackets^[The word for *note* is [la nota]{tl}.].

[^1]: Most nouns ending in *-a* are feminine, but not all: [el dia]{tl} = *the day* is
  masculine and [la mà]{tl} = *the hand* is feminine. A few differ from Spanish:
  [la dent]{tl} = *the tooth*, [el costum]{tl} = *the custom*.

A link to a web page is its text in square brackets followed by the address in round ones: a
[short animated film](https://www.youtube.com/watch?v=aqz-KE-bpKQ) with no words at all.

A link to another note gives that note's name (its title) after `doc:`, as in this link to
[another note](doc:My second Catalan note). Leave the square brackets empty and the link shows the
note's title as its text: [](doc:My second Catalan note). A link to a name that no note has yet is
shown as a dangling link; create a note with that title and the link starts to work.

## Latin blocks

A paragraph of English in square brackets followed by `{la}` (Latin as in the Latin alphabet) is
set apart as a block of its own. It is meant for the prose language inside a right-to-left or
vertical page, but it works on any page to centre a passage's lines, tint it, or narrow and
indent it as a picture is. The Verdaguer lines above, translated, centred, on sand, at 80% of the
width:

[*Sweet Catalonia,* ⏎
homeland of my heart, ⏎
whoever goes far from you ⏎
dies of longing.]{la align=center bg=sand width=80}

[**A tip.** Read the lines aloud. In [s'allunya]{tl} and [enyorança]{tl} the *ll* and the *ny*
are single sounds, and the apostrophe joins [es]{tl} and [de]{tl} to the word after them: no
pause.]{la bg=lilac width=80 offset=10}

## Mathematics

A formula in LaTeX notation between square brackets, followed by `{math}`, sits inside the line:
[\tfrac{1}{2}]{math} is [un mig]{tl} and a third is [un terç]{tl}. On a line of its own
between `:::math` and `:::` it is set apart. Catalan writes a decimal comma, so three coffees at
one euro fifty cost:

:::math
3 \times 1{,}50 = 4{,}50
:::

[Tres cafès són quatre euros amb cinquanta.]{tl}

## Pictures, recordings and a video

A picture is a line of its own: an exclamation mark, a caption in square brackets, the file under
`images/` in round brackets, and its layout in braces (`width` and `offset` in per cent of the
column, `align` left, center or right). A caption cannot hold square brackets, so it cannot mark a
Catalan word; name the word in the text. Here is [una poma]{tl} = *an apple*, centred:

![An apple, centred at 40% of the width](images/starter-apple.svg){width=40 align=center}

and [una casa]{tl} = *a house*, on the left and indented a little:

![A house, on the left](images/starter-house.svg){width=30 align=left offset=10}

A recording is written the same way, with its file under `audio/`. This one rings like
[una campaneta]{tl} = *a little bell*:

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
in Catalan's own direction, which is left to right.

:::exercise fill-blanks
prompt: Complete the sentence with the right form of [ser]{tl} or [estar]{tl}.
content-direction: target
text: [La meva germana [[job]] metgessa i avui [[state]] molt cansada.]{tl}
- [job] [és]{tl}
- [state] [està]{tl}
- [ ] [són]{tl}
- [ ] [estic]{tl}
explanation-correct: Right: [ser]{tl} for what she is, [estar]{tl} for how she is today.
explanation-incorrect: A profession takes [ser]{tl}, a state right now takes [estar]{tl}: [és metgessa]{tl}, [està cansada]{tl}.
:::

Put the lines in order; the rows are written in the right order and shuffled on the page.

:::exercise order-sentences
prompt: Put the conversation in the café in order.
- [1] [Bon dia. Què li poso?]{tl}
- [2] [Un cafè amb llet, si us plau.]{tl}
- [3] [Aquí té. Són dos euros.]{tl}
- [4] [Gràcies. Fins després!]{tl}
:::

Build a sentence from its pieces:

:::exercise construct-sentence
prompt: Build the sentence: On Sundays my grandmother cooks paella for the whole family.
- [1] [Els diumenges]{tl}
- [2] [la meva àvia]{tl}
- [3] [cuina]{tl}
- [4] [paella]{tl}
- [5] [per a tota la família.]{tl}
:::

### Matching

Each row is a pair, left and right of `=>`; a picture can stand on either side.

:::exercise match-translations
prompt: Match each picture or English word with its Catalan name.
- ![An apple](images/starter-apple.svg) => [la poma]{tl}
- ![A house](images/starter-house.svg) => [la casa]{tl}
- the street => [el carrer]{tl}
- the son => [el fill]{tl}
:::

:::exercise match-opposites
prompt: Match each word with its opposite.
- [gran]{tl} => [petit]{tl}
- [sempre]{tl} => [mai]{tl}
- [calent]{tl} => [fred]{tl}
- [molt]{tl} => [poc]{tl}
:::

The rows below are written word first; `direction: definition-to-word` shows the definitions and
asks for the words.

:::exercise match-definitions
prompt: Match each definition with the word it defines. Careful: a [llibreria]{tl} is not a library.
direction: definition-to-word
- [la fleca]{tl} => [la botiga on es ven pa]{tl}
- [la llibreria]{tl} => [la botiga on es venen llibres]{tl}
- [la biblioteca]{tl} => [el lloc on es deixen llibres]{tl}
- [el carter]{tl} => [la persona que reparteix les cartes]{tl}
:::

### Choosing

A row whose own text needs an arrow writes it `\=>`, so that it is not read as the answer's arrow.

:::exercise yes-no
prompt: Answer each question about Catalan.
- Is the *h* of [home]{tl} pronounced? => no
- Is [dent]{tl} feminine, although Spanish *diente* is masculine? => yes
- Is a [llibreria]{tl} a place to borrow books? => no
- Is [parlar]{tl} \=> [vaig parlar]{tl}, *to speak* and *I spoke*, the usual way to tell the past? => yes
:::

Only the Catalan passage of the next prompt is in regular weight; the rest of a prompt is bold.

:::exercise true-false
prompt: Read the text, then decide whether each statement is true or false. ⏎ [[L'Anna viu a Girona amb els seus dos fills. Al matí treballa en una llibreria del centre i a la tarda estudia anglès en una acadèmia a prop de casa seva.]{tl}]{no-bold}
- Anna lives in Girona with her two children. => true
- Anna works in a library. => false
- Anna has three children. => false
- In the mornings Anna works in a bookshop in the centre of the city, and in the afternoons she studies English at a language school near her home. => true
:::

:::exercise single-choice
prompt: Listen. What is making this sound?
audio: audio/starter-chime.mp3 {width=50 align=center}
- [x] [una campaneta]{tl}
- [ ] [un gos]{tl}
- [ ] [la pluja]{tl}
explanation-correct: Yes: [una campaneta]{tl}, a little bell, is ringing.
explanation-incorrect: Listen again: it rings, so it is [una campaneta]{tl}, a little bell. A dog barks and the rain patters.
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *apple*?
image-answer: images/starter-apple.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] [la poma]{tl}
- [ ] [la taronja]{tl}
- [ ] [el pa]{tl}
explanation-correct: [la poma]{tl} is an apple; [la taronja]{tl} is an orange and [el pa]{tl} bread. The chime stands in for the word said aloud.
:::

:::exercise incorrect-part
prompt: Which part of the sentence is wrong?
- [ ] [La gent]{tl}
- [x] [són]{tl}
- [ ] [molt amable]{tl}
- [ ] [en aquest poble.]{tl}
explanation-correct: Right: [gent]{tl} is singular, so [La gent és molt amable en aquest poble.]{tl}
explanation-incorrect: The verb is the problem: [gent]{tl} is singular and takes [és]{tl}, not [són]{tl}.
:::

:::exercise choose-all
prompt: Which of these nouns are feminine?
- [x] [mà]{tl}
- [ ] [dia]{tl}
- [x] [dent]{tl}
- [x] [calor]{tl}
- [ ] [problema]{tl}
explanation-correct: [la mà]{tl}, [la dent]{tl} and [la calor]{tl} are feminine; [el dia]{tl} and [el problema]{tl} are masculine.
:::

:::exercise odd-one-out
prompt: Look at the house. Which word does not name a part of it?
image: images/starter-house.svg {width=30 align=center}
- [ ] [la teulada]{tl}
- [ ] [la porta]{tl}
- [ ] [la finestra]{tl}
- [x] [el riu]{tl}
explanation-correct: [el riu]{tl} is a river; the roof, the door and the window belong to the house.
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: At a café a customer says: [Bon dia. Vull un cafè i una torrada, si us plau.]{tl} Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then something to eat.
::::exercise single-choice
prompt: What does the customer want to drink?
- [x] [un cafè]{tl}
- [ ] [una torrada]{tl}
- [ ] [un suc]{tl}
explanation-correct: [Un cafè]{tl}, *a coffee*; the toast is [una torrada]{tl}.
::::
::::exercise true-false
prompt: Now decide.
- [Torrada]{tl} is a feminine noun, so it takes [una]{tl}. => true
- [Si us plau]{tl} means *excuse me*. => false
explanation-correct: [Si us plau]{tl} is *please*; *excuse me* is [perdó]{tl}.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the words you have just read.
content-direction: target
text: [Bon dia. Vull [[drink]] i [[food]], si us plau.]{tl}
- [drink] [un cafè]{tl}
- [food] [una torrada]{tl}
- [ ] [un torrada]{tl}
explanation-correct: [Cafè]{tl} is masculine and [torrada]{tl} feminine.
::::
:::

### Flashcards

A flashcard turns over when it is clicked and is never scored. A vocabulary card, whose speaker
button plays the recording its `back-audio:` names (the chime, where the word said aloud would go)
without turning the card:

:::exercise flashcard
card-type: vocab
target: [la poma]{tl}
transliteration: lə pómə
meaning: the apple
context: [Cada matí menjo una poma.]{tl} = *Every morning I eat an apple.*
notes: feminine; the plural is [les pomes]{tl}, the final *a* written *e*
back-audio: audio/starter-chime.mp3
:::

A card of opposites, each side with its pronunciation:

:::exercise flashcard
card-type: opposites
target: [obrir]{tl}
transliteration: ubrí
opposite: [tancar]{tl}
opposite-transliteration: tənká
notes: [obrir]{tl} has an irregular participle: [he obert la porta]{tl} = *I have opened the door.*
:::

A free card has two fields on each side, and each field may hold several lines of anything a note
holds: a picture, a recording, paragraphs. `-size` and `-shade` change how a field is drawn.

:::exercise flashcard
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=40 align=center}
front-secondary: What is this, and what colours can it be?
back-primary: |
  **[una poma]{tl}** = *an apple*

  [Les pomes poden ser vermelles, verdes o grogues.]{tl}
back-secondary: |
  ![A chime for a right answer](audio/starter-chime.mp3)

  [Molt bé!]{tl}
front-secondary-size: 90
front-secondary-shade: muted
back-primary-size: 110
back-primary-shade: accent
:::
