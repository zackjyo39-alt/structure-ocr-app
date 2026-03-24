FROM node:22-bookworm-slim

ARG PAPERCLIP_VERSION=2026.318.0

WORKDIR /app

RUN npm install -g "paperclipai@${PAPERCLIP_VERSION}"

COPY scripts/paperclip-sync-config.mjs /app/scripts/paperclip-sync-config.mjs
COPY scripts/paperclip-rewrite-paths.mjs /app/scripts/paperclip-rewrite-paths.mjs
COPY docker/entrypoint.sh /usr/local/bin/paperclip-entrypoint.sh

RUN chmod +x /usr/local/bin/paperclip-entrypoint.sh

ENV PAPERCLIP_HOME=/data/paperclip \
    CODEX_HOME=/data/codex-home \
    PAPERCLIP_INSTANCE_ID=demo \
    PAPERCLIP_CONFIG=/data/paperclip/config.json \
    PAPERCLIP_DEPLOYMENT_MODE=authenticated \
    PAPERCLIP_DEPLOYMENT_EXPOSURE=private \
    PAPERCLIP_CANONICAL_PROJECT_ROOT=/workspace/paperclip-demo \
    PAPERCLIP_ALLOWED_HOSTNAMES=localhost,127.0.0.1 \
    HOST=0.0.0.0 \
    PORT=3100 \
    SERVE_UI=true \
    PAPERCLIP_OPEN_ON_LISTEN=false

VOLUME ["/data/paperclip", "/data/codex-home", "/workspace/paperclip-demo"]

EXPOSE 3100

ENTRYPOINT ["/usr/local/bin/paperclip-entrypoint.sh"]
