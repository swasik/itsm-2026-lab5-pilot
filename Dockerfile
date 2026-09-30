# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md sections 1.8 and 7.4; the lecturer built and ran it with Docker Compose
# Lab 5 (design/LAB5.md 1.2 and 13.5; Claude Code, Opus 5.5): base pinned by digest and OS packages upgraded at build time, so the image gate (Trivy HIGH/CRITICAL with a fix) passes; what no upgrade fixes is in .trivyignore.
# Dependencies are installed at build time; the running container needs no network (Tier B has no egress).
FROM python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b

# Debian's security updates published after the base image was built (Lab 5 image gate).
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SVCDESK_DB=/data/svcdesk.db

WORKDIR /app

# The whole repository (minus .dockerignore) so that the tests service can also run the repository self-checks.
COPY . /app

RUN pip install ".[tests]" \
    && useradd --system --uid 10001 --create-home svcdesk \
    && mkdir -p /data \
    && chown svcdesk:svcdesk /data

USER svcdesk
EXPOSE 8080

CMD ["uvicorn", "svcdesk.main:app", "--host", "0.0.0.0", "--port", "8080"]
