# Who may reach Parseh

*The contract behind **Settings → Network**: what the doors mean, what is
written where, and what a VPN other than Tailscale needs. Decided with the
owner on 2026-09-23 (TO-DO §0, §1.1, §3.3, §3.4).*

Parseh is one person's toolbox on one person's computer, and every route in
it can delete a book, overwrite an edition or stop the server. Until this
page existed it bound every interface and asked nobody who they were: anyone
on the same Wi-Fi could do all three. This is the door.

## The three places a knock can come from

| Where | What counts as it | What Parseh does |
|---|---|---|
| **This computer** | `127.0.0.0/8`, `::1` | always served, never asked anything, and the only place the settings can be *changed* |
| **A VPN** | Tailscale's `100.64.0.0/10` and `fd7a:115c:a1e0::/48`, plus every range and name you add | served when the VPN door is open (it is, on a fresh install); **no code** |
| **The Wi-Fi** | `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, `fc00::/7`, `fe80::/10` | served when the Wi-Fi door is open **and** the device has been let in with a code |

Anything else — a public address — is refused at the socket, before a byte of
HTTP is read.

**A fresh install answers this computer and a VPN. The Wi-Fi door is shut.**

## Two questions, asked in two places

The **range** question is asked of the *connection*, in
`Server.verify_request` (`serve.py`), before any HTTP: a refusal costs a
closed socket and nothing else, and a port scan on the Wi-Fi finds a door
that does not open rather than a toolbox that answers.

The **"has this device been let in"** question is asked of the *request*, in
`Handler._gate`, because the answer is a cookie and a cookie arrives in a
request. A device that has not been let in is served one page at every
address it asks for — one sentence, one field, one button, carrying its own
style and its own script, because it cannot fetch `/lib/parseh.css` either —
and the one route that page posts to, `POST /settings/api/pair`.

**"This computer only" is not a rule; it is a closed socket.** With both
doors shut Parseh binds `127.0.0.1`, and there is nothing on the network to
knock at. That is the one position of this door that does not depend on a
line of Parseh's code being right.

## The pairing code

Six characters from an alphabet with no `I`, `O`, `0` or `1` in it, shown as
`KP4-R7M`. It is:

- **printed when the server starts** (when the Wi-Fi door is open) and shown
  on **Settings → Network**, where a button makes a fresh one;
- **good for fifteen minutes**, and replaced by a new one the moment the page
  asks for it after that — so the page always shows one that works, and the
  line printed at start is good for a quarter of an hour;
- **spent when it is used**: it lets *one* device in;
- **thrown away at the eighth wrong guess**. A six-character code is a
  billion guesses deep, and a billion guesses is an afternoon for a program.

A device that types it right is remembered in `config/network.json` by a
random token it carries in a cookie (`parseh_device`, ten years, `HttpOnly`,
`Secure` wherever there is TLS), and named by what it says it is — "Android
phone · Chrome", exactly as `lib/prefs.js` names one. Each device has its own
line on the page, with its own **Forget this device** button, and there is a
**Forget every device** beside them.

## Only the computer may save

A phone may **read** the page — it is useful to see which door let you in
from the device that came through it — and every control on it is drawn
disabled, with a line saying why. Every `POST /settings/api/…` but the
pairing one is refused unless it comes from loopback. One device that has
been let in must never be able to let the whole network in, or move the port
out from under the others.

## A change takes effect at once

No restart, no terminal. The save answers **before** anything is re-bound,
because the page that asked is about to lose the address it asked from:

1. the settings are checked (the port is free, the ranges parse, a
   certificate of your own loads) and written;
2. the answer goes out, carrying the addresses that will work;
3. a thread waits for it to reach the page, writes the new address into
   `RUN` and asks the server to stop;
4. `main`'s loop — the only place in Parseh that binds or closes a socket —
   closes the old socket and opens the new one, refreshes the printed
   addresses, and serves again;
5. the page knocks at each address it was given until one answers, and goes
   there.

If the new address cannot be bound after all, the loop says so on the
terminal, **goes back to the address that was working** and writes the old
settings back, so the page that saved can be reached and told why.

## The port

`7654`, out of AnkiConnect's `8765` (TO-DO §2.14): an Anki user with the
add-on running could not start Parseh at all. Moving it:

- changes **every address**, so a bookmark on a phone stops working until it
  is made again, and the mobile interface **installed as an app** has to be
  installed again from its new address;
- is refused, in words, when something else already holds the port, or when
  it is below 1024 (which the operating system will not give a
  double-clicked toolbox).

`serve.sh`, `Parseh.command` and `lib/launcher.py` **read** the port from
`config/network.json`; a number on their command line wins for that one
start. Nothing but the Settings page writes it.

## The certificate

Parseh's own, signed by an authority it makes for this machine alone, is the
default: a phone told to trust that authority once (`/m/install/`) never sees
a warning again, and **a fresh certificate under it costs the phone nothing**
— which is why Parseh now makes one again by itself when the machine's
addresses have changed (`.tls/names.txt` against `cert_names()`, TO-DO §3.6).
Opening a door can add an address to it; the Settings page says when a device
will have to accept something again, which is only when there is no authority
— a certificate put in `.tls/` by hand, or one made before authorities
existed.

**Use my own certificate** points Parseh at a certificate and a key of your
own. It is tried before it is saved, and Parseh **never writes to either
file**: renewing it is yours to do. Leave both empty to go back to Parseh's
own.

## This computer on plain `http://localhost` (a0.7.0)

