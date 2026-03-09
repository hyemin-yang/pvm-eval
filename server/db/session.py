from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session, sessionmaker

from server.db.engine import engine

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
