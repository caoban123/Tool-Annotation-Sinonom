import pytest
import io
from pathlib import Path
from fastapi.testclient import TestClient
from Web.app.main import app

client = TestClient(app)

def test_api_workflow_end_to_end():
    # 1. Create project
    res = client.post("/api/projects", json={
        "ma_de_tai": "HVB_01",
        "ma_tac_pham": "TEST_WORK",
        "name": "Dự Án Test E2E",
        "scope": "Quyển 1",
        "assigned_to": "Sinh Viên A"
    })
    assert res.status_code == 200, res.text
    project = res.json()
    proj_id = project["id"]

    # 2. Upload han.txt and viet.txt
    fixtures_dir = Path(__file__).parent / "fixtures"
    with open(fixtures_dir / "han.txt", "rb") as fh:
        han_data = fh.read()
    with open(fixtures_dir / "viet.txt", "rb") as fv:
        viet_data = fv.read()

    files = {
        "han_file": ("han.txt", io.BytesIO(han_data), "text/plain"),
        "viet_file": ("viet.txt", io.BytesIO(viet_data), "text/plain")
    }
    upload_res = client.post(f"/api/projects/{proj_id}/import", files=files)
    assert upload_res.status_code == 200, upload_res.text
    upload_json = upload_res.json()
    assert upload_json["han_segments_count"] > 0
    assert upload_json["viet_segments_count"] > 0

    # 3. List segments
    seg_res = client.get(f"/api/segments?project_id={proj_id}")
    assert seg_res.status_code == 200
    segments = seg_res.json()
    han_segs = [s for s in segments if s["language"] == "han"]
    viet_segs = [s for s in segments if s["language"] == "viet"]

    # 4. Create 1-1 alignment
    align_res = client.post("/api/alignments", json={
        "project_id": proj_id,
        "han_segment_ids": [han_segs[0]["id"]],
        "viet_segment_ids": [viet_segs[0]["id"]],
        "status": "confirmed"
    })
    assert align_res.status_code == 200
    align_data = align_res.json()
    assert align_data["alignment_type"] == "1-1"

    # 5. Check stats
    stats_res = client.get(f"/api/projects/{proj_id}/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["confirmed_alignments"] == 1
    assert stats["confirmed_11"] == 1

    # 6. Test undo
    undo_res = client.post("/api/alignments/undo", json={"project_id": proj_id})
    assert undo_res.status_code == 200
    stats_after_undo = client.get(f"/api/projects/{proj_id}/stats").json()
    assert stats_after_undo["confirmed_alignments"] == 0

    # Re-align 1-1
    client.post("/api/alignments", json={
        "project_id": proj_id,
        "han_segment_ids": [han_segs[0]["id"]],
        "viet_segment_ids": [viet_segs[0]["id"]],
        "status": "confirmed"
    })

    # 7. Test QA scan
    qa_res = client.post(f"/api/qa/scan?project_id={proj_id}")
    assert qa_res.status_code == 200
    issues = qa_res.json()
    assert len(issues) > 0 # Should detect unassigned remaining segments

    # 8. Test Export TSV & XLSX
    tsv_res = client.get(f"/api/exports/tsv?project_id={proj_id}")
    assert tsv_res.status_code == 200
    assert "\t" in tsv_res.text

    xlsx_res = client.get(f"/api/exports/xlsx?project_id={proj_id}")
    assert xlsx_res.status_code == 200
    assert len(xlsx_res.content) > 0

    # 9. Test Export ZIP delivery
    zip_res = client.get(f"/api/exports/zip?project_id={proj_id}")
    assert zip_res.status_code == 200
    assert len(zip_res.content) > 0
