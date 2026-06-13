import assert from "node:assert/strict";
import test from "node:test";
import worker from "../src/index.js";

class MockD1 {
  constructor() {
    this.users = [];
    this.divinations = [];
    this.dailyUsage = new Map();
    this.nextUserId = 1;
    this.nextDivinationId = 1;
  }

  prepare(sql) {
    return new Statement(this, sql);
  }
}

class Statement {
  constructor(db, sql) {
    this.db = db;
    this.sql = sql;
    this.params = [];
  }

  bind(...params) {
    this.params = params;
    return this;
  }

  async first() {
    const sql = this.sql;
    const p = this.params;
    if (sql.includes("SELECT 1 AS ok")) return { ok: 1 };
    if (sql.includes("SELECT id FROM users WHERE username")) {
      return this.db.users.find((u) => u.username === p[0]) || null;
    }
    if (sql.includes("SELECT id, username, password_hash FROM users")) {
      return this.db.users.find((u) => u.username === p[0]) || null;
    }
    if (sql.includes("SELECT count FROM daily_usage")) {
      const key = `${p[0]}:${p[1]}`;
      return this.db.dailyUsage.has(key) ? { count: this.db.dailyUsage.get(key) } : null;
    }
    if (sql.includes("SELECT COUNT(*) AS total FROM divinations")) {
      return { total: filterDivinations(this.db.divinations, p, sql).length };
    }
    if (sql.includes("FROM divinations WHERE id = ? AND user_id = ?")) {
      return this.db.divinations.find((r) => r.id === p[0] && r.user_id === p[1]) || null;
    }
    return null;
  }

  async all() {
    const sql = this.sql;
    const p = this.params;
    if (sql.includes("FROM divinations WHERE")) {
      const limit = p[p.length - 2];
      const offset = p[p.length - 1];
      return { results: filterDivinations(this.db.divinations, p.slice(0, -2), sql).slice(offset, offset + limit) };
    }
    return { results: [] };
  }

  async run() {
    const sql = this.sql;
    const p = this.params;
    if (sql.includes("INSERT INTO users")) {
      const user = { id: this.db.nextUserId++, username: p[0], password_hash: p[1] };
      this.db.users.push(user);
      return { meta: { last_row_id: user.id, changes: 1 } };
    }
    if (sql.includes("INSERT INTO daily_usage")) {
      const key = `${p[0]}:${p[1]}`;
      const current = this.db.dailyUsage.get(key) || 0;
      if (current >= p[2]) return { meta: { changes: 0 } };
      this.db.dailyUsage.set(key, current + 1);
      return { meta: { changes: 1 } };
    }
    if (sql.includes("UPDATE daily_usage SET count")) {
      const key = `${p[0]}:${p[1]}`;
      this.db.dailyUsage.set(key, Math.max((this.db.dailyUsage.get(key) || 0) - 1, 0));
      return { meta: { changes: 1 } };
    }
    if (sql.includes("INSERT INTO divinations")) {
      const record = {
        id: this.db.nextDivinationId++,
        user_id: p[0],
        question: p[1],
        hexagram_data: p[2],
        ai_response: p[3],
        category: p[4],
        client_version: p[5],
        created_date_cn: p[6],
        created_at: "2026-06-12 12:00:00",
      };
      this.db.divinations.unshift(record);
      return { meta: { last_row_id: record.id, changes: 1 } };
    }
    return { meta: { changes: 0 } };
  }
}

function filterDivinations(records, params, sql) {
  let index = 0;
  let result = records.filter((r) => r.user_id === params[index++]);
  if (sql.includes("category = ?")) {
    const category = params[index++];
    result = result.filter((r) => r.category === category);
  }
  if (sql.includes("question LIKE ?")) {
    const q = String(params[index++] || "").replaceAll("%", "");
    result = result.filter((r) => r.question.includes(q));
  }
  return result;
}

