# Triển khai plan_ui — 05/11/2026

Phạm vi: Web, kiểm thử và tài liệu. Không thay đổi notebook, OCR hoặc Crawl.

Đã triển khai P1.1–P1.3, P2.1–P2.3 và P3. Chi tiết và giới hạn nằm trong
[plan_ui.md](../plan_ui.md), cách dùng tại [user-guide.md](user-guide.md).

## Kiểm chứng

43 kiểm thử nghiệp vụ/API/browser qua. Nhóm regression bao gồm schema/hash/revision
AI, concurrent accept, đánh giá mẫu nhiều loại lỗi và hết hiệu lực, mốc 20%/30%,
ghi chú CHECKED không phải mẫu, snapshot qua sửa/tách/gộp/xóa, phiên bản khi reimport,
nguồn upload, metadata trang, mục tiêu từng nhiệm vụ, manifest ZIP và migration.
Giữ các bài kiểm tra bốn kiểu dóng hàng, Unicode, parity TSV/XLSX và backup/restore.

Browser thật Chrome headless kiểm tra tạo dự án → import → dóng hàng → QA → export;
chặn mọi request ngoài localhost, kiểm tra năm trang chính ở 1366×768 và 390×844,
tab điều hướng, cỡ chữ/chế độ gọn, modal/Esc/trả focus và QA nhảy đúng vị trí.
Ảnh local tại `artifacts/web-plan-ui/workspace-1366.png`, `workspace-390.png`.

Lệnh chạy với database kiểm tra riêng:

```powershell
$env:DATABASE_URL='sqlite:///D:/tool-dong-hang/artifacts/web-plan-test/session.db'
.venv/Scripts/python -m pytest tests/test_web_plan.py tests/test_alignment_types.py tests/test_segmentation.py tests/test_qa.py tests/test_export_parity.py tests/test_web_api.py tests/test_ai_contract.py tests/test_backup_restore.py tests/e2e/test_browser.py -q
```

Migration đã chạy hai lần trên fixture schema cũ và bản sao SQLite hiện có.
Bản sao có 14 dự án, 14 nhiệm vụ, 28 tài liệu, 239 phân đoạn, 20 cặp, 106 vấn đề QA,
125 lịch sử. So sánh trước/sau xác nhận số bản ghi và raw_text/clean_text không đổi;
backup trước nâng cấp tồn tại. Không migrate DB làm việc của người dùng trong phiên này.

## Giới hạn

Đây là kiểm chứng trên dữ liệu thử và bản sao, không xác nhận dữ liệu thật đã đủ
2.000/8.000 cặp hoặc đã đúng ngữ nghĩa. Dữ liệu cũ thiếu snapshot không thể khôi phục
từ phân đoạn đã sửa. Ghi chú CHECKED không được tự chuyển thành đánh giá; QA cũ giữ
nguồn `legacy`. Nguồn chỉ đóng gói tệp thực sự đã upload. Font có fallback hệ thống;
khả năng hiển thị mọi chữ hiếm phụ thuộc glyph có sẵn. Thư viện Python cần được cài
trước khi chạy offline; Node chỉ cần khi nhà phát triển build lại CSS.
