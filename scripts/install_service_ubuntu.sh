#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/linkedin-autoposter}"
SERVICE_NAME="${SERVICE_NAME:-linkedin-autoposter}"
SERVICE_FILE="${SERVICE_NAME}.service"

if [[ "$(pwd)" != "${APP_DIR}" ]]; then
  echo "Run this from ${APP_DIR}."
  echo "Current directory: $(pwd)"
  exit 1
fi

if [[ ! -f ".env" ]]; then
  cp .env.example .env
  echo "Created .env from .env.example."
  echo "Fill .env, run setup_linkedin_oauth.py, then rerun this script."
  exit 1
fi

python3 -m venv venv
./venv/bin/pip install -r requirements.txt
mkdir -p data logs

./venv/bin/python healthcheck.py

sudo cp "${SERVICE_FILE}" "/etc/systemd/system/${SERVICE_FILE}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl --no-pager status "${SERVICE_NAME}"
