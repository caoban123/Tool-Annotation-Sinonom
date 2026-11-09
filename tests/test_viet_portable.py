import base64
import json
from pathlib import Path
import sys
import types
import zipfile

import numpy as np
from PIL import Image
import pytest

from OCR.viet_runner import run, WorkerEngine
from OCR.utils.viet_engine import VietnameseOCREngine, parse_prediction


class ContractEngine:
    info = dict(engine_type='contract_test', is_mock=False, device='cpu')

    def __init__(self, fail_at=None):
        self.calls = 0
        self.fail_at = fail_at

    def recognize_image(self, image):
        self.calls += 1
        if self.calls == self.fail_at:
            raise RuntimeError('native inference failed')
        return [dict(text='Tiếng Việt: Nguyễn, 123.', confidence=.92, bbox=[0, 0, 20, 10]),
                dict(text='Tiếng Việt: Nguyễn, 123.', confidence=.4, bbox=[0, 11, 20, 21])]


def config(tmp_path):
    path = tmp_path / 'input.tiff'
    Image.new('RGB', (40, 50), 'white').save(path, save_all=True,
        append_images=[Image.new('RGB', (40, 50), 'black'), Image.new('RGB', (40, 50), 'red')])
    return dict(input_path=str(path), start_page=2, end_page=3, device='cpu',
                output_dir=str(tmp_path / 'output'))


def test_pages_unicode_duplicates_zip_resume_and_identity(tmp_path):
    settings = config(tmp_path)
    engine = ContractEngine()
    result = run(settings, engine)
    assert result['complete'] and result['needs_review']
    assert [p['page_number'] for p in result['pages']] == [2, 3]
    assert result['pages'][0]['low_confidence_lines'] == [1]
    assert result['full_text'].count('Tiếng Việt: Nguyễn, 123.') == 4
    out = Path(settings['output_dir'])
    assert not (out / 'viet.partial.txt').exists()
    with zipfile.ZipFile(out / 'viet_ocr.zip') as archive:
        assert archive.read('viet.txt').decode() == result['full_text']
        assert len([n for n in archive.namelist() if n.startswith('checkpoints/')]) == 2
    resumed = run(settings, engine)
    assert engine.calls == 2
    assert all(p['is_cached'] for p in resumed['pages'])
    # Review threshold does not require inference again.
    settings['review_score'] = .1
    assert not run(settings, engine)['needs_review']
    assert engine.calls == 2
    # Recognition/rendering settings must invalidate cache.
    settings['det_limit_side_len'] = 1920
    run(settings, engine)
    assert engine.calls == 4
    Image.new('RGB', (40, 50), 'blue').save(settings['input_path'], save_all=True,
        append_images=[Image.new('RGB', (40, 50), 'green')] * 2)
    run(settings, engine)
    assert engine.calls == 6


def test_failed_page_never_cached_or_exported_as_complete(tmp_path):
    settings = config(tmp_path)
    engine = ContractEngine(fail_at=1)
    result = run(settings, engine)
    assert not result['complete']
    assert result['errors'][0]['page_number'] == 2
    assert result['pages'][1]['status'] == 'complete'
    out = Path(settings['output_dir'])
    assert not (out / 'viet.txt').exists()
    assert len(list((out / 'checkpoints').glob('*.json'))) == 1
    with zipfile.ZipFile(out / 'viet_ocr.zip') as archive:
        assert 'viet.partial.txt' in archive.namelist()
        assert 'viet.txt' not in archive.namelist()
    engine.fail_at = None
    recovered = run(settings, engine)
    assert recovered['complete']
    assert not recovered['pages'][0]['is_cached'] and recovered['pages'][1]['is_cached']
    assert engine.calls == 3


def test_reverse_pages_exports_in_order_and_reuses_forward_cache(tmp_path, monkeypatch):
    import OCR.viet_runner as runner
    settings = config(tmp_path)
    settings['reverse_pages'] = True
    loaded = []
    load = runner.load_page
    def record(path, number, scale):
        loaded.append(number)
        return load(path, number, scale)
    monkeypatch.setattr(runner, 'load_page', record)
    engine = ContractEngine()
    reverse = run(settings, engine)
    assert loaded == [3, 2]
    assert reverse['reverse_pages'] is True
    assert [p['page_number'] for p in reverse['pages']] == [3, 2]
    calls = engine.calls
    settings['reverse_pages'] = False
    forward = run(settings, engine)
    assert engine.calls == calls and loaded == [3, 2]
    assert all(p['is_cached'] for p in forward['pages'])
    assert [p['page_number'] for p in forward['pages']] == [2, 3]
    settings['reverse_pages'] = True
    resumed = run(settings, engine)
    with zipfile.ZipFile(Path(settings['output_dir']) / 'viet_ocr.zip') as archive:
        assert archive.read('viet.txt').decode() == resumed['full_text'] == reverse['full_text']
        assert [p['page_number'] for p in json.loads(archive.read('viet_metadata.json'))['pages']] == [3, 2]


