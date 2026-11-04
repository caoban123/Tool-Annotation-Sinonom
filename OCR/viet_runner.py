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
from OCR.utils.notebook_process import emit_progress
from OCR.utils.render_pdf import render_pdf_to_images


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
    try:
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
    if not 0 <= settings['review_score'] <= 1:
        raise ValueError('review_score must be in 0..1')
    digest = digest_file(path)
    identity = {key: settings[key] for key in ('detector', 'recognizer', 'render_scale',
                'rec_batch_size', 'det_limit_side_len', 'use_textline_orientation', 'device')}
    identity.update(pipeline_version=1, paddleocr='3.7.0', paddlex='3.7.2', paddle='3.2.2')
    signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    output = Path(config['output_dir']).resolve()
    cache_dir = Path(config.get('checkpoint_dir') or output / 'checkpoints').resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    for name in ('viet.txt', 'viet.partial.txt', 'viet_metadata.json', 'viet_ocr.zip'):
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
    try:
        for number in range(start, end + 1):
            report('page_start', page=number, region=None)
            key = hashlib.sha256(f'{digest}:{signature}:{number}'.encode()).hexdigest()
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
                # Initialization failures are fatal configuration errors, not blank pages.
                if engine is None:
                    report('model_loading', page=number)
                    engine = WorkerEngine(settings)
                engine_info = engine.info
                began = time.monotonic()
                image = None
                try:
                    image = load_page(path, number, settings['render_scale'])
                    boxes = engine.recognize_image(image)
                    page = dict(page_number=number, text='\n'.join(b['text'] for b in boxes),
                                boxes=boxes, status='complete', source_sha256=digest,
                                signature=signature, engine_info=engine_info, is_cached=False,
                                inference_time_sec=round(time.monotonic() - began, 3))
                    page['payload_sha256'] = checkpoint_digest(page)
                    write_json(checkpoint, page)
                except Exception as error:
                    traceback.print_exc()
                    errors.append(dict(page_number=number, error=str(error)))
                    page = dict(page_number=number, text='', boxes=[], status='error',
                                is_cached=False, inference_time_sec=round(time.monotonic() - began, 3))
                    if owns_engine:
                        engine.close()
                        engine = None
                finally:
                    if image is not None:
                        image.close()
            else:
                engine_info = page['engine_info']
            if page['status'] == 'complete':
                checkpoints.append(checkpoint)
            # Blank and low-confidence lines are review flags, never silently dropped.
            page['is_blank'] = not page['text'].strip()
            page['low_confidence_lines'] = [i for i, b in enumerate(page['boxes'])
                                            if b['confidence'] < settings['review_score']]
            page['needs_review'] = bool(page['status'] == 'error' or page['is_blank'] or page['low_confidence_lines'])
            pages.append(page)
            (output / 'viet.partial.txt').write_bytes('\n\n'.join(p['text'] for p in pages).encode('utf-8'))
            write_json(output / 'progress.json', dict(processed=len(pages), total=total, page=number, errors=errors))
            write_json(output / 'error_report.json', dict(errors=errors))
            print(f"Trang {number}/{end}: {'cache' if page['is_cached'] else page['status']} | {len(page['text'])} ký tự", flush=True)
            report('page_done', page=number)
            if errors and not config.get('continue_on_error', True):
                raise RuntimeError(errors[-1]['error'])
    finally:
        if owns_engine and engine is not None:
            engine.close()
    report('export')
    complete = not errors
    text_file = 'viet.txt' if complete else 'viet.partial.txt'
    result = dict(complete=complete, needs_review=any(p['needs_review'] for p in pages),
                  source_file=str(path), source_sha256=digest, config=settings,
                  engine_info=engine_info, total_pages=len(pages), start_page=start, end_page=end,
                  pages=pages, errors=errors, text_file=text_file,
                  full_text='\n\n'.join(p['text'] for p in pages))
    (output / text_file).write_bytes(result['full_text'].encode('utf-8'))
    write_json(output / 'viet_metadata.json', result)
    write_json(output / 'error_report.json', dict(complete=complete, errors=errors,
               review_pages=[p['page_number'] for p in pages if p['needs_review']]))
    with zipfile.ZipFile(output / 'viet_ocr.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in (text_file, 'viet_metadata.json', 'error_report.json', 'progress.json'):
            archive.write(output / name, name)
        for checkpoint in checkpoints:
            archive.write(checkpoint, 'checkpoints/' + checkpoint.name)
    if complete:
        (output / 'viet.partial.txt').unlink(missing_ok=True)
    report('finish', complete=complete and not result['needs_review'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    run(json.loads(Path(args.config).read_text(encoding='utf-8')))
