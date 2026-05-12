#!/usr/bin/env bash
set -o errexit

# Install Tesseract OCR
apt-get update -qq && apt-get install -y -qq tesseract-ocr || echo "apt-get failed, continuing"

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements-prod.txt || pip install -r requirements-prod.txt --no-deps

# Static files
python manage.py collectstatic --no-input

# Database migrations
python manage.py migrate
