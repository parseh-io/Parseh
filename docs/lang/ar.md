# Arabic — the annotation conventions

{{?new}}How an Arabic sentence becomes a glossed line: what goes into each field
and how it is written. These rules bind both the reading editions and the
video captions; they are embedded into every prompt that asks for Arabic
annotation, so they are written as instructions to the annotator.

Two of the field names are languages, and neither is a claim about one:
`fa` is the text in the target language — Arabic here — and `en` is the
gloss beside it. They are the names Persian and English left behind from
the days when they were the only two languages the toolbox had, and they
are the same two keys in every book and every video. Which language the
gloss is written in is the book's or the video's own choice, `"gloss"` in
`book.json` / `video.json`, and English when the key is absent. This file
is about Arabic as the language being **taught**: the examples below gloss
into English because they must gloss into something, and every rule that
turns on the gloss language says so.{{/new}}

## The text field

`fa` reproduces the source **verbatim**: same spelling, same punctuation,
same hamza seats and alif forms (`أ إ آ ا ى ة` exactly as the source has
them), the source's own oddities included — a dialect word in a caption, a
misspelling the ASR made. Chunks split only at spaces; joined back with
single spaces they must reproduce the sentence exactly, and a machine
checks that. **Never correct the text in `fa`**{{?new}} — the correction goes in {{?video}}`note`{{/video}}{{?book}}the
vocabulary line{{/book}}{{/new}}.{{?nomarks}} It carries no short vowels of your making: the
text is copied as the source has it{{?video}}, a caption as YouTube has it{{/video}}.{{/nomarks}}{{?marks}} The short
vowels are asked for in this prompt: `fa` is then the source's text WITH the
tashkil added and nothing else changed — by the rules under Reading.{{/marks}}

## Reading

This language has no reading field.

{{?marks}}What stands in its place is the short vowels, which `fa` itself carries when they are
asked for: **full tashkil on every word** — fatha, kasra, damma on every short
vowel, **sukun** on every vowelless consonant, **shadda** on every doubled one
(with its own vowel on top), **tanwin** on every indefinite case ending
(`كِتَابٌ`, `كِتَابًا`, `كِتَابٍ`), the dagger alif where the orthography has it
(`هَٰذَا`, `لَٰكِنْ`). A word is either fully vowelled or it is wrong; a
half-vowelled word tells the reader nothing about which half was left out. The
bare pass is made by stripping these marks, so nothing but the marks may differ
between the vowelled text and the plain one.{{?video}} A caption is then
YouTube's text with the marks added and nothing else changed: not a letter, not
a hamza seat, not a space, not a stop.{{/video}} The marks agree with the
transliteration beside them: the transliteration is what the marks are checked
against.

Case endings are written as the text is read: full iʿrāb in classical and
literary prose (`الْكِتَابُ جَدِيدٌ`), pausal form at a pause (`جَدِيدْ`), and
what is actually said in a caption of spoken Arabic. There is no ezafe in
Arabic; the annexation (idafa) is shown by the case marks alone.{{/marks}}

## Transliteration

{{?classic}}`tr` is a consistent scholarly transliteration of what is actually said or
printed — Modern Standard Arabic as written, the dialect form as heard when
the video speaks dialect.

- Long vowels **ā ī ū**; short a i u; the diphthongs **aw** and **ay**.
- Hamza is **ʾ** (never at the start of a word: `amal`, not `ʾamal`);
  ʿayn is **ʿ**.
- Emphatics with a dot under: **ṣ ḍ ṭ ẓ**; **ḥ** = ح; **ḏ** = ذ, **ṯ** = ث;
  **ġ** = غ; **q** = ق; **š** = ش; **j** = ج.
- خ is **ḫ** — one letter, always; never `kh`.
- Tā marbūṭa is **-a** in pause and at the end of a phrase (`madīna`),
  **-at** when the word is the first term of an idafa or carries a case
  ending that is read (`madīnat al-malik`, `madīnatun`).
- The article is written **al-** with a hyphen and **assimilated as heard**
  before a sun letter: `aš-šams`, `an-nūr`, `ar-rajul`; `al-qamar`. After a
  vowel the alif of the article is elided and written with an apostrophe
  after the hyphen only when the form is read that way (`fī l-bayt`,
  `wa-l-kitāb`).
