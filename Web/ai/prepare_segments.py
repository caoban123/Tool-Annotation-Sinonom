import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

def load_segments_manifest(filepath: str) -> Dict[str, Any]:
    """Loads and validates segments JSON/JSONL exported from Web Studio."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file segments: {filepath}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "segments" not in data or "source_sha256_han" not in data:
        raise ValueError("File segments không đúng schema chuẩn của Web Studio.")

    return data

def split_han_viet_segments(manifest: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Separates active segments into Han and Viet lists sorted by order_index."""
    segs = manifest.get("segments", [])
    han_segs = sorted([s for s in segs if s.get("language") == "han" and s.get("active", True)], key=lambda x: x["order_index"])
    viet_segs = sorted([s for s in segs if s.get("language") == "viet" and s.get("active", True)], key=lambda x: x["order_index"])
    return han_segs, viet_segs
