import { Button, Card } from "@/components/ui";
import { formatFileSize, formatFileType, type FileDetails } from "@/lib/file";

type FilePreviewProps = { file: FileDetails; onRemove?: () => void; onChange?: () => void; disabled?: boolean };
export function FilePreview({ file, onRemove, onChange, disabled }: FilePreviewProps) {
  return <Card className="file-preview"><div className="file-preview-details"><p className="file-preview-name" title={file.name}>{file.name}</p><p className="file-preview-meta">{formatFileType(file.type)} · {formatFileSize(file.size)}</p></div><div className="flex shrink-0 gap-2">{onChange && <Button variant="ghost" disabled={disabled} onClick={onChange}>Change</Button>}{onRemove && <Button variant="ghost" disabled={disabled} onClick={onRemove}>Remove</Button>}</div></Card>;
}