function env(overrides = {}) {
  return {
    DB: new MockD1(),
    JWT_SECRET: "test-secret",
    DAILY_AI_LIMIT: "2",
    CORS_ORIGINS: "https://www.qfeng.cloud,http://localhost:8081,null",
    ...overrides,
  };
}

async function json(res) {
  return res.json();
}

async function register(testEnv, username = "tester") {
  const res = await worker.fetch(new Request("https://www.qfeng.cloud/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: "https://www.qfeng.cloud" },
    body: JSON.stringify({ username, password: "secret123" }),
  }), testEnv);
  assert.equal(res.status, 201);
  return json(res);
}

test("health reports ok when D1 responds", async () => {
  const testEnv = env();
  const res = await worker.fetch(new Request("https://www.qfeng.cloud/api/health", {
    headers: { Origin: "https://www.qfeng.cloud" },
  }), testEnv);
  assert.equal(res.status, 200);
  assert.equal((await json(res)).status, "ok");
});

test("protected routes reject missing tokens", async () => {
  const testEnv = env();
  const res = await worker.fetch(new Request("https://www.qfeng.cloud/api/history", {
    headers: { Origin: "https://www.qfeng.cloud" },
  }), testEnv);
  assert.equal(res.status, 401);
});

test("requests from disallowed origins are rejected", async () => {
  const testEnv = env();
  const res = await worker.fetch(new Request("https://www.qfeng.cloud/api/health", {
    headers: { Origin: "https://example.com" },
  }), testEnv);
  assert.equal(res.status, 403);
});

test("file origin is allowed for local static checks", async () => {
  const testEnv = env();
  const res = await worker.fetch(new Request("https://www.qfeng.cloud/api/health", {
    headers: { Origin: "null" },
  }), testEnv);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("Access-Control-Allow-Origin"), "null");
});

test("login succeeds after registration and clears failure limit", async () => {
  const testEnv = env();
  await register(testEnv);
  const res = await worker.fetch(new Request("https://www.qfeng.cloud/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: "https://www.qfeng.cloud" },
    body: JSON.stringify({ username: "tester", password: "secret123" }),
  }), testEnv);
  assert.equal(res.status, 200);
  assert.ok((await json(res)).token);
});

