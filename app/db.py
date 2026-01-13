from __future__ import annotations

import os
from sqlmodel import SQLModel, Session, create_engine
from .settings import settings

def _db_path() -> str:
    os.makedirs(settings.config_dir, exist_ok=True)
    return os.path.join(settings.config_dir, "papertrellis.db")

engine = create_engine(f"sqlite:///{_db_path()}", connect_args={"check_same_thread": False})

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    return Session(engine)
