---
title: Windows — serve.bat and its setup wizard
linkTitle: The Windows wizard
weight: 2
description: What serve.bat does the first time and every time after, the five steps of its wizard, and its options.
---

On Windows, **serve.bat** is the one file you double-click: the first time
it is a setup wizard — what the installer and its report are on Linux and
macOS — and every time after that it starts Parseh and opens the browser
on it.

## Finding a Python

serve.bat looks for a Python before anything else, the Parseh environment
first:

1. the Python named by the environment variable `PARSEH_PYTHON`, when it
   is set;
2. the folder's own `.runtime\env`, which **install.bat** makes;
3. an `ilya-frank` environment that an Anaconda, a Miniconda, a Miniforge
   or a micromamba keeps;
4. failing those, any Python 3.8 or newer: the `py` launcher, `python`,
   `python3`, or one in the usual install folders. The Microsoft Store's
   `python`, which only opens the Store, does not count.

When the computer has no Python at all, it says so and offers two ways on.
The simplest is to close the window and double-click **install.bat**, which
brings its own Python with everything else Parseh needs. Or, where the
Windows package manager is there, it asks **Install Python 3.12 now? [Y/N]**
and installs it with winget; without winget, it opens the download page of
python.org.

## The wizard

The wizard runs by itself the first time — when it has never run through,
or when the books' library page has never been built. It goes in five
steps; a question takes its default, **Y**, when you only press Enter.

No page has a button that runs it again. It knows it has run through by a
small file it leaves in the Parseh folder, `.setup-done`: delete that file
and double-click **serve.bat**, and the wizard runs once more (from a
command prompt, `serve.bat setup` does the same — see
[For the command line](#for-the-command-line)).

**1. Welcome.** What Parseh is, and what the wizard is about to do.
*Press Enter to begin.*

**2. This computer.** Four groups of checks, each line marked `ok`, `MISS`
for something missing, or `--` for something optional that is not there:

- *Required to serve*: the Python it found — the `ilya-frank` environment's
  when that is the one — the bundled web fonts, and a Japanese or Chinese
  font when there is a book or a video in that language (Windows ships
  Yu Mincho and Meiryo, so here that is taken as given).
- *Needed once, to make the certificate*: `openssl`. The wizard finds one
  that Git for Windows or a conda brought with it; where there is none it
  asks **Install OpenSSL with winget now?** (OpenSSL Light, from Shining
  Light Productions — Windows asks you to allow the installer).
- *The environment*: every package Parseh's environment lists, and pkuseg's
  models. When something is missing it asks **Install it now?** and does
  what install.bat does: makes the environment in `.runtime\` with
  micromamba, or adds what an older one lacks, compiles this guide and
  fetches the models. It then carries on in the environment's own Python,
  so the readers it builds and the server it starts are the environment's.
- *Optional tools*: LuaLaTeX, ffmpeg and pdftotext, and Tailscale — with
  it installed, the address of your private network of devices is printed
  and put in the certificate too.

**3. The books.** Every book on the shelf, filed under its language, with
its narration and its alignment; then it builds every reader and the
library page, and compiles this guide — every time, whatever step 2
installed, unless the guide is already compiled from the same pages.

**4. The certificate.** Parseh serves HTTPS to other devices with a
certificate it makes for itself, in `.tls\`, for every name and address the
computer has; this computer opens `http://localhost:7654/` and never sees it.
Two things happen once, and the wizard says so: the browser of a phone or
another computer warns about that certificate — it is yours, accept it (in
Chrome: **Advanced**, then **Proceed**) — and Windows Firewall asks whether
Python may accept connections. Allow it, or only this computer can reach
Parseh.

**5. Done.** How many checks passed and how many are missing, what to do
from now on, and **Start Parseh now?**

## Every time after that

A double-click on serve.bat starts the server in its own window and opens
the browser on `http://localhost:7654/`:

```text
Parseh is up at http://localhost:7654/ -- this window is its log.  Close it, press Ctrl-C,
or use the stop button on any page to stop the server.
```

The window is the server: what it prints is the log. The **⏻ stop** button
on any page, Ctrl-C in the window, or closing the window stops it. When
Parseh is already running, a double-click only opens the browser on it.

**Without OpenSSL** there is no certificate, and Parseh serves plain
`http://` instead, and says so. On this computer everything works. From a
phone or another computer everything works but three things, which
browsers allow only on a secure address — and `localhost` is the one plain
address they count as secure: the studio's copying, capturing a video's
frame for a card, and recording a YouTube video's sound from its tab
([From a phone or another computer](other-devices.md#why-https) says
which buttons those are). The copy buttons of the books, the videos and
the card sheets go on working there, the old way.

To get the certificate, run the wizard again (above): it offers to
install OpenSSL. Once OpenSSL is there — or Git for Windows, which brings
one — start Parseh again, and it makes the certificate as it starts.

## For the command line

In a command prompt in the Parseh folder, serve.bat takes:

```text
serve.bat               the wizard once; then start and open it
serve.bat 9000          ... on another port for this start (Settings >
                        Network keeps the port; 7654 on a fresh install)
serve.bat setup         run the wizard again
serve.bat stop          stop a running server
serve.bat status        is it running, and where
serve.bat cert          a fresh certificate (then stop, start)
serve.bat readers       every reader and the library page, rebuilt
serve.bat --no-browser  start without opening a browser window
```

A fresh certificate is what a computer whose addresses have changed needs —
though Parseh now notices that as it starts and makes one by itself:
[From a phone or another computer](other-devices.md#the-certificate) says
why, and what a phone has to trust.

serve.bat only finds the Python; the rest is `lib\launcher.py`, which does
on Windows what `./serve.sh` and `./install.sh` do elsewhere.
