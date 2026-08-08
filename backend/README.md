# FluxFile backend

## Architecture

`app/api` owns HTTP routing only. `schemas` contains Pydantic API contracts, while `models` contains HTTP-independent domain concepts. `services` coordinate application workflows through interfaces in `encoders`, `storage`, `queue`, and `repositories`. `workers` contains future background entry points and must never run from request handlers.

`storage/local.py` is a development implementation behind `FileStorage`; Cloudflare R2 can implement the same contract later. Jobs are persisted through `JobRepository`: `RedisJobRepository` is used at runtime, while `InMemoryJobRepository` is available for isolated tests. `RedisRQQueue` implements the `JobQueue` abstraction; routes only receive `JobService`.

## Local startup

From `backend/`, create and activate a Python 3.11+ virtual environment, then install development dependencies:

```bash
python -m pip install -e ".[dev]"
docker run --rm -p 6379:6379 redis:7-alpine
uvicorn app.main:app --reload
```

The health check is available at `GET http://127.0.0.1:8000/api/v1/health`.

Before starting the API, check the non-secret local prerequisites:

```bash
python -m app.utils.diagnostic
# or, after installing the package:
fluxfile-diagnose
```

The command reports `PASS`, `WARNING`, or `FAIL` for Python, configured media binaries and versions, Redis reachability (host only), storage mode, writable scratch/storage directories, and optional NVENC detection. It never prints Redis passwords, R2 credentials, signed URLs, or application secrets.

RQ 2.10's `SpawnWorker` calls Unix-only `os.wait4`, so FluxFile uses a tiny compatibility subclass that preserves its spawn-based execution model on Windows:

```bash
rq worker -w app.workers.windows_spawn_worker.WindowsSpawnWorker --url redis://localhost:6379/0 video-cpu
```

On Linux production, use the normal RQ worker:

```bash
rq worker --url redis://localhost:6379/0 video-cpu
```

Image compression is a separate CPU queue and can be scaled independently:

```bash
# Windows
rq worker -w app.workers.windows_spawn_worker.WindowsSpawnWorker --url redis://localhost:6379/0 image-cpu

# Linux production
rq worker --url redis://localhost:6379/0 image-cpu
```

An NVIDIA-capable worker is optional and uses the same platform-specific command with `video-gpu` as its queue name. `SimpleWorker` is only appropriate for isolated tests, not production-style video processing.

## Jobs and queue processing

The production flow creates a queued job only after an upload with a server-generated storage key has completed. `GET /api/v1/jobs/{job_id}` provides stable status polling, and `DELETE /api/v1/jobs/{job_id}` marks a job cancelled. The worker progresses jobs through `queued → probing → processing → completed` and invokes the CPU encoder only for jobs whose server-owned input storage key refers to an uploaded file.

Job records are JSON documents at private Redis keys shaped as `fluxfile:jobs:{uuid}` and have `JOB_TTL_SECONDS` applied with every update. Their storage keys are data only, never API response fields. A future expiry cleanup worker can use these keys to remove corresponding temporary objects; this stage does not yet create persistent upload/output objects.

Queued RQ jobs are cancelled where RQ permits it. Running FFmpeg jobs are cooperatively cancelled by terminating the child process when the worker observes the cancellation state. Abrupt machine or process termination still requires a future storage sweeper for orphaned workspaces and objects; normal success, encoder failures, cancellation, and timeout clean temporary intermediate files through `TemporaryDirectory`.

`POST /api/v1/videos/jobs` remains available only as a hidden, deprecated development/testing endpoint. It accepts no storage key and cannot reference arbitrary client paths or objects; production clients must use the upload flow below.

## CPU compression

`FFmpegCPUEncoder` implements `VideoEncoder`; workers and `CompressionService` depend on that abstraction rather than FFmpeg command details. The encoder uses fixed argument lists, emits MP4 with H.264 video and AAC audio, and has centrally defined presets for `best_quality`, `balanced`, and `smallest_size`.

When no target size is supplied, presets use CRF. When `target_size_bytes` is supplied, the encoder derives an approximate total bitrate from file duration, reserves audio bitrate, and validates that a positive video bitrate remains. This is a single-pass approximation; exact byte-level sizing and two-pass encoding remain future work.

FFmpeg emits `-progress pipe:1 -nostats`. The encoder parses `out_time_us`/`out_time_ms` and reports duration-based progress, while the worker persists it no more frequently than `PROGRESS_PERSIST_INTERVAL_SECONDS`. On success the worker probes the MP4 result and stores output size, duration, codec, resolution, bitrate, and actual size-reduction percentage in the job record.

## Optional NVIDIA encoding and queue routing

Jobs are routed by `ProcessingSelectionService` from their existing complexity classification. `CPU_QUEUE_NAME` and `GPU_QUEUE_NAME` default to `video-cpu` and `video-gpu`. With `GPU_ENABLED=false`, or when `h264_nvenc` is not in `GPU_AVAILABLE_ENCODERS`, jobs remain on CPU. `GPU_MIN_COMPLEXITY` determines the first class eligible for GPU routing (normally `heavy`).

