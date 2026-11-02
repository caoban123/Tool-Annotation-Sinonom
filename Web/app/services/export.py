import os
import json
import csv
import zipfile
import tempfile
import openpyxl
from pathlib import Path
from typing import List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from ..models import Project, Alignment, AlignmentMember, Segment, Document, QAIssue
from .quality import get_project_statistics

def sanitize_text(text: str) -> str:
    """
    Sanitizes internal tabs, carriage returns, and line feeds
    by replacing them with a single space. Strips edge whitespace.
    Preserves all Unicode characters (BMP and supplementary CJK/Nôm).
    """
    clean = text.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
    # Collapse multiple spaces into one space while keeping characters intact
    parts = clean.split()
    return " ".join(parts)

def get_confirmed_pairs(db: Session, project_id: str) -> List[Tuple[str, str, str]]:
    """
    Retrieves confirmed alignment pairs sorted by original source order.
    Returns list of tuples: (alignment_id, han_merged_text, viet_merged_text)
    """
    alignments = db.query(Alignment).filter(
        Alignment.project_id == project_id,
        Alignment.status == "confirmed"
    ).all()

    pairs = []
    for align in alignments:
        members = db.query(AlignmentMember, Segment).join(Segment).filter(
            AlignmentMember.alignment_id == align.id
        ).order_by(AlignmentMember.side, AlignmentMember.position).all()

        han_segs = [s for m, s in members if m.side == "han"]
        viet_segs = [s for m, s in members if m.side == "viet"]

        if not han_segs or not viet_segs:
            continue

        min_han_order = min(s.order_index for s in han_segs)

        # Merge segments on each side
        # For Han, classical text does not require space between sentences, but single space is acceptable if distinct
        han_text = sanitize_text(" ".join(s.clean_text for s in han_segs))
        viet_text = sanitize_text(" ".join(s.clean_text for s in viet_segs))

        pairs.append((min_han_order, align.id, han_text, viet_text))

    # Sort by the minimum Han order index
    pairs.sort(key=lambda x: x[0])
    return [(p[1], p[2], p[3]) for p in pairs]

def generate_tsv(pairs: List[Tuple[str, str, str]], out_path: Path) -> None:
    """Generates TSV file without header, exactly 1 tab between columns, ending with \\n."""
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for _, han_text, viet_text in pairs:
            # Ensure no tabs inside text
            assert "\t" not in han_text, "Found tab character in Han text"
            assert "\t" not in viet_text, "Found tab character in Viet text"
            f.write(f"{han_text}\t{viet_text}\n")

