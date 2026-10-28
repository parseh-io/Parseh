# exlex authoring prompt

Do not copy the prompt from this file: copy it from the studio's **LLM
prompt** page. This file holds every rule the prompt can teach, and the page
resolves it: a rule is in a section marked `{{?id}}…{{/id}}` and reaches the
copy only when its box is ticked there, the parts a language does not need are
left out, the answer contract (`{{?contract}}…{{/contract}}`) is put after the
instructions, and the target language's own conventions (`docs/lang/<code>.md`)
are added. A copy taken from this file would carry the marks along. Paste the
copy **before your question**, in the same message. The model creates a `.md`
file, or, where it cannot make one, gives the whole document in one fenced
block; download the file (or use *Paste LLM answer*) and open it in exlex
studio, or run `exlex.py build` on it, to get the typeset, verified PDF.

The prompt is generic: the language the document is about is named by the
`target:` line of the front matter, and its value is one of the codes in the
toolbox's registry, `lib/languages.json` -- the one table that says which
languages there are. The prompt page has a select for it and states the target
at the top of the copied text.

The sections and what each costs are the boxes of `markdown/app/promptboxes.py`.
Write every section so that it is complete on its own: with the other boxes
off, nothing in it may point at a rule that is not there. What two features
say to each other goes in a sentence that only appears when both are ticked.
A section a language cannot use, or says differently, is cut by `lang_*` blocks
(`lang_own_script`, `lang_latin_script`, `lang_reading`, `lang_rtl`, ...), and
what a box left out still names is a line of the reserved list, at the end,
inside `{{?no_id}}…{{/no_id}}`. A new feature is a section here, a row of
`BOXES` there, its line in the reserved list, and its rows in the table of
`tests/test_prompts.py` (`RESERVED`), which drives each mark through the parser.

---

{{?authoring}}You are writing a document for **exlex**, a toolchain that compiles Markdown into a XeLaTeX PDF and a web page, with the text of a **target language** (the language being learned, set in large type in its own script and direction) embedded in prose written in another language. Follow the rules below exactly, and write the prose in the language of the question.

{{/authoring}}**The features are tools, not tasks.** Some rules fix the *format* (how the target language is written, the shape of the file): follow those always. Everything else you are taught below is *optional machinery*: reach for a feature only when the content genuinely calls for it, exactly as you would reach for italics — and it is completely normal for an answer to use few of them or none. Never use a feature to demonstrate it, never construct an example *in order to* exercise one (a sentence mixing the two languages belongs in the document only if that mixture is what you are teaching), and never let the set of available features shape what you say. Above all, the result must contain **no trace of the machinery itself**: the reader sees a typeset page, and must find nothing about "this document", its colours, its markup, its rendering, or what any tool "allows us" to show. If a sentence talks about the document instead of the subject, delete it.

{{?authoring}}**Front matter.** Start the file, with nothing before it, with:

```
---
title: <short title>
subtitle: <one line; may contain the target language>
note: <optional small line under the title>
lang: <ISO code of the prose language: en, it, fr, de, es …>
target: <registry code of the language the document is about>
---
```

Write the values plainly, without quotes. `target:` names the language being learned; it decides the script, the direction, the fonts and which headings are vocabulary entries, so set it before anything else (omitted, or a code that is not in the registry, the document is taken to be about Persian). `lang:` is the language of the **prose** — it is not decoration: it picks the hyphenation patterns the typesetter breaks words with, and one language's patterns applied to another are worse than none at all. Set it to the language you are actually writing the prose in — the language of the question. If you omit it the document is typeset as English.{{?lang_latin_script}} The two may be the same language (a document in {{LANGUAGE}} about {{LANGUAGE}}): every run of the target is marked all the same (see below).{{/lang_latin_script}} Those five keys are all that is read: any other key is dropped without a word, and a front matter that is never closed by its second `---` takes the whole document with it.

**Structure.** `##` for sections, `###` for subsections, and never deeper: `####` is shown as typed. No `#` heading (the title comes from the front matter; a `#` line is dropped). Sections are **numbered automatically** by the toolchain — never number them yourself: write `## The four words`, not `## 2. The four words` (a hand-typed number would come out doubled), and a heading has no closing hashes (`## Title ##` would show them). A section title never contains a `|` (the studio reads a `|` in a `##` heading as the fields of a vocabulary entry) and takes no gloss (a trailing `= *…*` is dropped).

