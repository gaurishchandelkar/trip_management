import logging
from collections.abc import Mapping
from urllib.parse import urlsplit

import httpx2

from backend.identity.oidc import GOOGLE_ISSUER, OidcProvider, OidcSettings

# Names of environment variables. The human sets their values; they never enter the repo.
CLIENT_ID_VAR = "TRIP_GOOGLE_CLIENT_ID"
CLIENT_CREDENTIAL_VAR = "TRIP_GOOGLE_CLIENT_SECRET"
ISSUER_VAR = "TRIP_GOOGLE_ISSUER"
PUBLIC_URL_VAR = "TRIP_PUBLIC_URL"
DEFAULT_PUBLIC_URL = "http://localhost:5173"
CALLBACK_PATH = "/api/auth/google/callback"
LOCAL_HOSTS = {"127.0.0.1", "localhost"}

logger = logging.getLogger(__name__)


class InsecureUrlError(ValueError):
    def __init__(self, variable: str) -> None:
        super().__init__(f"{variable} must use https, or http on 127.0.0.1 or localhost.")


def _checked_url(variable: str, url: str) -> str:
    """The URL without a trailing slash. Raises InsecureUrlError unless it's https or local http."""
    parts = urlsplit(url)
    local = parts.scheme == "http" and parts.hostname in LOCAL_HOSTS
    if not parts.hostname or (parts.scheme != "https" and not local):
        raise InsecureUrlError(variable)
    return url.rstrip("/")


def google_provider(env: Mapping[str, str]) -> OidcProvider | None:
    """The Google provider, with its own HTTP client, or None when Google isn't configured."""
    settings = google_settings(env)
    return None if settings is None else OidcProvider("google", settings, httpx2.Client())


def google_settings(env: Mapping[str, str]) -> OidcSettings | None:
    """Google sign-in settings from the environment, or None when Google isn't configured."""
    client_id = env.get(CLIENT_ID_VAR, "")
    client_secret = env.get(CLIENT_CREDENTIAL_VAR, "")
    if not client_id or not client_secret:
        if client_id or client_secret:
            missing = CLIENT_CREDENTIAL_VAR if client_id else CLIENT_ID_VAR
            logger.warning("Google sign-in is off: %s isn't set", missing)
        return None
    issuer = _checked_url(ISSUER_VAR, env.get(ISSUER_VAR) or GOOGLE_ISSUER)
    return OidcSettings(
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=f"{public_url(env)}{CALLBACK_PATH}",
    )


def public_url(env: Mapping[str, str]) -> str:
    """Where people open the app, without a trailing slash. Raises InsecureUrlError at startup
    for a public http address, which would leave the session cookie without Secure."""
    return _checked_url(PUBLIC_URL_VAR, env.get(PUBLIC_URL_VAR) or DEFAULT_PUBLIC_URL)


def serves_https(env: Mapping[str, str]) -> bool:
    """True when people open the app over https, so its cookies must be Secure."""
    return urlsplit(public_url(env)).scheme == "https"