The certificate is for **other devices** only. A browser counts
`http://localhost` and `http://127.0.0.1` as secure contexts — clipboard, tab
and screen capture, a service worker, an installed app all work there — so the
computer itself is served plain HTTP, with no certificate and no warning, at
`http://localhost:<port>/`. Every address Parseh writes for itself on this
computer (the launcher, `serve.sh`, `serve.bat`, `Parseh.command`, the printed
lines, the hub, the guide) is that one. The design is in `lib/localhttp.py`:

- **One port, sniffed.** `Server.finish_request` peeks at each connection's
  first byte: `0x16` starts a TLS handshake; anything else is plain HTTP, which
  is **served only to loopback**; from any other address it gets a redirect to
  the `https://` address and nothing else. A second plain listener on
  `127.0.0.1` was not chosen: it needs a second port (`127.0.0.1:7654` cannot be
  bound beside `0.0.0.0:7654` on Linux), a second socket for every re-bind, and
  a second one for the updater's progress page, which sniffs the same way.
- **Host is checked on plain HTTP.** TLS used to stop DNS rebinding (a site
  whose name points at 127.0.0.1): no certificate matches such a name. Over
  plain HTTP a request from loopback must say `Host: localhost`, `127.x.y.z` or
  `[::1]`, or it is refused (421).
- **The move of origin.** `https://localhost:7654` and `http://localhost:7654`
  are two origins. Measured: the pages keep their device's settings, reading
  places, unsaved timing edits and studio choices in **localStorage** (the
  ones that follow a person are on the server already, `lib/prefs.py`); no page
  opens **IndexedDB**; the service worker's **caches** hold only copies of the
  server's files; **an installed app** opens the old address. A navigation over
  TLS from this computer to `localhost`/`127.x` is answered, once, by a page on
  the old origin that posts its whole localStorage to `/__move`, empties the
  old worker and caches, and goes to `http://localhost:<port>/__move?t=…`,
  where the new origin writes every key it does not have yet and goes on. A
  cookie (`parseh_moved_<port>`, `Secure`) then sends every later navigation
  on with a 302. Only when an app was in use (standalone display) or a worker
  existed is the person told, once, to install the app again.
- `Secure` stays on the `parseh_device` cookie: a device let in by code never
  uses loopback.

## A VPN other than Tailscale

Tailscale needs nothing: its ranges are built in. Another VPN — WireGuard,
Tailscale's own `fd7a:` aside, a company's, a router's — needs one line in
**Other networks that count as a VPN**, which takes either:

- **an address range**, `10.8.0.0/24` or `fd00:dead:beef::/48` — the range
  the VPN hands its clients, *not* the range of your Wi-Fi. A range that
  overlaps the Wi-Fi turns the Wi-Fi into a VPN and takes the code away from
  it, which is the one way to get this wrong;
