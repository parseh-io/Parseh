---
title: New Chinese note
subtitle: a guided tour of everything a note can hold
note: 中文 Zhōngwén · simplified characters, with pinyin · prose in English
lang: en
target: zh
---

> **This page is a demo.** It shows everything a note can contain, each thing used once or
> twice with real Chinese: text, lists, pinyin, colours, tables, notes, links, pictures, sound,
> mathematics and exercises. Keep what you need, delete the rest, and write your own note in
> its place.

Chinese needs no mark in a note: the characters give it away, so a word such as 中文 is found
and set in the Chinese face on its own. What you add by hand is the pronunciation, in pinyin.
Each section below shows one thing a note can do by doing it; the source beside the preview
shows how it is written.

## Plain text

### Emphasis and code

Two asterisks on each side make **bold** text and one makes *italic* text; bold and italic at
once, with three, is not supported, so choose one of the two. Backticks make `inline code`,
handy for things typed rather than read: tone numbers such as `ni3 hao3` are what some
keyboards take, while a note writes the tone marks, nǐ hǎo.

A word followed by an equals sign and an italic meaning is a gloss: in 你好 = *hello* the equals
sign is set in grey, and the pair goes into the note's glossary.

### Lists

A dash at the start of a line makes a bullet list, and an item indented by two spaces sits one
level down:

- [你好]{translit:nǐ hǎo} = *hello*
- [谢谢]{translit:xièxie} = *thank you*
  - and the answer to it, [不客气]{translit:bú kèqi} = *you're welcome*
- [再见]{translit:zàijiàn} = *goodbye*

A number and a full stop make a numbered list, here the first five numbers:

1. 一 *yī*
2. 二 *èr*
3. 三 *sān*
4. 四 *sì*
5. 五 *wǔ*

When every item starts with a **bold label**, the list is set as terms and their descriptions:

- **Greeting** 你好 (nǐ hǎo), the everyday hello, at any hour of the day.
- **Thanks** 谢谢 (xièxie), whose second syllable is in the neutral tone and has no mark.
- **Parting** 再见 (zàijiàn), said on leaving, like *goodbye*.

### Arrows, right and wrong, line breaks

An arrow points from one thing to the next: 谢谢 → 不客气, *thank you* → *you're welcome*. A
hyphen and a greater-than sign make the same arrow: 对不起 -> 没关系, *sorry* -> *never mind*.

A cross marks a wrong form and a tick the right one: ✗三个书 ✅ 三本书. Books are counted with 本,
not with the general 个. The toolbar above the editor has a button for each of the three.

A paragraph runs on until a blank line. To break a line inside it, press the line-break button
of the toolbar where the break should go,⏎like this,⏎and like this.

## Chinese in the text

### Words and sentences

Chinese inside an English sentence is recognised by its script: 我学习中文 = *I study Chinese*
needs nothing around it. Two asterisks make Chinese bold as they make English bold: **中文**
(Zhōngwén) is the Chinese language.

A stretch in square brackets followed by `{tl}` is marked as Chinese by hand. The script is
enough on its own, so the mark is needed only where a Latin letter or a figure sits inside
Chinese and would cut it in two: [我买了一件T恤。]{tl} = *I bought a T-shirt.*

A paragraph with no Latin letter in it becomes a Chinese paragraph by itself, figures and
punctuation included. This one says *I study Chinese for thirty minutes every day, and for an
hour at the weekend*:

我每天学习30分钟中文，周末学习一个小时。

A paragraph that does hold a Latin letter is marked as a whole, in the same square brackets.
Here the letters are the OK of 卡拉OK, *karaoke*, and the paragraph says *let's go and sing
karaoke at the weekend!*

[周末我们去唱卡拉OK吧！]{tl}

A paragraph of nothing but Chinese characters and Chinese punctuation, not even a figure, is a
display line, set large. Here is the opening line of the *Analects*, which asks whether it is
not a joy to learn something and to practise it at the right time:

