"""Real OCR adapters. PaddleOCR-VL uses native Transformers, without global patches."""
import time
import logging
from typing import List, Dict, Any, Optional
from PIL import Image
from .checkpoints import OCRCheckpointManager
from .page_order import sort_bounding_boxes
from .regions import GenerationGuard, OCRRegionError

logger = logging.getLogger("OCR-Pipeline")


class PaddleVLOCREngine:
    """Element recognition through the official native Transformers VLM API.

    Output is page text, not detected line geometry or calibrated confidence.
    No fallback to text-only input, another model, or mock results is allowed.
    """
    def __init__(self, model_id="PaddlePaddle/PaddleOCR-VL-1.6", use_gpu=True,
                 max_new_tokens=4096, max_pixels=1003520, revision=None,
                 max_retry_tokens=16384, region_timeout=90):
        if max_new_tokens < 1 or max_pixels < 784:
            raise ValueError("max_new_tokens >= 1; max_pixels >= 784")
        self.model_id = model_id
        self.model_name = model_id
        self.use_gpu = use_gpu
        self.max_new_tokens = max_new_tokens
        if max_retry_tokens < 1:
            raise ValueError("max_retry_tokens >= 1")
        self.max_retry_tokens = max(max_new_tokens, max_retry_tokens)
        self.max_pixels = max_pixels
        if region_timeout <= 0:
            raise ValueError('region_timeout phải lớn hơn 0')
        self.region_timeout = region_timeout
        self.revision = revision
        self.is_mock = False
        self.last_truncated = False
        self._init_engine()

    def _init_engine(self):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        from transformers.utils import logging as hf_logging
        # Per-parameter progress creates hundreds of lines in notebook pipes.
        # Keep warnings and explicit model/page/retry messages visible.
        hf_logging.disable_progress_bar()
        if self.use_gpu and not torch.cuda.is_available():
            raise RuntimeError("Không thấy CUDA. Bật GPU trong Colab/Kaggle hoặc chọn USE_GPU=False để chạy CPU chậm.")
        self.hardware = "cuda" if self.use_gpu else "cpu"
        # T4/P100 do not support BF16. FP32 is deliberately used on CPU.
        native_bf16 = self.use_gpu and torch.cuda.get_device_capability(0)[0] >= 8 and torch.cuda.is_bf16_supported()
        dtype = (torch.bfloat16 if native_bf16 else torch.float16) if self.use_gpu else torch.float32
        kwargs = {"revision": self.revision} if self.revision else {}
        self.processor = AutoProcessor.from_pretrained(self.model_id, trust_remote_code=False, **kwargs)
        self.model = AutoModelForImageTextToText.from_pretrained(
            self.model_id, dtype=dtype, attn_implementation="eager",
            trust_remote_code=False, **kwargs,
        ).to(device=self.hardware, dtype=dtype).eval()
        self.engine_type = f"transformers_native ({self.model_id}, {dtype})"
        print(f"[OCR] Model sẵn sàng: {self.hardware}, {dtype}; retry tối đa {self.max_retry_tokens} token.", flush=True)

    def _prepare_inputs(self, image):
        messages = [{"role": "user", "content": [
            {"type": "image", "image": image}, {"type": "text", "text": "OCR:"}
        ]}]
        return self.processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=True,
            return_tensors="pt", images_kwargs={"size": {
                "shortest_edge": self.processor.image_processor.min_pixels,
                "longest_edge": self.max_pixels,
            }},
        )

    def recognize_image(self, image: Image.Image, show_progress=True):
        import torch
        from transformers import StoppingCriteriaList
        image = image.convert("RGB")
        inputs = self._prepare_inputs(image).to(self.model.device)
        if "pixel_values" not in inputs or "input_ids" not in inputs:
            raise RuntimeError("Processor không trả về pixel_values/input_ids; từ chối suy luận thiếu ảnh.")
        # Move only floating image tensors to the model precision; keep token IDs integral.
        inputs["pixel_values"] = inputs["pixel_values"].to(dtype=self.model.dtype)
        prompt_len = inputs["input_ids"].shape[-1]
        eos = self.model.generation_config.eos_token_id
        eos_ids = eos if isinstance(eos, list) else [eos]
        budget = self.max_new_tokens
        ceiling = getattr(self, 'max_retry_tokens', budget)
        while True:
            guard = GenerationGuard(prompt_len, getattr(self, 'region_timeout', 90))
            with torch.inference_mode():
                output = self.model.generate(**inputs, max_new_tokens=budget,
                                             do_sample=False, use_cache=True,
                                             stopping_criteria=StoppingCriteriaList([guard]))
            generated = output[0][prompt_len:]
            ended = len(generated) > 0 and int(generated[-1]) in eos_ids
            if guard.reason and not ended:
                raise OCRRegionError(f"Vùng ảnh chưa hoàn tất: {guard.reason}. Cần chia vùng nhỏ hơn.")
            self.last_truncated = len(generated) >= budget and not ended
            if not self.last_truncated:
                break
            if budget >= ceiling:
                raise OCRRegionError(
                    f"OCR đạt max_new_tokens={budget} trước EOS sau khi thử lại. "
                    "Trang này chưa được cache. Kiểm tra ảnh/chữ lặp; chia ảnh theo cột "
                    "hoặc bật SPLIT_SPREAD nếu ảnh có hai mặt sách."
                )
            next_budget = min(budget * 2, ceiling)
            print(f"[OCR] Chạm {budget} token trước EOS; thử lại vùng ảnh với {next_budget} token.", flush=True)
            del output, generated
            budget = next_budget
        self.last_token_budget = budget
        text = self.processor.decode(generated, skip_special_tokens=True).strip()
        if show_progress:
            print(text or "[Trang không có văn bản]")
        return [{"bbox": [0, 0, image.width, image.height], "bbox_type": "page",
                 "text": text, "confidence": None, "token_budget": budget,
                 "generated_tokens": len(generated)}] if text else []

