"""Build the self-contained Vietnamese OCR notebook without modifying Han OCR."""
import base64
import hashlib
import json
from pathlib import Path
import textwrap
import zlib

ROOT = Path(__file__).resolve().parents[1]
FILES = ['OCR/viet_runner.py', 'OCR/utils/__init__.py', 'OCR/utils/viet_engine.py',
         'OCR/utils/vietocr_engine.py', 'OCR/utils/vietocr_reader.py',
         'OCR/configs/vietocr/base.yml', 'OCR/configs/vietocr/vgg-transformer.yml',
         'OCR/configs/vietocr/SOURCE.txt', 'OCR/requirements-vietocr.txt',
         'OCR/configs/vietocr/LICENSE',
         'OCR/utils/notebook_process.py', 'OCR/utils/render_pdf.py', 'OCR/requirements-viet.txt',
         'OCR/requirements-pdf.txt', 'Crawl/extractors/pdf_pages.py',
         'tests/fixtures/sample_viet_scan.png']


def build_ocr_viet_notebook(target=None):
    payload = json.dumps({name: base64.b64encode((ROOT / name).read_bytes()).decode()
                          for name in FILES}).encode()
    cells = []

    def cell(kind, source):
        item = dict(cell_type=kind, id=f'viet-{len(cells)}', metadata={},
                    source=textwrap.dedent(source).strip() + '\n')
        if kind == 'code':
            item.update(execution_count=None, outputs=[])
        cells.append(item)

    cell('markdown', '''
    # PDF tiếng Việt — trích xuất text + OCR scan / Colab / Kaggle

    [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/OCR/notebooks/02_OCR_Viet.ipynb)

    Mặc định: `PP-OCRv5_mobile_det` tìm/cắt dòng, VietOCR `vgg_transformer` đọc tiếng Việt.
    Đặt `OCR_BACKEND="paddle"` để đối chiếu với PP-OCRv6; giữ dòng lặp và tọa độ gốc.
    Không có cam kết chính xác tuyệt đối: đối chiếu các dòng điểm thấp và trang trắng.
    Chế độ `auto` lấy text trực tiếp ở trang dùng được, chỉ OCR trang scan/text lỗi.
    PDF trộn được ghép theo số trang gốc; PDF text thuần không cần cài Paddle hay GPU.

    **Cách chạy:** tải PDF/ảnh lên, điền `INPUT_PATH` trong cell 1, rồi **Run all**.
    Colab: Runtime → Change runtime type → GPU. Kaggle: bật GPU và Internet.
    Có thể chọn `DEVICE="cpu"`. Notebook dùng Python 3.11 và môi trường riêng;
    không sửa kernel, không clone repo, không tự tải bộ sách hay thay tài liệu bằng ảnh mẫu.
    Lần đầu cần Internet để cài runtime và tải model, các lần sau dùng cache.
    ''')
    cell('code', '''
    # 1. Cấu hình đầu vào và tốc độ
    from pathlib import Path
    import os, sys, json, subprocess
    INPUT_PATH = ""  # Colab: /content/sach.pdf; Kaggle: /kaggle/input/ten-dataset/sach.pdf
    START_PAGE = 1
    END_PAGE = None  # None = hết tài liệu; số trang bắt đầu từ 1
    INPUT_MODE = "auto"  # auto: tự chọn từng trang; ocr: ép OCR; text: chỉ lấy lớp text PDF
    FORCE_OCR_PAGES = []  # VD [3, 7]: ép OCR những trang này trong chế độ auto
    DEVICE = "gpu:0"  # "cpu" nếu không dùng GPU; không tự đổi GPU sang CPU
    GPU_WHEEL = "cu126"  # cu118 cho driver cũ / GPU P100; cần chọn trước khi cài
    RENDER_SCALE = 2.0  # 144 DPI; tăng 3.0 cho chữ nhỏ (chậm hơn)
    DET_LIMIT_SIDE_LEN = 1280  # tăng 1920 nếu mất chữ nhỏ trên trang lớn
    REC_BATCH_SIZE = 16  # giảm 8 hoặc 4 nếu thiếu VRAM
    DETECTOR = "PP-OCRv5_mobile_det" # DETECTOR = "PP-OCRv5_server_det" mạnh hơn
    OCR_BACKEND = "paddle_vietocr"  # Paddle tìm dòng + VietOCR đọc tiếng Việt; "paddle" dùng PP-OCR
    RECOGNIZER = "PP-OCRv6_small_rec"  # có thể thử PP-OCRv6_medium_rec để đối chiếu chất lượng
    USE_TEXTLINE_ORIENTATION = False  # True nếu dòng chữ bị quay 180 độ
    PAGE_TIMEOUT = 300  # VietOCR transformer có thể chậm trên CPU; timeout -> báo lỗi và đi tiếp
    REVIEW_SCORE = 0.7  # chỉ gắn cờ kiểm tra, không xóa dòng điểm thấp
    FORCE_REPROCESS = False
    CHECKPOINT_DIR = ""  # thư mục Drive đã mount để giữ cache sau khi hết phiên
    SMOKE = os.environ.get('OCR_NOTEBOOK_SMOKE') == '1'  # kiểm tra cell, KHÔNG inference
    WORK_DIR = (Path('/kaggle/working/viet_ocr') if Path('/kaggle/working').is_dir() else
                Path('/content/viet_ocr') if Path('/content').is_dir() else
                Path.cwd() / 'artifacts/viet_notebook')
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    print('Thư mục làm việc:', WORK_DIR)
    ''')
    bootstrap = '''
    # 2. Giải nén mã nguồn đi kèm notebook
    import base64, zlib, hashlib
    packed = zlib.decompress(base64.b64decode('__PAYLOAD__'))
    assert hashlib.sha256(packed).hexdigest() == '__HASH__', 'Bundle bị hỏng'
    SOURCE_DIR = WORK_DIR / 'runtime'
    for relative, data in json.loads(packed).items():
        target = SOURCE_DIR / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(data))
    input_file = (SOURCE_DIR / 'tests/fixtures/sample_viet_scan.png') if SMOKE else Path(INPUT_PATH).expanduser()
    if not SMOKE and not INPUT_PATH:
        raise ValueError('Tải tài liệu lên và điền INPUT_PATH trong cell 1.')
    if not input_file.is_file():
        raise FileNotFoundError(f'Không thấy tài liệu: {input_file}')
    input_file = input_file.resolve()
    print('Tài liệu:', input_file)
    '''
    cell('code', bootstrap.replace('__PAYLOAD__', base64.b64encode(zlib.compress(payload)).decode())
         .replace('__HASH__', hashlib.sha256(payload).hexdigest()))
    cell('code', '''
    # 3. Python 3.11 riêng để tránh xung đột Python/Paddle của kernel Colab/Kaggle
    environment = dict(os.environ, PYTHONPATH=str(SOURCE_DIR), PYTHONUNBUFFERED='1',
                       PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True')
    ENV_DIR = WORK_DIR / ('env_cpu' if DEVICE == 'cpu' else 'env_' + GPU_WHEEL)
    PYTHON = ENV_DIR / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    VIETOCR_ENV = WORK_DIR / ('vietocr_cpu' if DEVICE == 'cpu' else 'vietocr_' + GPU_WHEEL)
    VIETOCR_PYTHON = VIETOCR_ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not SMOKE:
        if OCR_BACKEND not in ('paddle', 'paddle_vietocr'):
            raise ValueError('OCR_BACKEND must be paddle or paddle_vietocr')
        if OCR_BACKEND == 'paddle_vietocr' and USE_TEXTLINE_ORIENTATION:
            raise ValueError('VietOCR cần dòng ngang đúng chiều: USE_TEXTLINE_ORIENTATION=False')
        if DEVICE != 'cpu' and not (DEVICE.startswith('gpu:') and DEVICE[4:].isdigit()):
            raise ValueError('DEVICE phải là cpu hoặc gpu:N')
        if GPU_WHEEL not in ('cu118', 'cu126'):
            raise ValueError('GPU_WHEEL phải là cu118 hoặc cu126')
        bootstrap_dir = WORK_DIR / 'bootstrap'
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--target', str(bootstrap_dir),
                        'uv>=0.9,<1'], check=True)
        bootstrap_env = dict(os.environ, PYTHONPATH=str(bootstrap_dir))
        uv = [sys.executable, '-m', 'uv']
        if not PYTHON.exists():
            subprocess.run(uv + ['venv', '--python', '3.11', '--seed', str(ENV_DIR)],
                           env=bootstrap_env, check=True)
        subprocess.run([str(PYTHON), '-m', 'pip', 'install',
                        '-r', str(SOURCE_DIR / 'OCR/requirements-pdf.txt')], env=environment, check=True)
        plan_config = dict(input_path=str(input_file), start_page=START_PAGE, end_page=END_PAGE,
                           input_mode=INPUT_MODE, force_ocr_pages=FORCE_OCR_PAGES)
        plan_code = ('import json,sys; from Crawl.extractors.pdf_pages import plan_input; '
                     'print(json.dumps(plan_input(json.loads(sys.argv[1]))))')
        plan = json.loads(subprocess.check_output([str(PYTHON), '-c', plan_code, json.dumps(plan_config)],
                                                  env=environment, text=True))
        print('Trang lấy text trực tiếp:', plan['text_pages'], '| Trang cần OCR:', plan['ocr_pages'])
        if plan['ocr_pages']:
            if DEVICE != 'cpu':
                import shutil
                nvidia_smi = shutil.which('nvidia-smi')
                if nvidia_smi is None:
                    raise RuntimeError(
                        'Đang chọn DEVICE="gpu:0" nhưng phiên này không có công cụ NVIDIA. '
                        'Colab: bật GPU trong Runtime > Change runtime type. '
                        'Kaggle: Settings > Accelerator > GPU, rồi chạy lại notebook. '
                        'Nếu muốn chạy CPU, đổi DEVICE="cpu" ở cell 1 rồi Run all '
                        '(OCR nhiều trang sẽ chậm).')
                gpu_check = subprocess.run([nvidia_smi], capture_output=True, text=True)
                if gpu_check.returncode:
                    raise RuntimeError('GPU NVIDIA chưa sẵn sàng; bật GPU rồi chạy lại, '
                                       'hoặc chọn DEVICE="cpu" ở cell 1. Chi tiết: ' +
                                       gpu_check.stderr.strip())
                print(gpu_check.stdout)
            runtime = 'paddlepaddle' if DEVICE == 'cpu' else 'paddlepaddle-gpu'
            index = 'cpu' if DEVICE == 'cpu' else GPU_WHEEL
            subprocess.run([str(PYTHON), '-m', 'pip', 'install', runtime + '==3.2.2',
                            '--index-url', 'https://www.paddlepaddle.org.cn/packages/stable/' + index + '/'],
                           env=environment, check=True)
            subprocess.run([str(PYTHON), '-m', 'pip', 'install',
                            '-r', str(SOURCE_DIR / 'OCR/requirements-viet.txt')], env=environment, check=True)
        preflight = """import paddle, paddleocr
    device = __DEVICE__
    if device.startswith('gpu:'):
        assert paddle.is_compiled_with_cuda(), 'Paddle CPU được cài thay vì bản GPU'
        assert int(device[4:]) < paddle.device.cuda.device_count(), 'Không thấy GPU đã chọn'
    paddle.set_device(device)
    print('Paddle:', paddle.__version__, 'Device:', paddle.get_device())
    print((paddle.ones([2, 2]) @ paddle.ones([2, 2])).numpy())
    """.replace('__DEVICE__', repr(DEVICE))
        if plan['ocr_pages']:
            subprocess.run([str(PYTHON), '-c', preflight], env=environment, check=True)
            if OCR_BACKEND == 'paddle_vietocr':
                if not VIETOCR_PYTHON.exists():
                    subprocess.run(uv + ['venv', '--python', '3.11', '--seed', str(VIETOCR_ENV)],
                                   env=bootstrap_env, check=True)
                torch_index = 'cpu' if DEVICE == 'cpu' else GPU_WHEEL
                subprocess.run([str(VIETOCR_PYTHON), '-m', 'pip', 'install',
                                '--timeout', '120', '--retries', '5',
                                'torch==2.6.0', 'torchvision==0.21.0', '--index-url',
                                'https://download.pytorch.org/whl/' + torch_index],
                               env=environment, check=True)
                subprocess.run([str(VIETOCR_PYTHON), '-m', 'pip', 'install', '-r',
                                str(SOURCE_DIR / 'OCR/requirements-vietocr.txt'),
                                '--timeout', '120', '--retries', '5'],
                               env=environment, check=True)
                torch_check = ("import torch,torchvision; "
                               "from vietocr.tool.translate import build_model,process_input,translate; device=" +
                               repr(DEVICE.replace('gpu:', 'cuda:')) +
                               "; print('VietOCR device:',device); print(torch.ones(1,device=device))")
                subprocess.run([str(VIETOCR_PYTHON), '-c', torch_check], env=environment, check=True)
        else:
            print('PDF text: bỏ qua cài/nạp model OCR, không cần GPU.')
    else:
        print('SMOKE: không cài Paddle, không chạy model, không xác nhận chất lượng OCR.')
    ''')
    cell('code', '''
    # 4. Ghi cấu hình; kiểm tra số trang bằng worker đã cài thư viện
    total_pages = 1 if SMOKE else int(subprocess.check_output(
        [str(PYTHON), '-c', 'from OCR.viet_runner import page_count; import sys; print(page_count(sys.argv[1]))',
         str(input_file)], env=environment, text=True).strip())
    end_page = total_pages if END_PAGE is None else END_PAGE
    if not 1 <= START_PAGE <= end_page <= total_pages:
        raise ValueError(f'Khoảng trang không hợp lệ; tài liệu có {total_pages} trang')
    config = dict(input_path=str(input_file), output_dir=str(WORK_DIR / 'output'),
                  ocr_backend=OCR_BACKEND, vietocr_python=str(VIETOCR_PYTHON),
                  detector=DETECTOR, recognizer=RECOGNIZER,
                  input_mode=INPUT_MODE, force_ocr_pages=FORCE_OCR_PAGES,
                  start_page=START_PAGE, end_page=end_page, device=DEVICE,
                  render_scale=RENDER_SCALE, det_limit_side_len=DET_LIMIT_SIDE_LEN,
                  rec_batch_size=REC_BATCH_SIZE, use_textline_orientation=USE_TEXTLINE_ORIENTATION,
                  page_timeout=PAGE_TIMEOUT, review_score=REVIEW_SCORE,
                  continue_on_error=True, force_reprocess=FORCE_REPROCESS,
                  checkpoint_dir=CHECKPOINT_DIR or str(WORK_DIR / 'output/checkpoints'))
    config_file = WORK_DIR / 'config.json'
    config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(config, ensure_ascii=False, indent=2))
    ''')
    cell('code', '''
    # 5. Chạy OCR — bảng tiến độ hiện bên dưới cell này
    if not SMOKE:
        import runpy
        run_logged = runpy.run_path(str(SOURCE_DIR / 'OCR/utils/notebook_process.py'))['run_logged_process']
        run_logged([str(PYTHON), '-u', '-m', 'OCR.viet_runner', '--config', str(config_file)],
                   cwd=SOURCE_DIR, env=environment, log_path=WORK_DIR / 'ocr_run.log')
    else:
        print('SMOKE: bỏ qua OCR, không xuất viet.txt giả.')
    ''')
    cell('code', '''
    # 6. Xem báo cáo và tải kết quả
    if not SMOKE:
        from IPython.display import display, FileLink
        output = Path(config['output_dir'])
        report = json.loads((output / 'viet_metadata.json').read_text(encoding='utf-8'))
        print('ĐỦ TRANG XỬ LÝ' if report['complete'] else 'THIẾU TRANG — xem error_report.json')
        print('Trang cần đối chiếu:', [p['page_number'] for p in report['pages'] if p['needs_review']])
        print('Cách lấy chữ:', report['method_counts'])
        print(report['full_text'][:3000])
        for name in (report['text_file'], 'viet_metadata.json', 'error_report.json', 'viet_ocr.zip'):
            display(FileLink(os.path.relpath(output / name, Path.cwd())))
        if 'google.colab' in sys.modules:
            from google.colab import files
            files.download(str(output / 'viet_ocr.zip'))
    else:
        print('Đã kiểm tra các cell. Chưa chạy inference thực tế.')
    ''')
    cell('markdown', '''
    ## Chạy tiếp và đọc đầu ra

    Ngắt cell rồi chạy lại cell 5: chỉ xử lý trang chưa thành công. Nếu hết phiên,
    dùng lại `CHECKPOINT_DIR` trên Drive, chọn đúng tài liệu/cấu hình và Run all.
    Cache gắn với SHA256 nội dung, trang và cấu hình/model; không dùng nhầm sách cùng tên.

    ZIP gồm `viet.txt` (khi xử lý đủ trang) hoặc `viet.partial.txt` (còn lỗi),
    `viet_metadata.json` (text, tọa độ, điểm từng dòng, số trang gốc), `error_report.json`,
    `progress.json` và checkpoint. Trang trắng/dòng điểm thấp được gắn cờ; điểm confidence
    không phải phần trăm chính xác. Log đầy đủ ở `WORK_DIR/ocr_run.log`.
    Sách nhiều cột hoặc bảng vẫn cần kiểm tra thứ tự đọc. PDF/ảnh được nạp từng trang.
    Metadata mỗi trang ghi `method=pdf_text` hoặc `ocr`, lý do chọn và chất lượng lớp text.
    Kiểm tra tự động không phát hiện hết lớp OCR cũ sai chữ: dùng `FORCE_OCR_PAGES` hoặc
    `INPUT_MODE="ocr"` khi cần. Đổi chế độ sẽ dùng cache riêng.

    VietOCR cần dòng ngang đúng chiều, không bật `USE_TEXTLINE_ORIENTATION` ở chế độ kết hợp.
    Paddle và Torch chạy trong hai môi trường/tiến trình riêng. Lần đầu tải thêm weights
    VietOCR khoảng 152 MB. `RECOGNIZER` chỉ dùng khi `OCR_BACKEND="paddle"`.
    Để thử model mới trên PDF có lớp text cũ, chọn `INPUT_MODE="ocr"` và 5–10 trang trước.

    API/model: [VietOCR](https://github.com/pbcquoc/vietocr), [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR),
    [PP-OCRv6](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html).
    ''')
    notebook = dict(cells=cells, metadata=dict(
        kernelspec=dict(display_name='Python 3', language='python', name='python3'),
        language_info=dict(name='python', version='3.11'), accelerator='GPU', colab=dict(provenance=[])),
        nbformat=4, nbformat_minor=5)
    target = ROOT / (target or 'OCR/notebooks/02_OCR_Viet.ipynb')
    if target.parent.parent.name == 'Crawl':
        for item in cells:
            item['source'] = item['source'].replace('blob/main/OCR/notebooks/02_OCR_Viet.ipynb',
                                                    'blob/main/Crawl/notebooks/01_Crawl_Text.ipynb')
    target.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return target


if __name__ == '__main__':
    print(build_ocr_viet_notebook())
