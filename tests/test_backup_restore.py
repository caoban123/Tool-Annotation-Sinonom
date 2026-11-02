import pytest
from pathlib import Path
from Web.app.services.backup import create_database_backup, restore_database_backup, list_backups, BACKUP_DIR

def test_backup_and_restore_cycle():
    # 1. Create a backup
    res = create_database_backup(tag="test_suite")
    assert res["filename"].startswith("backup_test_suite_")
    backup_file = BACKUP_DIR / res["filename"]
    assert backup_file.exists()
    assert backup_file.stat().st_size > 0

    # 2. List backups
    backups = list_backups()
    assert len(backups) > 0
    assert any(b["filename"] == res["filename"] for b in backups)

    # 3. Restore from backup
    restore_res = restore_database_backup(res["filename"])
    assert restore_res["status"] == "success"
