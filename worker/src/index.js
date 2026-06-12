const DEFAULT_CORS_ORIGINS = [
  "http://localhost:8081",
  "http://localhost:8787",
  "null",
];
const QUESTION_MAX_LENGTH = 300;
const LOGIN_WINDOW_MS = 10 * 60 * 1000;
const LOGIN_MAX_FAILURES = 8;
const loginFailures = new Map();

export default {
  async fetch(request, env) {
    try {
      if (!isAllowedOrigin(request, env)) {
        return new Response(JSON.stringify({ error: "请求来源不被允许" }), {
          status: 403,
          headers: { "Content-Type": "application/json; charset=utf-8" },
        });
      }

      if (request.method === "OPTIONS") {
        return new Response(null, { status: 204, headers: corsHeaders(request, env) });
      }

      const url = new URL(request.url);
      const path = url.pathname.replace(/\/+$/, "") || "/";

      if (request.method === "GET" && path === "/api/health") {
        return handleHealth(request, env);
      }
      if (request.method === "POST" && path === "/api/auth/register") {
        return handleRegister(request, env);
      }
      if (request.method === "POST" && path === "/api/auth/login") {
        return handleLogin(request, env);
      }
      if (request.method === "GET" && path === "/api/user/info") {
        return withAuth(request, env, handleUserInfo);
      }
      if (request.method === "POST" && path === "/api/divine") {
        return withAuth(request, env, handleDivine);
      }
      if (request.method === "GET" && path === "/api/history") {
        return withAuth(request, env, handleHistory);
      }

      const detailMatch = path.match(/^\/api\/history\/(\d+)$/);
      if (request.method === "GET" && detailMatch) {
        return withAuth(request, env, (req, env, user) =>
          handleHistoryDetail(req, env, user, Number(detailMatch[1]))
        );
      }

      return json(request, env, { error: "接口不存在" }, 404);
    } catch (error) {
      console.error("Unhandled request error", error && error.stack ? error.stack : error);
      return json(request, env, { error: "服务器内部错误", detail: String(error.message || error) }, 500);
    }
  },
};

async function handleHealth(request, env) {
  const result = {
    status: "ok",
    service: "yijing-divine",
    version: env.BUILD_VERSION || "cloudflare-d1",
  };

  try {
    await env.DB.prepare("SELECT 1 AS ok").first();
    result.db = "connected";
  } catch (error) {
    result.status = "degraded";
    result.db = "error";
    result.db_error = String(error.message || error);
  }

  return json(request, env, result);
}

async function handleRegister(request, env) {
  const data = await readJson(request);
  const username = String(data.username || "").trim();
  const password = String(data.password || "");

  if (!username || !password) {
    return json(request, env, { error: "用户名和密码不能为空" }, 400);
  }
  if (username.length < 2 || username.length > 50) {
    return json(request, env, { error: "用户名长度应为 2-50 字符" }, 400);
  }
  if (password.length < 6) {
    return json(request, env, { error: "密码长度至少 6 位" }, 400);
  }

  const existing = await env.DB.prepare("SELECT id FROM users WHERE username = ?")
    .bind(username)
    .first();
  if (existing) {
    return json(request, env, { error: "用户名已存在" }, 409);
  }

  const passwordHash = await hashPassword(password);
  const inserted = await env.DB.prepare(
    "INSERT INTO users (username, password_hash) VALUES (?, ?)"
  ).bind(username, passwordHash).run();
  const userId = inserted.meta.last_row_id;
  const token = await createToken(env, userId, username);

  return json(request, env, {
    token,
    user: { id: userId, username },
  }, 201);
}

async function handleLogin(request, env) {
  const data = await readJson(request);
  const username = String(data.username || "").trim();
  const password = String(data.password || "");
  const loginKey = `${request.headers.get("CF-Connecting-IP") || "local"}:${username}`;

  if (isLoginLimited(loginKey)) {
    return json(request, env, { error: "登录尝试过于频繁，请稍后再试" }, 429);
  }

  const user = await env.DB.prepare(
    "SELECT id, username, password_hash FROM users WHERE username = ?"
  ).bind(username).first();

  if (!user || !(await verifyPassword(password, user.password_hash))) {
    recordLoginFailure(loginKey);
    return json(request, env, { error: "用户名或密码错误" }, 401);
  }

  clearLoginFailure(loginKey);
  const token = await createToken(env, user.id, user.username);
  return json(request, env, {
    token,
    user: { id: user.id, username: user.username },
  });
}

