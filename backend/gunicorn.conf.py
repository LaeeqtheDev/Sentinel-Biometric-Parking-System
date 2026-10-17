"""Gunicorn settings. Recognition runs on Celery workers, so API workers stay
I/O-bound and threads give cheap concurrency."""

import multiprocessing
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
threads = int(os.environ.get("GUNICORN_THREADS", 4))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 30))
graceful_timeout = 30
keepalive = 5
max_requests = 2000          # recycle workers to cap memory growth
max_requests_jitter = 200
accesslog = "-"
errorlog = "-"
forwarded_allow_ips = "*"
