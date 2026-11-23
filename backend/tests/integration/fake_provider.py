"""An in-process identity provider for the integration tests: no HTTP, but the same checks.

It remembers the nonce and PKCE challenge each authorization URL carried, issues single-use
codes for the identities a test approves, and checks the verifier and nonce on exchange.
"""

import secrets
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi.testclient import TestClient

from backend.domain.errors import DomainError, IdentityRejectedError
from backend.domain.models import Identity
from backend.domain.pkce import code_challenge

AUTHORIZE_URL = "https://idp.test/authorize"
START = "/api/auth/google/start"
CALLBACK = "/api/auth/google/callback"
REGISTRATION = "/api/auth/registration"


@dataclass
class FakeIdentityProvider:
    name: str = "google"
    failure: type[DomainError] | None = None
    exchanges: int = 0
    _authorizations: dict[str, tuple[str, str]] = field(default_factory=dict[str, tuple[str, str]])
    _codes: dict[str, tuple[Identity, str, str]] = field(
        default_factory=dict[str, tuple[Identity, str, str]]
    )

    def authorization_url(self, state: str, nonce: str, code_challenge: str) -> str:
        if self.failure is not None:
            raise self.failure
        self._authorizations[state] = (nonce, code_challenge)
        return f"{AUTHORIZE_URL}?{urlencode({'state': state})}"

    def approve(self, state: str, subject: str, name: str | None = "Ada Lovelace") -> str:
        """What the provider does when the person consents: a code for this identity."""
        nonce, challenge = self._authorizations[state]
        code = secrets.token_urlsafe(16)
        self._codes[code] = (Identity(subject=subject, name=name), nonce, challenge)
        return code

    def verified_identity(self, code: str, code_verifier: str, nonce: str) -> Identity:
        self.exchanges += 1
        if self.failure is not None:
            raise self.failure
        if code not in self._codes:
            raise IdentityRejectedError
        identity, expected_nonce, challenge = self._codes.pop(code)
        if nonce != expected_nonce or code_challenge(code_verifier) != challenge:
            raise IdentityRejectedError
        return identity


def start(client: TestClient, return_to: str | None = None) -> str:
    """Starts a sign-in and returns the state the provider was sent."""
    params = {} if return_to is None else {"return_to": return_to}
    response = client.get(START, params=params, follow_redirects=False)
    assert response.status_code == 302, response.text
    return parse_qs(urlsplit(response.headers["location"]).query)["state"][0]


def come_back(client: TestClient, state: str, code: str) -> str:
    """The provider sends the browser back. Returns where the app redirects it."""
    response = client.get(CALLBACK, params={"state": state, "code": code}, follow_redirects=False)
    assert response.status_code == 302, response.text
    return response.headers["location"]


def sign_up(
    client: TestClient,
    provider: FakeIdentityProvider,
    user_id: str,
    subject: str | None = None,
    display_name: str | None = None,
    mobile: str = "+919876543210",
) -> None:
    """A new person signs in with the provider and finishes registering."""
    state = start(client)
    assert come_back(client, state, provider.approve(state, subject or f"sub-{user_id}")) == (
        "/register/complete"
    )
    response = client.post(
        REGISTRATION,
        json={
            "user_id": user_id,
            "display_name": display_name or user_id.capitalize(),
            "mobile": mobile,
        },
    )
    assert response.status_code == 201, response.text
