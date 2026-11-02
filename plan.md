# MASTER PLAN — HAN–VIET ALIGNMENT STUDIO

> **Vai trò của tài liệu:** Đây là lệnh triển khai **end-to-end** dành cho coding agent (Cursor / VS Code Agent / Claude Code / Codex hoặc tương đương). Không phải bản ý tưởng. Agent phải thực sự tạo source code, notebook chạy được, test tự động, dữ liệu kiểm thử, tài liệu và chạy kiểm nghiệm.
>
> **Chỉ thị cốt lõi:** **KHÔNG DỪNG ở việc scaffold, thiết kế giao diện, tạo notebook rỗng, viết pseudo-code, chạy được trang chủ, hoặc chỉ vượt qua unit test. Chỉ đánh dấu HOÀN THÀNH khi toàn bộ Definition of Done và các hành trình end-to-end bên dưới đạt.** Khi gặp lỗi, tự đọc log → chẩn đoán → sửa → chạy lại. Không bỏ qua lỗi bằng cách xóa test, sửa expected result để khớp bug, hay thay inference thật bằng output hard-code mà không ghi rõ là fixture.
>
> **Giới hạn trung thực:** Nếu bị chặn bởi GPU/Internet/quyền truy cập PDF/nguồn web hoặc giới hạn môi trường, tiếp tục hoàn thiện tất cả phần có thể chạy local; ghi rõ mục nào **CHƯA KIỂM CHỨNG**, lý do, lệnh chạy lại và bằng chứng. **Không tuyên bố đạt toàn bộ khi một gate bắt buộc chưa được chứng minh.** Không yêu cầu người dùng xác nhận các tiểu tiết kỹ thuật nếu có thể tự đưa ra quyết định hợp lý.

## 0. BỐI CẢNH, MỤC TIÊU VÀ NGUỒN CHUẨN

Đồ án NLP: **dóng hàng Hán–Việt ở cấp câu/đoạn**. Nhóm 4 sinh viên, **mỗi người chạy ứng dụng local độc lập trên máy riêng**, mỗi người làm phạm vi / tác phẩm được giao, xuất kết quả để trưởng nhóm tổng hợp. **Không hosting, không VPS, không backend dùng chung, không đăng nhập online, không cloud database, không đồng bộ realtime.** Internet / Google Colab chỉ tùy chọn dùng lúc cào tài liệu, cài model hoặc OCR/AI.

Tài liệu yêu cầu nghiệp vụ: `Guideline.pdf` của giảng viên nếu có sẵn trong workspace; nếu không, các quy tắc bắt buộc đã được trích ở mục này. Agent phải phân biệt quy định giảng viên với tính năng do dự án đề xuất; **không tự gán benchmark của model thành độ chính xác trên Hán văn cổ**.

**Quy tắc theo Guideline.pdf:**

- 4 người, tối thiểu **2.000 cặp hợp lệ/người**, **8.000 cặp hợp lệ/nhóm**. Đây là chỉ tiêu sản phẩm do người dùng tạo, **không** phải yêu cầu phải sinh 8.000 cặp giả để tuyên bố hoàn thành phần mềm.
- Đầu ra nộp: hai file **TSV và XLSX giống nhau về nội dung/thứ tự**, hai bản text Hán/Việt sạch, báo cáo số cặp/số dòng mỗi phía/kết quả tự kiểm tra, nguồn tài liệu và công cụ.
- Một dòng TSV = `<CÂU_HÁN><TAB><CÂU_VIỆT>`; đúng **một TAB phân tách**, không TAB/CR/LF trong mỗi vế; không ghép nhiều khoảng trắng thay TAB. Dữ liệu trong Excel: sheet `DONG_HANG`, tiêu đề đúng `Hán`, `Việt`; chỉ hai cột, một cặp mỗi hàng từ hàng 2; không ô gộp, không dòng trống, không công thức, không số thứ tự chen vào hai cột. Có thể thêm sheet thống kê **riêng**, nhưng v1 chỉ nên xuất một sheet `DONG_HANG` để dễ kiểm chứng.
- Phải hỗ trợ **`1–1`, `1–n`, `n–1`, `n–m`** (n,m >= 2 khi ký hiệu n/m xuất hiện); ưu tiên đơn vị nhỏ nhất giữ đầy đủ nghĩa; không tách câu cơ học. `n–m` chỉ chọn khi bản dịch tái cấu trúc mạnh, không thể tách nhỏ hơn mà giữ đúng nghĩa.
- Làm sạch: loại đầu/chân trang, chú thích không thuộc nội dung, OCR rác/trùng; ghép câu đứt do trang; chuẩn hóa khoảng trắng/dấu câu **không đổi nghĩa**; giữ tên riêng, địa danh, niên hiệu, số và đơn vị; bỏ bảng/tranh nếu không thuộc nội dung.
- Chất lượng: cùng nghĩa, không bỏ/thừa nội dung, đúng tên/chức danh/địa danh/thời gian/ranh giới; lỗi **OMISSION, ADDITION, MISSING**. Tỷ lệ lỗi = số cặp lỗi / số cặp đã kiểm tra hợp lệ; **<= 30%** là ngưỡng nghiệm thu dự kiến, **<= 20%** là mục tiêu nội bộ. **Không được gắn nhãn “đạt” khi chưa có mẫu kiểm tra, không tự xóa lỗi đã phát hiện chỉ vì còn trong ngưỡng.**
- Lưu nguồn, OCR thô và text sạch riêng để truy vết; ghi phạm vi quyển/chương/trang.

