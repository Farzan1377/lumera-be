"""
Authentication and resource ownership (Cognito JWT + DynamoDB).
"""

from .flask_hooks import register_api_auth
from .access import (
    ensure_project_owned,
    ensure_graph_owned,
    ensure_simulation_owned,
    ensure_report_id_owned,
    ensure_task_owned,
    filter_owned_ids,
    jsonify_error,
)

__all__ = [
    "register_api_auth",
    "ensure_project_owned",
    "ensure_graph_owned",
    "ensure_simulation_owned",
    "ensure_report_id_owned",
    "ensure_task_owned",
    "filter_owned_ids",
    "jsonify_error",
]
