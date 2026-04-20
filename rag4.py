backend/api/routes/query.py

import os
from fastapi import APIRouter, HTTPException
from backend.api.schemas.query import QueryRequest
from backend.core.pipelines import create_rag_pipeline

router = APIRouter()
rag_pipe = create_rag_pipeline()

@router.post("/query")
def handle_query(request: QueryRequest):
    try:
        result = rag_pipe.run({
            "dense_text_embedder": {"text": request.query},
            "sparse_text_embedder": {"text": request.query},
            "ranker": {"query": request.query},
            "prompt_builder": {"query": request.query}
        })
        return {"answer": result["llm"]["replies"][0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
      
