# Hướng Dẫn Chạy OCR & Semantic Alignment Trên Google Colab

Dành cho các thành viên cần xử lý file scan nặng hoặc muốn tận dụng GPU T4/V100 miễn phí trên Google Colab để chạy mô hình AI.

---

## 📌 Hướng Dẫn Mở Notebook Bằng Biểu Tượng "Open In Colab"

Ở đầu mỗi notebook (`01_Crawl_Text.ipynb`, `01_OCR_Han.ipynb`, `02_OCR_Viet.ipynb`, `01_Semantic_Alignment.ipynb`) đều có sẵn biểu tượng:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com)

### ⚠️ Lưu ý quan trọng khi bấm vào biểu tượng:
1. **Nếu Repository ở chế độ Public:**
   - Chỉ cần nhấp vào biểu tượng, notebook sẽ tự động mở ngay trên Google Colab.

2. **Nếu Repository ở chế độ Private (hoặc gặp thông báo lỗi 404 Not Found / Unable to open):**
   - Google Colab mặc định không thể đọc mã nguồn từ kho lưu trữ riêng tư nếu chưa được ủy quyền.
   - **Cách khắc phục 1 (Khuyến nghị)**: 
     1. Truy cập [Google Colab](https://colab.research.google.com).
     2. Chọn menu **File** $\rightarrow$ **Open notebook** (hoặc mở cửa sổ chọn file).
     3. Chọn thẻ **GitHub** $\rightarrow$ Tích chọn ô **"Include private repositories"** (Bao gồm kho lưu trữ riêng tư).
     4. Đăng nhập và ủy quyền tài khoản GitHub cho Google Colab.
     5. Nhập tên repo `caoban123/Tool-Annotation-Sinonom`, chọn nhánh `main` và mở notebook tương ứng.
   - **Cách khắc phục 2**: 
     - Vào GitHub $\rightarrow$ **Settings** của repository $\rightarrow$ Cuộn xuống mục **Danger Zone** $\rightarrow$ Chọn **Change repository visibility** sang **Public**.
   - **Cách khắc phục 3**: 
     - Tải trực tiếp file `.ipynb` từ máy tính lên tab **Upload** của Google Colab.

---

## 1. OCR chữ Hán trên Colab và Kaggle

Bản `OCR/notebooks/01_OCR_Han.ipynb` hiện tại tự mang mã nguồn OCR, không cần upload thư mục OCR hay clone GitHub.

1. Upload file `.ipynb` lên Colab hoặc Kaggle.
2. Colab: bật GPU trong Runtime. Kaggle: bật GPU và Internet trong Settings.
3. Upload PDF/ảnh (Colab: bảng Files; Kaggle: Add Input).
4. Điền `INPUT_PATH` ở cell đầu, ví dụ `/content/sach.pdf` hoặc `/kaggle/input/dataset/sach.pdf`.
5. Chọn `START_PAGE`, `END_PAGE` và Run all. Chưa có đầu vào thì chạy ảnh minh họa đi kèm,
   có thông báo rõ. Đặt `USE_DEMO_IF_NO_INPUT=False` để yêu cầu tài liệu của bạn.
6. Notebook tự cài Transformers 5.1.0 vào venv riêng, dùng PyTorch/CUDA có sẵn.
   Không chạy lệnh cài PaddlePaddle hoặc các bản vá attention từ notebook cũ.
7. Tải `han_ocr.zip`, gồm `han.txt`, metadata và checkpoint. Colab tự mở tải ZIP;
   Kaggle lấy từ `/kaggle/working/han_ocr/output/`.

Nếu ảnh là hai mặt sách Hán dọc, bật `SPLIT_SPREAD=True` để đọc nửa phải trước nửa trái.
Giới hạn token không được coi là trang hoàn tất: tăng `MAX_NEW_TOKENS` hoặc chia nhỏ ảnh khi có lỗi.
Xem [hướng dẫn và kết quả kiểm thử bản sửa](../OCR/PORTABLE_HAN.md).

## OCR tiếng Việt trên Colab và Kaggle

Mở `OCR/notebooks/02_OCR_Viet.ipynb`, upload tài liệu và điền `INPUT_PATH` ở cell 1.
Chọn `DEVICE="gpu:0"` (bật GPU) hoặc `"cpu"`, rồi Run all. Notebook tự cài Python 3.11
và PaddleOCR vào môi trường riêng. Cell 5 có bảng tiến độ; cell 6 tải `viet_ocr.zip`.
Lỗi trang được báo rõ và xuất `viet.partial.txt` thay cho bản đầy đủ. Chạy lại để
tiếp tục từ checkpoint; dùng thư mục Drive đã mount để giữ checkpoint qua các phiên.
Xem [hướng dẫn OCR Việt](../OCR/PORTABLE_VIET.md).

`Crawl/notebooks/01_Crawl_Text.ipynb` cũng dùng luồng PDF Việt này. Giữ
`INPUT_MODE="auto"` để tự chọn trích xuất text/OCR theo từng trang, không tách file.
Cell 3 đếm các loại trang và chỉ cài OCR khi cần; PDF text thuần không cần GPU.
Metadata ghi rõ phương pháp từng trang. `FORCE_OCR_PAGES` dùng khi lớp text cũ sai;
kiểm tra tự động không thay thế đối chiếu nội dung với scan.

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
