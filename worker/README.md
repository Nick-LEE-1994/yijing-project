# Yijing Cloudflare Worker API

This Worker provides the API for the static `index.html` frontend using Cloudflare Workers and D1.

## Commands

```powershell
npm install
npm run dev
npm run deploy
npm run d1:migrate
```

## D1 Setup

Create the database if needed:

```powershell
npx wrangler d1 create yijing-project
```

Copy the returned `database_id` into `wrangler.toml`, then apply migrations:

```powershell
npx wrangler d1 migrations apply yijing-project --remote
```

## Secrets

Set production secrets in Cloudflare:

```powershell
npx wrangler secret put DEEPSEEK_API_KEY
npx wrangler secret put JWT_SECRET
```

For local development, create `worker/.dev.vars`:

```text
DEEPSEEK_API_KEY=your-deepseek-api-key
JWT_SECRET=dev-only-change-me
```

## API Routes

- `GET /api/health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/user/info`
- `POST /api/divine`
- `GET /api/history`
- `GET /api/history/:id`

These routes are compatible with the frontend calls in the root `index.html`.
