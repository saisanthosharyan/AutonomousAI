from typing import List, Dict


class MemoryRanker:
    """
    Simple memory ranking utility.

    Currently returns the most recent memories.
    Later this can be upgraded to semantic similarity
    using embeddings.
    """

    def rank(
        self,
        memories: List[Dict],
        query: str,
        top_k: int = 5,
    ) -> List[Dict]:
        if not memories:
            return []

        return memories[-top_k:]