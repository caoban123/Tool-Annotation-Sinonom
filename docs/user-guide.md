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
3. Bấm **"Tải Gói Giao Nộp (ZIP)"** để nhận file zip nén chuẩn đóng gói toàn bộ dữ liệu. Gửi file zip này cho trưởng nhóm để tổng hợp.
4. Nhấn **"Tạo Bản Sao Lưu Ngay"** bất kỳ lúc nào để lưu trữ trạng thái cơ sở dữ liệu SQLite an toàn.
