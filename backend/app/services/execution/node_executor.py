import hashlib
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

from app.core.logger import logger


class NodeExecutor:
    """
    Executes Node.js based projects.

    Supported:
    - React (CRA / Vite)
    - Next.js
    - Express
    - NestJS
    - TypeScript (ts-node / tsx)
    - Plain Node.js
    """

    INSTALL_TIMEOUT = 300
    EXECUTION_TIMEOUT = 120
    SERVER_STARTUP_GRACE = 20  # secs to watch for a "ready" signal before falling back to full timeout

    IGNORE_DIRS = {"node_modules", "dist", "build", "coverage", ".next", ".git", ".turbo"}

    FRONTEND_DEPS = {"next", "vite", "react-scripts", "@vue/cli-service", "@angular/core"}

    SERVER_READY_PATTERNS = (
        "listening",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "ready in",
        "compiled successfully",
        "server started",
        "started server",
    )

    TS_RUNNERS = ["tsx", "ts-node"]

    def run(self, project_path: str) -> dict:

        project = Path(project_path).resolve()

        if not project.exists():
            return self._result(False, "", f"Project does not exist: {project}", -1, 0)

        logger.info("=" * 60)
        logger.info("Node Executor Started")
        logger.info("=" * 60)

        node_path = shutil.which("node")
        npm_path = shutil.which("npm")

        if node_path is None:
            return self._result(False, "", "Node.js not found in PATH.", -1, 0)

        if npm_path is None:
            return self._result(False, "", "npm not found in PATH.", -1, 0)

        logger.info(f"Node executable : {node_path}")
        logger.info(f"NPM executable  : {npm_path}")

        package_json = project / "package.json"

        try:

            if package_json.is_file():

                package = self._read_package(package_json)

                install_result = self._install_dependencies(project, npm_path)

                if install_result is not None:
                    return install_result

                command, is_server = self._select_command(package, project, npm_path, node_path)

            else:

                command = self._fallback_command(project, node_path)
                is_server = True  # unknown plain scripts: treat cautiously, watch for ready signal

            env = self._build_env(project)

            return self._execute(project, command, is_server, env)

        except RuntimeError as e:

            return self._result(False, "", str(e), -1, 0)

        finally:

            logger.info("=" * 60)
            logger.info("Node Executor Finished")
            logger.info("=" * 60)

    def _result(self, success: bool, stdout: str, stderr: str, return_code: int, execution_time: float):
        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
            "execution_time": execution_time,
        }

    def _read_package(self, package_json: Path):

        try:
            with open(package_json, "r", encoding="utf-8") as file:
                package = json.load(file)

                if not isinstance(package, dict):
                    raise RuntimeError("Invalid package.json")

            logger.info("package.json loaded successfully.")
            return package

        except Exception as e:
            logger.exception("Failed to read package.json")
            raise RuntimeError(str(e))

    # -------------------------------------------------
    # Dependency installation (Issue 1, 10)
    # -------------------------------------------------

    def _dependency_fingerprint(self, project: Path) -> str:
        """
        Hash package.json + lockfile (if present) so we reinstall whenever
        dependencies actually change, instead of trusting node_modules'
        mere existence.
        """
        hasher = hashlib.sha256()

        for name in ("package.json", "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock"):
            file = project / name
            if file.is_file():
                hasher.update(file.read_bytes())

        return hasher.hexdigest()

    def _install_dependencies(self, project: Path, npm_path: str):

        node_modules = project / "node_modules"
        marker = node_modules / ".install_fingerprint"

        current_fingerprint = self._dependency_fingerprint(project)

        if node_modules.is_dir() and marker.is_file():
            try:
                previous_fingerprint = marker.read_text(encoding="utf-8").strip()
            except Exception:
                previous_fingerprint = None

            if previous_fingerprint == current_fingerprint:
                logger.info("Dependencies unchanged since last install. Skipping.")
                return None

            logger.info("Dependency manifest changed since last install. Reinstalling.")

        logger.info("Installing Node dependencies...")

        start = time.perf_counter()

        try:

            process = subprocess.run(
                [npm_path, "install", "--no-audit", "--no-fund"],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=self.INSTALL_TIMEOUT,
            )

            elapsed = round(time.perf_counter() - start, 2)

            if process.stdout:
                logger.info(process.stdout)

            if process.stderr:
                logger.error(process.stderr)

            if process.returncode != 0:
                return self._result(False, process.stdout, process.stderr, process.returncode, elapsed)

            try:
                node_modules.mkdir(exist_ok=True)
                marker.write_text(current_fingerprint, encoding="utf-8")
            except Exception:
                logger.warning("Could not write install fingerprint marker.")

            logger.info(f"Dependencies installed successfully in {elapsed} seconds.")

            return None

        except subprocess.TimeoutExpired:
            return self._result(False, "", "npm install timed out.", -1, self.INSTALL_TIMEOUT)

        except Exception as e:
            logger.exception("Dependency installation failed.")
            return self._result(False, "", str(e), -1, 0)

    # -------------------------------------------------
    # Environment variables (Issue 7)
    # -------------------------------------------------

    def _build_env(self, project: Path) -> dict:

        env = os.environ.copy()

        env_file = project / ".env"
        env_example = project / ".env.example"

        source = env_file if env_file.is_file() else (env_example if env_example.is_file() else None)

        if source is None:
            return env

        try:
            for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()

                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                # Don't clobber a value the platform explicitly already set.
                env.setdefault(key, value)

            if source is env_example:
                logger.info("No .env found; loaded defaults from .env.example.")

        except Exception:
            logger.warning("Failed to parse .env file; continuing without it.")

        return env

    # -------------------------------------------------
    # Command selection (Issue 2, 4, 5)
    # -------------------------------------------------

    def _select_command(self, package: dict, project: Path, npm_path: str, node_path: str):
        """
        Returns (command, is_server).
        is_server=True means the process may run indefinitely (dev server) and
        should be watched for a "ready" signal rather than run to completion.
        """

        scripts = package.get("scripts", {})

        dependencies = {
            **package.get("dependencies", {}),
            **package.get("devDependencies", {}),
        }

        logger.info("Detecting Node.js project type...")

        is_frontend = any(dep in dependencies for dep in self.FRONTEND_DEPS)

        # -------------------------------------------------
        # Tests take priority when present (Issue 5)
        # -------------------------------------------------

        if "test" in scripts and any(
            runner in dependencies for runner in ("jest", "vitest", "mocha", "ava")
        ):
            logger.info("Detected test suite. Running npm test.")
            return [npm_path, "run", "test"], False

        # -------------------------------------------------
        # Frontend frameworks: "build" is a valid smoke test
        # -------------------------------------------------

        if is_frontend:

            framework = next((dep for dep in self.FRONTEND_DEPS if dep in dependencies), "frontend")
            logger.info(f"Detected frontend project ({framework}).")

            if "build" in scripts:
                return [npm_path, "run", "build"], False

            if "dev" in scripts:
                return [npm_path, "run", "dev"], True

            if "start" in scripts:
                return [npm_path, "run", "start"], True

        # -------------------------------------------------
        # NestJS
        # -------------------------------------------------

        if "@nestjs/core" in dependencies:

            logger.info("Detected NestJS project.")

            if "start" in scripts:
                return [npm_path, "run", "start"], True

            if "build" in scripts:
                return [npm_path, "run", "build"], False

        # -------------------------------------------------
        # Express / generic Node backend
        # -------------------------------------------------

        if "express" in dependencies:

            logger.info("Detected Express project.")

            if "start" in scripts:
                return [npm_path, "run", "start"], True

            if "dev" in scripts:
                return [npm_path, "run", "dev"], True

            server = project / "server.js"

            if server.exists():
                return [node_path, str(server)], True

        # -------------------------------------------------
        # TypeScript entry points (Issue 4)
        # -------------------------------------------------

        if "typescript" in dependencies:

            ts_command = self._typescript_command(project, dependencies)

            if ts_command is not None:
                logger.info("Detected TypeScript project.")
                return ts_command, True

        # -------------------------------------------------
        # Generic package.json scripts
        # -------------------------------------------------

        priority = ["start", "dev", "serve", "preview", "build"]

        for script in priority:

            if script in scripts:

                logger.info(f"Using npm script: {script}")

                # Anything other than "build" may be a long-running server.
                return [npm_path, "run", script], script != "build"

        # -------------------------------------------------
        # Plain Node.js fallback
        # -------------------------------------------------

        return self._fallback_command(project, node_path), True

    def _typescript_command(self, project: Path, dependencies: dict):

        candidates = [
            "src/main.ts",
            "src/index.ts",
            "src/server.ts",
            "src/app.ts",
            "main.ts",
            "index.ts",
            "server.ts",
            "app.ts",
        ]

        entry = next((project / c for c in candidates if (project / c).exists()), None)

        if entry is None:
            return None

        for runner in self.TS_RUNNERS:
            runner_path = shutil.which(runner) or (project / "node_modules" / ".bin" / runner)

            if isinstance(runner_path, Path):
                if runner_path.exists():
                    return [str(runner_path), str(entry)]
            elif runner_path:
                return [runner_path, str(entry)]

        # No runner installed; nothing we can do reliably.
        return None

    def _fallback_command(self, project: Path, node_path: str):

        logger.info("Using fallback Node.js execution.")

        candidates = [
            "server.js",
            "index.js",
            "app.js",
            "main.js",
            "src/server.js",
            "src/index.js",
            "src/app.js",
            "src/main.js",
        ]

        for candidate in candidates:

            file = project / candidate

            # Guard against picking up entry files inside ignored build/output dirs.
            if any(part in self.IGNORE_DIRS for part in file.relative_to(project).parts[:-1]):
                continue

            if file.exists():
                logger.info(f"Found entry file: {candidate}")
                return [node_path, str(file)]

        raise RuntimeError("No runnable Node.js entry file found.")

    # -------------------------------------------------
    # Execution (Issue 3, 8, minor cleanups)
    # -------------------------------------------------

    def _execute(self, project: Path, command: list[str], is_server: bool, env: dict):

        logger.info("=" * 60)
        logger.info("Executing Node Project")
        logger.info("=" * 60)
        logger.info(f"Command: {' '.join(command)}")

        start = time.perf_counter()

        try:
            process = subprocess.Popen(
                command,
                cwd=project,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                bufsize=1,
                env=env,
            )
        except Exception as e:
            logger.exception("Failed to start process.")
            return self._result(False, "", str(e), -1, 0)

        output_lines: list[str] = []
        line_queue: "queue.Queue[str | None]" = queue.Queue()

        def reader():
            try:
                for line in process.stdout:
                    line_queue.put(line)
            finally:
                line_queue.put(None)  # sentinel: stream closed

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()

        deadline = start + self.EXECUTION_TIMEOUT
        server_detected = False
        stream_closed = False

        while True:
            remaining = deadline - time.perf_counter()

            if remaining <= 0:
                break

            try:
                line = line_queue.get(timeout=min(remaining, 0.5))
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue

            if line is None:
                stream_closed = True
                break

            output_lines.append(line)
            logger.info(line.rstrip())

            if is_server and not server_detected and any(
                pattern in line.lower() for pattern in self.SERVER_READY_PATTERNS
            ):
                server_detected = True
                # Give it a brief moment to flush any immediate errors, then treat as success.
                time.sleep(1)
                break

            if process.poll() is not None and line_queue.empty():
                stream_closed = True
                break

        elapsed = round(time.perf_counter() - start, 2)
        stdout_text = "".join(output_lines)

        if server_detected:
            logger.info(f"Server startup detected after {elapsed} seconds. Terminating gracefully.")
            self._terminate(process)
            return self._result(True, stdout_text, "", 0, elapsed)

        if stream_closed or process.poll() is not None:
            return_code = process.wait()
            success = return_code == 0
            logger.info(f"Execution finished in {elapsed} seconds (exit code {return_code}).")
            return self._result(success, stdout_text, "" if success else stdout_text, return_code, elapsed)

        # Timed out without a server-ready signal and without exiting.
        logger.error(f"Execution timed out after {self.EXECUTION_TIMEOUT} seconds.")
        self._terminate(process)
        return self._result(
            False,
            stdout_text,
            f"Execution timed out after {self.EXECUTION_TIMEOUT} seconds without completing or signaling readiness.",
            -1,
            elapsed,
        )

    def _terminate(self, process: subprocess.Popen):
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        except Exception:
            logger.warning("Failed to cleanly terminate process.")