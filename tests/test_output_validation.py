import pytest
from pathlib import Path
from OCR.utils.export_text import validate_ocr_output, export_ocr_result

def test_validate_ocr_output_rejects_mock():
    mock_res = {
        "full_text": "古南交，周號越裳。",
        "pages": [{"page_number": 1, "text": "古南交，周號越裳。"}],
        "engine_info": {"model_name": "PaddleOCR-VL-1.6", "is_mock": True, "engine_type": "cpu_test_adapter"}
    }
    with pytest.raises(ValueError, match="Mock Adapter"):
        validate_ocr_output(mock_res)

def test_validate_ocr_output_rejects_placeholder_strings():
    fake_res = {
        "full_text": "古南交，周號越裳。",
        "pages": [{"page_number": 1, "text": "古南交，周號越裳。"}],
        "engine_info": {"model_name": "PaddleOCR-VL-1.6", "is_mock": False, "engine_type": "paddleocr_vl"}
    }
    with pytest.raises(ValueError, match="chứa chuỗi văn bản mẫu giả lập"):
        validate_ocr_output(fake_res)

def test_validate_ocr_output_passes_real_content():
    real_res = {
        "full_text": "皇越一統輿地誌\n卷之一\n京師第一",
        "pages": [
            {"page_number": 1, "text": "皇越一統輿地誌\n卷之一\n京師第一"}
        ],
        "engine_info": {"model_name": "PaddleOCR-VL-1.6", "is_mock": False, "engine_type": "paddleocr_vl"}
    }
    stats = validate_ocr_output(real_res)
    assert stats["is_valid"] is True
    assert stats["total_pages"] == 1
    assert stats["total_characters"] > 0

def test_export_ocr_result_writes_utf8(tmp_path):
    real_res = {
        "full_text": "欽定越史通鑑綱目\n正編卷之一",
        "pages": [
            {"page_number": 1, "text": "欽定越史通鑑綱目\n正編卷之一"}
        ],
        "engine_info": {"model_name": "PaddleOCR-VL-1.6", "is_mock": False, "engine_type": "paddleocr_vl"}
    }
    txt_path = tmp_path / "han.txt"
    meta_path = tmp_path / "meta.json"

    stats = export_ocr_result(real_res, txt_path, meta_path)
    assert stats["is_valid"] is True
    assert txt_path.exists()
    assert meta_path.exists()

    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "欽定越史通鑑綱目" in content
