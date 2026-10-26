---
title: New Hindi note
subtitle: a guided tour of everything a note can hold — हिंदी
note: a demo page: keep what you need and delete the rest
lang: en
target: hi
---

> **This page is a demo.** It shows everything a note can hold: ordinary Markdown, Hindi words
> and sentences, transliterations, colours, dictionary entries, tables, footnotes, links,
> formulas, pictures, a recording, a video and one exercise of every kind. The source in the
> editor shows how each thing is written. Keep what you need and delete the rest.

## Hindi on the page

Devanagari is recognised by its script, so Hindi needs no marking at all: type नमस्ते and it is
set in the Hindi font, ready to be coloured or given a transliteration. An equals sign and a
meaning in italics after a word make a gloss, which also goes into the note's glossary:
धन्यवाद = *thank you*. Bold works on Hindi just as it does on English: **बहुत अच्छा** =
*very good*.

A stretch in square brackets followed by `{tl}` is marked as Hindi explicitly. Hindi is found
without it, but the mark keeps a whole phrase, commas and question mark included, together as one
unit: [आप कैसे हैं?]{tl} means *how are you?* Hindi's own code, `{hi}`, works the same way:
[शुभ रात्रि]{hi}, *good night*. An English word fits inside the mark as well and keeps its place in
the sentence; the PDF sets it in a typeface that has Latin letters, which the Devanagari one does
not: [मैंने PDF भेजा]{tl}, *I sent the PDF*. A mark can also tint the words it holds:
[आइए, बैठिए]{tl bg=rose}, *come in, sit down*.

### Sentences, display lines and blocks

A paragraph with no Latin letters in it becomes a paragraph of Hindi by itself:

आज सोमवार है और मौसम बहुत अच्छा है। क्या आप मेरे साथ चाय पिएँगे?

That says *Today is Monday and the weather is lovely. Will you have tea with me?* Hindi ends a
sentence with the danda । rather than a full stop, and closes a couplet with the double danda ॥.
A line made only of Devanagari, spaces and dandas is a display line, set larger, like this
proverb:

जैसी करनी वैसी भरनी।

Several lines of Hindi make one block when they are marked like a single stretch, with the
opening bracket and the closing mark on lines of their own. A return sign at the end of a line
keeps the line break, and `bg=` tints the block. Here is a couplet by the poet Kabir, and a
greeting between two friends:

[
बुरा जो देखन मैं चला, बुरा न मिलिया कोय।⏎
जो दिल खोजा आपना, मुझसा बुरा न कोय॥
]{tl bg=sand}

[
नेहा: नमस्ते! आप कैसे हैं?⏎
अमित: मैं ठीक हूँ, धन्यवाद। और आप?⏎
नेहा: मैं भी ठीक हूँ।
]{tl bg=sage}

The tints are `quote`, `sand`, `rose`, `sage` and `lilac`. Two more block options do not apply
to Hindi. `font=` picks a language's alternative typeface, and the toolbox has none for Hindi;
`vertical` sets Japanese or Chinese in columns, and Hindi is always written in lines, from left to
right.

## Saying it: transliteration

A mark with `translit:` gives a word its transliteration, shown when the pointer rests on it:
[नमस्ते]{translit:namaste}. The transliteration writes what is said, not each letter: in
[समझना]{translit:samajhnā} = *to understand*, the *a* that झ carries in writing is not said. A
moon with a dot over a letter nasalises its vowel, [हूँ]{translit:hūṁ} = *am*, and a dot under a
letter changes its sound, [ज़रूर]{translit:zarūr} = *of course*. A colour and a transliteration
can share the braces: [हिंदी]{teal translit:hindī}. Hindi has no separate reading field (that is
for Japanese kana), so the transliteration is all a word needs.

> **Three spelling habits to notice**
>
> - The dot under a letter, the nukta, mostly marks a sound that came with words from Persian,
>   Arabic or English: ज is *j* but ज़ is *z*, and फ is *ph* but फ़ is *f*. Under ड and ढ it
>   marks sounds of Hindi's own, as in लड़का *laṛkā*, *boy*.
> - The dot above a letter is said as the nasal of the consonant after it, as in हिंदी *hindī*
>   and ठंडा *ṭhaṇḍā*, and elsewhere it nasalises the vowel, as in नहीं *nahīṁ*. The moon with a
>   dot, as in हूँ *hūṁ*, always nasalises.
> - Some words are printed both ways, like हिंदी and हिन्दी: keep whichever your source uses.

