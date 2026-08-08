class ApplicationError(Exception):
    """Base error with a safe HTTP-facing message."""

    status_code = 400
    public_message = "The request could not be completed."
    code = "REQUEST_FAILED"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)


class NotFoundError(ApplicationError):
    status_code = 404
    public_message = "The requested resource was not found."


class ValidationError(ApplicationError):
    status_code = 422
    public_message = "The request is invalid."


class UnsupportedMediaError(ApplicationError):
    status_code = 415
    public_message = "This file type is not supported."


class InvalidVideoError(ApplicationError):
    status_code = 422
    public_message = "The uploaded file is not a valid video."


class ProbeError(ApplicationError):
    status_code = 422
    public_message = "We could not inspect this video."


class FileTooLargeError(ApplicationError):
    status_code = 413
    public_message = "The uploaded file exceeds the allowed size."
    code = "FILE_TOO_LARGE"

class RateLimitedError(ApplicationError):
    status_code = 429
    public_message = "Too many job requests. Please try again later."
    code = "RATE_LIMITED"
class VideoTooLongError(ApplicationError):
    status_code = 422
    public_message = "The video duration exceeds the guest limit."
    code = "VIDEO_TOO_LONG"
class ResolutionNotAllowedError(ApplicationError):
    status_code = 422
    public_message = "The video resolution exceeds the guest limit."
    code = "RESOLUTION_NOT_ALLOWED"
class TooManyActiveJobsError(ApplicationError):
    status_code = 429
    public_message = "Too many active jobs are already running."
    code = "TOO_MANY_ACTIVE_JOBS"
