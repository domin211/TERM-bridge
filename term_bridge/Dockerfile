FROM alpine:3.24@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

RUN apk add --no-cache \
    python3 \
    py3-pip \
    libstdc++ \
    libc6-compat \
    gcompat

WORKDIR /app
COPY app/ /app/
COPY hmpd /app/hmpd

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes -r /app/requirements.txt \
    && find /app -type d -exec chmod 0555 {} + \
    && find /app -type f -exec chmod 0444 {} + \
    && chmod 0555 /app/run.sh /app/hmpd

ENV PATH="/opt/venv/bin:${PATH}"

LABEL org.opencontainers.image.title="TERM Bridge" \
      org.opencontainers.image.description="HMPD thermostat controller bridge for Home Assistant" \
      org.opencontainers.image.source="https://github.com/domin211/term-bridge" \
      org.opencontainers.image.licenses="MIT" \
      io.hass.type="app"

CMD ["/app/run.sh"]
