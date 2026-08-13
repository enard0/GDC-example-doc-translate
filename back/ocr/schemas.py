from pydantic import BaseModel
from typing import List, Optional


class Block(BaseModel):
    id: str
    type: str
    text: Optional[str]
    bbox: List[float]


class PageResponse(BaseModel):
    page: int
    blocks: List[Block]
