class AppError(Exception):
    status_code = 400


class AgentError(AppError):
    status_code = 502


class ProviderError(AppError):
    status_code = 502


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class AuthError(AppError):
    status_code = 401


class UnavailableError(AppError):
    """The process is alive but cannot accept work.

    503 rather than 500: nothing raised, and the service still answers — it
    has simply run out of the capacity to take on more. A load balancer or a
    liveness probe should act on it; a caller should retry elsewhere.
    """

    status_code = 503
