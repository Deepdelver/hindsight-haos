# syntax=docker/dockerfile:1
#################
# 1 Build Image #
#################

ARG BUILD_FROM
FROM ${BUILD_FROM}

##################
# 2 Modify Image #
##################

# S6 overlay tuning
ENV S6_CMD_WAIT_FOR_SERVICES=1 \
    S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0 \
    S6_SERVICES_GRACETIME=0

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

##################
# 3 Install apps #
##################

# Add rootfs
COPY rootfs/ /
RUN find . -type f \( -name "*.sh" -o -name "run" -o -name "finish" \) -print -exec chmod +x {} \;

RUN \
    echo "Installing system dependencies" && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg && \
    \
    echo "Adding PostgreSQL Global Development Group repository" && \
    install -d /usr/share/postgresql-common/pgdg && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc && \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list && \
    \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-15 \
        postgresql-15-pgvector \
        python3 \
        python3-pip \
        python3-venv \
        jq && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Hindsight slim API (no local ML models; embeddings/reranker are external).
# Installed into a dedicated venv so it never conflicts with system python.
RUN \
    echo "Installing hindsight-api-slim" && \
    python3 -m venv /opt/hindsight-venv && \
    /opt/hindsight-venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/hindsight-venv/bin/pip install --no-cache-dir "hindsight-api-slim[embedded-db]"

# Uses /bin for compatibility purposes
RUN if [ ! -f /bin/sh ] && [ -f /usr/bin/sh ]; then ln -s /usr/bin/sh /bin/sh; fi && \
    if [ ! -f /bin/bash ] && [ -f /usr/bin/bash ]; then ln -s /usr/bin/bash /bin/bash; fi

# Modules
ARG MODULES="00-banner.sh 00-global_var.sh"

COPY ha_automodules.sh /ha_automodules.sh
RUN chmod 744 /ha_automodules.sh && /ha_automodules.sh "$MODULES" && rm /ha_automodules.sh

ENV PACKAGES=""
COPY ha_autoapps.sh /ha_autoapps.sh
RUN chmod 744 /ha_autoapps.sh && /ha_autoapps.sh "$PACKAGES" && rm /ha_autoapps.sh

################
# 4 Entrypoint #
################

ENV S6_STAGE2_HOOK=/ha_entrypoint.sh
COPY ha_entrypoint.sh /ha_entrypoint.sh
RUN chmod 777 /ha_entrypoint.sh

COPY bashio-standalone.sh /usr/local/lib/bashio-standalone.sh
RUN chmod 0755 /usr/local/lib/bashio-standalone.sh

WORKDIR /data
ENTRYPOINT [ "/usr/bin/env" ]
CMD [ "/ha_entrypoint.sh" ]

############
# 5 Labels #
############

ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION
ENV BUILD_VERSION="${BUILD_VERSION}"
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="Deepdelver (https://github.com/Deepdelver)" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Home Assistant Add-ons" \
    org.opencontainers.image.authors="Deepdelver (https://github.com/Deepdelver)" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/Deepdelver" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}

#################
# 6 Healthcheck #
#################

ENV HEALTH_PORT="8888" \
    HEALTH_URL=""
HEALTHCHECK \
    --interval=10s \
    --retries=6 \
    --start-period=120s \
    --timeout=25s \
    CMD curl -A "HealthCheck: Docker/1.0" -s -f "http://127.0.0.1:${HEALTH_PORT}${HEALTH_URL}" >/dev/null 2>&1 || exit 1
