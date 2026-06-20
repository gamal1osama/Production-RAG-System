from celery_app import celery_app, get_setup_utils
from helpers.config import get_settings
from utils.idempotency_manager import IdempotencyManager

import asyncio


import logging



logger = logging.getLogger('celery.task')






@celery_app.task(bind=True, name="tasks.maintenance.cleanup_celery_executions_table",
                 autoretry_for=(Exception,),
                 retry_kwargs={'max_retries': 3, 'countdown': 60})
def cleanup_celery_executions_table(self):

    return asyncio.run(_cleanup_celery_executions_table(self))



async def _cleanup_celery_executions_table(task_instance):
    

    db_engine, vector_db_client = None, None
    try:

        (db_engine, db_client, generation_client, 
        embedding_client, vector_db_client, template_parser) = await get_setup_utils()

        idempotency_manager = IdempotencyManager(db_client=db_client, db_engine=db_engine)


        _ = await idempotency_manager.cleanup_old_tasks()

        return True


    except Exception as e:

        logger.error(f"Task cleanup failed: {str(e)}")
        raise

    finally:
        try:    
            if db_engine:
                await db_engine.dispose()
            if vector_db_client:
                await vector_db_client.disconnect()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