学而时习之，不亦说乎？

### Longer pieces, tints and vertical text

A piece of several lines is written with its opening bracket on a line of its own and its
closing bracket and braces on another, with a line break after each line of the piece. The
word `bg=` in the braces tints it: quote, sand, rose, sage or lilac. Li Bai's *Quiet Night
Thought*, on sand:

[
床前明月光，⏎
疑是地上霜。⏎
举头望明月，⏎
低头思故乡。
]{tl bg=sand}

A short exchange on sage, in which two people ask each other *how are you?* The Latin letters
A and B are why it is marked:

[
A：你好吗？⏎
B：我很好，谢谢。你呢？⏎
A：我也很好。
]{tl bg=sage}

Some languages have a second typeface for such blocks, chosen with `font=`; Chinese has none in
the toolbox, so that option does not apply here.

Chinese can also be set vertically, in columns read from right to left: add `vertical` to the
braces, and the height of a column in `height=`. A Tang quatrain about climbing a tower:

[
白日依山尽，黄河入海流。⏎
欲穷千里目，更上一层楼。
]{tl vertical height=14}

## Pinyin

The pinyin of a word rides in braces after it and appears when the pointer rests on the word:
[苹果]{translit:píngguǒ} = *apple*. A colour can share the same braces:
[谢谢]{teal translit:xièxie} = *thank you*.

Pinyin is the one reading a Chinese note writes. Chinese has no sound script of its own to set
over the characters, as Japanese has kana, so the `kana:` key of Japanese notes does not apply
here.

> **Pinyin in four rules**
>
> - Tone marks, never tone numbers: 你好 nǐ hǎo.
> - The neutral tone carries no mark: 妈妈 māma, 谢谢 xièxie.
> - A word is written in one piece: 中国 Zhōngguó, 图书馆 túshūguǎn.
> - Capitals are for names only: 北京 Běijīng, 长城 Chángchéng.

## Colours