{{/authoring}}{{?lang_own_script}}**Text in the target language.** Write it inline as plain Unicode, exactly where it belongs in the sentence, in its own script. Never transliterate instead of writing it; never put Latin letters, Western digits, or markdown syntax *inside* a phrase of the target language. Use the script's own conventions{{?lang_arabic_script}} (the zero-width non-joiner where its orthography requires it: می‌رود, به‌آهستگی){{/lang_arabic_script}}. Multi-word phrases are fine; the toolchain keeps them together and sets them in the right direction. Every run of the script is **detected**: nothing has to be marked for it to be set in the target language's face and direction. A paragraph that holds no Latin letter at all is set as a block of the target language of its own, a large display line when it is only the script, so write one only for showcased material (a proverb, an example sentence), never for prose.{{/lang_own_script}}{{?lang_latin_script}}**Text in the target language.** Write it inline, exactly where it belongs in the sentence, in the language's own spelling — never transliterated, never translated. It is written in the same alphabet as the prose, so it cannot be told apart from it: **every run of it is marked**, a word, a phrase or a whole sentence, as `[word]{tl}` — the braces may hold the language's code, `{{{LANGUAGE_CODE}}}`, in place of `tl`. Any bracketed word that carries attributes counts as the mark too. A word of the prose language is never marked, and a marked word is never a word of the prose. The content of the mark is opaque: no markdown, no square brackets inside it.{{/lang_latin_script}}

**One paragraph, one line.** Write every paragraph of prose as ONE line, however long: never wrap it at a fixed width and never break a line inside it. The studio joins the lines of a paragraph with a space (which a language written without spaces, such as Japanese or Chinese, does not want), and it reads certain marks at the head of ANY line — so a line that begins with `- `, `* `, `+ `, `> `, `## `, `### `, a number and a full stop or a bracket (`1. `, `2) `, a year such as `1921. `, or the same in the digits of another script, `۱. `), `:::exercise …`, `:::math` or `::::latex …`, or that is only `![…](images/…)`, `![…](audio/…)` or `@[…](…)`, starts a list, a box, a section, a numbered list, a fence, a picture or a video right there, in the middle of the paragraph (indenting the line changes nothing). A blank line is what ends a paragraph. Never break a line inside a mark or a link address.

**Pictures, recordings, videos and links to other documents are never yours to write.** `![…](images/…)`, `![…](audio/…)`, `@[…](…)` and `[…](doc:…)` are put in by hand, in the studio: they name files and documents that only the studio has, so one you invent points nowhere. Leave them out; if the text needs one, say in words what it should show.

{{?authoring}}**Do not invent information.** Above all do not create words out of the usual rules of the language that are in practice never or almost never used.

{{/authoring}}{{?vocab}}**Vocabulary entries.** For each headword treated in depth, use a `##` heading of the form

```
## <headword> | {{?lang_reading}}<reading> | {{/lang_reading}}<transliteration> | <short etymology note> | = *translation*
```

{{?lang_reading}}This language has a **reading**, and it is a field of its own, **before** the transliteration: `## 漢字 | かんじ | kanji | <etymology> | = *translation*`.

{{/lang_reading}}The last field is optional and **is printed nowhere**: the heading already carries the transliteration and the etymology, and a translation set beside them would only repeat what the entry goes on to say. It exists so the headword joins the document's glossary, which otherwise sees only the words glossed in running prose. Give every entry one, and put in it the senses the entry actually treats{{?lang_arabic_script}}: `## تند | tond | mp. tund, 'sharp, violent' | = *sharp, spicy, fast*`{{/lang_arabic_script}}.

The first field must be the headword alone, in the target language; it is typeset very large. Everything under the heading, until the next heading, belongs to the entry.{{?lang_latin_script}} In a Latin-script target ANY `|` in a `##` heading makes it an entry, so a section title never contains one.{{/lang_latin_script}}{{?lists}} Inside an entry, use a bullet list where **every** item starts with a bold label — `- **Attributive** …`, `- **Register** …`, in the language of the document: such lists are drawn as definition lists.{{/lists}}

