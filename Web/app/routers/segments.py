from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Segment, Alignment, AlignmentMember
from ..schemas import SegmentOut, SegmentUpdate, SegmentSplitRequest, SegmentMergeRequest
from ..services.segmentation import edit_segment, split_segment, merge_segments, delete_segment

router = APIRouter(prefix="/api/segments", tags=["segments"])

@router.get("", response_model=List[SegmentOut])
def list_segments(
    project_id: str = Query(...),
    language: Optional[str] = Query(None),
    status: Optional[str] = Query(None), # unassigned, confirmed, needs_review
    db: Session = Depends(get_db)
):
    query = db.query(Segment).filter(
        Segment.project_id == project_id,
        Segment.active == True
    )
    if language:
        query = query.filter(Segment.language == language)

    segments = query.order_by(Segment.language, Segment.order_index).all()

    # Determine alignment status for each segment
    seg_ids = [s.id for s in segments]
    members = db.query(AlignmentMember, Alignment).join(Alignment).filter(
        AlignmentMember.segment_id.in_(seg_ids)
    ).all()

    align_map = {}
    priority = {'confirmed': 4, 'needs_review': 3, 'suggested': 2, 'draft': 1}
    for m, a in members:
        if a.status in priority and priority[a.status] > priority.get(align_map.get(m.segment_id, (None, ''))[1], 0):
            align_map[m.segment_id] = (a.id, a.status)

    results = []
    for s in segments:
        a_id, a_status = align_map.get(s.id, (None, "unassigned"))
        if status and status != a_status:
            continue
        seg_out = SegmentOut(
            id=s.id,
            document_id=s.document_id,
            language=s.language,
            order_index=s.order_index,
            raw_text=s.raw_text,
            clean_text=s.clean_text,
            page_ref=s.page_ref,
            active=s.active,
            revision=s.revision,
            alignment_id=a_id,
            alignment_status=a_status
        )
        results.append(seg_out)

    return results

@router.put("/{segment_id}", response_model=SegmentOut)
def update_segment_text(
    segment_id: str,
    payload: SegmentUpdate,
    project_id: str = Query(...),
    db: Session = Depends(get_db)
):
    try:
        updated = edit_segment(db, project_id, segment_id, payload.clean_text)
        db.commit()
        return SegmentOut(
            id=updated.id,
            document_id=updated.document_id,
            language=updated.language,
            order_index=updated.order_index,
            raw_text=updated.raw_text,
            clean_text=updated.clean_text,
            page_ref=updated.page_ref,
            active=updated.active,
            revision=updated.revision
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/split", response_model=List[SegmentOut])
def split_segment_endpoint(
    payload: SegmentSplitRequest,
    project_id: str = Query(...),
    db: Session = Depends(get_db)
):
    try:
        children = split_segment(db, project_id, payload.segment_id, payload.split_texts)
        db.commit()
        return [
            SegmentOut(
                id=c.id,
                document_id=c.document_id,
                language=c.language,
                order_index=c.order_index,
                raw_text=c.raw_text,
                clean_text=c.clean_text,
                page_ref=c.page_ref,
                active=c.active,
                revision=c.revision
            ) for c in children
        ]
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/merge", response_model=SegmentOut)
def merge_segments_endpoint(
    payload: SegmentMergeRequest,
    project_id: str = Query(...),
    db: Session = Depends(get_db)
):
    try:
        merged = merge_segments(db, project_id, payload.segment_ids)
        db.commit()
        return SegmentOut(
            id=merged.id,
            document_id=merged.document_id,
            language=merged.language,
            order_index=merged.order_index,
            raw_text=merged.raw_text,
            clean_text=merged.clean_text,
            page_ref=merged.page_ref,
            active=merged.active,
            revision=merged.revision
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{segment_id}")
def delete_segment_endpoint(
    segment_id: str,
    project_id: str = Query(...),
    db: Session = Depends(get_db)
):
    try:
        deleted = delete_segment(db, project_id, segment_id)
        db.commit()
        return {"status": "success", "deleted_id": deleted.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

