import re
from collections import Counter
from typing import List, Dict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

STOPWORDS = set(
    "the a and to of in for on with at from by this that is it an as be are was were or which".split()
)

def preprocess_text(text: str) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text.strip())
    text = re.sub(r'[^\w\s.,!?;:]', '', text)
    return text

def summarize(text: str, max_sents: int = 3) -> str:
    text = preprocess_text(text)
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    sents = [s for s in sents if s and len(s.split()) >= 3]
    
    if not sents:
        return ""
    if len(sents) <= max_sents:
        return " ".join(sents)

    vec = TfidfVectorizer(stop_words='english').fit_transform(sents)
    scores = np.asarray(vec.sum(axis=1)).ravel()
    top = scores.argsort()[::-1][:max_sents]
    return " ".join(sents[i] for i in sorted(top))

def keyphrases(text: str, top_k: int = 8) -> List[str]:
    text = preprocess_text(text)
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    words = [w for w in words if w not in STOPWORDS]
    return [w for w, _ in Counter(words).most_common(top_k)]

def build_search_index(docs: List[Dict]):
    """
    docs = [{id, text, meta}]
    returns {"vec","mat","docs"}
    """
    texts = [d["text"] for d in docs] or [""]
    vec = TfidfVectorizer(stop_words='english').fit(texts)
    mat = vec.transform(texts)
    return {"vec": vec, "mat": mat, "docs": docs}

def search(index, q: str, top_k: int = 5):
    qv = index["vec"].transform([q])
    sims = cosine_similarity(qv, index["mat"]).ravel()
    order = sims.argsort()[::-1][:top_k]
    results = []
    for i in order:
        d = index["docs"][i]
        results.append({
            "id": d["id"],
            "text": d["text"],
            "score": float(sims[i]),
            "meta": d.get("meta", {}),
        })
    return results