- Hyphenate clitics: the conjunctions `wa-` `fa-`, the prepositions `bi-`
  `li-` `ka-`, the pronoun suffixes `-hu -hā -ka -ki -ī -nā -kum -hum`, the
  future `sa-`.
- Doubled consonants written double (`muʿallim`, `šidda`).
- Case endings only where `fa` has them and they are read.

The scheme does not follow the gloss language: `š`, `ḫ` and `ʿ` are what
they are in a book glossed in Italian or in Turkish as much as in one
glossed in English, and never `sh`, `kh` or a dropped mark. It is a
transliteration of the Arabic, not a respelling in somebody's orthography,
and a reader who has learnt it once must be able to read the next edition
with it.{{/classic}}{{?ipa}}`tr` is the pronunciation of what is actually said or printed, written in
**IPA**: the broad (phonemic) IPA of Modern Standard Arabic as it is read, and
of the dialect as heard when the video speaks dialect — the speaker's own
vowels and consonants, not the standard's. No slashes, no square brackets, and
one scheme from the first chunk to the last.

- Vowels: short **a i u**, long **aː iː uː**; the diphthongs **aw** and **aj**.
- Hamza is **ʔ**, written at the start of a word too (`ʔamal`); ʿayn is **ʕ**.
- Consonants: **ħ** = ح, **x** = خ, **ɣ** = غ, **q** = ق, **ʃ** = ش, **dʒ** = ج,
  **θ** = ث, **ð** = ذ; the emphatics carry ˤ: **tˤ dˤ sˤ ðˤ**; the rest are
  IPA's own (b t d k f s z h m n l r w j).
- A doubled consonant (a shadda) is written long, **ː**: `muʕalːim`, `ʃidːa`;
  so is the article assimilated before a sun letter (`ʃːams`, `nːuːr`,
  `rːadʒul`), while `l-` stays before a moon letter (`l-qamar`).
- Tā marbūṭa is **-a** in pause and at the end of a phrase (`madiːna`), **-at**
  when the word is the first term of an idafa or carries a case ending that is
  read (`madiːnat l-malik`, `madiːnatun`).
- Stress is not written: it follows from the syllables and differs with the
  reader.
- The hyphens that part clitics stay: the conjunctions `wa-` `fa-`, the
  prepositions `bi-` `li-` `ka-`, the pronoun suffixes `-hu -haː -ka -ki -iː
  -naː -kum -hum`, the future `sa-`.
- Case endings only where `fa` has them and they are read.

IPA does not follow the gloss language: it is the same in a book glossed in
Italian or in Turkish as in one glossed in English, and a reader who has learnt
it once must be able to read the next edition with it.{{/ipa}}

## Vocabulary

{{?classic}}`voc` is written in the voice of the books' gloss blocks: headword +
transliteration + meaning.{{/classic}}{{?ipa}}`voc` is written in the voice of the books' gloss blocks: headword +
IPA + meaning.{{/ipa}} The Arabic of `voc` is written as `fa` is: with its marks
where the text has them, bare where it has none{{?nomarks}} (a caption has none, and then the
transliteration carries the vowels and the case endings; the examples below are vowelled only so
that an entry can be read){{/nomarks}}.

- A **noun** gives the singular with its plural
  ({{?classic}}`\dw{كِتَاب}{kitāb} book, pl. \pw{كُتُب} \textit{kutub}`{{/classic}}{{?ipa}}`\dw{كِتَاب}{kitaːb} book, pl. \pw{كُتُب} \textit{kutub}`{{/ipa}}) and the
  **root in parentheses** (`(\pw{ك ت ب})`).
- A **verb** is given as the perfect with its form, the imperfect and the
  masdar, in the seven slots of its `\vb` (below), and every verb in the text
  gets this entry the first time it appears.
- A **participle**, a **verbal noun** or a broken plural is tied to its
  verb or singular, not glossed as a word of its own.
- Name what was stripped from the form in the text: the pronoun suffix, the
  case ending, the dual, the sound plural, the feminine ending.