- **a name**, `laptop.example.ts.net` — looked up again every five minutes,
  so a VPN that re-uses names as devices come and go is followed. A name
  this computer cannot look up at all is refused when it is typed, since
  Parseh could never tell whether a device is it.

An address in one of these is trusted **without a code**, on the same
reasoning as Tailscale's: a device is on that network only because you put it
there. If that is not true of your VPN, leave it out and let its devices in
by code, over the Wi-Fi door.

What a VPN cannot do is make the certificate name it: the certificate carries
`localhost`, this machine's name, its `.local` and `.ts.net` names and its
private and Tailscale addresses (the authority is name-constrained to exactly
those, TO-DO §3.5). Reaching Parseh by an address outside them warns about
the certificate as any other unknown address does, and is accepted the same
way.

## The file

`config/network.json`, written whole through a temporary file beside it, as
`config/prefs.json` is, and `chmod 600`:

```json
{"port": 7654,
 "vpn": true, "lan": false,
 "extra": ["10.8.0.0/24", "laptop.example.ts.net"],
 "cert": {"cert": "/etc/ssl/mine.pem", "key": "/etc/ssl/mine.key"},
 "devices": {"<token>": {"name": "Android phone · Chrome",
                         "at": 1758531600.0, "seen": 1758531600.0,
                         "ip": "192.168.1.20"}}}
```

It is **this machine's**: gitignored, in no bundle and in no backup. It says
who may reach *this* computer, which means nothing anywhere else, and the
tokens in it are as good as keys. The pairing code is **not** in it — a code
lives in the running process and for fifteen minutes.

## Only Parseh's own pages may write

The doors above ask *which device* is knocking. They cannot see a web page on
another site, open in a tab of this computer's own browser, making that
browser post to `http://localhost:7654/` — the request comes from this
computer, where the door is always open. So every request that is not a read
(anything but `GET` and `HEAD`, on every route) is asked where it came from,
once, before its body is read (`lib/crosssite.py`, TO-DO §3.1; decided with
the owner on 2026-09-25):

| The request says | Parseh |
|---|---|
| `Sec-Fetch-Site: same-origin` — one of Parseh's own pages | answers |
| `Sec-Fetch-Site: none` — the person typed the address | answers |
| `Sec-Fetch-Site: same-site` — another port on this computer, or a sibling name | refuses (403, in words) |
| `Sec-Fetch-Site: cross-site` — any other site | refuses |
| no `Sec-Fetch-Site` (an older browser), an `Origin` that is not this address, `null` included | refuses |
| no `Sec-Fetch-Site`, `Origin` this very address | answers |
| neither header — curl (`serve.sh stop`), the Windows launcher, the test suites | answers: none of them is a browser a page could drive |

`Sec-Fetch-Site` is written by the browser alone, so where it is present it
decides, and `Origin` is read only where it is absent (a page of Parseh's own
that asks for no referrer sends `Origin: null` on its own writes). Every page
Parseh serves writes to a relative address — on the computer, on a phone, in
the installed app — so every one is same-origin; the service worker writes
nothing; a page exported to one file and opened from the disk cannot reach the
server at all. The studio run on its own (`markdown/app/server.py`) asks the
same. The updater's routes also insist on their own kind of body
(`Handler._cross_site`).

## What this is not

It is not authentication *between* the people using one Parseh: there is one
person, and a device that has been let in is that person's. It is not a
defence against somebody who has the computer itself, or against a program
running on it (which is not a browser, and is answered). And it does not yet
check the `Host` header against DNS rebinding (TO-DO §3.2).

## Where the code is

| What | Where |
|---|---|
| the store, the ranges, the code, the devices | `lib/network.py` |
| the pages: the section, Network, the locked page | `lib/settingspage.py` |
| the connection door, the request gate, the re-bind | `serve.py` (`Server.verify_request`, `Handler._gate`, `_settings_save`, `_rebind_soon`, `main`) |
| only Parseh's own pages may write | `lib/crosssite.py`, asked in `serve.py` `Handler._dispatch` and `markdown/app/server.py` `Handler._dispatch` |
| the door without a server | `tests/test_network.py` |
| the cross-site check, through the real server | `tests/test_cross_site.py` |
