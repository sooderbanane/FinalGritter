#!/usr/bin/env bash
set -euo pipefail

# ─── CONFIG ────────────────────────────────────────────────────────
# Python anomaly detector
PY_SCRIPT_DIR="./managing_sensorData"
PY_SCRIPT="Analizing.py"
OTHER_SCRIPT="fromMQTTtocsv.py"


VENV_DIR=".venv"


# Zigbee2MQTT command (could be a service or binary)
ZIGBEE2MQTT_CMD="zigbee2mqtt"   # or "npm run start:zigbee" or "systemctl start zigbee2mqtt"

# Next.js frontend
FRONTEND_DIR="./frontend/gritter-frontend"
# ────────────────────────────────────────────────────────────────────

cleanup() {
  echo
  echo "🛑 Shutting down…"
  [[ -n "${PY_PID-}"       ]] && kill "$PY_PID"       2>/dev/null || true
  [[ -n "${PY_PID-}"    ]] && kill "$fromMQTTtocsv"    2>/dev/null || true
  [[ -n "${ZIGBEE_PID-}"   ]] && kill "$ZIGBEE_PID"   2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "🟢 Starting Zigbee2MQTT…"
# If you need to cd into its folder, do: cd /path/to/zigbee2mqtt
cd ~
$ZIGBEE2MQTT_CMD &
ZIGBEE_PID=$!
echo "   → Zigbee2MQTT PID: $ZIGBEE_PID"


echo "🚀 Activating Python venv (if present)…"
if [[ -f "$VENV_DIR/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
else
  echo "⚠️  No venv at $VENV_DIR — assuming 'python' is available globally."
fi

echo "🟢 Starting Python anomaly detector…"
cd "$PY_SCRIPT_DIR"
python "$PY_SCRIPT" &
PY_PID=$!
echo "   → Python PID: $PY_PID"

echo "🟢 Starting your other script…"
python "$fromMQTTtocsv" &
PY_PID=$!
echo "   → Other script PID: $OTHER_PID"


echo "🟢 Starting Next.js frontend…"
cd "$FRONTEND_DIR"
npm run dev

# When Next.js exits (or you hit Ctrl+C), clean up everything:
cleanup
