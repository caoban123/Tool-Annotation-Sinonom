# Module Crawl — PDF text, PDF scan và HTML

Notebook PDF nhận tài liệu tiếng Việt có lớp text, scan hoặc trộn cả hai.
Hệ thống quyết định theo từng trang: lấy text trực tiếp khi dùng được, gọi OCR Việt
khi cần, rồi ghép đúng thứ tự vào một file. Không phải tách PDF hay chạy hai notebook.

[Mở notebook PDF trên Colab](https://colab.research.google.com/github/caoban123/Tool-Annotation-Sinonom/blob/main/Crawl/notebooks/01_Crawl_Text.ipynb).

## Cấu trúc thư mục
- `extractors/html_extractor.py`: Trích xuất bài viết từ HTML (URL hoặc file local), loại bỏ menu, header, footer, quảng cáo.
- `extractors/pdf_text_extractor.py`: Trích xuất văn bản số hóa từ PDF, tự động cảnh báo nếu phát hiện tài liệu là PDF Scan (ảnh chụp).
- `extractors/pdf_pages.py`: Kiểm tra lớp text và quyết định cách xử lý từng trang.
- `notebooks/01_Crawl_Text.ipynb`: Luồng PDF Việt chung, dùng `OCR/viet_runner.py`, có tiến độ, checkpoint và ZIP.

## Cài đặt
```bash
pip install -r Crawl/requirements.txt
```

## Cách sử dụng
1. Mở notebook `Crawl/notebooks/01_Crawl_Text.ipynb` trên Colab hoặc upload lên Kaggle.
2. Điền `INPUT_PATH` tới PDF, giữ `INPUT_MODE="auto"`, chọn khoảng trang rồi Run all.
3. Cell 3 báo số trang text/OCR. PDF text thuần không cần cài Paddle hay bật GPU.
   Nếu có trang cần OCR, bật GPU hoặc chọn `DEVICE="cpu"`.
4. Cell 5 hiển thị tiến độ; cell 6 tải ZIP chứa `viet.txt`, metadata và báo cáo lỗi.
   Có trang lỗi thì xuất `viet.partial.txt`, không coi là bản đầy đủ.

Metadata mỗi trang ghi `method=pdf_text` hoặc `ocr`, lý do chọn, số trang gốc và cờ
kiểm tra. Trang scan chỉ có header/URL chọn được sẽ được ưu tiên chuyển OCR.
Lớp OCR cũ trên ảnh scan vẫn có thể sai chữ dù Unicode hợp lệ; hệ thống gắn cảnh báo
`image_backed_text_layer`. Dùng `FORCE_OCR_PAGES=[3, 7]` hoặc `INPUT_MODE="ocr"`
để yêu cầu nhận dạng lại. Kiểm tra tự động không bảo đảm phát hiện mọi lỗi text.

Hai notebook Crawl PDF và OCR Việt dùng chung pipeline và định dạng đầu ra;
chỉ cần chọn một notebook để chạy. Không tự tải bộ sách hay thay file thiếu bằng mẫu.
Hướng dẫn cấu hình/khôi phục: [PORTABLE_VIET.md](../OCR/PORTABLE_VIET.md).
OCR Hán vẫn dùng notebook Hán riêng. HTML tiếp tục có API `extract_from_html`;
notebook PDF này không nhận URL HTML.
