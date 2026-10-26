---
title: New Turkish note
subtitle: A tour of everything a note can hold
note: Written in English about Turkish · keep what you need, delete the rest
lang: en
target: tr
---

> **This page is a demo.** It shows everything a note can contain: plain Markdown, Turkish words
> and sentences, pronunciations, colours, vocabulary entries, a table, footnotes, links, pictures,
> a recording, a video, formulas and one exercise of every kind. Keep what you need and delete
> the rest; the editor beside the preview shows how each thing is written.
>
> Turkish is written in the same alphabet as the English around it, so the studio cannot
> recognise it on its own: **every Turkish word on this page is marked**, and every Turkish word
> you write has to be marked too.

## Plain Markdown

A paragraph is simply lines of text: they join into one, and a blank line starts the next
paragraph. Words can be **bold** or *italic*, and something to be typed exactly as it stands,
such as a file name, can be set as `inline code`. A line can also be broken without starting a
new paragraph: the toolbar's return-arrow button puts in the sign for it,⏎
and this is the line it starts.

Each heading with two hashes starts a section, numbered for you (there is no need to number it
yourself), and one with three hashes starts a smaller, unnumbered subsection, like the next one.

### Lists

A dash starts a bullet list; a line indented by two spaces goes one level in:

- [merhaba]{tl} = *hello*, at any time of day
- [günaydın]{tl} = *good morning*
  - from [gün]{tl} *day* and [aydın]{tl} *bright*
- [iyi akşamlar]{tl} = *good evening*
- [iyi geceler]{tl} = *good night*

A number with a full stop starts a numbered list, and the numbers are counted for you:

1. [bir]{tl} = *one*
2. [iki]{tl} = *two*
3. [üç]{tl} = *three*

When every item starts with a **bold label**, the list is laid out as a list of terms:

- **Vowel harmony** most endings take the vowel that suits the word: the ending
  [-de/-da/-te/-ta]{tl} *in* gives [evde]{tl} *at home* and [okulda]{tl} *at school*.
- **Endings in a row** a word is built by adding one ending after another:
  [evlerimizden]{tl} = *from our houses* is [ev-ler-imiz-den]{tl}, house + plural + our + from.
- **The verb last** a sentence usually ends on its verb: [Ben çay içiyorum.]{tl}
  *I am drinking tea.*

An arrow shows what becomes what: [kitap]{tl} → [kitabı]{tl}, *the book* as an object. A hyphen
and a greater-than sign make the same arrow: [ağaç]{tl} -> [ağacı]{tl}, *the tree*. A cross marks
a form that is wrong and a tick one that is right: ✗[kitapı]{tl} ✅ [kitabı]{tl}.

## Turkish in the text

A word in square brackets followed by `{tl}` is marked as Turkish: [merhaba]{tl}. It is set in
the Turkish font, and in the preview a hover over it lets you give it a colour and a
pronunciation. The language's own code does the same, [teşekkürler]{tr}, and so does any other
mark in braces, a colour or a pronunciation, as the next sections show. A mark followed by an
equals sign and a meaning in italics is a **gloss**: [teşekkür ederim]{tl} = *thank you*. The
studio's glossary collects every gloss in the note.

Bold works on Turkish as well: **[çok güzel]{tl}** = *very beautiful*.

A whole paragraph of Turkish is one mark around the paragraph:

[Merhaba! Ben bir öğrenciyim. Her gün biraz Türkçe okuyorum ve yeni kelimeler öğreniyorum.]{tl}

*Hello! I am a student. Every day I read a little Turkish and learn new words.*

A language with a script of its own is recognised without any mark, and a paragraph written only
in that script becomes a large display line. Turkish shares its letters with English, so it has
neither: the mark is always what makes Turkish Turkish.

### Blocks of Turkish

A block can span several lines: an opening square bracket on a line of its own, the text, then
the closing bracket with its braces. The lines still join, so each one ends with the return
sign. Written as `bg=` inside the braces, a tint sets the block apart: `quote`, `sand`, `rose`,
`sage` or `lilac`.

[
— Merhaba, nasılsın?⏎
— İyiyim, teşekkür ederim. Sen nasılsın?⏎
— Ben de iyiyim. Bir çay içelim mi?⏎
— Olur, içelim!
]{tl bg=sand}

*Hello, how are you? I'm fine, thank you. And you? I'm fine too. Shall we have a tea? All right,
let's!*

Four lines by Yunus Emre, the poet who wrote in Turkish seven hundred years ago, in today's
spelling:

