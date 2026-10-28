---
title: LaTeX drawings in the exercises
linkTitle: LaTeX in exercises
weight: 9
description: A limit, a reaction or a molecule drawn by LaTeX inside an exercise — in a prompt, in blanks and options, on a Jolly card — with [...]{latex} in a line or a ::::latex block on its own.
---

A formula MathJax cannot draw — a reaction with `mhchem`, a molecule with
`chemfig`, a limit set at full height, a TikZ plot — is drawn by LaTeX
itself, and an exercise may hold one as a document does: the [LaTeX
drawings](../dialect/latex-drawings.md) of the dialect, in two forms.

- **`[…]{latex}`, in a line.** A mark that draws what is between the
  brackets right where it stands, sized to the words round it and set on
  their baseline. It goes wherever an exercise shows text: the prompt, the
  sentence of a fill-in, every option, block and entry, both sides of a
  matching pair, the statements of a yes-no exercise, the explanations. A
  word after `latex` names a [theme](../dialect/latex-drawings.md#themes),
  `[\ce{H2O}]{latex chemistry}`; no word is the default theme.
- **`::::latex … ::::`, on its own.** A block on lines of its own, with
  `{width= align=}` if it wants them. It stands in a multi-line
  **prompt** (`prompt: |`) and in the four fields of a **Jolly card**, and
  has four colons so that the exercise does not end where the drawing
  does. Anywhere else — an option, an explanation, the sentence of a
  fill-in — its lines stay as text: write those with a mark. A block is
  **part of the prompt, not a field of its own**: written on its own lines
  between the fields, straight after a one-line `prompt: …` or among the
  rows, it belongs to no field and the exercise is refused (*a LaTeX drawing
  goes inside the prompt, not between the fields*). Write `prompt: |` and put
  every line of the prompt under it, indented, the drawing's fences and its
  LaTeX too.

In a step of a [follow-up](follow-up.md#how-it-is-written) a block has one colon
more, like every fence in it: `:::::latex chemistry` … `:::::`. In the editor's
preview, **✎** on a block in a prompt or in a step opens it again and rewrites it
where it stands, indented and fenced as it was.

Both are drawn once, by LaTeX, and the page, the PDF and a deck show the
same picture. What the learner drags, chooses or matches is the option's
own LaTeX, never its picture: **Check exercises** compares what was
written.

## In a sentence, in the blanks, in the options

A fill-in whose sentence holds drawings, and whose blocks are drawings
too. It has **two blanks**, each named, and each blank's row says which
block goes there; the two others fit neither. Drag a block into a blank, or
click a blank and choose from its cloud, as in any
[fill-in](placement.md#fill-blanks).

```parseh-example
:::exercise fill-blanks
prompt: Drag the blocks into the blanks.
text: [$\displaystyle\lim_{x\rightarrow 0}\frac{\sin(x)}{x} = $]{latex} [[first]], [$\displaystyle\lim_{x\rightarrow\infty}\frac{1}{x} = $]{latex} [[second]]
- [first] [$1$]{latex}
- [second] [$0$]{latex}
- [ ] [$2$]{latex}
- [ ] [$\infty$]{latex}
:::
```

The options of a choice exercise are drawn the same way:

```parseh-example
:::exercise choose-all
prompt: Choose every entry that computes to 1.
- [x] [$\displaystyle\lim_{x\rightarrow 0}\frac{\sin(x)}{x}$]{latex}
- [ ] [$2 + 2$]{latex}
- [x] [$4 \cdot 0.25$]{latex}
:::
```

## Chemistry

`mhchem`'s `\ce{…}` writes a formula or a whole reaction, and the
**chemistry** theme has it. Here the options are reactions, and so is the
explanation:

```parseh-example
:::exercise single-choice
prompt: Which equation is balanced?
- [ ] [\ce{H2 + O2 -> H2O}]{latex chemistry}
- [x] [\ce{2H2 + O2 -> 2H2O}]{latex chemistry}
- [ ] [\ce{2H2 + O2 -> H2O}]{latex chemistry}
explanation-correct: Each side has four atoms of hydrogen and two of oxygen: [\ce{2H2 + O2 -> 2H2O}]{latex chemistry}.
:::
```

Both sides of a matching pair may be drawn, or one of them:

```parseh-example
:::exercise match-translations
prompt: Match each formula with its name.
- [\ce{H2O}]{latex chemistry} => water
- [\ce{CO2}]{latex chemistry} => carbon dioxide
- [\ce{NaCl}]{latex chemistry} => table salt
:::
```

## A drawing on its own

A structural formula is a drawing rather than a piece of a line, so it is
a **block** — in the prompt, which is then written `prompt: |` with its
lines indented under it. `chemfig` draws it, with the same **chemistry**
theme:

```parseh-example
:::exercise single-choice
prompt: |
  Which molecule is this?
  ::::latex chemistry
  \chemfig{H-C(-[2]H)(-[6]H)-C(-[2]H)(-[6]H)-O-H}
  ::::
- [x] ethanol
- [ ] methanol
- [ ] ethane
explanation-correct: Two carbon atoms and an OH group: ethanol, [\ce{C2H5OH}]{latex chemistry}.
:::
```

The block's own LaTeX is written as it would stand between
`\begin{document}` and `\end{document}`, so a formula in it keeps its `$`
signs:

```parseh-example
:::exercise single-choice
prompt: |
  Choose the correct answer.
  ::::latex
  $\displaystyle\lim_{x\rightarrow 0}\frac{\sin(x)}{x} = ?$
  ::::
- [x] 1
- [ ] 2
- [ ] 0
:::
```

On a **Jolly card** a block may stand in any of the four fields, and a
mark in any line of them:

```parseh-example
:::exercise flashcard
card-type: jolly
front-primary: |
  ::::latex
  $\displaystyle\lim_{x\rightarrow 0}\frac{\sin(x)}{x}$
  ::::
back-primary: 1
:::
```

```parseh-example
:::exercise flashcard
card-type: jolly
front-primary: |
  ::::latex chemistry
  \chemfig{*6(-=-=(-[:30]O-[:-30]C(-[:30]CH_3)=[:-90]O)-(-[:90]C(-[:30]OH)=[:150]O)=)}
  ::::
front-secondary: What is it called?
back-primary: aspirin
back-secondary: acetylsalicylic acid, [\ce{C9H8O4}]{latex chemistry}
:::
```

## When it cannot be drawn

A drawing needs TeX on the computer Parseh runs on. Where there is none,
or where the LaTeX has a fault, the exercise still works:

- **A block** shows its LaTeX in a frame, with one line saying why.
- **A mark** shows its LaTeX where it stands, in code, with no frame.
- **On paper** a block is a framed note, and a mark is set in typewriter
  type.

The reasons, and what mends each, are in [LaTeX drawings](../dialect/latex-drawings.md#when-it-cannot-be-drawn).