Five named colours tint a word: [红]{crimson translit:hóng} = *red*,
[蓝]{indigo translit:lán} = *blue*, [绿]{teal translit:lǜ} = *green*,
[紫]{violet translit:zǐ} = *purple* and [黄]{amber translit:huáng} = *yellow*. Any other colour
is written as a hash sign and six hexadecimal digits: [粉红]{#C2185B translit:fěnhóng} = *pink*.

## Vocabulary entries

A heading whose parts are divided by vertical bars is a dictionary entry: the word, its pinyin,
where it comes from, and after an equals sign its meaning, which is not printed but goes into
the glossary. Under it, a list with bold labels holds the senses and examples.

## 幽默 | yōumò | borrowed in the 1920s from English *humour* | = *humour*

- **Meaning** humour; as an adjective, funny or witty
- **Example** [他很幽默。]{translit:tā hěn yōumò.} = *He has a good sense of humour.*
- **Sound** yōumò was chosen to echo the English word

The pinyin alone makes a shorter entry:

## 学习 | xuéxí | = *to study, to learn*

- **Example** [我在学习中文。]{translit:wǒ zài xuéxí Zhōngwén.} = *I am studying Chinese.*
- **Also a noun** [学习很重要。]{translit:xuéxí hěn zhòngyào.} = *Studying matters.*

The headword can wear a colour, and its pinyin can ride in the same braces, leaving the pinyin
field empty:

## [咖啡]{teal translit:kāfēi} | | borrowed from English *coffee* or French *café* | = *coffee*

- **Example** [一杯咖啡]{translit:yì bēi kāfēi} = *a cup of coffee*
- **Measure word** 杯 (bēi), for what is served in a cup or a glass

## Tables

A table is drawn with vertical bars. The dashes under the header row set each column's
alignment: a colon on the left, on both sides or on the right; `--` alone in a cell leaves it
empty. Chinese counts with a measure word between the number and the noun, but not every noun
takes one:

| Noun | Meaning | Measure word | Three of them |
|:---|:---|:---:|---:|
| 书 shū | book | 本 běn | 三本书 |
| 猫 māo | cat | 只 zhī | 三只猫 |
| 人 rén | person | 个 ge | 三个人 |
| 天 tiān | day | -- | 三天 |

## Footnotes

A footnote adds a remark without interrupting the sentence, and its text is written apart,
anywhere in the note. In the display line of the *Analects* above, 说 is not read shuō.[^1]

[^1]: There 说 stands for 悦 and is read yuè, *to be pleased*. A character can have more than one
  reading, and the pinyin is where the reading is settled.

A note can also be written in place, after a caret and in square brackets: 您好 is the polite
hello.^[It is built on [您]{translit:nín}, the respectful form of 你.]

## Links

A link is its text in square brackets followed by the address in round ones:
[a short film to try things on](https://www.youtube.com/watch?v=aqz-KE-bpKQ).

A link can also point to another note by its name, which is the note's title:
[another note](doc:My second Chinese note). Left empty, the square brackets show that title:
[](doc:My second Chinese note). Until a note with that title exists, the link is a dangling
one, drawn in red and dashed while it waits; create a note called *My second Chinese note* and
the link starts to work. The **Doc link…** button above the editor writes such a link for you.

## Latin blocks

A paragraph of English in square brackets followed by `{la}` is set apart as a block of the
prose language: made for a translation beside a Chinese passage, and for English inside a
vertical or right-to-left page. `width=` and `offset=` narrow it and move it as they do a
picture, `align=` sets its lines to the left, the centre or the right, and `bg=` tints it. The
night poem above, its lines centred, on sand:

[Before my bed the moonlight is bright;⏎
I take it for frost upon the ground.⏎
I raise my head and gaze at the bright moon;⏎
I lower it, and think of home.]{la align=center bg=sand width=80}

The quatrain on the tower, narrower and moved a little to the right:

[*The white sun sets behind the mountains, the Yellow River flows into the sea.
To see a thousand miles further, climb one more storey.*]{la width=70 offset=10}

## Mathematics

A formula inside a line goes in square brackets followed by `{math}`, in LaTeX notation.
Children learn the times table as a chant, and 三七二十一 (sān qī èrshíyī) is
[3 \times 7 = 21]{math}.

A formula on lines of its own goes between a line `:::math` and a closing line `:::`. Rank the
[N]{math} different characters of a text by frequency, the *i*-th one occurring [f_i]{math}
times; the share of the text covered by the commonest [n]{math} of them is

:::math
C(n) = \frac{\sum_{i=1}^{n} f_i}{\sum_{i=1}^{N} f_i}
:::

and the thousand commonest characters cover roughly nine tenths of an everyday text.

## Pictures, recordings and video

A picture stands on a line of its own: an exclamation mark, the caption in square brackets, the
file in round ones, and its width, side and shift in braces.

![An apple, 苹果 píngguǒ](images/starter-apple.svg){width=40 align=center}

![A house, 房子 fángzi](images/starter-house.svg){width=30 align=left offset=10}

A recording is written the same way, with its file under `audio/`; `start=` and `end=` play only
that stretch of it.

![A short chime](audio/starter-chime.mp3){width=50 align=center start=0 end=1.4}

A video starts with an at sign instead of the exclamation mark, and takes a YouTube address:

@[A short film](https://www.youtube.com/watch?v=aqz-KE-bpKQ){width=70 align=center start=10 end=40}

These pictures and this recording come with every new note: replace them with your own. The
**Image**, **Audio** and **Video** buttons above the editor upload a file or take an address and
write its line for you.

## Exercises

An exercise is written between a line `:::exercise` followed by its type and a closing line
`:::`. The page starts them unanswered, and the **Check exercises** button at the end marks
them all. **Add exercise…**, in the **Exercises** menu above the editor, writes one for you
from a form. Here is one of each type.

### Filling and ordering

:::exercise fill-blanks
prompt: Fill each gap with the right measure word.
content-direction: target
text: 我有两[[1]]哥哥，还有一[[2]]猫。
- [1] 个
- [2] 只
- [ ] 本
explanation-correct: People take the general 个 (ge), and animals take 只 (zhī): 我有两个哥哥，还有一只猫。 = *I have two elder brothers, and a cat too.*
explanation-incorrect: 本 (běn) counts books. People take 个 (ge), and cats take 只 (zhī).
:::

:::exercise order-sentences
prompt: Put the lines of this short conversation in order.
- [1] 你好！你叫什么名字？
- [2] 我叫小明。你呢？
- [3] 我叫小红。认识你很高兴！
- [4] 我也很高兴认识你。
:::

:::exercise construct-sentence
prompt: Build the sentence *My little brother loves playing football with his friends.*
- [1] 我弟弟
- [2] 很喜欢
- [3] 跟朋友
- [4] 一起
- [5] 踢足球。
explanation-correct: 我弟弟很喜欢跟朋友一起踢足球。 wǒ dìdi hěn xǐhuan gēn péngyou yìqǐ tī zúqiú.
:::

### Matching

:::exercise match-translations
prompt: Match each English word, and the picture, with its Chinese word.
- water => 水
- mountain => 山
- the moon => 月亮
- ![An apple](images/starter-apple.svg) => [苹果]{tl}
:::

:::exercise match-opposites
prompt: Match each word with its opposite.
- 大 => 小
- 长 => 短
- 新 => 旧
- 冷 => 热
- 早 => 晚
:::

:::exercise match-definitions
prompt: Read what each word does, and find the word.
direction: definition-to-word
- 因为 => gives the reason: *because*
- 所以 => gives the result, as in cause \=> effect: *so, therefore*
- 但是 => turns to a contrast: *but*
- 如果 => sets a condition: *if*
:::

### Choosing

:::exercise yes-no
prompt: Look at the picture and answer yes or no. [房子 (fángzi) means *house*.]{no-bold}
image: images/starter-house.svg {width=30 align=center}
- Is this a 房子? => yes
- Is this a 苹果? => no
- Does counting houses need a measure word, as in 一座房子 (yí zuò fángzi)? => yes
:::

:::exercise true-false
prompt: True or false?
- Chinese leaves a space between one word and the next. => false
- 他 (he) and 她 (she) sound exactly alike: both are tā. => true
- In pinyin a syllable in the neutral tone, like the second one in 妈妈 (māma), 谢谢 (xièxie) or 桌子 (zhuōzi), is written with no tone mark at all, because it is said short and light. => true
- 不 is always said in the fourth tone, bù. => false
explanation-correct: Right. 不 changes to bú before another fourth tone, as in 不是 (bú shì).
explanation-incorrect: Chinese runs its words together; 他 and 她 are both tā; the neutral tone is unmarked; and 不 turns into bú before a fourth tone, as in 不是 (bú shì).
:::

:::exercise single-choice
prompt: Someone says 谢谢！ to you. What do you answer? [The chime stands in for a recording of the question.]{no-bold}
audio: audio/starter-chime.mp3 {width=45 align=center}
- [ ] 对不起。
- [x] 不客气。
- [ ] 再见。
explanation-correct: 不客气 (bú kèqi) means *you're welcome*.
explanation-incorrect: 对不起 (duìbuqǐ) is *sorry* and 再见 (zàijiàn) is *goodbye*; the answer is 不客气 (bú kèqi).
:::

An exercise can also keep a picture and a recording back until the answers are checked, right
or wrong: `image-answer:` and `audio-answer:`, as in the next one. The editor's preview, which
shows every exercise solved, shows them at once, and the PDF leaves them out.

:::exercise single-choice
prompt: Which word means *apple*?
image-answer: images/starter-apple.svg {width=30 align=center}
audio-answer: audio/starter-chime.mp3 {width=50 align=center}
- [x] 苹果
- [ ] 月亮
- [ ] 水
explanation-correct: 苹果 (píngguǒ) is an apple; 月亮 (yuèliang) is the moon and 水 (shuǐ) water. The chime stands in for the word said aloud.
:::

:::exercise incorrect-part
prompt: One part of this sentence is wrong. Which one?
- [ ] 我
- [ ] 买了
- [x] 三个
- [ ] 书。
explanation-correct: Books are counted with 本 (běn): 我买了三本书。
:::

:::exercise choose-all
prompt: Which of these are fruit? Choose all that apply.
- [x] 苹果
- [ ] 椅子
- [x] 香蕉
- [x] 西瓜
- [ ] 书包
explanation-correct: 苹果 apple, 香蕉 banana and 西瓜 watermelon are fruit; 椅子 is a chair and 书包 a school bag.
:::

:::exercise odd-one-out
prompt: Which word does not belong with the others?
- [ ] 爸爸
- [ ] 妈妈
- [x] 桌子
- [ ] 姐姐
explanation-correct: 桌子 (zhuōzi) is a table; the others are family: father, mother and elder sister.
:::

### Follow-up questions

A follow-up is a chain of exercises answered one after the other: check a step, read what it says, and the next one comes under it. A step is any exercise, written inside the chain with one colon more on its fences (`::::exercise …` and `::::`). The PDF prints every step at once, numbered, so write each one so that it does not give away the one before.

:::exercise follow-up
prompt: At a teahouse a customer says: 你好！我要一杯茶和一个包子。 Answer about it, one question at a time.
explanation-correct: You followed the whole order.
explanation-incorrect: Read the sentence once more, slowly: a drink first, then something to eat.
::::exercise single-choice
prompt: What does the customer want to drink?
- [x] 茶
- [ ] 包子
- [ ] 书
explanation-correct: 茶 (chá) is tea; 包子 (bāozi) is a steamed bun.
::::
::::exercise true-false
prompt: Now decide.
- 包子 (bāozi) is something to eat. => true
- 谢谢 (xièxie) means *please*. => false
explanation-correct: 请 (qǐng) is *please*; 谢谢 (xièxie) is *thank you*.
::::
::::exercise fill-blanks
prompt: Order for yourself, with the measure words you have just seen.
content-direction: target
text: 我要一[[cup]]茶和一[[piece]]包子。
- [cup] 杯
- [piece] 个
- [ ] 本
explanation-correct: 杯 (bēi) counts cups of a drink, and 个 (ge) is the general measure word.
::::
:::

### Flashcards

Flashcards turn over when clicked and are never scored. The speaker button on the back of the first
one plays the recording its `back-audio:` names (the chime, where the word said aloud would go)
without turning it.

:::exercise flashcard
prompt: Say the word aloud, then turn the card.
card-type: vocab
target: 房子
transliteration: fángzi
meaning: house
context: 这座房子很大。 = *This house is big.*
notes: The second syllable is in the neutral tone, so it carries no tone mark.
front-image: images/starter-house.svg
back-audio: audio/starter-chime.mp3
:::

:::exercise flashcard
prompt: Recall the opposite, then turn the card.
card-type: opposites
target: 冷
transliteration: lěng
opposite: 热
opposite-transliteration: rè
notes: 今天很冷，昨天很热。 = *It is cold today; yesterday was hot.*
:::

:::exercise flashcard
prompt: Name the fruit in Chinese, then turn the card to check.
card-type: jolly
front-primary: |
  ![An apple](images/starter-apple.svg){width=40 align=center}
front-secondary: a fruit, round and crisp
front-secondary-size: 110
front-secondary-shade: subdued
back-primary: [苹果]{translit:píngguǒ}
back-primary-size: 160
back-primary-shade: accent
back-secondary: |
  **píngguǒ** · *apple*

  ![A chime, standing in for the word spoken](audio/starter-chime.mp3)

  - 一个苹果 = *an apple*
  - 我喜欢吃苹果。 = *I like apples.*
:::
