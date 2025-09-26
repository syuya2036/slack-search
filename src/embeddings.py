from __future__ import annotations

import numpy as np
from openai import OpenAI

from .config import EMBED_MODEL, OPENAI_API_KEY

_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def embed_texts(texts: list[str]) -> np.ndarray:
    if _client is None:
        raise RuntimeError("OPENAI_API_KEY が未設定です")
    resp = _client.embeddings.create(model=EMBED_MODEL, input=texts)
    vecs = [np.array(d.embedding, dtype=np.float32) for d in resp.data]
    return np.vstack(vecs)