async function handleUserInfo(request, env, user) {
  const todayCount = await getDailyCount(env, user.user_id);
  const dailyLimit = getInt(env.DAILY_AI_LIMIT, 10);
  const remaining = Math.max(dailyLimit - todayCount, 0);

  return json(request, env, {
    user: {
      id: user.user_id,
      username: user.username,
    },
    daily_limit: dailyLimit,
    today_used: todayCount,
    remaining,
  });
}

async function handleDivine(request, env, user) {
  const data = await readJson(request);
  const question = String(data.question || "").trim();
  const category = normalizeCategory(data.category);
  const clientVersion = String(data.client_version || "").slice(0, 80);
  const hexagramData = data.hexagram_data || {};

  if (!question) {
    return json(request, env, { error: "请输入您的问题" }, 400);
  }
  if (question.length > QUESTION_MAX_LENGTH) {
    return json(request, env, { error: `问题最多 ${QUESTION_MAX_LENGTH} 字，请精简后再起卦` }, 400);
  }

  const dailyLimit = getInt(env.DAILY_AI_LIMIT, 10);
  const usageDate = todayChinaDate();
  const reservedCount = await reserveDailyUsage(env, user.user_id, usageDate, dailyLimit);
  if (!reservedCount) {
    return json(request, env, {
      error: `今日 AI 解读次数已用完（每日 ${dailyLimit} 次），请明天再试。`,
      remaining: 0,
    }, 403);
  }

  let aiResponse;
  try {
    const promptQuestion = category ? `【分类：${category}】${question}` : question;
    const prompts = buildPrompts(promptQuestion, hexagramData);
    aiResponse = await callDeepSeek(env, prompts.system, prompts.user);
    aiResponse = normalizeAiResponse(aiResponse);
  } catch (error) {
    await refundDailyUsage(env, user.user_id, usageDate);
    const message = String(error.message || error);
    const status = message.includes("timeout") || message.includes("超时") ? 504 : 502;
    return json(request, env, { error: `AI 服务调用失败：${message}` }, status);
  }

  const saved = await env.DB.prepare(
    "INSERT INTO divinations (user_id, question, hexagram_data, ai_response, category, client_version, created_date_cn) VALUES (?, ?, ?, ?, ?, ?, ?)"
  ).bind(
    user.user_id,
    question,
    JSON.stringify(hexagramData),
    aiResponse,
    category,
    clientVersion,
    usageDate
  ).run();

  return json(request, env, {
    ai_response: aiResponse,
    record_id: saved.meta.last_row_id,
    remaining: Math.max(dailyLimit - reservedCount, 0),
  });
}

async function handleHistory(request, env, user) {
  const url = new URL(request.url);
  const page = Math.max(getInt(url.searchParams.get("page"), 1), 1);
  const pageSize = Math.min(Math.max(getInt(url.searchParams.get("page_size"), 20), 1), 50);
  const offset = (page - 1) * pageSize;
  const category = normalizeCategory(url.searchParams.get("category"));
  const q = String(url.searchParams.get("q") || "").trim();

  const where = ["user_id = ?"];
  const binds = [user.user_id];
  if (category) {
    where.push("category = ?");
    binds.push(category);
  }
  if (q) {
    where.push("question LIKE ?");
    binds.push(`%${q.slice(0, 80)}%`);
  }
  const whereSql = where.join(" AND ");

  const totalRow = await env.DB.prepare(
    `SELECT COUNT(*) AS total FROM divinations WHERE ${whereSql}`
  ).bind(...binds).first();
  const records = await env.DB.prepare(
    `SELECT id, question, category, created_at, created_date_cn FROM divinations WHERE ${whereSql} ORDER BY created_at DESC LIMIT ? OFFSET ?`
  ).bind(...binds, pageSize, offset).all();

  return json(request, env, {
    records: records.results || [],
    total: totalRow ? totalRow.total : 0,
    page,
    page_size: pageSize,
  });
}

async function handleHistoryDetail(request, env, user, id) {
  const row = await env.DB.prepare(
    "SELECT id, question, hexagram_data, ai_response, category, client_version, created_date_cn, created_at " +
      "FROM divinations WHERE id = ? AND user_id = ?"
  ).bind(id, user.user_id).first();

  if (!row) {
    return json(request, env, { error: "记录不存在" }, 404);
  }

  return json(request, env, {
    ...row,
    hexagram_data: safeJsonParse(row.hexagram_data, {}),
  });
}

async function withAuth(request, env, handler) {
  const authHeader = request.headers.get("Authorization") || "";
  if (!authHeader.startsWith("Bearer ")) {
    return json(request, env, { error: "缺少认证令牌" }, 401);
  }

  const payload = await verifyToken(env, authHeader.slice(7));
  if (!payload) {
    return json(request, env, { error: "认证令牌无效或已过期" }, 401);
  }

  return handler(request, env, payload);
}


