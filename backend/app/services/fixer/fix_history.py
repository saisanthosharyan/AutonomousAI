from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from app.core.logger import logger

class FixHistory:
    """
    Stores every automatic repair attempt.

    history.json example:

    [
        {
            "timestamp": "...",
            "attempt": 1,
            "success": false,
            "modified_files": [...],
            "error": "...",
            "summary": "..."
        }
    ]
    """

    FILE_NAME = "fix_history.json"

    def __init__(
        self,
        project_path: str,
    ) -> None:

        self.project = Path(project_path).resolve()

        self.history_file = (
            self.project / self.FILE_NAME
        )

    # =====================================================
    # LOAD
    # =====================================================

    def load(
        self,
    ) -> list[dict[str, Any]]:

        if not self.history_file.exists():
            return []

        try:

            with open(
                self.history_file,
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(file)

                if isinstance(data, list):
                    return data

        except Exception:
            logger.exception(
                "Failed to load fix history."
            )

        return []

    # =====================================================
    # SAVE ENTRY
    # =====================================================

    def save(
        self,
        *,
        success: bool,
        modified_files: list[str],
        error: str = "",
        summary: str = "",
    ) -> None:

        self.project.mkdir(
            parents=True,
            exist_ok=True,
        )

        history = self.load()

        history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "attempt": len(history) + 1,
                "success": success,
                "modified_files": modified_files,
                "error": error,
                "summary": summary,
            }
        )

        temp_file = self.history_file.with_suffix(".tmp")

        with open(
            temp_file,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                history,
                file,
                indent=4,
            )

        temp_file.replace(self.history_file)
    # =====================================================
    # LAST ATTEMPT
    # =====================================================

    def last_attempt(
        self,
    ) -> dict | None:

        history = self.load()

        if not history:
            return None

        return history[-1]

    # =====================================================
    # TOTAL ATTEMPTS
    # =====================================================

    def total_attempts(
        self,
    ) -> int:

        return len(self.load())

    # =====================================================
    # CLEAR HISTORY
    # =====================================================

    def clear(
        self,
    ) -> None:

        if self.history_file.exists():
            self.history_file.unlink()