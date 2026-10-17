# One image, three roles: api | worker | beat (see docker-compose.yml).
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-prod.txt requirements-face.txt ./
RUN pip install -r requirements-prod.txt

# Face recognition is optional and heavy (compiles dlib). Build with
#   docker build --build-arg WITH_FACE=1 .
ARG WITH_FACE=0
RUN if [ "$WITH_FACE" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends build-essential cmake \
        && pip install -r requirements-face.txt \
        && apt-get purge -y build-essential cmake && apt-get autoremove -y \
        && rm -rf /var/lib/apt/lists/*; \
    fi

COPY . .
RUN SECRET_KEY=build-only ALLOWED_HOSTS=build DATABASE_URL=sqlite:////tmp/build.db REDIS_URL=redis://localhost:6379/0 \
    python manage.py collectstatic --no-input

RUN useradd --create-home --uid 10001 sentinel && chown -R sentinel /app
USER sentinel

EXPOSE 8000
CMD ["gunicorn", "core.wsgi:application", "-c", "gunicorn.conf.py"]
