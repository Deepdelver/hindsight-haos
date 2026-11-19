ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

# Install Python, pip, and PostgreSQL (Hindsight uses embedded PG)
RUN apk add --no-cache \
    python3 \
    py3-pip \
    postgresql16 \
    postgresql16-client \
    postgresql16-contrib \
    libpq \
    gcc \
    python3-dev \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    && rm -rf /var/cache/apk/*

# Create hindsight user (UID 1000, matching upstream image)
RUN adduser -D -u 1000 -h /home/hindsight hindsight

# Install hindsight-api via pip
RUN pip3 install --no-cache-dir --break-system-packages hindsight-api

# Clean up build deps to reduce image size
RUN apk del gcc python3-dev musl-dev libffi-dev openssl-dev cargo 2>/dev/null || true

# Create data directories
RUN mkdir -p /data/pg /data/hindsight && \
    chown -R hindsight:hindsight /data/pg /data/hindsight

# PostgreSQL data dir
ENV PGDATA=/data/pg

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
