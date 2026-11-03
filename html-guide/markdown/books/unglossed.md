---
title: Reading a book nobody has glossed
linkTitle: Reading unglossed chunks
weight: 11
description: The dictionary switch and its panel — the dictionary, the machine's reading, sentences somebody translated, Load more — and the sources sidebar and Ask LLM, which put them into a gloss; what the verb draft does in each language, and why a gloss is not a fluent translation.
---

Between pasting a text in and finishing its glosses lie weeks, and for
those weeks every unglossed chunk is a phrase you cannot get past. Three
things help, all on this machine, and none of them is a gloss:

- **a dictionary** gives you the *words*: what each one can mean, and how the
  word on the page was reached from the headword it is a form of;
- **a translation model** reads *the sentence* your chunk sits in, and marks
  the part of its reading that seems to be your chunk's;
- **sentences somebody has already translated** — a real sentence, written
  by one person and translated by another, sharing the rare words of your
  chunk — settle which of the senses on the list is the live one.

They are installed once, with buttons, on the **reading help** page
(Settings, `/settings/reading-help/`), which **Get a dictionary for this language →**, in the
⚙ panel's **Looking a word up**, opens; the Lookup and
languages section of this guide goes through it. A reader with none of them
is exactly the reader it always was.

## The dictionary switch

Once anything is installed for the book's language, the header shows
**dictionary**. It is **off** until you turn it on — then it is remembered,
for this book, in this browser — and its tooltip says what it will do: *look
the words up, show a sentence somebody translated, translate the line —
where nothing is glossed*, or as much of that as is installed. With it off,
nothing is fetched, nothing is translated, and the page costs exactly what it
did before.

With it on, **click any chunk that has no vocabulary line** — in any mode,
hover or not — and its cloud opens with the panel in it. (In hover mode,
pointing is enough.) A chunk somebody has glossed is left alone: the panel
exists for the chunk nobody has got to yet, and a finished edition looks
exactly as it did.

**English is explained in English.** Every dictionary here is the English
Wiktionary's, which explains the words of every language in English — for
Persian a translation, but for English itself a *definition*, in the very
language you are learning. So a book in English has two more switches, in the
⚙ panel's **Looking a word up**: **Show the dictionary's definitions** (off until
turned on) shows Wiktionary's definitions under
each word, with their labels (*transitive*, *countable*, *slang*), the
first three at once and the rest behind **N more definitions**; and, where a
translation model into the language of your glosses is installed, **Translate
the definitions into *Italian*** (named after that language) puts each definition
into it, underneath — a machine's reading of a definition, labelled so. Off, an entry
still gives the headword, how it is said, its part of speech, how it was
reached and a verb's forms.

## The panel

The panel is tinted and ruled off from the gloss, and holds up to three
blocks, each headed with what it is and ending with where it came from:

**dictionary — not a gloss.** Each word of the chunk, and under it every
entry the dictionary has: the headword and its romanisation, the part of
speech, and the senses — the likely ones first, obsolete and rare ones last.
When the word on the page is not the headword, a line says how it was
reached (*found without the marks and the case*, for instance), which is
the line that teaches. A verb carries a line of its
principal parts. A word it cannot find says what it tried: *not found
(tried …)*. At the foot, the source and its licence.

**a machine's reading of the sentence — not a gloss.** The whole sentence
the chunk sits in, translated by the model on this machine. A chunk is a
fragment by construction, and a fragment translated alone comes back as
one, so it is the sentence that is read; the words of the reading that seem
to be **your chunk's** are marked in it — in colour and bold where the
dictionary accounts for at least half of the chunk's words, with a dotted
underline where it accounts for fewer — and a line under it says what
the mark stands on, `this chunk is likely: “…” — مثل → parable · ایران → Iran`,
or *part of this chunk is likely*, or that nothing matched and nothing is
marked. The mark is a guess from meaning, never from
position: word order is exactly what a translation changes. Where the chunk
*is* the whole sentence, there is nothing to mark, and the heading is just
*a machine's reading — not a gloss*. The model and its engine are named at
the foot. There is no button to use it as a gloss, and there will not be one.

**a sentence somebody translated — not this one.** Sentences from a
translated corpus (Tatoeba) that share the rare words of your chunk: both
sides, the shared words marked on both, and *shares …* naming them.
**Load more** fetches five more, for as long as there are more. It is not
your line and never pretends to be, which is exactly its use.