function normalizeCategory(value) {
  const category = String(value || "").trim();
  const allowed = new Set(["事业", "感情", "财运", "学业", "健康", "其他"]);
  return allowed.has(category) ? category : "";
}

async function reserveDailyUsage(env, userId, usageDate, dailyLimit) {
  const result = await env.DB.prepare(
    "INSERT INTO daily_usage (user_id, usage_date, count) VALUES (?, ?, 1) " +
      "ON CONFLICT(user_id, usage_date) DO UPDATE SET count = count + 1 WHERE count < ?"
  ).bind(userId, usageDate, dailyLimit).run();
  if (!result.meta || result.meta.changes === 0) {
    return 0;
  }
  const row = await env.DB.prepare(
    "SELECT count FROM daily_usage WHERE user_id = ? AND usage_date = ?"
  ).bind(userId, usageDate).first();
  return row ? Number(row.count) : 0;
}

async function refundDailyUsage(env, userId, usageDate) {
  await env.DB.prepare(
    "UPDATE daily_usage SET count = MAX(count - 1, 0) WHERE user_id = ? AND usage_date = ?"
  ).bind(userId, usageDate).run();
}

function isLoginLimited(key) {
  const entry = loginFailures.get(key);
  if (!entry) return false;
  if (Date.now() - entry.firstAt > LOGIN_WINDOW_MS) {
    loginFailures.delete(key);
    return false;
  }
  return entry.count >= LOGIN_MAX_FAILURES;
}

function recordLoginFailure(key) {
  const now = Date.now();
  const entry = loginFailures.get(key);
  if (!entry || now - entry.firstAt > LOGIN_WINDOW_MS) {
    loginFailures.set(key, { count: 1, firstAt: now });
    return;
  }
  entry.count += 1;
}

function clearLoginFailure(key) {
  loginFailures.delete(key);
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return {};
  }
}

function json(request, env, body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders(request, env),
    },
  });
}

function isAllowedOrigin(request, env) {
  const requestOrigin = request.headers.get("Origin") || "";
  if (!requestOrigin) {
    return true;
  }
  const configured = String(env.CORS_ORIGINS || "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
  const origins = configured.length ? configured : DEFAULT_CORS_ORIGINS;
  return origins.includes("*") || origins.includes(requestOrigin);
}

function corsHeaders(request, env) {
  const requestOrigin = request.headers.get("Origin") || "";
  const configured = String(env.CORS_ORIGINS || "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
  const origins = configured.length ? configured : DEFAULT_CORS_ORIGINS;
  const allowOrigin = origins.includes("*")
    ? "*"
    : origins.includes(requestOrigin)
      ? requestOrigin
      : origins[0];

  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Authorization,Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

async function hashPassword(password) {
  const iterations = 20000;
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"]
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    key,
    256
  );
  return `pbkdf2_sha256$${iterations}$${base64url(salt)}$${base64url(new Uint8Array(bits))}`;
}

async function verifyPassword(password, encoded) {
  const parts = String(encoded || "").split("$");
  if (parts.length !== 4 || parts[0] !== "pbkdf2_sha256") {
    return false;
  }
  const iterations = Number(parts[1]);
  const salt = fromBase64url(parts[2]);
  const expected = fromBase64url(parts[3]);
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"]
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    key,
    expected.length * 8
  );
  return timingSafeEqual(new Uint8Array(bits), expected);
}

async function createToken(env, userId, username) {
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    user_id: userId,
    username,
    iat: now,
    exp: now + getInt(env.JWT_EXPIRES_DAYS, 7) * 86400,
  };
  const header = { alg: "HS256", typ: "JWT" };
  const body = `${base64urlJson(header)}.${base64urlJson(payload)}`;
  const signature = await hmac(env.JWT_SECRET, body);
  return `${body}.${signature}`;
}

async function verifyToken(env, token) {
  const parts = String(token || "").split(".");
  if (parts.length !== 3) {
    return null;
  }

  const body = `${parts[0]}.${parts[1]}`;
  const expected = await hmac(env.JWT_SECRET, body);
  if (!timingSafeEqual(fromBase64url(parts[2]), fromBase64url(expected))) {
    return null;
  }

  const payload = safeJsonParse(new TextDecoder().decode(fromBase64url(parts[1])), null);
  if (!payload || !payload.exp || payload.exp < Math.floor(Date.now() / 1000)) {
    return null;
  }
  return payload;
}

