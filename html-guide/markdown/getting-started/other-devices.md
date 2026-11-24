---
title: From a phone or another computer
linkTitle: From a phone
weight: 4
description: Who may reach Parseh and how to let a phone in, the addresses, the port, why it speaks HTTPS, and the certificate.
---

Parseh runs on one computer, but it is a web server: a phone, a tablet or
a laptop that can reach that computer can use it too — read a book on the
sofa while the narration plays, study a deck on the train. Nothing needs
installing on the phone; a browser is all it takes.

**But not every device may.** A fresh Parseh answers *this computer and a
VPN*, and nothing else; the Wi-Fi door is shut until you open it, and a
device on the Wi-Fi is then let in once, by hand. Everything on this page is
set on one page of Parseh's own: **Settings → Network**, from the hub's
**⚙ Settings** door.

## Who may reach Parseh

| The door | What it lets in | On a fresh install |
|---|---|---|
| **This computer** | the computer Parseh runs on, and only it | always open, and nothing is ever asked of it |
| **A VPN** | your own devices on Tailscale, and anything else you name | **open** — and no code is asked for |
| **The Wi-Fi** | every device on the same network as the computer | **shut** |
| **Paired computers** | only another Parseh paired with this one on **Settings → Devices** — never a browser, and only from the Wi-Fi or a VPN | **shut**; it opens by itself when you show a pairing code or pair a computer |

The third door is for [several computers](several-computers.md) that keep one
shelf. Shut it whenever you like: your partners then cannot reach this
computer, and sync from them waits until you open it again.

With all three doors shut Parseh does not listen on the network at all, even
with computers paired: it is
not that it turns devices away, it is that there is nothing there to knock
at. That is what **this computer only** means here.

**Changing a door takes effect at once.** Save, and Parseh moves to its new
address by itself — no restart, no window to close — and the page you saved
from follows it there.

