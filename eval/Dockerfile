FROM python:3.12.7-slim-bookworm

ARG SOURCE_GIT_SHA
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app SOURCE_GIT_SHA=${SOURCE_GIT_SHA}
LABEL org.opencontainers.image.revision=${SOURCE_GIT_SHA}
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends tar && \
    rm -rf /var/lib/apt/lists/* && useradd -u 10001 -r -s /bin/false -d /app evaluator
WORKDIR /app
COPY eval/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    python -c "import os,re; assert re.fullmatch('[0-9a-f]{40}',os.environ['SOURCE_GIT_SHA'])"
COPY ragops/__init__.py /app/ragops/__init__.py
COPY ragops/evalsuite /app/ragops/evalsuite
COPY ragops/gate.py ragops/coverage.py /app/ragops/
COPY config/schemas /app/config/schemas
USER 10001:10001
CMD ["python", "-m", "ragops.evalsuite.job"]