**Dữ liệu người dùng nhận được:** Có năm đề tài minh họa HVB_01..HVB_05. Mọi bản Hán được mô tả là PDF Scan; HVB_01..03 Việt PDF Scan; HVB_04..05 Việt PDF Text. Một số tài liệu qua Google Drive và thư viện Hán Nôm. **Không giả định quyền truy cập URL hay tính tương ứng trước khi thực sự tải và kiểm tra.**

## 1. KIẾN TRÚC BẮT BUỘC — 3 MODULE, MỌI ĐƯỜNG CHẠY ĐỘC LẬP

**Module 1: `OCR/`**. Hai notebook trên Colab/Jupyter:

1. `OCR/notebooks/01_OCR_Han.ipynb`: PDF Scan/ảnh Hán → `han.txt` UTF-8; lưu OCR theo trang, metadata, log và checkpoint. Ưu tiên **PaddleOCR-VL-1.6** cho đối chứng chính, fallback **PP-OCRv6 Medium / phiên bản đang được PaddleOCR chính thức hỗ trợ tại lúc triển khai**, và chế độ test CPU nhỏ. Bảo vệ chữ Hán phồn thể/hiếm, không giản thể hóa, không dịch, không tự sửa nội dung không có trên ảnh.
2. `OCR/notebooks/02_OCR_Viet.ipynb`: PDF Scan/ảnh Việt → `viet.txt` UTF-8; ưu tiên dòng PaddleOCR tương thích, tùy chọn VietOCR để so sánh trên mẫu thật. Nếu đầu vào là PDF có text trích được, chỉ dẫn chuyển sang `Crawl/` thay vì OCR dư thừa.

**Module 2: `Crawl/`**. `Crawl/notebooks/01_Crawl_Text.ipynb`: URL website văn bản / PDF Text → `han.txt` hoặc `viet.txt`, kèm metadata nguồn. Website adapter có thể mở rộng; phải có HTML fixture chạy offline. Không cào vào vùng yêu cầu đăng nhập khi không có quyền, không vượt paywall, tôn trọng robots/ToS và rate limits. Ưu tiên trích xuất text trực tiếp từ PDF Text, tránh OCR không cần thiết. Cần kiểm tra font encoding và thứ tự đọc.

**Module 3: `Web/`**. Web **FastAPI + Jinja2 + JavaScript/CSS thuần + SQLite + SQLAlchemy + openpyxl**. Chạy trên `http://127.0.0.1:8000`, offline sau cài đặt. Nhập **`han.txt` + `viet.txt`**, tạo project/task, làm sạch, tách/ghép, dóng hàng thủ công bốn kiểu, kiểm tra lỗi, chỉnh sửa/hoàn tác, autosave, tìm kiếm, backup/restore, nhập gợi ý AI, xuất kết quả chuẩn.

**Notebook bổ trợ đặt trong `Web/notebooks/01_Semantic_Alignment.ipynb`** (không tạo module thứ tư): đọc dữ liệu câu đã có ID do Web xuất, embedding + optional reranking + dò đường theo thứ tự, xuất `suggestions.json`; hỗ trợ fallback nhập hai TXT với cùng engine phân đoạn; **không yêu cầu notebook để dùng Web**. Ưu tiên thử **Qwen3-Embedding-4B** khi GPU đủ, **Qwen3-Embedding-0.6B** khi GPU ít, baseline **LaBSE**; reranker **Qwen3-Reranker-0.6B** là tùy chọn. Không mặc định model mạnh hơn = đúng hơn trên Hán cổ; so sánh trên gold set trước khi quyết định mặc định. Không đưa trực tiếp model 4B vào web local.

**Luồng chính:** PDF Scan → OCR notebook → `han.txt`/`viet.txt` **HOẶC** URL/PDF Text → Crawl notebook → `han.txt`/`viet.txt` → Web import → làm sạch/tách → (tùy chọn Web export segments → Semantic notebook → `suggestions.json` → Web import) → người xác nhận → QA → TSV/XLSX/TXT sạch/report/backup.

## 2. CẤU TRÚC REPOSITORY PHẢI TẠO

```text
HanViet-Alignment/
├── plan.md
├── README.md
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── user-guide.md
│   ├── colab-guide.md
│   ├── model-benchmark.md
│   ├── acceptance-report.md
│   └── contracts.md
├── OCR/
│   ├── README.md
│   ├── notebooks/
│   │   ├── 01_OCR_Han.ipynb
│   │   └── 02_OCR_Viet.ipynb
│   ├── utils/
│   │   ├── render_pdf.py
│   │   ├── ocr_pipeline.py
│   │   ├── page_order.py
│   │   ├── checkpoints.py
│   │   └── export_text.py
│   └── requirements.txt
├── Crawl/
│   ├── README.md
│   ├── notebooks/01_Crawl_Text.ipynb
│   ├── extractors/
│   │   ├── html_extractor.py
│   │   └── pdf_text_extractor.py
│   └── requirements.txt
├── Web/
│   ├── README.md
│   ├── run.py
│   ├── run.bat
│   ├── run.sh
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── routers/
│   │   │   ├── projects.py
│   │   │   ├── segments.py
│   │   │   ├── alignments.py
│   │   │   ├── quality.py
│   │   │   ├── suggestions.py
│   │   │   └── exports.py
│   │   ├── services/
│   │   │   ├── import_txt.py
│   │   │   ├── segmentation.py
│   │   │   ├── alignment.py
│   │   │   ├── quality.py
│   │   │   ├── versioning.py
│   │   │   ├── backup.py
│   │   │   └── export.py
│   │   ├── templates/
│   │   └── static/
│   ├── notebooks/01_Semantic_Alignment.ipynb
│   ├── ai/
│   │   ├── prepare_segments.py
│   │   ├── candidate_generation.py
│   │   ├── monotonic_alignment.py
│   │   └── export_suggestions.py
│   └── data/                       # local-only, gitignored; tự tạo lúc chạy
├── tests/
│   ├── fixtures/
│   │   ├── han.txt
│   │   ├── viet.txt
│   │   ├── sample.html
│   │   ├── sample_text.pdf
│   │   ├── sample_han_scan.png
│   │   ├── sample_viet_scan.png
│   │   └── expected_pairs.json
│   ├── test_web_api.py
│   ├── test_alignment_types.py
│   ├── test_segmentation.py
│   ├── test_export_parity.py
│   ├── test_qa.py
│   ├── test_backup_restore.py
│   ├── test_crawl.py
│   ├── test_ocr_contract.py
│   ├── test_ai_contract.py
│   ├── test_notebooks.py
│   └── e2e/test_browser.py
└── scripts/
    ├── verify_all.py
    ├── make_demo_data.py
    ├── benchmark_models.py
    └── consolidate_team.py
```

