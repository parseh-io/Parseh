# LaTeX drawings

A `::::latex` block, or an inline `[…]{latex}` mark, is compiled on its own by `lib/latexdraw.py`, under its theme's preamble (`lib/latexthemes.py`) and compiler, and kept in `markdown/latex/` under a key that is the hash of everything that decides what it looks like: the block's LaTeX, the resolved theme, the TeX installation (the compiler's version and the packages Parseh got) and `RENDERER`, the module's own number. The module's header comment is the design; this file keeps what a header cannot: the things found by driving it.

## What is kept with a drawing (a0.5.4)

Beside `<key>.svg`, `<key>.pdf` and `<key>.json` the compile keeps `<key>.tex` — the exact document TeX was given, which `source()` built — and `<key>.log` — the log it wrote, up to `LOG_MAX` (512 KB) with a line saying where it was cut, and under it, marked as such, the lines of the compiler's terminal that its log does not hold (kpathsea and `mktextfm` looking for a font, xdvipdfmx). A failure, which has no picture, keeps them beside its `<key>.fail.json`, as long as its key stands. They are asked for by `/latex/<key>.tex` and `/latex/<key>.log`; nothing is built a second time to show them. `RENDERER` was raised to 3 for it: a drawing kept before has neither, so every drawing is made again once, with them. `explain()` reports `marks`, the lines of the log it read (the `FILE:LINE:` line or the `! ` line, and `l.N`), which the viewers mark and scroll to.

## A drawing that "stopped without saying why" (the owner's report, 2026-10-25)

A theme with `\usepackage{xskak}` and the sample `\newchessgame\mainline{1.e4 e5 2.Nf3 Nc6}\chessboard[hideblack]` ended with *LaTeX stopped without saying why* and the memory statistics of the log as the detail, "No pages of output" under them. Reproduced on a clean disposable `texmf/` (the packages got through `texpackages`, one at a time) and read to its end, there were two faults, one in what Parseh said and one in what Parseh got.

**What it said.** The first error of the log was `…/skak.sty:1774: Font LSB/skaknew/m/n/20=SkakNew-Diagram at 20.0pt not loadable: Metric (TFM) file or installed font not found.` With `-file-line-error` TeX writes a message from a *package* as `FILE:LINE: message` and one from the document as `d.tex:N: message`; `explain()` looked only for `d.tex:` and for a `! ` line, found neither, and fell through to its last resort, the tail of the log, which is memory statistics. A `! ` error raised inside a package also had its `l.N` taken for a line of the block, so a missing file asked for by `xskak.sty` was said to be on "line 1 of the block". `explain()` now reads a message from any file and says which file; takes `l.N` for the block only where TeX was reading the block; says a font TeX could not load with the package that has it (`FONT_PACKAGES`: `SkakNew…` → `skaknew`) and the install that mends it; and says a log that ends with no page and no error as *LaTeX made no page*, with the likeliest cause (an empty block, or nothing in it that typesets), never with the memory tail as the detail.

**What it got.** The TeX Live entries of `xskak`, `skak`, `chessboard` and `chessfss` declare no dependency, so getting them (and `collection-plaingeneric`, which brings `lambda-lists`) leaves a compile failing on the next missing file, one at a time: `chessfss.sty`, the fonts `skaknew`, `xifthen.sty` (which wants `ifmtarg`), `pst-node.sty` (which wants `pstricks`). A compile runs with no shell and `openout_any=p`, so a font that is not installed is not made on the fly (`mktextfm` is tried and fails, and the log now shows it). The skaknew fonts come as Type 1, TFM and OpenType: once they are there nothing has to be generated, and the board draws under xelatex, in the PDF that paper includes. The catalogue (`latexthemes.CATALOGUE`) therefore has one row, **xskak**, that names the whole set (`xskak, skak, chessfss, chessboard, skaknew, lambda-lists, xifthen, ifmtarg, pst-node, pstricks`); a theme that ticks it, or loads `xskak`, `skak`, `chessboard` or `chessfss` by name (`ALSO_LOADS`), is *Parseh's own* package like the others, and a drawing that lacks any of them asks for all of them in one **Get**. The set was found by drawing the sample from nothing; it is checked by `tests/test_latex.py` (`TheChessSetIsOneRow`), and the log of the font failure, with its paths made neutral, is kept as `tests/fixtures/latex/font-not-loadable.log`.

## The drawings of many documents, made by a helper process (a0.5.6; a helper since a0.5.7)

A page opened before its drawings are made has them made by `static/latexwait.js` through `/api/docs/<id>/drawings`: four at a
time, each round answered with the whole page rendered again, under a bar that is that page's own. The library's **Make drawings of N
shown** (`#btn-make-drawings`, `static/app.js`) makes those of the documents it shows **without opening one**, and its work is a job of the
server, not of a page: `lib/latexbatch.py`.

**a0.5.6 did it in threads of the server, and the server paid for it** (the owner: the bar was worse than the other one, and going to the hub
meanwhile gave slowdowns): the POST read and planned every document before it answered (1.6 s for 150 documents, the page saying nothing),
the scan, the planning and the PDF-to-SVG step took the GIL from the threads that answer pages (requests up to 0.6 s on two cores, five times
their usual time), the bookkeeping of each finished drawing rewrote `owners.json` under the lock every page's lookups take, and the TeX ran at
the same priority as the browser. a0.5.7 moved all of it out:

- `POST /api/latex/make {ids}` validates the ids, writes `spec.json` into `drawn/.batch/<pid>-<n>/` and starts
  `python lib/latexbatch.py --worker <spec>`; it answers at once with the status (`starting`). **Nothing is read in the request.**
  `GET /api/latex/make` is the status (the file `status.json`, read by its time and size), `POST /api/latex/make/stop` writes the file `stop`.
  One batch at a time (`Busy`, 409 with the first one's status).
- **The helper** (`latexbatch.work`) runs at **nice 19** (the idle class on Windows) and so does every TeX it starts. It looks through the documents
  one at a time yielding between two (`phase` `scanning`, a count of documents), works out the distinct drawings not made yet by
  `latexdraw.peek`'s key (`planning`), and makes them (`making`, a count of drawings) with `workers()` side by side: half the cores, four at most,
  and as many as the free memory holds (900 MB each after 900 MB are kept); with little memory free it begins no new run beside those under way
  (`waiting`). It writes `status.json` whole, at most every 0.2 s, and never touches `owners.json` (`latexdraw.BOOKKEEPING = False`). It watches its
  parent every two seconds and ends, with its TeX, when the server is gone (not `PR_SET_PDEATHSIG`: Linux sends that when the *thread* that started the
  child ends, and that thread is the request's).
- `latexdraw._mark_unowned` rewrites the books only when it changes them (it rewrote the whole file for every drawing made); `drawn/.batch` is
  never a drawing (`_persistent_keys`, `prune`) and is removed at the server's start.
- **The bar is the activity list's** (`lib/activity.py`, `lib/activity.js`, `serve.py`'s `activity_now`): `latexbatch.activity_entries` gives one entry,
  kind `compile`, with the page's `?job=` token (`ParsehActivity.expect(...).url(...)`), whose label and counts follow the stage (*Looking through N
  documents*, then *Making the LaTeX drawings of N documents*), and the `unit` field `"items"`: `done` and `total` count documents and then drawings, not
  bytes, so `activity.js` draws the share (`pct`) and "41 of 63" (`meta`) at every moment; while an entry of that unit runs the list is asked every 600 ms
  (`COUNTED`). The stage line says how many are being made and for which document. An entry of bytes has no `unit` key.
- The page answers at the click ("Starting…", before the POST returns), asks for the status once a second (0.7 s where there is no activity list)
  and draws its own `<progress>` only there.
- Tests: `tests/test_latex_batch.py` (the helper's work with the TeX left out; the server's side with a stand-in process; the routes; the books; and the
  REAL helper: nice 19 for it and its TeX, killed with its parent) and `tests/latex_batch.mjs` (63 drawings made for real, the pill, the hub's
  panel, Stop, a failure, a reload, a studio with no hub, and a library of 120 more documents: the answer in a moment, the hub quick meanwhile,
  pages opened to and fro with no failed request). `studio_harness.py --latex-slow=SECONDS` gives the bar time to be looked at.
