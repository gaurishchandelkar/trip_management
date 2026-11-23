import logging
from collections.abc import Mapping
from urllib.parse import urlsplit

from backend.identity.oidc import GOOGLE_ISSUER, OidcSettings

# Names of environment variables. The human sets their values; they never enter the repo.
CLIENT_ID_VAR = "TRIP_GOOGLE_CLIENT_ID"
CLIENT_CREDENTIAL_VAR = "TRIP_GOOGLE_CLIENT_SECRET"
ISSUER_VAR = "TRIP_GOOGLE_ISSUER"
PUBLIC_URL_VAR = "TRIP_PUBLIC_URL"
DEFAULT_PUBLIC_URL = "http://localhost:5173"
CALLBACK_PATH = "/api/auth/google/callback"
LOCAL_HOSTS = {"127.0.0.1", "localhost"}

logger = logging.getLogger(__name__)


class InsecureIssuerError(ValueError):
    def __init__(self) -> None:
        super().__init__(f"{ISSUER_VAR} must use https, or http on 127.0.0.1 or localhost.")


def google_settings(env: Mapping[str, str]) -> OidcSettings | None:
    """Google sign-in settings from the environment, or None when Google isn't configured."""
    client_id = env.get(CLIENT_ID_VAR, "")
    client_secret = env.get(CLIENT_CREDENTIAL_VAR, "")
    if not client_id or not client_secret:
        if client_id or client_secret:
            missing = CLIENT_CREDENTIAL_VAR if client_id else CLIENT_ID_VAR
            logger.warning("Google sign-in is off: %s isn't set", missing)
        return None
    issuer = (env.get(ISSUER_VAR) or GOOGLE_ISSUER).rstrip("/")
    parts = urlsplit(issuer)
    local = parts.scheme == "http" and parts.hostname in LOCAL_HOSTS
    if parts.scheme != "https" and not local:
        raise InsecureIssuerError
    public_url = (env.get(PUBLIC_URL_VAR) or DEFAULT_PUBLIC_URL).rstrip("/")
    return OidcSettings(
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=f"{public_url}{CALLBACK_PATH}",
    )
