from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from app.core.logger import logger
from app.memory.embeddings import get_embedding_manager


class MemoryStore:
    """
    Stores learning memories on disk.

    Each memory represents one learning experience such as

    • successful generation
    • execution failure
    • automatic repair
    • review feedback

    Schema (current, SCHEMA_VERSION = 1):

    {
        "id": "uuid4 hex string",
        "created_at": "ISO-8601 timestamp",
        "timestamp": "ISO-8601 timestamp",   # legacy alias, see below
        "type": "repair",
        "prompt": "...",
        "embedding": [0.01, -0.02, ...] | None,
        "language": "Python",
        "framework": "FastAPI",
        "error": "...",
        "fix": "...",
        "review": "...",
        "success": true,
        "version": 1,
        "metadata": {"category": "ImportError", "attempt": 2, ...}
    }

    Backward compatibility notes:

    - "timestamp" is kept alongside the new "created_at" field with the
      same value, since existing readers (e.g. memory_retriever.py)
      may already key off "timestamp".
    - load() still returns a plain list[dict], same as before.
    - save() still accepts every original keyword argument
      (memory_type, prompt, language, framework, error, fix, review,
      success) with the same meanings and defaults. Any *additional*
      keyword arguments callers pass (e.g. category="ImportError",
      attempt=2, as used by RetryManager/FixerAgent) are no longer a
      TypeError -- they're captured into the new "metadata" field
      instead of requiring a signature change every time a caller
      wants to attach a new attribute.
    """

    MEMORY_FILE = "memory.json"
    SCHEMA_VERSION = 1

    def __init__(self, memory_directory: str):

        self.memory_dir = Path(memory_directory)

        self.memory_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.memory_file = (
            self.memory_dir /
            self.MEMORY_FILE
        )

        if not self.memory_file.exists():

            self._atomic_write("[]")

        # Embedding generation is best-effort: if the embedding
        # manager fails to initialize (missing model, misconfigured
        # provider, etc.), memory storage should still work -- it
        # just falls back to storing memories without an embedding
        # (semantic search over those entries degrades gracefully;
        # memory_retriever.py can still fall back to keyword matching).
        try:
            self.embedding_manager = get_embedding_manager()
        except Exception:
            logger.exception(
                "Failed to initialize embedding manager. "
                "Memories will be saved without embeddings."
            )
            self.embedding_manager = None

    # =====================================================
    # Public
    # =====================================================

    def save(
        self,
        *,
        memory_type: str,
        prompt: str,
        language: str = "",
        framework: str = "",
        error: str = "",
        fix: str = "",
        review: str = "",
        success: bool = False,
        **metadata: Any,
    ) -> Optional[str]:
        """
        Save one memory entry. Returns the new memory's id, or None if
        the entry was skipped as a duplicate.

        Any keyword arguments beyond the named ones (e.g.
        category="ImportError", attempt=2) are stored under the
        "metadata" field rather than raising a TypeError, so this
        stays forward-compatible with new fields callers may want to
        attach later.
        """

        logger.info(
            "Saving memory..."
        )

        memories = self.load()

        # --------------------------------------------------
        # Duplicate detection
        # --------------------------------------------------
        #
        # NOTE: deliberately keying on (type, prompt, error, fix)
        # rather than just (type, prompt) as a naive first pass would
        # suggest. In this pipeline "prompt" is frequently the project
        # title, which stays identical across every retry attempt on
        # the same project -- deduping on (type, prompt) alone would
        # silently drop every execution_failure/repair memory after
        # the first attempt, which defeats the purpose of retry
        # history. Including error/fix content means genuinely
        # identical saves are still caught (e.g. accidental double
        # save() calls) without losing distinct attempts.

        duplicate_key = (
            memory_type,
            prompt,
            error,
            fix,
        )

        for existing in memories:

            existing_key = (
                existing.get("type"),
                existing.get("prompt"),
                existing.get("error", ""),
                existing.get("fix", ""),
            )

            if existing_key == duplicate_key:

                logger.info(
                    "Duplicate memory detected; skipping save."
                )

                return None

        # --------------------------------------------------
        # Embedding
        # --------------------------------------------------

        combined_text = "\n".join(
            filter(
                None,
                [
                    prompt,
                    error,
                    fix,
                    review,
                ],
            )
        )

        embedding = None

        if self.embedding_manager is not None and combined_text:

            try:
                embedding = self.embedding_manager.embed(
                    combined_text
                )

            except Exception:

                logger.exception(
                    "Failed to generate embedding for memory; "
                    "saving without one."
                )

                embedding = None

        # --------------------------------------------------
        # Build entry
        # --------------------------------------------------

        memory_id = uuid4().hex

        created_at = datetime.now().isoformat()

        entry = {
            "id": memory_id,

            "created_at": created_at,

            # Legacy alias -- kept so existing readers that expect
            # "timestamp" keep working unmodified.
            "timestamp": created_at,

            "type": memory_type,

            "prompt": prompt,

            "embedding": embedding,

            "language": language,

            "framework": framework,

            "error": error,

            "fix": fix,

            "review": review,

            "success": success,

            "version": self.SCHEMA_VERSION,

            "metadata": metadata,
        }

        memories.append(entry)

        self._atomic_write(
            json.dumps(
                memories,
                indent=4,
            )
        )

        logger.info(
            "Memory saved (id=%s, type=%s).",
            memory_id,
            memory_type,
        )

        return memory_id

    # =====================================================
    # Read
    # =====================================================

    def load(self) -> list:

        try:

            return json.loads(
                self.memory_file.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            logger.exception(
                "Failed to load memory."
            )

            return []

    # =====================================================
    # Internal
    # =====================================================

    def _atomic_write(self, content: str) -> None:
        """
        Write `content` to self.memory_file atomically: write to a
        temp file in the same directory, flush + fsync it, then
        os.replace() it over the real file. os.replace() is atomic on
        both POSIX and Windows, so a crash or concurrent read during
        the write can never observe a truncated/corrupted memory.json
        -- readers either see the old complete file or the new
        complete file, never a partial one.
        """

        fd, tmp_path = tempfile.mkstemp(
            dir=self.memory_dir,
            prefix=".memory-",
            suffix=".tmp",
        )

        try:

            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:

                tmp_file.write(content)

                tmp_file.flush()

                os.fsync(tmp_file.fileno())

            os.replace(tmp_path, self.memory_file)

        except Exception:

            logger.exception(
                "Atomic write to memory file failed."
            )

            try:
                os.remove(tmp_path)
            except OSError:
                pass

            raise