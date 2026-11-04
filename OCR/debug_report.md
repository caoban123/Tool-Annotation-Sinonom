# BÁO CÁO AUDIT & ĐIỀU TRA NGUYÊN NHÂN GỐC (ROOT CAUSE REPORT)
**Dự án:** HanViet-Alignment / OCR Pipeline  
**Module:** `PaddleOCR-VL-1.6` cho nhận dạng chữ Hán cổ từ PDF Scan  
**Thời gian:** 2026-11-04  
**Tác giả:** Senior OCR Infrastructure & ML Engineer  

---

## 1. Tóm Tắt Hiện Trạng & Vấn Đề Nghiêm Trọng

Hệ thống OCR chữ Hán trong `OCR/notebooks/01_OCR_Han.ipynb` và `OCR/utils/ocr_pipeline.py` đang gặp sự cố nghiêm trọng về **tính toàn vẹn dữ liệu (Data Integrity)**:
1. Mô hình Vision-Language `PaddlePaddle/PaddleOCR-VL-1.6` không thể khởi tạo trên môi trường Google Colab.
2. Khi gặp lỗi import hoặc lỗi runtime, pipeline tự động chuyển sang chế độ `cpu_test_adapter` (mock adapter).
3. Mock adapter trả về chuỗi văn bản giả cố định `"古南交，周號越裳。"` với confidence giả lập `0.98`.
4. Cơ chế checkpoint (`OCRCheckpointManager`) lưu chuỗi giả lập này vào thư mục `data/ocr_checkpoints/*.json`.
5. Trong các lần chạy tiếp theo, checkpoint manager đọc lại kết quả giả từ ổ đĩa và coi đó là kết quả OCR hợp lệ.
6. Kết quả xuất ra `han.txt` cho 83 trang PDF chỉ là 83 dòng `"古南交，周號越裳。"`, gây nguy cơ ô nhiễm toàn bộ dữ liệu song ngữ Hán - Việt của đồ án.

---

## 2. Phân Tích Nguyên Nhân Gốc (Root Cause Analysis)

### 2.1. Lỗi Import: `No module named 'transformers.modeling_layers'`
- **Nguyên nhân trực tiếp:** 
  File remote code `modeling_paddleocr_vl.py` của mô hình `PaddlePaddle/PaddleOCR-VL-1.6` trên Hugging Face Hub (dòng 35) thực hiện import:
  ```python
  from transformers.modeling_layers import GradientCheckpointingLayer
  ```
  Module `transformers.modeling_layers` là cấu trúc mới chỉ xuất hiện trong `transformers >= 4.49.0` (và `transformers >= 5.0.0`).
- **Nguyên nhân phát sinh:**
  Khi cấu hình `requirements.txt` hoặc notebook ghim `transformers>=4.40.0,<4.49.0` (ví dụ 4.48.x), module này hoàn toàn không tồn tại trong thư viện, dẫn tới ngoại lệ `ModuleNotFoundError`.

### 2.2. Lỗi Import: `cannot import name 'create_causal_mask' from 'transformers.modeling_attn_mask_utils'`
- **Nguyên nhân:**
  Trong các bản `transformers` trước đó hoặc các nhánh remote code, `create_causal_mask` được chuyển từ `modeling_attn_mask_utils` sang `transformers.masking_utils`. Khi gọi import từ `modeling_attn_mask_utils`, Python báo lỗi `ImportError`.

### 2.3. Lỗi Inference: `create_causal_mask() got an unexpected keyword argument 'cache_position'`
- **Nguyên nhân:**
  Trong `modeling_paddleocr_vl.py` (dòng 606–613), hàm `forward` gọi:
  ```python
  causal_mask = create_causal_mask(
      config=self.config,
      inputs_embeds=inputs_embeds,
      attention_mask=attention_mask,
      past_key_values=past_key_values,
      position_ids=position_ids,
      cache_position=cache_position,
  )
  ```
  Trong phiên bản Transformers mới, hàm `create_causal_mask` trong `transformers.masking_utils` đã loại bỏ tham số `cache_position` (và đổi `inputs_embeds` thành `input_embeds` ở một số bản). Khi gọi với tham số này, Python ném ngoại lệ `TypeError`.

### 2.4. Sai Lầm Về Precision Trên GPU: `torch.bfloat16` trên Tesla T4
- Code cũ đặt mặc định:
  ```python
  dtype = torch.bfloat16 if device == "cuda" else torch.float32
  ```
