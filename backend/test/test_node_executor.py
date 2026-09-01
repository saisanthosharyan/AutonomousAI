from pathlib import Path

from app.services.execution.node_executor import NodeExecutor


def create_project(tmp_path: Path, files: dict[str, str]) -> Path:
    project = tmp_path / "project"
    project.mkdir()

    for name, content in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return project


def test_plain_node_project(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.js": 'console.log("hello node")',
        },
    )

    result = NodeExecutor().run(str(project))

    assert result["success"] is True
    assert "hello node" in result["stdout"]
    assert result["return_code"] == 0


def test_package_json_start_script(tmp_path):
    project = create_project(
        tmp_path,
        {
            "package.json": """
{
  "name": "test-project",
  "version": "1.0.0",
  "scripts": {
    "start": "node main.js"
  }
}
""",
            "main.js": 'console.log("started")',
        },
    )

    result = NodeExecutor().run(str(project))

    assert result["success"] is True
    assert "started" in result["stdout"]
    assert result["return_code"] == 0


def test_package_json_build_script(tmp_path):
    project = create_project(
        tmp_path,
        {
            "package.json": """
{
  "name": "test-project",
  "version": "1.0.0",
  "scripts": {
    "build": "node build.js"
  }
}
""",
            "build.js": 'console.log("build successful")',
        },
    )

    result = NodeExecutor().run(str(project))

    assert result["success"] is True
    assert "build successful" in result["stdout"]
    assert result["return_code"] == 0


def test_npm_test_takes_priority(tmp_path):
    project = create_project(
        tmp_path,
        {
            "package.json": """
{
  "name": "test-project",
  "version": "1.0.0",
  "scripts": {
    "test": "node test.js",
    "start": "node main.js"
  },
  "devDependencies": {
    "jest": "^30.0.0"
  }
}
""",
            "test.js": 'console.log("tests passed")',
            "main.js": 'console.log("start")',
        },
    )

    result = NodeExecutor().run(str(project))

    assert result["success"] is True
    assert "tests passed" in result["stdout"]
    assert result["return_code"] == 0


def test_express_server(tmp_path):
    project = create_project(
        tmp_path,
        {
            "package.json": """
{
  "name": "express-test",
  "version": "1.0.0",
  "dependencies": {
    "express": "^5.0.0"
  }
}
""",
            "server.js": """
const http = require("http");

const server = http.createServer((req, res) => {
    res.end("hello");
});

server.listen(0, "127.0.0.1", () => {
    console.log("server started");
});
""",
        },
    )

    result = NodeExecutor().run(str(project))

    assert result["success"] is True
    assert "server started" in result["stdout"]
    assert result["return_code"] == 0


def test_invalid_package_json(tmp_path):
    project = create_project(
        tmp_path,
        {
            "package.json": "{ invalid json",
        },
    )

    result = NodeExecutor().run(str(project))

    assert result["success"] is False
    assert result["return_code"] == -1
    assert result["stderr"]


def test_missing_project(tmp_path):
    project = tmp_path / "missing"

    result = NodeExecutor().run(str(project))

    assert result["success"] is False
    assert result["return_code"] == -1
    assert "does not exist" in result["stderr"]


def test_missing_node_entry(tmp_path):
    project = create_project(
        tmp_path,
        {
            "package.json": """
{
  "name": "empty-project",
  "version": "1.0.0"
}
""",
        },
    )

    result = NodeExecutor().run(str(project))

    assert result["success"] is False
    assert result["return_code"] == -1
    assert "No runnable Node.js entry file found" in result["stderr"]


def test_env_file_is_loaded(tmp_path):
    project = create_project(
        tmp_path,
        {
            ".env": "AUTODEV_TEST=value123",
            "main.js": """
console.log(process.env.AUTODEV_TEST);
""",
        },
    )

    result = NodeExecutor().run(str(project))

    assert result["success"] is True
    assert "value123" in result["stdout"]
    assert result["return_code"] == 0