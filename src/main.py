from fastapi import FastAPI

from routes import base, data
from helpers.config import get_settings

from motor.motor_asyncio import AsyncIOMotorClient





app = FastAPI()


@app.on_event("startup")
async def startup_db_client():

    settings = get_settings()

    app.mongo_connection = AsyncIOMotorClient(settings.MONGODB_URL)
    app.db_client = app.mongo_connection[settings.MONGODB_DATABASE]


@app.on_event("shutdown")
async def shutdown_db_client():

    app.mongo_connection.close()




app.include_router(base.base_router)
app.include_router(data.data_router)



