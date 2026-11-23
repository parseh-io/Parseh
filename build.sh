#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Build one book, or every book.
#
#   ./build.sh                 every book that changed: PDF + reader + index
#   ./build.sh boof-e-koor     just that one (a slug, persian/boof-e-koor, or the
#                              directory as a shell completes it, books/persian/boof-e-koor/)
#   ./build.sh --html          skip LaTeX, rebuild readers and index only
#   ./build.sh --force         ignore the cache and rebuild even if unchanged
#   ./build.sh --draft ch3h    a PDF of just those chapters, in seconds
#   ./build.sh --draft ch3h ch3i
#
# Each book is a directory books/<language>/<slug>/ with a book.json, the
# language folder being the registry's (lib/languages.json: persian, arabic,
# italian and so on, one per row -- docs/languages.md section 2).  Nothing here has a list
# of books or of languages in it: adding a directory is all it takes.  A
# book.json lying directly under books/, the layout before languages, is still
# built, as a Persian book, with a note asking for it to be moved.
#
# WHY THERE IS A CACHE.  One lualatex pass over Buf-e Kur is about eleven
# minutes -- 2500 pages, four passes of bidi shaping over every sentence -- and
# the book needs two of them.  Rebuilding a book nothing touched, or rebuilding
# the whole book to look at one paragraph, is the difference between a second
# and three quarters of an hour.  So:
#
#   * a book whose sources are unchanged is skipped outright;
#   * the second lualatex pass runs only if the first moved .aux or .toc;
#   * --draft builds only the chapters named, for looking at your own work.
#
# THE RULE THE CACHE IS WRITTEN AROUND: a false rebuild only costs time, but a
# false *skip* serves a stale PDF as if it were current, and there is nothing
# downstream that would notice.  Every judgement call here is therefore settled
# in favour of rebuilding.  Three consequences worth keeping:
#
#   * a key is recorded ONLY on a path that actually ran the tool it stands for
#     -- --html must never stamp the LaTeX key, or the next real build skips a
#     chapter that was never typeset;
#   * a key is captured BEFORE the tool runs and written after it succeeds, so
#     an edit made during the eleven minutes leaves the key stale and forces a
#     rebuild rather than being recorded as already built;
#   * a tool that fails must not have its key written, which means its exit
#     status may not be swallowed by a pipe (`| sed` hides it) or by `|| true`.
#
# The LaTeX key ignores the "% @par" timing comments, because those are
# whole-line comments that TeX eats with their newline and so cannot move a
# single page.  timestamp.py --from-sidecar is run before the keys are taken,
# so both keys describe the tree as it will be left.
#
# Both keys take in everything a build reads that is not the book's own: the
# shared preamble and front matter, every lib/lang/<code>.tex (the preamble
# inputs the book's), lib/languages.json and config/languages.json (the
# registry's two halves, Parseh's languages and this machine's: the preamble
# reads the fonts from them, and the reader its language record -- a missing
# config/languages.json adds nothing to either key), the fonts, and lib/*.py
# for the reader.  A file left out of a key is a change that can never
# trigger a rebuild -- exactly the false skip the rule above forbids.
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

# The environment's python3 first on the PATH (lib/env.sh), so that the readers
# are built by the Python that has the packages whether or not anybody
# activated anything -- the build button in the pages runs this script too.
. "$ROOT/lib/env.sh"
parseh_env

# The Persian and Arabic faces travel with the repo, so no font need be
# installed on the machine for them (the CJK faces are the system's).
# luaotfload reads OSFONTDIR, which is how LuaLaTeX is told where to look.
OSFONTDIR="$ROOT/lib/fonts:/usr/share/fonts:/usr/local/share/fonts:$HOME/.local/share/fonts"
export OSFONTDIR

