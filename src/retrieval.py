"""TF-IDF retrieval over schema documentation (standard library only).

Used in both modes: in live mode the retrieved docs ground the Bedrock
prompt; in demo mode the retrieved example pairs drive the deterministic
SQL translator. Pure stdlib so demo mode has no heavy ML dependency.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class TfidfRetriever:
    def __init__(self, docs: list[dict]):
        self.docs = docs
        self._doc_tokens = [tokenize(d["text"]) for d in docs]
        self._df: Counter[str] = Counter()
        for toks in self._doc_tokens:
            for t in set(toks):
                self._df[t] += 1
        self._n = len(docs)
        self._idf = {
            t: math.log((1 + self._n) / (1 + df)) + 1.0
            for t, df in self._df.items()
        }
        self._doc_vectors = [self._vector(toks) for toks in self._doc_tokens]

    def _vector(self, tokens: list[str]) -> dict[str, float]:
        counts = Counter(tokens)
        total = len(tokens) or 1
        vec = {t: (c / total) * self._idf.get(t, 1.0)
               for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(v * b.get(t, 0.0) for t, v in a.items())

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """Return the top-k docs as {'doc': doc, 'score': float}."""
        qvec = self._vector(tokenize(query))
        if not qvec:
            return []
        scored = [
            {"doc": doc, "score": self._cosine(qvec, vec)}
            for doc, vec in zip(self.docs, self._doc_vectors)
        ]
        scored.sort(key=lambda s: s["score"], reverse=True)
        return [s for s in scored[:top_k] if s["score"] > 0]
