# Installing Parseh, and a window to do it in

What installs Parseh today, what it leaves where, and the contract a graphical
installer will be built on.

## What there is to install

Serving needs only Python 3's standard library. Everything else — rebuilding
books, dividing Japanese and Chinese into words, opening an Anki export, the
browser tests — needs the packages of [`environment.yml`](../environment.yml),
and they live in one environment called `ilya-frank`:

| where | what |
|---|---|
| `.runtime/bin/micromamba` | micromamba: one program, downloaded only where no environment exists yet |
| `.runtime/env/` | the environment itself, a few hundred megabytes |
| `.runtime/mamba/` | micromamba's package cache |
| `~/.pkuseg/` | pkuseg's word and part-of-speech models, about 75 MB (`$PKUSEG_HOME` moves them) |

Nothing is installed system-wide, and nothing outside the checkout but the
pkuseg models. An environment called `ilya-frank` that a conda, a mamba or a
micromamba already keeps is used as it is, and only what it lacks is added.
Removing `.runtime/` removes the rest.

## The entry points

| system | the first time | every time after |
|---|---|---|
| Linux | `./install.sh` | `./serve.sh` |
| macOS | double-click `Parseh.command`, or `./install.sh` | `Parseh.command`, or `./serve.sh` |
| Windows | double-click `install.bat` (`serve.bat`'s wizard offers it too) | `serve.bat` |

Every one of them runs [`lib/runtime.py`](../lib/runtime.py) `install`, which
does, in order:

1. **env** — find the environment (`$PARSEH_PYTHON`; `.runtime/env`; an
   `envs/ilya-frank` under any conda, mamba or micromamba), or make it: with
   micromamba into `.runtime/env`, or with `--conda` by the machine's conda.
2. **packages** — add what `environment.yml` lists and the environment lacks:
   the pip packages with its own pip, the programs it carries (`openssl`,
   `deno`) with micromamba or conda. This is how a package listed after a
   machine was set up reaches it.
3. **guide** — `html-guide/build.py`: the guide's pages, written in
   `html-guide/markdown/`, compiled into `html-guide/site/`, which the hub's
   **guide** button opens (`html-guide/README.md`). It needs only the
   standard library. A compile that fails ends as a `warning`, not a failure:
   Parseh works without it, and the guide's front page compiles it again from
   a button.
4. **models** — `lib/words.py --fetch ja zh`, so that no request of the
   server is ever the one that waits for a download.
5. **readers** — `./build.sh --html`, or the Windows launcher's copy of it.

`./install.sh --guide` runs the guide's step alone, with the environment's
Python or the system's, and stops; `./install.sh --check` compiles it too,
after the readers.

`python3 lib/runtime.py status` says what the machine has; `--json` says it as
one object. `lib/env.sh` (for `serve.sh`, `build.sh`, `install.sh`) and
`serve.bat` search for the environment in the same order `runtime.py` does.

## The protocol a window reads

`python3 lib/runtime.py install --json` (and `./install.sh --json`) writes one
JSON object a line on standard output, and nothing else:

```json
{"event": "step", "id": "env", "title": "the environment", "state": "running", "detail": "with micromamba, into .runtime/env -- a few hundred megabytes, once"}
{"event": "log", "line": "Transaction finished"}
{"event": "step", "id": "env", "title": "the environment", "state": "done", "detail": "/home/you/Parseh/.runtime/env"}
{"event": "step", "id": "packages", "title": "the packages", "state": "done", "detail": "all 9, and the programs it carries"}
{"event": "step", "id": "guide", "title": "the guide", "state": "done", "detail": ""}
{"event": "step", "id": "models", "title": "the word analyzers' models", "state": "done", "detail": ""}
{"event": "done", "ok": true, "python": "/home/you/Parseh/.runtime/env/bin/python3", "environment": "/home/you/Parseh/.runtime/env"}
```

- `step.id` is `env`, `packages`, `guide`, `models` or `readers`, in that
  order; `state` is `running`, `done`, `skipped`, `warning` or `failed`. A
  step says `running` before it starts and once more when it ends. `warning`
  is a step that did not finish but that Parseh works without (the guide):
  it is shown, and it does not make `done.ok` false.
- `log` lines are whatever the tools print. Show them in a details pane; never
  parse them.
- `done` comes last and once. `ok` false means a step failed, and the process
  exits 1 (2 for a wrong argument).
- `--dry-run` walks the same steps as `skipped` and touches nothing: the way
  to try a window out.

`tests/test_runtime.py` holds the protocol to this page.

## Toward an installer without a terminal

The work is all in `runtime.py`, so what a window has to do is small:

1. **Have a Python to start with.** Where the machine has none, do what
   `install.sh` and `install.bat` do before anything else: download
   micromamba — a single file — and make `.runtime/env` from
   `environment.yml`. From then on the environment's own Python runs
   `lib/runtime.py install --json`.
2. **Show the steps.** Five rows with their states, the `log` lines in a pane
   that can be opened, and a last screen decided by `done.ok`.
3. **Start Parseh.** `serve.bat` on Windows, `./serve.sh` elsewhere, then open
   `http://localhost:7654/` — or whatever port `config/network.json` names,
   which is the one thing an installer must read rather than write
   (`docs/network.md`).

The packagings that fit, none of them built yet: on Windows an Inno Setup or
MSIX installer that copies the checkout and runs `install.bat` out of sight;
on macOS an `.app` whose executable does what `Parseh.command` does; on Linux
an AppImage, or a `.desktop` entry, doing the same. Each is a wrapper around
the protocol above.
