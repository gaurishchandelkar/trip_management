import base64
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from joserfc import jwt
from joserfc.jwk import OctKey, RSAKey

from backend.domain.errors import IdentityRejectedError, ProviderUnavailableError
from backend.domain.models import Identity
from backend.domain.pkce import code_challenge, new_code_verifier
from backend.identity.oidc import GOOGLE_ISSUER, JWKS_TTL_S, OidcProvider, OidcSettings

ISSUER = "https://idp.example"
NOW = 1_800_000_000.0
CODE = "the-code"
VERIFIER = "the-verifier"
NONCE = "the-nonce"
CLIENT_CREDENTIAL = "client-credential-for-tests"


def _key(kid: str) -> RSAKey:
    return RSAKey.generate_key(2048, parameters={"kid": kid, "alg": "RS256"}, private=True)


KEY = _key("k1")
ROTATED_KEY = _key("k2")
SETTINGS = OidcSettings(
    issuer=ISSUER,
    client_id="client-1",
    client_secret=CLIENT_CREDENTIAL,
    redirect_uri="http://localhost:5173/api/auth/google/callback",
)


def claims(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "iss": ISSUER,
        "aud": "client-1",
        "sub": "subject-1",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "nonce": NONCE,
        "iat": int(NOW),
        "exp": int(NOW) + 3600,
    }
    return {**base, **overrides}


def sign(payload: dict[str, Any], key: RSAKey = KEY) -> str:
    return jwt.encode({"alg": "RS256", "kid": key.kid}, payload, key)


def hs256_with_public_key(payload: dict[str, Any]) -> str:
    """Algorithm confusion: the RSA public key used as an HMAC secret."""
    secret = OctKey.import_key(json.dumps(KEY.as_dict(private=False)).encode())
    return jwt.encode({"alg": "HS256", "kid": KEY.kid}, payload, secret)


def unsigned(payload: dict[str, Any]) -> str:
    def part(value: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(payload)}."


@dataclass
class FakeIdp:
    """Answers discovery, JWKS and token calls the way a provider does, and records them."""

    id_token: str = field(default_factory=lambda: sign(claims()))
    keys: list[RSAKey] = field(default_factory=lambda: [KEY])
    issuer: str = ISSUER
    fail: dict[str, Callable[[], httpx2.Response]] = field(
        default_factory=dict[str, Callable[[], httpx2.Response]]
    )
    requests: list[httpx2.Request] = field(default_factory=list[httpx2.Request])

    def count(self, path: str) -> int:
        return sum(1 for request in self.requests if request.url.path == path)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        step = {
            "/.well-known/openid-configuration": "discovery",
            "/jwks": "jwks",
            "/token": "token",
        }[request.url.path]
        if step in self.fail:
            return self.fail[step]()
        if step == "discovery":
            return httpx2.Response(
                200,
                json={
                    "issuer": self.issuer,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                },
            )
        if step == "jwks":
            keys = [key.as_dict(private=False) for key in self.keys]
            return httpx2.Response(200, json={"keys": keys})
        return httpx2.Response(200, json={"access_token": "at", "id_token": self.id_token})


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> float:
        return self.now


def provider(idp: FakeIdp, clock: Clock | None = None) -> OidcProvider:
    http = httpx2.Client(transport=httpx2.MockTransport(idp))
    return OidcProvider("google", SETTINGS, http, clock or Clock())


def test_authorization_url_has_every_parameter() -> None:
    url = urlsplit(provider(FakeIdp()).authorization_url("st", "nn", "cc"))
    query = {name: values[0] for name, values in parse_qs(url.query).items()}

    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISSUER}/authorize"
    assert query == {
        "response_type": "code",
        "client_id": "client-1",
        "redirect_uri": "http://localhost:5173/api/auth/google/callback",
        "scope": "openid profile email",
        "state": "st",
        "nonce": "nn",
        "code_challenge": "cc",
        "code_challenge_method": "S256",
    }


# RFC 7636 appendix B gives its example as octets: the verifier's 32 random bytes, and the
# SHA-256 of the encoded verifier. Kept as octets, the way the RFC prints them.
RFC_VERIFIER_OCTETS = [
    *(116, 24, 223, 180, 151, 153, 224, 37, 79, 250, 96, 125, 216, 173, 187, 186),
    *(22, 212, 37, 77, 105, 214, 191, 240, 91, 88, 5, 88, 83, 132, 141, 121),
]
RFC_DIGEST_OCTETS = [
    *(19, 211, 30, 150, 26, 26, 216, 236, 47, 22, 177, 12, 76, 152, 46, 8),
    *(118, 168, 120, 173, 109, 241, 68, 86, 110, 225, 137, 74, 203, 112, 249, 195),
]


