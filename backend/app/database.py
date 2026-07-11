from sqlmodel import SQLModel, Session, create_engine

from app.config import settings

connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Creates all tables (if they don't already exist)."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: yields a database session for each request."""
    with Session(engine) as session:
        yield session
