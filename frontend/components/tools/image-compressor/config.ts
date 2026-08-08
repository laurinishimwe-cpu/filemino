export const IMAGE_ACCEPT_TYPES = ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp";
const configuredUploadSize = Number(process.env.NEXT_PUBLIC_MAX_IMAGE_UPLOAD_SIZE_BYTES);
export const MAX_IMAGE_UPLOAD_SIZE = Number.isSafeInteger(configuredUploadSize) && configuredUploadSize > 0
  ? configuredUploadSize
  : 100 * 1024 * 1024;
export const IMAGE_TARGET_MIN_BYTES = 1_024;
export const IMAGE_TARGET_MAX_BYTES = 50 * 1024 * 1024;
export const IMAGE_BALANCED_QUALITY_DEFAULT = 80;
export const IMAGE_SMALLEST_QUALITY_DEFAULT = 55;
export const IMAGE_TARGET_MIN_QUALITY_DEFAULT = 45;
export const IMAGE_MIN_DIMENSION_PERCENT = 1;
export const IMAGE_MAX_DIMENSION_PERCENT = 100;
