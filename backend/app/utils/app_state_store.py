"""
Shared DynamoDB store for API task status and simulation run_state snapshots.

Enables multiple Flask workers/processes to read consistent status without shared RAM.
Subprocess-based simulation still runs on one host; cross-instance stop/start is not solved here.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from ..config import Config
from .logger import get_logger

logger = get_logger("mirofish.app_state_store")

_client = None
_client_lock = threading.Lock()

ENTITY_TASK = "TASK"
ENTITY_RUN = "RUN"
PK_TASK = "TASK#"
PK_RUN = "RUN#"
# DynamoDB item size limit 400 KB; leave margin for attributes
_MAX_RUN_PAYLOAD_BYTES = 350_000


def _ddb():
    global _client
    with _client_lock:
        if _client is None:
            kwargs = {"region_name": Config.AWS_REGION or Config.COGNITO_REGION}
            if Config.AWS_DYNAMODB_ENDPOINT_URL:
                kwargs["endpoint_url"] = Config.AWS_DYNAMODB_ENDPOINT_URL
            _client = boto3.client("dynamodb", **kwargs)
    return _client


def app_state_enabled() -> bool:
    return bool(Config.DYNAMODB_APP_STATE_TABLE_NAME)


def _task_pk(task_id: str) -> str:
    return f"{PK_TASK}{task_id}"


def _run_pk(simulation_id: str) -> str:
    return f"{PK_RUN}{simulation_id}"


def _shrink_run_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    raw = json.dumps(data, ensure_ascii=False)
    if len(raw.encode("utf-8")) <= _MAX_RUN_PAYLOAD_BYTES:
        return data
    shrunk = dict(data)
    ra = shrunk.get("recent_actions") or []
    if isinstance(ra, list) and len(ra) > 30:
        shrunk["recent_actions"] = ra[:30]
    raw2 = json.dumps(shrunk, ensure_ascii=False)
    if len(raw2.encode("utf-8")) > _MAX_RUN_PAYLOAD_BYTES:
        shrunk.pop("recent_actions", None)
        shrunk["_truncated"] = True
    return shrunk


def put_run_state_payload(simulation_id: str, detail_dict: Dict[str, Any]) -> None:
    if not app_state_enabled():
        return
    table = Config.DYNAMODB_APP_STATE_TABLE_NAME
    payload = _shrink_run_payload(detail_dict)
    body = json.dumps(payload, ensure_ascii=False)
    try:
        _ddb().put_item(
            TableName=table,
            Item={
                "id": {"S": _run_pk(simulation_id)},
                "entity_type": {"S": ENTITY_RUN},
                "updated_at": {"S": datetime.now(timezone.utc).isoformat()},
                "payload": {"S": body},
            },
        )
    except ClientError as e:
        logger.error("DynamoDB put run state failed: %s", e)


def get_run_state_payload(simulation_id: str) -> Optional[Dict[str, Any]]:
    if not app_state_enabled():
        return None
    table = Config.DYNAMODB_APP_STATE_TABLE_NAME
    try:
        resp = _ddb().get_item(
            TableName=table,
            Key={"id": {"S": _run_pk(simulation_id)}},
            ProjectionExpression="payload",
        )
        item = resp.get("Item")
        if not item or "payload" not in item:
            return None
        return json.loads(item["payload"]["S"])
    except ClientError as e:
        logger.error("DynamoDB get run state failed: %s", e)
        return None
    except json.JSONDecodeError as e:
        logger.error("DynamoDB run state JSON invalid: %s", e)
        return None


def put_task_item(task_dict: Dict[str, Any]) -> None:
    if not app_state_enabled():
        return
    table = Config.DYNAMODB_APP_STATE_TABLE_NAME
    task_id = task_dict["task_id"]
    body = json.dumps(task_dict, ensure_ascii=False, default=str)
    try:
        _ddb().put_item(
            TableName=table,
            Item={
                "id": {"S": _task_pk(task_id)},
                "entity_type": {"S": ENTITY_TASK},
                "updated_at": {"S": task_dict.get("updated_at", "")},
                "payload": {"S": body},
            },
        )
    except ClientError as e:
        logger.error("DynamoDB put task failed: %s", e)


def get_task_item(task_id: str) -> Optional[Dict[str, Any]]:
    if not app_state_enabled():
        return None
    table = Config.DYNAMODB_APP_STATE_TABLE_NAME
    try:
        resp = _ddb().get_item(
            TableName=table,
            Key={"id": {"S": _task_pk(task_id)}},
            ProjectionExpression="payload",
        )
        item = resp.get("Item")
        if not item or "payload" not in item:
            return None
        return json.loads(item["payload"]["S"])
    except ClientError as e:
        logger.error("DynamoDB get task failed: %s", e)
        return None
    except json.JSONDecodeError as e:
        logger.error("DynamoDB task JSON invalid: %s", e)
        return None


def scan_tasks(task_type: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    if not app_state_enabled():
        return []
    table = Config.DYNAMODB_APP_STATE_TABLE_NAME
    out: List[Dict[str, Any]] = []
    try:
        scan_kwargs: Dict[str, Any] = {
            "TableName": table,
            "FilterExpression": "entity_type = :e",
            "ExpressionAttributeValues": {":e": {"S": ENTITY_TASK}},
        }
        pages = 0
        while len(out) < limit and pages < 50:
            pages += 1
            resp = _ddb().scan(**scan_kwargs)
            for it in resp.get("Items", []):
                pl = it.get("payload", {}).get("S")
                if not pl:
                    continue
                try:
                    d = json.loads(pl)
                    if task_type and d.get("task_type") != task_type:
                        continue
                    out.append(d)
                    if len(out) >= limit:
                        break
                except json.JSONDecodeError:
                    continue
            lek = resp.get("LastEvaluatedKey")
            if not lek or len(out) >= limit:
                break
            scan_kwargs["ExclusiveStartKey"] = lek
    except ClientError as e:
        logger.error("DynamoDB scan tasks failed: %s", e)
    out.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return out[:limit]
