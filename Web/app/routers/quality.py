from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import QAIssue, QualityReview, Alignment
from ..schemas import QAIssueOut, ReviewRequest
from ..services.quality import run_automated_qa, save_review, valid_reviews, delivery_checklist
import json

router = APIRouter(prefix="/api/qa", tags=["qa"])

@router.get("", response_model=List[QAIssueOut])
def list_qa_issues(project_id: str = Query(...), db: Session = Depends(get_db)):
    return db.query(QAIssue).filter(QAIssue.project_id == project_id).all()

@router.post("/scan", response_model=List[QAIssueOut])
def run_qa_scan(project_id: str = Query(...), db: Session = Depends(get_db)):
    try:
        issues = run_automated_qa(db, project_id)
        db.commit()
        return issues
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{issue_id}/resolve")
def resolve_issue(issue_id: str, db: Session = Depends(get_db)):
    issue = db.query(QAIssue).filter(QAIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Không tìm thấy vấn đề QA")
    issue.status = "resolved"
    import datetime
    issue.resolved_at = datetime.datetime.utcnow()
    db.commit()
    return {"status": "success", "issue_id": issue_id}


@router.post('/reviews/{alignment_id}')
def review_alignment(alignment_id: str, payload: ReviewRequest, db: Session = Depends(get_db)):
    try:
        review = save_review(db, alignment_id, **payload.model_dump())
        db.commit()
        return {'id': review.id, 'outcome': review.outcome}
    except ValueError as error:
        db.rollback()
        raise HTTPException(400, str(error))


@router.get('/reviews')
def list_reviews(project_id: str, db: Session = Depends(get_db)):
    valid = {r.id for r in valid_reviews(db, project_id)}
    return [dict(id=r.id, alignment_id=r.alignment_id, outcome=r.outcome, error_codes=json.loads(r.error_codes),
                 note=r.note, reviewer=r.reviewer, current=r.id in valid) for r in
            db.query(QualityReview).filter_by(project_id=project_id).all()]


@router.get('/checklist')
def checklist(project_id: str, db: Session = Depends(get_db)):
    return delivery_checklist(db, project_id)
