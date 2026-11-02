from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Alignment, AlignmentMember, Segment
from ..schemas import AlignmentCreateRequest, AlignmentOut, AlignmentUndoRequest, SegmentOut
from ..services.alignment import create_alignment, undo_last_alignment

router = APIRouter(prefix="/api/alignments", tags=["alignments"])

def _format_alignment_out(db: Session, align: Alignment) -> AlignmentOut:
    members = db.query(AlignmentMember, Segment).join(Segment).filter(
        AlignmentMember.alignment_id == align.id
    ).order_by(AlignmentMember.side, AlignmentMember.position).all()

    han_outs = [
        SegmentOut(
            id=s.id,
            document_id=s.document_id,
            language=s.language,
            order_index=s.order_index,
            raw_text=s.raw_text,
            clean_text=s.clean_text,
            page_ref=s.page_ref,
            active=s.active,
            revision=s.revision,
            alignment_id=align.id,
            alignment_status=align.status
        ) for m, s in members if m.side == "han"
    ]

    viet_outs = [
        SegmentOut(
            id=s.id,
            document_id=s.document_id,
            language=s.language,
            order_index=s.order_index,
            raw_text=s.raw_text,
            clean_text=s.clean_text,
            page_ref=s.page_ref,
            active=s.active,
            revision=s.revision,
            alignment_id=align.id,
            alignment_status=align.status
        ) for m, s in members if m.side == "viet"
    ]

    return AlignmentOut(
        id=align.id,
        project_id=align.project_id,
        task_id=align.task_id,
        alignment_type=align.alignment_type,
        status=align.status,
        notes=align.notes,
        created_at=align.created_at,
        updated_at=align.updated_at,
        revision=align.revision,
        han_segments=han_outs,
        viet_segments=viet_outs
    )

@router.get("", response_model=List[AlignmentOut])
def list_alignments(
    project_id: str = Query(...),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Alignment).filter(Alignment.project_id == project_id)
    if status:
        query = query.filter(Alignment.status == status)
    alignments = query.order_by(Alignment.created_at.asc()).all()
    return [_format_alignment_out(db, a) for a in alignments]

@router.post("", response_model=AlignmentOut)
def create_new_alignment(payload: AlignmentCreateRequest, db: Session = Depends(get_db)):
    try:
        align = create_alignment(
            db,
            project_id=payload.project_id,
            han_segment_ids=payload.han_segment_ids,
            viet_segment_ids=payload.viet_segment_ids,
            task_id=payload.task_id,
            notes=payload.notes,
            status=payload.status or "confirmed"
        )
        db.commit()
        return _format_alignment_out(db, align)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/undo")
def undo_alignment_endpoint(payload: AlignmentUndoRequest, db: Session = Depends(get_db)):
    try:
        undone = undo_last_alignment(db, payload.project_id, payload.alignment_id)
        db.commit()
        return {"status": "success", "undone_alignment_id": undone.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{alignment_id}")
def delete_alignment(alignment_id: str, db: Session = Depends(get_db)):
    align = db.query(Alignment).filter(Alignment.id == alignment_id).first()
    if not align:
        raise HTTPException(status_code=404, detail="Không tìm thấy cặp dóng hàng")
    project_id = align.project_id
    undo_last_alignment(db, project_id, alignment_id)
    db.commit()
    return {"status": "success", "deleted_id": alignment_id}
