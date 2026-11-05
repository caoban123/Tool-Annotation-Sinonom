"""Paddle detection followed by perspective-corrected Vietnamese VietOCR lines."""
import base64
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import threading

from OCR.utils.viet_engine import DEFAULT_DETECTOR, parse_prediction


def line_crops(image, polygons):
    import cv2
    import numpy as np
    from PIL import Image
    pixels = np.asarray(image.convert('RGB'))
    items = []
    for polygon in polygons:
        points = np.asarray(polygon, dtype=np.float32)
        if points.shape != (4, 2) or not np.isfinite(points).all():
            raise ValueError('Detector returned invalid quadrilateral')
        # Paddle emits clockwise top-left, top-right, bottom-right, bottom-left.
        width = round(max(np.linalg.norm(points[0]-points[1]), np.linalg.norm(points[2]-points[3])))
        height = round(max(np.linalg.norm(points[0]-points[3]), np.linalg.norm(points[1]-points[2])))
        if width < 2 or height < 2:
            raise ValueError('Detector returned degenerate text line')
        matrix = cv2.getPerspectiveTransform(points, np.array(
            [[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]], dtype=np.float32))
        crop = Image.fromarray(cv2.warpPerspective(pixels, matrix, (width, height),
                                                  borderMode=cv2.BORDER_REPLICATE))
        items.append((points.tolist(), crop))
    # Sort baselines, then restore left-to-right order within each row.
    items.sort(key=lambda item: (item[0][0][1], item[0][0][0]))
    for i in range(1, len(items)):
        j = i
        while j > 0:
            a, b = items[j-1][0], items[j][0]
            tolerance = min(abs(a[3][1]-a[0][1]), abs(b[3][1]-b[0][1])) * .5
            if abs(a[0][1]-b[0][1]) > tolerance or a[0][0] <= b[0][0]:
                break
            items[j-1], items[j] = items[j], items[j-1]
            j -= 1
    return items


class PaddleVietOCREngine:
    def __init__(self, config):
        import paddle
        from paddleocr import TextDetection
        python = Path(config.get('vietocr_python', ''))
        if not python.is_file():
            raise ValueError('vietocr_python must point to the isolated VietOCR Python interpreter')
        if config.get('use_textline_orientation', False):
            raise ValueError('Paddle + VietOCR requires upright horizontal text; set USE_TEXTLINE_ORIENTATION=False')
        device = config.get('device', 'gpu:0')
        if device.startswith('gpu:') and (not paddle.is_compiled_with_cuda() or
                int(device[4:]) >= paddle.device.cuda.device_count()):
            raise RuntimeError('Paddle detector: requested GPU unavailable')
        paddle.set_device(device)
        (paddle.ones([2, 2]) @ paddle.ones([2, 2])).numpy()
        detector = config.get('detector', DEFAULT_DETECTOR)
        self.detector = TextDetection(model_name=detector, device=device,
            limit_side_len=config.get('det_limit_side_len', 1280), limit_type='max',
            enable_mkldnn=False, enable_hpi=False)
        options = dict(device=device, batch_size=config.get('rec_batch_size', 16),
                       weights_dir=str(config.get('vietocr_weights_dir') or
                       Path(config['output_dir']).parent / 'vietocr_weights'))
        self.process = subprocess.Popen([str(python), '-u', '-m', 'OCR.utils.vietocr_reader',
            json.dumps(options)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding='utf-8', errors='strict',
            env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        self.messages = queue.Queue()
        def read():
            try:
                for line in self.process.stdout:
                    self.messages.put(json.loads(line))
            except Exception as error:
                self.messages.put({'error': str(error)})
            finally:
                self.messages.put({'error': 'VietOCR reader exited; see process log'})
        threading.Thread(target=read, daemon=True).start()
        self.timeout = config.get('page_timeout', 120)
        try:
            ready = self.receive(config.get('model_timeout', 600))
            if not ready.get('ready'):
                raise RuntimeError('VietOCR reader did not initialize')
        except BaseException:
            self.close()
            raise
        self.info = dict(engine_type='PaddleVietOCR', model_name=f'{detector}+vgg_transformer',
            detector=detector, recognizer='VietOCR/vgg_transformer', device=device,
            paddle_version=paddle.__version__, vietocr_version='0.3.13',
            weights_sha256=ready['weights_sha256'], torch_version=ready['torch_version'], is_mock=False)

    def receive(self, timeout):
        try:
            response = self.messages.get(timeout=timeout)
        except queue.Empty as error:
            raise TimeoutError(f'VietOCR reader exceeded {timeout}s') from error
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response

    def recognize_image(self, image):
        import numpy as np
        prediction = self.detector.predict(np.asarray(image.convert('RGB'))[:, :, ::-1].copy())
        if len(prediction) != 1:
            raise ValueError('Expected one detection page')
        crops = line_crops(image, prediction[0]['dt_polys'])
        try:
            encoded = []
            for _, crop in crops:
                data = io.BytesIO()
                crop.save(data, format='PNG')
                encoded.append(base64.b64encode(data.getvalue()).decode('ascii'))
            if not crops:
                return []
            self.process.stdin.write(json.dumps({'images': encoded}) + '\n')
            self.process.stdin.flush()
            results = self.receive(self.timeout)['results']
            if len(results) != len(crops):
                raise ValueError('VietOCR returned mismatched line count')
            return parse_prediction([dict(rec_texts=[r['text'] for r in results],
                rec_scores=[r['confidence'] for r in results], rec_polys=[p for p, _ in crops])])
        finally:
            for _, crop in crops:
                crop.close()

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()
