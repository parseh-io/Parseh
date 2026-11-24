#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The video player no longer has a server of its own.

It is one of the four doors of Parseh, served with everything else by
../serve.py under a single https address:

    cd ..            # the project root
    ./serve.sh       # then open  http://localhost:7654/youtube/

The pages and the Anki endpoints that used to live here are in
lib/ytpages.py, and the root server mounts them at /youtube/.
"""
import sys

sys.exit(__doc__)
