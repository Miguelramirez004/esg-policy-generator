import chromadb
from chromadb.config import Settings
import os

def get_chroma_client():
    # Create the directory if it doesn't exist
    os.makedirs("./chroma_db", exist_ok=True)
    
    return chromadb.PersistentClient(
        path="./chroma_db",
        settings=Settings(
            allow_reset=True,
            anonymized_telemetry=False,
            is_persistent=True
        ),
    )

def init_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="company_profile_docs",
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,  # We're providing our own embeddings
    )