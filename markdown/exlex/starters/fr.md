---
title: New French note
subtitle: A tour of everything a note can hold, with a little French on the way
note: A demo page: keep what you need and delete the rest
lang: en
target: fr
---

> **This page is a demo** of everything a note can contain: text, French with its pronunciation,
> vocabulary entries, tables, notes, links, formulas, pictures, a recording, a video and every
> kind of exercise. Keep what you need and delete the rest; each section stands on its own.
>
> French is written in the same alphabet as the English around it, so nothing picks it out by
> itself. **Every French word on this page is marked**, and yours need to be marked as well.

## Plain text

Lines that follow each other join into one paragraph, and a blank line starts the next one.
Words can be **bold**, *italic*, or set as `inline code`, like the `target: fr` line at the top of
the source, which is what makes this a French note.⏎
After a return sign, this sentence starts on a line of its own without starting a new paragraph.

An arrow shows where one thing leads: [à]{tl} + [le]{tl} → [au]{tl}. Typed as a hyphen and a
greater-than sign, it is the same arrow: [de]{tl} + [le]{tl} -> [du]{tl}. A cross marks a form that
is wrong and a green tick the form that is right: ✗[à le marché]{tl} → ✅ [au marché]{tl}.

### Lists

A bullet list starts each line with a dash, and a line indented by two spaces sits one level in:

- [le pain]{tl} = *bread*
- [le fromage]{tl} = *cheese*
- [les pommes]{tl} = *apples*
  - and just one: [une pomme]{tl} = *an apple*

A numbered list starts each line with a number and a full stop; the numbers are counted for you:

1. Mark the French word.
2. Add how it is said.
3. Give its meaning after an equals sign, in italics.

When every item opens with a bold label, the list is laid out as a list of terms:

- **By day** [Bonjour !]{tl} = *Hello!*
- **In the evening** [Bonsoir !]{tl} = *Good evening!*
- **At bedtime** [Bonne nuit !]{tl} = *Good night!*
- **On leaving** [Au revoir !]{tl} = *Goodbye!*

## French on the page

A word in square brackets followed by `{tl}` is French: [bonjour]{tl}. The note's own language
code, `fr`, does the same job: [merci]{fr}. Persian, Arabic, Hindi, Japanese and Chinese are
recognised by their script alone, but French never is, so every French word, phrase and sentence
gets a mark. Bold works on French as well: **[Attention !]{tl}** = *Watch out!*

### Pronunciation

