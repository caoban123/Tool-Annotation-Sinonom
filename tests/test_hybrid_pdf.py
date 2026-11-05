import base64
import json
from pathlib import Path
import sys
import zlib

from PIL import Image
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, DecodedStreamObject, DictionaryObject

from Crawl.extractors.pdf_pages import text_quality, inspect_page, plan_input
from OCR.viet_runner import run


class RecordingOCR:
    info = dict(engine_type='test_contract', is_mock=False)

    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def recognize_image(self, image):
        self.calls += 1
        if self.fail:
            raise TimeoutError('scan timed out')
        return [dict(text='Trang quét: tiếng Việt có dấu.', confidence=.91, bbox=[0, 0, 40, 15])]


def mixed_document(tmp_path):
    native = PdfReader('tests/fixtures/sample_text.pdf').pages[0]
    scan_path = tmp_path / 'scan.pdf'
    Image.open('tests/fixtures/sample_viet_scan.png').convert('RGB').save(scan_path, 'PDF')
    writer = PdfWriter()
    for page in (native, PdfReader(scan_path).pages[0], native):
        writer.add_page(page)
    path = tmp_path / 'mixed.pdf'
    with path.open('wb') as stream:
        writer.write(stream)
    return path


def configuration(tmp_path, path):
    return dict(input_path=str(path), output_dir=str(tmp_path / 'output'), device='cpu')


def test_mixed_pages_routes_order_cache_and_forced_page(tmp_path):
    path = mixed_document(tmp_path)
    settings = configuration(tmp_path, path)
    plan = plan_input(settings)
    assert plan['text_pages'] == 2 and plan['ocr_pages'] == 1
    assert [p['method'] for p in plan['pages']] == ['pdf_text', 'ocr', 'pdf_text']
    engine = RecordingOCR()
    result = run(settings, engine)
    assert result['complete'] and engine.calls == 1
    assert result['method_counts'] == dict(pdf_text=2, ocr=1)
    assert result['engine_info']['engine_type'] == 'HybridPDF'
    assert [p['page_number'] for p in result['pages']] == [1, 2, 3]
    assert result['full_text'] == '\n\n'.join(p['text'] for p in result['pages'])
    assert result['pages'][0]['text'] == result['pages'][2]['text']
    assert 'tiếng Việt có dấu' in result['pages'][1]['text']
    resumed = run(settings, engine)
    assert engine.calls == 1 and all(p['is_cached'] for p in resumed['pages'])
    settings['force_ocr_pages'] = [3]
    forced = run(settings, engine)
    assert engine.calls == 2
    assert [p['is_cached'] for p in forced['pages']] == [True, True, False]
    assert forced['pages'][2]['method'] == 'ocr'


def test_scan_failure_keeps_later_text_and_resume(tmp_path):
    settings = configuration(tmp_path, mixed_document(tmp_path))
    engine = RecordingOCR(fail=True)
    result = run(settings, engine)
    assert not result['complete'] and result['errors'][0]['page_number'] == 2
    assert result['pages'][2]['method'] == 'pdf_text'
    assert result['text_file'] == 'viet.partial.txt'
    engine.fail = False
    result = run(settings, engine)
    assert result['complete'] and engine.calls == 2
    assert [p['is_cached'] for p in result['pages']] == [True, False, True]


def test_native_only_does_not_import_numpy_or_start_ocr(tmp_path, monkeypatch):
    settings = configuration(tmp_path, Path('tests/fixtures/sample_text.pdf'))
    monkeypatch.setitem(sys.modules, 'paddle', None)
    monkeypatch.setitem(sys.modules, 'paddleocr', None)
    monkeypatch.setitem(sys.modules, 'numpy', None)
    monkeypatch.setattr('OCR.viet_runner.WorkerEngine', lambda config: pytest.fail('unnecessary OCR'))
    result = run(settings)
    assert result['complete'] and result['method_counts']['ocr'] == 0
    assert 'Dat Nam Giao xua' in result['full_text']
    assert result['pages'][0]['boxes'] == []  # no invented line positions/confidence


