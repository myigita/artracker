from pydantic import BaseModel
from datetime import datetime

class SubjectIn(BaseModel):
    name: str

class SubjectOut(BaseModel):
    id: int
    name: str
    date_created: datetime

    model_config = {"from_attributes": True}

class PlatformIn(BaseModel):
    name: str

class PlatformOut(BaseModel):
    id: int
    name: str
    date_created: datetime

    model_config = {"from_attributes": True}

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