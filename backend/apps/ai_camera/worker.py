"""Background worker entrypoint for AI camera jobs (Render worker service).

Uses the same Redis/Valkey as the web service. Wire RQ/Celery later; for now a
simple loop can call `process_recording` for queued MatchRecording rows.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger("ai_camera.worker")


def run_forever(poll_seconds: int = 5) -> None:
    import django

    django.setup()
    from .models import MatchRecording
    from .services import process_recording

    logger.info("AI camera worker started")
    while True:
        ready = list(
            MatchRecording.objects.filter(status=MatchRecording.Status.READY).order_by("created_at")[
                :5
            ]
        )
        for recording in ready:
            try:
                process_recording(recording)
                logger.info("processed recording %s", recording.id)
            except Exception:  # noqa: BLE001
                logger.exception("failed recording %s", recording.id)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
