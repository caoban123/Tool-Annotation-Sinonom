import pytest
import os
import json
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from Web.app.db import Base
from Web.app.models import Project, Task, Document, Segment, Alignment, AlignmentMember, QAIssue
from Web.app.services.import_txt import process_txt_bytes
from Web.app.services.segmentation import segment_document, edit_segment, split_segment, merge_segments, delete_segment
from Web.app.services.alignment import create_alignment, undo_last_alignment
from Web.app.services.export import get_confirmed_pairs, generate_tsv, generate_xlsx, verify_export_parity
from Web.app.services.quality import get_project_statistics, run_automated_qa

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def project_setup(test_db):
    proj = Project(
        id="proj_test_01",
        ma_de_tai="HVB_01",
        ma_tac_pham="NAM_QUOC_SON_HA",
        name="Dự Án Kiểm Thử"
    )
    test_db.add(proj)
    test_db.commit()

    # Load fixtures
    fixtures_dir = Path(__file__).parent / "fixtures"
    with open(fixtures_dir / "han.txt", "rb") as f:
        han_bytes = f.read()
    with open(fixtures_dir / "viet.txt", "rb") as f:
        viet_bytes = f.read()

    han_doc = process_txt_bytes(test_db, proj.id, "han", han_bytes, "han.txt")
    viet_doc = process_txt_bytes(test_db, proj.id, "viet", viet_bytes, "viet.txt")

    han_segs = segment_document(test_db, han_doc, han_bytes.decode("utf-8"))
    viet_segs = segment_document(test_db, viet_doc, viet_bytes.decode("utf-8"))
    test_db.commit()

    return {
        "project": proj,
        "han_segs": han_segs,
        "viet_segs": viet_segs
    }

def test_t01_one_to_one(test_db, project_setup):
    """T01: 1 Han segment + 1 Viet segment -> '1-1'"""
    proj = project_setup["project"]
    h0 = project_setup["han_segs"][0]
    v0 = project_setup["viet_segs"][0]

    align = create_alignment(test_db, proj.id, [h0.id], [v0.id])
    test_db.commit()

    assert align.alignment_type == "1-1"
    assert align.status == "confirmed"

    pairs = get_confirmed_pairs(test_db, proj.id)
    assert len(pairs) == 1
    assert "古南交" in pairs[0][1]
    assert "Đất Nam Giao" in pairs[0][2]

def test_t02_one_to_many(test_db, project_setup):
    """T02: 1 Han segment + 2 contiguous Viet segments -> '1-n' joined into 1 cell"""
    proj = project_setup["project"]
    h1 = project_setup["han_segs"][1]
    v1 = project_setup["viet_segs"][1]
    v2 = project_setup["viet_segs"][2]

    align = create_alignment(test_db, proj.id, [h1.id], [v1.id, v2.id])
    test_db.commit()

    assert align.alignment_type == "1-n"
    pairs = get_confirmed_pairs(test_db, proj.id)
    assert len(pairs) == 1
    # Both Viet segments must be merged in one cell
    assert "Nhà Tần đặt quận Tượng." in pairs[0][2]
    assert "Lại chia đặt các quan cai trị." in pairs[0][2]

def test_t03_many_to_one(test_db, project_setup):
    """T03: 2 contiguous Han segments + 1 Viet segment -> 'n-1' joined into 1 cell"""
    proj = project_setup["project"]
    h2 = project_setup["han_segs"][2]
    h3 = project_setup["han_segs"][3]
    v3 = project_setup["viet_segs"][3]

    align = create_alignment(test_db, proj.id, [h2.id, h3.id], [v3.id])
    test_db.commit()

    assert align.alignment_type == "n-1"
    pairs = get_confirmed_pairs(test_db, proj.id)
    assert len(pairs) == 1
    assert "漢武帝平南越。" in pairs[0][1]
    assert "置交趾九郡。" in pairs[0][1]

def test_t04_many_to_many(test_db, project_setup):
    """T04: 2 contiguous Han + 2 contiguous Viet -> 'n-m' in 1 row"""
    proj = project_setup["project"]
    h4 = project_setup["han_segs"][4]
    h5 = project_setup["han_segs"][5]
    v4 = project_setup["viet_segs"][4]
    v5 = project_setup["viet_segs"][5]

    align = create_alignment(test_db, proj.id, [h4.id, h5.id], [v4.id, v5.id])
    test_db.commit()

    assert align.alignment_type == "n-m"
    pairs = get_confirmed_pairs(test_db, proj.id)
    assert len(pairs) == 1

