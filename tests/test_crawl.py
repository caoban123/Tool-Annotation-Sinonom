import pytest
from pathlib import Path
from Crawl.extractors.html_extractor import extract_from_html
from Crawl.extractors.pdf_text_extractor import extract_from_pdf_text

def test_extract_from_html_local_fixture():
    fixtures_dir = Path(__file__).parent / "fixtures"
    html_path = fixtures_dir / "sample.html"

    res = extract_from_html(str(html_path))
    assert "Khảo Cứu Địa Chí Cổ" in res["text"]
    assert "Đất Nam Giao xưa" in res["text"]
    # Check that navigation links and footer copyright are stripped
    assert "Trang chủ" not in res["text"]
    assert "Bản quyền tài liệu" not in res["text"]
    assert res["provenance"]["char_count"] > 0

def test_extract_from_pdf_text_fixture():
    fixtures_dir = Path(__file__).parent / "fixtures"
    pdf_path = fixtures_dir / "sample_text.pdf"

    res = extract_from_pdf_text(str(pdf_path))
    assert "Dat Nam Giao xua" in res["text"]
    assert "quan Tuong" in res["text"]
    assert res["provenance"]["total_chars"] > 0

def test_pdf_scanned_detection(tmp_path):
    # Create an empty or scan-like PDF with no text stream
    scan_pdf = tmp_path / "fake_scan.pdf"
    content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer << /Size 4 /Root 1 0 R >>
startxref
185
%%EOF
"""
    with open(scan_pdf, "wb") as f:
        f.write(content)

    with pytest.raises(ValueError, match="Module OCR"):
        extract_from_pdf_text(str(scan_pdf))

def test_missing_files_error():
    with pytest.raises(FileNotFoundError):
        extract_from_html("non_existent_file.html")
    with pytest.raises(FileNotFoundError):
        extract_from_pdf_text("non_existent_file.pdf")
