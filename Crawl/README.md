# Module Crawl — Trích Xuất Dữ Liệu Web & PDF Text

Module này chịu trách nhiệm thu thập văn bản từ các trang web lưu trữ tư liệu hoặc trích xuất trực tiếp văn bản từ file PDF số hóa (PDF Text), phục vụ làm sạch và dóng hàng song ngữ.

## Cấu trúc thư mục
- `extractors/html_extractor.py`: Trích xuất bài viết từ HTML (URL hoặc file local), loại bỏ menu, header, footer, quảng cáo.
- `extractors/pdf_text_extractor.py`: Trích xuất văn bản số hóa từ PDF, tự động cảnh báo nếu phát hiện tài liệu là PDF Scan (ảnh chụp).
- `notebooks/01_Crawl_Text.ipynb`: Jupyter notebook trực quan để cấu hình nguồn, chạy trích xuất và xuất `han.txt` hoặc `viet.txt`.

## Cài đặt
```bash
pip install -r Crawl/requirements.txt
```

## Cách sử dụng
1. Mở notebook `Crawl/notebooks/01_Crawl_Text.ipynb`.
2. Đặt `SOURCE_TYPE = "html"` hoặc `"pdf_text"`.
3. Chỉ định `URL_OR_PATH` và ngôn ngữ (`LANGUAGE = "han"` hoặc `"viet"`).
4. Chạy toàn bộ notebook để nhận file text sạch và metadata sidecar JSON.
