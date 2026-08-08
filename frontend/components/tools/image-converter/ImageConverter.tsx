"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Card, Input } from "@/components/ui";
import { DropZone, ProcessingState, RelatedTools, ResultCard, ToolErrorCard, ToolPage } from "@/components/tools";
import { FileToolIcon } from "@/components/icons/files/FileToolIcon";
import { cancelJob, createImageConversionJob, FluxFileApiError, getDownload, initializeUpload, uploadFile } from "@/lib/api/fluxfile-client";
import { pollJobUntilTerminal } from "@/lib/api/poll-job";
import { errorMessageForImageCode, toFrontendJobState, type ImageConversionOutputFormat, type JobResponse } from "@/lib/api/types";
import { imageConversionCapabilities, imageConversionTargetDetails, preliminaryImageFormat, type DetectedImageFormat } from "@/lib/image-conversion-formats";

type ViewState = "idle" | "selected" | "uploading" | "preparing" | "queued" | "processing" | "completed" | "error" | "cancelled";
const ACCEPTED_IMAGES = ".jpg,.jpeg,.png,.webp,.ico,.bmp,.tif,.tiff";

function isAbortError(error: unknown) { return error instanceof DOMException && error.name === "AbortError"; }
function messageForError(error: unknown) { return error instanceof FluxFileApiError ? errorMessageForImageCode(error.code) : "We couldn’t connect to FluxFile. Please try again."; }

