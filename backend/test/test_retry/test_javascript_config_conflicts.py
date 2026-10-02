from app.agents.fixer_agent import FixerAgent


def test_resolves_duplicate_browserslist_configuration():

    fixer = FixerAgent.__new__(FixerAgent)

    package_json = """{
  "name": "task-management-app",
  "browserslist": {
    "production": [">0.2%", "not dead"]
  }
}"""

    file_blocks = [
        (
            "package.json",
            package_json,
        ),
        (
            ".browserslistrc",
            ">0.2%\nnot dead\n",
        ),
    ]

    original_files = {
        "package.json": package_json,
    }

    result = fixer._resolve_javascript_config_conflicts(
        file_blocks,
        original_files,
    )

    paths = {
        fixer._normalize_path_key(path)
        for path, _ in result
    }

    assert "package.json" in paths
    assert ".browserslistrc" not in paths
