---
title: New Japanese note
subtitle: a guided tour of everything a note can hold
note: a demo page: keep what you need and delete the rest
lang: en
target: ja
---

> **This page is a demo.** It shows, one after another, everything a note can contain, each
> with a small piece of real Japanese. Keep what you need and delete the rest. The source is
> open in the editor beside the preview, so you can see how each thing is written.

## Writing prose

A note is written in Markdown, plain text with a few signs in it. A line that starts with `##`
is a numbered section, like the one above, and `###` starts a subsection inside it.

### Emphasis and code

Two asterisks make text **bold**, one makes it *italic*, and backticks set it in `code` type.
On a computer Japanese is usually typed in rōmaji: type `nihongo`, press the space bar, and the
input method offers 日本語.

### Lists

A dash starts a bullet list, and an item indented by two spaces sits one level down:

- おはようございます *ohayō gozaimasu*, good morning
- こんにちは *konnichiwa*, hello
  - its last kana is は, said *wa* here, as the topic particle is
- こんばんは *konbanwa*, good evening

A number and a full stop start a numbered list, which counts by itself:

1. Switch the keyboard to Japanese input.
2. Type the word in rōmaji: `taberu`.
3. Press the space bar and choose 食べる from the list.
4. Press Enter to keep it.

When every item starts with a **bold label**, the list is laid out as labels and explanations:

- **は** *wa* marks the topic, what the sentence is about.
- **を** *o* marks the direct object.
- **に** *ni* marks a time, or the place something goes to.

### Arrows, right and wrong forms, line breaks

An arrow shows where a form leads: 食べる → 食べます → 食べました, *taberu* (to eat) →
*tabemasu* (polite) → *tabemashita* (polite past). A hyphen and a greater-than sign make the
same arrow: 飲む -> 飲みます, *nomu* -> *nomimasu*, to drink.

A cross marks a wrong form and a tick the right one. The topic particle is said *wa* but
written with the kana for *ha*: ✗私わ学生です。 ✅ 私は学生です。

A line can be broken without starting a new paragraph, the way a sign stacks
its words:⏎入口 *iriguchi*, entrance⏎出口 *deguchi*, exit

## Japanese in the text

Japanese needs no mark: its script is enough for the page to recognise it and set it in the
Japanese font, like 日本語 *nihongo* here. Two asterisks around it make it bold: **日本語**.
A word followed by an equals sign and an italic meaning is a gloss, 水 = *water*: the sign
turns grey and the word goes into the note's glossary.

Japanese is written without spaces, and the lines of one paragraph are joined with a space,
so keep each Japanese sentence on one line of the source.

> **Three scripts in one sentence.** 私はコーヒーを飲みます。 *watashi wa kōhī o nomimasu*,
> I drink coffee.
>
> - **Kanji** 私 and 飲 carry the meaning.
> - **Hiragana** は, を and みます carry the grammar.
> - **Katakana** コーヒー is a word borrowed from abroad.

A word in square brackets followed by `{tl}` is marked as Japanese by hand. That is needed
when Latin letters or figures belong to the Japanese: [Tシャツ]{tl} *tīshatsu*, a T-shirt,
stays one word, and so does [3時]{tl} *sanji*, three o'clock.

A paragraph with no Latin letters in it is laid out as a Japanese block by itself, figures
and all:

毎朝7時に起きて、8時に家を出ます。

That is *maiasa shichiji ni okite, hachiji ni ie o demasu*, every morning I get up at seven
and leave home at eight. A paragraph made only of Japanese characters and Japanese
punctuation is a display line, set larger:

猿も木から落ちる。

The proverb, *saru mo ki kara ochiru*, says that even monkeys fall from trees. A Japanese
paragraph with Latin letters in it is marked as a whole:

[週末はDVDで映画を見ます。]{tl}

That is *shūmatsu wa DVD de eiga o mimasu*, at weekends I watch films on DVD.

### Blocks of Japanese

A passage of several lines is marked the same way, with its brackets on lines of their own
and the line-break sign at the end of every line but the last; the pencil button named
**Japanese** above the editor opens a box to write one in. Words after `tl` style the block:
`bg=` tints it, with `quote`, `sand`, `rose`, `sage` or `lilac`. Here is a first meeting, on
sand:

[
「はじめまして。どうぞよろしくお願いします。」⏎
「こちらこそ、よろしくお願いします。」
]{tl bg=sand}

That is *hajimemashite. dōzo yoroshiku onegai shimasu*, how do you do, pleased to meet you;
and *kochira koso, yoroshiku onegai shimasu*, the pleasure is mine.

A haiku by Yosa Buson, tinted as a quotation:

[菜の花や　月は東に　日は西に]{tl bg=quote}

That is *na no hana ya / tsuki wa higashi ni / hi wa nishi ni*: rapeseed flowers; the moon
in the east, the sun in the west. `font=gothic` sets a block in the plain sans-serif face of
signs and screens, here on a rose tint:

[本日休業]{tl font=gothic bg=rose}

It reads *honjitsu kyūgyō*, closed today, as a shop door would say it. Last, `vertical`
writes a block from top to bottom, in columns that follow each other from right to left, as
books and poems often are; `height` sets how tall the columns are. Matsuo Bashō's frog:

[
古池や⏎
蛙飛び込む⏎
水の音
]{tl vertical height=8}

[The old pond / a frog jumps in / the sound of the water.]{la align=center bg=sand}

### Latin blocks

The translation under the poem is a Latin block: English, or whatever language the note is
written in, set apart as a block of its own, which is what a translation needs beside
vertical Japanese. Its lines can be centred and the block tinted, as above, or the block
narrowed and moved like a picture:

[In rōmaji the haiku is *furuike ya / kawazu tobikomu / mizu no oto*. This block is 80% of
the column wide and starts 10% in from its left edge.]{la width=80 offset=10 bg=lilac}

## Readings and rōmaji

Any Japanese word can carry its reading in kana, its rōmaji, or both. On screen they appear
when the pointer rests on the word; on paper the word is printed alone. The **kana** button
above the editor wraps the selected word in a reading mark, ready for its kana. Easier still,
rest the pointer on a Japanese word in the preview: a small cloud opens with a field for its
kana, one for its rōmaji and a row of colours, and whatever you type or pick there is written
into the source for you.

- [漢字]{kana:かんじ} has its reading only.
- [東京]{translit:Tōkyō} has its rōmaji only.
- [日本語]{kana:にほんご translit:nihongo} has both.
- [先生]{teal translit:sensei} has a colour and its rōmaji in the same braces.
- [学校]{indigo kana:がっこう translit:gakkō} has a colour, its reading and its rōmaji.

Rōmaji here is Hepburn: long vowels take a macron (ō, ū), and particles are spelt as they
sound, so は is *wa* when it marks the topic.

## Colours

