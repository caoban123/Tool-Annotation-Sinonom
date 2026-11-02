# Module Web — HanViet Alignment Studio

Module Web cung cấp giao diện cục bộ (Local Web App) độc lập cho từng thành viên trong nhóm dóng hàng Hán - Việt.

## Công nghệ sử dụng
- **Backend**: FastAPI, SQLAlchemy, SQLite (WAL mode + Foreign Keys enabled), openpyxl.
- **Frontend**: Jinja2 Templates, HTML5/CSS3 (Tailwind CSS), Vanilla JavaScript.
- **Bảo mật**: Chạy trên `127.0.0.1:8000`, không mở public ra LAN.

## Hướng dẫn cài đặt & Khởi chạy

### Cách 1: Sử dụng môi trường ảo venv (Khuyến nghị)
```bash
# Windows
py -3.10 -m venv .venv
.venv\Scripts\python -m pip install -r Web/requirements.txt
.venv\Scripts\python Web/run.py

# Linux / macOS
python3 -m venv .venv
.venv/bin/python -m pip install -r Web/requirements.txt
.venv/bin/python Web/run.py
```

### Cách 2: Sử dụng file script chạy nhanh
- Trên Windows: Nhấp đúp vào `Web/run.bat`
- Trên Linux/macOS: Chạy `bash Web/run.sh`

Mở trình duyệt tại: **http://127.0.0.1:8000**
