from typing import List, Dict, Any

def sort_bounding_boxes(
    boxes: List[Dict[str, Any]],
    reading_order: str = "ltr_horizontal"
) -> List[Dict[str, Any]]:
    """
    Sorts detected text bounding boxes according to reading order.
    - 'ltr_horizontal': Left-to-right, top-to-bottom.
    - 'rtl_vertical': Classical Han right-to-left column order, top-to-bottom.
    Each box is expected to have 'bbox': [x1, y1, x2, y2] and 'text': str.
    """
    if not boxes:
        return []

    if reading_order == "rtl_vertical":
        # Group by vertical columns or sort by x descending, then y ascending
        # Primary key: x right-to-left (descending) with column tolerance
        sorted_boxes = sorted(
            boxes,
            key=lambda b: (-b.get("bbox", [0, 0, 0, 0])[2], b.get("bbox", [0, 0, 0, 0])[1])
        )
    else:
        # Standard horizontal: Primary key: y top-to-bottom with line tolerance, then x ascending
        sorted_boxes = sorted(
            boxes,
            key=lambda b: (round(b.get("bbox", [0, 0, 0, 0])[1] / 15) * 15, b.get("bbox", [0, 0, 0, 0])[0])
        )

    return sorted_boxes