class BaseOCREngine:
    """
    OCR Engine wrapper for classic PaddleOCR (PP-OCRv4).
    Routes to PaddleVLOCREngine if model_name contains 'vl'.
    """
    def __init__(
        self,
        model_name: str = "PP-OCRv4",
        use_gpu: bool = False,
        allow_mock: bool = False
    ):
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.hardware = "cuda" if use_gpu else "cpu"
        self.allow_mock = allow_mock
        self.is_mock = False
        self._vl_engine = None

        if "vl" in str(model_name).lower():
            model_id = "PaddlePaddle/PaddleOCR-VL-1.6" if "1.6" in str(model_name) else "PaddlePaddle/PaddleOCR-VL"
            self._vl_engine = PaddleVLOCREngine(model_id=model_id, use_gpu=use_gpu)
            self.engine_type = self._vl_engine.engine_type
            self.hardware = self._vl_engine.hardware
            self.is_mock = False
        else:
            self._init_engine()

    def _init_engine(self):
        try:
            from paddleocr import PaddleOCR
            lang = "ch" if ("han" in self.model_name.lower() or "ch" in self.model_name.lower()) else "vi"
            self.paddle = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
            self.engine_type = f"paddleocr_official (model={self.model_name}, lang={lang})"
            self.is_mock = False
            print(f"[OCR Engine] ✓ Đã nạp thành công mô hình AI PaddleOCR thật ({self.engine_type})")
        except Exception as e:
            self.paddle = None
            if self.allow_mock:
                self.is_mock = True
                self.engine_type = f"test_mock_adapter ({e})"
                logger.warning(f"[OCR Engine] Đang chạy ở chế độ MOCK TEST ADAPTER (chỉ dùng cho tests: {e})")
            else:
                raise RuntimeError(
                    f"Không thể khởi tạo mô hình PaddleOCR thật ({e}). "
                    f"Vui lòng cài đặt: pip install paddlepaddle paddleocr"
                ) from e

    def recognize_image(self, image: Image.Image, *args, **kwargs) -> List[Dict[str, Any]]:
        """Recognizes text lines and bboxes from a PIL Image."""
        if self._vl_engine is not None:
            return self._vl_engine.recognize_image(image)

        if self.is_mock:
            # Explicit test mock adapter for unit tests only
            w, h = image.size
            return [{
                "bbox": [20, 30, w - 20, 60],
                "text": "测试文本" if "han" in self.model_name.lower() else "Van ban thu nghiem",
                "confidence": 0.98
            }]

        if self.paddle is None:
            raise RuntimeError("Mô hình PaddleOCR chưa được khởi tạo.")

        import numpy as np
        img_arr = np.array(image.convert("RGB"))
        raw_res = None
        for method in [
            lambda: self.paddle.ocr(img_arr),
            lambda: self.paddle.ocr(img_arr, cls=True),
            lambda: self.paddle(img_arr),
            lambda: self.paddle.predict(img_arr)
        ]:
            try:
                raw_res = method()
                if raw_res is not None:
                    break
            except Exception:
                continue

        boxes = []
        if raw_res and isinstance(raw_res, list) and len(raw_res) > 0 and isinstance(raw_res[0], list):
            for item in raw_res[0]:
                try:
                    pts = item[0]
                    text = item[1][0]
                    conf = item[1][1]
                    x1 = min(p[0] for p in pts)
                    y1 = min(p[1] for p in pts)
                    x2 = max(p[0] for p in pts)
                    y2 = max(p[1] for p in pts)
                    boxes.append({
                        "bbox": [x1, y1, x2, y2],
                        "text": str(text),
                        "confidence": float(conf)
                    })
                except Exception:
                    continue

        return boxes

