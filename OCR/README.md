# Module OCR — Nhận Dạng Văn Bản Hán & Việt Từ Ảnh / PDF Scan

Module OCR cung cấp quy trình nhận dạng ký tự quang học (OCR) cho tài liệu scan dạng ảnh hoặc PDF Scan.

## Tính năng chính
- **OCR Chữ Hán (`01_OCR_Han.ipynb`)**: Ưu tiên PaddleOCR-VL / PP-OCR, hỗ trợ cả bố cục chữ dọc truyền thống (RTL Vertical) và ngang (LTR Horizontal). Bảo vệ chữ Hán phồn thể/hiếm nguyên bản, tuyệt đối không giản thể hóa hay dịch nghĩa.
- **OCR Tiếng Việt (`02_OCR_Viet.ipynb`)**: Paddle tìm/cắt dòng + VietOCR `vgg_transformer` đọc chữ; có thể chọn lại PP-OCRv6 để đối chiếu. Có checkpoint, tiến độ, tọa độ/điểm từng dòng và báo cáo lỗi.
- **Cơ chế Checkpointing (`OCR/utils/checkpoints.py`)**: Lưu cache kết quả từng trang dựa trên hash. Nếu quá trình OCR bị gián đoạn, khi chạy lại sẽ tiếp tục từ trang kế tiếp mà không phải OCR lại từ đầu.
- **Tính năng độc lập**: Chạy tốt trên Google Colab GPU (T4/V100) và cung cấp bộ adapter kiểm thử CPU cục bộ.

## Cài đặt
```bash
pip install -r OCR/requirements.txt
```
*(Nếu sử dụng GPU trên Colab, cài thêm `paddlepaddle-gpu` và `paddleocr`)*.

## Notebook Hán trên Kaggle/Colab (bản sửa 04/11/2026)

Upload trực tiếp `notebooks/01_OCR_Han.ipynb`, bật GPU/Internet, điền `INPUT_PATH`
và Run all. Notebook tự mang mã nguồn, dùng Transformers native 5.1.0 trong venv riêng;
không cần PaddlePaddle và không cài lại torch/torchvision trên runtime GPU chuẩn.
Hướng dẫn chi tiết: [PORTABLE_HAN.md](PORTABLE_HAN.md).
Lệnh cài PaddlePaddle ở trên chỉ dành cho adapter OCR cổ điển, không dành cho notebook Hán mới.

## Notebook Việt trên Kaggle/Colab

Mở `notebooks/02_OCR_Viet.ipynb`, điền `INPUT_PATH` rồi Run all. Notebook tự tạo
Python 3.11, môi trường Paddle và Torch riêng; chọn GPU hoặc CPU ở cell 1. Không cần làm
bước cài đặt chung ở trên. Có tiến độ ở cell 5, ZIP ở cell 6 và chạy tiếp từ cache.
Xem cấu hình tốc độ/chất lượng và cách đọc kết quả thiếu trang tại [PORTABLE_VIET.md](PORTABLE_VIET.md).

Mặc định `INPUT_MODE="auto"`: PDF có lớp text dùng được sẽ lấy trực tiếp; chỉ OCR
trang scan/text lỗi và ghép theo thứ tự. Notebook Crawl PDF dùng cùng luồng này,
không cần chạy hai notebook cho cùng tài liệu. PDF text thuần không cần Paddle/GPU.
