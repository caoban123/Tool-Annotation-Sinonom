# Hiệu năng Workspace

Đợt tối ưu ngày 06/11/2026 xử lý ba điểm chậm: dựng toàn bộ thẻ trong DOM,
tải lại toàn bộ phân đoạn/cặp sau mỗi xác nhận, và truy vấn thành viên riêng cho
từng cặp khi lấy danh sách alignment.

- Giới hạn 100 thẻ mỗi cột, có Trước/Sau và đi tới số ô. Giữ lựa chọn xuyên trang;
  tìm kiếm, Shift chọn dải, liên kết QA và sửa nhấp đúp vẫn dùng toàn bộ dữ liệu.
- Lập chỉ mục ID trong trình duyệt; chỉ cập nhật màu của các ô được chọn/bỏ chọn.
- Xác nhận/hoàn tác/hủy một cặp cập nhật các ô liên quan từ phản hồi server.
  Chỉ báo đã lưu sau phản hồi thành công; chặn gửi xác nhận lặp khi đang lưu.
  Các lựa chọn mới tạo trong lúc chờ được giữ lại.
- Một API dữ liệu làm việc gọn, bỏ bản raw text lặp và nội dung cặp lặp;
  lấy dữ liệu bằng 4 truy vấn cố định. API danh sách cặp cũ gom thành 2 truy vấn,
  giữ định dạng phản hồi cũ cho các chức năng khác.
- Sửa/tách/gộp/xóa ô vẫn tải lại snapshot để đồng bộ nội dung, chỉ mục và trạng thái.
  Tab khác không tự đồng bộ liên tục; bấm Tải lại dữ liệu khi cần.

## Lần đo local

Chrome headless trên Windows, SQLite riêng, 6.000 ô giả lập (1.000 Hán + 5.000 Việt),
50 cặp đã xác nhận. Cùng dữ liệu, so JS trước tối ưu (commit `40bfe1c`) với JS mới.
Dưới đây là khoảng quan sát trong hai lượt đo local, không phải cam kết tốc độ
cho mọi máy/tài liệu hay số liệu trung bình trên nhiều máy.

| Chỉ số | Trước | Sau |
|---|---:|---:|
| Thẻ trong DOM | 6.000 | 200 |
| Dựng lại danh sách và tính layout | 2.529–4.162 ms | 92–119 ms |
| Xác nhận một cặp, gồm lưu server và cập nhật UI | 5.797–9.209 ms | 59–75 ms |

Kiểm thử thêm 25.692 ô (2.213 Hán + 23.479 Việt): DOM vẫn tối đa 200 thẻ,
đi tới được ô Việt cuối. Kiểm tra số truy vấn với 500 cặp; phân trang/chọn xuyên
trang, tìm kiếm cuối sách, QA nhảy tới ô xa, nhấp đúp, fallback về gợi ý khi hủy cặp,
gửi xác nhận lặp và giữ lựa chọn mới trong lúc đang lưu.

Tái hiện (luôn dùng DB kiểm thử riêng):

```powershell
$env:DATABASE_URL='sqlite:///D:/tool-dong-hang/artifacts/workspace-performance/test.db'
.venv/Scripts/python -m pytest tests/test_workspace_performance.py -q
```

Để đo cả bản cũ, lưu nội dung `Web/app/static/workspace.js` ở commit `40bfe1c`
vào `artifacts/workspace-performance/baseline.js` (UTF-8) trước khi chạy.
Các số đo máy hiện tại được ghi tại `artifacts/workspace-performance/timings.json`.
Kết quả có thể khác giữa các lần chạy do CPU, cache, font và tải hệ thống.

## Phản hồi khi nhấp ô

Kiểm tra bổ sung bằng click thật trong Chrome ở chế độ chuyển động bình thường,
với 25.692 ô: trước sửa, trạng thái chọn đã cập nhật ở callback khung hình kế tiếp
(khoảng 4 ms trong lượt đo), nhưng màu nền, viền và bóng tiếp tục transition 150 ms.
Bỏ transition trên thẻ để trạng thái chọn/bỏ chọn hiển thị ngay; giữ nguyên nhấp đúp
để sửa và thao tác bàn phím. Các thẻ có trạng thái chọn không đổi không bị ghi lại
thuộc tính CSS khi chọn thêm ô khác.

Test `test_native_click_feedback_with_normal_motion` kiểm tra không có transition
đang chạy sau click, giữ nguyên DOM của thẻ, không ghi lại thẻ đã chọn khác và
khôi phục lựa chọn sau nhấp đúp. Số đo khung hình được ghi vào
`artifacts/workspace-performance/native-click.json`; đây là thời gian tới callback
requestAnimationFrame, không phải phép đo độ trễ màn hình vật lý.
