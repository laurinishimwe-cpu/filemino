import type { CompressionOptions, DownloadResponse, ImageCompressionOptions, ImageConversionOptions, JobResponse, UploadInitializeResponse } from "./types";

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

export class FluxFileApiError extends Error {
  constructor(message: string, public readonly code: string | null, public readonly status: number) {
    super(message);
    this.name = "FluxFileApiError";
  }
}

type ApiErrorPayload = { detail?: unknown; code?: unknown };

function apiUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}

function resolveServerUrl(url: string) {
  if (/^https?:\/\//i.test(url)) return url;
  return new URL(url, new URL(apiBaseUrl).origin).toString();
}

async function responseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let payload: ApiErrorPayload | null = null;
    try { payload = await response.json() as ApiErrorPayload; } catch { /* Safe fallback below. */ }
    const detail = typeof payload?.detail === "string" ? payload.detail : "The request could not be completed.";
    const code = typeof payload?.code === "string" ? payload.code : null;
    throw new FluxFileApiError(detail, code, response.status);
  }
  return response.json() as Promise<T>;
}

function xhrError(request: XMLHttpRequest) {
  let payload: ApiErrorPayload | null = null;
  try { payload = JSON.parse(request.responseText) as ApiErrorPayload; } catch { /* Safe fallback below. */ }
  const detail = typeof payload?.detail === "string" ? payload.detail : "Upload failed.";
  const code = typeof payload?.code === "string" ? payload.code : null;
  return new FluxFileApiError(detail, code, request.status || 0);
}

export async function initializeUpload(file: File, signal?: AbortSignal) {
  const response = await fetch(apiUrl("/uploads"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, content_type: file.type || null }),
    signal,
  });
  return responseJson<UploadInitializeResponse>(response);
}

export function uploadFile(file: File, uploadUrl: string, onProgress: (percent: number) => void, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    const abort = () => request.abort();
    signal?.addEventListener("abort", abort, { once: true });
    request.open("PUT", resolveServerUrl(uploadUrl));
    if (file.type) request.setRequestHeader("Content-Type", file.type);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.min(100, Math.round(event.loaded / event.total * 100)));
    };
    request.onerror = () => { signal?.removeEventListener("abort", abort); reject(xhrError(request)); };
    request.onabort = () => { signal?.removeEventListener("abort", abort); reject(new DOMException("Upload aborted.", "AbortError")); };
    request.onload = () => {
      signal?.removeEventListener("abort", abort);
      if (request.status >= 200 && request.status < 300) resolve();
      else reject(xhrError(request));
    };
    request.send(file);
  });
}

export async function completeUpload(uploadId: string, options: CompressionOptions, signal?: AbortSignal) {
  const response = await fetch(apiUrl(`/uploads/${encodeURIComponent(uploadId)}/complete`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
    signal,
  });
  return responseJson<JobResponse>(response);
}

export async function createImageCompressionJob(uploadId: string, options: ImageCompressionOptions, signal?: AbortSignal) {
  const response = await fetch(apiUrl("/images/jobs"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId, ...options }),
    signal,
  });
  return responseJson<JobResponse>(response);
}

export async function createImageConversionJob(uploadId: string, options: ImageConversionOptions, signal?: AbortSignal) {
  const response = await fetch(apiUrl("/images/conversion-jobs"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId, ...options }),
    signal,
  });
  return responseJson<JobResponse>(response);
}

export async function getJob(jobId: string, signal?: AbortSignal) {
  return responseJson<JobResponse>(await fetch(apiUrl(`/jobs/${encodeURIComponent(jobId)}`), { signal }));
}

export async function cancelJob(jobId: string, signal?: AbortSignal) {
  return responseJson<JobResponse>(await fetch(apiUrl(`/jobs/${encodeURIComponent(jobId)}`), { method: "DELETE", signal }));
}

export async function getDownload(jobId: string, signal?: AbortSignal) {
  const response = await responseJson<DownloadResponse>(await fetch(apiUrl(`/jobs/${encodeURIComponent(jobId)}/download`), { signal }));
  return { ...response, download_url: resolveServerUrl(response.download_url) };
}