- The line uses the four macros `\dw` `\vb` `\bw` `\pw` (plus `\textit`,
  `\emph`, `\nobreak`), as the Persian editions do, and its entries are
  parted by `; `: `\vb` for every verb, `\dw` for every other headword. The
  seven slots of `\vb` are, in this order, **perfect, imperfect, masdar**,
  each with its {{?classic}}transliteration{{/classic}}{{?ipa}}IPA{{/ipa}}, then the meaning —
  {{?classic}}`\vb{كَتَبَ}{kataba (I)}{يَكْتُبُ}{yaktubu}{كِتَابَة}{kitāba}{to write}`{{/classic}}{{?ipa}}`\vb{كَتَبَ}{kataba (I)}{يَكْتُبُ}{jaktubu}{كِتَابَة}{kitaːba}{to write}`{{/ipa}} — and
  the edition prints its own label before the second and third forms,
  so never put another form into those slots:
  - the **perfect** is the third person masculine singular,
    {{?marks}}fully vowelled{{/marks}}{{?nomarks}}written as `fa` is{{/nomarks}},
    and its {{?classic}}transliteration{{/classic}}{{?ipa}}IPA{{/ipa}} carries the verb's **form** in brackets, Roman
    numerals I–X (Iq–IVq for a four-letter root):
    {{?classic}}`kataba (I)`, `arāda (IV)`, `ištarā (VIII)`, `tarjama (Iq)`{{/classic}}{{?ipa}}`kataba (I)`, `ʔaraːda (IV)`, `ʔiʃtaraː (VIII)`, `tardʒama (Iq)`{{/ipa}}. The number is what makes the other two
    slots a pattern for every form but the first; write it every time.
  - the **imperfect** is the third person masculine singular indicative,
    with its final *-u*: {{?classic}}`yaktubu`, `yaqūlu`, `yaṣilu`, `yarā`{{/classic}}{{?ipa}}`jaktubu`, `jaquːlu`, `jasˤilu`, `jaraː`{{/ipa}}. For form I its
    vowel is the one thing nobody can guess.
  - the **masdar** is the verbal noun **that goes with the sense in the
    text**, one only: {{?classic}}`وُصُول wuṣūl` for وَصَلَ *to arrive*, not the صِلَة of
    its other sense; `رُؤْيَة ruʾya` for رَأَى *to see*{{/classic}}{{?ipa}}`وُصُول wusˤuːl` for وَصَلَ *to arrive*, not the صِلَة of
    its other sense; `رُؤْيَة ruʔja` for رَأَى *to see*{{/ipa}}. It is **never the
    perfect written again** — a masdar slot that repeats the perfect prints
    {{?classic}}`masdar رَأَى raʾā`{{/classic}}{{?ipa}}`masdar رَأَى raʔaː`{{/ipa}} and teaches something false. A verb with no masdar in
    use leaves the pair empty, `{}{}`, and the edition prints nothing there,
    label and all.
{{?video}}- What a video adds is the form its chunk has, where it is none of the three the `\vb`
  prints, nor one its parenthesis names: it is named after the entry, outside
  it, with its sound,
  {{?classic}}`\vb{أَرَادَ}{arāda (IV)}{يُرِيدُ}{yurīdu}{إِرَادَة}{irāda}{to want}; here \pw{يُرِيدُونَ}
  \textit{yurīdūna}, sound plural`{{/classic}}{{?ipa}}`\vb{أَرَادَ}{ʔaraːda (IV)}{يُرِيدُ}{juriːdu}{إِرَادَة}{ʔiraːda}{to want}; here \pw{يُرِيدُونَ}
  \textit{juriːduːna}, sound plural`{{/ipa}}.
{{/video}}- What the three forms cannot say goes in **one parenthesis after the
  meaning**, items parted by `; `. Arabic has one such item: the
  **preposition the verb governs**, where the verb does not simply take a
  direct object — `+ \pw{إِلَى}`:
  {{?classic}}`\vb{وَصَلَ}{waṣala (I)}{يَصِلُ}{yaṣilu}{وُصُول}{wuṣūl}{to arrive (+
  \pw{إِلَى})}`{{/classic}}{{?ipa}}`\vb{وَصَلَ}{wasˤala (I)}{يَصِلُ}{jasˤilu}{وُصُول}{wusˤuːl}{to arrive (+
  \pw{إِلَى})}`{{/ipa}}; so `رَغِبَ … (+ \pw{فِي})`, `بَحَثَ … (+ \pw{عَنْ})`. Two
  prepositions that are alternatives take one `+` and a slash (`بَعُدَ … (+
  \pw{مِنْ}/\pw{عَنْ})`), a second object a second `+` (`سَمَحَ … (+ \pw{لِ}
  + \pw{بِ})`). Nothing else goes in the parenthesis: not the root, not a
  transitivity label.
