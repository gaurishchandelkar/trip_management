"""OpenID Connect sign-in: discovery, the authorization URL, the code exchange and the ID-token
check. Google in production; a local stand-in in the E2E tests (docs/specs/sso-registration.md).
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import NoReturn, cast
from urllib.parse import urlencode

import httpx2
from joserfc import jwt
from joserfc.errors import InvalidKeyIdError, JoseError
from joserfc.jwk import KeySet, KeySetSerialization

from backend.domain.errors import IdentityRejectedError, ProviderUnavailableError
from backend.domain.models import Identity

TIMEOUT_S = 5
JWKS_TTL_S = 3600
# Allowed clock difference between us and the provider when checking exp and iat.
LEEWAY_S = 300
SCOPE = "openid profile email"
ALGORITHMS = ["RS256"]
GOOGLE_ISSUER = "https://accounts.google.com"
MAX_SUBJECT_LENGTH = 255

logger = logging.getLogger(__name__)

type Json = dict[str, object]


@dataclass(frozen=True)
class OidcSettings:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class _Endpoints:
    authorization: str
    token: str
    jwks: str


class OidcProvider:
    """One configured provider. Discovery is fetched once; the signing keys once an hour."""

    def __init__(
        self,
        name: str,
        settings: OidcSettings,
        http: httpx2.Client,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.name = name
        self._settings = settings
        self._http = http
        self._now = now
        self._endpoints: _Endpoints | None = None
        self._keys: KeySet | None = None
        self._keys_fetched_at = 0.0
        # Google's ID tokens may name the issuer without the scheme.
        self._issuers = [settings.issuer]
        if settings.issuer == GOOGLE_ISSUER:
            self._issuers.append("accounts.google.com")

    def close(self) -> None:
        self._http.close()

    def authorization_url(self, state: str, nonce: str, code_challenge: str) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._settings.client_id,
                "redirect_uri": self._settings.redirect_uri,
                "scope": SCOPE,
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self._discover().authorization}?{query}"

    def verified_identity(self, code: str, code_verifier: str, nonce: str) -> Identity:
        body = self._json(
            "token",
            "POST",
            self._discover().token,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.redirect_uri,
                "client_id": self._settings.client_id,
                "client_secret": self._settings.client_secret,
                "code_verifier": code_verifier,
            },
        )
        id_token = body.get("id_token")
        if not isinstance(id_token, str):
            self._unavailable("token")
        claims = self._verified_claims(id_token, nonce)
        subject = claims.get("sub")
        if not isinstance(subject, str) or not 0 < len(subject) <= MAX_SUBJECT_LENGTH:
            self._rejected("subject")
        # joserfc accepts a list that contains the expected nonce; OIDC sends a single string.
        if not isinstance(claims.get("nonce"), str):
            self._rejected("nonce")
        # A token for several audiences must name us as the party it was issued to (OIDC
        # Core 3.1.3.7), or a token minted for another client could sign someone in here.
        audience = claims.get("aud")
        if isinstance(audience, list) and claims.get("azp") != self._settings.client_id:
            self._rejected("azp")
        name = claims.get("name")
        return Identity(subject=subject, name=name if isinstance(name, str) else None)

    def _verified_claims(self, id_token: str, nonce: str) -> Json:
        registry = jwt.JWTClaimsRegistry(
            now=int(self._now()),
            leeway=LEEWAY_S,
            iss={"essential": True, "values": self._issuers},
            aud={"essential": True, "value": self._settings.client_id},
            exp={"essential": True},
            iat={"essential": True},
            sub={"essential": True},
            nonce={"essential": True, "value": nonce},
        )
        try:
            token = self._decode(id_token)
            registry.validate(token.claims)
        except JoseError:
            self._rejected("token")
        return token.claims

    def _decode(self, id_token: str) -> jwt.Token:
        try:
            return jwt.decode(id_token, self._key_set(), algorithms=ALGORITHMS)
        except InvalidKeyIdError:
            # The provider rotates its keys, so an unknown key ID earns one refetch.
            return jwt.decode(id_token, self._key_set(refresh=True), algorithms=ALGORITHMS)

    def _discover(self) -> _Endpoints:
        if self._endpoints is None:
            url = f"{self._settings.issuer}/.well-known/openid-configuration"
            body = self._json("discovery", "GET", url)
            fields = ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")
            values = [body.get(field) for field in fields]
            strings = [value for value in values if isinstance(value, str)]
            if len(strings) != len(fields) or strings[0] != self._settings.issuer:
                self._unavailable("discovery")
            self._endpoints = _Endpoints(*strings[1:])
        return self._endpoints

    def _key_set(self, refresh: bool = False) -> KeySet:
        stale = self._now() - self._keys_fetched_at >= JWKS_TTL_S
        if self._keys is None or stale or refresh:
            body = self._json("jwks", "GET", self._discover().jwks)
            try:
                self._keys = KeySet.import_key_set(cast(KeySetSerialization, body))
            except (JoseError, ValueError, TypeError, KeyError):
                self._unavailable("jwks")
            self._keys_fetched_at = self._now()
        return self._keys

    def _json(self, step: str, method: str, url: str, data: dict[str, str] | None = None) -> Json:
        try:
            response = self._http.request(method, url, data=data, timeout=TIMEOUT_S)
            response.raise_for_status()
            body: object = response.json()
        except (httpx2.HTTPError, ValueError):
            self._unavailable(step)
        if not isinstance(body, dict):
            self._unavailable(step)
        return cast(Json, body)

    def _unavailable(self, step: str) -> NoReturn:
        # The step and provider only: never a code, token or response body.
        logger.warning("identity provider unavailable provider=%s step=%s", self.name, step)
        raise ProviderUnavailableError

    def _rejected(self, check: str) -> NoReturn:
        # Which check failed, never the token or its claims.
        logger.warning("identity token rejected provider=%s check=%s", self.name, check)
        raise IdentityRejectedError
