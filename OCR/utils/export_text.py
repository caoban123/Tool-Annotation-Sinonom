import json
from pathlib import Path
from typing import Dict, Any

def export_ocr_result(
    ocr_result: Dict[str, Any],
    output_txt_path: Path,
    output_meta_path: Path
) -> None:
    """Exports OCR text to UTF-8 without BOM, and saves sidecar metadata JSON."""
    output_txt_path.parent.mkdir(parents=True, exist_ok=True)
    output_meta_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_txt_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(ocr_result["full_text"])

    with open(output_meta_path, "w", encoding="utf-8") as f:
        json.dump(ocr_result, f, ensure_ascii=False, indent=2)
