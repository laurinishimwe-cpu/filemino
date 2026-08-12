"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AutoScrollRegion, Button, Card } from "@/components/ui";
import { DropZone, ProcessingState, RelatedTools, ResultCard, ToolErrorCard, ToolPage } from "@/components/tools";
import { FileToolIcon } from "@/components/icons/files/FileToolIcon";
import { cancelJob, createImageCompressionJob, FileMinoApiError, getDownload, initializeUpload, uploadFile } from "@/lib/api/filemino-client";
import { pollJobUntilTerminal } from "@/lib/api/poll-job";
import { errorMessageForImageCode, isImageTargetSizeValid, kilobytesToBytes, toFrontendJobState, type ImageCompressionMode, type ImageOutputFormat, type ImageResizeOption, type JobResponse } from "@/lib/api/types";
import { IMAGE_ACCEPT_TYPES, IMAGE_TARGET_MAX_BYTES, IMAGE_TARGET_MIN_BYTES, MAX_IMAGE_UPLOAD_SIZE } from "./config";
import { ImageCompressionControls, type TargetPreset } from "./ImageCompressionControls";
import { PopularTargetSizes } from "./PopularTargetSizes";

type ViewState = "idle" | "selected" | "uploading" | "preparing" | "queued" | "processing" | "completed" | "error" | "cancelled";
type Dimensions = { width: number; height: number } | null;

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function messageForError(error: unknown) {
  if (error instanceof FileMinoApiError) return errorMessageForImageCode(error.code);
  return "We couldn’t connect to FileMino. Please try again.";
}

type ImageCompressorProps = {
  initialTargetSizeKb?: number;
  initialOutputFormat?: ImageOutputFormat;
  initialAllowResizeForTarget?: boolean;
  title?: string;
  description?: string;
  supportingInfo?: string;
};

