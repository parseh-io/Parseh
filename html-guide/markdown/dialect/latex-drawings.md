---
title: LaTeX drawings
weight: 13
description: Chemistry, drawings, plots and units drawn by LaTeX itself, in a ::::latex block or inline, [...]{latex}, beside the formulas MathJax draws — with named themes, made in Settings, and a drawing that travels to paper, to a web page and onto a phone.
---

A formula is written with `[…]{math}` or `:::math`, and MathJax draws it
([Mathematics](mathematics.md)). That is still **the ordinary way to write
mathematics**: nothing to install, drawn in the page, on a phone and
offline. What MathJax cannot draw — a chemical reaction written with
`mhchem`, a molecule with `chemfig`, a drawing or a plot with TikZ, units
with `siunitx` — LaTeX itself can, and a **latex block**, or `[…]{latex}`
inline, asks it to.

A latex drawing is **optional**. It needs TeX on the computer Parseh runs on
(TeX Live or MiKTeX): a document without one is read exactly as before.

## Writing one

Between a line `::::latex` and a line `::::` — **four colons**, one more
than a formula's fence, so that a block may also stand in a Jolly card's
field, where a line of three colons ends the exercise:

```parseh-example
::::latex chemistry {width=45 align=center caption="Water forms from hydrogen and oxygen"}
\ce{2H2 + O2 -> 2H2O}
::::
```

