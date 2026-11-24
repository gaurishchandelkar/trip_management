import logging

import pytest

from backend.identity.config import InsecureIssuerError, google_provider, google_settings
from backend.identity.oidc import GOOGLE_ISSUER, OidcProvider, OidcSettings

ID = "client-id-value"
CREDENTIAL = "client-credential-value"
BOTH = {"TRIP_GOOGLE_CLIENT_ID": ID, "TRIP_GOOGLE_CLIENT_SECRET": CREDENTIAL}


def test_no_variables_means_google_is_off() -> None:
    assert google_settings({}) is None
    assert google_provider({}) is None


def test_configured_google_gets_its_own_provider() -> None:
    provider = google_provider(BOTH)

    assert isinstance(provider, OidcProvider)
    assert provider.name == "google"
    provider.close()


def test_defaults_to_google_and_the_dev_server() -> None:
    assert google_settings(BOTH) == OidcSettings(
        issuer=GOOGLE_ISSUER,
        client_id=ID,
        client_secret=CREDENTIAL,
        redirect_uri="http://localhost:5173/api/auth/google/callback",
    )


def test_public_url_sets_the_redirect_uri() -> None:
    settings = google_settings({**BOTH, "TRIP_PUBLIC_URL": "http://127.0.0.1:5273/"})

    assert settings is not None
    assert settings.redirect_uri == "http://127.0.0.1:5273/api/auth/google/callback"


@pytest.mark.parametrize(
    ("present", "missing"),
    [
        ("TRIP_GOOGLE_CLIENT_ID", "TRIP_GOOGLE_CLIENT_SECRET"),
        ("TRIP_GOOGLE_CLIENT_SECRET", "TRIP_GOOGLE_CLIENT_ID"),
    ],
)
def test_half_configured_is_off_and_names_the_missing_variable(
    present: str, missing: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        assert google_settings({present: BOTH[present]}) is None

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert missing in logged
    assert ID not in logged
    assert CREDENTIAL not in logged


@pytest.mark.parametrize(
    "issuer", ["http://example.com", "http://127.0.0.1.example.com", "ftp://x"]
)
def test_refuses_an_issuer_that_is_neither_https_nor_local(issuer: str) -> None:
    with pytest.raises(InsecureIssuerError):
        google_settings({**BOTH, "TRIP_GOOGLE_ISSUER": issuer})


@pytest.mark.parametrize("issuer", ["http://127.0.0.1:8102", "http://localhost:8102/"])
def test_accepts_a_local_http_issuer_for_tests(issuer: str) -> None:
    settings = google_settings({**BOTH, "TRIP_GOOGLE_ISSUER": issuer})

    assert settings is not None
    assert settings.issuer == issuer.rstrip("/")