Tên có thể chỉnh vì kỹ thuật thực tế nhưng phải giữ **đúng ba module cấp cao**, các **bốn notebook chức năng** và mọi chức năng/đầu ra của kế hoạch. Không commit dữ liệu PDF có bản quyền, API key, cookie, file SQLite cá nhân, bản OCR thực tế hay model weights.

## 3. CONTRACT DỮ LIỆU — KHÔNG ĐƯỢC TỰ Ý ĐỔI

### 3.1. Hai TXT đầu vào Web

- UTF-8 (chấp nhận BOM khi import nhưng chuẩn xuất không BOM), Unicode nguyên bản, thứ tự văn bản đúng; tên file có thể khác nhưng UI phải rõ ngôn ngữ Hán/Việt; output notebook mặc định `han.txt`, `viet.txt`.
- Không yêu cầu số dòng Hán = số dòng Việt. Không coi **một dòng PDF** đồng nghĩa **một câu**. Không tự thêm bản dịch, không bỏ trang, không xóa chữ khó nhận dạng. Có thể bảo tồn ranh giới đoạn trong TXT, phân đoạn đúng nghiệp vụ xảy ra tại Web.
- Web lưu **snapshot byte gốc**, phiên bản decoded, hash SHA-256, metadata encoding, bản sạch và lịch sử; xử lý chuẩn newline `\r\n` và `\r`. Không làm mất chữ hiếm, dấu câu Hán, niên hiệu/tên riêng hoặc các ký tự Unicode ngoài BMP.
- OCR/crawler nên xuất thêm sidecar JSON với `source`, `language`, `page_number/url`, `reading_order`, `lines/regions`, `bbox` nếu có, `engine`, `model_version`, `timestamp`, `warnings`, `source_hash`. TXT là điều kiện tối thiểu; sidecar là tùy chọn, không làm Web phụ thuộc sidecar.

### 3.2. Gói Web → notebook AI

Web xuất `segments.jsonl` / ZIP gồm `schema_version`, `project_id`, `task_id`, `revision`, `source_sha256`, và mỗi segment: `segment_id`, `language` (`han`/`viet`), `order_index`, `text`, `page_ref`, `active`. Gồm cả hai ngôn ngữ ở cùng trạng thái revision. Notebook phải giữ nguyên ID/thứ tự, không tái định danh im lặng.

### 3.3. Notebook AI → Web

`suggestions.json` gồm `schema_version`, `project_id`, `task_id`, `source_revision`, `source_sha256` theo từng vế, `model_name`, `model_version`, `created_at`, `suggestions` array. Mỗi suggestion gồm `han_ids: string[]`, `viet_ids: string[]`, `alignment_type`, `score` (không mặc nhiên là xác suất), `status: suggested`, `explanation?` (tùy chọn). Chỉ dùng các ID có thật, phần tử trong từng vế phải tăng theo thứ tự và liền kề khi được gộp; nếu input hash/revision khác nhau phải **từ chối import rõ ràng**, không áp gợi ý sai văn bản.

Gợi ý chỉ là **proposed**, không được tự động tính là cặp đã xác nhận, không tự động đưa vào TSV/XLSX.

### 3.4. Kết quả bàn giao

```text
<MA_DE_TAI>_<MA_TAC_PHAM>/
├── 01_nguon/han/  va 01_nguon/viet/
├── 02_ocr_tho/han/ va 02_ocr_tho/viet/
├── 03_text_sach/han.txt va 03_text_sach/viet.txt
├── 04_dong_hang/<MA_TAC_PHAM>_parallel.tsv
├── 04_dong_hang/<MA_TAC_PHAM>_parallel.xlsx
├── reports/statistics.json
├── reports/qa_report.csv
├── reports/provenance.json
└── task_manifest.json
```

Nếu thiếu OCR vì trích PDF Text thì thư mục OCR thô có thể trống nhưng báo cáo nêu rõ phương pháp. Tệp phải mang mã nguồn/tác phẩm hợp lệ, chống path traversal.

**Export TSV/XLSX:** Chỉ lấy alignment `confirmed` và đủ hai vế, theo thứ tự nguồn. Một dòng TSV = hai vế đã gộp bằng một khoảng trắng hợp lý, cách nhau **đúng một TAB**, kết thúc `\n`. Với vế chứa TAB/CR/LF: **phát hiện và yêu cầu xử lý** hoặc chuẩn hóa whitespace một cách hiển thị rõ / có log; tuyệt đối không cắt mất chữ. Dữ liệu cần được escape đúng để không tạo công thức Excel, nhưng phải giữ **giá trị text chính xác bằng TSV**. XLSX sheet `DONG_HANG`, `A1=Hán`, `B1=Việt`, `A2:B...` đều là **kiểu chuỗi** (không có formula), không dòng trống/merged cells; không có cột ngoài A/B và v1 không có sheet khác. Sau khi export, **đọc lại cả hai file bằng code để so sánh số hàng, Unicode, giá trị, thứ tự; lỗi thì không cho tải kết quả với nhãn hợp lệ**. TSV không có header.

