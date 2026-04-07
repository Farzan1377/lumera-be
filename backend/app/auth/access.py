"""
Flask helpers: map HTTP errors to ownership checks against DynamoDB.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from flask import jsonify

from ..config import Config
from ..models.task import Task
from ..services.report_agent import ReportManager
from .ownership import user_owns_resource

JsonResponse = Tuple[dict, int]


def _forbidden() -> JsonResponse:
    return (
        {"success": False, "error": "Forbidden", "error_code": "FORBIDDEN"},
        403,
    )


def _not_found() -> JsonResponse:
    return (
        {"success": False, "error": "Not found", "error_code": "NOT_FOUND"},
        404,
    )


def filter_owned_ids(
    user_sub: str, resource_ids: Iterable[str], *, kind: str = "default"
) -> List[str]:
    """Keep only ids present in DynamoDB with matching userSub."""
    return [
        rid
        for rid in resource_ids
        if rid and user_owns_resource(user_sub, rid, kind=kind)
    ]


def ensure_project_owned(user_sub: str, project_id: str) -> Optional[JsonResponse]:
    if not Config.AUTH_ENABLED:
        return None
    if user_owns_resource(user_sub, project_id, kind="project"):
        return None
    return _forbidden()


def ensure_graph_owned(user_sub: str, graph_id: str) -> Optional[JsonResponse]:
    if not Config.AUTH_ENABLED:
        return None
    if user_owns_resource(user_sub, graph_id, kind="graph"):
        return None
    return _forbidden()


def ensure_simulation_owned(user_sub: str, simulation_id: str) -> Optional[JsonResponse]:
    if not Config.AUTH_ENABLED:
        return None
    if user_owns_resource(user_sub, simulation_id, kind="simulation"):
        return None
    return _forbidden()


def ensure_report_id_owned(user_sub: str, report_id: str) -> Optional[JsonResponse]:
    if not Config.AUTH_ENABLED:
        return None
    report = ReportManager.get_report(report_id)
    if not report:
        return _not_found()
    return ensure_simulation_owned(user_sub, report.simulation_id)


def ensure_task_owned(user_sub: str, task: Optional[Task]) -> Optional[JsonResponse]:
    if not Config.AUTH_ENABLED:
        return None
    if task is None:
        return _not_found()
    meta = task.metadata or {}
    if meta.get("simulation_id"):
        return ensure_simulation_owned(user_sub, meta["simulation_id"])
    if meta.get("project_id"):
        return ensure_project_owned(user_sub, meta["project_id"])
    if meta.get("graph_id"):
        return ensure_graph_owned(user_sub, str(meta["graph_id"]))
    return _forbidden()


def jsonify_error(response: JsonResponse):
    body, status = response
    return jsonify(body), status