def base64url(octets: list[int]) -> str:
    return base64.urlsafe_b64encode(bytes(octets)).rstrip(b"=").decode()


def test_code_challenge_matches_the_rfc_7636_example() -> None:
    verifier = base64url(RFC_VERIFIER_OCTETS)

    assert len(verifier) == 43
    assert code_challenge(verifier) == base64url(RFC_DIGEST_OCTETS)


def test_code_verifiers_are_long_and_fresh() -> None:
    first, second = new_code_verifier(), new_code_verifier()

    assert first != second
    assert 43 <= len(first) <= 128


def test_valid_token_returns_the_identity() -> None:
    identity = provider(FakeIdp()).verified_identity(CODE, VERIFIER, NONCE)

    assert identity == Identity(subject="subject-1", name="Ada Lovelace")


def test_identity_without_a_name_has_none() -> None:
    payload = claims()
    del payload["name"]

    identity = provider(FakeIdp(id_token=sign(payload))).verified_identity(CODE, VERIFIER, NONCE)

    assert identity == Identity(subject="subject-1", name=None)


def test_google_tokens_may_name_the_issuer_without_the_scheme() -> None:
    google = OidcSettings(GOOGLE_ISSUER, "client-1", CLIENT_CREDENTIAL, SETTINGS.redirect_uri)
    idp = FakeIdp(id_token=sign(claims(iss="accounts.google.com")), issuer=GOOGLE_ISSUER)
    http = httpx2.Client(transport=httpx2.MockTransport(idp))

    identity = OidcProvider("google", google, http, Clock()).verified_identity(CODE, "v", NONCE)

    assert identity.subject == "subject-1"


def test_token_request_sends_the_code_verifier() -> None:
    idp = FakeIdp()

    provider(idp).verified_identity(CODE, VERIFIER, NONCE)

    token_request = next(r for r in idp.requests if r.url.path == "/token")
    assert token_request.method == "POST"
    assert parse_qs(token_request.content.decode()) == {
        "grant_type": ["authorization_code"],
        "code": [CODE],
        "redirect_uri": [SETTINGS.redirect_uri],
        "client_id": ["client-1"],
        "client_secret": [CLIENT_CREDENTIAL],
        "code_verifier": [VERIFIER],
    }


@pytest.mark.parametrize(
    "id_token",
    [
        pytest.param(sign(claims(), _key("k1")), id="bad signature"),
        pytest.param(sign(claims(iss="https://evil.example")), id="wrong issuer"),
        pytest.param(sign(claims(aud="another-client")), id="wrong audience"),
        pytest.param(sign(claims(exp=int(NOW) - 600)), id="expired"),
        pytest.param(sign(claims(iat=int(NOW) + 3600)), id="issued in the future"),
        pytest.param(sign(claims(nonce="another-nonce")), id="wrong nonce"),
        pytest.param(sign({k: v for k, v in claims().items() if k != "nonce"}), id="no nonce"),
        pytest.param(sign(claims(sub="")), id="empty subject"),
        pytest.param(sign(claims(sub="s" * 256)), id="subject too long"),
        pytest.param(unsigned(claims()), id="alg none"),
        pytest.param(hs256_with_public_key(claims()), id="HS256 with the public key"),
        pytest.param(sign(claims(nonce=[NONCE])), id="nonce as a list"),
        pytest.param(sign(claims(aud=["client-1", "other"])), id="several audiences, no azp"),
        pytest.param(
            sign(claims(aud=["client-1", "other"], azp="other")),
            id="several audiences, azp is another client",
        ),
        pytest.param("not-a-token", id="garbage"),
    ],
)
def test_rejects_tokens_that_fail_any_check(id_token: str) -> None:
    with pytest.raises(IdentityRejectedError):
        provider(FakeIdp(id_token=id_token)).verified_identity(CODE, VERIFIER, NONCE)


def test_several_audiences_are_accepted_when_issued_to_us() -> None:
    token = sign(claims(aud=["client-1", "other"], azp="client-1"))

    identity = provider(FakeIdp(id_token=token)).verified_identity(CODE, VERIFIER, NONCE)

    assert identity.subject == "subject-1"


