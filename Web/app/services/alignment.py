import uuid
import datetime
from typing import List, Tuple
from sqlalchemy.orm import Session
from ..models import Alignment, AlignmentMember, Segment, Project, Task
from .versioning import record_revision
from .integrity import lock_project, source_context
import json

def infer_alignment_type(num_han: int, num_viet: int) -> str:
    """Infer alignment type from segment cardinality."""
    if num_han < 1 or num_viet < 1:
        raise ValueError("Một cặp dóng hàng phải chứa ít nhất 1 phân đoạn Hán và 1 phân đoạn Việt.")
    if num_han == 1 and num_viet == 1:
        return "1-1"
    elif num_han == 1 and num_viet >= 2:
        return "1-n"
    elif num_han >= 2 and num_viet == 1:
        return "n-1"
    else:
        return "n-m"

def validate_contiguous_segments(segments: List[Segment]) -> None:
    """Validate that the list of segments is sorted and contiguous by order_index without gaps."""
    if len(segments) <= 1:
        return
    # Sort by order_index
    segments.sort(key=lambda s: s.order_index)
    for i in range(len(segments) - 1):
        if segments[i+1].order_index != segments[i].order_index + 1:
            raise ValueError(
                f"Các phân đoạn trong một vế phải liền kề theo thứ tự. Phát hiện khoảng cách giữa #{segments[i].order_index} và #{segments[i+1].order_index}."
            )

def create_alignment(
    db: Session,
    project_id: str,
    han_segment_ids: List[str],
    viet_segment_ids: List[str],
    task_id: str = None,
    notes: str = "",
    status: str = "confirmed"
) -> Alignment:
    """
    Creates an alignment between Han and Viet segments.
    Enforces all core business invariants:
    1. At least 1 Han and 1 Viet segment (no empty sides).
    2. Segments on each side must be strictly adjacent and contiguous.
    3. Segments must be active and belong to project.
    4. NO segment can already belong to an active 'confirmed' alignment.
    5. Alignment type is strictly inferred from cardinality (1-1, 1-n, n-1, n-m).
    """
    if not han_segment_ids or not viet_segment_ids:
        raise ValueError("Không thể tạo cặp dóng hàng khi một vế rỗng (MISSING).")
    lock_project(db, project_id)
    if status not in ('confirmed', 'suggested', 'draft', 'needs_review', 'rejected'):
        raise ValueError('Trạng thái dóng hàng không hợp lệ')
    if task_id and not db.query(Task).filter_by(id=task_id, project_id=project_id).first():
        raise ValueError('Nhiệm vụ không thuộc dự án')

    # Fetch Han segments
    han_segs = db.query(Segment).filter(
        Segment.id.in_(han_segment_ids),
        Segment.project_id == project_id,
        Segment.language == "han",
        Segment.active == True
    ).all()
    if len(han_segs) != len(han_segment_ids):
        raise ValueError("Một số phân đoạn Hán không hợp lệ hoặc đã bị vô hiệu hóa.")

    # Fetch Viet segments
    viet_segs = db.query(Segment).filter(
        Segment.id.in_(viet_segment_ids),
        Segment.project_id == project_id,
        Segment.language == "viet",
        Segment.active == True
    ).all()
    if len(viet_segs) != len(viet_segment_ids):
        raise ValueError("Một số phân đoạn Việt không hợp lệ hoặc đã bị vô hiệu hóa.")

    # Validate contiguity
    if not any(s.clean_text.strip() for s in han_segs) or not any(s.clean_text.strip() for s in viet_segs):
        raise ValueError('Không được xác nhận cặp có một vế không còn nội dung')
    validate_contiguous_segments(han_segs)
    validate_contiguous_segments(viet_segs)

    # Duplicate check: check if any segment is already in a confirmed alignment
    all_seg_ids = [s.id for s in han_segs] + [s.id for s in viet_segs]
    conflict = db.query(AlignmentMember).join(Alignment).filter(
        AlignmentMember.segment_id.in_(all_seg_ids),
        Alignment.project_id == project_id,
        Alignment.status == "confirmed"
    ).first()
    if conflict:
        conflicting_seg = db.query(Segment).filter(Segment.id == conflict.segment_id).first()
        raise ValueError(
            f"Phân đoạn '{conflicting_seg.clean_text if conflicting_seg else conflict.segment_id}' "
            f"đã thuộc cặp dóng hàng xác nhận #{conflict.alignment_id} khác. Không được gán trùng!"
        )

    alignment_type = infer_alignment_type(len(han_segs), len(viet_segs))
    if task_id is None:
        task = db.query(Task).filter_by(project_id=project_id).first()
        task_id = task.id if task else None
    align_id = f"align_{uuid.uuid4().hex[:10]}"

    alignment = Alignment(
        id=align_id,
        project_id=project_id,
        task_id=task_id,
        alignment_type=alignment_type,
        status=status,
        notes=notes or "",
        revision=1
    )
    db.add(alignment)
    db.flush()

    # Add members in sorted order
    for pos, s in enumerate(han_segs):
        m = AlignmentMember(
            alignment_id=align_id,
            segment_id=s.id,
            side="han",
            position=pos
        )
        db.add(m)

    for pos, s in enumerate(viet_segs):
        m = AlignmentMember(
            alignment_id=align_id,
            segment_id=s.id,
            side="viet",
            position=pos
        )
        db.add(m)

    record_revision(
        db,
        project_id=project_id,
        action="confirm_alignment",
        entity_type="Alignment",
        entity_id=align_id,
        after_state={
            "alignment_type": alignment_type,
            "han_ids": [s.id for s in han_segs],
            "viet_ids": [s.id for s in viet_segs],
            "status": status
        }
    )
    db.flush()
    return alignment


