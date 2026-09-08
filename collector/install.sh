#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run this installer with sudo." >&2
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="/opt/football-ai"
DATA_DIR="/var/lib/football-ai"

if ! id football-ai >/dev/null 2>&1; then
  useradd --system --home-dir "${DATA_DIR}" --shell /usr/sbin/nologin football-ai
fi

install -d -o root -g root -m 0755 "${INSTALL_DIR}" "${INSTALL_DIR}/collector"
install -d -o football-ai -g football-ai -m 0750 "${DATA_DIR}"
install -o root -g root -m 0755 "${SOURCE_DIR}/collector/collector.py" "${INSTALL_DIR}/collector/collector.py"
install -o root -g root -m 0644 "${SOURCE_DIR}/collector/systemd/football-ai-collector.service" /etc/systemd/system/football-ai-collector.service
install -o root -g root -m 0644 "${SOURCE_DIR}/collector/systemd/football-ai-collector.timer" /etc/systemd/system/football-ai-collector.timer

systemctl daemon-reload
systemctl enable --now football-ai-collector.timer
systemctl start football-ai-collector.service

echo "Collector installed."
systemctl --no-pager --full status football-ai-collector.service || true
