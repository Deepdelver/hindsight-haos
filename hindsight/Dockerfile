ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

# Install Python, pip, PostgreSQL with pgvector, and build deps
RUN apk add --no-cache \
    python3 \
    py3-pip \
    postgresql16 \
    postgresql16-client \
    postgresql16-contrib \
    postgresql16-dev \
    libpq \
    gcc \
    g++ \
    python3-dev \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    make \
    cmake \
    git \
    && rm -rf /var/cache/apk/*

# Build and install pgvector extension
RUN cd /tmp && \
    git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git && \
    cd pgvector && \
    make && make install && \
    cd / && rm -rf /tmp/pgvector

# Create hindsight user (UID 1000, matching upstream image)
RUN adduser -D -u 1000 -h /home/hindsight hindsight

# Install hindsight-api-slim (no local ML models — uses external/OpenAI embeddings by default)
# Use slim to keep image size manageable on HA hardware
RUN pip3 install --no-cache-dir --break-system-packages "hindsight-api[embedded-db]"

# Clean up build deps to reduce image size
RUN apk del gcc g++ python3-dev musl-dev libffi-dev openssl-dev cargo make cmake git postgresql16-dev 2>/dev/null || true && \
    rm -rf /root/.cache /tmp/*

# Create data directories
RUN mkdir -p /data/pg /data/hindsight && \
    chown -R hindsight:hindsight /data/pg /data/hindsight

# PostgreSQL data dir
ENV PGDATA=/data/pg

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
