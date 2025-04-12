import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(path="vector_store")

def get_chroma_collection():
    return client.get_or_create_collection("chat_rag_collection")
