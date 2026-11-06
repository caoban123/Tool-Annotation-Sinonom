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

## Tùy chọn Qwen3-VL-8B-Instruct

Trong cell 1 của `01_OCR_Han.ipynb`, thay dòng `MODEL_ID` bằng:

```python
MODEL_ID = "Qwen/Qwen3-VL-8B-Instruct"
QWEN_LOAD_IN_4BIT = True
USE_GPU = True
```

Sau đó Run all. Nếu đã chạy notebook rồi, sửa cell 1 và chạy cell đó, sau đó
chạy lại từ cell 4 (cài/preflight) đến cuối. Chỉ có một dòng MODEL_ID cần hiệu lực;
notebook nhận diện Qwen từ tên model, hoặc `model_type` trong config của thư mục local.
Để trở về model cũ, đặt `MODEL_ID="PaddlePaddle/PaddleOCR-VL-1.6"`.

Qwen dùng prompt chép nguyên văn, giữ phồn thể/chữ hiếm, đọc cột dọc phải sang trái;
không yêu cầu dịch hoặc thêm dấu câu. Đây là chỉ dẫn, không bảo đảm model không sai.
Vẫn dùng cùng cơ chế chia vùng, giới hạn token/thời gian, ảnh vùng lỗi và xuất partial.
Cache tách theo model và chế độ 4-bit; đổi model không xóa checkpoint cũ.
Hãy tải/lưu ZIP trước khi đổi model vì các file kết quả trong cùng output được thay bởi lượt mới.

Qwen 8B nặng hơn PaddleOCR-VL 0.9B. Mặc định tùy chọn Qwen dùng NF4 4-bit với
bitsandbytes 0.48.2 để giảm VRAM; cell 4 kiểm tra kernel 4-bit trước khi tải weights.
Chỉ cài gói này khi chọn Qwen 4-bit, giữ nguyên PyTorch/CUDA của nền tảng.
Chế độ 4-bit có thể ảnh hưởng chất lượng; cần đối chiếu vài trang trước khi chạy cả sách.
`QWEN_LOAD_IN_4BIT=False` dùng FP16/BF16 trên GPU: riêng weights 8B đã khoảng
16 GB, chưa tính ảnh và KV cache. CPU dùng FP32 rất nặng và phải tắt 4-bit.
Thiếu VRAM: giảm `MAX_PIXELS`, chia ảnh hai mặt bằng `SPLIT_SPREAD=True` nếu phù hợp.
Nếu model chạy chậm, thử tăng `REGION_TIMEOUT`/`PAGE_TIMEOUT` trên vài trang trước.

Chưa kiểm chứng Qwen 8B đầy đủ hoặc NF4 trên GPU Colab/Kaggle trong phiên phát triển.
Các kiểm tra native dùng model Qwen cấu hình nhỏ với weights ngẫu nhiên để kiểm tra
vision/attention/KV cache, không phải bằng chứng chất lượng OCR.
Đã đối chiếu processor Qwen3-VL chính thức: ảnh đi qua chat template với đúng
`pixel_values`, `image_grid_thw` và giới hạn pixel. Kiểm thử bao gồm chọn model,
FP16/BF16, cấu hình NF4, không cast model sau lượng tử hóa, prompt đọc cột, chặn
text bị cắt, cache riêng và chạy hết notebook ở smoke mode cho cả hai lựa chọn.
Nguồn: [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct),
[bitsandbytes](https://huggingface.co/docs/bitsandbytes/installation).

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
- Chia ảnh theo đường kẻ/khoảng trắng; dừng sinh lặp hoặc quá thời gian, chia vùng nhỏ hơn.
  Không tăng toàn trang lên 16K token để thử lại liên tục.
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
ZIP cũng chứa `region_cache/`. Để tiếp tục các vùng trong trang còn lỗi sau khi hết
phiên, khôi phục thư mục này vào `<output_dir>/region_cache/` của phiên mới.

## Khi cell 6 báo lỗi

### Bảng tiến độ trực quan

Khi chạy cell 6, bảng **Tiến độ OCR Hán** xuất hiện ngay dưới cell, phía trên log.
Không cần chạy thêm cell hay cài ipywidgets. Bảng dùng display của IPython có sẵn
trong Colab/Jupyter, cập nhật tại chỗ thay vì tạo thêm bảng sau mỗi dòng log.

- Phần trăm và số trang đã xử lý/tổng trang trong khoảng START_PAGE–END_PAGE.
- Số trang lấy từ cache, trang/vùng đang OCR và thời gian đã chạy.
- Trạng thái nạp model, chia vùng, đóng gói và số trang/vùng cần kiểm tra.
- Đồng hồ tiếp tục cập nhật khi worker chưa sinh log mới.
- Khi có lỗi hoặc hủy cell, bảng giữ tiến độ đã đạt và báo đã dừng; không tự nhảy 100%.
- Xử lý hết lượt nhưng còn vùng lỗi: bảng màu vàng, không báo OCR đầy đủ.

Phần trăm đo tiến độ xử lý, không phải độ chính xác hay tỷ lệ trang nhận dạng thành công.
Terminal không có IPython tiếp tục dùng log như cũ. Có thể tắt bảng bằng
`show_progress=False` khi gọi `run_logged_process`.

### Log lỗi gốc

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

Bản tăng 4096 → 8192 → 16384 đã không giải quyết được trang này: log mới ghi nhận
15 phút 20 giây rồi vẫn thiếu EOS. Đã tìm được PDF local có đúng SHA-256 trong log
`15e0c07f0af59a6e9c4989936a498648e3b752e462967ae9d323f53fd81231da` và xem trang 27:
hai mặt sách, nhiều cột Hán dọc, đường kẻ và phần lề nhiễu.

Bản hiện tại chuyển sang xử lý vùng ảnh theo bố cục:

- Chia tại đường kẻ dài hoặc khoảng trắng, giữ tọa độ và thứ tự đọc.
- Phát hiện chu kỳ token lặp và giới hạn mềm 90 giây mỗi generate; không coi dừng
  vì guard là EOS thành công. Thời gian được kiểm tra ở bước sinh token kế tiếp.
- Vùng thiếu EOS/sinh lặp/hết thời gian/OOM được chia nhỏ tiếp, tối đa ba tầng.
- Mỗi phần ảnh có tối đa 40 lần thử, ngân sách mềm cả trang 300 giây; phần hai mặt
  sách dùng chung ngân sách thời gian trang. Cột/lề nhiễu không được phép chặn cả sách.
- `CONTINUE_ON_ERROR=True`: lưu ảnh và lỗi tại `needs_review/`, tiếp tục trang khác.
  Có thể đặt False để dừng ngay khi cần chẩn đoán.
- Chỉ ghi checkpoint hoàn tất khi vùng/trang đầy đủ. Các vùng thành công trong
  trang còn lỗi được checkpoint riêng để dùng lại khi chạy tiếp.
- Có đủ mọi trang mới xuất `han.txt`. Còn vùng lỗi thì chỉ xuất `han.partial.txt`,
  `han_metadata.json` với `complete=false`, `error_report.json` và ảnh lỗi trong ZIP.
  Không dùng file partial làm bản nộp hoàn chỉnh. Mã thoát 0 khi xử lý hết lượt
  không có nghĩa mọi trang đã OCR thành công; xem trường `complete` và cảnh báo cell 7.

Đây là heuristic chia vùng, không phải detector từng chữ; vẫn cần soát lỗi chữ,
thứ tự và mép cột. Không xóa hoặc tự sửa chữ lặp trong văn bản để giả làm kết quả đúng.

Giữ `MAX_NEW_TOKENS`, `MAX_PIXELS`, `SPLIT_SPREAD` và các cấu hình cũ để dùng lại
cache trang 1–26; đặt `FORCE_REPROCESS=False`. Khóa cache hoàn tất cũ được giữ để
tiếp tục trang 27. Không cần xóa cache, tải lại weights hoặc restart runtime chỉ
để áp dụng bản sửa này. Muốn kiểm tra lại chất lượng các trang cũ thì chủ động OCR lại.

## Kiểm chứng và giới hạn

Môi trường kiểm thử: Windows, Python 3.10.5; môi trường CPU bổ sung có
PyTorch `2.13.0+cpu`, Transformers `5.1.0`. Không có CUDA trong phiên làm việc này.

- Kiểm thử hồi quy local: PDF/ảnh, API Web, split/merge, QA, xuất file, checkpoint.
- Bản chia vùng: **24 passed** với `test_resilient_ocr.py`, `test_han_portable.py`
  và `test_notebook_process.py` trong môi trường có torch/Transformers. Bao gồm
  sinh lặp, timeout, chia vùng, tiếp tục trang sau, cache/resume và chặn xuất đầy đủ khi còn lỗi.
- Đã render và kiểm tra vùng trên PDF khớp hash, trang 1/26/27/28/83: lần lượt
  1/4/12/9/6 vùng; tổng diện tích vùng phủ đủ ảnh, không bỏ dải pixel giữa các vùng.
  Kiểm tra này không chứng minh các ký tự nhận dạng đúng hoặc mọi mép cột đều tối ưu.
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
python -m pytest tests/test_resilient_ocr.py tests/test_han_portable.py tests/test_notebook_process.py -q
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
