from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Protocol, runtime_checkable

from app.core.logger import logger

from app.services.execution.python_executor import PythonExecutor
from app.services.execution.node_executor import NodeExecutor
from app.services.execution.java_executor import JavaExecutor
from app.services.execution.cpp_executor import CPPExecutor
from app.services.execution.docker_executor import DockerExecutor
from app.services.execution.static_web_executor import StaticWebExecutor
from app.services.execution.execution_logger import ExecutionLogger

# Single source of truth for project-type / language / framework detection.
from app.project.project_analyzer import ProjectAnalyzer


@runtime_checkable
class Executor(Protocol):
    """
    Minimal structural type for executors.

    Executors may return either a dictionary or an ExecutionResult.
    """

    def run(self, project_path: str) -> object:
        ...


@dataclass
class ExecutionResult:
    """
    Structured result of a project execution attempt.
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
    Executes a generated project using the appropriate executor.

    Supported project types:

    • Python
    • Node.js
    • Java
    • C++
    • Docker
    • Static Web (HTML/CSS/JavaScript)

    Project-type detection is delegated to ProjectAnalyzer.
    """

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def __init__(
        self,
        analyzer: Optional[ProjectAnalyzer] = None,
    ) -> None:

        self.executors: Dict[str, Executor] = {
            "python": PythonExecutor(),
            "node": NodeExecutor(),
            "java": JavaExecutor(),
            "cpp": CPPExecutor(),
            "docker": DockerExecutor(),
            "static_web": StaticWebExecutor(),
        }

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
        Check whether Docker is installed and reachable.
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
                "Docker installed but unavailable "
                "(daemon not running?)."
            )

            return False

    # ==========================================================
    # DETECT PROJECT TYPE
    # ==========================================================

    def detect_project_type(
        self,
        project_path: str,
    ) -> str:
        """
        Delegate project-type detection to ProjectAnalyzer.

        Docker availability is handled here because it depends on
        the runtime environment rather than project structure.
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

        logger.info(
            "Detecting project type: %s",
            project,
        )

        detected = self.analyzer.detect(
            str(project)
        )

        # ------------------------------------------------------
        # Docker fallback
        # ------------------------------------------------------

        if (
            detected == "docker"
            and not self._docker_available()
        ):

            logger.warning(
                "Dockerfile exists but Docker is not usable; "
                "falling back to native detection."
            )

            fallback = self.analyzer.detect(
                str(project),
                exclude={"docker"},
            )

            return fallback or "unknown"

        logger.info(
            "Detected project type: %s",
            detected,
        )

        return detected or "unknown"

    # ==========================================================
    # GET EXECUTOR
    # ==========================================================

    def _get_executor(
        self,
        project_type: str,
    ) -> Executor:

        executor = self.executors.get(
            project_type
        )

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
    def _normalize_execution_result(
        execution_result: object,
    ) -> dict:
        """
        Normalize executor output into a dictionary.

        Supported executor result types:

        - dict
        - ExecutionResult

        This allows typed executors such as StaticWebExecutor to
        coexist with older executors that return dictionaries.
        """

        # ------------------------------------------------------
        # Dictionary result
        # ------------------------------------------------------

        if isinstance(
            execution_result,
            dict,
        ):
            return execution_result

        # ------------------------------------------------------
        # Typed ExecutionResult
        # ------------------------------------------------------

        if isinstance(
            execution_result,
            ExecutionResult,
        ):
            return execution_result.to_dict()

        # ------------------------------------------------------
        # Unsupported result
        # ------------------------------------------------------

        logger.warning(
            "Executor returned an unsupported result type (%s); "
            "normalizing.",
            type(execution_result).__name__,
        )

        return {
            "success": False,
            "stdout": "",
            "stderr": "Executor returned invalid result.",
            "return_code": -1,
        }

    # ==========================================================
    # RUN PROJECT
    # ==========================================================

    def run(
        self,
        project_path: str,
    ) -> ExecutionResult:

        start_time = time.perf_counter()

        result = ExecutionResult()

        logger.info("=" * 60)
        logger.info("Execution Manager Started")
        logger.info("=" * 60)

        try:

            # --------------------------------------------------
            # Detect project type
            # --------------------------------------------------

            project_type = self.detect_project_type(
                project_path
            )

            result.project_type = project_type

            if project_type == "unknown":

                result.stderr = (
                    "Unable to detect generated project type."
                )

                return result

            # --------------------------------------------------
            # Get executor
            # --------------------------------------------------

            executor = self._get_executor(
                project_type
            )

            logger.info(
                "Using %s executor.",
                project_type,
            )

            # --------------------------------------------------
            # Execute project
            # --------------------------------------------------

            execution_result = executor.run(
                project_path
            )

            execution_result = (
                self._normalize_execution_result(
                    execution_result
                )
            )

            # --------------------------------------------------
            # Docker fallback
            # --------------------------------------------------

            if (
                project_type == "docker"
                and execution_result.get(
                    "skip",
                    False,
                )
            ):

                fallback = self.analyzer.detect(
                    project_path,
                    exclude={"docker"},
                )

                if (
                    fallback
                    and fallback != "unknown"
                ):

                    logger.info(
                        "Docker skipped. Falling back to %s.",
                        fallback,
                    )

                    fallback_executor = (
                        self._get_executor(
                            fallback
                        )
                    )

                    execution_result = (
                        self._normalize_execution_result(
                            fallback_executor.run(
                                project_path
                            )
                        )
                    )

                    result.project_type = fallback

            # --------------------------------------------------
            # Normalize result
            # --------------------------------------------------

            result.success = bool(
                execution_result.get(
                    "success",
                    False,
                )
            )

            result.stdout = str(
                execution_result.get(
                    "stdout",
                    "",
                )
                or ""
            )

            result.stderr = str(
                execution_result.get(
                    "stderr",
                    "",
                )
                or ""
            )

            result.return_code = int(
                execution_result.get(
                    "return_code",
                    -1,
                )
            )

            return result

        except Exception as exc:

            logger.exception(
                "Execution Manager crashed."
            )

            result.success = False
            result.stderr = str(exc)
            result.return_code = -1

            return result

        finally:

            result.execution_time = round(
                time.perf_counter()
                - start_time,
                3,
            )

            # --------------------------------------------------
            # Save execution log
            # --------------------------------------------------

            try:

                ExecutionLogger(
                    project_path
                ).save(
                    result.to_dict()
                )

            except Exception:

                logger.exception(
                    "Failed to write execution log."
                )

            # --------------------------------------------------
            # Logging
            # --------------------------------------------------

            if result.success:

                logger.info(
                    "Execution completed successfully."
                )

            else:

                logger.warning(
                    "Execution failed."
                )

                if result.stderr:

                    logger.error(
                        "Execution failed: %s",
                        result.stderr,
                    )

            logger.info("=" * 60)
            logger.info(
                "Execution Manager Finished"
            )
            logger.info("=" * 60)

    # ==========================================================
    # REGISTER EXECUTOR
    # ==========================================================

    def register_executor(
        self,
        name: str,
        executor: Executor,
    ) -> None:
        """
        Register a custom executor.
        """

        if not hasattr(
            executor,
            "run",
        ):
            raise TypeError(
                "Executor must implement run()."
            )

        self.executors[name] = executor

        logger.info(
            "Registered executor: %s",
            name,
        )

    # ==========================================================
    # AVAILABLE EXECUTORS
    # ==========================================================

    def available_executors(self) -> list[str]:
        """
        Return all registered executors.
        """

        return sorted(
            self.executors.keys()
        )

    # ==========================================================
    # HAS EXECUTOR
    # ==========================================================

    def has_executor(
        self,
        name: str,
    ) -> bool:
        """
        Check whether an executor exists.
        """

        return name in self.executors