Five colours have names: [赤]{crimson} *aka*, red, in crimson; [青]{indigo} *ao*, blue, in
indigo; [緑]{teal} *midori*, green, in teal; [紫]{violet} *murasaki*, purple, in violet; and
[黄色]{amber} *kiiro*, yellow, in amber. Any other colour is written as a hex code, as for
[茶色]{#8B4513} *chairo*, brown. 青 covers some greens too: a green traffic light is
青信号 *aoshingō*.

## Vocabulary entries

A heading whose first part is Japanese, with its parts divided by upright bars, is a
vocabulary entry: the word set large, then its reading in kana, its rōmaji and a note on
where it comes from. A last part made of an equals sign and an italic meaning is printed
nowhere but puts the word into the glossary. The second entry leaves out the note on origin,
and the third tints its headword, carrying the rōmaji in the headword's own mark.

## 日本語 | にほんご | nihongo | 日本 *Nihon* ‘Japan’ + 語 *go* ‘language’ | = *the Japanese language*

- **Meaning** the Japanese language.
- **Example** 日本語を勉強しています。 *nihongo o benkyō shiteimasu*, I am studying Japanese.
- **Related** 英語 *eigo*, English; 中国語 *chūgokugo*, Chinese: the names of languages end in 語.

## 食べる | たべる | taberu | = *to eat*

- **Class** ichidan verb, transitive.
- **Forms** stem 食べ *tabe*, as in 食べます *tabemasu*; -te form 食べて *tabete*.
- **Example** 毎朝パンを食べます。 *maiasa pan o tabemasu*, I eat bread every morning.

## [猫]{teal translit:neko} | ねこ | = *cat*

- **Meaning** cat.
- **Example** 猫が好きです。 *neko ga suki desu*, I like cats.

## Tables

A table is drawn with upright bars. The colons in the line under the header align a column
to the left, the centre or the right, and a cell holding only two dashes is left empty.

| Meaning | Kanji | Kana | Strokes |
|:---|:---:|:---:|---:|
| mountain | 山 | やま *yama* | 3 |
| water | 水 | みず *mizu* | 4 |
| to eat | 食べる | たべる *taberu* | 9 |
| television | -- | テレビ *terebi* | -- |

The last column counts the strokes of the kanji; テレビ, a borrowed word, has no kanji at all.

## Notes and links

Japanese has many words that sound alike.[^1] On screen a note opens when the pointer rests
on its number; on paper it goes to the foot of the page. The **note** button above the editor
asks for the note's text and writes both halves for you.

[^1]: 箸 *hashi*, chopsticks; 橋 *hashi*, bridge; and 端 *hashi*, edge, are all read はし.
  The kanji tell them apart in writing, and in Tokyo speech so does the pitch of the voice,
  most clearly when a particle follows.

A note can also be written straight into the sentence,^[In kana all three are written the
same way, [はし]{tl}.] and the notes are numbered in order, whichever way they were written.

A link to a web page opens in a new tab:
[the short film shown further down](https://www.youtube.com/watch?v=aqz-KE-bpKQ).

A link to another note uses that note's name, its title:
[another note](doc:My second Japanese note) leads to the note called “My second Japanese
note”, and [](doc:My second Japanese note), with nothing between its brackets, shows that
note's title as its text. Until a note with that title exists, the link is shown as a dangling
link; create a note with that title and the link works. **Doc link…** above the editor picks
the note from a list and writes the link for you.

## Mathematics

A formula in square brackets followed by `{math}` sits in the line. The kana chart is called
五十音 *gojūon*, the fifty sounds, after its grid of [5 \times 10 = 50]{math} places, though
the basic set in use today has 46 kana.

A formula on lines of its own goes between `:::math` and `:::`; **∑ Maths** above the editor
writes either kind with the formula drawn beside it as you type. A haiku counts its sounds,
five, seven and five:

:::math
\underbrace{5}_{\text{fu-ru-i-ke-ya}}
+ \underbrace{7}_{\text{ka-wa-zu-to-bi-ko-mu}}
+ \underbrace{5}_{\text{mi-zu-no-o-to}} = 17
:::

## Pictures, recordings and video

A picture sits on a line of its own. The words in its square brackets are its caption, and
the braces after it give its width as a share of the column, its side, and a shift:

![An apple: りんご, *ringo*](images/starter-apple.svg){width=40 align=center}

![A house: 家, *ie*](images/starter-house.svg){width=30 align=left offset=10}

A recording is written the same way, with its file in `audio/`; on paper it becomes a card
that names the file:

![A chime: ピンポーン, *pinpōn*](audio/starter-chime.mp3){width=60 align=center}

`start=` and `end=` in the braces, in seconds or in minutes and seconds, play only a stretch of
it; this one is its first note alone, the ピン *pin*:

![The chime's first note: ピン, *pin*](audio/starter-chime.mp3){width=50 align=center start=0 end=0.4}

A video starts with `@` and takes a YouTube address; `start` and `end` play only a stretch of
it. This film has no words: describe what you see in Japanese as it plays.

@[A short animated film](https://www.youtube.com/watch?v=aqz-KE-bpKQ){width=70 align=center start=0:10 end=0:40}

You need not type any of these lines: the **Image**, **Audio** and **Video** buttons above the
editor write them for you. In the preview a click on a picture, or on the **layout** button of
a recording or a film, opens a panel for its width, side and shift, and for the stretch a
recording or a film plays.

## Exercises

An exercise sits between `:::exercise` and `:::`, with its kind on the first line; **Add
exercise…** in the **Exercises** menu above the editor writes one from a form. A button at the
end of the page checks the answers; on paper the exercises are printed unsolved.

### Putting things in place

:::exercise fill-blanks
prompt: Drag the right particle into each blank.
content-direction: target
text: 私[[topic]]学生です。毎朝パン[[object]]食べます。
- [topic] は
- [object] を
- [ ] へ
- [ ] に
explanation-correct: は marks the topic, *watashi wa*, and を the object, *pan o*.
explanation-incorrect: は (said *wa*) marks the topic and を (said *o*) the object: 私は学生です。毎朝パンを食べます。
:::

:::exercise order-sentences
prompt: Put the morning in order.
- [1] 七時に起きます。
- [2] 朝ご飯を食べます。
- [3] 家を出ます。
- [4] 電車に乗ります。
- [5] 学校に着きます。
explanation-correct: In order: *shichiji ni okimasu*, I get up at seven; *asagohan o tabemasu*, I have breakfast; *ie o demasu*, I leave home; *densha ni norimasu*, I take the train; *gakkō ni tsukimasu*, I reach school.
:::

:::exercise construct-sentence
prompt: Build the sentence “This apple is very sweet.”
image: images/starter-apple.svg {width=30 align=center}
- [1] この
- [2] りんごは
- [3] とても
- [4] 甘い
- [5] です。
explanation-correct: このりんごはとても甘いです。 *kono ringo wa totemo amai desu.*
:::

### Matching

:::exercise match-translations
prompt: Match each picture or meaning with its Japanese word.
direction: translation-to-target
- りんご => ![an apple](images/starter-apple.svg)
- 家 => ![a house](images/starter-house.svg)
- 水 => water
- 山 => mountain
explanation-correct: りんご *ringo*, 家 *ie*, 水 *mizu*, 山 *yama*.
:::

:::exercise match-opposites
prompt: Match each word with its opposite.
- 大きい => 小さい
- 新しい => 古い
- 長い => 短い
- 右 => 左
explanation-correct: Big *ōkii*, small *chiisai*; new *atarashii*, old *furui*; long *nagai*, short *mijikai*; right *migi*, left *hidari*.
:::

:::exercise match-definitions
prompt: Match each description with the place it describes. [Each one ends in ところ *tokoro*, “the place where…”.]{no-bold}
direction: definition-to-word
- 駅 => 電車が止まるところ
- 図書館 => 本を借りるところ
- 病院 => 病気のときに行くところ
- 郵便局 => 手紙を出すところ
explanation-correct: A station, 駅 *eki*, is 電車が止まるところ *densha ga tomaru tokoro*, where trains stop; a library, 図書館 *toshokan*, is 本を借りるところ *hon o kariru tokoro*, where you borrow books; a hospital, 病院 *byōin*, is 病気のときに行くところ *byōki no toki ni iku tokoro*, where you go when you are ill; a post office, 郵便局 *yūbinkyoku*, is 手紙を出すところ *tegami o dasu tokoro*, where you send letters.
:::

### Choosing

:::exercise yes-no
prompt: Answer each question. [はい *hai* is yes, いいえ *iie* is no.]{no-bold}
- りんごは果物ですか。 => yes
- 猫は魚ですか。 => no
- 富士山は日本にありますか。 => yes
- 一週間は十日ですか。 => no
explanation-correct: A week, 一週間 *isshūkan*, has seven days, 七日 *nanoka*, not ten, 十日 *tōka*.
:::

:::exercise true-false
prompt: True or false?
- Everyday Japanese mixes three scripts: kanji, hiragana and katakana. => true
- テレビ is written in hiragana. => false
- When は marks the topic of a sentence it is said *wa*, although it is still written with the kana that spells *ha* in a word like はな *hana*, flower (は \=> *wa*). => true
- Japanese puts a space between words. => false
explanation-correct: テレビ is written in katakana, and Japanese runs its words together without spaces.
:::

:::exercise single-choice
prompt: Listen. On a Japanese quiz show a chime like this one follows an answer. What does the host say next?
audio: audio/starter-chime.mp3 {width=50 align=center}
- [x] [正解です！]{kana:せいかいです translit:seikai desu}
- [ ] [残念でした。]{kana:ざんねんでした translit:zannen deshita}
- [ ] [もう一度どうぞ。]{kana:もういちどどうぞ translit:mō ichido dōzo}
explanation-correct: Yes: the chime, ピンポーン *pinpōn*, means 正解 *seikai*, a right answer. A wrong one gets a buzzer, ブー *bū*.
explanation-incorrect: The chime, ピンポーン *pinpōn*, is for a right answer, so the host says 正解です！ *seikai desu*, that is correct!
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *house*?
image-answer: images/starter-house.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] 家
- [ ] 山
- [ ] 水
explanation-correct: 家 *ie* is a house; 山 *yama* is a mountain and 水 *mizu* water. The chime stands in for the word said aloud.
:::

:::exercise incorrect-part
prompt: One part of this sentence is wrong. Which one? [(I go to school every day.)]{no-bold}
- [ ] 私は
- [ ] 毎日
- [x] 学校を
- [ ] 行きます。
explanation-correct: Right: the place you go to takes に *ni* or へ *e*, as in 学校に行きます。
explanation-incorrect: Look at the particles: the place you go to takes に *ni* or へ *e*, so 私は毎日学校に行きます。 *watashi wa mainichi gakkō ni ikimasu.*
:::

:::exercise choose-all
prompt: Choose every word written in katakana.
- [x] テレビ
- [ ] ねこ
- [x] コーヒー
- [ ] 山
- [x] パン
explanation-correct: テレビ *terebi*, コーヒー *kōhī* and パン *pan* are katakana; ねこ is hiragana and 山 is a kanji.
:::

:::exercise odd-one-out
prompt: Which word is the odd one out?
- [ ] 犬
- [ ] 猫
- [ ] 鳥
- [x] 机
explanation-correct: 犬 *inu* dog, 猫 *neko* cat and 鳥 *tori* bird are animals; 机 *tsukue* is a desk.
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: At a counter a customer says: [お茶とおにぎりをください。]{kana:おちゃとおにぎりをください translit:ocha to onigiri o kudasai} Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then something to eat.
::::exercise single-choice
prompt: What does the customer ask for to drink?
- [x] [お茶]{kana:おちゃ translit:ocha}
- [ ] [おにぎり]{kana:おにぎり translit:onigiri}
- [ ] [本]{kana:ほん translit:hon}
explanation-correct: お茶 *ocha* is tea; おにぎり *onigiri* is a rice ball.
::::
::::exercise true-false
prompt: Now decide.
- おにぎり *onigiri* is something to eat. => true
- ください *kudasai* means *thank you*. => false
explanation-correct: ください is *please give me*; *thank you* is ありがとう *arigatō*.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the particles you have just seen.
content-direction: target
text: お茶[[and]]おにぎり[[obj]]ください。
- [and] と
- [obj] を
- [ ] は
- [ ] に
explanation-correct: と joins the two things, *to*, and を marks what is asked for, *o*.
::::
:::

### Flashcards

A flashcard turns over when it is clicked and is never scored. A vocabulary card, whose speaker
button plays the recording its `back-audio:` names (the chime, where the word said aloud would go)
without turning the card:

:::exercise flashcard
card-type: vocab
target: 家
reading: いえ
transliteration: ie
meaning: house, home
context: 大きい家ですね。 *ōkii ie desu ne*, what a big house!
notes: Also read うち *uchi*, which leans towards ‘home’.
back-image: images/starter-house.svg
back-audio: audio/starter-chime.mp3
:::

A card of opposites:

:::exercise flashcard
card-type: opposites
target: 暑い
reading: あつい
transliteration: atsui
opposite: 寒い
opposite-reading: さむい
opposite-transliteration: samui
notes: Hot and cold weather. A thing hot or cold to the touch is 熱い *atsui* or 冷たい *tsumetai*.
:::

A free card, whose four fields hold anything a note can hold, pictures and recordings included:

:::exercise flashcard
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=30 align=center}

  これは何ですか。
front-secondary: *kore wa nan desu ka?* What is this?
back-primary: |
  りんごです。

  - **Reading** りんご *ringo*
  - **Kanji** 林檎, seldom written
back-secondary: |
  ![ピンポーン, a right answer](audio/starter-chime.mp3){width=80 align=center}
front-primary-size: 110
front-secondary-shade: subdued
back-primary-size: 130
back-secondary-shade: accent
:::
