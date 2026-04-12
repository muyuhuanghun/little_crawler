from __future__ import annotations

from celery.utils.log import get_task_logger

from app.celery_app import celery_app
from app.config import get_settings
from app.worker import process_next_queue_item_once


logger = get_task_logger(__name__)


@celery_app.task(
    name="app.celery_tasks.process_queue_batch",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_queue_batch(self: object, batch_size: int | None = None) -> dict[str, int]:
    settings = get_settings()
    normalized_batch_size = int(batch_size or settings.queue_batch_size)
    worked = 0
    for _ in range(max(1, normalized_batch_size)):
        if not process_next_queue_item_once():
            break
        worked += 1
    if worked:
        logger.info("processed queue batch: %s", worked)
    return {"processed": worked}


def enqueue_queue_drain() -> None:
    settings = get_settings()
    process_queue_batch.delay(int(settings.queue_batch_size))
