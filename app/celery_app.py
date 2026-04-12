from __future__ import annotations

from celery import Celery

from app.config import get_settings


settings = get_settings()

celery_app = Celery(
    "pyms",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.celery_tasks"],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="pyms-default",
    beat_schedule={
        "pyms-queue-drain": {
            "task": "app.celery_tasks.process_queue_batch",
            "schedule": float(settings.queue_poll_interval_seconds),
            "args": (int(settings.queue_batch_size),),
        }
    },
)