ONLY=""; HTML_ONLY=""; FORCE=""; DRAFT=""; DRAFT_CH=""
for a in "$@"; do
  case "$a" in
    --html)  HTML_ONLY=1 ;;
    --force) FORCE=1 ;;
    --draft) DRAFT=1 ;;
    --*)     echo "unknown option: $a"; exit 2 ;;
    *)       if [ -n "$DRAFT" ]; then DRAFT_CH="$DRAFT_CH $a"; else ONLY="$a"; fi ;;
  esac
done
# A book is named by its slug or by <language>/<slug>, but what a shell
# tab-completes is the directory -- books/persian/<slug>/, ./books/..., or the
# absolute path -- and that used to build nothing and exit 2.  Reduce every
# such spelling to <language>/<slug> before book_wanted ever sees it.
ONLY="${ONLY#"$ROOT"/}"; ONLY="${ONLY#./}"; ONLY="${ONLY#books/}"; ONLY="${ONLY%/}"

# ---------------------------------------------------------------- diagnostics
# A PDF is not proof of success and neither is a silent log.  Four different
# things have each produced a "clean" build of a damaged book:
#
#   * "no output PDF file produced" -- the obvious one;
#   * a ! error under nonstopmode -- a mistyped \Cgreen dropped the chunk it
#     was on and carried happily on to the end;
#   * a Lua error inside \directlua -- these do NOT start with a !.  When
#     frank_breaks hit one, \directlua abandoned the chunk, tex.sprint never
#     ran, and EVERY chunk in passes 2 and 3 came out empty.  The book lost
#     145 pages of Persian and still reported 0 errors;
#   * lualatex never running at all -- killed, or missing.  The log and the PDF
#     from the PREVIOUS run are still lying there and pass every test above.
#     So the log is deleted before each run and its absence is a failure, and
#     "Output written on" must be present as positive proof of completion.
check_log() {                     # check_log <logfile> <pdf> <basename>
  log="$1"; pdf="$2"; b="$3"
  if [ ! -f "$log" ]; then
    echo "   NO LOG at $log -- lualatex did not run"
    return 1
  fi
  if grep -q "no output PDF file produced" "$log" 2>/dev/null || [ ! -f "$pdf" ]; then
    echo "   PDF FAILED -- first error from $log:"
    grep -m1 -A4 '^!' "$log" 2>/dev/null | sed 's/^/     /'
    return 1
  fi
  if ! grep -q "Output written on .*$b\.pdf" "$log" 2>/dev/null; then
    echo "   $log has no \"Output written on\" -- the run did not finish;"
    echo "   the PDF beside it is from an earlier build and is NOT current"
    return 1
  fi
  if grep -q '^!' "$log" 2>/dev/null; then
    echo "   LaTeX ERRORS in $log (a PDF was still produced, so check it):"
    grep -n -m3 -A3 '^!' "$log" | sed 's/^/     /'
    return 1
  fi
  if grep -q '^\[\\directlua\]\|attempt to \(get\|call\|index\|perform\|concatenate\)' "$log" 2>/dev/null; then
    # grep -c PRINTS 0 and EXITS 1 when nothing matches, so the status is
    # swallowed rather than allowed to append a second zero of its own.
    n="$(grep -c '^\[\\directlua\]' "$log" 2>/dev/null || true)"
    echo "   LUA ERRORS in $log (${n:-0} of them) -- \\directlua abandoned its chunk,"
    echo "   so whatever it was printing is MISSING from the PDF:"
    grep -n -m2 -B1 -A4 '^\[\\directlua\]\|attempt to ' "$log" | sed 's/^/     /'
    return 1
  fi
  return 0
}

# run_latex <dir> <mainfile> <basename> -- deletes the old log first, so that a
# run which never happens cannot be mistaken for one that succeeded.
run_latex() {
  rm -f "$1/$3.log"
  ( cd "$1" && lualatex -interaction=nonstopmode "$2" >/dev/null 2>&1 ) || true
}

