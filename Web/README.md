# Module Web — HanViet Alignment Studio

Module Web cung cấp giao diện cục bộ (Local Web App) độc lập cho từng thành viên trong nhóm dóng hàng Hán - Việt.

## Công nghệ sử dụng
- **Backend**: FastAPI, SQLAlchemy, SQLite (WAL mode + Foreign Keys enabled), openpyxl.
- **Frontend**: Jinja2 Templates, HTML5/CSS3 (Tailwind CSS), Vanilla JavaScript.
- **Bảo mật**: Chạy trên `127.0.0.1:8000`, không mở public ra LAN.

## Hướng dẫn cài đặt & Khởi chạy

### Cách 1: Sử dụng môi trường ảo venv (Khuyến nghị)
```bash
# Windows
py -3.10 -m venv .venv
.venv\Scripts\python -m pip install -r Web/requirements.txt
.venv\Scripts\python Web/run.py

# Linux / macOS
python3 -m venv .venv
.venv/bin/python -m pip install -r Web/requirements.txt
.venv/bin/python Web/run.py
```

### Cách 2: Sử dụng file script chạy nhanh
- Trên Windows: Nhấp đúp vào `Web/run.bat`
- Trên Linux/macOS: Chạy `bash Web/run.sh`

Mở trình duyệt tại: **http://127.0.0.1:8000**

## Quy trình mới

- **Xóa dự án**: nút Xóa trên mỗi thẻ mở hộp xác nhận theo tên dự án. Xác nhận sẽ
  xóa văn bản đã nhập (cả phiên bản cũ), nhiệm vụ, cặp dóng hàng, QA và lịch sử
  trong dự án. Xuất/lưu kết quả trước nếu cần giữ. Nếu dự án vừa thay đổi, tải lại
  danh sách trước khi xác nhận. Thao tác Hủy hoặc Esc không xóa dữ liệu.
- **Nguồn & nhiệm vụ**: kiểm kê nguồn Hán/Việt, tải tệp gốc, gắn metadata OCR khớp
  TXT trước biên tập, thêm người/phạm vi và mục tiêu cặp. Chọn nhiệm vụ khi dóng hàng.
- **QA & Lỗi**: quét cảnh báo tự động; duyệt/từ chối cặp chờ; kiểm tra mẫu đúng/sai
  và loại lỗi. Đánh giá thủ công không bị quét xóa; sửa nội dung làm mẫu cũ cần kiểm tra lại.
- **Thô & Sạch**: bản thô lấy từ snapshot gốc, không dựng từ phân đoạn đã sửa.
- **Xuất & Sao lưu**: checklist thể hiện phần còn thiếu. ZIP thông thường vẫn xuất
  bản đang làm; liên kết xuất có điều kiện yêu cầu checklist đạt. Cả hai có báo cáo.
- **Workspace**: chế độ gọn/cỡ chữ lưu theo trình duyệt, QA nhảy đúng câu/cặp,
  Enter/Space chọn thẻ, modal hỗ trợ Tab/Shift+Tab/Esc và trả focus khi đóng.
  Nhấp đúp ô Hán/Việt hoặc focus ô rồi nhấn F2 để mở chỉnh sửa; bấm Lưu Thay Đổi
  để lưu, Hủy/Esc để đóng. Nhấp đúp giữ lựa chọn dóng hàng trước đó.
  Mỗi cột hiển thị tối đa 100 ô để làm việc với sách lớn: dùng Trước/Sau hoặc nhập
  số ô `#` và bấm Đến. Lựa chọn được giữ giữa các trang; tìm kiếm vẫn xét toàn bộ
  tài liệu. Tới ô chưa gán và liên kết từ QA tự mở đúng trang chứa ô đó.
  Xác nhận/hoàn tác cập nhật phần vừa thay đổi sau khi server lưu thành công.
  Bấm Tải lại dữ liệu để lấy thay đổi từ tab khác. Xem [đo hiệu năng](PERFORMANCE.md).

### Dịch tham khảo từng ô Hán bằng Azure Translator

