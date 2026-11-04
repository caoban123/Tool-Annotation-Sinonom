import json
import zipfile
from pathlib import Path
import pytest
from PIL import Image
from OCR.han_runner import run
from OCR.utils.render_pdf import render_pdf_to_images


class RecordingEngine:
    model_name = 'injected_contract_engine'
    engine_type = 'injected_contract_engine'
    hardware = 'cpu'
    is_mock = False

    def __init__(self, fail_at=None):
        self.calls = 0
        self.fail_at = fail_at

    def recognize_image(self, image, **kwargs):
        self.calls += 1
        if self.calls == self.fail_at:
            raise RuntimeError('interrupted')
        return [{'bbox': [0, 0, image.width, image.height], 'text': f'辨識測試第{self.calls}頁', 'confidence': None}]


def configuration(tmp_path, input_path):
    return dict(input_path=str(input_path), output_dir=str(tmp_path / 'output'),
                model_id='contract_model', use_gpu=False, start_page=1, end_page=None,
                max_new_tokens=128, max_pixels=200704, render_scale=1.0,
                reading_order='rtl_vertical', continue_on_error=False)


def test_runner_pdf_export_and_resume(tmp_path):
    config = configuration(tmp_path, Path('tests/fixtures/sample_text.pdf'))
    engine = RecordingEngine()
    result = run(config, engine)
    calls = engine.calls
    # A page can now contain multiple ordered OCR regions.
    assert calls >= result['total_pages']
    assert all(p['page_number'] == i + 1 for i, p in enumerate(result['pages']))
    config['max_retry_tokens'] = 16384
    resumed = run(config, engine)
    assert engine.calls == calls
    assert all(p['is_cached'] for p in resumed['pages'])
    assert resumed['full_text'] == result['full_text']
    output = Path(config['output_dir'])
    assert (output / 'han.txt').read_text(encoding='utf-8') == result['full_text']
    with zipfile.ZipFile(output / 'han_ocr.zip') as archive:
        assert archive.read('han.txt').decode('utf-8') == result['full_text']
        assert 'han_metadata.json' in archive.namelist()
        assert any(n.startswith('checkpoints/') for n in archive.namelist())


def test_runner_cache_changes_with_pixels_and_document(tmp_path):
    path = tmp_path / 'scan.png'
    Image.new('RGB', (40, 60), 'white').save(path)
    config = configuration(tmp_path, path)
    engine = RecordingEngine()
    run(config, engine)
    config['max_pixels'] *= 2
    run(config, engine)
    assert engine.calls == 2
    Image.new('RGB', (40, 60), 'black').save(path)
    run(config, engine)
    assert engine.calls == 3


def test_runner_rejects_bad_range_before_model_load(tmp_path):
    config = configuration(tmp_path, Path('tests/fixtures/sample_han_scan.png'))
    config['start_page'] = 21
    with pytest.raises(ValueError, match='1..1'):
        run(config)


def test_runner_split_spread_and_interruption(tmp_path):
    path = tmp_path / 'spread.tiff'
    first = Image.new('RGB', (60, 40), 'white')
    second = Image.new('RGB', (60, 40), 'black')
    first.save(path, save_all=True, append_images=[second])
    config = configuration(tmp_path, path)
    engine = RecordingEngine(fail_at=2)
    with pytest.raises(RuntimeError, match='interrupted'):
        run(config, engine)
    assert not (Path(config['output_dir']) / 'han_ocr.zip').exists()
    engine.fail_at = None
    result = run(config, engine)
    assert result['pages'][0]['is_cached']
    assert not result['pages'][1]['is_cached']
    config['split_spread'] = True
    result = run(config, engine)
    assert len(result['pages'][0]['regions']) == 2
    assert '\n' in result['pages'][0]['text']


def test_pdf_images_remain_valid_after_document_closed():
    images = render_pdf_to_images('tests/fixtures/sample_text.pdf', max_pages=1)
    assert images[0].getpixel((0, 0)) is not None
    images[0].close()
    with pytest.raises(ValueError):
        render_pdf_to_images('tests/fixtures/sample_text.pdf', start_page=0)