A panel with nothing to say says so: *the dictionary has nothing for these
words*.

**It gets ahead of you.** While you are not asking anything, the reader
looks up the unglossed chunks of the next ten subparagraphs, and reads their
sentences with the model, so that the panel opens already filled. It waits
for a moment's quiet after your last scroll or keypress, and stands down the
moment you open a cloud yourself — and it does nothing at all while the
switch is off.

## The sources sidebar: taking it up into a gloss

The panel is for reading; nothing in it writes. Where the gloss is actually
written — the chunk sheet ([Writing a chunk](doc:Writing a chunk)) — the same
sources come with you: **⊕ sources** in the sheet's head opens a column on
the left of the fields (the picture on that page shows it). The fields do
not move; the sheet grows to the left. On a narrow screen the column goes
under the fields instead, and the sheet scrolls down to it. The column
stays open until you close it, remembered for this book.

It is offered on every chunk that has gloss slots, written or not —
correcting a line is as much of the work as writing one — and whether or
not the **dictionary** switch is on. Its four blocks, in the panel's order:

| Block | Its buttons |
|---|---|
| **dictionary** | per entry: **romanisation →** (the romanisation of the word as the chunk has it, into the transliteration), **\dw → vocabulary** (the whole entry, `\dw{word}{rom} sense`, onto the vocabulary line), **meaning →** (the sense into the meaning) |
| **a machine's reading** | **the marked words → meaning**, **the whole sentence → meaning** (just **meaning →** where nothing is marked) |
| **sentences somebody translated** | **its meaning →**, per sentence |
| **external chatbot** | **Ask LLM** and **Use translation** (below) |

Every button **appends** — a vocabulary line is built up entry by entry — and
leaves the cursor at the end of the field. **It writes into a box, never
into the book**: nothing is saved until you press **save chunk**, down the
same route, with the same checks, as anything you type.

**A verb goes in as `\vb`.** Where the dictionary's entry is a verb the
language knows how to conjugate, the row shows the line of its forms, and
the button is **\vb → vocabulary**: the verb with its principal parts, in
this language's order. Where the book has already glossed the same verb, the
row first offers **\vb as this book glosses it →**, so the twenty-first
occurrence matches the twenty before it; the dictionary's own is then
**the dictionary's \vb → vocabulary**, and is not drawn at all when the two
are the same. A `\vb` the dictionary could not complete still goes in, with
its gaps listed under the row, one to a line, headed *to fill in:* — and its
button has a dashed border. Where the verb is another verb's than the
headword (German's *stand … auf* going in as *aufstehen*, a reflexive going
in as *sich freuen*), the row says so with an arrow.

**A verb of two words.** Persian's compound verbs (*labxand zadan*, to
smile), Turkish's, Hindi's conjunct verbs and French's verbal locutions are
one vocabulary entry, not two. For them the row has a second button,
**compound verb → vocabulary** (**conjunct verb** in Hindi, **verbal
locution** in French), that puts the pair in whole; its tooltip says what it
will write.

What is always left to you: the meaning is the dictionary's *first* sense,
not necessarily the one your sentence wants; where two auxiliaries are
possible, both are printed — strike the one the sentence does not use;
every hit that could be a verb gets a `\vb`, the unlikely ones included.
A block with nothing to offer says so in its own words (*the dictionary has
nothing for these words*, *no translation model for this pair*).

## What the verb draft does in each language {#what-the-verb-draft-does-in-each-language}

A verb's draft is built from the dictionary's conjugation table, so it is as
good as that table, and the tables of Parseh's own languages have their own
gaps. It is always a **draft for you to correct**, and where it could not fill
a slot the button says which. In a video, where the phrase holds a form that
is none of the three a `\vb` prints, the draft also names that form after the
entry, outside it — `; here \pw{vint} \textit{vẽ}` — and what to call it
(*past historic*, say) is yours to type. What each language's draft proposes,
and what is left to you:

