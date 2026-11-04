# Notebook OCR Hán trên Kaggle và Colab

Bản sửa ngày 04/11/2026. File dùng để upload là
`OCR/notebooks/01_OCR_Han.ipynb`. Notebook tự mang các module OCR và ảnh minh họa;
không phụ thuộc nhánh GitHub đã được push, không clone/reset repo, không tải cả bộ sách mặc định.

## Chạy với tài liệu của bạn

1. Upload notebook lên Colab hoặc Kaggle trong một session GPU sạch.
2. Colab: bật GPU trong Runtime. Kaggle: bật GPU và Internet trong Settings.
3. Đưa PDF/ảnh vào phiên làm việc, điền đường dẫn `INPUT_PATH` ở cell đầu.
4. Chọn `START_PAGE`, `END_PAGE` rồi Run all. `END_PAGE=None` xử lý tới cuối.
5. Tải `han_ocr.zip` ở cell cuối hoặc bảng Output của Kaggle.

Ví dụ đường dẫn:

```python
INPUT_PATH = "/kaggle/input/ten-dataset/sach.pdf"
# Colab: INPUT_PATH = "/content/sach.pdf"
START_PAGE = 21
END_PAGE = 30
```

Không điền đường dẫn: tự chọn khi chỉ có một tài liệu; nhiều tài liệu thì liệt kê và
yêu cầu chọn rõ. Không có tài liệu thì chạy ảnh minh họa kèm thông báo.
Đặt `USE_DEMO_IF_NO_INPUT=False` nếu không muốn chạy mẫu.
Đường dẫn đã điền nhưng sai luôn báo lỗi, không chuyển sang ảnh mẫu.

Colab lưu tại `/content/han_ocr/output`, Kaggle tại `/kaggle/working/han_ocr/output`.
`han.txt` là UTF-8; `han_metadata.json` lưu kết quả từng trang, thời gian, model và cấu hình.
ZIP có thêm checkpoint để tiếp tục sau khi gián đoạn.

## Thay đổi kỹ thuật

- Transformers native `AutoModelForImageTextToText` và `AutoProcessor`, pin `5.1.0`.
  Không chạy remote code của model, không monkey patch attention, RoPE hay cache position.
- Cài vào venv có kế thừa PyTorch/CUDA của nền tảng; inference chạy ở process mới,
  tránh kernel giữ phiên bản Transformers cũ sau khi pip cài đặt.
  Không thay torch/torchvision trên session GPU chuẩn.
- T4/P100 dùng FP16; BF16 chỉ được chọn khi GPU có compute capability >= 8 và hỗ trợ BF16.
  Ép cùng dtype cho toàn bộ model để tránh vision/projector khác dtype. CPU dùng FP32.
- Prompt có ảnh thật; processor thiếu `pixel_values` sẽ báo lỗi. Không suy luận text-only
  và không thay bằng kết quả mock khi model lỗi.
- Render từng trang, đóng PDFium bitmap/page/document sau khi sao chép ảnh.
- Checkpoint phân biệt theo SHA-256 tài liệu và cấu hình model/render/token/reading order.
  Ghi checkpoint bằng file tạm rồi atomic replace; không đánh dấu trang inference lỗi là hoàn tất.
- Chặn kết quả chạm giới hạn token trước EOS, yêu cầu tăng giới hạn hoặc chia nhỏ ảnh.
- Bỏ tọa độ dòng suy diễn và confidence cố định `0.99`. Đầu ra VLM là văn bản theo vùng/trang,
  không phải kết quả detector từng chữ. Không có đánh giá độ chính xác tự động từ độ dài text.
- `SPLIT_SPREAD=True` chia ảnh hai mặt sách dọc, nhận dạng nửa phải trước nửa trái.
- Builder chung gọi `scripts/build_han_notebook.py`, tránh sinh lại notebook lỗi cũ.

## Tiếp tục sau khi hết phiên

Lưu ZIP ra máy hoặc Drive. Giải nén thư mục `checkpoints/` vào một vị trí writable
ở phiên mới, đặt `CHECKPOINT_DIR` trỏ tới thư mục đó và chọn lại đúng tài liệu/cấu hình.
Checkpoint trong `/content` hoặc `/kaggle/working` tự mất nếu nền tảng xóa session;
notebook không tự mount Drive. Có thể trỏ `CHECKPOINT_DIR` tới Drive đã được mount.
Không trỏ checkpoint vào `/kaggle/input` vì đây là vùng chỉ đọc.

## Khi cell 6 báo lỗi

`CalledProcessError: ... exit status 1` chỉ cho biết worker đã dừng; riêng thông báo
này không xác định được nguyên nhân model, GPU, tài liệu hay mạng.

Bản cập nhật cell 6 chuyển stdout/stderr của worker vào output notebook bằng pipe,
hiển thị log ngay khi có dữ liệu và lưu toàn bộ tại `WORK_DIR/ocr_run.log`
(Colab: `/content/han_ocr/ocr_run.log`). Khi thất bại, cell hiển thị phần cuối log
gồm traceback gốc thay vì chỉ báo lỗi subprocess. Hủy cell cũng dừng worker.

