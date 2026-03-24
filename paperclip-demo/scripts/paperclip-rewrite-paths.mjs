#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import postgres from "../runtime/node_modules/postgres/cjs/src/index.js";

function usage() {
  console.error(
    [
      "Usage:",
      "  node ./scripts/paperclip-rewrite-paths.mjs <old-root> <new-root>",
      "",
      "Example:",
      "  node ./scripts/paperclip-rewrite-paths.mjs \\",
      "    /Users/rock.xu/github/paperclip-demo \\",
      "    /Users/rock.xu/github/projects/ai-ml/paperclip-demo",
    ].join("\n"),
  );
}

function assertAbsoluteRoot(value, label) {
  if (!value || !path.isAbsolute(value)) {
    throw new Error(`${label} must be an absolute path`);
  }
  return path.resolve(value);
}

function replaceDeep(value, fromRoot, toRoot) {
  if (typeof value === "string") {
    return value.includes(fromRoot) ? value.split(fromRoot).join(toRoot) : value;
  }
  if (Array.isArray(value)) {
    return value.map((entry) => replaceDeep(entry, fromRoot, toRoot));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => [key, replaceDeep(entry, fromRoot, toRoot)]),
    );
  }
  return value;
}

function changed(a, b) {
  return JSON.stringify(a) !== JSON.stringify(b);
}

function normalizeJsonValue(value) {
  let current = value;
  for (let i = 0; i < 3; i += 1) {
    if (typeof current !== "string") {
      return current;
    }
    const trimmed = current.trim();
    if (!trimmed) {
      return current;
    }
    if (!trimmed.startsWith("{") && !trimmed.startsWith("[") && !trimmed.startsWith("\"")) {
      return current;
    }
    try {
      current = JSON.parse(current);
    } catch {
      return current;
    }
  }
  return current;
}

const [, , oldRootArg, newRootArg] = process.argv;

if (!oldRootArg || !newRootArg) {
  usage();
  process.exit(1);
}

const oldRoot = assertAbsoluteRoot(oldRootArg, "old-root");
const newRoot = assertAbsoluteRoot(newRootArg, "new-root");

if (!fs.existsSync(newRoot)) {
  throw new Error(`new-root does not exist: ${newRoot}`);
}

const paperclipHome = process.env.PAPERCLIP_HOME;
const instanceId = process.env.PAPERCLIP_INSTANCE_ID || "demo";
const dbPort = Number(process.env.PAPERCLIP_EMBEDDED_POSTGRES_PORT || "54329");

if (!paperclipHome) {
  throw new Error("PAPERCLIP_HOME is required");
}

const databaseUrl = `postgres://paperclip:paperclip@127.0.0.1:${dbPort}/paperclip`;
const sql = postgres(databaseUrl, { max: 1 });

const summary = {};

function identifier(value) {
  return `"${String(value).replaceAll('"', '""')}"`;
}

function updateTextValue(value, fromRoot, toRoot) {
  return typeof value === "string" && value.includes(fromRoot) ? value.split(fromRoot).join(toRoot) : value;
}

function normalizeDataType(column) {
  if (column.data_type === "character varying") {
    return "text";
  }
  return column.data_type;
}

try {
  const columns = await sql`
    select table_name, column_name, data_type
    from information_schema.columns
    where table_schema = 'public'
      and data_type in ('text', 'json', 'jsonb', 'character varying')
    order by table_name, ordinal_position
  `;

  for (const column of columns) {
    const tableName = column.table_name;
    const columnName = column.column_name;
    const dataType = normalizeDataType(column);
    const qualifiedTable = identifier(tableName);
    const qualifiedColumn = identifier(columnName);
    const rows =
      dataType === "json" || dataType === "jsonb"
        ? await sql.unsafe(
            `select ctid::text as row_tid, ${qualifiedColumn} as value
             from ${qualifiedTable}
             where ${qualifiedColumn}::text ilike $1
                or ${qualifiedColumn}::text like '\"{%'
                or ${qualifiedColumn}::text like '\"[%'`,
            [`%${oldRoot}%`],
          )
        : await sql.unsafe(
            `select ctid::text as row_tid, ${qualifiedColumn} as value
             from ${qualifiedTable}
             where ${qualifiedColumn}::text ilike $1`,
            [`%${oldRoot}%`],
          );

    if (rows.length === 0) {
      continue;
    }

    for (const row of rows) {
      const nextValue =
        dataType === "json" || dataType === "jsonb"
          ? replaceDeep(normalizeJsonValue(row.value), oldRoot, newRoot)
          : updateTextValue(row.value, oldRoot, newRoot);

      if (!changed(row.value, nextValue)) {
        continue;
      }

      if (dataType === "json" || dataType === "jsonb") {
        await sql.unsafe(
          `update ${qualifiedTable} set ${qualifiedColumn} = $1::${dataType} where ctid = $2::tid`,
          [nextValue, row.row_tid],
        );
      } else {
        await sql.unsafe(
          `update ${qualifiedTable} set ${qualifiedColumn} = $1 where ctid = $2::tid`,
          [nextValue, row.row_tid],
        );
      }

      const summaryKey = `${tableName}.${columnName}`;
      summary[summaryKey] = (summary[summaryKey] || 0) + 1;
    }
  }

  for (const column of columns) {
    const dataType = normalizeDataType(column);
    if (dataType !== "json" && dataType !== "jsonb") {
      continue;
    }

    const qualifiedTable = identifier(column.table_name);
    const qualifiedColumn = identifier(column.column_name);
    const repairedRows = await sql.unsafe(
      `with repaired as (
         update ${qualifiedTable}
         set ${qualifiedColumn} = (${qualifiedColumn} #>> '{}')::${dataType}
         where jsonb_typeof(${qualifiedColumn}::jsonb) = 'string'
           and ((${qualifiedColumn} #>> '{}') like '{%' or (${qualifiedColumn} #>> '{}') like '[%')
         returning 1
       )
       select count(*)::int as count from repaired`,
    );

    if (repairedRows[0]?.count > 0) {
      const summaryKey = `${column.table_name}.${column.column_name}.normalized`;
      summary[summaryKey] = repairedRows[0].count;
    }
  }

  console.log(JSON.stringify({ oldRoot, newRoot, paperclipHome, instanceId, dbPort, summary }, null, 2));
} finally {
  await sql.end();
}