- A verb that is perfect only — `لَيْسَ` — is a `\dw` and not a `\vb`, with
  what it does in the meaning:
  {{?classic}}`\dw{لَيْسَ}{laysa} is not, perfect in form and present in meaning`{{/classic}}{{?ipa}}`\dw{لَيْسَ}{lajsa} is not, perfect in form and present in meaning`{{/ipa}}.

One equivalent in the gloss language rather than a string of synonyms; no
etymologies; **an empty `voc` is the right answer** for a chunk needing
nothing. The repetition rule is Frank's own: a full entry the **first
time** a word appears, briefer or none on later appearances.

The meaning is what the gloss language is for; the labels around it are
not. *impf.* and *masdar* are printed by the edition itself — the same two
words in every Arabic book, out of the registry — so leave them, and the
form number, the `+` before a preposition, the `pl.` and the root, as they
are written here whatever the glosses are in. Where the gloss language is
Arabic, the meaning is a **definition** and not a translation: commoner
words than the headword, and never a word of the headword's own root, which
in Arabic is the easiest circle to write by accident. `docs/lang/en.md`
sets that case out in full; it belongs to no one language.

Which words the reader already owns turns on the gloss language as well. A
book glossed in Persian or in Turkish is read by somebody who has met a
great part of this vocabulary already, and sometimes in another sense —
كثيف is *dense* in Arabic where Persian took it for *dirty*, زحمة
is a *crowd* and not the Persian's trouble — so the entry those words want
names the difference rather than the meaning. To a reader of English or
Italian they are simply new words and take the ordinary entry.

## Never gloss

The article, the prepositions, the pronouns and the common conjunctions
never get a vocabulary entry:

```
ال في من إلى على عن بـ لـ كـ مع عند حتى منذ بين أمام خلف فوق تحت بعد قبل
أنا أنت أنتِ هو هي نحن أنتم هم هذا هذه ذلك تلك هؤلاء أولئك الذي التي الذين
و ف ثم أو أم لكن بل إن أن لأن إذا لو ما لا لم لن لماذا كيف أين متى كم هل
نعم لا كل بعض غير
```

## Chunking

A chunk is a sense group of roughly **2–6 words** — a verb with its
subject or object, a noun with its adjective, a preposition with its noun:
something a reader hovers and that *means* something on its own. Never
split an **idafa** (`بَيْتُ الرَّجُلِ`), a **preposition from its noun**
(`فِي الْبَيْتِ`), or **the article from its noun** — the article is written
joined and cannot be split anyway, but a phrase like `هَٰذَا الْكِتَاب` is one
chunk. A negation stays with its verb (`لَمْ يَكْتُبْ`, `لَا أَعْرِف`), a
conjunction clitic with the word it is written on. A very short sentence
(`نَعَمْ`, `اُكْتُبْ`) is one chunk; that is normal and not a fault.

{{?note}}THE DIALECTS, MEASURED (a word to whoever maintains this file; no prompt carries it).
A book or a video may be written in a variety (`ar.egy`, `ar.lev`, `ar.gulf`, `ar.mor`): its dictionary and
`lib/lang/ar.<v>.lookup.json` are read before the standard ones, `lib/lang/ar.<v>.chunk.json` (its function words)
before `ar.chunk.json`, and `lib/lang/ar.<v>.ipa.json` (how it says q, j and the interdentals) before `ar.ipa.json`.
The figures below are `python3 tests/dialect_bench.py` on the hand-judged sets of `tests/fixtures/arabic-dialects/`
(one person's judgement of a small sample: a word or two is noise), with kaikki's extracts of 2026-11-22.

Right entry first, as built (the held-out sets, written after the rules and never used to write one): Egyptian 85%
(24/28), Levantine 89% (25/28), Gulf 85% (24/28), Moroccan 83% (20/24); read as standard Arabic the same sets give
53%, 57%, 64% and 33%. On the sets the rules were written on: 81%, 81%, 77%, 72%. Standard Arabic's own set, by the
dictionary alone: 84% (66/78).

The order after the two dictionaries are merged (the dialect's entries first, then the standard's, `lookup.
_with_variety`) is the right one: with the standard dictionary's entries first instead, the held-out sets would give
53%, 67%, 64%, 58%. Of the 108 held-out words, 6 have the right entry on the panel but not first: 3 because the
dialect's dictionary has the same word under its own headword and the judged answer is the standard one (اليوم,
أبغى → بغي, الما → ما "water"), which a reader can call right; 2 because another entry of the dialect's dictionary
comes first (Levantine روح before راح, Gulf خل before خلى); 1 because another standard entry does (خليك → خلي before
خلى). Every other miss is a word no installed dictionary has, which no order can mend.

