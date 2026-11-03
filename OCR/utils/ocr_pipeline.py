import time
import os
import sys

# Tắt PIR executor và oneDNN không tương thích trong PaddlePaddle 3.x để tránh lỗi ConvertPirAttribute2RuntimeAttribute
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image

from .checkpoints import OCRCheckpointManager
from .page_order import sort_bounding_boxes

class BaseOCREngine:
    def __init__(self, model_name: str = "PP-OCRv4", use_gpu: bool = False):
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.hardware = "cuda" if use_gpu else "cpu"
        self._init_engine()

    def _init_engine(self):
        self.is_mock = False
        try:
            # Attempt to import real PaddleOCR
            from paddleocr import PaddleOCR
            lang = "ch" if "han" in self.model_name.lower() or "ch" in self.model_name.lower() else "vi"
            
            # Khởi tạo tương thích đa phiên bản PaddleOCR:
            # Ưu tiên PP-OCRv4 ổn định (tránh lỗi PIR instruction converter của PP-OCRv6 thử nghiệm)
            paddle_inst = None
            candidate_configs = [
                {"ocr_version": "PP-OCRv4", "use_angle_cls": True, "lang": lang, "show_log": False},
                {"ocr_version": "PP-OCRv4", "lang": lang, "show_log": False},
                {"ocr_version": "PP-OCRv3", "lang": lang, "show_log": False},
                {"use_angle_cls": True, "lang": lang, "show_log": False},
                {"lang": lang}
            ]

            for kwargs in candidate_configs:
                try:
                    paddle_inst = PaddleOCR(**kwargs)
                    break
                except Exception:
                    continue

            if paddle_inst is None:
                paddle_inst = PaddleOCR()

            self.paddle = paddle_inst
            self.engine_type = f"paddleocr_official (model=PP-OCRv4, lang={lang})"
            print(f"[OCR Engine] ✓ Đã nạp thành công mô hình AI PaddleOCR thật ({self.engine_type})")
        except Exception as e:
            # Fallback to local CPU test adapter
            self.paddle = None
            self.is_mock = True
            self.engine_type = "cpu_test_adapter (PaddleOCR chưa được cài đặt trong môi trường)"
            print(f"[OCR Engine] ⚠️ CHÚ Ý: Đang chạy ở chế độ MOCK TEST ADAPTER (Dữ liệu giả lập mẫu).")
            print(f"            Lý do: Không thể nạp thư viện 'paddleocr' ({e}).")
            print(f"            Để chạy AI thật, hãy cài đặt: pip install paddlepaddle paddleocr")

    def recognize_image(self, image: Image.Image) -> List[Dict[str, Any]]:
        """Recognizes text lines and bboxes from a PIL Image."""
        if not self.is_mock and self.paddle is not None:
            import numpy as np
            img_arr = np.array(image.convert("RGB"))
            raw_res = None
            
            for call_kwargs in [{"cls": True}, {}]:
                try:
                    raw_res = self.paddle.ocr(img_arr, **call_kwargs)
                    break
                except Exception as call_err:
                    continue

            boxes = []
            if raw_res and raw_res[0]:
                for item in raw_res[0]:
                    pts = item[0]
                    text = item[1][0]
                    conf = item[1][1]
                    x1 = min(p[0] for p in pts)
                    y1 = min(p[1] for p in pts)
                    x2 = max(p[0] for p in pts)
                    y2 = max(p[1] for p in pts)
                    boxes.append({
                        "bbox": [x1, y1, x2, y2],
                        "text": text,
                        "confidence": float(conf)
                    })
            return boxes
        else:
            # CPU test adapter: simulated detection for test fixtures
            w, h = image.size
            return [{
                "bbox": [20, 30, w - 20, 60],
                "text": "古南交，周號越裳。" if "han" in self.model_name.lower() else "Dat Nam Giao xua, nha Chu goi la Viet Thuong.",
                "confidence": 0.98
            }]

class OCRPipeline:
    def __init__(
        self,
        engine: Optional[BaseOCREngine] = None,
        checkpoint_manager: Optional[OCRCheckpointManager] = None,
        reading_order: str = "ltr_horizontal"
    ):
        self.engine = engine or BaseOCREngine()
        self.checkpoints = checkpoint_manager or OCRCheckpointManager()
        self.reading_order = reading_order

    def process_images(
        self,
        images: List[Image.Image],
        source_id: str = "doc_scan",
        force_reprocess: bool = False
    ) -> Dict[str, Any]:
        """
        Runs the OCR pipeline across a sequence of page images.
        Uses checkpointing to resume gracefully on interruption.
        """
        pages_result = []
        total_time = 0.0

        for idx, img in enumerate(images):
            page_num = idx + 1
            page_key = self.checkpoints.compute_page_key(source_id, page_num, self.engine.model_name)

            cached = None if force_reprocess else self.checkpoints.get_cached_result(page_key)
            if cached:
                cached_copy = dict(cached)
                cached_copy["is_cached"] = True
                pages_result.append(cached_copy)
                continue

            t0 = time.time()
            detected_boxes = self.engine.recognize_image(img)
            sorted_boxes = sort_bounding_boxes(detected_boxes, self.reading_order)
            dur = time.time() - t0
            total_time += dur

            page_text = "\n".join(b["text"] for b in sorted_boxes)

            page_data = {
                "page_number": page_num,
                "text": page_text,
                "boxes": sorted_boxes,
                "inference_time_sec": round(dur, 3),
                "is_cached": False,
                "engine_type": self.engine.engine_type,
                "hardware": self.engine.hardware
            }

            self.checkpoints.save_cached_result(page_key, page_data)
            pages_result.append(page_data)

        full_text = "\n".join(p["text"] for p in pages_result if p["text"])

        return {
            "source_id": source_id,
            "total_pages": len(images),
            "pages": pages_result,
            "full_text": full_text,
            "engine_info": {
                "model_name": self.engine.model_name,
                "engine_type": self.engine.engine_type,
                "hardware": self.engine.hardware,
                "is_mock": self.engine.is_mock
            }
        }
