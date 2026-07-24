#!/usr/bin/env sh
# Recreate the pmaports build input at our known-good pre-archival commit.
# The gtelwifi port was archived 2026-06-22 by a mass "unmaintained" sweep;
# commit a1ceca353 is its parent, where the package is still live in
# device/downstream/. Building from here avoids the archived-corpse state.
set -eu

REPO_URL="https://gitlab.postmarketos.org/postmarketOS/pmaports.git"
KNOWN_GOOD="a1ceca353"
BRANCH="quest-gtelwifi"
DEST="$(cd "$(dirname "$0")/.." && pwd)/pmaports"

if [ -e "$DEST/.git" ]; then
	echo "pmaports/ already exists at $DEST — leaving it alone."
	echo "Delete it first if you want a clean re-clone."
	exit 0
fi

echo "Cloning pmaports into $DEST ..."
git clone "$REPO_URL" "$DEST"

echo "Creating branch $BRANCH at known-good commit $KNOWN_GOOD ..."
git -C "$DEST" checkout -b "$BRANCH" "$KNOWN_GOOD"

echo "Done. Device package: device/downstream/device-samsung-gtelwifi"
echo "Kernel package:  device/downstream/linux-samsung-gtelwifi (3.10.17 fork)"
