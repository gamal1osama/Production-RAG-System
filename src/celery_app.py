from celery import Celery
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from helpers.config import get_settings
from stores.llm import LLMProviderFactory
from stores.vectordb import VectorDBProviderFactory
from stores.llm.templates import TemplateParser









settings = get_settings()

# Celery app instance
celery_app = Celery(
    "ragsys",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "tasks.file_processing",
        "tasks.data_indexing",
        "tasks.process_and_push_workflow",
        "tasks.maintenance",
    ]
)

async def get_setup_utils():

    settings = get_settings()

    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DB}"
    db_engine = create_async_engine(postgres_conn)
    db_client = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


    llm_provider_factory = LLMProviderFactory(config=settings)
    vector_db_provider_factory = VectorDBProviderFactory(config=settings, db_client=db_client)

    
    # generation client
    generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    # embedding client
    embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, 
                                             embedding_size=settings.EMBEDDING_MODEL_SIZE)

    # vector db client
    vector_db_client = vector_db_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    await vector_db_client.connect()

    # template parser
    template_parser = TemplateParser(language=settings.PRIMARY_LANGUAGE, default_language=settings.DEFAULT_LANGUAGE)

    return (
        db_engine,
        db_client,
        generation_client,
        embedding_client,
        vector_db_client,
        template_parser
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
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    worker_cancel_long_running_tasks_on_connection_loss=True,

    task_routes={
        "tasks.file_processing.process_files": {"queue": "file_processing_queue"},
        "tasks.data_indexing.index_data": {"queue": "data_indexing_queue"},
        "tasks.process_and_push_workflow.process_and_push_workflow": {"queue": "process_and_push_workflow_queue"},
        "tasks.maintenance.cleanup_celery_executions_table": {"queue": "default"},
    },

    beat_schedule={
        "cleanup_celery_executions_table": {
            "task": "tasks.maintenance.cleanup_celery_executions_table",
            "schedule": 10.0,  # every 24 hour     
            "args": (),  # no arguments
        }
    },

    timezone='UTC',

)


celery_app.conf.task_default_queue = "default"
