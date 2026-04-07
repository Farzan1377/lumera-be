"""
Validate AWS Cognito JWTs (RS256) using the pool JWKS.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Tuple

import jwt
from jwt import PyJWKClient

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger("mirofish.auth.cognito")

_jwks_client: Optional[PyJWKClient] = None
_jwks_lock = threading.Lock()
_jwks_url: Optional[str] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client, _jwks_url
    pool_id = Config.COGNITO_USER_POOL_ID
    region = Config.COGNITO_REGION
    url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    with _jwks_lock:
        if _jwks_client is None or _jwks_url != url:
            _jwks_url = url
            _jwks_client = PyJWKClient(
                url,
                cache_keys=True,
                max_cached_keys=16,
                lifespan=Config.COGNITO_JWKS_CACHE_SECONDS,
            )
    return _jwks_client


def _issuer() -> str:
    region = Config.COGNITO_REGION
    pool_id = Config.COGNITO_USER_POOL_ID
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"


def decode_and_verify_cognito_token(token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Returns (claims, error_message). claims is None on failure.
    Supports Cognito ID tokens (token_use=id, aud) and access tokens (token_use=access, client_id).
    """
    try:
        jwks = _get_jwks_client()
        signing_key = jwks.get_signing_key_from_jwt(token)
        issuer = _issuer()

        unverified = jwt.decode(token, options={"verify_signature": False})
        token_use = unverified.get("token_use")

        if token_use == "access":
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=issuer,
                options={"verify_aud": False},
            )
            if payload.get("client_id") != Config.COGNITO_APP_CLIENT_ID:
                return None, "Invalid token client_id"
        elif token_use == "id":
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=issuer,
                audience=Config.COGNITO_APP_CLIENT_ID,
            )
        else:
            return None, "Invalid or missing token_use"

        sub = payload.get("sub")
        if not sub:
            return None, "Token missing sub"
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token expired"
    except jwt.InvalidTokenError as e:
        logger.warning("JWT validation failed: %s", e)
        return None, "Invalid token"
    except Exception as e:
        logger.exception("Unexpected error validating JWT")
        return None, str(e)


def get_user_sub_from_claims(claims: Dict[str, Any]) -> Optional[str]:
    sub = claims.get("sub")
    return str(sub) if sub else None