# ---------------------------------------------------------------- cache keys
# Concatenation is done with find -print0 | sort -z | xargs -0, never with an
# unquoted glob: the project path itself contains spaces, and a word-split file
# list would quietly hash nothing at all and freeze the key at a constant.
#
# frankdraft.tex is excluded: --draft writes one into the book directory, and a
# glob that swept it up would make every draft invalidate the real book's cache
# and buy an eleven-minute rebuild of a PDF the draft cannot have changed.
cat_book_tex() {
  find "$1" -maxdepth 1 -name '*.tex' ! -name 'frankdraft.tex' -print0 \
    | sort -z | xargs -0 cat 2>/dev/null || true
}
cat_lib_py() {                    # everything tex2html.py imports, not just itself
  find "$ROOT/lib" -maxdepth 1 -name '*.py' -print0 | sort -z | xargs -0 cat 2>/dev/null || true
}
cat_fonts() {                     # embedded in the PDF, and served to the reader
  find "$ROOT/lib/fonts" -type f -print0 | sort -z | xargs -0 cat 2>/dev/null || true
}
cat_lib_lang() {                  # the per-language halves of the preamble
  find "$ROOT/lib/lang" -maxdepth 1 -name '*.tex' -print0 | sort -z | xargs -0 cat 2>/dev/null || true
}
# timestamp.py's own AT_RE is ^%\s*@(t|par)\b -- match that exactly, or a line it
# rewrites in a shape this does not strip would move the LaTeX key for nothing.
strip_at() { grep -v -E '^%[[:space:]]*@(t|par)\b' || true; }

# HASHING, ON A MAC AS ON LINUX.  sha1sum is GNU: a stock macOS ships shasum
# (and nothing called sha1sum), so every key came out EMPTY there -- and two
# empty keys are equal, which is the one thing a cache key must never be.
# After the first build, "unchanged, keeping the PDF" was then the answer to
# every edit, and the pages' build buttons served a stale PDF for ever.  The
# tool is chosen once, here, and used through this one name.
#
# With neither on the machine, a key that is never twice the same turns the
# cache OFF rather than freezing it: a rebuild that was not needed costs
# time, a skip that was not earned costs the truth of the PDF -- the rule
# this whole cache is written around.
if command -v sha1sum >/dev/null 2>&1; then
  sha1() { sha1sum | cut -d' ' -f1; }
elif command -v shasum >/dev/null 2>&1; then
  sha1() { shasum -a 1 | cut -d' ' -f1; }
else
  echo "note: no sha1sum and no shasum on this machine -- the build cache is off,"
  echo "      so every book is rebuilt whether it changed or not"
  # a key from /dev/urandom, not from a counter: every call is made in its
  # own subshell ($(...)), where a shell variable could not be carried
  # forward, and two calls that returned the same word would look like a
  # book nothing had touched
  sha1() {
    cat >/dev/null
    printf 'no-sha1-%s\n' "$(od -An -N8 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')"
  }
fi

# `find -printf` is GNU too.  Run from inside the directory, find names the
# files as ./<path>, which is %P once the ./ is off -- the same list, in the
# same order after sort, on either find.
list_rel() {                      # list_rel <dir> -- every file under it, relative
  ( cd "$1" 2>/dev/null && find . -type f | sed 's|^\./||' | sort ) || true
}

