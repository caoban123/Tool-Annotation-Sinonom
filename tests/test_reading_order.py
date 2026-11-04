import pytest
from OCR.utils.page_order import sort_bounding_boxes

def test_ltr_horizontal_order():
    boxes = [
        {"bbox": [100, 50, 150, 70], "text": "Dòng 2"},
        {"bbox": [10, 10, 60, 30], "text": "Dòng 1 Đầu"},
        {"bbox": [70, 10, 120, 30], "text": "Dòng 1 Cuối"}
    ]
    sorted_res = sort_bounding_boxes(boxes, reading_order="ltr_horizontal")
    assert sorted_res[0]["text"] == "Dòng 1 Đầu"
    assert sorted_res[1]["text"] == "Dòng 1 Cuối"
    assert sorted_res[2]["text"] == "Dòng 2"

def test_rtl_vertical_order():
    # Classical Han: Right to left vertical columns
    # Column 1 (Rightmost, x=300): Top (y=20), Bottom (y=100)
    # Column 2 (Left, x=100): Top (y=20), Bottom (y=100)
    boxes = [
        {"bbox": [100, 20, 150, 60], "text": "Cột 2 Đầu"},
        {"bbox": [300, 100, 350, 140], "text": "Cột 1 Cuối"},
        {"bbox": [300, 20, 350, 60], "text": "Cột 1 Đầu"},
        {"bbox": [100, 100, 150, 140], "text": "Cột 2 Cuối"}
    ]
    sorted_res = sort_bounding_boxes(boxes, reading_order="rtl_vertical")
    assert sorted_res[0]["text"] == "Cột 1 Đầu"
    assert sorted_res[1]["text"] == "Cột 1 Cuối"
    assert sorted_res[2]["text"] == "Cột 2 Đầu"
    assert sorted_res[3]["text"] == "Cột 2 Cuối"
