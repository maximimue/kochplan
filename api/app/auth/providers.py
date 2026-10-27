"""Prüfung von Apple-/Google-ID-Tokens direkt gegen deren JWKS.
Kein Supabase/Firebase nötig: Client macht den nativen Sign-in, schickt das ID-Token,
der Server verifiziert Signatur, Issuer, Audience, Ablauf (und bei Apple die Nonce)
und stellt eigene Tokens aus."""
import hashlib
from dataclasses import dataclass

import jwt
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.errors import AppError

APPLE_JWKS = "https://appleid.apple.com/auth/keys"
APPLE_ISS = "https://appleid.apple.com"
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISS = ("https://accounts.google.com", "accounts.google.com")


@dataclass
class VerifiedIdentity:
    provider: str
    subject: str
    email: str | None


_jwk_clients: dict[str, jwt.PyJWKClient] = {}


def _jwk_client(url: str) -> jwt.PyJWKClient:
    if url not in _jwk_clients:
        _jwk_clients[url] = jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)
    return _jwk_clients[url]


async def _decode(token: str, jwks_url: str, audiences: list[str], issuers) -> dict:
    try:
        key = await run_in_threadpool(_jwk_client(jwks_url).get_signing_key_from_jwt, token)
        claims = jwt.decode(
            token, key.key, algorithms=["RS256"], audience=audiences,
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
        )
    except jwt.PyJWTError:
        raise AppError("invalid_token", 401)
    if claims["iss"] not in (issuers if isinstance(issuers, tuple) else (issuers,)):
        raise AppError("invalid_token", 401)
    return claims


async def verify_apple(id_token: str, raw_nonce: str | None) -> VerifiedIdentity:
    auds = get_settings().apple_audiences
    if not auds:
        raise AppError("provider_not_configured", 503, provider="Apple")
    claims = await _decode(id_token, APPLE_JWKS, auds, APPLE_ISS)
    if raw_nonce is not None:
        expected = hashlib.sha256(raw_nonce.encode()).hexdigest()
        if claims.get("nonce") != expected:
            raise AppError("invalid_token", 401)
    return VerifiedIdentity("apple", claims["sub"], claims.get("email"))


async def verify_google(id_token: str) -> VerifiedIdentity:
    auds = get_settings().google_audiences
    if not auds:
        raise AppError("provider_not_configured", 503, provider="Google")
    claims = await _decode(id_token, GOOGLE_JWKS, auds, GOOGLE_ISS)
    email = claims.get("email") if claims.get("email_verified") else None
    return VerifiedIdentity("google", claims["sub"], email)
