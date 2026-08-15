from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logger import logger

from app.project.project_scanner import (
    ProjectScanner,
    ScannedFile,
)

from app.project.project_analyzer import (
    ProjectAnalyzer,
)

from app.project.dependency_analyzer import (
    DependencyAnalyzer,
)

from app.project.tree_builder import (
    TreeBuilder,
)

from app.project.code_indexer import (
    CodeIndexer,
    FileIndex,
)


# ==========================================================
# DATA MODELS
# ==========================================================


@dataclass
class ProjectSummary:
    """
    High-level project summary.
    """

    root: str

    project_name: str

    total_files: int = 0

    total_directories: int = 0

    languages: dict[str, int] = field(
        default_factory=dict
    )

    frameworks: list[str] = field(
        default_factory=list
    )

    dependencies: list[str] = field(
        default_factory=list
    )


@dataclass
class ProjectContextData:
    """
    Complete project context shared by AI agents.
    """

    summary: ProjectSummary

    tree: str

    scanned_files: list[ScannedFile]

    dependencies: dict[str, Any]

    analysis: dict[str, Any]

    code_index: dict[str, FileIndex]


# ==========================================================
# CONTEXT BUILDER
# ==========================================================


class ContextBuilder:
    """
    Converts ProjectContextData into compact LLM context.
    """

    def build(
        self,
        context: ProjectContextData,
        max_chars: int = 12000,
    ) -> str:

        sections: list[str] = []

        summary = context.summary

        sections.append(
            f"Project: {summary.project_name}"
        )

        sections.append(
            f"Root: {summary.root}"
        )

        sections.append(
            f"Files: {summary.total_files}"
        )

        sections.append(
            f"Directories: {summary.total_directories}"
        )

        if summary.languages:

            language_text = ", ".join(
                f"{name} ({count})"
                for name, count
                in summary.languages.items()
            )

            sections.append(
                f"Languages: {language_text}"
            )

        if summary.frameworks:

            sections.append(
                "Frameworks: "
                + ", ".join(
                    summary.frameworks
                )
            )

        if summary.dependencies:

            sections.append(
                "Dependencies: "
                + ", ".join(
                    summary.dependencies
                )
            )

        sections.append("")

        sections.append(
            "Directory Tree"
        )

        sections.append(
            context.tree
        )

        # --------------------------------------------------
        # Indexed source files
        # --------------------------------------------------

        sections.append("")

        sections.append(
            "Indexed Source Files"
        )

        for path, file_index in (
            context.code_index.items()
        ):

            sections.append(
                f"- {path}"
            )

            if file_index.classes:

                sections.append(
                    "  Classes: "
                    + ", ".join(
                        cls.name
                        for cls
                        in file_index.classes
                    )
                )

            if file_index.functions:

                sections.append(
                    "  Functions: "
                    + ", ".join(
                        function.name
                        for function
                        in file_index.functions
                    )
                )

        text = "\n".join(
            sections
        )

        if len(text) > max_chars:

            text = text[:max_chars]

        return text


# ==========================================================
# PROJECT CONTEXT
# ==========================================================


