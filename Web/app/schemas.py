from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import datetime

class ProjectCreate(BaseModel):
    ma_de_tai: str = Field(default="HVB_01")
    ma_tac_pham: str = Field(default="TAC_PHAM")
    name: str
    scope: str = Field(default="Chương 1")
    assigned_to: str = Field(default="Sinh viên")

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
    created_at: datetime.datetime
    resolved_at: Optional[datetime.datetime]

class AISuggestionItem(BaseModel):
    han_ids: List[str]
    viet_ids: List[str]
    alignment_type: str
    score: float
    status: str = "suggested"
    explanation: Optional[str] = None

class AISuggestionsFile(BaseModel):
    schema_version: str = "1.0"
    project_id: str
    task_id: Optional[str] = None
    source_revision: int
    source_sha256_han: str
    source_sha256_viet: str
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
