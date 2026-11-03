---
title: Writing Catalan
linkTitle: Catalan
weight: 12
description: target ca — a Latin-script target, every run marked; section titles without |; a pronunciation where the spelling does not say it, the stressed vowel always marked in it.
target: ca
---

`target: ca` — Catalan, *català*, written left to right in the Latin
alphabet: the studio cannot tell it from the prose, so every run of it is
marked. The reference is Central Catalan as the Institut d'Estudis
Catalans writes it; a Valencian or Balearic text is glossed as it is
written.

## Every run is marked

Any mark sets a word or a group as Catalan: `[…]{tl}`, Catalan's code
`[…]{ca}`, a colour, a pronunciation, or any other word in the braces but
`la`, `ltr` and `math`.

```parseh-example
---
target: ca
---
[bon dia]{translit:bòn día} = *good morning*, [la gent]{teal translit:lə ʒén} = *the people*,
and [el carrer]{ca} = *the street*.

[On és l'estació?]{tl bg=rose}
```

A whole paragraph marked `[…]{tl}` is a block, and takes `bg=`; inside a
line the options are not read. A wrong form is a marked run after `✗`:
`✗[sabo]{tl}`.

## What belongs to a word

The apostrophe, the hyphen and the middle dot are inside a Catalan word,
and a run keeps them: an elided article or pronoun in front
(`[l'home]{tl}`, `[m'agrada]{tl}`), the pronouns written after a verb
(`[menjar-lo]{tl}`, `[porta'l]{tl}`, `[dona-m'ho]{tl}`) and the long `l`
of `[col·lecció]{tl}`. The dictionary takes each of them apart when a word
is looked up: `l'home` is found as *home*, `porta'l` as *portar*, and
`al`, `del`, `pel` and `can` are pages of their own.

## Face

Catalan is set in the prose's own face, **TeX Gyre Pagella**, at the
prose's size; it has no second face and is not set vertically.

## Vocabulary entries

Any `##` heading with two parts or more is a vocabulary entry, so **a
section title in a Catalan document cannot hold a `|`**.

```parseh-example
---
target: ca
---
## fill | fiʎ | Latin *filius* | = *son*

## [carrer]{teal translit:kərré} | | = *street*
```

A verb's entry gives the infinitive, the first person of the present and
the past participle — `\vb{parlar}{}{parlo}{}{parlat}{}{to speak}` — and
the everyday past, *va* with the infinitive (*va parlar*), is read off the
first.

## Pronunciation

Catalan spelling says less of its sound than Spanish or Italian spelling,
so more words earn a pronunciation, and **its stressed vowel always carries
an accent there** — once the other vowels have gone to `ə` the stress is
what holds the word together:

- **open and closed e and o**: `è` /ɛ/ and `é` /e/, `ò` /ɔ/ and `ó` /o/
  (*porta* `pòrtə`, *boca* `bókə`);
- **the neutral vowel**: unstressed `a` and `e` are `ə`, unstressed `o` is
  `u` (*casa* `kázə`, *parlar* `pərlá`, *poder* `pudè`);
- **letters not said**: an infinitive's final `r`, a `t` after `l` or `n`,
  a `b` after `m`, and `h` (*molt* `mól`, *amb* `əm`, *home* `òmə`);
- **`x`** is `ʃ` (*caixa* `káʃə`), **`ll`** `ʎ`, **`ny`** `ɲ`, **`tx`** and
  a final **`ig`** `tʃ` (*cotxe* `kòtʃə`), **`j`** and **`g`** before e or i
  `ʒ` (*jove* `ʒòvə`);
- **`l·l`** is a long `l`, written `ll` (*col·lecció* `kulləksió`);
- a single **`s`** between vowels, and **`z`**, are `z` (*casa* `kázə`).

```parseh-example
---
target: ca
---
[la platja]{translit:lə pládʒə}, [el cotxe]{translit:əl kòtʃə}, [l'aigua]{teal translit:láigwə}.
```

With **IPA** chosen in a prompt the line is broad IPA of Central Catalan
instead. Catalan has **no reading**: `kana:` means nothing here.
