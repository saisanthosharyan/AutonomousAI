from pathlib import Path

from app.builders.project_builder import ProjectBuilder

def test_real_project_build(tmp_path):

    builder = ProjectBuilder()

    llm_output = """
FILE: app.py

print("Hello AutoDev-AI")

FILE: requirements.txt

"""

    result = builder.build(
        "test_project",
        llm_output,
        project_path=str(tmp_path / "test_project"),
    )

    project = Path(result["project_path"])

    assert project.exists()
    assert (project / "app.py").exists()
    assert (project / "requirements.txt").exists()
    assert Path(result["zip_path"]).exists()

    assert "app.py" in result["files"]
    assert "requirements.txt" in result["files"]