def test_bad_ranges_and_missing_files_fail_before_model(tmp_path):
    settings = config(tmp_path)
    settings['start_page'] = 4
    with pytest.raises(ValueError, match='page range'):
        run(settings)
    settings['input_path'] = str(tmp_path / 'absent.pdf')
    with pytest.raises(FileNotFoundError):
        run(settings)


def test_parser_validates_modern_api_and_preserves_scores():
    polygon = [[1, 2], [20, 2], [20, 10], [1, 10]]
    prediction = dict(rec_texts=['Việt', 'Việt'], rec_scores=np.array([.95, .1]),
                      rec_polys=np.array([polygon, polygon]))
    boxes = parse_prediction([prediction])
    assert len(boxes) == 2 and boxes[1]['confidence'] == .1
    assert boxes[0]['bbox'] == [1, 2, 20, 10]
    assert parse_prediction([dict(rec_texts=[], rec_scores=[], rec_polys=[])]) == []
    for bad in ([], [dict(rec_texts=[])], [dict(prediction, rec_scores=[])],
                [dict(prediction, rec_scores=[float('nan'), .1])]):
        with pytest.raises((ValueError, KeyError)):
            parse_prediction(bad)


def test_engine_explicit_device_batch_bgr_and_no_api_fallback(monkeypatch):
    captured = {}

    class Tensor:
        def __matmul__(self, other):
            return self

        def numpy(self):
            return np.ones((2, 2))

    paddle = types.SimpleNamespace(__version__='3.2.2', set_device=lambda d: captured.update(device=d),
        ones=lambda shape: Tensor(), is_compiled_with_cuda=lambda: True,
        device=types.SimpleNamespace(cuda=types.SimpleNamespace(device_count=lambda: 1)))

    class PaddleOCR:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def predict(self, image):
            assert image[0, 0].tolist() == [30, 20, 10]
            return [dict(rec_texts=[], rec_scores=[], rec_polys=[])]

    monkeypatch.setitem(sys.modules, 'paddle', paddle)
    monkeypatch.setitem(sys.modules, 'paddleocr', types.SimpleNamespace(PaddleOCR=PaddleOCR))
    engine = VietnameseOCREngine(dict(device='gpu:0', rec_batch_size=8))
    assert engine.recognize_image(Image.new('RGB', (10, 10), (10, 20, 30))) == []
    assert captured['device'] == 'gpu:0'
    assert captured['text_recognition_batch_size'] == 8
    assert captured['text_recognition_model_name'] == 'PP-OCRv6_small_rec'
    assert captured['text_rec_score_thresh'] == 0
    paddle.is_compiled_with_cuda = lambda: False
    with pytest.raises(RuntimeError, match='unavailable'):
        VietnameseOCREngine(dict(device='gpu:0'))


def test_worker_timeout_terminates_native_process():
    import multiprocessing as mp
    import time
    context = mp.get_context('spawn')
    worker = object.__new__(WorkerEngine)
    worker.connection, child = context.Pipe()
    worker.process = context.Process(target=time.sleep, args=(30,))
    worker.process.start()
    try:
        with pytest.raises(TimeoutError):
            worker.receive(.05, 'ok')
        assert not worker.process.is_alive()
    finally:
        child.close()
        if worker.process.is_alive():
            worker.close()


def test_corrupt_checkpoint_and_force_reprocess(tmp_path):
    settings = config(tmp_path)
    engine = ContractEngine()
    run(settings, engine)
    path = next((Path(settings['output_dir']) / 'checkpoints').glob('*.json'))
    page = json.loads(path.read_text(encoding='utf-8'))
    page['text'] = 'corrupted'
    path.write_text(json.dumps(page), encoding='utf-8')
    assert 'corrupted' not in run(settings, engine)['full_text']
    assert engine.calls == 3
    settings['force_reprocess'] = True
    run(settings, engine)
    assert engine.calls == 5


def test_bundle_matches_current_sources_and_cells_compile():
    from scripts.build_viet_notebook import FILES
    import zlib
    notebook = json.loads(Path('OCR/notebooks/02_OCR_Viet.ipynb').read_text(encoding='utf-8'))
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            compile(''.join(cell['source']), '<notebook>', 'exec')
    source = ''.join(notebook['cells'][2]['source'])
    encoded = source.split("b64decode('")[1].split("')")[0]
    payload = json.loads(zlib.decompress(base64.b64decode(encoded)))
    assert set(payload) == set(FILES)
    for name, data in payload.items():
        assert base64.b64decode(data) == Path(name).read_bytes()