**Only the computer may change this.** A phone can open the page and read
it, with every control greyed out and, under each part, a lock and a line
saying why; the doors are opened from the side they protect. What a phone may
and may not change is decided setting by setting, by one rule: a setting that
decides who may reach Parseh, what it exposes or what it runs is changed on
the computer alone. Every part of Network is one of those. Getting a
dictionary is not, so a phone that has been let in may get and remove
anything on the [reading-help page](../lookup-and-languages/reading-help.md).
Nor is a [LaTeX theme](../dialect/latex-drawings.md#themes): a phone that has
been let in may make, change and import themes, and get the TeX packages they
need. Nor is [speech to text](../lookup-and-languages/speech-to-text.md#who-may-use-it):
any device that has been let in — a phone, a tablet, another computer — may get,
stop and remove its program and its models, because the only files that can
ever arrive are the ones Parseh pins, each checked against its hash.
Nor are the [ARASAAC pictograms](../studio/pictograms.md#who-may-use-it): any
device that has been let in may get, update, stop and remove them, because the
only files that can arrive are ARASAAC's own, from two hosts Parseh names.
Nor is [a book being made by an agent](../books/made-by-an-agent.md#who-may-do-what):
a device that has been let in may do all of it — make the folder, give the
agent its text a part at a time, read the making panel, look at what is
written so far, write what to change, finish the book and reopen it — because
these only write files under `books/` and start Parseh's own build, and the
agent itself is started by you, on the computer. One thing is the computer's
own, and is not a permission: opening the folder shows it on that computer's
screen, so from another device the panel gives the path to copy.
Installing another version of Parseh changes what it runs: a phone may look
for a new version, but only the computer installs one
([Updating Parseh](updating.md#from-a-phone)).

## Letting a phone in

With the Wi-Fi door open, a device on the Wi-Fi that opens Parseh gets one
page: *this device has not been let in*, a box, and a button. On the
computer, **Settings → Network** shows a short code — only there: a phone
opening the same page is told *The code is shown on the computer only*,
since whoever can read the code can let a device in —

```text
  KP4-R7M
```

— which is also printed in Parseh's window when it starts. Type it on the
phone, press **Let this device in**, and Parseh opens. That phone is
remembered for good; it is never asked again.

- a code is good for **fifteen minutes**, and the page shows a fresh one
  after that. **Make a fresh code** makes one on the spot, and the old one
  stops working;
- a code lets **one** device in;
- eight wrong tries and Parseh throws the code away — ask for another;
- a device on a VPN is never asked for one, and the computer itself never is.

Every device that has been let in is listed on the page, named as it names
itself ("Android phone · Chrome"), each with **Forget this device**; there is
a **Forget every device** beside them.

## Which address

When Parseh starts it prints every address it can be reached at, and the
hub says the same at its foot, under **Reachable at**:

```text
  https://100.101.102.103:7654/              (tailscale)
  https://192.168.1.20:7654/                 (local network)
  http://localhost:7654/                     (this machine)
```

| Address | Who can use it |
|---|---|
| **tailscale** — one starting with `100.` | any of your own devices on your Tailscale network, wherever they are — with the VPN door open |
| **local network** | a device on the same Wi-Fi or network as the computer — with the Wi-Fi door open, and once that device has been let in |
| **localhost** | only the computer Parseh runs on |

The list is what Parseh can find by the computer's own name, and on some
computers the local network address is not among what that finds. It works
all the same, and the computer's network settings show what it is; if the
certificate does not name it, a browser reaching Parseh by it warns about
the certificate as for any other address, and is accepted the same way.

**Tailscale** is a private network between your own devices, which lets a
phone reach the computer at home from anywhere as if it were in the next
room — and nobody else. Parseh has nothing to set up for it: where the
`tailscale` program is installed, Parseh asks it for the address and puts
it first, and puts the computer's name on your tailnet into its
certificate too.

On a phone, open the address in the browser and bookmark it. The hub's
[mobile interface](mobile-mode.md), made for reading on a phone, is one
tap away on its **Browser | Mobile** switch.

With a door open, Parseh listens on every network the computer is connected
to and decides who may speak to it one connection at a time. On Windows the
firewall asks, the first time, whether Python may accept connections: allow
it, or only the computer itself can reach Parseh whatever the doors say.

### A VPN that is not Tailscale

Tailscale needs nothing at all. For any other private network — WireGuard, a
company's, your router's — put its addresses in **Other networks that count
as a VPN**, one per line:

- an **address range**, as `10.8.0.0/24`: the range the VPN gives its
  clients, not the range of your Wi-Fi;
- or a **name**, as `laptop.example.ts.net`, which Parseh looks up again
  every few minutes.

A device at one of these is let in without a code, as a Tailscale device is.
A name this computer cannot look up is refused as you type it, since Parseh
could never tell whether a device is it.

## A phone on Tailscale that cannot reach the internet

Parseh works over Tailscale and so do its books, its decks and its notes —
they all live on your own computer. **A YouTube video is the exception**: it
comes from YouTube, and for that the phone needs the ordinary internet as
well as the tailnet. A phone can be in a state where the tailnet works and
the open internet does not, and then the player says so: *YouTube's player
could not be fetched — Parseh itself is answering, so it is YouTube this
phone cannot reach.*

It is almost always **DNS**. Tailscale carries the names inside your tailnet
(`MagicDNS`), and hands every other name to whatever resolver the phone would
otherwise use — which, on Android, it often cannot reach from inside the
tunnel, especially when the phone has **Private DNS** switched on. The
computer does not show it because it resolves public names with its own
network's servers, which it *can* reach.

**How to tell**: open `https://www.youtube.com/iframe_api` in the phone's
browser with Tailscale on. *ERR_NAME_NOT_RESOLVED* is this; a timeout is
something else (a subnet route, or an exit node that is down).

**Three ways to mend it, best first.**

1. **Give the tailnet a resolver of its own.** In the Tailscale admin console
   → **DNS** → *Global nameservers*, add one (`1.1.1.1`, `9.9.9.9`, whichever
   you trust) and turn **Override local DNS** on. Every device then resolves
   public names through something it can reach inside the tunnel. One change,
   no device to touch, and **MagicDNS keeps working** — which matters if you
   installed Parseh's app from a `.ts.net` address.
2. **Turn Android's Private DNS off.** *Settings → Network & internet →
   Private DNS → Off* (or *Automatic*). Then try the link again with
   Tailscale on.
3. **Turn Tailscale's own DNS off on the phone.** In the Tailscale app:
   *Settings → Use Tailscale DNS* → off. It is the quickest, and it has a
   price: the phone stops resolving `.ts.net` names, so **if you installed
   Parseh's app from `https://<machine>.<tailnet>.ts.net:7654` the app will
   no longer open**. Do this only if you reach Parseh by its `100.x.y.z`
   address, which the certificate covers as well.

None of this is Parseh's to set, and Parseh cannot see it: from inside the
app, a phone that answers Parseh looks online in every way that matters
until something asks the open internet for something.

## The port

Parseh answers on port **7654**, and **Settings → Network** moves it. Two
things to know before you do:

- **every address changes.** A bookmark on a phone stops working until it is
  made again, and the mobile interface [installed as an
  app](mobile-mode.md) has to be installed again from its new address;
- Parseh **left 8765** because that is also the port Anki's AnkiConnect
  add-on uses: with both running, one of them could not start. If something
  else holds the port you pick, Parseh says so and nothing is changed.

## Why HTTPS

Parseh speaks HTTPS, the secure kind of address, to every device but the
computer it runs on, even though it only ever talks to your own devices. The
reason is the browsers: a few things a page can do, they allow only on a
secure address, and the one plain `http://` address they count as secure is
`localhost` — the computer Parseh runs on. So that computer opens Parseh at
`http://localhost:7654/`, with no certificate and no warning, and from any
other device, a phone or another computer, these three need the `https://`
address:

| What | The buttons |
|---|---|
| **the studio's copying** | a click on text in the language you are learning, in a document or the editor's preview, which copies it; **Copy prompt only** and **Copy prompt + question** on the prompt page; **Copy complete prompt**, under **Generate with LLM…** in the editor |
| **capturing a video's frame** for a card | **📷 capture the current frame**, in the player's card sheet |
| **recording a YouTube video's sound** from its tab, to cut a card's recording out of it | **🔊 cut the audio…**, in the same sheet — in Chrome or Edge, on a computer |

Without a secure address the studio says *Clipboard unavailable*, and the
player says that the capture, or the recording, needs the page opened at
this computer's address, or at the https address from another device.

Every other copy works on either kind of address — shift-click in a
book's reader, a prompt for an LLM copied from a book or a video, the
copy buttons of the card sheets and of the pages for adding a book or a
video: where the browser keeps its clipboard back, they copy the older
way, which every browser still allows.

Both kinds of address use the same port. An old `http://` bookmark on a
phone is not an error: Parseh sends it on to the `https://` address. And an
old `https://localhost` bookmark on the computer is not one either: it goes
on to `http://localhost` (see [Moving to
localhost](starting-and-stopping.md#moving-to-localhost)).

## The certificate

HTTPS needs a certificate, and Parseh makes its own the first time it
starts — with `openssl`, which the environment carries — for every name and
every address the computer has at that moment: `localhost`, its name, its
local addresses, its Tailscale address and name. It keeps it in `.tls/` in
the Parseh folder.

Nobody outside this computer vouches for it, so **every browser warns you
about it once**, on each device other than the computer itself, which opens
`http://localhost` and is never shown the certificate. The warning page always has a way through —
in Chrome **Advanced**, then **Proceed** — and once you have accepted it that
browser does not ask again. This is the whole ceremony: it is your own server
on your own network, and nobody else is being asked to trust it. A phone can
skip the ceremony altogether by trusting Parseh's own authority once, from
the mobile hub's [**As an app**](mobile-mode.md) page.

**When the computer's addresses change** — another network, or Tailscale
installed afterwards — the certificate does not name the new ones. Parseh
notices that as it starts and makes a fresh one by itself, for every name and
address the computer has now. A phone that trusts the authority notices
nothing at all; a browser that accepted the old certificate by hand asks once
more.

### Use my own certificate

If you already have a certificate for this computer — from Tailscale, from
Let's Encrypt, from a company's authority — **Settings → Network** takes the
two files and Parseh serves with them instead. It reads them and **never
writes to either**: renewing it stays yours to do. Leave both boxes empty to
go back to Parseh's own.

> **For the command line.** `./serve.sh cert`, then `./serve.sh restart`,
> makes a fresh certificate on Linux and macOS. On Windows, `serve.bat cert`
> makes it; then stop Parseh and start it again.

## Plain http

On a Windows computer with no OpenSSL at all, Parseh cannot make a
certificate, and serves plain `http://` instead ([the Windows
wizard](windows-wizard.md) offers to install OpenSSL). On that computer
everything works; from a phone or another computer everything works but
the three things [above](#why-https), which need the secure address.

> **For the command line.** `python3 serve.py --http` serves plain http
> on purpose, for debugging.

On Linux and macOS a missing `openssl` is not quietly worked round: the
server refuses to start without a certificate, and says why:

```text
openssl is needed to make the certificate (apt install openssl),
or run with --http to serve without TLS
```

The environment the installer makes carries one, so this happens only on
a computer serving without it.

## Keeping it to one computer

Shut all three doors on **Settings → Network** and save. Parseh stops listening on
the network there and then: it binds the computer itself and nothing else, so
there is no address for a phone to fail at. Open a door again the same way.

> **For the command line.** `python3 serve.py --local` does it for one run,
> without touching what the page keeps; `python3 serve.py --host
> 100.101.102.103` binds one address only. A run started with either stays on
> it: saving the page then keeps the setting for next time and says so.

## Each device keeps its own settings

The theme, the language picked on the hub's chips, the **Browser | Mobile**
choice, where you are in a book: a browser keeps these for itself, so your
phone and your computer each have their own. They are kept per address,
too — the same phone opening Parseh once by its Tailscale address and once
by its local one keeps two sets.

And the **⏻ stop** button stops the server for everybody: stopped from the
phone, Parseh stops on the computer as well.
