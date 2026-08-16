#!/usr/bin/env bash
set -e

# Render build script for Mirror Dashboard
# Injects the GITHUB_TOKEN environment variable into index.html at build time,
# along with a SHA-256 hash of the MIRROR_PIN passcode (the raw PIN itself
# never ends up in the built file). Neither secret touches the repo — they're
# baked in during the Render build from environment variables.

if [ -z "$GITHUB_TOKEN" ]; then
  echo "ERROR: GITHUB_TOKEN environment variable is not set."
  echo "Add it in Render → Your Service → Environment."
  exit 1
fi

if [ -z "$MIRROR_PIN" ]; then
  echo "ERROR: MIRROR_PIN environment variable is not set."
  echo "Add it in Render → Your Service → Environment (a 4-digit passcode)."
  exit 1
fi

PIN_HASH=$(printf '%s' "$MIRROR_PIN" | sha256sum | cut -d' ' -f1)

mkdir -p dist
sed \
  -e "s/MIRROR_TOKEN_PLACEHOLDER/${GITHUB_TOKEN}/" \
  -e "s/MIRROR_PIN_HASH_PLACEHOLDER/${PIN_HASH}/" \
  index.html > dist/index.html

echo "✓ Built dist/index.html with token and PIN hash injected."
