# FluxFile backend

## Architecture

`app/api` owns HTTP routing only. `schemas` contains Pydantic API contracts, while `models` contains HTTP-independent domain concepts. `services` coordinate application workflows through interfaces in `encoders`, `storage`, `queue`, and `repositories`. `workers` contains future background entry points and must never run from request handlers.

`storage/local.py` is a development implementation behind `FileStorage`; Cloudflare R2 can implement the same contract later. `InMemoryJobRepository` is development-only and can be replaced by Redis or a database. The queue and encoder packages are deliberate interfaces/placeholders until RQ and FFmpeg are introduced.

## Local startup

From `backend/`, create and activate a Python 3.11+ virtual environment, then install development dependencies:

```bash
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The health check is available at `GET http://127.0.0.1:8000/api/v1/health`.

## Configuration

Copy `.env.example` to `.env` and adjust the environment variables. `Settings` in `app/core/config.py` is the single source of configuration for application names, CORS, upload limits, job TTL, temporary storage, FFmpeg paths, and the future Redis URL. Route modules do not contain environment-specific values.

## Planned processing architecture

Uploads will receive server-generated storage keys and retain original filenames as metadata only. A future video route will create a job through `JobService`, store the upload through `FileStorage`, and enqueue it through `JobQueue`. A worker will probe and encode through safe argument-list subprocess calls (`shell=True` is never used), update the repository, and publish the output. CPU FFmpeg and future GPU encoders will both implement `VideoEncoder`.

No FFmpeg, Redis/RQ, cloud storage, authentication, or actual compression is included in this stage.
