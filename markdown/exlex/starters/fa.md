---
title: New Persian note
subtitle: a guided tour of everything a note can hold
note: English prose with Persian examples: keep what you need, delete the rest
lang: en
target: fa
---

> **This page is a demo.** It shows everything a studio note can contain, each thing by using it:
> text and lists, Persian in every form the page knows, colours, vocabulary entries, tables,
> footnotes, links, formulas, pictures, a recording, a video and one exercise of every kind.
> Keep what you need and delete the rest; the source beside the preview shows how each part is
> written.

Persian inside English prose needs no mark: the script is enough, so سلام *salām*, hello, is found
on its own and set right to left. A mark is needed only when a Persian stretch holds Latin letters,
or when you want to style it.

## Text, lists and boxes

### Plain text

Text can be **bold**, *italic*, **bold with *italic* inside**, or `code` for a file name such as
`starter-apple.svg`. The arrow is the sign itself, and the editor has a button for it:
infinitive → past stem. A hyphen and a greater-than sign make the same arrow: رفتن -> رفت. The
return sign breaks a line inside a paragraph,⏎ like this, without
starting a new one.

A cross marks a wrong form and a tick the right one: ✗من می‌رود, ✅ من می‌روم, *I go*.

### Lists

A dash and a space start a bullet:

- one item per line;
- a second item;
  - an item indented by two spaces sits one level down (one level only);
- and a blank line ends the list.

A number and a full stop start a numbered list:

1. Read the new word aloud.
2. Write it once by hand.
3. Use it in a sentence of your own → now it is yours.

When every item starts with a bold label, the list lines its labels up:

- **Script** an alphabet of 32 letters, joined as in handwriting
- **Direction** right to left
- **Vowels** the short ones are usually left unwritten

### Boxes

A line that starts with `>` goes into a box, and a box holds anything a page can, lists included:

> **The six vowels.** Persian writes its three long vowels with letters and usually leaves the
> three short ones out.
>
> - long ā, i, u: آب *āb* water, سیب *sib* apple, روز *ruz* day
> - short a, e, o: شب *šab* night, کتاب *ketāb* book, گل *gol* flower
>
> Books for beginners add the short vowels as small marks: کِتاب.

## Persian in the text

### Words and marks

Persian words run straight into the English, and **bold** works on them too: **فارسی** *fārsi*,
Persian. A word followed by an equals sign and an italic meaning is a gloss: کتاب = *book*. The
equals sign turns grey by itself, and the studio gathers every gloss into the note's glossary.

The zero-width non-joiner keeps the present prefix می apart from its verb without a space:
می‌روم *mi-ravam*, I go[^1]. The editor's **ZWNJ** button types one at the cursor, and a
transliteration writes it as a hyphen.

[^1]: Persian calls it نیم‌فاصله *nim-fāsele*, a “half space”.
  Most Persian keyboard layouts type it with a key combination of its own.

Text in square brackets followed by {tl} is marked as Persian. The mark is needed when a Latin word
sits inside Persian, so that the whole stretch keeps its direction: [یک فایل PDF]{tl}, *a PDF file*.

A transliteration can travel with a word without being printed: [تند]{translit:tond}, *fast*,
looks like plain Persian here, and the reading view shows *tond* when you point at it. A colour and
a transliteration can share the braces: [کتابخانه]{teal translit:ketābxāne}, *library*. Persian has
no reading field; the kana mark is for Japanese notes.

### Whole Persian paragraphs

A paragraph with no Latin letters becomes a Persian paragraph by itself, set right to left:

امروز هوا خیلی خوب است. با دوستم به پارک می‌روم!

*The weather is lovely today. I am going to the park with my friend!*

A paragraph of nothing but Persian letters, spaces and Persian punctuation is a display line, set
larger:

قطره قطره جمع گردد، وانگهی دریا شود

*Drop by drop it gathers, and then it becomes a sea*: a proverb, *qatre qatre jam' gardad,
vāngahi daryā šavad*.

A Persian paragraph that holds a Latin word is marked as a whole, and `bg=` tints it with one of
quote, sand, rose, sage or lilac:

[امروز یک فایل PDF برای معلمم فرستادم.]{tl bg=sage}

*Today I sent my teacher a PDF file.*

A longer passage can span several lines: an opening square bracket on a line of its own, the
lines, then the closing bracket with its braces. The return sign keeps each line apart:

