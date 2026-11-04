import pytest
from PIL import Image
from OCR.utils.checkpoints import OCRCheckpointManager
from OCR.utils.ocr_pipeline import OCRPipeline

class FakeRealEngine:
    """Dependency injection test engine simulating a real OCR model without network download."""
    def __init__(self, model_name="test_ai_model"):
        self.model_name = model_name
        self.engine_type = "paddleocr_vl_test"
        self.hardware = "cpu"
        self.is_mock = False
        self.call_count = 0

    def recognize_image(self, image: Image.Image):
        self.call_count += 1
        return [
            {"bbox": [10, 10, 100, 30], "text": f"真實辨識文字第{self.call_count}頁", "confidence": 0.99}
        ]

def test_pipeline_preserves_start_page(tmp_path):
    mgr = OCRCheckpointManager(cache_dir=str(tmp_path))
    engine = FakeRealEngine()
    pipeline = OCRPipeline(engine=engine, checkpoint_manager=mgr)

    img1 = Image.new("RGB", (100, 100), color=(255, 255, 255))
    img2 = Image.new("RGB", (100, 100), color=(255, 255, 255))

    # Process pages starting at page 21!
    res = pipeline.process_images([img1, img2], source_id="book_vol1", start_page=21)

    assert res["start_page"] == 21
    assert res["end_page"] == 22
    assert len(res["pages"]) == 2
    assert res["pages"][0]["page_number"] == 21
    assert res["pages"][1]["page_number"] == 22
    assert "真實辨識文字第1頁" in res["pages"][0]["text"]
    assert "真實辨識文字第2頁" in res["pages"][1]["text"]

def test_pipeline_checkpoint_caching_and_resume(tmp_path):
    mgr = OCRCheckpointManager(cache_dir=str(tmp_path))
    engine = FakeRealEngine()
    pipeline = OCRPipeline(engine=engine, checkpoint_manager=mgr)

    img = Image.new("RGB", (100, 100), color=(255, 255, 255))

    # Run 1: Cold run
    res1 = pipeline.process_images([img], source_id="doc_cache_test", start_page=5)
    assert res1["pages"][0]["is_cached"] is False
    assert engine.call_count == 1

    # Run 2: Cached run - should retrieve from disk and NOT call recognize_image
    res2 = pipeline.process_images([img], source_id="doc_cache_test", start_page=5)
    assert res2["pages"][0]["is_cached"] is True
    assert res2["pages"][0]["page_number"] == 5
    assert engine.call_count == 1 # Call count must NOT increase!

def test_pipeline_blank_page_handling(tmp_path):
    mgr = OCRCheckpointManager(cache_dir=str(tmp_path))

    class BlankEngine:
        def __init__(self):
            self.model_name = "blank_test_engine"
            self.engine_type = "paddleocr_vl"
            self.hardware = "cpu"
            self.is_mock = False

        def recognize_image(self, image):
            # No text on a genuine blank page
            return []

    pipeline = OCRPipeline(engine=BlankEngine(), checkpoint_manager=mgr)
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))

    res = pipeline.process_images([img], source_id="blank_doc", start_page=1)
    assert len(res["pages"]) == 1
    assert res["pages"][0]["is_blank"] is True
    assert res["pages"][0]["text"] == ""