## 4. MÔ HÌNH DỮ LIỆU & QUY TẮC TOÀN VẸN

Tối thiểu các bảng:

- `projects`: id, đề tài/tác phẩm, source info, phạm vi, thời điểm tạo, config/version.
- `tasks`: id duy nhất, project_id, tên người làm (local), scope (chương/quyển/trang), status, target_count=2000.
- `documents`: id, project, language, raw bytes/text path/hash, cleaned text/hash, provenance, revision.
- `segments`: id bất biến, document_id, language, order_index, raw_text, clean_text, page_ref, parent/replaced IDs, active, revision.
- `alignments`: id, project_id/task_id, status (`draft`, `suggested`, `confirmed`, `needs_review`, `rejected`), notes, created_at, updated_at, revision.
- `alignment_members`: alignment_id, segment_id, side, position; **mỗi alignment có >=1 Hán và >=1 Việt** khi confirmed.
- `qa_issues`: id, alignment/segment, code `OMISSION` / `ADDITION` / `MISSING` / `FORMAT` / `DUPLICATE` / `ORDER`, severity, status, comment, resolved_at.
- `revisions`: append-only audit log (action, before, after, timestamp, resource version). Backup snapshot riêng.

**Bất biến:**

1. Mỗi segment active thuộc đúng một document và một side; hai side riêng; thứ tự ổn định.
2. Một segment **không thể thuộc hai alignment `confirmed` đang hoạt động** trong cùng project/task. Kiểm tra trong **transaction**, không chỉ frontend. Nhập trùng phải trả lỗi có thông tin đoạn.
3. Chỉ chấp nhận nhóm segment theo thứ tự và liền kề ở từng side, trừ một chế độ gap được hỗ trợ bằng quy tắc rõ ràng; v1 **không** hỗ trợ gộp nhảy cóc. Không tái sử dụng segment từ ngoài phạm vi task.
4. `1–1`: H1,V1; `1–n`: H1,V>=2; `n–1`: H>=2,V1; `n–m`: H>=2,V>=2. Kiểu **được suy ra từ cardinality** và được validate server-side.
5. Khi split/merge/sửa nội dung một segment đã confirmed, trước tiên hiển thị cặp bị ảnh hưởng và chuyển chúng về `needs_review`/thực hiện giao dịch cập nhật có xác nhận; không để cặp confirmed trỏ vào segment đã deactivate; không mất lịch sử.
6. Xóa/hoàn tác chỉ thay đổi trạng thái theo transaction, không xóa bản gốc hay lịch sử quan trọng. Backup/restore cần được test với SQLite đúng cách (SQLite backup API / checkpoint WAL), không đơn giản copy file DB đang ghi.
7. Tính `count_confirmed` từ DB chứ không tăng counter bất biến sau click; phân biệt `draft`, `suggested`, `confirmed`, `rejected`, `needs_review`.
8. Có kiểm tra bao phủ văn bản: mỗi segment chưa gán hiện rõ `unassigned`; `MISSING` cho đoạn trống/bị thiếu; `OMISSION/ADDITION` chỉ là nhãn kiểm tra có người đánh giá, không suy đoán chắc chắn từ độ dài hay cosine score.

## 5. UI/UX WEB — KHÔNG CHỈ DỰNG LANDING PAGE

**Màn hình:** (1) Dashboard tiến độ cá nhân; (2) Tạo project, nhập hai TXT; (3) Kiểm tra text & tách/ghép câu; (4) **Workspace dóng hàng**; (5) QA; (6) Export & Backup. Responsive tối thiểu laptop 1366 px, các trạng thái loading/empty/error/success rõ.

### Workspace trọng tâm

- Hai cột Hán/Việt cạnh nhau, cuộn độc lập, thẻ segment hiển thị ID, số trang/ngữ cảnh lân cận, văn bản đầy đủ, trạng thái (`unassigned`, `selected`, `confirmed`, `needs_review`, `suggested`). Không khóa hai bên theo cùng số dòng.
- Chọn 1 hoặc nhiều segment liền kề mỗi bên (click, Shift-click, Ctrl/Cmd tùy hành vi rõ), hiển thị preview nội dung gộp, tự suy ra `1–1`/`1–n`/`n–1`/`n–m`. Nút Confirm chỉ bật nếu hợp lệ. Có nút bỏ chọn, Undo, sửa, tách/gộp phân đoạn, tìm ID/nội dung, lọc unassigned/needs-review.
- Giữ dấu câu và văn tự Hán, font fallback CJK rõ, không chèn khoảng trắng giữa từng chữ Hán; khi nối các đoạn, làm theo quy tắc đã khai báo, không sửa nội dung nguồn.
- Phím tắt ít nhất: Ctrl+Enter xác nhận, Ctrl+Z undo, Esc bỏ chọn, Ctrl+K tìm, di chuyển lựa chọn bằng phím. Không bắt phím tắt khi focus ở ô nhập.
- Autosave sau thay đổi thành công trên backend, thông báo khi lỗi lưu, khôi phục sau đóng/mở lại và khởi động lại server.
- AI suggestions xuất hiện theo từng cặp với score / model / chấp nhận / sửa / từ chối, không tự confirm.
- Dashboard: số confirmed / 2000, số needs_review/unassigned/suggestions, thông tin task, lần sao lưu. Không gọi 2000 mục tiêu là 2000 cặp đã có.
- QA: hiển thị thiếu đoạn, trùng, sai thứ tự, warning semantic, nhãn OMISSION/ADDITION/MISSING; lọc/lưu ghi chú/giải quyết. Tỷ lệ lỗi theo mẫu **đã kiểm tra** với mẫu số hiện rõ; trạng thái `not evaluated` nếu chưa có mẫu, không bịa 0%.
- Export: báo số cặp đủ điều kiện, các warning, trạng thái so sánh TSV/XLSX; người dùng có thể tải ZIP chuẩn. Nếu còn unassigned thì cảnh báo **chưa hoàn tất phạm vi**, không tự nhận tất cả nội dung đã được dóng.

