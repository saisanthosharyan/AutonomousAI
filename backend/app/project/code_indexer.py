from __future__ import annotations

import ast
import re

from dataclasses import dataclass, field
from pathlib import Path

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
    Represents one function or method.
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
    methods: list[FunctionSymbol] = field(
        default_factory=list
    )


@dataclass
class FileIndex:
    """
    Complete index of one source file.
    """

    path: str
    language: str

    imports: list[ImportSymbol] = field(
        default_factory=list
    )

    classes: list[ClassSymbol] = field(
        default_factory=list
    )

    functions: list[FunctionSymbol] = field(
        default_factory=list
    )


# ==========================================================
# CODE INDEXER
# ==========================================================


class CodeIndexer:
    """
    Builds an index of source files in a project.

    Python is parsed using AST.

    Other supported languages use lightweight
    regular-expression based extraction.
    """

    PYTHON_SUFFIXES = {
        ".py",
    }

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

    def __init__(self):

        self.index: dict[str, FileIndex] = {}

    # ======================================================
    # BUILD
    # ======================================================

    def build(
        self,
        project_directory: str | Path,
    ) -> dict[str, FileIndex]:

        root = Path(project_directory).resolve()

        if not root.exists():
            raise FileNotFoundError(root)

        if not root.is_dir():
            raise NotADirectoryError(root)

        logger.info(
            "Building code index..."
        )

        self.index.clear()

        for file in root.rglob("*"):

            if not file.is_file():
                continue

            # Ignore AutoDev/generated directories.
            if self._should_ignore(file, root):
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
    # IGNORE GENERATED DIRECTORIES
    # ======================================================

    def _should_ignore(
        self,
        file: Path,
        root: Path,
    ) -> bool:

        ignored = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            ".next",
            "coverage",
            ".pytest_cache",
            ".mypy_cache",
            "target",
            "out",
            ".autodev",
            ".autodev_debug",
            "execution",
        }

        try:

            relative = file.relative_to(root)

        except ValueError:

            return False

        return any(
            part in ignored
            for part in relative.parts
        )

    # ======================================================
    # PYTHON
    # ======================================================

    def _index_python(
        self,
        file: Path,
    ) -> None:

        try:

            source = file.read_text(
                encoding="utf-8"
            )

        except Exception:

            logger.exception(
                "Cannot read %s",
                file,
            )

            return

        try:

            tree = ast.parse(
                source,
                filename=str(file),
            )

        except SyntaxError:

            logger.warning(
                "Skipping invalid Python file: %s",
                file,
            )

            return

        index = FileIndex(
            path=str(file),
            language="python",
        )

        # --------------------------------------------------
        # IMPORTS
        # --------------------------------------------------

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                for alias in node.names:

                    index.imports.append(
                        ImportSymbol(
                            module=alias.name,
                            alias=alias.asname or "",
                        )
                    )

            elif isinstance(
                node,
                ast.ImportFrom,
            ):

                module = node.module or ""

                for alias in node.names:

                    index.imports.append(
                        ImportSymbol(
                            module=module,
                            name=alias.name,
                            alias=alias.asname or "",
                        )
                    )

        # --------------------------------------------------
        # TOP-LEVEL CLASSES
        # --------------------------------------------------

        for node in tree.body:

            if not isinstance(
                node,
                ast.ClassDef,
            ):
                continue

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
                        self._function_from_ast(item)
                    )

            index.classes.append(cls)

        # --------------------------------------------------
        # TOP-LEVEL FUNCTIONS
        # --------------------------------------------------

        for node in tree.body:

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):

                index.functions.append(
                    self._function_from_ast(node)
                )

        self.index[str(file)] = index

    # ======================================================
    # AST FUNCTION CONVERTER
    # ======================================================

    def _function_from_ast(
        self,
        node: ast.FunctionDef
        | ast.AsyncFunctionDef,
    ) -> FunctionSymbol:

        arguments = []

        for arg in node.args.posonlyargs:
            arguments.append(arg.arg)

        for arg in node.args.args:
            arguments.append(arg.arg)

        for arg in node.args.kwonlyargs:
            arguments.append(arg.arg)

        if node.args.vararg:
            arguments.append(
                "*" + node.args.vararg.arg
            )

        if node.args.kwarg:
            arguments.append(
                "**" + node.args.kwarg.arg
            )

        return FunctionSymbol(
            name=node.name,
            line=node.lineno,
            is_async=isinstance(
                node,
                ast.AsyncFunctionDef,
            ),
            arguments=arguments,
        )

    # ======================================================
    # OTHER LANGUAGES
    # ======================================================

    def _index_other_language(
        self,
        file: Path,
        language: str,
    ) -> None:

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

        lines = source.splitlines()

        # --------------------------------------------------
        # IMPORTS
        # --------------------------------------------------

        import_patterns = [
            re.compile(
                r"^\s*import\s+(.+)"
            ),
            re.compile(
                r"^\s*from\s+(.+?)\s+import"
            ),
            re.compile(
                r'^\s*#include\s+[<"]([^>"]+)[>"]'
            ),
            re.compile(
                r"^\s*use\s+(.+?);"
            ),
            re.compile(
                r"^\s*package\s+(.+?);"
            ),
        ]

        for line in lines:

            for pattern in import_patterns:

                match = pattern.search(line)

                if not match:
                    continue

                module = match.group(1).strip()

                index.imports.append(
                    ImportSymbol(
                        module=module
                    )
                )

                break

        # --------------------------------------------------
        # CLASSES
        # --------------------------------------------------

        class_patterns = [
            re.compile(
                r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)"
            ),
            re.compile(
                r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)"
            ),
            re.compile(
                r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)"
            ),
            re.compile(
                r"\benum\s+([A-Za-z_][A-Za-z0-9_]*)"
            ),
        ]

        for lineno, line in enumerate(
            lines,
            start=1,
        ):

            for pattern in class_patterns:

                match = pattern.search(line)

                if match:

                    index.classes.append(
                        ClassSymbol(
                            name=match.group(1),
                            line=lineno,
                        )
                    )

                    break

        # --------------------------------------------------
        # FUNCTIONS
        # --------------------------------------------------

        function_patterns = [
            # JavaScript / TypeScript
            re.compile(
                r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
            ),

            re.compile(
                r"\basync\s+function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
            ),

            re.compile(
                r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*async\s*\("
            ),

            re.compile(
                r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\("
            ),

            # Java / C++ / C#
            re.compile(
                r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*\{"
            ),

            # Go
            re.compile(
                r"\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
            ),
        ]

        for lineno, line in enumerate(
            lines,
            start=1,
        ):

            for pattern in function_patterns:

                match = pattern.search(line)

                if not match:
                    continue

                name = match.group(1)

                # Avoid treating control statements
                # as functions.
                if name in {
                    "if",
                    "for",
                    "while",
                    "switch",
                    "catch",
                }:
                    continue

                index.functions.append(
                    FunctionSymbol(
                        name=name,
                        line=lineno,
                    )
                )

                break

        self.index[str(file)] = index

    # ======================================================
    # LOOKUPS
    # ======================================================

    def get_file(
        self,
        file_path: str,
    ) -> FileIndex | None:

        return self.index.get(file_path)

    # ======================================================
    # FIND FUNCTION
    # ======================================================

    def find_function(
        self,
        name: str,
    ) -> list[tuple[str, FunctionSymbol]]:

        results = []

        target = name.lower()

        for file_path, file_index in self.index.items():

            for function in file_index.functions:

                if function.name.lower() == target:

                    results.append(
                        (
                            file_path,
                            function,
                        )
                    )

            for cls in file_index.classes:

                for method in cls.methods:

                    if method.name.lower() == target:

                        results.append(
                            (
                                file_path,
                                method,
                            )
                        )

        return results

    # ======================================================
    # FIND CLASS
    # ======================================================

    def find_class(
        self,
        name: str,
    ) -> list[tuple[str, ClassSymbol]]:

        results = []

        target = name.lower()

        for file_path, file_index in self.index.items():

            for cls in file_index.classes:

                if cls.name.lower() == target:

                    results.append(
                        (
                            file_path,
                            cls,
                        )
                    )

        return results

    # ======================================================
    # FIND IMPORT
    # ======================================================

    def find_import(
        self,
        module: str,
    ) -> list[tuple[str, ImportSymbol]]:

        results = []

        target = module.lower()

        for file_path, file_index in self.index.items():

            for imp in file_index.imports:

                if target in imp.module.lower():

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

        keyword = keyword.lower()

        return {
            "functions": [
                item
                for item in self._all_functions()
                if keyword in item[1].name.lower()
            ],
            "classes": [
                item
                for item in self._all_classes()
                if keyword in item[1].name.lower()
            ],
            "imports": [
                item
                for item in self._all_imports()
                if keyword in item[1].module.lower()
            ],
        }

    # ======================================================
    # INTERNAL ITERATORS
    # ======================================================

    def _all_functions(self):

        results = []

        for path, file_index in self.index.items():

            for function in file_index.functions:

                results.append(
                    (path, function)
                )

            for cls in file_index.classes:

                for method in cls.methods:

                    results.append(
                        (path, method)
                    )

        return results

    def _all_classes(self):

        results = []

        for path, file_index in self.index.items():

            for cls in file_index.classes:

                results.append(
                    (path, cls)
                )

        return results

    def _all_imports(self):

        results = []

        for path, file_index in self.index.items():

            for imp in file_index.imports:

                results.append(
                    (path, imp)
                )

        return results

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

            functions += len(
                item.functions
            )

            classes += len(
                item.classes
            )

            imports += len(
                item.imports
            )

            for cls in item.classes:

                functions += len(
                    cls.methods
                )

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
    # CLEAR
    # ======================================================

    def clear(self) -> None:

        self.index.clear()

    # ======================================================
    # MAGIC METHODS
    # ======================================================

    def __len__(self) -> int:

        return len(self.index)

    def __contains__(
        self,
        item: str,
    ) -> bool:

        return item in self.index

    def __iter__(self):

        return iter(
            self.index.items()
        )