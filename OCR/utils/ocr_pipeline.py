import time
import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
from PIL import Image

# Disable PIR executor and oneDNN flags in PaddlePaddle 3.x if present
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from .checkpoints import OCRCheckpointManager
from .page_order import sort_bounding_boxes

logger = logging.getLogger("OCR-Pipeline")

class PaddleVLOCREngine:
    """
    Vision-Language OCR Engine utilizing PaddleOCR-VL (0.9B parameter VLM)
    via Hugging Face transformers.
    Excels at ancient Sino-Nom documents, complex layouts, and semantic reading order.
    """
    def __init__(
        self,
        model_id: str = "PaddlePaddle/PaddleOCR-VL-1.6",
        use_gpu: bool = True
    ):
        self.model_name = "PaddleOCR-VL-1.6" if "1.6" in model_id else "PaddleOCR-VL"
        self.model_id = model_id
        self.use_gpu = use_gpu
        self.hardware = "cuda" if use_gpu else "cpu"
        self.processor = None
        self.model = None
        self.is_mock = False
        self._init_engine()

    @classmethod
    def _patch_transformers_compatibility(cls):
        """
        Targeted compatibility shims for PaddleOCR-VL remote code across
        modern Hugging Face Transformers releases.
        """
        import sys

        # 1. Patch rope_parameters attribute on PretrainedConfig for transformers 4.48+
        try:
            import transformers.configuration_utils
            if not hasattr(transformers.configuration_utils.PretrainedConfig, "rope_parameters"):
                transformers.configuration_utils.PretrainedConfig.rope_parameters = None
        except Exception:
            pass

        # 2. Bridge create_causal_mask between masking_utils and modeling_attn_mask_utils
        try:
            import transformers.modeling_attn_mask_utils as _mamu
        except Exception:
            _mamu = None

        try:
            import transformers.masking_utils as _mu
        except ImportError:
            if _mamu is not None:
                sys.modules['transformers.masking_utils'] = _mamu
            _mu = sys.modules.get('transformers.masking_utils')
        except Exception:
            _mu = None

        causal_mask_fn = None
        if _mu is not None and hasattr(_mu, "create_causal_mask"):
            causal_mask_fn = getattr(_mu, "create_causal_mask")
        elif _mamu is not None and hasattr(_mamu, "create_causal_mask"):
            causal_mask_fn = getattr(_mamu, "create_causal_mask")

        if causal_mask_fn is not None:
            if _mamu is not None and not hasattr(_mamu, "create_causal_mask"):
                setattr(_mamu, "create_causal_mask", causal_mask_fn)
            if _mu is not None and not hasattr(_mu, "create_causal_mask"):
                setattr(_mu, "create_causal_mask", causal_mask_fn)

        # 3. Patch ROPE_INIT_FUNCTIONS['default'] if needed
        try:
            import transformers.modeling_rope_utils as _mru
            if hasattr(_mru, "ROPE_INIT_FUNCTIONS") and isinstance(_mru.ROPE_INIT_FUNCTIONS, dict):
                if "default" not in _mru.ROPE_INIT_FUNCTIONS:
                    default_fn = getattr(_mru, "_compute_default_rope_parameters", None) or getattr(_mru, "compute_default_rope_parameters", None)
                    if default_fn is None:
                        import torch
                        def default_fn(config, device=None, seq_len=None, **kwargs):
                            dim = getattr(config, "head_dim", getattr(config, "hidden_size", 768) // getattr(config, "num_attention_heads", 12))
                            base = getattr(config, "rope_theta", 10000.0)
                            inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2, dtype=torch.int64).float().to(device) / dim))
                            return inv_freq, 1.0
                    _mru.ROPE_INIT_FUNCTIONS["default"] = default_fn
        except Exception:
            pass

        # 4. Patch _preprocess_mask_arguments for 3D mrope position_ids
        try:
            import transformers.masking_utils as _t_mu
            if hasattr(_t_mu, "_preprocess_mask_arguments"):
                _orig_pma = _t_mu._preprocess_mask_arguments
                if not getattr(_orig_pma, "_is_paddle_3d_patched", False):
                    import functools
                    @functools.wraps(_orig_pma)
                    def _safe_pma(*args, **kwargs):
                        import torch
                        if "position_ids" in kwargs and kwargs["position_ids"] is not None:
                            if getattr(kwargs["position_ids"], "ndim", 0) > 2:
                                kwargs["position_ids"] = None
                        new_args = []
                        for a in args:
                            if getattr(a, "ndim", 0) > 2 and getattr(a, "dtype", None) in (torch.int64, torch.int32):
                                new_args.append(None)
                            else:
                                new_args.append(a)
                        return _orig_pma(*new_args, **kwargs)
                    _safe_pma._is_paddle_3d_patched = True
                    _t_mu._preprocess_mask_arguments = _safe_pma
        except Exception:
            pass

        # 4. Patch all causal masks to safely strip unsupported cache_position
        try:
            cls._patch_all_causal_masks()
        except Exception:
            pass

    @staticmethod
    def _patch_causal_mask_in_target(target: Any):
        """Safely wraps create_causal_mask in a module or class to strip unsupported cache_position."""
        if hasattr(target, "create_causal_mask"):
            fn = getattr(target, "create_causal_mask")
            if not getattr(fn, "_is_paddle_patched", False):
                try:
                    import inspect
                    import functools
                    sig = inspect.signature(fn)
                    has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                    accepts_cp = has_varkw or ("cache_position" in sig.parameters)
                    accepts_inputs = has_varkw or ("inputs_embeds" in sig.parameters)
                    accepts_input = has_varkw or ("input_embeds" in sig.parameters)

                    @functools.wraps(fn)
                    def _safe_create_causal_mask(*args, **kwargs):
                        import torch
                        if not accepts_cp:
                            kwargs.pop("cache_position", None)
                        if not accepts_inputs and accepts_input and "inputs_embeds" in kwargs:
                            kwargs["input_embeds"] = kwargs.pop("inputs_embeds")
                        elif not accepts_input and accepts_inputs and "input_embeds" in kwargs:
                            kwargs["inputs_embeds"] = kwargs.pop("input_embeds")
                        if "position_ids" in kwargs and kwargs["position_ids"] is not None:
                            if getattr(kwargs["position_ids"], "ndim", 0) > 2:
                                kwargs["position_ids"] = None
                        new_args = []
                        for a in args:
                            if getattr(a, "ndim", 0) > 2 and getattr(a, "dtype", None) in (torch.int64, torch.int32):
                                new_args.append(None)
                            else:
                                new_args.append(a)
                        return fn(*new_args, **kwargs)

                    _safe_create_causal_mask._is_paddle_patched = True
                    setattr(target, "create_causal_mask", _safe_create_causal_mask)
                except Exception:
                    pass

    @classmethod
    def _patch_all_causal_masks(cls):
        """Scans transformers modules and remote code modules to patch create_causal_mask and prepare_inputs_for_generation."""
        import sys
        for mod_name in ['transformers.masking_utils', 'transformers.modeling_attn_mask_utils']:
            try:
                if mod_name in sys.modules:
                    cls._patch_causal_mask_in_target(sys.modules[mod_name])
                else:
                    import importlib
                    m = importlib.import_module(mod_name)
                    cls._patch_causal_mask_in_target(m)
            except Exception:
                pass

        for name, m in list(sys.modules.items()):
            if "paddleocr" in name.lower() or "modeling_" in name.lower():
                cls._patch_causal_mask_in_target(m)
                cls._patch_prepare_inputs_for_generation(m)
                for attr_name in dir(m):
                    try:
                        val = getattr(m, attr_name)
                        if isinstance(val, type):
                            cls._patch_prepare_inputs_for_generation(val)
                    except Exception:
                        pass

    @staticmethod
    def _patch_prepare_inputs_for_generation(target: Any):
        """
        Patches prepare_inputs_for_generation to prevent TypeError: 'NoneType' object is not subscriptable
        when modern transformers (v5.x) passes cache_position=None or omits it.
        Safely unwinds any previously wrapped functions to prevent RecursionError.
        """
        if hasattr(target, "prepare_inputs_for_generation"):
            fn = getattr(target, "_unwrapped_prep", None)
            if fn is None:
                fn = getattr(target, "prepare_inputs_for_generation")
                while hasattr(fn, "__wrapped__"):
                    fn = fn.__wrapped__
                setattr(target, "_unwrapped_prep", fn)

            try:
                import inspect
                import functools
                import torch

                sig = inspect.signature(fn)
                params = list(sig.parameters.keys())
                cp_idx = params.index("cache_position") if "cache_position" in params else -1
                pkv_idx = params.index("past_key_values") if "past_key_values" in params else -1

                @functools.wraps(fn)
                def _safe_prepare(*args, **kwargs):
                    dev = getattr(target, "device", "cpu")
                    if not isinstance(dev, (str, torch.device)):
                        dev = "cpu"

                    pkv = kwargs.get("past_key_values")
                    if pkv is None and pkv_idx >= 0 and len(args) > pkv_idx:
                        pkv = args[pkv_idx]

                    step_idx = 1 if pkv else 0
                    cp_tensor = torch.tensor([step_idx], device=dev)

                    if "cache_position" in kwargs:
                        if kwargs["cache_position"] is None:
                            kwargs["cache_position"] = cp_tensor
                    elif cp_idx >= 0 and len(args) > cp_idx:
                        if args[cp_idx] is None:
                            args_list = list(args)
                            args_list[cp_idx] = cp_tensor
                            args = tuple(args_list)
                    else:
                        kwargs["cache_position"] = cp_tensor

                    return fn(*args, **kwargs)

                _safe_prepare._is_paddle_cp_patched = True
                setattr(target, "prepare_inputs_for_generation", _safe_prepare)
            except Exception:
                pass

    def _load_model_instance(self, model_target: str, device: str, dtype: Any) -> tuple:
        self._patch_transformers_compatibility()
        from transformers import AutoConfig, AutoModelForCausalLM, AutoModel, AutoProcessor

        config = AutoConfig.from_pretrained(model_target, trust_remote_code=True)
        if hasattr(config, "vision_config") and not hasattr(config.vision_config, "rope_parameters"):
            setattr(config.vision_config, "rope_parameters", None)
        if hasattr(config, "text_config") and not hasattr(config.text_config, "rope_parameters"):
            setattr(config.text_config, "rope_parameters", None)

        processor = AutoProcessor.from_pretrained(model_target, trust_remote_code=True)

        load_kwargs = {
            "config": config,
            "device_map": "auto" if device == "cuda" else None,
            "trust_remote_code": True
        }

        model = None
        last_err = None
        for model_cls in [AutoModelForCausalLM, AutoModel]:
            try:
                try:
                    model = model_cls.from_pretrained(model_target, dtype=dtype, **load_kwargs)
                except TypeError:
                    model = model_cls.from_pretrained(model_target, torch_dtype=dtype, **load_kwargs)
                if model is not None:
                    break
            except Exception as e_cls:
                last_err = e_cls
                continue

        if model is None:
            raise RuntimeError(f"Không thể khởi tạo {model_target} qua AutoModelForCausalLM / AutoModel: {last_err}")

        # Disable strict generation parameter validation on multimodal VLM
        model._validate_model_kwargs = lambda *a, **kw: None
        self._patch_prepare_inputs_for_generation(model)
        self._patch_prepare_inputs_for_generation(model.__class__)

        # Re-patch any dynamically imported modules from the model repo
        self._patch_all_causal_masks()

        return processor, model

    def _init_engine(self):
        self._patch_transformers_compatibility()
        import torch

        device = "cuda" if (self.use_gpu and torch.cuda.is_available()) else "cpu"
        self.hardware = device

        # Determine precision based on hardware capabilities (Tesla T4 does not support BF16)
        if device == "cuda":
            if hasattr(torch.cuda, "is_bf16_supported") and torch.cuda.is_bf16_supported():
                dtype = torch.bfloat16
            else:
                dtype = torch.float16
        else:
            dtype = torch.float32

        print(f"[OCR-VL Engine] Đang tải mô hình Vision-Language '{self.model_id}' (device={device}, dtype={dtype})...")
        try:
            self.processor, self.model = self._load_model_instance(self.model_id, device, dtype)
            if device == "cpu" and self.model is not None:
                self.model = self.model.to("cpu")

            self.engine_type = f"paddleocr_vl (model={self.model_id}, device={device}, dtype={dtype})"
            self.is_mock = False
            print(f"[OCR-VL Engine] ✓ Đã nạp thành công mô hình Vision-Language thật: {self.engine_type}")
        except Exception as e:
            self.processor = None
            self.model = None
            self.is_mock = False
            # STRICT ERROR ENFORCEMENT: Never fallback to mock in production!
            raise RuntimeError(
                f"Không thể khởi tạo mô hình Vision-Language thật '{self.model_id}': {e}\n"
                f"Yêu cầu môi trường GPU và thư viện tương thích 'transformers>=5.0.0'."
            ) from e

    def recognize_image(self, image: Image.Image, show_progress: bool = True) -> List[Dict[str, Any]]:
        """Recognizes text lines from an image using the real Vision-Language Model."""
        if self.model is None or self.processor is None:
            raise RuntimeError("Mô hình PaddleOCR-VL chưa được nạp. Không thể thực hiện suy luận.")

        w, h = image.size
        import torch
        img_rgb = image.convert("RGB")

        # 1. Tối ưu kích thước ảnh (tránh bùng nổ token thị giác làm đơ hoặc treo GPU)
        max_edge = 1536
        if max(img_rgb.size) > max_edge:
            ratio = max_edge / max(img_rgb.size)
            new_size = (int(img_rgb.width * ratio), int(img_rgb.height * ratio))
            img_rgb = img_rgb.resize(new_size, Image.Resampling.LANCZOS)
            if show_progress:
                print(f"[OCR-VL] Đã tối ưu kích thước ảnh từ ({w}, {h}) -> {img_rgb.size} để tăng tốc GPU.")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": img_rgb},
                    {"type": "text", "text": "OCR:"}
                ]
            }
        ]

        # 2. Xây dựng prompt chuẩn (tokenize=False) để processor xử lý trọn vẹn cả text và ảnh
        if hasattr(self.processor, "apply_chat_template"):
            try:
                text_prompt = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            except Exception:
                text_prompt = "OCR:"
        else:
            text_prompt = "OCR:"

        try:
            inputs = self.processor(text=[text_prompt], images=[img_rgb], return_tensors="pt").to(self.model.device)
        except Exception:
            try:
                inputs = self.processor(images=img_rgb, text=text_prompt, return_tensors="pt").to(self.model.device)
            except Exception:
                inputs = self.processor(text=[text_prompt], return_tensors="pt").to(self.model.device)

        if inputs is not None and "input_ids" in inputs:
            inputs.pop("cache_position", None)
            if "attention_mask" not in inputs:
                inputs["attention_mask"] = torch.ones_like(inputs["input_ids"])

        # 3. Vá tương thích động
        self._patch_all_causal_masks()
        self._patch_prepare_inputs_for_generation(self.model)
        self._patch_prepare_inputs_for_generation(self.model.__class__)

        # 4. Streamer hiển thị chữ trực tiếp theo thời gian thực (chống cảm giác chờ đợi)
        streamer = None
        if show_progress:
            try:
                from transformers import TextStreamer
                tokenizer = getattr(self.processor, "tokenizer", None)
                if tokenizer is not None:
                    streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
                print("[OCR-VL] 🚀 Bắt đầu suy luận mô hình (Streaming văn bản trực tiếp)...")
            except Exception:
                pass

        prompt_len = inputs["input_ids"].shape[-1] if (inputs is not None and "input_ids" in inputs) else 0
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=1024,
                do_sample=False,
                repetition_penalty=1.1,
                streamer=streamer
            )

        generated_text = ""
        if outputs is not None and len(outputs) > 0:
            if hasattr(self.processor, "decode"):
                generated_text = self.processor.decode(outputs[0][prompt_len:], skip_special_tokens=True).strip()
            elif hasattr(self.processor, "batch_decode"):
                decoded_list = self.processor.batch_decode(outputs, skip_special_tokens=True)
                if decoded_list and isinstance(decoded_list, (list, tuple)):
                    generated_text = str(decoded_list[0]).strip()

        if "assistant\n" in generated_text:
            generated_text = generated_text.split("assistant\n", 1)[-1].strip()
        elif generated_text.startswith("OCR:"):
            generated_text = generated_text[4:].strip()

        lines = [line.strip() for line in generated_text.splitlines() if line.strip()]
        if not lines and generated_text:
            lines = [generated_text]

        if not lines:
            return []

        boxes = []
        line_h = max(20, h // max(1, len(lines)))
        for idx, line in enumerate(lines):
            boxes.append({
                "bbox": [10, idx * line_h, w - 10, (idx + 1) * line_h],
                "text": line,
                "confidence": 0.99
            })
        return boxes

# Auto-apply compatibility patch on module import
try:
    PaddleVLOCREngine._patch_transformers_compatibility()
except Exception:
    pass

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
