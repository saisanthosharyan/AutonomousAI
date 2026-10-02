from pathlib import Path
from unittest.mock import patch

from app.services.testing.node_test_runner import NodeTestRunner


def test_react_tests_run_non_interactively_and_allow_no_tests(tmp_path):

    (tmp_path / "package.json").write_text(
        """
{
  "name": "react-app",
  "scripts": {
    "test": "react-scripts test"
  }
}
""",
        encoding="utf-8",
    )

    (tmp_path / "node_modules").mkdir()

    runner = NodeTestRunner()

    with patch(
        "app.services.testing.node_test_runner.shutil.which",
        return_value="npm",
    ), patch(
        "app.services.testing.node_test_runner.subprocess.run"
    ) as run_mock:

        run_mock.return_value.returncode = 0
        run_mock.return_value.stdout = "No tests found"
        run_mock.return_value.stderr = ""

        result = runner.run(str(tmp_path))

    assert result["success"] is True

    command = run_mock.call_args.args[0]

    assert command == [
        "npm",
        "test",
        "--",
        "--watchAll=false",
        "--passWithNoTests",
    ]