def create_ocr_engine(
    engine_name: str = "PaddleOCR-VL-1.6",
    use_gpu: bool = True,
    allow_mock: bool = False
) -> Any:
    """Factory function to instantiate the preferred OCR engine."""
    if "vl" in engine_name.lower():
        model_id = "PaddlePaddle/PaddleOCR-VL-1.6" if "1.6" in engine_name else "PaddlePaddle/PaddleOCR-VL"
        return PaddleVLOCREngine(model_id=model_id, use_gpu=use_gpu)
    return BaseOCREngine(model_name=engine_name, use_gpu=use_gpu, allow_mock=allow_mock)

class OCRPipeline:
    def __init__(
        self,
        engine: Optional[Any] = None,
        checkpoint_manager: Optional[OCRCheckpointManager] = None,
        reading_order: str = "ltr_horizontal"
    ):
        self.engine = engine or BaseOCREngine(allow_mock=False)
        self.checkpoints = checkpoint_manager or OCRCheckpointManager(allow_mock=getattr(self.engine, 'allow_mock', False))
        if getattr(self.engine, 'allow_mock', False):
            self.checkpoints.allow_mock = True
        self.reading_order = reading_order

    def process_images(
        self,
        images: List[Any],
        source_id: str = "doc_scan",
        start_page: int = 1,
        force_reprocess: bool = False
    ) -> Dict[str, Any]:
        """
        Runs the OCR pipeline across a sequence of page images.
        Preserves original page numbering via start_page.
        Uses checkpointing to resume gracefully on interruption.
        """
        pages_result = []
        total_time = 0.0

        try:
            from tqdm.auto import tqdm
            pbar = tqdm(images, desc=f"Tiến độ OCR ({source_id})", unit="trang")
        except Exception:
            pbar = images

        for idx, item in enumerate(pbar):
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], int):
                page_num, img = item
            else:
                page_num = start_page + idx
                img = item

            page_key = self.checkpoints.compute_page_key(source_id, page_num, self.engine.model_name)

            cached = None if force_reprocess else self.checkpoints.get_cached_result(page_key)
            if cached:
                cached_copy = dict(cached)
                cached_copy["is_cached"] = True
                pages_result.append(cached_copy)
                if hasattr(pbar, "set_postfix"):
                    pbar.set_postfix({"Trang": page_num, "Trạng thái": "Nạp từ Cache", "Thời gian": "0.0s"})
                continue

            t0 = time.time()
            try:
                try:
                    detected_boxes = self.engine.recognize_image(img, show_progress=False)
                except TypeError:
                    detected_boxes = self.engine.recognize_image(img)
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise RuntimeError(f"Lỗi suy luận OCR tại trang {page_num} (source={source_id}): {e}") from e

            sorted_boxes = sort_bounding_boxes(detected_boxes, self.reading_order)
            dur = time.time() - t0
            total_time += dur

            page_text = "\n".join(b["text"] for b in sorted_boxes if b.get("text"))

            page_data = {
                "page_number": page_num,
                "text": page_text,
                "boxes": sorted_boxes,
                "inference_time_sec": round(dur, 3),
                "is_cached": False,
                "engine_type": self.engine.engine_type,
                "hardware": self.engine.hardware,
                "is_blank": len(page_text.strip()) == 0,
                "is_mock": getattr(self.engine, "is_mock", False)
            }

            if not getattr(self.engine, "is_mock", False) or getattr(self.checkpoints, "allow_mock", False):
                self.checkpoints.save_cached_result(page_key, page_data)

            pages_result.append(page_data)
            if hasattr(pbar, "set_postfix"):
                pbar.set_postfix({"Trang": page_num, "Trạng thái": f"{len(sorted_boxes)} dòng", "Thời gian": f"{dur:.1f}s"})

        full_text = "\n".join(p["text"] for p in pages_result if p.get("text"))

        return {
            "source_id": source_id,
            "total_pages": len(images),
            "start_page": start_page,
            "end_page": start_page + len(images) - 1,
            "pages": pages_result,
            "full_text": full_text,
            "engine_info": {
                "model_name": self.engine.model_name,
                "engine_type": self.engine.engine_type,
                "hardware": self.engine.hardware,
                "is_mock": getattr(self.engine, "is_mock", False)
            }
        }