**Quan trọng:** Chức năng sửa, split và merge **phân đoạn nguồn** phải phân biệt với chọn 2–3 phân đoạn để ghép thành **một cặp dóng hàng**; tên nút và xử lý không được nhầm.

## 6. OCR NOTEBOOKS — THỰC THI, KHÔNG PHẢI MẪU TRANG TRÍ

Cả hai notebook phải chứa cell cài dependency, cấu hình đầu vào, upload/mount Drive (tùy chọn), nhận GPU nếu có, chọn model có fallback, render PDF theo trang có giới hạn DPI/kích thước, inference, khôi phục checkpoint, preview trang + text, kiểm tra và ghi TXT đúng chuẩn, sidecar metadata, tóm tắt kết quả. Phân đoạn nội dung không được phụ thuộc độ dài dòng ảnh.

**Hán:** Hỗ trợ cột dọc, mặc định đọc từ phải sang trái và trên xuống dưới **chỉ khi layout thực tế xác nhận là như vậy**. Phải cung cấp chế độ kiểm tra/override thứ tự block/column, preview overlay số thứ tự vùng. Không âm thầm thay chữ Hán phồn thể/hiếm bằng chữ giản thể hoặc ký tự tưởng tượng. Khi model không chắc, bảo tồn bản OCR, đánh dấu vùng nghi ngờ trong metadata để hiệu đính.

**Việt:** Phát hiện vùng chữ, dấu, nối dòng hợp lý, bảo tồn Unicode; có tùy chọn bỏ header/footer nếu người dùng duyệt. Nếu model chỉ hỗ trợ crop từng dòng phải implement detector/crop thực sự, không feed cả trang vào recognizer yêu cầu ảnh dòng mà bỏ qua bước phân tách.

**Đo và lưu metrics:** thời gian/trang, số trang thành công/thất bại, model/version/hardware, optional CER trên ground truth đã nhập tay, cảnh báo reading-order. Không tuyên bố độ chính xác theo điểm benchmark chung. Xử lý lỗi trang đơn lẻ: log và tiếp tục, sau đó cho retry các trang lỗi; không được xuất thành công âm thầm khi còn trang thiếu. Không đưa API key/trình xác thực vào notebook hoặc log.

**Checkpoint:** cache từng trang, hash PDF + page + model/config; restart không OCR lại trang đã hợp lệ, có nút force reprocess; sau khi hoàn tất ghép theo số trang, không ghép theo thứ tự hoàn thành thread.

**Kiểm thử tối thiểu:** fixtures ảnh in rõ Hán/Việt do dự án tạo có văn bản chuẩn, bài smoke với inference thật khi môi trường/model cho phép, bài test hợp đồng với mock trong CI (phải ghi rõ mock), bài test checkpoint/resume, error/duplicate page, Unicode rare-char, reading-order mapping; notebook phải mở hợp lệ theo nbformat và chạy `nbclient/papermill` ở smoke mode.

## 7. CRAWL NOTEBOOK — WEBSITE VÀ PDF TEXT THẬT

- `SOURCE_TYPE = html | pdf_text`, `LANGUAGE = han | viet`, `URL_OR_PATH`, `OUTPUT_NAME`, `PAGE_RANGE`/selectors nếu cần.
- `html`: requests + BeautifulSoup/lxml, retry/backoff/crawl delay, chỉ crawl các URL được phép, hỗ trợ phân trang/quyển khi rõ quy luật, loại menu/footer/ads/boilerplate, giữ headings/paragraphs theo thứ tự, HTML entities đúng, provenance URL từng phần.
- `pdf_text`: ưu tiên công cụ trích xuất text, kiểm tra số chữ hợp lý, thứ tự cột, lỗi encoding, trang scan giả làm PDF Text. Nếu thất bại báo chuyển OCR; **không** xuất một file rỗng với trạng thái thành công.
- Phải test bằng HTML fixture local (không phụ thuộc site internet) và một PDF có text thực sự. Có testcase URL lỗi/403/429, file scan không có text, website trả nội dung không mong muốn; không cào dữ liệu ngoài phạm vi.

## 8. SEMANTIC ALIGNMENT NOTEBOOK — AI TÙY CHỌN NHƯNG ĐẦY ĐỦ

**Mục tiêu:** Gợi ý cặp từ hai bản đã làm sạch/tách câu, bao gồm bốn kiểu dóng hàng và các đoạn chưa có đối ứng. Không sinh dịch, không tự chữa OCR, không tự confirm.