Moroccan, a second look (2026-11-22): its misses on the working set were (a) فال- (في ال-) found nothing where the
Moroccan dictionary lists the noun without its article form (فالزنقة, فالسبيطار): a second rule takes فال off whole,
72% from 67%, the held-out set unchanged at 83%; (b) the Moroccan dictionary's own headword of the same word where the
set wanted the standard one (بالزاف for بزاف, سير "to go" for سار, جا for جاء, ما for ماء, دري for دراري): the reader
sees the right word, the judgement is strict; (c) verbs whose final hamza Darija drops or writes as ا (نقرا, مشا) and
imperatives with a pronoun (عطيني, عافاك), left for the verbs' brief (12.30). Arabizi (Darija in Latin letters) is
not read: no dictionary of it exists to install.

Cutting into phrases, on the longer sentences of `tests/fixtures/arabic-dialects/phrases/` (cut by hand before the
lists were written; the word sets' sentences are each one phrase), seams in the right place, standard rules → the
dialect's lists (12.31): Egyptian 5 of 11 → 8 of 11, Levantine 2 of 9 → 5 of 9, Gulf 3 of 9 → 5 of 9,
Moroccan 0 of 8 → 1 of 8 (its verbs were in no dictionary the chunker read, so their class was unknown). Then the
word classes from the dialect's dictionary (12.37, `chunker._dictionary_classes`: the variety's dictionary along its
rules first, the standard one as before when it has nothing; and `_marked_verb`: a word in neither dictionary as
written that a prefix marked `verb` in `ar.<v>.lookup.json` peels to a verb is a verb), with the 2026-11-23
extracts: Egyptian 8 of 11 (10 cut, from 11), Levantine 5 of 9, Gulf 3 of 9, Moroccan 4 of 8 (6 cut). The Gulf loses
2: its dictionary rightly files وياي as a preposition and وايد as an adverb, and the rules, written for standard
Arabic, then cut before وياي ("with me", a whole phrase) and join وايد to the clause before it. Reading the standard
dictionary along the dialect's prefixes instead put no seam more in the right place on any set (one fewer on the
Levantine and the Moroccan), so the fallback is standard Arabic's reading unchanged. The words' lookup is untouched
(the bench's lookup lines byte-identical), and so is standard Arabic's cut (byte-identical on all 136 sentences of the
sets).

Romanisation: the standard dictionary's entries in a dialect text are said the dialect's way, consonants only
(Egyptian q → ʾ, j → g, ṯ ḏ ẓ → t d ḍ; Levantine q → ʾ, ṯ ḏ ẓ → t d ḍ; Gulf q → g; Moroccan ṯ ḏ ẓ → t d ḍ); the
dialect dictionaries' own romanisations are kept as they are, but for the ʾ of a word written with ق. The standard
entries also lose their final case vowel and tanwīn (kataba → katab, kitāban → kitāb, madrasatun → madrasa): one rule,
`pausal` in `lib/lang/ar.ipa.json`, which each variety's file turns on; long vowels, the -a of ة and a word's own -un
(mudun, taʿāwun) stay. Tidying a transcript in a dialect also reads the dialect's question words (`question_words` in
`lib/lang/ar.<v>.chunk.json`), so «انت رايح فين» ends with ؟.{{/note}}

## Example

{{?note}}No speaker has reviewed this example yet: an Arabic reader should read the
chunks, the transliteration and the IPA before the prompt is trusted.{{/note}}Three chunks of one caption of formal Modern Standard Arabic, read with its case endings,
as an answer writes them: the same shape in every prompt. The meanings here are written in English because
an example has to be written in something; yours are written in the gloss language of this prompt. The Arabic
of `fa` and of `voc` is shown {{?marks}}with its marks, as this prompt asks for them{{/marks}}{{?nomarks}}without marks, as the caption has it (a text that
is vowelled keeps its marks, and so does the Arabic of its `voc`){{/nomarks}}.

