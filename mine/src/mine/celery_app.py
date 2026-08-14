from celery import Celery

from mine.config import settings

celery = Celery(
    "mine",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "mine.tasks.tag_article": {"queue": "tagging"},
    },
    beat_schedule={
        "dispatch-crawl-all": {
            "task": "mine.tasks.crawl_dispatch",
            "schedule": 300.0,  # every 5 minutes, check which sources need crawling
        },
        "twitter-health-check": {
            "task": "mine.tasks.twitter_health_check",
            "schedule": 1800.0,  # every 30 minutes, check Twitter cookie health
        },
    },
)

celery.autodiscover_tasks(["mine.tasks"])