latex_key() {
  { cat_book_tex "$1" | strip_at
    cat "$ROOT/lib/frank-preamble.tex" "$ROOT/lib/frank-frontmatter.tex" \
        "$ROOT/lib/languages.json" "$ROOT/config/languages.json" "$1/book.json" \
        2>/dev/null || true
    cat_lib_lang
    cat_fonts
  } | sha1
}
# What the reader is built from: the same .tex WITH their timing comments, the
# sidecar, and the whole generator surface -- tex2html.py imports texparse,
# timestamp and books, so hashing tex2html.py alone would miss a change in any
# of them.
reader_key() {
  # every cat is failure-proofed: this whole group runs under set -e in a
  # subshell, and a missing timings.json (a book with no narration) would
  # otherwise abort it MID-STREAM -- the key then hashed a truncated stream
  # that never included lib/*.py, so a tool change could never invalidate
  # that book's reader.  Exactly the false-skip class, found live.
  { cat_book_tex "$1"
    # reading.json belongs here too: the page is built FROM it -- what is
    # folded away and which paragraphs depart from their source are baked in
    # as FOLDED and FREE -- so a book whose only change is a fold would
    # otherwise hash the same, and "rebuild the reader" would write nothing
    # and report success.
    cat "$1/book.json" "$1/timings.json" "$1/reading.json" \
        "$ROOT/lib/languages.json" "$ROOT/config/languages.json" 2>/dev/null || true
    # The reader includes audio controls only for recordings present on disk.
    # A linked backup restores the metadata first; copying audio/ back later
    # must invalidate this key without hashing hundreds of MB of recordings.
    if [ -d "$1/audio" ]; then
      list_rel "$1/audio"
    fi
    cat_lib_py
    cat_fonts
  } | sha1
}

# ---------------------------------------------------------------- the books
# Both loops below walk books/*/*/ (books/<language>/<slug>/) and then books/*/
# for a legacy book; a directory without a book.json is not a book (books/persian/
# itself, a book's source/ or reader/).  Relative globs, and a for over them,
# not a $(...) list: the project path has spaces and a word-split list would
# lose them, while a glob is never split.  book_note prints the legacy
# note once per book; book_wanted says whether ONLY names this book -- by
# its slug, or by <language>/<slug> when two languages share a slug (the
# directory spellings were reduced to that just after the option loop).
book_note() {                     # book_note <dir>
  case "$1" in
    books/*/*/) ;;
    *) echo "   note: $(basename "$1") lies directly under books/ -- move it to books/<language>/$(basename "$1")/ (docs/languages.md section 2)" ;;
  esac
}
book_wanted() {                   # book_wanted <dir>: true when ONLY is empty or names it
  [ -z "$ONLY" ] && return 0
  slug="$(basename "$1")"
  folder="$(basename "$(dirname "$1")")"
  [ "$ONLY" = "$slug" ] && return 0
  [ "$ONLY" = "$folder/$slug" ] && return 0
  return 1
}

