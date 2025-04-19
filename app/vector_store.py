import os
import faiss
import pickle
from typing import List
import numpy as np

# 保存パス
FAISS_INDEX_PATH = "vector_store/index.faiss"
DOCS_PATH = "vector_store/docs.pkl"

# グローバル変数で保持（簡易実装）
_index = None
_docs = None

# 初期化またはロード
def load_faiss_index(d: int = 1536):
    global _index, _docs
    if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(DOCS_PATH):
        _index = faiss.read_index(FAISS_INDEX_PATH)
        with open(DOCS_PATH, "rb") as f:
            _docs = pickle.load(f)
    else:
        _index = faiss.IndexFlatL2(d)
        _docs = []

# 保存
def save_faiss_index():
    faiss.write_index(_index, FAISS_INDEX_PATH)
    with open(DOCS_PATH, "wb") as f:
        pickle.dump(_docs, f)

# 追加
def add_to_faiss(embeddings: List[List[float]], documents: List[str]):
    global _index, _docs
    _index.add(np.array(embeddings).astype("float32"))
    _docs.extend(documents)
    save_faiss_index()

# 検索
def search_faiss(query_embedding: List[float], top_k: int = 5) -> List[str]:
    global _index, _docs
    if _index is None or _docs is None:
        load_faiss_index()
    D, I = _index.search(np.array([query_embedding]).astype("float32"), top_k)
    return [_docs[i] for i in I[0] if i < len(_docs)]
