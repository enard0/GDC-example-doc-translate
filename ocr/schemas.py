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


class PredictInstance(BaseModel):
    file_base64: str
    page: int


class VertexPredictRequest(BaseModel):
    instances: List[PredictInstance]


class VertexPredictResponse(BaseModel):
    predictions: List[PageResponse]