export function ImageCompressor({
  initialTargetSizeKb,
  initialOutputFormat = initialTargetSizeKb ? "auto" : "original",
  initialAllowResizeForTarget = true,
  title = "Compress Image",
  description = "Reduce image size while keeping it clear.",
  supportingInfo = "JPG, PNG and WebP supported",
}: ImageCompressorProps) {
  const [view, setView] = useState<ViewState>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [sourceDimensions, setSourceDimensions] = useState<Dimensions>(null);
  const [mode, setMode] = useState<ImageCompressionMode>(initialTargetSizeKb ? "target_size" : "balanced");
  const [targetPreset, setTargetPreset] = useState<TargetPreset>(() => presetForTarget(initialTargetSizeKb));
  const [customTarget, setCustomTarget] = useState(() => customTargetFor(initialTargetSizeKb));
  const [outputFormat, setOutputFormat] = useState<ImageOutputFormat>(initialOutputFormat);
  const [resize, setResize] = useState<ImageResizeOption>("keep_original");
  const [qualityPercent, setQualityPercent] = useState<number | null>(null);
  const [resizePercent, setResizePercent] = useState("75");
  const [customWidth, setCustomWidth] = useState("");
  const [customHeight, setCustomHeight] = useState("");
  const [lockAspectRatio, setLockAspectRatio] = useState(true);
  const [allowResizeForTarget, setAllowResizeForTarget] = useState(initialAllowResizeForTarget);
  const [progress, setProgress] = useState(0);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const uploadController = useRef<AbortController | null>(null);
  const pollingController = useRef<AbortController | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const submitting = useRef(false);
  const mounted = useRef(true);

  const clearPreview = useCallback(() => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = null;
    setPreviewUrl(undefined);
    setSourceDimensions(null);
  }, []);
  const stopPolling = useCallback(() => {
    pollingController.current?.abort();
    pollingController.current = null;
  }, []);
  const reset = useCallback(() => {
    uploadController.current?.abort();
    uploadController.current = null;
    stopPolling();
    clearPreview();
    submitting.current = false;
    setFile(null); setJob(null); setProgress(0); setError(null); setErrorCode(null); setView("idle");
  }, [clearPreview, stopPolling]);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; uploadController.current?.abort(); stopPolling(); if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current); };
  }, [stopPolling]);

  const applyJob = useCallback((nextJob: JobResponse) => {
    setJob(nextJob); setProgress(nextJob.progress);
    const nextView = toFrontendJobState(nextJob.status);
    if (nextView === "error") {
      const nextCode = nextJob.status === "expired" ? "EXPIRED" : nextJob.error_code;
      setErrorCode(nextCode);
      setError(nextJob.status === "expired" ? "This image result has expired. Choose another image to continue." : errorMessageForImageCode(nextCode));
    }
    setView(nextView);
    return nextView;
  }, []);

  const pollJob = useCallback(async (jobId: string) => {
    stopPolling();
    const controller = new AbortController();
    pollingController.current = controller;
    try { await pollJobUntilTerminal(jobId, { signal: controller.signal, onJob: applyJob }); }
    catch (caught) { if (!isAbortError(caught) && mounted.current) { setError(messageForError(caught)); setView("error"); } }
    finally { if (pollingController.current === controller) pollingController.current = null; }
  }, [applyJob, stopPolling]);

  const chooseFile = (nextFile: File) => {
    uploadController.current?.abort(); stopPolling(); submitting.current = false; clearPreview();
    const nextPreviewUrl = URL.createObjectURL(nextFile);
    previewUrlRef.current = nextPreviewUrl; setPreviewUrl(nextPreviewUrl);
    const image = new window.Image();
    image.onload = () => { if (previewUrlRef.current === nextPreviewUrl) setSourceDimensions({ width: image.naturalWidth, height: image.naturalHeight }); };
    image.src = nextPreviewUrl;
    setFile(nextFile); setJob(null); setProgress(0); setError(null); setErrorCode(null); setView("selected");
  };

  const startCompression = async () => {
    if (!file || submitting.current) return;
    const targetSize = targetSizeBytes(mode, targetPreset, customTarget);
    const customDimensions = { width: positiveNumber(customWidth), height: positiveNumber(customHeight) };
    const requestedResizePercent = positiveNumber(resizePercent);
    if (mode === "target_size" && !isImageTargetSizeValid(targetSize, IMAGE_TARGET_MIN_BYTES, IMAGE_TARGET_MAX_BYTES)) { setError("Enter a target size within the supported range."); return; }
    if (resize === "percentage" && (!requestedResizePercent || requestedResizePercent > 100)) { setError("Choose a resize percentage between 1 and 100."); return; }
    if (resize === "custom" && !customDimensions.width && !customDimensions.height) { setError("Enter a width or height for custom dimensions."); return; }
    submitting.current = true; setError(null); setErrorCode(null);
    const controller = new AbortController(); uploadController.current = controller;
    try {
      setView("uploading"); setProgress(0);
      const upload = await initializeUpload(file, controller.signal);
      await uploadFile(file, upload.upload_url, setProgress, controller.signal);
      setView("preparing");
      const nextJob = await createImageCompressionJob(upload.upload_id, {
        compression_mode: mode, target_size_bytes: targetSize, output_format: outputFormat, resize,
        quality_percent: qualityPercent, resize_percent: resize === "percentage" ? requestedResizePercent : null,
        custom_width: resize === "custom" ? customDimensions.width : null, custom_height: resize === "custom" ? customDimensions.height : null,
        lock_aspect_ratio: lockAspectRatio, allow_resize_for_target: allowResizeForTarget,
      }, controller.signal);
      if (!mounted.current) return;
      applyJob(nextJob); void pollJob(nextJob.id);
    } catch (caught) {
      if (!isAbortError(caught) && mounted.current) {
        setErrorCode(caught instanceof FileMinoApiError ? caught.code : null);
        setError(messageForError(caught)); setView("error");
      }
    } finally { if (uploadController.current === controller) uploadController.current = null; submitting.current = false; }
  };

  const cancel = async () => {
    uploadController.current?.abort(); uploadController.current = null; stopPolling();
    if (job && ["queued", "probing", "processing"].includes(job.status)) {
      try { applyJob(await cancelJob(job.id)); } catch (caught) { setError(messageForError(caught)); setView("error"); return; }
    }
    setProgress(0); setView("cancelled");
  };
  const download = async () => {
    if (!job) return;
    try { window.location.assign((await getDownload(job.id)).download_url); }
    catch (caught) { setError(messageForError(caught)); setView("error"); }
  };
  const adjustTargetFailure = (action: "quality" | "resize" | "auto" | "webp") => {
    if (action === "quality") setQualityPercent((current) => Math.max(1, (current ?? 45) - 10));
    if (action === "resize") setAllowResizeForTarget(true);
    if (action === "auto") setOutputFormat("auto");
    if (action === "webp") setOutputFormat("webp");
    setError(null); setErrorCode(null); setView("selected");
  };
  const active = ["uploading", "preparing", "queued", "processing"].includes(view);
  const originalSize = job?.input_metadata?.size_bytes ?? file?.size ?? 0;
  const resultSize = job?.output_metadata?.size_bytes ?? 0;
  const reduction = job?.output_metadata?.size_reduction_percent ?? undefined;
  const isPng = Boolean(file && (file.type === "image/png" || file.name.toLowerCase().endsWith(".png")));
  const isTargetUnreachable = errorCode?.toLowerCase() === "target_size_unreachable";
  const failureTarget = job?.target_failure_context?.requested_target_bytes ?? job?.target_size_bytes;
  const targetErrorTitle = failureTarget ? `We couldn’t reach ${Math.round(failureTarget / 1024)} KB` : "We couldn’t reach that target";

  return <ToolPage title={title} description={description} badge="Image tool" supportingInfo={supportingInfo}>
    {(view === "idle" || view === "error" && !file) && <DropZone accept={IMAGE_ACCEPT_TYPES} title="Choose image" actionLabel="Choose image" icon={<FileToolIcon name="image" />} description="or drag and drop · JPG, PNG, WebP" maxSize={MAX_IMAGE_UPLOAD_SIZE} error={error ?? undefined} onFileSelected={chooseFile} />}
    {(view === "selected" || view === "error" && file) && file && <div className="tool-selection-flow">
      <DropZone accept={IMAGE_ACCEPT_TYPES} title="Choose image" icon={<FileToolIcon name="image" />} selectedFile={file} previewUrl={previewUrl} maxSize={MAX_IMAGE_UPLOAD_SIZE} error={error ?? undefined} onFileSelected={chooseFile} onRemove={reset} />
      <ImageCompressionControls mode={mode} setMode={setMode} targetPreset={targetPreset} setTargetPreset={setTargetPreset} customTarget={customTarget} setCustomTarget={setCustomTarget} outputFormat={outputFormat} setOutputFormat={setOutputFormat} resize={resize} setResize={setResize} qualityPercent={qualityPercent} setQualityPercent={setQualityPercent} resizePercent={resizePercent} setResizePercent={setResizePercent} customWidth={customWidth} setCustomWidth={setCustomWidth} customHeight={customHeight} setCustomHeight={setCustomHeight} lockAspectRatio={lockAspectRatio} setLockAspectRatio={setLockAspectRatio} allowResizeForTarget={allowResizeForTarget} setAllowResizeForTarget={setAllowResizeForTarget} sourceDimensions={sourceDimensions} isPng={isPng} onCompress={startCompression} />
      <ToolErrorCard title={isTargetUnreachable ? targetErrorTitle : "We couldn’t compress this image"} message={error} onRetry={() => { setError(null); setErrorCode(null); setView("selected"); }} onReset={reset} resetLabel="Choose another image" actions={isTargetUnreachable ? <div className="tool-cta image-target-error-actions">{qualityPercent !== null && <Button variant="secondary" onClick={() => adjustTargetFailure("quality")}>Lower minimum quality</Button>}{!allowResizeForTarget && <Button variant="secondary" onClick={() => adjustTargetFailure("resize")}>Allow resizing</Button>}{outputFormat === "original" && <><Button variant="secondary" onClick={() => adjustTargetFailure("auto")}>Use Auto</Button><Button variant="secondary" onClick={() => adjustTargetFailure("webp")}>Use WebP</Button></>}</div> : undefined} />
    </div>}
    {active && <><ProcessingState title={processingTitle(view)} progress={progress} indeterminate={view === "preparing" || view === "queued"} status={processingMessage(view, job)} showPercentage={view === "uploading" || view === "processing"} /><div className="tool-cta"><Button variant="ghost" onClick={() => void cancel()}>Cancel</Button></div></>}
    {view === "completed" && <AutoScrollRegion active><ResultCard title="Image compressed" description="Compression completed successfully." originalSize={originalSize} resultSize={resultSize} reduction={reduction} originalLabel="Original" resultLabel="Compressed" reductionLabel="Smaller" details={<ImageResultDetails job={job} />} downloadLabel="Download Image" processAnotherLabel="Compress another" onDownload={() => void download()} onProcessAnother={reset} /></AutoScrollRegion>}
    {view === "cancelled" && <Card className="tool-controls"><h2 className="processing-title">Compression cancelled</h2><p className="tool-control-description">Your image was not compressed.</p><div className="tool-cta"><Button onClick={reset}>Choose another image</Button></div></Card>}
    <PopularTargetSizes />
    <RelatedTools currentTool="Image Compressor" />
  </ToolPage>;
}

