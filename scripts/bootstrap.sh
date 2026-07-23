#!/usr/bin/env bash
# One-shot bootstrap for a fresh Ubuntu EC2 instance. Paste this block in
# over SSH AFTER the EC2 instance is up. Handles: apt deps, git clone,
# venv, .env, data/logs dirs. NOT systemd — that comes after the OAuth step,
# so this script exits without enabling the service and lets you verify
# OAuth works first.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/abnsrishik/linkedin_autopost.git}"
APP_DIR="${APP_DIR:-/home/ubuntu/linkedin-autoposter}"

echo "[.] Installing system packages..."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git

echo "[.] Cloning/refresh repo at ${APP_DIR}..."
mkdir -p "$(dirname "${APP_DIR}")"
if [[ -d "${APP_DIR}/.git" ]]; then
  cd "${APP_DIR}"
  git pull --ff-only
else
  git clone "${REPO_URL}" "${APP_DIR}"
  cd "${APP_DIR}"
fi

echo "[.] Creating virtualenv + installing deps..."
python3 -m venv venv
./venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt

echo "[.] Making runtime dirs..."
mkdir -p data logs

if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
    echo "[!] Created .env from .env.example."
    echo "[!] Fill .env now: nano .env   (then save Ctrl+O / Enter / Ctrl+X)"
    echo "[!] After saving .env, run: ./venv/bin/python setup_linkedin_oauth.py"
    echo "[!] Then run: ./venv/bin/python healthcheck.py && sudo bash scripts/install_service_ubuntu.sh"
    exit 0
  else
    echo "[!] .env.example missing in the repo. Re-clone."
    exit 1
  fi
fi

echo "[.] .env already present. Running healthcheck..."
./venv/bin/python healthcheck.py || echo "[!] Healthcheck failed — fix .env before installing service."
