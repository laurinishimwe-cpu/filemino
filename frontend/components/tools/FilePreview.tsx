import type { ReactNode } from "react";
import { Button, Card } from "@/components/ui";
import { formatFileSize, formatFileType, type FileDetails } from "@/lib/file";

type FilePreviewProps = { file: FileDetails; icon?: ReactNode; previewUrl?: string; onRemove?: () => void; onChange?: () => void; disabled?: boolean };
export function FilePreview({ file, icon, previewUrl, onRemove, onChange, disabled }: FilePreviewProps) {
  return <Card className="file-preview">
    {previewUrl ? (
      // eslint-disable-next-line @next/next/no-img-element -- Browser object URLs cannot use the Next image optimizer.
      <img className="file-preview-thumbnail" src={previewUrl} alt="" />
    ) : <span className="file-preview-icon" aria-hidden="true">{icon}</span>}
    <div className="file-preview-details"><p className="file-preview-name" title={file.name}>{file.name}</p><p className="file-preview-meta">{formatFileType(file.type)} · {formatFileSize(file.size)}</p></div>
    <div className="file-preview-actions">{onChange && <Button variant="ghost" disabled={disabled} onClick={onChange}>Change</Button>}{onRemove && <Button variant="ghost" disabled={disabled} onClick={onRemove}>Remove</Button>}</div>
  </Card>;
}
