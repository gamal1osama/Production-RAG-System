from celery import Celery
from helpers.config import get_settings


settings = get_settings()

# Celery app instance
celery_app = Celery(
    "ragsys",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Celery configuration update
celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=[settings.CELERY_TASK_SERIALIZER],

    # Late acknowledgment prevents task loss on worker crash
    task_acks_late=settings.CELERY_TASK_ACKS_LATE,
    
    # Time limits prevent hanging tasks
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,

    # result backend restore results for status tracking
    task_ignore_result=False,
    result_expires=3600,

    # worker settings
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,

    # Connection settings for better reliability
    broker_connnection_retry_on_startup=True,
    broker_connnection_retry=True,
    broker_connection_max_retries=10,
    worker_cancel_long_running_tasks_on_connection_loss=True,
)


celery_app.conf.task_default_queue = "default"
