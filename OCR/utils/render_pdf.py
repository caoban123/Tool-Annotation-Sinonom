import io
from pathlib import Path
from typing import List, Optional
from PIL import Image
import pypdfium2 as pdfium

def render_pdf_to_images(
    pdf_path: str,
    max_pages: Optional[int] = None,
    scale: float = 2.0 # 2.0 corresponds to ~144 DPI, suitable balance for OCR
) -> List[Image.Image]:
    """
    Renders pages of a PDF document to PIL Images using pypdfium2.
    Safe memory management and DPI bounding.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file PDF: {pdf_path}")

    pdf = pdfium.PdfDocument(str(path))
    total_pages = len(pdf)
    num_pages = min(total_pages, max_pages) if max_pages else total_pages

    images = []
    for i in range(num_pages):
        page = pdf[i]
        # Render page to bitmap
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        images.append(pil_image)

    return images