- **Persian.** The infinitive and the two stems, each with its sound. Where
  the book already has a `\vb` for the same infinitive, the book's own is
  offered first. The stems are Wiktionary's, from the literary Iranian table
  where there is one, and need not be the book's — it has *dah* for دادن
  where the series writes *deh* — so check them against the conventions, and
  trim the meaning to the one sense the text uses. For a compound the
  dictionary knows (فکر کردن and عوض کردن — not every one it should) the
  draft is the light verb's `\vb` with its meaning already empty, and the
  **compound verb** button puts the whole pair in, saying in so many words that
  لبخند زدن is one verb written in two words and not two entries:
  `\vb{زدن}{zadan}{زن}{zan}{زد}{zad}{}\bw{لبخند}{labxand}{to smile}`, the `\bw`
  run straight onto the `\vb` with no `; ` between them, which is what makes the
  pair one entry in the line (in a video, with the colloquial present in the
  light verb's parenthesis where there is one). The plain `\vb` button stays
  beside it — the light
  verb alone, still drawn unfinished — and the row goes on naming the `\bw` under
  *to fill in*, so you see what the entry is about to become before you press.
  Where the dictionary gave no meaning the compound still goes in, with that
  slot empty and the button dashed; where it does not know the compound at all
  (گمان کردن or معلوم شدن) the light verb comes with its own meaning, and
  emptying it is yours. A preverb is hyphenated only where the dictionary marks
  one (برگشتن, برداشتن, درآوردن, فراگرفتن and a few more): برخاستن comes as
  *barxāstan*, and the hyphen is yours to put in. A preverb verb the text writes
  apart (بر می‌گردم, در آورده) is offered whole, as برگشتن and درآوردن. In a
  video the draft adds the colloquial present wherever the dictionary's
  Tehrani table spells it differently — 18 verbs, among them *mi-gam*,
  *mi-ram*, *mi-šam* and *mi-dunam* — and you take it out where the speaker
  does not say it.
- **Arabic.** The vowelled perfect with its form, the imperfect, a masdar and a
  governed preposition where the dictionary has one, each transliteration
  respelt in the book's scheme (the dictionary writes `ʔ ʕ ḵ ḡ` and an initial
  hamza). Where the dictionary lists several masdars — it does for about one
  verb in six — the draft has the first, which is often the one for another
  sense (`صِلَة` where *to arrive* wants `وُصُول`); the meaning and the
  preposition are those of the sense the dictionary gives first, and its meaning
  runs to a line of synonyms; and a hit reached through an unvowelled word may be
  the wrong verb altogether. A masdar the dictionary does not know, which it does
  not tell apart from a verb that has none, goes in blank, and the button says
  so. In a video the draft comes without the vowel marks, as a video's line is
  written; the transliterations keep the vowels.
- **Italian.** The entry for a verb it recognises, the auxiliary and an
  irregular *passato remoto* included, and — for a form the dictionary only
  knows as a compound (`alzandosi`, `dimmelo`, `farlo`) — the entry of the verb
  it is a form of. The meaning is the dictionary's first sense cut to one
  equivalent, which is often not the one the chunk needs (`dovere` comes as
  *to owe*). Where a reflexive pronoun stands before the word and the dictionary
  lists the two together as a form of the pronominal verb (`si alzò`, `mi alzo`,
  `me ne vado`, `si è alzato`), it proposes the pronominal verb (`alzarsi`,
  `andarsene`) — but with `si` it cannot know a reflexive from an impersonal or
  passive one (`si dice`, `si vendono case` are `dire`, `vendere`), and the
  button says so. The auxiliary is the one the dictionary's head line gives, and
  that is sometimes wider than usage: `sapere` and `usare` come with
  *avere/essere*, the *essere* for a sense the text will hardly have (to taste
  of, to be in fashion) — trim it to what the chunk uses.
- **Japanese.** The three forms with the rōmaji the dictionary gives them (the
  -te form is its past with `た` made `て`: `書いた` kaita → `書いて` kaite), the
  class it records, checked against those forms — so `帰る`, which looks ichidan,
  comes out godan, as its stem `帰り` says — `tr.` or `intr.` only where it
  records one (about half the verbs; the rest are left without, not guessed),
  and `hon.` or `hum.` where the sense it prints is tagged so. A verb the chunk
  writes in another of the dictionary's spellings is proposed in the chunk's:
  `飲んだ` gives `飲む`, though the dictionary files it under `のむ`. The meaning
  is the dictionary's first sense, which is often a definition rather than the
  one equivalent wanted, or not the sense of the passage; an auxiliary after
  the -te form (`いる` in `書いている`, `しまう`, `みる`) is proposed as a verb of its
  own, and is glossed instead as the construction, `\textit{-te iru}`.