- Baseline: **LaBSE** hoặc sentence-transformers tương đương; candidate model: **Qwen3-Embedding-0.6B/4B**; reranker tùy chọn **Qwen3-Reranker-0.6B**; adapter interface `encode(texts)`, `score_pairs(pairs)` để thay model.
- GPU Colab T4 phải có lựa chọn 0.6B / batch nhỏ; 4B chạy khi đủ bộ nhớ và phiên bản phần mềm tương thích; không ép load 4B trên máy không đủ. CPU fallback hoặc no-model **deterministic** mode cho contract test, ghi nhãn rõ không phải AI semantic thật.
- Không brute force tất cả cặp O(N*M) cho sách dài. Ứng viên dùng đoạn/chương, cửa sổ theo thứ tự, top-K, giới hạn nhóm tối đa (cấu hình mặc định 3/3), cache embedding; có ràng buộc path đơn điệu (dynamic programming / beam search), penalty skip/mismatch, cơ chế abstain khi mơ hồ.
- Điểm reranker không phải xác suất chính xác. Nếu chưa có gold set, không hiển thị confidence % đánh lừa người dùng.
- Mọi suggestion trỏ tới ID từ Web, đúng hash/revision, mỗi vế liền kề và không chồng bất hợp lý; hỗ trợ 1-1,1-n,n-1,n-m và skip. Xuất JSON schema-versioned và log số gợi ý từng kiểu.
- Đo P/R/F1 và exact matching trên ít nhất 100–200 cặp đã gán chuẩn **nếu có dữ liệu thật**; nếu chưa có chỉ chạy fixture giả lập và ghi `real-data benchmark pending` (không bịa số). So sánh baseline và candidate, chốt model từ dữ liệu đo được.
- Notebook nhận 2 TXT độc lập **chỉ** trong chế độ tiện dụng: phải sử dụng cùng engine segmentation có version như Web hoặc chuẩn hóa thành segments, rồi đưa ra cảnh báo nếu ID/hash không khớp. Luồng chuẩn vẫn là Web export → notebook → Web import.

## 9. THỨ TỰ THỰC HIỆN — AGENT PHẢI LÀM ĐẾN CÙNG

**PHASE A — Khởi tạo và fixtures**

1. Đọc `plan.md` và `Guideline.pdf` nếu có. Tạo repo đúng cấu trúc, Python virtual env, pyproject/requirements phân module, `.gitignore`, README với 1 lệnh chạy web. Chọn phiên bản dependency **đã kiểm thử**, không pin package giả định tồn tại.
2. Tạo fixtures UTF-8 Hán cổ mô phỏng + Việt minh họa, nhiều đoạn khác độ dài, có 4 kiểu align và ít nhất một đoạn không đối ứng. Tạo HTML local và PDF Text/ảnh scan mẫu từ chính văn bản fixture (ghi rõ dữ liệu demo tự tạo, không phải trích sách nguồn). Xây dựng test contracts.
3. Build schema DB/migration an toàn, API và service cho import, segmentation, alignment, QA, export. Bắt đầu chạy test ngay.

**PHASE B — Web nghiệp vụ đầy đủ (ưu tiên cao nhất)**

4. Implement import TXT Unicode, source metadata, task/scope, raw/clean text/revision; split/merge/edit; lưu/reload đúng.
5. Implement all four alignment types, safeguards và thao tác undo; kiểm tra stale/concurrent update bằng revision ngay cả khi chạy đơn user.
6. Implement dashboard, workspace chọn hai cột, phím tắt, QA và suggestions import/export.
7. Implement ZIP/TSV/XLSX/sạch/statistics/backup/restore; test round-trip và file contract.
8. Chạy Playwright trên web thật và một demo end-to-end; sửa hết lỗi trước khi chuyển phase.

**PHASE C — Crawl**

9. Implement thư viện extractor + notebook; chạy HTML fixture và PDF Text thật; làm đúng báo lỗi/URL; output TXT import được vào Web; chạy test.

**PHASE D — OCR**

10. Implement render PDF, preprocessing, per-page pipeline, metadata, checkpoint, preview/order correction; hai notebook độc lập; chạy smoke trên fixture ảnh. Với model nặng, ưu tiên kiểm tra tài liệu chính thức và thử inference thật khi runtime cho phép, không dùng tên API tưởng tượng. Nếu runtime thiếu GPU/không tải được weights: test pipeline bằng adapter mock rồi ghi riêng trạng thái GPU inference **CHƯA KIỂM CHỨNG**; không tuyên bố OCR GPU hoạt động khi chưa chạy.
11. Kiểm tra output han.txt/viet.txt từ OCR thực tế hoặc fixture thông qua Web import. Chạy OCR resume sau ngắt giả lập và kiểm tra không bị mất/lặp trang.

**PHASE E — Semantic AI**

12. Implement baseline embedding và bộ thuật toán đề xuất không lệ thuộc model; chạy 4 kiểu với fixtures, score, skip, nhập Web. Thử model thật LaBSE/ Qwen3 theo tài nguyên môi trường, lưu log model/VRAM, benchmark khi có gold data.
13. Kiểm tra stale hash/revision; suggestions không xuất vào nộp khi chưa được confirm; kiểm tra hiệu năng trên bộ dữ liệu synthetic lớn.

**PHASE F — Tích hợp, kiểm tra và hướng dẫn nhóm**

14. Run end-to-end từ OCR và từ Crawl đến Web và export; chạy Playwright, pytest, notebook smoke, verify_all. Thử scenario 4 local installations tách nhau, mô phỏng 4 ZIP task hợp lệ, tổng hợp qua `scripts/consolidate_team.py` và phát hiện overlap/duplicate/sai tác phẩm.
15. Viết README + user-guide dễ hiểu cho 4 sinh viên, `colab-guide`, `model-benchmark`, `architecture`, `contracts`, `acceptance-report` có câu lệnh/chứng cứ thực tế. Không để TODO quan trọng trong critical path.
16. Lặp sửa/test đến khi **mọi gate bắt buộc pass**. Không chỉ viết kế hoạch rồi dừng.