class ProjectContext:
    """
    Central project knowledge provider.

    All AI agents should use this class instead of
    directly interacting with individual analyzers.
    """

    def __init__(self):

        self.scanner = ProjectScanner()

        self.tree_builder = TreeBuilder()

        self.dependency_analyzer = (
            DependencyAnalyzer()
        )

        self.project_analyzer = (
            ProjectAnalyzer()
        )

        self.code_indexer = CodeIndexer()

        self.context_builder = (
            ContextBuilder()
        )

        self.context: (
            ProjectContextData | None
        ) = None

        self._file_by_name: dict[
            str,
            list[ScannedFile],
        ] = {}

    # ======================================================
    # BUILD
    # ======================================================

    def build(
        self,
        project_directory: str | Path,
    ) -> ProjectContextData:

        root = Path(
            project_directory
        ).resolve()

        if not root.exists():

            raise FileNotFoundError(
                root
            )

        if not root.is_dir():

            raise NotADirectoryError(
                root
            )

        logger.info(
            "Building project context..."
        )

        # --------------------------------------------------
        # Scanner
        # --------------------------------------------------

        scanned_files = (
            self.scanner.scan(root)
        )

        # --------------------------------------------------
        # Tree
        # --------------------------------------------------

        tree = (
            self.tree_builder.build(root)
        )

        # --------------------------------------------------
        # Dependencies
        # --------------------------------------------------

        dependencies = (
            self.dependency_analyzer.analyze(
                root
            )
        )

        # --------------------------------------------------
        # Project analysis
        # --------------------------------------------------

        analysis = (
            self.project_analyzer.analyze(
                root
            )
        )

        # --------------------------------------------------
        # Code index
        # --------------------------------------------------

        code_index = (
            self.code_indexer.build(root)
        )

        # --------------------------------------------------
        # Language statistics
        # --------------------------------------------------

        languages: dict[str, int] = {}

        for item in scanned_files:

            language = (
                item.language
                or "unknown"
            )

            languages[language] = (
                languages.get(language, 0)
                + 1
            )

        # --------------------------------------------------
        # Filename index
        # --------------------------------------------------

        self._file_by_name.clear()

        for item in scanned_files:

            filename = (
                item.name.lower()
            )

            self._file_by_name.setdefault(
                filename,
                []
            ).append(item)

        # --------------------------------------------------
        # Directory count
        # --------------------------------------------------

        total_directories = sum(
            1
            for path in root.rglob("*")
            if path.is_dir()
            and not any(
                part in self.scanner.IGNORED_DIRECTORIES
                for part in path.relative_to(root).parts
            )
        )

        # --------------------------------------------------
        # Summary
        # --------------------------------------------------

        summary = ProjectSummary(
            root=str(root),

            project_name=root.name,

            total_files=len(
                scanned_files
            ),

            total_directories=(
                total_directories
            ),

            languages=languages,

            frameworks=analysis.get(
                "frameworks",
                [],
            ),

            dependencies=sorted(
                dependencies.keys()
            ),
        )

        # --------------------------------------------------
        # Context
        # --------------------------------------------------

        self.context = ProjectContextData(
            summary=summary,

            tree=tree,

            scanned_files=scanned_files,

            dependencies=dependencies,

            analysis=analysis,

            code_index=code_index,
        )

        logger.info(
            "Project context built successfully."
        )

        return self.context

    # ======================================================
    # STATE
    # ======================================================

    @property
    def ready(self) -> bool:

        return self.context is not None

    def require_context(
        self,
    ) -> ProjectContextData:

        if self.context is None:

            raise RuntimeError(
                "Project context has not been built."
            )

        return self.context

    # ======================================================
    # SUMMARY
    # ======================================================

    def get_summary(
        self,
    ) -> ProjectSummary:

        return (
            self.require_context()
            .summary
        )

    # ======================================================
    # TREE
    # ======================================================

    def get_tree(
        self,
    ) -> str:

        return (
            self.require_context()
            .tree
        )

    # ======================================================
    # ANALYSIS
    # ======================================================

    def get_analysis(
        self,
    ) -> dict[str, Any]:

        return dict(
            self.require_context()
            .analysis
        )

    # ======================================================
    # DEPENDENCIES
    # ======================================================

    def get_dependencies(
        self,
    ) -> dict[str, Any]:

        return dict(
            self.require_context()
            .dependencies
        )

    # ======================================================
    # INDEX
    # ======================================================

    def get_index(
        self,
    ) -> dict[str, FileIndex]:

        return dict(
            self.require_context()
            .code_index
        )

    # ======================================================
    # FILES
    # ======================================================

    def get_files(
        self,
    ) -> list[ScannedFile]:

        return list(
            self.require_context()
            .scanned_files
        )

    # ======================================================
    # FIND FILE
    # ======================================================

    def find_file(
        self,
        name: str,
    ) -> ScannedFile | None:

        results = self._file_by_name.get(
            name.lower(),
            []
        )

        if not results:

            return None

        return results[0]

    # ======================================================
    # FIND FILES
    # ======================================================

    def find_files(
        self,
        keyword: str,
    ) -> list[ScannedFile]:

        keyword = keyword.lower()

        return [
            file
            for file in self.get_files()
            if keyword in file.name.lower()
        ]

    # ======================================================
    # LANGUAGE FILTER
    # ======================================================

    def files_by_language(
        self,
        language: str,
    ) -> list[ScannedFile]:

        language = language.lower()

        return [
            file
            for file in self.get_files()
            if file.language.lower()
            == language
        ]

    # ======================================================
    # EXTENSION FILTER
    # ======================================================

    def files_by_extension(
        self,
        extension: str,
    ) -> list[ScannedFile]:

        extension = extension.lower()

        if not extension.startswith("."):

            extension = "." + extension

        return [
            file
            for file in self.get_files()
            if file.extension == extension
        ]

    # ======================================================
    # CODE SEARCH
    # ======================================================

    def find_function(
        self,
        name: str,
    ) -> list:

        return (
            self.code_indexer
            .find_function(name)
        )

    def find_class(
        self,
        name: str,
    ) -> list:

        return (
            self.code_indexer
            .find_class(name)
        )

    def find_import(
        self,
        module: str,
    ) -> list:

        return (
            self.code_indexer
            .find_import(module)
        )

    def search_symbols(
        self,
        keyword: str,
    ) -> dict[str, list]:

        return (
            self.code_indexer
            .search(keyword)
        )

    # ======================================================
    # STATISTICS
    # ======================================================

    def statistics(
        self,
    ) -> dict[str, Any]:

        context = (
            self.require_context()
        )

        code_stats = (
            self.code_indexer
            .statistics()
        )

        return {
            "project": (
                context.summary.project_name
            ),

            "files": (
                context.summary.total_files
            ),

            "directories": (
                context.summary.total_directories
            ),

            "languages": (
                context.summary.languages
            ),

            "frameworks": (
                context.summary.frameworks
            ),

            "dependencies": len(
                context.dependencies
            ),

            "indexed_files": (
                code_stats["files"]
            ),

            "classes": (
                code_stats["classes"]
            ),

            "functions": (
                code_stats["functions"]
            ),

            "imports": (
                code_stats["imports"]
            ),
        }

    # ======================================================
    # LLM CONTEXT
    # ======================================================

    def build_llm_context(
        self,
        max_chars: int = 12000,
    ) -> str:

        return (
            self.context_builder.build(
                self.require_context(),
                max_chars=max_chars,
            )
        )

    # ======================================================
    # EXPORT
    # ======================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:

        context = (
            self.require_context()
        )

        return {
            "summary": {
                "root": (
                    context.summary.root
                ),

                "project_name": (
                    context.summary.project_name
                ),

                "total_files": (
                    context.summary.total_files
                ),

                "total_directories": (
                    context.summary.total_directories
                ),

                "languages": (
                    context.summary.languages
                ),

                "frameworks": (
                    context.summary.frameworks
                ),

                "dependencies": (
                    context.summary.dependencies
                ),
            },

            "analysis": (
                context.analysis
            ),

            "dependencies": (
                context.dependencies
            ),

            "tree": context.tree,

            "index": (
                self.code_indexer
                .to_dict()
            ),
        }

    # ======================================================
    # REFRESH
    # ======================================================

    def refresh(self) -> None:

        context = (
            self.require_context()
        )

        self.build(
            context.summary.root
        )

    # ======================================================
    # CLEAR
    # ======================================================

    def clear(self) -> None:

        self.context = None

        self._file_by_name.clear()

        self.code_indexer.clear()

    # ======================================================
    # MAGIC METHODS
    # ======================================================

    def __len__(self) -> int:

        if not self.ready:

            return 0

        return (
            self.context
            .summary
            .total_files
        )

    def __bool__(self) -> bool:

        return self.ready

    def __repr__(self) -> str:

        if not self.ready:

            return (
                "ProjectContext(not built)"
            )

        summary = (
            self.context.summary
        )

        return (
            "ProjectContext("
            f"{summary.project_name}, "
            f"{summary.total_files} files)"
        )
        