[
Gelin tanış olalım,⏎
İşi kolay kılalım,⏎
Sevelim, sevilelim,⏎
Dünya kimseye kalmaz.
]{tl bg=quote}

*Come, let us get to know one another and make the work easy; let us love and be loved: the
world is left to no one.*

[Damlaya damlaya göl olur.]{tl bg=sage}

*Drop by drop, a lake is made*: a proverb for patient learners.

Two more options exist for other languages. `font=` picks a second typeface where the language
has one, and Turkish has none; `vertical` sets a block in columns, which only Japanese and
Chinese do.

## Pronunciation

Turkish is spelled as it is said, one letter for one sound, so most words need no help and the
letters are learned once: [c]{tl} is the *j* of *jam*, [ç]{tl} the *ch* of *church*, [ş]{tl}
the *sh* of *ship*. A pronunciation rides in the braces after `translit:`; hover over a word to
read it (the printed PDF shows only the word). It is worth writing in three cases:

> **Where a pronunciation helps**
>
> 1. **The soft g**, [ğ]{tl}, which is never a consonant. After [a ı o u]{tl} it lengthens
>    the vowel: [dağ]{translit:dā} *mountain*, [yağmur]{translit:yāmur} *rain*. After
>    [e]{tl} and [i]{tl} it sounds like a *y*: [iğne]{translit:iyne} *needle*. After [ö]{tl}
>    and [ü]{tl} it lengthens the vowel again: [düğün]{translit:dǖn} *wedding*, whose long
>    *ü* is all that tells it from [dün]{tl} *yesterday*.
> 2. **A long vowel**, in words from Arabic and Persian, which the spelling marks with a
>    circumflex only some of the time: [kâr]{translit:kār} *profit* against [kar]{tl} *snow*,
>    [hâlâ]{translit:hālā} *still* against [hala]{tl} *aunt*.
> 3. **Stress away from the last syllable**, written ˈ before the stressed one:
>    [Ankara]{translit:ˈAnkara}, [şimdi]{translit:ˈşimdi} *now*,
>    [yapamam]{translit:yaˈpamam} *I can't do it*.

A colour and a pronunciation can share the braces: [yağmur]{teal translit:yāmur}.

## Colours

