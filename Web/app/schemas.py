from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict
import datetime

class ProjectCreate(BaseModel):
    ma_de_tai: str = Field(default="HVB_01")
    ma_tac_pham: str = Field(default="TAC_PHAM")
    name: str
    scope: str = Field(default="Chương 1")
    assigned_to: str = Field(default="Sinh viên")
    target_count: int = Field(default=2000, ge=1, le=1000000)

class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ma_de_tai: str
    ma_tac_pham: str
    name: str
    scope: str
    revision: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    language: str
    order_index: int
    raw_text: str
    clean_text: str
    page_ref: str
    active: bool
    revision: int
    alignment_id: Optional[str] = None
    alignment_status: Optional[str] = None

class SegmentUpdate(BaseModel):
    clean_text: str

class SegmentSplitRequest(BaseModel):
    segment_id: str
    split_texts: List[str]

class SegmentMergeRequest(BaseModel):
    segment_ids: List[str]

class AlignmentCreateRequest(BaseModel):
    project_id: str
    task_id: Optional[str] = None
    han_segment_ids: List[str]
    viet_segment_ids: List[str]
    notes: Optional[str] = ""
    status: Optional[str] = "confirmed"

class AlignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    task_id: Optional[str]
    alignment_type: str
    status: str
    notes: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    revision: int
    han_segments: List[SegmentOut]
    viet_segments: List[SegmentOut]

class AlignmentUndoRequest(BaseModel):
    project_id: str
    alignment_id: Optional[str] = None

class QAIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    alignment_id: Optional[str]
    segment_id: Optional[str]
    code: str
    severity: str
    status: str
    comment: Optional[str]
    origin: str = 'legacy'
    created_at: datetime.datetime
    resolved_at: Optional[datetime.datetime]

class AISuggestionItem(BaseModel):
    han_ids: List[str] = Field(min_length=1)
    viet_ids: List[str] = Field(min_length=1)
    alignment_type: Literal['1-1', '1-n', 'n-1', 'n-m']
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    status: Literal['suggested'] = "suggested"
    explanation: Optional[str] = None

class AISuggestionsFile(BaseModel):
    schema_version: Literal['1.0']
    project_id: str
    task_id: Optional[str] = None
    source_revision: int = Field(strict=True, ge=1)
    source_sha256_han: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_sha256_viet: str = Field(pattern=r'^[a-f0-9]{64}$')
    model_name: str
    model_version: str
    created_at: str
    suggestions: List[AISuggestionItem]

class StatsOut(BaseModel):
    project_id: str
    total_han_segments: int
    total_viet_segments: int
    confirmed_alignments: int
    confirmed_11: int
    confirmed_1n: int
    confirmed_n1: int
    confirmed_nm: int
    unassigned_han: int
    unassigned_viet: int
    target_count: int
    qa_issues_count: int
    checked_sample_size: int = 0
    checked_error_count: int = 0
    error_rate_pct: Optional[float] = None
    evaluation_status: str = 'not evaluated'
    needs_review_alignments: int = 0


class ReviewRequest(BaseModel):
    outcome: Literal['correct', 'error']
    error_codes: List[Literal['OMISSION', 'ADDITION', 'MISSING']] = Field(default_factory=list)
    note: str = ''
    reviewer: str = ''


class SourceUpdate(BaseModel):
    title: str = ''
    url: str = ''
    filename: str = ''
    format: str = ''
    page_count: Optional[int] = Field(default=None, ge=1)
    scope: str = ''
    tools: str = ''
    notes: str = ''


class TaskRequest(BaseModel):
    assigned_to: str = Field(min_length=1, max_length=128)
    scope: str = Field(min_length=1, max_length=255)
    target_count: int = Field(ge=1, le=1000000)
