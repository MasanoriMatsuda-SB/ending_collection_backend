import os
from typing import List
from app.models import Message
from app.vector_store import get_chroma_collection
from openai import AzureOpenAI
from app.crud import get_messages_by_item_id
from sqlalchemy.orm import Session


# Azure OpenAI 設定
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-03-01-preview",  # ← Azureポータルに合わせて
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")  
)

# 要約
def chat_llm_summarize(text: str) -> str:
    prompt = f"以下のチャットを要約してください:\n{text}"
    response = client.chat.completions.create(  
        model="gpt-4o-mini", 
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# ベクトル検索（Chroma）
def embed_text(text: str) -> List[float]:
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )
    return response.data[0].embedding

def index_messages_for_item(db: Session, item_id: str):
    messages = get_messages_by_item_id(db, item_id)
    collection = get_chroma_collection()
    
    docs, ids, embeddings = [], [], []
    for m in messages:
        docs.append(m.content)
        ids.append(f"{item_id}_{m.message_id}")
        embeddings.append(embed_text(m.content))
    
    collection.add(documents=docs, ids=ids, embeddings=embeddings)


def search_chat_vector(item_id: str, query: str) -> List[dict]:
    collection = get_chroma_collection()
    query_embedding = embed_text(query)
    results = collection.query(query_embeddings=[query_embedding], n_results=5)
    
    print(f"検索結果: {results}")    #検証用（後で削除）
    
    return [{"content": doc} for doc in results["documents"][0]]