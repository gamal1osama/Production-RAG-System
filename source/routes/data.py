import os
import aiofiles

from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController
from models import ResponseSignal

from fastapi import FastAPI, APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse


data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)

@data_router.post("/upload/{project_id}")
async def upload_data(project_id: str, file: UploadFile, app_settings: Settings = Depends(get_settings)):
    
    # validate the uploaded file
    is_valid, message = DataController().validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal":message
            }
        )
    
    # Save the file to the specified directory
    project_dir_path = ProjectController().get_project_path(project_id=project_id)
    file_path = os.path.join(project_dir_path, file.filename)

    async with aiofiles.open(file_path, 'wb') as f: # open for wring in binary mode
        while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE): # read the file in chunks
            await f.write(chunk) # write the chunk to the file
    
    return JSONResponse(
        status_code=status.HTTP_200_OK, # that is the default U can delete it
        content={
            "signal":ResponseSignal.FILE_UPLOADED_SUCCESSFULLY.value
        }
    )