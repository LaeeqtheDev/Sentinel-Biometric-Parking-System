"""
Celery application.

Two queues:
  * recognition  CPU-heavy OCR and face matching. Scale these workers
                 independently of the API (one process per CPU core).
  * default      housekeeping (expired challenge / token cleanup).

Run:
  celery -A core worker -Q recognition -c 4 --loglevel=info
  celery -A core worker -Q default -c 1 --loglevel=info
  celery -A core beat --loglevel=info
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("sentinel")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["core", "recognition"])
