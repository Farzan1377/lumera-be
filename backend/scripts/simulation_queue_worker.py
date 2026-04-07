"""
SQS worker for distributed simulation start jobs.

Usage:
  python backend/scripts/simulation_queue_worker.py

Required env:
  DISTRIBUTED_EXECUTION_ENABLED=true
  SIMULATION_WORKER_MODE=true
  SQS_SIMULATION_START_QUEUE_URL=...
"""

from __future__ import annotations

import json
import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.config import Config
from app.services.simulation_manager import SimulationManager, SimulationStatus
from app.services.simulation_runner import SimulationRunner
from app.utils.distributed_execution import download_simulation_artifacts
from app.utils.logger import get_logger
import boto3

logger = get_logger("mirofish.simulation_queue_worker")


def _sqs():
    return boto3.client("sqs", region_name=Config.AWS_REGION or Config.COGNITO_REGION)


def _validate():
    if not Config.DISTRIBUTED_EXECUTION_ENABLED:
        raise RuntimeError("DISTRIBUTED_EXECUTION_ENABLED must be true for queue worker.")
    if not Config.SIMULATION_WORKER_MODE:
        raise RuntimeError("SIMULATION_WORKER_MODE must be true for queue worker.")
    if not Config.SQS_SIMULATION_START_QUEUE_URL:
        raise RuntimeError("SQS_SIMULATION_START_QUEUE_URL is required.")


def _handle_start_job(body: dict):
    simulation_id = body.get("simulation_id")
    if not simulation_id:
        raise ValueError("Missing simulation_id in queue message.")

    platform = body.get("platform", "parallel")
    max_rounds = body.get("max_rounds")
    enable_graph_memory_update = bool(body.get("enable_graph_memory_update", False))
    graph_id = body.get("graph_id")

    download_simulation_artifacts(simulation_id)

    manager = SimulationManager()
    state = manager.get_simulation(simulation_id)
    if not state:
        raise ValueError(f"Simulation not found: {simulation_id}")

    run_state = SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        platform=platform,
        max_rounds=max_rounds,
        enable_graph_memory_update=enable_graph_memory_update,
        graph_id=graph_id,
    )
    state.status = SimulationStatus.RUNNING
    manager._save_simulation_state(state)
    logger.info(
        "Started simulation from queue: %s pid=%s",
        simulation_id,
        run_state.process_pid,
    )


def main():
    _validate()
    queue_url = Config.SQS_SIMULATION_START_QUEUE_URL
    poll_seconds = max(Config.SIMULATION_WORKER_POLL_SECONDS, 1)
    logger.info("Simulation queue worker started.")

    while True:
        try:
            resp = _sqs().receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=min(poll_seconds, 20),
                VisibilityTimeout=120,
            )
            msgs = resp.get("Messages", [])
            if not msgs:
                continue
            msg = msgs[0]
            receipt = msg["ReceiptHandle"]
            body = json.loads(msg.get("Body") or "{}")
            kind = body.get("kind")
            if kind != "simulation_start":
                logger.warning("Skipping unknown queue message kind=%s", kind)
                _sqs().delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
                continue

            _handle_start_job(body)
            _sqs().delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
        except Exception as e:
            logger.error("Worker loop error: %s", e)
            time.sleep(2)


if __name__ == "__main__":
    main()
