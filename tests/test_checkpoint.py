import pytest
import json
from pathlib import Path
from OCR.utils.checkpoints import OCRCheckpointManager

def test_checkpoint_key_computation(tmp_path):
    mgr = OCRCheckpointManager(cache_dir=str(tmp_path))
    k1 = mgr.compute_page_key("docA", 1, "PaddleOCR-VL-1.6")
    k2 = mgr.compute_page_key("docA", 1, "PaddleOCR-VL-1.6")
    k3 = mgr.compute_page_key("docA", 2, "PaddleOCR-VL-1.6")
    k4 = mgr.compute_page_key("docA", 1, "PP-OCRv4")

    assert k1 == k2
    assert k1 != k3
    assert k1 != k4

def test_checkpoint_saves_and_retrieves_valid_data(tmp_path):
    mgr = OCRCheckpointManager(cache_dir=str(tmp_path))
    key = mgr.compute_page_key("doc_real", 10, "PaddleOCR-VL-1.6")

    real_data = {
        "page_number": 10,
        "text": "大越史記全書",
        "boxes": [{"bbox": [10, 10, 100, 30], "text": "大越史記全書", "confidence": 0.99}],
        "is_mock": False,
        "engine_type": "paddleocr_vl"
    }

    assert mgr.save_cached_result(key, real_data) is True
    cached = mgr.get_cached_result(key)
    assert cached is not None
    assert cached["text"] == "大越史記全書"
    assert cached["page_number"] == 10

def test_checkpoint_rejects_mock_data(tmp_path):
    mgr = OCRCheckpointManager(cache_dir=str(tmp_path))
    key = mgr.compute_page_key("doc_mock", 1, "test_engine")

    # 1. Attempt to save data with is_mock=True
    mock_data = {
        "page_number": 1,
        "text": "Something",
        "is_mock": True,
        "engine_type": "cpu_test_adapter"
    }
    assert mgr.save_cached_result(key, mock_data) is False
    assert mgr.get_cached_result(key) is None

    # 2. Attempt to save known fake mock string
    fake_string_data = {
        "page_number": 1,
        "text": "古南交，周號越裳。",
        "is_mock": False,
        "engine_type": "real_ocr"
    }
    assert mgr.save_cached_result(key, fake_string_data) is False
    assert mgr.get_cached_result(key) is None

def test_checkpoint_purges_existing_invalid_files(tmp_path):
    mgr = OCRCheckpointManager(cache_dir=str(tmp_path))

    # Manually write an invalid mock file
    invalid_file = tmp_path / "mock_old.json"
    with open(invalid_file, "w", encoding="utf-8") as f:
        json.dump({
            "text": "古南交，周號越裳。",
            "engine_type": "cpu_test_adapter",
            "is_mock": True
        }, f)

    # Manually write a valid file
    valid_file = tmp_path / "valid.json"
    with open(valid_file, "w", encoding="utf-8") as f:
        json.dump({
            "text": "真品文獻記錄",
            "engine_type": "paddleocr_vl",
            "is_mock": False
        }, f)

    purged = mgr.purge_invalid_checkpoints()
    assert purged == 1
    assert not invalid_file.exists()
    assert valid_file.exists()