test("divine saves category metadata and history can filter it", async () => {
  const originalFetch = globalThis.fetch;
  let modelRequest;
  globalThis.fetch = async (_url, init) => {
    modelRequest = JSON.parse(init.body);
    return new Response(JSON.stringify({
      choices: [{ message: { content: "决策摘要：\n当前态势：稳\n关键阻力：急\n建议动作：缓\n留意项：节奏" } }],
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  try {
    const testEnv = env({ DEEPSEEK_API_KEY: "sk-test" });
    const { token } = await register(testEnv);
    const divineRes = await worker.fetch(new Request("https://www.qfeng.cloud/api/divine", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, Origin: "https://www.qfeng.cloud" },
      body: JSON.stringify({ question: "是否推进新项目", category: "事业", hexagram_data: { movingYao: 1 } }),
    }), testEnv);
    assert.equal(divineRes.status, 200);

    const historyRes = await worker.fetch(new Request("https://www.qfeng.cloud/api/history?category=事业&q=项目", {
      headers: { Authorization: `Bearer ${token}`, Origin: "https://www.qfeng.cloud" },
    }), testEnv);
    assert.equal(historyRes.status, 200);
    const history = await json(historyRes);
    assert.equal(history.total, 1);
    assert.equal(history.records[0].category, "事业");
    assert.equal(history.records[0].question, "是否推进新项目");
    assert.match(modelRequest.messages.at(-1).content, /【分类：事业】是否推进新项目/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("daily AI limit is enforced before calling the model", async () => {
  let modelCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    modelCalls += 1;
    return new Response(JSON.stringify({
      choices: [{ message: { content: "决策摘要：\n当前态势：稳\n关键阻力：急\n建议动作：缓\n留意项：节奏" } }],
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  try {
    const testEnv = env({ DEEPSEEK_API_KEY: "sk-test", DAILY_AI_LIMIT: "1" });
    const { token } = await register(testEnv);
    const body = JSON.stringify({ question: "是否推进", category: "事业", hexagram_data: { movingYao: 1 } });
    const first = await worker.fetch(new Request("https://www.qfeng.cloud/api/divine", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, Origin: "https://www.qfeng.cloud" },
      body,
    }), testEnv);
    const second = await worker.fetch(new Request("https://www.qfeng.cloud/api/divine", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, Origin: "https://www.qfeng.cloud" },
      body,
    }), testEnv);
    assert.equal(first.status, 200);
    assert.equal(second.status, 403);
    assert.equal(modelCalls, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("objective questions are rejected before model call or quota usage", async () => {
  let modelCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    modelCalls += 1;
    return new Response(JSON.stringify({
      choices: [{ message: { content: "不应调用" } }],
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  try {
    const testEnv = env({ DEEPSEEK_API_KEY: "sk-test", DAILY_AI_LIMIT: "1" });
    const { token } = await register(testEnv);
    const res = await worker.fetch(new Request("https://www.qfeng.cloud/api/divine", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, Origin: "https://www.qfeng.cloud" },
      body: JSON.stringify({ question: "明天天气如何", category: "其他", hexagram_data: { movingYao: 1 } }),
    }), testEnv);
    assert.equal(res.status, 422);
    const body = await json(res);
    assert.equal(body.code, "direct");
    assert.equal(modelCalls, 0);

    const infoRes = await worker.fetch(new Request("https://www.qfeng.cloud/api/user/info", {
      headers: { Authorization: `Bearer ${token}`, Origin: "https://www.qfeng.cloud" },
    }), testEnv);
    const info = await json(infoRes);
    assert.equal(info.today_used, 0);
    assert.equal(testEnv.DB.divinations.length, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("casual and noisy inputs ask for clarification", async () => {
  const testEnv = env({ DEEPSEEK_API_KEY: "sk-test" });
  const { token } = await register(testEnv);
  for (const question of ["？？？？", "哈哈哈哈", "asdfgh"]) {
    const res = await worker.fetch(new Request("https://www.qfeng.cloud/api/divine", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, Origin: "https://www.qfeng.cloud" },
      body: JSON.stringify({ question, category: "其他", hexagram_data: { movingYao: 1 } }),
    }), testEnv);
    assert.equal(res.status, 422);
    assert.equal((await json(res)).code, "clarify");
  }
});

test("blocked questions are rejected before divination", async () => {
  let modelCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    modelCalls += 1;
    return new Response(JSON.stringify({
      choices: [{ message: { content: "不应调用" } }],
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  try {
    const testEnv = env({ DEEPSEEK_API_KEY: "sk-test" });
    const { token } = await register(testEnv);
    const res = await worker.fetch(new Request("https://www.qfeng.cloud/api/divine", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, Origin: "https://www.qfeng.cloud" },
      body: JSON.stringify({ question: "如何诈骗别人", category: "其他", hexagram_data: { movingYao: 1 } }),
    }), testEnv);
    assert.equal(res.status, 422);
    assert.equal((await json(res)).code, "blocked");
    assert.equal(modelCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("objective words with action choice can still enter divination", async () => {
  let modelCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    modelCalls += 1;
    return new Response(JSON.stringify({
      choices: [{ message: { content: "决策摘要：\n当前态势：可观\n关键阻力：天气\n建议动作：备选\n留意项：节奏" } }],
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  try {
    const testEnv = env({ DEEPSEEK_API_KEY: "sk-test" });
    const { token } = await register(testEnv);
    const res = await worker.fetch(new Request("https://www.qfeng.cloud/api/divine", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, Origin: "https://www.qfeng.cloud" },
      body: JSON.stringify({ question: "明天下雨我是否还该去谈合作", category: "事业", hexagram_data: { movingYao: 1 } }),
    }), testEnv);
    assert.equal(res.status, 200);
    assert.equal(modelCalls, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
