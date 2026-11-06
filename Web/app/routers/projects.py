import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import delete
from ..db import get_db
from ..models import Project, Task, Document, Segment, Alignment
from ..schemas import ProjectCreate, ProjectOut, ProjectDeleteRequest, StatsOut, SourceUpdate, TaskRequest
from ..services.integrity import lock_project
import json
from ..services.documents import current_document, attach_page_metadata
from ..services.versioning import record_revision
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
        target_count=payload.target_count
    )
    db.add(task)
    db.commit()
    db.refresh(project)
    return project


@router.delete('/{project_id}')
def delete_project(project_id: str, payload: ProjectDeleteRequest, db: Session = Depends(get_db)):
    lock_project(db, project_id)
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, 'Không tìm thấy dự án')
    if payload.confirmation_name != project.name:
        raise HTTPException(400, 'Tên dự án xác nhận không khớp')
    if payload.revision != project.revision:
        raise HTTPException(409, 'Dự án đã thay đổi. Tải lại trang và kiểm tra trước khi xóa.')
    # All project-owned tables have ON DELETE CASCADE, including raw snapshots,
    # archived documents, memberships, QA reviews and revision history. A single
    # statement keeps the deletion atomic and avoids loading large texts in ORM.
    db.execute(delete(Project).where(Project.id == project_id),
               execution_options={'synchronize_session': False})
    db.commit()
    return {'status': 'deleted', 'project_id': project_id}

@router.post("/{project_id}/import")
async def import_project_files(
    project_id: str,
    han_file: UploadFile = File(...),
    viet_file: UploadFile = File(...),
    han_metadata: Optional[UploadFile] = File(None),
    viet_metadata: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    han_bytes = await han_file.read()
    viet_bytes = await viet_file.read()
    try:
        han_bytes.decode('utf-8-sig')
        viet_bytes.decode('utf-8-sig')
    except UnicodeError:
        raise HTTPException(400, 'Tệp TXT phải có mã hóa UTF-8; chưa thay đổi dữ liệu dự án')

    # Process and segment Han document
    han_doc = process_txt_bytes(db, project_id, "han", han_bytes, han_file.filename or "han.txt")
    han_text = han_bytes.decode("utf-8-sig", errors="replace")
    han_segs = segment_document(db, han_doc, han_text)

    # Process and segment Viet document
    viet_doc = process_txt_bytes(db, project_id, "viet", viet_bytes, viet_file.filename or "viet.txt")
    viet_text = viet_bytes.decode("utf-8-sig", errors="replace")
    viet_segs = segment_document(db, viet_doc, viet_text)

    try:
        if han_metadata:
            attach_page_metadata(db, han_doc, json.loads(await han_metadata.read()))
        if viet_metadata:
            attach_page_metadata(db, viet_doc, json.loads(await viet_metadata.read()))
        db.commit()
    except (ValueError, UnicodeError) as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(error))

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


@router.get('/{project_id}/tasks')
def get_tasks(project_id: str, db: Session = Depends(get_db)):
    return [dict(id=t.id, assigned_to=t.assigned_to, scope=t.scope, target_count=t.target_count) for t in
            db.query(Task).filter_by(project_id=project_id).all()]


@router.post('/{project_id}/tasks')
def add_task(project_id: str, payload: TaskRequest, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(404, 'Không tìm thấy dự án')
    task = Task(id='task_' + uuid.uuid4().hex[:12], project_id=project_id, assigned_to=payload.assigned_to,
                scope=payload.scope, target_count=payload.target_count)
    db.add(task)
    record_revision(db, project_id, 'add_task', 'Task', task.id)
    db.commit()
    return {'id': task.id}


@router.put('/{project_id}/tasks/{task_id}')
def update_task(project_id: str, task_id: str, payload: TaskRequest, db: Session = Depends(get_db)):
    task = db.query(Task).filter_by(id=task_id, project_id=project_id).first()
    if not task:
        raise HTTPException(404, 'Không tìm thấy nhiệm vụ')
    task.assigned_to, task.scope, task.target_count = payload.assigned_to, payload.scope, payload.target_count
    record_revision(db, project_id, 'update_task', 'Task', task.id, after_state=payload.model_dump())
    db.commit()
    return {'status': 'success'}


@router.get('/{project_id}/sources')
def get_sources(project_id: str, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(404, 'Không tìm thấy dự án')
    return {language: dict(json.loads(doc.provenance or '{}'), document_id=doc.id,
                filename=doc.raw_filename, raw_sha256=doc.raw_sha256) if
                (doc := current_document(db, project_id, language)) else {} for language in ('han', 'viet')}


@router.put('/{project_id}/sources/{language}')
def update_source(project_id: str, language: str, payload: SourceUpdate, db: Session = Depends(get_db)):
    doc = current_document(db, project_id, language)
    if not doc:
        raise HTTPException(404, 'Chưa nhập tài liệu cho ngôn ngữ này')
    if payload.url and not payload.url.startswith(('https://', 'http://')):
        raise HTTPException(400, 'URL nguồn phải dùng http hoặc https')
    provenance = json.loads(doc.provenance or '{}')
    provenance['source'] = payload.model_dump()
    doc.provenance = json.dumps(provenance, ensure_ascii=False)
    record_revision(db, project_id, 'update_source', 'Document', doc.id, after_state=payload.model_dump())
    db.commit()
    return payload.model_dump()


@router.post('/{project_id}/metadata/{language}')
async def import_metadata(project_id: str, language: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    doc = current_document(db, project_id, language)
    if not doc:
        raise HTTPException(404, 'Không tìm thấy tài liệu')
    try:
        attach_page_metadata(db, doc, json.loads(await file.read()))
        record_revision(db, project_id, 'attach_page_metadata', 'Document', doc.id)
        db.commit()
    except (ValueError, UnicodeError) as error:
        db.rollback()
        raise HTTPException(400, str(error))
    return {'status': 'success'}


@router.post('/{project_id}/sources/{language}/file')
async def attach_source_file(project_id: str, language: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    import hashlib
    doc = current_document(db, project_id, language)
    if not doc:
        raise HTTPException(404, 'Không tìm thấy tài liệu')
    doc.source_bytes = await file.read()
    doc.source_sha256 = hashlib.sha256(doc.source_bytes).hexdigest()
    provenance = json.loads(doc.provenance or '{}')
    provenance['source_upload_name'] = (file.filename or 'source').replace('\\', '/').split('/')[-1]
    provenance.setdefault('source', {})['filename'] = provenance['source_upload_name']
    doc.provenance = json.dumps(provenance, ensure_ascii=False)
    record_revision(db, project_id, 'attach_source_file', 'Document', doc.id,
                    after_state={'sha256': doc.source_sha256})
    db.commit()
    return {'status': 'success', 'sha256': doc.source_sha256}
