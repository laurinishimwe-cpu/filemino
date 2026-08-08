"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AutoScrollRegion, Button, Card, Input, Select } from "@/components/ui";
import { DropZone, ProcessingState, ResultCard, ToolPage, ToolRail } from "@/components/tools";
import { FileToolIcon } from "@/components/icons/files/FileToolIcon";
import { relatedFluxFileTools } from "@/lib/tools";
import {
  FluxFileApiError,
  cancelJob,
  completeUpload,
  getDownload,
  getJob,
  initializeUpload,
  uploadFile,
} from "@/lib/api/fluxfile-client";
import {
  errorMessageForCode,
  megabytesToBytes,
  toFrontendJobState,
  type CompressionMode,
  type JobResponse,
  type ResolutionOption,
} from "@/lib/api/types";
import { MAX_VIDEO_UPLOAD_SIZE, VIDEO_ACCEPT_TYPES } from "./config";

type ViewState = "idle" | "selected" | "uploading" | "preparing" | "queued" | "processing" | "completed" | "error" | "cancelled";
type TargetOption = "Auto" | "100 MB" | "50 MB" | "25 MB" | "Custom target size";

const compressionModes: { label: string; value: CompressionMode }[] = [
  { label: "Best Quality", value: "best_quality" },
  { label: "Balanced", value: "balanced" },
  { label: "Smallest Size", value: "smallest_size" },
];
const resolutions: { label: string; value: ResolutionOption }[] = [
  { label: "Keep original", value: "original" },
  { label: "1080p", value: "1080" },
  { label: "720p", value: "720" },
  { label: "480p", value: "480" },
];

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function messageForError(error: unknown) {
  if (error instanceof FluxFileApiError) return errorMessageForCode(error.code);
  return "We couldn’t connect to FluxFile. Please try again.";
}

