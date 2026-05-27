#!/usr/bin/env bash
set -e

# Render build script for Mirror Dashboard
# Injects the GITHUB_TOKEN environment variable into index.html at build time.
# The token never touches the client — it's baked in during the Render build.

if [ -z "$GITHUB_TOKEN" ]; then
  echo "ERROR: GITHUB_TOKEN environment variable is not set."
  echo "Add it in Render → Your Service → Environment."
  exit 1
fi

mkdir -p dist
sed "s/MIRROR_TOKEN_PLACEHOLDER/${GITHUB_TOKEN}/" index.html > dist/index.html

echo "✓ Built dist/index.html with token injected."