- **French.** The three forms with their sounds, the auxiliary, an irregular
  *nous* form and an irregular future, all read from Wiktionary's conjugation
  table. The sounds are Wiktionary's pronunciations written into the book's
  scheme by rule: they follow the scheme, and say what Wiktionary says — where it
  gives *aurai* as /ɔ.ʁe/ the draft has `òré`. The meaning is a dictionary's
  first sense rather than the text's. A verb is taken as pronominal only where
  the chunk shows the pronoun — `se`, `s'`, or `me`, `te`, `nous`, `vous`
  agreeing with the subject (`je me lève`, not `il me regarde`) — and then the
  draft is the pronominal verb, *aux. être* and a reflexive sense; `il s'en va`
  is *s'en aller*. Where Wiktionary lists two forms (`paye` and `paie`, `assois`
  and `assieds`) the draft offers the first.
  A verbal locution the chunk makes — `j'ai peur`, `il fait attention`, even with
  the negation (`je n'ai pas peur`) — is recognised as the locution it is: the
  verb comes with its seventh argument already empty, the row names the `\bw`
  still to add (*bw for peur after it: to be afraid*), and a button of its own,
  headed *verbal locution*, puts the pair in as the one entry the file asks for,
  `\vb{avoir}{avwar}{ai}{é}{eu}{ü}{}\bw{peur}{peur}{to be afraid}`, with the
  `\bw` run straight onto the `\vb`. The noun's sound is the noun's own
  pronunciation respelt; where it is missing the slot stays empty. It is found
  only where the noun stands right after the verb in the same chunk and the
  dictionary has the pair as a verb page of its own; a locution it has not got
  comes as the plain verb with its own meaning, and emptying that is yours.
- **German.** The three principal parts, the third person where it changes, the
  auxiliary, and the case or preposition where the dictionary gives one for the
  meaning; `sich` in front where the chunk holds the reflexive pronoun (or the
  verb has no other use); and a separable verb put back together — at `stand`,
  the entry of *aufstehen* — where its prefix ends the clause in the text that
  was looked up. It offers no `\vb` for `hat`, `ist` or `wird` where the clause
  ends in the participle or the infinitive they make a tense with: that pointer
  is yours to write. A verb the dictionary gives both auxiliaries says
  `aux. haben/sein` until you strike one for the sense in the text (*fahren*,
  and *liegen*, *sitzen*, *stehen*, whose perfect the south makes with *sein*); a
  preposition that takes either case is printed `auf + …` where the dictionary
  does not say which; a prefix outside the text that was looked up is not seen,
  and the finite verb then comes as its plain stem (`stand`, *stehen*); the sound
  slots are empty, for you to fill where a pronunciation line is given; and the
  meaning is the dictionary's first sense rather than the text's.
- **Turkish.** The aorist from the dictionary's head line, the present from its
  conjugation table, the first equivalent of its first sense, and the
  government where the dictionary tags that sense — which is seldom, 78 verbs in
  2 559 (`bakmak` -e, `korkmak` -den, `evlenmek` ile), so most of it is yours to
  add, and `beklemek`'s `(-i)` always is. It stops there: the segmented form the
  text has (`; \textit{…}`) is yours as well. A homograph comes as two entries,
  each with its own forms — `yenmek` *to defeat*, `yener`, and `yenmek` *to be
  eaten*, `yenir` — and you keep the one the text means. For a compound it
  proposes the light verb's `\vb` with the empty meaning, and the row names the
  `\bw` still to add, with the compound's own meaning and government (*bw for
  teşekkür after it: to thank (-e)*); the **compound verb** button puts the pair
  in as the one entry it is — `\vb{etmek}{}{ediyor}{}{eder}{}{}\bw{teşekkür}{}{to thank (-e)}` —
  and what it writes in the `\bw` is the compound's meaning, the one the
  dictionary's entry is for: an edition that would rather gloss the noun itself
  (`thanks (-e)`) trims it there, as it trims every other draft. Nothing is
  romanised: both sound slots stay empty, and the segmentation is yours. The
  compound is found only where the noun stands right before the verb in the same
  chunk, which is where the chunking rules put it. A derived verb the dictionary
  has only as a note on its base (`yapılmak`, *passive of yapmak*) comes as its
  infinitive alone, the forms and the meaning left to you — never with `yapar`
  under it; and about one verb in twelve has no conjugation table in the
  dictionary (`ilerlemek`, `incelemek`, `hedeflemek`) and comes without its
  present, or without both forms. Where the dictionary contradicts itself
  (`hafifletmek`: its head says `hafifletir`, its table `hafiflediyor`) the
  button says why.
