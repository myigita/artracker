from pydantic import BaseModel
from datetime import datetime

class TrackerIn(BaseModel):
    name: str | None = None
    subject_name: str
    platform_name: str
    url: str
    description: str | None = None

class TrackerOut(BaseModel):
    id: int
    name: str
    subject_name: str
    platform_name: str
    url: str
    description: str | None
    date_created: datetime
    last_checked: datetime | None

    model_config = {"from_attributes": True}