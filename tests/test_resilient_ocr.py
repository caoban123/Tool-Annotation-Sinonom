import json
import zipfile

import pytest
from PIL import Image, ImageDraw

from OCR.han_runner import run
from OCR.utils.regions import GenerationGuard, OCRRegionError, plan_regions, split_region
from OCR.utils.export_text import export_ocr_result


def test_ruled_columns_keep_every_pixel_and_read_right_to_left():
    image = Image.new('RGB', (400, 240), 'white')
    draw = ImageDraw.Draw(image)
    for x in (80, 160, 240, 320):
        draw.line((x, 15, x, 225), fill='black', width=2)
    regions = plan_regions(image)
    assert len(regions) == 5
    assert regions[0][2] == 400 and regions[-1][0] == 0
    assert sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in regions) == 400 * 240
    assert all(regions[i][0] == regions[i + 1][2] for i in range(len(regions) - 1))
    assert plan_regions(Image.new('RGB', (100, 150), 'white')) == [(0, 0, 100, 150)]


def test_split_children_partition_parent_in_reading_order():
    image = Image.new('RGB', (400, 240), 'white')
    right, left = split_region(image, (0, 0, 400, 240))
    assert right[0] == left[2]
    assert left[0] == 0 and right[2] == 400
    assert right[1::2] == left[1::2] == (0, 240)


class Tokens:
    def __init__(self, values):
        self.values = values
        self.shape = (1, len(values))
    def __getitem__(self, index):
        return Tokens(self.values[index[1]])
    def tolist(self):
        return self.values


def test_generation_guard_stops_loop_and_timeout_without_rewriting_text():
    guard = GenerationGuard(0, clock=lambda: 0)
    assert guard(Tokens(list(range(32)) * 4))
    assert guard.reason == 'repetition'
    guard = GenerationGuard(0, clock=lambda: 0)
    assert not guard(Tokens(list(range(128))))
    ticks = iter([0, 91])
    guard = GenerationGuard(0, seconds=90, clock=lambda: next(ticks))
    assert guard(Tokens([1, 2]))
    assert guard.reason == 'time_limit'


class RecoveringEngine:
    model_name = engine_type = 'contract_region_engine'
    hardware = 'cpu'
    is_mock = False
    def __init__(self):
        self.calls = 0
        self.fail_dark = False
    def recognize_image(self, image, **kwargs):
        self.calls += 1
        if self.fail_dark and image.getpixel((0, 0))[0] < 100:
            raise RuntimeError('unreadable region')
        if image.width > 200:
            raise OCRRegionError('generation loop')
        return [{'bbox': [0, 0, image.width, image.height], 'text': '完整辨識結果', 'confidence': None}]


def config(tmp_path, path):
    return dict(input_path=str(path), output_dir=str(tmp_path / 'out'),
                model_id='contract', use_gpu=False, reading_order='rtl_vertical',
                max_new_tokens=4096, render_scale=1, start_page=1, end_page=None)


def test_failed_full_page_splits_and_completes(tmp_path):
    path = tmp_path / 'wide.png'
    Image.new('RGB', (400, 120), 'white').save(path)
    engine = RecoveringEngine()
    result = run(config(tmp_path, path), engine)
    assert result['complete']
    assert engine.calls == 3
    assert (tmp_path / 'out/han.txt').exists()


def test_bad_page_does_not_stop_later_pages_or_become_complete_cache(tmp_path):
    path = tmp_path / 'pages.tiff'
    dark = Image.new('RGB', (80, 120), 'black')
    dark.save(path, save_all=True, append_images=[Image.new('RGB', (80, 120), 'white')])
    engine = RecoveringEngine()
    engine.fail_dark = True
    settings = config(tmp_path, path)
    result = run(settings, engine)
    assert result['complete'] is False
    assert result['status'] == 'needs_review'
    assert result['pages'][0]['errors']
    assert result['pages'][1]['text'] == '完整辨識結果'
    assert not (tmp_path / 'out/han.txt').exists()
    assert (tmp_path / 'out/han.partial.txt').exists()
    with zipfile.ZipFile(tmp_path / 'out/han_ocr.zip') as archive:
        assert 'han.partial.txt' in archive.namelist()
        assert 'han.txt' not in archive.namelist()
        assert 'error_report.json' in archive.namelist()
        assert any(name.startswith('needs_review/') for name in archive.namelist())
        assert any(name.startswith('region_cache/') for name in archive.namelist())
    with pytest.raises(ValueError, match='partial'):
        export_ocr_result(result, tmp_path / 'invalid.txt', tmp_path / 'invalid.json')
    engine.fail_dark = False
    calls = engine.calls
    resumed = run(settings, engine)
    assert engine.calls == calls + 1
    assert resumed['complete']
    assert resumed['pages'][1]['is_cached']
    assert (tmp_path / 'out/han.txt').exists()
    assert json.loads((tmp_path / 'out/error_report.json').read_text()) == []


def test_page_time_budget_is_reported_as_missing_not_blank(tmp_path):
    path = tmp_path / 'page.png'
    Image.new('RGB', (100, 100), 'white').save(path)
    settings = config(tmp_path, path)
    settings['page_timeout'] = 0
    engine = RecoveringEngine()
    result = run(settings, engine)
    assert engine.calls == 0
    assert result['complete'] is False
    assert result['pages'][0]['is_blank'] is False
