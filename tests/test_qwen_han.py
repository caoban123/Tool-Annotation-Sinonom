"""Qwen Han adapter contracts and native tiny-model execution (not OCR accuracy)."""
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from OCR.utils.qwen_engine import QwenVLOCREngine, is_qwen_model


def test_model_detection_and_quantized_cpu_rejection(tmp_path):
    assert is_qwen_model('Qwen/Qwen3-VL-8B-Instruct')
    assert not is_qwen_model('PaddlePaddle/PaddleOCR-VL-1.6')
    (tmp_path / 'config.json').write_text(json.dumps({'model_type': 'qwen3_vl'}))
    assert is_qwen_model(str(tmp_path))
    with pytest.raises(ValueError, match='4-bit requires CUDA'):
        QwenVLOCREngine(use_gpu=False)


@pytest.mark.parametrize('quantized,capability', [(True, 7), (True, 8), (False, 7)])
def test_loader_quantization_precision_and_placement(monkeypatch, quantized, capability):
    torch = pytest.importorskip('torch')
    transformers = pytest.importorskip('transformers')
    calls = {}
    class Model:
        def to(self, **kwargs):
            assert not quantized, 'Quantized model must not be moved/cast after loading'
            calls['to'] = kwargs
            return self
        def eval(self): return self
    def load(*args, **kwargs):
        calls.update(kwargs)
        return Model()
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(torch.cuda, 'get_device_capability', lambda _: (capability, 0))
    monkeypatch.setattr(torch.cuda, 'is_bf16_supported', lambda: True)
    monkeypatch.setattr(transformers.AutoModelForImageTextToText, 'from_pretrained', load)
    monkeypatch.setattr(transformers.AutoProcessor, 'from_pretrained', lambda *a, **k: object())
    from transformers.utils import quantization_config
    monkeypatch.setattr(quantization_config, 'BitsAndBytesConfig', lambda **k: k)
    monkeypatch.setattr(transformers, 'BitsAndBytesConfig', lambda **k: k)
    engine = QwenVLOCREngine(load_in_4bit=quantized, revision='fixed-revision')
    dtype = torch.float16 if capability == 7 else torch.bfloat16
    assert calls['dtype'] == dtype and calls['trust_remote_code'] is False
    assert calls['revision'] == 'fixed-revision'
    if quantized:
        assert calls['device_map'] == {'': 0} and 'to' not in calls
        assert calls['quantization_config']['bnb_4bit_compute_dtype'] == dtype
        assert calls['quantization_config']['bnb_4bit_quant_type'] == 'nf4'
    else:
        assert calls['to'] == dict(device='cuda', dtype=dtype)
    assert 'qwen3_vl' in engine.engine_type


def test_transcription_prompt_and_image_resize_are_model_specific():
    torch = pytest.importorskip('torch')
    pytest.importorskip('transformers')
    class Inputs(dict):
        def to(self, device): return self
    class Processor:
        def apply_chat_template(self, messages, **kwargs):
            prompt = messages[0]['content'][1]['text']
            assert 'right to left' in prompt and 'Do not translate' in prompt
            assert 'Traditional Chinese' in prompt
            assert kwargs['images_kwargs']['size'] == dict(shortest_edge=65536, longest_edge=200704)
            assert messages[0]['content'][0]['type'] == 'image'
            return Inputs(input_ids=torch.tensor([[7, 8]]), pixel_values=torch.zeros(1))
        def decode(self, tokens, **kwargs):
            assert tokens.tolist() == [11, 2]
            return '古籍漢字'
    class Model:
        device = 'cpu'
        dtype = torch.float32
        generation_config = SimpleNamespace(eos_token_id=2)
        def generate(self, **kwargs):
            assert not kwargs['do_sample']
            return torch.tensor([[7, 8, 11, 2]])
    engine = QwenVLOCREngine.__new__(QwenVLOCREngine)
    engine.processor, engine.model = Processor(), Model()
    engine.reading_order = 'rtl_vertical'
    engine.max_new_tokens, engine.max_pixels = 2, 200704
    boxes = engine.recognize_image(Image.new('RGB', (40, 80)), show_progress=False)
    assert boxes[0]['text'] == '古籍漢字' and boxes[0]['confidence'] is None
    engine.model.generation_config.eos_token_id = 99
    with pytest.raises(RuntimeError, match='max_new_tokens'):
        engine.recognize_image(Image.new('RGB', (40, 80)), show_progress=False)


