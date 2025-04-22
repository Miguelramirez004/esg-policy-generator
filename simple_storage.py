import os
import json
import pickle
from typing import List, Dict, Any, Optional
from datetime import datetime
import shutil

class SimpleDocumentStore:
    """
    A simple document store that works without SQLite dependencies.
    This is a fallback when ChromaDB can't be used due to SQLite version constraints.
    """
    
    def __init__(self, directory="./simple_db"):
        self.directory = directory
        self.docs_dir = os.path.join(directory, "documents")
        self.index_path = os.path.join(directory, "index.pickle")
        self.metadata_path = os.path.join(directory, "metadata.json")
        self.initialize()
    
    def initialize(self):
        """Initialize the document store."""
        os.makedirs(self.directory, exist_ok=True)
        os.makedirs(self.docs_dir, exist_ok=True)
        
        # Create index if it doesn't exist
        if not os.path.exists(self.index_path):
            self.save_index({})
            
        # Create metadata if it doesn't exist
        if not os.path.exists(self.metadata_path):
            with open(self.metadata_path, 'w') as f:
                json.dump({"created_at": datetime.now().isoformat()}, f)
    
    def save_index(self, index):
        """Save the index to disk."""
        with open(self.index_path, 'wb') as f:
            pickle.dump(index, f)
    
    def load_index(self):
        """Load the index from disk."""
        if os.path.exists(self.index_path):
            with open(self.index_path, 'rb') as f:
                return pickle.load(f)
        return {}
    
    def add(self, documents: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]], ids: List[str]):
        """Add documents to the store."""
        index = self.load_index()
        
        for i, (doc, embedding, metadata, doc_id) in enumerate(zip(documents, embeddings, metadatas, ids)):
            # Save the document
            doc_path = os.path.join(self.docs_dir, f"{doc_id}.txt")
            with open(doc_path, 'w', encoding='utf-8') as f:
                f.write(doc)
                
            # Save the metadata and embedding
            index[doc_id] = {
                "doc_path": doc_path,
                "embedding": embedding,
                "metadata": metadata
            }
            
        # Save the updated index
        self.save_index(index)
        
        return {"success": True}
    
    def get(self, ids=None, where=None, limit=None):
        """Get documents by IDs or conditions."""
        index = self.load_index()
        
        if ids is None:
            # Return all document IDs
            return {
                "ids": list(index.keys()),
                "documents": [],
                "embeddings": [],
                "metadatas": []
            }
        
        result_ids = []
        result_docs = []
        result_embeddings = []
        result_metadatas = []
        
        for doc_id in ids:
            if doc_id in index:
                entry = index[doc_id]
                result_ids.append(doc_id)
                
                # Load the document content
                with open(entry["doc_path"], 'r', encoding='utf-8') as f:
                    doc_content = f.read()
                
                result_docs.append(doc_content)
                result_embeddings.append(entry["embedding"])
                result_metadatas.append(entry["metadata"])
        
        return {
            "ids": result_ids,
            "documents": result_docs,
            "embeddings": result_embeddings,
            "metadatas": result_metadatas
        }
    
    def query(self, query_embeddings, n_results=5, include=None):
        """
        Basic similarity search. 
        Note: This is just a placeholder that returns a fixed number of results.
        In a real implementation, you would compute cosine similarity against the query.
        """
        index = self.load_index()
        all_ids = list(index.keys())
        
        # Take the first n entries or fewer if there aren't enough
        result_count = min(n_results, len(all_ids))
        result_ids = all_ids[:result_count]
        
        result_documents = []
        result_metadatas = []
        
        if include is None:
            include = []
        
        if "documents" in include:
            for doc_id in result_ids:
                with open(index[doc_id]["doc_path"], 'r', encoding='utf-8') as f:
                    result_documents.append([f.read()])
        else:
            result_documents = [[]]
            
        if "metadatas" in include:
            for doc_id in result_ids:
                result_metadatas.append([index[doc_id]["metadata"]])
        else:
            result_metadatas = [[]]
            
        return {
            "ids": [result_ids],
            "documents": result_documents,
            "metadatas": result_metadatas,
            "distances": [[1.0] * result_count]  # Placeholder similarity scores
        }
    
    def count(self):
        """Count the number of documents."""
        index = self.load_index()
        return len(index)
    
    def reset(self):
        """Reset the store."""
        if os.path.exists(self.directory):
            shutil.rmtree(self.directory)
        self.initialize()

def create_document_store():
    """Create and return a document store instance."""
    return SimpleDocumentStore()
