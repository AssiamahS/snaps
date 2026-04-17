#!/usr/bin/env bash
# Find the latest NPPES monthly zip on download.cms.gov and pull it.
set -euo pipefail

OUT="${1:-/tmp/nppes.zip}"
INDEX_URL="https://download.cms.gov/nppes/NPI_Files.html"

URL=$(curl -sL "$INDEX_URL" \
  | grep -oE "NPPES_Data_Dissemination_[A-Za-z]+_[0-9]{4}_V[0-9]+\.zip" \
  | head -1)

if [ -z "$URL" ]; then
  echo "Could not find NPPES monthly file on $INDEX_URL" >&2
  exit 1
fi

FULL_URL="https://download.cms.gov/nppes/${URL}"
echo "==> Downloading $FULL_URL -> $OUT"
curl -L --fail -o "$OUT" "$FULL_URL"
ls -lh "$OUT"
