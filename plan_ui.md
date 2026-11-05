# Kế hoạch cải tiến Web — Han–Viet Alignment Studio

Ngày đánh giá: 04/11/2026.

## 1. Mục tiêu và phạm vi

Cải thiện độ tin cậy của dữ liệu, quy trình tự kiểm tra và giao diện Web sau khi
đối chiếu `Guideline.pdf` tại `C:/Users/ASUS/Desktop/Guideline.pdf`.

- Chỉ triển khai phần Web, kiểm thử và tài liệu liên quan.
- **Không sửa notebook, mã OCR hoặc Crawl.** Web có thể nhận metadata OCR đang có.
- Giữ kiến trúc FastAPI, Jinja2, JavaScript và SQLite local hiện tại.
- Ưu tiên tính đúng của dữ liệu trước thay đổi hình thức giao diện.
- Các hạng mục dưới đây đã được triển khai ngày 05/11/2026; bằng chứng và giới hạn ở mục 7.

Các yêu cầu từ Guideline cần đối chiếu: tối thiểu 2.000 cặp hợp lệ/người và
8.000 cặp/nhóm; bốn kiểu dóng hàng; TSV/XLSX cùng nội dung; text sạch; báo cáo
số cặp, số dòng Hán/Việt, kết quả tự kiểm tra, nguồn và công cụ. Tỷ lệ lỗi là
số cặp lỗi trên số cặp được kiểm tra hợp lệ; ngưỡng nghiệm thu dự kiến ≤30%,
mục tiêu nội bộ ≤20%. Mọi lỗi cụ thể đã phát hiện vẫn cần được sửa.

Các đề xuất như giao diện kiểm tra mẫu, checklist trước xuất, tài nguyên offline
và cải tiến responsive là giải pháp của dự án; không gán chúng thành yêu cầu
giao diện bắt buộc của Guideline. Cấu trúc thư mục bàn giao trong PDF là khuyến nghị.

## 2. Hiện trạng và bằng chứng

Đã đọc cả bốn trang Guideline, đối chiếu mã nguồn, xem các trang dự án, workspace,
làm sạch, QA và xuất dữ liệu bằng trình duyệt. Việc xem giao diện dùng bản sao
database; các tình huống lỗi được tái hiện trên dữ liệu thử trong bộ nhớ.

Phần đã có nền tảng phù hợp:

- Dóng hàng `1–1`, `1–n`, `n–1`, `n–m`; sửa, tách, gộp phân đoạn.
- Xuất cặp đã xác nhận; TSV và XLSX với sheet `DONG_HANG`, hai cột `Hán`, `Việt`.
- Kiểm tra parity giữa TSV/XLSX và cảnh báo một số lỗi định dạng/phạm vi.
- 20 kiểm thử liên quan đến alignment, segmentation, QA, AI contract và export đã qua.

Các vấn đề đã kiểm chứng:

- JSON gợi ý có schema sai, thiếu hash và thông tin revision không hợp lệ vẫn được nhập.
- API duyệt cho phép hai gợi ý trùng phân đoạn cùng chuyển sang `confirmed`.
- Quét QA xóa cả lỗi `OMISSION` đang mở do người kiểm tra ghi nhận.
- Ghi chú `[CHECKED_SOMETHING]` trên cặp bị từ chối vẫn được tính vào mẫu kiểm tra.
- Sau sửa rồi tách phân đoạn, phần OCR thô trong ZIP chứa nội dung đã sửa.
- ZIP không có `01_nguon`, trong khi giao diện mô tả có đầy đủ nguồn.
- Khi chặn CDN, Web mất CSS và xuất hiện lỗi `tailwind is not defined`.
- Khi có mạng, desktop hiển thị ổn; viewport 390px bị tràn ngang tới 704px.

Kiểm thử đang qua không chứng minh các luồng lỗi kể trên đã được xử lý.

## 3. P1 — Sửa trước khi dùng để nghiệm thu

### P1.1. Khóa tính toàn vẹn của gợi ý AI

Vị trí chính: `Web/app/routers/suggestions.py`, service alignment và schema liên quan.

