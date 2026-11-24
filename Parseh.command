#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Parseh on a Mac -- double-click this file in the Finder.
#
# The first time, it installs what Parseh needs (./install.sh: everything goes
# into this folder, under .runtime/, unless the Mac already has conda with an
# ilya-frank environment).  Every time, it starts the server (./serve.sh) and
# opens the browser on it.  Terminal shows what happens; closing its window
# does not stop the server -- the stop button on any page does.
#
# Linux has no double-click convention this could follow; ./install.sh and
# ./serve.sh are the same two steps there.
cd "$(dirname "$0")" || exit 1
. ./lib/env.sh
parseh_env
if [ -z "$PARSEH_PREFIX" ]; then
  echo "The first start: installing what Parseh needs.  This takes a while, once."
  echo
  if ! ./install.sh; then
    echo
    echo "The installation did not finish -- the lines above say why."
    echo "Press Return to close."
    read -r _
    exit 1
  fi
fi
./serve.sh || { echo "Press Return to close."; read -r _; exit 1; }
# The port Parseh is on is the one its Settings > Network page keeps, which a
# change there moves at once -- so it is read rather than written down here.
PORT=$("$PARSEH_PY" -c 'import json
try:
    with open("config/network.json", encoding="utf-8") as f:
        p = int(json.load(f).get("port") or 0)
except Exception:
    p = 0
print(p if 1024 <= p <= 65535 else 7654)' 2>/dev/null) || PORT=7654
[ -n "$PORT" ] || PORT=7654
open "http://localhost:$PORT/"
