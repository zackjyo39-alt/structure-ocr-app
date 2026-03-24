# Paperclip local runner

This directory wraps the current Paperclip setup into reusable scripts.

## Current deployment mode

This instance is **not** using `docker-compose`.

It runs as:

- `paperclipai` CLI installed into `./runtime`
- embedded PostgreSQL under `./.paperclip-home`
- loopback-only web server on `127.0.0.1:3100`

## Scripts

- `./scripts/paperclip-start.sh`
- `./scripts/paperclip-stop.sh`
- `./scripts/paperclip-status.sh`
- `./scripts/paperclip-sync-config.mjs`
- `./scripts/paperclip-rewrite-paths.mjs`

## Migration to another machine

1. Copy this project directory, especially `./scripts` and `./.paperclip-home`.
2. Install Node.js 20+ on the target machine.
3. Run `./scripts/paperclip-start.sh`.

If `./runtime` is missing on the target machine, the start script will install `paperclipai@2026.318.0` automatically.

If the same `.paperclip-home` directory moves between host mode and Docker mode, `paperclip-sync-config.mjs` rewrites only path and deployment fields. It preserves the rest of your config.

If the project root itself changes, local agent/workspace records inside the embedded database may still reference the old absolute path. Repair them with:

```bash
PAPERCLIP_HOME="$(pwd)/.paperclip-home" \
PAPERCLIP_INSTANCE_ID=demo \
node ./scripts/paperclip-rewrite-paths.mjs <old-root> <new-root>
```

This is especially relevant for local adapters such as Codex, Cursor, Claude, Gemini, and OpenCode because they store absolute `cwd` and `instructionsFilePath` values.

You can also automate the rewrite during startup:

- Host mode: set `PAPERCLIP_REWRITE_FROM_ROOT=/previous/root` before `./scripts/paperclip-start.sh`
- Docker mode: set `PAPERCLIP_REWRITE_FROM_ROOT=/previous/root` in `.env`, or let Compose pass the current host `${PWD}` and rewrite to `/workspace/paperclip-demo`

## Docker Compose mode

Files:

- `./docker-compose.yml`
- `./docker/Dockerfile`
- `./docker/entrypoint.sh`
- `./.env.compose.example`

Secure default:

- container binds to `0.0.0.0:3100`
- host publishes only `127.0.0.1:${PAPERCLIP_SERVER_PORT}`
- deployment mode defaults to `authenticated/private`
- project workspace is mounted at the fixed in-container path `/workspace/paperclip-demo`
- Codex home is persisted at `./.codex-home`

Typical usage:

1. `cp .env.compose.example .env`
2. `docker compose up -d --build`

For a VPS, set `PAPERCLIP_PUBLIC_URL` in `.env` to your real external URL or reverse-proxy URL before first start.

## Paths

- Config: `./.paperclip-home/config.json`
- Secrets env: `./.paperclip-home/.env`
- Local secrets key: `./.paperclip-home/instances/demo/secrets/master.key`
- Launcher log: `./.paperclip-home/instances/demo/logs/launcher.log`

## Notes

- The instance stays local-only by default.
- `paperclip-start.sh` disables auto-opening a browser.
- Keep `./.paperclip-home/.env` and `./.paperclip-home/instances/demo/secrets/master.key` private.
