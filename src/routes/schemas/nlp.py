from pydantic import BaseModel
from typing import Optional



class PushRequest(BaseModel):
    do_reset: Optional[int] = 0
    

class ProcessAndPushRequest(BaseModel):
    file_id: Optional[int] = None

    chunk_size: Optional[int] = 100
    chunk_overlap: Optional[int] = 20

    do_reset: Optional[int] = 0
    
class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 10
