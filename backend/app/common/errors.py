class AppError(Exception):
    status_code = 400


class AgentError(AppError):
    status_code = 502


class ProviderError(AppError):
    status_code = 502


class NotFoundError(AppError):
    status_code = 404


class AuthError(AppError):
    status_code = 401

