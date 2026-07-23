#!/usr/bin/env bash
# Idempotently install the LinkedIn Autoposter as a systemd service.
# Running this multiple times is safe: it won't recreate venv if present,
# won't overwrite .env if present, and will always re-enable + restart
# the service so deploys pick up the new code.
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/linkedin-autoposter}"
SERVICE_NAME="${SERVICE_NAME:-linkedin-autoposter}"
SERVICE_FILE="${SERVICE_NAME}.service"

# Must be run from the app directory.
if [[ "$(pwd)" != "${APP_DIR}" ]]; then
  echo "Run this from ${APP_DIR}."
  echo "Current directory: $(pwd)"
  exit 1
fi

# .env handling: create from example ONLY if missing, fail loudly either way
# so the user can fill it in before we install the service.
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
    echo "[.] Created .env from .env.example."
    echo "[!] Fill in .env, then rerun this script."
    exit 1
  else
    echo "[!] Neither .env nor .env.example present. Run the bootstrap script first."
    exit 1
  fi
fi

# mkdir before any venv work, so pip install has stable cwd.
mkdir -p data logs

# Idempotent venv: only create if missing.
if [[ ! -d "venv" ]]; then
  echo "[.] Creating virtualenv..."
  python3 -m venv venv
fi

# Requirements: install only if venv is fresh OR requirements.txt changed.
# Skip reinstall if already up to date — keeps restarts fast.
./venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt

# Healthcheck gates the systemd install/upgrade — fails loud before restart.
echo "[.] Running healthcheck..."
./venv/bin/python healthcheck.py
HEALTHCHECK_EXIT=$?
if [[ ${HEALTHCHECK_EXIT} -ne 0 ]]; then
  echo "[!] Healthcheck failed (exit ${HEALTHCHECK_EXIT}). Not touching the service."
  exit "${HEALTHCHECK_EXIT}"
fi

# Install + enable + start the service.
sudo cp "${SERVICE_FILE}" "/etc/systemd/system/${SERVICE_FILE}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "[.] Service status:"
sudo systemctl --no-pager --full status "${SERVICE_NAME}" || true