[
— سلام! حالت چطوره؟ ⏎
— خوبم، مرسی. تو چطوری؟ ⏎
— من هم خوبم.
]{tl bg=sand}

*A short exchange in spoken Persian: “Hi! How are you?” “Fine, thanks. And you?” “I’m fine too.”*

`font=nastaliq` sets a passage in Nastaliq, the flowing hand of Persian calligraphy and poetry,
here on the `bg=quote` tint:

[
بنی آدم اعضای یک پیکرند ⏎
که در آفرینش ز یک گوهرند
]{tl font=nastaliq bg=quote}

A Latin block, text in square brackets followed by {la}, sets English apart from the flow of a
right-to-left or vertical page. `width=` and `offset=` narrow it and move it as they do a
picture, `align=` sets its lines to a side inside it, and `bg=` tints it:

[*The children of Adam are limbs of one body, for in their creation they share one essence.*
— Saadi, *Golestan*, 13th century]{la align=center bg=sand width=80}

[A second Latin block, 70% of the column wide and shifted 10% to the right: room for a note in
English beside the Persian.]{la width=70 offset=10 bg=lilac}

Japanese and Chinese notes can also set a block vertically; Persian is always set horizontally, so
this page has none.

### Colours

Five colours have names, written in the braces after the word: crimson, indigo, teal, violet and
amber. Here each one paints a Persian colour word: [قرمز]{crimson} *qermez* red, [آبی]{indigo}
*ābi* blue, [سبز]{teal} *sabz* green, [بنفش]{violet} *banafš* violet and [قهوه‌ای]{amber}
*qahve-i* brown. Any other colour is a hash and six hex digits: [صورتی]{#C2185B} *surati*, pink.

## Vocabulary entries

A heading made of a Persian word and fields parted by bars is a vocabulary entry: the word, its
transliteration, where it comes from and, after an equals sign, its meaning. The meaning is not
printed; it puts the word into the glossary.

## کتاب | ketāb | from Arabic *kitāb* | = *book*

- **Plural** کتاب‌ها *ketāb-hā*, books
- **Example** [این کتاب را دوست دارم.]{tl} *I like this book.*
- **Compound** کتابخانه = *library*, a “book house”

## آب | āb | = *water*

The origin can be left out, as it is here.

- **Example** [یک لیوان آب، لطفاً.]{tl} *A glass of water, please.*
- **Idiom** آب خوردن *āb xordan*, to drink water: Persian “eats” it

## [خانه]{teal translit:xāne} | | Middle Persian *xānag* | = *house*

The word itself can be coloured, and its transliteration can ride in the colour's braces, leaving
its own field empty.

- **With the ezafe** خانهٔ من *xāne-ye man*, my house
- **Plural** خانه‌ها *xāne-hā*, houses

## Tables

Bars draw a table. The row under the header sets each column's alignment with colons (left
`:---`, centre `:---:`, right `---:`), and a cell holding only `--` is left empty.

| Infinitive | Present stem | Past stem | Meaning | Spoken *I …* |
|:---|:---:|:---:|:---|---:|
| رفتن *raftan* | رو *rav* | رفت *raft* | to go | می‌رم *mi-ram* |
| آمدن *āmadan* | آ *ā* | آمد *āmad* | to come | میام *mi-yām* |
| گفتن *goftan* | گو *gu* | گفت *goft* | to say | می‌گم *mi-gam* |
| دیدن *didan* | بین *bin* | دید *did* | to see | -- |

The past stem is the infinitive without its *-an*; the present stem has to be learnt by heart.
Speech shortens the present of the commonest verbs, but *I see* stays می‌بینم *mi-binam*, so its
cell is left empty.

## Notes and links

A footnote is a mark in square brackets with a caret, like the one after *I go* above; its text
goes on a line of its own that starts with the same mark and a colon, and lines indented by two
spaces carry it on. An inline note is written where it belongs, a caret and the text in square
brackets^[In everyday speech می‌روم shrinks to [می‌رم]{translit:mi-ram}.].

