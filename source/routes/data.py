import os
import aiofiles
import logging

from helpers.config import get_settings, Settings
from controllers import DataController, ProcessController
from models import ResponseSignal
from .schemas.data import ProcessRequest

from fastapi import FastAPI, APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse



logger = logging.getLogger('uvicorn.error')




data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)

@data_router.post("/upload/{project_id}")
async def upload_data(project_id: str, file: UploadFile, app_settings: Settings = Depends(get_settings)):
    
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

    return JSONResponse(
        status_code=status.HTTP_200_OK, # that is the default U can delete it
        content={
            "signal":ResponseSignal.FILE_UPLOADED_SUCCESSFULLY.value,
            "file_id": file_id
        }
    )


@data_router.post("/process/{project_id}")
async def process_endpoint(project_id: str, process_request: ProcessRequest):
    
    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    chunk_overlap = process_request.chunk_overlap

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
    else:
        return chunks