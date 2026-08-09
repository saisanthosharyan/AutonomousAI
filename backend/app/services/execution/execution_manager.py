from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional, Protocol, runtime_checkable

from app.core.logger import logger

from app.services.execution.python_executor import PythonExecutor
from app.services.execution.node_executor import NodeExecutor
from app.services.execution.java_executor import JavaExecutor
from app.services.execution.cpp_executor import CPPExecutor
from app.services.execution.docker_executor import DockerExecutor
from app.services.execution.execution_logger import ExecutionLogger

# Single source of truth for project-type / language / framework detection.
# ExecutionManager no longer re-implements detection heuristics of its own —
# it only knows how to run things once it's told what it's dealing with.
from app.project.project_analyzer import ProjectAnalyzer


@runtime_checkable
class Executor(Protocol):
    """
    Minimal structural type for executors: anything with a
    `run(project_path)` method qualifies. This gives us type
    safety without depending on a concrete BaseExecutor class
    that may not exist yet in the project.
    """

    def run(self, project_path: str) -> dict: ...


@dataclass
class ExecutionResult:
    """
    Structured result of a project execution attempt.

    Replaces the previous ad-hoc dict so callers (Reviewer, Fixer,
    ExecutionLogger, API layer) get a consistent, typed contract
    instead of relying on dict key conventions.
    """

    success: bool = False
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1
    execution_time: float = 0.0
    project_type: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


