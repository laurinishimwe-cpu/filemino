from uuid import UUID


def run_compression_job(job_id: UUID) -> None:
    """Future queue entry point; never called from an API request handler."""
    raise NotImplementedError("Worker processing is not implemented yet.")
