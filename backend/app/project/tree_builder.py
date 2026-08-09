from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logger import logger


# ==========================================================
# TREE NODE
# ==========================================================


@dataclass
class TreeNode:
    """
    Represents one node inside a project tree.

    A node can be either:
        • directory
        • file
    """

    name: str

    path: str

    is_file: bool

    size: int = 0

    extension: str = ""

    children: list["TreeNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:

        return {
            "name": self.name,
            "path": self.path,
            "is_file": self.is_file,
            "size": self.size,
            "extension": self.extension,
            "children": [
                child.to_dict()
                for child in self.children
            ],
        }


# ==========================================================
# TREE BUILDER
# ==========================================================


class TreeBuilder:
    """
    Builds an in-memory representation of an entire project.

    Example

    project/
    ├── app/
    │   ├── main.py
    │   └── api/
    ├── requirements.txt
    └── README.md
    """

    DEFAULT_IGNORES = {

        ".git",

        ".idea",

        ".vscode",

        "__pycache__",

        ".pytest_cache",

        ".mypy_cache",

        ".ruff_cache",

        ".venv",

        "venv",

        "env",

        "node_modules",

        "dist",

        "build",

        ".next",

        ".cache",

        ".DS_Store",

        "Thumbs.db",
    }

    # ======================================================
    # PUBLIC
    # ======================================================

    def build(
        self,
        project_directory: str | Path,
    ) -> TreeNode:

        root = Path(project_directory)

        if not root.exists():

            raise FileNotFoundError(root)

        logger.info(
            "Building project tree: %s",
            root,
        )

        return self._build_node(root)

    # ======================================================
    # INTERNAL
    # ======================================================

    def _build_node(
        self,
        path: Path,
    ) -> TreeNode:

        if path.is_file():

            return TreeNode(

                name=path.name,

                path=str(path.resolve()),

                is_file=True,

                size=path.stat().st_size,

                extension=path.suffix.lower(),
            )

        node = TreeNode(

            name=path.name,

            path=str(path.resolve()),

            is_file=False,
        )

        try:

            children = sorted(

                path.iterdir(),

                key=lambda item: (
                    item.is_file(),
                    item.name.lower(),
                ),
            )

        except PermissionError:

            logger.warning(
                "Permission denied: %s",
                path,
            )

            return node

        for child in children:

            if child.name in self.DEFAULT_IGNORES:

                continue

            node.children.append(

                self._build_node(child)

            )

        return node

    # ======================================================
    # FLATTEN
    # ======================================================

    def flatten(
        self,
        root: TreeNode,
    ) -> list[TreeNode]:

        nodes: list[TreeNode] = []

        def walk(node: TreeNode):

            nodes.append(node)

            for child in node.children:

                walk(child)

        walk(root)

        return nodes

    # ======================================================
    # FILES ONLY
    # ======================================================

    def get_files(
        self,
        root: TreeNode,
    ) -> list[TreeNode]:

        return [

            node

            for node in self.flatten(root)

            if node.is_file

        ]

    # ======================================================
    # DIRECTORIES ONLY
    # ======================================================

    def get_directories(
        self,
        root: TreeNode,
    ) -> list[TreeNode]:

        return [

            node

            for node in self.flatten(root)

            if not node.is_file

        ]

    # ======================================================
    # FIND
    # ======================================================

    def find(
        self,
        root: TreeNode,
        name: str,
    ) -> TreeNode | None:

        for node in self.flatten(root):

            if node.name == name:

                return node

        return None

    # ======================================================
    # TREE AS TEXT
    # ======================================================

    def to_text(
        self,
        root: TreeNode,
    ) -> str:

        lines: list[str] = []

        def walk(
            node: TreeNode,
            prefix: str = "",
        ):

            lines.append(
                prefix + node.name
            )

            for child in node.children:

                walk(
                    child,
                    prefix + "    ",
                )

        walk(root)

        return "\n".join(lines)

    # ======================================================
    # STATISTICS
    # ======================================================

    def statistics(
        self,
        root: TreeNode,
    ) -> dict[str, int]:

        files = 0

        directories = 0

        total_size = 0

        for node in self.flatten(root):

            if node.is_file:

                files += 1

                total_size += node.size

            else:

                directories += 1

        return {

            "files": files,

            "directories": directories,

            "total_size": total_size,
        }