async function hmac(secret, body) {
  if (!secret) {
    throw new Error("JWT_SECRET 未配置");
  }
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  return base64url(new Uint8Array(signature));
}

async function getDailyCount(env, userId, usageDate = todayChinaDate()) {
  const row = await env.DB.prepare(
    "SELECT count FROM daily_usage WHERE user_id = ? AND usage_date = ?"
  ).bind(userId, usageDate).first();
  return row ? Number(row.count) : 0;
}

async function callDeepSeek(env, systemPrompt, userPrompt) {
  if (!env.DEEPSEEK_API_KEY) {
    throw new Error("DEEPSEEK_API_KEY 未配置");
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort("timeout"), 45000);
  const baseUrl = env.DEEPSEEK_BASE_URL || "https://api.deepseek.com";
  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${env.DEEPSEEK_API_KEY}`,
    },
    body: JSON.stringify({
      model: env.DEEPSEEK_MODEL || "deepseek-v4-flash",
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
      temperature: 0.7,
      max_tokens: 700,
      thinking: { type: "disabled" },
    }),
    signal: controller.signal,
  }).finally(() => clearTimeout(timeout));

  if (!response.ok) {
    throw new Error(`DeepSeek API 错误 ${response.status}: ${await response.text()}`);
  }

  const data = await response.json();
  return data?.choices?.[0]?.message?.content || "";
}

function buildPrompts(question, hd) {
  const ben = hd.benGua || {};
  const bian = hd.bianGua || {};
  const gz = hd.ganzhi || {};
  const solar = hd.solar || {};
  const movingYao = Number(hd.movingYao || 1);
  const moving = Array.isArray(ben.yaoci) ? ben.yaoci[movingYao - 1] || {} : {};
  const minuteText =
    solar.minute === undefined || solar.minute === null || solar.minute === ""
      ? ""
      : `${solar.minute}分`;

  const system = [
    "你是一位精通周易和梅花易数的解读者。",
    "请严格按顺序输出四段：决策摘要、卦象依据、动爻变化、时势补充。",
    "每段标题使用中文标题加冒号，不要使用 Markdown 标记。",
    "决策摘要段必须只包含四行：当前态势：、关键阻力：、建议动作：、留意项：。",
    "留意项只写一个温和提醒，不要把风险提示写成与前三项平级的结论。",
    "卦象依据说明本卦如何对应问题，动爻变化说明动爻和变卦方向，时势补充说明五行时机。",
    "先给可执行建议，再解释卦理。不要编造不存在的卦辞爻辞。",
    "整体 320-520 字，短句优先，语言自然克制。",
  ].join("");

  const user = [
    `用户问题：${question}`,
    `起卦时间：${solar.year || ""}年${solar.month || ""}月${solar.day || ""}日${solar.hour || ""}时${minuteText}`,
    `四柱：${formatGanzhi(gz.year)}年 ${formatGanzhi(gz.month)}月 ${formatGanzhi(gz.day)}日 ${formatGanzhi(gz.hour)}时`,
    `本卦：第${ben.id || ""}卦 ${ben.full_name || ""}（${ben.jijing || ""}）`,
    `卦辞：${ben.gua_ci || ""}`,
    `卦辞译文：${ben.gua_ci_translation || ""}`,
    `大象：${ben.xiang_ci || ""}`,
    `大象译文：${ben.xiang_ci_translation || ""}`,
    `动爻：第${movingYao}爻 ${moving.text || ""}`,
    `动爻译文：${moving.translation || ""}`,
    `变卦：第${bian.id || ""}卦 ${bian.full_name || ""}`,
    `变卦卦辞：${bian.gua_ci || ""}`,
    `变卦译文：${bian.gua_ci_translation || ""}`,
    "请综合以上信息回答。",
  ].join("\n");

  return { system, user };
}

function normalizeAiResponse(text) {
  return String(text || "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .map((line) => line.trim()
      .replace(/^#{1,6}\s*(.+?)\s*$/, "$1:")
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/__(.*?)__/g, "$1")
      .replace(/^\s*[-*+]\s+/, "")
      .replace(/^\s*\d+[.)]\s+/, ""))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function formatGanzhi(value) {
  if (!value) {
    return "";
  }
  return `${value.gan || ""}${value.zhi || ""}`;
}

function todayChinaDate() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const map = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${map.year}-${map.month}-${map.day}`;
}

function base64urlJson(value) {
  return base64url(new TextEncoder().encode(JSON.stringify(value)));
}

function base64url(bytes) {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function fromBase64url(value) {
  const base64 = String(value).replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a[i] ^ b[i];
  }
  return diff === 0;
}

function safeJsonParse(value, fallback) {
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function getInt(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}
