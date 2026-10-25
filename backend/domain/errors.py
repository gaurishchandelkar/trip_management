class DomainError(Exception):
    """A rule was broken. The API maps each subclass to a fixed status and message."""


class ConflictError(DomainError):
    pass


class UserIdTakenError(ConflictError):
    pass


class GroupNameTakenError(ConflictError):
    pass


class RequestAlreadyPendingError(ConflictError):
    pass


class AlreadyMemberError(ConflictError):
    pass


class LimitReachedError(DomainError):
    pass


class NotFoundError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass


class UnauthenticatedError(DomainError):
    pass


class StorageUnavailableError(DomainError):
    pass


class InvalidCredentialsError(UnauthenticatedError):
    pass
