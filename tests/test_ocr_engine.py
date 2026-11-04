import pytest
from PIL import Image
from OCR.utils.ocr_pipeline import PaddleVLOCREngine, BaseOCREngine, create_ocr_engine

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
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("Bỏ qua integration test: Cần GPU CUDA thật.")

    engine = PaddleVLOCREngine(model_id="PaddlePaddle/PaddleOCR-VL-1.6", use_gpu=True)
    assert engine.hardware == "cuda"
    assert engine.is_mock is False

    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    boxes = engine.recognize_image(img)
    assert isinstance(boxes, list)
