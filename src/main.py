from fastapi import FastAPI

from routes import base, data, nlp
from helpers.config import get_settings
from stores.llm import LLMProviderFactory
from stores.vectordb import VectorDBProviderFactory
from stores.llm.templates import TemplateParser

from motor.motor_asyncio import AsyncIOMotorClient





app = FastAPI()


@app.on_event("startup")
async def startup_span():

    settings = get_settings()

    app.mongo_connection = AsyncIOMotorClient(settings.MONGODB_URL)
    app.db_client = app.mongo_connection[settings.MONGODB_DATABASE]

    llm_provider_factory = LLMProviderFactory(config=settings)
    vector_db_provider_factory = VectorDBProviderFactory(config=settings)

    
    # generation client
    app.generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    # embedding client
    app.embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, 
                                             embedding_size=settings.EMBEDDING_MODEL_SIZE)

    # vector db client
    app.vector_db_client = vector_db_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    app.vector_db_client.connect()

    # template parser
    app.template_parser = TemplateParser(language=settings.PRIMARY_LANGUAGE, default_language=settings.DEFAULT_LANGUAGE)



@app.on_event("shutdown")
async def shutdown_span():

    app.mongo_connection.close()
    app.vector_db_client.disconnect()





app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)