def test_vlm_requires_image_and_decodes_only_new_tokens():
    torch = pytest.importorskip('torch')
    from types import SimpleNamespace
    from OCR.utils.ocr_pipeline import PaddleVLOCREngine

    class Inputs(dict):
        def to(self, device):
            return self

    class Processor:
        image_processor = SimpleNamespace(min_pixels=784)
        def apply_chat_template(self, messages, **kwargs):
            assert messages[0]['content'][0]['type'] == 'image'
            assert kwargs['tokenize'] is True
            return Inputs(input_ids=torch.tensor([[7, 8]]), pixel_values=torch.zeros(1))
        def decode(self, tokens, **kwargs):
            assert list(tokens) == [11, 2]
            return '漢字'

    class Model:
        device = 'cpu'
        dtype = torch.float32
        generation_config = SimpleNamespace(eos_token_id=2)
        def generate(self, **kwargs):
            assert kwargs['pixel_values'].dtype == torch.float32
            assert kwargs['input_ids'].dtype == torch.int64
            return torch.tensor([[7, 8, 11, 2]])

    engine = PaddleVLOCREngine.__new__(PaddleVLOCREngine)
    engine.model, engine.processor = Model(), Processor()
    engine.max_new_tokens, engine.max_pixels = 2, 200704
    boxes = engine.recognize_image(Image.new('RGB', (10, 10)), show_progress=False)
    assert boxes[0]['text'] == '漢字'
    assert boxes[0]['confidence'] is None
    assert boxes[0]['bbox_type'] == 'page'
    engine.model.generation_config.eos_token_id = 99
    with pytest.raises(RuntimeError, match='max_new_tokens'):
        engine.recognize_image(Image.new('RGB', (10, 10)), show_progress=False)


def test_han_notebook_bundle_matches_sources():
    import base64, hashlib, zlib
    nb = json.loads(Path('OCR/notebooks/01_OCR_Han.ipynb').read_text(encoding='utf-8'))
    context = {'WORK_DIR': Path('artifacts/bundle_test'), 'json': json}
    context['WORK_DIR'].mkdir(parents=True, exist_ok=True)
    exec(nb['cells'][2]['source'], context)
    packed = zlib.decompress(base64.b64decode(context['BUNDLED_SOURCES']))
    for name, data in json.loads(packed).items():
        assert base64.b64decode(data) == Path(name).read_bytes()
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            compile(cell['source'], cell['id'], 'exec')


@pytest.mark.parametrize('capability, expected', [(6, 'float16'), (7, 'float16'), (8, 'bfloat16')])
def test_native_loader_precision_and_no_remote_code(monkeypatch, capability, expected):
    torch = pytest.importorskip('torch')
    transformers = pytest.importorskip('transformers')
    from OCR.utils.ocr_pipeline import PaddleVLOCREngine
    from types import SimpleNamespace
    calls = {}

    class Model:
        def to(self, **kwargs):
            calls['placement'] = kwargs
            return self
        def eval(self):
            calls['eval'] = True
            return self

    def load_processor(*args, **kwargs):
        assert kwargs['trust_remote_code'] is False
        return SimpleNamespace()

    def load_model(*args, **kwargs):
        assert kwargs['trust_remote_code'] is False
        assert kwargs['attn_implementation'] == 'eager'
        return Model()

    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    # BF16 emulation must not select BF16 on T4/P100.
    monkeypatch.setattr(torch.cuda, 'is_bf16_supported', lambda: True)
    monkeypatch.setattr(torch.cuda, 'get_device_capability', lambda index: (capability, 0))
    monkeypatch.setattr(transformers.AutoProcessor, 'from_pretrained', load_processor)
    monkeypatch.setattr(transformers.AutoModelForImageTextToText, 'from_pretrained', load_model)
    PaddleVLOCREngine(use_gpu=True)
    assert calls['placement'] == {'device': 'cuda', 'dtype': getattr(torch, expected)}
    assert calls['eval']