export function VideoCompressor() {
  const [view, setView] = useState<ViewState>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<CompressionMode>("balanced");
  const [target, setTarget] = useState<TargetOption>("Auto");
  const [customTarget, setCustomTarget] = useState("");
  const [resolution, setResolution] = useState<ResolutionOption>("original");
  const [progress, setProgress] = useState(0);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const uploadController = useRef<AbortController | null>(null);
  const pollingController = useRef<AbortController | null>(null);
  const submitting = useRef(false);
  const mounted = useRef(true);

  const stopPolling = useCallback(() => {
    pollingController.current?.abort();
    pollingController.current = null;
  }, []);

  const reset = useCallback(() => {
    uploadController.current?.abort();
    uploadController.current = null;
    stopPolling();
    submitting.current = false;
    setFile(null);
    setJob(null);
    setProgress(0);
    setError(null);
    setView("idle");
  }, [stopPolling]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      uploadController.current?.abort();
      stopPolling();
    };
  }, [stopPolling]);

  const applyJob = useCallback((nextJob: JobResponse) => {
    setJob(nextJob);
    setProgress(nextJob.progress);
    const nextView = toFrontendJobState(nextJob.status);
    if (nextView === "error") setError(errorMessageForCode(nextJob.error_code));
    setView(nextView);
    return nextView;
  }, []);

  const pollJob = useCallback(async (jobId: string) => {
    stopPolling();
    const controller = new AbortController();
    pollingController.current = controller;
    let consecutiveNetworkErrors = 0;
    while (!controller.signal.aborted && mounted.current) {
      try {
        const nextJob = await getJob(jobId, controller.signal);
        consecutiveNetworkErrors = 0;
        const nextView = applyJob(nextJob);
        if (nextView === "completed" || nextView === "error" || nextView === "cancelled") break;
      } catch (caught) {
        if (isAbortError(caught)) break;
        consecutiveNetworkErrors += 1;
        if (consecutiveNetworkErrors >= 3) {
          setError(messageForError(caught));
          setView("error");
          break;
        }
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1_000));
    }
    if (pollingController.current === controller) pollingController.current = null;
  }, [applyJob, stopPolling]);

  const chooseFile = (nextFile: File) => {
    uploadController.current?.abort();
    stopPolling();
    submitting.current = false;
    setFile(nextFile);
    setJob(null);
    setProgress(0);
    setError(null);
    setView("selected");
  };

  const selectedTargetBytes = () => {
    if (target === "Auto") return null;
    if (target === "Custom target size") return megabytesToBytes(customTarget);
    return megabytesToBytes(target.replace(" MB", ""));
  };

  const startCompression = async () => {
    if (!file || submitting.current) return;
    const targetSizeBytes = selectedTargetBytes();
    if (target === "Custom target size" && targetSizeBytes === null) {
      setError("Enter a positive target size in MB.");
      return;
    }
    submitting.current = true;
    setError(null);
    const controller = new AbortController();
    uploadController.current = controller;
    try {
      setView("uploading");
      setProgress(0);
      const upload = await initializeUpload(file, controller.signal);
      await uploadFile(file, upload.upload_url, setProgress, controller.signal);
      setView("preparing");
      const nextJob = await completeUpload(upload.upload_id, {
        compression_mode: mode,
        resolution,
        target_size_bytes: targetSizeBytes,
      }, controller.signal);
      if (!mounted.current) return;
      applyJob(nextJob);
      void pollJob(nextJob.id);
    } catch (caught) {
      if (!isAbortError(caught) && mounted.current) {
        setError(messageForError(caught));
        setView("error");
      }
    } finally {
      if (uploadController.current === controller) uploadController.current = null;
      submitting.current = false;
    }
  };

  const cancel = async () => {
    uploadController.current?.abort();
    uploadController.current = null;
    stopPolling();
    if (job && ["queued", "probing", "processing"].includes(job.status)) {
      try {
        applyJob(await cancelJob(job.id));
      } catch (caught) {
        setError(messageForError(caught));
        setView("error");
        return;
      }
    }
    setProgress(0);
    setView("cancelled");
  };

  const download = async () => {
    if (!job) return;
    try {
      const response = await getDownload(job.id);
      window.location.assign(response.download_url);
    } catch (caught) {
      setError(messageForError(caught));
      setView("error");
    }
  };

  const active = view === "uploading" || view === "preparing" || view === "queued" || view === "processing";
  const originalSize = job?.input_metadata?.size_bytes ?? file?.size ?? 0;
  const resultSize = job?.output_metadata?.size_bytes ?? 0;
  const reduction = job?.output_metadata?.size_reduction_percent ?? undefined;

  return <ToolPage title="Compress Video" description="Reduce video size while preserving excellent visual quality." badge="Video tool" supportingInfo="MP4, MOV, WEBM and MKV supported">
    {(view === "idle" || view === "error" && !file) && <><DropZone accept={VIDEO_ACCEPT_TYPES} title="Choose video" actionLabel="Choose video" icon={<FileToolIcon name="video" />} description="or drag and drop · MP4, MOV, WEBM, MKV" maxSize={MAX_VIDEO_UPLOAD_SIZE} error={error ?? undefined} onFileSelected={chooseFile} /><TrustLine /></>}
    {(view === "selected" || view === "error" && file) && file && <div className="tool-selection-flow"><DropZone accept={VIDEO_ACCEPT_TYPES} title="Choose video" icon={<FileToolIcon name="video" />} selectedFile={file} maxSize={MAX_VIDEO_UPLOAD_SIZE} error={error ?? undefined} onFileSelected={chooseFile} onRemove={reset} /><CompressionControls mode={mode} setMode={setMode} target={target} setTarget={setTarget} customTarget={customTarget} setCustomTarget={setCustomTarget} resolution={resolution} setResolution={setResolution} onCompress={startCompression} disabled={false} /><ErrorCard message={error} onRetry={() => { setError(null); setView("selected"); }} onReset={reset} /></div>}
    {active && <><ProcessingState title={processingTitle(view)} progress={progress} indeterminate={view === "preparing"} status={processingMessage(view, job)} showPercentage={view !== "preparing"} /><div className="tool-cta"><Button variant="ghost" onClick={cancel}>Cancel</Button></div></>}
    {view === "completed" && <AutoScrollRegion active><ResultCard title="Your video is ready" description="Compression completed successfully." originalSize={originalSize} resultSize={resultSize} reduction={reduction} originalLabel="Original" resultLabel="Compressed" reductionLabel="Smaller" downloadLabel="Download Video" processAnotherLabel="Choose another file" onDownload={() => void download()} onProcessAnother={reset} /></AutoScrollRegion>}
    {view === "cancelled" && <Card className="tool-controls"><h2 className="processing-title">Compression cancelled</h2><p className="tool-control-description">Your video was not compressed.</p><div className="tool-cta"><Button onClick={reset}>Choose another file</Button></div></Card>}
    <RelatedTools />
  </ToolPage>;
}

