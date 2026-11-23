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


class ProviderUnavailableError(DomainError):
    """The identity provider timed out, failed, or answered with something unreadable."""


class IdentityRejectedError(DomainError):
    """The provider's ID token failed a check: signature, issuer, audience, expiry or nonce."""
