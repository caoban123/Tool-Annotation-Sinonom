"""Build a standalone notebook; bundle current OCR sources so GitHub is not required."""
import base64
import hashlib
import json
from pathlib import Path
import textwrap
import zlib

ROOT = Path(__file__).resolve().parents[1]


def build_ocr_han_notebook():
    files = ['OCR/han_runner.py', 'OCR/utils/__init__.py', 'OCR/utils/ocr_pipeline.py',
             'OCR/utils/checkpoints.py', 'OCR/utils/export_text.py', 'OCR/utils/page_order.py',
             'OCR/utils/render_pdf.py', 'OCR/requirements-han.txt',
             'OCR/assets/han_demo.png', 'OCR/assets/han_demo.txt']
    payload = json.dumps({name: base64.b64encode((ROOT / name).read_bytes()).decode() for name in files}).encode()
    encoded = base64.b64encode(zlib.compress(payload)).decode()
    cells = []

    def cell(kind, source):
        value = {'cell_type': kind, 'id': f'han-{len(cells)}', 'metadata': {},
                 'source': textwrap.dedent(source).strip() + '\n'}
        if kind == 'code':
            value.update(execution_count=None, outputs=[])
        cells.append(value)

    cell('markdown', '''
    # OCR chữ Hán — Colab / Kaggle / Jupyter

    **Cách chạy:** Colab chọn Runtime → Change runtime type → GPU; Kaggle chọn
    Settings → Accelerator → GPU và bật Internet. Sửa `INPUT_PATH` ở cell cấu hình,
    sau đó **Run all**. Không cần clone repo hay restart kernel khi chạy lần đầu.

    Notebook tự mang mã OCR hiện tại, dùng Transformers 5.1.0 trong môi trường riêng
    và giữ PyTorch/CUDA của nền tảng. Không cài PaddlePaddle/flash-attn, không vá attention/cache.
    Nếu chưa đưa tài liệu vào, notebook chạy ảnh Hán mẫu đi kèm (dữ liệu minh họa).
    Chỉ bật `USE_DEMO_IF_NO_INPUT` nếu muốn chạy mẫu; không thay thế tài liệu sai đường dẫn.

    Mô hình trả văn bản OCR, không phải tọa độ từng chữ. Cần đối chiếu scan để kiểm tra
    chữ hiếm và thứ tự đọc. `SPLIT_SPREAD=True` xử lý ảnh hai mặt sách dọc: phải rồi trái.
    Kết quả: `han.txt`, `han_metadata.json`, `han_ocr.zip` và checkpoint từng trang.
    ''')
    cell('code', '''
    # 1. Cấu hình (thay INPUT_PATH bằng PDF/PNG/JPG/TIFF của bạn)
    from pathlib import Path
    import os, sys, json, subprocess
    INPUT_PATH = ""  # VD Kaggle: /kaggle/input/ten-dataset/sach.pdf
    # Colab: tải file bằng bảng Files bên trái, rồi điền /content/sach.pdf
    START_PAGE = 1
    END_PAGE = 3  # None = đến cuối; tự giới hạn theo số trang tài liệu
    USE_DEMO_IF_NO_INPUT = True
    USE_GPU = True  # False cho CPU; model thật vẫn nặng và chạy chậm
    MODEL_ID = "PaddlePaddle/PaddleOCR-VL-1.6"
    MODEL_REVISION = None  # Có thể điền commit Hugging Face để tái lập weights
    MAX_NEW_TOKENS = 4096
    MAX_PIXELS = 1003520
    RENDER_SCALE = 2.0
    READING_ORDER = "rtl_vertical"
    SPLIT_SPREAD = False
    FORCE_REPROCESS = False
    # Điền thư mục Google Drive đã mount nếu cần checkpoint tồn tại sau khi hết phiên.
    CHECKPOINT_DIR = ""
    SMOKE = os.environ.get("OCR_NOTEBOOK_SMOKE") == "1"  # chỉ kiểm tra notebook, KHÔNG OCR
    if Path('/kaggle/working').is_dir():
        WORK_DIR = Path('/kaggle/working/han_ocr')
    elif Path('/content').is_dir():
        WORK_DIR = Path('/content/han_ocr')
    else:
        WORK_DIR = Path.cwd() / 'artifacts' / 'han_notebook'
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    print('Thư mục kết quả:', WORK_DIR)
    ''')
    bootstrap = '''
    # 2. Giải nén mã nguồn đi kèm, không phụ thuộc GitHub hoặc /content trên Kaggle
    import base64, zlib, hashlib
    BUNDLED_SOURCES = "__PAYLOAD__"
    packed = zlib.decompress(base64.b64decode(BUNDLED_SOURCES))
    assert hashlib.sha256(packed).hexdigest() == "__HASH__", 'Bundle bị hỏng'
    SOURCE_DIR = WORK_DIR / 'runtime'
    for relative, data in json.loads(packed).items():
        destination = SOURCE_DIR / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(base64.b64decode(data))
    print('Đã nạp mã OCR đi kèm notebook')
    '''
    cell('code', bootstrap.replace('__PAYLOAD__', encoded).replace('__HASH__', hashlib.sha256(payload).hexdigest()))
    cell('code', '''
    # 3. Chọn đầu vào rõ ràng, không tự tải bộ sách 660 MB
    input_file = Path(INPUT_PATH).expanduser() if INPUT_PATH else None
    if input_file is not None and not input_file.is_file():
        raise FileNotFoundError(f'INPUT_PATH không tồn tại: {input_file}')
    if input_file is None:
        roots = [Path('/kaggle/input')] if Path('/kaggle/input').is_dir() else [Path('/content')]
        found = sorted({p.resolve() for root in roots if root.exists() for p in root.rglob('*')
                        if p.is_file() and p.suffix.lower() in {'.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff'}
                        and WORK_DIR.resolve() not in p.resolve().parents
                        and '.cache' not in p.parts and '.config' not in p.parts})
        if len(found) == 1:
            input_file = found[0]
        elif len(found) > 1:
            print('Các tài liệu tìm thấy:', *map(str, found[:30]), sep='\\n')
            raise ValueError('Có nhiều tài liệu. Điền INPUT_PATH ở cell 1 rồi chạy lại.')
        elif USE_DEMO_IF_NO_INPUT:
            input_file = SOURCE_DIR / 'OCR/assets/han_demo.png'
            print('ĐANG CHẠY ẢNH HÁN MINH HỌA; chưa có tài liệu của bạn.')
        else:
            raise FileNotFoundError('Điền INPUT_PATH ở cell 1 trước khi chạy.')
    input_file = input_file.resolve()
    print('Tài liệu được chọn:', input_file)
    from IPython.display import display, FileLink
    if input_file.suffix.lower() != '.pdf':
        from PIL import Image
        with Image.open(input_file) as image:
            preview = image.copy()
            preview.thumbnail((700, 700))
            display(preview)
    ''')
    cell('code', '''
    # 4. Cài trong venv riêng; chạy OCR ở process mới nên không cần restart kernel
    import venv
    environment = dict(os.environ, PYTHONPATH=str(SOURCE_DIR), PYTHONUNBUFFERED='1',
                       USE_TF='0', USE_FLAX='0', TOKENIZERS_PARALLELISM='false', HF_HUB_DISABLE_XET='1')
    ENV_DIR = WORK_DIR / 'ocr_env'
    PYTHON = ENV_DIR / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not SMOKE:
        try:
            venv.EnvBuilder(with_pip=True, system_site_packages=True).create(ENV_DIR)
        except (subprocess.CalledProcessError, OSError) as error:
            # Some hosted Debian runtimes omit ensurepip. Bootstrap without
            # installing packages into the notebook kernel's environment.
            print('venv/ensurepip không sẵn sàng, dùng virtualenv:', error)
            bootstrap_dir = WORK_DIR / 'bootstrap'
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--target', str(bootstrap_dir),
                            'virtualenv>=20.26,<21'], check=True)
            bootstrap_env = dict(os.environ, PYTHONPATH=str(bootstrap_dir))
            subprocess.run([sys.executable, '-m', 'virtualenv', '--system-site-packages',
                            str(ENV_DIR)], env=bootstrap_env, check=True)
        # PyTorch và torchvision phải cùng build CUDA: giữ nguyên cặp của Colab/Kaggle.
        subprocess.run([str(PYTHON), '-c', 'import torch; print("PyTorch:", torch.__version__)'], check=True)
        subprocess.run([str(PYTHON), '-m', 'pip', 'install', '--disable-pip-version-check',
                        '-r', str(SOURCE_DIR / 'OCR/requirements-han.txt')], env=environment, check=True)
        preflight = """import torch, transformers
    from transformers import AutoModelForImageTextToText, AutoProcessor
    from transformers.models.paddleocr_vl.modeling_paddleocr_vl import PaddleOCRVLForConditionalGeneration
    print('Transformers:', transformers.__version__, 'CUDA:', torch.cuda.is_available())
    assert not __GPU__ or torch.cuda.is_available(), 'Bật GPU trong Settings của Kaggle hoặc Runtime của Colab'
    if torch.cuda.is_available():
        print(torch.cuda.get_device_name(0), 'BF16:', torch.cuda.is_bf16_supported())
    """.replace('__GPU__', repr(USE_GPU))
        subprocess.run([str(PYTHON), '-c', preflight], env=environment, check=True)
    else:
        print('SMOKE: bỏ qua cài đặt và model. Không phải kiểm chứng inference GPU.')
    ''')
    cell('code', '''
    # 5. Đọc số trang và ghi cấu hình đã kiểm tra
    if not SMOKE:
        count_code = "from pathlib import Path; from OCR.han_runner import page_count; import sys; print(page_count(Path(sys.argv[1])))"
        environment = dict(os.environ, PYTHONPATH=str(SOURCE_DIR), PYTHONUNBUFFERED='1',
                           USE_TF='0', USE_FLAX='0', TOKENIZERS_PARALLELISM='false', HF_HUB_DISABLE_XET='1')
        total_pages = int(subprocess.check_output([str(PYTHON), '-c', count_code, str(input_file)],
                                                  env=environment, text=True).strip())
    else:
        total_pages = 1
    end_page = total_pages if END_PAGE is None else min(END_PAGE, total_pages)
    if not 1 <= START_PAGE <= end_page <= total_pages:
        raise ValueError(f'START_PAGE/END_PAGE không hợp lệ; tài liệu có {total_pages} trang')
    config = dict(input_path=str(input_file), start_page=START_PAGE, end_page=end_page,
                  model_id=MODEL_ID, model_revision=MODEL_REVISION, use_gpu=USE_GPU,
                  max_new_tokens=MAX_NEW_TOKENS, max_pixels=MAX_PIXELS, render_scale=RENDER_SCALE,
                  reading_order=READING_ORDER, split_spread=SPLIT_SPREAD,
                  force_reprocess=FORCE_REPROCESS, output_dir=str(WORK_DIR / 'output'),
                  checkpoint_dir=CHECKPOINT_DIR or str(WORK_DIR / 'output/checkpoints'))
    config_file = WORK_DIR / 'config.json'
    config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(config, ensure_ascii=False, indent=2))
    ''')
    cell('code', '''
    # 6. OCR thật từng trang, log trực tiếp; dừng ngay nếu model/ảnh bị lỗi
    if not SMOKE:
        subprocess.run([str(PYTHON), '-u', '-m', 'OCR.han_runner', '--config', str(config_file)],
                       cwd=str(SOURCE_DIR), env=environment, check=True)
    else:
        print('SMOKE: không nhận dạng và không xuất han.txt.')
    ''')
    cell('code', '''
    # 7. Kiểm tra đầu ra và tải về (Kaggle: mở Output hoặc liên kết ZIP)
    if not SMOKE:
        output_dir = Path(config['output_dir'])
        metadata = json.loads((output_dir / 'han_metadata.json').read_text(encoding='utf-8'))
        text = (output_dir / 'han.txt').read_text(encoding='utf-8')
        assert len(metadata['pages']) == end_page - START_PAGE + 1
        assert text == metadata['full_text']
        assert not metadata['engine_info']['is_mock']
        print('Số trang:', metadata['total_pages'], '| Số ký tự:', len(text))
        print('Thời gian inference:', sum(p['inference_time_sec'] for p in metadata['pages'] if not p['is_cached']))
        blank = [p['page_number'] for p in metadata['pages'] if p['is_blank']]
        if blank:
            print('Cần kiểm tra trang không có text:', blank)
        print(text[:3000])
        for name in ('han.txt', 'han_metadata.json', 'han_ocr.zip'):
            display(FileLink(os.path.relpath(output_dir / name, Path.cwd())))
        if 'google.colab' in sys.modules:
            from google.colab import files
            files.download(str(output_dir / 'han_ocr.zip'))
    else:
        print('SMOKE HOÀN TẤT: cấu trúc, bundle và cấu hình hợp lệ; inference CHƯA CHẠY.')
    ''')
    cell('markdown', '''
    ## Nếu gặp lỗi
    - Thiếu GPU: bật GPU và chạy lại. T4/P100 dùng FP16; GPU hỗ trợ BF16 mới dùng BF16.
    - Không tải được model/package: bật Internet trên Kaggle; kiểm tra quota/mạng Hugging Face.
      Có thể đặt MODEL_ID thành thư mục weights đã đính kèm trong `/kaggle/input`.
    - Thiếu `torch`: dùng runtime GPU chuẩn của nền tảng (notebook giữ torch/CUDA có sẵn).
    - `torchvision::nms`, `librosa`, `numpy.dtype size changed`: runtime nền đã bị thay thư viện;
      khởi tạo session GPU sạch rồi Run all. Không chạy các cell cài đặt notebook cũ trước notebook này.
    - CUDA out of memory: giảm MAX_PIXELS (ví dụ 501760), bật SPLIT_SPREAD cho ảnh hai mặt.
    - Chạm giới hạn token: tăng MAX_NEW_TOKENS hoặc cắt nhỏ ảnh. Không cache trang bị cắt cụt.
    - Hết phiên: lưu ZIP/checkpoints. Khi mở phiên mới, đưa checkpoint vào thư mục writable
      và đặt CHECKPOINT_DIR trỏ tới đó. Cache được phân biệt theo hash tài liệu và cấu hình.

    Nguồn API: [model card chính thức](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6#paddleocr-vl-16-09b-usage-with-transformers).
    API Transformers là nhận dạng phần tử; không thay thế bộ phân tích bố cục đầy đủ của PaddleOCR.
    ''')
    notebook = {'cells': cells, 'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python', 'version': '3.10'},
        'accelerator': 'GPU', 'colab': {'provenance': []}}, 'nbformat': 4, 'nbformat_minor': 5}
    target = ROOT / 'OCR/notebooks/01_OCR_Han.ipynb'
    target.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return target


if __name__ == '__main__':
    print(build_ocr_han_notebook())
