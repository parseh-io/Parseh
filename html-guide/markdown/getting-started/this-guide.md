---
title: This guide
weight: 10
description: Opening this guide from Parseh, from the disk or on the web, compiling it from its front page, and finding your way in it.
---

This guide is a set of web pages that need no server to be read. Parseh
serves them, but the same pages open straight from the disk, and can be
put on any website.

## Opening it

**From Parseh**, at `https://localhost:7654/guide/`:

- the **guide** button in the hub's top bar;
- **Guide**, *How the toolbox works*, the last door of the hub's
  [mobile interface](mobile-mode.md);
- **the guide** at the foot of the hub;
- the **guide** button of the clip tray's top bar, which opens it in a tab
  of its own;
- the **guide** button in the top bar of every other page — a book's
  reader, the book library, a video's page, the video index, the pages that
  add a book or a video, a document and its editor, a deck, the Anki page,
  Settings — which opens the page of this guide about that page.

Some top bars have no room for one more button: the studio's library and
the list of exercise decks, and every page's bar in the
[mobile interface](mobile-mode.md). There **The guide to this page** is a
line at the foot of the page. On every page with a **⚙** it is also at the
foot of the gear's sheet, under *Parseh's own settings*: that is where a
book's reader and a video's page have it on a phone.

Served by Parseh, every page of the guide has a **Parseh** link in its top
bar, back to the hub.

**From the disk**, open `html-guide/index.html`, in the Parseh folder, in
any browser. Everything works there too — the list of pages, the search,
the exercises, the formulas — because nothing on these pages asks a
server for anything. The one exception is a YouTube video: YouTube plays
one inside a page only when the page was served, so from the disk each
video is a card, **Watch on YouTube** (on a phone, **YouTube** and the
time the clip starts at), that opens it on YouTube in a new tab.

**On the web**, the project publishes it at <https://parseh.io/guide/>: the
same pages, under a slim bar that leads to Parseh's site. That is the address
a page exported from Parseh gives for the guide, and it stays. Anyone's own
copy can be published the same way, to GitHub Pages, at
`https://<account>.github.io/<repository>/`;
[Compiling and publishing](../writing-this-guide/compiling.md) says how that
is switched on.

## When it needs compiling

The pages are written in Markdown, in `html-guide/markdown/`, and become
the web pages you are reading when they are **compiled**. The installer
does that every time it runs — `./install.sh --guide` does it and nothing
else — so after an installation they are simply there.

When they are not — the pages were never compiled, or the Markdown has
changed since they were — the guide's front page, opened from Parseh,
says so and offers the button:

| The front page says | The button |
|---|---|
| **The guide has not been compiled yet.** | **Compile the guide** |
| **The guide was compiled from older pages.** Compile it again to see the newest. | **Compile the guide again** |
| **Compiling the guide…** | **Compiling…**, while it works |
| **Compiled.** Opening the new pages… | — the page reloads by itself |
| **The last compile failed.** What it said is below. | **Compile the guide again** |

A compile takes a second or two, and while it runs it is on Parseh's
[Working… list](working-indicator.md): *Compiling the guide* on the
pill in the corner of this page, and on the hub. One that ends with errors
still writes every page it can, opens them, and shows what went wrong on
the front page.
A page of a guide never compiled leads back to the front page, where the
button is.

Opened from the disk, where there is no server to compile it, the front
page says instead that the guide has not been compiled yet, that the
installer compiles it, and that Parseh's **guide** button opens the page
with the button on it; the list of pages says *The list of pages appears
once the guide is compiled.*

## Finding your way

- **The list of pages**, on the left: the sections and their pages, the
  one you are reading marked and its section open. **☰** puts it away and
  brings it back, and the list remembers that, and which sections you
  opened or closed, from page to page. On a phone it is a drawer that ☰
  slides over the page; a tap beside it, or Escape, closes it.
- **The search box**, at the top of the list — *Search the guide* — looks
  through every word of every page as you type, and lists the pages that
  have all of your words (*No page has all of these words.* when none
  has). Press **/** anywhere to jump into it; ↑ and ↓ pick a result, Enter
  opens it, Escape clears the box.
- **On this page**, on the right of a wide screen and folded at the top on
  a phone, lists the page's headings.
- **Previous** and **Next**, at the foot of every page, walk the whole
  guide in the order of the list.
- Every heading has its own address: point at it and click the **#**
  beside it, and the address bar holds a link to that very place.
- The foot of every page, and of the front page, has three links,
  **GitHub**, to Parseh's own repository, **parseh.io**, to Parseh's
  website, and **imbrunoursino.net**, to the website of Bruno Ursino, who
  made Parseh — the same three as the hub's foot. Each opens in a tab of
  its own; nothing is fetched from any of the addresses until you click.

## On a page

- A block of code has a **Copy** button that copies it exactly, and says
  **Copied**.
- A picture opens large when you click it; Escape, or a click anywhere,
  closes it.
- The exercises work: answer them, and **Check exercises** at the end of
  the page marks them.
- An example of the studio's Markdown shows the Markdown and, under it,
  what the studio makes of it.
- The **◐** button changes the theme, light, dark and sepia. Served by
  Parseh the guide shares the toolbox's setting: change it here and the
  hub follows, and the other way round.

There is no other manual: these pages are the whole of it.
