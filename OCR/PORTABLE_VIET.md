# OCR tiếng Việt trên Colab / Kaggle

[Mở notebook trên Colab](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/OCR/notebooks/02_OCR_Viet.ipynb).
Kaggle: upload `OCR/notebooks/02_OCR_Viet.ipynb`, bật Internet và GPU.

1. Upload PDF/PNG/JPG/TIFF, điền đường dẫn thật vào `INPUT_PATH` ở cell 1.
2. Chọn `DEVICE="gpu:0"` hoặc `"cpu"`, `START_PAGE`, `END_PAGE` rồi Run all.
3. Cell 5 hiển thị tiến độ, số trang cache, trang cần kiểm tra và log trực tiếp.
4. Cell 6 tải `viet_ocr.zip`; Kaggle có thể lấy ZIP trong thư mục Output.

Notebook đóng gói mã nguồn, dùng Python 3.11 riêng qua uv, PaddleOCR 3.7.0,
PaddleX 3.7.2 và PaddlePaddle 3.2.2. Không cần clone repo hoặc restart kernel.
Internet cần cho lần đầu cài thư viện/Python và tải model. Không tải bộ sách tự động,
không thay đường dẫn thiếu bằng ảnh mẫu. `OCR_NOTEBOOK_SMOKE=1` chỉ kiểm tra các cell;
không tạo kết quả OCR và không kiểm chứng độ chính xác.

## Cấu hình ưu tiên tốc độ

- Phát hiện: `PP-OCRv5_mobile_det`; nhận dạng: `PP-OCRv6_small_rec` hỗ trợ tiếng Việt.
- Batch 16 dòng, giới hạn cạnh ảnh phát hiện 1280, render 144 DPI.
- Tắt phân loại hướng tài liệu, sửa cong và hướng dòng khi không cần.
- Dòng điểm thấp vẫn được giữ nguyên cùng dấu, số và dòng lặp; không tự sửa từ.

Có thể đổi `RECOGNIZER="PP-OCRv6_medium_rec"` để đối chiếu chất lượng. Small được
chọn vì ưu tiên tốc độ; không xem model lớn hơn là bảo đảm đúng dấu trên mọi sách.

Chữ nhỏ: thử `DET_LIMIT_SIDE_LEN=1920` và `RENDER_SCALE=3.0` trên vài trang trước.
Thiếu VRAM: giảm `REC_BATCH_SIZE` xuống 8 hoặc 4. Dòng quay 180°: bật
`USE_TEXTLINE_ORIENTATION`. Trang quay 90°/270° cần xoay về đúng hướng trước.
`GPU_WHEEL="cu126"` dùng CUDA 12.6; chọn `cu118` cho driver cũ/GPU P100.
Notebook kiểm tra tensor trên thiết bị đã chọn, không âm thầm chuyển GPU sang CPU.
Model và thư viện nằm trong môi trường riêng, tránh đè lên PyTorch của notebook Hán.

## Đầu ra và chạy tiếp

ZIP chứa:

- `viet.txt`: văn bản UTF-8 khi xử lý đủ các trang đã chọn.
- `viet.partial.txt`: thay cho `viet.txt` khi có trang lỗi; không dùng như bản đầy đủ.
- `viet_metadata.json`: SHA256 tài liệu, cấu hình, thiết bị/model, số trang gốc,
  nội dung và polygon/bbox/điểm từng dòng, cờ kiểm tra và thời gian.
- `error_report.json`: trang lỗi, lý do, danh sách trang cần kiểm tra.
- `progress.json` và `checkpoints/`: tiến độ và cache trang thành công.

Log chi tiết: `WORK_DIR/ocr_run.log` (ngoài ZIP).
`complete=true` nghĩa là không có trang gặp lỗi xử lý; không bảo đảm đúng mọi chữ.
Trang trắng và dòng có confidence dưới `REVIEW_SCORE` được gắn `needs_review`.
Confidence là điểm model, không phải tỉ lệ chính xác đã đo. Bố cục nhiều cột/bảng
vẫn cần đối chiếu thứ tự đọc; luồng này không phải bộ phân tích bố cục đầy đủ.

Chạy lại cell 5 để tiếp tục. Cache dựa trên SHA256 tài liệu, trang, phiên bản pipeline,
model và cấu hình nhận dạng/render; không lẫn hai sách cùng tên. Trang lỗi không cache.
Đặt `CHECKPOINT_DIR` vào Drive đã mount để giữ cache sau khi hết phiên.
Đổi ngưỡng kiểm tra không phải nhận dạng lại; đổi model/cấu hình ảnh sẽ tạo cache khác.
Đặt `FORCE_REPROCESS=True` nếu chủ động muốn chạy lại tất cả trang đã chọn.

Model được giữ trong worker qua nhiều trang. Quá `PAGE_TIMEOUT` (mặc định 120 giây
nhận dạng, không tính tải model/render) thì dừng worker, ghi lỗi và tiếp tục trang sau.
Lỗi cài đặt/nạp model dừng ngay để sửa môi trường. Mỗi trang được render riêng để
không giữ toàn bộ sách trong RAM. Trước khi thay một bản OCR đang dùng, đối chiếu
10–20 trang thật về dấu, mất dòng, thứ tự đọc và tốc độ.

Nguồn API: [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR),
[PP-OCRv6](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html),
[cài Paddle 3.2](https://github.com/PaddlePaddle/docs/blob/release/3.2/docs/install/pip/linux-pip_en.md).

Tạo lại notebook sau khi sửa mã: `python scripts/build_viet_notebook.py`.

## Kiểm chứng cục bộ ngày 05/11/2026

- 33 bài kiểm tra qua: API/thiết bị/BGR, giữ dấu và dòng lặp, số trang gốc,
  đổi tài liệu/cấu hình, cache hỏng, partial/ZIP, timeout tiến trình thật,
  notebook smoke và bảng tiến độ qua kernel thật. 8 bài Torch của Hán được bỏ qua
  vì môi trường kiểm tra không có Torch; smoke không xác nhận inference.
- Đã cài Paddle thật vào môi trường kiểm tra riêng trên Windows CPU Python 3.10,
  chạy ảnh mẫu và trang PDF 5–6 của `Đại Việt Địa Dư Toàn Biên.pdf`.
  Cấu hình cuối dùng detector v5 mobile + recognizer v6 small, PaddleOCR 3.7.0,
  PaddleX 3.7.2, Paddle 3.2.2. Chạy lại nạp 2/2 trang từ cache mà không nạp model.
- Khi thử riêng trang 5, Small mất khoảng 11 giây nhận dạng CPU, chưa tính tải/nạp
  model. Đây là một lần thử, không phải benchmark tốc độ GPU hay số liệu trung bình.
  Bài thử Medium vượt ngân sách 120 giây đã xuất partial và báo lỗi đúng cách.
- Đối chiếu ảnh gốc thấy vẫn có sai/mất ký tự có dấu, kể cả dòng có confidence cao.
  Chưa có bộ nhãn chuẩn để công bố CER/WER. Chưa chạy inference GPU trên Colab/Kaggle
  và chưa kiểm chứng cài mới Python 3.11 trên hai nền tảng đó.
