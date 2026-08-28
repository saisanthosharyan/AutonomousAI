from app.project.project_analyzer import ProjectAnalyzer


def test_detect_python_project(tmp_path):
    (tmp_path / "main.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect(str(tmp_path)) == "python"


def test_detect_node_project(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"name": "test-project"}',
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect(str(tmp_path)) == "node"


def test_detect_java_project(tmp_path):
    (tmp_path / "Main.java").write_text(
        "public class Main {}",
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect(str(tmp_path)) == "java"


def test_detect_cpp_project(tmp_path):
    (tmp_path / "main.cpp").write_text(
        "int main() { return 0; }",
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect(str(tmp_path)) == "cpp"


def test_detect_docker_project(tmp_path):
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.12",
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect(str(tmp_path)) == "docker"


def test_detect_unknown_project(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Test",
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect(str(tmp_path)) == "unknown"


def test_docker_can_be_excluded(tmp_path):
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.12",
        encoding="utf-8",
    )

    (tmp_path / "main.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect(
        str(tmp_path),
        exclude={"docker"},
    ) == "python"


def test_analyze_python_project(tmp_path):
    (tmp_path / "main.py").write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    (tmp_path / "requirements.txt").write_text(
        "fastapi\n",
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    result = analyzer.analyze(str(tmp_path))

    assert result["language"] == "Python"
    assert result["framework"] == "FastAPI"
    assert result["execution_type"] == "python"
    assert result["entry_point"] == "main.py"
    assert "fastapi" in result["dependencies"]
    assert result["file_count"] >= 2


def test_detect_node_framework(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"express": "^5.0.0"}}',
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect_framework(tmp_path) == "Express"


def test_detect_react_framework(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"react": "^19.0.0"}}',
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect_framework(tmp_path) == "React"


def test_detect_nextjs_framework(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"next": "^16.0.0"}}',
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect_framework(tmp_path) == "Next.js"


def test_detect_vue_framework(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"vue": "^3.0.0"}}',
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect_framework(tmp_path) == "Vue"


def test_detect_framework_from_dev_dependencies(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"devDependencies": {"react": "^19.0.0"}}',
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect_framework(tmp_path) == "React"


def test_invalid_package_json_returns_unknown(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": ',
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect_framework(tmp_path) == "Unknown"


def test_detect_entry_point_in_src(tmp_path):
    src = tmp_path / "src"
    src.mkdir()

    (src / "main.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect_entry_point(tmp_path) == "src/main.py"


def test_ignored_directories_are_not_detected(tmp_path):
    venv = tmp_path / ".venv"
    venv.mkdir()

    (venv / "fake.py").write_text(
        "print('fake')",
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect(str(tmp_path)) == "unknown"


def test_detect_language(tmp_path):
    (tmp_path / "main.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )

    analyzer = ProjectAnalyzer()

    assert analyzer.detect_language(tmp_path) == "Python"