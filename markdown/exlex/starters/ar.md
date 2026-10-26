---
title: New Arabic note
subtitle: a guided tour of what a note can hold
note: English prose, Arabic examples — keep what you need, delete the rest
lang: en
target: ar
---

> **This page is a demo of everything a note can contain**: text, Arabic words and blocks,
> dictionary entries, tables, footnotes, links, pictures, a recording, a video, formulas and
> every kind of exercise. The editor beside the preview shows how each one is written. Keep what
> you need and delete the rest.

## Writing the prose

The prose of this note is English, and plain Markdown works in it: **bold**, *italic* and
`inline code`. A word written in Arabic needs no mark at all, because the script is enough:
كِتَاب is recognised on its own and set right to left in an Arabic face. A word followed by `=`
and a meaning in italics is a gloss, كِتَاب = *book*, and every gloss goes into the page's
glossary.

> Three things to know about Arabic script before you start:
>
> - it runs from right to left, but its numbers run left to right, as ours do;
> - the letters of a word are joined, and most of them change shape with their place;
> - short vowels are small marks above and below the letters, and are usually left out.

### Lists

A list with a dash before each line; a line indented by two spaces sits one level down:

- a word you met today;
  - and its root, if it has one: مَكْتَبَة, from ك ت ب;
- the sentence you met it in;
- the question you still have about it.

A numbered list, for steps:

1. Find the three consonants of the root: كِتَاب → ك ت ب.
2. Look the root up in the dictionary.
3. Read the other words built on it, كَتَبَ, كَاتِب, مَكْتَبَة.

When every item starts with a **bold label**, the list is laid out as a list of terms. Here are
the four marks you meet first: the three short vowels, the *ḥarakāt*, and the sign for no vowel:

- **Fatha** a short *a*, a small stroke above the letter: بَ *ba*.
- **Kasra** a short *i*, the same stroke below it: بِ *bi*.
- **Damma** a short *u*, a little wāw above it: بُ *bu*.
- **Sukun** no vowel at all, a small circle: بْ *b*.

### Arrows, right and wrong, line breaks

An arrow is written → and shows where something leads: كَتَبَ *he wrote* → كَاتِب *writer*. A
hyphen and a greater-than sign make the same arrow: كَاتِب -> كُتَّاب, *writer* -> *writers*. A
cross marks a wrong form and a tick the right one: the feminine ending is tā marbūṭa, never a
plain hāʾ, so ✗مَكْتَبَه but ✅ مَكْتَبَة.

A paragraph runs on however you break its lines in the editor, and the line-break sign that the
editor's toolbar inserts starts a new line inside it:⏎
مَرْحَبًا *marḥaban*, hello!⏎
إِلَى اللِّقَاءِ *ilā l-liqāʾi*, see you!

## Arabic in the text

### Words and phrases

Arabic in bold stays Arabic: **الْعَرَبِيَّة** *al-ʿarabiyya*, the Arabic language. A stretch in
square brackets followed by `{tl}` (target language) is marked as Arabic explicitly, which is how
a stretch written left to right, such as a number in Western digits, stays inside an Arabic
phrase: [فِي الصَّفْحَةِ 12]{tl} *fī ṣ-ṣafḥati 12*, on page 12. An English word fits inside the
mark as well and keeps its place in the sentence; the PDF sets it in a typeface that has Latin
letters, which the Arabic one does not: [أَرْسَلْتُ مِلَفَّ PDF إِلَى الْمُعَلِّمِ]{tl}
*arsaltu milaffa PDF ilā l-muʿallimi*, I sent the PDF file to the teacher. The same mark takes a
tint: [صَبَاحُ الْخَيْرِ]{tl bg=rose} *ṣabāḥu l-ḫayri*, good morning.

### Vowel marks

Arabic is normally written with its consonants and long vowels only, كتاب, and a reader supplies
the rest. Texts for learners write the short vowels too, كِتَاب *kitāb*. Two more marks complete
the set: the shadda doubles a consonant, as in تُفَّاحَة *tuffāḥa*, an apple, and tanwin adds an
*-n* to an indefinite ending, as in كِتَابٌ *kitābun*, a book.

### A line on its own

A paragraph of nothing but Arabic letters and spaces, Arabic punctuation included, is set large
as a display line:

مَرْحَبًا، كَيْفَ حَالُكَ؟

*marḥaban, kayfa ḥāluka?* Hello, how are you? Its comma ، and question mark ؟ are the Arabic
ones, and that matters: a single English full stop or question mark would make it an ordinary
Arabic paragraph, like the next one.

### A paragraph of Arabic

