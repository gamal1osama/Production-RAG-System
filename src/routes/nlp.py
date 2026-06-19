from fastapi import FastAPI, APIRouter, Request, status
from fastapi.responses import JSONResponse

from tasks.data_indexing import index_data

from .schemas.nlp import PushRequest, SearchRequest
from models import ProjectModel, ChunkModel, ResponseSignal
from controllers import NLPController
from tqdm.auto import tqdm

import logging



logger = logging.getLogger("uvicorn.error")




nlp_router = APIRouter(
    prefix="/api/v1/nlp", 
    tags=["api_v1", "nlp"]
)




@nlp_router.post("/index/push/{project_id}")
async def index_project(project_id: int, request: Request, push_request: PushRequest):
    
    task = index_data.delay(project_id=project_id, do_reset=push_request.do_reset)
    
    return JSONResponse(
        content={
            "signal": ResponseSignal.DATA_PUSHING_STARTED.value,
            "task_id": task.id
        }
    )


@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(project_id: int, request: Request):
    
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=project_id)


    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )    


    collection_info = await nlp_controller.get_vector_db_collection_info(project=project)

    return JSONResponse(
        content={
            "signal": ResponseSignal.GETTING_VECTOR_DB_COLLECTION_INFO_SUCCESS.value,
            "collection_info": collection_info
        }
    )


@nlp_router.post("/index/search/{project_id}")
async def search_index(project_id: int, request: Request, search_request: SearchRequest):
    
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=project_id)


    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )    

    results = await nlp_controller.search_vector_db_collection(
        project=project,
        text=search_request.text,
        limit=search_request.limit
    )

    if not results:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            content={
                "signal": ResponseSignal.SEARCHING_VECTOR_DB_COLLECTION_FAILED.value
            }
        )
    
    return JSONResponse(
        content={
            "signal": ResponseSignal.SEARCHING_VECTOR_DB_COLLECTION_SUCCESS.value,
            "results": [result.dict() for result in results]
        }
    )


@nlp_router.post("/index/answer/{project_id}")
async def answer_query(project_id: int, request: Request, search_request: SearchRequest):
    
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=project_id)

    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )


    answer, full_prompt, chat_history = await nlp_controller.answer_rag_query(
        project=project,
        query=search_request.text,
        limit=search_request.limit
    )

    if not answer:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            content={
                "signal": ResponseSignal.ANSWERING_RAG_QUERY_FAILED.value
            }
        )
    
    return JSONResponse(
        content={
            "signal": ResponseSignal.ANSWERING_RAG_QUERY_SUCCESS.value,
            "answer": answer,
            "full_prompt": full_prompt,
            "chat_history": chat_history
        }
    )
