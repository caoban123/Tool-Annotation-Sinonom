# Nhiều PDF và phục hồi dòng VietOCR

Trong cell cấu hình của notebook Hán, Việt hoặc Crawl bản mới:

```python
BATCH_MODE = True
INPUT_PATHS = ["/content/quyen_1.pdf", "/content/quyen_2.pdf"]
START_PAGE = 1
END_PAGE = None
REVERSE_PAGES = False
```

`False` dùng `INPUT_PATH` như trước, bỏ qua list. `True` yêu cầu list đường dẫn
PDF tồn tại, không trùng. Một lần Run all xử lý **lần lượt**, tránh tranh VRAM.
Cài môi trường một lần; mỗi PDF chạy trong process riêng để giải phóng model.
Với notebook Việt, chỉ cài OCR nếu ít nhất một PDF cần OCR; PDF text thuần không
cần GPU. Khoảng trang áp dụng riêng từng file; `None` là cuối mỗi PDF. Chế độ
đảo trang chỉ đảo trang bên trong mỗi PDF, không đảo list.

## Đầu ra và chạy tiếp

- Notebook xuất `quyen_1.pdf` → `quyen_1.txt`, cả chế độ một file và batch.
  Nếu thiếu vùng/trang thì xuất `quyen_1.partial.txt`. Metadata ghi `text_file`.
- Batch lưu dưới `WORK_DIR/batch_output/<tên PDF>-<mã đường dẫn>/`. Hai PDF trùng
  tên ở hai thư mục không ghi đè. Mỗi thư mục có TXT, metadata, báo cáo lỗi, ZIP
  và checkpoint riêng. `batch_ocr.zip` chứa toàn bộ thư mục kết quả và báo cáo chung.
- `batch_report.json` ghi `complete`/`partial`/`failed` cho từng PDF; file hỏng hoặc
  khoảng trang sai không chặn các PDF tiếp theo. List rỗng, đường dẫn thiếu hoặc
  trùng được chặn trước khi chạy. Traceback gốc nằm trong `WORK_DIR/ocr_run.log`.
- Chạy lại cùng nguồn/cấu hình/đường dẫn dùng cache trang thành công. Nếu dùng
  Drive, `CHECKPOINT_DIR` có thư mục con riêng cho từng PDF. Cache chế độ một file
  cũ không tự chuyển sang thư mục batch. Ngắt cell dừng cả worker đang chạy.
- Runner CLI cũ không truyền `text_basename` vẫn xuất `han.txt`/`viet.txt`.

## VietOCR vượt 512 token

Giữ giới hạn 512 và yêu cầu EOS; không nhận văn bản bị cắt như kết quả đủ.
Chỉ dòng lỗi được tách gần giữa ảnh tại cột ít mực, đọc các phần trái sang phải.
Tối đa ba mức tách, có kích thước tối thiểu; không lặp vô hạn.

Dòng phục hồi được gắn `split_retry`, trang cần đối chiếu dù điểm cao. Nếu vẫn
còn phần lỗi, giữ các dòng/phần đọc được, đánh dấu trang `partial`, lưu ảnh dòng
trong `needs_review/` và vị trí phần lỗi trong `error_report.json`, kèm trong ZIP.
Trang partial không cache thành công; khi chạy lại chỉ trang chưa đủ được OCR lại.
Khóa cache các trang đã thành công được giữ nguyên nếu không đổi model/cấu hình.

Giới hạn thời gian trang vẫn có hiệu lực; lỗi native/timeout toàn worker vẫn có
thể làm trang không có text. Tách ảnh không bảo đảm chữ đúng; đối chiếu các vùng
được đánh dấu, nhất là detector gộp nhiều dòng hoặc ảnh bị cắt sai.
Kiểm thử logic dùng engine/protocol giả lập và PDF text thật không nạp OCR.
Reader CPU đã chạy với weights thật trên dòng mẫu; chưa kiểm chứng model GPU
trên hai trang lỗi thực tế của bạn.
