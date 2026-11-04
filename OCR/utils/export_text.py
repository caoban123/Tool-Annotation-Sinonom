import json
from pathlib import Path
from typing import Dict, Any

from .checkpoints import KNOWN_MOCK_STRINGS

def validate_ocr_output(ocr_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates OCR output authenticity and integrity before allowing text export.
    Raises ValueError if results contain mock data, error status, or placeholder text.
    """
    if not isinstance(ocr_result, dict):
        raise ValueError("Kết quả OCR không đúng định dạng dictionary.")
    if ocr_result.get('complete') is False or ocr_result.get('errors'):
        raise ValueError('Kết quả OCR chưa đầy đủ; chỉ được xuất bản partial kèm báo cáo lỗi.')

    engine_info = ocr_result.get("engine_info", {})
    if engine_info.get("is_mock", False):
        raise ValueError("Phát hiện kết quả từ Mock Adapter. Không cho phép xuất file dữ liệu giả!")

    engine_type = str(engine_info.get("engine_type", "")).lower()
    if "cpu_test_adapter" in engine_type or "mock" in engine_type:
        raise ValueError(f"Engine type '{engine_type}' là giả lập mock. Từ chối xuất dữ liệu.")

    pages = ocr_result.get("pages", [])
    if not pages:
        raise ValueError("Kết quả OCR không chứa trang nào.")

    # Check for placeholder strings in any page
    for p in pages:
        text = str(p.get("text", "")).strip()
        if text in KNOWN_MOCK_STRINGS:
            raise ValueError(f"Trang {p.get('page_number')} chứa chuỗi văn bản mẫu giả lập '{text}'.")

    full_text = str(ocr_result.get("full_text", ""))
    total_chars = len(full_text)
    total_pages = len(pages)
    blank_pages = sum(1 for p in pages if len(str(p.get("text", "")).strip()) == 0)

    stats = {
        "total_pages": total_pages,
        "blank_pages": blank_pages,
        "active_pages": total_pages - blank_pages,
        "total_characters": total_chars,
        "is_valid": True,
        "model_name": engine_info.get("model_name", "unknown")
    }
    return stats

def export_ocr_result(
    ocr_result: Dict[str, Any],
    output_txt_path: Path,
    output_meta_path: Path
) -> Dict[str, Any]:
    """
    Validates and exports OCR text to UTF-8 without BOM, with sidecar metadata JSON.
    """
    stats = validate_ocr_output(ocr_result)

    output_txt_path = Path(output_txt_path)
    output_meta_path = Path(output_meta_path)
    output_txt_path.parent.mkdir(parents=True, exist_ok=True)
    output_meta_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_txt_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(ocr_result.get("full_text", ""))

    with open(output_meta_path, "w", encoding="utf-8") as f:
        json.dump(ocr_result, f, ensure_ascii=False, indent=2)

    return stats
