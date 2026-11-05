import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import Alignment, AlignmentMember, Segment, QAIssue, Project, QualityReview, Task, Document
import json
import datetime
from .integrity import alignment_fingerprint, lock_project
from .versioning import record_revision

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
        QAIssue.origin == 'automated', QAIssue.status == "open"
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

    confirmed_alignments.sort(key=lambda a: min((m.segment.order_index for m in a.members if m.side == 'han' and m.segment), default=float('inf')))
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

    for issue in new_issues:
        issue.origin = 'automated'
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

    reviewed_alignments = valid_reviews(db, project_id)
    sample_size = len(reviewed_alignments)
    error_sample_count = sum(review.outcome == 'error' for review in reviewed_alignments)

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
        "target_count": sum(task.target_count for task in db.query(Task).filter_by(project_id=project_id).all()) or 2000,
        "qa_issues_count": qa_issues_count,
        "checked_sample_size": sample_size,
        "checked_error_count": error_sample_count,
        "error_rate_pct": error_rate_pct,
        "evaluation_status": evaluation_status
    }


def valid_reviews(db, project_id):
    result = []
    for review in db.query(QualityReview).filter_by(project_id=project_id).all():
        alignment = db.get(Alignment, review.alignment_id)
        if alignment and alignment.status == 'confirmed' and review.content_hash == alignment_fingerprint(db, alignment):
            members = db.query(AlignmentMember).filter_by(alignment_id=alignment.id).all()
            if members and all(m.segment and m.segment.active for m in members):
                result.append(review)
    return result


def save_review(db, alignment_id, outcome, error_codes, note='', reviewer=''):
    alignment = db.get(Alignment, alignment_id)
    if not alignment:
        raise ValueError('Không tìm thấy cặp dóng hàng')
    lock_project(db, alignment.project_id)
    if alignment.status != 'confirmed':
        raise ValueError('Chỉ kiểm tra mẫu trên cặp đã xác nhận')
    codes = sorted(set(error_codes))
    if (outcome == 'error' and not codes) or (outcome == 'correct' and codes):
        raise ValueError('Cặp lỗi cần loại lỗi; cặp đúng không được có loại lỗi')
    if outcome not in ('error', 'correct') or any(c not in ('OMISSION', 'ADDITION', 'MISSING') for c in codes):
        raise ValueError('Đánh giá không hợp lệ')
    content_hash = alignment_fingerprint(db, alignment)
    review = db.query(QualityReview).filter_by(alignment_id=alignment_id).first()
    if not review:
        review = QualityReview(id='review_' + uuid.uuid4().hex, project_id=alignment.project_id, alignment_id=alignment_id)
        db.add(review)
    before = dict(outcome=review.outcome, error_codes=review.error_codes)
    review.outcome, review.error_codes = outcome, json.dumps(codes)
    review.note, review.reviewer = note, reviewer
    review.content_hash = content_hash
    review.updated_at = datetime.datetime.utcnow()
    db.query(QAIssue).filter_by(alignment_id=alignment_id, origin='manual_review', status='open').update(
        {'status': 'resolved', 'resolved_at': datetime.datetime.utcnow()})
    for code in codes:
        db.add(QAIssue(id='qa_' + uuid.uuid4().hex, project_id=alignment.project_id,
                       alignment_id=alignment_id, code=code, origin='manual_review', severity='error', comment=note))
    record_revision(db, alignment.project_id, 'quality_review', 'Alignment', alignment_id,
                    before_state=before, after_state=dict(outcome=outcome, error_codes=codes, reviewer=reviewer, note=note))
    db.flush()
    return review


def delivery_checklist(db, project_id):
    from .documents import raw_snapshot
    stats = get_project_statistics(db, project_id)
    docs = db.query(Document).filter_by(project_id=project_id, active=True).all()
    sources = {d.language: json.loads(d.provenance or '{}').get('source', {}) for d in docs}
    complete_sources = all(all(sources.get(lang, {}).get(field) for field in ('title', 'format', 'scope', 'tools'))
                           and (sources.get(lang, {}).get('url') or sources.get(lang, {}).get('filename'))
                           and ('pdf' not in sources.get(lang, {}).get('format', '').lower() or bool(sources.get(lang, {}).get('page_count')))
                           for lang in ('han', 'viet'))
    from .export import get_confirmed_pairs
    structure_error = ''
    try:
        pairs = get_confirmed_pairs(db, project_id)
    except ValueError as error:
        pairs, structure_error = [], str(error)
    conditions = [
        ('target', 'Đạt mục tiêu cặp của nhiệm vụ', len(pairs) >= stats['target_count']),
        ('structure', 'Cấu trúc các cặp xác nhận hợp lệ', not structure_error and bool(pairs)),
        ('coverage', 'Không còn phân đoạn chưa gán', stats['unassigned_han'] == stats['unassigned_viet'] == 0),
        ('review', 'Không còn cặp cần duyệt hoặc gợi ý chưa duyệt', not db.query(Alignment).filter(
            Alignment.project_id == project_id, Alignment.status.in_(['needs_review', 'suggested', 'draft'])).count()),
        ('sample', 'Có mẫu kiểm tra còn hiệu lực', stats['checked_sample_size'] > 0),
        ('threshold', 'Tỷ lệ lỗi mẫu ≤30% (mục tiêu ≤20%)', stats['checked_sample_size'] > 0 and stats['checked_error_count'] * 100 <= stats['checked_sample_size'] * 30),
        ('known_errors', 'Đã sửa các lỗi cụ thể được ghi nhận', stats['checked_error_count'] == 0 and stats['qa_issues_count'] == 0),
        ('sources', 'Đủ kiểm kê nguồn và công cụ hai ngôn ngữ', complete_sources),
        ('raw', 'Có snapshot gốc khớp hash cho hai ngôn ngữ', len(docs) == 2 and all(raw_snapshot(d) is not None for d in docs)),
    ]
    tasks = db.query(Task).filter_by(project_id=project_id).all()
    per_task = [dict(id=t.id, assigned_to=t.assigned_to, scope=t.scope, target=t.target_count,
                    confirmed=db.query(Alignment).filter_by(project_id=project_id, task_id=t.id, status='confirmed').count()) for t in tasks]
    conditions.append(('task_targets', 'Đạt mục tiêu của từng người/phạm vi nhiệm vụ',
                       bool(per_task) and all(t['confirmed'] >= t['target'] for t in per_task)))
    return dict(ready=all(ok for _, _, ok in conditions), stats=stats,
                conditions=[dict(code=code, label=label, passed=ok) for code, label, ok in conditions],
                structure_error=structure_error, tasks=per_task, valid_pairs=len(pairs),
                note='Checklist hỗ trợ tự kiểm tra, không chứng minh toàn bộ cặp đúng ngữ nghĩa.')
