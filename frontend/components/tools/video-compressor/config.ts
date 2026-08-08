export const VIDEO_ACCEPT_TYPES = "video/mp4,video/quicktime,video/webm,video/x-matroska";
const configuredUploadSize = Number(process.env.NEXT_PUBLIC_MAX_VIDEO_UPLOAD_SIZE_BYTES);
export const MAX_VIDEO_UPLOAD_SIZE = Number.isSafeInteger(configuredUploadSize) && configuredUploadSize > 0
  ? configuredUploadSize
  : 500 * 1024 * 1024;
