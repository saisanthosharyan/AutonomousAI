from __future__ import annotations

from collections import defaultdict
from typing import Any


class ContextBuilder:
    """
    Converts retrieved memories into a compact,
    structured prompt for the LLM.

    Responsibilities

    - Remove duplicates
    - Group by memory type
    - Prefer successful memories
    - Truncate very large memories
    - Produce deterministic output
    """

    MAX_FIELD_LENGTH = 600
    MAX_TOTAL_LENGTH = 8000

    def build(
        self,
        memories: list[dict[str, Any]],
        max_chars: int | None = None,
    ) -> str:

        if not memories:
            return "No relevant previous memories were found."

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

        seen = set()

        for memory in memories:

            key = (
                memory.get("type"),
                memory.get("prompt"),
                memory.get("error"),
                memory.get("fix"),
            )

            if key in seen:
                continue

            seen.add(key)

            grouped[
                memory.get(
                    "type",
                    "unknown",
                )
            ].append(memory)

        sections: list[str] = []

        sections.append(
            "=" * 60
        )

        sections.append(
            "PREVIOUS RELEVANT MEMORIES"
        )

        sections.append(
            "=" * 60
        )

        total_size = 0

        order = [
            "execution_success",
            "repair_applied",
            "repair",
            "review",
            "execution_failure",
            "retry_failed",
        ]

        for memory_type in order:

            items = grouped.get(memory_type)

            if not items:
                continue

            sections.append("")
            sections.append(
                f"## {memory_type.replace('_', ' ').title()}"
            )

            for index, memory in enumerate(
                items,
                start=1,
            ):

                block = self._format_memory(
                    index=index,
                    memory=memory,
                )

                limit = max_chars or self.MAX_TOTAL_LENGTH

                if (
                    total_size + len(block)
                    > limit
                ):
                    break

                total_size += len(block)

                sections.append(block)

        return "\n".join(sections)

    def _format_memory(
        self,
        *,
        index: int,
        memory: dict[str, Any],
    ) -> str:

        def trim(text: str) -> str:

            text = text.strip()

            if len(text) <= self.MAX_FIELD_LENGTH:
                return text

            return (
                text[
                    : self.MAX_FIELD_LENGTH
                ]
                + "\n..."
            )

        parts = []

        parts.append(
            f"\nMemory #{index}"
        )

        if memory.get("prompt"):

            parts.append(
                f"Prompt:\n{trim(memory['prompt'])}"
            )

        if memory.get("error"):

            parts.append(
                f"Error:\n{trim(memory['error'])}"
            )

        if memory.get("fix"):

            parts.append(
                f"Fix:\n{trim(memory['fix'])}"
            )

        if memory.get("review"):

            parts.append(
                f"Review:\n{trim(memory['review'])}"
            )

        metadata = memory.get(
            "metadata",
            {},
        )

        if metadata:

            parts.append(
                f"Metadata:\n{metadata}"
            )

        parts.append(
            f"Success: {memory.get('success', False)}"
        )

        parts.append(
            "-" * 50
        )

        return "\n".join(parts)