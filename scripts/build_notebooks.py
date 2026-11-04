"""
Script to build upgraded notebooks fully optimized for Google Colab First workflow:
- Crawl/notebooks/01_Crawl_Text.ipynb
- OCR/notebooks/01_OCR_Han.ipynb
- OCR/notebooks/02_OCR_Viet.ipynb
- Web/notebooks/01_Semantic_Alignment.ipynb
"""

import json
from pathlib import Path

COLAB_HEADER = (
    "> 🚀 **Chế độ Mặc Định Google Colab (GPU Khuyến Nghị)**\n"
    "> - Notebook đã được tối ưu chạy trực tiếp 1-click trên Google Colab.\n"
    "> - Khuyến nghị bật GPU: Vào menu **Runtime** → **Change runtime type** → Chọn **T4 GPU** để tăng tốc nhận dạng gấp 10-20 lần.\n"
    "> - Toàn bộ dữ liệu sách cổ (660MB PDF) và mô hình AI sẽ được tự động tải về phiên làm việc."
)

def build_crawl_notebook():
    cells = [
        {
            "cell_type": "markdown",
            "id": "intro_md",
            "metadata": {},
            "source": [
                "# Module 2 — Crawl & Trích Xuất Văn Bản Số Hóa (PDF Text & Web HTML)\n",
                "\n",
                "[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/Crawl/notebooks/01_Crawl_Text.ipynb)\n",
                "\n",
                f"{COLAB_HEADER}\n",
                "\n",
                "Notebook này thực hiện trích xuất dữ liệu từ các tài liệu số hóa đã chuẩn hóa:\n",
                "- **Tự động kéo dữ liệu 660MB:** Tự động tải toàn bộ kho sách cổ PDF gốc từ Google Drive vào Colab.\n",
                "- **Tự động phân loại:** Soi xét PDF để nhận diện **PDF_TEXT** (trích xuất text layer trực tiếp) hay **PDF_SCAN** (ảnh scan cần OCR).\n",
                "- **Tự động gán mã:** Gán mã đề tài `HVB_01`, mã tác phẩm, document ID, tính mã SHA-256 provenance theo hợp đồng chuẩn."
            ]
        },
        {
            "cell_type": "code",
            "id": "setup_code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. Khởi tạo môi trường Colab & Tự động tải kho dữ liệu 660MB\n",
                "import os\n",
                "import sys\n",
                "import subprocess\n",
                "from pathlib import Path\n",
                "\n",
                "if 'google.colab' in sys.modules:\n",
                "    colab_repo = Path('/content/Tool-Annotation-Sinonom')\n",
                "    if not colab_repo.exists() and not (Path('.').resolve() / 'Crawl').exists():\n",
                "        print('Đang tải mã nguồn hệ thống về Google Colab...')\n",
                "        try:\n",
                "            subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/caoban123/Tool-Annotation-Sinonom.git', str(colab_repo)], check=True, capture_output=True)\n",
                "            print('✓ Tải mã nguồn thành công!')\n",
                "        except Exception as e:\n",
                "            print(f'Thông báo: {e}')\n",
                "    for candidate in [colab_repo, Path('/content'), Path('.')]:\n",
                "        if (candidate / 'Crawl').exists():\n",
                "            os.chdir(str(candidate))\n",
                "            break\n",
                "    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'pypdf', 'pypdfium2', 'beautifulsoup4', 'pydantic', 'requests', 'gdown'], check=False)\n",
                "\n",
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
                "# Tự động kéo 660MB tài liệu PDF gốc từ link Google Drive\n",
                "source_dir = ensure_data_source(base_dir=str(REPO_ROOT / 'data' / 'source_materials'))\n",
                "print('✓ Hệ thống sẵn sàng làm việc!')"
            ]
        },
        {
            "cell_type": "code",
            "id": "catalog_code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 2. Lựa chọn tác phẩm cần trích xuất văn bản\n",
                "catalog = get_works_catalog()\n",
                "print('=== DANH MỤC CÁC TÁC PHẨM CÓ SẴN ===')\n",
                "for idx, (key, info) in enumerate(catalog.items(), 1):\n",
                "    print(f\"[{idx}] {key:15s} | {info['name']} ({info['author']})\")\n",
                "\n",
                "# Lựa chọn tác phẩm: HVNTDDC, LTHCLC_Q20_25, LTHCLC_Q46_49, VIET_SU_YEU, DVDDTB\n",
                "SELECTED_WORK_KEY = 'LTHCLC_Q20_25'\n",
                "LANGUAGE = 'viet'  # 'han' hoặc 'viet'\n",
                "START_PAGE = 1    # Trang bắt đầu\n",
                "END_PAGE = 20     # Trang kết thúc (đặt None để trích xuất toàn bộ sách)\n",
                "\n",
                "work_info = resolve_work(SELECTED_WORK_KEY, base_dir=str(source_dir))\n",
                "target_file = work_info['han_abs_path'] if LANGUAGE == 'han' else work_info['viet_abs_path']\n",
                "print(f\"\\nĐang chọn: {work_info['name']} ({work_info['ma_tac_pham']}) — Ngôn ngữ: {LANGUAGE.upper()}\")\n",
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
                "if not target_file or not Path(target_file).exists() or pdf_info.get('total_pages', 0) == 0:\n",
                "    print(f'[LƯU Ý] Chưa thấy file PDF hoặc file rỗng. Chuyển sang file mẫu kiểm thử: tests/fixtures/sample_text.pdf')\n",
                "    target_file = str(REPO_ROOT / 'tests' / 'fixtures' / 'sample_text.pdf')\n",
                "    pdf_info = inspect_pdf(target_file, sample_pages=5)\n",
                "\n",
                "print('=== KẾT QUẢ TỰ ĐỘNG PHÂN TÍCH PDF ===')\n",
                "print(f\"Tệp tin:           {Path(target_file).name}\")\n",
                "print(f\"Loại tài liệu:     {pdf_info['pdf_type']}\")\n",
                "print(f\"Tổng số trang:     {pdf_info['total_pages']}\")\n",
                "print(f\"Ký tự mẫu/trang:   {pdf_info['avg_chars_per_page']}\")\n",
                "print(f\"Khuyến nghị:       {pdf_info['recommended_engine']}\")\n",
                "print(f\"Nhận định:         {pdf_info['reason']}\")\n",
                "\n",
                "if pdf_info['pdf_type'] == 'PDF_SCAN':\n",
                "    print('\\n[LƯU Ý] Đây là bản scan ảnh. Hãy mở notebook OCR (OCR/notebooks/01_OCR_Han.ipynb hoặc 02_OCR_Viet.ipynb) để nhận dạng.')"
            ]
        },
        {
            "cell_type": "code",
            "id": "extract_code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 4. Trích xuất văn bản thực tế & Tự động gán mã định danh\n",
                "output_dir = REPO_ROOT / 'data' / 'crawled'\n",
                "output_dir.mkdir(parents=True, exist_ok=True)\n",
                "\n",
                "result = extract_from_pdf_text(target_file, start_page=START_PAGE, end_page=END_PAGE)\n",
                "extracted_text = result['text']\n",
                "\n",
                "# Tính mã SHA-256 provenance và sinh Document ID, Project ID\n",
                "source_sha256 = compute_sha256(target_file)\n",
                "doc_id = generate_document_id(work_info['ma_tac_pham'], LANGUAGE, source_sha256)\n",
                "project_id = generate_project_id(work_info['ma_de_tai'], work_info['ma_tac_pham'])\n",
                "\n",
                "lines = [l.strip() for l in extracted_text.splitlines() if l.strip()]\n",
                "print(f'\\n✓ Đã trích xuất thành công: {len(extracted_text)} ký tự ({len(lines)} đoạn/câu)')\n",
                "print(f'Document ID: {doc_id}')\n",
                "print(f'Project ID:  {project_id}')\n",
                "print(f'SHA-256:     {source_sha256[:16]}...')\n",
                "\n",
                "print('\\n--- 5 ĐOẠN ĐẦU TIÊN ---')\n",
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
                "# 5. Lưu kết quả ra file chuẩn hóa & Tải về máy tính cá nhân\n",
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
                "    extractor_type='pdf_text_extractor',\n",
                "    hardware='colab'\n",
                ")\n",
                "\n",
                "with open(out_meta, 'w', encoding='utf-8') as f:\n",
                "    json.dump(meta, f, ensure_ascii=False, indent=2)\n",
                "\n",
                "print(f'✓ Đã lưu file text:     {out_txt}')\n",
                "print(f'✓ Đã lưu file metadata: {out_meta}')\n",
                "\n",
                "# Tự động tải file text về máy tính để nạp vào Web Studio cục bộ\n",
                "if 'google.colab' in sys.modules:\n",
                "    from google.colab import files\n",
                "    print('\\nĐang chuẩn bị tải file về máy tính của bạn...')\n",
                "    files.download(str(out_txt))"
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
    # Keep all-notebooks generation on the same portable implementation.
    import sys
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from build_han_notebook import build_ocr_han_notebook as build
    return build()


def build_ocr_viet_notebook():
    import sys
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from build_viet_notebook import build_ocr_viet_notebook as build
    return build()


def build_semantic_alignment_notebook():
    cells = [
        {
            "cell_type": "markdown",
            "id": "align_intro",
            "metadata": {},
            "source": [
                "# Module Bổ Trợ — Semantic Alignment (AI Gợi Ý Dóng Hàng Bằng Embedding Trên GPU)\n",
                "\n",
                "[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/Web/notebooks/01_Semantic_Alignment.ipynb)\n",
                "\n",
                f"{COLAB_HEADER}\n",
                "\n",
                "Notebook này áp dụng mô hình embedding đa ngữ cao cấp (**LaBSE / Qwen3-Embedding**) trên Colab GPU để tìm gợi ý dóng hàng câu/đoạn Hán – Việt:\n",
                "- **Nạp các đoạn câu:** Đọc gói phân đoạn `segments_export.json` từ Web Studio xuất ra.\n",
                "- **Trích xuất Vector Ngữ Nghĩa:** Mô hình nhúng biểu diễn câu Hán và câu Việt vào không gian vector chung.\n",
                "- **Quy hoạch động đơn điệu:** Tự động tìm cặp nối tối ưu (1-1, 1-N, N-1, N-M).\n",
                "- **Xuất file `suggestions.json`:** Tự động tải về máy cá nhân để nhập trở lại vào Web Studio."
            ]
        },
        {
            "cell_type": "code",
            "id": "align_setup",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. Khởi tạo môi trường Colab & Nạp mô hình Sentence-Transformers\n",
                "import os\n",
                "import sys\n",
                "import subprocess\n",
                "from pathlib import Path\n",
                "\n",
                "if 'google.colab' in sys.modules:\n",
                "    colab_repo = Path('/content/Tool-Annotation-Sinonom')\n",
                "    if not colab_repo.exists() and not (Path('.').resolve() / 'Web').exists():\n",
                "        print('Đang tải mã nguồn dự án về Google Colab...')\n",
                "        try:\n",
                "            subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/caoban123/Tool-Annotation-Sinonom.git', str(colab_repo)], check=True, capture_output=True)\n",
                "            print('✓ Tải mã nguồn thành công!')\n",
                "        except Exception as e:\n",
                "            print(f'Thông báo: {e}')\n",
                "    for candidate in [colab_repo, Path('/content'), Path('.')]:\n",
                "        if (candidate / 'Web').exists():\n",
                "            os.chdir(str(candidate))\n",
                "            break\n",
                "            \n",
                "    print('Đang cài đặt thư viện Sentence-Transformers & PyTorch...')\n",
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
                "print('✓ Đã nạp thành công module AI Semantic Alignment!')"
            ]
        },
        {
            "cell_type": "code",
            "id": "align_config",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 2. Cấu hình tệp đầu vào & Mô hình AI Embedding\n",
                "INPUT_SEGMENTS_PATH = 'data/segments_export.json'\n",
                "# Các lựa chọn mô hình AI: 'sentence-transformers/LaBSE' (Khuyên dùng GPU), 'Qwen/Qwen3-Embedding-0.6B', hoặc 'deterministic_baseline'\n",
                "MODEL_CHOICE = 'sentence-transformers/LaBSE' if 'google.colab' in sys.modules else 'deterministic_baseline'\n",
                "OUTPUT_FILE = Path('data/suggestions.json')\n",
                "\n",
                "# Tạo fixture kiểm thử nếu chưa tải file xuất từ Web Studio\n",
                "if not Path(INPUT_SEGMENTS_PATH).exists():\n",
                "    Path('data').mkdir(parents=True, exist_ok=True)\n",
                "    import json\n",
                "    dummy_manifest = {\n",
                "        'schema_version': '1.0',\n",
                "        'project_id': 'proj_colab_demo',\n",
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
                "    print('✓ Đã tạo mẫu data/segments_export.json để kiểm thử.')\n",
                "else:\n",
                "    print(f'✓ Đã tìm thấy file phân đoạn: {INPUT_SEGMENTS_PATH}')"
            ]
        },
        {
            "cell_type": "code",
            "id": "align_run",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 3. Nạp phân đoạn & Khởi chạy thuật toán AI Gợi Ý Dóng Hàng\n",
                "manifest = load_segments_manifest(INPUT_SEGMENTS_PATH)\n",
                "han_segs, viet_segs = split_han_viet_segments(manifest)\n",
                "\n",
                "print(f'Tổng số câu Hán:  {len(han_segs)}')\n",
                "print(f'Tổng số câu Việt: {len(viet_segs)}')\n",
                "print(f'Đang tính toán với mô hình: {MODEL_CHOICE}...')\n",
                "\n",
                "try:\n",
                "    if MODEL_CHOICE == 'deterministic_baseline':\n",
                "        scorer = DeterministicSimAdapter()\n",
                "    else:\n",
                "        scorer = RealModelAdapter(MODEL_CHOICE)\n",
                "except Exception as e:\n",
                "    print(f'Cảnh báo: Không thể tải mô hình {MODEL_CHOICE} ({e}), chuyển sang baseline...')\n",
                "    scorer = DeterministicSimAdapter()\n",
                "\n",
                "suggestions = align_segments_monotonic(han_segs, viet_segs, scorer)\n",
                "print(f'\\n🚀 Đã tìm thấy {len(suggestions)} cặp gợi ý dóng hàng!')\n",
                "for s in suggestions[:10]:\n",
                "    print(f\"  [{s['alignment_type']}] Score={s['score']:.2f} | Hán: {s['han_ids']} <===> Việt: {s['viet_ids']}\")"
            ]
        },
        {
            "cell_type": "code",
            "id": "align_export",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 4. Xuất file suggestions.json & Tải về máy tính cá nhân\n",
                "res = create_suggestions_file(manifest, suggestions, model_name=MODEL_CHOICE, output_path=OUTPUT_FILE)\n",
                "print(f'✓ Đã lưu file kết quả: {OUTPUT_FILE}')\n",
                "print(f'✓ Tổng số cặp gợi ý:   {len(res[\"suggestions\"])}')\n",
                "\n",
                "# Tự động tải file suggestions.json về máy tính để nạp vào Web Studio cục bộ\n",
                "if 'google.colab' in sys.modules:\n",
                "    from google.colab import files\n",
                "    print('\\nĐang chuẩn bị tải file suggestions.json về máy tính của bạn...')\n",
                "    files.download(str(OUTPUT_FILE))"
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
    print("All 4 Colab-First notebooks built successfully!")
