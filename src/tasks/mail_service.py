from celery_app import celery_app
from helpers.config import get_settings

from time import sleep
from datetime import datetime

import logging
import asyncio



logger = logging.getLogger("celery.task")




@celery_app.task(bind=True, name="tasks.mail_service.send_report")
def send_report(self, mail_wait_seconds: int):
    
    return asyncio.run(_send_report(self, mail_wait_seconds))




async def _send_report(task_instance, mail_wait_seconds):
    
    started_at = str(datetime.now())
    task_instance.update_state(
        state="PROGRESS", 
        meta={
            "started_at": started_at,
        }
    )

    for ix in range(15):
        logger.info(f"Sending report {ix+1}...")
        await asyncio.sleep(mail_wait_seconds)  # Simulate time-consuming task


    return {  # that what stored in the result backend
        "no_emails": 15,
        "ended_at": str(datetime.now()),
    }

