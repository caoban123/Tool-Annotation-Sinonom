"""
Automated PDF Type Detector (PDF Text vs PDF Scan).
Inspects internal PDF streams to reliably differentiate between:
- PDF_TEXT: Digitized PDF with an existing selectable text layer.
- PDF_SCAN: Scanned image document requiring OCR image recognition.
"""

from pathlib import Path
from typing import Dict, Any
import pypdf

def inspect_pdf(pdf_path: str, sample_pages: int = 5) -> Dict[str, Any]:
    """
    Analyzes a PDF file to automatically classify it as PDF_TEXT or PDF_SCAN.
    
    Returns:
        dict with keys:
        - pdf_type: 'PDF_TEXT' | 'PDF_SCAN'
        - total_pages: int
        - sample_pages_count: int
        - total_sampled_chars: int
        - avg_chars_per_page: float
        - is_selectable_text: bool
        - recommended_engine: 'extract_from_pdf_text' | 'ocr_pipeline'
        - preview_snippet: str
        - reason: str
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file PDF: {pdf_path}")

    try:
        reader = pypdf.PdfReader(str(path))
        total_pages = len(reader.pages)
        if total_pages == 0:
            return {
                "pdf_type": "PDF_SCAN",
                "total_pages": 0,
                "sample_pages_count": 0,
                "total_sampled_chars": 0,
                "avg_chars_per_page": 0.0,
                "is_selectable_text": False,
                "recommended_engine": "ocr_pipeline",
                "preview_snippet": "",
                "reason": "File PDF không chứa trang nào."
            }

        num_sample = min(sample_pages, total_pages)
        extracted_samples = []
        for i in range(num_sample):
            try:
                page_text = reader.pages[i].extract_text() or ""
                extracted_samples.append(page_text.strip())
            except Exception:
                extracted_samples.append("")

        total_sampled_chars = sum(len(t) for t in extracted_samples)
        avg_chars = total_sampled_chars / max(1, num_sample)

        # Threshold criteria:
        # A true digitized text page typically has hundreds of characters.
        # Scanned documents have 0 characters (or occasional 1-5 artifact chars).
        is_pdf_text = (avg_chars >= 35.0) or (total_sampled_chars >= 150)

        all_text = " ".join(extracted_samples).strip()
        preview_snippet = (all_text[:120] + "...") if len(all_text) > 120 else all_text

        if is_pdf_text:
            pdf_type = "PDF_TEXT"
            recommended_engine = "extract_from_pdf_text"
            reason = (
                f"Phát hiện có lớp text số hóa sẵn (trung bình {avg_chars:.1f} ký tự/trang). "
                f"Có thể bóc tách trực tiếp cực nhanh trong vài giây mà không cần chạy GPU OCR."
            )
        else:
            pdf_type = "PDF_SCAN"
            recommended_engine = "ocr_pipeline"
            reason = (
                f"Không tìm thấy lớp text số hóa (chỉ có {total_sampled_chars} ký tự/trang mẫu). "
                f"Đây là bản scan ảnh chụp, cần chạy Module OCR để nhận dạng chữ."
            )

        return {
            "pdf_type": pdf_type,
            "total_pages": total_pages,
            "sample_pages_count": num_sample,
            "total_sampled_chars": total_sampled_chars,
            "avg_chars_per_page": round(avg_chars, 1),
            "is_selectable_text": is_pdf_text,
            "recommended_engine": recommended_engine,
            "preview_snippet": preview_snippet,
            "reason": reason
        }

    except Exception as e:
        return {
            "pdf_type": "PDF_SCAN",
            "total_pages": 0,
            "sample_pages_count": 0,
            "total_sampled_chars": 0,
            "avg_chars_per_page": 0.0,
            "is_selectable_text": False,
            "recommended_engine": "ocr_pipeline",
            "preview_snippet": "",
            "reason": f"Không thể đọc text stream của PDF ({str(e)}). Mặc định chuyển sang OCR."
        }
