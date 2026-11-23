"""A stand-in for Google's OpenID Connect provider, for the E2E tests only.

The backend under test talks to it exactly as it talks to Google: discovery, an authorization
page, the token endpoint and the signing keys. It signs real RS256 ID tokens with a key made at
startup, checks the client, the redirect URI and the PKCE verifier, and lets a test approve or
cancel. Instead of Google's consent screen it shows a small form: an account ID and a name.

Started by e2e/conftest.py on 127.0.0.1 with FAKE_GOOGLE_ISSUER, FAKE_GOOGLE_CLIENT_ID and
FAKE_GOOGLE_CLIENT_SECRET in its environment. It keeps its codes in memory.
"""

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from html import escape
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from joserfc import jwt
from joserfc.jwk import RSAKey

ISSUER = os.environ.get("FAKE_GOOGLE_ISSUER", "http://127.0.0.1:8102")
CLIENT_ID = os.environ.get("FAKE_GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("FAKE_GOOGLE_CLIENT_SECRET", "")
CALLBACK_PATH = "/api/auth/google/callback"
TOKEN_LIFETIME_S = 3600

KEY = RSAKey.generate_key(2048, parameters={"kid": "fake-google-1", "alg": "RS256"}, private=True)

app = FastAPI(title="Fake Google")


@dataclass(frozen=True)
class Grant:
    subject: str
    name: str
    nonce: str
    code_challenge: str
    redirect_uri: str


GRANTS: dict[str, Grant] = {}


def _local_callback(redirect_uri: str) -> bool:
    parts = urlsplit(redirect_uri)
    return (
        parts.scheme == "http"
        and parts.hostname == "127.0.0.1"
        and parts.path == CALLBACK_PATH
        and not parts.query
    )


def _bad_request(error: str) -> JSONResponse:
    return JSONResponse({"error": error}, status_code=400)


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@app.get("/.well-known/openid-configuration")
def discovery() -> dict[str, str]:
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/jwks",
    }


@app.get("/jwks")
def jwks() -> dict[str, object]:
    return {"keys": [KEY.as_dict(private=False)]}


AUTHORIZE_PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Fake Google sign-in</title></head>
<body>
<main>
<h1>Fake Google sign-in</h1>
<form action="/decide" method="get" aria-label="Choose an account">
{hidden}
<p><label for="subject">Account ID</label> <input id="subject" name="subject" required></p>
<p><label for="name">Name</label> <input id="name" name="name"></p>
<p>
<button type="submit" name="decision" value="allow">Continue</button>
<button type="submit" name="decision" value="deny" formnovalidate>Cancel</button>
</p>
</form>
</main>
</body>
</html>
"""


@app.get("/authorize", response_model=None)
def authorize(
    response_type: str = "",
    client_id: str = "",
    redirect_uri: str = "",
    scope: str = "",
    state: str = "",
    nonce: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
) -> HTMLResponse | JSONResponse:
    checks = (
        response_type == "code",
        client_id == CLIENT_ID,
        _local_callback(redirect_uri),
        set(scope.split()) == {"openid", "profile", "email"},
        bool(state and nonce and code_challenge),
        code_challenge_method == "S256",
    )
    if not all(checks):
        return _bad_request("invalid_request")
    carried = {
        "redirect_uri": redirect_uri,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
    }
    hidden = "\n".join(
        f'<input type="hidden" name="{name}" value="{escape(value, quote=True)}">'
        for name, value in carried.items()
    )
    return HTMLResponse(AUTHORIZE_PAGE.format(hidden=hidden))


@app.get("/decide", response_model=None)
def decide(
    redirect_uri: str = "",
    state: str = "",
    nonce: str = "",
    code_challenge: str = "",
    subject: str = "",
    name: str = "",
    decision: str = "",
) -> RedirectResponse | JSONResponse:
    if not _local_callback(redirect_uri):
        return _bad_request("invalid_request")
    if decision != "allow":
        query = urlencode({"error": "access_denied", "state": state})
        return RedirectResponse(f"{redirect_uri}?{query}", status_code=302)
    if not subject:
        return _bad_request("invalid_request")
    code = secrets.token_urlsafe(24)
    GRANTS[code] = Grant(subject, name, nonce, code_challenge, redirect_uri)
    return RedirectResponse(f"{redirect_uri}?{urlencode({'code': code, 'state': state})}", 302)


@app.post("/token", response_model=None)
async def token(request: Request) -> dict[str, object] | JSONResponse:
    form = {key: values[0] for key, values in parse_qs((await request.body()).decode()).items()}
    client_ok = form.get("client_id") == CLIENT_ID and hmac.compare_digest(
        form.get("client_secret", ""), CLIENT_SECRET
    )
    if not client_ok:
        return _bad_request("invalid_client")
    grant = GRANTS.pop(form.get("code", ""), None)
    if (
        form.get("grant_type") != "authorization_code"
        or grant is None
        or form.get("redirect_uri") != grant.redirect_uri
        or _s256(form.get("code_verifier", "")) != grant.code_challenge
    ):
        return _bad_request("invalid_grant")
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "sub": grant.subject,
        "email": f"{grant.subject}@example.com",
        "nonce": grant.nonce,
        "iat": now,
        "exp": now + TOKEN_LIFETIME_S,
    }
    if grant.name:
        claims["name"] = grant.name
    id_token = jwt.encode({"alg": "RS256", "kid": KEY.kid}, claims, KEY)
    return {
        "access_token": secrets.token_urlsafe(24),
        "token_type": "Bearer",
        "expires_in": TOKEN_LIFETIME_S,
        "id_token": id_token,
    }
