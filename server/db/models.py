from __future__ import annotations

from sqlalchemy import Column, String

from server.db.engine import Base


class ProjectModel(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