## 10. BÀI TEST BẮT BUỘC CHO 4 KIỂU DÓNG HÀNG

Fixture minh họa:

```text
H001: 古南交，周號越裳。
H002: 秦置象郡。
H003: 漢武帝平南越。
H004: 置交趾郡。
H005: 其地山川秀麗。
H006: 又稱山川之勝。
H007: [đoạn giả lập chưa có đối ứng]

V001: Đất Nam Giao xưa, nhà Chu gọi là Việt Thường.
V002: Nhà Tần đặt quận Tượng.
V003: Vua Hán Vũ Đế bình định Nam Việt và đặt quận Giao Chỉ.
V004: Núi sông vùng này tươi đẹp. Cảnh núi sông được ca ngợi.
V005: [đoạn Việt thứ hai để tạo kiểm thử 1–n]
```

**Test phải dùng fixture khác có mapping gold rõ và chính xác cho từng loại**, không mặc định cứ câu liền kề là đúng nghĩa. Định nghĩa test độc lập:

| Case | Chọn Hán | Chọn Việt | Kết quả bắt buộc |
|---|---|---|---|
| T01 | 1 segment | 1 segment | `1–1`, lưu, reload, export đúng một hàng |
| T02 | 1 segment | 2 segment liền kề | `1–n`, ghép đúng 2 vế Việt **vào cùng một ô**, không tạo 2 cặp |
| T03 | 2 segment liền kề | 1 segment | `n–1`, ghép đúng 2 vế Hán **vào cùng một ô** |
| T04 | 2 segment liền kề | 2 hoặc 3 segment liền kề | `n–m`, đúng 1 hàng TSV và 1 hàng Excel |
| T05 | 2 segment không liền kề | 1 segment | từ chối hoặc yêu cầu điều chỉnh, không silently skip |
| T06 | segment đã confirmed | tạo confirmed thứ hai | reject, không duplicate |
| T07 | một vế rỗng | confirm | reject, gắn cảnh báo MISSING nếu phù hợp |
| T08 | edit/split/merge segment đã confirmed | thao tác | invalidation/review được quản lý, không mất dữ liệu |
| T09 | undo rồi reload | thao tác | trạng thái/DB đúng; có audit trail |
| T10 | AI gợi ý đúng nhưng chưa duyệt | export | **không** xuất suggestions chưa confirmed |
| T11 | file AI hash/revision cũ | import | từ chối rõ ràng |
| T12 | cả 4 kiểu đã confirmed | export | TSV/XLSX **4 hàng data**, hai cột giống nhau hoàn toàn |
| T13 | ký tự Hán ngoài BMP, dấu thanh Việt, `\t`, `\n`, dấu `=` | import / export | Unicode không mất; định dạng hợp lệ; Excel không có formula |
| T14 | lưu → dừng server → chạy lại | thao tác | vẫn đủ project, segment, alignment, notes, progress |
| T15 | backup → sửa/xóa → restore | thao tác | khôi phục đúng nội dung/hash, có xác nhận |
| T16 | export/import 4 task local | consolidate | thống kê chính xác; chặn trùng task/scope/cặp/khác tác phẩm sai cách |

Ngoài test logic, **Playwright bắt buộc thao tác UI thật**: import 2 TXT, chọn từng kiểu, xác nhận, undo, sửa, refresh, xem QA, export, mở file kết quả xác minh. Screenshot bằng chứng lỗi/đúng và log có thể lưu `artifacts/` nhưng không commit dung lượng lớn.

## 11. TEST & DEFINITION OF DONE — ĐIỀU KIỆN DỪNG DUY NHẤT

**Commands phải tồn tại và chạy được trên môi trường sạch:**

```bash
# Windows PowerShell (ví dụ; hướng dẫn cần có cho các OS)
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r Web/requirements.txt
.venv\Scripts\python Web/run.py

# Linux/macOS
python3 -m venv .venv
.venv/bin/python -m pip install -r Web/requirements.txt
.venv/bin/python Web/run.py

# Kiểm thử tổng hợp
python scripts/verify_all.py
```

Nếu thiếu dependency từ notebook GPU, **không được** buộc cả 4 người cài chúng để chạy Web. Tài liệu hướng dẫn cài riêng `OCR/requirements.txt`, `Crawl/requirements.txt` và bộ `Web/ai` khi cần.

**Các gate bắt buộc:**

