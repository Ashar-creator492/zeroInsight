# SQLAlchemy engine and request-scoped database session setup.
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def make_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


# Provide a database session whose lifetime is scoped to the request.
def get_db() -> Generator[Session, None, None]:
    with sessionmaker(bind=make_engine())() as session:
        yield session
