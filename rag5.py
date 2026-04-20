backend/api/schema/query.py

from pydantic import BaseModel
class QueryRequest(BaseModel):
    query: str
