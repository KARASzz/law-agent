#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

HOST="127.0.0.1"
PORT="8000"
WORKBENCH_URL="http://${HOST}:${PORT}/workbench"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_CMD=".venv/bin/python"
elif [[ -x ".venv/Scripts/python.exe" ]]; then
  PYTHON_CMD=".venv/Scripts/python.exe"
else
  PYTHON_CMD="python3"
fi

echo "[Law Agent] Project: $(pwd)"
echo "[Law Agent] Python: ${PYTHON_CMD}"

if lsof -nP -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[Law Agent] Port ${PORT} is already listening."
  echo "[Law Agent] Opening ${WORKBENCH_URL}"
  open "${WORKBENCH_URL}"
  exit 0
fi

if ! "${PYTHON_CMD}" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "[Law Agent] Missing FastAPI or uvicorn."
  echo "[Law Agent] Please run:"
  echo "    ${PYTHON_CMD} -m pip install -r requirements.txt"
  read -r -p "Press Enter to exit..."
  exit 1
fi

echo "[Law Agent] Opening ${WORKBENCH_URL}"
open "${WORKBENCH_URL}"

echo "[Law Agent] Starting API service. Press Ctrl+C to stop."
"${PYTHON_CMD}" -m law_agent.main api

read -r -p "Press Enter to exit..."
