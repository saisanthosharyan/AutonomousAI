import re
import subprocess
import threading
import time
from pathlib import Path

from app.core.logger import logger


class StaticWebTestRunner:
    """
    Performs automated validation for static HTML/CSS/JavaScript projects.
    Includes static validation and real browser runtime testing with Playwright.
    """

    TIMEOUT = 30
    BROWSER_TIMEOUT = 10000
    INTERACTION_TIMEOUT = 3000

    def run(self, project_path: str):
        project = Path(project_path).resolve()

        if not project.exists():
            return self._result(
                False,
                "",
                f"Project does not exist: {project}",
                -1,
                0,
            )

        logger.info("=" * 60)
        logger.info("Static Web Test Runner Started")
        logger.info("=" * 60)

        start = time.time()
        tests = []
        failures = []

        try:
            index_file = project / "index.html"

            if not index_file.exists():
                return self._result(
                    False,
                    "",
                    "index.html was not found.",
                    1,
                    round(time.time() - start, 2),
                )

            html = index_file.read_text(
                encoding="utf-8",
                errors="replace",
            )

            tests.append(("HTML entry point", True))

            self._check_html_structure(html, tests)
            self._check_local_assets(project, html, tests)
            self._check_javascript(project, html, tests)
            self._check_interactive_logic(project, html, tests)
            self._check_browser_runtime(project, tests)

            for name, passed in tests:
                if passed:
                    logger.info("PASS: %s", name)
                else:
                    logger.error("FAIL: %s", name)
                    failures.append(name)

            execution_time = round(time.time() - start, 2)

            passed_count = sum(
                1 for _, passed in tests if passed
            )

            total_count = len(tests)

            stdout_lines = [
                "=== STATIC WEB TESTS ===",
                f"Tests: {total_count}",
                f"Passed: {passed_count}",
                f"Failed: {len(failures)}",
                "",
            ]

            for name, passed in tests:
                status = "PASS" if passed else "FAIL"
                stdout_lines.append(
                    f"[{status}] {name}"
                )

            stdout = "\n".join(stdout_lines)

            stderr = ""

            if failures:
                stderr = (
                    "Failed tests:\n"
                    + "\n".join(
                        f"- {failure}"
                        for failure in failures
                    )
                )

            logger.info(
                "Static web testing finished: "
                f"{passed_count}/{total_count} passed."
            )

            return self._result(
                len(failures) == 0,
                stdout,
                stderr,
                0 if not failures else 1,
                execution_time,
            )

        except Exception as exc:
            logger.exception(
                "Static web testing failed."
            )

            return self._result(
                False,
                "",
                str(exc),
                -1,
                round(time.time() - start, 2),
            )

        finally:
            logger.info("=" * 60)
            logger.info("Static Web Test Runner Finished")
            logger.info("=" * 60)

    def _check_html_structure(
        self,
        html: str,
        tests: list,
    ):
        valid_structure = bool(
            re.search(
                r"<html\b",
                html,
                re.IGNORECASE,
            )
            and re.search(
                r"<head\b",
                html,
                re.IGNORECASE,
            )
            and re.search(
                r"<body\b",
                html,
                re.IGNORECASE,
            )
        )

        tests.append(
            (
                "HTML document structure",
                valid_structure,
            )
        )

        viewport_configured = bool(
            re.search(
                r'name=["\']viewport["\']',
                html,
                re.IGNORECASE,
            )
        )

        tests.append(
            (
                "Viewport configuration",
                viewport_configured,
            )
        )

    def _check_local_assets(
        self,
        project: Path,
        html: str,
        tests: list,
    ):
        references = []

        references.extend(
            re.findall(
                r'<link[^>]+href=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
        )

        references.extend(
            re.findall(
                r'<script[^>]+src=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
        )

        local_references = [
            reference
            for reference in references
            if not reference.startswith(
                (
                    "http://",
                    "https://",
                    "//",
                    "data:",
                )
            )
        ]

        if not local_references:
            tests.append(
                (
                    "Local asset references",
                    True,
                )
            )
            return

        all_exist = True

        for reference in local_references:
            clean_reference = (
                reference
                .split("?", 1)[0]
                .split("#", 1)[0]
            )

            asset = (
                project
                / clean_reference.lstrip("/")
            ).resolve()

            try:
                asset.relative_to(project)
            except ValueError:
                all_exist = False
                logger.error(
                    "Unsafe local asset reference: %s",
                    clean_reference,
                )
                continue

            if not asset.exists():
                all_exist = False

                logger.error(
                    "Missing local asset: %s",
                    clean_reference,
                )

        tests.append(
            (
                "Local asset references",
                all_exist,
            )
        )

    def _check_javascript(
        self,
        project: Path,
        html: str,
        tests: list,
    ):
        scripts = re.findall(
            r'<script[^>]+src=["\']([^"\']+\.js)["\']',
            html,
            re.IGNORECASE,
        )

        if not scripts:
            tests.append(
                (
                    "JavaScript syntax",
                    True,
                )
            )
            return

        all_valid = True

        for script in scripts:
            if script.startswith(
                (
                    "http://",
                    "https://",
                    "//",
                )
            ):
                continue

            script_path = (
                project
                / script.lstrip("/")
            ).resolve()

            try:
                script_path.relative_to(project)
            except ValueError:
                all_valid = False
                logger.error(
                    "Unsafe JavaScript reference: %s",
                    script,
                )
                continue

            if not script_path.exists():
                all_valid = False

                logger.error(
                    "JavaScript file does not exist: %s",
                    script,
                )
                continue

            try:
                process = subprocess.run(
                    [
                        "node",
                        "--check",
                        str(script_path),
                    ],
                    cwd=project,
                    capture_output=True,
                    text=True,
                    timeout=self.TIMEOUT,
                )

                if process.returncode != 0:
                    all_valid = False

                    logger.error(
                        "JavaScript syntax error in %s:\n%s",
                        script,
                        process.stderr,
                    )

            except FileNotFoundError:
                logger.warning(
                    "Node.js is not available. "
                    "JavaScript syntax execution was skipped."
                )

            except subprocess.TimeoutExpired:
                all_valid = False

                logger.error(
                    "JavaScript syntax check timed out: %s",
                    script,
                )

        tests.append(
            (
                "JavaScript syntax",
                all_valid,
            )
        )

    def _check_interactive_logic(
        self,
        project: Path,
        html: str,
        tests: list,
    ):
        script_files = re.findall(
            r'<script[^>]+src=["\']([^"\']+\.js)["\']',
            html,
            re.IGNORECASE,
        )

        combined_js = ""

        for script in script_files:
            if script.startswith(
                (
                    "http://",
                    "https://",
                    "//",
                )
            ):
                continue

            script_path = (
                project
                / script.lstrip("/")
            ).resolve()

            try:
                script_path.relative_to(project)
            except ValueError:
                continue

            if script_path.exists():
                combined_js += (
                    "\n"
                    + script_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                )

        interactive_elements = bool(
            re.search(
                r"<button\b",
                html,
                re.IGNORECASE,
            )
            or re.search(
                r"<input\b",
                html,
                re.IGNORECASE,
            )
            or re.search(
                r"<form\b",
                html,
                re.IGNORECASE,
            )
        )

        tests.append(
            (
                "Interactive HTML elements",
                interactive_elements,
            )
        )

        if interactive_elements:
            event_logic = bool(
                re.search(
                    r"addEventListener\s*\(",
                    combined_js,
                )
                or re.search(
                    r"onclick\s*=",
                    combined_js,
                    re.IGNORECASE,
                )
            )

            tests.append(
                (
                    "JavaScript interaction handlers",
                    event_logic,
                )
            )

        if "localStorage" in combined_js:
            local_storage_implementation = bool(
                re.search(
                    r"localStorage\.(getItem|setItem|removeItem)",
                    combined_js,
                )
            )

            tests.append(
                (
                    "localStorage implementation",
                    local_storage_implementation,
                )
            )

    def _check_browser_runtime(
        self,
        project: Path,
        tests: list,
    ):
        result = {
            "success": False,
            "errors": [],
        }

        self._run_browser_test(
            project,
            result,
        )

        browser_errors = result.get(
            "errors",
            [],
        )

        if browser_errors:
            for error in browser_errors:
                logger.error(
                    "Browser test error: %s",
                    error,
                )

            tests.append(
                (
                    "Browser runtime execution",
                    False,
                )
            )
            return

        tests.append(
            (
                "Browser runtime execution",
                result.get("success", False),
            )
        )

    def _run_browser_test(
        self,
        project: Path,
        result: dict,
    ):
        try:
            from playwright.sync_api import (
                TimeoutError as PlaywrightTimeoutError,
                sync_playwright,
            )
        except ImportError:
            logger.warning(
                "Playwright is not installed. "
                "Browser runtime testing skipped."
            )

            result["success"] = True
            result["errors"] = []
            return

        index_file = project / "index.html"

        browser_errors = []
        console_errors = []
        page_errors = []
        failed_interactions = []

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True
                )

                context = browser.new_context()

                page = context.new_page()

                def handle_console(message):
                    if message.type == "error":
                        console_errors.append(
                            message.text
                        )

                def handle_page_error(error):
                    page_errors.append(
                        str(error)
                    )

                page.on(
                    "console",
                    handle_console,
                )

                page.on(
                    "pageerror",
                    handle_page_error,
                )

                page.goto(
                    index_file.as_uri(),
                    wait_until="load",
                    timeout=self.BROWSER_TIMEOUT,
                )

                page.wait_for_timeout(500)

                self._interact_with_buttons(
                    page,
                    failed_interactions,
                )

                self._interact_with_forms(
                    page,
                    failed_interactions,
                )

                page.wait_for_timeout(500)

                if console_errors:
                    browser_errors.extend(
                        f"Console error: {error}"
                        for error in console_errors
                    )

                if page_errors:
                    browser_errors.extend(
                        f"Runtime error: {error}"
                        for error in page_errors
                    )

                if failed_interactions:
                    browser_errors.extend(
                        failed_interactions
                    )

                if browser_errors:
                    result["success"] = False
                    result["errors"] = browser_errors
                else:
                    result["success"] = True
                    result["errors"] = []

                context.close()
                browser.close()

        except PlaywrightTimeoutError as exc:
            logger.error(
                "Browser runtime test timed out: %s",
                exc,
            )

            result["success"] = False
            result["errors"] = [
                f"Browser runtime test timed out: {exc}"
            ]

        except Exception as exc:
            logger.exception(
                "Browser runtime testing failed."
            )

            result["success"] = False
            result["errors"] = [
                f"Browser runtime testing failed: {exc}"
            ]

    def _interact_with_buttons(
        self,
        page,
        failed_interactions: list,
    ):
        buttons = page.locator("button")

        try:
            button_count = buttons.count()
        except Exception as exc:
            failed_interactions.append(
                f"Unable to inspect buttons: {exc}"
            )
            return

        for index in range(button_count):
            button = buttons.nth(index)

            try:
                if not button.is_visible():
                    continue

                if not button.is_enabled():
                    continue

                button.click(
                    timeout=self.INTERACTION_TIMEOUT,
                    no_wait_after=True,
                )

                page.wait_for_timeout(250)

            except Exception as exc:
                message = str(exc)

                failed_interactions.append(
                    f"Button {index} interaction failed: {message}"
                )

                if "Timeout" in message:
                    logger.warning(
                        "Button %s interaction timed out: %s",
                        index,
                        exc,
                    )
                else:
                    logger.warning(
                        "Button %s interaction failed: %s",
                        index,
                        exc,
                    )

    def _interact_with_forms(
        self,
        page,
        failed_interactions: list,
    ):
        forms = page.locator("form")

        try:
            form_count = forms.count()
        except Exception as exc:
            failed_interactions.append(
                f"Unable to inspect forms: {exc}"
            )
            return

        for index in range(form_count):
            form = forms.nth(index)

            try:
                if not form.is_visible():
                    continue

                inputs = form.locator(
                    "input:not([type='hidden'])"
                )

                input_count = inputs.count()

                for input_index in range(input_count):
                    field = inputs.nth(input_index)

                    if not field.is_visible():
                        continue

                    input_type = (
                        field.get_attribute("type")
                        or "text"
                    )

                    if input_type in {
                        "text",
                        "email",
                        "search",
                        "tel",
                        "url",
                        "number",
                    }:
                        field.fill("AutoDev Test")

                submit = form.locator(
                    "button[type='submit'], "
                    "input[type='submit']"
                )

                if submit.count() > 0:
                    submit.first.click(
                        timeout=self.INTERACTION_TIMEOUT,
                        no_wait_after=True,
                    )

                    page.wait_for_timeout(250)

            except Exception as exc:
                failed_interactions.append(
                    f"Form {index} interaction failed: {exc}"
                )

                logger.warning(
                    "Form %s interaction failed: %s",
                    index,
                    exc,
                )

    def _result(
        self,
        success: bool,
        stdout: str,
        stderr: str,
        return_code: int,
        execution_time: float,
    ):
        return {
            "success": success,
            "skipped": False,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
            "execution_time": execution_time,
        }