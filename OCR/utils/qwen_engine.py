"""Optional Qwen3-VL Han transcription through native Transformers."""
import json
from pathlib import Path

from .ocr_pipeline import PaddleVLOCREngine


def is_qwen_model(model_id):
    """Recognize the public model and local copies with a native Qwen3-VL config."""
    path = Path(model_id)
    if path.is_dir():
        config = json.loads((path / 'config.json').read_text(encoding='utf-8'))
        return config.get('model_type') == 'qwen3_vl'
    return 'qwen3-vl' in str(model_id).lower()


class QwenVLOCREngine(PaddleVLOCREngine):
    def __init__(self, model_id='Qwen/Qwen3-VL-8B-Instruct', use_gpu=True,
                 load_in_4bit=True, reading_order='rtl_vertical', **kwargs):
        if load_in_4bit and not use_gpu:
            raise ValueError('Qwen 4-bit requires CUDA here; select USE_GPU=True or QWEN_LOAD_IN_4BIT=False')
        if reading_order not in ('rtl_vertical', 'ltr_horizontal'):
            raise ValueError('Qwen reading_order must be rtl_vertical or ltr_horizontal')
        if kwargs.get('max_pixels', 1003520) < 1024:
            raise ValueError('Qwen MAX_PIXELS must be >= 1024')
        self.load_in_4bit = load_in_4bit
        self.reading_order = reading_order
        super().__init__(model_id=model_id, use_gpu=use_gpu, **kwargs)

    def _init_engine(self):
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
        from transformers.utils import logging as hf_logging
        hf_logging.disable_progress_bar()
        if self.use_gpu and not torch.cuda.is_available():
            raise RuntimeError('Qwen requires the selected CUDA GPU; enable GPU in Colab/Kaggle')
        self.hardware = 'cuda' if self.use_gpu else 'cpu'
        native_bf16 = self.use_gpu and torch.cuda.get_device_capability(0)[0] >= 8 and torch.cuda.is_bf16_supported()
        dtype = (torch.bfloat16 if native_bf16 else torch.float16) if self.use_gpu else torch.float32
        revision = {'revision': self.revision} if self.revision else {}
        self.processor = AutoProcessor.from_pretrained(self.model_id, trust_remote_code=False, **revision)
        options = dict(dtype=dtype, attn_implementation='eager', trust_remote_code=False, **revision)
        if self.load_in_4bit:
            # Never cast/move a bitsandbytes model after loading its quantized weights.
            options.update(device_map={'': 0}, quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=dtype))
        self.model = AutoModelForImageTextToText.from_pretrained(self.model_id, **options)
        if not self.load_in_4bit:
            self.model = self.model.to(device=self.hardware, dtype=dtype)
        self.model.eval()
        mode = 'NF4 4-bit' if self.load_in_4bit else str(dtype)
        self.engine_type = f'transformers_qwen3_vl ({self.model_id}, {mode})'
        print(f'[OCR] Qwen ready: {self.hardware}, {mode}; max pixels={self.max_pixels}', flush=True)

    def _prepare_inputs(self, image):
        order = ('Read each vertical column from top to bottom, and columns from right to left.'
                 if self.reading_order == 'rtl_vertical' else
                 'Read horizontal lines from left to right, and lines from top to bottom.')
        prompt = ('Transcribe only the text actually visible in this image of a Chinese document. '
                  + order + ' Preserve Traditional Chinese, rare characters and character variants as printed. '
                  'Do not translate, summarize, explain, modernize, or convert to Simplified Chinese. '
                  'Do not add punctuation absent from the image or invent missing text. '
                  'Output only the transcription, without Markdown or introductory text.')
        messages = [{'role': 'user', 'content': [
            {'type': 'image', 'image': image}, {'type': 'text', 'text': prompt}]}]
        return self.processor.apply_chat_template(messages, tokenize=True,
            add_generation_prompt=True, return_dict=True, return_tensors='pt',
            images_kwargs={'size': {'shortest_edge': min(65536, self.max_pixels),
                                    'longest_edge': self.max_pixels}})
