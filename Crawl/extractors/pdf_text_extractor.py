import os
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pypdf

def extract_from_pdf_text(
    pdf_path: str,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None
) -> Dict[str, Any]:
    """
    Extracts selectable text directly from a digital PDF without OCR.
    Detects scanned image PDFs masquerading as digital text and advises switching to OCR.
    Preserves page boundaries and records provenance.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file PDF: {pdf_path}")

    reader = pypdf.PdfReader(str(path))
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("File PDF rỗng, không có trang nào.")

    s_page = max(0, (start_page - 1) if start_page else 0)
    e_page = min(total_pages, end_page if end_page else total_pages)

    page_texts = []
    total_extracted_chars = 0

    for p_num in range(s_page, e_page):
        page = reader.pages[p_num]
        raw_page_text = page.extract_text() or ""
        cleaned_page_text = "\n".join(
            line.strip() for line in raw_page_text.splitlines() if line.strip()
        )
        page_texts.append({
            "page_number": p_num + 1,
            "text": cleaned_page_text,
            "char_count": len(cleaned_page_text)
        })
        total_extracted_chars += len(cleaned_page_text)

    # Scanned detection threshold: if avg chars per page < 15, likely image scan
    num_processed = e_page - s_page
    avg_chars = total_extracted_chars / max(1, num_processed)

    if total_extracted_chars == 0 or avg_chars < 15:
        raise ValueError(
            f"PDF '{path.name}' không có lớp text số hóa hợp lệ (tổng số ký tự: {total_extracted_chars}). "
            f"Đây là PDF Scan (ảnh chụp). Vui lòng chuyển sang Module OCR để nhận dạng chữ."
        )

    full_text = "\n".join(p["text"] for p in page_texts if p["text"])

    provenance = {
        "source_file": str(path.resolve()),
        "total_pdf_pages": total_pages,
        "processed_range": [s_page + 1, e_page],
        "total_chars": total_extracted_chars,
        "extracted_at": datetime.datetime.utcnow().isoformat()
    }

    return {
        "text": full_text,
        "pages": page_texts,
        "provenance": provenance
    }
