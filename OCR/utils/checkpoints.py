import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("OCRCheckpointManager")

# Chuỗi giả lập mock cần cấm lưu và cấm nạp
KNOWN_MOCK_STRINGS = {
    "古南交，周號越裳。",
    "Dat Nam Giao xua, nha Chu goi la Viet Thuong."
}

class OCRCheckpointManager:
    """
    Manages OCR page checkpoints with strict integrity validation.
    Prevents caching of mock data, errors, or corrupted results.
    """
    def __init__(self, cache_dir: str = "data/ocr_checkpoints", allow_mock: bool = False):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.allow_mock = allow_mock

    def compute_page_key(
        self,
        source_id: str,
        page_num: int,
        model_name: str,
        config_hash: str = ""
    ) -> str:
        """Computes deterministic hash key based on source, page, model and optional config."""
        h = hashlib.sha256()
        key_str = f"{source_id}:{page_num}:{model_name}"
        if config_hash:
            key_str += f":{config_hash}"
        h.update(key_str.encode("utf-8"))
        return h.hexdigest()[:16]

    def is_valid_result(self, data: Dict[str, Any]) -> bool:
        """
        Validates if checkpoint data originates from genuine OCR inference.
        Returns False if data contains mock markers, error status, or known mock strings,
        unless allow_mock is explicitly enabled for unit testing.
        """
        if not isinstance(data, dict):
            return False

        if not self.allow_mock:
            # 1. Reject if marked as mock or error
            if data.get("is_mock", False) is True:
                return False
            if data.get("status") == "error" or "error" in data:
                return False

            # 2. Reject mock engine signatures
            engine_type = str(data.get("engine_type", "")).lower()
            if "cpu_test_adapter" in engine_type or "mock" in engine_type:
                return False

            # 3. Reject known placeholder strings
            text = str(data.get("text", "")).strip()
            if text in KNOWN_MOCK_STRINGS:
                return False

            # Check boxes text
            boxes = data.get("boxes", [])
            if boxes and isinstance(boxes, list):
                first_box_text = str(boxes[0].get("text", "")).strip() if isinstance(boxes[0], dict) else ""
                if first_box_text in KNOWN_MOCK_STRINGS:
                    return False

        return True

    def get_cached_result(self, page_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached result only if it passes strict integrity checks.
        Automatically removes invalid or mock cached files.
        """
        path = self.cache_dir / f"{page_key}.json"
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not self.is_valid_result(data):
                # Isolate / remove corrupted mock file
                try:
                    path.unlink()
                except Exception:
                    pass
                return None

            return data
        except Exception:
            return None

    def save_cached_result(self, page_key: str, data: Dict[str, Any]) -> bool:
        """
        Saves OCR result only if it passes strict integrity validation.
        Refuses to save mock, error, or placeholder results.
        """
        if not self.is_valid_result(data):
            logger.warning(f"[Checkpoint] Từ chối lưu kết quả không hợp lệ hoặc dữ liệu mock (key={page_key})")
            return False

        path = self.cache_dir / f"{page_key}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"[Checkpoint] Lỗi ghi file checkpoint: {e}")
            return False

    def purge_invalid_checkpoints(self) -> int:
        """
        Scans all files in cache_dir and deletes any checkpoint containing mock or corrupted data.
        Returns the number of purged files.
        """
        purged = 0
        if not self.cache_dir.exists():
            return 0

        for file_path in self.cache_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not self.is_valid_result(data):
                    file_path.unlink()
                    purged += 1
            except Exception:
                try:
                    file_path.unlink()
                    purged += 1
                except Exception:
                    pass
        return purged
