from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ExecutionResult:
    """
    Represents the result of executing a generated project.
    """

    success: bool
    stdout: str
    stderr: str
    return_code: int

    command: str = ""
    working_directory: str = ""

    execution_time: float = 0.0

    timed_out: bool = False

    error_category: Optional[str] = None

    exception: Optional[str] = None