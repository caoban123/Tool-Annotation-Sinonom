# Hướng Dẫn Sử Dụng — Dành Cho Thành Viên Nhóm

Tài liệu này hướng dẫn từng sinh viên trong nhóm cài đặt, chạy ứng dụng trên máy cá nhân, thao tác dóng hàng và xuất file nộp bài cho trưởng nhóm.

## 1. Cài Đặt & Khởi Chạy Web Local
Yêu cầu: Máy tính đã cài đặt Python 3.10 trở lên.

### Khởi chạy nhanh bằng 1 lệnh:
- **Trên Windows**:
  Nhấp đúp chuột vào file `Web/run.bat` (hoặc mở terminal chạy `.venv\Scripts\python Web/run.py`).
- **Trên macOS / Linux**:
  Chạy lệnh: `bash Web/run.sh`.

Mở trình duyệt web truy cập vào: **http://127.0.0.1:8000**

## 2. Các Bước Thao Tác Nghiệp Vụ

### Bước 1: Tạo dự án mới & Nhập tài liệu
1. Tại Trang chủ, bấm nút **"Tạo Dự Án Mới"**.
2. Điền mã đề tài (ví dụ: `HVB_01`), mã tác phẩm (ví dụ: `NAM_QUOC_SON_HA`), tên tác phẩm và tên người làm.
3. Chọn file `han.txt` và `viet.txt` từ máy tính.
4. Bấm **"Khởi Tạo & Nhập Văn Bản"**. Hệ thống sẽ tự động phân tách câu theo dấu câu Hán và Việt, bảo tồn toàn bộ ký tự Unicode.

### Bước 2: Thao tác dóng hàng trong Workspace
- **Chọn câu**: Nhấp chuột vào một thẻ câu Hán ở cột trái và một thẻ câu Việt ở cột phải.
- **Dóng hàng 1–n / n–1 / n–m**:
  - Nhấp chọn 1 câu Hán, sau đó nhấp chọn 2 (hoặc nhiều) câu Việt liền kề $\rightarrow$ Hệ thống tự nhận diện kiểu **1–n**.
  - Nhấp chọn 2 câu Hán liền kề, chọn 1 câu Việt $\rightarrow$ Nhận diện kiểu **n–1**.
  - Nhấp chọn nhiều câu Hán liền kề và nhiều câu Việt liền kề $\rightarrow$ Nhận diện kiểu **n–m**.
- **Xác nhận**: Bấm nút **"Xác nhận"** hoặc nhấn tổ hợp phím **Ctrl + Enter**. Thẻ chuyển sang màu xanh lá (*Đã dóng*).
- **Hoàn tác**: Bấm nút **"Hoàn tác"** hoặc nhấn phím **Ctrl + Z** để hủy cặp vừa dóng.
- **Hủy chọn**: Bấm phím **Esc**.
- **Tìm kiếm**: Nhấn **Ctrl + K** để tìm nhanh nội dung hoặc mã ID câu.
- **Sửa / Tách / Gộp câu**: Nhấp vào nút "Sửa" hoặc "Tách" trực tiếp trên từng thẻ nếu câu bị tách nhầm trong quá trình OCR/Crawl.

### Bước 3: Kiểm định chất lượng (QA)
1. Bấm vào tab **"QA & Lỗi"** trên thanh menu.
2. Bấm nút **"Quét Lỗi Tự Động"** để rà soát:
   - Các câu chưa được gán đối ứng (`MISSING`).
   - Các câu chứa ký tự bắt đầu công thức Excel như `=`, `+`, `-`, `@` (`FORMAT`).
   - Các câu có thứ tự đảo lộn so với nguyên bản (`ORDER`).

### Bước 4: Xuất kết quả nghiệm thu & Sao lưu
1. Bấm vào tab **"Xuất & Sao lưu"**.
2. Có thể tải riêng file **TSV Song Ngữ** hoặc **Excel XLSX** để kiểm tra.
3. Xem checklist trước khi bấm **"Tải Gói Giao Nộp (ZIP)"**. ZIP thông thường là bản đang làm,
   có thể còn dữ liệu thiếu; báo cáo ghi rõ trạng thái. Liên kết xuất có điều kiện chỉ cho tải khi checklist đạt.