A colour name in the braces paints a word. There are five: [kırmızı]{crimson} *red* in crimson,
[lacivert]{indigo} *navy blue* in indigo, [turkuaz]{teal} *turquoise* in teal, [mor]{violet}
*purple* in violet and [kehribar]{amber} *amber* in amber. Any other colour is a hash sign and
six hexadecimal digits: [gök mavisi]{#2F6B8F} *sky blue*.

Colours are good at showing the pieces of a long word:
[ev]{teal}[ler]{crimson}[imiz]{indigo}[den]{amber} *from our houses*.

## Vocabulary entries

A heading whose parts are divided by upright bars is a vocabulary entry: the word in large type,
then its pronunciation, its origin and, after an equals sign, its meaning, which is not printed
but goes into the glossary. A Turkish entry needs at least two parts, so a section title in a
Turkish note can never contain a bar. The full form:

## dağ | dā | Old Turkic *taġ* | = *mountain*

- **Meaning** a mountain, and a great heap of anything: [dağ gibi bulaşık]{tl} = *a mountain
  of dishes*, literally “dishes like a mountain”.
- **Example** [Dağın tepesinde hâlâ kar var.]{tl} = *There is still snow on the top of the
  mountain.*
- **Family** [dağcı]{tl} = *mountaineer*, [dağlık]{tl} = *mountainous*.

Two parts are enough, the word and its pronunciation:

## öğle | ȫle | = *noon*

- **Lunch** [öğle yemeği]{tl} = *lunch*, the noon meal.
- **Afternoon** [öğleden sonra]{tl} = *afternoon*, literally “after noon”.

The word may carry a colour, and its pronunciation may ride in its braces; the pronunciation's
own part is then left empty:

## [kâr]{teal translit:kār} | | from Persian *kār*, “work, business” | = *profit*

- **Not to be confused with** [kar]{tl} = *snow*, with a short vowel and a hard *k*.
- **Example** [Bu yıl kâr düşük.]{tl} = *Profits are low this year.*
- **Family** [kârlı]{tl} = *profitable*, [kârsız]{tl} = *unprofitable*.

## A table

A table is rows of cells divided by bars, with a row of dashes under the header. A colon on the
left, on both sides or on the right of the dashes aligns that column, and a cell holding only two
dashes stays empty. The plural ending [-ler/-lar]{tl} follows the last vowel of the word; after a
number, though, a Turkish noun stays singular, so the last row has no plural at all.

| Word | Meaning | Plural | Ending |
|:-----|:-------:|-------:|:------:|
| [ev]{tl} | house | [evler]{tl} | [-ler]{tl} |
| [kitap]{tl} | book | [kitaplar]{tl} | [-lar]{tl} |
| [göz]{tl} | eye | [gözler]{tl} | [-ler]{tl} |
| [okul]{tl} | school | [okullar]{tl} | [-lar]{tl} |
| [üç kitap]{tl} | three books | -- | -- |

## Footnotes

A footnote is a caret and a name inside square brackets in the text, and the same mark followed
by a colon at the start of a line anywhere in the note; lines that continue that note are
indented by two spaces. Turkish has no grammatical gender and no word for *the*[^1].

A note can also be written where it belongs, between a caret with an opening square bracket and
a closing one: tea is the drink of every hour^[It comes in small glasses shaped like a tulip,
called [ince belli bardak]{tl}, *slim-waisted glass*.].

[^1]: The one word [o]{tl} means *he*, *she* and *it*. With no article, [kapı açık]{tl} is
  *the door is open*, and [bir kapı]{tl} is *a door*, or *one door*.

## Links

A link is its text in square brackets followed by the address in round brackets:
[a short film](https://www.youtube.com/watch?v=aqz-KE-bpKQ) opens in a new tab.

A link can point to another note too, by its name: [another note](doc:My second Turkish note).
With nothing between the square brackets it shows that name: [](doc:My second Turkish note).
A link goes by a note's title: while no note is called that, the link is shown as a dangling
link, and creating a note with that title makes it work.

## Blocks of English set apart

A paragraph of English wrapped in square brackets with `la` in the braces is a block of its own:
`align` centres its lines or sets them to the right, `bg` tints it, `width` narrows it and
`offset` moves it sideways, both in percent of the column. It is made for notes in a
right-to-left or vertical language, where English needs a box of its own direction; in a
Turkish note it is simply a way to set a paragraph apart.

[Turkish has no verb for *to have*. It says that something of yours exists instead:
[Bir kedim var]{tl}, *I have a cat*, is literally
“a cat of mine there is”.]{la align=center bg=sand width=80}

[A narrower block, 80% of the column wide and moved 10% to the right,
with no tint.]{la width=80 offset=10}

## Formulas

A formula inside a sentence is written in LaTeX between square brackets, followed by `math` in
braces. Turkish has eight vowels, one for every way of answering three yes-or-no questions,
[2 \times 2 \times 2 = 8]{math}: front or back, rounded or not, high or low. Together they are
[a e ı i o ö u ü]{tl}.

A formula on its own lines goes between a line reading `:::math` and a line of three colons. One
noun, with or without the plural, with no possessive or one of six, in any of six cases:

:::math
\underbrace{2}_{\text{plural}} \times \underbrace{7}_{\text{possessive}}
  \times \underbrace{6}_{\text{case}} = 84
:::

That is 84 combinations for the one noun [ev]{tl}, from [ev]{tl} itself to [evlerimizden]{tl}.

## Pictures, a recording and a video

A picture stands on a line of its own: an exclamation mark, the caption in square brackets, the
file in round brackets, then in braces its `width` in percent of the column, its `align` (left,
center or right) and an `offset` that moves it sideways.

![An apple: *elma*](images/starter-apple.svg){width=40 align=center}

![A house: *ev*](images/starter-house.svg){width=30 align=left offset=10}

A caption cannot hold square brackets, so a Turkish word in it is simply set in italics.

A recording is written the same way, with its file in `audio/`.

![A short chime](audio/starter-chime.mp3){width=60 align=center}

A `start` and an `end`, in seconds or minutes and seconds, play only that stretch of it, here the
chime's first note:

![The chime, its first note only](audio/starter-chime.mp3){width=50 align=center start=0 end=0.4}

A video from YouTube starts with an at sign instead of the exclamation mark, and can be clipped
the same way:

@[A short film](https://www.youtube.com/watch?v=aqz-KE-bpKQ){width=70 align=center start=0:10 end=1:00}

## Exercises

An exercise sits between a line reading `:::exercise` with its kind and a line of three colons.
On the page it starts unsolved and **Check exercises** at the end marks them all; the editor's
preview shows each one solved. The **Exercises** menu in the editor writes them from a form.

### Filling and ordering

:::exercise fill-blanks
prompt: Fill in the blanks. [Each word from the bank fills one gap; two are left over.]{no-bold}
content-direction: target
text: [Sabahları]{tl} [[drink]] [içerim, akşamları]{tl} [[read]] [okurum.]{tl}
- [drink] [çay]{tl}
- [read] [kitap]{tl}
- [ ] [ekmek]{tl}
- [ ] [elma]{tl}
explanation-correct: *In the mornings I drink tea, in the evenings I read.*
explanation-incorrect: One drinks [çay]{tl} *tea* and reads a [kitap]{tl} *book*.
:::

:::exercise order-sentences
prompt: Put the day in order. [The lines are shuffled on the page.]{no-bold}
- [1] [Sabah yedide kalkarım.]{tl}
- [2] [Kahvaltıda peynir ve zeytin yerim.]{tl}
- [3] [Sonra otobüsle işe giderim.]{tl}
- [4] [Akşam eve dönerim.]{tl}
explanation-correct: *I get up at seven in the morning. At breakfast I eat cheese and olives. Then I go to work by bus. In the evening I come home.*
:::

:::exercise construct-sentence
prompt: Build the sentence *This red apple is very sweet.*
- [1] [Bu]{tl}
- [2] [kırmızı]{tl}
- [3] [elma]{tl}
- [4] [çok]{tl}
- [5] [tatlı.]{tl}
explanation-correct: The adjective comes before its noun, and *is* needs no word of its own here.
:::

### Matching

:::exercise match-translations
prompt: Match each picture or word with its Turkish.
- ![An apple](images/starter-apple.svg) => [elma]{tl}
- ![A house](images/starter-house.svg) => [ev]{tl}
- water => [su]{tl}
- bread => [ekmek]{tl}
- tea => [çay]{tl}
:::

:::exercise match-opposites
prompt: Match each word with its opposite.
- [büyük]{tl} => [küçük]{tl}
- [sıcak]{tl} => [soğuk]{tl}
- [açık]{tl} => [kapalı]{tl}
- [erken]{tl} => [geç]{tl}
- [gelmek]{tl} => [gitmek]{tl}
explanation-correct: *Big and small, hot and cold, open and closed, early and late, to come and to go.*
:::

:::exercise match-definitions
prompt: Match each job with what it does. [The definitions are in easy Turkish.]{no-bold}
direction: definition-to-word
- [doktor]{tl} => [Hastaları iyileştirir.]{tl}
- [öğretmen]{tl} => [Okulda ders verir.]{tl}
- [aşçı]{tl} => [Lokantada yemek pişirir.]{tl}
- [postacı]{tl} => [Mektupları getirir.]{tl}
explanation-correct: *A doctor makes the sick well, a teacher teaches at school, a cook cooks in a restaurant, a postman brings the letters.*
:::

### Choosing

:::exercise yes-no
prompt: Answer yes or no.
- Does [evler]{tl} mean *houses*? => yes
- Does [kâr]{tl}, with the circumflex, mean *snow*? => no
- Are [ılık]{tl} and [ilik]{tl} the same word? => no
- Does a Turkish sentence usually end on its verb? => yes
explanation-correct: [kar]{tl} is *snow* and [kâr]{tl} *profit*; [ılık]{tl} is *lukewarm* and [ilik]{tl} *marrow*: the dot on the [i]{tl} makes it another letter.
:::

:::exercise true-false
prompt: True or false?
- Turkish has eight vowels, and most endings take their vowel from the last vowel of the word they are added to, so that one ending comes in two or four shapes: this is vowel harmony. => true
- [kitap]{tl} \=> [kitabı]{tl}: here the final [p]{tl} turns into [b]{tl} before an ending that starts with a vowel. => true
- The capital of [i]{tl} is [I]{tl}. => false
- [Ankara]{tl} is stressed on its last syllable. => false
explanation-incorrect: The capital of [i]{tl} is [İ]{tl}, with its dot, and [I]{tl} is the capital of the dotless [ı]{tl}. [Ankara]{tl} is stressed on its first syllable.
:::

:::exercise single-choice
prompt: Listen. Which of these is the sound you hear?
audio: audio/starter-chime.mp3 {width=50 align=center}
- [x] [zil sesi]{tl}
- [ ] [kuş sesi]{tl}
- [ ] [yağmur sesi]{tl}
explanation-correct: [zil sesi]{tl} is *the sound of a bell*; [kuş sesi]{tl} is birdsong and [yağmur sesi]{tl} the sound of rain.
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *house*?
image-answer: images/starter-house.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] [ev]{tl}
- [ ] [elma]{tl}
- [ ] [kitap]{tl}
explanation-correct: [ev]{tl} = *house*; [elma]{tl} is an apple, [kitap]{tl} a book. The chime stands in for the word said aloud.
:::

:::exercise incorrect-part
prompt: One part of this sentence is wrong. Which one?
- [ ] [Dün akşam]{tl}
- [ ] [arkadaşlarımla]{tl}
- [ ] [sinemaya]{tl}
- [x] [gideceğiz.]{tl}
explanation-correct: [Dün]{tl} *yesterday* asks for the past: [Dün akşam arkadaşlarımla sinemaya gittik.]{tl} *Yesterday evening we went to the cinema with my friends.*
explanation-incorrect: Look at the time: [dün]{tl} is *yesterday*, but [gideceğiz]{tl} means *we will go*.
:::

:::exercise choose-all
prompt: Which of these are fruits, like the one in the picture?
image: images/starter-apple.svg {width=25 align=center}
- [x] [elma]{tl}
- [ ] [ekmek]{tl}
- [x] [armut]{tl}
- [ ] [peynir]{tl}
- [x] [muz]{tl}
explanation-correct: [elma]{tl} *apple*, [armut]{tl} *pear* and [muz]{tl} *banana* are fruits; [ekmek]{tl} is *bread* and [peynir]{tl} *cheese*.
:::

:::exercise odd-one-out
prompt: Which word does not belong with the others?
- [ ] [pazartesi]{tl}
- [ ] [salı]{tl}
- [ ] [çarşamba]{tl}
- [x] [ocak]{tl}
- [ ] [cuma]{tl}
explanation-correct: [ocak]{tl} is *January*, a month; the others are days of the week: Monday, Tuesday, Wednesday and Friday.
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: At a tea house a customer says: [Merhaba! Bir çay ve bir simit lütfen.]{tl} Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then something to eat.
::::exercise single-choice
prompt: What does the customer want to drink?
- [x] [çay]{tl}
- [ ] [simit]{tl}
- [ ] [kitap]{tl}
explanation-correct: [Çay]{tl} is *tea*; [simit]{tl} is a ring of bread covered with sesame.
::::
::::exercise true-false
prompt: Now decide.
- [Simit]{tl} is something to eat. => true
- [Lütfen]{tl} means *thank you*. => false
explanation-correct: [Lütfen]{tl} is *please*; *thank you* is [teşekkürler]{tl}.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the words you have just read.
content-direction: target
text: [Merhaba! Bir [[drink]] ve bir [[food]] lütfen.]{tl}
- [drink] [çay]{tl}
- [food] [simit]{tl}
- [ ] [kitap]{tl}
explanation-correct: [Bir]{tl}, *one*, comes before each: [bir çay]{tl}, [bir simit]{tl}.
::::
:::

### Flashcards

A flashcard turns over when it is clicked. A vocabulary card, whose speaker button plays the
recording its `back-audio:` names (the chime, where the word said aloud would go) without turning
the card:

:::exercise flashcard
card-type: vocab
target: [yağmur]{tl}
transliteration: yāmur
meaning: rain
context: [Yarın yağmur yağacak.]{tl} *It will rain tomorrow.*
notes: The soft [ğ]{tl} is not said as a g: it makes the vowel before it long.
back-audio: audio/starter-chime.mp3
:::

A card of opposites:

:::exercise flashcard
card-type: opposites
target: [önce]{tl}
transliteration: ˈönce
opposite: [sonra]{tl}
opposite-transliteration: ˈsonra
notes: *before* and *after*. The word in front of either takes the ending [-den/-dan/-ten/-tan]{tl} *from*: [yemekten önce]{tl} *before the meal*, [yemekten sonra]{tl} *after the meal*.
:::

A free card, whose four fields can hold anything a note can: here a picture on the front, and on
the back a gloss, two lines and a recording. Each field can have its own size and shade.

:::exercise flashcard
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=40 align=center}
front-secondary: What is it called in Turkish?
back-primary: [elma]{tl} = *apple*
back-secondary: |
  [bir elma]{tl} *an apple*,⏎
  [iki elma]{tl} *two apples*: after a number the word stays singular.

  ![Replace this chime with the word in your voice](audio/starter-chime.mp3){width=70 align=center}
front-secondary-size: 90
front-secondary-shade: subdued
back-primary-size: 160
back-primary-shade: accent
:::

[İyi çalışmalar!]{tl} = *Happy studying!*
