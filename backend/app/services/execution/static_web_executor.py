from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.core.logger import logger


class StaticWebExecutor:
    """
    Executor for static browser applications.

    Static HTML/CSS/JavaScript projects do not have a native
    command-line process to execute. Instead, this executor
    performs deterministic runtime-structure checks:

    - project directory exists
    - index.html exists
    - referenced local CSS/JS files exist
    - frontend files are non-empty

    Browser-level interaction testing is handled separately.
    """

    def run(self, project_path: str):
        from app.services.execution.execution_manager import ExecutionResult

        project = Path(project_path).resolve()

        result = ExecutionResult(
            success=False,
            project_type="static_web",
        )

        if not project.exists():
            result.stderr = (
                f"Project directory does not exist: {project}"
            )
            return result

        if not project.is_dir():
            result.stderr = (
                f"Project path is not a directory: {project}"
            )
            return result

        index_html = project / "index.html"

        if not index_html.is_file():
            result.stderr = (
                "Static web project is missing index.html."
            )
            return result

        try:
            html = index_html.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except Exception as exc:
            result.stderr = (
                f"Unable to read index.html: {exc}"
            )
            return result

        if not html.strip():
            result.stderr = "index.html is empty."
            return result

        missing_assets: List[str] = []

        for asset in self._extract_local_assets(html):

            asset_path = (
                project / asset
            ).resolve()

            try:
                asset_path.relative_to(project)
            except ValueError:
                missing_assets.append(
                    f"{asset} (outside project)"
                )
                continue

            if not asset_path.is_file():
                missing_assets.append(asset)

        if missing_assets:
            result.stderr = (
                "Missing referenced static assets: "
                + ", ".join(missing_assets)
            )
            return result

        frontend_files = [
            project / "style.css",
            project / "script.js",
        ]

        empty_files = []

        for file_path in frontend_files:

            if file_path.is_file():

                try:
                    if not file_path.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    ).strip():
                        empty_files.append(
                            file_path.name
                        )
                except Exception:
                    empty_files.append(
                        file_path.name
                    )

        if empty_files:
            result.stderr = (
                "Empty frontend files: "
                + ", ".join(empty_files)
            )
            return result

        result.success = True
        result.stdout = (
            "Static web project execution validation passed.\n"
            f"Entry point: {index_html.name}\n"
            "HTML entry point and referenced local assets "
            "are valid."
        )

        logger.info(
            "Static web execution validation passed: %s",
            project,
        )

        return result

    @staticmethod
    def _extract_local_assets(
        html: str,
    ) -> List[str]:
        """
        Extract local CSS/JavaScript references from HTML.

        This intentionally avoids external URLs such as:
        https://...
        http://...
        //cdn.example.com/...
        data:...
        """
        import re

        assets = []

        patterns = (
            r'<link[^>]+href=["\']([^"\']+)["\']',
            r'<script[^>]+src=["\']([^"\']+)["\']',
        )

        for pattern in patterns:

            for match in re.findall(
                pattern,
                html,
                flags=re.IGNORECASE,
            ):

                asset = match.strip()

                if not asset:
                    continue

                if asset.startswith(
                    (
                        "http://",
                        "https://",
                        "//",
                        "data:",
                        "#",
                    )
                ):
                    continue

                # Remove URL query/hash components.
                asset = asset.split(
                    "?",
                    1,
                )[0]

                asset = asset.split(
                    "#",
                    1,
                )[0]

                if asset:
                    assets.append(asset)

        return list(
            dict.fromkeys(assets)
        )