- [ ] G01: README ghi rõ Python hỗ trợ; người mới cài và chạy Web local bằng 1 lệnh, không cần Internet sau cài. Host mặc định `127.0.0.1`, không public ra LAN.
- [ ] G02: Import TXT Hán/Việt UTF-8 thành công, giữ nguồn và revision; sửa/tách/ghép đúng, không mất chữ.
- [ ] G03: Bốn kiểu dóng hàng **1–1, 1–n, n–1, n–m** qua API **và giao diện** hoạt động, lưu và reload đúng.
- [ ] G04: Conflict, duplicate, noncontiguous, empty side và stale revision bị ngăn chặn server-side.
- [ ] G05: Autosave/undo/history/split/merge/backup/restore đều được thực nghiệm.
- [ ] G06: QA OMISSION/ADDITION/MISSING và báo cáo tiến độ/coverage/checked-sample error rate đúng, không giả định AI là ground truth.
- [ ] G07: TSV/XLSX theo đúng Guideline và **so sánh round-trip giá trị từng ô** pass; ký tự đặc biệt không bị mất; 4 kiểu đều xuất chính xác.
- [ ] G08: Crawl HTML fixture & PDF Text thành TXT đúng thứ tự, lỗi nguồn được báo, tích hợp import vào Web.
- [ ] G09: Notebook OCR Hán và Việt có code inference thật, khởi chạy hợp lệ, checkpoint/resume, text output; smoke thực tế trên ảnh fixture và ghi bằng chứng model/hardware đã chạy. Nếu thiếu GPU thì chỉ được ghi pass cho phần CPU/mock đã kiểm chứng, không pass giả GPU.
- [ ] G10: Notebook AI thật hoặc baseline embedding có thể chạy trên môi trường hỗ trợ; gợi ý 4 kiểu + skip, đúng schema/hash/revision, Web import và duyệt; không lẫn `suggested` với `confirmed`.
- [ ] G11: 4 local tasks xuất gói riêng, công cụ tổng hợp kiểm tra trùng/overlap và tổng hợp hợp lệ; không cộng nhầm tác phẩm khác nhau.
- [ ] G12: `pytest`, browser E2E, notebook smoke, `scripts/verify_all.py` chạy và report đầy đủ; test không bỏ qua im lặng. Không có exception chưa xử lý trong luồng chính.
- [ ] G13: Dùng được với fixture 2.000 cặp một máy và 8.000 cặp phân bố 4 task; đo truy vấn/dóng hàng/export hợp lý, không treo browser hoặc nhân đôi dữ liệu.
- [ ] G14: Docs đủ để một sinh viên khác chạy độc lập; `.gitignore` loại DB, secrets, tài liệu nguồn nhạy cảm; sample dataset ghi rõ là giả lập.
- [ ] G15: `docs/acceptance-report.md` có OS/Python/version, commands thực chạy, số test pass/fail, các thao tác E2E, bằng chứng file output, hạn chế chưa được xác minh. Nếu bất kỳ G01–G14 fail thì ghi rõ **NOT DONE**.

**Không chấp nhận**: notebook chỉ in `print('OCR done')`, mock data được ghi là kết quả model thực, giao diện nút giả không có backend, `n–m` chỉ lưu vào 2 hàng, Excel có cột số thứ tự, TSV thêm header, PDF Text chỉ output rỗng, notebook AI tự confirm, SQLite không giữ dữ liệu sau restart, file XLSX dùng formula, hay thiếu README khởi chạy.

## 12. CHECKLIST THỰC THI HẰNG VÒNG CHO AGENT

Sau mỗi phase, agent phải:

1. **Implement** code thật, không để TODO trong critical path.
2. **Run** unit/integration/browser smoke liên quan, ghi lệnh đã chạy.
3. **Inspect** output (`han.txt`, `viet.txt`, `suggestions.json`, TSV, XLSX, SQLite). Không chỉ dựa vào status 200 hoặc log `Success`.
4. **Debug** mọi lỗi, viết regression test, chạy lại cho đến pass.
5. **Update** `docs/acceptance-report.md` theo gate thật, không đánh dấu đạt trước.
6. Tiếp tục phase sau; cuối cùng chạy `scripts/verify_all.py` trên bản build cuối.

Chọn hướng ít phức tạp nhất đáp ứng yêu cầu. Không tự kéo React, Next.js, Postgres, Redis, Docker hay dịch vụ SaaS vào critical path nếu không có lý do rõ. Không sử dụng tài nguyên người dùng không cung cấp quyền truy cập. Nếu repo là Git, commit theo phase khi có thể nhưng không yêu cầu GitHub/Internet để chạy.

## 13. TÀI LIỆU CÔNG NGHỆ ĐỂ AGENT ĐỐI CHIẾU API CHÍNH THỨC

- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- PaddleOCR-VL-1.6: https://www.paddleocr.ai/main/en/version3.x/algorithm/PaddleOCR-VL/PaddleOCR-VL-1.6.html
- Qwen3 Embedding: https://github.com/QwenLM/Qwen3-Embedding
- Bertalign: https://pypi.org/project/bertalign/ (tham khảo `is_split=True`; không bắt buộc dùng nguyên bộ, có thể tự triển khai DP)
- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy: https://docs.sqlalchemy.org/en/20/
- openpyxl: https://openpyxl.readthedocs.io/
- Playwright Python: https://playwright.dev/python/

**Hãy dùng tài liệu đang tương thích với phiên bản package thực sự cài.** Với PyMuPDF, rà soát điều kiện giấy phép trước khi phân phối source; có thể dùng các thư viện PDF khác nếu cần.

---

## LỆNH CUỐI CÙNG CHO CODING AGENT

**BẮT ĐẦU TRIỂN KHAI NGAY.** Đọc toàn bộ file này. Đưa source vào đúng repository, xây dựng và chạy đủ 3 module OCR/Crawl/Web cùng notebook Semantic Alignment. Tự tạo fixtures hợp pháp để không lệ thuộc nguồn bên ngoài trong bộ kiểm thử. Chạy **end-to-end thật** trên Web, Crawl, OCR với điều kiện phần cứng hiện có, và Semantic Alignment; bắt buộc test **tất cả bốn kiểu `1–1`, `1–n`, `n–1`, `n–m`** qua UI, DB và file export. Tự sửa lỗi tới khi tất cả gate đã kiểm chứng đều pass. **Chỉ kết luận DONE khi G01–G15 thật sự đạt**; nếu thiếu GPU/quyền truy cập làm một gate chưa đạt, báo `NOT DONE — BLOCKED` kèm bằng chứng và bước tái kiểm thử, không che giấu hoặc tuyên bố hoàn thành giả.
