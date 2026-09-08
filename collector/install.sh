#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run this installer with sudo." >&2
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="/opt/football-ai"
DATA_DIR="/var/lib/football-ai"
CONFIG_DIR="/etc/football-ai"

if ! id football-ai >/dev/null 2>&1; then
  useradd --system --home-dir "${DATA_DIR}" --shell /usr/sbin/nologin football-ai
fi

install -d -o root -g root -m 0755 "${INSTALL_DIR}" "${INSTALL_DIR}/collector"
install -d -o football-ai -g football-ai -m 0750 "${DATA_DIR}"
install -d -o root -g football-ai -m 0750 "${CONFIG_DIR}"
install -o root -g root -m 0755 "${SOURCE_DIR}/collector/collector.py" "${INSTALL_DIR}/collector/collector.py"
install -o root -g root -m 0755 "${SOURCE_DIR}/collector/api_server.py" "${INSTALL_DIR}/collector/api_server.py"
install -o root -g root -m 0644 "${SOURCE_DIR}/collector/systemd/football-ai-collector.service" /etc/systemd/system/football-ai-collector.service
install -o root -g root -m 0644 "${SOURCE_DIR}/collector/systemd/football-ai-collector.timer" /etc/systemd/system/football-ai-collector.timer
install -o root -g root -m 0644 "${SOURCE_DIR}/collector/systemd/football-ai-relay.service" /etc/systemd/system/football-ai-relay.service

if [[ ! -s "${CONFIG_DIR}/relay-secret" ]]; then
  umask 0077
  head -c 48 /dev/urandom | base64 > "${CONFIG_DIR}/relay-secret"
fi
chown root:football-ai "${CONFIG_DIR}/relay-secret"
chmod 0640 "${CONFIG_DIR}/relay-secret"

systemctl daemon-reload
systemctl enable --now football-ai-collector.timer
systemctl start football-ai-collector.service
systemctl enable --now football-ai-relay.service

echo "Collector installed."
systemctl --no-pager --full status football-ai-collector.service || true
systemctl --no-pager --full status football-ai-relay.service || true
