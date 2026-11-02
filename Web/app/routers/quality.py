from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import QAIssue
from ..schemas import QAIssueOut
from ..services.quality import run_automated_qa

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
    db.commit()
    return {"status": "success", "issue_id": issue_id}
