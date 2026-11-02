# Kiến Trúc Hệ Thống — Han–Viet Alignment Studio

## 1. Tổng Quan Kiến Trúc
Hệ thống **Han–Viet Alignment Studio** được thiết kế theo mô hình **Local-First độc lập**, phục vụ nhóm 4 sinh viên thực hiện đồ án NLP song ngữ Hán - Việt.
- **Không phụ thuộc Cloud**: Mỗi sinh viên cài đặt và chạy ứng dụng Web độc lập trên máy tính cá nhân (`127.0.0.1:8000`), không cần kết nối Internet sau khi cài đặt.
- **Không dùng chung Backend / Database trung gian**: Tránh xung đột kết nối, mất dữ liệu hoặc phụ thuộc hạ tầng mạng.
- **Kiến trúc 3 Module rõ ràng**:
  1. `OCR/`: Nhận dạng chữ Hán/Việt từ ảnh chụp, PDF scan (chạy trên Google Colab GPU hoặc local).
  2. `Crawl/`: Cào dữ liệu từ website tư liệu hoặc trích xuất text trực tiếp từ PDF Text số hóa.
  3. `Web/`: Ứng dụng dóng hàng cục bộ FastAPI + Jinja2 + SQLite + openpyxl, đi kèm notebook `01_Semantic_Alignment.ipynb` hỗ trợ gợi ý AI.

```
                      +-----------------------------+
                      |   Tài liệu nguồn PDF / URL   |
                      +--------------+--------------+
                                     |
              +----------------------+----------------------+
              |                                             |
              v                                             v
     [ Module 1: OCR ]                             [ Module 2: Crawl ]
  (01_OCR_Han / 02_OCR_Viet)                      (01_Crawl_Text.ipynb)
              |                                             |
              +----------------------+----------------------+
                                     |
                         han.txt & viet.txt (UTF-8)
                                     |
                                     v
                       +----------------------------+
                       |     Module 3: Web App      |
                       |  (FastAPI + SQLite + Web)  |
                       +--------------+-------------+
                                     |
              +----------------------+----------------------+
              | (Tùy chọn)                                  | (Thao tác chính)
              v                                             v
 [ 01_Semantic_Alignment ]                     [ Workspace Song Ngữ ]
(Gợi ý 1-1, 1-n, n-1, n-m)                     (1-1, 1-n, n-1, n-m)
              |                                             |
       suggestions.json                                     v
              |                                    [ Kiểm định QA ]
              +------------------------------------>        |
                                                            v
                                                   [ Gói Giao Nộp ZIP ]
                                                (TSV, XLSX, Clean Text, QA)
```

## 2. Mô Hình Dữ Liệu & Quy Tắc Toàn Vẹn
Cơ sở dữ liệu SQLite cục bộ được kích hoạt `PRAGMA foreign_keys=ON` và `PRAGMA journal_mode=WAL` để đảm bảo tốc độ cao và tính toàn vẹn giao dịch (ACID).

- **`projects`**: Thông tin tác phẩm, mã đề tài, người thực hiện, phiên bản (revision).
- **`tasks`**: Tiến độ thực hiện của từng sinh viên (mục tiêu chuẩn 2.000 cặp/người).
- **`documents`**: Lưu trữ text gốc, text sạch, SHA-256 hash và metadata nguồn.
- **`segments`**: Phân đoạn câu bất biến với `order_index`, trạng thái `active`. Khi tách/gộp, phân đoạn cũ chuyển `active=False` và ghi nhận `parent_ids` / `replaced_ids`.
- **`alignments`**: Lưu các cặp dóng hàng xác nhận (`confirmed`), gợi ý (`suggested`) hoặc cần duyệt lại (`needs_review`).
- **`alignment_members`**: Bảng quan hệ nhiều-nhiều liên kết alignment với các phân đoạn Hán và Việt.
- **`qa_issues`**: Ghi nhận các vấn đề chất lượng (`OMISSION`, `ADDITION`, `MISSING`, `FORMAT`, `DUPLICATE`, `ORDER`).
- **`revisions`**: Nhật ký append-only ghi lại toàn bộ lịch sử thao tác phục vụ hoàn tác (Undo) và kiểm toán.

## 3. Quy Tắc Bất Biến (Business Invariants)
1. **Không gán trùng**: Một phân đoạn đang `active` không thể thuộc 2 cặp dóng hàng `confirmed` khác nhau. Điều này được kiểm tra bằng database query trong transaction.
2. **Liền kề và có thứ tự**: Trong các kiểu gộp `1-n`, `n-1`, `n-m`, các phân đoạn ở mỗi vế bắt buộc phải liền kề theo `order_index`.
3. **Suy diễn kiểu từ số lượng**:
   - 1 Hán, 1 Việt $\rightarrow$ `1-1`
   - 1 Hán, $n \ge 2$ Việt $\rightarrow$ `1-n`
   - $n \ge 2$ Hán, 1 Việt $\rightarrow$ `n-1`
   - $n \ge 2$ Hán, $m \ge 2$ Việt $\rightarrow$ `n-m`
4. **Bảo toàn dữ liệu khi sửa đổi**: Khi tách (split), gộp (merge) hoặc sửa (edit) một phân đoạn đã dóng hàng, hệ thống tự động chuyển cặp dóng hàng liên quan sang trạng thái `needs_review` và tạo cảnh báo QA, không xóa mất dấu vết.
5. **Sao lưu an toàn**: Sử dụng SQLite Online Backup API với checkpoint WAL tự động, đảm bảo file sao lưu hoàn chỉnh và không bị hỏng do ghi dở dang.
