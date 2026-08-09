from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from app.core.logger import logger


class ProjectBuilder:
    """
    Converts LLM-generated FILE: output into a real project.

    Expected LLM output:

    FILE: app.py

    import argparse

    FILE: requirements.txt

    requests

    FILE: README.md

    # My Project
    """

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def __init__(self):

        from app.core.config import settings

        self.output_dir = Path(
            settings.GENERATED_PROJECTS_DIR
        ).resolve()

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            f"ProjectBuilder initialized. "
            f"Output directory: {self.output_dir}"
        )

    # ==========================================================
    # BUILD NEW PROJECT
    # ==========================================================

    def build(
        self,
        project_name: str,
        llm_output: str,
        project_path: str | None = None,
    ) -> dict:
        """
        Build a new project from LLM output.

        If project_path is not supplied, a timestamped project
        directory will be created inside generated_projects.
        """

        safe_name = self._safe_name(
            project_name
        )

        if not safe_name:
            safe_name = "generated_project"

        # ------------------------------------------------------
        # Determine project path
        # ------------------------------------------------------

        if project_path is None:

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            project_path = (
                self.output_dir
                / f"{safe_name}_{timestamp}"
            )

        else:

            project_path = Path(
                project_path
            ).resolve()

        project_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            f"Building new project at: {project_path}"
        )

        # ------------------------------------------------------
        # Write generated files
        # ------------------------------------------------------

        created_files = self._write_files(
            project_path,
            llm_output,
        )

        if not created_files:

            raise ValueError(
                "No files were created from LLM output."
            )

        # ------------------------------------------------------
        # Create ZIP
        # ------------------------------------------------------

        zip_path = self.create_zip(
            project_path
        )

        logger.info(
            f"Project built successfully. "
            f"Files created: {len(created_files)}"
        )

        return {
            "project_path": str(
                project_path
            ),
            "zip_path": zip_path,
            "files": created_files,
            "file_count": len(
                created_files
            ),
        }
    # ==========================================================
    # REBUILD / REPAIR EXISTING PROJECT
    # ==========================================================

    def rebuild(
        self,
        project_path: str,
        llm_output: str,
    ) -> dict:
        """
        Update an existing project using LLM output.

        Only files returned by the LLM are created or replaced.

        Existing files not returned by the LLM are preserved.
        """

        project = Path(
            project_path
        ).resolve()

        if not project.exists():

            raise FileNotFoundError(
                f"Project does not exist: {project}"
            )

        if not project.is_dir():

            raise NotADirectoryError(
                f"Project path is not a directory: {project}"
            )

        logger.info(
            f"Rebuilding existing project: {project}"
        )

        updated_files = self._write_files(
            project,
            llm_output,
        )

        if not updated_files:

            raise ValueError(
                "AI repair produced no valid files."
            )

        zip_path = self.create_zip(
            project
        )

        logger.info(
            f"Project rebuilt successfully. "
            f"Updated files: {len(updated_files)}"
        )

        return {
            "project_path": str(project),
            "zip_path": zip_path,
            "files": updated_files,
            "file_count": len(updated_files),
        }

    # ==========================================================
    # WRITE FILES
    # ==========================================================

    def _write_files(
        self,
        project_path: Path,
        llm_output: str,
    ) -> list[str]:
        """
        Parse FILE: sections from LLM output and write them
        safely into project_path.
        """

        if not llm_output:

            raise ValueError(
                "LLM output is empty."
            )

        # ------------------------------------------------------
        # Clean complete LLM output
        # ------------------------------------------------------

        llm_output = self._clean_output(
            llm_output
        )

        print("=" * 80)
        print("RAW AFTER CLEANING")
        print(repr(llm_output[:700]))
        print("=" * 80)

        if not llm_output:

            raise ValueError(
                "LLM output became empty after cleaning."
            )

        # ------------------------------------------------------
        # Parse FILE sections
        #
        # NOTE: the previous pattern used a non-anchored
        # `(?=FILE:)` lookahead, which could match "FILE:" text
        # appearing mid-line (e.g. inside a comment or string in
        # generated code), and didn't require "FILE:" markers to
        # start on their own line. That caused sections to merge
        # or fail to split, which is why ProjectBuilder sometimes
        # reported "No FILE: sections found" even when the LLM
        # output looked correct at a glance.
        #
        # This version anchors "FILE:" to the start of a line
        # with `(?m)^FILE:` and requires the next section to also
        # start at a line boundary, which is far more robust to
        # blank lines and incidental "FILE:" substrings in file
        # content.
        # ------------------------------------------------------

        pattern = re.compile(
            r"^FILE:\s*(.*?)\n([\s\S]*?)(?=^FILE:|\Z)",
            re.MULTILINE,
        )

        matches = list(pattern.finditer(llm_output))

        print("MATCHES FOUND:", len(matches))

        for match in matches:
            print("FILE:", match.group(1))

        if not matches:

            logger.error(
                "No FILE: sections found in LLM output."
            )

            raise ValueError(
                "LLM returned no project files. "
                "Expected format: FILE: path/to/file"
            )

        # ------------------------------------------------------
        # Project root
        # ------------------------------------------------------

        project_root = project_path.resolve()

        project_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ------------------------------------------------------
        # Files that should never be generated
        # ------------------------------------------------------

        ignored = {
            ".git",
            ".github",
            ".idea",
            ".vscode",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".coverage",
            ".DS_Store",
            "__MACOSX",
            "node_modules",
            ".venv",
            "venv",
            "dist",
            "build",
            ".env",
            ".env.local",
        }

        created: list[str] = []

        seen: set[str] = set()

        # ------------------------------------------------------
        # Process every FILE section
        # ------------------------------------------------------

        for match in matches:

            raw_file_path = match.group(1)
            content = match.group(2)

            file_path = (
                raw_file_path
                .strip()
                .replace("\\", "/")
            )

            file_path = re.sub(
                r"/+",
                "/",
                file_path,
            )

            while file_path.startswith("./"):
                file_path = file_path[2:]

            file_path = file_path.strip()

            # --------------------------------------------------
            # Validate path
            # --------------------------------------------------

            if not file_path:

                logger.warning(
                    "Skipping empty file path."
                )

                continue

            if file_path.startswith("/"):

                raise ValueError(
                    f"Unsafe absolute file path detected: {file_path}"
                )

            if re.match(
                r"^[A-Za-z]:",
                file_path,
            ):

                raise ValueError(
                    f"Unsafe Windows absolute path detected: {file_path}"
                )

            path_parts = Path(
                file_path
            ).parts

            if any(
                part in {
                    "",
                    ".",
                    "..",
                }
                for part in path_parts
            ):

                raise ValueError(
                    f"Unsafe file path detected: {file_path}"
                )
            # --------------------------------------------------
            # Ignore system directories
            # --------------------------------------------------

            first_part = (
                path_parts[0]
                if path_parts
                else ""
            )

            if (
                file_path.lower() in ignored
                or first_part.lower() in ignored
            ):

                logger.warning(
                    f"Ignoring system file/directory: "
                    f"{file_path}"
                )

                continue

            # --------------------------------------------------
            # Duplicate protection
            # --------------------------------------------------

            normalized_key = (
                file_path.lower()
            )

            if normalized_key in seen:

                logger.warning(
                    f"Duplicate file ignored: "
                    f"{file_path}"
                )

                continue

            seen.add(
                normalized_key
            )

            # --------------------------------------------------
            # Clean file content
            # --------------------------------------------------

            content = self._clean_file_content(
                file_path,
                content,
            )

            if not content.strip():

                logger.warning(
                    f"Skipping empty file: "
                    f"{file_path}"
                )

                continue

            # --------------------------------------------------
            # Destination
            # --------------------------------------------------

            destination = (
                project_root
                / file_path
            ).resolve()

            # --------------------------------------------------
            # Path traversal protection
            # --------------------------------------------------

            try:

                destination.relative_to(
                    project_root
                )

            except ValueError:

                raise ValueError(
                    f"Unsafe file path detected: "
                    f"{file_path}"
                )

            # --------------------------------------------------
            # Create parent directories
            # --------------------------------------------------

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            # --------------------------------------------------
            # Write file
            # --------------------------------------------------

            try:

                temp = destination.with_suffix(destination.suffix + ".tmp")

                temp.write_text(
                    content,
                    encoding="utf-8",
                )

                temp.replace(destination)

            except Exception as e:

                logger.exception(
                    f"Failed writing file: "
                    f"{file_path}"
                )

                raise RuntimeError(
                    f"Failed writing file "
                    f"{file_path}: {e}"
                ) from e

            # --------------------------------------------------
            # Relative path
            # --------------------------------------------------

            relative = (
                destination.relative_to(
                    project_root
                )
            )

            relative_string = (
                relative.as_posix()
            )

            created.append(
                relative_string
            )

            logger.info(
                f"Created/updated file: "
                f"{relative_string}"
            )

        # ------------------------------------------------------
        # Final validation
        # ------------------------------------------------------

        if not created:

            raise ValueError(
                "LLM output contained no valid project files."
            )

        return created

    # ==========================================================
    # CLEAN INDIVIDUAL FILE CONTENT
    # ==========================================================

    def _clean_file_content(
        self,
        file_path: str,
        content: str,
    ) -> str:

        if not content:
            return ""

        content = content.strip("\n")

        suffix = Path(
            file_path
        ).suffix.lower()

        language_markers = {
            ".py": {"python", "py"},
            ".js": {"javascript", "js"},
            ".jsx": {"javascript", "jsx"},
            ".ts": {"typescript", "ts"},
            ".tsx": {"typescript", "tsx"},
            ".java": {"java"},
            ".cpp": {"cpp", "c++"},
            ".cc": {"cpp", "c++"},
            ".cxx": {"cpp", "c++"},
            ".html": {"html"},
            ".css": {"css"},
            ".json": {"json"},
            ".yaml": {"yaml", "yml"},
            ".yml": {"yaml", "yml"},
            ".md": {"markdown", "md"},
        }

        markers = language_markers.get(
            suffix,
            set(),
        )

        lines = content.splitlines()

        if lines:

            first_line = lines[0].strip().lower()

            if first_line in markers:

                logger.warning(
                    f"Removing accidental language marker "
                    f"'{lines[0].strip()}' from {file_path}"
                )

                lines = lines[1:]

        return "\n".join(
            lines
        ).strip()

    # ==========================================================
    # CREATE ZIP
    # ==========================================================

    def create_zip(
        self,
        project_path: Path,
    ) -> str:

        project_path = Path(
            project_path
        ).resolve()

        if not project_path.exists():

            raise FileNotFoundError(
                f"Cannot zip missing project: "
                f"{project_path}"
            )

        if not project_path.is_dir():

            raise NotADirectoryError(
                f"Cannot zip non-directory project: "
                f"{project_path}"
            )

        zip_file = project_path.with_suffix(".zip")

        if zip_file.exists():

            try:
                zip_file.unlink()

            except Exception as e:

                raise RuntimeError(
                    f"Unable to remove existing ZIP: "
                    f"{zip_file}"
                ) from e

        archive = shutil.make_archive(
            base_name=str(project_path),
            format="zip",
            root_dir=str(project_path),
        )

        logger.info(
            f"Created archive: {archive}"
        )

        return archive

    # ==========================================================
    # CLEAR PROJECT
    # ==========================================================

    def _clear_project(
        self,
        project_path: Path,
    ) -> None:

        if not project_path.exists():
            return

        if not project_path.is_dir():

            raise NotADirectoryError(
                f"Cannot clear non-directory: "
                f"{project_path}"
            )

        for item in project_path.iterdir():

            try:

                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

            except Exception:

                logger.exception(
                    f"Unable to remove: {item}"
                )

                raise

    # ==========================================================
    # CLEAN COMPLETE LLM OUTPUT
    # ==========================================================

    def _clean_output(
        self,
        text: str,
    ) -> str:

        if not text:
            return ""

        text = text.strip()

        text = re.sub(
            r"^\s*```(?:text|plaintext|"
            r"python|javascript|typescript|"
            r"json|bash|shell|sh|"
            r"java|cpp|c\+\+|c|"
            r"html|css|yaml|yml|"
            r"markdown|md)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```\s*$",
            "",
            text,
        )

        text = text.replace(
            "```",
            "",
        )

        return text.strip()

    # ==========================================================
    # SAFE PROJECT NAME
    # ==========================================================

    def _safe_name(
        self,
        name: str,
    ) -> str:

        if not name:
            return "generated_project"

        safe = re.sub(
            r"[^a-zA-Z0-9_-]",
            "_",
            str(name),
        )

        safe = re.sub(
            r"_+",
            "_",
            safe,
        )

        safe = safe.strip("_")

        if not safe:
            return "generated_project"

        return safe.lower()