## Colours

Five colours have names: [लाल]{crimson} = *red*, [नीला]{indigo} = *blue*, [हरा]{teal} = *green*,
[बैंगनी]{violet} = *purple* and [पीला]{amber} = *yellow*. Any other colour is written as a hex
code: [गुलाबी]{#C2185B} = *pink*.

## Plain Markdown

The prose around the Hindi takes ordinary Markdown: **bold**, *italic*, and `code` for anything
typed literally, like the line `target: hi` at the top of this note, which says that the
language being learned is Hindi.

Hindi has more than one word for *you*:⏎ तुम *tum*, for friends and children,⏎ आप *āp*, for
elders, strangers and anyone you address with respect.

A few things to know from the start; an item indented by two spaces sits one level down:

- Hindi is written in Devanagari, from left to right.
- Every noun is masculine or feminine, and the words around it agree.
  - An adjective in -ā shows it: अच्छा लड़का, *a good boy*, but अच्छी लड़की, *a good girl*.
- The verb usually comes last: मैं चाय पीता हूँ = *I drink tea*.

Three verbs worth learning first:

1. होना *honā*, to be
2. करना *karnā*, to do
3. जाना *jānā*, to go

An arrow shows a change: लड़का → लड़के, *boy* → *boys*. A hyphen and a greater-than sign make the
same arrow: कमरा -> कमरे, *room* -> *rooms*. A cross marks a wrong form and a tick the
right one: ✗मैं जाता है → ✅ मैं जाता हूँ, *I go*, because with मैं the helping verb is हूँ.

## Dictionary entries

A heading with the word, its transliteration, where it comes from and its meaning after an equals
sign, separated by upright bars, becomes a dictionary entry with the word set large. The meaning
is printed nowhere: it goes into the glossary. The origin may be left out, and the word may carry
a colour and its transliteration in its own braces, with the transliteration slot left empty. A
list whose items start with a bold label is set as a list of definitions.

## किताब | kitāb | f. · from Arabic *kitāb* | = *book*

- **Gender** feminine, so an adjective in -ā changes to -ī: अच्छी किताब = *a good book*
- **Plural** किताबें *kitābeṁ*
- **Example** मेरी किताब मेज़ पर है। — *My book is on the table.*

## पानी | pānī | = *water*

- **Gender** masculine, although it ends in -ī
- **Example** एक गिलास पानी दीजिए। — *A glass of water, please.*

## [घर]{teal translit:ghar} | | m. · from Sanskrit *griha* | = *house, home*

- **Gender** masculine
- **Phrases** घर पर = *at home*, घर जाना = *to go home*
- **Example** मेरा घर छोटा है, पर सुंदर है। — *My house is small, but beautiful.*

## Tables

A table has a header row and a line of dashes under it; a colon on the left, on both sides or on
the right of the dashes aligns that column, and a cell holding only `--` is left empty.

| Singular | Meaning | Plural | Change |
|:---|:---:|:---|---:|
| लड़का *laṛkā* | boy (m.) | लड़के *laṛke* | -ā → -e |
| लड़की *laṛkī* | girl (f.) | लड़कियाँ *laṛkiyāṁ* | -ī → -iyāṁ |
| किताब *kitāb* | book (f.) | किताबें *kitābeṁ* | + -eṁ |
| घर *ghar* | house (m.) | घर *ghar* | -- |

## Footnotes and links

A footnote is a small mark in the text with its note written on a line of its own, anywhere in
the note; a short note can also be written right where it belongs. Hindi has taken many words
from English^[Such as [स्टेशन]{tl} *sṭeśan*, from English *station*.] and, long before that, from
Persian and Arabic[^1].

[^1]: Among them किताब, *book*, and दोस्त, *friend*. A dot under a letter, as in ज़रूर, often
  shows a word that came this way.

A link to a web page: [a short animated film](https://www.youtube.com/watch?v=aqz-KE-bpKQ).

A link can also point to another of your notes by its name:
[another note](doc:My second Hindi note). With nothing in its brackets it shows that note's
title: [](doc:My second Hindi note). A link names a note by its title; while no note has that
title the link is shown as a dangling link, and creating a note called *My second Hindi note*
makes it work.

## Setting English apart

A Latin block sets a paragraph of English apart: `width=` and `offset=` narrow it and move it
as they do a picture, `align=` sets its lines to a side, and `bg=` tints it. It is made for
right-to-left and vertical pages, where English needs a box of its own; in a Hindi note it keeps
a translation apart from the text. Kabir's couplet above means:

[I went looking for the wicked and found no one wicked; when I searched my own heart,
I found no one more wicked than me.]{la align=center bg=sand width=80}

And the proverb:

[As you sow, so shall you reap: word for word,
*as the doing, so the paying*.]{la width=70 offset=10}

## Numbers and formulas

Hindi has digits of its own, ० १ २ ३ ४ ५ ६ ७ ८ ९, though most texts today use 0 to 9. A formula
on its own line is written in LaTeX:

:::math
f = \frac{n}{N} \times 1000
:::

Here *n* is how many times a word appears in a text of *N* words, and *f* how often it comes in
every thousand. A formula can also sit inside a sentence: if है appears 60 times in a text of
2000 words, [f = \frac{60}{2000} \times 1000 = 30]{math}.

## Pictures, sound and video

A picture stands on a line of its own, with its caption in the square brackets and its width,
side and offset in the braces after it:

![An apple — सेब, seb](images/starter-apple.svg){width=40 align=center}

![A house — घर, ghar](images/starter-house.svg){width=30 align=left offset=10}

A recording is written the same way, with its file under `audio/`:

![A short chime](audio/starter-chime.mp3){width=50 align=center}

`start=` and `end=` in the braces, in seconds or in minutes and seconds, play only a stretch of
it, here the chime's first note:

![The chime, its first note only](audio/starter-chime.mp3){width=50 align=center start=0 end=0.4}

A video from YouTube starts with `@` and can be cut to the stretch you want:

@[A short animated film](https://www.youtube.com/watch?v=aqz-KE-bpKQ){width=70 align=center start=0:10 end=0:40}

## Exercises

An exercise stands between a line `:::exercise` with its kind and a line `:::`, and
**Add exercise…** in the editor's **Exercises** menu writes one for you with a form. The page
shows the exercises unsolved, and **Check exercises** at the end marks them.

### Filling in and putting in order

:::exercise fill-blanks
prompt: Complete the sentence with the right form of *to be*.
content-direction: target
text: [मैं छात्र [[am]] और मेरी बहन डॉक्टर [[is]]।]{tl}
- [am] हूँ
- [is] है
- [ ] हैं
- [ ] हो
explanation-correct: हूँ goes with मैं, and है with one person spoken about.
explanation-incorrect: Match each verb to its subject: मैं … हूँ, but बहन … है.
:::

:::exercise order-sentences
prompt: Put the lines of this conversation at a fruit stall in order.
- [1] भैया, ये सेब कितने के हैं?
- [2] सौ रुपये किलो।
- [3] ठीक है, एक किलो दे दीजिए।
- [4] ये लीजिए। और कुछ?
- [5] बस, धन्यवाद!
:::

:::exercise construct-sentence
prompt: Build the Hindi for *Will you have tea with me?*
- [1] क्या
- [2] आप
- [3] मेरे साथ
- [4] चाय
- [5] पिएँगे?
explanation-correct: क्या at the start makes a yes-or-no question, and the verb comes last.
:::

### Matching

:::exercise match-translations
prompt: Match each meaning, or picture, with its Hindi word.
direction: translation-to-target
- पानी => water
- चाय => tea
- घर => house
- सेब => ![an apple](images/starter-apple.svg)
:::

:::exercise match-opposites
prompt: Match each word with its opposite.
- बड़ा => छोटा
- गरम => ठंडा
- दिन => रात
- अंदर => बाहर
- आसान => मुश्किल
:::

:::exercise match-definitions
prompt: Match each word with what it means.
direction: word-to-definition
- रसोई => the room where food is cooked
- डाकिया => the person who brings the post
- छाता => what keeps the rain off your head
- तकिया => what your head rests on in bed
:::

### Choosing

:::exercise yes-no
prompt: Listen to the recording, then answer each question.
audio: audio/starter-chime.mp3
- Is it the sound of a chime, like a small bell? => yes
- Is it a dog barking? => no
- Is it somebody saying नमस्ते? => no
explanation-correct: A small bell is a घंटी *ghaṇṭī*, and its sound is घंटी की आवाज़.
:::

:::exercise true-false
prompt: Read the text, then decide whether each statement is true or false.⏎[नेहा दिल्ली में रहती है। वह हर सुबह चाय पीती है और फिर बस से दफ़्तर जाती है।]{no-bold}
- Neha lives in Delhi. => true
- Neha drinks coffee in the morning. => false
- The verbs end in -ī (पीता \=> पीती) because their subject, नेहा, is a woman: in sentences like these a Hindi verb agrees with the gender of its subject. => true
- Neha walks to her office. => false
:::

:::exercise single-choice
prompt: What is in the picture?
image: images/starter-house.svg {width=30 align=center}
- [x] घर
- [ ] सेब
- [ ] किताब
explanation-correct: Yes: घर *ghar* is a house, and also a home.
explanation-incorrect: Not quite: this is a घर *ghar*, a house.
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *apple*?
image-answer: images/starter-apple.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] सेब
- [ ] पानी
- [ ] चाय
explanation-correct: सेब *seb* is an apple; पानी *pānī* is water and चाय *cāy* tea. The chime stands in for the word said aloud.
:::

:::exercise incorrect-part
prompt: This should say *The girl goes to school*, but one word is in the wrong form. Which one?
- [ ] लड़की
- [ ] स्कूल
- [x] जाता
- [ ] है।
explanation-correct: लड़की is feminine, so the verb is जाती: लड़की स्कूल जाती है।
:::

:::exercise choose-all
prompt: Choose every correct plural.
- [x] लड़का → लड़के
- [x] किताब → किताबें
- [ ] कमरा → कमरें
- [x] घर → घर
- [ ] लड़की → लड़कीयाँ
explanation-correct: Masculine -ā becomes -e (कमरा → कमरे); feminine -ī becomes -iyāṁ, with a short i (लड़की → लड़कियाँ).
:::

:::exercise odd-one-out
prompt: Which word is not a fruit?
- [ ] सेब
- [ ] आम
- [ ] केला
- [x] कुर्सी
explanation-correct: सेब, आम and केला are an apple, a mango and a banana; a कुर्सी is a chair.
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: At a stall a customer says: [नमस्ते! एक चाय और एक समोसा, कृपया।]{tl} Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then something to eat.
::::exercise single-choice
prompt: What does the customer want to drink?
- [x] चाय
- [ ] समोसा
- [ ] किताब
explanation-correct: चाय *chāy* is tea; समोसा *samosā* is a samosa.
::::
::::exercise true-false
prompt: Now decide.
- समोसा *samosā* is something to eat. => true
- कृपया *kripayā* means *thank you*. => false
explanation-correct: कृपया *kripayā* is *please*; *thank you* is धन्यवाद *dhanyavād*.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the words you have just read.
content-direction: target
text: [नमस्ते! एक [[drink]] और एक [[food]], कृपया।]{tl}
- [drink] चाय
- [food] समोसा
- [ ] किताब
explanation-correct: एक *ek*, one, before each: एक चाय, एक समोसा.
::::
:::

### Flashcards

A flashcard turns over when it is clicked, and it is never marked. The speaker button on the back of
the first one plays the recording its `back-audio:` names (the chime, where the word said aloud
would go) without turning it.

:::exercise flashcard
card-type: vocab
target: चाय
transliteration: cāy
meaning: tea
context: एक कप चाय पीजिए। — *Have a cup of tea.*
notes: feminine: अच्छी चाय, *good tea*
back-audio: audio/starter-chime.mp3
:::

:::exercise flashcard
card-type: opposites
target: गरम
transliteration: garam
opposite: ठंडा
opposite-transliteration: ṭhaṇḍā
notes: गरम never changes; ठंडा becomes ठंडी with a feminine noun: ठंडी चाय, *cold tea*.
:::

:::exercise flashcard
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=40 align=center}
front-secondary: What is it called in Hindi? Say it aloud, then turn the card.
back-primary: सेब
back-secondary: |
  **seb**, masculine; the plural is the same word.

  ![A chime, until you record सेब yourself](audio/starter-chime.mp3){width=70 align=center}

  - यह सेब लाल है। — *This apple is red.*
  - ये दो सेब हैं। — *These are two apples.*
front-secondary-size: 90
front-secondary-shade: subdued
back-primary-size: 160
back-primary-shade: accent
:::

That is the whole tour. Delete what you do not need and start writing: शुभकामनाएँ = *best wishes*!
