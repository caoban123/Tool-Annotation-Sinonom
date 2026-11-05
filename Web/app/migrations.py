"""Additive SQLite migration; never reconstruct original input from edited segments."""
import hashlib
import json
import sqlite3
from pathlib import Path
from sqlalchemy import inspect, text
from .db import Base


def migrate_database(engine):
    from . import models  # register all tables for direct invocation as well
    existing = set(inspect(engine).get_table_names())
    additions = {'documents': {'raw_bytes': 'BLOB', 'active': 'BOOLEAN NOT NULL DEFAULT 1',
                              'source_bytes': 'BLOB', 'source_sha256': 'VARCHAR(64)'},
                 'alignments': {'suggestion_context': "TEXT DEFAULT '{}'"},
                 'qa_issues': {'origin': "VARCHAR(32) NOT NULL DEFAULT 'legacy'"}}
    pending = [(table, name, definition) for table, fields in additions.items() if table in existing
               for name, definition in fields.items()
               if name not in {column['name'] for column in inspect(engine).get_columns(table)}]
    if pending and engine.dialect.name == 'sqlite' and engine.url.database not in (None, ':memory:'):
        path = Path(engine.url.database)
        backup = path.with_name(path.name + '.before-web-v2.bak')
        if not backup.exists():
            with sqlite3.connect(path) as source, sqlite3.connect(backup) as target:
                source.backup(target)
    with engine.begin() as conn:
        for table, name, definition in pending:
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {definition}'))
        if pending:
            # Old imports assigned every segment to page 1 without page metadata.
            # Preserve real references only when provenance actually carries pages.
            if 'documents' in existing:
                for row in conn.execute(text('SELECT id, provenance, raw_sha256 FROM documents')).mappings():
                    try:
                        provenance = json.loads(row['provenance'] or '{}')
                    except ValueError:
                        provenance = {}
                    if not provenance.get('pages'):
                        conn.execute(text("UPDATE segments SET page_ref='' WHERE document_id=:id AND page_ref='1'"), {'id': row['id']})
                    path = Path(provenance.get('raw_storage_path') or '__missing_snapshot__')
                    if path.is_file():
                        data = path.read_bytes()
                        if hashlib.sha256(data).hexdigest() == row['raw_sha256']:
                            conn.execute(text('UPDATE documents SET raw_bytes=:data WHERE id=:id AND raw_bytes IS NULL'),
                                         {'data': data, 'id': row['id']})
    Base.metadata.create_all(engine)
