#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const paperclipHome = process.env.PAPERCLIP_HOME;
const instanceId = process.env.PAPERCLIP_INSTANCE_ID || "demo";
const configPath = process.env.PAPERCLIP_CONFIG;

if (!paperclipHome || !configPath) {
  console.error("PAPERCLIP_HOME and PAPERCLIP_CONFIG are required.");
  process.exit(1);
}

if (!fs.existsSync(configPath)) {
  process.exit(0);
}

const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
const instanceRoot = path.join(paperclipHome, "instances", instanceId);

const deploymentMode = process.env.PAPERCLIP_DEPLOYMENT_MODE;
const deploymentExposure = process.env.PAPERCLIP_DEPLOYMENT_EXPOSURE;
const host = process.env.HOST;
const port = Number(process.env.PORT || "");
const serveUi = process.env.SERVE_UI;
const publicUrl =
  process.env.PAPERCLIP_PUBLIC_URL ||
  process.env.PAPERCLIP_AUTH_PUBLIC_BASE_URL ||
  process.env.BETTER_AUTH_URL ||
  process.env.BETTER_AUTH_BASE_URL ||
  "";
const allowedHostnamesRaw = process.env.PAPERCLIP_ALLOWED_HOSTNAMES || "";
const allowedHostnames = allowedHostnamesRaw
  .split(",")
  .map((value) => value.trim().toLowerCase())
  .filter(Boolean);

config.$meta = {
  ...(config.$meta || {}),
  updatedAt: new Date().toISOString(),
  // paperclipai doctor only accepts: onboard | configure | doctor
  source: "configure",
};

if (config.database?.mode === "embedded-postgres") {
  config.database.embeddedPostgresDataDir = path.join(instanceRoot, "db");
  if (config.database.backup) {
    config.database.backup.dir = path.join(instanceRoot, "data", "backups");
  }
}

if (config.logging) {
  config.logging.logDir = path.join(instanceRoot, "logs");
}

if (config.storage?.provider === "local_disk" && config.storage.localDisk) {
  config.storage.localDisk.baseDir = path.join(instanceRoot, "data", "storage");
}

if (config.secrets?.provider === "local_encrypted" && config.secrets.localEncrypted) {
  config.secrets.localEncrypted.keyFilePath = path.join(instanceRoot, "secrets", "master.key");
}

if (config.server) {
  if (deploymentMode) {
    config.server.deploymentMode = deploymentMode;
  }
  if (deploymentExposure) {
    config.server.exposure = deploymentExposure;
  }
  if (host) {
    config.server.host = host;
  }
  if (Number.isFinite(port) && port > 0) {
    config.server.port = port;
  }
  if (serveUi) {
    config.server.serveUi = ["1", "true", "yes"].includes(serveUi.toLowerCase());
  }
  if (allowedHostnames.length > 0) {
    config.server.allowedHostnames = Array.from(new Set(allowedHostnames));
  } else if (config.server.deploymentMode === "local_trusted") {
    config.server.allowedHostnames = [];
  }
}

if (config.auth) {
  if (publicUrl) {
    config.auth.baseUrlMode = "explicit";
    config.auth.publicBaseUrl = publicUrl.replace(/\/+$/, "");
  } else if (config.server?.deploymentMode === "local_trusted") {
    config.auth.baseUrlMode = "auto";
    delete config.auth.publicBaseUrl;
  }
}

fs.mkdirSync(path.dirname(configPath), { recursive: true });
fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`);
