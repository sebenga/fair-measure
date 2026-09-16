"""Authentication services: Google identity verification and account linking."""

from __future__ import annotations

import logging

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from jwt import PyJWKClient
from rest_framework.exceptions import AuthenticationFailed

from .models import SocialAccount

logger = logging.getLogger(__name__)
User = get_user_model()

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

# PyJWKClient caches the signing keys, so this is one network call per rotation
# rather than one per login.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, lifespan=3600)
    return _jwks_client


def verify_google_id_token(id_token: str) -> dict:
    """Validate a Google ID token's signature, audience and issuer.

    Verifying the signature locally against Google's JWKS avoids trusting an
    unauthenticated `tokeninfo` round trip on every sign-in.
    """

    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise AuthenticationFailed("Google sign-in is not configured on this server.")

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_OAUTH_CLIENT_ID,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.PyJWTError as exc:
        logger.info("Rejected Google ID token: %s", exc)
        raise AuthenticationFailed("Invalid Google credentials.") from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise AuthenticationFailed("Invalid Google credentials.")

    return claims


@transaction.atomic
def get_or_create_user_from_google(claims: dict) -> tuple[User, bool]:
    """Resolve a Google identity to a local user, creating or linking as needed."""

    subject = claims["sub"]
    email = (claims.get("email") or "").lower()

    social = (
        SocialAccount.objects.select_related("user")
        .filter(provider=SocialAccount.Provider.GOOGLE, provider_user_id=subject)
        .first()
    )
    if social:
        return social.user, False

    if not email:
        raise AuthenticationFailed("Google account did not provide an email address.")

    # Only link to an existing local account when Google vouches for the email;
    # otherwise an unverified Google address could take over someone's account.
    user = User.objects.filter(email__iexact=email).first()
    created = False
    if user is None:
        user = User.objects.create_user(
            email=email,
            password=None,
            display_name=claims.get("name", ""),
            avatar_url=claims.get("picture", ""),
            email_verified=bool(claims.get("email_verified")),
        )
        created = True
    elif not claims.get("email_verified"):
        raise AuthenticationFailed(
            "An account with this email already exists. Sign in with your password."
        )

    SocialAccount.objects.create(
        user=user,
        provider=SocialAccount.Provider.GOOGLE,
        provider_user_id=subject,
        raw_profile=claims,
    )
    return user, created