{{?classic}}{{?marks}}```json
{"chunks": [
  {"fa": "ذَهَبَ الطُّلَّابُ", "tr": "ḏahaba ṭ-ṭullābu", "voc": "\\vb{ذَهَبَ}{ḏahaba (I)}{يَذْهَبُ}{yaḏhabu}{ذَهَاب}{ḏahāb}{to go (+ \\pw{إِلَى})}; \\dw{طَالِب}{ṭālib} student, pl. \\pw{طُلَّاب} \\textit{ṭullāb} (\\pw{ط ل ب})", "en": "went the students"},
  {"fa": "إِلَى الْمَكْتَبَةِ", "tr": "ilā l-maktabati", "voc": "\\dw{مَكْتَبَة}{maktaba} library, pl. \\pw{مَكَاتِب} \\textit{makātib} (\\pw{ك ت ب})", "en": "to the library"},
  {"fa": "بَعْدَ الدَّرْسِ", "tr": "baʿda d-darsi", "voc": "\\dw{دَرْس}{dars} lesson, pl. \\pw{دُرُوس} \\textit{durūs} (\\pw{د ر س})", "en": "after the lesson"}
]}
```{{/marks}}{{?nomarks}}```json
{"chunks": [
  {"fa": "ذهب الطلاب", "tr": "ḏahaba ṭ-ṭullābu", "voc": "\\vb{ذهب}{ḏahaba (I)}{يذهب}{yaḏhabu}{ذهاب}{ḏahāb}{to go (+ \\pw{إلى})}; \\dw{طالب}{ṭālib} student, pl. \\pw{طلاب} \\textit{ṭullāb} (\\pw{ط ل ب})", "en": "went the students"},
  {"fa": "إلى المكتبة", "tr": "ilā l-maktabati", "voc": "\\dw{مكتبة}{maktaba} library, pl. \\pw{مكاتب} \\textit{makātib} (\\pw{ك ت ب})", "en": "to the library"},
  {"fa": "بعد الدرس", "tr": "baʿda d-darsi", "voc": "\\dw{درس}{dars} lesson, pl. \\pw{دروس} \\textit{durūs} (\\pw{د ر س})", "en": "after the lesson"}
]}
```{{/nomarks}}{{/classic}}{{?ipa}}{{?marks}}```json
{"chunks": [
  {"fa": "ذَهَبَ الطُّلَّابُ", "tr": "ðahaba tˤːulːaːbu", "voc": "\\vb{ذَهَبَ}{ðahaba (I)}{يَذْهَبُ}{jaðhabu}{ذَهَاب}{ðahaːb}{to go (+ \\pw{إِلَى})}; \\dw{طَالِب}{tˤaːlib} student, pl. \\pw{طُلَّاب} \\textit{tˤulːaːb} (\\pw{ط ل ب})", "en": "went the students"},
  {"fa": "إِلَى الْمَكْتَبَةِ", "tr": "ʔilaː l-maktabati", "voc": "\\dw{مَكْتَبَة}{maktaba} library, pl. \\pw{مَكَاتِب} \\textit{makaːtib} (\\pw{ك ت ب})", "en": "to the library"},
  {"fa": "بَعْدَ الدَّرْسِ", "tr": "baʕda dːarsi", "voc": "\\dw{دَرْس}{dars} lesson, pl. \\pw{دُرُوس} \\textit{duruːs} (\\pw{د ر س})", "en": "after the lesson"}
]}
```{{/marks}}{{?nomarks}}```json
{"chunks": [
  {"fa": "ذهب الطلاب", "tr": "ðahaba tˤːulːaːbu", "voc": "\\vb{ذهب}{ðahaba (I)}{يذهب}{jaðhabu}{ذهاب}{ðahaːb}{to go (+ \\pw{إلى})}; \\dw{طالب}{tˤaːlib} student, pl. \\pw{طلاب} \\textit{tˤulːaːb} (\\pw{ط ل ب})", "en": "went the students"},
  {"fa": "إلى المكتبة", "tr": "ʔilaː l-maktabati", "voc": "\\dw{مكتبة}{maktaba} library, pl. \\pw{مكاتب} \\textit{makaːtib} (\\pw{ك ت ب})", "en": "to the library"},
  {"fa": "بعد الدرس", "tr": "baʕda dːarsi", "voc": "\\dw{درس}{dars} lesson, pl. \\pw{دروس} \\textit{duruːs} (\\pw{د ر س})", "en": "after the lesson"}
]}
```{{/nomarks}}{{/ipa}}