{{/vocab}}{{?gloss}}**Glosses.** Give quick translations with an equals sign, one space on each side, and set **the translation itself in italics**: `آهسته برو = *go slowly*`. The `=` is styled automatically; the italics are yours to write, and they are what tells the reader where the translation stops (without them the glossary keeps one word and flags it as a guess). So the asterisks must enclose the whole translation and nothing else. Several near-synonyms rendering one word are all translation, and go inside together: `آهستگی = *slowness, gentleness*`. Anything that is commentary, context or a further remark is not translation, and stays outside: `حرکت آهسته = *slow motion*, in film`, `زود باش = *hurry up*, literally "be early"`. Italicise the translation only — never the target-language text, never the `=`.{{?lang_latin_script}} The word before the `=` must be a marked run, `[word]{tl} = *translation*`: an unmarked word followed by `=` is no gloss.{{/lang_latin_script}}

{{/gloss}}{{?translit}}**Marks for the {{TR_LABEL}}.** {{?lang_own_script}}Every time the target language stands in the prose as a **word or a short group of two or three words** — an inline mention, the subject of a gloss, a table cell, a fixed collocation cited as a unit (a preposition + noun, a noun + light verb{{?lang_arabic_script}} such as عجله کردن or کند شدن{{/lang_arabic_script}}) — write it as `[تند]{translit:tond}`{{?classic}} or `[یواش برو]{translit:yavâš borou}`{{/classic}}. This is a format rule, not an optional tool: the mark leaves no visible trace (the text renders exactly as if bare, on screen and on paper), but the studio shows the {{TR_LABEL}} when the reader points at it. {{?classic}}Use the scholarly scheme that the conventions of the target language, below, give.{{/classic}}{{?ipa}}Write IPA, as the conventions of the target language, below, give it.{{/ipa}}{{/lang_own_script}}{{?lang_latin_script}}A word or a short group of the target language may carry its {{TR_LABEL}} in the braces of its mark, `[word]{translit:…}`: the mark leaves no visible trace (the text renders exactly as if bare), but the studio shows the {{TR_LABEL}} when the reader points at it. It is optional here: give it where the sound is not obvious from the spelling, {{?classic}}using the scheme that the conventions of the target language, below, give{{/classic}}{{?ipa}}in IPA, as the conventions of the target language, below, give it{{/ipa}}.{{/lang_latin_script}}

{{?lang_own_script}}Do **not** add these marks to a full **example sentence** — anything with a subject-and-verb reading, an imperative addressed to "you", or a question, even a short one — those stay optional, exactly like any other multi-word phrase. The line is what the group *is*: a citation form or a fixed expression gets the mark; a sentence demonstrating usage does not. {{/lang_own_script}}{{?vocab}}Leave the mark out of `##` entries (they already carry a {{TR_LABEL}} field){{?blocks}}, of display lines and of `[…]{tl}` blocks{{/blocks}}.{{/vocab}}{{?no_vocab}}{{?blocks}}Leave the mark out of display lines and `[…]{tl}` blocks.{{/blocks}}{{/no_vocab}}{{?colours}} A colour mark can share the braces, the colour first: `[تند]{teal translit:tond}` (written after the {{TR_LABEL}}, a colour becomes part of it).{{/colours}}

{{/translit}}{{?reading}}**The reading mark.** For a word or group of this language, the reading — the kana — goes in the braces of its mark: `[漢字]{kana:かんじ}`, `[水の音]{kana:みずのおと}`. Like a {{TR_LABEL}}, it leaves no visible trace and shows when the reader points at the word. The kana is the reading of the whole bracketed text, never a per-character alignment. `reading:` is accepted as an alias of `kana:`.{{?translit}} When you also give the {{TR_LABEL}}, the kana goes first, in the same braces: `[漢字]{kana:かんじ translit:kanji}`. Give the reading wherever a {{TR_LABEL}} is given.{{/translit}}

{{/reading}}{{?punct}}**Punctuation: use the Latin mark almost everywhere.** The target language's own punctuation — {{OWN_MARKS}} — belongs **only inside a continuous sentence or clause of the target language of its own**{{?blocks}} (typically inside a `[…]{tl}` block or a full display line){{/blocks}}. Everywhere else the document is running prose in the language of the question, and that prose takes its own Latin punctuation. It is a common and incorrect reflex to reach for the target's mark whenever punctuation sits next to its script; do not do this. The test is always what the mark itself is punctuating — the sentence structure of the target language, or that of the prose you are writing in — never how much of the target's script sits on either side of it.

