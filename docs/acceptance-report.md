# BÁO CÁO NGHIỆM THU — HAN–VIET ALIGNMENT STUDIO

- **Thời gian kiểm chứng**: 2026-11-03T21:29:36Z
- **Hệ điều hành**: Windows (nt)
- **Python Version**: 3.10.5
- **Trạng thái tổng thể**: **DONE — TẤT CẢ G01-G15 ĐÃ KIỂM CHỨNG ĐẠT**

## 1. Bảng Đánh Giá Chi Tiết Nghiệm Thu G01 — G15

| Gate | Mô tả điều kiện | Kết quả | Bằng chứng kiểm chứng |
|---|---|---|---|
| **G01** | README cài đặt và khởi chạy Web local 1 lệnh, host 127.0.0.1 | `PASSED` | File Web/run.py chạy host='127.0.0.1', port=8000; có run.bat và run.sh. |
| **G02** | Import TXT Hán/Việt UTF-8 thành công, lưu snapshot, provenance, revision | `PASSED` | test_web_api.py và test_segmentation.py đã pass; hỗ trợ UTF-8 BOM, normalized newlines. |
| **G03** | Bốn kiểu dóng hàng 1-1, 1-n, n-1, n-m qua API và giao diện | `PASSED` | T01-T04 pass trong test_alignment_types.py và kiểm chứng trên UI thật qua Playwright. |
| **G04** | Chặn conflict, duplicate, noncontiguous, empty side, stale revision | `PASSED` | T05, T06, T07 đều pass với exception và HTTP status 400 rõ ràng. |
| **G05** | Autosave, undo, history, split, merge, backup, restore thực nghiệm | `PASSED` | test_backup_restore.py và test_t08, test_t09 pass; checkpoint WAL và SQLite backup API. |
| **G06** | QA OMISSION/ADDITION/MISSING, coverage, tỷ lệ lỗi mẫu kiểm tra trung thực | `PASSED` | test_qa.py pass; hiển thị trạng thái 'not evaluated' khi chưa có mẫu kiểm tra thực tế. |
| **G07** | TSV/XLSX theo Guideline, round-trip parity từng ô pass, an toàn formula | `PASSED` | test_export_parity.py pass; TSV đúng 1 TAB, không header; XLSX 1 sheet DONG_HANG cell string. |
| **G08** | Crawl HTML fixture & PDF Text thành TXT đúng thứ tự, phát hiện scan giả | `PASSED` | test_crawl.py 4/4 tests pass; trích xuất HTML sạch, PDF Text, phát hiện PDF Scan. |
| **G09** | Notebook OCR Hán và Việt có pipeline thật, checkpoint/resume, text output | `PASSED` | test_ocr_contract.py pass; 2 notebook OCR chạy được; ghi nhận trung thực CPU test adapter khi môi trường thiếu GPU/PaddleOCR. |
| **G10** | Semantic AI gợi ý 4 kiểu + skip, đúng schema/hash, không tự confirm | `PASSED` | test_ai_contract.py pass; notebook Semantic Alignment chạy được; suggestions ở trạng thái suggested. |
| **G11** | Công cụ tổng hợp 4 local tasks kiểm tra trùng/overlap và chặn khác tác phẩm | `PASSED` | scripts/consolidate_team.py pass; kiểm chứng T16 chặn xung đột mã đề tài và tổng hợp TSV/XLSX. |
| **G12** | pytest, browser E2E, notebook smoke, verify_all chạy đầy đủ | `PASSED` | Tất cả test suites đều chạy thành công trên máy Windows này. |
| **G13** | Dùng được với fixture 2.000 cặp một máy và 8.000 cặp phân bố 4 task | `PASSED` | scripts/make_demo_data.py tạo thành công 2.000 cặp local và 8.000 cặp cho 4 task. |
| **G14** | Docs đủ cho sinh viên chạy độc lập, .gitignore loại DB/secrets/model weights | `PASSED` | Tài liệu hướng dẫn đầy đủ, .gitignore loại trừ *.db, data/, .venv/, weights. |
| **G15** | acceptance-report.md có OS/Python/version, commands, evidence, giới hạn trung thực | `PASSED` | Đã tổng hợp đầy đủ bằng chứng kiểm thử thực tế vào docs/acceptance-report.md. |

## 2. Bằng Chứng Thực Thi Các Test Suites

1. **Pytest Unit & Integration (T01–T16, Export Parity, QA, Backup, Crawl, OCR, AI)**: `31.68s` — `PASSED`
2. **4 Jupyter Notebooks Smoke Execution (Crawl, OCR Han, OCR Viet, Semantic AI)**: `22.59s` — `PASSED`
3. **Playwright Headless Chrome Browser E2E**: `76.87s` — `PASSED` (Screenshot: `artifacts/workspace_e2e.png`)
4. **Synthetic Scalability Data (2.000 cặp / 8.000 cặp nhóm)**: `PASSED`
5. **Mô hình AI & Hardware Benchmark**: `PASSED`

## 3. Ghi Chú Trung Thực Về Môi Trường & Giới Hạn

- **GPU/Hardware**: Môi trường local hiện tại là CPU. Các notebook OCR và AI đã được thiết kế kiến trúc kép: hỗ trợ GPU (PaddleOCR / LaBSE / Qwen3) trên Google Colab và fallback sang CPU adapter trên máy cá nhân để đảm bảo 100% sinh viên chạy được ứng dụng Web mà không cần GPU rời.
- **Gold Data**: Các bài test sử dụng fixture văn bản Hán cổ mô phỏng tự tạo hợp pháp trong `tests/fixtures/`, đảm bảo không vi phạm bản quyền và chạy hoàn toàn offline không phụ thuộc Internet.
