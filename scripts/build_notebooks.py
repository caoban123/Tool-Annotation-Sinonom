"""
Script to build upgraded notebooks:
- Crawl/notebooks/01_Crawl_Text.ipynb
- OCR/notebooks/01_OCR_Han.ipynb
- OCR/notebooks/02_OCR_Viet.ipynb
- Web/notebooks/01_Semantic_Alignment.ipynb
"""

import json
from pathlib import Path

COLAB_TIP = (
    "> 💡 **Mẹo khi mở bằng nút 'Open In Colab'**:\n"
    "> - **Nếu repo ở chế độ Public:** Nhấp vào nút trên sẽ mở ngay notebook trên Google Colab.\n"
    "> - **Nếu repo ở chế độ Private (hoặc gặp lỗi 404):** Mở [Google Colab](https://colab.research.google.com) → Chọn thẻ **GitHub** → Tích chọn **'Include private repositories'** và cấp quyền GitHub → Chọn repository `caoban123/Tool-Annotation-Sinonom` và nhánh `main` (hoặc chuyển repository sang chế độ **Public** trong GitHub Settings)."
)

def build_crawl_notebook():
    cells = [
        {
            "cell_type": "markdown",
            "id": "intro_md",
            "metadata": {},
            "source": [
                "# Module 2 — Crawl & Trích Xuất Văn Bản (PDF Text & Web HTML)\n",
                "\n",
                "[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/Crawl/notebooks/01_Crawl_Text.ipynb)\n",
                "\n",
                f"{COLAB_TIP}\n",
                "\n",
                "Notebook này thực hiện trích xuất dữ liệu từ các tài liệu số hóa đã chuẩn hóa:\n",
                "- **Tự động kéo dữ liệu:** Tự động phát hiện và kéo tài liệu từ GitHub repo (`https://github.com/caoban123/CV01.git`) nếu chưa có sẵn local.\n",
                "- **Tự động phân loại:** Soi xét PDF để nhận diện **PDF_TEXT** (trích xuất text layer trực tiếp) hay **PDF_SCAN** (ảnh scan cần OCR).\n",
                "- **Tự động gán mã:** Gán mã đề tài `HVB_01`, mã tác phẩm, document ID, tính mã SHA-256 provenance theo hợp đồng chuẩn `plan.md`."
            ]
        },
        {
            "cell_type": "code",
            "id": "setup_code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. Cài đặt môi trường & Nạp thư viện\n",
                "import os\n",
                "import sys\n",
                "import subprocess\n",
                "from pathlib import Path\n",
                "\n",
                "# Tự động phát hiện và khởi tạo nếu chạy trên Google Colab\n",
                "if 'google.colab' in sys.modules:\n",
                "    colab_repo = Path('/content/Tool-Annotation-Sinonom')\n",
                "    if not colab_repo.exists() and not (Path('.').resolve() / 'Crawl').exists():\n",
                "        print('Đang chuẩn bị môi trường trên Google Colab...')\n",
                "        try:\n",
                "            subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/caoban123/Tool-Annotation-Sinonom.git', str(colab_repo)], check=True, capture_output=True)\n",
                "            print('✓ Đã nạp mã nguồn dự án thành công!')\n",
                "        except Exception as e:\n",
                "            print('⚠️ Lưu ý: Nếu repo ở chế độ Private, vui lòng cấp quyền GitHub hoặc tải thư mục dự án lên /content.')\n",
                "    for candidate in [colab_repo, Path('/content'), Path('.')]:\n",
                "        if (candidate / 'Crawl').exists():\n",
                "            os.chdir(str(candidate))\n",
                "            break\n",
                "    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'pypdf', 'pypdfium2', 'beautifulsoup4', 'pydantic', 'requests'], check=False)\n",
                "\n",
                "# Tự động xác định thư mục gốc của repository\n",
                "REPO_ROOT = Path('.').resolve()\n",
                "while REPO_ROOT.name and not (REPO_ROOT / 'Crawl').exists() and REPO_ROOT != REPO_ROOT.parent:\n",
                "    REPO_ROOT = REPO_ROOT.parent\n",
                "\n",
                "if str(REPO_ROOT) not in sys.path:\n",
                "    sys.path.insert(0, str(REPO_ROOT))\n",
                "\n",
                "from Crawl.utils.catalog import get_works_catalog, resolve_work, ensure_data_source\n",
                "from Crawl.utils.id_generator import generate_project_id, generate_document_id, compute_sha256, build_sidecar_metadata\n",
                "from Crawl.extractors.html_extractor import extract_from_html\n",
                "from Crawl.extractors.pdf_text_extractor import extract_from_pdf_text\n",
                "from OCR.utils.pdf_detector import inspect_pdf\n",
                "\n",
                "# Tự động đảm bảo nguồn tài liệu có sẵn (kéo từ GitHub nếu chạy trên Colab)\n",
                "source_dir = ensure_data_source(base_dir=str(REPO_ROOT / 'data' / 'source_materials'))\n",
                "print('✓ Hệ thống nạp thư viện và kiểm tra dữ liệu thành công!')"
            ]
        },
        {
            "cell_type": "code",
            "id": "catalog_code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 2. Danh mục tác phẩm & Lựa chọn tài liệu\n",
                "catalog = get_works_catalog()\n",
                "print('=== DANH MỤC CÁC TÁC PHẨM CÓ SẴN ===')\n",
                "for idx, (key, info) in enumerate(catalog.items(), 1):\n",
                "    print(f\"[{idx}] {key:15s} | {info['name']} ({info['author']})\")\n",
                "\n",
                "# Chọn tác phẩm cần trích xuất (HVNTDDC, LTHCLC_Q20_25, LTHCLC_Q46_49, VIET_SU_YEU, DVDDTB)\n",
                "SELECTED_WORK_KEY = 'LTHCLC_Q20_25'\n",
                "LANGUAGE = 'viet'  # 'han' hoặc 'viet'\n",
                "START_PAGE = 1    # Trang bắt đầu\n",
                "END_PAGE = 15     # Trang kết thúc mẫu (hoặc đặt None để bóc tách toàn bộ tài liệu)\n",
                "\n",
                "# Hoặc nếu bạn tự upload file PDF cá nhân lên Colab, hãy điền đường dẫn tại đây (nếu không để None):\n",
                "CUSTOM_PDF_PATH = None\n",
                "\n",
                "work_info = resolve_work(SELECTED_WORK_KEY, base_dir=str(source_dir))\n",
                "print(f\"\\nĐang chọn: {work_info['name']} ({work_info['ma_tac_pham']}) — Ngôn ngữ: {LANGUAGE.upper()}\")\n",
                "target_file = CUSTOM_PDF_PATH if (CUSTOM_PDF_PATH and Path(CUSTOM_PDF_PATH).exists()) else (work_info['han_abs_path'] if LANGUAGE == 'han' else work_info['viet_abs_path'])\n",
                "print(f\"Đường dẫn file: {target_file}\")"
            ]
        },
        {
            "cell_type": "code",
            "id": "inspect_code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 3. Tự động kiểm tra PDF Text vs PDF Scan\n",
                "pdf_info = inspect_pdf(target_file, sample_pages=5) if (target_file and Path(target_file).exists()) else {'pdf_type': 'PDF_MISSING', 'total_pages': 0}\n",
                "\n",
                "# Tự động phát hiện nếu file là Git LFS pointer (~130 bytes) hoặc không có trang nhị phân\n",
                "if not target_file or not Path(target_file).exists() or pdf_info.get('pdf_type') == 'PDF_LFS_POINTER' or pdf_info.get('total_pages', 0) == 0:\n",
                "    print(f'[LƯU Ý] File PDF ({target_file}) là Git LFS pointer (chưa kéo nhị phân từ GitHub LFS) hoặc không có trang hợp lệ.')\n",
                "    print('🔄 Tự động chuyển sang file PDF text mẫu fixture để chạy demo trơn tru: tests/fixtures/sample_text.pdf')\n",
                "    target_file = str(REPO_ROOT / 'tests' / 'fixtures' / 'sample_text.pdf')\n",
                "    pdf_info = inspect_pdf(target_file, sample_pages=5)\n",
                "\n",
                "print('=== KẾT QUẢ TỰ ĐỘNG PHÂN TÍCH PDF ===')\n",
                "print(f\"File đang xử lý:   {Path(target_file).name}\")\n",
                "print(f\"Loại tài liệu:     {pdf_info['pdf_type']}\")\n",
                "print(f\"Tổng số trang:     {pdf_info['total_pages']}\")\n",
                "print(f\"Ký tự mẫu/trang:   {pdf_info['avg_chars_per_page']}\")\n",
                "print(f\"Khuyến nghị:       {pdf_info['recommended_engine']}\")\n",
                "print(f\"Nhận định:         {pdf_info['reason']}\")\n",
                "\n",
                "if pdf_info['pdf_type'] == 'PDF_SCAN':\n",
                "    print('\\n[CẢNH BÁO] Đây là file scan ảnh. Khuyến nghị chạy bằng Module OCR (OCR/notebooks/01_OCR_Han.ipynb) để có độ chính xác cao nhất.')"
            ]
        },
        {
            "cell_type": "code",
            "id": "extract_code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 4. Trích xuất văn bản & Tự động gán mã ID chuẩn\n",
                "output_dir = REPO_ROOT / 'data' / 'crawled'\n",
                "output_dir.mkdir(parents=True, exist_ok=True)\n",
                "\n",
                "result = extract_from_pdf_text(target_file, start_page=START_PAGE, end_page=END_PAGE)\n",
                "extracted_text = result['text']\n",
                "\n",
                "# Tính mã SHA-256 provenance và sinh Document ID\n",
                "source_sha256 = compute_sha256(target_file)\n",
                "doc_id = generate_document_id(work_info['ma_tac_pham'], LANGUAGE, source_sha256)\n",
                "project_id = generate_project_id(work_info['ma_de_tai'], work_info['ma_tac_pham'])\n",
                "\n",
                "lines = [l.strip() for l in extracted_text.splitlines() if l.strip()]\n",
                "print(f'\\n✓ Đã trích xuất: {len(extracted_text)} ký tự ({len(lines)} câu/dòng)')\n",
                "print(f'Document ID: {doc_id}')\n",
                "print(f'Project ID:  {project_id}')\n",
                "print(f'SHA-256:     {source_sha256[:16]}...')\n",
                "\n",
                "print('\\n--- 5 DÒNG ĐẦU TIÊN ---')\n",
                "for line in lines[:5]:\n",
                "    print('>', line)"
            ]
        },
        {
            "cell_type": "code",
            "id": "save_code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 5. Lưu kết quả ra file chuẩn hóa phục vụ Web Studio\n",
                "import json\n",
                "\n",
                "out_txt = output_dir / f\"{LANGUAGE}.txt\"\n",
                "out_meta = output_dir / f\"{LANGUAGE}_metadata.json\"\n",
                "\n",
                "with open(out_txt, 'w', encoding='utf-8', newline='\\n') as f:\n",
                "    f.write(extracted_text)\n",
                "\n",
                "meta = build_sidecar_metadata(\n",
                "    ma_de_tai=work_info['ma_de_tai'],\n",
                "    ma_tac_pham=work_info['ma_tac_pham'],\n",
                "    tac_pham_name=work_info['name'],\n",
                "    language=LANGUAGE,\n",
                "    source_file_path=target_file,\n",
                "    total_segments=len(lines),\n",
                "    total_characters=len(extracted_text),\n",
                "    extractor_type='pdf_text_extractor' if pdf_info['pdf_type'] == 'PDF_TEXT' else 'pdf_scan_fallback',\n",
                "    hardware='cpu'\n",
                ")\n",
                "\n",
                "with open(out_meta, 'w', encoding='utf-8') as f:\n",
                "    json.dump(meta, f, ensure_ascii=False, indent=2)\n",
                "\n",
                "print(f'✓ Đã lưu file text sạch: {out_txt}')\n",
                "print(f'✓ Đã lưu metadata:   {out_meta}')\n",
                "print('\\nSẵn sàng tải lên Han–Viet Alignment Studio tại http://127.0.0.1:8000!')"
            ]
        }
    ]

    nb = {
        "cells": cells,
        "metadata": {"language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5
    }
    with open("Crawl/notebooks/01_Crawl_Text.ipynb", "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("Built Crawl/notebooks/01_Crawl_Text.ipynb")

def build_ocr_han_notebook():
    cells = [
        {
            "cell_type": "markdown",
            "id": "han_intro",
            "metadata": {},
            "source": [
                "# Module 1 — OCR Văn Bản Chữ Hán (PDF Scan / Ảnh Chụp)\n",
                "\n",
                "[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/OCR/notebooks/01_OCR_Han.ipynb)\n",
                "\n",
                f"{COLAB_TIP}\n",
                "\n",
                "Notebook này thực hiện nhận dạng chữ Hán phồn thể/cổ từ PDF scan ảnh chụp:\n",
                "- **Tự động kéo dữ liệu:** Kéo tài liệu từ `https://github.com/caoban123/CV01.git` nếu chạy trên Colab GPU.\n",
                "- **Tự động nhận diện:** Soi xem PDF đã có sẵn text layer chưa; nếu là PDF Scan thì render ảnh và OCR.\n",
                "- **Cơ chế Checkpoint:** Tự động lưu kết quả theo từng trang, bảo vệ chống mất mát dữ liệu khi Colab ngắt kết nối.\n",
                "- **Tự động sinh mã ID:** Gán mã tác phẩm, mã đề tài `HVB_01`, SHA-256 provenance và xuất `han.txt`."
            ]
        },
        {
            "cell_type": "code",
            "id": "han_setup",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. Cài đặt môi trường & Nạp thư viện OCR\n",
                "import os\n",
                "import sys\n",
                "import subprocess\n",
                "from pathlib import Path\n",
                "\n",
                "# Tự động phát hiện và khởi tạo nếu chạy trên Google Colab\n",
                "if 'google.colab' in sys.modules:\n",
                "    colab_repo = Path('/content/Tool-Annotation-Sinonom')\n",
                "    if not colab_repo.exists() and not (Path('.').resolve() / 'OCR').exists():\n",
                "        print('Đang chuẩn bị môi trường trên Google Colab...')\n",
                "        try:\n",
                "            subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/caoban123/Tool-Annotation-Sinonom.git', str(colab_repo)], check=True, capture_output=True)\n",
                "            print('✓ Đã nạp mã nguồn dự án thành công!')\n",
                "        except Exception as e:\n",
                "            print('⚠️ Lưu ý: Nếu repo ở chế độ Private, vui lòng cấp quyền GitHub hoặc tải thư mục dự án lên /content.')\n",
                "    for candidate in [colab_repo, Path('/content'), Path('.')]:\n",
                "        if (candidate / 'OCR').exists():\n",
                "            os.chdir(str(candidate))\n",
                "            break\n",
                "    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'pypdf', 'pypdfium2', 'pillow', 'pydantic', 'requests'], check=False)\n",
                "    # Để chạy nhận diện với GPU nâng cao trên Colab, bạn có thể uncomment dòng sau:\n",
                "    # subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'paddlepaddle-gpu', 'paddleocr'], check=False)\n",
                "\n",
                "REPO_ROOT = Path('.').resolve()\n",
                "while REPO_ROOT.name and not (REPO_ROOT / 'OCR').exists() and REPO_ROOT != REPO_ROOT.parent:\n",
                "    REPO_ROOT = REPO_ROOT.parent\n",
                "\n",
                "if str(REPO_ROOT) not in sys.path:\n",
                "    sys.path.insert(0, str(REPO_ROOT))\n",
                "\n",
                "from PIL import Image\n",
                "from Crawl.utils.catalog import get_works_catalog, resolve_work, ensure_data_source\n",
                "from Crawl.utils.id_generator import generate_project_id, generate_document_id, compute_sha256, build_sidecar_metadata\n",
                "from OCR.utils.ocr_pipeline import BaseOCREngine, OCRPipeline\n",
                "from OCR.utils.checkpoints import OCRCheckpointManager\n",
                "from OCR.utils.export_text import export_ocr_result\n",
                "from OCR.utils.pdf_detector import inspect_pdf\n",
                "\n",
                "source_dir = ensure_data_source(base_dir=str(REPO_ROOT / 'data' / 'source_materials'))\n",
                "print('✓ Nạp thư viện OCR và chuẩn bị dữ liệu thành công!')"
            ]
        },
        {
            "cell_type": "code",
            "id": "han_select",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 2. Lựa chọn tác phẩm chữ Hán & Tự động gán mã\n",
                "catalog = get_works_catalog()\n",
                "print('=== DANH MỤC CÁC TÁC PHẨM CÓ BẢN HÁN ===')\n",
                "for k, v in catalog.items():\n",
                "    if v['han_relpath']:\n",
                "        print(f\"- {k:15s}: {v['name']}\")\n",
                "\n",
                "# Chọn tác phẩm chữ Hán cần OCR (HVNTDDC, LTHCLC_Q20_25, LTHCLC_Q46_49, VIET_SU_YEU, DVDDTB)\n",
                "SELECTED_WORK_KEY = 'DVDDTB'\n",
                "READING_ORDER = 'ltr_horizontal'  # 'ltr_horizontal' hoặc 'rtl_vertical'\n",
                "USE_GPU = False                   # Bật True nếu chạy trên Colab GPU\n",
                "\n",
                "# Hoặc nếu bạn tự upload file ảnh/PDF chữ Hán lên Colab, gán đường dẫn vào đây:\n",
                "CUSTOM_INPUT_PATH = None\n",
                "\n",
                "work_info = resolve_work(SELECTED_WORK_KEY, base_dir=str(source_dir))\n",
                "target_pdf = CUSTOM_INPUT_PATH if (CUSTOM_INPUT_PATH and Path(CUSTOM_INPUT_PATH).exists()) else work_info['han_abs_path']\n",
                "print(f\"\\nĐang chọn: {work_info['name']} ({work_info['ma_tac_pham']})\")\n",
                "print(f\"Đường dẫn PDF: {target_pdf}\")"
            ]
        },
        {
            "cell_type": "code",
            "id": "han_inspect",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 3. Tự động soi xét cấu trúc PDF (Text vs Scan)\n",
                "target_file = target_pdf\n",
                "is_scan_image = False\n",
                "\n",
                "if target_file and target_file.endswith('.pdf') and Path(target_file).exists():\n",
                "    pdf_info = inspect_pdf(target_file, sample_pages=5)\n",
                "    # Tự động phát hiện nếu file chỉ là Git LFS pointer (~130 bytes) hoặc không có trang nhị phân\n",
                "    if pdf_info.get('pdf_type') == 'PDF_LFS_POINTER' or pdf_info.get('total_pages', 0) == 0:\n",
                "        print(f'[LƯU Ý] File PDF ({target_file}) là Git LFS pointer (chưa tải nhị phân từ GitHub LFS).')\n",
                "        print('🔄 Tự động chuyển sang ảnh scan Hán mẫu fixture để kiểm thử: tests/fixtures/sample_han_scan.png')\n",
                "        target_file = str(REPO_ROOT / 'tests' / 'fixtures' / 'sample_han_scan.png')\n",
                "        is_scan_image = True\n",
                "    else:\n",
                "        print('=== THÔNG SỐ TÀI LIỆU ===')\n",
                "        print(f\"Loại tài liệu:   {pdf_info['pdf_type']}\")\n",
                "        print(f\"Tổng số trang:   {pdf_info['total_pages']}\")\n",
                "        print(f\"Nhận định:       {pdf_info['reason']}\")\n",
                "elif not target_file or not Path(target_file).exists():\n",
                "    print(f'[LƯU Ý] Chưa thấy file PDF tại {target_pdf}. Dùng ảnh scan mẫu fixture...')\n",
                "    target_file = str(REPO_ROOT / 'tests' / 'fixtures' / 'sample_han_scan.png')\n",
                "    is_scan_image = True\n",
                "else:\n",
                "    is_scan_image = not target_file.endswith('.pdf')\n",
                "\n",
                "output_dir = REPO_ROOT / 'data' / 'ocr_output'\n",
                "output_dir.mkdir(parents=True, exist_ok=True)\n",
                "print(f'✓ File đầu vào OCR: {Path(target_file).name}')"
            ]
        },
        {
            "cell_type": "code",
            "id": "han_ocr",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 4. Khởi tạo Engine và Thực Thi Nhận Dạng (Kèm Checkpoint)\n",
                "engine = BaseOCREngine(model_name='han', use_gpu=USE_GPU)\n",
                "pipeline = OCRPipeline(engine=engine, reading_order=READING_ORDER)\n",
                "\n",
                "if target_file.endswith('.pdf'):\n",
                "    from OCR.utils.render_pdf import render_pdf_to_images\n",
                "    # Render mẫu 3 trang đầu để kiểm chứng nhanh\n",
                "    images = render_pdf_to_images(target_file, max_pages=3)\n",
                "else:\n",
                "    images = [Image.open(target_file)]\n",
                "    \n",
                "source_id = f\"{work_info['ma_tac_pham']}_han\"\n",
                "print(f\"Bắt đầu nhận dạng {len(images)} trang cho nguồn: {source_id}...\")\n",
                "result = pipeline.process_images(images, source_id=source_id)\n",
                "\n",
                "print('=== KẾT QUẢ OCR CHỮ HÁN ===')\n",
                "print(f\"Số ký tự nhận dạng: {len(result['full_text'])}\")\n",
                "print('\\n--- TRÍCH ĐOẠN VĂN BẢN ---')\n",
                "print(result['full_text'][:300])"
            ]
        },
        {
            "cell_type": "code",
            "id": "han_export",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 5. Xuất file han.txt và Metadata\n",
                "out_txt = output_dir / 'han.txt'\n",
                "out_meta = output_dir / 'han_metadata.json'\n",
                "export_ocr_result(result, out_txt, out_meta)\n",
                "\n",
                "print(f'✓ Đã xuất kết quả chữ Hán: {out_txt}')\n",
                "print(f'✓ Đã xuất metadata:          {out_meta}')\n",
                "print('\\nHoàn tất! Sẵn sàng đưa vào Studio để dóng hàng.')"
            ]
        }
    ]

    nb = {
        "cells": cells,
        "metadata": {"language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5
    }
    with open("OCR/notebooks/01_OCR_Han.ipynb", "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("Built OCR/notebooks/01_OCR_Han.ipynb")

def build_ocr_viet_notebook():
    cells = [
        {
            "cell_type": "markdown",
            "id": "viet_intro",
            "metadata": {},
            "source": [
                "# Module 1 — OCR Văn Bản Tiếng Việt (PDF Scan / Ảnh Dịch Nghĩa)\n",
                "\n",
                "[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/OCR/notebooks/02_OCR_Viet.ipynb)\n",
                "\n",
                f"{COLAB_TIP}\n",
                "\n",
                "Notebook này nhận dạng văn bản tiếng Việt từ bản dịch scan:\n",
                "- **Tự động kéo dữ liệu:** Kéo từ GitHub `https://github.com/caoban123/CV01.git` nếu chạy trên Colab.\n",
                "- **Tự động nhận diện:** Tự động phát hiện nếu bản dịch đã có sẵn text layer số hóa (PDF Text).\n",
                "- **Lưu Checkpoint:** Tự động lưu tiến trình từng trang.\n",
                "- **Tự động sinh mã ID:** Gán mã đề tài `HVB_01`, mã tác phẩm, và xuất `viet.txt`."
            ]
        },
        {
            "cell_type": "code",
            "id": "viet_setup",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. Cài đặt môi trường & Nạp thư viện OCR Việt\n",
                "import os\n",
                "import sys\n",
                "import subprocess\n",
                "from pathlib import Path\n",
                "\n",
                "# Tự động phát hiện và khởi tạo nếu chạy trên Google Colab\n",
                "if 'google.colab' in sys.modules:\n",
                "    colab_repo = Path('/content/Tool-Annotation-Sinonom')\n",
                "    if not colab_repo.exists() and not (Path('.').resolve() / 'OCR').exists():\n",
                "        print('Đang chuẩn bị môi trường trên Google Colab...')\n",
                "        try:\n",
                "            subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/caoban123/Tool-Annotation-Sinonom.git', str(colab_repo)], check=True, capture_output=True)\n",
                "            print('✓ Đã nạp mã nguồn dự án thành công!')\n",
                "        except Exception as e:\n",
                "            print('⚠️ Lưu ý: Nếu repo ở chế độ Private, vui lòng cấp quyền GitHub hoặc tải thư mục dự án lên /content.')\n",
                "    for candidate in [colab_repo, Path('/content'), Path('.')]:\n",
                "        if (candidate / 'OCR').exists():\n",
                "            os.chdir(str(candidate))\n",
                "            break\n",
                "    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'pypdf', 'pypdfium2', 'pillow', 'pydantic', 'requests'], check=False)\n",
                "\n",
                "REPO_ROOT = Path('.').resolve()\n",
                "while REPO_ROOT.name and not (REPO_ROOT / 'OCR').exists() and REPO_ROOT != REPO_ROOT.parent:\n",
                "    REPO_ROOT = REPO_ROOT.parent\n",
                "\n",
                "if str(REPO_ROOT) not in sys.path:\n",
                "    sys.path.insert(0, str(REPO_ROOT))\n",
                "\n",
                "from PIL import Image\n",
                "from Crawl.utils.catalog import get_works_catalog, resolve_work, ensure_data_source\n",
                "from Crawl.utils.id_generator import generate_project_id, generate_document_id, compute_sha256, build_sidecar_metadata\n",
                "from OCR.utils.ocr_pipeline import BaseOCREngine, OCRPipeline\n",
                "from OCR.utils.checkpoints import OCRCheckpointManager\n",
                "from OCR.utils.export_text import export_ocr_result\n",
                "from OCR.utils.pdf_detector import inspect_pdf\n",
                "\n",
                "source_dir = ensure_data_source(base_dir=str(REPO_ROOT / 'data' / 'source_materials'))\n",
                "print('✓ Nạp thư viện OCR Việt và chuẩn bị dữ liệu thành công!')"
            ]
        },
        {
            "cell_type": "code",
            "id": "viet_select",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 2. Lựa chọn tác phẩm bản dịch Việt & Tự động gán mã\n",
                "catalog = get_works_catalog()\n",
                "print('=== DANH MỤC CÁC TÁC PHẨM CÓ BẢN VIỆT ===')\n",
                "for k, v in catalog.items():\n",
                "    if v['viet_relpath']:\n",
                "        print(f\"- {k:15s}: {v['name']}\")\n",
                "\n",
                "# Chọn tác phẩm bản Việt cần OCR (HVNTDDC, LTHCLC_Q20_25, LTHCLC_Q46_49, DVDDTB)\n",
                "SELECTED_WORK_KEY = 'DVDDTB'\n",
                "USE_GPU = False\n",
                "\n",
                "# Hoặc nếu bạn tự upload file ảnh/PDF bản dịch Việt lên Colab, gán đường dẫn vào đây:\n",
                "CUSTOM_INPUT_PATH = None\n",
                "\n",
                "work_info = resolve_work(SELECTED_WORK_KEY, base_dir=str(source_dir))\n",
                "target_pdf = CUSTOM_INPUT_PATH if (CUSTOM_INPUT_PATH and Path(CUSTOM_INPUT_PATH).exists()) else work_info['viet_abs_path']\n",
                "print(f\"\\nĐang chọn: {work_info['name']} ({work_info['ma_tac_pham']})\")\n",
                "print(f\"Đường dẫn PDF: {target_pdf}\")"
            ]
        },
        {
            "cell_type": "code",
            "id": "viet_inspect",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 3. Tự động soi xét cấu trúc PDF (Text vs Scan)\n",
                "target_file = target_pdf\n",
                "is_scan_image = False\n",
                "\n",
                "if target_file and target_file.endswith('.pdf') and Path(target_file).exists():\n",
                "    pdf_info = inspect_pdf(target_file, sample_pages=5)\n",
                "    # Tự động phát hiện nếu file là Git LFS pointer (~130 bytes) hoặc không có trang nhị phân\n",
                "    if pdf_info.get('pdf_type') == 'PDF_LFS_POINTER' or pdf_info.get('total_pages', 0) == 0:\n",
                "        print(f'[LƯU Ý] File PDF ({target_file}) là Git LFS pointer (chưa tải nhị phân từ GitHub LFS).')\n",
                "        print('🔄 Tự động chuyển sang ảnh scan Việt mẫu fixture để kiểm thử: tests/fixtures/sample_viet_scan.png')\n",
                "        target_file = str(REPO_ROOT / 'tests' / 'fixtures' / 'sample_viet_scan.png')\n",
                "        is_scan_image = True\n",
                "    else:\n",
                "        print('=== THÔNG SỐ TÀI LIỆU ===')\n",
                "        print(f\"Loại tài liệu:   {pdf_info['pdf_type']}\")\n",
                "        print(f\"Tổng số trang:   {pdf_info['total_pages']}\")\n",
                "        print(f\"Nhận định:       {pdf_info['reason']}\")\n",
                "elif not target_file or not Path(target_file).exists():\n",
                "    print(f'[LƯU Ý] Chưa thấy file PDF tại {target_pdf}. Dùng ảnh scan mẫu fixture...')\n",
                "    target_file = str(REPO_ROOT / 'tests' / 'fixtures' / 'sample_viet_scan.png')\n",
                "    is_scan_image = True\n",
                "else:\n",
                "    is_scan_image = not target_file.endswith('.pdf')\n",
                "\n",
                "output_dir = REPO_ROOT / 'data' / 'ocr_output'\n",
                "output_dir.mkdir(parents=True, exist_ok=True)\n",
                "print(f'✓ File đầu vào OCR: {Path(target_file).name}')"
            ]
        },
        {
            "cell_type": "code",
            "id": "viet_ocr",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 4. Khởi tạo Engine và Thực Thi Nhận Dạng (Kèm Checkpoint)\n",
                "engine = BaseOCREngine(model_name='viet', use_gpu=USE_GPU)\n",
                "pipeline = OCRPipeline(engine=engine, reading_order='ltr_horizontal')\n",
                "\n",
                "if target_file.endswith('.pdf'):\n",
                "    from OCR.utils.render_pdf import render_pdf_to_images\n",
                "    images = render_pdf_to_images(target_file, max_pages=3)\n",
                "else:\n",
                "    images = [Image.open(target_file)]\n",
                "\n",
                "source_id = f\"{work_info['ma_tac_pham']}_viet\"\n",
                "print(f\"Bắt đầu nhận dạng {len(images)} trang cho nguồn: {source_id}...\")\n",
                "result = pipeline.process_images(images, source_id=source_id)\n",
                "\n",
                "print('=== KẾT QUẢ OCR TIẾNG VIỆT ===')\n",
                "print(f\"Số ký tự nhận dạng: {len(result['full_text'])}\")\n",
                "print('\\n--- TRÍCH ĐOẠN VĂN BẢN ---')\n",
                "print(result['full_text'][:300])"
            ]
        },
        {
            "cell_type": "code",
            "id": "viet_export",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 5. Xuất file viet.txt và Metadata\n",
                "out_txt = output_dir / 'viet.txt'\n",
                "out_meta = output_dir / 'viet_metadata.json'\n",
                "export_ocr_result(result, out_txt, out_meta)\n",
                "\n",
                "print(f'✓ Đã xuất kết quả tiếng Việt: {out_txt}')\n",
                "print(f'✓ Đã xuất metadata:            {out_meta}')\n",
                "print('\\nHoàn tất! Sẵn sàng đưa vào Studio để dóng hàng.')"
            ]
        }
    ]

    nb = {
        "cells": cells,
        "metadata": {"language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5
    }
    with open("OCR/notebooks/02_OCR_Viet.ipynb", "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("Built OCR/notebooks/02_OCR_Viet.ipynb")

def build_semantic_alignment_notebook():
    cells = [
        {
            "cell_type": "markdown",
            "id": "align_intro",
            "metadata": {},
            "source": [
                "# Module Bổ Trợ — Semantic Alignment (AI Gợi Ý Dóng Hàng Song Ngữ)\n",
                "\n",
                "[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/Web/notebooks/01_Semantic_Alignment.ipynb)\n",
                "\n",
                f"{COLAB_TIP}\n",
                "\n",
                "Notebook này đọc gói phân đoạn `segments_export.json` do Web Studio xuất, áp dụng mô hình embedding (Qwen3-Embedding / LaBSE hoặc baseline sim) cùng thuật toán quy hoạch động đơn điệu để tìm gợi ý dóng hàng 1-1, 1-n, n-1, n-m.\n",
                "Kết quả xuất ra file `suggestions.json` để nhập trở lại vào Web Studio."
            ]
        },
        {
            "cell_type": "code",
            "id": "align_setup",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. Cài đặt và nạp thư viện\n",
                "import os\n",
                "import sys\n",
                "import subprocess\n",
                "from pathlib import Path\n",
                "\n",
                "# Tự động phát hiện và khởi tạo nếu chạy trên Google Colab\n",
                "if 'google.colab' in sys.modules:\n",
                "    colab_repo = Path('/content/Tool-Annotation-Sinonom')\n",
                "    if not colab_repo.exists() and not (Path('.').resolve() / 'Web').exists():\n",
                "        print('Đang chuẩn bị môi trường trên Google Colab...')\n",
                "        try:\n",
                "            subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/caoban123/Tool-Annotation-Sinonom.git', str(colab_repo)], check=True, capture_output=True)\n",
                "            print('✓ Đã nạp mã nguồn dự án thành công!')\n",
                "        except Exception as e:\n",
                "            print('⚠️ Lưu ý: Nếu repo ở chế độ Private, vui lòng cấp quyền GitHub hoặc tải thư mục dự án lên /content.')\n",
                "    for candidate in [colab_repo, Path('/content'), Path('.')]:\n",
                "        if (candidate / 'Web').exists():\n",
                "            os.chdir(str(candidate))\n",
                "            break\n",
                "    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'pydantic', 'sentence-transformers', 'torch'], check=False)\n",
                "\n",
                "REPO_ROOT = Path('.').resolve()\n",
                "while REPO_ROOT.name and not (REPO_ROOT / 'Web').exists() and REPO_ROOT != REPO_ROOT.parent:\n",
                "    REPO_ROOT = REPO_ROOT.parent\n",
                "\n",
                "if str(REPO_ROOT) not in sys.path:\n",
                "    sys.path.insert(0, str(REPO_ROOT))\n",
                "\n",
                "from Web.ai.prepare_segments import load_segments_manifest, split_han_viet_segments\n",
                "from Web.ai.candidate_generation import DeterministicSimAdapter, RealModelAdapter\n",
                "from Web.ai.monotonic_alignment import align_segments_monotonic\n",
                "from Web.ai.export_suggestions import create_suggestions_file\n",
                "print('✓ Đã nạp module AI Semantic Alignment thành công!')"
            ]
        },
        {
            "cell_type": "code",
            "id": "align_config",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 2. Cấu hình đầu vào và lựa chọn mô hình\n",
                "# Đường dẫn file segments tải về từ Web Studio\n",
                "INPUT_SEGMENTS_PATH = 'data/segments_export.json'\n",
                "MODEL_CHOICE = 'deterministic_baseline'  # Hoặc 'LaBSE', 'Qwen3-Embedding-0.6B'\n",
                "OUTPUT_FILE = Path('data/suggestions.json')\n",
                "\n",
                "# Tạo fixture giả lập nếu chưa có file export từ Web\n",
                "if not Path(INPUT_SEGMENTS_PATH).exists():\n",
                "    Path('data').mkdir(parents=True, exist_ok=True)\n",
                "    import json\n",
                "    dummy_manifest = {\n",
                "        'schema_version': '1.0',\n",
                "        'project_id': 'proj_demo',\n",
                "        'revision': 1,\n",
                "        'source_sha256_han': 'abc123han',\n",
                "        'source_sha256_viet': 'def456viet',\n",
                "        'segments': [\n",
                "            {'segment_id': 'h1', 'language': 'han', 'order_index': 0, 'text': '古南交，周號越裳。', 'active': True},\n",
                "            {'segment_id': 'h2', 'language': 'han', 'order_index': 1, 'text': '秦始皇置象郡。', 'active': True},\n",
                "            {'segment_id': 'v1', 'language': 'viet', 'order_index': 0, 'text': 'Đất Nam Giao xưa, nhà Chu gọi là Việt Thường.', 'active': True},\n",
                "            {'segment_id': 'v2', 'language': 'viet', 'order_index': 1, 'text': 'Nhà Tần đặt quận Tượng.', 'active': True},\n",
                "            {'segment_id': 'v3', 'language': 'viet', 'order_index': 2, 'text': 'Lại chia đặt các quan cai trị.', 'active': True}\n",
                "        ]\n",
                "    }\n",
                "    with open(INPUT_SEGMENTS_PATH, 'w', encoding='utf-8') as f:\n",
                "        json.dump(dummy_manifest, f, ensure_ascii=False, indent=2)\n",
                "    print('✓ Đã tạo demo data/segments_export.json')"
            ]
        },
        {
            "cell_type": "code",
            "id": "align_run",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 3. Nạp phân đoạn và chạy tìm gợi ý dóng hàng\n",
                "manifest = load_segments_manifest(INPUT_SEGMENTS_PATH)\n",
                "han_segs, viet_segs = split_han_viet_segments(manifest)\n",
                "\n",
                "print(f'Tổng phân đoạn Hán:  {len(han_segs)}')\n",
                "print(f'Tổng phân đoạn Việt: {len(viet_segs)}')\n",
                "\n",
                "if MODEL_CHOICE == 'deterministic_baseline':\n",
                "    scorer = DeterministicSimAdapter()\n",
                "else:\n",
                "    scorer = RealModelAdapter(MODEL_CHOICE)\n",
                "\n",
                "suggestions = align_segments_monotonic(han_segs, viet_segs, scorer)\n",
                "print(f'\\n✓ Đã tìm thấy {len(suggestions)} gợi ý dóng hàng!')\n",
                "for s in suggestions[:5]:\n",
                "    print(f\"  [{s['alignment_type']}] Score={s['score']:.2f} | Han: {s['han_ids']} <-> Viet: {s['viet_ids']}\")"
            ]
        },
        {
            "cell_type": "code",
            "id": "align_export",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 4. Xuất file suggestions.json đúng schema\n",
                "res = create_suggestions_file(manifest, suggestions, model_name=MODEL_CHOICE, output_path=OUTPUT_FILE)\n",
                "print(f'✓ Đã lưu gợi ý: {OUTPUT_FILE}')\n",
                "print(f'✓ Tổng số gợi ý: {len(res[\"suggestions\"])}')\n",
                "print('\\nSẵn sàng nhập suggestions.json vào Web Studio tại http://127.0.0.1:8000!')"
            ]
        }
    ]

    nb = {
        "cells": cells,
        "metadata": {"language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5
    }
    with open("Web/notebooks/01_Semantic_Alignment.ipynb", "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("Built Web/notebooks/01_Semantic_Alignment.ipynb")

if __name__ == "__main__":
    build_crawl_notebook()
    build_ocr_han_notebook()
    build_ocr_viet_notebook()
    build_semantic_alignment_notebook()
    print("All 4 notebooks built successfully!")
