# 易经项目 Cloudflare Worker API

这个 Worker 用 **Cloudflare Workers + D1** 替代原来的 Flask + 腾讯云数据库 API。

## 部署步骤

进入 Worker 目录：

```powershell
cd worker
```

创建 D1 数据库：

```powershell
npx wrangler d1 create yijing-project
```

命令会返回一个 `database_id`。把它复制到 `wrangler.toml`：

```toml
database_id = "这里替换成你的 D1 database_id"
```

应用数据库表结构：

```powershell
npx wrangler d1 migrations apply yijing-project --remote
```

设置生产环境密钥：

```powershell
npx wrangler secret put DEEPSEEK_API_KEY
npx wrangler secret put JWT_SECRET
```

部署 Worker：

```powershell
npx wrangler deploy
```

## 本地开发

本地开发时，在 `worker/.dev.vars` 创建密钥配置：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API Key
JWT_SECRET=dev-only-change-me
```

然后启动本地 Worker：

```powershell
npx wrangler dev
```

## 前端 API 地址

静态页面现在会优先读取 `window.YJ_BACKEND_URL`。如果没有设置，就继续使用原来的腾讯云 SCF 地址。

切换到 Cloudflare Worker 时，在主页面脚本之前加入：

```html
<script>
  window.YJ_BACKEND_URL = "https://<你的-worker>.<你的子域>.workers.dev";
</script>
```

也可以直接把页面里的默认 SCF 地址替换成 Worker 地址。

## 配置项

`wrangler.toml` 中可以调整：

```toml
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
JWT_EXPIRES_DAYS = "7"
DAILY_AI_LIMIT = "10"
CORS_ORIGINS = "http://localhost:8081,http://localhost:8787"
```

上线前建议把 `CORS_ORIGINS` 改成你的正式前端域名和必要的本地开发地址。

## 已实现接口

- `GET /api/health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/user/info`
- `POST /api/divine`
- `GET /api/history`
- `GET /api/history/:id`

这些接口保持和现有前端兼容。