A paragraph with no Latin letters in it becomes an Arabic paragraph, right to left, by itself:

هَٰذَا بَيْتِي. الْبَيْتُ صَغِيرٌ، لَٰكِنَّ الْحَدِيقَةَ كَبِيرَةٌ.

*hāḏā baytī. al-baytu ṣaġīrun, lākinna l-ḥadīqata kabīratun.* This is my house. The house is
small, but the garden is big.

A whole paragraph in square brackets with `{tl}` is an Arabic paragraph as well, and the braces
are where its options go, here a tint:

[وُلِدَ الْمُتَنَبِّي سَنَةَ 915]{tl bg=quote}

*wulida l-Mutanabbī sanata 915*, al-Mutanabbī was born in the year 915.

### Poems and dialogues

A block may span several lines: an opening bracket alone on a line, the lines of the block, then
the closing bracket with `{tl}` and its options, such as a tint. A line-break sign ends each line.
This is a verse by al-Mutanabbī:

[
الْخَيْلُ وَاللَّيْلُ وَالْبَيْدَاءُ تَعْرِفُنِي ⏎
وَالسَّيْفُ وَالرُّمْحُ وَالْقِرْطَاسُ وَالْقَلَمُ
]{tl bg=sand}

[*al-ḫaylu wa-l-laylu wa-l-baydāʾu taʿrifunī ⏎ wa-s-sayfu wa-r-rumḥu wa-l-qirṭāsu
wa-l-qalamu* ⏎ The horses, the night and the desert know me, ⏎ and the sword, the spear, the
paper and the pen.]{la align=center bg=lilac width=80}

The translation under the verse is a block of English set apart with `{la}`: it keeps prose
left to right inside a right-to-left page or card. `align=` sets its lines to a side and `bg=`
tints it, while `width=` and `offset=`, as percentages of the column, narrow the block and move
it, as they do a picture. A dialogue, with its transliteration and translation set a little in
from the left:

[
صَبَاحُ الْخَيْرِ يَا سَلْمَى! ⏎
صَبَاحُ النُّورِ يَا عُمَرُ! كَيْفَ حَالُكَ؟ ⏎
بِخَيْرٍ، وَالْحَمْدُ لِلَّهِ. وَأَنْتِ؟ ⏎
أَنَا أَيْضًا بِخَيْرٍ، شُكْرًا.
]{tl bg=sage}

[*ṣabāḥu l-ḫayri yā Salmā!* Good morning, Salmā! ⏎
*ṣabāḥu n-nūri yā ʿUmaru! kayfa ḥāluka?* Good morning, ʿUmar! How are you? ⏎
*bi-ḫayrin, wa-l-ḥamdu li-llāhi. wa-anti?* Fine, thank God. And you? ⏎
*anā ayḍan bi-ḫayrin, šukran.* I am fine too, thanks.]{la width=75 offset=10 bg=sand}

Two block options do not apply to Arabic. `font=` picks a language's second typeface, and Arabic
has none here (Persian has its Nastaliq). `vertical` sets Japanese and Chinese in columns from
top to bottom; Arabic is never set that way.

## Pronunciation and colour

A transliteration can ride on a word without being printed: a word in square brackets followed
by `{translit:…}` keeps it for the hover card and the glossary, [مَكْتَبَة]{translit:maktaba} =
*library*. A colour and a transliteration share the braces:
[مَكْتَب]{teal translit:maktab} = *desk, office*. Arabic has no reading field (that is for
Japanese kana): the transliteration is all an Arabic word needs.

