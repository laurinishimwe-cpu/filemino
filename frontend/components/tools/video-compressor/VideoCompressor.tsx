"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Card, Input, Select } from "@/components/ui";
import { DropZone, ProcessingState, ResultCard, ToolPage } from "@/components/tools";
import { MAX_VIDEO_UPLOAD_SIZE, MOCK_COMPRESSED_VIDEO_SIZE, MOCK_ORIGINAL_VIDEO_SIZE, VIDEO_ACCEPT_TYPES } from "./config";

type ViewState = "idle" | "selected" | "processing" | "complete" | "error";
type CompressionMode = "Best Quality" | "Balanced" | "Smallest Size";
type Resolution = "Keep original" | "1080p" | "720p" | "480p";

const compressionModes: CompressionMode[] = ["Best Quality", "Balanced", "Smallest Size"];
const resolutions: Resolution[] = ["Keep original", "1080p", "720p", "480p"];
const relatedTools = [{ name: "Image Compressor", description: "Reduce image file size." }, { name: "Remove Background", description: "Remove image backgrounds." }, { name: "Video to MP3", description: "Extract audio from video." }];

export function VideoCompressor() {
  const [view, setView] = useState<ViewState>("idle"); const [file, setFile] = useState<File | null>(null); const [mode, setMode] = useState<CompressionMode>("Balanced"); const [target, setTarget] = useState("Auto"); const [customTarget, setCustomTarget] = useState(""); const [resolution, setResolution] = useState<Resolution>("Keep original"); const [progress, setProgress] = useState(0); const interval = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => () => { if (interval.current) clearInterval(interval.current); }, []);
  const reset = () => { if (interval.current) clearInterval(interval.current); setFile(null); setProgress(0); setView("idle"); };
  const chooseFile = (nextFile: File) => { setFile(nextFile); setProgress(0); setView("selected"); };
  const startProcessing = (shouldFail = false) => { if (!file) return; setView("processing"); setProgress(0); interval.current = setInterval(() => { setProgress((current) => { const next = Math.min(current + 8, 100); if (next === 100) { if (interval.current) clearInterval(interval.current); window.setTimeout(() => setView(shouldFail ? "error" : "complete"), 300); } return next; }); }, 220); };

  return <ToolPage title="Compress Video" description="Reduce video size while preserving excellent visual quality." badge="Video tool" supportingInfo="MP4, MOV, WEBM and MKV supported">
    {view === "idle" && <><DropZone accept={VIDEO_ACCEPT_TYPES} title="Drop your video here" description="MP4, MOV, WEBM, MKV" maxSize={MAX_VIDEO_UPLOAD_SIZE} onFileSelected={chooseFile} /><TrustLine /></>}
    {view === "selected" && file && <><DropZone accept={VIDEO_ACCEPT_TYPES} title="Drop your video here" selectedFile={file} maxSize={MAX_VIDEO_UPLOAD_SIZE} onFileSelected={chooseFile} onRemove={reset} /><CompressionControls mode={mode} setMode={setMode} target={target} setTarget={setTarget} customTarget={customTarget} setCustomTarget={setCustomTarget} resolution={resolution} setResolution={setResolution} onCompress={() => startProcessing()} onSimulateError={() => startProcessing(true)} /></>}
    {view === "processing" && <ProcessingState title="Compressing video" progress={progress} status={progress < 100 ? "Optimizing video…" : "Finalizing your compressed video…"} />}
    {view === "complete" && <ResultCard title="Your video is ready" description="Compression completed successfully." originalSize={MOCK_ORIGINAL_VIDEO_SIZE} resultSize={MOCK_COMPRESSED_VIDEO_SIZE} reduction={70} originalLabel="Original" resultLabel="Compressed" reductionLabel="Smaller" downloadLabel="Download Video" processAnotherLabel="Choose another file" onDownload={() => undefined} onProcessAnother={reset} />}
    {view === "error" && <Card className="tool-error"><h2 className="tool-error-title">We couldn’t compress this video</h2><p className="tool-error-message">This is a simulated processing error. Please choose another file and try again.</p><div className="tool-cta"><Button onClick={() => setView("selected")}>Try again</Button><Button variant="secondary" onClick={reset}>Choose another file</Button></div></Card>}
    <RelatedTools />
  </ToolPage>;
}

function TrustLine() { return <p className="tool-trust"><span>No watermark</span><span>Private</span><span>Fast</span></p>; }

type ControlsProps = { mode: CompressionMode; setMode: (value: CompressionMode) => void; target: string; setTarget: (value: string) => void; customTarget: string; setCustomTarget: (value: string) => void; resolution: Resolution; setResolution: (value: Resolution) => void; onCompress: () => void; onSimulateError: () => void };
function CompressionControls({ mode, setMode, target, setTarget, customTarget, setCustomTarget, resolution, setResolution, onCompress, onSimulateError }: ControlsProps) {
  return <Card className="tool-controls"><fieldset><legend className="tool-control-label">Compression mode</legend><p className="tool-control-description">Balanced is recommended for most videos.</p><div className="tool-options" role="radiogroup" aria-label="Compression mode">{compressionModes.map((option) => <button className="tool-option" data-selected={mode === option} type="button" role="radio" aria-checked={mode === option} key={option} onClick={() => setMode(option)}>{option}</button>)}</div></fieldset><div><label className="tool-control-label" htmlFor="target-size">Target size</label><p className="tool-control-description">Choose a preset or set your own size.</p><Select id="target-size" className="mt-3" value={target} onChange={(event) => setTarget(event.target.value)}><option>Auto</option><option>100 MB</option><option>50 MB</option><option>25 MB</option><option>Custom target size</option></Select>{target === "Custom target size" && <Input className="mt-3" value={customTarget} onChange={(event) => setCustomTarget(event.target.value)} inputMode="decimal" placeholder="Enter target size in MB" aria-label="Custom target size in megabytes" />}</div><fieldset><legend className="tool-control-label">Resolution</legend><div className="tool-options" role="radiogroup" aria-label="Resolution">{resolutions.map((option) => <button className="tool-option" data-selected={resolution === option} type="button" role="radio" aria-checked={resolution === option} key={option} onClick={() => setResolution(option)}>{option}</button>)}</div></fieldset><div className="tool-cta"><Button onClick={onCompress}>Compress Video</Button><Button variant="ghost" onClick={onSimulateError}>Simulate error</Button></div></Card>;
}

function RelatedTools() { return <section className="related-tools" aria-labelledby="related-tools-title"><h2 className="related-tools-title" id="related-tools-title">More file tools</h2><p className="related-tools-description">More focused utilities are coming soon.</p><div className="related-tools-grid">{relatedTools.map((tool) => <Card className="ui-card-interactive related-tool-card" key={tool.name}><h3 className="related-tool-name">{tool.name}</h3><p className="related-tool-description">{tool.description}</p></Card>)}</div></section>; }
