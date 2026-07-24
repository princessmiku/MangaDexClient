from datetime import datetime

from .base_model import BaseModel
from .manga_model import Relationship


class CoverAttributes(BaseModel):
    description: str | None
    volume: str | None
    file_name: str
    locale: str | None
    created_at: datetime
    updated_at: datetime
    version: int


class Cover(BaseModel):
    id: str
    type: str
    attributes: CoverAttributes
    relationships: list[Relationship]
