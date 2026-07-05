from functools import lru_cache
from collections.abc import Generator

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import get_settings

Base = declarative_base()


@lru_cache
def get_engine():
    database_url = get_settings().database_url
    if not database_url:
        return None

    return create_engine(database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory():
    engine = get_engine()
    if engine is None:
        return None

    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def is_database_enabled() -> bool:
    return get_engine() is not None


def init_database() -> None:
    engine = get_engine()
    if engine is None:
        return

    Base.metadata.create_all(bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="Banco de dados nao configurado. Defina DATABASE_URL.",
        )

    db = session_factory()
    try:
        yield db
    finally:
        db.close()
