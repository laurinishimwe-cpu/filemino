import { getJob } from "./filemino-client";
import type { JobResponse } from "./types";

const terminalStatuses = new Set(["completed", "failed", "cancelled", "expired"]);

type JobPollingOptions = {
  signal: AbortSignal;
  onJob: (job: JobResponse) => void;
  intervalMs?: number;
};

export async function pollJobUntilTerminal(jobId: string, { signal, onJob, intervalMs = 1_000 }: JobPollingOptions) {
  let consecutiveNetworkErrors = 0;
  while (!signal.aborted) {
    try {
      const job = await getJob(jobId, signal);
      consecutiveNetworkErrors = 0;
      onJob(job);
      if (terminalStatuses.has(job.status)) return;
    } catch (error) {
      if (signal.aborted) throw error;
      consecutiveNetworkErrors += 1;
      if (consecutiveNetworkErrors >= 3) throw error;
    }
    await wait(intervalMs, signal);
  }
}

function wait(duration: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(done, duration);
    const abort = () => {
      window.clearTimeout(timeout);
      signal.removeEventListener("abort", abort);
      reject(new DOMException("Polling aborted.", "AbortError"));
    };
    function done() {
      signal.removeEventListener("abort", abort);
      resolve();
    }
    signal.addEventListener("abort", abort, { once: true });
  });
}