def test_runner_selects_qwen_and_separates_quantized_cache(tmp_path, monkeypatch):
    from OCR import han_runner
    calls = []
    class Engine:
        engine_type, hardware, is_mock = 'test', 'cpu', False
        model_name = 'Qwen/Qwen3-VL-8B-Instruct'
        def __init__(self, **kwargs): calls.append(kwargs)
        def recognize_image(self, image, **kwargs):
            return [dict(text='漢字', bbox=[0, 0, image.width, image.height], confidence=None)]
    image = tmp_path / 'scan.png'
    Image.new('RGB', (80, 100), 'white').save(image)
    monkeypatch.setattr(han_runner, 'QwenVLOCREngine', Engine)
    config = dict(input_path=str(image), output_dir=str(tmp_path / 'out'),
                  model_id='Qwen/Qwen3-VL-8B-Instruct', use_gpu=False,
                  qwen_load_in_4bit=False, max_pixels=200704)
    han_runner.run(config)
    assert len(calls) == 1 and calls[0]['load_in_4bit'] is False
    assert han_runner.run(config)['pages'][0]['is_cached']
    config['qwen_load_in_4bit'] = True
    assert not han_runner.run(config)['pages'][0]['is_cached']
    assert len(calls) == 2 and calls[1]['load_in_4bit'] is True


def test_tiny_native_qwen_vision_and_kv_cache():
    torch = pytest.importorskip('torch')
    transformers = pytest.importorskip('transformers')
    from transformers.models.qwen2_vl.image_processing_qwen2_vl import Qwen2VLImageProcessor
    config = transformers.Qwen3VLConfig(
        text_config=dict(vocab_size=32, hidden_size=32, intermediate_size=64,
                         num_hidden_layers=1, num_attention_heads=4, num_key_value_heads=2,
                         head_dim=8, rope_parameters={'rope_type': 'default',
                         'rope_theta': 10000., 'mrope_section': [1, 1, 2]}),
        vision_config=dict(depth=1, hidden_size=32, intermediate_size=64, num_heads=4,
                           out_hidden_size=32, patch_size=16, spatial_merge_size=2,
                           num_position_embeddings=16, deepstack_visual_indexes=[0]),
        image_token_id=3, vision_start_token_id=4, vision_end_token_id=5,
        eos_token_id=2, pad_token_id=0)
    processor = Qwen2VLImageProcessor(patch_size=16, temporal_patch_size=2, merge_size=2,
                                      size=dict(shortest_edge=1024, longest_edge=1024))
    pixels = processor(images=Image.new('RGB', (32, 32)), return_tensors='pt')
    model = transformers.Qwen3VLForConditionalGeneration(config).eval()
    with torch.inference_mode():
        output = model.generate(input_ids=torch.tensor([[1, 4, 3, 5, 6]]),
            attention_mask=torch.ones((1, 5), dtype=torch.long), **pixels,
            max_new_tokens=2, do_sample=False)
    assert 5 < output.shape[1] <= 7


def test_han_notebook_qwen_selection_smoke(monkeypatch):
    import nbformat
    from nbclient import NotebookClient
    monkeypatch.setenv('OCR_NOTEBOOK_SMOKE', '1')
    notebook = nbformat.read('OCR/notebooks/01_OCR_Han.ipynb', as_version=4)
    notebook.cells[1].source = notebook.cells[1].source.replace(
        'MODEL_ID = "PaddlePaddle/PaddleOCR-VL-1.6"',
        'MODEL_ID = "Qwen/Qwen3-VL-8B-Instruct"')
    NotebookClient(notebook, timeout=60, kernel_name='python3').execute()
    config = json.loads(Path('artifacts/han_notebook/config.json').read_text(encoding='utf-8'))
    assert config['model_id'] == 'Qwen/Qwen3-VL-8B-Instruct'
    assert config['qwen_load_in_4bit'] is True
