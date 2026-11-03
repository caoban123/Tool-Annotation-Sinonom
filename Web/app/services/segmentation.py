import re
import uuid
import json
from typing import List
from sqlalchemy.orm import Session
from ..models import Segment, Document, Alignment, AlignmentMember, QAIssue
from .versioning import record_revision

def split_sentences_han(text: str) -> List[str]:
    """
    Split Classical/Literary Chinese text into sentence segments.
    Preserves punctuation marks (。！？；) attached to sentences.
    Preserves lines and ignores pure whitespace.
    """
    lines = text.split('\n')
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Split by CJK sentence-ending punctuation: 。！？；
        # Use regex lookbehind or capture group to keep delimiters
        pattern = r'([^。！？；\n]+[。！？；]?)'
        parts = re.findall(pattern, line)
        for p in parts:
            p_str = p.strip()
            if p_str:
                results.append(p_str)
    return results

def split_sentences_viet(text: str) -> List[str]:
    """
    Split Vietnamese text into sentence segments.
    Preserves punctuation (.!?;\n) and ignores empty whitespace.
    """
    lines = text.split('\n')
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Split by Vietnamese sentence endings while preserving punctuation
        pattern = r'([^.!?;\n]+[.!?;]?)'
        parts = re.findall(pattern, line)
        for p in parts:
            p_str = p.strip()
            if p_str:
                results.append(p_str)
    return results

def segment_document(
    db: Session,
    document: Document,
    text: str
) -> List[Segment]:
    """
    Segment the document's text into initial Segment records.
    """
    if document.language == 'han':
        sentence_list = split_sentences_han(text)
    else:
        sentence_list = split_sentences_viet(text)

    # Remove existing active segments for this document
    db.query(Segment).filter(Segment.document_id == document.id).delete()
    db.flush()

    segments = []
    for idx, s_text in enumerate(sentence_list):
        seg_id = f"seg_{document.language}_{idx+1:04d}_{uuid.uuid4().hex[:4]}"
        seg = Segment(
            id=seg_id,
            document_id=document.id,
            project_id=document.project_id,
            language=document.language,
            order_index=idx,
            raw_text=s_text,
            clean_text=s_text,
            page_ref="1",
            active=True,
            revision=1
        )
        db.add(seg)
        segments.append(seg)

    db.flush()
    record_revision(
        db,
        project_id=document.project_id,
        action="segment_document",
        entity_type="Document",
        entity_id=document.id,
        after_state={"segment_count": len(segments), "language": document.language}
    )
    return segments

def _invalidate_affected_alignments(db: Session, segment_id: str, reason: str):
    """Marks any confirmed alignment containing segment_id as needs_review."""
    memberships = db.query(AlignmentMember).filter(AlignmentMember.segment_id == segment_id).all()
    for m in memberships:
        alignment = db.query(Alignment).filter(Alignment.id == m.alignment_id).first()
        if alignment and alignment.status == "confirmed":
            alignment.status = "needs_review"
            alignment.notes = f"{alignment.notes} | Cần duyệt lại do: {reason}".strip(" | ")
            # Add QA warning
            qa = QAIssue(
                id=f"qa_{uuid.uuid4().hex[:8]}",
                project_id=alignment.project_id,
                alignment_id=alignment.id,
                segment_id=segment_id,
                code="FORMAT",
                severity="warning",
                status="open",
                comment=f"Phân đoạn bị thay đổi: {reason}"
            )
            db.add(qa)
    db.flush()

def edit_segment(
    db: Session,
    project_id: str,
    segment_id: str,
    new_clean_text: str
) -> Segment:
    """Edit clean_text of a segment and flag any affected confirmed alignments."""
    seg = db.query(Segment).filter(
        Segment.id == segment_id,
        Segment.project_id == project_id,
        Segment.active == True
    ).first()
    if not seg:
        raise ValueError(f"Không tìm thấy phân đoạn {segment_id}")

    old_text = seg.clean_text
    seg.clean_text = new_clean_text
    seg.revision += 1

    _invalidate_affected_alignments(db, segment_id, f"Sửa nội dung phân đoạn '{old_text}' -> '{new_clean_text}'")

    record_revision(
        db,
        project_id=project_id,
        action="edit_segment",
        entity_type="Segment",
        entity_id=segment_id,
        before_state={"text": old_text},
        after_state={"text": new_clean_text}
    )
    db.flush()
    return seg