def test_a_rejected_token_is_logged_at_warning_without_its_contents(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = sign(claims(iss="https://evil.example"))

    with caplog.at_level(logging.DEBUG), pytest.raises(IdentityRejectedError):
        provider(FakeIdp(id_token=token)).verified_identity(CODE, VERIFIER, NONCE)

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["identity token rejected provider=google check=token"]
    for value in (token, CODE, VERIFIER, NONCE, "subject-1", "evil.example"):
        assert value not in "\n".join(r.getMessage() for r in caplog.records)


def _timeout() -> httpx2.Response:
    raise httpx2.TimeoutException("timed out")


FAILURES: dict[str, Callable[[], httpx2.Response]] = {
    "timeout": _timeout,
    "500": lambda: httpx2.Response(500),
    "not json": lambda: httpx2.Response(200, text="<html>"),
    "not an object": lambda: httpx2.Response(200, json=["a"]),
}


@pytest.mark.parametrize("step", ["discovery", "jwks", "token"])
@pytest.mark.parametrize("failure", FAILURES)
def test_provider_failures_raise_unavailable(step: str, failure: str) -> None:
    idp = FakeIdp(fail={step: FAILURES[failure]})

    with pytest.raises(ProviderUnavailableError):
        provider(idp).verified_identity(CODE, VERIFIER, NONCE)


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"issuer": ISSUER}, id="missing endpoints"),
        pytest.param(
            {
                "issuer": "https://evil.example",
                "authorization_endpoint": "a",
                "token_endpoint": "t",
                "jwks_uri": "j",
            },
            id="another issuer",
        ),
    ],
)
def test_discovery_must_describe_the_configured_issuer(response: dict[str, str]) -> None:
    idp = FakeIdp(fail={"discovery": lambda: httpx2.Response(200, json=response)})

    with pytest.raises(ProviderUnavailableError):
        provider(idp).authorization_url("s", "n", "c")


def test_unreadable_keys_raise_unavailable() -> None:
    idp = FakeIdp(fail={"jwks": lambda: httpx2.Response(200, json={"keys": [{"kty": "nope"}]})})

    with pytest.raises(ProviderUnavailableError):
        provider(idp).verified_identity(CODE, VERIFIER, NONCE)


def test_token_response_without_an_id_token_raises_unavailable() -> None:
    idp = FakeIdp(fail={"token": lambda: httpx2.Response(200, json={"access_token": "at"})})

    with pytest.raises(ProviderUnavailableError):
        provider(idp).verified_identity(CODE, VERIFIER, NONCE)


def test_discovery_is_fetched_once() -> None:
    idp = FakeIdp()
    oidc = provider(idp)

    oidc.authorization_url("s", "n", "c")
    oidc.verified_identity(CODE, VERIFIER, NONCE)

    assert idp.count("/.well-known/openid-configuration") == 1


def test_jwks_is_cached_for_an_hour() -> None:
    idp = FakeIdp()
    clock = Clock()
    oidc = provider(idp, clock)

    oidc.verified_identity(CODE, VERIFIER, NONCE)
    clock.now += JWKS_TTL_S - 1
    idp.id_token = sign(claims(iat=int(clock.now), exp=int(clock.now) + 3600))
    oidc.verified_identity(CODE, VERIFIER, NONCE)
    assert idp.count("/jwks") == 1

    clock.now += 1
    idp.id_token = sign(claims(iat=int(clock.now), exp=int(clock.now) + 3600))
    oidc.verified_identity(CODE, VERIFIER, NONCE)
    assert idp.count("/jwks") == 2


def test_unknown_key_id_refetches_once() -> None:
    idp = FakeIdp()
    oidc = provider(idp)
    oidc.verified_identity(CODE, VERIFIER, NONCE)

    idp.keys = [ROTATED_KEY]
    idp.id_token = sign(claims(), ROTATED_KEY)

    assert oidc.verified_identity(CODE, VERIFIER, NONCE).subject == "subject-1"
    assert idp.count("/jwks") == 2


def test_key_id_unknown_after_a_refetch_is_rejected() -> None:
    idp = FakeIdp(id_token=sign(claims(), ROTATED_KEY))

    with pytest.raises(IdentityRejectedError):
        provider(idp).verified_identity(CODE, VERIFIER, NONCE)
    assert idp.count("/jwks") == 2


def test_never_logs_tokens_or_codes(caplog: pytest.LogCaptureFixture) -> None:
    private = [CODE, VERIFIER, NONCE, CLIENT_CREDENTIAL, "subject-1", "ada@example.com"]
    with caplog.at_level(logging.DEBUG):
        provider(FakeIdp()).verified_identity(CODE, VERIFIER, NONCE)
        with pytest.raises(ProviderUnavailableError):
            provider(FakeIdp(fail={"token": FAILURES["500"]})).verified_identity(
                CODE, VERIFIER, NONCE
            )

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "provider=google step=token" in logged
    for value in private:
        assert value not in logged
