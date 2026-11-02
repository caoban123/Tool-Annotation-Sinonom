import nbformat as nbf
from pathlib import Path

def create_semantic_alignment_notebook():
    nb = nbf.v4.new_notebook()
    cells = [
        nbf.v4.new_markdown_cell("# Module Bổ Trợ — Semantic Alignment (AI Gợi Ý Dóng Hàng Song Ngữ)\n\nNotebook này đọc gói phân đoạn `segments.jsonl` do Web Studio xuất, áp dụng mô hình embedding (Qwen3-Embedding / LaBSE hoặc baseline sim) cùng thuật toán quy hoạch động đơn điệu để tìm gợi ý dóng hàng 1-1, 1-n, n-1, n-m.\nKết quả xuất ra file `suggestions.json` để nhập trở lại vào Web Studio."),
        nbf.v4.new_code_cell("""# 1. Cài đặt và nạp thư viện
import os
import sys
from pathlib import Path

REPO_ROOT = Path('.').resolve()
if (REPO_ROOT / 'Web').exists():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
elif (REPO_ROOT.parent / 'Web').exists():
    if str(REPO_ROOT.parent) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT.parent))

from Web.ai.prepare_segments import load_segments_manifest, split_han_viet_segments
from Web.ai.candidate_generation import DeterministicSimAdapter, RealModelAdapter
from Web.ai.monotonic_alignment import align_segments_monotonic
from Web.ai.export_suggestions import create_suggestions_file
print("Đã nạp module AI Semantic Alignment thành công!")"""),
        nbf.v4.new_code_cell("""# 2. Cấu hình đầu vào và lựa chọn mô hình
# Đường dẫn file segments tải về từ Web Studio
INPUT_SEGMENTS_PATH = "data/segments_export.json"
MODEL_CHOICE = "deterministic_baseline"  # Hoặc 'LaBSE', 'Qwen3-Embedding-0.6B'
OUTPUT_FILE = Path("data/suggestions.json")

# Tạo fixture giả lập nếu chưa có file export từ Web
if not Path(INPUT_SEGMENTS_PATH).exists():
    Path("data").mkdir(parents=True, exist_ok=True)
    import json
    dummy_manifest = {
        "schema_version": "1.0",
        "project_id": "proj_demo",
        "revision": 1,
        "source_sha256_han": "abc123han",
        "source_sha256_viet": "def456viet",
        "segments": [
            {"segment_id": "h1", "language": "han", "order_index": 0, "text": "古南交，周號越裳。", "active": True},
            {"segment_id": "h2", "language": "han", "order_index": 1, "text": "秦始皇置象郡。", "active": True},
            {"segment_id": "v1", "language": "viet", "order_index": 0, "text": "Đất Nam Giao xưa, nhà Chu gọi là Việt Thường.", "active": True},
            {"segment_id": "v2", "language": "viet", "order_index": 1, "text": "Nhà Tần đặt quận Tượng.", "active": True},
            {"segment_id": "v3", "language": "viet", "order_index": 2, "text": "Lại chia đặt các quan cai trị.", "active": True}
        ]
    }
    with open(INPUT_SEGMENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(dummy_manifest, f, ensure_ascii=False, indent=2)
    print("Đã tạo demo segments_export.json")"""),
        nbf.v4.new_code_cell("""# 3. Nạp phân đoạn và chạy tìm gợi ý dóng hàng
manifest = load_segments_manifest(INPUT_SEGMENTS_PATH)
han_segs, viet_segs = split_han_viet_segments(manifest)

print(f"Tổng phân đoạn Hán: {len(han_segs)}")
print(f"Tổng phân đoạn Việt: {len(viet_segs)}")

if MODEL_CHOICE == "deterministic_baseline":
    scorer = DeterministicSimAdapter()
else:
    scorer = RealModelAdapter(MODEL_CHOICE)

suggestions = align_segments_monotonic(han_segs, viet_segs, scorer)
print(f"Đã tìm thấy {len(suggestions)} gợi ý dóng hàng!")
for s in suggestions:
    print(f"  [{s['alignment_type']}] Score={s['score']} | Han: {s['han_ids']} <-> Viet: {s['viet_ids']}")"""),
        nbf.v4.new_code_cell("""# 4. Xuất file suggestions.json đúng schema
res = create_suggestions_file(manifest, suggestions, model_name=MODEL_CHOICE, output_path=OUTPUT_FILE)
print(f"Đã lưu gợi ý: {OUTPUT_FILE}")
print(f"Tổng số gợi ý: {len(res['suggestions'])}")""")
    ]
    nb.cells = cells
    out_path = Path("Web/notebooks/01_Semantic_Alignment.ipynb")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print("Created Web/notebooks/01_Semantic_Alignment.ipynb")

if __name__ == "__main__":
    create_semantic_alignment_notebook()