def test_pdf_unicode_mapping_preserves_vietnamese_and_non_bmp(tmp_path):
    text = 'Tiếng Việt: Nguyễn, 𠀀.'
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=200)
    mappings = '\n'.join(f'<{i + 33:02X}> <{char.encode("utf-16-be").hex()}>'
                         for i, char in enumerate(text))
    cmap = DecodedStreamObject()
    cmap.set_data(('''/CIDInit /ProcSet findresource begin
12 dict begin begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /TestUnicode def /CMapType 2 def
1 begincodespacerange <00> <FF> endcodespacerange
''' + f'{len(text)} beginbfchar\n{mappings}\nendbfchar\n' +
        'endcmap CMapName currentdict /CMap defineresource pop end end').encode())
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica'),
                             NameObject('/ToUnicode'): writer._add_object(cmap)})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
        NameObject('/F1'): writer._add_object(font)})})
    content = DecodedStreamObject()
    codes = bytes(i + 33 for i in range(len(text))).hex()
    content.set_data(f'BT /F1 16 Tf 20 100 Td <{codes}> Tj ET'.encode())
    page[NameObject('/Contents')] = writer._add_object(content)
    path = tmp_path / 'unicode.pdf'
    with path.open('wb') as stream:
        writer.write(stream)
    result = run(configuration(tmp_path, path))
    assert result['full_text'] == text
    assert result['pages'][0]['method'] == 'pdf_text'


@pytest.mark.parametrize('text', ['Tiếng Việt đầy đủ dấu.', 'Bìa', 'Tiếng Việt', 'Lặp lại\nLặp lại'])
def test_unicode_and_short_cover_are_usable(text):
    assert text_quality(text)['usable']


@pytest.mark.parametrize('text', ['', '1', '\ufffd' * 30, '\ue001\ue002 text', '(cid:132) (cid:134)',
                                  'x' * 100, '1234 2353 3453', 'Tiáº¿ng Viá»‡t'])
def test_suspicious_text_requires_ocr(text):
    assert not text_quality(text)['usable']


@pytest.mark.parametrize('full_text_layer', [False, True])
def test_scan_with_selectable_header_still_needs_ocr(tmp_path, full_text_layer):
    path = mixed_document(tmp_path)
    reader = PdfReader(path)
    native = reader.pages[0]
    scan = reader.pages[1]
    scan[NameObject('/Resources')][NameObject('/Font')] = native['/Resources']['/Font']
    content = scan.get_contents().get_data()
    font = next(iter(native['/Resources']['/Font']))
    stream = DecodedStreamObject()
    if full_text_layer:
        lines = ['Digital text layer from a scanned book needs manual review.'] * 6
        body = ' T* '.join(f'({line}) Tj' for line in lines)
        layer = f'\nBT {font} 8 Tf 12 TL 20 {float(scan.mediabox.height) - 20} Td {body} ET'
    else:
        layer = f'\nBT {font} 12 Tf 20 20 Td (Header only) Tj ET'
    stream.set_data(content + layer.encode())
    scan[NameObject('/Contents')] = stream
    writer = PdfWriter()
    writer.add_page(scan)
    output = tmp_path / 'header-scan.pdf'
    with output.open('wb') as handle:
        writer.write(handle)
    inspection = inspect_page(output, 1)
    if full_text_layer:
        assert inspection['quality']['usable']
        assert inspection['quality']['warnings'] == ['image_backed_text_layer']
        result = run(configuration(tmp_path, output))
        assert result['complete'] and result['pages'][0]['needs_review']
        assert result['pages'][0]['method'] == 'pdf_text'
    else:
        assert 'Header only' in inspection['text']
        assert 'image_with_sparse_text' in inspection['quality']['reasons']
        assert plan_input(dict(input_path=str(output)))['ocr_pages'] == 1


def test_modes_ranges_and_selected_page_numbers(tmp_path):
    settings = configuration(tmp_path, mixed_document(tmp_path))
    settings.update(start_page=2, end_page=3)
    result = run(settings, RecordingOCR())
    assert [p['page_number'] for p in result['pages']] == [2, 3]
    assert plan_input(dict(settings, input_mode='ocr'))['ocr_pages'] == 2
    for invalid in (dict(input_mode='unknown'), dict(force_ocr_pages=[0]), dict(start_page=0), dict(end_page=9)):
        with pytest.raises(ValueError):
            plan_input(dict(settings, **invalid))
    text_only = run(dict(settings, input_mode='text'))
    assert not text_only['complete'] and text_only['pages'][0]['status'] == 'error'
    assert text_only['pages'][1]['method'] == 'pdf_text'


def test_crawl_bundle_has_current_sources_and_compiles():
    from scripts.build_viet_notebook import FILES
    notebook = json.loads(Path('Crawl/notebooks/01_Crawl_Text.ipynb').read_text(encoding='utf-8'))
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            compile(cell['source'], '<crawl-notebook>', 'exec')
    encoded = notebook['cells'][2]['source'].split("b64decode('")[1].split("')")[0]
    payload = json.loads(zlib.decompress(base64.b64decode(encoded)))
    assert set(payload) == set(FILES)
    for name, value in payload.items():
        assert base64.b64decode(value) == Path(name).read_bytes()
