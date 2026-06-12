# Cloudflare Deployment

This project now uses a single deployment path:

- `index.html` for the static frontend
- Cloudflare Workers for the API
- Cloudflare D1 for persistence

Legacy deployment files have been removed.

## 1. Install Worker Dependencies

```powershell
cd worker
npm install
```

## 2. Configure D1

Create the D1 database if it does not already exist:

```powershell
npx wrangler d1 create yijing-project
```

Copy the returned `database_id` into `worker/wrangler.toml`, then apply the schema:

```powershell
npx wrangler d1 migrations apply yijing-project --remote
```

## 3. Configure Secrets

Production secrets are stored in Cloudflare, not in source files:

```powershell
npx wrangler secret put DEEPSEEK_API_KEY
npx wrangler secret put JWT_SECRET
```

For local development, create `worker/.dev.vars`:

```text
DEEPSEEK_API_KEY=your-deepseek-api-key
JWT_SECRET=dev-only-change-me
```

## 4. Deploy Worker

```powershell
npx wrangler deploy
```

The configured routes in `worker/wrangler.toml` serve the API at:

```text
https://qfeng.cloud/api/*
https://www.qfeng.cloud/api/*
```

## 5. Serve Frontend

The root `index.html` is the only frontend entry file. For local checks:

```powershell
python -m http.server 8081
```

Open:

```text
http://localhost:8081
```

When opened from `localhost` or `file:`, the page uses `https://www.qfeng.cloud` as the API base. In production on `qfeng.cloud` or `www.qfeng.cloud`, API calls use the current origin.

## 6. Acceptance Checks

- `GET /api/health` returns JSON from the Worker.
- Register and log in with a test account.
- Run one divination and confirm `/api/divine` returns an AI response and decrements the quota.
- Open history and a history detail.
- Confirm browser console has no CORS or JavaScript errors.
- Confirm source scan has no legacy cloud, SQL backend, Flask, or `server/` runtime references.
