#!/usr/bin/env bash
# Pull the latest NPPES monthly file and reload the 3 provider tables.
# Called by snaps-refresh.timer once a month.
set -euo pipefail

SNAPS_DIR="${SNAPS_DIR:-/opt/snaps}"
ZIP_PATH="${NPPES_ZIP_PATH:-/tmp/nppes.zip}"

: "${PGUSER:?set PGUSER}"; : "${PGPASSWORD:?set PGPASSWORD}"
: "${PGDATABASE:?set PGDATABASE}"; : "${PGHOST:=localhost}"; : "${PGPORT:=5432}"
export PGUSER PGPASSWORD PGDATABASE PGHOST PGPORT NPPES_ZIP_PATH

echo "[refresh] fetch"
bash "$SNAPS_DIR/scripts/fetch_nppes.sh" "$ZIP_PATH"

echo "[refresh] load"
python3 "$SNAPS_DIR/loader/npi_loader.py"

echo "[refresh] analyze"
psql "postgresql://$PGUSER:$PGPASSWORD@$PGHOST:$PGPORT/$PGDATABASE" \
  -c "ANALYZE providers_doctors; ANALYZE providers_dentists; ANALYZE providers_pharmacists;"

echo "[refresh] cleanup"
rm -f "$ZIP_PATH"
echo "[refresh] done"