class ExecutionManager:
    """
    Executes a generated project using the appropriate executor,
    based on the project type reported by ProjectAnalyzer.

    Supported project types:

    • Python
    • Node.js
    • Java
    • C++
    • Docker

    If Docker execution is unavailable, the manager automatically
    falls back to the underlying native executor (as reported by
    ProjectAnalyzer for the non-docker case).
    """

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def __init__(self, analyzer: Optional[ProjectAnalyzer] = None) -> None:

        self.executors: Dict[str, Executor] = {
            "python": PythonExecutor(),
            "node": NodeExecutor(),
            "java": JavaExecutor(),
            "cpp": CPPExecutor(),
            "docker": DockerExecutor(),
        }

        # Allow injection for testing / reuse of an already-configured
        # analyzer; default to a fresh one otherwise.
        self.analyzer = analyzer or ProjectAnalyzer()

        logger.info(
            "ExecutionManager initialized with %d executors.",
            len(self.executors),
        )

    # ==========================================================
    # DOCKER AVAILABILITY
    # ==========================================================

    def _docker_available(self) -> bool:
        """
        Check that Docker is not just installed, but actually
        running and reachable (`docker info` succeeds).
        """

        try:
            subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=True,
            )
            return True

        except Exception:
            logger.warning(
                "Docker installed but unavailable (daemon not running?)."
            )
            return False

    # ==========================================================
    # DETECT PROJECT TYPE (delegated to ProjectAnalyzer)
    # ==========================================================

    def detect_project_type(self, project_path: str) -> str:
        """
        Delegate detection to ProjectAnalyzer, the single source of
        truth for language/framework/test-framework/entry-point
        detection across ExecutionManager and TestManager.

        Execution-specific nuance (Docker daemon reachability) is
        still handled here, since that's runtime environment state,
        not project structure.
        """

        project = Path(project_path).resolve()

        if not project.exists():
            raise FileNotFoundError(
                f"Project directory does not exist: {project}"
            )

        if not project.is_dir():
            raise NotADirectoryError(
                f"Project path is not a directory: {project}"
            )

        logger.info("Detecting project type: %s", project)

        detected = self.analyzer.detect(str(project))

        # If the analyzer says "docker" but the daemon isn't actually
        # reachable, fall back to whatever the analyzer would report
        # for a non-docker execution of the same project.
        if detected == "docker" and not self._docker_available():

            logger.warning(
                "Dockerfile exists but Docker is not usable; "
                "falling back to native detection."
            )

            fallback = self.analyzer.detect(
                str(project),
                exclude={"docker"},
            )

            return fallback or "unknown"

        logger.info("Detected project type: %s", detected)

        return detected or "unknown"

    # ==========================================================
    # GET EXECUTOR
    # ==========================================================

    def _get_executor(self, project_type: str) -> Executor:

        executor = self.executors.get(project_type)

        if executor is None:
            raise RuntimeError(
                f"No executor registered for '{project_type}'."
            )

        if not hasattr(executor, "run"):
            raise RuntimeError(
                f"Executor '{project_type}' has no run() method."
            )

        return executor

    # ==========================================================
    # NORMALIZE EXECUTOR RESULT
    # ==========================================================

    @staticmethod
    def _normalize_execution_result(execution_result: object) -> dict:
        """
        Guarantee that whatever an executor returns is usable as
        a dict downstream. Executors are third-party-ish code
        (one per language); a buggy one returning None, a string,
        a list, or anything else shouldn't crash the manager.
        """

        if not isinstance(execution_result, dict):

            logger.warning(
                "Executor returned a non-dict result (%s); normalizing.",
                type(execution_result).__name__,
            )

            return {
                "success": False,
                "stdout": "",
                "stderr": "Executor returned invalid result.",
                "return_code": -1,
            }

        return execution_result

    # ==========================================================
    # RUN PROJECT
    # ==========================================================

    def run(self, project_path: str) -> ExecutionResult:

        start_time = time.perf_counter()

        result = ExecutionResult()

        logger.info("=" * 60)
        logger.info("Execution Manager Started")
        logger.info("=" * 60)

        try:

            # --------------------------------------------------
            # Detect project type
            # --------------------------------------------------

            project_type = self.detect_project_type(project_path)

            result.project_type = project_type

            if project_type == "unknown":
                result.stderr = "Unable to detect generated project type."
                return result

            # --------------------------------------------------
            # Get executor
            # --------------------------------------------------

            executor = self._get_executor(project_type)

            logger.info("Using %s executor.", project_type)

            # --------------------------------------------------
            # Execute project
            # --------------------------------------------------

            execution_result = executor.run(project_path)

            execution_result = self._normalize_execution_result(
                execution_result
            )

            # --------------------------------------------------
            # Docker fallback (executor itself opted to skip, e.g.
            # image build failed for a reason short of "unavailable")
            # --------------------------------------------------

            if project_type == "docker" and execution_result.get(
                "skip", False
            ):

                fallback = self.analyzer.detect(
                    project_path,
                    exclude={"docker"},
                )

                if fallback and fallback != "unknown":

                    logger.info(
                        "Docker skipped. Falling back to %s.",
                        fallback,
                    )

                    fallback_executor = self._get_executor(fallback)

                    execution_result = self._normalize_execution_result(
                        fallback_executor.run(project_path)
                    )

                    result.project_type = fallback

            # --------------------------------------------------
            # Normalize result
            # --------------------------------------------------

            result.success = bool(execution_result.get("success", False))
            result.stdout = str(execution_result.get("stdout", "") or "")
            result.stderr = str(execution_result.get("stderr", "") or "")
            result.return_code = int(
                execution_result.get("return_code", -1)
            )

            return result

        except Exception as exc:

            logger.exception("Execution Manager crashed.")

            result.success = False
            result.stderr = str(exc)
            result.return_code = -1

            return result

        finally:

            result.execution_time = round(
                time.perf_counter() - start_time, 3
            )

            try:
                ExecutionLogger(project_path).save(result.to_dict())

            except Exception:
                logger.exception("Failed to write execution log.")

            if result.success:
                logger.info("Execution completed successfully.")

            else:
                logger.warning("Execution failed.")

                if result.stderr:
                    logger.error("Execution failed: %s", result.stderr)

            logger.info("=" * 60)
            logger.info("Execution Manager Finished")
            logger.info("=" * 60)

    # ==========================================================
    # REGISTER EXECUTOR
    # ==========================================================

    def register_executor(self, name: str, executor: Executor) -> None:
        """
        Register a custom executor.
        """

        if not hasattr(executor, "run"):
            raise TypeError("Executor must implement run().")

        self.executors[name] = executor

        logger.info("Registered executor: %s", name)

    # ==========================================================
    # AVAILABLE EXECUTORS
    # ==========================================================

    def available_executors(self) -> list[str]:
        """
        Return all registered executors.
        """

        return sorted(self.executors.keys())

    # ==========================================================
    # HAS EXECUTOR
    # ==========================================================

    def has_executor(self, name: str) -> bool:
        """
        Check whether an executor exists.
        """

        return name in self.executors