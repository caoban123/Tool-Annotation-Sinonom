"""
Standardized ID & Provenance Generator.
Generates unique, deterministic, and contract-compliant identifiers
for Projects, Tasks, Documents, Segments, and Sidecar metadata.
"""

import hashlib
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List

def compute_sha256(file_path_or_bytes) -> str:
    """Computes SHA-256 hex digest of a file path or raw bytes."""
    h = hashlib.sha256()
    if isinstance(file_path_or_bytes, (str, Path)):
        p = Path(file_path_or_bytes)
        if not p.exists():
            return ""
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
    elif isinstance(file_path_or_bytes, bytes):
        h.update(file_path_or_bytes)
    else:
        h.update(str(file_path_or_bytes).encode("utf-8"))
    return h.hexdigest()

def generate_project_id(ma_de_tai: str, ma_tac_pham: str) -> str:
    """Generates standardized project ID."""
    clean_de_tai = ma_de_tai.strip().replace(" ", "_")
    clean_tac_pham = ma_tac_pham.strip().replace(" ", "_")
    return f"proj_{clean_de_tai}_{clean_tac_pham}"

def generate_document_id(ma_tac_pham: str, language: str, source_sha256: str = "") -> str:
    """Generates standardized document ID."""
    short_hash = source_sha256[:8] if source_sha256 else uuid.uuid4().hex[:8]
    return f"doc_{ma_tac_pham}_{language}_{short_hash}"

def generate_segment_id(language: str, order_index: int, text: str = "") -> str:
    """Generates standardized segment ID."""
    short_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:4] if text else uuid.uuid4().hex[:4]
    return f"seg_{language}_{order_index+1:04d}_{short_hash}"

def build_sidecar_metadata(
    ma_de_tai: str,
    ma_tac_pham: str,
    tac_pham_name: str,
    language: str,
    source_file_path: str,
    total_segments: int,
    total_characters: int,
    extractor_type: str, # 'pdf_text_stream', 'ocr_han_paddle', 'ocr_viet_vietocr'
    hardware: str = "cpu"
) -> Dict[str, Any]:
    """
    Constructs standardized sidecar JSON metadata matching Section 3.4 of plan.md.
    """
    source_path = Path(source_file_path) if source_file_path else None
    sha256_hash = compute_sha256(source_path) if source_path and source_path.exists() else ""

    return {
        "metadata_version": "1.0",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "ma_de_tai": ma_de_tai,
        "ma_tac_pham": ma_tac_pham,
        "tac_pham_name": tac_pham_name,
        "language": language,
        "source": {
            "filename": source_path.name if source_path else "unknown",
            "path": str(source_path) if source_path else "",
            "sha256": sha256_hash,
            "size_bytes": source_path.stat().st_size if source_path and source_path.exists() else 0
        },
        "extraction": {
            "extractor_type": extractor_type,
            "hardware": hardware,
            "total_segments": total_segments,
            "total_characters": total_characters
        }
    }
