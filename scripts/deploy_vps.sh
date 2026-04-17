#!/usr/bin/env bash
# One-shot deploy for a fresh ubuntu 22.04 VPS that already has postgres.
# Clones snaps, installs cloudflared, writes /etc/snaps/env, and enables
# three systemd units:
#   snaps-api.service      — uvicorn on 127.0.0.1:8000
#   snaps-tunnel.service   — cloudflared quick tunnel, public HTTPS
#   snaps-refresh.timer    — monthly NPPES reload
set -euo pipefail

REPO=https://github.com/AssiamahS/snaps.git
DIR=/opt/snaps

echo "==> deps"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-pip curl

echo "==> cloudflared"
if ! command -v cloudflared >/dev/null; then
  ARCH=$(dpkg --print-architecture)
  curl -sL -o /tmp/cloudflared.deb \
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}.deb"
  sudo dpkg -i /tmp/cloudflared.deb
fi

echo "==> clone"
if [ ! -d "$DIR/.git" ]; then
  sudo git clone "$REPO" "$DIR"
else
  sudo git -C "$DIR" pull --ff-only
fi
sudo chown -R ubuntu:ubuntu "$DIR"

echo "==> pip"
pip3 install --quiet -r "$DIR/api/requirements.txt"

echo "==> /etc/snaps/env"
sudo mkdir -p /etc/snaps
if [ ! -f /etc/snaps/env ]; then
  sudo tee /etc/snaps/env >/dev/null <<'ENV'
PGHOST=localhost
PGPORT=5432
PGDATABASE=medchat
PGUSER=medchat_app
PGPASSWORD=medchat_dev_pw_change_later
NPPES_ZIP_PATH=/tmp/nppes.zip
SNAPS_DIR=/opt/snaps
ENV
  sudo chmod 640 /etc/snaps/env
  sudo chown root:ubuntu /etc/snaps/env
  echo "   wrote /etc/snaps/env (rotate PGPASSWORD before prod)"
fi

echo "==> systemd units"
sudo cp "$DIR"/scripts/systemd/*.service /etc/systemd/system/
sudo cp "$DIR"/scripts/systemd/*.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now snaps-api.service
sudo systemctl enable --now snaps-tunnel.service
sudo systemctl enable --now snaps-refresh.timer

echo "==> status"
systemctl --no-pager status snaps-api.service    | head -5
systemctl --no-pager status snaps-tunnel.service | head -5
systemctl --no-pager list-timers snaps-refresh.timer | head -3

echo "==> done — tail the tunnel log to grab the public URL:"
echo "   journalctl -u snaps-tunnel.service -n 50 --no-pager | grep trycloudflare"