- Validate schema thực tế, project, revision và hash; không bỏ qua kiểm tra khi trường bắt buộc bị thiếu.
- Đối chiếu gợi ý với dữ liệu hiện tại sau sửa/tách/gộp; từ chối gợi ý cũ.
- Khi duyệt, kiểm tra lại phân đoạn còn active, đúng ngôn ngữ/dự án, liền kề và chưa thuộc cặp confirmed khác.
- Thực hiện kiểm tra và chuyển trạng thái trong transaction; ghi lịch sử thao tác.
- Báo rõ số gợi ý nhập được, bị từ chối và lý do; tránh bỏ qua lỗi âm thầm.
- Giữ định dạng trao đổi hiện tại với notebook; không yêu cầu thay đổi notebook.

Nghiệm thu:

- Từ chối JSON sai schema, thiếu hash, sai project hoặc revision/hash cũ.
- Nhập hai gợi ý dùng cùng phân đoạn: sau khi duyệt một, duyệt gợi ý còn lại phải bị chặn.
- Gợi ý chưa duyệt không xuất vào TSV/XLSX; lỗi import/duyệt không để lại dữ liệu dở dang.

### P1.2. Hoàn thiện tự kiểm tra chất lượng

Vị trí chính: service quality, models/schema, API và giao diện QA.

- Thêm thao tác ghi nhận cặp đã kiểm tra đúng/sai, loại lỗi `OMISSION`, `ADDITION`, `MISSING` và ghi chú.
- Lưu đánh giá bằng dữ liệu có cấu trúc, không suy luận từ chuỗi trong `Alignment.notes`.
- Phân biệt cảnh báo tự động và lỗi thủ công; quét lại không xóa hoặc ghi đè đánh giá của người dùng.
- Tính tỷ lệ lỗi từ các cặp được kiểm tra hợp lệ, không đếm lặp khi một cặp có nhiều loại lỗi.
- Khi nội dung cặp thay đổi, đánh dấu đánh giá liên quan cần kiểm tra lại.
- Hiển thị mẫu số, số cặp lỗi và trạng thái chưa đánh giá khi chưa có mẫu hợp lệ.
- Thay câu “Dữ liệu sạch sẽ” bằng thông báo đúng phạm vi kiểm tra; không coi không có cảnh báo tự động là đúng ngữ nghĩa.

Nghiệm thu:

- Đánh giá thủ công tồn tại sau quét lại và tải lại trang.
- Cặp rejected, chưa kiểm tra hoặc đánh giá đã lỗi thời không làm sai mẫu số.
- Một cặp có nhiều lỗi chỉ được tính một lần trong số cặp lỗi.
- Không hiển thị đạt ngưỡng khi chưa có mẫu; số liệu đúng tại các mốc 20% và 30%.

### P1.3. Bảo toàn OCR/text thô

Vị trí chính: service import, segmentation và export.

- Xuất bản thô từ snapshot gốc đã lưu, không dựng lại từ các phân đoạn active.
- Sửa/tách/gộp/xóa phân đoạn chỉ tác động bản làm việc và lịch sử, không thay đổi bản thô.
- Đảm bảo file tải thô riêng và bản thô trong ZIP cùng trỏ tới đúng phiên bản nguồn.
- Khi không còn snapshot gốc, báo rõ thiếu bản thô; không gọi nội dung đã sửa là nguyên bản.

Nghiệm thu:

- Hash bản thô giữ nguyên sau sửa/tách/gộp/xóa và qua xuất ZIP.
- Text sạch phản ánh thay đổi đã lưu, trong khi bản thô vẫn khớp đầu vào gốc.

## 4. P2 — Hoàn thiện quy trình và vận hành

### P2.1. Truy vết nguồn và số trang

- Bổ sung form kiểm kê riêng cho Hán/Việt: tên tài liệu, URL, tên tệp, định dạng,
  số trang, phạm vi quyển/chương/trang, công cụ xử lý và ghi chú nguồn.
- Cho Web nhận metadata OCR hiện có để giữ liên kết giữa phân đoạn và trang nguồn.
- Với TXT không có metadata trang, hiển thị chưa rõ trang; không gán mọi câu thành Trang 1.
- Từ phân đoạn có thể mở nguồn hoặc tham chiếu trang tương ứng; phân đoạn gộp cần giữ đủ tham chiếu nguồn.

