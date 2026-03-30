from pydantic import BaseModel
from typing import Optional, List

class ProcessRequest(BaseModel):
    file_id: str = None
    chunk_size: Optional[int] = 100
    overlap_size: Optional[int] = 20
    do_reset: Optional[int] = 0


class DeleteRequest(BaseModel):
    file_ids: List[str] = None