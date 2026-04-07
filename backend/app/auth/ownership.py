"""
DynamoDB lookup: partition key equals resource id (project, graph, or simulation),
attribute userSub must match the authenticated Cognito sub.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger("mirofish.auth.ownership")

_client = None
_client_lock = threading.Lock()


def _ddb_client():
    global _client
    with _client_lock:
        if _client is None:
            kwargs = {"region_name": Config.AWS_REGION or Config.COGNITO_REGION}
            if Config.AWS_DYNAMODB_ENDPOINT_URL:
                kwargs["endpoint_url"] = Config.AWS_DYNAMODB_ENDPOINT_URL
            _client = boto3.client("dynamodb", **kwargs)
    return _client


def _partition_key_attr(kind: str) -> str:
    if kind == "simulation":
        return Config.AUTH_DYNAMODB_SIMULATION_PK_ATTRIBUTE or Config.AUTH_DYNAMODB_PK_ATTRIBUTE
    if kind == "project":
        return Config.AUTH_DYNAMODB_PROJECT_PK_ATTRIBUTE or Config.AUTH_DYNAMODB_PK_ATTRIBUTE
    if kind == "graph":
        return Config.AUTH_DYNAMODB_GRAPH_PK_ATTRIBUTE or Config.AUTH_DYNAMODB_PK_ATTRIBUTE
    return Config.AUTH_DYNAMODB_PK_ATTRIBUTE


def user_owns_resource(user_sub: str, resource_id: str, *, kind: str = "default") -> bool:
    """
    True if a table row exists with partition key = resource_id and userSub == user_sub.
    kind selects which DynamoDB partition key attribute name to use (simulation / project / graph).
    """
    if not resource_id:
        return False
    pk_attr = _partition_key_attr(kind)
    user_attr = Config.AUTH_DYNAMODB_USER_SUB_ATTRIBUTE
    table = Config.AUTH_DYNAMODB_TABLE_NAME
    try:
        resp = _ddb_client().get_item(
            TableName=table,
            Key={pk_attr: {"S": str(resource_id)}},
            ProjectionExpression=f"{user_attr}, {pk_attr}",
        )
        item = resp.get("Item")
        if not item:
            return False
        owner = item.get(user_attr, {}).get("S")
        return owner == user_sub
    except ClientError as e:
        logger.error("DynamoDB get_item failed: %s", e)
        return False
