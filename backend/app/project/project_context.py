from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logger import logger

from app.project.project_scanner import ProjectScanner
from app.project.project_analyzer import ProjectAnalyzer
from app.project.dependency_analyzer import DependencyAnalyzer
from app.project.tree_builder import TreeBuilder
from app.project.code_indexer import CodeIndexer, FileIndex


# ==========================================================
# DATA MODELS
# ==========================================================


@dataclass
class ProjectSummary:
    """
    High-level summary of the project.
    """

    root: str

    project_name: str

    total_files: int = 0

    total_directories: int = 0

    languages: dict[str, int] = field(default_factory=dict)

    frameworks: list[str] = field(default_factory=list)

    dependencies: list[str] = field(default_factory=list)


@dataclass
class ProjectContextData:
    """
    Complete project context shared across all agents.
    """

    summary: ProjectSummary

    tree: str

    scanned_files: list[Any]

    dependencies: dict[str, Any]

    analysis: dict[str, Any]

    code_index: dict[str, FileIndex]


# ==========================================================
# CONTEXT BUILDER
# ==========================================================


class ContextBuilder:
    """
    Formats a ProjectContextData into a compact string suitable
    for injection into LLM prompts.

    Kept separate from ProjectContext so the prompt-formatting
    logic can evolve (architecture summary, entry points,
    README summary, detected APIs/DBs/tests, etc.) without
    touching the data-access layer.
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
            f"Files: {summary.total_files}"
        )

        sections.append(
            f"Directories: {summary.total_directories}"
        )

        if summary.languages:

            sections.append(
                "Languages: "
                + ", ".join(
                    f"{k} ({v})"
                    for k, v in summary.languages.items()
                )
            )

        if summary.frameworks:

            sections.append(
                "Frameworks: "
                + ", ".join(summary.frameworks)
            )

        if summary.dependencies:

            sections.append(
                "Dependencies: "
                + ", ".join(summary.dependencies)
            )

        # TODO: add architecture summary, entry points (main.py),
        # package manager, README summary, detected APIs,
        # detected database, detected tests, etc.

        sections.append("")

        sections.append("Directory Tree")

        sections.append(context.tree)

        text = "\n".join(sections)

        if len(text) > max_chars:

            text = text[:max_chars]

        return text


# ==========================================================
# PROJECT CONTEXT
# ==========================================================


class ProjectContext:
    """
    Central project knowledge provider.

    This class combines information from every project-analysis
    subsystem and exposes one unified API.

    Components
    ----------

    • ProjectScanner

    • TreeBuilder

    • DependencyAnalyzer

    • ProjectAnalyzer

    • CodeIndexer

    • ContextBuilder

    Every AI agent should obtain project knowledge through this
    class instead of using individual analyzers directly.
    """

    def __init__(self):

        self.scanner = ProjectScanner()

        self.tree_builder = TreeBuilder()

        self.dependency_analyzer = DependencyAnalyzer()

        self.project_analyzer = ProjectAnalyzer()

        self.code_indexer = CodeIndexer()

        self.context_builder = ContextBuilder()

        self.context: ProjectContextData | None = None

        # filename -> file object, for O(1) exact-name lookups
        self._file_by_name: dict[str, Any] = {}

    # ======================================================
    # BUILD CONTEXT
    # ======================================================

    def build(
        self,
        project_directory: str | Path,
    ) -> ProjectContextData:

        root = Path(project_directory).resolve()

        if not root.exists():
            raise FileNotFoundError(root)

        logger.info(
            "Building project context..."
        )

        # ------------------------------------------
        # Scan project
        # ------------------------------------------

        scanned_files = self.scanner.scan(root)

        # ------------------------------------------
        # Directory tree
        # ------------------------------------------

        tree = self.tree_builder.build(root)

        # ------------------------------------------
        # Dependency analysis
        # ------------------------------------------

        dependencies = self.dependency_analyzer.analyze(root)

        # ------------------------------------------
        # Project analysis
        # ------------------------------------------

        analysis = self.project_analyzer.analyze(root)

        # ------------------------------------------
        # Source code index
        # ------------------------------------------

        code_index = self.code_indexer.build(root)

        # ------------------------------------------
        # Language statistics
        # ------------------------------------------

        languages: dict[str, int] = {}

        for item in scanned_files:

            language = getattr(
                item,
                "language",
                "unknown",
            )

            languages[language] = (
                languages.get(language, 0) + 1
            )

        # ------------------------------------------
        # Filename index (for O(1) find_file lookups)
        # ------------------------------------------

        self._file_by_name = {
            Path(item.path).name.lower(): item
            for item in scanned_files
        }

        # ------------------------------------------
        # Summary
        # ------------------------------------------

        summary = ProjectSummary(

            root=str(root),

            project_name=root.name,

            total_files=len(scanned_files),

            total_directories=sum(
                1
                for path in root.rglob("*")
                if path.is_dir()
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
    # ACCESSORS
    # ======================================================

    @property
    def ready(self) -> bool:
        """
        Whether a project has already been indexed.
        """

        return self.context is not None

    def require_context(self) -> ProjectContextData:

        if self.context is None:

            raise RuntimeError(
                "Project context has not been built."
            )

        return self.context

    def get_summary(
        self,
    ) -> ProjectSummary:

        return self.require_context().summary

    def get_tree(
        self,
    ) -> str:

        return self.require_context().tree

    def get_analysis(
        self,
    ) -> dict[str, Any]:

        return dict(self.require_context().analysis)

    def get_dependencies(
        self,
    ) -> dict[str, Any]:

        return dict(self.require_context().dependencies)

    def get_index(
        self,
    ) -> dict[str, FileIndex]:

        return dict(self.require_context().code_index)

    # ======================================================
    # FILE ACCESS
    # ======================================================

    def get_files(self) -> list[Any]:
        """
        Return every scanned file.
        """

        return list(self.require_context().scanned_files)

    def find_file(
        self,
        name: str,
    ) -> Any | None:
        """
        Find a file by filename (O(1) lookup).
        """

        return self._file_by_name.get(name.lower())

    def find_files(
        self,
        keyword: str,
    ) -> list[Any]:
        """
        Find files whose filename contains keyword.
        """

        keyword = keyword.lower()

        results = []

        for file in self.get_files():

            path = Path(file.path)

            if keyword in path.name.lower():

                results.append(file)

        return results

    # ======================================================
    # LANGUAGE FILTERING
    # ======================================================

    def files_by_language(
        self,
        language: str,
    ) -> list[Any]:
        """
        Return files written in one language.
        """

        language = language.lower()

        return [

            file

            for file in self.get_files()

            if getattr(
                file,
                "language",
                "",
            ).lower() == language

        ]

    def files_by_extension(
        self,
        extension: str,
    ) -> list[Any]:
        """
        Return files matching an extension.
        """

        extension = extension.lower()

        if not extension.startswith("."):

            extension = "." + extension

        results = []

        for file in self.get_files():

            if Path(file.path).suffix.lower() == extension:

                results.append(file)

        return results

    # ======================================================
    # CODE INDEX SEARCH
    # ======================================================

    def find_function(
        self,
        name: str,
    ) -> list:
        """
        Search indexed functions.
        """

        return self.code_indexer.find_function(
            name
        )

    def find_class(
        self,
        name: str,
    ) -> list:
        """
        Search indexed classes.
        """

        return self.code_indexer.find_class(
            name
        )

    def find_import(
        self,
        module: str,
    ) -> list:
        """
        Search indexed imports.
        """

        return self.code_indexer.find_import(
            module
        )

    def search_symbols(
        self,
        keyword: str,
    ) -> list:
        """
        Global symbol search.
        """

        return self.code_indexer.search(
            keyword
        )

    # ======================================================
    # PROJECT STATISTICS
    # ======================================================

    def statistics(
        self,
    ) -> dict[str, Any]:
        """
        Return project-wide statistics.
        """

        context = self.require_context()

        code_stats = self.code_indexer.statistics()

        return {

            "project": context.summary.project_name,

            "files": context.summary.total_files,

            "directories": context.summary.total_directories,

            "languages": context.summary.languages,

            "frameworks": context.summary.frameworks,

            "dependencies": len(
                context.dependencies
            ),

            "indexed_files": code_stats["files"],

            "classes": code_stats["classes"],

            "functions": code_stats["functions"],

            "imports": code_stats["imports"],

        }

    # ======================================================
    # LLM CONTEXT
    # ======================================================

    def build_llm_context(
        self,
        max_chars: int = 12000,
    ) -> str:
        """
        Build a compact context string for LLM prompts.

        Delegates formatting to ContextBuilder, which can be
        extended independently (architecture summary, entry
        points, README summary, detected APIs/DB/tests, etc.)
        without changes here.
        """

        return self.context_builder.build(
            self.require_context(),
            max_chars=max_chars,
        )

    # ======================================================
    # EXPORT
    # ======================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Export complete project context.
        """

        context = self.require_context()

        return {

            "summary": {

                "root": context.summary.root,

                "project_name": context.summary.project_name,

                "total_files": context.summary.total_files,

                "total_directories": context.summary.total_directories,

                "languages": context.summary.languages,

                "frameworks": context.summary.frameworks,

                "dependencies": context.summary.dependencies,

            },

            "analysis": context.analysis,

            "dependencies": context.dependencies,

            "tree": context.tree,

            "index": self.code_indexer.to_dict(),

        }

    # ======================================================
    # REFRESH
    # ======================================================

    def refresh(
        self,
    ) -> None:
        """
        Rebuild project context after files change.
        """

        self.build(
            Path(self.require_context().summary.root)
        )

    # ======================================================
    # RESET
    # ======================================================

    def clear(
        self,
    ) -> None:
        """
        Remove cached project context.
        """

        self.context = None

        self._file_by_name = {}

        self.code_indexer.clear()

    # ======================================================
    # MAGIC METHODS
    # ======================================================

    def __len__(
        self,
    ) -> int:

        if not self.ready:

            return 0

        return self.context.summary.total_files

    def __bool__(
        self,
    ) -> bool:

        return self.ready

    def __repr__(
        self,
    ) -> str:

        if not self.ready:

            return "ProjectContext(not built)"

        summary = self.context.summary

        return (
            "ProjectContext("
            f"{summary.project_name}, "
            f"{summary.total_files} files)"
        )