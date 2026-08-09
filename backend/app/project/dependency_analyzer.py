from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DependencyAnalyzer:
    """
    Detects dependencies, frameworks and package managers
    used by an existing project.

    Supported ecosystems

    - Python
    - Node.js
    - Java
    - Go
    - Rust
    - PHP

    More ecosystems can easily be added later.
    """

    def analyze(
        self,
        project_path: str | Path,
    ) -> dict[str, Any]:

        root = Path(project_path).resolve()

        result = {
            "language": None,
            "framework": None,
            "package_manager": None,
            "dependencies": [],
        }

        # -------------------------
        # Python
        # -------------------------

        requirements = root / "requirements.txt"

        if requirements.exists():

            result["language"] = "Python"

            result["package_manager"] = "pip"

            deps = []

            for line in requirements.read_text(
                encoding="utf-8"
            ).splitlines():

                line = line.strip()

                if (
                    not line
                    or line.startswith("#")
                ):
                    continue

                deps.append(line)

            result["dependencies"] = deps

            framework = self._detect_python_framework(
                deps
            )

            result["framework"] = framework

            return result

        # -------------------------
        # package.json
        # -------------------------

        package = root / "package.json"

        if package.exists():

            result["language"] = "JavaScript"

            result["package_manager"] = "npm"

            data = json.loads(
                package.read_text(
                    encoding="utf-8"
                )
            )

            deps = {}

            deps.update(
                data.get(
                    "dependencies",
                    {},
                )
            )

            deps.update(
                data.get(
                    "devDependencies",
                    {},
                )
            )

            result["dependencies"] = list(
                deps.keys()
            )

            result["framework"] = (
                self._detect_node_framework(
                    deps.keys()
                )
            )

            return result

        # -------------------------
        # Java
        # -------------------------

        if (root / "pom.xml").exists():

            result["language"] = "Java"

            result["package_manager"] = "Maven"

            result["framework"] = "Spring"

            return result

        # -------------------------
        # Go
        # -------------------------

        if (root / "go.mod").exists():

            result["language"] = "Go"

            result["package_manager"] = "Go Modules"

            return result

        # -------------------------
        # Rust
        # -------------------------

        if (root / "Cargo.toml").exists():

            result["language"] = "Rust"

            result["package_manager"] = "Cargo"

            return result

        # -------------------------
        # PHP
        # -------------------------

        if (root / "composer.json").exists():

            result["language"] = "PHP"

            result["package_manager"] = "Composer"

            return result

        return result

    # =======================================================
    # Private
    # =======================================================

    def _detect_python_framework(
        self,
        dependencies: list[str],
    ) -> str | None:

        text = "\n".join(
            dependencies
        ).lower()

        if "fastapi" in text:
            return "FastAPI"

        if "django" in text:
            return "Django"

        if "flask" in text:
            return "Flask"

        return None

    def _detect_node_framework(
        self,
        dependencies,
    ) -> str | None:

        deps = {
            dep.lower()
            for dep in dependencies
        }

        if "next" in deps:
            return "Next.js"

        if "react" in deps:
            return "React"

        if "express" in deps:
            return "Express"

        if "vue" in deps:
            return "Vue"

        if "angular" in deps:
            return "Angular"

        return None