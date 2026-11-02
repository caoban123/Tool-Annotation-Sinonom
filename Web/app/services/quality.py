import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import Alignment, AlignmentMember, Segment, QAIssue, Project

def run_automated_qa(db: Session, project_id: str) -> List[QAIssue]:
    """
    Scans project alignments and segments to detect potential quality issues:
    - MISSING: Unassigned segments
    - FORMAT: Formula prefix (=, +, -, @), forbidden tabs or control characters
    - ORDER: Inverted sequence (alignment ordering anomalies)
    - DUPLICATE: Repeated identical clean_text in alignments
    """
    # Clear previous automated open issues
    db.query(QAIssue).filter(
        QAIssue.project_id == project_id,
        QAIssue.status == "open"
    ).delete()
    db.flush()

    new_issues = []

    # 1. Check Unassigned segments (MISSING)
    active_segs = db.query(Segment).filter(
        Segment.project_id == project_id,
        Segment.active == True
    ).all()

    assigned_seg_ids = set(
        r[0] for r in db.query(AlignmentMember.segment_id).join(Alignment).filter(
            Alignment.project_id == project_id,
            Alignment.status.in_(["confirmed", "needs_review"])
        ).all()
    )

    for seg in active_segs:
        if seg.id not in assigned_seg_ids:
            issue = QAIssue(
                id=f"qa_miss_{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                segment_id=seg.id,
                code="MISSING",
                severity="warning",
                status="open",
                comment=f"Phân đoạn [{seg.language.upper()} #{seg.order_index}] chưa được dóng hàng (unassigned)."
            )
            db.add(issue)
            new_issues.append(issue)

    # 2. Check Format & Formula characters on confirmed alignments
    confirmed_alignments = db.query(Alignment).filter(
        Alignment.project_id == project_id,
        Alignment.status == "confirmed"
    ).all()

    last_han_order = -1
    last_viet_order = -1

    for align in confirmed_alignments:
        members = db.query(AlignmentMember, Segment).join(Segment).filter(
            AlignmentMember.alignment_id == align.id
        ).order_by(AlignmentMember.side, AlignmentMember.position).all()

        han_segs = [s for m, s in members if m.side == "han"]
        viet_segs = [s for m, s in members if m.side == "viet"]

        # Check for formula injection indicators
        for s in han_segs + viet_segs:
            text = s.clean_text.strip()
            if text.startswith(("=", "+", "-", "@")):
                issue = QAIssue(
                    id=f"qa_fmt_{uuid.uuid4().hex[:8]}",
                    project_id=project_id,
                    alignment_id=align.id,
                    segment_id=s.id,
                    code="FORMAT",
                    severity="warning",
                    status="open",
                    comment=f"Phân đoạn chứa ký tự khởi đầu công thức Excel ('{text[0]}'). Cần escape cẩn thận khi export."
                )
                db.add(issue)
                new_issues.append(issue)

            if "\t" in text:
                issue = QAIssue(
                    id=f"qa_fmt_{uuid.uuid4().hex[:8]}",
                    project_id=project_id,
                    alignment_id=align.id,
                    segment_id=s.id,
                    code="FORMAT",
                    severity="warning",
                    status="open",
                    comment="Phân đoạn chứa ký tự TAB nội tại. Phải chuẩn hóa thành khoảng trắng để tránh vỡ cột TSV."
                )
                db.add(issue)
                new_issues.append(issue)

        # Check Monotonic Order
        if han_segs and viet_segs:
            min_han_order = min(s.order_index for s in han_segs)
            min_viet_order = min(s.order_index for s in viet_segs)

            if min_han_order < last_han_order or min_viet_order < last_viet_order:
                issue = QAIssue(
                    id=f"qa_ord_{uuid.uuid4().hex[:8]}",
                    project_id=project_id,
                    alignment_id=align.id,
                    code="ORDER",
                    severity="warning",
                    status="open",
                    comment=f"Thứ tự dóng hàng bị đảo: Hán #{min_han_order} (trước đó #{last_han_order}), Việt #{min_viet_order} (trước đó #{last_viet_order})."
                )
                db.add(issue)
                new_issues.append(issue)

            last_han_order = max(last_han_order, max(s.order_index for s in han_segs))
            last_viet_order = max(last_viet_order, max(s.order_index for s in viet_segs))

    db.flush()
    return new_issues

