class ApplicationError(Exception):
    """Base error with a safe HTTP-facing message."""

    status_code = 400
    public_message = "The request could not be completed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)


class NotFoundError(ApplicationError):
    status_code = 404
    public_message = "The requested resource was not found."


class ValidationError(ApplicationError):
    status_code = 422
    public_message = "The request is invalid."
