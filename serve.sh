#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Run Parseh -- the whole toolbox, one https server -- in the background.
# Linux and macOS alike.  (On Windows, double-click serve.bat instead.)
#
#   ./serve.sh              start it and print the addresses
#   ./serve.sh 9000         ... on another port, this once (the port Parseh
#                           keeps is on its Settings > Network page, and a
#                           change there moves it for good and at once)
#   ./serve.sh stop         stop it
#   ./serve.sh status       is it running, and where
#   ./serve.sh log          follow the log (serve.log; the run before is
#                           serve.log.1, and Settings > About shows both)
#   ./serve.sh restart      stop, then start again
#   ./serve.sh cert         make the server's certificate afresh (.tls/),
#                           e.g. after the machine's addresses changed; the
#                           authority a phone was told to trust stays
#
# Everything -- the book reader, the video player, the studio, the exercise
# decks, the Anki store -- is served by serve.py at ONE https address:
#
#   https://localhost:7654/          (and the Tailscale / LAN addresses it prints)
#
# WHO CAN REACH IT is not decided here.  A fresh Parseh answers this computer
# and a VPN, and the Wi-Fi door is shut until Settings > Network opens it; a
# device on the Wi-Fi is then let in once with a code shown on the computer.
# Nothing in this file can change that, and nothing needs to (lib/network.py).
#
# The certificate is made by serve.py itself on first start, signed by an
# authority of this machine's own (docs/mobile.md, "Parseh as an app").
# Every browser warns once about it; accept, and it never asks again -- or
# tell a phone to trust the authority, from the mobile hub's "As an app",
# and it never warns at all.  It is our own server on our own network.
#
# `python3 serve.py &` is not enough, and the way it fails is nasty: the job
# keeps the terminal as its stdout and stderr.  Close that terminal, or let the
# shell exit, and every write to them raises -- so the endpoints that log
# (which are exactly the POSTs: saving times, and the stop-server button)
# started failing while plain page loads carried on working.  serve.py no
# longer lets a log line break a request, but a background job still wants a
# session of its own and a real file to write to, which is what this does:
#
#   setsid       a new session, so closing the terminal cannot HUP it
#   < /dev/null  nothing to read, so it can never be stopped for reading the tty
#   >> log 2>&1  both streams land in a file that is always writable
#
# macOS has no setsid(1) -- it is a util-linux tool -- but setsid(2) is POSIX,
# and Python, which is about to run anyway, exposes it: os.setsid() and then
# exec serve.py is exactly what the command does.  Nor has macOS a /proc, so
# "is this pid our server" is asked of ps there.  That is the whole of the
# difference between the two systems; on Linux nothing here changed.
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"
ENVNAME=ilya-frank
PIDFILE="$ROOT/.serve.pid"
LOG="$ROOT/serve.log"
# The port Parseh keeps, which its Settings > Network page writes; a number on
# this command line wins for this one start.  Filled in below, once the Python
# that can read the file has been found -- config/network.json is JSON, and
# this is /bin/sh.
PORT=""
DEFAULT_PORT=7654

cmd=""
for a in "$@"; do
  case "$a" in
    start|stop|status|log|restart|cert) cmd="$a" ;;
    [0-9]*) PORT="$a" ;;
    *) echo "unknown argument: $a"; exit 2 ;;
  esac
done
[ -n "$cmd" ] || cmd=start

cmdline_of() {                    # the arguments of a pid, one per line
  if [ -r "/proc/$1/cmdline" ]; then                 # Linux
    tr '\0' '\n' < "/proc/$1/cmdline"
  else                                               # macOS, the BSDs: no /proc
    ps -ww -p "$1" -o args= 2>/dev/null | tr ' ' '\n'
  fi
}

running() {                       # 0 if the pidfile names a live serve.py
  [ -f "$PIDFILE" ] || return 1
  pid=$(cat "$PIDFILE" 2>/dev/null) || return 1
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  cmdline_of "$pid" | grep -q serve.py || return 1
  return 0
}

port_of() {                       # the port a running server is actually on
  pid=$(cat "$PIDFILE" 2>/dev/null) || return 1
  cmdline_of "$pid" | grep -m1 -x '[0-9][0-9]*'
}

do_stop() {
  if ! running; then
    echo "not running"
    rm -f "$PIDFILE"
    return 0
  fi
  pid=$(cat "$PIDFILE")
  p=$(port_of); [ -n "$p" ] || p=$PORT
  # ask it to stop the way the page's button does, then insist
  curl -sk -m 5 -X POST "https://127.0.0.1:$p/__shutdown" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.3
  done
  if kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null || true; sleep 1; fi
  if kill -0 "$pid" 2>/dev/null; then kill -9 "$pid" 2>/dev/null || true; fi
  rm -f "$PIDFILE"
  echo "stopped (pid $pid)"
}

# ---- the environment ---------------------------------------------------------
# lib/env.sh finds it -- $PARSEH_PYTHON, the checkout's .runtime/env that
# ./install.sh makes, an environment called ilya-frank wherever conda, mamba
# or micromamba keeps one -- and puts its programs first on the PATH, which
# every tool serve.py starts inherits.  Without one the machine's python3
# serves, and says so.
. "$ROOT/lib/env.sh"
parseh_env
PY="$PARSEH_PY"
if [ -z "$PARSEH_PREFIX" ]; then
  echo "note: no '$ENVNAME' environment -- serving with $PY"
  echo "      ./install.sh makes it (rebuilding books and dividing words need it)"
