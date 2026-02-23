from pydantic import BaseModel

class SyncDataResponse(BaseModel):
    success: bool
    data_source: str
    code: str
    start_date: str
    end_date: str
    data: dict | None = None
    error: dict | str | None = None
    timestamp: str
