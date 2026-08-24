# FileMino

FileMino is a full-stack media-processing application for compressing and converting video and image files without making the browser wait for heavy work to finish. The product is presented in the frontend as **FluxFile**.

The core design decision is simple: an API request should create and track work, not perform FFmpeg or Pillow processing inside the request itself. A user receives an upload URL, a durable job record, meaningful progress, and a temporary download link when the work is complete.

## Why the backend is more than a file upload API

Media processing is unreliable when it is handled as one long request:

- a large upload can time out;
- encoding can block the API process;
- worker machines can have different CPU or GPU capabilities;
- object-storage credentials must never reach the browser;
- a cancelled or failed job must not leave an unclear result or exposed file path;
- image conversion needs safety checks that are different from video encoding.

FileMino separates these concerns into explicit layers so each part can be tested, replaced, and scaled independently.

```text
Next.js frontend
      |
      | 1. initialise upload
      v
FastAPI API -----------------------------------+
      |                                        |
      | 2. short-lived signed PUT URL          | status / cancellation / download URL
      v                                        |
Private Cloudflare R2 (or LocalStorage)        |
      |                                        |
      | 3. verify object + inspect privately   |
      v                                        |
FastAPI services -> Redis job record -> RQ queue
                                           |
                  +------------------------+------------------------+
                  |                         |                        |
             video-cpu                  video-gpu                image-cpu
             FFmpeg/x264                FFmpeg/NVENC             Pillow
                  |                         |                        |
                  +-------------------------+------------------------+
                                            |
                                            v
                                 private output object + metadata
                                            |
                                            v
                            temporary signed download URL for user
```

## Architecture

### Frontend

The Next.js frontend manages the user-facing flow: choosing a file, uploading directly to the storage URL, polling job status, displaying processing stages, and requesting a download only after a job is complete. It does not receive storage credentials or construct object keys.

### API and domain boundary

`backend/app/api` is intentionally thin. Routes validate request schemas and call services; they do not build FFmpeg commands, talk directly to Redis, or implement storage rules.

The main layers are:

| Layer | Responsibility |
| --- | --- |
| `schemas/` | Pydantic request and response contracts. |
| `models/` | HTTP-independent job, upload, image, and video domain concepts. |
| `services/` | Upload completion, probing, queue selection, job lifecycle, rate limits, and processing coordination. |
| `storage/` | A shared file-storage contract with local development and private Cloudflare R2 implementations. |
| `repositories/` | Durable job and upload records; Redis is used at runtime and in-memory repositories support isolated tests. |
| `queue/` | RQ queue abstraction, so services enqueue work without depending on RQ details. |
| `workers/` | Background entry points only. Workers must never run inside a request handler. |
| `encoders/` | FFmpeg CPU, optional NVIDIA NVENC, and Pillow implementations behind narrow interfaces. |

This separation keeps HTTP, storage, job state, and media tooling from becoming one tightly coupled module.

## End-to-end processing flow

### 1. Initialise an upload

`POST /api/v1/uploads` creates an opaque upload ID and a server-generated storage key. With Cloudflare R2, the response contains a short-lived presigned `PUT` URL. In local development, it uses a temporary API endpoint instead.

The browser knows the upload ID and signed URL. It does not receive permanent R2 credentials, arbitrary filesystem paths, or authority to choose a storage key.

### 2. Upload directly to private storage

The client uploads raw bytes to the returned URL. Direct-to-storage upload prevents the API from becoming a slow proxy for large files.

### 3. Validate before creating a job

`POST /api/v1/uploads/{upload_id}/complete` verifies that the object exists and is non-empty. The backend downloads it only to private scratch space for inspection:

- **Video:** `ffprobe` verifies streams and normalises duration, dimensions, codec, bitrate, and size metadata.
- **Images:** Pillow must decode the file. The probe applies EXIF orientation, checks dimensions and pixel limits, detects transparency, and rejects animated images rather than silently using the first frame.

Only a verified upload becomes a job. Client-provided storage keys and arbitrary server paths are never accepted.

### 4. Create a durable job and choose a queue

The API stores job state in Redis with a TTL and enqueues work through RQ. Users poll `GET /api/v1/jobs/{job_id}` rather than holding one request open during processing.

The normal video lifecycle is:

```text
queued -> probing -> processing -> completed
                              \-> failed
                              \-> cancelled
```

Video and image jobs have independent queues, so a busy video encoder does not prevent image work from progressing. Video jobs are classified by complexity; eligible heavy jobs can use `video-gpu` when NVIDIA NVENC is available. If GPU execution is unavailable, the policy can explicitly fall back to CPU.

### 5. Process outside the API

Workers build fixed command arguments and work inside disposable temporary directories:

- **FFmpeg CPU:** H.264 video and AAC audio with quality presets or a target-size bitrate approximation.
- **FFmpeg NVIDIA:** optional `h264_nvenc` route with independent NVENC presets.
- **Pillow image compression:** quality modes, metadata stripping, orientation correction, no upscaling, bounded quality search, and optional bounded resizing for a requested target size.
- **Image conversion:** validated format compatibility; transparent images cannot be silently converted to JPEG.

FFmpeg reports duration-based progress through `-progress pipe:1`. Worker updates are throttled before persistence, preventing Redis writes from becoming a new bottleneck.

### 6. Deliver a short-lived result

Completed jobs persist safe output metadata such as output size, dimensions, codec, duration, and reduction percentage. `GET /api/v1/jobs/{job_id}/download` returns a temporary signed `GET` URL for R2, or a development-only local endpoint.

Storage keys, filesystem paths, raw subprocess errors, and permanent credentials are not returned in public job records.

## Security and resilience decisions

- Private R2 bucket; browser access is limited to short-lived signed URLs.
- Opaque, server-owned upload IDs and object keys.
- Pydantic validation at API boundaries and decoded-content validation for images and video.
- Fixed FFmpeg/ffprobe argument lists; no `shell=True` command execution.
- File size, duration, resolution, image-pixel, concurrency, and hourly rate policies.
- Safe public errors; internal command output and private paths remain in logs only.
- Cooperative cancellation of active FFmpeg processes and RQ cancellation for queued work where supported.
- Temporary processing workspaces clean up on success, failure, cancellation, and timeout.
- TTL-based job records and configurable storage-retention windows.

An external lifecycle rule should be configured on the R2 `uploads/` and `outputs/` prefixes using the same retention policy as the application. A dedicated sweeper for objects left by abrupt machine termination is a planned operational improvement.

## Local development

### Requirements

- Python 3.11+
- Redis 7+
- FFmpeg and ffprobe on `PATH` for video processing and integration tests
- Docker is optional but convenient for Redis

```bash
cd backend
python -m pip install -e ".[dev]"
docker run --rm -p 6379:6379 redis:7-alpine
python -m app.utils.diagnostic
uvicorn app.main:app --reload
```

Health check: `GET http://127.0.0.1:8000/api/v1/health`

Run workers in separate terminals:

```bash
# Linux production-style workers
rq worker --url redis://localhost:6379/0 video-cpu
rq worker --url redis://localhost:6379/0 image-cpu

# Windows uses a SpawnWorker compatibility wrapper
rq worker -w app.workers.windows_spawn_worker.WindowsSpawnWorker --url redis://localhost:6379/0 video-cpu
rq worker -w app.workers.windows_spawn_worker.WindowsSpawnWorker --url redis://localhost:6379/0 image-cpu
```

Use `STORAGE_BACKEND=local` for development. Configure `STORAGE_BACKEND=r2` plus the required `R2_*` values for private Cloudflare R2.

## Testing

```bash
cd backend

# Unit tests without local media binaries or Redis
python -m pytest -m "not integration and not e2e"

# FFmpeg/ffprobe integration tests
python -m pytest -m integration

# End-to-end LocalStorage -> Redis -> RQ -> FFmpeg flow
# PowerShell:
$env:FILEMINO_RUN_E2E = "1"
python -m pytest -m e2e
```

The test suite covers configuration, job transitions, storage boundaries, queue selection, CPU/NVIDIA processing choices, video probing, image compression and conversion, rate limits, and local end-to-end pipeline behavior.

## Deployment shape

The deployment configuration is intentionally split by responsibility:

- **Vercel:** Next.js frontend.
- **Render:** public FastAPI API and private Redis-compatible Key Value instance.
- **Oracle VM or equivalent worker host:** independent RQ workers for `video-cpu` and `image-cpu`.
- **Cloudflare R2:** private media object storage.

Read [DEPLOYMENT.md](./DEPLOYMENT.md) before production deployment. In particular, do not use local storage on Render, keep Redis private, allowlist worker access deliberately, and keep `GPU_ENABLED=false` unless a suitable GPU worker environment is available.

## Current scope and next steps

Implemented architecture includes signed upload/download flows, local and R2 storage adapters, job records, Redis/RQ queues, CPU processing, optional NVIDIA route selection, image workflows, cancellation, progress, and safe metadata exposure.

Future improvements include:

- a dedicated storage sweeper for objects orphaned by abrupt worker termination;
- multipart/resumable uploads for very large files;
- two-pass video target sizing where exact output size matters;
- more GPU codec policies beyond the current H.264 NVENC route;
- product-level authentication and account ownership policies.

These are deliberately documented as future work rather than claimed as complete features.
