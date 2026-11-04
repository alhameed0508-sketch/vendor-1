# Railway demo deployment

One Railway service serves the React app and the FastAPI API on one URL. It runs in
demo mode: synthetic alerts and complaints, plus the **real Bitcoin payment feed** on
the Live stream page (public mempool.space transactions, scored as they arrive).

## Why Railway and not Vercel

Demo data lives in memory. Vercel runs the API as short-lived serverless copies that do
not share memory, so an alert listed by one copy can be "not found" by the next, and
status changes or decisions disappear between clicks. Vercel also cuts each live stream
off at 300 seconds. Railway runs one long-lived process, so data stays consistent for the
whole demo and the live stream can run as long as you watch it.

## Deploy

1. Railway → **New Project** → **Deploy from GitHub repo** → `alhameed0508-sketch/buildx`.
2. In the service **Settings**, set the branch to **`railway`**. Railway reads
   `railway.json`, builds `railway/Dockerfile` and checks `/health`.
3. Add the variables below under **Variables**, then redeploy.
4. **Settings → Networking → Generate Domain** to get the public URL.

Keep **one replica** and leave **App Sleeping** off: a second replica would hold different
demo data, and a sleeping service loses its data when it wakes.

## Variables

| Variable | Value | Why |
|---|---|---|
| `AUTH_ENABLED` | `true` | Required. The server refuses to start without it, because demo mode without auth makes every visitor ADMIN |
| `JWT_SECRET` | 32+ random characters | Required. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DEMO_INVESTIGATOR_PASSWORD` | 12+ characters | Required. Password for the `investigator` login |
| `DEMO_SUPERVISOR_PASSWORD` | 12+ characters | Required. Password for the `supervisor` login |
| `DEMO_ADMIN_PASSWORD` | 12+ characters | Required. Password for the `admin` login |
| `ENV` | leave unset | Unset means demo mode: synthetic data, demo logins and the live Bitcoin feed |
| `LIVE_FEED_ENABLED` | `true` (optional) | The live feed is already on in demo mode; this keeps it on if `ENV` ever changes |

`REACT_APP_EXTRA_PAGES=true` is baked into the Docker build, so Fraud complaints, ROI
analytics, Compliance, Customer risk and Data import are all in the menu.

## What this image leaves out

It uses the slim `requirements.txt` the Vercel function uses, so it fits a small plan:

- No PyTorch: the GNN layer falls back to the lightweight scorer.
- No PyOD or SHAP: the anomaly tier is skipped and explanations use the built-in fallback.
- No GenAI SDKs: GenAI panels use their template fallback.

For the full model stack, use `backend/Dockerfile` with `docker-compose.yml` instead.

## Updating from the upstream repo

```bash
git fetch upstream
git checkout railway
git merge upstream/buildx-integrated
git push origin railway
```

Every redeploy or restart resets the in-memory demo data to its seed state.
