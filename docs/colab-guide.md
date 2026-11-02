# Hướng Dẫn Chạy OCR & Semantic Alignment Trên Google Colab

Dành cho các thành viên cần xử lý file scan nặng hoặc muốn tận dụng GPU T4/V100 miễn phí trên Google Colab để chạy mô hình AI.

## 1. Hướng Dẫn Chạy OCR Chữ Hán / Việt Trên Colab
1. Mở [Google Colab](https://colab.research.google.com).
2. Chọn **Runtime** $\rightarrow$ **Change runtime type** $\rightarrow$ Chọn **T4 GPU**.
3. Upload thư mục `OCR/` và tải notebook `OCR/notebooks/01_OCR_Han.ipynb` (hoặc `02_OCR_Viet.ipynb`) lên Colab.
4. Cài đặt PaddleOCR GPU:
   ```bash
   !pip install paddlepaddle-gpu paddleocr pypdfium2 pillow
   ```
5. Đổi biến cấu hình:
   ```python
   USE_GPU = True
   MODEL_NAME = "PaddleOCR-VL-1.6"
   INPUT_IMAGE_OR_PDF = "/content/ten_sach_scan.pdf"
   ```
6. Chạy toàn bộ notebook: Kết quả `han.txt` (hoặc `viet.txt`) sẽ được lưu vào thư mục `data/ocr_output/` và tải về máy tính để import vào Web Studio.

## 2. Hướng Dẫn Chạy Gợi Ý Dóng Hàng Semantic Alignment Trên Colab
1. Trong Web Studio trên máy cá nhân, vào Workspace $\rightarrow$ bấm **"Gợi ý AI"** $\rightarrow$ nhấp vào link tải **`segments.jsonl`**.
2. Mở notebook `Web/notebooks/01_Semantic_Alignment.ipynb` trên Google Colab (chế độ T4 GPU).
3. Cài đặt dependencies:
   ```bash
   !pip install sentence-transformers torch
   ```
4. Đặt đường dẫn:
   ```python
   INPUT_SEGMENTS_PATH = "/content/segments_export.json"
   MODEL_CHOICE = "sentence-transformers/LaBSE" # Hoặc Qwen/Qwen3-Embedding-0.6B
   ```
5. Chạy notebook để sinh file `suggestions.json`.
6. Tải file `suggestions.json` về máy cá nhân $\rightarrow$ mở Web Studio $\rightarrow$ chọn **"Nhập Gợi Ý"**.
7. Các cặp gợi ý sẽ hiển thị trên giao diện với màu tím kèm điểm số tương đồng (score), người dùng xem xét và bấm **"Chấp nhận"** hoặc **"Từ chối"**.
