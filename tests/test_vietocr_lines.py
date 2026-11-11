from types import SimpleNamespace
import io
import numpy as np
from PIL import Image
import pytest
from OCR.utils.vietocr_lines import recover_line, split_line
from OCR.utils.vietocr_reader import recognize_batch
from OCR.utils.vietocr_engine import PaddleVietOCREngine

LIMIT = dict(error='512 tokens without EOS', code='token_limit')


def test_retry_splits_only_failed_line_preserves_order_and_text():
    image = Image.new('L',(200,20),'white')
    assert split_line(image) == 100
    sizes = []
    def recognize(images):
        sizes.extend(i.size for i in images)
        return [dict(text='Bên trái',confidence=.9),dict(text='Bên phải',confidence=.8)]
    result = recover_line(image, recognize, LIMIT)
    assert sizes == [(100,20),(100,20)]
    assert result['text'] == 'Bên trái Bên phải' and result['confidence'] == .8
    assert result['split_retry'] and not result['errors']


def test_retry_is_bounded_and_retains_successful_piece():
    image = Image.new('L',(512,20),'white')
    calls = []
    def recognize(images):
        calls.append([i.width for i in images])
        return [dict(text='Đọc được',confidence=.9), LIMIT] if len(calls)==1 else [LIMIT,LIMIT]
    result = recover_line(image,recognize,LIMIT,max_depth=2)
    assert result['text'] == 'Đọc được' and len(result['errors']) == 2
    assert len(calls) == 2
    assert all(error['bbox'][0] >= 256 for error in result['errors'])
    assert all(error['bbox'][2] <= 512 for error in result['errors'])


def test_recognize_batch_eos_failure_does_not_discard_other_lines():
    class Tensor:
        shape = (1,3,32,64)
        def to(self, device): return self
    images = [Image.new('RGB',(64,32)) for _ in range(2)]
    calls = []
    def translate(tensor, model, **kwargs):
        calls.append(kwargs)
        return np.array([[1,3,3],[1,3,2]]), [.8,.9]
    result = recognize_batch(images,lambda *args:Tensor(),translate,None,
        SimpleNamespace(decode=lambda _: 'Việt'),SimpleNamespace(cat=lambda _:Tensor()),'cpu',16)
    assert result[0]['code']=='token_limit' and result[1]['text']=='Việt'
    assert calls == [dict(max_seq_length=512)]


def test_failed_empty_line_does_not_shift_following_box(tmp_path):
    pytest.importorskip('cv2')
    engine = object.__new__(PaddleVietOCREngine)
    polygons = [[[1,1],[90,1],[90,20],[1,20]],[[1,30],[90,30],[90,49],[1,49]]]
    engine.detector = SimpleNamespace(predict=lambda _: [dict(dt_polys=polygons)])
    engine.process = SimpleNamespace(stdin=io.StringIO())
    engine.timeout = 1; engine.output_dir = tmp_path
    engine.receive = lambda _: dict(results=[dict(text='',confidence=0,split_retry=True,
        errors=[dict(error='token limit',bbox=[0,0,89,19])]),dict(text='Dòng sau',confidence=.9)])
    result = engine.recognize_image(Image.new('RGB',(100,60),'white'))
    assert len(result['boxes'])==1 and result['boxes'][0]['bbox']==[1,30,90,49]
    assert result['errors'][0]['line_index']==0 and result['errors'][0]['polygon']==polygons[0]
    assert (tmp_path/result['errors'][0]['image']).is_file()
