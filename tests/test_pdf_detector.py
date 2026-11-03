import pytest
from pathlib import Path
from OCR.utils.pdf_detector import inspect_pdf
from Crawl.utils.catalog import get_works_catalog, resolve_work
from Crawl.utils.id_generator import (
    generate_project_id, generate_document_id, generate_segment_id, compute_sha256, build_sidecar_metadata
)

def test_catalog_structure():
    catalog = get_works_catalog()
    assert len(catalog) == 5
    assert "HVNTDDC" in catalog
    assert "LTHCLC_Q20_25" in catalog
    assert "LTHCLC_Q46_49" in catalog
    assert "VIET_SU_YEU" in catalog
    assert "DVDDTB" in catalog

def test_resolve_work():
    res = resolve_work("LTHCLC_Q20_25")
    assert res["ma_de_tai"] == "HVB_01"
    assert res["ma_tac_pham"] == "LTHCLC_Q20_25"
    assert res["han_exists"] is True
    assert res["viet_exists"] is True

def test_pdf_detector_real_materials():
    base = Path("data/source_materials")
    if not base.exists():
        pytest.skip("data/source_materials not found")

    # 1. LTHCLC Q20-25 Han should be PDF_TEXT
    lthclc_han = base / "Lịch_triều_hiến_chương_loại_chí_Quyển_20-25_Lễ_nghi_chí" / "han" / "Lịch triều hiến chương loại chí Quyển 20-25 Lễ nghi chí.pdf"
    if lthclc_han.exists():
        info = inspect_pdf(str(lthclc_han), sample_pages=5)
        assert info["pdf_type"] == "PDF_TEXT"
        assert info["is_selectable_text"] is True
        assert info["recommended_engine"] == "extract_from_pdf_text"

    # 2. HVNTDDC Han should be PDF_SCAN
    hvntddc_han = base / "Hoàng_Việt_Nhất_Thống_Địa_Dư_Chí" / "han" / "Hoàng Việt Nhất Thống Dư Địa Chí.pdf"
    if hvntddc_han.exists():
        info = inspect_pdf(str(hvntddc_han), sample_pages=5)
        assert info["pdf_type"] == "PDF_SCAN"
        assert info["is_selectable_text"] is False
        assert info["recommended_engine"] == "ocr_pipeline"

    # 3. DVDDTB Han should be PDF_SCAN
    dvddtb_han = base / "Đại_Việt_địa_dư_toàn_biên" / "han" / "Đại việt địa dư toàn biên.pdf"
    if dvddtb_han.exists():
        info = inspect_pdf(str(dvddtb_han), sample_pages=5)
        assert info["pdf_type"] == "PDF_SCAN"
        assert info["is_selectable_text"] is False
        assert info["recommended_engine"] == "ocr_pipeline"

def test_id_generator():
    proj_id = generate_project_id("HVB 01", "HVNTDDC")
    assert proj_id == "proj_HVB_01_HVNTDDC"

    doc_id = generate_document_id("HVNTDDC", "han", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    assert doc_id == "doc_HVNTDDC_han_e3b0c442"

    seg_id = generate_segment_id("han", 0, "古南交")
    assert seg_id.startswith("seg_han_0001_")

    meta = build_sidecar_metadata(
        ma_de_tai="HVB_01",
        ma_tac_pham="HVNTDDC",
        tac_pham_name="Hoàng Việt Nhất Thống",
        language="han",
        source_file_path="",
        total_segments=10,
        total_characters=200,
        extractor_type="ocr_han_paddle"
    )
    assert meta["ma_de_tai"] == "HVB_01"
    assert meta["extraction"]["total_segments"] == 10
