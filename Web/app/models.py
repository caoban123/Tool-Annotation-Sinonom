import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index, UniqueConstraint, LargeBinary
)
from sqlalchemy.orm import relationship
from .db import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True)
    ma_de_tai = Column(String(64), nullable=False, default="HVB_01")
    ma_tac_pham = Column(String(128), nullable=False, default="TAC_PHAM")
    name = Column(String(255), nullable=False)
    source_info = Column(Text, default="{}")
    scope = Column(String(255), default="Chương 1")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    revision = Column(Integer, default=1)
    config = Column(Text, default="{}")

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    segments = relationship("Segment", back_populates="project", cascade="all, delete-orphan")
    alignments = relationship("Alignment", back_populates="project", cascade="all, delete-orphan")
    qa_issues = relationship("QAIssue", back_populates="project", cascade="all, delete-orphan")
    revisions = relationship("Revision", back_populates="project", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    assigned_to = Column(String(128), default="Sinh viên")
    scope = Column(String(255), default="Chương 1")
    status = Column(String(32), default="in_progress")
    target_count = Column(Integer, default=2000)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="tasks")

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    language = Column(String(16), nullable=False) # 'han' or 'viet'
    raw_filename = Column(String(255), default="")
    raw_sha256 = Column(String(64), nullable=False)
    clean_sha256 = Column(String(64), nullable=False)
    provenance = Column(Text, default="{}")
    raw_bytes = Column(LargeBinary, nullable=True)
    source_bytes = Column(LargeBinary, nullable=True)
    source_sha256 = Column(String(64), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    revision = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="documents")
    segments = relationship("Segment", back_populates="document", cascade="all, delete-orphan")

class Segment(Base):
    __tablename__ = "segments"

    id = Column(String(64), primary_key=True)
    document_id = Column(String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    language = Column(String(16), nullable=False) # 'han' or 'viet'
    order_index = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=False)
    clean_text = Column(Text, nullable=False)
    page_ref = Column(String(64), default="")
    parent_ids = Column(Text, default="[]")
    replaced_ids = Column(Text, default="[]")
    active = Column(Boolean, default=True, nullable=False)
    revision = Column(Integer, default=1)

    project = relationship("Project", back_populates="segments")
    document = relationship("Document", back_populates="segments")
    memberships = relationship("AlignmentMember", back_populates="segment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_segment_proj_lang_order", "project_id", "language", "order_index"),
        Index("idx_segment_active", "project_id", "active"),
    )

class SegmentTranslation(Base):
    __tablename__ = "segment_translations"

    # Content-addressed cache, scoped to a segment so project deletion cascades.
    id = Column(String(64), primary_key=True)
    segment_id = Column(String(64), ForeignKey("segments.id", ondelete="CASCADE"), nullable=False, index=True)
    source_language = Column(String(16), nullable=False, default="lzh")
    target_language = Column(String(16), nullable=False, default="vi")
    provider = Column(String(32), nullable=False, default="azure")
    translated_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Alignment(Base):
    __tablename__ = "alignments"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(64), nullable=True)
    alignment_type = Column(String(16), nullable=False) # '1-1', '1-n', 'n-1', 'n-m'
    status = Column(String(32), default="confirmed", nullable=False) # 'draft', 'suggested', 'confirmed', 'needs_review', 'rejected'
    notes = Column(Text, default="")
    suggestion_context = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    revision = Column(Integer, default=1)

    project = relationship("Project", back_populates="alignments")
    members = relationship("AlignmentMember", back_populates="alignment", cascade="all, delete-orphan", order_by="AlignmentMember.position")
    qa_issues = relationship("QAIssue", back_populates="alignment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_alignment_proj_status", "project_id", "status"),
    )

class AlignmentMember(Base):
    __tablename__ = "alignment_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alignment_id = Column(String(64), ForeignKey("alignments.id", ondelete="CASCADE"), nullable=False)
    segment_id = Column(String(64), ForeignKey("segments.id", ondelete="CASCADE"), nullable=False)
    side = Column(String(16), nullable=False) # 'han' or 'viet'
    position = Column(Integer, nullable=False, default=0)

    alignment = relationship("Alignment", back_populates="members")
    segment = relationship("Segment", back_populates="memberships")

    __table_args__ = (
        Index("idx_member_align_side", "alignment_id", "side", "position"),
        Index("idx_member_seg", "segment_id"),
    )

class QAIssue(Base):
    __tablename__ = "qa_issues"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    alignment_id = Column(String(64), ForeignKey("alignments.id", ondelete="SET NULL"), nullable=True)
    segment_id = Column(String(64), ForeignKey("segments.id", ondelete="SET NULL"), nullable=True)
    code = Column(String(32), nullable=False) # OMISSION, ADDITION, MISSING, FORMAT, DUPLICATE, ORDER
    severity = Column(String(16), default="warning") # warning, error
    status = Column(String(16), default="open") # open, resolved, ignored
    comment = Column(Text, default="")
    origin = Column(String(32), default="manual", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="qa_issues")
    alignment = relationship("Alignment", back_populates="qa_issues")


class QualityReview(Base):
    __tablename__ = 'quality_reviews'
    id = Column(String(64), primary_key=True)
    alignment_id = Column(String(64), ForeignKey('alignments.id', ondelete='CASCADE'), unique=True, nullable=False)
    project_id = Column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    outcome = Column(String(16), nullable=False)
    error_codes = Column(Text, default='[]')
    note = Column(Text, default='')
    reviewer = Column(String(128), default='')
    content_hash = Column(String(64), nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Revision(Base):
    __tablename__ = "revisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    before_state = Column(Text, default="{}")
    after_state = Column(Text, default="{}")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    resource_version = Column(Integer, default=1)

    project = relationship("Project", back_populates="revisions")
