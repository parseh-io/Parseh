# LaTeX drawings

A `::::latex` block, or an inline `[…]{latex}` mark, is compiled on its own by `lib/latexdraw.py`, under its theme's preamble (`lib/latexthemes.py`) and compiler, and kept in `markdown/latex/` under a key that is the hash of everything that decides what it looks like: the block's LaTeX, the resolved theme, the TeX installation (the compiler's version and the packages Parseh got) and `RENDERER`, the module's own number. The module's header comment is the design; this file keeps what a header cannot: the things found by driving it.

## What is kept with a drawing (a0.5.4)

Beside `<key>.svg`, `<key>.pdf` and `<key>.json` the compile keeps `<key>.tex` — the exact document TeX was given, which `source()` built — and `<key>.log` — the log it wrote, up to `LOG_MAX` (512 KB) with a line saying where it was cut, and under it, marked as such, the lines of the compiler's terminal that its log does not hold (kpathsea and `mktextfm` looking for a font, xdvipdfmx). A failure, which has no picture, keeps them beside its `<key>.fail.json`, as long as its key stands. They are asked for by `/latex/<key>.tex` and `/latex/<key>.log`; nothing is built a second time to show them. `RENDERER` was raised to 3 for it: a drawing kept before has neither, so every drawing is made again once, with them. `explain()` reports `marks`, the lines of the log it read (the `FILE:LINE:` line or the `! ` line, and `l.N`), which the viewers mark and scroll to.

## A drawing that "stopped without saying why" (the owner's report, 2026-10-25)

A theme with `\usepackage{xskak}` and the sample `\newchessgame\mainline{1.e4 e5 2.Nf3 Nc6}\chessboard[hideblack]` ended with *LaTeX stopped without saying why* and the memory statistics of the log as the detail, "No pages of output" under them. Reproduced on a clean disposable `texmf/` (the packages got through `texpackages`, one at a time) and read to its end, there were two faults, one in what Parseh said and one in what Parseh got.

**What it said.** The first error of the log was `…/skak.sty:1774: Font LSB/skaknew/m/n/20=SkakNew-Diagram at 20.0pt not loadable: Metric (TFM) file or installed font not found.` With `-file-line-error` TeX writes a message from a *package* as `FILE:LINE: message` and one from the document as `d.tex:N: message`; `explain()` looked only for `d.tex:` and for a `! ` line, found neither, and fell through to its last resort, the tail of the log, which is memory statistics. A `! ` error raised inside a package also had its `l.N` taken for a line of the block, so a missing file asked for by `xskak.sty` was said to be on "line 1 of the block". `explain()` now reads a message from any file and says which file; takes `l.N` for the block only where TeX was reading the block; says a font TeX could not load with the package that has it (`FONT_PACKAGES`: `SkakNew…` → `skaknew`) and the install that mends it; and says a log that ends with no page and no error as *LaTeX made no page*, with the likeliest cause (an empty block, or nothing in it that typesets), never with the memory tail as the detail.

**What it got.** The TeX Live entries of `xskak`, `skak`, `chessboard` and `chessfss` declare no dependency, so getting them (and `collection-plaingeneric`, which brings `lambda-lists`) leaves a compile failing on the next missing file, one at a time: `chessfss.sty`, the fonts `skaknew`, `xifthen.sty` (which wants `ifmtarg`), `pst-node.sty` (which wants `pstricks`). A compile runs with no shell and `openout_any=p`, so a font that is not installed is not made on the fly (`mktextfm` is tried and fails, and the log now shows it). The skaknew fonts come as Type 1, TFM and OpenType: once they are there nothing has to be generated, and the board draws under xelatex, in the PDF that paper includes. The catalogue (`latexthemes.CATALOGUE`) therefore has one row, **xskak**, that names the whole set (`xskak, skak, chessfss, chessboard, skaknew, lambda-lists, xifthen, ifmtarg, pst-node, pstricks`); a theme that ticks it, or loads `xskak`, `skak`, `chessboard` or `chessfss` by name (`ALSO_LOADS`), is *Parseh's own* package like the others, and a drawing that lacks any of them asks for all of them in one **Get**. The set was found by drawing the sample from nothing; it is checked by `tests/test_latex.py` (`TheChessSetIsOneRow`), and the log of the font failure, with its paths made neutral, is kept as `tests/fixtures/latex/font-not-loadable.log`.

## The drawings of many documents, made in the background (a0.5.6)

A page opened before its drawings are made has them made by `static/latexwait.js` through `/api/docs/<id>/drawings`: four at a
time, each round answered with the whole page rendered again, under a bar that is that page's own. The library's **Make drawings of N
shown** (`#btn-make-drawings`, `static/app.js`) makes those of the documents it shows **without opening one**, and its work is a job of the
server, not of a page: `lib/latexbatch.py`.

- `POST /api/latex/make {ids}` reads each saved document (`htmlgen.latex_wanted`: blocks and inline marks, in the text and in the
  exercises, steps of a follow-up included), `latexbatch.sort_out` keeps the **distinct** drawings (by `latexdraw.peek`'s key, so a
  drawing two documents share is one) that are not made and not known to fail, and `latexbatch.start` makes them in a thread. The answer
  is the job's status; `total` 0 is "nothing to make" and starts no thread. `GET /api/latex/make` is the status a page asks every
  700 ms, `POST /api/latex/make/stop` begins no new drawing. One batch at a time (`Busy`, answered 409 with how far the first has got).
- The batch keeps **only as many compiles in `latexdraw._POOL` as the pool has workers** (a sliding window, not a queue of every drawing):
  a page opened meanwhile, whose own drawings go through the same pool, waits for one compile and never for the rest of the batch.
  A drawing that fails, or raises, is over and kept as a problem with its document; the batch goes on. Nothing is written but where
  `latexdraw` keeps its drawings, and a document's ownership of them (`owners.json`) is what saving it already recorded.
- **The bar is the activity list's** (`lib/activity.py`, `lib/activity.js`, `serve.py`'s `activity_now`): `latexbatch.activity_entries`
  gives one entry, kind `compile`, with the page's `?job=` token so that the page shows it once from the first moment
  (`ParsehActivity.expect(...).url(...)`), and the new `unit` field `"items"`: `done` and `total` count drawings, not bytes, so
  `activity.js` draws the share (`pct`) and "41 of 63" (`meta`) at every moment, where for bytes it draws a percentage only while they are
  moving; while an entry of that unit runs the list is asked every 600 ms (`COUNTED`) instead of 1500, so the bar goes on in small steps.
  An entry of bytes has no `unit` key at all. A studio run on its own has no activity list: the page then draws its own `<progress>` and number.
- Tests: `tests/test_latex_batch.py` (the job with the TeX left out, the entry, the routes, the hub's list) and `tests/latex_batch.mjs`
  (63 drawings made for real, `studio_harness.py --latex-slow=0.12` to give the bar time to be looked at, the pill, the hub's panel,
  Stop, a failure, a reload, a studio with no hub).