def test_t05_non_contiguous_rejected(test_db, project_setup):
    """T05: non-contiguous segments must be rejected"""
    proj = project_setup["project"]
    h0 = project_setup["han_segs"][0]
    h2 = project_setup["han_segs"][2] # Gap between 0 and 2
    v0 = project_setup["viet_segs"][0]

    with pytest.raises(ValueError, match="khoảng cách"):
        create_alignment(test_db, proj.id, [h0.id, h2.id], [v0.id])

def test_t06_duplicate_confirmed_rejected(test_db, project_setup):
    """T06: Segment already in confirmed alignment cannot be assigned to another confirmed alignment"""
    proj = project_setup["project"]
    h0 = project_setup["han_segs"][0]
    v0 = project_setup["viet_segs"][0]
    v1 = project_setup["viet_segs"][1]

    create_alignment(test_db, proj.id, [h0.id], [v0.id])
    test_db.commit()

    with pytest.raises(ValueError, match="Không được gán trùng"):
        create_alignment(test_db, proj.id, [h0.id], [v1.id])

def test_t07_empty_side_rejected(test_db, project_setup):
    """T07: Alignment with empty side must be rejected"""
    proj = project_setup["project"]
    h0 = project_setup["han_segs"][0]

    with pytest.raises(ValueError, match="vế rỗng"):
        create_alignment(test_db, proj.id, [h0.id], [])

def test_t08_edit_split_merge_invalidates_confirmed(test_db, project_setup):
    """T08: Modifying a segment in a confirmed alignment marks alignment as needs_review"""
    proj = project_setup["project"]
    h0 = project_setup["han_segs"][0]
    v0 = project_setup["viet_segs"][0]

    align = create_alignment(test_db, proj.id, [h0.id], [v0.id])
    test_db.commit()
    assert align.status == "confirmed"

    # Edit v0
    edit_segment(test_db, proj.id, v0.id, "Đất Nam Giao thời xưa.")
    test_db.commit()

    test_db.refresh(align)
    assert align.status == "needs_review"
    assert "Cần duyệt lại" in align.notes

def test_t09_undo_restores_state(test_db, project_setup):
    """T09: Undo alignment removes alignment and frees up segments"""
    proj = project_setup["project"]
    h0 = project_setup["han_segs"][0]
    v0 = project_setup["viet_segs"][0]

    align = create_alignment(test_db, proj.id, [h0.id], [v0.id])
    test_db.commit()
    assert test_db.query(Alignment).count() == 1

    undo_last_alignment(test_db, proj.id)
    test_db.commit()
    assert test_db.query(Alignment).count() == 0

    # Now h0 and v0 can be aligned again without duplicate error
    align2 = create_alignment(test_db, proj.id, [h0.id], [v0.id])
    test_db.commit()
    assert align2.status == "confirmed"

def test_t12_all_four_types_export_parity(test_db, project_setup, tmp_path):
    """T12: Confirm all 4 types and export TSV + XLSX; exactly 4 rows with full parity"""
    proj = project_setup["project"]
    han = project_setup["han_segs"]
    viet = project_setup["viet_segs"]

    # 1-1
    create_alignment(test_db, proj.id, [han[0].id], [viet[0].id])
    # 1-n
    create_alignment(test_db, proj.id, [han[1].id], [viet[1].id, viet[2].id])
    # n-1
    create_alignment(test_db, proj.id, [han[2].id, han[3].id], [viet[3].id])
    # n-m
    create_alignment(test_db, proj.id, [han[4].id, han[5].id], [viet[4].id, viet[5].id])
    test_db.commit()

    pairs = get_confirmed_pairs(test_db, proj.id)
    assert len(pairs) == 4

    tsv_file = tmp_path / "test.tsv"
    xlsx_file = tmp_path / "test.xlsx"

    generate_tsv(pairs, tsv_file)
    generate_xlsx(pairs, xlsx_file)

    assert verify_export_parity(tsv_file, xlsx_file) == True

def test_t13_special_characters_and_formula_handling(test_db, project_setup, tmp_path):
    """T13: Formula characters (=, +, -, @), rare CJK outside BMP (𠀀, 𡨸) and Vietnamese accents"""
    proj = project_setup["project"]
    h6 = project_setup["han_segs"][6] # Contains =SUM(1+1) and 𠀀 𡨸喃
    v6 = project_setup["viet_segs"][6] # Contains =1+1 and 𠀀 𡨸喃

    align = create_alignment(test_db, proj.id, [h6.id], [v6.id])
    test_db.commit()

    pairs = get_confirmed_pairs(test_db, proj.id)
    assert len(pairs) == 1
    assert "𠀀" in pairs[0][1]
    assert "𠀀" in pairs[0][2]
    assert "=SUM(1+1)" in pairs[0][1]

    tsv_file = tmp_path / "special.tsv"
    xlsx_file = tmp_path / "special.xlsx"

    generate_tsv(pairs, tsv_file)
    generate_xlsx(pairs, xlsx_file)

    assert verify_export_parity(tsv_file, xlsx_file) == True