Five colours have names. One root, five words, five colours: [كَتَبَ]{crimson} = *he wrote*,
[كِتَاب]{indigo} = *book*, [كَاتِب]{teal} = *writer*, [مَكْتَب]{violet} = *desk*,
[مَكْتَبَة]{amber} = *library*. Any other colour is a hex code:
[مَكْتُوب]{#2F6B8F} = *written; a letter*.

## كِتَاب | kitāb | from the root ك ت ب, *writing* | = *book*

A `##` heading that starts with an Arabic word and has fields split by `|` is a dictionary entry:
the headword, its transliteration, its origin, and after `=` the meaning, which is not printed but
goes into the glossary.

- **Plural** كُتُب *kutub*, a broken plural: the root stays and the vowels inside it change.
- **Example** [هَٰذَا كِتَابٌ جَدِيدٌ.]{tl} *hāḏā kitābun jadīdun*, this is a new book.
- **Family** كَتَبَ *kataba*, he wrote; كَاتِب *kātib*, writer; مَكْتَبَة *maktaba*, library.

## بَيْت | bayt | = *house, home*

The origin may be left out.

- **Plural** بُيُوت *buyūt*.
- **Example** [أَنَا فِي الْبَيْتِ.]{tl} *anā fī l-bayti*, I am at home.

## [قَلَم]{teal translit:qalam} | | from Greek *kálamos*, a reed pen | = *pen*

The headword may carry a colour, and its transliteration may ride in the same braces, leaving its
own field empty.

- **Example** [عِنْدِي قَلَمٌ أَزْرَقُ.]{tl} *ʿindī qalamun azraqu*, I have a blue pen.
- **In the verse** the last word of al-Mutanabbī's line: وَالْقَلَمُ *wa-l-qalamu*, and the pen.

## Tables

A table has a header row and a separator row. Colons in the separator align a column to the left,
the centre or the right, and a cell holding only `--` is left empty.

| Arabic | Transliteration | Meaning | Plural |
|:---|:---|:---:|---:|
| كِتَاب | kitāb | book | كُتُب |
| كَاتِب | kātib | writer | كُتَّاب |
| مَكْتَب | maktab | desk, office | مَكَاتِب |
| مَكْتَبَة | maktaba | library | مَكْتَبَات |
| كِتَابَة | kitāba | writing | -- |

## Footnotes

Arabic has no capital letters[^1]. A note can be written away from its place, as that one is,
with its text on a line of its own further down, or on the spot, inside the sentence.

Its short vowels are usually left unwritten^[Which is why a text for learners adds them:
[كَتَبَ]{translit:kataba} *he wrote* and [كُتُب]{translit:kutub} *books* look the same without
them, كتب.]. Hover over a note's number to read it; all the notes are listed again at the end of
the page.

[^1]: Nor does it have one alphabet for print and another for handwriting: print joins the
  letters of a word just as a pen does, and most letters change shape at the start, in the
  middle and at the end of a word.

## Links

A link to a web page: [a short film](https://www.youtube.com/watch?v=aqz-KE-bpKQ). A link to
another note, by its name: [another note](doc:My second Arabic note). With nothing between the
square brackets, the link shows the other note's title: [](doc:My second Arabic note). A link
points to a document's name, its title. A name that no document has yet is shown as a dangling
link, and it starts working as soon as you create a note with that title.

## Numbers and formulas

Most Arabic words grow from a root of three consonants. With 28 letters to choose from there are
[28^3 = 21\,952]{math} possible sequences of three, and this many if the three must all differ:

:::math
28 \times 27 \times 26 = 19\,656
:::

Only a fraction of them are real roots.

Arabic also has digits of its own, used beside ours:

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| ٠ | ١ | ٢ | ٣ | ٤ | ٥ | ٦ | ٧ | ٨ | ٩ |

A number made of them runs left to right, like ours, even inside a right-to-left sentence:

فِي الْعَرَبِيَّةِ ٢٨ حَرْفًا.

*fī l-ʿarabiyyati ṯamāniyatun wa-ʿišrūna ḥarfan*, there are 28 letters in Arabic.

## Pictures, recordings and video

A picture stands on a line of its own. Its caption goes in the square brackets, and the braces
after it give its width (a percentage of the column), its side and an offset:

![An apple, تُفَّاحَة](images/starter-apple.svg){width=40 align=center}

![A house, بَيْت](images/starter-house.svg){width=30 align=left offset=10}

A recording is written the same way, with its file under `audio/`:

![A short chime](audio/starter-chime.mp3){width=60 align=center}

`start=` and `end=` in the braces, in seconds or in minutes and seconds, play only a stretch of
it, here the chime's first note:

![The chime, its first note only](audio/starter-chime.mp3){width=50 align=center start=0 end=0.4}

A video from YouTube is written with `@` in front, and may be cut to a stretch as well:

@[A short film](https://www.youtube.com/watch?v=aqz-KE-bpKQ){width=70 align=center start=0:10 end=0:40}

## Exercises

Each exercise sits between a line `:::exercise` with its type and a closing `:::`. Answer them,
then press **Check exercises** at the end of the page; the preview in the editor shows them
already solved.

### Putting words in place

:::exercise fill-blanks
prompt: Complete the sentence “I went to the bookshop and bought a book”. Mind the case endings.
content-direction: target
text: ذَهَبْتُ إِلَى [[place]] وَاشْتَرَيْتُ [[object]].
- [ ] [كِتَابٌ]{tl}
- [place] [الْمَكْتَبَةِ]{tl}
- [ ] [الْمَكْتَبَةُ]{tl}
- [object] [كِتَابًا]{tl}
explanation-correct: After [إِلَى]{tl} a noun takes the genitive, [الْمَكْتَبَةِ]{translit:al-maktabati}; the object of a verb takes the accusative, [كِتَابًا]{translit:kitāban}. A [مَكْتَبَة]{translit:maktaba} is a bookshop as well as a library.
explanation-incorrect: The endings in *-u* and *-un* are nominative. Here one noun follows a preposition (genitive, *-i*) and the other is an object (accusative, *-an*).
:::

:::exercise order-sentences
prompt: Put the dialogue from “Poems and dialogues” back in order.
content-direction: target
- [1] [صَبَاحُ الْخَيْرِ يَا سَلْمَى!]{tl}
- [2] [صَبَاحُ النُّورِ يَا عُمَرُ! كَيْفَ حَالُكَ؟]{tl}
- [3] [بِخَيْرٍ، وَالْحَمْدُ لِلَّهِ. وَأَنْتِ؟]{tl}
- [4] [أَنَا أَيْضًا بِخَيْرٍ، شُكْرًا.]{tl}
explanation-correct: A greeting, the answer to it, the question back, and the last reply.
:::

:::exercise construct-sentence
prompt: Build the sentence that means [“I like to read a book in the garden.”]{no-bold}
- [1] [أُحِبُّ]{tl}
- [2] [أَنْ]{tl}
- [3] [أَقْرَأَ]{tl}
- [4] [كِتَابًا]{tl}
- [5] [فِي الْحَدِيقَةِ]{tl}
explanation-correct: [أُحِبُّ أَنْ أَقْرَأَ كِتَابًا فِي الْحَدِيقَةِ.]{tl} *uḥibbu an aqraʾa kitāban fī l-ḥadīqati.*
:::

### Matching

:::exercise match-translations
prompt: Match each picture or English word with its Arabic name.
- ![An apple](images/starter-apple.svg) => [تُفَّاحَة]{tl}
- ![A house](images/starter-house.svg) => [بَيْت]{tl}
- a pen => [قَلَم]{tl}
- the sun => [الشَّمْس]{tl}
- the moon => [الْقَمَر]{tl}
:::

:::exercise match-opposites
prompt: Match each adjective with its opposite.
- [كَبِير]{tl} => [صَغِير]{tl}
- [طَوِيل]{tl} => [قَصِير]{tl}
- [جَدِيد]{tl} => [قَدِيم]{tl}
- [حَارّ]{tl} => [بَارِد]{tl}
explanation-correct: *kabīr / ṣaġīr* big and small, *ṭawīl / qaṣīr* long and short, *jadīd / qadīm* new and old, *ḥārr / bārid* hot and cold.
:::

:::exercise match-definitions
prompt: Four words from the root ك ت ب. Match each definition with its word.
direction: definition-to-word
- [كَاتِب]{tl} => a person who writes
- [مَكْتَبَة]{tl} => a place where books are kept, lent or sold
- [مَكْتَب]{tl} => a desk, or the room where someone works
- [كِتَابَة]{tl} => the act of writing
:::

### Choosing

:::exercise yes-no
prompt: Play the recording (here only a chime, where yours would go), then answer each question.
audio: audio/starter-chime.mp3 {width=50 align=center}
- Is [بَيْت]{tl} a masculine noun? => yes
- Does [مَكْتَبَة]{tl} end in a tā marbūṭa? => yes
- Do Arabic letters have capital forms? => no
:::

:::exercise true-false
prompt: True or false?
- The Arabic alphabet has 28 letters. => true
- Arabic is written from left to right. => false
- [كِتَاب]{tl} \=> [كُتُب]{tl} is a broken plural: the root stays and the vowels inside it change. => true
- In [الشَّمْس]{translit:aš-šams}, the sun, the *l* of the article is not pronounced, because *š* is a “sun letter” and the article takes on its sound; in [الْقَمَر]{translit:al-qamar}, the moon, the *l* is kept, because *q* is a “moon letter”. => true
explanation-correct: The sun and the moon give their names to the two groups of letters.
:::

:::exercise single-choice
prompt: What is this called in Arabic?
image: images/starter-apple.svg {width=30 align=center}
- [ ] [بُرْتُقَالَة]{tl}
- [x] [تُفَّاحَة]{tl}
- [ ] [مَوْزَة]{tl}
explanation-correct: [تُفَّاحَة]{translit:tuffāḥa} is an apple; [بُرْتُقَالَة]{translit:burtuqāla} is an orange and [مَوْزَة]{translit:mawza} a banana.
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *house*?
image-answer: images/starter-house.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] [بَيْت]{tl}
- [ ] [قَلَم]{tl}
- [ ] [كِتَاب]{tl}
explanation-correct: [بَيْت]{translit:bayt} is a house; [قَلَم]{translit:qalam} is a pen and [كِتَاب]{translit:kitāb} a book. The chime stands in for the word said aloud.
:::

:::exercise incorrect-part
prompt: One part of this sentence has a mistake. Which one?
content-direction: target
- [ ] [ذَهَبَتْ سَلْمَى]{tl}
- [ ] [إِلَى السُّوقِ]{tl}
- [x] [مَعَ أَخُوهَا]{tl}
- [ ] [فِي الصَّبَاحِ.]{tl}
explanation-correct: After [مَعَ]{tl} a noun is genitive, and [أَخ]{tl} with a pronoun joined to it shows its case with a long vowel: [مَعَ أَخِيهَا]{translit:maʿa aḫīhā}, with her brother.
explanation-incorrect: Look at the noun after [مَعَ]{tl}: a preposition wants the genitive, [أَخِيهَا]{tl}.
:::

:::exercise choose-all
prompt: Which of these words are built on the root ك ت ب?
- [x] [كِتَاب]{tl}
- [ ] [قَلَم]{tl}
- [x] [مَكْتَب]{tl}
- [x] [كَاتِب]{tl}
- [ ] [بَيْت]{tl}
:::

:::exercise odd-one-out
prompt: Three of these words are colours. Which one is not?
- [ ] [أَحْمَر]{tl}
- [ ] [أَزْرَق]{tl}
- [x] [كَبِير]{tl}
- [ ] [أَخْضَر]{tl}
explanation-correct: [أَحْمَر]{translit:aḥmar} red, [أَزْرَق]{translit:azraq} blue and [أَخْضَر]{translit:aḫḍar} green share the pattern *afʿal*; [كَبِير]{translit:kabīr} means big.
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: In a café a customer says: [صَبَاحُ الْخَيْرِ! أُرِيدُ قَهْوَةً وَخُبْزًا، مِنْ فَضْلِكَ.]{tl} Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then something to eat.
::::exercise single-choice
prompt: What does the customer want to drink?
- [x] [قَهْوَة]{tl}
- [ ] [خُبْز]{tl}
- [ ] [كِتَاب]{tl}
explanation-correct: [قَهْوَة]{translit:qahwa} is coffee; [خُبْز]{translit:khubz} is bread.
::::
::::exercise true-false
prompt: Now decide.
- [خُبْز]{tl} is something to eat. => true
- [مِنْ فَضْلِكَ]{tl} means *thank you*. => false
explanation-correct: [مِنْ فَضْلِكَ]{translit:min faḍlika} is *please*; *thank you* is [شُكْرًا]{translit:shukran}.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the words you have just read. Mind the case endings.
content-direction: target
text: أُرِيدُ [[drink]] وَ[[food]]، مِنْ فَضْلِكَ.
- [drink] [قَهْوَةً]{tl}
- [food] [خُبْزًا]{tl}
- [ ] [قَهْوَةٌ]{tl}
explanation-correct: The thing wanted is the object of [أُرِيدُ]{tl}, so it takes the accusative ending *-an*: [قَهْوَةً]{translit:qahwatan}, [خُبْزًا]{translit:khubzan}.
::::
:::

### Flashcards

A flashcard turns over when you click it and is not scored. A vocabulary card, whose speaker button
plays the recording its `back-audio:` names (the chime, where the word said aloud would go) without
turning the card:

:::exercise flashcard
card-type: vocab
target: بَيْت
transliteration: bayt
meaning: a house, a home
context: [هَٰذَا بَيْتِي.]{tl} This is my house.
notes: plural بُيُوت *buyūt*
back-image: images/starter-house.svg
back-audio: audio/starter-chime.mp3
:::

A card of opposites:

:::exercise flashcard
card-type: opposites
target: كَبِير
transliteration: kabīr
opposite: صَغِير
opposite-transliteration: ṣaġīr
notes: big and small, both on the pattern *faʿīl*
:::

A free card, whose sides hold anything a note holds: a picture, a recording, a list.

:::exercise flashcard
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=35 align=center}
front-secondary: What is this called in Arabic?
back-primary: |
  **تُفَّاحَة** = *an apple*

  ![A short chime](audio/starter-chime.mp3){width=60 align=center}
back-secondary: |
  - [تُفَّاح]{translit:tuffāḥ} = *apples*, the fruit in general
  - [تُفَّاحَات]{translit:tuffāḥāt} = *apples* you can count
front-primary-size: 140
front-secondary-shade: accent
back-primary-size: 130
back-secondary-size: 90
back-secondary-shade: subdued
:::