def split_segment(
    db: Session,
    project_id: str,
    segment_id: str,
    split_texts: List[str]
) -> List[Segment]:
    """
    Split an existing active segment into 2 or more child segments.
    Deactivates the parent and updates affected alignments to needs_review.
    """
    seg = db.query(Segment).filter(
        Segment.id == segment_id,
        Segment.project_id == project_id,
        Segment.active == True
    ).first()
    if not seg:
        raise ValueError(f"Không tìm thấy phân đoạn {segment_id}")

    valid_splits = [t.strip() for t in split_texts if t.strip()]
    if len(valid_splits) < 2:
        raise ValueError("Yêu cầu ít nhất 2 phần để tách đoạn.")

    _invalidate_affected_alignments(db, segment_id, "Phân đoạn gốc đã được tách thành nhiều đoạn nhỏ")

    seg.active = False
    seg.revision += 1

    # Shift order_index of subsequent active segments
    subsequent = db.query(Segment).filter(
        Segment.project_id == project_id,
        Segment.language == seg.language,
        Segment.active == True,
        Segment.order_index > seg.order_index
    ).all()
    for s in subsequent:
        s.order_index += (len(valid_splits) - 1)

    new_segments = []
    for i, part in enumerate(valid_splits):
        child_id = f"{seg.id}_s{i+1}_{uuid.uuid4().hex[:4]}"
        child = Segment(
            id=child_id,
            document_id=seg.document_id,
            project_id=project_id,
            language=seg.language,
            order_index=seg.order_index + i,
            raw_text=part,
            clean_text=part,
            page_ref=seg.page_ref,
            parent_ids=json.dumps([seg.id]),
            active=True,
            revision=1
        )
        db.add(child)
        new_segments.append(child)

    seg.replaced_ids = json.dumps([c.id for c in new_segments])
    record_revision(
        db,
        project_id=project_id,
        action="split_segment",
        entity_type="Segment",
        entity_id=segment_id,
        before_state={"text": seg.clean_text},
        after_state={"child_ids": [c.id for c in new_segments]}
    )
    db.flush()
    return new_segments

def merge_segments(
    db: Session,
    project_id: str,
    segment_ids: List[str]
) -> Segment:
    """
    Merge multiple contiguous active segments into a single segment.
    Deactivates original segments and updates affected alignments to needs_review.
    """
    if len(segment_ids) < 2:
        raise ValueError("Cần ít nhất 2 phân đoạn để gộp.")

    segs = db.query(Segment).filter(
        Segment.id.in_(segment_ids),
        Segment.project_id == project_id,
        Segment.active == True
    ).order_index_ascending() if hasattr(Segment, 'order_index_ascending') else \
    db.query(Segment).filter(
        Segment.id.in_(segment_ids),
        Segment.project_id == project_id,
        Segment.active == True
    ).order_by(Segment.order_index).all()

    if len(segs) != len(segment_ids):
        raise ValueError("Một số phân đoạn không tồn tại hoặc đã bị vô hiệu hóa.")

    # Check contiguous order
    lang = segs[0].language
    for i in range(len(segs) - 1):
        if segs[i].language != lang or segs[i+1].language != lang:
            raise ValueError("Không thể gộp các phân đoạn khác ngôn ngữ.")
        if segs[i+1].order_index != segs[i].order_index + 1:
            raise ValueError("Chỉ có thể gộp các phân đoạn liền kề theo thứ tự.")

    for s in segs:
        _invalidate_affected_alignments(db, s.id, "Phân đoạn được gộp vào phân đoạn mới")
        s.active = False
        s.revision += 1

    joiner = " " if lang == "viet" else ""
    merged_clean = joiner.join(s.clean_text for s in segs)
    merged_raw = joiner.join(s.raw_text for s in segs)

    merged_id = f"seg_{lang}_m_{uuid.uuid4().hex[:8]}"
    merged_seg = Segment(
        id=merged_id,
        document_id=segs[0].document_id,
        project_id=project_id,
        language=lang,
        order_index=segs[0].order_index,
        raw_text=merged_raw,
        clean_text=merged_clean,
        page_ref=segs[0].page_ref,
        parent_ids=json.dumps([s.id for s in segs]),
        active=True,
        revision=1
    )
    db.add(merged_seg)

    # Shift subsequent order_index
    subsequent = db.query(Segment).filter(
        Segment.project_id == project_id,
        Segment.language == lang,
        Segment.active == True,
        Segment.order_index > segs[-1].order_index
    ).all()
    shift = len(segs) - 1
    for s in subsequent:
        s.order_index -= shift

    for s in segs:
        s.replaced_ids = json.dumps([merged_id])

    record_revision(
        db,
        project_id=project_id,
        action="merge_segments",
        entity_type="Segment",
        entity_id=merged_id,
        before_state={"parent_ids": [s.id for s in segs]},
        after_state={"merged_text": merged_clean}
    )
    db.flush()
    return merged_seg

def delete_segment(
    db: Session,
    project_id: str,
    segment_id: str
) -> Segment:
    """
    Deactivates a segment (soft delete / remove from active workspace).
    Invalidates/removes any associated alignments and shifts order_index of subsequent segments.
    """
    seg = db.query(Segment).filter(
        Segment.id == segment_id,
        Segment.project_id == project_id,
        Segment.active == True
    ).first()
    if not seg:
        raise ValueError(f"Không tìm thấy phân đoạn {segment_id}")

    # Remove any alignments this segment is part of
    memberships = db.query(AlignmentMember).filter(AlignmentMember.segment_id == segment_id).all()
    for m in memberships:
        align = db.query(Alignment).filter(Alignment.id == m.alignment_id).first()
        if align:
            db.delete(align)

    seg.active = False
    seg.revision += 1

    # Shift order_index of subsequent active segments
    subsequent = db.query(Segment).filter(
        Segment.project_id == project_id,
        Segment.language == seg.language,
        Segment.active == True,
        Segment.order_index > seg.order_index
    ).all()
    for s in subsequent:
        s.order_index -= 1

    record_revision(
        db,
        project_id=project_id,
        action="delete_segment",
        entity_type="Segment",
        entity_id=segment_id,
        before_state={"text": seg.clean_text, "order_index": seg.order_index, "language": seg.language}
    )
    db.flush()
    return seg

