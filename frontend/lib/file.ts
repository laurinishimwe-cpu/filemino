export type FileDetails = Pick<File, "name" | "size" | "type">;

export function formatFileSize(bytes: number) {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** unit).toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function formatFileType(type: string) {
  return type ? type.replace(/^\w+\//, "").toUpperCase() : "Unknown type";
}
