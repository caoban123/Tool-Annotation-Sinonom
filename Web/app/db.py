import os
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

# Determine base data directory
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "hanviet.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")
if make_url(DATABASE_URL).database not in (None, ':memory:'):
    DB_PATH = Path(make_url(DATABASE_URL).database)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

# Enable SQLite foreign keys & WAL mode for performance & atomic operations
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def backup_sqlite_db(dest_path: Path) -> bool:
    """Safely back up the SQLite database using SQLite Online Backup API with checkpointing."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(DB_PATH)
    try:
        # Checkpoint WAL first
        source_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        dest_conn = sqlite3.connect(dest_path)
        try:
            source_conn.backup(dest_conn)
            return True
        finally:
            dest_conn.close()
    finally:
        source_conn.close()

def restore_sqlite_db(source_path: Path) -> bool:
    """Safely restore the SQLite database from a backup file."""
    if not source_path.exists():
        raise FileNotFoundError(f"Backup file not found: {source_path}")
    source_conn = sqlite3.connect(source_path)
    try:
        dest_conn = sqlite3.connect(DB_PATH)
        try:
            source_conn.backup(dest_conn)
            dest_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            engine.dispose()
            from .migrations import migrate_database
            migrate_database(engine)
            return True
        finally:
            dest_conn.close()
    finally:
        source_conn.close()
