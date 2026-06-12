# Public Deployment

This project uses Tencent Cloud SCF for the Flask API and Tencent Cloud COS
static website hosting for `index.html`.

## 1. Rotate Exposed Secrets

Several secrets were previously present in source files. Before publishing,
rotate them in Tencent Cloud / DeepSeek / database:

- Tencent Cloud API key pair
- DeepSeek API key
- Database password
- Production JWT secret

Do not put the new values in source files. Set them as environment variables.

## 2. Configure Environment

Copy `.env.example` to your shell profile or set the variables in the current
PowerShell session. Required variables:

```powershell
$env:TENCENT_SECRET_ID="..."
$env:TENCENT_SECRET_KEY="..."
$env:TENCENT_APP_ID="..."
$env:DEEPSEEK_API_KEY="..."
$env:DB_HOST="..."
$env:DB_PASSWORD="..."
$env:JWT_SECRET="..."
```

Keep `CORS_ORIGINS` as `http://localhost:8081` for the first backend deploy.
After COS deployment, append the COS website URL and redeploy SCF config.

## 3. Build And Deploy Backend

```powershell
python rebuild_v4.py
python deploy_scf.py
```

`deploy_scf.py` creates or updates the SCF Web Function, updates runtime
environment variables, and ensures the function URL trigger exists.

Health check:

```text
https://<scf-url>/api/health
```

`status: degraded` is acceptable only when the database status is understood
and expected during setup.

## 4. Deploy Frontend To COS

```powershell
python deploy_frontend_cos.py
```

The script creates or reuses the bucket, enables static website hosting, uploads
`index.html`, and prints the public website URL:

```text
https://<bucket>-<appid>.cos-website.ap-chengdu.myqcloud.com
```

## 5. Tighten CORS

Set `CORS_ORIGINS` to both local development and the COS website URL, then run
`python deploy_scf.py` again:

```powershell
$env:CORS_ORIGINS="http://localhost:8081,https://<bucket>-<appid>.cos-website.ap-chengdu.myqcloud.com"
python deploy_scf.py
```

## 6. Acceptance Checks

- Open the COS website URL and confirm the first screen renders.
- Register and log in with a test account.
- Run one divination while logged in and confirm `/api/divine` returns an AI
  response and decrements the quota.
- Open history and a history detail.
- Confirm browser console has no CORS or JavaScript errors.
- Confirm source scan contains no real Tencent, DeepSeek, database, or JWT
  secrets.
