"""Hybrid OCR boundaries: real crop geometry, reader IPC and independent cache."""
import json
import os
import subprocess
import sys
import types

import numpy as np
from PIL import Image
import pytest

from OCR.utils.vietocr_engine import PaddleVietOCREngine, line_crops
from OCR.viet_runner import run


def test_crops_reading_order_geometry_and_repeated_lines():
    pytest.importorskip('cv2')
    image = Image.new('RGB', (120, 80), (10, 20, 30))
    polygons = [[[5, 45], [80, 45], [80, 65], [5, 65]],
                [[65, 7], [105, 7], [105, 27], [65, 27]],
                [[5, 9], [45, 9], [45, 29], [5, 29]]]
    crops = line_crops(image, polygons)
    assert [p[0][0] for p, _ in crops] == [5, 65, 5]
    assert [crop.size for _, crop in crops] == [(40, 20), (40, 20), (75, 20)]
    assert crops[0][1].getpixel((2, 2)) == (10, 20, 30)
    for _, crop in crops:
        crop.close()
    for polygon in ([[[0, 0]] * 4], [[[float('nan'), 0]] * 4]):
        with pytest.raises(ValueError):
            line_crops(image, polygon)


def test_hybrid_real_reader_protocol_unicode_bgr_and_close(tmp_path, monkeypatch):
    pytest.importorskip('cv2')
    class Tensor:
        def __matmul__(self, other): return self
        def numpy(self): return np.ones((2, 2))
    monkeypatch.setitem(sys.modules, 'paddle', types.SimpleNamespace(
        __version__='3.2.2', set_device=lambda _: None, ones=lambda _: Tensor()))
    captured = {}
    class Detector:
        def __init__(self, **kwargs): captured.update(kwargs)
        def predict(self, pixels):
            assert pixels[0, 0].tolist() == [30, 20, 10]
            return [dict(dt_polys=[[[1, 1], [30, 1], [30, 15], [1, 15]],
                                   [[1, 20], [30, 20], [30, 35], [1, 35]]])]
    monkeypatch.setitem(sys.modules, 'paddleocr', types.SimpleNamespace(TextDetection=Detector))
    real_popen = subprocess.Popen
    # Real process and UTF-8 pipes; no model is impersonated as an inference test.
    stub = """import sys,json,base64,io
from PIL import Image
print(json.dumps(dict(ready=True, weights_sha256='test', torch_version='test')),flush=True)
for line in sys.stdin:
 r=json.loads(line)
 for crop in r['images']:
  with Image.open(io.BytesIO(base64.b64decode(crop))) as im: assert im.size[0]>1
 print(json.dumps({'results':[{'text':'Tiếng Việt', 'confidence':.9} for _ in r['images']]},ensure_ascii=False),flush=True)
"""
    monkeypatch.setattr('OCR.utils.vietocr_engine.subprocess.Popen',
        lambda *a, **kw: real_popen([sys.executable, '-u', '-c', stub], **kw))
    engine = PaddleVietOCREngine(dict(device='cpu', vietocr_python=sys.executable,
                                     output_dir=str(tmp_path), page_timeout=5))
    try:
        boxes = engine.recognize_image(Image.new('RGB', (50, 50), (10, 20, 30)))
        assert [b['text'] for b in boxes] == ['Tiếng Việt', 'Tiếng Việt']
        assert boxes[1]['bbox'] == [1, 20, 30, 35]
        assert captured['model_name'] == 'PP-OCRv5_mobile_det'
        assert engine.info['engine_type'] == 'PaddleVietOCR'
    finally:
        engine.close()
    assert engine.process.poll() is not None


def test_backend_cache_separation_and_native_text_routing(tmp_path):
    class Engine:
        info = {'engine_type': 'contract'}
        calls = 0
        def recognize_image(self, image):
            self.calls += 1
            return [dict(text='Việt', confidence=.9)]
    image = tmp_path / 'scan.png'
    Image.new('RGB', (40, 40), 'white').save(image)
    config = dict(input_path=str(image), output_dir=str(tmp_path / 'out'), device='cpu')
    engine = Engine()
    run(config, engine)
    config['ocr_backend'] = 'paddle_vietocr'
    assert not run(config, engine)['pages'][0]['is_cached']
    assert run(config, engine)['pages'][0]['is_cached']
    config['ocr_backend'] = 'paddle'
    assert run(config, engine)['pages'][0]['is_cached']
    assert engine.calls == 2


