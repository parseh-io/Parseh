# Catalan — the annotation conventions

{{?new}}How a Catalan sentence becomes a glossed line: what goes into each field and
how it is written. These rules bind both the reading editions and the video
captions; they are embedded whole into every prompt that asks for Catalan
annotation, so they are written as instructions to the annotator.

Two of the field names are languages, and neither is a claim about one: `fa`
is the text in the target language — Catalan here — and `en` is the gloss
beside it. They are the names Persian and English left behind from the days
when they were the only two languages the toolbox had, and they are the same
two keys in every book and every video. Which language the gloss is written
in is the book's or the video's own choice, `"gloss"` in `book.json` /
`video.json`, and English when the key is absent. This file is about Catalan
as the language being **taught**: the examples below gloss into English
because they must gloss into something, and every rule that turns on the
gloss language says so.{{/new}}

The reference is **standard Central Catalan**, as the Institut d'Estudis
Catalans writes it (the IEC's spelling and grammar) and as Barcelona says it.
A Valencian or a Balearic text is not an error: its forms (`parle`, `vindre`,
`eixir`, `meua`, `este`; `parl`, the article `es`/`sa`) are reproduced and
glossed as written, and where the entry needs it the vocabulary line says which
standard form they answer to.

## The text field

`fa` reproduces the source **verbatim**: same spelling, same accents, same
apostrophes, hyphens and middle dots, same punctuation, the source's own
oddities included — a regional form, an old spelling, an ASR slip in a
caption. Chunks split only at spaces; joined back with single spaces they must
reproduce the sentence exactly, and a machine checks that. **Never correct the
text in `fa`**{{?new}} — the correction goes in
{{?video}}`note`{{/video}}{{?book}}the vocabulary line{{/book}}{{/new}}.

Catalan is plain text: there are no marks to add and none to strip{{?book}}, so the
registry's `strip` is null and there is no bare pass{{/book}}. What goes wrong is
folding away something that is spelling:

- **The written accent is spelling, not decoration.** It marks the stress
  where the default rule does not put it (`català`, `cafè`, `només`,
  `història`), and the grave and the acute are not the same letter: `è` and `ò`
  are open, `é` and `ó` closed (`cafè`, `perquè`; `també`, `cançó`). On a
  handful of monosyllables it tells two words apart: `és`/`es`, `més`/`mes`,
  `són`/`son`, `sí`/`si`, `té`/`te`, `bé`/`be`, `sé`/`se`, `què`/`que`,
  `món`/`mon`, `pèl`/`pel`, `vós`/`vos`, `ús`/`us`, `déu`/`deu`, `mà`/`ma`,
  `sòl`/`sol`. Never add one the source does not write and never drop one it
  does. The IEC's spelling of 2016 took most of the other diacritic accents
  away (`dóna` → `dona`, `sóc` → `soc`, `ós` → `os`, `véns` → `vens`, `nét` →
  `net`); a source that still writes the old ones keeps them — that is its
  spelling, not an error.
- **The diaeresis is spelling too**: `ï` and `ü` mark a vowel said apart from
  the one before it (`veïna`, `raïm`, `traduït`) or a `u` that is said after
  `g`/`q` before `e`/`i` (`qüestió`, `pingüí`, `aigües`).
- **The apostrophe and the hyphen belong to the word.** An article, a
  preposition or a pronoun that has lost its vowel is written onto the next
  word with an apostrophe (`l'home`, `d'aigua`, `m'agrada`, `n'hi ha`,
  `s'ha acabat`), and the pronouns written after a verb are joined to it by a
  hyphen or an apostrophe (`menjar-lo`, `fer-ho`, `dona-m'ho`, `porta'l`).
  There is no space in any of these, so a chunk never ends inside one. A
  straight `'` and a curly `’` are reproduced as the source has them.
- **The middle dot is part of the word.** `l·l` is a long `l`, written with
  `·` between the two (`col·lecció`, `il·lusió`, `intel·ligent`), and it is
  not punctuation. A source typed without the right key writes `l.l`, `l•l`
  or the single character `ŀl`; reproduce whichever it wrote, and never turn
  `l·l` into `ll`, which is another sound.

`ç` is a letter of its own and not a `c` with something on it, and it may not
be folded away either.

{{?studio}}Catalan has no character range of its own in the registry and could not be
given one: it is written in the alphabet the toolbox's own prose is written
in. So nothing detects a run of Catalan — and where the glosses are in
another Latin-script language, English or Spanish or French, nothing tells
the two apart by eye either. Wherever the format asks you to mark the target
text (a studio document's `[…]{tl}` mark), mark every Catalan run; in a book
chunk or a video chunk `fa` is Catalan by definition and needs no mark.{{/studio}}

## Reading

This language has no reading field: the `kana` key is ignored where it
appears, and nothing asks for one.

## Transliteration

{{?classic}}`tr` is an **IPA-lite pronunciation aid, only where it helps**, and it may be
omitted. Catalan spelling says less of the sound than Spanish or Italian
spelling does, so more chunks earn a line than in either; but what follows a
rule — the neutral vowel, the `u` for an unstressed `o`, the silent `r` of an
infinitive, the `b` of `amb` — is told the reader once on the how-to-read page,
and a chunk that holds nothing else needs no line. Give a `tr` for what the
spelling does not show:

- the **open and closed e and o**, which the spelling shows only where it
  writes an accent anyway: `è` for /ɛ/ and `é` for /e/, `ò` for /ɔ/ and `ó` for
  /o/, on the stressed vowel (`porta` → `pòrtə` door, `boca` → `bókə` mouth;
  `net` → `nèt` clean, `nét` grandson; `os` → `òs` bone, `ós` bear; `dona` →
  `dònə` woman, `dónə` gives). In the line, the stressed vowel of **every**
  word of more than one syllable carries its accent, `à`, `í`, `ú` included
  (`kázə`, `pərlá`), and so does the `e` or `o` of a monosyllable (`sèl`,
  `ʒén`), because once the other vowels have gone to `ə` the stress is what
  holds the word together;
- the **neutral vowel**: unstressed `a` and `e` are both `ə` (`casa` →
  `kázə`, `pare` → `párə`, `parlar` → `pərlá`), and unstressed `o` is `u`
  (`poder` → `pudè`, `parlo` → `párlu`). Valencian keeps `a`, `e` and `o`
  apart where Central merges them: write what the recording says;
- the **letters that are not said**: the final `r` of an infinitive and of
  many nouns and adjectives (`parlar` → `pərlá`, `carrer` → `kərré`, `primer`
  → `primé`, but `mar` → `mar`, `cor` → `kòr`), a `t` after `l` or `n` at the
  end of a word (`molt` → `mól`, `sant` → `san`), a `b` after `m` (`amb` →
  `əm`), and `h` (`home` → `òmə`, `ahir` → `əí`);
- **`x`**, which is `ʃ` at the start of a word, after a consonant and in `ix`
  — whose `i` is not said after `a`, `o` or `u` (`xocolata` → `ʃukulátə`,
  `caixa` → `káʃə`, `peix` → `péʃ`) — but `ks` or `gz` in a learned word
  (`taxi` → `táksi`, `examen` → `əgzámən`);
- **`ll`** is `ʎ` and **`ny`** is `ɲ` (`llibre` → `ʎíbrə`, `any` → `aɲ`) —
  the `ɲ` Spanish's `ñ` and Italian's `gn` take;
- the **affricates and `j`**: `tx` and a final `ig` are `tʃ` (`cotxe` →
  `kòtʃə`, `maig` → `matʃ`, `vaig` → `vatʃ`); `j`, and `g` before `e`/`i`, are
  `ʒ`, the *s* of *pleasure* (`jove` → `ʒòvə`, `gent` → `ʒén`), and `tj`/`tg`
  are `dʒ` (`platja` → `pládʒə`, `metge` → `médʒə`);
- **`l·l`** is a long `l`, written `ll` in the line (`col·lecció` →
  `kulləksió`) — in the line a double `l` is never `ʎ`, which has its own sign;
- **`s` and `z`**: a single `s` between vowels, and `z`, are voiced `z`
  (`casa` → `kázə`, `zero` → `zèru`); `ss`, `ç` and `c` before `e`/`i` are
  `s` (`passa` → `pássə`, `plaça` → `plásə`, `cel` → `sèl`);
- **`qu`, `gu`, `ü`**: before `e`/`i`, `qu` and `gu` are plain `k` and `g`
  (`que` → `kə`, `guerra` → `gèrrə`), but before `a` and `o` the `u` is said
  (`quan` → `kwan`, `aigua` → `áigwə`), and `ü` says it before `e`/`i`
  (`qüestió` → `kwəstió`);
- **`r`**: the trill — at the start of a word, after `n`, `l` or `s`, and
  written `rr` — is written `rr` in the line, against the single tap of `r`
  between vowels (`rosa` → `rròzə`, `carro` → `kárru`, against `cara` →
  `kárə`);
- a **borrowed or foreign word** said the way the source says it (`whisky` →
  `wíski`), which is the case the spelling helps least.

`b` and `v` are one sound in Central Catalan, and the letter does not say
which; that is worth knowing once and is on the how-to-read page, not repeated
in every chunk. Valencian and Balearic speakers often keep a `v` apart: write
what the recording says.{{/classic}}{{?ipa}}`tr` is written in **IPA**: broad (phonemic), for standard Central
Catalan, with no slashes and no square brackets round it, and **only where it
helps**; it may be omitted. Catalan spelling says less of the sound than
Spanish or Italian spelling does, so more chunks earn a line than in either;
but what follows a rule — the neutral vowel, the `u` for an unstressed `o`,
the silent `r` of an infinitive, the `b` of `amb` — is told the reader once on
the how-to-read page, and a chunk that holds nothing else needs no line. The
stress is written with `ˈ` before the stressed syllable of every word of more
than one syllable (`ˈkazə`, `pəɾˈla`). Give a line for what the spelling does
not show:

- the **open and closed e and o**, which the spelling shows only where it
  writes an accent anyway: `ɛ` and `e`, `ɔ` and `o` (`porta` → `ˈpɔɾtə` door,
  `boca` → `ˈbokə` mouth; `net` → `ˈnɛt` clean, `ˈnet` grandson; `os` → `ˈɔs`
  bone, `ˈos` bear; `dona` → `ˈdɔnə` woman, `ˈdonə` gives);
- the **neutral vowel**: unstressed `a` and `e` are both `ə` (`casa` →
  `ˈkazə`, `pare` → `ˈpaɾə`, `parlar` → `pəɾˈla`), and unstressed `o` is `u`
  (`poder` → `puˈdɛ`, `parlo` → `ˈpaɾlu`). Valencian keeps `a`, `e` and `o`
  apart where Central merges them: write what the recording says;
- the **letters that are not said**: the final `r` of an infinitive and of
  many nouns and adjectives (`parlar` → `pəɾˈla`, `carrer` → `kəˈre`, `primer`
  → `pɾiˈme`, but `mar` → `ˈmar`, `cor` → `ˈkɔɾ`), a `t` after `l` or `n` at
  the end of a word (`molt` → `ˈmol`, `sant` → `ˈsan`), a `b` after `m` (`amb`
  → `əm`), and `h` (`home` → `ˈɔmə`, `ahir` → `əˈi`);
- **`x`**, which is `ʃ` at the start of a word, after a consonant and in `ix`
  — whose `i` is not said after `a`, `o` or `u` (`xocolata` → `ʃukuˈlatə`,
  `caixa` → `ˈkaʃə`, `peix` → `ˈpeʃ`) — but `ks` or `gz` in a learned word
  (`taxi` → `ˈtaksi`, `examen` → `əgˈzamən`);
- **`ll`** is `ʎ` and **`ny`** is `ɲ` (`llibre` → `ˈʎibɾə`, `any` → `ˈaɲ`) —
  the `ɲ` Spanish's `ñ` and Italian's `gn` take;
- the **affricates and `j`**: `tx` and a final `ig` are `tʃ` (`cotxe` →
  `ˈkɔtʃə`, `maig` → `ˈmatʃ`, `vaig` → `ˈbatʃ`); `j`, and `g` before `e`/`i`,
  are `ʒ` (`jove` → `ˈʒɔbə`, `gent` → `ˈʒen`), and `tj`/`tg` are `dʒ` (`platja`
  → `ˈpladʒə`, `metge` → `ˈmedʒə`);
- **`l·l`** is a long `l`, written `ll` (`col·lecció` → `kulləkˈsjo`), never
  `ʎ`;
- **`s` and `z`**: a single `s` between vowels, and `z`, are `z` (`casa` →
  `ˈkazə`, `zero` → `ˈzɛɾu`); `ss`, `ç` and `c` before `e`/`i` are `s`
  (`passa` → `ˈpasə`, `plaça` → `ˈplasə`, `cel` → `ˈsɛl`);
- **`qu`, `gu`, `ü`**: before `e`/`i`, `qu` and `gu` are plain `k` and `g`
  (`que` → `kə`, `guerra` → `ˈgɛrə`), but before `a` and `o` the `u` is said
  (`quan` → `ˈkwan`, `aigua` → `ˈajgwə`), and `ü` says it before `e`/`i`
  (`qüestió` → `kwəstiˈo`);
- **`r`**: the trill `r` — at the start of a word, after `n`, `l` or `s`, and
  for `rr` — against the tap `ɾ` everywhere else (`rosa` → `ˈrɔzə`, `carro` →
  `ˈkaru`, against `cara` → `ˈkaɾə`);
- a **borrowed or foreign word** said the way the source says it (`whisky` →
  `ˈwiski`), which is the case the spelling helps least.

`b` and `v` are one sound in Central Catalan, written `b` (`vaca` → `ˈbakə`),
and the letter does not say which: that is worth knowing once and is on the
how-to-read page. Valencian and Balearic speakers often keep a `v` apart:
write what the recording says.{{/ipa}}

Write the whole chunk in `tr` when you give one, not a single word out of it.
Never write `tr` for a chunk whose sound the spelling and the rules above
already give.{{?video}} In a **video** `tr` is the sound of what was **said**: where
the speaker drops a vowel or runs words together ({{?classic}}`està` → `stá`{{/classic}}{{?ipa}}`està` → `ˈsta`{{/ipa}}),
that is what goes in, because the reader is listening to the same recording.{{/video}}

## Vocabulary

`voc` is written in the voice of the books' gloss blocks: headword + meaning,
with the grammar a learner needs to recognise the form. The pronunciation
slots of the macros are filled only where the spelling leaves the word's
stressed vowel open to doubt — in Catalan, a stressed `e` or `o` the spelling
does not mark (below); elsewhere they are left empty.

- A **verb** is given as **infinitive, first person present, past
  participle**, in that order, then the meaning. The edition prints *pres.*
  and *p.p.* before the second and the third, so never put another form into
  those slots. The first person present is the form you cannot guess: it
  carries the odd consonant of the irregular verbs (`tinc`, `vinc`, `faig`,
  `dic`, `puc`, `visc`, `bec`, `conec`), the `-eix-` that most `-ir` verbs
  take and some do not (`serveixo`, `pateixo`, against `dormo`, `sento`,
  `obro`), and the stem the present subjunctive is built on (`tingui`,
  `vingui`, `faci`). The participle is the other unguessable one (`fet`,
  `dit`, `vist`, `escrit`, `pres`, `mort`, `obert`, `tingut`, `vingut`,
  `pogut`, `begut`, `conegut`, `viscut`), and it is what the perfect (`he
  parlat`) is made with. No class (`-ar`, `-er`/`-re`, `-ir`) and no auxiliary:
  the perfect of every Catalan verb is made with `haver`, so there is nothing
  to say. `\vb{parlar}{}{parlo}{}{parlat}{}{to speak}`,
  `\vb{tenir}{}{tinc}{}{tingut}{}{to have (fut. \pw{tindré})}`,
  `\vb{dir}{}{dic}{}{dit}{}{to say}`. A **regular** verb gets all three too:
  **every** verb gets a `\vb`, no exceptions.
- {{?classic}}A form's pronunciation is given **only where its stressed vowel is an `e` or
  an `o` with no accent written on it** — the form as it is written, with that
  vowel marked `è`/`é`, `ò`/`ó` as the line marks it (`pèrdre`, `pèrdo`, `fér`,
  `fét`, `servèixo`); empty for `parlar`, `tinc`, `perdut`, `només`. The rest
  of the sound — the neutral vowels, the silent letters — is left to the
  chunk's own `tr`.{{/classic}}{{?ipa}}A form's pronunciation is given **only where its stressed vowel is an `e` or
  an `o` with no accent written on it** — the form in IPA, with `ˈ` before the
  stressed syllable of a word of more than one (`ˈpɛɾdɾə`, `ˈpɛɾdu`, `ˈfe`,
  `ˈfet`, `səɾˈbɛʃu`); empty for `parlar`, `tinc`, `perdut`, `només`.{{/ipa}}
  {{?classic}}`\vb{perdre}{pèrdre}{perdo}{pèrdo}{perdut}{}{to lose}`,
  `\vb{fer}{fér}{faig}{}{fet}{fét}{to do, to make (fut. \pw{faré})}`,
  `\vb{servir}{}{serveixo}{servèixo}{servit}{}{to serve}`{{/classic}}{{?ipa}}`\vb{perdre}{ˈpɛɾdɾə}{perdo}{ˈpɛɾdu}{perdut}{}{to lose}`,
  `\vb{fer}{ˈfe}{faig}{}{fet}{ˈfet}{to do, to make (fut. \pw{faré})}`,
  `\vb{servir}{}{serveixo}{səɾˈbɛʃu}{servit}{}{to serve}`{{/ipa}}.
- A **pronominal** verb is the infinitive with its pronoun written on, the
  present with its own before it, and the participle bare: `\vb{casar-se}{}{em
  caso}{}{casat}{}{to get married}`, `\vb{anar-se'n}{}{me'n vaig}{}{anat}{}{to
  leave, to go away (fut. \pw{me n'aniré})}`. A fixed verbal phrase is whole
  (`tenir ganes de`, `en tinc ganes`), and an **impersonal** verb, which has
  no first person, gives the third person in the second slot:
  `\vb{caldre}{}{cal}{}{calgut}{}{to be needed}` — and the entry says so,
  because `cal` is also `ca` + `el` (*the house of*, `cal metge`).
- What the three forms cannot say goes in **one parenthesis after the
  meaning**, items parted by `; `, **only where it is irregular**, in these
  words: `fut. \pw{tindré}`, the first person future, where it is not the
  infinitive plus an ending — `tindré`, `vindré`, `faré`, `aniré`, `hauré`,
  `podré`, `sabré`, `voldré`, `valdré`, `cabré`. The same stem makes the
  conditional, and `tindria`, `faria`, `podria` are on every page of a novel.
  An impersonal verb gives the third person here as it does in the second
  slot (`fut. \pw{caldrà}`).
- **The past a story is told in is `va` + the infinitive**, and it is not
  *go*: `vaig parlar` is *I spoke*, `va dir` *he said*, `vam arribar` *we
  arrived* — the forms `vaig`, `vas`/`vares`, `va`, `vam`/`vàrem`, `vau`/`vàreu`,
  `van`/`varen` are the present of `anar` used as the past's auxiliary. The
  entry is the **infinitive's**, and the past is named after it, outside it:
  `\vb{parlar}{}{parlo}{}{parlat}{}{to speak}; here \pw{vaig parlar}, 1sg past
  (\pw{va} + inf.)`. Never gloss it as *I go to speak*: that is `vaig a
  parlar`, with an `a`, which the spoken language uses for a future, and the
  `a` is the whole difference. Literary prose and Valencian also have a simple
  past (`parlà`, `parlí`, `fou`, `digué`), named the same way: `; here
  \pw{fou}, 3sg simple past (lit.)`. The **perfect** (`he parlat`, `ha dit`)
  is the past of today and of a time not yet over (`avui he parlat`, against
  `ahir vaig parlar`); the auxiliary `haver` and the participle are glossed
  together, under the participle's verb.
- **The past and the imperfect are not one past tense**, and neither survives
  an English gloss that says *did*: `va parlar` is one finished event (*spoke,
  said his piece*), `parlava` the background, the habit, the unfinished (*was
  speaking, used to speak*); the imperfect is named after the entry,
  `; here \pw{parlava}, 1/3sg imperf.`. The handful of verbs whose **meaning**
  changes with the tense earn a full entry every time: `sabia` *knew* against
  `va saber` *found out*; `coneixia` *knew (a person)* against `va conèixer`
  *met*; `podia` *could* against `va poder` *managed to*; `volia` *wanted*
  against `va voler` *tried to* and `no va voler` *refused*.
- **`ser` and `estar` are both "to be", and the entry must say which and
  why** — and the line is not where Spanish draws it, which matters most to a
  reader who knows Spanish. Standard Catalan says where a thing is with `ser`:
  `la Maria és a casa`, `el llibre és a la taula`. Name the division in the
  meaning slot every time either verb is given a full entry:
  {{?classic}}`\vb{ser}{sér}{soc}{sóc}{estat}{}{to be — ser: what a thing \textit{is}
  (identity, origin, time, what it is like) and \textit{where} it is}`{{/classic}}{{?ipa}}`\vb{ser}{ˈse}{soc}{ˈsok}{estat}{}{to be — ser: what a thing \textit{is}
  (identity, origin, time, what it is like) and \textit{where} it is}`{{/ipa}},
  `\vb{estar}{}{estic}{}{estat}{}{to be — estar: how it is \textit{right now}
  (a state, the result of a change); also to stay, to spend (time)}`. Speech
  also uses `estar` for a place (`està a casa`); that is reproduced, and
  glossed by the same entry. `estat` is the participle of **both**, and the
  entry for it says so: `\dw{estat}{} \pw{ser} or \pw{estar}, p.p. — the same
  form for both; the sentence decides` (`sigut`, heard for `ser`, is glossed
  the same). `ésser` is the older, more formal infinitive of `ser`.
- **The subjunctive must be named**, always, because the gloss language
  almost certainly has no form to show it with: *vull que vinguis* comes into
  English as *I want you to come*. Write it after the entry:
  `\vb{venir}{}{vinc}{}{vingut}{}{to come (fut. \pw{vindré})}; here
  \pw{vinguis}, pres. subj. after \pw{voler que}`, and so `; here \pw{fos},
  imperf. subj.` for `ser`. **Name the trigger** with it — `voler que`,
  `perquè` (*so that*), `abans que`, `tant de bo`, `no crec que`, `quan` + a
  future, `si` + a condition contrary to fact — since the trigger is the whole
  of why the form is there. The imperfect subjunctive is `-és` in Central and
  Balearic and `-ara`/`-era` in Valencian (`parlés`/`parlara`,
  `tingués`/`tinguera`); both are correct, they are not corrected into one
  another, and the entry names whichever the source wrote.
- A **noun** carries its **gender**, every time, because the article in the
  text is so often elided into `l'` and shows none: `\dw{aigua}{} water, f.`;
  `\dw{home}{} man, m.`. A reader who knows Spanish is misled by the ones
  whose gender differs: `\dw{dent}{} tooth, f.`; `\dw{calor}{} heat, f.`;
  `\dw{anàlisi}{} analysis, f.`; `\dw{dubte}{} doubt, m.`; `\dw{costum}{}
  custom, m.`; `\dw{postres}{} dessert, f. pl.`. A plural that is not the
  noun plus `-s` is given with it: `\dw{mà}{} hand, f., pl. \pw{mans}`;
  `\dw{camió}{} lorry, m., pl. \pw{camions}`; `\dw{peix}{} fish, m., pl.
  \pw{peixos}`.
- An **adjective** is given in the masculine singular, with the feminine where
  it is not the masculine plus `-a` (`bo / bona`, `nou / nova`, `boig /
  boja`, `gros / grossa`, `blanc / blanca`); `bo` before its noun is `bon`
  (`un bon dia`), and that is named. Name what was stripped: the plural `-s`,
  `-os`, `-es`, the feminine, the diminutive (`-et`, `-ó`), the augmentative
  (`-às`), the absolute superlative (`-íssim`), the adverb's `-ment`.
- **The weak pronouns lean on the verb, and the entry is filed under the
  verb.** Before it they stand apart, or are written onto it with an
  apostrophe, and get no entry of their own (`em diu`, `li ho dono`, `m'agrada`,
  `l'he vist`, `se'n va`); after an infinitive, a gerund or an imperative they
  are written onto it with a hyphen or an apostrophe, and the whole is one
  word in the text: `menjar-lo`, `fer-ho`, `dona-m'ho`, `porta'l`,
  `explicant-t'ho`. Spell it out under its verb, after the entry: `; here
  \pw{dona-m'ho}, imperative + \pw{em} + \pw{ho} — give it to me`; `; here
  \pw{porta'l}, imperative + \pw{el} — bring it`. The pronoun changes shape
  with what is round it (`em`, `m'`, `-me`, `'m`, `me'n`) and is reproduced,
  never regularised. Two of them have no English counterpart and must be
  explained where a chunk turns on them: `hi` (*there*, *to it*, and the
  `hi` of `hi ha` *there is*) and `en` (*of it*, *some*, *from there*: `en
  tinc dos` *I have two (of them)*): `\dw{en}{} = of it / of them: \pw{en tinc
  dos}, I have two of them`. `ho` is the neuter *it*, for a whole idea (`no
  ho sé` *I do not know (it)*).
- **The article before a first name is not *the*.** Catalan puts `en`, `la`
  or `l'` before a person's name (`en Joan`, `la Maria`, `l'Anna`), and the
  Balearic `na` before a woman's; a reader glossing word by word gets *the
  Maria*, or reads `en` as *in*. It takes no entry of its own — it is in the
  never-gloss list below — but where the chunk's gloss could be misread, say
  it in the vocabulary line once: `\dw{en}{} the personal article: before a
  man's name, not "in"`.
- The line uses four macros and nothing else: `\dw{fa}{rom} gloss` ·
  `\vb{inf}{rom}{pres}{rom}{pp}{rom}{meaning}` · `\bw{base}{rom}{meaning}` ·
  `\pw{fa}` — plus `\textit`, `\emph`, `\nobreak` — and its entries are parted
  by `; `. `\vb` for every verb, `\dw` for every other headword; a `\dw`'s
  pronunciation slot follows the same rule as a `\vb`'s.
- A form in the text that is none of the three the `\vb` prints, nor one its
  parenthesis names, is named after the entry, outside it, with what it is:
  `\vb{parlar}{}{parlo}{}{parlat}{}{to speak}; here \pw{parlava}, 1/3sg
  imperf.`. A Valencian or Balearic form is named the same way, with the
  region: `; here \pw{parle}, 1sg pres. (Val.)`.

One equivalent in the gloss language rather than a string of synonyms; no
etymologies; **an empty `voc` is the right answer** for a chunk needing
nothing. The repetition rule is Frank's own: a full entry the **first time** a
word appears, briefer or none on later appearances.

The meaning is what the gloss language is for; the labels around it are not.
*pres.* and *p.p.* are printed by the edition itself — the same two words in
every Catalan book, out of the registry — so leave them, and `fut.`, `past`,
`imperf.`, `subj.`, `lit.`, `Val.`, the `f.`, the `m.` and the `pl.`, as they
are written above whatever the glosses are in: a line that translated the
labels and not the forms would be reading in two conventions at once. Where
the gloss language is Catalan, the meaning is a **definition** and not a
translation: commoner words than the headword, and never the headword's own
relatives. `docs/lang/en.md` sets that case out in full; it belongs to no one
language.

Which words the reader already owns turns on the gloss language, and the
judgement is yours: a word transparent from the reader's own language earns a
shorter entry or none. `important`, `nació` and `possible` say themselves to
a reader of English, Spanish, Italian or French and need no meaning, only what
the form is doing; to a reader of Persian, Turkish or Japanese they say
nothing at all. Judge from the gloss language, never from English — and beware
the ones that only look transparent (`embarassada` is pregnant, not
embarrassed; `constipat` has a cold; `actualment` is currently, not actually;
`llibreria` is a bookshop; and to a reader of Spanish, `cama` is a leg and not
a bed, `llevar` is to take away, `res` is nothing, `sopar` is dinner), which
are worth a full entry precisely because the reader will not stop for them.

## Never gloss

The articles, the simple prepositions and their contractions, the pronouns,
the weak pronouns and the commonest conjunctions never get a vocabulary
entry:

```
el la els les l' un una uns unes en na es sa ses
a de d' en amb per sense sobre entre fins des cap contra segons
al als del dels pel pels can cal
jo tu ell ella vostè nosaltres vosaltres ells elles vostès mi
em et es ens us li el la els les ho hi en m' t' s' n' l' me te se ne
i o ni però sinó que si no
```

`per` and `per a`, and `hi` and `en`, are on that list as words and not as a
problem: none is glossed on its own, and where a chunk turns on one the verb
or the noun that governs it carries the explanation. `can` and `cal` (`ca` + `en`, `ca` + `el`: *the house of*) begin many a
place name (`Can Serra`, `cal metge`) and take no entry; the verb `cal` (*it is
needed*) is another word, and is glossed under `caldre`.

## Chunking

A chunk is a sense group of roughly **2–6 words** — a verb with its object, a
noun with its adjective, a preposition with its noun: something a reader
hovers and that *means* something on its own. A very short sentence (`Sí.`,
`Vine!`) is one chunk; that is normal and not a fault.

Never split:

- an **article from its noun** (`la casa`, `el meu germà`), or a
  **contraction from what it governs** (`al final`, `del poble`, `pel
  carrer`) — `al`, `del`, `pel` are `a`/`de`/`per` with the article
  swallowed and are half a phrase on their own;
- a **preposition from its object** (`a la taula`, `amb el meu germà`), and the
  **personal article from its name** (`en Joan`, `la Maria`);
- a **weak pronoun from its verb** (`em diu`, `li ho dono`, `ens n'anem`):
  it is unglossable alone, and the dictionary calls it a pronoun, so only this
  rule keeps it on the verb;
- the **`va` of the past from its infinitive** (`vaig parlar`, `va dir`,
  `van arribar`): `va` alone reads as *goes*;
- a **negation from its verb** (`no ho sé`, `no m'ho va dir`), including the
  second negative Catalan keeps (`no vaig veure ningú`, `no en tinc cap`, `no
  és pas veritat`);
- an **auxiliary from what it carries**: `he vist`, `havia arribat`, `està
  parlant`, `acaba de sortir`, `continua plovent`, `ha de venir`;
- a **noun from the adjective after it** (`la casa gran`), which is where
  Catalan puts it, nor from the short ones that come before (`bon dia`, `una
  gran cosa`);
- a **fixed expression**, whatever its syntax: `tenir ganes de`, `fer falta`,
  `hi ha`, `cal que`, `adonar-se de`, `és a dir`, `de seguida`, `per cert`,
  `tot i que`. The meaning is not in the pieces, and showing the pieces
  teaches the reader something untrue.

`que` and the other relativisers open the chunk they introduce rather than
closing the one before them (`Vull | que vinguis`). The elided and the
attached forms need no rule: `l'home`, `m'agrada`, `menjar-lo`, `dona-m'ho`
are written without a space, so there is no gap for a cut to fall in.

## Example

One sentence of Catalan, answered: its chunks as they stand in the list of your
answer. The `en` of each chunk says only what that chunk says, in the order of
the Catalan.

```json
{"chunks": [
  {"fa": "Ahir vaig parlar", "tr": "{{?classic}}əí vatʃ pərlá{{/classic}}{{?ipa}}əˈi ˈbatʃ pəɾˈla{{/ipa}}", "voc": "\\vb{parlar}{}{parlo}{}{parlat}{}{to speak, to talk}; here \\pw{vaig parlar}, 1sg past (\\pw{va} + inf.)", "en": "yesterday I spoke"},
  {"fa": "amb la Maria", "voc": "\\dw{la}{} the personal article: before a woman's name, not \"the\"", "en": "with Maria"},
  {"fa": "a la porta del mercat.", "tr": "{{?classic}}ə lə pòrtə dəl mərkát{{/classic}}{{?ipa}}ə lə ˈpɔɾtə dəl məɾˈkat{{/ipa}}", "voc": "\\dw{porta}{{{?classic}}pòrta{{/classic}}{{?ipa}}ˈpɔɾtə{{/ipa}}} door, f.; \\dw{mercat}{} market, m.", "en": "at the door of the market."}
]}
```

Notice: the first chunk has a `tr` for the `ahir` whose `h` and `r` are not
said, and the third for the open `o` of `porta`, which the spelling does not
show — so the `\dw` of `porta` fills its sound slot too; the second needs none,
the rules saying all there is to say. `vaig parlar` stays one chunk and is
glossed as the past under `parlar`, never as *I go*; the personal article is
explained once and is not rendered as *the*; and every noun carries its
gender.

{{?note}}No speaker has reviewed this example yet.{{/note}}
