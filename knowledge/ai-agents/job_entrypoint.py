"""
Job entrypoint: run one workflow and exit.

Used when the app runs as an Azure Container Apps Job. Reads a single WorkflowEvent
from PAYLOAD_URL, WORKFLOW_EVENT_JSON, or PAYLOAD_B64; initializes the router;
runs router.route(event); exits with 0 or 1.

See docs/job-per-workflow.md for payload contract and deployment.
"""

import asyncio
import base64
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

# Ensure package root on path when run as script
if __name__ == "__main__":
    package_root = Path(__file__).resolve().parent.parent
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))

# Set job mode before loading config so validate() skips Service Bus
os.environ["RUN_AS_JOB"] = "true"

from app.config import Config
from app.models.workflow_event import WorkflowEvent

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging (mirror main.py)."""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)


def load_payload_json() -> str:
    """
    Load WorkflowEvent JSON from PAYLOAD_URL, WORKFLOW_EVENT_JSON, or PAYLOAD_B64.
    Returns the JSON string. Raises ValueError if none set or fetch fails.
    """
    url = os.environ.get("PAYLOAD_URL")
    if url:
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to fetch PAYLOAD_URL: {e}") from e

    raw = os.environ.get("WORKFLOW_EVENT_JSON")
    if raw:
        return raw

    b64 = os.environ.get("PAYLOAD_B64")
    if b64:
        try:
            return base64.b64decode(b64).decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decode PAYLOAD_B64: {e}") from e

    raise ValueError(
        "No payload source set. Set one of: PAYLOAD_URL, WORKFLOW_EVENT_JSON, PAYLOAD_B64"
    )


async def run_job() -> None:
    """Load payload, init router, run workflow, exit."""
    setup_logging()

    try:
        from app.main import setup_logfire
        setup_logfire()
    except Exception:
        pass

    logger.info("Job entrypoint starting (one workflow per run)")

    missing = Config.validate()
    if missing:
        logger.error("Missing required configuration: %s", ", ".join(missing))
        sys.exit(1)

    payload_str = None
    try:
        payload_str = load_payload_json()
    except ValueError as e:
        logger.error("%s", e)
        sys.exit(1)

    try:
        event = WorkflowEvent.from_json(payload_str)
    except (ValueError, json.JSONDecodeError) as e:
        logger.exception("Invalid WorkflowEvent payload: %s", e)
        sys.exit(1)

    logger.info(
        "Running workflow run_id=%s workflow_id=%s",
        event.run_id[:8] if event.run_id else "",
        event.workflow_id,
    )

    from app.main import initialize_router  # noqa: E402

    router = await initialize_router()
    result = await router.route(event)

    if result.success:
        logger.info(
            "Workflow succeeded run_id=%s duration=%.2fs",
            result.run_id,
            result.duration_seconds,
        )
        sys.exit(0)
    else:
        logger.error(
            "Workflow failed run_id=%s error=%s",
            result.run_id,
            result.error,
        )
        sys.exit(1)


def main() -> None:
    asyncio.run(run_job())


if __name__ == "__main__":
    main()
