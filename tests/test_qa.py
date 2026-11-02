import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from Web.app.db import Base
from Web.app.models import Project, Segment, Alignment, AlignmentMember, QAIssue
from Web.app.services.quality import run_automated_qa, get_project_statistics
from Web.app.services.alignment import create_alignment

@pytest.fixture
def qa_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def test_qa_detection_missing_and_format(qa_db):
    proj = Project(id="proj_qa_1", ma_de_tai="HVB_01", ma_tac_pham="TEST", name="QA Test")
    qa_db.add(proj)

    # Segment with formula trigger
    h0 = Segment(id="h0", document_id="d1", project_id=proj.id, language="han", order_index=0, raw_text="=SUM(1)", clean_text="=SUM(1)", active=True)
    v0 = Segment(id="v0", document_id="d2", project_id=proj.id, language="viet", order_index=0, raw_text="Công thức", clean_text="Công thức", active=True)
    # Unassigned segment
    h1 = Segment(id="h1", document_id="d1", project_id=proj.id, language="han", order_index=1, raw_text="Đoạn chưa gán", clean_text="Đoạn chưa gán", active=True)

    qa_db.add_all([h0, v0, h1])
    qa_db.commit()

    create_alignment(qa_db, proj.id, [h0.id], [v0.id])
    qa_db.commit()

    issues = run_automated_qa(qa_db, proj.id)
    qa_db.commit()

    codes = [i.code for i in issues]
    assert "FORMAT" in codes # Because h0 starts with '='
    assert "MISSING" in codes # Because h1 is unassigned

    stats = get_project_statistics(qa_db, proj.id)
    assert stats["unassigned_han"] == 1
    assert stats["unassigned_viet"] == 0
    assert stats["evaluation_status"] == "not evaluated"
