import hashlib
import json
import uuid
import datetime
from sqlalchemy.orm import Session
from ..models import Document
from .versioning import record_revision

def compute_sha256(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def process_txt_bytes(
    db: Session,
    project_id: str,
    language: str,
    raw_bytes: bytes,
    filename: str = ""
) -> Document:
    """
    Decodes raw bytes into clean UTF-8 text.
    Handles UTF-8 BOM, normalizes newlines (\r\n and \r -> \n),
    calculates SHA-256 for both raw and cleaned text, records provenance.
    """
    raw_sha = compute_sha256(raw_bytes)

    # Check for UTF-8 BOM
    has_bom = raw_bytes.startswith(b'\xef\xbb\xbf')
    if has_bom:
        decoded_text = raw_bytes[3:].decode('utf-8', errors='replace')
    else:
        decoded_text = raw_bytes.decode('utf-8', errors='replace')

    # Normalize newlines
    normalized_text = decoded_text.replace('\r\n', '\n').replace('\r', '\n')
    clean_bytes = normalized_text.encode('utf-8')
    clean_sha = compute_sha256(clean_bytes)

    provenance = {
        "filename": filename,
        "raw_byte_size": len(raw_bytes),
        "clean_byte_size": len(clean_bytes),
        "has_utf8_bom": has_bom,
        "raw_sha256": raw_sha,
        "clean_sha256": clean_sha,
        "line_count": len(normalized_text.splitlines()),
        "imported_at": datetime.datetime.utcnow().isoformat()
    }

    doc_id = f"doc_{language}_{uuid.uuid4().hex[:8]}"

    # Deactivate or remove previous document for this language in project if re-importing
    old_doc = db.query(Document).filter(
        Document.project_id == project_id,
        Document.language == language
    ).first()
    if old_doc:
        db.delete(old_doc)
        db.flush()

    doc = Document(
        id=doc_id,
        project_id=project_id,
        language=language,
        raw_filename=filename,
        raw_sha256=raw_sha,
        clean_sha256=clean_sha,
        provenance=json.dumps(provenance, ensure_ascii=False),
        revision=1
    )
    db.add(doc)
    db.flush()

    record_revision(
        db,
        project_id=project_id,
        action="import_document",
        entity_type="Document",
        entity_id=doc_id,
        after_state=provenance
    )

    return doc
