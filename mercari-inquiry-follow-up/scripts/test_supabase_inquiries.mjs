#!/usr/bin/env node

import assert from "node:assert/strict";
import childProcess from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const inquiryScript = path.join(scriptDirectory, "supabase_inquiries.mjs");
const auditScript = path.join(scriptDirectory, "build_audit_input.mjs");
const renderScript = path.join(scriptDirectory, "render_audit_report.mjs");
const temporaryRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mercari-follow-up-tests-"));

test.after(() => fs.rmSync(temporaryRoot, { recursive: true, force: true }));

function privateMode(filePath) {
  return fs.statSync(filePath).mode & 0o777;
}

function writeFixture(name, value) {
  const filePath = path.join(temporaryRoot, name);
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  return filePath;
}

function runNode(script, args, { serverUrl, env = {}, credentials = true } = {}) {
  const childEnv = {
    LANG: "C.UTF-8",
    LC_ALL: "C.UTF-8",
    ...env,
  };
  if (credentials) {
    childEnv.SUPABASE_URL = serverUrl;
    childEnv.SUPABASE_SERVICE_ROLE_KEY = "local-mock-service-key";
  }
  return new Promise((resolve) => {
    const child = childProcess.spawn(process.execPath, [script, ...args], {
      env: childEnv,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("close", (exitCode) => resolve({ exitCode, stdout, stderr }));
  });
}

async function withMockServer(responder, callback) {
  const requests = [];
  const handlerErrors = [];
  const server = http.createServer(async (request, response) => {
    let body = "";
    for await (const chunk of request) body += chunk;
    const captured = {
      method: request.method,
      url: new URL(request.url, "http://local.test"),
      headers: request.headers,
      body,
    };
    requests.push(captured);
    try {
      const result = await responder(captured, requests.length - 1);
      response.writeHead(result?.status ?? 200, { "Content-Type": "application/json" });
      response.end(result?.body === undefined ? "[]" : JSON.stringify(result.body));
    } catch (error) {
      handlerErrors.push(error);
      response.writeHead(500, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ error: String(error) }));
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const serverUrl = `http://127.0.0.1:${address.port}`;
  try {
    await callback({ requests, serverUrl });
    assert.deepEqual(handlerErrors, []);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

function canonicalRow(id, overrides = {}) {
  return {
    id,
    inquiry_date: "2026-07-18T03:00:00.000Z",
    status: "answered",
    automation_status: "drafted",
    follow_up_status: "open",
    shop_key: "shop1",
    customer_nickname: "山田",
    inquiry_type: "product_availability",
    url: `https://example.invalid/inquiries/${id}`,
    product_name_snapshot: "収納棚",
    units: 2,
    last_custom_message: "在庫はありますか？",
    message_log_raw: "customer: 在庫はありますか？\nseller: はい",
    inquiry_body: "在庫はありますか？",
    reply_strategy: "verified stock",
    draft_reply: "お問い合わせありがとうございます。",
    inquiry_skill_reply: null,
    follow_up_sent_at: null,
    order_id: null,
    mercari_product_id: "mercari-123",
    mercari_variant_name: "白",
    notes: null,
    extra: {},
    inquiry_product_links: [{
      item_code_snapshot: "SKU-123",
      product_name_snapshot: "収納棚 白",
      is_primary: true,
      product_variant_id: "11111111-1111-4111-8111-111111111111",
    }],
    ...overrides,
  };
}

test("query enforces eligibility, exact JST bounds, operational fields, and private output", async () => {
  await withMockServer(async () => ({ body: [canonicalRow(1)] }), async ({ requests, serverUrl }) => {
    const output = path.join(temporaryRoot, "query-output.json");
    const result = await runNode(inquiryScript, [
      "query", "--start", "2026-07-16", "--end", "2026-07-19", "--output", output,
    ], { serverUrl });
    assert.equal(result.exitCode, 0, result.stderr);
    assert.equal(requests.length, 1);
    const search = requests[0].url.searchParams;
    assert.equal(search.get("status"), "eq.answered");
    assert.equal(search.get("follow_up_status"), "eq.open");
    assert.equal(search.get("deleted_at"), "is.null");
    assert.equal(search.get("order"), "id.asc");
    assert.deepEqual(search.getAll("inquiry_date"), [
      "gte.2026-07-15T15:00:00.000Z",
      "lt.2026-07-19T15:00:00.000Z",
    ]);
    const saved = JSON.parse(fs.readFileSync(output, "utf8"));
    assert.equal(saved.count, 1);
    assert.equal(saved.records[0].url, "https://example.invalid/inquiries/1");
    assert.equal(saved.records[0].lastCustomerMessage, "在庫はありますか？");
    assert.equal(saved.records[0].messageLog.includes("seller"), true);
    assert.equal(saved.records[0].itemCode, "SKU-123");
    assert.equal(saved.records[0].productVariantId, "11111111-1111-4111-8111-111111111111");
    assert.equal(privateMode(output), 0o600);
  });
});

test("query uses deterministic keyset pagination", async () => {
  await withMockServer(async (request, index) => {
    if (index === 0) return { body: Array.from({ length: 200 }, (_, offset) => canonicalRow(offset + 1)) };
    assert.equal(request.url.searchParams.get("id"), "gt.200");
    return { body: [canonicalRow(201)] };
  }, async ({ requests, serverUrl }) => {
    const output = path.join(temporaryRoot, "paginated-output.json");
    const result = await runNode(inquiryScript, [
      "query", "--start", "2026-07-16", "--end", "2026-07-19", "--output", output,
    ], { serverUrl });
    assert.equal(result.exitCode, 0, result.stderr);
    assert.equal(requests.length, 2);
    assert.equal(JSON.parse(fs.readFileSync(output, "utf8")).count, 201);
  });
});

test("get returns canonical operational context and writes mode 0600", async () => {
  await withMockServer(async () => ({ body: [canonicalRow(9)] }), async ({ requests, serverUrl }) => {
    const output = path.join(temporaryRoot, "get-output.json");
    const result = await runNode(inquiryScript, ["get", "--id", "9", "--output", output], { serverUrl });
    assert.equal(result.exitCode, 0, result.stderr);
    assert.equal(requests[0].url.searchParams.get("id"), "eq.9");
    assert.equal(requests[0].url.searchParams.get("deleted_at"), "is.null");
    assert.equal(JSON.parse(fs.readFileSync(output, "utf8")).draftReply, "お問い合わせありがとうございます。");
    assert.equal(privateMode(output), 0o600);
  });
});

test("database and external-send switches fail closed without making requests", async () => {
  const actionFile = writeFixture("followed-up-action.json", [{ id: 7, status: "followed_up", sendConfirmed: true }]);
  await withMockServer(async () => ({ body: [] }), async ({ requests, serverUrl }) => {
    const absent = await runNode(inquiryScript, ["batch-status", "--input", actionFile], { serverUrl });
    assert.notEqual(absent.exitCode, 0);
    assert.match(absent.stderr, /DB_WRITES_ENABLED=true is required/);

    const malformed = await runNode(inquiryScript, ["batch-status", "--input", actionFile], {
      serverUrl,
      env: { INQUIRY_FOLLOWUP_DB_WRITES_ENABLED: "yes" },
    });
    assert.notEqual(malformed.exitCode, 0);
    assert.match(malformed.stderr, /DB_WRITES_ENABLED=true is required/);

    const sendDisabled = await runNode(inquiryScript, ["batch-status", "--input", actionFile], {
      serverUrl,
      env: {
        INQUIRY_FOLLOWUP_DB_WRITES_ENABLED: "true",
        INQUIRY_EXTERNAL_SEND_ENABLED: "false",
      },
    });
    assert.notEqual(sendDisabled.exitCode, 0);
    assert.match(sendDisabled.stderr, /EXTERNAL_SEND_ENABLED=true is required/);
    assert.equal(requests.length, 0);
  });
});

test("followed_up requires visible-send confirmation proof", async () => {
  const actionFile = writeFixture("unconfirmed-action.json", [{ id: 7, status: "followed_up" }]);
  await withMockServer(async () => ({ body: [] }), async ({ requests, serverUrl }) => {
    const result = await runNode(inquiryScript, ["batch-status", "--input", actionFile], {
      serverUrl,
      env: {
        INQUIRY_FOLLOWUP_DB_WRITES_ENABLED: "true",
        INQUIRY_EXTERNAL_SEND_ENABLED: "true",
      },
    });
    assert.notEqual(result.exitCode, 0);
    assert.match(result.stderr, /sendConfirmed=true/);
    assert.equal(requests.length, 0);
  });
});

test("preflight-send requires both switches to be explicitly true", async () => {
  await withMockServer(async () => ({ body: [] }), async ({ requests, serverUrl }) => {
    const disabled = await runNode(inquiryScript, ["preflight-send"], {
      serverUrl,
      env: { INQUIRY_FOLLOWUP_DB_WRITES_ENABLED: "true" },
    });
    assert.notEqual(disabled.exitCode, 0);
    const enabled = await runNode(inquiryScript, ["preflight-send"], {
      serverUrl,
      env: {
        INQUIRY_FOLLOWUP_DB_WRITES_ENABLED: "true",
        INQUIRY_EXTERNAL_SEND_ENABLED: "true",
      },
    });
    assert.equal(enabled.exitCode, 0, enabled.stderr);
    assert.equal(requests.length, 0);
  });
});

test("confirmed followed_up update is conditional and checks the returned row", async () => {
  const actionFile = writeFixture("confirmed-action.json", [{
    id: 7,
    status: "followed_up",
    sendConfirmed: true,
    followUpDate: "2026-07-22T01:02:03Z",
  }]);
  await withMockServer(async (request) => {
    assert.equal(request.method, "PATCH");
    assert.equal(request.url.searchParams.get("id"), "eq.7");
    assert.equal(request.url.searchParams.get("status"), "eq.answered");
    assert.equal(request.url.searchParams.get("follow_up_status"), "eq.open");
    assert.equal(request.url.searchParams.get("deleted_at"), "is.null");
    assert.equal(request.headers.prefer, "return=representation");
    assert.deepEqual(JSON.parse(request.body), {
      status: "followed_up",
      follow_up_status: "followed_up",
      follow_up_sent_at: "2026-07-22T01:02:03.000Z",
    });
    return { body: [{ id: 7, status: "followed_up", follow_up_status: "followed_up", follow_up_sent_at: "2026-07-22T01:02:03Z" }] };
  }, async ({ requests, serverUrl }) => {
    const result = await runNode(inquiryScript, ["batch-status", "--input", actionFile], {
      serverUrl,
      env: {
        INQUIRY_FOLLOWUP_DB_WRITES_ENABLED: "true",
        INQUIRY_EXTERNAL_SEND_ENABLED: "true",
      },
    });
    assert.equal(result.exitCode, 0, result.stderr);
    assert.equal(requests.length, 1);
  });
});

test("conditional zero-row update is a hard failure", async () => {
  const actionFile = writeFixture("zero-row-action.json", [{ id: 8, status: "do_not_follow_up" }]);
  await withMockServer(async () => ({ body: [] }), async ({ serverUrl }) => {
    const result = await runNode(inquiryScript, ["batch-status", "--input", actionFile], {
      serverUrl,
      env: { INQUIRY_FOLLOWUP_DB_WRITES_ENABLED: "true" },
    });
    assert.notEqual(result.exitCode, 0);
    assert.match(result.stderr, /changed 0 rows/);
  });
});

test("dry-run validates locally without switches or HTTP writes", async () => {
  const actionFile = writeFixture("dry-run-action.json", [{ id: 12, status: "followed_up" }]);
  await withMockServer(async () => ({ body: [] }), async ({ requests, serverUrl }) => {
    const result = await runNode(inquiryScript, ["batch-status", "--input", actionFile, "--dry-run"], { serverUrl });
    assert.equal(result.exitCode, 0, result.stderr);
    assert.match(result.stdout, /no rows changed/);
    assert.equal(requests.length, 0);
  });
});

test("invalid IDs, statuses, and duplicate actions are rejected before HTTP", async () => {
  const invalidId = writeFixture("invalid-id.json", [{ id: "7 or true", status: "open" }]);
  const invalidStatus = writeFixture("invalid-status.json", [{ id: 7, status: "answered" }]);
  const duplicates = writeFixture("duplicates.json", [{ id: 7, status: "open" }, { id: "7", status: "open" }]);
  await withMockServer(async () => ({ body: [] }), async ({ requests, serverUrl }) => {
    for (const file of [invalidId, invalidStatus, duplicates]) {
      const result = await runNode(inquiryScript, ["batch-status", "--input", file, "--dry-run"], { serverUrl });
      assert.notEqual(result.exitCode, 0);
    }
    assert.equal(requests.length, 0);
  });
});

test("verify-status checks follow-up timestamp and writes a private report", async () => {
  const input = writeFixture("verify-input.json", [{ id: 14, status: "followed_up" }]);
  await withMockServer(async () => ({
    body: [{ id: 14, status: "followed_up", follow_up_status: "followed_up", follow_up_sent_at: "2026-07-22T01:00:00Z" }],
  }), async ({ serverUrl }) => {
    const output = path.join(temporaryRoot, "verification.json");
    const result = await runNode(inquiryScript, ["verify-status", "--input", input, "--output", output], { serverUrl });
    assert.equal(result.exitCode, 0, result.stderr);
    assert.equal(JSON.parse(fs.readFileSync(output, "utf8")).allVerified, true);
    assert.equal(privateMode(output), 0o600);
  });
});

test("audit status refresh batches 205 IDs into three requests", async () => {
  const ids = Array.from({ length: 205 }, (_, index) => index + 1);
  const snapshot = writeFixture("audit-snapshot.json", {
    records: ids.map((id) => ({ id, inquiryDate: "2026-07-18T03:00:00Z", shop: `shop${(id % 4) + 1}` })),
  });
  const idFile = writeFixture("audit-ids.json", ids);
  const overrides = writeFixture("audit-overrides.json", {
    _sets: { sentFollowedUp: ids },
    _meta: { periodStart: "2026-07-16", periodEnd: "2026-07-19", allSentMessagesVerified: true },
  });
  await withMockServer(async (request) => {
    const filter = request.url.searchParams.get("id");
    assert.match(filter, /^in\.\([0-9,]+\)$/);
    const batchIds = filter.slice(4, -1).split(",").map(Number);
    return {
      body: batchIds.map((id) => ({
        id,
        follow_up_status: "followed_up",
        status: "followed_up",
        follow_up_sent_at: "2026-07-22T01:00:00Z",
      })),
    };
  }, async ({ requests, serverUrl }) => {
    const output = path.join(temporaryRoot, "audit-input.json");
    const result = await runNode(auditScript, [snapshot, idFile, overrides, output], { serverUrl });
    assert.equal(result.exitCode, 0, result.stderr);
    assert.equal(requests.length, 3);
    assert.deepEqual(requests.map((request) => request.url.searchParams.get("order")), ["id.asc", "id.asc", "id.asc"]);
    const saved = JSON.parse(fs.readFileSync(output, "utf8"));
    assert.equal(saved.cases.length, 205);
    assert.equal(saved.allStatusesVerified, true);
    assert.equal(privateMode(output), 0o600);
  });
});

test("environment files are ignored unless explicitly supplied", async () => {
  await withMockServer(async () => ({ body: [] }), async ({ requests, serverUrl }) => {
    const envFile = path.join(temporaryRoot, "explicit.env");
    fs.writeFileSync(envFile, `SUPABASE_URL=${serverUrl}\nSUPABASE_SERVICE_ROLE_KEY=local-file-key\n`, "utf8");
    const ignoredOutput = path.join(temporaryRoot, "ignored-env-output.json");
    const ignored = await runNode(inquiryScript, [
      "query", "--start", "2026-07-16", "--end", "2026-07-19", "--output", ignoredOutput,
    ], {
      credentials: false,
      env: { SUPABASE_ENV_FILE: envFile },
    });
    assert.notEqual(ignored.exitCode, 0);
    assert.match(ignored.stderr, /Missing SUPABASE_URL/);

    const explicitOutput = path.join(temporaryRoot, "explicit-env-output.json");
    const explicit = await runNode(inquiryScript, [
      "query", "--start", "2026-07-16", "--end", "2026-07-19", "--output", explicitOutput,
      "--env-file", envFile,
    ], { credentials: false });
    assert.equal(explicit.exitCode, 0, explicit.stderr);
    assert.equal(requests.length, 1);
  });
});

test("rendered audit report uses Supabase terminology and mode 0600", async () => {
  const input = writeFixture("render-input.json", {
    periodStart: "2026-07-16",
    periodEnd: "2026-07-19",
    allSentMessagesVerified: true,
    allStatusesVerified: true,
    jobWindowsClosed: true,
    cases: [{
      inquiryDate: "2026-07-18",
      shop: "shop1",
      chronologyGate: "passed",
      action: "sent",
      disclaimerVerified: true,
      statusVerified: true,
      note: "Verified without private details.",
    }],
  });
  const output = path.join(temporaryRoot, "audit-report.md");
  const result = await runNode(renderScript, [input, output], { credentials: false });
  assert.equal(result.exitCode, 0, result.stderr);
  const report = fs.readFileSync(output, "utf8");
  assert.match(report, /Supabase statuses verified: 1/);
  assert.match(report, /Every terminal Supabase state verified: yes/);
  assert.equal(privateMode(output), 0o600);
});
