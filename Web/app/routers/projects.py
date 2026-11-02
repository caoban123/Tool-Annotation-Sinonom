import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Project, Task, Document, Segment, Alignment
from ..schemas import ProjectCreate, ProjectOut, StatsOut
from ..services.import_txt import process_txt_bytes
from ..services.segmentation import segment_document
from ..services.quality import get_project_statistics

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()

@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    proj_id = f"proj_{uuid.uuid4().hex[:8]}"
    project = Project(
        id=proj_id,
        ma_de_tai=payload.ma_de_tai,
        ma_tac_pham=payload.ma_tac_pham,
        name=payload.name,
        scope=payload.scope
    )
    db.add(project)

    task = Task(
        id=f"task_{uuid.uuid4().hex[:8]}",
        project_id=proj_id,
        assigned_to=payload.assigned_to,
        scope=payload.scope,
        target_count=2000
    )
    db.add(task)
    db.commit()
    db.refresh(project)
    return project

@router.post("/{project_id}/import")
async def import_project_files(
    project_id: str,
    han_file: UploadFile = File(...),
    viet_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    han_bytes = await han_file.read()
    viet_bytes = await viet_file.read()

    # Process and segment Han document
    han_doc = process_txt_bytes(db, project_id, "han", han_bytes, han_file.filename or "han.txt")
    han_text = han_bytes.decode("utf-8", errors="replace")
    han_segs = segment_document(db, han_doc, han_text)

    # Process and segment Viet document
    viet_doc = process_txt_bytes(db, project_id, "viet", viet_bytes, viet_file.filename or "viet.txt")
    viet_text = viet_bytes.decode("utf-8", errors="replace")
    viet_segs = segment_document(db, viet_doc, viet_text)

    db.commit()

    return {
        "status": "success",
        "han_segments_count": len(han_segs),
        "viet_segments_count": len(viet_segs),
        "han_doc_id": han_doc.id,
        "viet_doc_id": viet_doc.id
    }

@router.get("/{project_id}/stats", response_model=StatsOut)
def get_stats(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    stats = get_project_statistics(db, project_id)
    return stats
