# Module OCR — Nhận Dạng Văn Bản Hán & Việt Từ Ảnh / PDF Scan

Module OCR cung cấp quy trình nhận dạng ký tự quang học (OCR) cho tài liệu scan dạng ảnh hoặc PDF Scan.

## Tính năng chính
- **OCR Chữ Hán (`01_OCR_Han.ipynb`)**: Ưu tiên PaddleOCR-VL / PP-OCR, hỗ trợ cả bố cục chữ dọc truyền thống (RTL Vertical) và ngang (LTR Horizontal). Bảo vệ chữ Hán phồn thể/hiếm nguyên bản, tuyệt đối không giản thể hóa hay dịch nghĩa.
- **OCR Tiếng Việt (`02_OCR_Viet.ipynb`)**: Nhận dạng tiếng Việt có dấu Unicode đầy đủ, nối dòng và khử nhiễu.
- **Cơ chế Checkpointing (`OCR/utils/checkpoints.py`)**: Lưu cache kết quả từng trang dựa trên hash. Nếu quá trình OCR bị gián đoạn, khi chạy lại sẽ tiếp tục từ trang kế tiếp mà không phải OCR lại từ đầu.
- **Tính năng độc lập**: Chạy tốt trên Google Colab GPU (T4/V100) và cung cấp bộ adapter kiểm thử CPU cục bộ.

## Cài đặt
```bash
pip install -r OCR/requirements.txt
```
*(Nếu sử dụng GPU trên Colab, cài thêm `paddlepaddle-gpu` và `paddleocr`)*.
