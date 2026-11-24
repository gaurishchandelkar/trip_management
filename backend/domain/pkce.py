"""Proof Key for Code Exchange (RFC 7636), S256 only."""

import base64
import hashlib
import secrets


def new_code_verifier() -> str:
    # 48 random bytes encode to 64 characters, inside RFC 7636's 43 to 128.
    return secrets.token_urlsafe(48)


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
