"use client";

import type { ReactNode } from "react";
import { useId, useRef, useState } from "react";
import { FilePreview } from "./FilePreview";

type DropZoneProps = { accept?: string; title: string; description?: string; actionLabel?: string; icon?: ReactNode; maxSize?: number; disabled?: boolean; selectedFile?: File | null; previewUrl?: string; error?: string; onFileSelected: (file: File) => void; onRemove?: () => void; onChange?: () => void };

function matchesAcceptedType(file: File, accept?: string) {
  if (!accept) return true;
  return accept.split(",").map((item) => item.trim()).some((item) => item === file.type || (item.endsWith("/*") && file.type.startsWith(item.slice(0, -1))) || (item.startsWith(".") && file.name.toLowerCase().endsWith(item.toLowerCase())));
}

export function DropZone({ accept, title, description, actionLabel, icon, maxSize, disabled = false, selectedFile, previewUrl, error, onFileSelected, onRemove, onChange }: DropZoneProps) {
  const inputId = useId(); const inputRef = useRef<HTMLInputElement>(null); const [dragging, setDragging] = useState(false); const [localError, setLocalError] = useState<string>(); const message = error ?? localError;
  const selectFile = (file?: File) => { if (!file || disabled) return; if (!matchesAcceptedType(file, accept)) { setLocalError("This file type is not supported."); return; } if (maxSize && file.size > maxSize) { setLocalError(`File must be ${maxSize / 1024 / 1024} MB or smaller.`); return; } setLocalError(undefined); onFileSelected(file); };
  const fileInput = <input ref={inputRef} id={inputId} className="sr-only" type="file" accept={accept} disabled={disabled} onChange={(event) => { selectFile(event.target.files?.[0]); event.currentTarget.value = ""; }} />;
  if (selectedFile) return <div>{fileInput}<FilePreview file={selectedFile} icon={icon} previewUrl={previewUrl} onRemove={onRemove} onChange={onChange ?? (() => inputRef.current?.click())} disabled={disabled} /></div>;
  return <div>{fileInput}<label htmlFor={inputId} className="dropzone" data-dragging={dragging} data-disabled={disabled} onDragEnter={(event) => { event.preventDefault(); if (!disabled) setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); selectFile(event.dataTransfer.files[0]); }}><span className="dropzone-icon" aria-hidden="true">{icon ?? "↑"}</span><span className="dropzone-title">{title}</span>{actionLabel && <span className="dropzone-action">{actionLabel}</span>}{description && <span className="dropzone-description">{description}</span>}{maxSize && <span className="dropzone-detail">Maximum file size: {maxSize / 1024 / 1024} MB</span>}{message && <span className="dropzone-error" role="alert">{message}</span>}</label></div>;
}