Nghiệm thu: thông tin nguồn lưu/reload/export đúng; chỉnh sửa phân đoạn không làm mất truy vết trang.

### P2.2. Checklist bàn giao

- Phân biệt xuất kết quả đang làm với đánh giá mức sẵn sàng bàn giao.
- Hiển thị số cặp theo người/phạm vi, số dòng Hán/Việt, đoạn chưa gán, cặp cần duyệt,
  mẫu đã kiểm tra, tỷ lệ lỗi, lỗi chưa xử lý và mức đầy đủ của nguồn/công cụ.
- Không dùng số cặp đã xác nhận làm bằng chứng tự động rằng toàn bộ cặp đều hợp lệ.
- Mô tả chính xác nội dung ZIP; chỉ ghi có nguồn khi thực sự đóng gói được nguồn.
- Đưa checklist và kết quả tự kiểm tra vào báo cáo xuất; nêu rõ dữ liệu còn thiếu.
- Đọc mục tiêu từ nhiệm vụ thay vì cố định mọi dự án thành 2.000 cặp.

Nghiệm thu: chỉ số trên dashboard, QA, checklist và báo cáo xuất khớp nhau;
không ghi đủ điều kiện bàn giao khi chưa có mẫu kiểm tra hoặc còn điều kiện chưa xác minh.

### P2.3. Chạy Web offline

- Đóng gói CSS và font cần thiết trong static assets của Web.
- Bỏ phụ thuộc Tailwind CDN/Google Fonts khi sử dụng ứng dụng local.
- Giữ font dự phòng đọc được chữ Hán và dấu tiếng Việt.

Nghiệm thu: chặn toàn bộ request ngoài localhost, các trang chính vẫn có bố cục
và thao tác bình thường; không có lỗi JavaScript do thiếu CDN.

## 5. P3 — Cải thiện thao tác giao diện

- Cho liên kết QA nhảy tới đúng câu/cặp, tự cuộn và làm nổi bật vị trí cần xử lý.
- Thêm chế độ hiển thị gọn và điều chỉnh cỡ chữ để thao tác với hàng nghìn cặp.
- Đánh dấu đúng tab điều hướng hiện tại; không luôn làm nổi bật Dóng Hàng.
- Cải thiện modal: nhãn rõ, focus bàn phím, đóng/mở và quay lại vị trí thao tác hợp lý.
- Sửa bố cục màn hình nhỏ, tránh thanh công cụ và hai cột ép nhau gây tràn ngang.
- Giữ desktop/laptop là ưu tiên; responsive không làm giảm khả năng đối chiếu hai ngôn ngữ.

Nghiệm thu: kiểm tra desktop 1366×768 và màn hình 390×844; không mất nút quan trọng,
không tràn ngang ngoài vùng cuộn chủ đích; thao tác bàn phím không bị mắc kẹt hoặc mất focus.

## 6. Thứ tự triển khai và kiểm thử

1. P1.1 → P1.2 → P1.3: khóa dữ liệu AI, hoàn thiện QA, bảo toàn bản thô.
2. P2.1 → P2.2 → P2.3: truy vết nguồn, bàn giao, offline.
3. P3: tối ưu thao tác và responsive.

- Thêm regression test cho từng lỗi đã tái hiện; không chỉ dựa vào status HTTP 200.
- Giữ các kiểm thử bốn kiểu dóng hàng, Unicode và parity TSV/XLSX.
- Kiểm tra round-trip import → biên tập → dóng hàng → kiểm tra mẫu → export.
- Thay đổi schema phải có migration giữ dữ liệu hiện có, được thử trên bản sao database.
- Chạy kiểm thử bằng database riêng; không dùng database đang làm việc của người dùng.
- Cập nhật báo cáo theo bằng chứng thực tế; chưa kiểm chứng thì ghi rõ, không đánh dấu hoàn tất.
- Không thay đổi notebook trong bất kỳ hạng mục nào của kế hoạch này.

## 7. Trạng thái triển khai — 05/11/2026

