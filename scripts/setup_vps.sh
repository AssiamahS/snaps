#!/usr/bin/env bash
# One-shot VPS bring-up for the snaps NPI database.
# Target: Ubuntu 22.04 with >= 2 GB RAM, >= 40 GB free disk.
set -euo pipefail

echo "==> 4 GB swap"
if ! swapon --show | grep -q swapfile; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab
fi

echo "==> Postgres"
sudo apt-get update -qq
sudo apt-get install -y -qq postgresql postgresql-contrib python3 python3-pip

CONF=$(sudo -u postgres psql -t -c "SHOW config_file" | xargs)
sudo sed -i "s/^#*shared_buffers.*/shared_buffers = 256MB/"        "$CONF"
sudo sed -i "s/^#*work_mem.*/work_mem = 16MB/"                     "$CONF"
sudo sed -i "s/^#*maintenance_work_mem.*/maintenance_work_mem = 256MB/" "$CONF"
sudo sed -i "s/^#*effective_cache_size.*/effective_cache_size = 1GB/"  "$CONF"
sudo sed -i "s/^#*wal_compression.*/wal_compression = on/"         "$CONF"
sudo systemctl restart postgresql

echo "==> DB + user"
PG_PW="${PG_PW:-$(openssl rand -hex 16)}"
sudo -u postgres psql <<SQL
CREATE DATABASE medchat;
CREATE USER medchat_app WITH PASSWORD '${PG_PW}';
GRANT ALL PRIVILEGES ON DATABASE medchat TO medchat_app;
\c medchat
GRANT ALL ON SCHEMA public TO medchat_app;
SQL

echo "==> Schema"
sudo -u postgres psql medchat -f "$(dirname "$0")/../schema/001_init.sql"
sudo -u postgres psql medchat -c "ALTER TABLE providers_doctors OWNER TO medchat_app;"
sudo -u postgres psql medchat -c "ALTER TABLE providers_dentists OWNER TO medchat_app;"
sudo -u postgres psql medchat -c "ALTER TABLE providers_pharmacists OWNER TO medchat_app;"

echo "==> DONE"
echo "DSN: postgresql://medchat_app:${PG_PW}@localhost/medchat"
echo "Save that password — it won't print again."