Nếu đang mở bản notebook cũ, có thể lấy lỗi gốc bằng cell chẩn đoán sau, sau khi
đã chạy các cell cấu hình/cài đặt trước đó. Lệnh này có thể chạy lại inference
trang chưa có checkpoint; không dùng kết quả mock hoặc bỏ qua lỗi.

```python
r = subprocess.run(
    [str(PYTHON), '-u', '-m', 'OCR.han_runner', '--config', str(config_file)],
    cwd=str(SOURCE_DIR), env=environment,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding='utf-8', errors='replace'
)
print(r.stdout)
print('Exit code:', r.returncode)
```

Giữ lại traceback gốc để xác định cách sửa. Không đổi phiên bản thư viện, tắt
kiểm tra kết quả hoặc chuyển sang CPU chỉ dựa trên mã thoát 1.

### Trang 27 dừng do giới hạn token

Log Colab đã xác nhận 26 trang đầu được nạp từ cache; trang 27 thất bại vì
`max_new_tokens` được dùng hết trước EOS. Model đã nạp thành công; cảnh báo
HF token, fast processor và RoPE trong log đó không phải lỗi khiến tiến trình dừng.

Bản sửa giữ ngân sách ban đầu 4096 và tự thử lại **chỉ vùng ảnh chưa hoàn tất** với
8192 rồi tối đa `MAX_RETRY_TOKENS=16384`. Nếu vẫn thiếu EOS thì dừng, không cache
hay xuất văn bản bị cắt cụt. Kiểm tra ảnh/chữ lặp và chia vùng theo cột khi cần;
không đảm bảo tăng token sẽ khắc phục mọi trang khó.

Giữ `MAX_NEW_TOKENS`, `MAX_PIXELS`, `SPLIT_SPREAD` và các cấu hình cũ để dùng lại
cache trang 1–26; đặt `FORCE_REPROCESS=False`. Trần retry mới không làm thay đổi
khóa cache của các trang đã kết thúc đầy đủ. Không cần xóa cache, tải lại weights
hoặc restart runtime chỉ để áp dụng bản sửa này. Tăng trần có thể làm trang khó
chạy lâu hơn và dùng thêm bộ nhớ GPU.

## Kiểm chứng và giới hạn

Môi trường kiểm thử: Windows, Python 3.10.5; môi trường CPU bổ sung có
PyTorch `2.13.0+cpu`, Transformers `5.1.0`. Không có CUDA trong phiên làm việc này.

- Kiểm thử hồi quy local: PDF/ảnh, API Web, split/merge, QA, xuất file, checkpoint.
- Kết quả: **55 passed, 7 skipped** trong venv (các bài thiếu torch/CUDA được ghi skip);
  **11 passed** cho `test_han_portable.py` trong môi trường có PyTorch/Transformers.
  Hai bài nbformat/smoke của notebook Hán đều pass.
- Notebook Hán chạy hết cell bằng nbclient ở **smoke mode**: kiểm tra bundle/cấu hình,
  không cài model và không xuất kết quả OCR giả.
- Kiểm thử native bổ sung chạy attention/cache thật với **model nhỏ có weights ngẫu nhiên**,
  cùng các kiểm tra dtype T4/P100/BF16, ảnh bắt buộc, decode và token truncation.
  Đây là kiểm chứng API/tensor, không phải bằng chứng chất lượng nhận dạng.
- Đã tải processor/config công khai của PaddleOCR-VL-1.6 và khởi tạo bằng API native.
- Inference với weights đầy đủ và chạy trực tiếp trên GPU Kaggle/Colab **chưa được xác nhận**.
  Việc tải weights trong phiên local gặp gián đoạn mạng. Không suy ra GPU/model chính xác
  chỉ từ các bài test contract hay smoke.

Lệnh chạy kiểm thử:

```powershell
.venv\Scripts\python -m pytest tests --ignore=tests/test_notebooks.py --ignore=tests/e2e -q
.venv\Scripts\python -m pytest tests/test_notebooks.py -k OCR_Han -q
# Môi trường có torch và Transformers 5.1.0:
python -m pytest tests/test_han_portable.py -q
```

Kiểm thử GPU thật:

```powershell
python -m pytest tests/test_ocr_engine.py tests/test_ocr_contract.py -m requires_gpu -q
```

Chạy Run all trên runtime GPU với tài liệu đã chọn và đối chiếu `han.txt` với scan
là bước kiểm chứng triển khai còn lại. Với sách Hán cổ, vẫn cần soát chữ hiếm, cột và trang.
API Transformers nhận dạng phần tử không thay thế pipeline phân tích bố cục đầy đủ.

Nguồn chính thức đã đối chiếu:

- [PaddleOCR-VL-1.6 — API Transformers và giới hạn nhận dạng phần tử](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6#paddleocr-vl-16-09b-usage-with-transformers)
- [Native implementation trong Transformers](https://github.com/huggingface/transformers/tree/v5.1.0/src/transformers/models/paddleocr_vl)
