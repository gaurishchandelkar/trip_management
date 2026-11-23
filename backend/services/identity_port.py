from typing import Protocol

from backend.domain.models import Identity


class IdentityProvider(Protocol):
    """An OpenID Connect provider. The adapter lives in backend.identity; tests use a fake.

    Both methods raise ProviderUnavailableError when the provider can't be reached, and
    verified_identity raises IdentityRejectedError when the ID token fails a check.
    """

    @property
    def name(self) -> str: ...

    def authorization_url(self, state: str, nonce: str, code_challenge: str) -> str: ...

    def verified_identity(self, code: str, code_verifier: str, nonce: str) -> Identity: ...
