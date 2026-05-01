import os
import aiofiles
import logging

from helpers.config import get_settings, Settings
from controllers import DataController, ProcessController
from models import ResponseSignal, ProjectModel, ChunkModel, AssetModel
from models.db_schemas import DataChunk, Asset
from models.enums import AssetTypeEnum
from .schemas.data import ProcessRequest

from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse



logger = logging.getLogger('uvicorn.error')




data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)

@data_router.post("/upload/{project_id}")
async def upload_data(request: Request, project_id: str, file: UploadFile, 
                      app_settings: Settings = Depends(get_settings)):
    
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=project_id)


    # validate the uploaded file
    data_controller = DataController()
    is_valid, message = data_controller.validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal":message
            }
        )
    
    # Save the file to the specified directory
    file_path, file_id = data_controller.generate_unique_filename_path(original_filename=file.filename, project_id=project_id)

    try:
        async with aiofiles.open(file_path, 'wb') as f: # open for wring in binary mode
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE): # read the file in chunks
                await f.write(chunk) # write the chunk to the file
    except Exception as e:
        logger.error(f"Error while uploading file: {e}")
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal":ResponseSignal.FILE_UPLOAD_FAILED.value,
            }
        )
    


    # store the assets into the database
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)

    asset_resource = Asset(
        asset_project_id = project.id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=file_id,
        asset_size=os.path.getsize(file_path)
    )

    assert_record = await asset_model.create_asset(asset=asset_resource)

    return JSONResponse(
        status_code=status.HTTP_200_OK, # that is the default U can delete it
        content={
            "signal":ResponseSignal.FILE_UPLOADED_SUCCESSFULLY.value,
            "file_id": str(assert_record.id),
        }
    )


@data_router.post("/process/{project_id}")
async def process_endpoint(request: Request, project_id: str, process_request: ProcessRequest):
    
    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    chunk_overlap = process_request.chunk_overlap
    do_reset = process_request.do_reset

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id=project_id)





    process_controller = ProcessController(project_id=project_id)

    file_content = process_controller.get_file_content(file_id=file_id)
    chunks = process_controller.split_file_content(file_content=file_content, 
                                                   chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    if chunks is None or len(chunks) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal":ResponseSignal.FILE_PROCESSING_FAILED.value,
            }
        )
   
    chunks_records = [
        DataChunk(
            chunk_text=chunk.page_content,
            chunk_metadata=chunk.metadata,
            chunk_order=index,
            chunk_project_id=project.id
        ) for index, chunk in enumerate(chunks, start=1)
    ]

    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)

    if do_reset==1:
        await chunk_model.delete_chunks_by_project_id(project_id=project.id)

    no_records =await chunk_model.insert_many_chunks(chunks=chunks_records)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal":ResponseSignal.FILE_PROCESSING_SUCCESS.value,
            "inserted_chunks_count": no_records
        }
    )
