import os
import shutil
import datetime
from pathlib import Path
from typing import List, Dict, Any
from ..db import DB_PATH, backup_sqlite_db, restore_sqlite_db

BACKUP_DIR = DB_PATH.parent / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def create_database_backup(tag: str = "manual") -> Dict[str, Any]:
    """Creates a timestamped backup of the SQLite database."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{tag}_{timestamp}.sqlite"
    backup_file_path = BACKUP_DIR / backup_filename

    success = backup_sqlite_db(backup_file_path)
    if not success:
        raise RuntimeError("Không thể tạo backup database.")

    file_size = backup_file_path.stat().st_size
    return {
        "filename": backup_filename,
        "path": str(backup_file_path),
        "size_bytes": file_size,
        "created_at": timestamp,
        "tag": tag
    }

def restore_database_backup(filename: str) -> Dict[str, Any]:
    """Restores the SQLite database from a chosen backup file."""
    # Prevent path traversal
    safe_name = os.path.basename(filename)
    backup_file_path = BACKUP_DIR / safe_name

    if not backup_file_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file backup: {safe_name}")

    # First take an emergency snapshot of current state
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    emergency_path = BACKUP_DIR / f"pre_restore_emergency_{timestamp}.sqlite"
    backup_sqlite_db(emergency_path)

    success = restore_sqlite_db(backup_file_path)
    if not success:
        raise RuntimeError(f"Lỗi khi khôi phục từ {safe_name}")

    return {
        "restored_from": safe_name,
        "emergency_backup": emergency_path.name,
        "status": "success"
    }

def list_backups() -> List[Dict[str, Any]]:
    """Lists available backup files."""
    backups = []
    for f in sorted(BACKUP_DIR.glob("*.sqlite"), key=os.path.getmtime, reverse=True):
        backups.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "modified_at": datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat()
        })
    return backups
