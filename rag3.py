backend/core/pipelines.py

from haystack import Pipeline
from haystack.components.converters import PyPDFToDocument
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.components.builders import PromptBuilder
from haystack.components.rankers import SentenceTransformersSimilarityRanker
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from haystack_integrations.components.retrievers.qdrant import QdrantHybridRetriever
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder, OllamaTextEmbedder
from haystack_integrations.components.embedders.fastembed import FastembedSparseDocumentEmbedder, FastembedSparseTextEmbedder
from haystack_integrations.components.generators.ollama import OllamaGenerator
from backend.config.settings import settings

def get_document_store():
    return QdrantDocumentStore(
        url=settings.qdrant_url,
        index=settings.index_name,
        embedding_dim=settings.embedding_dim,
        use_sparse_embeddings=True,
        recreate_index=False
    )

def create_indexing_pipeline():
    document_store = get_document_store()
    pipeline = Pipeline()
    
    pipeline.add_component("converter", PyPDFToDocument())
    pipeline.add_component("cleaner", DocumentCleaner(remove_empty_lines=True, remove_extra_whitespaces=True))
    pipeline.add_component("splitter", DocumentSplitter(split_by="word", split_length=250, split_overlap=30))
    pipeline.add_component("dense_embedder", OllamaDocumentEmbedder(model=settings.embedding_model, url=settings.ollama_url, prefix="search_document: "))
    pipeline.add_component("sparse_embedder", FastembedSparseDocumentEmbedder(model="Qdrant/bm25"))
    pipeline.add_component("writer", DocumentWriter(document_store=document_store))

    pipeline.connect("converter", "cleaner")
    pipeline.connect("cleaner", "splitter")
    pipeline.connect("splitter", "dense_embedder")
    pipeline.connect("dense_embedder", "sparse_embedder")
    pipeline.connect("sparse_embedder", "writer")
    return pipeline

def create_rag_pipeline():
    document_store = get_document_store()
    pipeline = Pipeline()

    pipeline.add_component("dense_text_embedder", OllamaTextEmbedder(model=settings.embedding_model, url=settings.ollama_url, prefix="search_query: "))
    pipeline.add_component("sparse_text_embedder", FastembedSparseTextEmbedder(model="Qdrant/bm25"))
    pipeline.add_component("retriever", QdrantHybridRetriever(document_store=document_store, top_k=settings.top_k_retriever))
    pipeline.add_component("ranker", SentenceTransformersSimilarityRanker(model="BAAI/bge-reranker-base", top_k=settings.top_k_ranker))
    
    template = """
    Beantworte die Frage NUR basierend auf dem Kontext. Wenn die Info fehlt, sag es.
    Zitiere Quellen am Satzende als [Quelle: Name, Seite X].

    Kontext:
    {% for doc in documents %}
      {{ doc.content }} (Quelle: {{ doc.meta['file_name'] }}, Seite: {{ doc.meta.get('page_number', '?') }})
    {% endfor %}

    Frage: {{ query }}
    Antwort:
    """
    pipeline.add_component("prompt_builder", PromptBuilder(template=template))
    pipeline.add_component("llm", OllamaGenerator(model=settings.generation_model, url=settings.ollama_url))

    pipeline.connect("dense_text_embedder.embedding", "retriever.query_embedding")
    pipeline.connect("sparse_text_embedder.sparse_embedding", "retriever.query_sparse_embedding")
    pipeline.connect("retriever.documents", "ranker.documents")
    pipeline.connect("ranker.documents", "prompt_builder.documents")
    pipeline.connect("prompt_builder.answers", "llm.query")
    
    return pipeline