def test_t16_team_consolidation(test_db, project_setup, tmp_path):
    """T16: Consolidate multiple task delivery zip files, check duplicate handling and mismatched work rejection"""
    from Web.app.services.export import build_delivery_zip
    from scripts.consolidate_team import consolidate_packages
    
    proj1 = project_setup["project"]
    han = project_setup["han_segs"]
    viet = project_setup["viet_segs"]

    # Alignment 1 in Task 1
    create_alignment(test_db, proj1.id, [han[0].id], [viet[0].id])
    test_db.commit()

    zip1 = tmp_path / "task1.zip"
    build_delivery_zip(test_db, proj1.id, zip1)

    # Create Task 2 with matching ma_de_tai
    proj2 = Project(id="proj_t2", ma_de_tai="HVB_01", ma_tac_pham="NAM_QUOC_SON_HA", name="Task 2")
    test_db.add(proj2)
    test_db.commit()

    h1_copy = Segment(id="h1_c", document_id="d2", project_id=proj2.id, language="han", order_index=0, raw_text="秦始皇置象郡。", clean_text="秦始皇置象郡。", active=True)
    v1_copy = Segment(id="v1_c", document_id="d3", project_id=proj2.id, language="viet", order_index=0, raw_text="Nhà Tần đặt quận Tượng.", clean_text="Nhà Tần đặt quận Tượng.", active=True)
    test_db.add_all([h1_copy, v1_copy])
    test_db.commit()

    create_alignment(test_db, proj2.id, [h1_copy.id], [v1_copy.id])
    test_db.commit()

    zip2 = tmp_path / "task2.zip"
    build_delivery_zip(test_db, proj2.id, zip2)

    # Consolidate matching tasks
    cons_dir = tmp_path / "consolidated"
    report = consolidate_packages([zip1, zip2], cons_dir)
    assert report["status"] == "success"
    assert report["tasks_consolidated"] == 2
    assert report["total_unique_pairs"] == 2

    # Verify cross-topic conflict rejection
    proj3_conflict = Project(id="proj_conflict", ma_de_tai="HVB_99_DIFFERENT", ma_tac_pham="DIFF", name="Diff Topic")
    test_db.add(proj3_conflict)
    test_db.commit()
    h_diff = Segment(id="h_diff", document_id="d4", project_id=proj3_conflict.id, language="han", order_index=0, raw_text="異", clean_text="異", active=True)
    v_diff = Segment(id="v_diff", document_id="d5", project_id=proj3_conflict.id, language="viet", order_index=0, raw_text="Khác", clean_text="Khác", active=True)
    test_db.add_all([h_diff, v_diff])
    test_db.commit()
    create_alignment(test_db, proj3_conflict.id, [h_diff.id], [v_diff.id])
    test_db.commit()
    zip_conflict = tmp_path / "conflict.zip"
    build_delivery_zip(test_db, proj3_conflict.id, zip_conflict)

    with pytest.raises(ValueError, match="xung đột mã đề tài"):
        consolidate_packages([zip1, zip_conflict], cons_dir)

def test_delete_segment_and_cascade_unconfirm(test_db, project_setup):
    proj_id = project_setup["project"].id
    han_segs = project_setup["han_segs"]
    viet_segs = project_setup["viet_segs"]

    # Create 1-1 alignment with first segments
    align = create_alignment(test_db, proj_id, [han_segs[0].id], [viet_segs[0].id])
    test_db.commit()

    # Verify alignment exists
    assert test_db.query(Alignment).filter(Alignment.id == align.id).count() == 1

    # Delete han_segs[0]
    deleted_seg = delete_segment(test_db, proj_id, han_segs[0].id)
    test_db.commit()

    assert deleted_seg.active is False
    # Verify alignment was cleaned up / deleted
    assert test_db.query(Alignment).filter(Alignment.id == align.id).count() == 0

    # Verify next Han segment had order_index shifted from 1 to 0
    remaining_han = test_db.query(Segment).filter(
        Segment.project_id == proj_id,
        Segment.language == "han",
        Segment.active == True
    ).order_by(Segment.order_index).all()
    assert remaining_han[0].order_index == 0

