# Deploying FileMino on Render

`render.yaml` creates two services in Frankfurt: a public FastAPI API and a private Redis-compatible Render Key Value instance. The Next.js frontend deploys to Vercel. The Oracle VM will run the RQ workers for the `video-cpu` and `image-cpu` queues.

## Before the first deploy

1. Push this repository to GitHub and create a Render Blueprint from `render.yaml`.
2. Supply the API service's requested R2 values: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, and `R2_ENDPOINT`.
3. Keep the R2 bucket private. Add lifecycle rules for the `uploads/` and `outputs/` prefixes using the same window as `FILE_RETENTION_SECONDS`.
4. Deploy `frontend/` to Vercel. Set `NEXT_PUBLIC_API_BASE_URL` to the API's public URL plus `/api/v1`, and set `FILEMINO_SITE_URL` to the Vercel URL or your custom frontend domain.
5. Set the API's `CORS_ORIGINS` to a JSON list containing the Vercel URL or your custom frontend domain, then redeploy the API.

## Custom domains

After adding custom domains, use the public Vercel domain for `FILEMINO_SITE_URL` and `CORS_ORIGINS`, and the public API domain for `NEXT_PUBLIC_API_BASE_URL`. The API URL is embedded in the Next.js client bundle, so redeploy Vercel after changing it.

## Operations

- Do not use `STORAGE_BACKEND=local` in production: Render's local filesystem is ephemeral and is not shared by web and worker services.
- The Oracle VM should run separate RQ workers for `video-cpu` and `image-cpu`, and both workers need the same Redis, R2, and rate-limit configuration as the API.
- Render Key Value is intentionally private (`ipAllowList: []`) until the Oracle VM is ready. To let Oracle consume queues, enable external access in Render and allowlist the VM's stable public IP; do not allow all IPs.
- GPU processing is not configured. Keep `GPU_ENABLED=false` unless you move GPU work to a suitable platform.
