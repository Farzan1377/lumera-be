"""
Register JWT validation on API blueprints (Bearer token).
"""

from __future__ import annotations

from flask import g, jsonify, request

from ..config import Config
from .cognito import decode_and_verify_cognito_token, get_user_sub_from_claims


def _extract_bearer_token() -> str | None:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def authenticate_api_request():
    """
    before_request handler: validate Bearer JWT and set g.user_sub.
    Returns None to continue, or (response, status) tuple to abort.
    """
    if not Config.AUTH_ENABLED:
        return None
    if request.method == "OPTIONS":
        return None
    token = _extract_bearer_token()
    if not token:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Missing or invalid Authorization header",
                    "error_code": "UNAUTHORIZED",
                }
            ),
            401,
        )
    claims, err = decode_and_verify_cognito_token(token)
    if err or not claims:
        return (
            jsonify(
                {
                    "success": False,
                    "error": err or "Unauthorized",
                    "error_code": "UNAUTHORIZED",
                }
            ),
            401,
        )
    sub = get_user_sub_from_claims(claims)
    if not sub:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Token missing sub",
                    "error_code": "UNAUTHORIZED",
                }
            ),
            401,
        )
    g.user_sub = sub
    g.cognito_claims = claims
    return None


def register_api_auth(_app=None):
    from ..api import graph_bp, simulation_bp, report_bp

    graph_bp.before_request(authenticate_api_request)
    simulation_bp.before_request(authenticate_api_request)
    report_bp.before_request(authenticate_api_request)
