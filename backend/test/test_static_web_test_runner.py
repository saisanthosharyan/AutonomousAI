from app.services.testing.static_web_test_runner import StaticWebTestRunner


def test_browser_runtime_handles_number_input(tmp_path):
    index_file = tmp_path / "index.html"

    index_file.write_text(
        """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Number Input Test</title>
</head>
<body>
    <form id="test-form">
        <input type="text" id="title" required>
        <input type="number" id="amount" required>
        <button type="submit">Submit</button>
    </form>

    <script>
        document
            .getElementById("test-form")
            .addEventListener("submit", function (event) {
                event.preventDefault();
            });
    </script>
</body>
</html>
""".strip(),
        encoding="utf-8",
    )

    runner = StaticWebTestRunner()

    result = runner.run(str(tmp_path))

    assert result["success"] is True, (
        result.get("stderr")
        or result.get("stdout")
    )
