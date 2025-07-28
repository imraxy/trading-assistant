"""
Database connection and session management.

Handles SQLAlchemy engine creation, session management,
and provides dependency injection for FastAPI.
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Generator
from app.config import get_database_url, get_settings

# Get settings
settings = get_settings()

# Create SQLAlchemy engine with appropriate settings for SQLite vs PostgreSQL
if settings.is_sqlite():
    # SQLite-specific configuration
    engine = create_engine(
        get_database_url(),
        pool_pre_ping=True,
        echo=settings.database.echo,
        connect_args={"check_same_thread": False}  # Required for SQLite with FastAPI
    )
else:
    # PostgreSQL configuration
    engine = create_engine(
        get_database_url(),
        pool_pre_ping=True,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        echo=settings.database.echo,
    )

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
metadata = MetaData()
Base = declarative_base(metadata=metadata)


def get_db() -> Generator:
    """
    Dependency function to get database session.
    
    Yields:
        SQLAlchemy database session
        
    Usage:
        @app.get("/")
        def read_root(db: Session = Depends(get_db)):
            # Use db session here
            pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    print(f"Created database tables using: {settings.get_database_url()}")


def drop_tables():
    """Drop all database tables (use with caution!)"""
    Base.metadata.drop_all(bind=engine)
    print("Dropped all database tables")


def get_engine():
    """Get the database engine"""
    return engine 