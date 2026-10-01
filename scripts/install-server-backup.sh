#!/usr/bin/env bash
# One-time setup ON the server: installs the daily Postgres backup timer.
#   sudo ./scripts/install-server-backup.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$HERE/backup-db.sh" "$HERE/restore-db.sh"
install -m 644 "$HERE/systemd/viscan-backup.service" /etc/systemd/system/viscan-backup.service
install -m 644 "$HERE/systemd/viscan-backup.timer"   /etc/systemd/system/viscan-backup.timer
systemctl daemon-reload
systemctl enable --now viscan-backup.timer
systemctl list-timers viscan-backup.timer --no-pager
echo
echo "Installed. Backups land in /home/ubuntu/.viscan-backups/"
echo "Manual run:   sudo -u ubuntu $HERE/backup-db.sh"
echo "Logs:         tail -f /home/ubuntu/.viscan-deploy/backup.log"
echo "Restore:      $HERE/restore-db.sh viscan /home/ubuntu/.viscan-backups/viscan_....sql.gz"
