"""
Data loading and catalog helper utilities for OCR pipeline.
"""
from pathlib import Path
from typing import Dict, Any, Optional

from .pdf_detector import inspect_pdf

try:
    from Crawl.utils.catalog import get_works_catalog, resolve_work, ensure_data_source
except ImportError:
    import json
    def get_works_catalog() -> Dict[str, Dict[str, Any]]:
        cat_file = Path("data/works_catalog.json")
        if cat_file.exists():
            with open(cat_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def resolve_work(work_key: str, base_dir: str = "data/source_materials") -> Dict[str, Any]:
        catalog = get_works_catalog()
        info = catalog.get(work_key, {})
        han_rel = info.get("han_relpath", "")
        han_abs = str(Path(base_dir) / han_rel) if han_rel else ""
        info["han_abs_path"] = han_abs
        return info

    def ensure_data_source() -> bool:
        return True

__all__ = ["inspect_pdf", "get_works_catalog", "resolve_work", "ensure_data_source"]
