#!/usr/bin/env bash
# One-time setup ON the server: installs the systemd timer that runs
# scripts/server-deploy.sh every 2 minutes. Re-run after editing the units.
#   sudo ./scripts/install-server-deployer.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
install -m 644 "$HERE/systemd/viscan-deploy.service" /etc/systemd/system/viscan-deploy.service
install -m 644 "$HERE/systemd/viscan-deploy.timer"   /etc/systemd/system/viscan-deploy.timer
systemctl daemon-reload
systemctl enable --now viscan-deploy.timer
systemctl list-timers viscan-deploy.timer --no-pager
echo "Installed. Logs: journalctl -u viscan-deploy.service -f   and   /home/ubuntu/.viscan-deploy/deploy.log"