At the GPU worker startup point, FluxFile runs the fixed command `ffmpeg -hide_banner -encoders` and only permits NVENC execution if `h264_nvenc` is reported. FFmpeg command construction remains in `FFmpegNvidiaEncoder`; the worker only chooses the encoder and orchestrates the job. The current compatible output remains MP4/H.264/AAC. `hevc_nvenc` and `av1_nvenc` are detected for future policy use but are not selected yet.

NVENC presets are separate from CPU x264 presets: NVENC uses `p` presets and CQ values, not CPU CRF values. If a GPU worker cannot run and `GPU_FALLBACK_TO_CPU=true`, it explicitly hands the job to the CPU implementation; set it to `false` when GPU-only handling is a policy requirement.

`app/utils/benchmark.py` provides `BenchmarkRecord` and `append_benchmark` for JSONL benchmark records. Each record includes input characteristics, encoder and preset, elapsed seconds, relative-to-realtime speed, output bytes, and compression ratio. It intentionally makes no visual-quality claim.

## Video inspection

`POST /api/v1/videos/probe` accepts a multipart `file` upload and returns normalized video and optional audio metadata. The route delegates to `VideoProbeService`; it does not run commands itself. Uploaded bytes are written through `LocalStorage` under a generated object key, bounded by `MAX_UPLOAD_SIZE_BYTES`, inspected using a fixed ffprobe argument list, and deleted in a `finally` block after both success and failure.

ffprobe output is internal-only JSON. Invalid JSON, execution failures, and files without a detected video stream receive safe application errors; raw stderr, commands, and filesystem paths are not returned to clients.

## Image compression

Image Compressor uses Pillow through `app/encoders/image/ImageEncoder`; routes and services do not depend on Pillow directly. The first implementation accepts only decoded JPEG, PNG, and WebP files. Names, extensions, and content types are metadata only: Pillow must successfully decode the file before it can become an image job.

`ImageProbeService` returns normalized filename, byte size, actual format, EXIF-oriented dimensions, mode, alpha support, and animation details. Animated images are rejected rather than silently processing their first frame. The service also enforces `IMAGE_MAX_PIXELS`, `IMAGE_MAX_WIDTH`, and `IMAGE_MAX_HEIGHT` while retaining Pillow's decompression-bomb protections.

The image encoder strips incidental metadata, applies EXIF orientation, never upscales, and supports `best_quality`, `balanced`, `smallest_size`, and `target_size` modes. JPEG and lossy WebP use bounded binary quality search for target sizes. If the lowest configured quality still exceeds the target, dimensions are reduced by the configured factor for a bounded number of attempts. PNG uses optimization rather than JPEG-style quality controls. A transparent image cannot be converted to JPEG; it must remain PNG/WebP or receive a safe compatibility error.

Image upload and job flow uses the same private upload records, storage keys, rate limits, Redis job repository, downloads, and temporary-storage policy as video:

1. `POST /api/v1/uploads` initializes an opaque, server-owned upload.
2. Upload to the returned URL. LocalStorage returns the existing development-only `/api/v1/uploads/{upload_id}/content` endpoint; R2 returns a signed PUT URL.
3. `POST /api/v1/images/jobs` accepts the opaque `upload_id` plus `compression_mode`, `target_size_bytes`, `output_format` (`original`, `jpeg`, `webp`), and `resize` (`keep_original`, `75_percent`, `50_percent`).
4. Poll the existing `GET /api/v1/jobs/{job_id}` endpoint and download with the existing job download flow.

`POST /api/v1/images/probe` is available for local multipart inspection. Public errors include `INVALID_IMAGE`, `UNSUPPORTED_ANIMATED_IMAGE`, `IMAGE_DIMENSIONS_EXCEEDED`, `INVALID_TARGET_SIZE`, `TARGET_SIZE_UNREACHABLE`, and `INCOMPATIBLE_IMAGE_OUTPUT`; Pillow exceptions remain internal.

## Object storage and direct uploads

Set `STORAGE_BACKEND=local` to use filesystem storage without Cloudflare credentials. Set `STORAGE_BACKEND=r2` with the `R2_*` variables from `.env.example` to use Cloudflare R2's S3-compatible API. The bucket must remain private; the backend never returns permanent R2 URLs or credentials.

`POST /api/v1/uploads` creates an opaque upload ID, a server-generated `uploads/{uuid}.mp4` key, and a short-lived upload URL. With R2, that is a presigned PUT URL and the browser uploads directly to R2. With local storage, it is a development-only FastAPI URL. `POST /api/v1/uploads/{upload_id}/complete` verifies object existence and size, downloads only to private scratch for ffprobe validation, and then creates a job from the upload ID—not from a caller-supplied storage key.

Completed R2 jobs use `GET /api/v1/jobs/{job_id}/download` to obtain a temporary signed GET URL. Local development returns a temporary local content endpoint instead. Worker downloads and output probes use `FileStorage.download_to` with disposable scratch directories, so services do not import boto3.