1. Sao chép `Web/.env.example` thành `Web/.env` (không ghi đè nếu đã có).
2. Điền KEY 1 của tài nguyên Translator vào `AZURE_TRANSLATOR_KEY`. Với tài nguyên
   East Asia, giữ `AZURE_TRANSLATOR_REGION=eastasia`; Global có thể để trống region.
   Endpoint dùng **Text Translation**: `https://api.cognitive.microsofttranslator.com`.
3. Cài/cập nhật `Web/requirements.txt`, khởi động lại `Web/run.py` hoặc `Web/run.bat`,
   rồi Ctrl+F5 trên trình duyệt. Web tự đọc `Web/.env`; biến môi trường đã đặt có ưu tiên.
4. Bấm **Dịch tham khảo** trên ô Hán. Bản dịch nằm dưới nguyên văn, có thể ẩn/hiện.
   Không thay nội dung Hán/Việt, không tạo cặp hay thay trạng thái QA.

Chỉ gửi nội dung `clean_text` của ô vừa bấm tới Azure, ngôn ngữ nguồn Hán văn cổ
`lzh`, đích `vi`; không gửi toàn sách hay các ô Việt. Khóa chỉ dùng ở backend, không
trả cho trình duyệt. `Web/.env` được Git bỏ qua; không đưa khóa lên GitHub/chat.
Nếu chưa cấu hình, UI báo hướng dẫn; lỗi quyền/quota/kết nối có thông báo và nút thử lại.

Mỗi ô tối đa 5.000 ký tự, chờ kết nối tối đa 10 giây và timeout đọc 30 giây.
Không tự retry để tránh gọi tính phí lặp. Cache nằm trong SQLite, theo ID ô và
nội dung: mở lại trang rồi bấm dịch sẽ dùng bản lưu; sửa nội dung sẽ dịch lại.
Request dùng revision để từ chối dữ liệu cũ; nếu ô thay đổi trong lúc dịch, kết quả
không được lưu vào ô mới (lượt gọi Azure đã gửi vẫn có thể tính vào quota).
Chặn gọi lặp cùng ô trong tiến trình web cục bộ; chạy nhiều worker có thể phát sinh
lượt Azure trùng khi cache chưa có. Xóa dự án sẽ xóa cache tương ứng; backup SQLite
bao gồm cache, ZIP xuất văn bản/cặp hiện không kèm bản dịch tham khảo.

Đây là bản dịch máy hỗ trợ đọc và tìm đoạn Việt tương ứng. Cần kiểm tra tên riêng,
chức quan, niên hiệu và thuật ngữ; chưa có đánh giá chất lượng trên sách thực tế.
Tham khảo [API Translate](https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/v3/translate)
và [xác thực theo Region](https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/authentication).

### Database và migration

Khi khởi động, ứng dụng tự thêm cột/bảng mới và tạo bản sao SQLite có đuôi
`.before-web-v2.bak` trước khi nâng cấp DB cũ. Không xóa dự án/phân đoạn.
Snapshot nhập mới và nguồn upload nằm trong DB, đi cùng backup. Với tài liệu cũ,
chỉ đọc lại snapshot trên đĩa khi còn tệp và khớp hash; nếu thiếu sẽ báo rõ.
QA cũ được giữ ở nguồn `legacy`, không suy diễn ghi chú CHECKED thành đánh giá mới.
`DATABASE_URL` có thể trỏ tới DB riêng để kiểm thử; không dùng DB đang làm việc cho tests.

### Offline và xây dựng CSS

CSS đã biên dịch và font đi kèm trong `app/static`; chạy Web không cần Node hoặc
Internet sau khi cài dependencies Python. Inter/Noto Serif TC được phân phối theo
OFL; giấy phép nằm tại `app/static/fonts/*-OFL.txt`. Font dự phòng dùng font hệ thống.
Chỉ nhà phát triển cần Node khi thay class Tailwind:

```bash
cd Web
npm ci --ignore-scripts
npm run build:css
```

Hướng dẫn người dùng: [docs/user-guide.md](../docs/user-guide.md).
Kết quả triển khai: [docs/web-plan-validation.md](../docs/web-plan-validation.md).
