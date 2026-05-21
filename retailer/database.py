"""
SQLite database setup for the Retailer App.

Uses retailer.db (separate from factory simulator.db and supplier.db).
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
RETAILER_DATABASE_URL = os.getenv("RETAILER_DATABASE_URL", "sqlite:///./retailer.db")

if RETAILER_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(RETAILER_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(RETAILER_DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db() -> None:
    """Create all retailer tables."""
    import retailer.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yield a DB session and close it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
