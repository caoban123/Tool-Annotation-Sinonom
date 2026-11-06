"""One compact workspace snapshot without raw text duplication or per-pair SQL."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Project, Segment, Alignment, AlignmentMember

router = APIRouter(prefix='/api/workspace', tags=['workspace'])


@router.get('/{project_id}')
def workspace_snapshot(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, 'Không tìm thấy dự án')
    segments = [row._asdict() for row in db.query(
        Segment.id, Segment.document_id, Segment.language, Segment.order_index,
        Segment.clean_text, Segment.page_ref, Segment.active, Segment.revision
    ).filter(Segment.project_id == project_id, Segment.active == True)
        .order_by(Segment.language, Segment.order_index).all()]
    pairs = {row.id: dict(id=row.id, status=row.status, han_segments=[], viet_segments=[])
             for row in db.query(Alignment.id, Alignment.status)
             .filter(Alignment.project_id == project_id).order_by(Alignment.created_at, Alignment.id).all()}
    membership = {}
    priority = {'confirmed': 4, 'needs_review': 3, 'suggested': 2, 'draft': 1}
    for row in db.query(AlignmentMember.alignment_id, AlignmentMember.segment_id, AlignmentMember.side).join(
            Alignment).filter(Alignment.project_id == project_id).order_by(
                Alignment.created_at, Alignment.id, AlignmentMember.side, AlignmentMember.position).all():
        pair = pairs[row.alignment_id]
        if row.side in ('han', 'viet'):
            pair[f'{row.side}_segments'].append({'id': row.segment_id})
        current = membership.get(row.segment_id)
        if priority.get(pair['status'], 0) > priority.get(current['status'] if current else '', 0):
            membership[row.segment_id] = pair
    for segment in segments:
        pair = membership.get(segment['id'])
        segment.update(alignment_id=pair['id'] if pair else None,
                       alignment_status=pair['status'] if pair else 'unassigned')
    return dict(revision=project.revision, segments=segments, alignments=list(pairs.values()))