fi

# The port the Settings page keeps, unless one was given above.  serve.py
# would find it by itself; it is read here too because this script polls the
# address to see that the server came up, and stops it by posting to it.
if [ -z "$PORT" ]; then
  PORT=$("$PY" -c 'import json,sys
try:
    with open("config/network.json", encoding="utf-8") as f:
        p = int(json.load(f).get("port") or 0)
except Exception:
    p = 0
print(p if 1024 <= p <= 65535 else '"$DEFAULT_PORT"')' 2>/dev/null) || PORT=""
  [ -n "$PORT" ] || PORT=$DEFAULT_PORT
fi

case "$cmd" in
  stop)   do_stop; exit 0 ;;
  status)
    if running; then
      echo "running: pid $(cat "$PIDFILE"), https port $(port_of), log $LOG"
    else
      echo "not running"
    fi
    exit 0 ;;
  log)    exec tail -n 40 -f "$LOG" ;;
  cert)
    "$PY" serve.py --cert
    if running; then echo "now:  ./serve.sh restart"; fi
    exit 0 ;;
  restart) do_stop ;;
esac

if running; then
  echo "already running: pid $(cat "$PIDFILE") on port $(port_of)"
  echo "use  ./serve.sh restart  to replace it, or  ./serve.sh stop"
  exit 0
fi

# A Mac ships a python3 that is only a stub until the command line tools are
# installed; better to hear that here than from an empty log.
if ! "$PY" -c 'import sys' >/dev/null 2>&1; then
  echo "python3 does not run here ($PY)."
  echo "  macOS:  xcode-select --install   (or Python from python.org, or the conda env)"
  echo "  Linux:  apt install python3      (or:  conda env create -f environment.yml)"
  exit 1
fi

# Serving needs only the standard library, but saving an edited timestamp
# shells out to lib/timestamp.py and lib/tex2html.py, and those do not.
"$PY" - <<'PYEOF' || echo "note: the save-times endpoint needs the conda env; serving still works"
import sys
for m in ("rapidfuzz",):
    try:
        __import__(m)
    except ImportError:
        sys.exit(1)
PYEOF

# The log of the run before is KEPT, as serve.log.1 (its last megabyte), and
# this run starts an empty serve.log: the traceback that made somebody restart
# Parseh must not be erased by the restart.  Settings > About shows both, and
# makes a fault report of them (lib/faultlog.py, TO-DO 5.31).
"$PY" "$ROOT/lib/faultlog.py" rotate "$LOG" 2>/dev/null || : > "$LOG"
rm -f "$PIDFILE"
# the server is told which file is its log, so the page reads the right one
PARSEH_LOG="$LOG"; export PARSEH_LOG
# The server records its own pid: setsid forks when it is already a process
# group leader, so $! could be setsid's pid and not the server's.  -u because
# Python block-buffers stdout when it is a file rather than a terminal, and a
# log you cannot read while it runs is not a log.
if command -v setsid >/dev/null 2>&1; then
  SERVE_PIDFILE="$PIDFILE" setsid sh -c 'echo $$ > "$SERVE_PIDFILE"; exec "$0" -u serve.py "$1"' \
      "$PY" "$PORT" < /dev/null >> "$LOG" 2>&1 &
else
  # no setsid(1) on this system: the same three steps -- a new session, the
  # pid, then exec -- done by Python itself
  SERVE_PIDFILE="$PIDFILE" "$PY" -c '
import os, sys
try:
    os.setsid()
except OSError:
    pass                          # already a session leader: nothing to leave
with open(os.environ["SERVE_PIDFILE"], "w") as f:
    f.write("%d\n" % os.getpid())
os.execv(sys.executable, [sys.executable, "-u", "serve.py", sys.argv[1]])
' "$PORT" < /dev/null >> "$LOG" 2>&1 &
fi
bg=$!

# wait until it actually answers, so a failure to bind is reported here and
# not discovered later from a browser (-k: our own self-signed certificate).
# The pidfile appears a moment after the fork -- Python takes longer to start
# than curl takes to be refused -- so only once it is there can "not running"
# mean the server died; three seconds without it mean it never started.
ok=""
for i in $(seq 1 80); do
  if curl -sk -m 1 -o /dev/null "https://127.0.0.1:$PORT/" 2>/dev/null; then ok=1; break; fi
  if [ -s "$PIDFILE" ]; then running || break
  elif [ "$i" -gt 12 ]; then break; fi
  sleep 0.25
done

if [ "$ok" != "1" ]; then
  echo "failed to start -- the log says:"
  sed 's/^/    /' "$LOG"
  # alive but never answered (bound, yet unreachable on 127.0.0.1): do not
  # leave it behind with no pidfile for `stop` to find it by
  if running; then kill "$(cat "$PIDFILE")" 2>/dev/null || true; fi
  wait "$bg" 2>/dev/null || true          # reap it quietly, or sh reports "Terminated"
  rm -f "$PIDFILE"
  exit 1
fi

sed -n '1,14p' "$LOG"
echo
echo "running in the background: pid $(cat "$PIDFILE"),  log $LOG"
echo "stop it with:  ./serve.sh stop      (or the stop button on any page)"
