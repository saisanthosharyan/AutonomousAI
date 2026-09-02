from datetime import datetime, UTC
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from .database import Base


class Project(Base):
    """
    Stores generated projects.
    """

    __tablename__ = "projects"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    session_id = Column(
        String(100),
        index=True,
        nullable=False,
    )

    title = Column(
        String(255),
        nullable=False,
    )

    prompt = Column(
        Text,
        nullable=False,
    )

    project_path = Column(
        String(500),
        nullable=False,
    )

    zip_path = Column(
        String(500),
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
class Run(Base):
    """
    Stores the lifecycle and progress state of an AutoDev-AI execution.
    """

    __tablename__ = "runs"

    id = Column(
        String(100),
        primary_key=True,
        index=True,
    )

    session_id = Column(
        String(100),
        index=True,
        nullable=False,
    )

    prompt = Column(
        Text,
        nullable=False,
    )

    status = Column(
        String(30),
        nullable=False,
        default="queued",
    )

    current_step = Column(
        String(100),
        nullable=False,
        default="queued",
    )

    progress = Column(
        Integer,
        nullable=False,
        default=0,
    )

    message = Column(
        Text,
        nullable=False,
        default="Run queued.",
    )

    result = Column(
        Text,
        nullable=True,
    )

    error = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )

    started_at = Column(
        DateTime,
        nullable=True,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )