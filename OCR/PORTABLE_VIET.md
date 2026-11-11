# OCR tiếng Việt trên Colab / Kaggle

## Một luồng cho PDF text, scan và PDF trộn

Giữ `INPUT_MODE="auto"` (mặc định): hệ thống kiểm tra **từng trang**, lấy text trực
tiếp nếu lớp text dùng được; trang scan, chỉ có số trang/URL, ký tự lỗi hoặc thiếu
mapping được chuyển OCR. Ghép kết quả theo số trang gốc vào cùng `viet.txt`.
Ảnh PNG/JPG/TIFF luôn đi qua OCR. Không phải tách tài liệu hoặc chạy hai notebook.

Có thể dùng [notebook Crawl PDF](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/Crawl/notebooks/01_Crawl_Text.ipynb)
hoặc notebook Việt bên dưới: cả hai dùng chung mã xử lý và định dạng đầu ra.
Cell 3 chỉ cài thư viện PDF trước, đếm trang cần OCR, rồi mới cài Paddle khi cần.
PDF text thuần không tải model và không kiểm tra GPU. Vẫn cần Internet lần đầu để
cài Python/thư viện. Không tự sửa chính tả hay xóa dòng lặp của lớp text.

- `INPUT_MODE="ocr"`: nhận dạng lại mọi trang đã chọn.
- `INPUT_MODE="text"`: chỉ lấy lớp text; trang không có text báo lỗi và xuất partial.
- `FORCE_OCR_PAGES=[3, 7]`: ép OCR các trang gốc 3, 7; các trang khác vẫn tự chọn.

Kiểm tra dựa trên Unicode, ký tự bất thường, lặp glyph và ảnh lớn với ít text.
Không thể chứng minh nội dung đúng nghĩa hoặc phát hiện hết lỗi dấu. Trang có ảnh
scan lớn và lớp text được gắn cảnh báo `image_backed_text_layer` để đối chiếu lớp OCR
cũ; không mặc định xóa lớp text này. Nếu đọc thử thấy sai, dùng tùy chọn ép OCR.
Trang bìa ngắn có chữ hợp lệ và không có ảnh lớn vẫn được trích xuất trực tiếp.
PDF nhiều cột/bảng vẫn cần kiểm tra thứ tự đọc.

[Mở notebook trên Colab](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/OCR/notebooks/02_OCR_Viet.ipynb).
Kaggle: upload `OCR/notebooks/02_OCR_Viet.ipynb`, bật Internet và GPU.

1. Upload PDF/PNG/JPG/TIFF, điền đường dẫn thật vào `INPUT_PATH` ở cell 1.
2. Chọn `DEVICE="gpu:0"` hoặc `"cpu"`, `START_PAGE`, `END_PAGE` rồi Run all.
3. Cell 5 hiển thị tiến độ, số trang cache, trang cần kiểm tra và log trực tiếp.
4. Cell 6 tải `viet_ocr.zip`; Kaggle có thể lấy ZIP trong thư mục Output.

### OCR từ trang cao xuống thấp

Trong cell cấu hình của cả notebook Hán, Việt và Crawl, đặt:

```python
START_PAGE = 1
END_PAGE = 100  # None = trang cuối tài liệu
REVERSE_PAGES = True
```

Khoảng trang vẫn khai báo số nhỏ trước, số lớn sau. Ví dụ trên xử lý và ghép TXT
theo thứ tự 100, 99, …, 1; `False` giữ thứ tự 1, 2, …, 100. Không đảo chữ/cột trong
mỗi trang. Metadata giữ số trang PDF gốc, có `reverse_pages` để web nhập đúng nguồn.
Cache từng trang vẫn dùng lại khi đổi chiều; không cần bật `FORCE_REPROCESS`.
Notebook cũ đã mở trên Colab/Kaggle cần thay bằng bản mới vì mã runner được đóng gói
bên trong notebook; chỉ thêm biến vào notebook cũ sẽ chưa có tác dụng.

Notebook đóng gói mã nguồn, dùng Python 3.11 riêng qua uv, PaddleOCR 3.7.0,
PaddleX 3.7.2 và PaddlePaddle 3.2.2. Không cần clone repo hoặc restart kernel.
Internet cần cho lần đầu cài thư viện/Python và tải model. Không tải bộ sách tự động,
không thay đường dẫn thiếu bằng ảnh mẫu. `OCR_NOTEBOOK_SMOKE=1` chỉ kiểm tra các cell;
không tạo kết quả OCR và không kiểm chứng độ chính xác.

Nếu kho Paddle báo `No matching distribution found` / 502 / timeout, bước cài đặt
thử lại hữu hạn rồi dùng wheel 3.2.2 cùng CPU/CUDA từ máy chủ tệp chính thức
`paddle-whl.bj.bcebos.com` (Linux x86_64 / Python 3.11). Dependencies lấy từ PyPI.
Không tự đổi sang CPU, CUDA khác hoặc nâng phiên bản Paddle. Wheel cu126 khoảng
1,9 GB; cần đủ dung lượng và Internet. Xem `WORK_DIR/paddle_install.log` và
`paddle_install.index.log`, `paddle_install.official-wheel.log` để lấy lỗi pip gốc.
Đây là đường tải dự phòng, không khắc phục được trường hợp cả máy chủ wheel và
PyPI cùng không truy cập được. GPU vẫn được kiểm tra bằng phép toán sau khi cài.

## Paddle tìm dòng + VietOCR đọc chữ (mặc định mới)

Trong cell 1, giữ `OCR_BACKEND="paddle_vietocr"`. Paddle dùng detector
`PP-OCRv5_mobile_det`, cắt và chỉnh phối cảnh từng dòng, VietOCR `vgg_transformer`
đọc tiếng Việt; kết quả ghép theo hàng từ trên xuống, trái sang phải. Dòng lặp
được giữ. Đây là thứ tự dòng cơ bản, cần soát lại sách nhiều cột/bảng.

VietOCR chạy trong môi trường Torch riêng, không cài chung với Paddle. Notebook
tự tạo và cài hai môi trường khi có trang cần OCR; PDF text thuần vẫn bỏ qua cả hai.
Weights VietOCR tải lần đầu khoảng 152 MB và được giữ ở `WORK_DIR/vietocr_weights`.
Metadata ghi tên model, checksum weights, phiên bản và điểm từng dòng.

Để thử mới trên tài liệu đã chạy, đặt `INPUT_MODE="ocr"`, chọn 5–10 trang và Run all.
Nếu giữ `auto`, trang có lớp text hợp lệ vẫn được lấy trực tiếp, không qua VietOCR.
Cache của VietOCR tách khỏi Paddle; không cần xóa kết quả cũ để đổi chế độ.
Giữ `USE_TEXTLINE_ORIENTATION=False` và xoay trang/dòng về đúng chiều trước.
VietOCR có thể chậm hơn trên CPU; ngân sách notebook mới là `PAGE_TIMEOUT=300`.
Quá thời gian hoặc dòng không kết thúc trong 512 token sẽ báo lỗi, không cache trang thiếu.

Muốn đối chiếu luồng cũ, đặt `OCR_BACKEND="paddle"`; lúc đó `RECOGNIZER` chọn
PP-OCRv6 Small/Medium và tùy chọn hướng dòng mới có hiệu lực. Chất lượng cần đo
trên trang thật; không coi việc thay model là bảo đảm chính xác hơn.

Nguồn: [VietOCR chính thức](https://github.com/pbcquoc/vietocr),
[cặp phiên bản Torch/torchvision](https://pytorch.org/get-started/previous-versions/).

## Kiểm chứng luồng Paddle + VietOCR

- Kiểm thử CPU Windows/Python 3.10 với Paddle 3.2.2, PaddleOCR 3.7.0,
  VietOCR 0.3.13, Torch 2.6.0 và torchvision 0.21.0 trong hai môi trường riêng.
- Đã chạy weights thật trên ảnh mẫu, ảnh có dấu tiếng Việt và trang 5 của
  `Đại Việt Địa Dư Toàn Biên.pdf` (30 dòng), xuất ZIP/text/metadata và chạy lại từ cache.
- Ảnh chữ rõ đọc được dấu ở “Lịch triều hiến chương loại chí”, “Nguyễn, Trường, Đặng”,
  nhưng mất dấu chấm cuối dòng. Trang sách còn lỗi chữ và phần cuối dòng;
  confidence cao vẫn cần soát. Chưa có nhãn chuẩn để kết luận hơn PP-OCRv6.
- 49 bài kiểm tra (bật `VIETOCR_TEST_PYTHON` và `VIETOCR_TEST_WEIGHTS` cho bài weights thật): cache riêng, tọa độ/crop, Unicode qua tiến trình, timeout và dừng
  tiến trình con, lỗi render, PDF text bỏ qua OCR, bundle và notebook smoke.
- Chưa chạy inference GPU hoặc cài mới trên Colab/Kaggle. Notebook dùng Python 3.11;
  smoke chỉ kiểm tra thực thi cell, không xác nhận chất lượng model.

Log Kaggle từng dừng ở `ModuleNotFoundError: No module named 'pkg_resources'`:
`Predictor` của VietOCR kéo theo downloader `gdown` cũ dù weights đã được quản lý
riêng. Bản sửa dùng trực tiếp `build_model`, nạp state dict đã kiểm tra SHA256
với `weights_only=True`; không cần import downloader hay cài thêm `pkg_resources`.
Kiểm thử weights thật chặn cả `gdown`, `pkg_resources`, `Predictor` và utils cũ
vẫn khởi tạo và nhận dạng thành công. Cell 3 cũng kiểm tra module inference thật.

## Cấu hình Paddle ưu tiên tốc độ

- Phát hiện: `PP-OCRv5_mobile_det`; nhận dạng: `PP-OCRv6_small_rec` hỗ trợ tiếng Việt.
- Batch 16 dòng, giới hạn cạnh ảnh phát hiện 1280, render 144 DPI.
- Tắt phân loại hướng tài liệu, sửa cong và hướng dòng khi không cần.
- Dòng điểm thấp vẫn được giữ nguyên cùng dấu, số và dòng lặp; không tự sửa từ.

Có thể đổi `RECOGNIZER="PP-OCRv6_medium_rec"` để đối chiếu chất lượng. Small được
chọn vì ưu tiên tốc độ; không xem model lớn hơn là bảo đảm đúng dấu trên mọi sách.

Chữ nhỏ: thử `DET_LIMIT_SIDE_LEN=1920` và `RENDER_SCALE=3.0` trên vài trang trước.
Thiếu VRAM ở chế độ Paddle: giảm `REC_BATCH_SIZE` xuống 8 hoặc 4. Dòng quay 180°: bật
`USE_TEXTLINE_ORIENTATION`. Trang quay 90°/270° cần xoay về đúng hướng trước.
`GPU_WHEEL="cu126"` dùng CUDA 12.6; chọn `cu118` cho driver cũ/GPU P100.
Notebook kiểm tra tensor trên thiết bị đã chọn, không âm thầm chuyển GPU sang CPU.
Nếu báo không tìm thấy `nvidia-smi`, kiểm tra phiên đã bật GPU chưa. Bật GPU trong
cài đặt runtime Colab hoặc Accelerator của Kaggle rồi chạy lại notebook. Nếu chỉ
có CPU, đổi `DEVICE="cpu"` ở cell 1 rồi Run all; nhiều trang scan sẽ chạy chậm.
Model và thư viện nằm trong môi trường riêng, tránh đè lên PyTorch của notebook Hán.

## Đầu ra và chạy tiếp

ZIP chứa:

- `viet.txt`: văn bản UTF-8 khi xử lý đủ các trang đã chọn.
- `viet.partial.txt`: thay cho `viet.txt` khi có trang lỗi; không dùng như bản đầy đủ.
- `viet_metadata.json`: SHA256 tài liệu, cấu hình, thiết bị/model, số trang gốc,
  `method`, `routing_reason`, `text_quality`, nội dung và polygon/bbox/điểm từng dòng
  OCR, cờ kiểm tra và thời gian. Trang text trực tiếp không tạo tọa độ/điểm OCR giả.
  `method_counts` tổng hợp số trang theo cách xử lý, gồm cả trang lỗi của cách đó.
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

Model được giữ trong worker qua nhiều trang. Quá `PAGE_TIMEOUT` (notebook mới: 300 giây
nhận dạng, không tính tải model/render) thì dừng worker, ghi lỗi và tiếp tục trang sau.
Lỗi cài đặt/nạp model dừng ngay để sửa môi trường. Mỗi trang được render riêng để
không giữ toàn bộ sách trong RAM. Trước khi thay một bản OCR đang dùng, đối chiếu
10–20 trang thật về dấu, mất dòng, thứ tự đọc và tốc độ.

Cache phân biệt chế độ tự chọn/ép text/ép OCR và phiên bản phân loại trang.
Ép OCR riêng một trang không làm mất cache các trang khác.

Nguồn API: [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR),
[PP-OCRv6](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html),
[cài Paddle 3.2](https://github.com/PaddlePaddle/docs/blob/release/3.2/docs/install/pip/linux-pip_en.md).

Tạo lại notebook sau khi sửa mã: `python scripts/build_viet_notebook.py`.

## Kiểm chứng cục bộ ngày 05/11/2026 — luồng OCR ban đầu

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

## Kiểm chứng sau khi ghép PDF text và scan

- 63 bài qua, 8 bài Torch được bỏ qua và 2 bài Semantic ngoài phạm vi không chạy.
  Bao gồm PDF trộn, giữ thứ tự/số trang gốc, Unicode tiếng Việt và ngoài BMP,
  trang scan có header, cảnh báo lớp OCR cũ, lỗi scan không chặn trang text sau,
  chỉ ép OCR trang được chọn, cache và smoke của cả hai notebook.
- Đã chạy model CPU thật trên PDF thử nghiệm ba trang text → scan → text:
  chỉ trang giữa nạp OCR, xuất chung ZIP; chạy lại lấy đủ 3/3 trang từ cache.
- Đã kiểm tra các PDF Việt trong tư liệu: scan không có text và scan chỉ có URL
  được chuyển OCR; lớp OCR cũ đủ chữ được lấy trực tiếp kèm cảnh báo để đối chiếu.
  Bộ kiểm tra tự động không xác nhận nội dung đúng nghĩa hay hết lỗi dấu.
