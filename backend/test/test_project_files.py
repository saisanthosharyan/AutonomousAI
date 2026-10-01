from app.api.project_files import _collect_files


def test_collect_files_ignores_repair_directory(tmp_path):
    (tmp_path / "index.html").write_text(
        "<html></html>",
        encoding="utf-8",
    )

    repair_dir = tmp_path / "repair"
    repair_dir.mkdir()

    (repair_dir / "old_code.txt").write_text(
        "OLD BROKEN CODE",
        encoding="utf-8",
    )

    (repair_dir / "repair_report.md").write_text(
        "Internal repair report",
        encoding="utf-8",
    )

    files = _collect_files(tmp_path)

    paths = {
        item["path"]
        for item in files
    }

    assert "index.html" in paths
    assert not any(
        path.startswith("repair/")
        for path in paths
    )
