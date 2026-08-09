from __future__ import annotations

from typing import Any

from app.core.logger import logger
from app.memory.embeddings import get_embedding_manager
from app.memory.memory_store import MemoryStore


class MemoryRetriever:
    """
    Retrieves relevant memories using semantic vector search.

    Ranking strategy:
        1. Cosine similarity between query and memory embeddings.
        2. Keyword score fallback.
        3. Successful memories receive a small bonus.
    """

    def __init__(self, memory_directory: str):

        self.store = MemoryStore(memory_directory)

        try:
            self.embedding_manager = get_embedding_manager()
        except Exception:
            logger.exception(
                "Failed to initialize embedding manager."
            )
            self.embedding_manager = None

    # =====================================================
    # PUBLIC
    # =====================================================

    def retrieve(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:

        logger.info("Retrieving memories...")

        memories = self.store.load()

        if not memories:
            return []

        query_embedding = None

        if self.embedding_manager is not None:

            try:
                query_embedding = self.embedding_manager.embed(
                    query
                )

            except Exception:

                logger.exception(
                    "Failed generating query embedding."
                )

        scored: list[tuple[float, dict]] = []

        for memory in memories:

            score = 0.0

            # --------------------------------------------
            # Semantic similarity
            # --------------------------------------------

            embedding = memory.get("embedding")

            if (
                query_embedding is not None
                and embedding
            ):

                try:

                    similarity = (
                        self.embedding_manager.cosine_similarity(
                            query_embedding,
                            embedding,
                        )
                    )

                    score += similarity * 100

                except Exception:

                    logger.exception(
                        "Embedding similarity failed."
                    )

            # --------------------------------------------
            # Keyword fallback
            # --------------------------------------------

            score += self._keyword_score(
                query=query,
                memory=memory,
            )

            # --------------------------------------------
            # Prefer successful memories
            # --------------------------------------------

            if memory.get("success"):

                score += 2

            if score > 0:

                scored.append(
                    (
                        score,
                        memory,
                    )
                )

        scored.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        logger.info(
            "Retrieved %d relevant memories.",
            min(limit, len(scored)),
        )

        return [
            memory
            for _, memory in scored[:limit]
        ]

    # =====================================================
    # KEYWORD FALLBACK
    # =====================================================

    @staticmethod
    def _keyword_score(
        query: str,
        memory: dict,
    ) -> float:

        query_words = {
            word.lower()
            for word in query.split()
            if len(word) > 2
        }

        prompt = memory.get(
            "prompt",
            "",
        ).lower()

        error = memory.get(
            "error",
            "",
        ).lower()

        fix = memory.get(
            "fix",
            "",
        ).lower()

        review = memory.get(
            "review",
            "",
        ).lower()

        score = 0.0

        for word in query_words:

            if word in prompt:
                score += 3

            if word in error:
                score += 2

            if word in fix:
                score += 2

            if word in review:
                score += 1

        return score