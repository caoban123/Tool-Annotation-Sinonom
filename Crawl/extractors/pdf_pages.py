"""Page-level PDF routing. Text quality checks are heuristics, not proofreading."""
from collections import Counter
from contextlib import nullcontext
from pathlib import Path
import re
import unicodedata

ROUTING_VERSION = 1


def text_quality(text):
    visible = [char for char in text if not char.isspace()]
    reasons = []
    if not visible:
        return dict(usable=False, reasons=['no_text'], visible_chars=0)
    bad = sum(char == '\ufffd' or unicodedata.category(char) in ('Co', 'Cs', 'Cn', 'Cc')
              for char in visible)
    letters = sum(unicodedata.category(char).startswith('L') for char in visible)
    if bad:
        reasons.append('invalid_unicode')
    if re.search(r'\(cid:\d+\)', text, re.I):
        reasons.append('unmapped_cid')
    if letters < 2:
        reasons.append('too_little_text')
    if len(visible) >= 20 and letters / len(visible) < .45:
        reasons.append('mostly_nonletters')
    if len(visible) >= 30 and Counter(visible).most_common(1)[0][1] / len(visible) > .5:
        reasons.append('repeated_glyphs')
    if re.search(r'(?:Ã.|Â.|á[º»]|â[€™])', text):
        reasons.append('possible_mojibake')
    return dict(usable=not reasons, reasons=reasons, visible_chars=len(visible),
                letter_chars=letters, invalid_chars=bad)


def inspect_page(path, number, document=None):
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw
    context = pdfium.PdfDocument(str(path)) if document is None else nullcontext(document)
    with context as document:
        page = document[number - 1]
        try:
            textpage = page.get_textpage()
            try:
                # PDFium decodes ToUnicode mappings; do not strip accents, repeated
                # lines or normalize words. Bounded extraction supports full Unicode.
                text = textpage.get_text_bounded(errors='replace')
            finally:
                textpage.close()
            text = text.replace('\r\n', '\n').replace('\r', '\n').strip()
            width, height = page.get_size()
            largest_image = 0.0
            for obj in page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE]):
                left, bottom, right, top = obj.get_bounds()
                area = max(0, min(width, right) - max(0, left)) * max(0, min(height, top) - max(0, bottom))
                largest_image = max(largest_image, area / max(1, width * height))
            quality = text_quality(text)
            quality['largest_image_coverage'] = round(largest_image, 4)
            quality['warnings'] = ['image_backed_text_layer'] if largest_image >= .65 and text else []
            # A scanned body with only a selectable header/page number is not a
            # usable digital page. Prefer OCR rather than losing the image body.
            if largest_image >= .25 and quality.get('letter_chars', 0) < 150:
                quality['reasons'].append('image_with_sparse_text')
                quality['usable'] = False
            return dict(text=text, quality=quality)
        finally:
            page.close()


def route_page(path, number, mode='auto', force_ocr_pages=(), document=None):
    if mode == 'ocr' or number in force_ocr_pages or Path(path).suffix.lower() != '.pdf':
        return dict(method='ocr', reason='forced_ocr' if mode == 'ocr' or number in force_ocr_pages else 'image_input',
                    text='', quality=None)
    try:
        inspection = inspect_page(path, number, document)
    except Exception as error:
        if mode == 'text':
            raise
        return dict(method='ocr', reason='text_extraction_failed', text='', quality=None,
                    extraction_error=str(error))
    method = 'pdf_text' if mode == 'text' or inspection['quality']['usable'] else 'ocr'
    return dict(method=method, reason='forced_text' if mode == 'text' else
                'usable_text' if method == 'pdf_text' else 'text_quality_check_failed', **inspection)


def plan_input(config):
    """Preflight without Paddle, so digital PDFs do not install/download OCR."""
    from OCR.viet_runner import page_count
    path = Path(config['input_path']).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    count = page_count(path)
    start, end = config.get('start_page', 1), config.get('end_page')
    end = count if end is None else end
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= count:
        raise ValueError(f'Invalid page range {start}..{end}; document has {count} pages')
    mode = config.get('input_mode', 'auto')
    if mode not in ('auto', 'ocr', 'text'):
        raise ValueError('input_mode must be auto, ocr or text')
    forced = config.get('force_ocr_pages', [])
    if not isinstance(forced, list) or any(type(n) is not int or not 1 <= n <= count for n in forced):
        raise ValueError('force_ocr_pages must be a list of original page numbers')
    if mode == 'text' and path.suffix.lower() != '.pdf':
        raise ValueError('Text extraction mode requires PDF input')
    import pypdfium2 as pdfium
    context = pdfium.PdfDocument(str(path)) if path.suffix.lower() == '.pdf' and mode != 'ocr' else nullcontext(None)
    pages = []
    with context as document:
        for number in range(start, end + 1):
            route = route_page(path, number, mode, forced, document)
            pages.append(dict(page_number=number, method=route['method'], reason=route['reason']))
    return dict(total_pdf_pages=count, total_pages=len(pages), pages=pages,
                text_pages=sum(p['method'] == 'pdf_text' for p in pages),
                ocr_pages=sum(p['method'] == 'ocr' for p in pages))
