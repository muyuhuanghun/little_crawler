from __future__ import annotations

from celery.utils.log import get_task_logger

from app.celery_app import celery_app
from app.config import get_settings
from app.worker import process_next_queue_item_once


logger = get_task_logger(__name__)
_SETTINGS = get_settings()


@celery_app.task(
    name="app.celery_tasks.process_queue_batch",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
    rate_limit=_SETTINGS.celery_queue_drain_rate_limit,
)
def process_queue_batch(self: object, batch_size: int | None = None) -> dict[str, int]:
    settings = get_settings()
    normalized_batch_size = int(batch_size or settings.queue_batch_size)
    dispatched = 0
    for _ in range(max(1, normalized_batch_size)):
        process_queue_item_once_task.delay()
        dispatched += 1
    if dispatched:
        logger.info("dispatched queue batch: %s", dispatched)
    return {"dispatched": dispatched}


@celery_app.task(
    name="app.celery_tasks.process_queue_item_once",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
    rate_limit=_SETTINGS.celery_item_rate_limit,
)
def process_queue_item_once_task(self: object) -> dict[str, int]:
    worked = 1 if process_next_queue_item_once() else 0
    if worked:
        logger.info("processed queue item")
    return {"processed": worked}


def process_queue_item_once() -> dict[str, int]:
    worked = 1 if process_next_queue_item_once() else 0
    return {"processed": worked}


def enqueue_queue_drain(batch_size: int | None = None) -> None:
    settings = get_settings()
    process_queue_batch.delay(int(batch_size or settings.queue_batch_size))


def enqueue_queue_item_once() -> None:
    process_queue_item_once_task.delay()


def drain_queue_inline(batch_size: int | None = None) -> dict[str, int]:
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
