import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any

class OCRCheckpointManager:
    def __init__(self, cache_dir: str = "data/ocr_checkpoints"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def compute_page_key(self, source_id: str, page_num: int, model_name: str) -> str:
        h = hashlib.sha256()
        h.update(f"{source_id}:{page_num}:{model_name}".encode("utf-8"))
        return h.hexdigest()[:16]

    def get_cached_result(self, page_key: str) -> Optional[Dict[str, Any]]:
        path = self.cache_dir / f"{page_key}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def save_cached_result(self, page_key: str, data: Dict[str, Any]) -> None:
        path = self.cache_dir / f"{page_key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
