import logging
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import inspect, text
from app.config import get_settings
from contextlib import contextmanager

logger = logging.getLogger(__name__)

engine = create_engine(
    get_settings().database_uri, 
    echo=get_settings().env.lower() in ["dev", "development", "test", "testing", "staging"],
    pool_size=get_settings().db_pool_size,
    max_overflow=get_settings().db_additional_overflow,
    pool_timeout=get_settings().db_pool_timeout,
    pool_recycle=get_settings().db_pool_recycle,
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    _ensure_exercise_columns()


def _ensure_exercise_columns():
    inspector = inspect(engine)
    try:
        table_names = inspector.get_table_names()
    except Exception as e:
        logger.warning(f"Schema inspection failed: {e}")
        return

    if "exercise" not in table_names:
        return

    try:
        columns = {c["name"] for c in inspector.get_columns("exercise")}
    except Exception as e:
        logger.warning(f"Could not inspect exercise columns: {e}")
        return

    if "secondary_muscles" in columns:
        return

    # Safe additive migration for both SQLite and PostgreSQL.
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE exercise ADD COLUMN secondary_muscles VARCHAR"))
        logger.info("Added missing column: exercise.secondary_muscles")
    except Exception as e:
        logger.warning(f"Could not add exercise.secondary_muscles column automatically: {e}")

def drop_all():
    SQLModel.metadata.drop_all(bind=engine)
    
def _session_generator():
    with Session(engine) as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

def get_session():
    yield from _session_generator()

@contextmanager
def get_cli_session():
    yield from _session_generator()
