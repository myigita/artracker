from pydantic import BaseModel
from datetime import datetime

class TrackerCreate(BaseModel):
    artist_name: str
    platform_name: str
    url: str

class TrackerOut(BaseModel):
    id: int
    name: str
    artist_name: str
    platform_name: str
    url: str
    date_created: datetime
    last_checked: datetime | None

    model_config = {"from_attributes": True}