A link to the web: [a short film on YouTube](https://www.youtube.com/watch?v=aqz-KE-bpKQ).

A link to another note names that note: [another note](doc:My second Persian note). With nothing
in the square brackets it shows the name itself: [](doc:My second Persian note). A link points to
a name (the note's title), not to a file: while no note has that name it is shown as a dangling
link, and creating a note called *My second Persian note* makes it work.

## Mathematics

Persian has 32 letters, [28 + 4 = 32]{math}: the 28 of the Arabic alphabet and four of its own,
پ چ ژ گ, for the sounds p, č, ž and g.

A formula can also stand on its own lines, between `:::math` and `:::`. Ten new words a day for a
month:

:::math
\sum_{d=1}^{30} 10 = 10 \times 30 = 300 \text{ words}
:::

## Pictures, sound and video

A picture, a recording and a video each sit on a line of their own. The braces after them set the
width in percent of the column, the side, and a sideways shift. The editor's **Image**, **Audio**
and **Video** buttons put them in for you.

![An apple, سیب](images/starter-apple.svg){width=40 align=center}

![A small house, خانه](images/starter-house.svg){width=30 align=left offset=10}

![A short chime](audio/starter-chime.mp3){width=50 align=center}

`start=` and `end=`, in seconds or in minutes and seconds, cut a recording to a stretch, here the
chime's first note:

![The chime, its first note only](audio/starter-chime.mp3){width=50 align=center start=0 end=0.4}

A video is written like a picture with an at sign in front, and its start and end cut out the
stretch it plays:

@[A short film](https://www.youtube.com/watch?v=aqz-KE-bpKQ){width=70 align=center start=0:10 end=0:40}

## Exercises

Each exercise sits between a line `:::exercise` with its type and a closing `:::`. The reading view
starts them unsolved and **Check exercises** at the end of the page scores them all; the editor's
**Add exercise…** writes them for you.

### Filling and ordering

:::exercise fill-blanks
prompt: Complete the sentence: *I go to school by bus every day.*
content-direction: target
text: [من هر روز با [[how]] به مدرسه [[verb]].]{tl}
- [how] [اتوبوس]{tl}
- [verb] [می‌روم]{tl}
- [ ] [می‌رود]{tl}
- [ ] [کتاب]{tl}
explanation-correct: Right: با اتوبوس *bā otobus*, by bus, and می‌روم *mi-ravam*, I go.
explanation-incorrect: With من *man*, I, the verb ends in *-am*, می‌روم; and you go با اتوبوس, *by bus*.
:::

:::exercise order-sentences
prompt: Put the day in order.
content-direction: target
- [1] [صبح زود بیدار شدم.]{tl}
- [2] [صبحانه خوردم.]{tl}
- [3] [به مدرسه رفتم.]{tl}
- [4] [عصر به خانه برگشتم.]{tl}
explanation-correct: *I woke up early, had breakfast, went to school, and came home in the late afternoon.*
:::

:::exercise construct-sentence
prompt: Build the sentence *My friend's house is very big.*
answer-direction: rtl
- [1] [خانهٔ]{tl}
- [2] [دوستِ]{tl}
- [3] [من]{tl}
- [4] [خیلی]{tl}
- [5] [بزرگ]{tl}
- [6] [است]{tl}
explanation-correct: The ezafe links the words in a chain: خانهٔ دوستِ من *xāne-ye dust-e man*.
:::

### Matching

:::exercise match-translations
prompt: Drag each Persian word to its meaning.
- ![an apple](images/starter-apple.svg) => سیب
- ![a house](images/starter-house.svg) => خانه
- a book => کتاب
- water => آب
:::

:::exercise match-opposites
prompt: Match each word with its opposite.
- بزرگ => کوچک
- گرم => سرد
- روز => شب
- زیاد => کم
explanation-correct: *big, small; warm, cold; day, night; much, little.*
:::

:::exercise match-definitions
prompt: Match each place with its word.
direction: definition-to-word
- کتابخانه => where you borrow books
- نانوایی => where bread is baked and sold
- بیمارستان => where the sick are cared for
- فرودگاه => where planes take off and land
:::

### Choosing

:::exercise yes-no
prompt: Look at the picture and answer each question.
image: images/starter-house.svg {width=35 align=center}
- [آیا این یک خانه است؟]{tl} => yes
- [آیا این یک سیب است؟]{tl} => no
- [آیا این خانه پنجره دارد؟]{tl} => yes
:::

:::exercise true-false
prompt: True or false?
- Persian is written from right to left. => true
- The Persian alphabet has 26 letters. => false
- Persian took the Arabic alphabet and added four letters for sounds Arabic does not have, such as the p of پدر *pedar*, father, and the g of گل *gol*, flower. => true
- The past stem is the infinitive without *-an*: رفتن \=> رفت. => true
explanation-correct: Persian has 32 letters: 28 from Arabic and پ چ ژ گ.
:::

:::exercise single-choice
prompt: Listen. Which Persian word names this sound?
audio: audio/starter-chime.mp3 {width=50 align=center}
- [x] زنگ
- [ ] سیب
- [ ] کتاب
explanation-correct: زنگ *zang* is a bell and its ring; زنگ زدن *zang zadan* is to ring, and also to phone.
explanation-incorrect: Listen again: a bell is زنگ *zang*.
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *apple*?
image-answer: images/starter-apple.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] سیب
- [ ] نان
- [ ] آب
explanation-correct: سیب *sib* is an apple; نان *nān* is bread and آب *āb* water. The chime stands in for the word said aloud.
:::

:::exercise incorrect-part
prompt: One part of this sentence is wrong. Which one?⏎[[من دیروز به بازار می‌روم.]{tl}]{no-bold}
content-direction: target
- [ ] [من]{tl}
- [ ] [دیروز]{tl}
- [ ] [به بازار]{tl}
- [x] [می‌روم]{tl}
explanation-correct: Right: دیروز *diruz*, yesterday, asks for the past, رفتم *raftam*, I went.
explanation-incorrect: Look at دیروز *diruz*, yesterday: the verb must be in the past, رفتم.
:::

:::exercise choose-all
prompt: Choose every word that names a food.
- [x] سیب
- [ ] کتاب
- [x] نان
- [ ] آب
- [x] پنیر
explanation-correct: سیب *sib* apple, نان *nān* bread and پنیر *panir* cheese are foods; آب *āb* is water, though Persian says آب خوردن, to “eat” water.
:::

:::exercise odd-one-out
prompt: Which word does not belong with the others?
- [ ] قرمز
- [ ] آبی
- [x] کتاب
- [ ] سبز
explanation-correct: کتاب *ketāb* is a book; the others are colours.
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: In a tea house a customer says: [سلام! یک چای و یک نان، لطفاً.]{tl} Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then something to eat.
::::exercise single-choice
prompt: What does the customer want to drink?
- [x] چای
- [ ] نان
- [ ] کتاب
explanation-correct: چای *chāy* is tea; نان *nān* is bread.
::::
::::exercise true-false
prompt: Now decide.
- نان *nān* is something to eat. => true
- لطفاً *lotfan* means *thank you*. => false
explanation-correct: لطفاً *lotfan* is *please*; *thank you* is ممنون *mamnun*.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the words you have just read.
content-direction: target
text: [یک [[drink]] و یک [[food]]، لطفاً.]{tl}
- [drink] [چای]{tl}
- [food] [نان]{tl}
- [ ] [کتاب]{tl}
explanation-correct: یک *yek*, one, before each: یک چای، یک نان.
::::
:::

### Flashcards

A flashcard turns over when it is clicked and is never scored. The speaker button on the back of the
first one plays the recording its `back-audio:` names (the chime, where the word said aloud would
go) without turning it.

:::exercise flashcard
card-type: vocab
target: خانه
transliteration: xāne
meaning: house, home
context: [این خانه خیلی قشنگ است.]{tl}
notes: With the ezafe: خانهٔ من *xāne-ye man*, my house.
front-image: images/starter-house.svg
back-audio: audio/starter-chime.mp3
:::

:::exercise flashcard
card-type: opposites
target: بزرگ
transliteration: bozorg
opposite: کوچک
opposite-transliteration: kučak
notes: *big* and *small*
direction: reverse
:::

:::exercise flashcard
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=40 align=center}
front-secondary: What is it called, and how do you say *I eat an apple every day*?
back-primary: |
  **سیب** *sib*, an apple

  [
  این سیب خیلی شیرین است. ⏎
  من هر روز یک سیب می‌خورم.
  ]{tl bg=rose}
back-secondary: |
  ![At the chime, say both sentences aloud](audio/starter-chime.mp3){width=60 align=center}

  *This apple is very sweet. I eat an apple every day.*
front-secondary-size: 90
front-secondary-shade: subdued
back-secondary-shade: muted
:::