- **English.** The three principal parts with their sounds, and the present of
  *be*, *have*, *do* and *say*, the four whose present nobody could build from
  the plain form. It never offers a `\vb` for a modal, nor for the particle of a
  phrasal verb (the `down` of *put it down* is not the verb *to down*). Where the
  dictionary lists two pasts it takes the one the chunk has, and otherwise the
  first listed, which is the American one (`dreamed`, `learned`). A phrasal verb
  is proposed whole when its particle ends the chunk (`came in`, `put it down`,
  `what he was waiting for`); one with words after its particle (`gave up
  smoking`) is proposed as the plain verb, for you to lengthen. The sound of a
  regular past is worked out by the book's rule for endings; an irregular one is
  the dictionary's own transcription of that form, and a phrasal verb with none
  of its own is said as its verb and its particle (`give up` `gɪv ʌp`). The
  dictionary's transcription of many a word is British only (`stop` `/stɒp/`,
  `wrote` `/ɹəʊt/`, and `was` and `were` have no American one at all), and such a
  slot is left empty rather than converted from one accent into the other; and
  the meaning is the dictionary's first sense, which is not always the one in
  the text, nor built of words commoner than the headword.
- **Hindi.** The stem, the perfective and the `ने` mark, each with its
  transliteration. The forms are the dictionary's conjugation table and the
  sounds are its romanisation of each form, respelt into the book's scheme (its
  tilde is ṁ, its `ŕ` is *ri*, its `ṣ` is *ś*), so the schwa is right form by
  form — *samajhnā* but *samjhā*. The `ने` mark is a proposal and never a fact,
  and the meaning is the dictionary's first sense rather than the text's (`रखना`
  comes as *to keep* where the text may mean *to put*). The chunk decides two
  things. In a conjunct the light verb comes with no meaning and the row names
  the `\bw` still to write; the second verb of a compound, the `रहा` of the
  progressive and the `था` or `है` after a participle get no `\vb` at all, only
  the `\dw` they always had, because what they add is yours to say.
- **Spanish.** The two forms, and an irregular participle or future, read off the
  dictionary's own conjugation rows and never made up. It reads the chunk for the
  **pronominal** verb: `me voy`, `te quedas`, `nos casamos`, `siéntate` and
  `irse` give `irse`, `quedarse`, `casarse`, `sentarse`. `se` alone gives the
  `-se` verb too, but the button asks whether it is — `se fue` is `irse`, while
  `se dice` and `se venden casas` are the plain verb with a passive or impersonal
  `se`, and nothing in a dictionary tells them apart. A clitic in front of an
  auxiliary or a modal (`se ha ido`, `me tengo que ir`) and an infinitive with
  `me` or `te` on it (`irme` looks like `llamarme`, which is *to call me*) get
  the plain verb: those are yours. `haber` comes as `hay` where no participle
  follows it (`había una vez`, `ha habido problemas`) and as the auxiliary where
  one does (`había llegado`). A **fixed phrase** is never reached: the
  dictionary is asked one word at a time, so `se dio cuenta` comes back as `dar`,
  and `darse cuenta` is yours to write. The meaning is the dictionary's first
  sense and not the text's; for a pronominal verb, the first sense marked
  reflexive, which is often not the one meant (`ponerse` comes out *to turn
  on*). `ser` and `estar` come with the division between them in its own words,
  without the two italics the conventions put round the words that carry it,
  which are yours to add. Where the dictionary lacks a slot (a defective verb has
  no `yo`: `manir`), or cannot say whether the participle or the future is
  irregular, the button says which.
