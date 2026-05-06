from fastapi import FastAPI, APIRouter, Request, status
from fastapi.responses import JSONResponse

from .schemas.nlp import PushRequest
from models import ProjectModel, ChunkModel, ResponseSignal
from controllers import NLPController

import logging



logger = logging.getLogger(__name__)




nlp_router = APIRouter(
    prefix="/api/v1/nlp", 
    tags=["api_v1", "nlp"]
)




@nlp_router.post("/index/push/{project_id}")
async def index_project(project_id: str, request: Request, push_request: PushRequest):
    

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
        embedding_client=request.app.embedding_client
    )



    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)
    
    has_records, page_no, inserted_items_cnt, idx = True, 1, 0, 0
    while has_records:
        page_chunks = await chunk_model.get_project_chunks(
            project_id=project.id, 
            page_no=page_no, 
            page_size=100
        )

        if len(page_chunks):
            page_no += 1
        elif not page_chunks or len(page_chunks) == 0:
            has_records = False

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
