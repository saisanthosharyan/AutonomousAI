from __future__ import annotations

import json
import threading
from typing import Any

from app.core.logger import logger

from app.memory.memory_store import MemoryStore
from app.memory.memory_retriever import MemoryRetriever
from app.memory.context_builder import ContextBuilder


class MemoryManager:
    """
    Production-grade Memory Manager.

    Responsibilities
    ----------------

    - Persist memories (via MemoryStore)
    - Retrieve relevant memories (via MemoryRetriever)
    - Build LLM context (via ContextBuilder)
    - Thread-safe, shared across every agent in the pipeline

    Components
    ----------

    MemoryStore
        Handles persistence: duplicate detection, embedding
        generation, atomic writes, schema handling.

    MemoryRetriever
        Handles semantic search over stored memories.

    ContextBuilder
        Builds optimized prompts for LLMs from a list of memories.
    """

    MAX_MEMORY_RECORDS = 500

    def __init__(
        self,
        memory_directory: str = "memory",
    ):

        self._lock = threading.RLock()

        self.store = MemoryStore(
            memory_directory=memory_directory
        )

        self.retriever = MemoryRetriever(
            memory_directory=memory_directory
        )

        self.context_builder = ContextBuilder()

        logger.info(
            "Memory Manager initialized successfully."
        )

    # ==========================================================
    # SAVE
    # ==========================================================

    def save(
        self,
        *,
        memory_type: str,
        prompt: str,
        language: str = "",
        framework: str = "",
        review: str = "",
        success: bool = False,
        error: str = "",
        fix: str = "",
        **metadata: Any,
    ) -> str | None:
        """
        Save one memory.

        This method is intentionally lightweight. MemoryStore performs
        duplicate detection, embedding generation, atomic writes, and
        schema handling -- MemoryManager only validates inputs,
        coordinates storage under the lock, and returns the id.

        Returns the new memory's id, or None if MemoryStore treated it
        as a duplicate and skipped the save.
        """

        if not memory_type.strip():
            raise ValueError(
                "memory_type cannot be empty."
            )

        if not prompt.strip():
            raise ValueError(
                "prompt cannot be empty."
            )

        logger.info(
            "Saving %s memory...",
            memory_type,
        )

        with self._lock:

            try:

                memory_id = self.store.save(
                    memory_type=memory_type,
                    prompt=prompt,
                    language=language,
                    framework=framework,
                    review=review,
                    success=success,
                    error=error,
                    fix=fix,
                    **metadata,
                )

            except Exception:

                logger.exception(
                    "Memory save failed."
                )

                raise

        if memory_id:

            logger.info(
                "Memory saved successfully (%s).",
                memory_id,
            )

        else:

            logger.info(
                "Duplicate memory ignored."
            )

        return memory_id

    # ==========================================================
    # RETRIEVE
    # ==========================================================

    def retrieve(
        self,
        prompt: str,
        limit: int = 5,
    ) -> list[dict]:
        """
        Retrieve the memories most relevant to `prompt`, ranked by
        semantic similarity (MemoryRetriever -> MemoryRanker).
        """

        return self.retriever.retrieve(
            query=prompt,
            limit=limit,
        )

    # ==========================================================
    # BUILD CONTEXT
    # ==========================================================

    def build_context(
        self,
        memories: list[dict],
        max_chars: int = 8000,
    ) -> str:
        """
        Turn a list of memories into a single prompt-ready string,
        truncated to roughly `max_chars` characters.
        """

        return self.context_builder.build(
            memories,
            max_chars=max_chars,
        )

    # ==========================================================
    # GET CONTEXT (convenience: retrieve + build_context in one call)
    # ==========================================================

    def get_context(
        self,
        prompt: str,
        limit: int = 5,
        max_chars: int = 8000,
    ) -> str:
        """
        Convenience wrapper: retrieve the top `limit` memories relevant
        to `prompt` and immediately build them into a context string.
        Equivalent to:

            memories = manager.retrieve(prompt, limit=limit)
            manager.build_context(memories, max_chars=max_chars)
        """

        memories = self.retrieve(
            prompt,
            limit=limit,
        )

        return self.build_context(
            memories,
            max_chars=max_chars,
        )

    # ==========================================================
    # DOMAIN-SPECIFIC SAVE HELPERS
    # ==========================================================
    #
    # These are thin convenience wrappers around save() for the two
    # most common memory shapes in the pipeline. They don't add new
    # storage behavior -- they just fix memory_type and the
    # field-to-parameter mapping so call sites don't have to repeat
    # it. Existing call sites using save(memory_type=..., ...)
    # directly (RetryManager, FixerAgent) are unaffected and keep
    # working exactly as before.

    def save_code(
        self,
        *,
        prompt: str,
        code: str,
        language: str = "",
        framework: str = "",
        success: bool = True,
        **metadata: Any,
    ) -> str | None:
        """
        Save a generated-code memory. `code` is stored in the same
        "fix" field MemoryStore already uses for generated content,
        so it's retrievable and embeddable the same way repairs are.
        """

        return self.save(
            memory_type="code",
            prompt=prompt,
            language=language,
            framework=framework,
            fix=code,
            success=success,
            **metadata,
        )

    def save_review(
        self,
        *,
        prompt: str,
        review: str,
        success: bool = True,
        **metadata: Any,
    ) -> str | None:
        """
        Save an AI-review memory.
        """

        return self.save(
            memory_type="review",
            prompt=prompt,
            review=review,
            success=success,
            **metadata,
        )

    def get_review(
        self,
        prompt: str,
        limit: int = 1,
    ) -> list[dict]:
        """
        Retrieve the most relevant past review memories for `prompt`.

        Pulls a slightly wider candidate set from the retriever, then
        filters down to memory_type == "review", since MemoryRetriever
        ranks by semantic similarity across all memory types and has
        no type filter of its own.
        """

        candidates = self.retriever.retrieve(
            query=prompt,
            limit=max(limit * 4, limit),
        )

        reviews = [
            memory
            for memory in candidates
            if memory.get("type") == "review"
        ]

        return reviews[:limit]

    # ==========================================================
    # MAINTENANCE
    # ==========================================================

    def stats(self) -> dict[str, Any]:
        """
        Summary statistics over everything currently in the memory
        store: total count, per-type breakdown, and overall success
        rate.
        """

        memories = self.store.load()

        by_type: dict[str, int] = {}

        successes = 0

        for memory in memories:

            memory_type = memory.get("type", "unknown")

            by_type[memory_type] = by_type.get(memory_type, 0) + 1

            if memory.get("success"):
                successes += 1

        total = len(memories)

        return {
            "total": total,
            "by_type": by_type,
            "success_count": successes,
            "success_rate": (
                successes / total if total else 0.0
            ),
        }

    def cleanup(self) -> int:
        """
        Trim stored memories down to the most recent
        MAX_MEMORY_RECORDS, oldest-first eviction. Returns the number
        of records removed.

        NOTE: MemoryStore's public API only exposes save() (append
        one) and load() (read all) -- there's no bulk-overwrite
        method, since normal operation never needs one. Trimming
        necessarily needs to rewrite the whole file, so this reuses
        MemoryStore's own atomic-write helper rather than duplicating
        that logic here with a plain write_text() call, which would
        reintroduce the corruption risk atomic writes were added to
        prevent.
        """

        with self._lock:

            memories = self.store.load()

            overflow = len(memories) - self.MAX_MEMORY_RECORDS

            if overflow <= 0:
                return 0

            trimmed = memories[overflow:]

            self.store._atomic_write(
                json.dumps(
                    trimmed,
                    indent=4,
                )
            )

        logger.info(
            "Memory cleanup removed %d record(s).",
            overflow,
        )

        return overflow

    def clear(self) -> None:
        """
        Wipe all stored memories. Destructive -- use with care (e.g.
        tests, or an explicit user-triggered reset).
        """

        with self._lock:

            self.store._atomic_write("[]")

        logger.warning(
            "All memories cleared."
        )