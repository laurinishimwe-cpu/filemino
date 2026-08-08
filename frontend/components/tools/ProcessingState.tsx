import { Card, Progress } from "@/components/ui";
type ProcessingStateProps = { title: string; progress?: number; indeterminate?: boolean; status?: string; showPercentage?: boolean };
export function ProcessingState({ title, progress = 0, indeterminate = false, status, showPercentage = true }: ProcessingStateProps) { return <Card className="processing-state"><h2 className="processing-title">{title}</h2><Progress className="mt-4" value={progress} indeterminate={indeterminate} status={status} showPercentage={showPercentage} /></Card>; }
