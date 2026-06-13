#!/usr/bin/env bash
# Pulls the latest code and restarts the SafeSight service.
# Run automatically by the self-hosted GitHub Actions runner on every push to
# main. Safe to run by hand too: ./deploy/deploy.sh
set -o errexit
set -o nounset
set -o pipefail

PROJECT_DIR=/home/ubuntu/safesight-backend
VENV=/home/ubuntu/venv

cd "$PROJECT_DIR"

echo "==> Pulling latest code"
git pull --ff-only

echo "==> Installing dependencies (no-op if unchanged)"
"$VENV/bin/pip" install -q -r requirements.txt

echo "==> Loading environment"
set -a; source "$PROJECT_DIR/.env"; set +a

echo "==> Applying migrations"
"$VENV/bin/python" manage.py migrate --no-input

echo "==> Collecting static files"
"$VENV/bin/python" manage.py collectstatic --no-input

echo "==> Restarting daphne service"
sudo systemctl restart safesight

echo "==> Deploy complete"