function targetSizeBytes(mode: ImageCompressionMode, targetPreset: TargetPreset, customTarget: string) {
  if (mode !== "target_size") return null;
  return targetPreset === "Custom" ? kilobytesToBytes(customTarget) : kilobytesToBytes(targetPreset.replace(" KB", ""));
}
function positiveNumber(value: string) {
  const result = Number(value);
  return Number.isInteger(result) && result > 0 ? result : null;
}
function processingTitle(view: ViewState) {
  if (view === "uploading") return "Uploading image";
  if (view === "preparing") return "Preparing image";
  if (view === "queued") return "Waiting to start";
  return "Compressing image";
}
function presetForTarget(targetKb?: number): TargetPreset {
  const preset = targetKb ? `${targetKb} KB` as TargetPreset : "50 KB";
  return ["20 KB", "50 KB", "100 KB", "200 KB", "500 KB"].includes(preset) ? preset : "Custom";
}
function customTargetFor(targetKb?: number) { return presetForTarget(targetKb) === "Custom" && targetKb ? String(targetKb) : ""; }
function processingMessage(view: ViewState, job: JobResponse | null) {
  if (view === "uploading") return "Uploading your image…";
  if (view === "preparing") return "Preparing image…";
  if (view === "queued") return "Waiting to start…";
  if (job?.compression_mode === "target_size") return "Optimizing image…";
  return job?.message || "Compressing image…";
}
function ImageResultDetails({ job }: { job: JobResponse | null }) {
  const input = job?.input_metadata;
  const output = job?.output_metadata;
  const target = output?.target_size_bytes ?? job?.target_size_bytes;
  const dimensionsChanged = input?.width && input.height && output?.width && output.height && (input.width !== output.width || input.height !== output.height);
  const formatChanged = input?.format && output?.format && input.format !== output.format;
  if (!target && !dimensionsChanged && !formatChanged) return null;
  return <dl className="result-detail-list">
    {target && <div><dt>Target</dt><dd>{Math.round(target / 1024)} KB {output?.target_achieved ? "✓" : ""}</dd></div>}
    {formatChanged && <div><dt>Format</dt><dd>{input.format} <span aria-hidden="true">→</span> {output.format}</dd></div>}
    {dimensionsChanged && <div><dt>Dimensions</dt><dd>{input.width} × {input.height} <span aria-hidden="true">→</span> {output.width} × {output.height}</dd></div>}
    {output?.resized_for_target && <div><dt>Note</dt><dd>Dimensions reduced to reach target.</dd></div>}
  </dl>;
}