def test_native_generation_with_tiny_random_model():
    """Exercise real attention/cache math offline; NOT OCR-quality evidence."""
    torch = pytest.importorskip('torch')
    transformers = pytest.importorskip('transformers')
    from OCR.utils.regions import GenerationGuard
    config = transformers.PaddleOCRVLConfig(
        text_config=dict(vocab_size=32, hidden_size=32, intermediate_size=64,
                         num_attention_heads=4, num_key_value_heads=2, head_dim=8,
                         num_hidden_layers=1, rope_parameters={'rope_type': 'default',
                         'rope_theta': 10000.0, 'mrope_section': [1, 1, 2]}),
        vision_config=dict(hidden_size=32, intermediate_size=64, num_attention_heads=4,
                           num_hidden_layers=1, patch_size=14, spatial_merge_size=2),
        image_token_id=3, vision_start_token_id=4, vision_end_token_id=5)
    model = transformers.PaddleOCRVLForConditionalGeneration(config).to(dtype=torch.float32).eval()
    with torch.inference_mode():
        result = model.generate(input_ids=torch.tensor([[1, 4, 3, 5, 6]]),
            attention_mask=torch.ones((1, 5), dtype=torch.long),
            pixel_values=torch.zeros((4, 3, 14, 14)), image_grid_thw=torch.tensor([[1, 2, 2]]),
            max_new_tokens=2, do_sample=False, use_cache=True,
            stopping_criteria=transformers.StoppingCriteriaList([GenerationGuard(5)]))
    assert result.shape[0] == 1
    assert result.shape[1] > 5


@pytest.fixture
def retry_engine():
    torch = pytest.importorskip('torch')
    from types import SimpleNamespace
    from OCR.utils.ocr_pipeline import PaddleVLOCREngine

    class Inputs(dict):
        def to(self, device):
            return self

    class Processor:
        image_processor = SimpleNamespace(min_pixels=784)
        def apply_chat_template(self, *args, **kwargs):
            return Inputs(input_ids=torch.tensor([[7, 8]]), pixel_values=torch.zeros(1))
        def decode(self, tokens, **kwargs):
            assert int(tokens[-1]) == 2, 'Never accept or decode a truncated attempt as final text'
            return '辨識完整文字'

    class Model:
        device = 'cpu'
        dtype = torch.float32
        generation_config = SimpleNamespace(eos_token_id=2)
        finish_at = 4
        failure = None
        def __init__(self):
            self.budgets = []
        def generate(self, **kwargs):
            budget = kwargs['max_new_tokens']
            self.budgets.append(budget)
            if self.failure:
                raise self.failure
            generated = [11] * budget
            if self.finish_at is not None and budget >= self.finish_at:
                generated[-1] = 2
            return torch.tensor([[7, 8] + generated])

    engine = PaddleVLOCREngine.__new__(PaddleVLOCREngine)
    engine.model, engine.processor = Model(), Processor()
    engine.max_new_tokens, engine.max_retry_tokens, engine.max_pixels = 2, 8, 200704
    engine.model_name = engine.engine_type = 'native_contract'
    engine.hardware, engine.is_mock = 'cpu', False
    return engine


def test_truncated_page_retries_then_caches_complete_result(retry_engine, tmp_path):
    from OCR.utils.ocr_pipeline import OCRPipeline
    from OCR.utils.checkpoints import OCRCheckpointManager
    pipeline = OCRPipeline(retry_engine, OCRCheckpointManager(str(tmp_path)))
    image = Image.new('RGB', (30, 40))
    result = pipeline.process_images([image], source_id='book', start_page=27)
    assert retry_engine.model.budgets == [2, 4]
    assert retry_engine.last_truncated is False
    assert result['pages'][0]['page_number'] == 27
    assert result['pages'][0]['boxes'][0]['token_budget'] == 4
    assert result['full_text'] == '辨識完整文字'
    result = pipeline.process_images([image], source_id='book', start_page=27)
    assert result['pages'][0]['is_cached']
    assert retry_engine.model.budgets == [2, 4]


def test_retry_limit_still_rejects_truncated_page(retry_engine, tmp_path):
    from OCR.utils.ocr_pipeline import OCRPipeline
    from OCR.utils.checkpoints import OCRCheckpointManager
    retry_engine.model.finish_at = None
    pipeline = OCRPipeline(retry_engine, OCRCheckpointManager(str(tmp_path)))
    with pytest.raises(RuntimeError, match='max_new_tokens=8'):
        pipeline.process_images([Image.new('RGB', (30, 40))], start_page=27)
    assert retry_engine.model.budgets == [2, 4, 8]
    assert not list(tmp_path.glob('*.json'))


def test_other_inference_errors_do_not_trigger_token_retry(retry_engine):
    retry_engine.model.failure = ValueError('unrelated inference error')
    with pytest.raises(ValueError, match='unrelated inference error'):
        retry_engine.recognize_image(Image.new('RGB', (30, 40)))
    assert retry_engine.model.budgets == [2]
