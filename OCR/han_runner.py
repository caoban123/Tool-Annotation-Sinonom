"""Streaming PDF/image OCR entry point used by the portable Han notebook."""
import argparse
import hashlib
import json
import platform
import sys
import time
import zipfile
from pathlib import Path
from PIL import Image, ImageOps
from OCR.utils.checkpoints import OCRCheckpointManager
from OCR.utils.export_text import export_ocr_result
from OCR.utils.ocr_pipeline import OCRPipeline, PaddleVLOCREngine
from OCR.utils.qwen_engine import QwenVLOCREngine, is_qwen_model
from OCR.utils.render_pdf import render_pdf_to_images
from OCR.utils.resilient_pages import recognize_page
from OCR.utils.notebook_process import emit_progress


def source_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def page_count(path):
    if path.suffix.lower() == '.pdf':
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(str(path)) as pdf:
            return len(pdf)
    with Image.open(path) as image:
        return getattr(image, 'n_frames', 1)


def load_page(path, number, scale):
    if path.suffix.lower() == '.pdf':
        return render_pdf_to_images(str(path), start_page=number, end_page=number, scale=scale)[0]
    with Image.open(path) as image:
        image.seek(number - 1)
        return ImageOps.exif_transpose(image).convert('RGB').copy()


def run(config, engine=None):
    path = Path(config['input_path']).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Khong thay tai lieu: {path}')
    count = page_count(path)
    print(f'[OCR] Input: {path} | {count} trang | Python {platform.python_version()}', flush=True)
    start = config.get('start_page', 1)
    end = config.get('end_page') or count
    if not 1 <= start <= end <= count:
        raise ValueError(f'Khoang trang phai thuoc 1..{count}, nhan {start}..{end}')
    reverse_pages = config.get('reverse_pages', False)
    if type(reverse_pages) is not bool:
        raise ValueError('reverse_pages must be a boolean')
    emit_progress('start', total=end - start + 1)
    if config.get('split_spread', False) and config.get('reading_order', 'rtl_vertical') != 'rtl_vertical':
        raise ValueError('split_spread danh cho sach doc: nua phai truoc nua trai')
    output_dir = Path(config['output_dir']).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ('han.txt', 'han.partial.txt', 'han_metadata.json', 'han_ocr.zip'):
        (output_dir / name).unlink(missing_ok=True)
    digest = source_digest(path)
    qwen = is_qwen_model(config['model_id'])
    cache_config = {k: config.get(k) for k in (
        'model_id', 'model_revision', 'max_new_tokens', 'max_pixels', 'render_scale',
        'reading_order', 'split_spread', 'use_gpu')}
    cache_config['pipeline_version'] = 2
    if qwen:
        cache_config.update(qwen_adapter_version=1,
                            load_in_4bit=config.get('qwen_load_in_4bit', True))
    # Retry ceiling changes only failed/truncated generations, which are never
    # cached. Keep existing completed-page keys so a retry can resume page 27
    # without recomputing pages 1-26.
    signature = hashlib.sha256(json.dumps(cache_config, sort_keys=True).encode()).hexdigest()
    checkpoint_dir = Path(config.get('checkpoint_dir') or output_dir / 'checkpoints')
    manager = OCRCheckpointManager(str(checkpoint_dir))
    pages = []
    def report_progress(event, **values):
        emit_progress(event, total=end - start + 1, processed=len(pages),
                      cached=sum(bool(p.get('is_cached')) for p in pages),
                      review_pages=sum(bool(p.get('errors')) for p in pages),
                      error_regions=sum(len(p.get('errors', [])) for p in pages), **values)
    pipeline = None
    page_numbers = range(end, start - 1, -1) if reverse_pages else range(start, end + 1)
    for number in page_numbers:
        key = manager.compute_page_key(digest, number, config['model_id'], signature)
        cached = None if config.get('force_reprocess') else manager.get_cached_result(key)
        if cached is not None:
            pages.append(dict(cached, is_cached=True))
            (output_dir / 'han.partial.txt').write_text('\n'.join(p['text'] for p in pages), encoding='utf-8')
            print(f'Trang {number}/{end}: cache', flush=True)
            report_progress('page_done', page=number, region=None)
            continue
        report_progress('page_start', page=number, region=None)
        if engine is None:
            report_progress('model_loading', page=number)
            print(f"[OCR] Đang nạp model {config['model_id']} (use_gpu={config.get('use_gpu', True)})...", flush=True)
            engine_class = QwenVLOCREngine if qwen else PaddleVLOCREngine
            model_options = dict(load_in_4bit=config.get('qwen_load_in_4bit', True),
                                 reading_order=config.get('reading_order', 'rtl_vertical')) if qwen else {}
            engine = engine_class(
                model_id=config['model_id'], use_gpu=config.get('use_gpu', True),
                max_new_tokens=config.get('max_new_tokens', 4096),
                max_pixels=config.get('max_pixels', 1003520), revision=config.get('model_revision'),
                # Stop a failed crop promptly and split it instead of escalating
                # full-page generations to 16K tokens for another fifteen minutes.
                max_retry_tokens=config.get('max_new_tokens', 4096),
                region_timeout=config.get('region_timeout', 90), **model_options)
        if pipeline is None:
            pipeline = OCRPipeline(engine, OCRCheckpointManager(str(output_dir / 'region_cache')),
                                   config.get('reading_order', 'rtl_vertical'))
        image = load_page(path, number, config.get('render_scale', 2.0))
        print(f'[OCR] Nhận dạng trang {number}/{end}, ảnh {image.width}x{image.height}', flush=True)
        try:
            regions = [image]
            if config.get('split_spread'):
                middle = image.width // 2
                regions = [image.crop((middle, 0, image.width, image.height)),
                           image.crop((0, 0, middle, image.height))]
            region_pages = []
            page_started = time.monotonic()
            try:
                for index, region in enumerate(regions):
                    region_pages.append(recognize_page(
                        engine, region, pipeline.checkpoints, f'{digest}:{signature}:{index}', number,
                        output_dir, config.get('reading_order', 'rtl_vertical'),
                        force=config.get('force_reprocess', False),
                        max_attempts=config.get('max_region_attempts', 40),
                        page_timeout=max(0, config.get('page_timeout', 300) - (time.monotonic() - page_started))))
            finally:
                for region in regions:
                    if region is not image:
                        region.close()
            page = dict(region_pages[0])
            page['text'] = '\n'.join(p['text'] for p in region_pages)
            page['regions'] = region_pages
            page['boxes'] = []  # Region-local coordinates are not page detections.
            page['is_blank'] = not page['text'].strip()
            page['inference_time_sec'] = sum(p['inference_time_sec'] for p in region_pages)
            page['source_sha256'] = digest
            page['recovery_version'] = 3
            page['errors'] = [error for p in region_pages for error in p.get('errors', [])]
            page['status'] = 'needs_review' if page['errors'] else 'complete'
            page['is_blank'] = not page['text'].strip() and not page['errors']
            if page['errors'] and not config.get('continue_on_error', True):
                raise RuntimeError(page['errors'][0]['error'])
            if not page['errors'] and not manager.save_cached_result(key, page):
                raise RuntimeError(f'Khong luu duoc checkpoint trang {number}')
            pages.append(page)
            (output_dir / 'han.partial.txt').write_text('\n'.join(p['text'] for p in pages), encoding='utf-8')
            (output_dir / 'progress.json').write_text(json.dumps({
                'last_page': number, 'pages_processed': len(pages),
                'needs_review': [p['page_number'] for p in pages if p.get('errors')]
            }, ensure_ascii=False, indent=2), encoding='utf-8')
            (output_dir / 'error_report.json').write_text(json.dumps([
                error for saved_page in pages for error in saved_page.get('errors', [])
            ], ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"Trang {number}/{end}: {len(page['text'])} ky tu", flush=True)
            report_progress('page_done', page=number, region=None)
        finally:
            image.close()
    result = {
        'source_id': path.name, 'source_sha256': digest,
        'start_page': start, 'end_page': end, 'total_pages': len(pages), 'pages': pages,
        'reverse_pages': reverse_pages,
        'full_text': '\n'.join(p['text'] for p in pages),
        'reading_order': config.get('reading_order', 'rtl_vertical'),
        'engine_info': {'model_name': config['model_id'], 'is_mock': False,
                       'engine_type': pages[0]['engine_type'], 'hardware': pages[0]['hardware']},
        'config': config, 'python': sys.version, 'platform': platform.platform(),
        'limitations': 'VLM OCR tra text; khong co bounding box dong hay confidence. Can soat ban scan.'}
    result['errors'] = [error for page in pages for error in page.get('errors', [])]
    result['complete'] = not result['errors']
    result['status'] = 'complete' if result['complete'] else 'needs_review'
    result['text_file'] = 'han.txt' if result['complete'] else 'han.partial.txt'
    report_progress('export', region=None)
    from importlib.metadata import version
    result['packages'] = {}
    for package in ('torch', 'transformers', 'pypdfium2', 'pillow', 'accelerate', 'bitsandbytes'):
        try:
            result['packages'][package] = version(package)
        except Exception:
            result['packages'][package] = 'not installed'
    if result['complete']:
        export_ocr_result(result, output_dir / 'han.txt', output_dir / 'han_metadata.json')
        (output_dir / 'han.partial.txt').unlink(missing_ok=True)
    else:
        (output_dir / 'han.partial.txt').write_text(result['full_text'], encoding='utf-8')
        (output_dir / 'han_metadata.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (output_dir / 'error_report.json').write_text(json.dumps(result['errors'], ensure_ascii=False, indent=2), encoding='utf-8')
    with zipfile.ZipFile(output_dir / 'han_ocr.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in (result['text_file'], 'han_metadata.json', 'error_report.json'):
            archive.write(output_dir / name, name)
        for failure in result['errors']:
            image_path = output_dir / failure['image']
            archive.write(image_path, failure['image'])
        for checkpoint in checkpoint_dir.glob('*.json'):
            archive.write(checkpoint, f'checkpoints/{checkpoint.name}')
        for checkpoint in (output_dir / 'region_cache').glob('*.json'):
            archive.write(checkpoint, f'region_cache/{checkpoint.name}')
    print(f"[OCR] {result['status']}: {len(result['errors'])} vùng cần kiểm tra. {output_dir / 'han_ocr.zip'}", flush=True)
    report_progress('finish', complete=result['complete'], region=None)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    run(json.loads(Path(args.config).read_text(encoding='utf-8')))
