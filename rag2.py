backend/config/setring.py


import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Ollama
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text-v2-moe"
    generation_model: str = "llama3"
    
    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    index_name: str = "enterprise_docs"
    embedding_dim: int = 768
    
    # RAG Settings
    top_k_retriever: int = 20
    top_k_ranker: int = 5

settings = Settings()