- Trên Google Colab miễn phí, GPU mặc định là **NVIDIA Tesla T4 (Turing, Compute Capability 7.5)**. Phần cứng T4 **không hỗ trợ bfloat16 nguyên bản** (`torch.cuda.is_bf16_supported() == False`).
- Việc ép buộc `bfloat16` trên T4 gây suy giảm hiệu năng nghiêm trọng (emulation) hoặc lỗi kernel CUDA.

### 2.5. Lỗ Hổng Checkpoint: Đọc & Lưu Dữ Liệu Mock
- Trong `ocr_pipeline.py`, khi model không nạp được, cờ `self.is_mock = True` được bật nhưng `process_images` vẫn gọi `self.checkpoints.save_cached_result(page_key, page_data)`.
- `OCRCheckpointManager.get_cached_result` không kiểm tra tính hợp lệ của cache, chấp nhận trả về bất kỳ file JSON nào có sẵn, khiến các lần chạy sau đọc phải dữ liệu giả.

### 2.6. Lỗ Hổng Mất Số Trang Gốc (Page Number Drift)
- Trong `process_images`:
  ```python
  for idx, img in enumerate(images):
      page_num = idx + 1
  ```
  Nếu người dùng render từ trang 21 đến 30 (10 ảnh), `idx` chạy từ 0 đến 9, biến số trang bị ghi sai thành 1 đến 10.

---

## 3. Môi Trường Thực Tế

### 3.1. Môi trường phát triển cục bộ (Local Development)
- **Hệ điều hành:** Windows 10/11 (AMD64)
- **Python:** 3.10.5
- **PyTorch:** 2.13.0+cpu (Không có GPU CUDA cục bộ)
- **Transformers:** 5.1.0
- **PaddlePaddle / PaddleOCR:** Chưa cài đặt cục bộ (Cần chạy unit test với contract tách biệt, mock kiểm thử có kiểm soát)

### 3.2. Môi trường đích triển khai (Target Production Environment)
- **Nền tảng:** Google Colab
- **GPU:** NVIDIA Tesla T4 16GB (hoặc L4 / A100)
- **CUDA:** 12.x
- **Framework ưu tiên:** 
  - Cách 1: Native `paddleocr[doc-parser]>=3.6.0` và `paddlepaddle-gpu==3.2.1`
  - Cách 2: Hugging Face `transformers>=5.0.0`, `torch`, `accelerate`

---

## 4. Kế Hoạch Sửa Đổi Toàn Diện (Action Plan)

1. **Loại bỏ hoàn toàn mock fallback trong runtime production**:
   - Nếu nạp model thất bại, lập tức `raise RuntimeError("Không thể khởi tạo mô hình PaddleOCR-VL thật: ...")`.
   - Xóa bỏ mọi chuỗi `"古南交，周號越裳。"` trong pipeline thực thi.
2. **Khắc phục triệt để tương thích Transformers cho PaddleOCR-VL**:
   - Yêu cầu `transformers>=5.0.0` (hỗ trợ `transformers.modeling_layers` nguyên bản).
   - Thiết lập wrapper an toàn cho `create_causal_mask` loại bỏ `cache_position` và map `inputs_embeds` / `input_embeds`.
   - Cross-export `create_causal_mask` sang `transformers.modeling_attn_mask_utils`.
3. **Quản lý Precision chuẩn xác theo GPU**:
   - Tự động kiểm tra `torch.cuda.is_bf16_supported()`. Nếu là T4 (không hỗ trợ BF16), tự động dùng `torch.float16`.
4. **Cách ly và thanh trừng Checkpoint rác**:
   - Cập nhật `OCRCheckpointManager` từ chối nạp/lưu mọi kết quả có `is_mock=True` hoặc text giả.
   - Thêm hàm `purge_invalid_checkpoints()` dọn sạch toàn bộ 33 file checkpoint giả hiện tại.
5. **Bảo toàn số trang gốc**:
   - Bổ sung `start_page` vào `process_images` và `render_pdf_to_images`.
6. **Xác thực đầu ra OCR (Output Validation)**:
   - Thêm module `validate_ocr_output()` kiểm tra tính chân thực của văn bản trước khi cho phép xuất `han.txt`.
7. **Refactor Notebook `01_OCR_Han.ipynb`**:
   - Thiết kế 12 cell tuần tự chuẩn, chẩn đoán phần cứng, cài đặt chính xác, OCR từng trang có đối chiếu trực quan rồi mới chạy đa trang.