export function ImageConverter() {
  const [view, setView] = useState<ViewState>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState<DetectedImageFormat | null>(null);
  const [target, setTarget] = useState<ImageConversionOutputFormat>("webp");
  const [quality, setQuality] = useState<number | null>(null);
  const [showMore, setShowMore] = useState(false);
  const [background, setBackground] = useState("#ffffff");
  const [hasAlpha, setHasAlpha] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [job, setJob] = useState<JobResponse | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const uploadController = useRef<AbortController | null>(null);
  const pollingController = useRef<AbortController | null>(null);
  const previewRef = useRef<string | null>(null);
  const mounted = useRef(true);
  const submitting = useRef(false);

  const capability = format ? imageConversionCapabilities[format] : null;
  const active = ["uploading", "preparing", "queued", "processing"].includes(view);
  const requiresBackground = hasAlpha && target === "jpeg";

  const clearPreview = useCallback(() => { if (previewRef.current) URL.revokeObjectURL(previewRef.current); previewRef.current = null; setPreviewUrl(undefined); }, []);
  const stopPolling = useCallback(() => { pollingController.current?.abort(); pollingController.current = null; }, []);
  const reset = useCallback(() => { uploadController.current?.abort(); stopPolling(); clearPreview(); submitting.current = false; setFile(null); setFormat(null); setJob(null); setProgress(0); setError(null); setView("idle"); }, [clearPreview, stopPolling]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; uploadController.current?.abort(); stopPolling(); if (previewRef.current) URL.revokeObjectURL(previewRef.current); }; }, [stopPolling]);

  const applyJob = useCallback((next: JobResponse) => {
    setJob(next); setProgress(next.progress); const nextView = toFrontendJobState(next.status);
    if (nextView === "error") setError(next.status === "expired" ? "This image result has expired. Choose another image to continue." : errorMessageForImageCode(next.error_code));
    setView(nextView); return nextView;
  }, []);
  const poll = useCallback(async (id: string) => { stopPolling(); const controller = new AbortController(); pollingController.current = controller; try { await pollJobUntilTerminal(id, { signal: controller.signal, onJob: applyJob }); } catch (caught) { if (!isAbortError(caught) && mounted.current) { setError(messageForError(caught)); setView("error"); } } finally { if (pollingController.current === controller) pollingController.current = null; } }, [applyJob, stopPolling]);

  const chooseFile = (next: File) => {
    uploadController.current?.abort(); stopPolling(); clearPreview(); submitting.current = false;
    const detected = preliminaryImageFormat(next); setFormat(detected); setTarget(detected ? imageConversionCapabilities[detected].recommended : "webp");
    const url = URL.createObjectURL(next); previewRef.current = url; setPreviewUrl(url);
    const image = new window.Image(); image.onload = () => { if (previewRef.current === url) setHasAlpha(next.type === "image/png" || next.type === "image/webp"); }; image.src = url;
    setFile(next); setJob(null); setProgress(0); setError(null); setView("selected");
  };
  const convert = async () => {
    if (!file || !capability || submitting.current) return;
    if (requiresBackground && !/^#[0-9a-f]{6}$/i.test(background)) { setError("Choose a valid background color for JPG."); return; }
    submitting.current = true; setError(null); const controller = new AbortController(); uploadController.current = controller;
    try {
      setView("uploading"); setProgress(0); const upload = await initializeUpload(file, controller.signal); await uploadFile(file, upload.upload_url, setProgress, controller.signal);
      setView("preparing"); const next = await createImageConversionJob(upload.upload_id, { output_format: target, quality_percent: quality, background_color: requiresBackground ? background : null }, controller.signal);
      if (!mounted.current) return; setFormat((next.input_metadata?.format?.toUpperCase() as DetectedImageFormat) || format); applyJob(next); void poll(next.id);
    } catch (caught) { if (!isAbortError(caught) && mounted.current) { setError(messageForError(caught)); setView("error"); } }
    finally { if (uploadController.current === controller) uploadController.current = null; submitting.current = false; }
  };
  const cancel = async () => { uploadController.current?.abort(); stopPolling(); if (job && ["queued", "probing", "processing"].includes(job.status)) { try { applyJob(await cancelJob(job.id)); } catch (caught) { setError(messageForError(caught)); setView("error"); return; } } setView("cancelled"); };
  const download = async () => { if (!job) return; try { window.location.assign((await getDownload(job.id)).download_url); } catch (caught) { setError(messageForError(caught)); setView("error"); } };

  return <ToolPage title="Image Converter" description="Convert images between popular formats." badge="Image tool" supportingInfo="PNG, JPG, WebP, ICO and more">
    {(view === "idle" || view === "error" && !file) && <DropZone accept={ACCEPTED_IMAGES} title="Choose image" actionLabel="Choose image" icon={<FileToolIcon name="image" />} description="or drag and drop · PNG, JPG, WebP, ICO, BMP, TIFF" onFileSelected={chooseFile} error={error ?? undefined} />}
    {(view === "selected" || view === "error" && file) && file && <div className="tool-selection-flow">
      <DropZone accept={ACCEPTED_IMAGES} title="Choose image" icon={<FileToolIcon name="image" />} selectedFile={file} previewUrl={previewUrl} description={format ? `Detected format: ${capability?.label ?? format}` : "Format will be verified before conversion."} onFileSelected={chooseFile} onRemove={reset} error={error ?? undefined} />
      {capability ? <Card className="tool-controls"><div className="tool-control-heading"><div><h2>Convert to</h2><p className="tool-control-description">FluxFile will verify the uploaded format before converting.</p></div></div><div className="image-format-options" role="radiogroup" aria-label="Output format">{capability.targets.map((value) => <button type="button" key={value} role="radio" aria-checked={target === value} className={`image-format-option ${target === value ? "is-selected" : ""}`} onClick={() => setTarget(value)}><strong>{imageConversionTargetDetails[value].label}</strong><span>{imageConversionTargetDetails[value].description}</span>{capability.recommended === value && <em>Recommended</em>}</button>)}</div>
        {requiresBackground && <div className="conversion-background"><p>JPG doesn’t support transparency. Choose a background color.</p><div className="tool-option-row"><Button type="button" variant={background === "#ffffff" ? "secondary" : "ghost"} onClick={() => setBackground("#ffffff")}>White</Button><Button type="button" variant={background === "#000000" ? "secondary" : "ghost"} onClick={() => setBackground("#000000")}>Black</Button><label>Custom <Input type="color" value={background} onChange={(event) => setBackground(event.target.value)} aria-label="Custom JPG background color" /></label></div></div>}
        {(target === "jpeg" || target === "webp") && <div className="tool-advanced"><Button type="button" variant="ghost" onClick={() => setShowMore((value) => !value)} aria-expanded={showMore}>More control</Button>{showMore && <label className="tool-field-label">Quality <Input type="range" min="1" max="100" value={quality ?? (target === "jpeg" ? 90 : 88)} onChange={(event) => setQuality(Number(event.target.value))} /><span>{quality ?? (target === "jpeg" ? 90 : 88)}%</span></label>}</div>}
        <div className="tool-cta"><Button onClick={() => void convert()}>Convert Image</Button></div></Card> : <ToolErrorCard title="Unsupported image" message="Choose a PNG, JPG, WebP, ICO, BMP, or TIFF image." onRetry={reset} onReset={reset} resetLabel="Choose another image" />}
      {view === "error" && <ToolErrorCard title="We couldn’t convert this image" message={error} onRetry={() => { setError(null); setView("selected"); }} onReset={reset} resetLabel="Choose another image" />}
    </div>}
    {active && <><ProcessingState title={view === "uploading" ? "Uploading image" : view === "queued" ? "Waiting to start" : view === "preparing" ? "Preparing image" : "Converting image"} progress={progress} indeterminate={view === "queued" || view === "preparing"} status={view === "processing" ? "Converting image…" : undefined} showPercentage={view === "uploading" || view === "processing"} /><div className="tool-cta"><Button variant="ghost" onClick={() => void cancel()}>Cancel</Button></div></>}
    {view === "completed" && job && <ResultCard title="Image converted" description={`${job.input_metadata?.format ?? "Image"} → ${job.output_metadata?.format ?? target.toUpperCase()}`} originalSize={job.input_metadata?.size_bytes ?? file?.size ?? 0} resultSize={job.output_metadata?.size_bytes ?? 0} originalLabel="Original" resultLabel="Converted" showReduction={false} details={<ConversionDetails job={job} />} downloadLabel={`Download ${imageConversionTargetDetails[target].label}`} processAnotherLabel="Convert another" onDownload={() => void download()} onProcessAnother={reset} />}
    {view === "cancelled" && <Card className="tool-controls"><h2 className="processing-title">Conversion cancelled</h2><p className="tool-control-description">Your image was not converted.</p><div className="tool-cta"><Button onClick={reset}>Choose another image</Button></div></Card>}
    <RelatedTools currentTool="Image Converter" />
  </ToolPage>;
}

function ConversionDetails({ job }: { job: JobResponse }) { const input = job.input_metadata; const output = job.output_metadata; const dimensionsChanged = input?.width !== output?.width || input?.height !== output?.height; return <dl className="result-detail-list">{dimensionsChanged && <div><dt>Dimensions</dt><dd>{input?.width} × {input?.height} <span aria-hidden="true">→</span> {output?.width} × {output?.height}</dd></div>}{output?.background_flattened && <div><dt>Background</dt><dd>{output.background_color === "#000000" ? "Black" : "White"}</dd></div>}{output?.source_icon_size && <div><dt>Source icon</dt><dd>{output.source_icon_size[0]} × {output.source_icon_size[1]}</dd></div>}</dl>; }
