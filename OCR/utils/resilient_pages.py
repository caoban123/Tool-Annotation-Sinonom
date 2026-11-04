"""Bounded region recovery with explicit incomplete-page reporting."""
from collections import deque
import hashlib
import inspect
import json
import time
from pathlib import Path

from .regions import OCRRegionError, plan_regions, split_region


def recognize_page(engine, image, manager, source_id, page_number, output_dir,
                   reading_order='rtl_vertical', force=False, max_attempts=40,
                   page_timeout=300, max_depth=3):
    started = time.monotonic()
    planned = plan_regions(image, reading_order)
    # Process narrow outer borders last so a noisy spine cannot consume the
    # page budget before its actual text. Restore reading order below.
    planned.sort(key=lambda b: int(reading_order == 'rtl_vertical' and
                 (b[0] == 0 or b[2] == image.width) and b[2] - b[0] < image.width * .08))
    queue = deque((box, 0) for box in planned)
    boxes, errors = [], []
    attempts = 0
    output_dir = Path(output_dir)
    while queue:
        bbox, depth = queue.popleft()
        identity = hashlib.sha256(json.dumps(['regions-v1', source_id, bbox]).encode()).hexdigest()
        key = manager.compute_page_key(identity, page_number, engine.model_name)
        cached = None if force else manager.get_cached_result(key)
        if cached is not None:
            boxes.extend(cached['boxes'])
            continue
        failure = None
        if attempts >= max_attempts or time.monotonic() - started >= page_timeout:
            failure = RuntimeError('Đã tới giới hạn thời gian/số lần thử của trang')
        else:
            attempts += 1
            print(f'[OCR] Trang {page_number}: vùng {bbox}, lần {attempts}', flush=True)
            try:
                with image.crop(bbox) as crop:
                    parameters = inspect.signature(engine.recognize_image).parameters
                    supports_progress = 'show_progress' in parameters or any(
                        p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values())
                    detected = engine.recognize_image(crop, show_progress=False) if supports_progress else engine.recognize_image(crop)
                text = '\n'.join(b['text'] for b in detected if b.get('text'))
                region_boxes = [{'bbox': list(bbox), 'bbox_type': 'crop', 'text': text,
                                 'confidence': None}]
                data = dict(text=text, boxes=region_boxes, is_mock=getattr(engine, 'is_mock', False),
                            engine_type=engine.engine_type)
                if not manager.save_cached_result(key, data):
                    raise RuntimeError('Không lưu được checkpoint vùng ảnh')
                boxes.extend(region_boxes)
                continue
            except Exception as exc:
                failure = exc
                recoverable = isinstance(exc, OCRRegionError) or 'out of memory' in str(exc).lower()
                if recoverable and depth < max_depth and attempts < max_attempts:
                    children = split_region(image, bbox, reading_order)
                    if children:
                        # The children replace the failed parent in reading order.
                        queue.extendleft(reversed([(child, depth + 1) for child in children]))
                        print(f'[OCR] Trang {page_number}: chia vùng nhỏ hơn ({exc})', flush=True)
                        if 'out of memory' in str(exc).lower():
                            import gc
                            failure = None
                            exc.__traceback__ = None
                            gc.collect()
                            if engine.hardware.startswith('cuda'):
                                import torch
                                torch.cuda.empty_cache()
                        continue
        directory = output_dir / 'needs_review'
        directory.mkdir(parents=True, exist_ok=True)
        name = f'page_{page_number:04d}_{identity[:8]}_{bbox[0]}_{bbox[1]}_{bbox[2]}_{bbox[3]}.png'
        with image.crop(bbox) as crop:
            crop.thumbnail((1200, 1200))
            crop.save(directory / name)
        errors.append({'page_number': page_number, 'bbox': list(bbox),
                       'error': str(failure), 'image': f'needs_review/{name}'})
        print(f'[OCR] CẦN KIỂM TRA trang {page_number}, vùng {bbox}: {failure}', flush=True)
    boxes.sort(key=(lambda b: (-b['bbox'][2], b['bbox'][1])) if reading_order == 'rtl_vertical'
               else (lambda b: (b['bbox'][1], b['bbox'][0])))
    text = '\n'.join(b['text'] for b in boxes if b['text'])
    return dict(page_number=page_number, text=text, boxes=boxes, errors=errors,
                status='needs_review' if errors else 'complete', is_cached=False,
                inference_time_sec=round(time.monotonic() - started, 3),
                is_blank=not text.strip() and not errors, is_mock=getattr(engine, 'is_mock', False),
                engine_type=engine.engine_type, hardware=engine.hardware)
