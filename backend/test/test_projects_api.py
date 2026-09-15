import uuid
from datetime import datetime, UTC

from fastapi.testclient import TestClient

from app.database.database import Base, SessionLocal, engine
from app.database.models import Project
from app.main import app
from app.services.auth.service import create_access_token


Base.metadata.create_all(bind=engine)
TEST_TOKEN = create_access_token(
    user_id=1,
    username="santhosh_test",
)

AUTH_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
}


def create_test_project(
    session_id="test-project-session",
):
    db = SessionLocal()

    try:
        project = Project(
            user_id=1,
            session_id=session_id,
            title="Test Project",
            prompt="Create a hello world application",
            project_path="generated/test-project",
            zip_path="generated/test-project.zip",
            created_at=datetime.now(UTC).replace(
                tzinfo=None
            ),
        )

        db.add(project)
        db.commit()
        db.refresh(project)

        return project

    finally:
        db.close()


def delete_test_project(project_id):
    db = SessionLocal()

    try:
        project = (
            db.query(Project)
            .filter(Project.id == project_id)
            .first()
        )

        if project is not None:
            db.delete(project)
            db.commit()

    finally:
        db.close()


def delete_test_projects_by_session(session_id):
    db = SessionLocal()

    try:
        projects = (
            db.query(Project)
            .filter(Project.session_id == session_id)
            .all()
        )

        for project in projects:
            db.delete(project)

        db.commit()

    finally:
        db.close()


def test_get_project():
    project = create_test_project(
        session_id=f"single-project-{uuid.uuid4()}"
    )

    try:
        client = TestClient(app)

        response = client.get(
            f"/projects/{project.id}", headers=AUTH_HEADERS)

        assert response.status_code == 200

        data = response.json()

        assert data["success"] is True

        result = data["project"]

        assert result["id"] == project.id
        assert (
            result["session_id"]
            == project.session_id
        )
        assert result["title"] == "Test Project"
        assert (
            result["prompt"]
            == "Create a hello world application"
        )
        assert (
            result["project_path"]
            == "generated/test-project"
        )
        assert (
            result["zip_path"]
            == "generated/test-project.zip"
        )
        assert result["created_at"] is not None

    finally:
        delete_test_project(project.id)


def test_get_missing_project():
    client = TestClient(app)

    response = client.get(
        f"/projects/999999999", headers=AUTH_HEADERS)

    assert response.status_code == 404

    data = response.json()

    assert (
        data["detail"]
        == "Project not found."
    )


def test_get_projects_by_session():
    session_id = (
        f"project-history-{uuid.uuid4()}"
    )

    project_1 = create_test_project(
        session_id=session_id
    )

    project_2 = create_test_project(
        session_id=session_id
    )

    try:
        client = TestClient(app)

        response = client.get(
            "/projects/",
            params={"session_id": session_id}, headers=AUTH_HEADERS)

        assert response.status_code == 200

        data = response.json()

        assert data["success"] is True
        assert data["count"] == 2
        assert len(data["projects"]) == 2

        project_ids = [
            project["id"]
            for project in data["projects"]
        ]

        assert project_1.id in project_ids
        assert project_2.id in project_ids

        for project in data["projects"]:
            assert (
                project["session_id"]
                == session_id
            )

    finally:
        delete_test_projects_by_session(
            session_id
        )


def test_get_projects_empty_session():
    session_id = (
        f"empty-project-session-{uuid.uuid4()}"
    )

    client = TestClient(app)

    response = client.get(
        "/projects/",
        params={"session_id": session_id}, headers=AUTH_HEADERS)

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["count"] == 0
    assert data["projects"] == []


def test_get_all_projects():
    session_id = (
        f"all-projects-{uuid.uuid4()}"
    )

    project = create_test_project(
        session_id=session_id
    )

    try:
        client = TestClient(app)

        response = client.get("/projects/", headers=AUTH_HEADERS)

        assert response.status_code == 200

        data = response.json()

        assert data["success"] is True
        assert data["count"] >= 1

        project_ids = [
            item["id"]
            for item in data["projects"]
        ]

        assert project.id in project_ids

    finally:
        delete_test_project(project.id)


def test_delete_project():
    project = create_test_project(
        session_id=f"delete-project-{uuid.uuid4()}"
    )

    client = TestClient(app)

    response = client.delete(
        f"/projects/{project.id}", headers=AUTH_HEADERS)

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert (
        data["message"]
        == "Project deleted successfully."
    )
    assert data["project_id"] == project.id

    db = SessionLocal()

    try:
        deleted_project = (
            db.query(Project)
            .filter(Project.id == project.id)
            .first()
        )

        assert deleted_project is None

    finally:
        db.close()


def test_delete_missing_project():
    client = TestClient(app)

    project_id = 999999999

    response = client.delete(
        f"/projects/{project_id}", headers=AUTH_HEADERS)

    assert response.status_code == 404

    data = response.json()

    assert (
        data["detail"]
        == "Project not found."
    )

