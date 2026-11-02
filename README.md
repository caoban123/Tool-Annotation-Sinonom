# Han–Viet Alignment Studio

> Hệ thống phần mềm dóng hàng song ngữ Hán – Việt cấp câu/đoạn chuyên dụng cho đồ án xử lý ngôn ngữ tự nhiên (NLP).

Phần mềm được thiết kế theo triết lý **Local-First độc lập**: Mỗi thành viên trong nhóm 4 sinh viên tự cài đặt và chạy ứng dụng cục bộ trên máy tính cá nhân, không chia sẻ backend, không dùng database đám mây, đảm bảo tính bảo mật và độc lập trong quá trình xử lý tài liệu được phân công.

---

## 1. Yêu Cầu Hệ Thống & Phiên Bản Hỗ Trợ
- **Hệ điều hành**: Windows 10/11, macOS, Linux (Ubuntu/Debian/Fedora).
- **Python hỗ trợ**: **Python 3.10, Python 3.11, Python 3.12** (Đã kiểm nghiệm đạt 100% trên Python 3.10.5 64-bit).
- **Mạng**: Không cần kết nối Internet sau khi cài đặt thư viện; ứng dụng chạy offline trên `127.0.0.1:8000`.

---

## 2. Hướng Dẫn Cài Đặt & Chạy Web Bằng 1 Lệnh

### Cách 1: Chạy trực tiếp (Khuyến nghị cho sinh viên)
- **Trên Windows**:
  Nhấp đúp vào file `Web/run.bat`
- **Trên macOS / Linux**:
  Mở terminal và gõ:
  ```bash
  bash Web/run.sh
  ```

### Cách 2: Tạo môi trường ảo venv thủ công
```bash
# 1. Tạo môi trường ảo
py -3.10 -m venv .venv        # Windows
python3 -m venv .venv         # Linux / macOS

# 2. Cài đặt các thư viện cần thiết cho Web
.venv\Scripts\python -m pip install -r Web/requirements.txt   # Windows
.venv/bin/python -m pip install -r Web/requirements.txt      # Linux / macOS

# 3. Khởi chạy ứng dụng Web
.venv\Scripts\python Web/run.py                              # Windows
.venv/bin/python Web/run.py                                 # Linux / macOS
```

Mở trình duyệt truy cập: **http://127.0.0.1:8000**

---

## 3. Cấu Trúc Repository
```text
HanViet-Alignment/
├── plan.md                               # Kế hoạch & đặc tả triển khai
├── README.md                             # Tài liệu tổng quan & hướng dẫn khởi chạy
├── .gitignore                            # Loại trừ database, secrets, dữ liệu nguồn
├── docs/
│   ├── architecture.md                   # Kiến trúc hệ thống & mô hình dữ liệu
│   ├── user-guide.md                     # Hướng dẫn sử dụng cho 4 sinh viên
│   ├── colab-guide.md                    # Hướng dẫn chạy OCR & AI trên Colab GPU
│   ├── model-benchmark.md                # Báo cáo đánh giá mô hình và tài nguyên
│   ├── acceptance-report.md              # Báo cáo nghiệm thu các Gate G01 - G15
│   └── contracts.md                      # Đặc tả định dạng dữ liệu TSV, XLSX, JSON
├── OCR/                                  # Module 1: Nhận dạng ký tự quang học
│   ├── notebooks/
│   │   ├── 01_OCR_Han.ipynb              # OCR Chữ Hán (PaddleOCR / CPU Fallback)
│   │   └── 02_OCR_Viet.ipynb             # OCR Tiếng Việt có dấu
│   └── utils/                            # Render PDF, pipeline, checkpoints, sorting
├── Crawl/                                # Module 2: Thu thập tư liệu
│   ├── notebooks/01_Crawl_Text.ipynb     # Notebook cào HTML & trích xuất PDF Text
│   └── extractors/                       # html_extractor, pdf_text_extractor
├── Web/                                  # Module 3: Ứng dụng dóng hàng cục bộ
│   ├── run.py / run.bat / run.sh         # Khởi chạy server 127.0.0.1:8000
│   ├── app/                              # FastAPI, SQLAlchemy, routers, services, UI
│   ├── notebooks/
│   │   └── 01_Semantic_Alignment.ipynb   # Gợi ý dóng hàng bằng AI Semantic (Qwen3/LaBSE)
│   └── ai/                               # Thuật toán Dynamic Programming & Scoring
├── tests/                                # Bộ kiểm thử tự động toàn diện
│   ├── fixtures/                         # han.txt, viet.txt, HTML, PDF Text, Scan PNG
│   ├── test_alignment_types.py           # Kiểm chứng 4 kiểu dóng hàng T01 - T16
│   ├── test_segmentation.py              # Kiểm thử phân tách câu Hán - Việt
│   ├── test_web_api.py                   # Kiểm thử trọn vẹn API Web
│   ├── test_export_parity.py             # So sánh từng ô giữa file TSV và XLSX
│   ├── test_qa.py                        # Kiểm thử phát hiện lỗi tự động
│   ├── test_backup_restore.py            # Kiểm thử SQLite Backup/Restore an toàn
│   ├── test_crawl.py                     # Kiểm thử cào HTML và trích xuất PDF
│   ├── test_ocr_contract.py              # Kiểm thử OCR pipeline và checkpoint
│   ├── test_ai_contract.py               # Kiểm thử AI suggestion contract
│   ├── test_notebooks.py                 # Kiểm thử thực thi cả 4 notebook Jupyter
│   └── e2e/test_browser.py               # Kiểm thử giao diện thật bằng Playwright
└── scripts/
    ├── verify_all.py                     # Script kiểm chứng toàn bộ Gate G01 - G15
    ├── make_demo_data.py                 # Tạo 2.000 cặp và 8.000 cặp nhóm giả lập
    ├── benchmark_models.py               # Đo lường hiệu năng và độ chính xác mô hình
    └── consolidate_team.py               # Tổng hợp kết quả 4 sinh viên thành file chung
```

---

## 4. Chạy Kiểm Thử Toàn Diện & Nghiệm Thu
Để tự động chạy tất cả unit test, integration test, Playwright browser test trên trình duyệt thật và xác minh 15 tiêu chí nghiệm thu (Gate G01 - G15):

```bash
# Windows
.venv\Scripts\python scripts/verify_all.py

# Linux / macOS
.venv/bin/python scripts/verify_all.py
```
Toàn bộ bằng chứng thực nghiệm, thời gian chạy và bảng đánh giá G01–G15 sẽ được ghi nhận chi tiết tại `docs/acceptance-report.md`.
