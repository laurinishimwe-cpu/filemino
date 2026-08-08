"""Windows compatibility wrapper for RQ's spawn-based worker."""

import os
import subprocess
import sys
import time

from rq.worker.worker_classes import get_connection_kwargs
from rq.worker import SpawnWorker


class WindowsSpawnWorker(SpawnWorker):
    """Use SpawnWorker's process model without Unix-only spawn/wait calls on Windows."""

    def fork_work_horse(self, job, queue) -> None:
        if os.name != "nt":
            super().fork_work_horse(job, queue)
            return

        os.environ["RQ_WORKER_ID"] = self.name
        os.environ["RQ_EXECUTION_ID"] = self.execution.id
        redis_kwargs = get_connection_kwargs(self.connection)
        redis_kwargs.pop("retry", None)
        redis_kwargs.pop("driver_info", None)
        source = f"""
import os
import sys
from redis import Redis
from rq import Worker, Queue
from rq.job import Job
from rq.executions import Execution

redis = Redis(**{redis_kwargs!r})
worker = Worker.find_by_key({self.key!r}, connection=redis, serializer={self._serializer_arg!r})
if not worker:
    sys.exit(1)
job = Job.fetch({job.id!r}, connection=worker.connection, serializer=worker.serializer)
queue = Queue({queue.name!r}, connection=worker.connection, serializer=worker.serializer)
execution_id = os.environ["RQ_EXECUTION_ID"]
worker.execution = Execution.fetch(execution_id, job.id, connection=worker.connection)
worker._is_horse = True
worker.main_work_horse(job, queue)
"""
        process = subprocess.Popen([sys.executable, "-c", source], env=os.environ.copy())
        self._horse_process = process
        self._horse_pid = process.pid
        self.procline(f"Spawned {process.pid} at {time.time()}")

    def wait_for_horse(self) -> tuple[int | None, int | None, object | None]:
        if os.name != "nt":
            return super().wait_for_horse()
        process = getattr(self, "_horse_process", None)
        if process is None:
            return None, None, None
        return process.pid, process.wait(), None

    def monitor_work_horse(self, job, queue) -> None:
        if os.name != "nt":
            super().monitor_work_horse(job, queue)
            return

        # RQ's monitor is otherwise portable but formats non-zero exits with
        # POSIX-only os.WIFSIGNALED/os.WTERMSIG helpers.
        missing_signal_helpers = not hasattr(os, "WIFSIGNALED")
        if missing_signal_helpers:
            setattr(os, "WIFSIGNALED", lambda _: False)
            setattr(os, "WTERMSIG", lambda _: 0)
        try:
            super().monitor_work_horse(job, queue)
        finally:
            if missing_signal_helpers:
                delattr(os, "WIFSIGNALED")
                delattr(os, "WTERMSIG")
