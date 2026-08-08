"use client";

import { useState } from "react";
import { Button, Card, Input, Select } from "@/components/ui";
import type { ImageCompressionMode, ImageOutputFormat, ImageResizeOption } from "@/lib/api/types";
import {
  IMAGE_BALANCED_QUALITY_DEFAULT,
  IMAGE_MAX_DIMENSION_PERCENT,
  IMAGE_MIN_DIMENSION_PERCENT,
  IMAGE_SMALLEST_QUALITY_DEFAULT,
  IMAGE_TARGET_MIN_QUALITY_DEFAULT,
} from "./config";

export type TargetPreset = "20 KB" | "50 KB" | "100 KB" | "200 KB" | "500 KB" | "Custom";

const compressionModes: { label: string; value: ImageCompressionMode }[] = [
  { label: "Best Quality", value: "best_quality" },
  { label: "Balanced", value: "balanced" },
  { label: "Smallest", value: "smallest_size" },
  { label: "Target Size", value: "target_size" },
];

const outputFormats: { label: string; value: ImageOutputFormat }[] = [
  { label: "Auto — Recommended", value: "auto" },
  { label: "Keep original", value: "original" },
  { label: "WebP", value: "webp" },
  { label: "JPG", value: "jpeg" },
];

type Dimensions = { width: number; height: number } | null;

type Props = {
  mode: ImageCompressionMode;
  setMode: (value: ImageCompressionMode) => void;
  targetPreset: TargetPreset;
  setTargetPreset: (value: TargetPreset) => void;
  customTarget: string;
  setCustomTarget: (value: string) => void;
  outputFormat: ImageOutputFormat;
  setOutputFormat: (value: ImageOutputFormat) => void;
  resize: ImageResizeOption;
  setResize: (value: ImageResizeOption) => void;
  qualityPercent: number | null;
  setQualityPercent: (value: number | null) => void;
  resizePercent: string;
  setResizePercent: (value: string) => void;
  customWidth: string;
  setCustomWidth: (value: string) => void;
  customHeight: string;
  setCustomHeight: (value: string) => void;
  lockAspectRatio: boolean;
  setLockAspectRatio: (value: boolean) => void;
  allowResizeForTarget: boolean;
  setAllowResizeForTarget: (value: boolean) => void;
  sourceDimensions: Dimensions;
  isPng: boolean;
  onCompress: () => void;
};

