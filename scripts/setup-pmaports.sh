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

# Apply our fixes for tooling drift since the pin (see patches/ and quest/PHASE0.md).
PATCHDIR="$(cd "$(dirname "$0")/.." && pwd)/patches"
if ls "$PATCHDIR"/*.patch >/dev/null 2>&1; then
	echo "Applying our patches from $PATCHDIR ..."
	for p in "$PATCHDIR"/*.patch; do
		echo "  git apply $(basename "$p")"
		git -C "$DEST" apply "$p"
	done
fi

# Place the vendored Mali GPU driver tarball into the kernel aport dir. It's a LOCAL source in
# the linux-samsung-gtelwifi APKBUILD (see patches/0002-mali-gpu-driver.patch) — a binary that
# can't live in a git-apply patch. Provenance + sha512 in vendor/SOURCES.md.
MALI_TARBALL="$(cd "$(dirname "$0")/.." && pwd)/vendor/mali-utgard-sc8830-r4p1.tar.gz"
if [ -f "$MALI_TARBALL" ]; then
	echo "Placing Mali driver tarball into the kernel aport dir ..."
	cp "$MALI_TARBALL" "$DEST/device/downstream/linux-samsung-gtelwifi/"
else
	echo "WARNING: $MALI_TARBALL missing — GPU kernel build will fail checksum. See vendor/SOURCES.md."
fi

echo "Done. Device package: device/downstream/device-samsung-gtelwifi"
echo "Kernel package:  device/downstream/linux-samsung-gtelwifi (3.10.17 fork)"
