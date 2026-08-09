"""
ExecutionLogger
===============

Persists the results of a single command execution (stdout, stderr,
structured JSON, human-readable log) to disk in a safe, debuggable,
and dashboard-friendly way.

Improvements over the original implementation:
    1.  Uses the standard `logging` module instead of silent writes.
    2.  Every file operation is wrapped in try/except so a disk error
        never crashes the pipeline.
    3.  Saves the executor + command that was run.
    4.  Saves project type / framework metadata.
    5.  Saves execution duration in both seconds and milliseconds.
    6.  Archives every execution into a `history/` folder, timestamped,
        while still keeping `latest.*` for quick access.
    7.  Captures environment info (python/node/docker versions, os, platform).
    8.  Rotates `execution.log` once it grows past a size threshold.
    9.  Provides `load_latest()` and `load_history()` readers.
    10. Converts raw tracebacks into structured error dicts.
    11. Uses atomic writes (write to .tmp then os.replace) everywhere.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional


class ExecutionLogger:
    """Saves and retrieves execution results for a project."""

    LOG_ROTATE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    LOG_ROTATE_BACKUPS = 5

    def __init__(self, project_path: str, logger: Optional[logging.Logger] = None):
        self.project = Path(project_path)
        self.logs = self.project / "execution"
        self.history_dir = self.logs / "history"

        self.logs.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logger or self._build_default_logger()

    # ------------------------------------------------------------------ #
    # Setup helpers
    # ------------------------------------------------------------------ #
    def _build_default_logger(self) -> logging.Logger:
        """Creates a rotating file logger scoped to this project's execution dir."""
        logger = logging.getLogger(f"ExecutionLogger.{self.project.resolve()}")
        logger.setLevel(logging.INFO)

        # Avoid duplicate handlers if instantiated multiple times.
        if not logger.handlers:
            handler = RotatingFileHandler(
                self.logs / "execution.log",
                maxBytes=self.LOG_ROTATE_MAX_BYTES,
                backupCount=self.LOG_ROTATE_BACKUPS,
                encoding="utf-8",
            )
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    # ------------------------------------------------------------------ #
    # Atomic write helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _atomic_write_text(path: Path, content: str) -> None:
        fd, tmp_path = tempfile.mkstemp(
            dir=path.parent, prefix=path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @staticmethod
    def _atomic_write_json(path: Path, data: dict) -> None:
        fd, tmp_path = tempfile.mkstemp(
            dir=path.parent, prefix=path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ------------------------------------------------------------------ #
    # Environment / metadata helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _safe_version(cmd: list[str]) -> Optional[str]:
        try:
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5
            )
            return (out.stdout or out.stderr).strip() or None
        except Exception:
            return None

    def _collect_environment_info(self) -> dict:
        return {
            "python_version": platform.python_version(),
            "node_version": self._safe_version(["node", "--version"]),
            "docker_version": self._safe_version(["docker", "--version"]),
            "os": platform.system(),
            "platform": platform.platform(),
        }

    @staticmethod
    def _structure_error(result: dict) -> Optional[dict]:
        """Turns raw stderr / exception info into a structured error dict."""
        exc = result.get("exception")
        if isinstance(exc, BaseException):
            return {
                "error_type": type(exc).__name__,
                "message": str(exc),
                "traceback": "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                ),
            }

        stderr = result.get("stderr") or ""
        if not result.get("success", True) and stderr.strip():
            lines = stderr.strip().splitlines()
            error_type = "UnknownError"
            for line in reversed(lines):
                if ":" in line and not line.startswith(" "):
                    error_type = line.split(":", 1)[0].strip()
                    break
            return {
                "error_type": error_type,
                "message": lines[-1].strip() if lines else "",
                "traceback": stderr,
            }

        return None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def save(
        self,
        result: dict[str, Any],
        executor: Optional[str] = None,
        command: Optional[str] = None,
        project_type: Optional[str] = None,
        framework: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Saves stdout, stderr, and a structured JSON record for a single
        execution. Also archives the run into history/ and appends a
        human-readable entry to the rotating execution.log.

        Returns the record that was saved, or None if saving failed.
        """
        try:
            self.logger.info("Saving execution results...")

            timestamp_dt = datetime.now()
            timestamp_str = timestamp_dt.strftime("%Y%m%d_%H%M%S")

            stdout = result.get("stdout", "") or ""
            stderr = result.get("stderr", "") or ""

            exec_time_sec = result.get("execution_time", 0) or 0
            exec_time_ms = round(exec_time_sec * 1000, 2)

            record = {
                "timestamp": timestamp_dt.isoformat(),
                "success": result.get("success"),
                "return_code": result.get("return_code"),
                "execution_time_sec": exec_time_sec,
                "execution_time_ms": exec_time_ms,
                "executor": executor,
                "command": command,
                "project_type": project_type,
                "framework": framework,
                "environment": self._collect_environment_info(),
            }

            error_info = self._structure_error(result)
            if error_info:
                record["error"] = error_info

            # --- latest ---
            self._atomic_write_text(self.logs / "latest_stdout.txt", stdout)
            self._atomic_write_text(self.logs / "latest_stderr.txt", stderr)
            self._atomic_write_json(self.logs / "latest.json", record)

            # --- history (archive every execution) ---
            self._atomic_write_text(
                self.history_dir / f"{timestamp_str}_stdout.txt", stdout
            )
            self._atomic_write_text(
                self.history_dir / f"{timestamp_str}_stderr.txt", stderr
            )
            self._atomic_write_json(
                self.history_dir / f"{timestamp_str}.json", record
            )

            # --- human readable rotating log ---
            self.logger.info(
                "Success=%s | ReturnCode=%s | Time=%.3fs (%sms) | Executor=%s | Command=%s",
                record["success"],
                record["return_code"],
                exec_time_sec,
                exec_time_ms,
                executor,
                command,
            )

            self.logger.info("Execution log saved successfully.")
            return record

        except Exception:
            self.logger.exception("Failed to save execution log.")
            return None

    def load_latest(self) -> Optional[dict]:
        """Loads the most recent execution record, or None if unavailable."""
        try:
            latest_path = self.logs / "latest.json"
            if not latest_path.exists():
                return None
            with open(latest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            self.logger.exception("Failed to load latest execution log.")
            return None

    def load_history(self, limit: Optional[int] = None) -> list[dict]:
        """
        Loads past execution records, most recent first.
        `limit` optionally caps how many records are returned.
        """
        try:
            files = sorted(
                self.history_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if limit is not None:
                files = files[:limit]

            records = []
            for path in files:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        records.append(json.load(f))
                except Exception:
                    self.logger.exception("Failed to load history file: %s", path)

            return records
        except Exception:
            self.logger.exception("Failed to load execution history.")
            return []

    def clear_history(self, keep_latest: bool = True) -> None:
        """Deletes archived history files. Keeps `latest.*` unless told otherwise."""
        try:
            shutil.rmtree(self.history_dir, ignore_errors=True)
            self.history_dir.mkdir(parents=True, exist_ok=True)
            if not keep_latest:
                for f in ("latest.json", "latest_stdout.txt", "latest_stderr.txt"):
                    p = self.logs / f
                    if p.exists():
                        p.unlink()
            self.logger.info("Execution history cleared.")
        except Exception:
            self.logger.exception("Failed to clear execution history.")