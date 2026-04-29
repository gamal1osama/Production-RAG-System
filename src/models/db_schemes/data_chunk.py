from pydantic import BaseModel, Field, validator
from bson.objectid import ObjectId
from typing import Optional

class DataChunk(BaseModel):
    _id: Optional[ObjectId]
    
    chunk_text: str = Field(..., min_length=1)
    chunk_metadata: dict
    
    chunk_order: int = Field(..., gt=0)

    chunk_project_id: ObjectId
    


    class Config:
        arbitrary_types_allowed = True