from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.core.logger import logger


class FileManager:
    """
    Centralized file system manager.

    Responsibilities
    ----------------
    - Safe file reading
    - Safe file writing
    - Append content
    - Delete files
    - Rename files
    - Move files
    - Copy files
    - Create directories
    - List files
    - File metadata

    Every agent should use this class instead of directly
    using open(), shutil, or pathlib operations.
    """

    DEFAULT_ENCODING = "utf-8"

    # =====================================================
    # READ
    # =====================================================

    def read_file(
        self,
        path: str | Path,
        encoding: str = DEFAULT_ENCODING,
    ) -> str:

        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(file_path)

        logger.info("Reading file: %s", file_path)

        return file_path.read_text(
            encoding=encoding,
            errors="ignore",
        )

    # =====================================================
    # WRITE
    # =====================================================

    def write_file(
        self,
        path: str | Path,
        content: str,
        encoding: str = DEFAULT_ENCODING,
    ) -> None:

        file_path = Path(path)

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info("Writing file: %s", file_path)

        file_path.write_text(
            content,
            encoding=encoding,
        )

    # =====================================================
    # APPEND
    # =====================================================

    def append_file(
        self,
        path: str | Path,
        content: str,
        encoding: str = DEFAULT_ENCODING,
    ) -> None:

        file_path = Path(path)

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info("Appending file: %s", file_path)

        with open(
            file_path,
            "a",
            encoding=encoding,
        ) as file:

            file.write(content)

    # =====================================================
    # CREATE EMPTY FILE
    # =====================================================

    def create_file(
        self,
        path: str | Path,
    ) -> Path:

        file_path = Path(path)

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path.touch(
            exist_ok=True,
        )

        logger.info(
            "Created file: %s",
            file_path,
        )

        return file_path

    # =====================================================
    # DELETE
    # =====================================================

    def delete_file(
        self,
        path: str | Path,
    ) -> bool:

        file_path = Path(path)

        if not file_path.exists():
            return False

        file_path.unlink()

        logger.info(
            "Deleted file: %s",
            file_path,
        )

        return True

    # =====================================================
    # COPY
    # =====================================================

    def copy_file(
        self,
        source: str | Path,
        destination: str | Path,
    ) -> Path:

        source = Path(source)
        destination = Path(destination)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

        logger.info(
            "Copied file %s -> %s",
            source,
            destination,
        )

        return destination

    # =====================================================
    # MOVE
    # =====================================================

    def move_file(
        self,
        source: str | Path,
        destination: str | Path,
    ) -> Path:

        source = Path(source)
        destination = Path(destination)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.move(
            str(source),
            str(destination),
        )

        logger.info(
            "Moved file %s -> %s",
            source,
            destination,
        )

        return destination

    # =====================================================
    # RENAME
    # =====================================================

    def rename_file(
        self,
        source: str | Path,
        new_name: str,
    ) -> Path:

        source = Path(source)

        destination = source.with_name(
            new_name,
        )

        source.rename(destination)

        logger.info(
            "Renamed %s -> %s",
            source,
            destination,
        )

        return destination

    # =====================================================
    # DIRECTORY
    # =====================================================

    def create_directory(
        self,
        path: str | Path,
    ) -> Path:

        directory = Path(path)

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            "Created directory: %s",
            directory,
        )

        return directory

    # =====================================================
    # EXISTS
    # =====================================================

    def exists(
        self,
        path: str | Path,
    ) -> bool:

        return Path(path).exists()

    # =====================================================
    # LIST FILES
    # =====================================================

    def list_files(
        self,
        directory: str | Path,
        recursive: bool = True,
    ) -> list[Path]:

        directory = Path(directory)

        if not directory.exists():
            return []

        if recursive:

            return [
                item
                for item in directory.rglob("*")
                if item.is_file()
            ]

        return [
            item
            for item in directory.iterdir()
            if item.is_file()
        ]

    # =====================================================
    # FILE INFO
    # =====================================================

    def get_file_info(
        self,
        path: str | Path,
    ) -> dict[str, Any]:

        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(file_path)

        stat = file_path.stat()

        return {
            "name": file_path.name,
            "path": str(file_path.resolve()),
            "extension": file_path.suffix,
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "is_file": file_path.is_file(),
            "is_directory": file_path.is_dir(),
        }