import os
import sys
import json
import zipfile
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Web.app.services.export import generate_tsv, generate_xlsx, verify_export_parity, sanitize_text

def inspect_task_package(zip_path: Path) -> Dict[str, Any]:
    """Inspects a task delivery zip file and extracts manifest and TSV content."""
    if not zip_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as z:
        manifest_files = [f for f in z.namelist() if f.endswith("task_manifest.json")]
        if not manifest_files:
            raise ValueError(f"File zip '{zip_path.name}' thiếu task_manifest.json")

        with z.open(manifest_files[0]) as mf:
            manifest = json.load(mf)

        tsv_files = [f for f in z.namelist() if f.endswith("_parallel.tsv")]
        if not tsv_files:
            raise ValueError(f"File zip '{zip_path.name}' thiếu file TSV song ngữ.")

        with z.open(tsv_files[0]) as tf:
            tsv_text = tf.read().decode("utf-8")

    pairs = []
    for line in tsv_text.splitlines():
        if not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) == 2:
            pairs.append((cols[0], cols[1]))

    return {
        "zip_path": str(zip_path),
        "manifest": manifest,
        "pairs": pairs
    }

def consolidate_packages(
    package_paths: List[Path],
    output_dir: Path
) -> Dict[str, Any]:
    """
    Consolidates multiple student task export packages.
    Enforces cross-task validation:
    1. Same ma_de_tai
    2. Overlap and duplicate detection
    3. Exporting consolidated parallel TSV and XLSX with round-trip parity
    """
    if not package_paths:
        raise ValueError("Cần cung cấp ít nhất một gói xuất task để tổng hợp.")

    output_dir.mkdir(parents=True, exist_ok=True)

    inspected = [inspect_task_package(p) for p in package_paths]

    # Verify matching ma_de_tai
    ma_de_tai_set = set(item["manifest"]["ma_de_tai"] for item in inspected)
    if len(ma_de_tai_set) > 1:
        raise ValueError(
            f"Phát hiện xung đột mã đề tài giữa các thành viên: {ma_de_tai_set}. "
            f"Không được tổng hợp các tác phẩm thuộc đề tài khác nhau!"
        )

    ma_de_tai = list(ma_de_tai_set)[0]
    ma_tac_pham = inspected[0]["manifest"]["ma_tac_pham"]

    all_pairs = []
    seen_pairs = set()
    duplicate_count = 0

    task_summaries = []

    for item in inspected:
        manifest = item["manifest"]
        pairs = item["pairs"]
        task_summaries.append({
            "task_file": Path(item["zip_path"]).name,
            "scope": manifest.get("scope", "Chưa rõ"),
            "pairs_count": len(pairs)
        })

        for h, v in pairs:
            clean_h = sanitize_text(h)
            clean_v = sanitize_text(v)
            key = (clean_h, clean_v)
            if key in seen_pairs:
                duplicate_count += 1
            else:
                seen_pairs.add(key)
                all_pairs.append((f"pair_{len(all_pairs)+1}", clean_h, clean_v))

    # Generate consolidated outputs
    out_tsv = output_dir / f"{ma_de_tai}_{ma_tac_pham}_group_consolidated.tsv"
    out_xlsx = output_dir / f"{ma_de_tai}_{ma_tac_pham}_group_consolidated.xlsx"
    out_summary = output_dir / "consolidation_report.json"

    generate_tsv(all_pairs, out_tsv)
    generate_xlsx(all_pairs, out_xlsx)
    verify_export_parity(out_tsv, out_xlsx)

    report = {
        "status": "success",
        "ma_de_tai": ma_de_tai,
        "ma_tac_pham": ma_tac_pham,
        "tasks_consolidated": len(inspected),
        "total_unique_pairs": len(all_pairs),
        "duplicate_pairs_skipped": duplicate_count,
        "tasks": task_summaries,
        "consolidated_tsv": str(out_tsv),
        "consolidated_xlsx": str(out_xlsx)
    }

    with open(out_summary, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tổng hợp các gói xuất kết quả từ 4 sinh viên.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Danh sách các file ZIP giao nộp của các thành viên")
    parser.add_argument("--output", default="data/consolidated", help="Thư mục xuất kết quả tổng hợp")
    args = parser.parse_args()

    paths = [Path(p) for p in args.inputs]
    res = consolidate_packages(paths, Path(args.output))
    print(f"Tổng hợp thành công {res['tasks_consolidated']} tác phẩm ({res['total_unique_pairs']} cặp song ngữ).")