| Hạng mục | Trạng thái | Kết quả chính |
|---|---|---|
| P1.1 — AI | Đã triển khai | Schema/hash/project/revision bắt buộc; snapshot phân đoạn; khóa ghi SQLite trước duyệt; chặn gợi ý cũ/trùng; báo từng lý do từ chối và lưu lịch sử. |
| P1.2 — QA | Đã triển khai | Bảng đánh giá riêng, đúng/sai và loại lỗi; mẫu còn hiệu lực; một cặp lỗi chỉ đếm một lần; quét không xóa đánh giá thủ công. |
| P1.3 — Bản thô | Đã triển khai | Snapshot byte gốc theo phiên bản tài liệu trong DB; tải riêng/ZIP/trang đối chiếu cùng dùng snapshot; thiếu hoặc sai hash được báo rõ. |
| P2.1 — Nguồn | Đã triển khai | Form riêng Hán/Việt; upload nguồn; gắn metadata khớp TXT trước biên tập; giữ số trang qua tách/gộp; TXT thiếu metadata hiển thị chưa rõ trang. |
| P2.2 — Bàn giao | Đã triển khai | Checklist chung cho API/giao diện/ZIP; nhiệm vụ và mục tiêu tùy chỉnh; thống kê từng người/phạm vi; xuất bản đang làm hoặc yêu cầu đủ điều kiện. |
| P2.3 — Offline | Đã triển khai | CSS Tailwind đã biên dịch và font Inter/Noto Serif TC kèm OFL nằm trong static; không tải CDN/font ngoài khi chạy. |
| P3 — Thao tác | Đã triển khai | QA nhảy tới câu/cặp, danh sách chờ duyệt, chế độ gọn/cỡ chữ, tab hiện tại, modal giữ/trả focus, bố cục 1366×768 và 390×844. |

Kiểm chứng:

- 43 kiểm thử Web/nghiệp vụ/trình duyệt qua. Kiểm thử concurrent accept cho kết quả
  một yêu cầu thành công, một yêu cầu bị chặn; không có hai cặp confirmed trùng đoạn.
- Tỷ lệ mẫu kiểm tra tại 0 mẫu, 20%, 30%, 40%; ghi chú CHECKED và cặp rejected không
  thuộc mẫu; sửa nội dung làm đánh giá cũ mất hiệu lực. Lỗi nhiều loại không đếm lặp.
- Bản thô byte/hash giữ nguyên sau sửa, tách, gộp, xóa và xuất ZIP; reimport giữ phiên bản cũ.
- Smoke trình duyệt chạy quy trình tạo dự án → dóng hàng → QA → xuất; chặn toàn bộ
  request ngoài localhost, kiểm tra các trang chính ở hai viewport, modal và focus.
- Migration được thử trên fixture schema cũ và bản sao DB thật: 14 dự án, 14 nhiệm vụ,
  28 tài liệu, 239 phân đoạn, 20 cặp, 106 vấn đề QA, 125 lịch sử; số bản ghi và text
  phân đoạn giữ nguyên. Chạy lại migration không lỗi, có backup trước nâng cấp.
- Không chạy migration trên database làm việc trong phiên triển khai; ứng dụng sẽ
  tự nâng cấp khi khởi động bản mới. Bản sao trước nâng cấp có đuôi `.before-web-v2.bak`.

Giới hạn cần hiểu đúng:

- Migration giữ vấn đề QA cũ ở nguồn `legacy` vì không thể suy ra chắc chắn lỗi nào
  do người dùng ghi nhận. Chúng không bị quét tự động xóa; người dùng đối chiếu/xử lý.
- Đánh giá cũ chỉ nằm trong ghi chú không tự chuyển thành mẫu đã kiểm tra hợp lệ.
- Snapshot cũ chỉ phục hồi khi tệp lưu còn tồn tại và khớp SHA256; không phục dựng
  từ text đã biên tập. Thiếu snapshot được báo trong checklist và ZIP.
- Tệp nguồn chỉ vào ZIP khi thực sự đã upload; URL và kiểm kê nguồn nằm trong
  `01_nguon/inventory.json`. Không tự tải tài liệu từ URL ngoài.
- Checklist và quét tự động không chứng minh tất cả cặp đúng nghĩa. Dữ liệu thực tế
  vẫn cần kiểm tra và sửa lỗi cụ thể. Notebook/OCR/Crawl không đổi trong đợt này.
