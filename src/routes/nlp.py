from fastapi import FastAPI, APIRouter, Request, status
from fastapi.responses import JSONResponse

from .schemas.nlp import PushRequest, SearchRequest
from models import ProjectModel, ChunkModel, ResponseSignal
from controllers import NLPController

import logging



logger = logging.getLogger(__name__)




nlp_router = APIRouter(
    prefix="/api/v1/nlp", 
    tags=["api_v1", "nlp"]
)




@nlp_router.post("/index/push/{project_id}")
async def index_project(project_id: int, request: Request, push_request: PushRequest):
    

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=project_id)


    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, 
            content={
                "signal": ResponseSignal.PROJECT_NOT_FOUND.value
            }
        )


    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )



    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)
    
    has_records, page_no, inserted_items_cnt, idx = True, 1, 0, 0
    while has_records:
        page_chunks = await chunk_model.get_project_chunks(
            project_id=project.project_id, 
            page_no=page_no, 
            page_size=100
        )

        if len(page_chunks):
            page_no += 1
        else:
            has_records = False
            break

        chunks_ids = [str(chunk_id) for chunk_id in range(idx, idx + len(page_chunks))]
        idx += len(page_chunks)

        is_inserted = nlp_controller.index_into_db(
            project=project,
            chunks=page_chunks,
            do_reset=push_request.do_reset,
            chunks_ids=chunks_ids
        )
        if not is_inserted:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                content={
                    "signal": ResponseSignal.INSERTING_CHUNKS_INTO_DB_FAILED.value
                }
            )
        
        inserted_items_cnt += len(page_chunks)
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseSignal.INSERTING_CHUNKS_INTO_DB_SUCCESS.value,
            "inserted_items_count": inserted_items_cnt
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


    collection_info = nlp_controller.get_vector_db_collection_info(project=project)

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

    results = nlp_controller.search_vector_db_collection(
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


    answer, full_prompt, chat_history = nlp_controller.answer_rag_query(
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
