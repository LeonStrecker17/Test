main.py


from fastapi import FastAPI
from backend.api.routes import query
import uvicorn

app = FastAPI(title="Enterprise RAG Backend")
app.include_router(query.router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
  
