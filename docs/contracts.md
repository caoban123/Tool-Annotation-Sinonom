# Đặc Tả Giao Diện Dữ Liệu (Data Contracts)

Tài liệu này quy định bất biến các chuẩn dữ liệu trao đổi giữa các Module để đảm bảo không bị đứt gãy luồng xử lý.

## 1. Hợp Đồng File Text Đầu Vào Web (`han.txt` & `viet.txt`)
- Định dạng: UTF-8 nguyên bản, chấp nhận UTF-8 BOM khi tải lên nhưng chuẩn xuất nội bộ không có BOM.
- Ký tự: Bảo tồn toàn bộ chữ Hán phồn thể, chữ Nôm, ký tự ngoài BMP (ví dụ `𠀀`, `𡨸`), dấu thanh tiếng Việt đầy đủ.
- Dòng/Phân đoạn: Không quy định số dòng Hán phải bằng số dòng Việt; phân đoạn nghiệp vụ diễn ra tại Web dựa trên dấu câu.
- Newlines: Chuẩn hóa `\r\n` và `\r` thành `\n`.

## 2. Gói Web $\rightarrow$ Notebook AI (`segments.jsonl`)
Web Studio xuất manifest JSON/JSONL chứa:
```json
{
  "schema_version": "1.0",
  "project_id": "proj_123",
  "task_id": "task_456",
  "revision": 3,
  "source_sha256_han": "e3b0c44298fc1c149afbf4c8996fb924...",
  "source_sha256_viet": "ca978112ca1bbdcafac231b39a23dc4...",
  "exported_at": "2026-11-03T01:00:00Z",
  "segments": [
    {
      "segment_id": "seg_han_0001_abcd",
      "language": "han",
      "order_index": 0,
      "text": "古南交，周號越裳。",
      "page_ref": "1",
      "active": true
    }
  ]
}
```

## 3. Gói Notebook AI $\rightarrow$ Web (`suggestions.json`)
Notebook AI trả về danh sách gợi ý kèm kiểm tra toàn vẹn hash:
```json
{
  "schema_version": "1.0",
  "project_id": "proj_123",
  "task_id": "task_456",
  "source_revision": 3,
  "source_sha256_han": "e3b0c44298fc1c149afbf4c8996fb924...",
  "source_sha256_viet": "ca978112ca1bbdcafac231b39a23dc4...",
  "model_name": "sentence-transformers/LaBSE",
  "model_version": "1.0",
  "created_at": "2026-11-03T01:05:00Z",
  "suggestions": [
    {
      "han_ids": ["seg_han_0001_abcd"],
      "viet_ids": ["seg_viet_0001_efgh"],
      "alignment_type": "1-1",
      "score": 0.892,
      "status": "suggested"
    }
  ]
}
```
**Quy tắc bắt buộc:**
- Web sẽ từ chối nhập (`HTTP 400`) nếu `source_sha256_han` hoặc `source_sha256_viet` không khớp với văn bản hiện tại của dự án.
- Gợi ý chỉ lưu ở trạng thái `suggested`, không tự động đánh dấu `confirmed` và không đưa vào file xuất TSV/XLSX khi chưa có người xác nhận.

## 4. Định Dạng Giao Nộp Cuối Cùng (TSV & XLSX)
### File TSV (`<MA_TAC_PHAM>_parallel.tsv`):
- Mỗi dòng tương ứng một cặp dóng hàng xác nhận.
- Cột Hán và cột Việt phân tách bằng đúng **1 ký tự TAB (`\t`)**.
- Không có dòng tiêu đề (header).
- Kết thúc bằng ký tự `\n`.
- Không có ký tự TAB hoặc xuống dòng nội tại trong từng ô văn bản (phải được thay thế bằng khoảng trắng).

### File Excel (`<MA_TAC_PHAM>_parallel.xlsx`):
- Đúng một sheet duy nhất tên: `DONG_HANG`.
- Dòng 1: Tiêu đề cột `Hán` (ô A1) và `Việt` (ô B1).
- Từ dòng 2 trở đi: Mỗi dòng một cặp song ngữ.
- Toàn bộ ô dữ liệu được đặt kiểu chuỗi tường minh (`cell.data_type = 's'`) để tránh thực thi công thức đối với các câu bắt đầu bằng `=`, `+`, `-`, `@`.
- **Kiểm định Parity**: Sau khi xuất, hệ thống đọc lại cả 2 file để so sánh số hàng, thứ tự và giá trị từng ô; nếu sai lệch sẽ chặn xuất file.
