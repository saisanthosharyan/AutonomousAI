from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logger import logger


# ==========================================================
# DATA MODELS
# ==========================================================


@dataclass
class ImportSymbol:
    """
    Represents one import statement.
    """

    module: str

    name: str = ""

    alias: str = ""


@dataclass
class FunctionSymbol:
    """
    Represents one function.
    """

    name: str

    line: int

    is_async: bool = False

    arguments: list[str] = field(default_factory=list)


@dataclass
class ClassSymbol:
    """
    Represents one class.
    """

    name: str

    line: int

    methods: list[FunctionSymbol] = field(default_factory=list)


@dataclass
class FileIndex:
    """
    Complete index of one source file.
    """

    path: str

    language: str

    imports: list[ImportSymbol] = field(default_factory=list)

    classes: list[ClassSymbol] = field(default_factory=list)

    functions: list[FunctionSymbol] = field(default_factory=list)


# ==========================================================
# CODE INDEXER
# ==========================================================


class CodeIndexer:
    """
    Builds an index of every source file in a project.

    Initially supports:

        ✔ Python

    Future support:

        ✔ JavaScript
        ✔ TypeScript
        ✔ React
        ✔ Java
        ✔ C/C++
        ✔ Go
        ✔ Rust
    """

    PYTHON_SUFFIXES = {
        ".py",
    }

    def __init__(self):

        self.index: dict[str, FileIndex] = {}

    # ======================================================
    # PUBLIC
    # ======================================================

    def build(
        self,
        project_directory: str | Path,
    ) -> dict[str, FileIndex]:

        root = Path(project_directory)

        if not root.exists():

            raise FileNotFoundError(root)

        logger.info(
            "Building code index..."
        )

        self.index.clear()

        for file in root.rglob("*"):

            if not file.is_file():

                continue

            suffix = file.suffix.lower()

            if suffix in self.PYTHON_SUFFIXES:

                self._index_python(file)

            elif suffix in self.JAVASCRIPT_SUFFIXES:

                self._index_other_language(
                    file,
                    "javascript",
                )

            elif suffix in self.JAVA_SUFFIXES:

                self._index_other_language(
                    file,
                    "java",
                )

            elif suffix in self.CPP_SUFFIXES:

                self._index_other_language(
                    file,
                    "cpp",
                )

            elif suffix in self.GO_SUFFIXES:

                self._index_other_language(
                    file,
                    "go",
                )

            elif suffix in self.RUST_SUFFIXES:

                self._index_other_language(
                    file,
                    "rust",
                )

        logger.info(
            "Indexed %d files.",
            len(self.index),
        )

        return self.index

    # ======================================================
    # PYTHON
    # ======================================================

    def _index_python(
        self,
        file: Path,
    ) -> None:

        try:

            source = file.read_text(
                encoding="utf-8",
            )

        except Exception:

            logger.exception(
                "Cannot read %s",
                file,
            )

            return

        try:

            tree = ast.parse(source)

        except SyntaxError:

            logger.warning(
                "Skipping invalid python file: %s",
                file,
            )

            return

        index = FileIndex(

            path=str(file),

            language="python",
        )

        # ------------------------------------------
        # Imports
        # ------------------------------------------

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                for alias in node.names:

                    index.imports.append(

                        ImportSymbol(

                            module=alias.name,

                            alias=alias.asname or "",
                        )

                    )

            elif isinstance(node, ast.ImportFrom):

                module = node.module or ""

                for alias in node.names:

                    index.imports.append(

                        ImportSymbol(

                            module=module,

                            name=alias.name,

                            alias=alias.asname or "",
                        )

                    )

        # ------------------------------------------
        # Classes
        # ------------------------------------------

        for node in tree.body:

            if isinstance(node, ast.ClassDef):

                cls = ClassSymbol(

                    name=node.name,

                    line=node.lineno,
                )

                for item in node.body:

                    if isinstance(
                        item,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                        ),
                    ):

                        cls.methods.append(

                            FunctionSymbol(

                                name=item.name,

                                line=item.lineno,

                                is_async=isinstance(
                                    item,
                                    ast.AsyncFunctionDef,
                                ),

                                arguments=[
                                    arg.arg
                                    for arg in item.args.args
                                ],
                            )

                        )

                index.classes.append(cls)

        # ------------------------------------------
        # Top-level functions
        # ------------------------------------------

        for node in tree.body:

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):

                index.functions.append(

                    FunctionSymbol(

                        name=node.name,

                        line=node.lineno,

                        is_async=isinstance(
                            node,
                            ast.AsyncFunctionDef,
                        ),

                        arguments=[
                            arg.arg
                            for arg in node.args.args
                        ],
                    )

                )

        self.index[str(file)] = index
    # ======================================================
    # MULTI-LANGUAGE SUPPORT
    # ======================================================

    JAVASCRIPT_SUFFIXES = {
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
    }

    JAVA_SUFFIXES = {
        ".java",
    }

    CPP_SUFFIXES = {
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
        ".h",
        ".c",
    }

    GO_SUFFIXES = {
        ".go",
    }

    RUST_SUFFIXES = {
        ".rs",
    }

    def _index_other_language(
        self,
        file: Path,
        language: str,
    ) -> None:

        import re

        try:

            source = file.read_text(
                encoding="utf-8",
                errors="ignore",
            )

        except Exception:

            logger.exception(
                "Cannot read %s",
                file,
            )

            return

        index = FileIndex(
            path=str(file),
            language=language,
        )

        # ------------------------------------------
        # Imports
        # ------------------------------------------

        import_patterns = [
            r"^\s*import\s+(.+)$",
            r"^\s*from\s+(.+?)\s+import",
            r'^\s*#include\s+[<"].+[>"]',
            r'^\s*use\s+(.+);',
            r'^\s*package\s+(.+);',
        ]

        for line in source.splitlines():

            for pattern in import_patterns:

                match = re.search(pattern, line)

                if match:

                    module = match.group(1).strip()

                    index.imports.append(
                        ImportSymbol(
                            module=module,
                        )
                    )

        # ------------------------------------------
        # Classes
        # ------------------------------------------

        class_patterns = [

            r"class\s+([A-Za-z_][A-Za-z0-9_]*)",

            r"interface\s+([A-Za-z_][A-Za-z0-9_]*)",

            r"struct\s+([A-Za-z_][A-Za-z0-9_]*)",

            r"enum\s+([A-Za-z_][A-Za-z0-9_]*)",
        ]

        lines = source.splitlines()

        for lineno, line in enumerate(
            lines,
            start=1,
        ):

            for pattern in class_patterns:

                match = re.search(pattern, line)

                if match:

                    index.classes.append(

                        ClassSymbol(

                            name=match.group(1),

                            line=lineno,
                        )

                    )

        # ------------------------------------------
        # Functions
        # ------------------------------------------

        function_patterns = [

            r"function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",

            r"async\s+function\s+([A-Za-z_][A-Za-z0-9_]*)",

            r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(",

            r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*async",

            r"(?:public|private|protected)?\s*(?:static\s+)?[A-Za-z0-9_<>\[\]]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",

            r"func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        ]

        for lineno, line in enumerate(
            lines,
            start=1,
        ):

            for pattern in function_patterns:

                match = re.search(
                    pattern,
                    line,
                )

                if match:

                    index.functions.append(

                        FunctionSymbol(

                            name=match.group(1),

                            line=lineno,
                        )

                    )

        self.index[str(file)] = index
    # ======================================================
    # LOOKUPS
    # ======================================================

    def get_file(
        self,
        file_path: str,
    ) -> FileIndex | None:
        """
        Return the index for one file.
        """

        return self.index.get(file_path)

    def find_function(
        self,
        name: str,
    ) -> list[tuple[str, FunctionSymbol]]:
        """
        Find every function having the given name.
        """

        results = []

        for file_path, file_index in self.index.items():

            for function in file_index.functions:

                if function.name == name:

                    results.append(
                        (
                            file_path,
                            function,
                        )
                    )

            for cls in file_index.classes:

                for method in cls.methods:

                    if method.name == name:

                        results.append(
                            (
                                file_path,
                                method,
                            )
                        )

        return results

    def find_class(
        self,
        name: str,
    ) -> list[tuple[str, ClassSymbol]]:
        """
        Find every class having the given name.
        """

        results = []

        for file_path, file_index in self.index.items():

            for cls in file_index.classes:

                if cls.name == name:

                    results.append(
                        (
                            file_path,
                            cls,
                        )
                    )

        return results

    def find_import(
        self,
        module: str,
    ) -> list[tuple[str, ImportSymbol]]:
        """
        Find every file importing a module.
        """

        results = []

        for file_path, file_index in self.index.items():

            for imp in file_index.imports:

                if module.lower() in imp.module.lower():

                    results.append(
                        (
                            file_path,
                            imp,
                        )
                    )

        return results

    # ======================================================
    # SEARCH
    # ======================================================

    def search(
        self,
        keyword: str,
    ) -> dict[str, list]:
        """
        Search every indexed symbol.
        """

        keyword = keyword.lower()

        return {

            "functions": [

                item

                for item in self.find_function(keyword)

            ],

            "classes": [

                item

                for item in self.find_class(keyword)

            ],

            "imports": [

                item

                for item in self.find_import(keyword)

            ],
        }

    # ======================================================
    # STATISTICS
    # ======================================================

    def statistics(
        self,
    ) -> dict[str, int]:

        files = len(self.index)

        functions = 0

        classes = 0

        imports = 0

        for item in self.index.values():

            functions += len(item.functions)

            classes += len(item.classes)

            imports += len(item.imports)

            for cls in item.classes:

                functions += len(cls.methods)

        return {

            "files": files,

            "classes": classes,

            "functions": functions,

            "imports": imports,
        }

    # ======================================================
    # EXPORT
    # ======================================================

    def to_dict(
        self,
    ) -> dict:

        data = {}

        for path, item in self.index.items():

            data[path] = {

                "language": item.language,

                "imports": [

                    vars(i)

                    for i in item.imports

                ],

                "functions": [

                    vars(f)

                    for f in item.functions

                ],

                "classes": [

                    {

                        "name": c.name,

                        "line": c.line,

                        "methods": [

                            vars(m)

                            for m in c.methods

                        ],

                    }

                    for c in item.classes

                ],
            }

        return data

    # ======================================================
    # RESET
    # ======================================================

    def clear(
        self,
    ) -> None:
        """
        Remove the entire in-memory index.
        """

        self.index.clear()

    # ======================================================
    # ITERATION
    # ======================================================

    def __len__(
        self,
    ) -> int:

        return len(self.index)

    def __contains__(
        self,
        item: str,
    ) -> bool:

        return item in self.index

    def __iter__(
        self,
    ):

        return iter(self.index.items())