def test_reader_timeout_and_error_are_not_empty_results():
    import queue
    engine = object.__new__(PaddleVietOCREngine)
    engine.messages = queue.Queue()
    with pytest.raises(TimeoutError):
        engine.receive(.01)
    engine.messages.put({'error': 'line exceeded EOS limit'})
    with pytest.raises(RuntimeError, match='EOS'):
        engine.receive(.01)


def test_render_error_keeps_model_for_following_pages(tmp_path, monkeypatch):
    import OCR.viet_runner as runner
    path = tmp_path / 'pages.tiff'
    Image.new('RGB', (40, 40)).save(path, save_all=True,
        append_images=[Image.new('RGB', (40, 40)) for _ in range(2)])
    created = []
    class Worker:
        info = {'engine_type': 'test'}
        def __init__(self, config):
            created.append(self)
            self.calls = self.closed = 0
        def recognize_image(self, image):
            self.calls += 1
            return [dict(text='Việt', confidence=.9)]
        def close(self): self.closed += 1
    load = runner.load_page
    def render(path, number, scale):
        if number == 2:
            raise RuntimeError('Failed to load page')
        return load(path, number, scale)
    monkeypatch.setattr(runner, 'WorkerEngine', Worker)
    monkeypatch.setattr(runner, 'load_page', render)
    report = run(dict(input_path=str(path), output_dir=str(tmp_path / 'out')))
    assert not report['complete']
    assert len(created) == 1 and created[0].calls == 2 and created[0].closed == 1
    assert report['pages'][2]['status'] == 'complete'


def _spawn_reader(connection):
    import time
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    connection.send(child.pid)
    time.sleep(30)


def test_worker_close_kills_reader_descendant():
    import multiprocessing as mp
    psutil = pytest.importorskip('psutil')
    from OCR.viet_runner import WorkerEngine
    context = mp.get_context('spawn')
    worker = object.__new__(WorkerEngine)
    worker.connection, child = context.Pipe()
    worker.process = context.Process(target=_spawn_reader, args=(child,))
    worker.process.start()
    child.close()
    try:
        assert worker.connection.poll(10)
        pid = worker.connection.recv()
        worker.close()
        assert not worker.process.is_alive()
        try:
            psutil.Process(pid).wait(timeout=5)
        except psutil.NoSuchProcess:
            pass
        assert not psutil.pid_exists(pid)
    finally:
        if worker.process.is_alive():
            worker.close()


@pytest.mark.skipif(not os.environ.get('VIETOCR_TEST_PYTHON'),
                    reason='Set VIETOCR_TEST_PYTHON and VIETOCR_TEST_WEIGHTS for real inference')
def test_real_reader_without_pkg_resources_or_gdown():
    """Reproduce the fresh Kaggle environment without importing legacy downloaders."""
    import base64
    import io
    from pathlib import Path
    from PIL import ImageDraw
    image = Image.new('RGB', (300, 40), 'white')
    ImageDraw.Draw(image).text((5, 10), 'Viet Nam 123', fill='black')
    encoded = io.BytesIO()
    image.save(encoded, format='PNG')
    request = json.dumps({'images': [base64.b64encode(encoded.getvalue()).decode()]}) + '\n'
    wrapper = """import sys,runpy
sys.modules['pkg_resources'] = None
sys.modules['gdown'] = None
sys.modules['vietocr.tool.predictor'] = None
sys.modules['vietocr.tool.utils'] = None
sys.argv = ['vietocr_reader', sys.argv[1]]
runpy.run_module('OCR.utils.vietocr_reader', run_name='__main__')
"""
    options = dict(device='cpu', weights_dir=os.environ['VIETOCR_TEST_WEIGHTS'])
    result = subprocess.run([os.environ['VIETOCR_TEST_PYTHON'], '-u', '-c', wrapper,
                             json.dumps(options)], input=request, capture_output=True,
                             encoding='utf-8', timeout=120, cwd=Path(__file__).resolve().parents[1],
                             env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    assert result.returncode == 0, result.stderr
    ready, response = map(json.loads, result.stdout.splitlines())
    assert ready['ready'] and len(ready['weights_sha256']) == 64
    assert response['results'][0]['text'].strip()
    assert 0 <= response['results'][0]['confidence'] <= 1
