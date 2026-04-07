from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

from ..config import Config
from .logger import get_logger

logger = get_logger("mirofish.distributed_execution")


def distributed_enabled() -> bool:
    return bool(Config.DISTRIBUTED_EXECUTION_ENABLED)


def worker_mode_enabled() -> bool:
    return bool(Config.SIMULATION_WORKER_MODE)


def _aws_kwargs() -> Dict[str, Any]:
    return {"region_name": Config.AWS_REGION or Config.COGNITO_REGION}


def _s3():
    return boto3.client("s3", **_aws_kwargs())


def _sqs():
    return boto3.client("sqs", **_aws_kwargs())


def _s3_prefix_for(simulation_id: str) -> str:
    base = (Config.S3_SIMULATION_PREFIX or "simulations").strip("/")
    return f"{base}/{simulation_id}/"


def _local_dir_for(simulation_id: str) -> str:
    return os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)


def s3_sync_enabled() -> bool:
    return bool(distributed_enabled() and Config.S3_SIMULATION_BUCKET)


def queue_enabled() -> bool:
    return bool(distributed_enabled() and Config.SQS_SIMULATION_START_QUEUE_URL)


def upload_simulation_artifacts(simulation_id: str) -> bool:
    if not s3_sync_enabled():
        return False
    local_dir = _local_dir_for(simulation_id)
    if not os.path.isdir(local_dir):
        return False

    bucket = Config.S3_SIMULATION_BUCKET
    prefix = _s3_prefix_for(simulation_id)
    uploaded = 0
    try:
        for root, _, files in os.walk(local_dir):
            for file_name in files:
                full_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(full_path, local_dir).replace("\\", "/")
                key = f"{prefix}{rel_path}"
                _s3().upload_file(full_path, bucket, key)
                uploaded += 1
    except ClientError as e:
        logger.error("S3 upload failed for %s: %s", simulation_id, e)
        return False
    if uploaded:
        logger.info("Uploaded %s artifact(s) to s3://%s/%s", uploaded, bucket, prefix)
    return uploaded > 0


def download_simulation_artifacts(simulation_id: str) -> bool:
    if not s3_sync_enabled():
        return False
    bucket = Config.S3_SIMULATION_BUCKET
    prefix = _s3_prefix_for(simulation_id)
    local_dir = _local_dir_for(simulation_id)
    os.makedirs(local_dir, exist_ok=True)

    downloaded = 0
    continuation_token = None
    try:
        while True:
            kwargs: Dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
            resp = _s3().list_objects_v2(**kwargs)
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                rel_path = key[len(prefix):]
                if not rel_path:
                    continue
                target = os.path.join(local_dir, rel_path)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                _s3().download_file(bucket, key, target)
                downloaded += 1
            if not resp.get("IsTruncated"):
                break
            continuation_token = resp.get("NextContinuationToken")
    except ClientError as e:
        logger.error("S3 download failed for %s: %s", simulation_id, e)
        return False
    return downloaded > 0


def enqueue_start_job(payload: Dict[str, Any]) -> str:
    if not queue_enabled():
        raise ValueError("Distributed queue is not configured.")
    queue_url = Config.SQS_SIMULATION_START_QUEUE_URL
    body = json.dumps(
        {
            **payload,
            "kind": "simulation_start",
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )
    resp = _sqs().send_message(QueueUrl=queue_url, MessageBody=body)
    return resp["MessageId"]
