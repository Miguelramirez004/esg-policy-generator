import os
import traceback
import streamlit as st

def init_collection():
    """
    Initialize and return either a ChromaDB collection or a fallback storage solution.
    Falls back to a simple storage mechanism if ChromaDB is not available due to SQLite 
    version or other compatibility issues.
    """
    try:
        # Try to use ChromaDB first
        import chromadb
        from chromadb.config import Settings
        
        # Create the directory if it doesn't exist
        os.makedirs("./chroma_db", exist_ok=True)
        
        client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(
                allow_reset=True,
                anonymized_telemetry=False,
                is_persistent=True
            ),
        )
        
        collection = client.get_or_create_collection(
            name="company_profile_docs",
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,  # We're providing our own embeddings
        )
        
        # Store a flag in session state that we're using ChromaDB
        st.session_state.using_chromadb = True
        return collection
    
    except Exception as e:
        error_msg = str(e)
        traceback.print_exc()
        
        # Check if the error is related to SQLite version
        if "unsupported version of sqlite3" in error_msg:
            st.warning(
                "ChromaDB requires SQLite ≥ 3.35.0, which is not available in this environment. "
                "Using a simple fallback storage mechanism instead. "
                "Some features may be limited."
            )
        else:
            st.warning(
                f"Failed to initialize ChromaDB: {error_msg}. "
                "Using a simple fallback storage mechanism instead."
            )
        
        # Import and use the simple storage fallback
        from simple_storage import create_document_store
        
        # Store a flag in session state that we're using the fallback
        st.session_state.using_chromadb = False
        return create_document_store()