def generate_xlsx(pairs: List[Tuple[str, str, str]], out_path: Path) -> None:
    """
    Generates Excel XLSX with exactly one sheet 'DONG_HANG'.
    Header row A1='Hán', B1='Việt'.
    All cells explicitly typed as string to prevent formula injection while keeping exact values.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DONG_HANG"

    # Header
    ws.append(["Hán", "Việt"])

    for _, han_text, viet_text in pairs:
        # Append as strings
        row_idx = ws.max_row + 1
        c_han = ws.cell(row=row_idx, column=1, value=han_text)
        c_han.data_type = 's'
        c_viet = ws.cell(row=row_idx, column=2, value=viet_text)
        c_viet.data_type = 's'

    wb.save(out_path)
    wb.close()

def verify_export_parity(tsv_path: Path, xlsx_path: Path) -> bool:
    """
    Reads back both TSV and XLSX files to verify line-by-line, cell-by-cell exact equality.
    Raises ValueError on any discrepancy.
    """
    tsv_rows = []
    with open(tsv_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            cols = line.rstrip("\r\n").split("\t")
            if len(cols) != 2:
                raise ValueError(f"Dòng TSV #{line_num} không có đúng 2 cột (phát hiện {len(cols)} cột).")
            tsv_rows.append((cols[0], cols[1]))

    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    if "DONG_HANG" not in wb.sheetnames:
        raise ValueError("File Excel thiếu sheet 'DONG_HANG'.")
    ws = wb["DONG_HANG"]

    # Check header
    header_han = ws.cell(row=1, column=1).value
    header_viet = ws.cell(row=1, column=2).value
    if header_han != "Hán" or header_viet != "Việt":
        raise ValueError(f"Tiêu đề Excel không hợp lệ: A1='{header_han}', B1='{header_viet}', kỳ vọng 'Hán' và 'Việt'.")

    xlsx_rows = []
    for r in range(2, ws.max_row + 1):
        v1 = ws.cell(row=r, column=1).value or ""
        v2 = ws.cell(row=r, column=2).value or ""
        xlsx_rows.append((str(v1), str(v2)))
    wb.close()

    if len(tsv_rows) != len(xlsx_rows):
        raise ValueError(f"Số hàng không khớp: TSV có {len(tsv_rows)} hàng, XLSX có {len(xlsx_rows)} hàng.")

    for idx, ((t_h, t_v), (x_h, x_v)) in enumerate(zip(tsv_rows, xlsx_rows), 1):
        if t_h != x_h:
            raise ValueError(f"Sai khác cột Hán ở hàng #{idx}:\nTSV:  '{t_h}'\nXLSX: '{x_h}'")
        if t_v != x_v:
            raise ValueError(f"Sai khác cột Việt ở hàng #{idx}:\nTSV:  '{t_v}'\nXLSX: '{x_v}'")

    return True

def build_delivery_zip(db: Session, project_id: str, out_zip_path: Path) -> Dict[str, Any]:
    """
    Constructs the full standardized delivery ZIP according to Section 3.4 of plan.md:
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
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError(f"Không tìm thấy dự án {project_id}")

    ma_prefix = f"{project.ma_de_tai}_{project.ma_tac_pham}"
    pairs = get_confirmed_pairs(db, project_id)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        tsv_file = tmp / f"{project.ma_tac_pham}_parallel.tsv"
        xlsx_file = tmp / f"{project.ma_tac_pham}_parallel.xlsx"

        generate_tsv(pairs, tsv_file)
        generate_xlsx(pairs, xlsx_file)
        verify_export_parity(tsv_file, xlsx_file)

        # Get Clean Documents
        han_doc = db.query(Document).filter(Document.project_id == project_id, Document.language == "han").first()
        viet_doc = db.query(Document).filter(Document.project_id == project_id, Document.language == "viet").first()

        han_clean_path = tmp / "han.txt"
        viet_clean_path = tmp / "viet.txt"

        han_segs = db.query(Segment).filter(
            Segment.project_id == project_id,
            Segment.language == "han",
            Segment.active == True
        ).order_by(Segment.order_index).all()
        viet_segs = db.query(Segment).filter(
            Segment.project_id == project_id,
            Segment.language == "viet",
            Segment.active == True
        ).order_by(Segment.order_index).all()

        with open(han_clean_path, "w", encoding="utf-8", newline="\n") as f:
            for s in han_segs:
                f.write(s.clean_text + "\n")

        with open(viet_clean_path, "w", encoding="utf-8", newline="\n") as f:
            for s in viet_segs:
                f.write(s.clean_text + "\n")

        # Reports
        stats = get_project_statistics(db, project_id)
        stats_file = tmp / "statistics.json"
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        provenance_file = tmp / "provenance.json"
        prov_data = {
            "project_id": project.id,
            "ma_de_tai": project.ma_de_tai,
            "ma_tac_pham": project.ma_tac_pham,
            "han_document": json.loads(han_doc.provenance) if han_doc and han_doc.provenance else {},
            "viet_document": json.loads(viet_doc.provenance) if viet_doc and viet_doc.provenance else {},
        }
        with open(provenance_file, "w", encoding="utf-8") as f:
            json.dump(prov_data, f, ensure_ascii=False, indent=2)

        # QA Report CSV
        qa_issues = db.query(QAIssue).filter(QAIssue.project_id == project_id).all()
        qa_file = tmp / "qa_report.csv"
        with open(qa_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "code", "severity", "status", "alignment_id", "segment_id", "comment"])
            for q in qa_issues:
                writer.writerow([q.id, q.code, q.severity, q.status, q.alignment_id or "", q.segment_id or "", q.comment])

        # Manifest
        manifest = {
            "schema_version": "1.0",
            "ma_de_tai": project.ma_de_tai,
            "ma_tac_pham": project.ma_tac_pham,
            "scope": project.scope,
            "confirmed_pairs_count": len(pairs),
            "unassigned_han_count": stats["unassigned_han"],
            "unassigned_viet_count": stats["unassigned_viet"],
            "exported_files": [
                f"{ma_prefix}/04_dong_hang/{project.ma_tac_pham}_parallel.tsv",
                f"{ma_prefix}/04_dong_hang/{project.ma_tac_pham}_parallel.xlsx",
                f"{ma_prefix}/03_text_sach/han.txt",
                f"{ma_prefix}/03_text_sach/viet.txt",
                f"{ma_prefix}/reports/statistics.json",
                f"{ma_prefix}/reports/qa_report.csv",
                f"{ma_prefix}/reports/provenance.json"
            ]
        }
        manifest_file = tmp / "task_manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # Build ZIP archive
        out_zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(tsv_file, f"{ma_prefix}/04_dong_hang/{project.ma_tac_pham}_parallel.tsv")
            z.write(xlsx_file, f"{ma_prefix}/04_dong_hang/{project.ma_tac_pham}_parallel.xlsx")
            z.write(han_clean_path, f"{ma_prefix}/03_text_sach/han.txt")
            z.write(viet_clean_path, f"{ma_prefix}/03_text_sach/viet.txt")
            z.write(stats_file, f"{ma_prefix}/reports/statistics.json")
            z.write(qa_file, f"{ma_prefix}/reports/qa_report.csv")
            z.write(provenance_file, f"{ma_prefix}/reports/provenance.json")
            z.write(manifest_file, f"{ma_prefix}/task_manifest.json")

    return {
        "status": "success",
        "zip_path": str(out_zip_path),
        "pairs_count": len(pairs),
        "stats": stats
    }