A mark can carry the pronunciation, which appears when you hover over the word:
[s'il vous plaît]{translit:sil vou plè} = *please*. A colour and a pronunciation can share the
braces: [Bonjour]{teal translit:bõʒour} = *hello*.

The pronunciation is written in the toolbox's French respelling. The nasal vowels are ã, ẽ and õ;
ʃ, ʒ and ɲ are the sounds of *ch*, *j* and *gn*; silent letters are left out; and a hyphen marks
a liaison, as in [les amis]{translit:lé-zami} = *the friends*. A Japanese note can also give a
word its reading in kana; French has no such reading, so the pronunciation is all it needs.

### Colours

Five colour names can follow a word: [rouge]{crimson}, [bleu]{indigo}, [vert]{teal},
[violet]{violet} and [ambre]{amber} (*red, blue, green, purple, amber*). Any other colour is a #
and six hex digits: [rose]{#C2185B} = *pink*.

> **French spelling keeps every mark.** Copy a French text exactly as it is written:
>
> - the accents, which can change the word: [ou]{tl} = *or*, but [où]{tl} = *where*
> - the cedilla and the ligature œ: [ça]{tl}, [français]{tl}, [sœur]{tl}, [cœur]{tl}
> - the apostrophe of elision: [l'homme]{tl}, [aujourd'hui]{tl}
> - the space before ; : ! ? and inside « »: [Vraiment ?]{tl}, [« Oui »]{tl}

### Whole paragraphs and blocks

A whole paragraph in square brackets with `{tl}` after it is a French paragraph, set in the
French face:

[Le samedi matin, nous allons au marché. Nous achetons du pain, du fromage et des pommes, puis
nous rentrons à la maison pour déjeuner.]{tl}

A block can also open with a bracket on a line of its own and close with the bracket and its
braces on the last line. A return sign at the end of a line keeps the break, and `bg=` gives the
block a tint (quote, sand, rose, sage or lilac). Here is a poem by Paul Verlaine, from 1874:

[
Il pleure dans mon cœur⏎
Comme il pleut sur la ville ;⏎
Quelle est cette langueur⏎
Qui pénètre mon cœur ?
]{tl bg=quote}

And a short exchange at the baker's:

[
— Bonjour ! Une baguette, s'il vous plaît.⏎
— Voilà. Ce sera tout ?⏎
— Oui, merci. Bonne journée !
]{tl bg=sand}

Three things you may meet in notes for other languages do not apply to French. A display line,
a paragraph of nothing but the target script set large, needs a script the studio recognises on
its own, and French shares its alphabet with English. The `font=` option picks a language's
second typeface, and French has only one. Vertical setting is for Japanese and Chinese only.

## Vocabulary entries

A heading made of parts separated by vertical bars is a vocabulary entry: the word, how it is
said, where it comes from, and after an equals sign the meaning, which is not printed but goes
into the glossary. The origin may be left out, as in the second entry. The word may carry its own
colour and pronunciation, as in the third, whose empty second part takes the pronunciation from
the word's mark.

## fromage | fròmaʒ | Old French *formage*, from Latin *formaticus*, shaped in a mould | = *cheese*

- **gender** masculine: [le fromage]{tl}, [un fromage]{tl}
- **example** [Encore un peu de fromage ?]{tl} = *A little more cheese?*
- **the shop** [la fromagerie]{tl} = *cheese shop*

## maison | mèzõ | = *house*

- **gender** feminine: [la maison]{tl}
- **phrase** [à la maison]{tl} = *at home*
- **example** [Nous rentrons à la maison.]{tl} = *We are going home.*

## [pomme]{teal translit:pòm} | | from Latin *pōma*, fruits | = *apple*

- **gender** feminine: [la pomme]{tl}, [une pomme]{tl}
- **example** [Je mange une pomme.]{tl} = *I am eating an apple.*
- **idiom** [tomber dans les pommes]{tl} = *to faint* (word for word, to fall into the apples)

## Tables

A table is rows of cells between vertical bars. The line under the header sets each column's
alignment with colons (left, centred, right), and a cell holding only two dashes is empty:

| Masculine | Before a vowel | Feminine | Meaning |
|:---|:---:|:---:|---:|
| [beau]{tl} | [bel]{tl} | [belle]{tl} | beautiful |
| [vieux]{tl} | [vieil]{tl} | [vieille]{tl} | old |
| [nouveau]{tl} | [nouvel]{tl} | [nouvelle]{tl} | new |
| [blanc]{tl} | -- | [blanche]{tl} | white |

## Notes and links

A footnote is a mark like this one[^1], with its text written on a line of its own that starts
with the same mark; a longer text goes on in lines indented by two spaces.

A short note can also be written right where it belongs, inside the sentence.^[The h of
[homme]{tl} is silent, so the article loses its vowel: [l'homme]{tl}.]

[^1]: A liaison sounds a final consonant that is otherwise silent, when the next word
  begins with a vowel: [les amis]{translit:lé-zami}, but [les copains]{translit:lé kòpẽ}.

A web link opens in a new tab: [a short open film](https://www.youtube.com/watch?v=aqz-KE-bpKQ).

A link to another note points to that note's name, which is its title:
[another note](doc:My second French note). Left without a label, it shows the title itself:
[](doc:My second French note). A link to a name that no note has yet is shown as a dangling
link; create a note with that title and the link works.

## Latin blocks

A paragraph in square brackets with `{la}` after it is a Latin block: a paragraph in the note's
own language, English here, set apart with its own width, shift, alignment and tint. It exists
for notes that run right to left or vertically, where a paragraph of English needs a box of its
own; in a French note it is a handy way to set a remark apart.

[Lines centred, on a sand tint, four fifths of the column wide: a good place for a rule of thumb,
such as *a final c, r, f or l is usually sounded*.]{la align=center bg=sand width=80}

[Pushed a tenth of the column to the right, on a sage tint, and a little
narrower.]{la width=70 offset=10 bg=sage}

## Mathematics

A formula is written in LaTeX notation: in square brackets followed by `{math}` when it sits in
a sentence, and between two fence lines when it stands on its own.

Past sixty, French builds its numbers from sums and twenties, [70 = 60 + 10]{math} and
[80 = 4 \times 20]{math}: seventy is [soixante-dix]{tl}, *sixty-ten*, and eighty is
[quatre-vingts]{tl}, *four twenties*. So ninety-nine is:

:::math
\text{quatre-vingt-dix-neuf} = 4 \times 20 + 10 + 9 = 99
:::

## Pictures, recordings and video

A picture sits on a line of its own. Its caption goes in the square brackets and cannot hold
brackets itself, so it is written in plain words; its width, side and offset go in the braces.
Here is [une pomme]{tl}, centred:

![An apple](images/starter-apple.svg){width=40 align=center}

and [une maison]{tl}, on the left and pushed a tenth of the column in:

![A house](images/starter-house.svg){width=30 align=left offset=10}

A recording is written the same way, with its file in the audio folder. Record yourself saying a
word or a sentence and put it in place of this chime:

![A short chime](audio/starter-chime.mp3)

A recording can be laid out like a picture and cut to the stretch you want to hear:

![The chime, its first note only](audio/starter-chime.mp3){width=50 align=center start=0 end=0.4}

A video line starts with @ and plays the stretch between its start and end:

@[A short film](https://www.youtube.com/watch?v=aqz-KE-bpKQ){width=70 align=center start=0:10 end=0:40}

## Exercises

Each exercise below is written between two fence lines, and the source shows every option it
uses. To make your own with a form, open the editor's **Exercises** menu and choose **Add
exercise…**. A **Check exercises** button at the end of the page marks your answers.

### Putting things in place

:::exercise fill-blanks
prompt: Complete the sentence with the right verbs.
content-direction: target
text: [Le matin, je [[drink]] un café et je [[read]] le journal.]{tl}
- [drink] [bois]{tl}
- [read] [lis]{tl}
- [ ] [boit]{tl}
- [ ] [lit]{tl}
explanation-correct: With [je]{tl}, both verbs end in -s: [je bois]{tl}, [je lis]{tl}.
:::

:::exercise order-sentences
prompt: Put this Saturday morning in order.
- [1] [Je me réveille à huit heures.]{tl}
- [2] [Je me lève et je prends une douche.]{tl}
- [3] [Je m'habille et je prends mon sac.]{tl}
- [4] [Enfin, je vais au marché.]{tl}
:::

:::exercise construct-sentence
prompt: Build the sentence: *On Saturday mornings we go to the market to buy fruit and vegetables.*
- [1] [Le samedi matin,]{tl}
- [2] [nous allons]{tl}
- [3] [au marché]{tl}
- [4] [pour acheter]{tl}
- [5] [des fruits et des légumes.]{tl}
:::

### Matching

:::exercise match-translations
prompt: Match each word or picture with its French name.
- bread => [le pain]{tl}
- cheese => [le fromage]{tl}
- water => [l'eau]{tl}
- ![An apple](images/starter-apple.svg) => [la pomme]{tl}
:::

:::exercise match-opposites
prompt: Match each word with its opposite.
- [grand]{tl} => [petit]{tl}
- [chaud]{tl} => [froid]{tl}
- [le jour]{tl} => [la nuit]{tl}
- [ouvrir]{tl} => [fermer]{tl}
:::

:::exercise match-definitions
prompt: Match each place with what it does.
direction: word-to-definition
- [la boulangerie]{tl} => a shop that bakes and sells bread
- [la librairie]{tl} => a shop that sells books
- [la bibliothèque]{tl} => a place that lends books
- [la pharmacie]{tl} => a shop that sells medicine
:::

### Choosing

:::exercise yes-no
prompt: Is the last consonant sounded? Say each word aloud, then choose. ⏎ [The player holds a placeholder chime: record the four words and put your file in its place.]{no-bold}
audio: audio/starter-chime.mp3 {width=50 align=center}
- [petit]{tl} => no
- [le chef]{tl} => yes
- [le sport]{tl} => no
- [le sac]{tl} => yes
explanation-correct: A final c, r, f or l is usually sounded (think of the English word *careful*); most other final consonants are silent.
:::

:::exercise true-false
prompt: True or false?
- [pain]{tl} is a feminine noun. => false
- [le]{tl} + [homme]{tl} \=> [l'homme]{tl}, because the h is silent. => true
- In [les amis]{tl} the s of [les]{tl} is sounded as a z, because the next word begins with a vowel; this link between two words is called a liaison, and it is never made after [et]{tl}, *and*. => true
- French typography puts a space before a question mark. => true
:::

:::exercise single-choice
prompt: What is this?
image: images/starter-house.svg {width=30 align=center}
- [ ] [un arbre]{tl}
- [x] [une maison]{tl}
- [ ] [une voiture]{tl}
explanation-correct: Yes: [une maison]{tl}, *a house*.
explanation-incorrect: It is [une maison]{tl}, *a house*; [un arbre]{tl} is a tree and [une voiture]{tl} a car.
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *apple*?
image-answer: images/starter-apple.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] [la pomme]{tl}
- [ ] [la poire]{tl}
- [ ] [le pain]{tl}
explanation-correct: [la pomme]{tl} is an apple; [la poire]{tl} is a pear and [le pain]{tl} bread. The chime stands in for the word said aloud.
:::

:::exercise single-choice
prompt: Which is the polite way to order? ⏎ [A hint: to a waiter you do not know, say [vous]{tl}, not [tu]{tl}.]{no-bold}
- [x] [Je voudrais un café, s'il vous plaît.]{tl}
- [ ] [Donne-moi un café.]{tl}
- [ ] [Un café, vite !]{tl}
explanation-correct: Right: [je voudrais]{tl}, *I would like*, and [s'il vous plaît]{tl}, *please*, make the request polite.
explanation-incorrect: The polite one asks with [je voudrais]{tl}, *I would like*, and ends with [s'il vous plaît]{tl}, *please*. [Donne-moi]{tl} is said to someone you call [tu]{tl}, and [vite]{tl} means *quickly*.
:::

:::exercise incorrect-part
prompt: One part of this sentence is wrong. Which one?
- [ ] [Hier soir,]{tl}
- [x] [nous avons allé]{tl}
- [ ] [au cinéma]{tl}
- [ ] [avec des amis.]{tl}
explanation-correct: Right: [aller]{tl} makes its past with [être]{tl}, so [nous sommes allés]{tl}.
explanation-incorrect: The wrong part is [nous avons allé]{tl}: [aller]{tl} makes its past with [être]{tl}, so [nous sommes allés]{tl}.
:::

:::exercise choose-all
prompt: Choose every feminine noun.
- [x] [maison]{tl}
- [ ] [soleil]{tl}
- [x] [eau]{tl}
- [ ] [fromage]{tl}
- [x] [nuit]{tl}
explanation-correct: [la maison]{tl}, [l'eau]{tl} and [la nuit]{tl} are feminine; [le soleil]{tl} and [le fromage]{tl} are masculine.
:::

:::exercise odd-one-out
prompt: Which one is not a fruit?
- [ ] [la pomme]{tl}
- [ ] [la poire]{tl}
- [x] [le pain]{tl}
- [ ] [la cerise]{tl}
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: At the bakery a customer says: [Bonjour ! Je voudrais un café et une baguette, s'il vous plaît.]{tl} Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then some bread.
::::exercise single-choice
prompt: What does the customer want to drink?
- [x] [un café]{tl}
- [ ] [une baguette]{tl}
- [ ] [un journal]{tl}
explanation-correct: [Un café]{tl}, *a coffee*; the bread is [une baguette]{tl}.
::::
::::exercise true-false
prompt: Now decide.
- [Une baguette]{tl} is a kind of bread, and [baguette]{tl} is a feminine noun. => true
- [S'il vous plaît]{tl} means *thank you*. => false
explanation-correct: [S'il vous plaît]{tl} is *please*; *thank you* is [merci]{tl}.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the words you have just read.
content-direction: target
text: [Bonjour ! Je voudrais [[drink]] et [[bread]], s'il vous plaît.]{tl}
- [drink] [un café]{tl}
- [bread] [une baguette]{tl}
- [ ] [un baguette]{tl}
explanation-correct: [Un café]{tl} is masculine and [une baguette]{tl} feminine.
::::
:::

### Flashcards

A flashcard turns over when you click it. A vocabulary card has the word on the front and its
meaning on the back, here with a speaker button that plays the recording its `back-audio:` names
(the chime, where the word said aloud would go) without turning the card:

:::exercise flashcard
card-type: vocab
target: [la boulangerie]{tl}
transliteration: la boulãʒri
meaning: bakery
context: [Je passe à la boulangerie.]{tl} = *I'm stopping by the bakery.*
notes: feminine; the baker is [le boulanger]{tl}
back-audio: audio/starter-chime.mp3
:::

An opposites card has a word on the front and its opposite on the back:

:::exercise flashcard
card-type: opposites
target: [chaud]{tl}
transliteration: ʃo
opposite: [froid]{tl}
opposite-transliteration: frwa
notes: hot and cold
:::

A free card has two fields on each side, and each field can hold anything the page can: here a
picture on the front and a recording and a list on the back, with sizes and shades of their own.

:::exercise flashcard
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=45 align=center}
front-secondary: What is it called in French?
back-primary: [une pomme]{teal translit:ün pòm}
back-secondary: |
  ![A short chime](audio/starter-chime.mp3){width=80 align=center}

  - **gender** feminine: [la pomme]{tl}
  - **plural** [les pommes]{tl}
front-primary-size: 130
front-secondary-shade: muted
back-primary-size: 150
back-primary-shade: accent
back-secondary-size: 90
:::
