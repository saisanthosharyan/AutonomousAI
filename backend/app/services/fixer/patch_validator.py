from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Dict, List

from app.core.logger import logger


class PatchValidator:
    """
    Validates and parses LLM-generated file patches.

    Expected format:

    FILE: path/to/file.py
    <full file contents>
    END FILE

    Protected test files are never allowed to be modified.
    """

    FILE_PATTERN = re.compile(
        r"(?m)^FILE:\s*(.+?)\s*$"
    )

    WINDOWS_DRIVE = re.compile(r"^[a-zA-Z]:")

    # Files/directories that the Fixer is never allowed to modify.
    PROTECTED_TEST_DIRS = {
        "tests",
        "test",
    }

    # Test filename patterns.
    TEST_FILE_PATTERNS = (
        re.compile(r"^test_.*\.py$", re.IGNORECASE),
        re.compile(r".*_test\.py$", re.IGNORECASE),
    )

    # ======================================================
    # PUBLIC
    # ======================================================

    def validate(
        self,
        response: str,
    ) -> List[Dict[str, str]]:

        logger.info("=" * 60)
        logger.info("Patch Validator Started")
        logger.info("=" * 60)

        if not response.strip():
            raise ValueError("LLM returned an empty response.")

        patches = self._parse(response)

        if not patches:
            raise ValueError(
                "No FILE blocks were found in the LLM response."
            )

        seen = set()

        validated: List[Dict[str, str]] = []

        for patch in patches:

            filename = patch["path"]
            content = patch["content"]

            self._validate_filename(filename)
            self._validate_content(content)
            self._validate_test_protection(filename)

            normalized_filename = self._normalize_filename(filename)

            if normalized_filename in seen:
                raise ValueError(
                    f"Duplicate file detected: {filename}"
                )

            seen.add(normalized_filename)

            validated.append(
                {
                    "path": filename,
                    "content": content,
                }
            )

        logger.info(
            "Validated %d patch(es).",
            len(validated),
        )

        logger.info("=" * 60)
        logger.info("Patch Validator Finished")
        logger.info("=" * 60)

        return validated

    # ======================================================
    # PARSE FILE BLOCKS
    # ======================================================

    def _parse(
        self,
        response: str,
    ) -> List[Dict[str, str]]:

        matches = list(
            self.FILE_PATTERN.finditer(response)
        )

        patches = []

        for i, match in enumerate(matches):

            filename = match.group(1).strip()

            start = match.end()

            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(response)

            content = (
                response[start:end]
                .replace("\r\n", "\n")
                .strip()
            )

            # Remove END FILE marker from the generated content.
            if content.endswith("END FILE"):
                content = content[:-len("END FILE")].rstrip()

            patches.append(
                {
                    "path": filename,
                    "content": content,
                }
            )

        return patches

    # ======================================================
    # VALIDATE FILE NAME
    # ======================================================

    def _validate_filename(
        self,
        filename: str,
    ) -> None:

        if not filename:
            raise ValueError(
                "Empty filename detected."
            )

        if self.WINDOWS_DRIVE.match(filename):
            raise ValueError(
                f"Absolute Windows path is not allowed: {filename}"
            )

        path = PurePosixPath(
            filename.replace("\\", "/")
        )

        if path.is_absolute():
            raise ValueError(
                f"Absolute path is not allowed: {filename}"
            )

        if ".." in path.parts:
            raise ValueError(
                f"Path traversal detected: {filename}"
            )

    # ======================================================
    # TEST FILE PROTECTION
    # ======================================================

    def _validate_test_protection(
        self,
        filename: str,
    ) -> None:
        """
        Prevent the Fixer Agent from modifying tests.

        Protected examples:

        tests/test_app.py
        tests/api/test_user.py
        test/test_app.py
        test_app.py
        app_test.py
        """

        normalized = self._normalize_filename(filename)

        path = PurePosixPath(normalized)

        # Protect files located inside tests/ or test/
        if any(
            part.lower() in self.PROTECTED_TEST_DIRS
            for part in path.parts[:-1]
        ):
            logger.warning(
                "Protected test file rejected: %s",
                filename,
            )

            raise ValueError(
                f"Protected test file cannot be modified: {filename}"
            )

        # Protect test_*.py and *_test.py
        for pattern in self.TEST_FILE_PATTERNS:

            if pattern.match(path.name):
                logger.warning(
                    "Protected test file rejected: %s",
                    filename,
                )

                raise ValueError(
                    f"Protected test file cannot be modified: {filename}"
                )

    # ======================================================
    # NORMALIZE PATH
    # ======================================================

    def _normalize_filename(
        self,
        filename: str,
    ) -> str:

        return filename.replace("\\", "/").strip().lstrip("./")

    # ======================================================
    # VALIDATE CONTENT
    # ======================================================

    def _validate_content(
        self,
        content: str,
    ) -> None:

        if not content.strip():
            raise ValueError(
                "Generated file has empty content."
            )