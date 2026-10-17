#!/usr/bin/env bash
# Build/release step for platforms without Docker (e.g. Render).
set -o errexit
pip install --upgrade pip
pip install -r requirements-prod.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