A comma that separates **items in a list**, or that punctuates the surrounding prose sentence, is doing Latin work even when every item on either side of it is a word or phrase of the target language — use the Latin `,`{{?lang_arabic_script}}: `کند, سریع, تند` (never `کند، سریع، تند`){{/lang_arabic_script}}. The same holds for the semicolon: between two clauses of the surrounding prose sentence it is the Latin `;`, not a mark of the target language. This holds however short the items are and however many of them there are in a row.{{?lang_arabic_script}} The question mark is the one member of this family that does stay the target's — but only when the whole sentence it closes is in the target language: چرا این‌قدر یواشی؟ (*why are you so slow?*). A question *about* a word or phrase, asked in the language of the document, still ends in the Latin `?`.{{/lang_arabic_script}}

{{/punct}}{{?rtl}}**Mixed-direction sequences: distinguish the direction of a run from the direction of its container.** This distinction is mandatory for a right-to-left target. A continuous target-language phrase or sentence is one RTL unit: write it in normal logical/read-aloud order inside a single `[…]{tl}` mark (or leave it unmarked where the dialect detects it), and never reverse anything inside it.

A line of LTR prose can instead contain several **separately marked RTL components** divided by operators, punctuation, labels, numbering, or intervening prose. This occurs in questions, answers, morphological analyses, derivations, lists, tables, and comparisons. In that case each marked RTL run is an indivisible visual box, while the containing expression and separators remain LTR. Write the boxes in the Markdown in the order they must appear **from left to right on the rendered page**. For successive parts of an RTL word or phrase, that box order is normally the reverse of the linguistic/read-aloud order. Reverse only the boxes; keep the characters and punctuation inside each box in natural order.

For example, Persian *dānešgāh* is analysed from the right as `dān + -eš + -gāh`, but an LTR expression showing its isolated components must be authored as:

```
[گاه]{tl} + [ش]{tl} + [دان]{tl}
```

{{?translit}}{{?colours}}With a colour and a transliteration on each box the same line reads {{?classic}}`[گاه]{#6B6B1A translit:-gāh} + [ش]{#C28E0E translit:-eš} + [دان]{translit:dān}`{{/classic}}{{?ipa}}`[گاه]{#6B6B1A translit:-gɒːh} + [ش]{#C28E0E translit:-eʃ} + [دان]{translit:dɒːn}`{{/ipa}}.

{{/colours}}{{/translit}}Do not put the read-first root *dān* in the leftmost visual box: once the RTL runs are isolated, that displays the component sequence backwards. The same rule applies with `→`, `=`, `/`, commas, parentheses, bullets, numbering, or any other LTR separator or surrounding prose; it is not a special property of `+`. Before returning a mixed-direction line, inspect its intended visual order from left to right and then check that reading the RTL components from right to left gives the intended linguistic order.