`FILE_RETENTION_SECONDS` controls temporary upload/job record retention. Configure the private R2 bucket's lifecycle rules for the same retention window on the `uploads/` and `outputs/` prefixes; this is the provider-side enforcement that removes objects after the download period. Local storage should be cleared by an environment scheduler using the same value until a dedicated cleanup worker is added.

## Frontend API flow

1. **Initialize upload** — `POST /api/v1/uploads`

   Request: `{ "filename": "clip.mp4", "content_type": "video/mp4" }`.
   Response: `upload_id`, server-generated `storage_key`, `upload_url`, and `expires_at`. Errors include `RATE_LIMITED` when applicable. The key is opaque metadata; the client must never construct one.

2. **Upload file** — `PUT {upload_url}`.

   With R2, upload directly to the presigned URL. With local development, `upload_url` is `PUT /api/v1/uploads/{upload_id}/content`. The browser sends the raw file body. Typical validation errors are `FILE_TOO_LARGE` and invalid request errors.

3. **Validate and create job** — `POST /api/v1/uploads/{upload_id}/complete`.

   Send optional JSON compression options: `{ "compression_mode": "balanced", "resolution": "original", "target_size_bytes": null }`. The server verifies object existence and size, downloads privately for ffprobe validation, applies policy limits, then returns `202` with the public job fields: `id`, `status`, `progress`, `stage`, `message`, and input metadata. Errors include `FILE_TOO_LARGE`, `VIDEO_TOO_LONG`, `RESOLUTION_NOT_ALLOWED`, and safe `REQUEST_FAILED` validation/probe errors.

4. **Poll job** — `GET /api/v1/jobs/{job_id}`.

   Read `status`, `progress`, `stage`, `message`, optional output metadata, `error_code`, and `safe_error_message`. Public records never expose storage keys or filesystem paths.

5. **Cancel** — `DELETE /api/v1/jobs/{job_id}`.

   Queued work is removed when RQ permits it. Active FFmpeg work observes cancellation, terminates only its own subprocess, and returns `cancelled` after scratch cleanup.

6. **Download result** — `GET /api/v1/jobs/{job_id}/download` after `status=completed`.

   Response contains a temporary `download_url` and `expires_at`. R2 URLs are short-lived signed URLs; local development returns a temporary API content URL. Calling it before completion returns a safe validation error.

7. **Process another file** — repeat steps 1–6; do not reuse an upload ID or object key.

## Tests

Run isolated unit tests with `python -m pytest -m "not integration and not e2e"`.

Run media integration tests with `python -m pytest -m integration` once FFmpeg and ffprobe are on `PATH`. These tests generate temporary synthetic video/audio fixtures with FFmpeg and do not commit binary media.

Run the LocalStorage → Redis → RQ → FFmpeg end-to-end test only after starting Redis and enabling it explicitly:

```bash
$env:FLUXFILE_RUN_E2E = "1" # PowerShell
python -m pytest -m e2e
```

It uses a uniquely named CPU queue and the Windows `SpawnWorker` compatibility wrapper, then removes its temporary Redis records and local objects.

## Configuration

Copy `.env.example` to `.env` and adjust the environment variables. `Settings` in `app/core/config.py` is the single source of configuration for application names, CORS, upload limits, job TTL, temporary storage, FFmpeg paths, and the future Redis URL. Route modules do not contain environment-specific values.

Image-specific controls are also centralized there: `IMAGE_MAX_PIXELS`, `IMAGE_MAX_WIDTH`, `IMAGE_MAX_HEIGHT`, `IMAGE_MIN_TARGET_SIZE_BYTES`, `IMAGE_MAX_TARGET_SIZE_BYTES`, `IMAGE_TARGET_SEARCH_MAX_ATTEMPTS`, `IMAGE_MIN_QUALITY`, `IMAGE_MAX_QUALITY`, `IMAGE_TARGET_RESIZE_MAX_ATTEMPTS`, `IMAGE_TARGET_RESIZE_FACTOR`, `IMAGE_TARGET_MIN_DIMENSION`, `IMAGE_QUEUE_NAME`, and the independent guest limits `GUEST_IMAGE_MAX_UPLOAD_SIZE_BYTES`, `GUEST_IMAGE_MAX_PIXELS`, `GUEST_IMAGE_MAX_JOBS_PER_HOUR`, and `GUEST_IMAGE_MAX_CONCURRENT_JOBS`.

## Planned processing architecture

Uploads will receive server-generated storage keys and retain original filenames as metadata only. A future video route will create a job through `JobService`, store the upload through `FileStorage`, and enqueue it through `JobQueue`. A worker will probe and encode through safe argument-list subprocess calls (`shell=True` is never used), update the repository, and publish the output. CPU FFmpeg and future GPU encoders will both implement `VideoEncoder`.

Two-pass target sizing, GPU codecs beyond H.264, authentication, and multipart upload-to-job orchestration remain future work.