- **The word after `latex`** names a [theme](#themes): the packages the
  drawing is compiled with. No word, the default theme.
- **The braces** are a figure's own: `width`, a percentage of the column
  from 5 to 100; `align`, `left`, `center` or `right`; `offset`, a
  sideways shift, as for a picture. With **no width** a drawing is at its
  natural size, measured against the text round it: it reads at the size
  of the words beside it and grows with them. With **no align** it is
  centred, as a formula is. On a card there is no offset.
- **A caption**, `caption="…"` in the braces, is set under the drawing as a
  picture's caption is, in small grey type. Write it between double quotes
  and with no `"` inside (the sheet turns a typed one into `”`). It takes
  inline markup, `*emphasis*` or `[x^2]{math}`, and it belongs to a block:
  an inline `[…]{latex}` mark has none. It is centred under the drawing, in
  a box at least 20 ems wide so that a long caption does not wrap into a
  sliver, and a drawing that could not be made shows none. A Jolly card
  may take one. Changing a caption never draws the picture again.
- **The body** is LaTeX, exactly as it would stand between
  `\begin{document}` and `\end{document}`.

```parseh-example
::::latex chemistry
\chemfig{H-[:30]O-[:-30]H}
::::
```

```parseh-example
::::latex drawing {width=50}
\begin{tikzpicture}
\draw[->] (0,0) -- (2,0) node[right] {$x$};
\draw[->] (0,0) -- (0,1.5) node[above] {$y$};
\draw[thick,domain=0:1.8] plot (\x,{0.4*\x*\x});
\end{tikzpicture}
::::
```

In the editor, **LaTeX drawing** opens a sheet: the preview beside the
LaTeX, made as the computer draws it while you type and always scaled to
fill its pane (the page shows the drawing at its own size), and under the
LaTeX a **Caption**. **Size and position** — the width, where it sits, a
sideways shift — is folded away unless the drawing already has one. The
**Theme** list marks a theme whose packages this computer lacks (*chemistry
— needs mhchem, not installed*), and a drawing that fails for a missing
package offers **Install …**, which opens Settings in another tab so that
what you wrote is not lost. In the preview, **✎** on a drawing opens it
again. In the exercise form, **LaTeX drawing…** puts one in the field of a
Jolly card you were last in.

### Inline, in the middle of a line

`[...]{latex}` draws its LaTeX right there, on the very line it sits in —
in a sentence, in an exercise's prompt or one of its options, wherever text
already goes — sized to the words round it and set on their baseline, the
same way `[...]{math}` is:

```parseh-example
The limit [$\displaystyle\lim_{x\rightarrow 0}\frac{\sin(x)}{x}$]{latex} is 1.
```

A word after `latex`, the same as a block's, names a theme:
`[\ce{H2O}]{latex chemistry}` is drawn with the chemistry theme, and no word
is the default theme.

```parseh-example
Water, [\ce{H2O}]{latex chemistry}, is made by burning hydrogen:
[\ce{2H2 + O2 -> 2H2O}]{latex chemistry}.
```

A tall drawing —
a big fraction, a stack — is shrunk to a height that will not push its own
line apart from the ones round it; whatever it draws stays in proportion.
An inline mark that cannot be drawn shows its own LaTeX in its place, in
code, rather than a hole in the sentence.

## Where it goes

A **block** goes wherever a `:::math` formula may — a document, a box, a
note in a book or a video — and in the four fields of a Jolly card, in a
document and in a deck; a whole exercise **prompt** may also be one, on its
own. An **inline** mark goes wherever prose already does: a document's
paragraphs, lists, tables, headings and captions, a note, and any exercise
field or option — the lines of prose a block alone could not reach. The
[exercises' page](../dialect-exercises/latex.md) shows both in a prompt, in
the blanks and options of a fill-in, and on a Jolly card.

## Drawn once, the same everywhere

A block, or an inline mark, is compiled **on its own**, in a document of its
own with its theme's preamble, and becomes a picture. So its packages can
never change an ordinary formula or the document it sits in, and the screen
and paper show **the same drawing** — an inline mark included, never
retypeset into the page's own LaTeX: the page shows it as a vector picture,
the PDF includes it, an [HTML export](../studio/web-page.md) carries it
inside the file, and a page kept on a phone keeps it. In the PDF it is a
picture, not text you can select, and it is set in LaTeX's own face.

It is made **once**, and made again only when something that decides what
it looks like changes: the block, its theme's packages, preamble or
compiler, the TeX installation, or Parseh's way of drawing. Renaming a
theme redraws nothing.

**Many documents at once.** The library's **Make drawings of N shown** makes the drawings of the documents it shows without
opening them, on the toolbox's Working bar ([Documents in and out](../studio/documents-in-and-out.md#make-drawings-of-n-shown)).

**A page never waits for its drawings.** A document or a note opens at
once: a drawing already made is there, and one not made yet stands as its
LaTeX while a bar at the top says how many are being made — *Making the
LaTeX drawings: 3 of 12* — and each comes into the page as it is made. On a
phone the page opens as quickly as any other, however many drawings it
holds.

**A drawing you are only trying is not kept for long.** While you are
typing, or trying a theme in the sheet, what is drawn lives in a small,
temporary place of its own, gone the next time the server starts; only a
document, a note or an exercise being **saved** keeps the drawings it
names, for as long as something still names them. Nothing you saved is
ever removed for being old — **Settings → LaTeX drawings** says how many
saved drawings there are, and **Forget drawings nothing uses** clears every
drawing that no document, deck or note names. Something in a trash counts
as gone: taken back, it is drawn again. A bar shows that it is working, and
the page says how many it let go.

## When it cannot be drawn

A block that cannot be drawn shows **its source**, in a frame, and **one
line saying why**, in plain words and with the line of the block where
LaTeX says one: a command a package would give (*\ce is not a command the
theme "default" knows… tick mhchem*), a brace missing, a package of its
theme that Parseh has not got yet (*mhchem is not among Parseh's own TeX
packages yet*), a theme this Parseh does not have, a compiler this computer
lacks, a drawing that took too long. An inline mark that cannot be drawn
shows its own LaTeX where it sits instead, without a frame — nothing that
small belongs in a box in the middle of a sentence. The rest of the page is
drawn. On the computer the frame has the button that mends it — the theme,
**Get mhchem…** for a package, or **Import a theme…** and **Make a theme
called …** for a theme that is not here. In the PDF and in an export the frame
stands where the drawing would, and the PDF's badge says how many could
not be made.

**To see what LaTeX was given, and what it said.** A frame of a block that went
to LaTeX has two more buttons. **The .tex that was compiled** opens, in a frame
on top of the page, the exact document LaTeX read — the theme's preamble, then
your block, as the computer wrote it for the compile and not built again to
show you. **The whole log** opens everything LaTeX wrote while it worked, with
the lines the sentence above was made from marked in red and the view scrolled
to the first. Each has its own **Copy**, and **Esc** closes it. They are kept
with the drawing for as long as it is, and a failure is kept as long as it
would be drawn the same way; in an export they are not there. In
**Settings → LaTeX drawings**, **Draw the sample** shows both under the picture
(or under the sentence, when it does not draw), above **The whole preamble**,
so that a theme that does not work can be read to the end.

**"LaTeX stopped without saying why"** used to be what a drawing said when
LaTeX's own message came from a *package* rather than from your block —
LaTeX writes such a message with the package's file name in front of it, where
Parseh looked for the block's. It now reads a message from any file, and says
which file asked: *The font "SkakNew-Diagram" is not on this computer in
skak.sty. It comes with the TeX Live package skaknew.* A compile that ends
*No pages of output* with no error in it is said as *LaTeX made no page*, and the
likeliest cause. The log, which Parseh keeps up to 512 KB of, also holds what the
programs LaTeX starts for a missing font print (kpathsea, mktextfm), which the
compiler's own log leaves out.

**A package that needs others TeX Live does not name.** A package may lean on
fonts and packages its own TeX Live entry does not list, so that getting it
alone leaves a drawing failing on the next missing file, one at a time. The
catalogue has one row for such a set — **xskak**, with the chess fonts and the
other packages it loads, among its **Games** — so that a theme that loads it
(ticked, or by name in its preamble, `skak` and `chessboard` too) asks for all
of them in one **Get**. For any other package, each missing file is said with
the **Get** that would bring it.
## Themes {#themes}

**Settings → LaTeX drawings** holds the themes, as many as you like, each
with a name of one word:

- **Packages** as checkboxes, each with a line and an example, in groups:
  **Base packages** — the basics every drawing uses, which come with the
  computer's TeX — `amsmath`,
  `amssymb`, `amsfonts`, `mathtools`, `bm`, `xcolor`, `siunitx`,
  `physics`; then letters and symbols (`mathrsfs`, `dsfont`, `esvect`,
  `stmaryrd`, `wasysym`, `marvosym`), operations and theorems (`cancel`,
  `slashed`, `relsize`, `amsthm`), drawings and plots (`tikz`, `tikz-cd`,
  `bayesnet`, `pgfplots`, `circuitikz`), chemistry (`mhchem`, `chemfig`),
  code (`listings`, `algorithm2e`), linguistics (`forest`,
  `tikz-dependency`), phonetics (`tipa`), scripts and annotation
  (`xpinyin`, pinyin over Chinese characters) and games (`xskak`, chess boards
  and games with their fonts).
- **Text in the languages Parseh teaches**: each language's face, as
  `\textfa{…}`, `\textja{…}`, `\texthi{…}` and so on, right to left
  where it is written so.
- **A font** of this computer's for the drawing.
- **A preamble of its own**, after the packages.
- **The compiler**: xelatex (a new theme's), pdflatex or lualatex.
- **A sample**, drawn with the theme as it stands in the editor: **Draw the
  sample** shows the picture, and **The .tex that was compiled** and **The whole
  log** under it, as [above](#when-it-cannot-be-drawn).

A fresh Parseh has three: **default**, which a block naming no theme is
drawn with, **chemistry** and **drawing**. **Make it the default** gives
another theme that part. **Export** saves a theme as a file to send to
somebody; **Import a theme…** reads one, and shows its whole preamble before
it is kept, under a name no other theme has. **Rename…** says first how
many blocks name the theme, and where — *3 documents, 1 exercise deck, 2
notes* — then rewrites the name in every one of them; if one of them cannot
be written (a deck taken out on a phone), nothing is renamed.

The same page says which of the three compilers this computer has, and
lists every **TeX package** the themes use, in two groups:

- **Parseh's own.** Every package a theme uses beyond the base — ticked,
  or loaded by name in its own preamble — is used by a drawing only once
  Parseh has got it into its own folder, `texmf/`, **even when the computer's TeX
  has it too**: what a drawing needs travels with Parseh, and **Remove…**
  really takes it away. A drawing that needs one Parseh has not got is not
  made: it says which, and offers to get it.
- **With this computer's TeX.** The base packages, and what every drawing
  loads (`standalone`, and `fontspec` for a font or the languages), come
  with the TeX this computer has. They are listed so that nothing is left
  out, marked as the computer's, with nothing to get or remove. One the
  computer's TeX lacks is listed with Parseh's own instead, to get into
  `texmf/`.

A package still missing — for a saved theme, or for the theme you are
editing and have not saved — reads *Not installed*, its size and its
licence, with why it is needed and its own **Get it**. Parseh asks the TeX Live repository what each costs as
soon as the page shows it, and downloads nothing until you press **Get
it**; if the repository cannot be reached the row says so and offers **Ask
again**. Packages are gotten one at a time, and a row says **Got** only once
it really is; **Get all** gets every ready package in one go. **Remove…**
asks first, in the row itself. Ticking a package this computer lacks in a
theme's editor says so at once — *Not installed here: circuitikz — see the
table* — and puts it in the table. **How long a drawing may take** is also
set here (30 seconds to begin with). **Forget drawings nothing uses** is
described [above](#drawn-once-the-same-everywhere).

Everything on the page may be changed from any device that has been let in,
a phone as well as the computer, as on the [reading
help](../lookup-and-languages/reading-help.md). The drawings are still made
by the computer Parseh runs on, and so are the packages it gets.

## Going back to an older Parseh

A version before a0.4.0 does not know a latex block: it shows its lines as
text. Going back from **Settings → Updating Parseh** says so first, under
*What may not survive going back*, and asks *I understand*. Nothing is
deleted, and when you come forward again every drawing is there.