- **Chinese.** A `\vb` for a verb the dictionary marks as separable or as a verb
  with a complement, and a `\dw` for everything else. The characters are the
  dictionary's own simplified spelling, the pinyin its standard Mandarin
  reading, the split always the plain A了B. The dictionary **marks fewer verbs
  than there are**: the commonest it misses — `散步`, `跑步`, `唱歌`, `请客`,
  `听懂`, `看懂`, `回来`, `进来`, `学会`, `记住` and some fifty more — are kept by hand in
  `lib/lang/zh.verbs.json`, which is also where its one common mistake is put
  right: it marks `想到` as verb-object, and `想了到` is not Chinese (`想不到`
  is). A verb in neither — `吃完` and `找到` are not in the dictionary as words at
  all, and come back as `吃` and `完` — is offered as `\dw`s, and the `\vb` is
  yours to write. A **word the dictionary has only in another lect** — Cantonese
  `揸车`, whose perfective is `揸咗车` — gets no `\vb`, because the `了` of the
  split is Mandarin grammar; nor does a word with no standard pinyin, which is
  how the dictionary says a word is not standard Mandarin, nor a split that
  belongs only to an old reading of a word whose plain reading does not split:
  `知道` "to know the Way" is marked separable, `知道` "to know" is not. A verb
  that has **come apart in the sentence** (`结了婚`, `见过面`, `睡了一觉`) is not
  found as one word, and a **potential** the dictionary lists as a word of its
  own (`看不见`, `听不懂`) comes back as that word, with a `\dw`: in both cases the
  `\vb` is the dictionary form's, and yours to write. Where the dictionary's only
  sense for a verb is a pointer (`聊天儿` is "erhua form of 聊天") the meaning is
  left empty and the button says so.

## Ask LLM

The last block hands the sentence to an external chatbot — any one, in
another tab — and brings its answer back:

1. **Ask LLM** copies a prompt to the clipboard: the sentence, the three
   sentences before and after it, the dictionary's results for the chunk,
   and every translated sentence the corpus has for it (it gathers them all
   first: *Preparing Ask LLM with all Tatoeba examples…*). The machine's own
   reading is deliberately never in it. *Prompt copied. Paste it into a
   chatbot, then paste its answer below.*
2. Paste the chatbot's translation into the box, and press **Use
   translation** (or **Ctrl+↵**). *Translation ready for this whole sentence.*
3. It is drawn like the machine's reading, with this chunk's share marked
   and the same buttons: **the marked words → meaning**, **the whole sentence
   → meaning**.

The answer is kept for the sentence, so the other chunks of the same
sentence reuse it (*Reusing the translation pasted for this sentence.*) and
only the mark moves. If the clipboard cannot be reached, the block says so
and **Ask LLM** tries again.

**Ask LLM** helps you write one chunk's gloss yourself. To have an LLM write
the glosses of a whole stretch — every chunk nobody has glossed, from one
sentence to a chapter — use the header's **gloss with an LLM** instead
([Glossing a stretch with an LLM](doc:Glossing a stretch with an LLM)): its
answer goes into the book, where nothing here does, but only into chunks
that have no gloss, and only whole.

## The gloss and the fluent translation {#the-gloss-and-the-fluent-translation}

What the machine's reading and **Ask LLM** bring is a fluent translation of
the whole sentence, and that is what they are for: to understand it. The
meaning you save under a chunk is another thing, a **gloss**: it says what
*that* chunk's own words say, in the order of the text, so that read in a row
the meanings are stiff, and may be poor English, and you can point from each
word of them to the word it renders and see how the language builds its
sentence. That is why **the marked words → meaning** and **the whole sentence
→ meaning** only start the box: they put in a share of a fluent sentence, and it
is yours to cut down to what this chunk's words say, and to bring into line with
the vocabulary line. It is also why **Ask LLM** asks the chatbot for a
translation, and stays so, while **gloss with an LLM** asks it for glosses
([What the meaning says](glossing-with-an-llm.md#what-the-meaning-says)).

> **None of this is a gloss.** A dictionary lists everything a word can
> mean and cannot say which is meant; a translated sentence is somebody
> else's sentence; a machine's reading is nobody's judgement. So in the
> reader they are drawn apart from the gloss, labelled with what they are,
> and shown only where nobody has written a vocabulary line — and the only
> place any of them becomes part of the book is a field of the chunk sheet,
> where you correct it and save it yourself.
