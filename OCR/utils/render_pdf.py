import io
import sys
import subprocess
from pathlib import Path
from typing import List, Optional
from PIL import Image

try:
    import pypdfium2 as pdfium
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pypdfium2"], check=False)
    import pypdfium2 as pdfium

def render_pdf_to_images(
    pdf_path: str,
    start_page: int = 1,
    end_page: Optional[int] = None,
    max_pages: Optional[int] = None,
    scale: float = 2.0 # 2.0 corresponds to ~144 DPI, suitable balance for OCR
) -> List[Image.Image]:
    """
    Renders pages of a PDF document to PIL Images using pypdfium2.
    Supports start_page (1-based), end_page, or max_pages.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file PDF: {pdf_path}")

    pdf = pdfium.PdfDocument(str(path))
    total_pages = len(pdf)

    # Compute 0-based range
    s_idx = max(0, start_page - 1)
    if end_page is not None:
        e_idx = min(total_pages, end_page)
    elif max_pages is not None:
        e_idx = min(total_pages, s_idx + max_pages)
    else:
        e_idx = total_pages

    images = []
    for i in range(s_idx, e_idx):
        page = pdf[i]
        # Render page to bitmap
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        images.append(pil_image)

    return images
