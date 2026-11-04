"""Streaming PDF/image OCR entry point used by the portable Han notebook."""
import argparse
import hashlib
import json
import platform
import sys
import zipfile
from pathlib import Path
from PIL import Image, ImageOps
from OCR.utils.checkpoints import OCRCheckpointManager
from OCR.utils.export_text import export_ocr_result
from OCR.utils.ocr_pipeline import OCRPipeline, PaddleVLOCREngine
from OCR.utils.render_pdf import render_pdf_to_images


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
    if config.get('split_spread', False) and config.get('reading_order', 'rtl_vertical') != 'rtl_vertical':
        raise ValueError('split_spread danh cho sach doc: nua phai truoc nua trai')
    output_dir = Path(config['output_dir']).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ('han.txt', 'han_metadata.json', 'han_ocr.zip'):
        (output_dir / name).unlink(missing_ok=True)
    digest = source_digest(path)
    cache_config = {k: config.get(k) for k in (
        'model_id', 'model_revision', 'max_new_tokens', 'max_pixels', 'render_scale',
        'reading_order', 'split_spread', 'use_gpu')}
    cache_config['pipeline_version'] = 2
    # Retry ceiling changes only failed/truncated generations, which are never
    # cached. Keep existing completed-page keys so a retry can resume page 27
    # without recomputing pages 1-26.
    signature = hashlib.sha256(json.dumps(cache_config, sort_keys=True).encode()).hexdigest()
    checkpoint_dir = Path(config.get('checkpoint_dir') or output_dir / 'checkpoints')
    manager = OCRCheckpointManager(str(checkpoint_dir))
    pages = []
    pipeline = None
    for number in range(start, end + 1):
        key = manager.compute_page_key(digest, number, config['model_id'], signature)
        cached = None if config.get('force_reprocess') else manager.get_cached_result(key)
        if cached is not None:
            pages.append(dict(cached, is_cached=True))
            print(f'Trang {number}/{end}: cache', flush=True)
            continue
        if engine is None:
            print(f"[OCR] Đang nạp model {config['model_id']} (use_gpu={config.get('use_gpu', True)})...", flush=True)
            engine = PaddleVLOCREngine(
                model_id=config['model_id'], use_gpu=config.get('use_gpu', True),
                max_new_tokens=config.get('max_new_tokens', 4096),
                max_pixels=config.get('max_pixels', 1003520), revision=config.get('model_revision'),
                max_retry_tokens=config.get('max_retry_tokens', 16384))
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
            try:
                for index, region in enumerate(regions):
                    result = pipeline.process_images([region], source_id=f'{digest}:{signature}:{index}',
                        start_page=number, force_reprocess=config.get('force_reprocess', False))
                    region_pages.extend(result['pages'])
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
            if not manager.save_cached_result(key, page):
                raise RuntimeError(f'Khong luu duoc checkpoint trang {number}')
            pages.append(page)
            print(f"Trang {number}/{end}: {len(page['text'])} ky tu", flush=True)
        finally:
            image.close()
    result = {
        'source_id': path.name, 'source_sha256': digest,
        'start_page': start, 'end_page': end, 'total_pages': len(pages), 'pages': pages,
        'full_text': '\n'.join(p['text'] for p in pages),
        'reading_order': config.get('reading_order', 'rtl_vertical'),
        'engine_info': {'model_name': config['model_id'], 'is_mock': False,
                       'engine_type': pages[0]['engine_type'], 'hardware': pages[0]['hardware']},
        'config': config, 'python': sys.version, 'platform': platform.platform(),
        'limitations': 'VLM OCR tra text; khong co bounding box dong hay confidence. Can soat ban scan.'}
    from importlib.metadata import version
    result['packages'] = {}
    for package in ('torch', 'transformers', 'pypdfium2', 'pillow'):
        try:
            result['packages'][package] = version(package)
        except Exception:
            result['packages'][package] = 'not installed'
    export_ocr_result(result, output_dir / 'han.txt', output_dir / 'han_metadata.json')
    with zipfile.ZipFile(output_dir / 'han_ocr.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('han.txt', 'han_metadata.json'):
            archive.write(output_dir / name, name)
        for checkpoint in checkpoint_dir.glob('*.json'):
            archive.write(checkpoint, f'checkpoints/{checkpoint.name}')
    print(f"Hoan tat: {output_dir / 'han_ocr.zip'}", flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    run(json.loads(Path(args.config).read_text(encoding='utf-8')))
