import os
import faiss
import pickle
from typing import List
from app.models import Message
from openai import AzureOpenAI
from app.crud import get_messages_by_item_id
from sqlalchemy.orm import Session
import numpy as np

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

print("[DEBUG] AZURE_OPENAI_KEY:", os.getenv("AZURE_OPENAI_KEY"))
print("[DEBUG] AZURE_OPENAI_ENDPOINT:", os.getenv("AZURE_OPENAI_ENDPOINT"))


# Azure OpenAI 設定
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-03-01-preview",  # ← Azureポータルに合わせて
    # api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")  
)

# FAISS用の保存先
INDEX_DIR = "faiss_index"
os.makedirs(INDEX_DIR, exist_ok=True)

# 要約
def chat_llm_summarize(text: str) -> str:
    prompt = f"以下のチャットを要約してください:\n{text}"
    print("[DEBUG] 要約プロンプト:", prompt[:300])  # 長さ制限
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("[ERROR] 要約失敗:", e)
        return "要約に失敗しました"

# テキスト埋め込み
def embed_text(text: str) -> List[float]:
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )
    return response.data[0].embedding

# インデックス作成（ベクトル登録）
def index_messages_for_item(db: Session, item_id: str):
    messages = get_messages_by_item_id(db, item_id)
    embeddings = []
    texts = []
    ids = []

    for m in messages:
        embeddings.append(embed_text(m.content))
        texts.append(m.content)
        ids.append(f"{item_id}_{m.message_id}")

    dim = len(embeddings[0])
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings).astype("float32"))

    # 永続化
    faiss.write_index(index, os.path.join(INDEX_DIR, f"{item_id}.faiss"))
    with open(os.path.join(INDEX_DIR, f"{item_id}.pkl"), "wb") as f:
        pickle.dump(texts, f)

# 検索
def search_chat_vector(item_id: str, query: str) -> List[dict]:
    index_path = os.path.join(INDEX_DIR, f"{item_id}.faiss")
    texts_path = os.path.join(INDEX_DIR, f"{item_id}.pkl")

    if not os.path.exists(index_path) or not os.path.exists(texts_path):
        return [{"content": "インデックスが存在しません。まずインデックス化してください。"}]

    index = faiss.read_index(index_path)
    with open(texts_path, "rb") as f:
        texts = pickle.load(f)

    query_embedding = embed_text(query)
    D, I = index.search(np.array([query_embedding]).astype("float32"), k=3)

    results = [{"content": texts[i]} for i in I[0] if i < len(texts)]
    return results