{{/rtl}}{{?blocks}}**Passages, display lines and line breaks.** {{?lang_own_script}}A paragraph that contains **no Latin letters at all** is laid out as a block of prose in the target language automatically, in its own direction and face — ASCII punctuation (`!`, `.`, `…`) and digits included{{?lang_arabic_script}}, so `درود!!! چطوری؟` reads correctly{{/lang_arabic_script}}. A paragraph of **nothing but the target language** (a proverb, an example sentence) is a large stand-alone line, a **display line**: use it for showcased material, with any translation in the paragraph before or after it. When a sentence of the target language must *contain* a Latin word or number, wrap the whole stretch as `[…]{tl}` (the document's own code, `{{{LANGUAGE_CODE}}}`, is an alias). Everything inside stays one unit in the target language's direction{{?lang_rtl}} (the Latin word becomes an embedded left-to-right island){{/lang_rtl}}. The content of `[…]{tl}` is opaque: no markdown, no glosses, no footnotes, no square brackets inside it. Use it only when Latin material genuinely belongs inside the sentence{{?gloss}} — for a gloss, keep the usual pattern `<target> = *translation*` instead{{/gloss}}.{{?lang_arabic_script}} For example:

```
[امروز یک فایل PDF فرستادم]{tl}
```
{{/lang_arabic_script}}{{/lang_own_script}}{{?lang_latin_script}}A whole paragraph that is only `[…]{tl}` (or `{{{LANGUAGE_CODE}}}` in place of `tl`) is a paragraph of the target language, set as a block of its own (a Latin-script target has no automatic block); inside prose the same mark is simply how a run is written. Its content is opaque: no markdown, no glosses, no footnotes, no square brackets inside it.{{/lang_latin_script}}

Newlines in the source are **ignored** (consecutive lines join into one paragraph); to force a real line break, write the symbol `⏎` where the break belongs. A longer `[…]{tl}` block is the one exception to *one paragraph, one line*: it may be written across several lines for readability, its opening bracket alone on the first line and `]{tl}` on the last, with `⏎` closing each line that must end there, and **no blank line and no line that begins with a mark of its own** (`- `, `1. `, `>`, `#`) inside it:

{{?lang_arabic_script}}```
[
امروز هوا آفتابی است.⏎
به پارک رفتیم
]{tl}
```{{/lang_arabic_script}}{{?lang_other_script}}```
[
the first line of the passage ⏎
the second line
]{tl}
```{{/lang_other_script}}

The mark accepts optional styling: `{tl bg=quote}` gives it a soft tinted background (other tints: `sand`, `rose`, `sage`, `lilac`){{?lang_alt_font}}, `{tl font={{ALT_FONT}}}` switches to the language's alternate face{{/lang_alt_font}}{{?lang_vertical}}, and `{tl vertical}` lays the block out in vertical columns, from top to bottom and from right to left (`height=<em>` sets the column height, 8 to 60, default 22){{/lang_vertical}}. These may be combined; omitted, the block renders plainly — which is the right choice almost always. They exist for the rare case where the content itself is a classical couplet, a haiku or a quoted passage that a reader would expect to see set apart; never add poetry or a quotation in order to use them.

{{/blocks}}{{?latin}}**Latin blocks.** A specular form exists for a **Latin paragraph**: `[text]{la}` (`{ltr}` is the same), with optional `align=right|center` (the text's alignment), `bg=quote|sand|rose|sage|lilac` (a tint), and `width=`/`offset=` (percentages of the column) to narrow the block and shift it sideways. Its content is ordinary markdown, and it is recognised only when the whole paragraph is the block: inside a sentence `[…]{la}` is shown as typed. It is layout machinery for the rare epigraph or set-apart passage, not something an answer needs.

{{/latin}}{{?forms}}**Ungrammatical and correct forms.** Prefix an ungrammatical form with `✗` and no space: `✗اینترنتِ تند`. It is rendered as a red ❌ followed by the form itself tinted red — the whole marked form, so the reader sees at a glance what is wrong. This red is reserved: a colour mark cannot override it. Do not use a raw `*` for this.{{?lang_latin_script}} In a Latin-script target write the form as a marked run, `✗[word]{tl}`, so that all of it turns red.{{/lang_latin_script}}

To flag the explicitly *correct* member of a contrast, put `✅` before it, with a space: `✅ یواش برو`. Unlike `✗`, the `✅` is a stand-alone green check and does **not** colour or otherwise affect the text that follows it. Use the pair in minimal contrasts: `✅ یواش برو / ✗یواشِ برو`.

{{/forms}}{{?lists}}**Lists.** A bullet list is lines that begin with `- ` (a dash and a space); a numbered list, lines that begin with `1. `, `2. `… (or `2) `; the studio counts from 1, whatever numbers you type). Keep the items of one list on consecutive lines: a blank line ends a list, and the next item starts another. Nest one level at most, the nested item indented by two spaces. When **every** item of a bullet list starts with a bold label, `- **Register** formal`, it is drawn as a definition list. Never begin a line of ordinary prose with `- `, `* `, `+ ` or a number followed by `.` or `)`: a year at the head of a line (`1921. The war ended`) starts a numbered list.

{{/lists}}{{?tables}}**Tables.** Use pipe tables with a header row and, under it, a line of dashes **and pipes** — two columns at least, a one-column table is not one:

```
| Form | Meaning |
|---|---|
| … | … |
```

Use `—` for an empty cell. Keep cell text short; the target language in cells is fine. Never put a `|` inside a cell: there is no way to escape it.

{{/tables}}{{?boxes}}**Highlight boxes.** Use a `>` line for the one or two passages that deserve a tinted box (a key caveat, a rule of thumb). Every line of the box begins with `>`, with a space after it or not (a lone `>` for a blank line inside it), and the first line without one ends the box.{{?lists}} A bullet list inside the box is allowed.{{/lists}} No box inside a box and no heading inside one.

{{/boxes}}{{?emphasis}}**Bold and italic.** `**bold**` and `*italic*` on Latin text only, never inside a word (`2*3*4` keeps its stars); italics are never around a word of the target language (its stars would show as typed), while `**bold**` around a lone word of the target language makes it bold. A star is always emphasis: two of them in a sentence italicise everything between them, so write a product as `5 × 3`, never `5 * 3`. Choose bold or italic, never `***both***`. Backticks set what they hold in typewriter type.

{{/emphasis}}{{?notes}}**Footnotes.** Use them for anything that would break the flow of the main argument: a caveat, a dialectal or diachronic aside, a disagreement between sources, the reason behind a claim. Two forms:

```
Persian آهسته covers two distinct areas[^areas].

[^areas]: Low speed and low volume; cf. یواش, which shares both.
```

and, for something short, an inline note: `… thus ^[a brief note here]`. Reference labels can be any word (`[^aree]`, `[^1]`); the definition sits on a line of its own, anywhere in the file, and its continuation lines must be indented. Notes are numbered automatically in the order they appear, and a note cannot hold another footnote. In the PDF the note appears at the bottom of the page; in the web reader the number is hoverable and the text appears in a floating cloud. Where the depth would otherwise clutter an entry, this is its natural place. Write `[^x]` or `^[…]` for nothing but a note: `x[^2]` for a square is an empty note.

{{/notes}}{{?links}}**Links.** `[visible text](https://example.org/page)` — the URL is hidden behind the text and is clickable in both the PDF and the web page. Only `http://`, `https://` and `mailto:` addresses are links (one with a space or a parenthesis in it is not); any other `[text](y)` loses its brackets and its address and shows only the text. The visible text may be in the target language: `[فرهنگ](https://www.vajehyab.com/)`. Link dictionaries, grammars, corpora or sources whenever they support a claim; do not link the same source twice in a row. A bare address is not a link.

{{/links}}{{?colours}}**Colour marks.** You *may* tint a word or phrase of the target language — five named colours (`crimson`, `indigo`, `teal`, `violet`, `amber`) or any six-digit hex value:

```
[آهسته]{crimson} and [تند]{#2F6B8F} occupy opposite poles.
```

*Effect:* the word is printed in that colour in the PDF and on the web. **Most documents need no colour at all** — the default is plain text, and an answer with zero colour marks is in no way incomplete. Reach for colour only when one specific contrast genuinely becomes clearer with it (say, the two poles of a single opposition, marked at the two or three places where they are compared), use as few colours as the idea needs — usually one or two, never all of them for completeness' sake — and stop there. Do not colour more than a handful of words per page, never colour a whole sentence, and **never explain the colours in the text**: no legend, no "colours in this document mark…" paragraph — the prose must read perfectly with the colours ignored.

{{/colours}}{{?colourparts}}**Colour inside a word.** When a lesson is about how ONE word is built — a stem against its ending, a root's letters — you may colour just part of it: a word coloured in parts is the one case where marks stand inside a word of the target language. Put the word in double brackets and each part to colour in single brackets, its colour after it: `[[ab[cd]{teal}ef]]`. The letters outside the single brackets stay plain, and no space or joiner goes between the parts: it is still ONE word, copied, searched, glossed and looked up whole. The colour is `crimson`, `indigo`, `teal`, `violet`, `amber` or a six-digit hex value, never another name. Write the whole word on one line, colour only part of it, and never put one such word inside another.{{?lang_arabic_script}} For example, the stem and the ending of a Persian verb: `[[بر[گشت]{teal}[م]{crimson}]]`.{{/lang_arabic_script}}{{?lang_latin_script}} In a Latin-script target such a word needs no `{tl}` mark, being a run of the target language by itself: `[[un[break]{crimson}able]]`.{{/lang_latin_script}} Whatever follows the closing `]]` is for the whole word and is never a colour.{{?translit}} The {{TR_LABEL}} of the whole word goes there: `[[ab[cd]{teal}ef]]{translit:…}`, never inside a piece.{{/translit}}{{?reading}} The reading of the whole word goes there too: `[[日[本]{indigo}語]]{kana:にほんご}`.{{/reading}}

Such a word may stand wherever a word of the target language can — in a sentence, a list, a table, a box, a title, a gloss, or as the headword of a vocabulary entry — but never inside a `^[…]` note. **Most documents need none**: reach for it only when the lesson itself is about the structure of a word, at the two or three places where that is the point, with as few colours as the idea needs, and never explain the colours in the text — no legend, no "the red part is the ending": the prose must read perfectly with the colours ignored.{{?colours}} Colouring a whole word stays the colour mark's job, `[word]{teal}`.{{/colours}}

{{/colourparts}}{{?math}}**Formulas.** Write a formula in LaTeX notation. In a line, put it in square brackets with `{math}` after them — `[a^2+b^2=c^2]{math}`; it may hold brackets of its own (`[x \in [0,1]]{math}`, `[\sqrt[3]{x}]{math}`), because it is read up to the `]{math}` that ends it. On its own line, put it between a line `:::math` and a line `:::` — the closing line is essential: without it the rest of the document becomes one formula; several lines between them are one formula (break it with `\\`, never with a blank line). Neither `$…$` nor `\(…\)` nor `\[…\]` is a marker here. Put no bracketed word or number that is only prose (`[sic]`, `[1]`) before a formula in the same paragraph: it would be taken into the formula.

{{/math}}{{?latex}}**LaTeX drawings.** What a formula cannot draw — a chemical reaction (`\ce{2H2 + O2 -> 2H2O}`), a molecule, a diagram or plot (TikZ), units — LaTeX itself draws. As a block, between a line `::::latex` and a line `::::` (**four** colons; the closing line is essential: without it the rest of the document is taken as the drawing):

```
::::latex chemistry {width=45 align=center caption="Water forms from hydrogen and oxygen"}
\ce{2H2 + O2 -> 2H2O}
::::
```

or in a line, `[\ce{H2O}]{latex chemistry}`. The word after `latex` names a **theme**, the set of packages the drawing is compiled with; it is optional (none: the default theme, which has what every theme has: formulas, colours, units) and must be one of these, because a theme the person does not have is not drawn: {{LATEX_THEMES}}. **Choose the theme by what the drawing needs.** A command comes from the package that defines it, and a theme loads only the packages it adds — `\ce` is mhchem's, `\chemfig` chemfig's, a `tikzpicture` TikZ's, an `axis` pgfplots', `\chessboard` xskak's — so name the theme that adds the package the commands come from. Write no `\usepackage` in the body (the theme loads its packages), and use no command of a package that none of these themes adds: say it another way, or draw nothing. In the braces after it, `width=` is a percentage of the column (5 to 100), `align=` is `left`, `center` or `right`, and `caption="…"` (in double quotes, with no `"` inside) gives a block a caption; an inline mark takes none. The body is LaTeX exactly as it would stand between `\begin{document}` and `\end{document}`. Draw only what a formula cannot say.

{{/latex}}{{?exercises}}**Exercises.** Put each exercise after the passage it tests. {{EXERCISE_BLOCKS}}

{{/exercises}}{{?revise}}**Revising a document you are given.** When the question comes with a document to revise, change only what you are asked to change, and keep everything else of it exactly as it is — above all what the studio's reader wrote into it and what only the studio can supply: the marks a reader adds to a word (colours such as `{crimson}` or `{#2F6B8F}`, a colour on only part of a word, `[[ab[cd]{teal}ef]]`, `{translit:…}`{{?lang_reading}}, `{kana:…}`{{/lang_reading}}), the pictures, recordings and videos (`![…](images/…)`, `![…](audio/…)`, `@[…](…)`), and the links to other documents (`[…](doc:…)`), with their attributes and names, the name after `doc:` character for character, even where you would spell or translate it otherwise. They carry the reader's own annotation and files you cannot see.

{{/revise}}**Reserved marks.** The studio reads the marks below, and each does something you did not ask for, so **write one only for a feature you were taught above; otherwise write the sentence without it.** They are listed so that you know what to avoid, not what to use: the marks of the features you were not taught, and a few that are always there.
{{?no_vocab}}
- A `##` heading that holds a `|` is a vocabulary entry{{?lang_latin_script}}: in every Latin-script target ANY `|` makes one{{/lang_latin_script}}{{?lang_own_script}} when its first field begins in the target script{{/lang_own_script}}. Never write a `|` in a section title.{{/no_vocab}}{{?no_gloss}}
- `word = *meaning*`: a word of the target language, then an equals sign and italics, is a gloss, gathered into the document's glossary.{{/no_gloss}}{{?no_translit}}
- `[word]{translit:…}` is a transliteration, shown when the reader points at the word.{{/no_translit}}{{?no_reading}}{{?lang_reading}}
- `[word]{kana:…}` (or `{reading:…}`) is a reading, shown when the reader points at the word.{{/lang_reading}}{{/no_reading}}{{?no_punct}}{{?lang_own_script}}
- The target's own punctuation ({{OWN_MARKS}}) joins the run of the target language it touches, and leaves the prose around it: write the punctuation of prose with the Latin marks.{{/lang_own_script}}{{/no_punct}}{{?no_blocks}}
- `[…]{tl}` (and `{{{LANGUAGE_CODE}}}` in place of `tl`) is a run of the target language; alone in a paragraph it is a block, with options (`bg=`{{?lang_alt_font}}, `font=`{{/lang_alt_font}}{{?lang_vertical}}, `vertical`{{/lang_vertical}}); `⏎` breaks a line.{{/no_blocks}}{{?no_latin}}
- `[text]{la}` (or `{ltr}`) alone in a paragraph is a Latin block.{{/no_latin}}{{?no_forms}}
- `✗` and `❌` before a form turn it red; `✅` is a green tick.{{/no_forms}}{{?no_lists}}
- `- `, `* ` and `+ ` at the head of a line start a bullet list; `1. `, `2) ` and a year with a full stop (`1921. `) a numbered list; `* * *` is a list too.{{/no_lists}}{{?no_tables}}
- A line that holds `|`, over a line of dashes and pipes such as `|---|---|`, starts a table.{{/no_tables}}{{?no_boxes}}
- A line that begins with `>`, with a space after it or not, starts a highlight box.{{/no_boxes}}{{?no_emphasis}}
- `*` and `**` are italic and bold: two stars in a sentence italicise everything between them (write a product as `×`). Backticks set what they hold in typewriter type.{{/no_emphasis}}{{?no_notes}}
- `^[…]` is a footnote written in place, `[^x]` cites one and a line beginning `[^x]:` holds its text and vanishes from the page (`x[^2]` is an empty note).{{/no_notes}}{{?no_links}}
- `[words](https://…)` is a link; any other `[x](y)` loses its brackets and its address and shows only `x` (`[0,1](closed)` shows `0,1`).{{/no_links}}{{?no_colours}}
- `[word]{crimson}`, with `{indigo}`, `{teal}`, `{violet}`, `{amber}` or `{#RRGGBB}` in the braces, tints the word.{{/no_colours}}{{?no_colourparts}}
- `[[ab[cd]{teal}ef]]`, a word in double brackets with a coloured piece `[cd]{teal}` inside, is one word coloured in parts.{{/no_colourparts}}{{?no_math}}
- `[…]{math}` is a formula, and a line `:::math` opens a formula block that, unclosed, swallows the rest of the document.{{/no_math}}{{?no_latex}}
- `[…]{latex}` is a LaTeX drawing, and a line `::::latex` opens a drawing block that, unclosed, swallows the rest of the document.{{/no_latex}}{{?no_exercises}}
- A line `:::exercise …` opens an exercise that, unclosed, swallows the rest of the document; `[[name]]` is a blank inside one (a double-bracket word with a coloured piece in it is no blank).{{/no_exercises}}
- A line of `---`, `***` or `___` is dropped (`* * *` is no rule: it is a list).{{?lang_latin_script}} In a Latin-script target ANY `[text]{word}`, whatever the word (`{red}`, `{note}`), makes the text a run of the target language; only `la`, `ltr`, `math` and `latex` mean something else.{{/lang_latin_script}}{{?lang_own_script}} A word the studio does not know in the braces of a mark (`{red}`) is shown as typed, brackets and all.{{/lang_own_script}}
- **Not read at all** — shown as typed, or mangled: `####` and deeper headings, and a title underlined with `===`; code fences and indented code (the code inside a fence is read as Markdown, line by line, so a `#` line vanishes and a `- ` line starts a list); `_x_` and `__x__`; `~~x~~`; `$x$`; HTML tags and entities (`<b>`, `&amp;`) and `<!-- -->`; backslash escapes (`\*` shows its backslash); `<https://…>` and `[text][ref]`; `- [ ] task` (a bullet list showing `[ ]`); definition lists; `:::note` and every fence but the ones above; shortcodes; `:smile:`; `## Title {#id}`. Write none of them, and no emoji either (the PDF has none): type the characters “ ” – — … → themselves.

{{?contract}}Answer the question that follows by **creating a markdown file** (`.md`) if you can make files: write and save the document as a file with a short name derived from the topic. If you cannot make a file, give the whole document instead as ONE fenced block, opened with four backticks and the word `markdown` and closed with four backticks. Either way it holds the document and nothing else: no preamble and no commentary inside it — anything you want to say to me goes in the chat, outside the file or the block.{{/contract}}
