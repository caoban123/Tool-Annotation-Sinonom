import pytest
from pathlib import Path
from PIL import Image

from OCR.utils.checkpoints import OCRCheckpointManager
from OCR.utils.page_order import sort_bounding_boxes
from OCR.utils.ocr_pipeline import BaseOCREngine, OCRPipeline

def test_ocr_checkpoint_manager(tmp_path):
    mgr = OCRCheckpointManager(cache_dir=str(tmp_path / "checkpoints"))
    key = mgr.compute_page_key("doc1", 1, "test_model")

    assert mgr.get_cached_result(key) is None
    mgr.save_cached_result(key, {"page": 1, "text": "古南交"})

    cached = mgr.get_cached_result(key)
    assert cached is not None
    assert cached["text"] == "古南交"

def test_page_order_sorting():
    # Two boxes: Box 1 at left, Box 2 at right
    box_left = {"bbox": [10, 20, 50, 40], "text": "Tả (Trái)"}
    box_right = {"bbox": [200, 20, 250, 40], "text": "Hữu (Phải)"}

    # In LTR horizontal: left first
    ltr = sort_bounding_boxes([box_right, box_left], reading_order="ltr_horizontal")
    assert ltr[0]["text"] == "Tả (Trái)"

    # In RTL vertical: right first
    rtl = sort_bounding_boxes([box_left, box_right], reading_order="rtl_vertical")
    assert rtl[0]["text"] == "Hữu (Phải)"

def test_ocr_pipeline_execution_and_caching(tmp_path):
    fixtures_dir = Path(__file__).parent / "fixtures"
    img_path = fixtures_dir / "sample_han_scan.png"
    img = Image.open(img_path)

    mgr = OCRCheckpointManager(cache_dir=str(tmp_path / "chk"))
    engine = BaseOCREngine(model_name="han_test")
    pipeline = OCRPipeline(engine=engine, checkpoint_manager=mgr)

    # First run: not cached
    res1 = pipeline.process_images([img], source_id="test_scan")
    assert len(res1["pages"]) == 1
    assert res1["pages"][0]["is_cached"] == False
    assert len(res1["full_text"]) > 0

    # Second run: must be retrieved from cache!
    res2 = pipeline.process_images([img], source_id="test_scan")
    assert res2["pages"][0]["is_cached"] == True

    # Third run with force_reprocess: re-processed
    res3 = pipeline.process_images([img], source_id="test_scan", force_reprocess=True)
    assert res3["pages"][0]["is_cached"] == False
