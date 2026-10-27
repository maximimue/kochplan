import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import providers
from app.config import get_settings
from app.errors import AppError


class FakeJWK:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, token):
        return self


@pytest.fixture
def rsa_key(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(providers, "_jwk_client", lambda url: FakeJWK(key.public_key()))
    monkeypatch.setattr(get_settings(), "google_audiences", ["my-client-id"])
    return key


def _token(key, **over):
    now = int(time.time())
    claims = {"iss": "https://accounts.google.com", "aud": "my-client-id", "sub": "123",
              "email": "a@b.de", "email_verified": True, "iat": now, "exp": now + 600, **over}
    return jwt.encode(claims, key, algorithm="RS256")


async def test_google_valid(rsa_key):
    ident = await providers.verify_google(_token(rsa_key))
    assert (ident.provider, ident.subject, ident.email) == ("google", "123", "a@b.de")


@pytest.mark.parametrize("over", [{"aud": "fremde-app"}, {"iss": "https://evil.example"}, {"exp": int(time.time()) - 10}])
async def test_google_rejects(rsa_key, over):
    with pytest.raises(AppError):
        await providers.verify_google(_token(rsa_key, **over))