4. Nhấn **"Tạo Bản Sao Lưu Ngay"** bất kỳ lúc nào để lưu trữ trạng thái cơ sở dữ liệu SQLite an toàn.

## 3. Nguồn, số trang và nhiệm vụ

Vào **Nguồn & nhiệm vụ**, lưu thông tin riêng cho Hán/Việt: tên, URL/tệp, định dạng,
số trang, phạm vi và công cụ. Có thể upload tệp nguồn để đưa thật vào ZIP; nhập URL
chỉ lưu tham chiếu. Tệp nguồn/TXT và phiên bản của chúng được lưu cùng DB.

Nếu có `han_metadata.json` / `viet_metadata.json`, chọn ở form tương ứng ngay sau
import, trước sửa/tách/gộp. Metadata phải khớp TXT, có `full_text` và `pages` với
`page_number`, `text`. TXT không có metadata sẽ hiện **Chưa rõ trang**. Tách giữ
tham chiếu trang; gộp giữ mọi trang liên quan. **Mở nguồn** trên thẻ mở tệp/URL đã lưu.

Mục tiêu mặc định 2.000 cặp có thể đổi khi tạo dự án hoặc sửa nhiệm vụ. Thêm nhiệm vụ
cho từng người/phạm vi, chọn nhiệm vụ ở Workspace trước khi xác nhận cặp. Checklist
kiểm tra cả tổng và mục tiêu riêng, không coi đủ tổng là mọi thành viên đều đạt.

## 4. Kiểm tra mẫu và gợi ý AI

Trong QA, đánh giá từng cặp xác nhận **Đúng** hoặc **Có lỗi**, chọn `OMISSION`
(thiếu ý), `ADDITION` (thêm ý), `MISSING` (thiếu đối ứng), nhập ghi chú/người kiểm tra
và lưu. Cặp có nhiều loại lỗi chỉ đếm một lần. Sửa nội dung làm đánh giá cũ hết hiệu
lực; cần duyệt lại cặp và đánh giá lại. Quét tự động không xóa lỗi người dùng.
Chưa có mẫu sẽ hiện chưa đánh giá, không hiển thị tỷ lệ 0% giả.

Gợi ý AI cần xuất manifest mới từ Web, dùng notebook hiện có rồi nhập JSON về.
File sai schema/project/hash/revision sẽ bị từ chối. Gợi ý chỉ là gợi ý; phải duyệt
mới xuất. Nếu một phân đoạn đã được xác nhận ở cặp khác, hệ thống chặn duyệt trùng.
Danh sách **Cặp và gợi ý chờ duyệt** trong QA cho phép loại bỏ gợi ý trùng hoặc cặp
không còn hợp lệ sau thay nguồn. Liên kết QA nhảy đến đúng câu/cặp trong Workspace.

## 5. Đọc gói ZIP

- `01_nguon/inventory.json`: kiểm kê nguồn; tệp gốc đã upload nằm theo Hán/Việt.
- `02_ocr_tho`: byte TXT nhập gốc còn khớp hash; không dùng nội dung đã sửa thay thế.
- `03_text_sach`: text hiện tại sau biên tập.
- `04_dong_hang`: cặp confirmed có cấu trúc hợp lệ, TSV/XLSX được kiểm tra parity.
- `reports`: thống kê, QA (kèm nguồn vấn đề), đánh giá mẫu, checklist và provenance.
- `task_manifest.json`: danh sách tệp thực sự có trong ZIP, trạng thái và phần thiếu.

Nếu không còn snapshot gốc cũ, Web báo thiếu thay vì tự phục dựng. Những vấn đề QA
từ dữ liệu cũ có nhãn `legacy` cần đối chiếu thủ công. Checklist đạt không có nghĩa
mọi câu đúng ngữ nghĩa; tiếp tục sửa các lỗi đã biết và kiểm tra chất lượng thực tế.

Web chạy offline sau khi cài thư viện. Sau cập nhật mã, khởi động lại Web và refresh
trình duyệt để nhận CSS/JavaScript mới. Database cũ được backup tự động trước migration.
