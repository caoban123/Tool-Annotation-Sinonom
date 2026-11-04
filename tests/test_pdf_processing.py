import pytest
from pathlib import Path
from OCR.utils.render_pdf import render_pdf_to_images

def test_render_pdf_page_range():
    # Use real historical PDF from source materials
    base_dir = Path("data/source_materials")
    candidates = list(base_dir.rglob("*.pdf"))
    if not candidates:
        pytest.skip("Chưa có file PDF trong data/source_materials")

    test_pdf = str(candidates[0])
    
    # Render exactly 2 pages: start_page=1, end_page=2
    images = render_pdf_to_images(test_pdf, start_page=1, end_page=2, scale=1.0)
    assert len(images) == 2
    assert images[0].size[0] > 100
    assert images[0].size[1] > 100

def test_render_pdf_not_found():
    with pytest.raises(FileNotFoundError):
        render_pdf_to_images("non_existent_file.pdf")