export function ImageCompressionControls(props: Props) {
  const {
    mode, setMode, targetPreset, setTargetPreset, customTarget, setCustomTarget,
    outputFormat, setOutputFormat, resize, setResize, qualityPercent, setQualityPercent,
    resizePercent, setResizePercent, customWidth, setCustomWidth, customHeight, setCustomHeight,
    lockAspectRatio, setLockAspectRatio, allowResizeForTarget, setAllowResizeForTarget,
    sourceDimensions, isPng, onCompress,
  } = props;
  const [showMoreControl, setShowMoreControl] = useState(false);
  const canAdjustQuality = mode !== "best_quality";
  const effectiveQuality = qualityPercent ?? defaultQualityForMode(mode);
  const updateCustomDimension = (axis: "width" | "height", value: string) => {
    if (axis === "width") {
      setCustomWidth(value);
      if (lockAspectRatio && sourceDimensions && value) {
        setCustomHeight(String(Math.max(1, Math.round(sourceDimensions.height * Number(value) / sourceDimensions.width))));
      }
      return;
    }
    setCustomHeight(value);
    if (lockAspectRatio && sourceDimensions && value) {
      setCustomWidth(String(Math.max(1, Math.round(sourceDimensions.width * Number(value) / sourceDimensions.height))));
    }
  };

  return <Card className="tool-controls image-compression-controls">
    <div className="tool-controls-heading">
      <div><h2 className="tool-control-label">Compression settings</h2><p className="tool-control-description">Balanced is recommended for most images.</p></div>
      <Button onClick={onCompress}>Compress Image</Button>
    </div>
    <fieldset>
      <legend className="tool-control-label">Compression goal</legend>
      <div className="tool-options" role="radiogroup" aria-label="Compression goal">
        {compressionModes.map((option) => <button className="tool-option" data-selected={mode === option.value} type="button" role="radio" aria-checked={mode === option.value} key={option.value} onClick={() => setMode(option.value)}>{option.label}</button>)}
      </div>
    </fieldset>
    {mode === "target_size" && <fieldset>
      <legend className="tool-control-label">Target size</legend>
      <p className="tool-control-description">FluxFile aims for the best result at or below your target.</p>
      <div className="tool-options tool-options-compact" role="radiogroup" aria-label="Target size">
        {(["20 KB", "50 KB", "100 KB", "200 KB", "500 KB", "Custom"] as TargetPreset[]).map((option) => <button className="tool-option" data-selected={targetPreset === option} type="button" role="radio" aria-checked={targetPreset === option} key={option} onClick={() => setTargetPreset(option)}>{option}</button>)}
      </div>
      {targetPreset === "Custom" && <label className="tool-target-input"><span className="sr-only">Custom target size in kilobytes</span><Input value={customTarget} onChange={(event) => setCustomTarget(event.target.value)} type="number" min="1" inputMode="numeric" placeholder="Target size" /><span className="tool-target-unit" aria-hidden="true">KB</span></label>}
      <label className="image-toggle"><input type="checkbox" checked={allowResizeForTarget} onChange={(event) => setAllowResizeForTarget(event.target.checked)} /> <span>Allow resizing if needed</span></label>
    </fieldset>}
    <fieldset>
      <legend className="tool-control-label">Output format</legend>
      <div className="tool-options" role="radiogroup" aria-label="Output format">
        {outputFormats.map((option) => <button className="tool-option" data-selected={outputFormat === option.value} type="button" role="radio" aria-checked={outputFormat === option.value} key={option.value} onClick={() => setOutputFormat(option.value)}>{option.label}</button>)}
      </div>
      {isPng && outputFormat === "original" && <p className="image-context-hint">PNG prioritizes lossless quality. Use WebP or lower quality for a much smaller file.</p>}
    </fieldset>
    <Button variant="ghost" className="image-more-control" onClick={() => setShowMoreControl((current) => !current)} aria-expanded={showMoreControl}>
      {showMoreControl ? "Hide more control" : "More control"}
    </Button>
    {showMoreControl && <div className="image-advanced-controls">
      {canAdjustQuality && <label className="image-quality-control">
        <span className="tool-control-label">{mode === "target_size" ? "Minimum quality" : "Quality"}</span>
        <span className="tool-control-description">{mode === "target_size" ? "FluxFile will not reduce quality below this while trying your target." : "Higher quality keeps more detail; lower quality makes a smaller file."}</span>
        <div className="image-range-row"><input type="range" min="1" max="100" value={effectiveQuality} onChange={(event) => setQualityPercent(Number(event.target.value))} aria-label={mode === "target_size" ? "Minimum quality" : "Image quality"} /><output>{effectiveQuality}%</output></div>
      </label>}
      <div className="image-dimensions-control">
        <label className="tool-control-label" htmlFor="image-dimensions">Dimensions</label>
        <Select id="image-dimensions" value={resize} onChange={(event) => setResize(event.target.value as ImageResizeOption)}>
          <option value="keep_original">Keep original</option>
          <option value="percentage">Percentage</option>
          <option value="custom">Custom pixels</option>
        </Select>
        {resize === "percentage" && <label className="tool-target-input"><span className="sr-only">Resize percentage</span><Input type="number" min={IMAGE_MIN_DIMENSION_PERCENT} max={IMAGE_MAX_DIMENSION_PERCENT} inputMode="numeric" value={resizePercent} onChange={(event) => setResizePercent(event.target.value)} /><span className="tool-target-unit">%</span></label>}
        {resize === "custom" && <div className="image-custom-dimensions">
          <label><span>Width</span><Input type="number" min="1" inputMode="numeric" value={customWidth} onChange={(event) => updateCustomDimension("width", event.target.value)} placeholder="Width" /><small>px</small></label>
          <label><span>Height</span><Input type="number" min="1" inputMode="numeric" value={customHeight} onChange={(event) => updateCustomDimension("height", event.target.value)} placeholder="Height" /><small>px</small></label>
          <label className="image-toggle"><input type="checkbox" checked={lockAspectRatio} onChange={(event) => setLockAspectRatio(event.target.checked)} /> <span>Lock aspect ratio</span></label>
        </div>}
      </div>
    </div>}
  </Card>;
}

function defaultQualityForMode(mode: ImageCompressionMode) {
  if (mode === "smallest_size") return IMAGE_SMALLEST_QUALITY_DEFAULT;
  if (mode === "target_size") return IMAGE_TARGET_MIN_QUALITY_DEFAULT;
  return IMAGE_BALANCED_QUALITY_DEFAULT;
}
