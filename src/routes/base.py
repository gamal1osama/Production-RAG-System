from helpers.config import get_settings, Settings
from tasks.mail_service import send_report

from fastapi import FastAPI, APIRouter, Depends

from datetime import datetime
from time import sleep
import logging


logger = logging.getLogger("uvicorn.error")


base_router = APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)

@base_router.get("/")
async def welcome(app_settings: Settings = Depends(get_settings)):
    app_name = app_settings.APP_NAME
    app_version = app_settings.APP_VERSION

    return {
        "message": "Hello World!",
        "app_name": app_name,
        "app_version": app_version,
        "date_&_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }



@base_router.get("/send_reports")
async def send_reports(app_settings: Settings = Depends(get_settings)):
    
    task = send_report.delay(mail_wait_seconds=3)

    return {
        "success": "True",
        "task_id": task.id
    }
    