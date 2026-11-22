# SPDX-License-Identifier: GPL-3.0-or-later
"""Where Parseh lives: ONE place that says it, so that the next move is one edit.

Every address Parseh writes for itself is built here -- the repository the
updates come from, the foot of every page exported from the studio, the icons
the phone app is installed with, the line a download introduces itself with --
and nothing else in the tree spells the organisation or the domain.  A move is
an edit of the three names below, and then

    python3 lib/release.py links

which asks every address what it answers (docs/releasing.md, "Where Parseh
lives").  tests/test_project.py pins the literal addresses: a move is a
decision, and that test is where it is written down.

STANDARD LIBRARY ONLY, AND NO OTHER PARSEH MODULE: the guide's compiler
(html-guide/engine) and the studio's own server import it with nothing else
around, as they import lib/author.py.  No version is written here either
(tests/test_version.py scans for one): `agent()` is handed it.

THE PERSON IS NOT THE PROJECT.  The author's own GitHub profile is
lib/author.py's, the GitHub link of the author line (the Licences page, About,
the README): a person's, who stays where he is when the project moves.  The
GitHub link at the foot of the hub, of the Settings hub and of the guide is the
PROJECT'S -- GITHUB_URL below, which the page that draws the foot hands to
lib/author.py (author.foot_links), as the exported pages' foot links it too.

THE ADDRESSES A PERSON IS GIVEN and THE ONES A MACHINE FETCHES are told apart
on purpose:

  * a person may be sent through a redirect, and is, by GitHub, from the old
    name of a repository to the new one;
  * a machine -- the update road, the icons Chrome's WebAPK server fetches --
    gets an address that answers `200` as written, because a redirect is one
    more place to fail, and where the failure is silent (the phone app's
    install button just vanishes) nobody learns of it.
"""

ORG = "parseh-io"
NAME = "Parseh"
REPO = ORG + "/" + NAME

# --- GitHub: the repository, its releases, and the feed the updater asks
GITHUB_URL = "https://github.com/" + REPO
RELEASES_URL = GITHUB_URL + "/releases"
LATEST_URL = RELEASES_URL + "/latest"
# where a fault is reported: Settings -> About links it beside "Copy a report"
ISSUES_URL = GITHUB_URL + "/issues"
# the newest PUBLISHED release that is not a prerelease (never a draft): the one
# Settings -> Updating Parseh looks at
FEED = "https://api.github.com/repos/%s/releases/latest" % REPO

# --- the domain, served by GitHub Pages
WEBSITE_URL = "https://parseh.io/"
# The guide's address: the one every page exported from Parseh carries for ever
# in its foot, and the one the README and the documents give.
GUIDE_URL = "https://parseh.io/guide"
# how the address of a page of the guide is built: SITE + "site/reference/whats-new.html"
SITE = GUIDE_URL + "/"
# The phone app's icons.  A MACHINE fetches these (Chrome on Android, from its own
# servers), so no redirect may stand before them: under the domain it is
# `parseh-io.github.io/guide/...` that redirects, and GitHub's own address is
# therefore the wrong one to write.  lib/mobile.py says what a 404 does.
ICONS_URL = SITE + "lib/icons/"

# --- where the guide and the site are published FROM (named by the documents and
# by `release.py links`, in no address)
GUIDE_REPO = ORG + "/guide"
SITE_REPO = ORG + "/" + ORG + ".github.io"


def agent(version):
    """The line every download introduces itself with, naming where to write."""
    return "%s/%s (+%s)" % (NAME, version, GITHUB_URL)
