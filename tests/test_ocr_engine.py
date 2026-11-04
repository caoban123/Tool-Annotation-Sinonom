import pytest
from PIL import Image
from OCR.utils.ocr_pipeline import PaddleVLOCREngine, BaseOCREngine, create_ocr_engine

def test_causal_mask_wrapper_strips_cache_position():
    """Verify that _patch_causal_mask_in_target safely removes cache_position on modern transformers."""
    class MockTarget:
        def __init__(self):
            self.last_kwargs = None

        def create_causal_mask(self, config, inputs_embeds, attention_mask):
            self.last_kwargs = {
                "config": config,
                "inputs_embeds": inputs_embeds,
                "attention_mask": attention_mask
            }
            return "mask_tensor"

    target = MockTarget()
    # Before patch, passing cache_position raises TypeError
    with pytest.raises(TypeError):
        target.create_causal_mask(config=1, inputs_embeds=2, attention_mask=3, cache_position=4)

    # Apply patch
    PaddleVLOCREngine._patch_causal_mask_in_target(target)

    # After patch, passing cache_position must succeed and cache_position must be popped
    res = target.create_causal_mask(config="cfg", inputs_embeds="emb", attention_mask="att", cache_position="strip_me")
    assert res == "mask_tensor"
    assert "cache_position" not in target.last_kwargs
    assert target.last_kwargs["inputs_embeds"] == "emb"

def test_base_ocr_engine_raises_error_without_mock():
    """Verify that BaseOCREngine raises RuntimeError when paddleocr is not installed and allow_mock=False."""
    # When allow_mock=False, missing engine must fail hard rather than silently degrading to fake mock
    try:
        from paddleocr import PaddleOCR
        # If paddleocr is installed, it should succeed
        engine = BaseOCREngine(model_name="han", allow_mock=False)
        assert engine.is_mock is False
    except (ImportError, RuntimeError):
        with pytest.raises(RuntimeError, match="Không thể khởi tạo mô hình"):
            BaseOCREngine(model_name="han", allow_mock=False)

@pytest.mark.integration
@pytest.mark.requires_gpu
def test_paddle_vl_real_gpu_inference():
    """Integration test that requires real CUDA GPU and weights."""
    import torch
    if not torch.cuda.is_available():
        pytest.skip("Bỏ qua integration test: Cần GPU CUDA thật.")

    engine = PaddleVLOCREngine(model_id="PaddlePaddle/PaddleOCR-VL-1.6", use_gpu=True)
    assert engine.hardware == "cuda"
    assert engine.is_mock is False

    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    boxes = engine.recognize_image(img)
    assert isinstance(boxes, list)
