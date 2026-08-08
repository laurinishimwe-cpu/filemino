export type CompressionMode = "best_quality" | "balanced" | "smallest_size";
export type ResolutionOption = "original" | "1080" | "720" | "480";
export type BackendJobStatus = "queued" | "probing" | "processing" | "completed" | "failed" | "cancelled" | "expired";

export type UploadInitializeResponse = {
  upload_id: string;
  storage_key: string;
  upload_url: string;
  expires_at: string;
};

export type CompressionOptions = {
  compression_mode: CompressionMode;
  resolution: ResolutionOption;
  target_size_bytes: number | null;
};

export type VideoStreamMetadata = {
  codec: string | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  pixel_format: string | null;
  bitrate: number | null;
};

export type JobMetadata = {
  size_bytes?: number;
  duration_seconds?: number | null;
  width?: number | null;
  height?: number | null;
  complexity?: string | null;
  video?: VideoStreamMetadata;
  size_reduction_percent?: number | null;
};

export type JobResponse = {
  id: string;
  status: BackendJobStatus;
  created_at: string;
  updated_at: string;
  original_filename: string;
  compression_mode: CompressionMode;
  target_size_bytes: number | null;
  resolution: ResolutionOption;
  progress: number;
  stage: string;
  message: string;
  input_metadata: JobMetadata | null;
  output_metadata: JobMetadata | null;
  error_code: string | null;
  safe_error_message: string | null;
  processing_started_at: string | null;
  completed_at: string | null;
};

export type DownloadResponse = {
  download_url: string;
  expires_at: string;
};

export type FrontendJobState = "queued" | "preparing" | "processing" | "completed" | "error" | "cancelled";

export function toFrontendJobState(status: BackendJobStatus): FrontendJobState {
  switch (status) {
    case "queued": return "queued";
    case "probing": return "preparing";
    case "processing": return "processing";
    case "completed": return "completed";
    case "cancelled": return "cancelled";
    case "failed":
    case "expired": return "error";
  }
}

export function megabytesToBytes(value: string): number | null {
  const megabytes = Number(value);
  if (!Number.isFinite(megabytes) || megabytes <= 0) return null;
  return Math.round(megabytes * 1024 * 1024);
}

export function errorMessageForCode(code: string | null | undefined): string {
  const messages: Record<string, string> = {
    FILE_TOO_LARGE: "This video is larger than the allowed upload size.",
    VIDEO_TOO_LONG: "This video is longer than the allowed duration.",
    RESOLUTION_NOT_ALLOWED: "This video resolution is not available on the free tier.",
    RATE_LIMITED: "You have reached the upload limit. Please try again later.",
    TOO_MANY_ACTIVE_JOBS: "You already have too many videos being processed.",
    REQUEST_FAILED: "We could not process that request. Please check the video and try again.",
    processing_failed: "We couldn’t compress this video. Please try another file.",
    invalid_target_size: "Choose a larger target size and try again.",
  };
  return code ? messages[code] ?? "Something went wrong. Please try again." : "Something went wrong. Please try again.";
}
