"""Stream Vietnamese OCR pages with resumable cache and explicit partial output."""
import argparse
import hashlib
import json
import multiprocessing as mp
import math
from pathlib import Path
import time
import traceback
import zipfile
from PIL import Image, ImageOps
from OCR.batch_runner import text_basename
from OCR.utils.notebook_process import emit_progress
from OCR.utils.render_pdf import render_pdf_to_images
from Crawl.extractors.pdf_pages import route_page, ROUTING_VERSION


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def page_count(path):
    path = Path(path)
    if path.suffix.lower() == '.pdf':
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(str(path)) as document:
            return len(document)
    with Image.open(path) as image:
        return getattr(image, 'n_frames', 1)


def load_page(path, number, scale):
    if path.suffix.lower() == '.pdf':
        return render_pdf_to_images(path, start_page=number, end_page=number, scale=scale)[0]
    with Image.open(path) as image:
        image.seek(number - 1)
        return ImageOps.exif_transpose(image).convert('RGB').copy()


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def checkpoint_digest(page):
    return hashlib.sha256(json.dumps({k: v for k, v in page.items() if k != 'payload_sha256'},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _worker(connection, config):
    engine = None
    try:
        if config.get('ocr_backend', 'paddle') == 'paddle_vietocr':
            from OCR.utils.vietocr_engine import PaddleVietOCREngine
            engine = PaddleVietOCREngine(config)
        else:
            from OCR.utils.viet_engine import VietnameseOCREngine
            engine = VietnameseOCREngine(config)
        connection.send(('ready', engine.info))
        while True:
            image = connection.recv()
            if image is None:
                break
            try:
                connection.send(('ok', engine.recognize_image(image)))
            except Exception:
                connection.send(('error', traceback.format_exc()))
            finally:
                image.close()
    except EOFError:
        pass
    except Exception:
        connection.send(('error', traceback.format_exc()))
    finally:
        if engine is not None and hasattr(engine, 'close'):
            engine.close()
        connection.close()


class WorkerEngine:
    """Keep models loaded; a stuck native call can be killed without losing cache."""
    def __init__(self, config):
        context = mp.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_worker, args=(child, config), daemon=True)
        self.timeout = config.get('page_timeout', 120)
        self.process.start()
        child.close()
        try:
            self.info = self.receive(config.get('model_timeout', 600), 'ready')
        except BaseException:
            self.close()
            raise

    def receive(self, timeout, expected):
        if not self.connection.poll(timeout):
            self.close()
            raise TimeoutError(f'OCR worker exceeded {timeout}s')
        try:
            status, value = self.connection.recv()
        except EOFError as error:
            raise RuntimeError('OCR worker exited unexpectedly; see process log') from error
        if status != expected:
            raise RuntimeError(value)
        return value

    def recognize_image(self, image):
        self.connection.send(image)
        return self.receive(self.timeout, 'ok')

    def close(self):
        if self.process.is_alive():
            # The hybrid engine owns a separate Torch subprocess. Kill descendants
            # as well when a native Paddle/Torch operation exceeds the deadline.
            try:
                import psutil
                children = psutil.Process(self.process.pid).children(recursive=True)
                for child in reversed(children):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
            except ImportError:
                pass
            except psutil.NoSuchProcess:
                pass
            self.process.terminate()
            self.process.join(5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
        self.connection.close()


def run(config, engine=None):
    path = Path(config['input_path']).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    count = page_count(path)
    start, end = config.get('start_page', 1), config.get('end_page')
    end = count if end is None else end
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= count:
        raise ValueError(f'Invalid page range {start}..{end}; document has {count} pages')
    reverse_pages = config.get('reverse_pages', False)
    if type(reverse_pages) is not bool:
        raise ValueError('reverse_pages must be a boolean')
    mode = config.get('input_mode', 'auto')
    forced = config.get('force_ocr_pages', [])
    if mode not in ('auto', 'ocr', 'text'):
        raise ValueError('input_mode must be auto, ocr or text')
    if not isinstance(forced, list) or any(type(n) is not int or not 1 <= n <= count for n in forced):
        raise ValueError('force_ocr_pages must contain original page numbers')
    if mode == 'text' and path.suffix.lower() != '.pdf':
        raise ValueError('Text extraction mode requires PDF input')
    for key, default in (('render_scale', 2), ('page_timeout', 120), ('model_timeout', 600),
                         ('rec_batch_size', 16), ('det_limit_side_len', 1280)):
        value = config.get(key, default)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{key} must be positive')
        if key in ('rec_batch_size', 'det_limit_side_len') and type(value) is not int:
            raise ValueError(f'{key} must be an integer')
    from OCR.utils.viet_engine import DEFAULT_DETECTOR, DEFAULT_RECOGNIZER
    settings = dict(detector=DEFAULT_DETECTOR, recognizer=DEFAULT_RECOGNIZER,
                    render_scale=2.0, rec_batch_size=16, det_limit_side_len=1280,
                    use_textline_orientation=False, device='gpu:0', review_score=.7)
    settings.update(config)
    backend = settings.get('ocr_backend', 'paddle')
    if backend not in ('paddle', 'paddle_vietocr'):
        raise ValueError('ocr_backend must be paddle or paddle_vietocr')
    if not 0 <= settings['review_score'] <= 1:
        raise ValueError('review_score must be in 0..1')
    digest = digest_file(path)
    identity = {key: settings[key] for key in ('detector', 'recognizer', 'render_scale',
                'rec_batch_size', 'det_limit_side_len', 'use_textline_orientation', 'device')}
    identity.update(pipeline_version=1, paddleocr='3.7.0', paddlex='3.7.2', paddle='3.2.2')
    identity.update(routing_version=ROUTING_VERSION, input_mode=mode)
    if backend == 'paddle_vietocr':
        from OCR.utils.vietocr_reader import WEIGHTS_SHA256
        identity['recognizer'] = 'VietOCR/vgg_transformer'
        identity.update(ocr_backend=backend, vietocr='0.3.13', hybrid_pipeline_version=1,
                        torch='2.6.0', vietocr_model='vgg_transformer', weights_sha256=WEIGHTS_SHA256)
        folder = Path(__file__).parent / 'configs/vietocr'
        identity['vietocr_config_sha256'] = hashlib.sha256(
            (folder / 'base.yml').read_bytes() + (folder / 'vgg-transformer.yml').read_bytes()).hexdigest()
    signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    output = Path(config['output_dir']).resolve()
    basename = text_basename(config, 'viet')
    full_name, partial_name = basename + '.txt', basename + '.partial.txt'
    cache_dir = Path(config.get('checkpoint_dir') or output / 'checkpoints').resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    for name in (full_name, partial_name, 'viet_metadata.json', 'viet_ocr.zip'):
        (output / name).unlink(missing_ok=True)
    pages, errors, checkpoints = [], [], []
    owns_engine = engine is None
    engine_info = None
    total = end - start + 1

    def report(event, **values):
        emit_progress(event, total=total, processed=len(pages),
                      cached=sum(p['is_cached'] for p in pages),
                      review_pages=sum(p['needs_review'] for p in pages),
                      error_regions=len(errors), **values)

    report('start')
    document = None
    try:
        if path.suffix.lower() == '.pdf' and mode != 'ocr':
            import pypdfium2 as pdfium
            document = pdfium.PdfDocument(str(path))
        page_numbers = range(end, start - 1, -1) if reverse_pages else range(start, end + 1)
        for number in page_numbers:
            report('page_start', page=number, region=None)
            key = hashlib.sha256(f'{digest}:{signature}:{number}:{number in forced}'.encode()).hexdigest()
            checkpoint = cache_dir / f'{key}.json'
            page = None
            if checkpoint.is_file() and not config.get('force_reprocess', False):
                try:
                    cached = json.loads(checkpoint.read_text(encoding='utf-8'))
                    if (cached['source_sha256'] == digest and cached['signature'] == signature
                            and cached['page_number'] == number and cached['status'] == 'complete'
                            and isinstance(cached['boxes'], list) and isinstance(cached['text'], str)
                            and isinstance(cached['engine_info'], dict)
                            and cached.get('payload_sha256') == checkpoint_digest(cached)):
                        page = dict(cached, is_cached=True)
                except (ValueError, KeyError, TypeError):
                    pass
            if page is None:
                route = route_page(path, number, mode, forced, document)
                began = time.monotonic()
                image = None
                initializing = inference_started = False
                try:
                    if route['method'] == 'pdf_text':
                        if not route['text'].strip():
                            raise ValueError('No selectable text; use auto or ocr mode')
                        boxes, text = [], route['text']
                        page_engine = dict(engine_type='PDFiumText', model_name=None, is_mock=False)
                    else:
                        image = load_page(path, number, settings['render_scale'])
                        if engine is None:
                            report('model_loading', page=number)
                            # Initialization failures are fatal configuration errors.
                            initializing = True
                            engine = WorkerEngine(settings)
                            initializing = False
                        inference_started = True
                        boxes = engine.recognize_image(image)
                        line_errors = []
                        if isinstance(boxes, dict):
                            line_errors = boxes['errors']
                            boxes = boxes['boxes']
                        text = '\n'.join(b['text'] for b in boxes)
                        page_engine = engine.info
                    page = dict(page_number=number, text=text,
                                boxes=boxes, status='complete', source_sha256=digest,
                                signature=signature, engine_info=page_engine, is_cached=False,
                                method=route['method'], routing_reason=route['reason'],
                                text_quality=route['quality'],
                                extraction_error=route.get('extraction_error'),
                                ocr_time_sec=round(time.monotonic() - began, 3) if route['method'] == 'ocr' else 0,
                                inference_time_sec=round(time.monotonic() - began, 3))
                    if route['method'] == 'ocr' and line_errors:
                        checkpoint.unlink(missing_ok=True)
                        page['status'] = 'partial'
                        page['errors'] = line_errors
                        errors.extend(dict(page_number=number, **error) for error in line_errors)
                    else:
                        page['payload_sha256'] = checkpoint_digest(page)
                        write_json(checkpoint, page)
                except Exception as error:
                    if initializing:
                        raise
                    traceback.print_exc()
                    checkpoint.unlink(missing_ok=True)
                    errors.append(dict(page_number=number, error=str(error)))
                    page = dict(page_number=number, text='', boxes=[], status='error',
                                method=route['method'], routing_reason=route['reason'], text_quality=route['quality'],
                                is_cached=False, inference_time_sec=round(time.monotonic() - began, 3))
                    if owns_engine and engine is not None and inference_started:
                        engine.close()
                        engine = None
                finally:
                    if image is not None:
                        image.close()
            if page.get('engine_info'):
                engine_info = page['engine_info']
            if page['status'] == 'complete':
                checkpoints.append(checkpoint)
            # Blank and low-confidence lines are review flags, never silently dropped.
            page['is_blank'] = not page['text'].strip()
            page['low_confidence_lines'] = [i for i, b in enumerate(page['boxes'])
                                            if b['confidence'] < settings['review_score']]
            page['needs_review'] = bool(page['status'] != 'complete' or page['is_blank'] or page['low_confidence_lines']
                or any(b.get('split_retry') for b in page['boxes'])
                or (page['method'] == 'pdf_text' and
                    (not page['text_quality']['usable'] or page['text_quality'].get('warnings'))))
            pages.append(page)
            (output / partial_name).write_bytes('\n\n'.join(p['text'] for p in pages).encode('utf-8'))
            write_json(output / 'progress.json', dict(processed=len(pages), total=total, page=number, errors=errors))
            write_json(output / 'error_report.json', dict(errors=errors))
            print(f"Trang {number}/{end}: {page['method']} | {'cache' if page['is_cached'] else page['status']} | {len(page['text'])} ký tự", flush=True)
            report('page_done', page=number)
            if errors and not config.get('continue_on_error', True):
                raise RuntimeError(errors[-1]['error'])
    finally:
        if owns_engine and engine is not None:
            engine.close()
        if document is not None:
            document.close()
    report('export')
    complete = not errors
    text_file = full_name if complete else partial_name
    result = dict(complete=complete, needs_review=any(p['needs_review'] for p in pages),
                  method_counts={method: sum(p['method'] == method for p in pages) for method in ('pdf_text', 'ocr')},
                  source_file=str(path), source_sha256=digest, config=settings,
                  engine_info=engine_info, total_pages=len(pages), start_page=start, end_page=end,
                  reverse_pages=reverse_pages,
                  pages=pages, errors=errors, text_file=text_file,
                  full_text='\n\n'.join(p['text'] for p in pages))
    engines = {json.dumps(p['engine_info'], sort_keys=True) for p in pages if p['status'] == 'complete'}
    if len(engines) > 1:
        result['engine_info'] = dict(engine_type='HybridPDF', is_mock=False,
                                    engines=[json.loads(value) for value in sorted(engines)])
    (output / text_file).write_bytes(result['full_text'].encode('utf-8'))
    write_json(output / 'viet_metadata.json', result)
    write_json(output / 'error_report.json', dict(complete=complete, errors=errors,
               review_pages=[p['page_number'] for p in pages if p['needs_review']]))
    with zipfile.ZipFile(output / 'viet_ocr.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in (text_file, 'viet_metadata.json', 'error_report.json', 'progress.json'):
            archive.write(output / name, name)
        for checkpoint in checkpoints:
            archive.write(checkpoint, 'checkpoints/' + checkpoint.name)
        for error in errors:
            if error.get('image'):
                image_file = output / error['image']
                if image_file.is_file() and error['image'] not in archive.namelist():
                    archive.write(image_file, error['image'])
    if complete:
        (output / partial_name).unlink(missing_ok=True)
    report('finish', complete=complete and not result['needs_review'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    run(json.loads(Path(args.config).read_text(encoding='utf-8')))