def confirm_alignment(db, alignment):
    lock_project(db, alignment.project_id)
    if alignment.status not in ('suggested', 'needs_review', 'draft'):
        raise ValueError('Chỉ duyệt gợi ý/bản nháp hoặc cặp cần duyệt lại')
    if alignment.status == 'suggested':
        context = json.loads(alignment.suggestion_context or '{}')
        if context.get('snapshot') != source_context(db, alignment.project_id)['snapshot']:
            raise ValueError('Gợi ý cũ hoặc thiếu ngữ cảnh nguồn; hãy xuất và tạo gợi ý mới')
    members = db.query(AlignmentMember).filter_by(alignment_id=alignment.id).all()
    sides = {}
    for side in ('han', 'viet'):
        group = [m.segment for m in members if m.side == side]
        if not group or any(not s or not s.active or s.project_id != alignment.project_id or s.language != side for s in group):
            raise ValueError('Phân đoạn không còn active hoặc sai dự án/ngôn ngữ')
        if len({s.id for s in group}) != len(group):
            raise ValueError('Phân đoạn trùng trong cặp')
        if not any(s.clean_text.strip() for s in group):
            raise ValueError('Một vế của cặp không còn nội dung')
        validate_contiguous_segments(group)
        sides[side] = group
    if any(m.side not in sides for m in members):
        raise ValueError('Vế dóng hàng không hợp lệ')
    ids = [m.segment_id for m in members]
    conflict = db.query(AlignmentMember).join(Alignment).filter(
        AlignmentMember.segment_id.in_(ids), Alignment.status == 'confirmed', Alignment.id != alignment.id).first()
    if conflict:
        raise ValueError('Phân đoạn đã thuộc cặp xác nhận khác; không được duyệt trùng')
    alignment.alignment_type = infer_alignment_type(len(sides['han']), len(sides['viet']))
    before = alignment.status
    alignment.status = 'confirmed'
    alignment.revision += 1
    record_revision(db, alignment.project_id, 'accept_alignment', 'Alignment', alignment.id,
                    before_state={'status': before}, after_state={'status': 'confirmed'})
    db.flush()
    return alignment

def undo_last_alignment(db: Session, project_id: str, alignment_id: str = None) -> Alignment:
    """
    Undoes / deletes the specified alignment (or the most recently created alignment).
    """
    query = db.query(Alignment).filter(Alignment.project_id == project_id)
    if alignment_id:
        target = query.filter(Alignment.id == alignment_id).first()
    else:
        target = query.order_by(Alignment.created_at.desc()).first()

    if not target:
        raise ValueError("Không có cặp dóng hàng nào để hoàn tác.")

    # Record audit trail before deletion
    members = db.query(AlignmentMember).filter(AlignmentMember.alignment_id == target.id).all()
    record_revision(
        db,
        project_id=project_id,
        action="undo_alignment",
        entity_type="Alignment",
        entity_id=target.id,
        before_state={
            "alignment_id": target.id,
            "type": target.alignment_type,
            "members": [m.segment_id for m in members]
        }
    )

    db.delete(target)
    db.flush()
    return target
