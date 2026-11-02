import json
import datetime
from sqlalchemy.orm import Session
from ..models import Project, Revision

def record_revision(
    db: Session,
    project_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before_state: dict = None,
    after_state: dict = None
) -> int:
    """Record an append-only audit revision log and bump the project's revision counter."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        current_rev = 1
    else:
        project.revision += 1
        current_rev = project.revision
        project.updated_at = datetime.datetime.utcnow()

    rev = Revision(
        project_id=project_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before_state=json.dumps(before_state or {}, ensure_ascii=False),
        after_state=json.dumps(after_state or {}, ensure_ascii=False),
        timestamp=datetime.datetime.utcnow(),
        resource_version=current_rev
    )
    db.add(rev)
    db.flush()
    return current_rev