function processingTitle(view: ViewState) {
  if (view === "uploading") return "Uploading video";
  if (view === "preparing") return "Preparing video";
  if (view === "queued") return "Waiting to start";
  return "Compressing video";
}

function processingMessage(view: ViewState, job: JobResponse | null) {
  if (view === "uploading") return "Uploading your video…";
  if (view === "preparing") return "Preparing video…";
  if (view === "queued") return "Waiting to start…";
  return job?.message || "Compressing video…";
}

function TrustLine() { return <p className="tool-trust"><span>No watermark</span><span>Private</span><span>Fast</span></p>; }

type ControlsProps = { mode: CompressionMode; setMode: (value: CompressionMode) => void; target: TargetOption; setTarget: (value: TargetOption) => void; customTarget: string; setCustomTarget: (value: string) => void; resolution: ResolutionOption; setResolution: (value: ResolutionOption) => void; onCompress: () => void; disabled: boolean };
function CompressionControls({ mode, setMode, target, setTarget, customTarget, setCustomTarget, resolution, setResolution, onCompress, disabled }: ControlsProps) {
  return <Card className="tool-controls"><div className="tool-controls-heading"><div><h2 className="tool-control-label">Compression settings</h2><p className="tool-control-description">Choose your preferred output, then compress.</p></div><Button onClick={onCompress} disabled={disabled}>Compress Video</Button></div><fieldset disabled={disabled}><legend className="tool-control-label">Compression mode</legend><p className="tool-control-description">Balanced is recommended for most videos.</p><div className="tool-options" role="radiogroup" aria-label="Compression mode">{compressionModes.map((option) => <button className="tool-option" data-selected={mode === option.value} type="button" role="radio" aria-checked={mode === option.value} key={option.value} onClick={() => setMode(option.value)}>{option.label}</button>)}</div></fieldset><div><label className="tool-control-label" htmlFor="target-size">Target size</label><p className="tool-control-description">Choose a preset or set your own size.</p><Select id="target-size" className="mt-3" value={target} disabled={disabled} onChange={(event) => setTarget(event.target.value as TargetOption)}><option>Auto</option><option>100 MB</option><option>50 MB</option><option>25 MB</option><option>Custom target size</option></Select>{target === "Custom target size" && <Input className="mt-3" value={customTarget} disabled={disabled} onChange={(event) => setCustomTarget(event.target.value)} inputMode="decimal" placeholder="Enter target size in MB" aria-label="Custom target size in megabytes" />}</div><fieldset disabled={disabled}><legend className="tool-control-label">Resolution</legend><div className="tool-options" role="radiogroup" aria-label="Resolution">{resolutions.map((option) => <button className="tool-option" data-selected={resolution === option.value} type="button" role="radio" aria-checked={resolution === option.value} key={option.value} onClick={() => setResolution(option.value)}>{option.label}</button>)}</div></fieldset></Card>;
}

function ErrorCard({ message, onRetry, onReset }: { message: string | null; onRetry: () => void; onReset: () => void }) {
  if (!message) return null;
  return <Card className="tool-error" role="alert"><h2 className="tool-error-title">We couldn’t compress this video</h2><p className="tool-error-message">{message}</p><div className="tool-cta"><Button onClick={onRetry}>Try again</Button><Button variant="secondary" onClick={onReset}>Choose another file</Button></div></Card>;
}

function RelatedTools() { return <section className="related-tools" aria-labelledby="related-tools-title"><h2 className="related-tools-title" id="related-tools-title">More file tools</h2><p className="related-tools-description">More focused utilities are coming soon.</p><ToolRail tools={relatedFluxFileTools} label="Related FluxFile tools" compact /></section>; }
