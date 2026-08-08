import type { ReactNode } from "react";
import { Button, Card } from "@/components/ui";
import { formatFileSize, formatFileType, type FileDetails } from "@/lib/file";

type FilePreviewProps = { file: FileDetails; icon?: ReactNode; onRemove?: () => void; onChange?: () => void; disabled?: boolean };
export function FilePreview({ file, icon, onRemove, onChange, disabled }: FilePreviewProps) {
  return <Card className="file-preview"><span className="file-preview-icon" aria-hidden="true">{icon}</span><div className="file-preview-details"><p className="file-preview-name" title={file.name}>{file.name}</p><p className="file-preview-meta">{formatFileType(file.type)} · {formatFileSize(file.size)}</p></div><div className="file-preview-actions">{onChange && <Button variant="ghost" disabled={disabled} onClick={onChange}>Change</Button>}{onRemove && <Button variant="ghost" disabled={disabled} onClick={onRemove}>Remove</Button>}</div></Card>;
}