# ---------------------------------------------------------------- draft build
# One or more chapter files, on their own, with the real preamble and front
# matter so that nothing is defined differently from the real book.  Written
# under its own jobname so it can never touch main.aux or main.pdf, and given
# a single pass, because a draft has no page references worth resolving.
if [ -n "$DRAFT" ]; then
  [ -n "$DRAFT_CH" ] || { echo "--draft needs at least one chapter, e.g. --draft ch3h"; exit 2; }
  did=""
  for d in books/*/*/ books/*/; do
    slug="$(basename "$d")"
    [ -f "$d/book.json" ] || continue
    book_wanted "$d" || continue
    have=""
    for c in $DRAFT_CH; do [ -f "$d/${c%.tex}.tex" ] && have=1; done
    [ -n "$have" ] || continue
    main="$(python3 -c "import json;print(json.load(open('$d/book.json'))['main'])")"
    inputs=""
    for c in $DRAFT_CH; do
      f="${c%.tex}.tex"
      [ -f "$d/$f" ] || { echo "== $slug: no $f, skipping it"; continue; }
      inputs="$inputs\\\\input{$f}
"
    done
    [ -n "$inputs" ] || continue
    echo "== $slug draft:$DRAFT_CH"
    book_note "$d"
    # main.tex with its chapter \inputs swapped for just the ones asked for
    awk -v repl="$inputs" '
      /^\\input\{ch/ { if (!done) { printf "%s", repl; done=1 } ; next }
      { print }
    ' "$d/$main" > "$d/frankdraft.tex"
    # a previous draft's .aux/.toc would put ITS contents page and outline in
    # this one, and a half-written one dies inside \BKM@entry
    rm -f "$d/frankdraft.aux" "$d/frankdraft.out" "$d/frankdraft.toc"
    run_latex "$d" "frankdraft.tex" "frankdraft"
    check_log "$d/frankdraft.log" "$d/frankdraft.pdf" "frankdraft" || exit 1
    pages="$(grep -o 'frankdraft.pdf ([0-9]* pages' "$d/frankdraft.log" 2>/dev/null | tail -1 | grep -o '[0-9]*' || true)"
    echo "   $d/frankdraft.pdf  (${pages:-?} pages)"
    did=1
  done
  if [ -z "$did" ]; then
    echo "--draft: no book has any of:$DRAFT_CH"
    exit 2
  fi
  exit 0
fi

# ---------------------------------------------------------------- full build
built=0; skipped=0; matched=""; failed=""
for d in books/*/*/ books/*/; do
  slug="$(basename "$d")"
  [ -f "$d/book.json" ] || continue
  book_wanted "$d" || continue
  matched=1
  book_note "$d"
  main="$(python3 -c "import json,sys;print(json.load(open('$d/book.json'))['main'])")"
  [ -f "$d/$main" ] || { echo "== $slug: no $main yet, skipping"; continue; }
  base="$(basename "$main" .tex)"
  log="$d/$base.log"; pdf="$d/$base.pdf"

  # A regenerated batch loses its % @par comments; the sidecar restores them.
  # Done BEFORE the keys are taken so that both describe the tree as it will be
  # left -- otherwise the reader key would be stale by exactly this edit and
  # every run would rebuild the reader once for nothing.
  if [ -f "$d/timings.json" ]; then
    ( cd "$d" && python3 "$ROOT/lib/timestamp.py" --from-sidecar >/dev/null 2>&1 ) || true
  fi

  key="$(latex_key "$d")"
  old=""; [ -f "$d/.build-key" ] && old="$(cat "$d/.build-key")"

  if [ -z "$HTML_ONLY" ]; then
    if [ -z "$FORCE" ] && [ "$key" = "$old" ] && [ -f "$pdf" ]; then
      echo "== $slug: unchanged, keeping the PDF  (--force to rebuild)"
      skipped=$((skipped+1))
    else
      echo "== $slug"
      pdf_failed=""
      # pass 1, then a second only if it moved anything a second pass would fix
      before="$(cat "$d/$base.aux" "$d/$base.toc" 2>/dev/null | sha1)"
      run_latex "$d" "$main" "$base"
      # A build that was killed part-way leaves a half-written .aux/.out/.toc,
      # and the next run dies inside them -- "File ended while scanning use of
      # \BKM@entry" -- which looks like a bug in the book and is not.  Clear
      # them and try once more before believing the error.
      if ! check_log "$log" "$pdf" "$base" >/dev/null 2>&1; then
        echo "   first pass failed; clearing stale .aux/.out/.toc and retrying once"
        rm -f "$d/$base.aux" "$d/$base.out" "$d/$base.toc"
        run_latex "$d" "$main" "$base"
      fi
      # A PDF THAT WILL NOT BUILD MUST NOT COST THE READER.  This used to
      # `exit 1` here, which is three steps above the reader: a book whose TeX
      # errors -- or a machine with no lualatex at all -- got no reader either,
      # and since every page builds through this script, there was then no way
      # to make one from the pages.  lib/bookbuild.py's own build, the path
      # taken where there is no sh, has always carried on to the reader and
      # reported the failure at the end; this now agrees with it.  The key is
      # still written only where lualatex ran and its output was judged sound.
      if check_log "$log" "$pdf" "$base"; then
        after="$(cat "$d/$base.aux" "$d/$base.toc" 2>/dev/null | sha1)"
        if [ "$before" != "$after" ]; then
          echo "   references moved, second pass"
          run_latex "$d" "$main" "$base"
          check_log "$log" "$pdf" "$base" || pdf_failed=1
        else
          echo "   references already settled, second pass not needed"
        fi
      else
        pdf_failed=1
      fi
      if [ -z "$pdf_failed" ]; then
        ovf="$(grep -c Overfull "$log" 2>/dev/null || true)"
        pages="$(grep -o "$base.pdf ([0-9]* pages" "$log" 2>/dev/null | tail -1 | grep -o '[0-9]*' || true)"
        echo "   pdf: ${ovf:-0} overfull boxes, ${pages:-?} pages"
      fi
      # A machine without this language's hyphenation patterns still builds a
      # clean PDF -- babel drops back to English and says so once, in the log,
      # among thirty thousand lines nobody opens, and every line of the book is
      # then broken where an English word would break.  It is not an error and
      # must not stop the build, but it belongs beside the page count, which is
      # the line someone actually reads.  Only the book's OWN language counts:
      # babel reports the same fallback for canadian and newzealand in every
      # run.  The name to match is babel's, which is the registry's (tex.babel,
      # `ngerman` for German), never the folder's -- and only for a language
      # the registry says HAS patterns (tex.hyphen).  Persian, Arabic and
      # Japanese fall back to English in every log there has ever been and are
      # none the worse: English patterns are made of ASCII letters, which those
      # three scripts do not contain, so no break point is ever found.  Warning
      # about them would put a false alarm on the Persian book for ever.
      bab="$(python3 -c "import json,sys; sys.path.insert(0, '$ROOT/lib'); import languages
L = languages.get_or_default(json.load(open('$d/book.json')).get('language'))
print(L.tex['babel'] if L.tex.get('hyphen') else '')" 2>/dev/null || true)"
      if [ -n "$bab" ] && grep -q "Hyphen rules for '$bab' set to" "$log" 2>/dev/null; then
        echo "   NO HYPHENATION PATTERNS for $bab -- every line was broken at ENGLISH"
        echo "   points.  The PDF is sound and the line breaks are wrong; fix it with"
        echo "   ./install.sh --pdf and rebuild with --force."
      fi
      # written only here: on the one path where lualatex actually ran and its
      # output was judged sound, and with the key taken BEFORE it started.  A
      # PDF that failed leaves no key, so the next run tries it again rather
      # than calling it unchanged.
      if [ -n "$pdf_failed" ]; then
        echo "   the PDF did not build -- writing the reader anyway"
        failed=1
      else
        printf '%s\n' "$key" > "$d/.build-key"
        built=$((built+1))
      fi
    fi
  fi

  rkey="$(reader_key "$d")"
  rold=""; [ -f "$d/.reader-key" ] && rold="$(cat "$d/.reader-key")"
  if [ -z "$FORCE" ] && [ "$rkey" = "$rold" ] && [ -f "$d/reader/index.html" ]; then
    echo "   reader unchanged"
  else
    # not `python3 ... | sed`: a pipe reports the status of the LAST command, so
    # a crashed generator would look like a success and get its key written
    if ! out="$( cd "$d" && python3 "$ROOT/lib/tex2html.py" 2>&1 )"; then
      printf '%s\n' "$out" | sed 's/^/   /'
      echo "   reader FAILED for $slug"
      exit 1
    fi
    printf '%s\n' "$out" | sed 's/^/   /'
    printf '%s\n' "$rkey" > "$d/.reader-key"
  fi
done

if [ -n "$ONLY" ] && [ -z "$matched" ]; then
  echo "no book named '$ONLY' under books/<language>/ -- nothing was built"
  exit 2
fi

python3 lib/make_index.py
echo
echo "$built book(s) built, $skipped unchanged"
echo "Serve everything with:  ./serve.sh"
# A PDF that would not build is still a failure and the caller has to hear it.
# The reader was written anyway -- that is the whole point of carrying on --
# but nothing here may report success for a book whose PDF is missing or is
# left over from an earlier run.
if [ -n "$failed" ]; then
  echo
  echo "at least one PDF did not build; its reader was written, see above"
  exit 1
fi
