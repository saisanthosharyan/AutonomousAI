from app.project.project_scanner import ProjectScanner


def test_scanner_ignores_autodev_repair_directory(tmp_path):
    (tmp_path / "index.html").write_text(
        "<html></html>",
        encoding="utf-8",
    )

    repair_dir = tmp_path / "repair"
    repair_dir.mkdir()

    (repair_dir / "old_code.txt").write_text(
        "BROKEN OLD CODE",
        encoding="utf-8",
    )

    (repair_dir / "new_code.txt").write_text(
        "REPAIRED CODE",
        encoding="utf-8",
    )

    scanner = ProjectScanner()

    files = scanner.scan(tmp_path)

    relative_paths = {
        item.relative_path.replace("\\", "/")
        for item in files
    }

    assert "index.html" in relative_paths
    assert not any(
        path.startswith("repair/")
        for path in relative_paths
    )