What to notice: the verb comes first and its subject follows in the same chunk, so
its `en` keeps that order (*went the students*); the `\vb` gives the form number,
the imperfect, the masdar and, in its parenthesis, the preposition the verb
governs; a noun gives its plural and its root in parentheses; the article and
the prepositions are never glossed.

{{?note}}DIALECT SENTENCES AND MACHINE TRANSLATION (TO-DO 12.33; a word to whoever maintains this file; no prompt
carries it).

A word only a dialect has found nothing among the translated sentences,
because the corpus (`lib/corpus.py`, built by `lib/getcorpus.py` from
Tatoeba's exports) and the translation models (`lib/getmt.py`) were standard
Arabic's. What was looked at, on 2026-11-22:

| Source | What it is | Licence | Used |
|---|---|---|---|
| Tatoeba | sentences with people's translations; a dialect under its own ISO code | CC BY 2.0 FR, as the rest of the corpus | **yes**, Egyptian and Levantine |
| MADAR (CAMeL Lab, NYU Abu Dhabi) | 25 city dialects + MSA, parallel; the English side held by the U-Star consortium | internal research and evaluation only, no redistribution | no |
| PADIC | 6 dialects (Algiers, Annaba, Tunisian, Moroccan, Syrian, Palestinian) + MSA, about 6,400 sentences | GPL-3.0 on SourceForge | no: no English side, so nothing to show as a translation |
| FLORES-200 / FLORES+ | about 2,000 sentences translated from English, among them `arz_Arab`, `ary_Arab`, `apc_Arab`, `acm_Arab`, `aeb_Arab` | CC BY-SA 4.0 | not now: a gated download, and news-register prose that a learner's dialect word is rarely in; the candidate if Tatoeba stays thin |

**Tatoeba, counted from its per-language exports** (sentences in Arabic
letters with an English translation; a sentence translated twice is two
pairs):

| Variety | Codes | Sentences (Arabic script, with English) | Pairs built | Offered |
|---|---|---|---|---|
| Egyptian | `arz` | 1,338 of 1,595 | 1,399 | yes |
| Levantine | `ajp`, `apc` | 250 + 38 (apc: 49 of 160 in Arabic letters, the rest Arabizi) | 321 | yes |
| Gulf | `afb`, `acw` (none at Tatoeba) | 80 | 81 | no |
| Moroccan | `ary` | 66 | 76 | no |

Also at Tatoeba, not a Parseh variety: Algerian `arq` (1,769 with English),
Mesopotamian `acm` (24). Tunisian `aeb` and Najdi `ars` have no export.

**The threshold is 100 pairs** (`getcorpus.VARIETY_FLOOR`): the English
export a pair needs is 25 MB whatever the dialect brings, and under a
hundred sentences a dialect word of a book is seldom among them (in the
Gulf set, *شلون*, *وايد* and *أبي* are in none). Below it the Reading help
row says *Too few yet* and the panel says plainly that there are no
translated sentences for that dialect yet. The counts are a table in
`getcorpus.VARIETY_PAIRS`, counted again at each release: the four `*-eng_links`
and `*_sentences` exports of a variety, read with `bzcat`, the sentence ids
of the links kept when the sentence has an Arabic letter.

**How it is built.** `getcorpus.build("ar.egy")` fetches each of the
variety's codes' exports (the registry's `kaikki` rows, the same codes),
skips a code Tatoeba has none of, keeps only sentences in Arabic letters,
and writes `corpus/ar.egy-en.db`, indexed with standard Arabic's folding.
The lookup of a text in a variety (`corpus.look_up_variety`) reads the
dialect's matches first and standard Arabic's after them, as one paged list,
each pair marked with its `variety`.

**Machine translation: no dialect model.** Mozilla's models are Arabic
(MSA) to English; there is no dialect pair, and none runs in the browser
engine Parseh uses. A dialect text is sent to the Arabic model as it is,
and the panel says so under the machine's reading.{{/note}}