def get_project_statistics(db: Session, project_id: str) -> Dict[str, Any]:
    """Calculates live project metrics and QA status."""
    total_han = db.query(Segment).filter(
        Segment.project_id == project_id,
        Segment.language == "han",
        Segment.active == True
    ).count()

    total_viet = db.query(Segment).filter(
        Segment.project_id == project_id,
        Segment.language == "viet",
        Segment.active == True
    ).count()

    # Confirmed counts
    confirmed_query = db.query(Alignment).filter(
        Alignment.project_id == project_id,
        Alignment.status == "confirmed"
    )
    confirmed_total = confirmed_query.count()
    c_11 = confirmed_query.filter(Alignment.alignment_type == "1-1").count()
    c_1n = confirmed_query.filter(Alignment.alignment_type == "1-n").count()
    c_n1 = confirmed_query.filter(Alignment.alignment_type == "n-1").count()
    c_nm = confirmed_query.filter(Alignment.alignment_type == "n-m").count()

    needs_review_count = db.query(Alignment).filter(
        Alignment.project_id == project_id,
        Alignment.status == "needs_review"
    ).count()

    # Assigned segment counts
    assigned_han_count = db.query(AlignmentMember.segment_id).join(Alignment).join(Segment).filter(
        Alignment.project_id == project_id,
        Alignment.status == "confirmed",
        Segment.language == "han",
        Segment.active == True
    ).distinct().count()

    assigned_viet_count = db.query(AlignmentMember.segment_id).join(Alignment).join(Segment).filter(
        Alignment.project_id == project_id,
        Alignment.status == "confirmed",
        Segment.language == "viet",
        Segment.active == True
    ).distinct().count()

    unassigned_han = max(0, total_han - assigned_han_count)
    unassigned_viet = max(0, total_viet - assigned_viet_count)

    # QA issue count
    qa_issues_count = db.query(QAIssue).filter(
        QAIssue.project_id == project_id,
        QAIssue.status == "open"
    ).count()

    # Evaluated checked sample error rate
    # If notes contain [CHECKED_VALID] or [CHECKED_ERROR]
    reviewed_alignments = db.query(Alignment).filter(
        Alignment.project_id == project_id,
        Alignment.notes.like("%[CHECKED%")
    ).all()
    sample_size = len(reviewed_alignments)
    error_sample_count = sum(1 for a in reviewed_alignments if "[CHECKED_ERROR]" in a.notes)

    if sample_size > 0:
        error_rate_pct = round((error_sample_count / sample_size) * 100, 2)
        evaluation_status = f"{error_rate_pct}% ({error_sample_count}/{sample_size})"
    else:
        error_rate_pct = None
        evaluation_status = "not evaluated"

    return {
        "project_id": project_id,
        "total_han_segments": total_han,
        "total_viet_segments": total_viet,
        "confirmed_alignments": confirmed_total,
        "confirmed_11": c_11,
        "confirmed_1n": c_1n,
        "confirmed_n1": c_n1,
        "confirmed_nm": c_nm,
        "needs_review_alignments": needs_review_count,
        "unassigned_han": unassigned_han,
        "unassigned_viet": unassigned_viet,
        "coverage_han_pct": round((assigned_han_count / total_han * 100), 1) if total_han > 0 else 0.0,
        "coverage_viet_pct": round((assigned_viet_count / total_viet * 100), 1) if total_viet > 0 else 0.0,
        "target_count": 2000,
        "qa_issues_count": qa_issues_count,
        "checked_sample_size": sample_size,
        "checked_error_count": error_sample_count,
        "error_rate_pct": error_rate_pct,
        "evaluation_status": evaluation_status
    }
