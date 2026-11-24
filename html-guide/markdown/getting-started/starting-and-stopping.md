---
title: Starting and stopping
weight: 3
description: Starting the server on Linux, macOS and Windows, what it prints, the ⏻ button that stops it, and what that button warns you about.
---

Parseh is one small web server — `serve.py` — that serves every page of the
toolbox at one port: `http://localhost:7654/` on this computer, and the
`https://` addresses it prints on every other device. While it runs, every
device you have let in can use Parseh; when it stops, the pages stop
answering until you start it again. Which devices those are — and which port
— is [**Settings → Network**](other-devices.md), and a change there takes
effect without a restart.

## Starting it

| System | How |
|---|---|
| Linux | `./serve.sh` in the Parseh folder |
| macOS | double-click **Parseh.command** (or `./serve.sh` in Terminal) |
| Windows | double-click **serve.bat** |

Then open `http://localhost:7654/` in a browser. The Mac's
**Parseh.command** and Windows' **serve.bat** open it for you. The browser
does not warn about anything: `http://localhost` needs no certificate, and
browsers count it as secure. A phone or another computer reaches Parseh over
`https://`, with a certificate Parseh made for itself, and its browser warns
about that once — [From a phone or another computer](other-devices.md) says
why there is one at all.

**On Linux and macOS** `./serve.sh` starts the server *in the background*:
the terminal is yours again at once, and closing it does not stop Parseh.
It waits until the server really answers, and then shows the first
fourteen lines of what the server printed: the books it found, one line
each, and after them the addresses it can be reached at — on a short
shelf, like this one:

```text
books:
  english/my-first-book                English  (no narration)
Parseh: serving /home/me/Parseh on 0.0.0.0:7654 (https)

  https://100.101.102.103:7654/              (tailscale)
  https://192.168.1.20:7654/                 (local network)
  http://localhost:7654/                     (this machine)

  /books/  /youtube/  /studio/  /exercises/  /anki/sync/  /settings/

reachable from: this computer and a VPN

this computer opens Parseh at http://localhost:7654/ with no warning; another device is
served the certificate, which its browser warns about once -- or tell
a phone to trust the authority once, from /m/install/.
Ctrl-C, or any of the page's stop buttons, to stop.

running in the background: pid 4821,  log /home/me/Parseh/serve.log
stop it with:  ./serve.sh stop      (or the stop button on any page)
```

On a longer shelf — some nine books or more — the books fill those
fourteen lines, and some of the addresses, or all of them, fall below
what is shown. Nothing is lost: the hub's foot, under **Reachable at**,
always lists every address, and so does the top of `serve.log`.

What the server goes on printing is kept in `serve.log`, in the Parseh
folder. Each start begins a fresh one and keeps the one before as
`serve.log.1`, so the error that made you restart Parseh is still there
after the restart. **Settings → About** shows the end of both, under
*When something goes wrong*. When it is already running,
`./serve.sh` says so and leaves it alone:

```text
already running: pid 4821 on port 7654
use  ./serve.sh restart  to replace it, or  ./serve.sh stop
```

and when it cannot start — the port taken by another program, say — it
says `failed to start -- the log says:` and shows the log.

**On Windows** the server runs in the window serve.bat opened: that window
shows its log, and closing it stops Parseh. Every line is also written to
`serve.log`, with the run before kept as `serve.log.1`, as on Linux and
macOS. Ctrl-C in the window stops the server and says `stopped.`. An
update from Settings runs in the same window and goes on in the same
`serve.log`; a new version that does not start is undone there too, and the
lines that say why stay in the log. The first double-click is a
[setup wizard](windows-wizard.md).

**Without the environment**, Parseh still serves — the pages need nothing
but Python — and says so as it starts:
`note: no 'ilya-frank' environment -- serving with /usr/bin/python3`.
Everything that rebuilds something then
says, on its own page, what it needs; [Installing Parseh](installing.md)
puts it all in place.

## Moving to localhost

Before a0.7.0 the computer opened Parseh at `https://localhost:7654/`, and its
browser warned about the certificate once. Now it opens `http://localhost:7654/`.
To a browser those are two different sites, and what it kept for the old one —
the settings a page keeps on this device, a reader's timing edits not yet
saved, the place in a book — the new one would not see. So the first time the
old address is opened, a short page there hands all of it to the new address,
and the browser goes on to the page that was asked for. From then on the old
address — a bookmark, a tab left open — simply sends the browser on.

Nothing has to be done, with one exception, which that page says when it
applies: **an app installed from the old address** keeps opening the old
address. Install Parseh again from `http://localhost:7654/` (the install
button in the browser's address bar, or its menu), and remove the old app.

## Stopping it

Almost every page has a button that stops the server:

| Where | The button |
|---|---|
| the hub, the books' library and its page for adding a book, the video pages, the Anki page, the clip tray | **⏻ stop**, at the right of the top bar |
| a video's player | **⏻** |
| a book's reader | **stop server**, which asks **really stop?** — click it again within four seconds; your place and the playback speed are saved first |
| the studio's pages | **Stop server** |
| the exercise decks' pages | **Stop server** |

**It asks first**, *Stop the Parseh server?*, and **it warns you when
Parseh is in the middle of something.** A book being built, a backup being
packed, a bundle going up: stopping the server cuts it off, so the question
names what is still running before you answer it —

```text
1 task is still running:

  • Uploading “mini-en-full.zip” (8.7 MB)

Stopping the server now cuts it off. Stop the Parseh server anyway?
```

— up to five of them, and *… and 2 more* after that (the studio's pages
name the first five and stop there, though the count above them says how
many there are). **Cancel** leaves everything as it was. On the exercise
decks' pages the same question is a dialog of their own, with **Cancel**
and **Stop server** — **Stop server anyway** when something is running.
Even the reader, whose button has already asked *really stop?*, asks
again when there is work in progress. [The Working…
indicator](working-indicator.md) shows the same list at any time.

Once it has stopped, the page says so — **Parseh stopped.**, or on the
studio's and the exercises' pages **Server stopped**, *You can close this
tab* — and every other page of Parseh, in every tab and on every device,
stops answering. To start again, start it the way you started it before,
and reload the page.

The hub's **Mobile** layout has no stop button, on purpose: the mobile
interface is for reading and studying, and shows nothing that administers
the toolbox ([Browser and Mobile](mobile-mode.md)). Switch to **Browser**
to stop the server from the hub, or use any other page.

## For the command line

On Linux and macOS, `./serve.sh` does more than start the server:

```bash
./serve.sh            # start it, in the background, on port 7654
./serve.sh 9000       # ... on another port
./serve.sh status     # is it running, and on which port
./serve.sh log        # follow the log; Ctrl-C stops following
./serve.sh stop       # stop it, as the page's button does
./serve.sh restart    # stop it, then start it again
./serve.sh cert       # a fresh certificate; then restart
```

`python3 serve.py` runs the same server in the foreground instead, until
Ctrl-C. It takes a port too, and `--local` (this computer only),
`--host <address>` (one address only), `--http` (no certificate) and
`--cert` (make a fresh certificate, and exit). On Windows, `serve.bat stop`,
`status` and `cert` are the same as these — the whole list is on
[the wizard's page](windows-wizard.md#for-the-command-line).
