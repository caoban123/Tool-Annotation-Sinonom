"""Vietnamese line OCR using the pinned PaddleOCR 3.x prediction contract."""
import math

DEFAULT_DETECTOR = 'PP-OCRv5_mobile_det'
DEFAULT_RECOGNIZER = 'PP-OCRv6_small_rec'


def parse_prediction(predictions):
    """Reject broken APIs rather than silently converting failures to blank pages."""
    import numpy as np
    predictions = list(predictions)
    if len(predictions) != 1:
        raise ValueError(f'Expected one OCR page, got {len(predictions)}')
    result = predictions[0]
    texts, scores, polygons = (result[k] for k in ('rec_texts', 'rec_scores', 'rec_polys'))
    if not len(texts) == len(scores) == len(polygons):
        raise ValueError('PaddleOCR returned mismatched text/score/polygon arrays')
    boxes = []
    for text, score, polygon in zip(texts, scores, polygons):
        points = np.asarray(polygon, dtype=float)
        score = float(score)
        if not isinstance(text, str) or points.shape != (4, 2) or not np.isfinite(points).all():
            raise ValueError('Invalid OCR line or polygon')
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError('Invalid OCR confidence')
        if not text.strip():
            continue
        boxes.append(dict(text=text, confidence=score, polygon=points.tolist(),
                          bbox=[float(points[:, 0].min()), float(points[:, 1].min()),
                                float(points[:, 0].max()), float(points[:, 1].max())]))
    # PaddleOCR already returns reading order. Keep it: a fixed y/15 sort can
    # scramble adjacent baselines and legitimate repeated lines must survive.
    return boxes


class VietnameseOCREngine:
    def __init__(self, config):
        import paddle
        from paddleocr import PaddleOCR
        device = config.get('device', 'gpu:0')
        if device != 'cpu' and not (device.startswith('gpu:') and device[4:].isdigit()):
            raise ValueError('device must be cpu or gpu:N')
        if device.startswith('gpu:'):
            if not paddle.is_compiled_with_cuda() or int(device[4:]) >= paddle.device.cuda.device_count():
                raise RuntimeError('GPU requested but unavailable. Enable GPU or select DEVICE="cpu".')
        paddle.set_device(device)
        # Exercise the runtime before downloading models. No silent CPU fallback.
        (paddle.ones([2, 2]) @ paddle.ones([2, 2])).numpy()
        detector = config.get('detector', DEFAULT_DETECTOR)
        recognizer = config.get('recognizer', DEFAULT_RECOGNIZER)
        self.info = dict(engine_type='PaddleOCR3', model_name=f'{detector}+{recognizer}',
                         detector=detector, recognizer=recognizer, device=device,
                         paddle_version=paddle.__version__, is_mock=False)
        self.ocr = PaddleOCR(
            text_detection_model_name=detector, text_recognition_model_name=recognizer,
            device=device, use_doc_orientation_classify=False, use_doc_unwarping=False,
            use_textline_orientation=config.get('use_textline_orientation', False),
            text_recognition_batch_size=config.get('rec_batch_size', 16),
            text_det_limit_side_len=config.get('det_limit_side_len', 1280),
            text_det_limit_type='max', text_rec_score_thresh=0.0,
            enable_mkldnn=False, enable_hpi=False,
        )

    def recognize_image(self, image):
        import numpy as np
        # Paddle's ndarray input is BGR, whereas PIL is RGB.
        bgr = np.asarray(image.convert('RGB'))[:, :, ::-1].copy()
        return parse_prediction(self.ocr.predict(bgr))
