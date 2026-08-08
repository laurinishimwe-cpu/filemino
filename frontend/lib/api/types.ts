export type CompressionMode = "best_quality" | "balanced" | "smallest_size";
export type ResolutionOption = "original" | "1080" | "720" | "480";
export type ImageCompressionMode = CompressionMode | "target_size";
export type ImageOutputFormat = "auto" | "original" | "jpeg" | "webp";
export type ImageResizeOption = "keep_original" | "75_percent" | "50_percent" | "percentage" | "custom";
export type JobTool = "video_compression" | "image_compression" | "image_conversion";
export type ImageConversionOutputFormat = "png" | "jpeg" | "webp" | "ico";
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

export type ImageCompressionOptions = {
  compression_mode: ImageCompressionMode;
  target_size_bytes: number | null;
  output_format: ImageOutputFormat;
  resize: ImageResizeOption;
  quality_percent: number | null;
  resize_percent: number | null;
  custom_width: number | null;
  custom_height: number | null;
  lock_aspect_ratio: boolean;
  allow_resize_for_target: boolean;
};
export type ImageConversionOptions = {
  output_format: ImageConversionOutputFormat;
  quality_percent: number | null;
  background_color: string | null;
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
  format?: string | null;
  mode?: string | null;
  has_alpha?: boolean;
  animated?: boolean;
  frame_count?: number | null;
  target_size_bytes?: number | null;
  target_achieved?: boolean | null;
  resized_for_target?: boolean | null;
  source_format?: string | null;
  output_format?: string | null;
  original_width?: number | null;
  original_height?: number | null;
  alpha_preserved?: boolean | null;
  background_flattened?: boolean | null;
  background_color?: string | null;
  source_icon_size?: [number, number] | null;
};

export type TargetFailureContext = {
  requested_target_bytes: number;
  smallest_achieved_bytes: number;
  smallest_width: number;
  smallest_height: number;
  output_format: string;
  quality_floor_was_explicit: boolean;
  resize_allowed: boolean;
};

export type JobResponse = {
  id: string;
  status: BackendJobStatus;
  created_at: string;
  updated_at: string;
  original_filename: string;
  tool: JobTool;
  compression_mode: CompressionMode | ImageCompressionMode;
  target_size_bytes: number | null;
  resolution: ResolutionOption;
  image_output_format: ImageOutputFormat | null;
  image_resize: ImageResizeOption | null;
  image_quality_percent: number | null;
  image_resize_percent: number | null;
  image_custom_width: number | null;
  image_custom_height: number | null;
  image_lock_aspect_ratio: boolean;
  image_allow_resize_for_target: boolean;
  image_conversion_output_format: ImageConversionOutputFormat | null;
  image_conversion_quality_percent: number | null;
  image_conversion_background_color: string | null;
  progress: number;
  stage: string;
  message: string;
  input_metadata: JobMetadata | null;
  output_metadata: JobMetadata | null;
  target_failure_context: TargetFailureContext | null;
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

export function kilobytesToBytes(value: string | number): number | null {
  const kilobytes = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(kilobytes) || kilobytes <= 0) return null;
  return Math.round(kilobytes * 1024);
}

export function isImageTargetSizeValid(value: number | null, minBytes: number, maxBytes: number) {
  return value !== null && value >= minBytes && value <= maxBytes;
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

export function errorMessageForImageCode(code: string | null | undefined): string {
  const messages: Record<string, string> = {
    FILE_TOO_LARGE: "This image is larger than the allowed upload size.",
    INVALID_IMAGE: "Choose a valid JPG, PNG, or WebP image.",
    UNSUPPORTED_ANIMATED_IMAGE: "Animated images are not supported yet.",
    IMAGE_DIMENSIONS_EXCEEDED: "This image is larger than the allowed dimensions.",
    INVALID_TARGET_SIZE: "Choose a target size within the supported range.",
    TARGET_SIZE_UNREACHABLE: "Try allowing more compression, reducing dimensions, or using Auto/WebP.",
    target_size_unreachable: "Try allowing more compression, reducing dimensions, or using Auto/WebP.",
    INCOMPATIBLE_IMAGE_OUTPUT: "JPG cannot preserve transparent areas. Choose WebP or keep the original format.",
    UNSUPPORTED_IMAGE_FORMAT: "This image format is not supported for conversion.",
    UNSUPPORTED_CONVERSION: "That conversion is not available for this image format.",
    RATE_LIMITED: "You have reached the image processing limit. Please try again later.",
    TOO_MANY_ACTIVE_JOBS: "You already have too many images being processed.",
    REQUEST_FAILED: "We could not process that image. Please try another file.",
    image_processing_failed: "We couldn’t compress this image. Please try another file.",
  };
  return code ? messages[code] ?? "Something went wrong while processing this image. Please try again." : "Something went wrong while processing this image. Please try again.";
}
