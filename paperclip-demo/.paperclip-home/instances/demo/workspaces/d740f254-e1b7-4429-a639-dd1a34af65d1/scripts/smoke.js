import { spawn } from "node:child_process";

const port = 3010;
const child = spawn("node", ["dist/server.js"], {
  env: { ...process.env, PORT: String(port) },
  stdio: "inherit"
});

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  await sleep(800);

  const health = await fetch(`http://127.0.0.1:${port}/health`);
  if (!health.ok) {
    throw new Error("health endpoint failed");
  }

  const create = await fetch(`http://127.0.0.1:${port}/api/v1/todos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: "Smoke" })
  });
  if (create.status !== 201) {
    throw new Error("create endpoint failed");
  }

  const list = await fetch(`http://127.0.0.1:${port}/api/v1/todos`);
  if (!list.ok) {
    throw new Error("list endpoint failed");
  }

  console.log("smoke passed");
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(() => {
    child.kill("SIGTERM");
  });
