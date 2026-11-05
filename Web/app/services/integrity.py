import hashlib
import json
from sqlalchemy import update
from ..models import Project, Segment, AlignmentMember


def lock_project(db, project_id):
    # SQLite has no SELECT FOR UPDATE. Acquire the write lock before reading
    # invariants so concurrent accept/create requests cannot both confirm a segment.
    db.flush()
    db.execute(update(Project).where(Project.id == project_id).values(revision=Project.revision))
    db.expire_all()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_context(db, project_id):
    rows = db.query(Segment).filter_by(project_id=project_id, active=True).order_by(Segment.language, Segment.order_index).all()
    hashes = {language: hashlib.sha256('\n'.join(s.clean_text for s in rows if s.language == language).encode()).hexdigest()
              for language in ('han', 'viet')}
    return dict(hashes=hashes, snapshot=fingerprint([(s.id, s.revision, s.order_index, s.clean_text) for s in rows]))


def alignment_fingerprint(db, alignment):
    members = db.query(AlignmentMember).filter_by(alignment_id=alignment.id).order_by(AlignmentMember.side, AlignmentMember.position).all()
    return fingerprint([(m.side, m.segment_id, m.position, m.segment.revision, m.segment.clean_text, m.segment.active) for m in members])
