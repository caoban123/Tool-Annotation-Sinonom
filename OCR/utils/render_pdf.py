"""Render bounded PDF ranges and release native PDFium resources promptly."""
from pathlib import Path


def render_pdf_to_images(pdf_path, start_page=1, end_page=None, max_pages=None, scale=2.0):
    import pypdfium2 as pdfium
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f'Khong tim thay PDF: {pdf_path}')
    if scale <= 0 or start_page < 1 or (max_pages is not None and max_pages < 1):
        raise ValueError('scale, start_page va max_pages phai lon hon 0')
    images = []
    with pdfium.PdfDocument(str(path)) as pdf:
        end = len(pdf) if end_page is None else end_page
        if not start_page <= end <= len(pdf):
            raise ValueError(f'Khoang trang phai thuoc 1..{len(pdf)}')
        if max_pages is not None:
            end = min(end, start_page + max_pages - 1)
        for index in range(start_page - 1, end):
            page = pdf[index]
            try:
                bitmap = page.render(scale=scale)
                try:
                    images.append(bitmap.to_pil().copy())
                finally:
                    bitmap.close()
            finally:
                page.close()
    return images
