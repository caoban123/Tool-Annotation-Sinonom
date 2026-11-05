import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Project
from ..services.export import (
    get_confirmed_pairs,
    generate_tsv,
    generate_xlsx,
    verify_export_parity,
    build_delivery_zip
)
from ..services.backup import (
    create_database_backup,
    restore_database_backup,
    list_backups
)

router = APIRouter(prefix="/api/exports", tags=["exports"])

@router.get("/tsv")
def export_tsv_endpoint(project_id: str = Query(...), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    pairs = get_confirmed_pairs(db, project_id)
    if not pairs:
        raise HTTPException(status_code=400, detail="Chưa có cặp dóng hàng nào được xác nhận (confirmed).")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tsv")
    tsv_path = Path(tmp.name)
    tmp.close()

    generate_tsv(pairs, tsv_path)
    return FileResponse(
        path=str(tsv_path),
        filename=f"{project.ma_tac_pham}_parallel.tsv",
        media_type="text/tab-separated-values"
    )

@router.get("/clean-text")
def export_clean_text(
    project_id: str = Query(...),
    language: str = Query("han"), # 'han' or 'viet'
    db: Session = Depends(get_db)
):
    from ..models import Segment
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    segs = db.query(Segment).filter(
        Segment.project_id == project_id,
        Segment.language == language,
        Segment.active == True
    ).order_by(Segment.order_index).all()

    clean_content = "\n".join(s.clean_text for s in segs)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    tmp_path = Path(tmp.name)
    tmp.close()

    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(clean_content)

    return FileResponse(
        path=str(tmp_path),
        filename=f"{project.ma_tac_pham}_{language}_clean.txt",
        media_type="text/plain; charset=utf-8"
    )

@router.get("/raw-text")
def export_raw_text(
    project_id: str = Query(...),
    language: str = Query("han"), # 'han' or 'viet'
    db: Session = Depends(get_db)
):
    from ..models import Segment, Document
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    from ..services.documents import current_document, raw_snapshot
    data = raw_snapshot(current_document(db, project_id, language))
    if data is None:
        raise HTTPException(404, 'Thiếu snapshot gốc khớp hash; không dùng phân đoạn đã sửa thay bản thô')
    return Response(data, media_type='text/plain; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{language}_raw.txt"'})

@router.get("/xlsx")
def export_xlsx_endpoint(project_id: str = Query(...), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    pairs = get_confirmed_pairs(db, project_id)
    if not pairs:
        raise HTTPException(status_code=400, detail="Chưa có cặp dóng hàng nào được xác nhận (confirmed).")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    xlsx_path = Path(tmp.name)
    tmp.close()

    generate_xlsx(pairs, xlsx_path)
    return FileResponse(
        path=str(xlsx_path),
        filename=f"{project.ma_tac_pham}_parallel.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@router.get("/zip")
def export_delivery_zip_endpoint(project_id: str = Query(...), delivery: bool = False, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    if delivery:
        from ..services.quality import delivery_checklist
        checklist = delivery_checklist(db, project_id)
        if not checklist['ready']:
            raise HTTPException(400, 'Chưa sẵn sàng bàn giao: ' + '; '.join(c['label'] for c in checklist['conditions'] if not c['passed']))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    zip_path = Path(tmp.name)
    tmp.close()

    try:
        build_delivery_zip(db, project_id, zip_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi tạo gói giao nộp: {str(e)}")

    return FileResponse(
        path=str(zip_path),
        filename=f"{project.ma_de_tai}_{project.ma_tac_pham}_delivery.zip",
        media_type="application/zip"
    )

@router.post("/backup")
def trigger_backup(tag: str = "manual"):
    try:
        res = create_database_backup(tag=tag)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/restore")
def trigger_restore(filename: str):
    try:
        res = restore_database_backup(filename=filename)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/backups")
def get_backups():
    return list_backups()
