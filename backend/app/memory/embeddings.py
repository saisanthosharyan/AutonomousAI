from __future__ import annotations

from functools import lru_cache
from typing import List, Union

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.logger import logger


class EmbeddingManager:
    """
    Central embedding service for AutoDev AI.

    Responsibilities
    ----------------
    • Load embedding model only once.
    • Convert text -> embedding vector.
    • Convert multiple texts -> embedding matrix.
    • Compute cosine similarity.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self) -> None:
        self.model = self._load_model()

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_model() -> SentenceTransformer:
        logger.info(
            "Loading embedding model: %s",
            EmbeddingManager.MODEL_NAME,
        )

        model = SentenceTransformer(
            EmbeddingManager.MODEL_NAME
        )

        logger.info("Embedding model loaded.")

        return model

    # ---------------------------------------------------------

    def embed(
        self,
        text: str,
    ) -> List[float]:
        """
        Generate embedding for one text.
        """

        if not text:
            return []

        vector = self.model.encode(
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return vector.tolist()

    # ---------------------------------------------------------

    def embed_batch(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        """

        if not texts:
            return []

        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return vectors.tolist()

    # ---------------------------------------------------------

    @staticmethod
    def cosine_similarity(
        embedding1: Union[List[float], np.ndarray],
        embedding2: Union[List[float], np.ndarray],
    ) -> float:
        """
        Cosine similarity between two vectors.
        """

        if embedding1 is None or embedding2 is None:
            return 0.0

        if len(embedding1) == 0:
            return 0.0

        if len(embedding2) == 0:
            return 0.0

        a = np.asarray(embedding1, dtype=np.float32)
        b = np.asarray(embedding2, dtype=np.float32)

        denominator = np.linalg.norm(a) * np.linalg.norm(b)

        if denominator == 0:
            return 0.0

        return float(np.dot(a, b) / denominator)

    # ---------------------------------------------------------

    def search(
        self,
        query: str,
        embeddings: List[List[float]],
    ) -> List[float]:
        """
        Compare one query against many embeddings.

        Returns similarity scores.
        """

        if not embeddings:
            return []

        query_embedding = np.asarray(
            self.embed(query),
            dtype=np.float32,
        )

        scores = []

        for emb in embeddings:

            score = self.cosine_similarity(
                query_embedding,
                emb,
            )

            scores.append(score)

        return scores


_embedding_manager: EmbeddingManager | None = None


def get_embedding_manager() -> EmbeddingManager:
    """
    Singleton accessor.
    """

    global _embedding_manager

    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager()

    return _embedding_manager