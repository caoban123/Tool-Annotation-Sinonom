import os
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .db import engine, Base, get_db
from .models import Project
from .routers import projects, segments, alignments, quality, suggestions, exports
from .services.quality import get_project_statistics

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HanViet Alignment Studio",
    description="Hệ thống dóng hàng Hán - Việt cấp câu/đoạn chuyên dụng cho đồ án NLP",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include Routers
app.include_router(projects.router)
app.include_router(segments.router)
app.include_router(alignments.router)
app.include_router(quality.router)
app.include_router(suggestions.router)
app.include_router(exports.router)

@app.get("/")
def index_page(request: Request, db: Session = Depends(get_db)):
    all_projects = db.query(Project).order_by(Project.created_at.desc()).all()
    project_stats = []
    for p in all_projects:
        stats = get_project_statistics(db, p.id)
        project_stats.append({"project": p, "stats": stats})
    return templates.TemplateResponse(request=request, name="index.html", context={"projects": project_stats})

@app.get("/clean/{project_id}")
def clean_text_page(project_id: str, request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return templates.TemplateResponse(request=request, name="404.html", context={"message": "Không tìm thấy dự án"})
    stats = get_project_statistics(db, project_id)
    return templates.TemplateResponse(request=request, name="clean_text.html", context={"project": project, "stats": stats})

@app.get("/workspace/{project_id}")
def workspace_page(project_id: str, request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return templates.TemplateResponse(request=request, name="404.html", context={"message": "Không tìm thấy dự án"})
    stats = get_project_statistics(db, project_id)
    return templates.TemplateResponse(request=request, name="workspace.html", context={"project": project, "stats": stats})

@app.get("/qa/{project_id}")
def qa_page(project_id: str, request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return templates.TemplateResponse(request=request, name="404.html", context={"message": "Không tìm thấy dự án"})
    stats = get_project_statistics(db, project_id)
    return templates.TemplateResponse(request=request, name="qa.html", context={"project": project, "stats": stats})

@app.get("/export/{project_id}")
def export_page(project_id: str, request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return templates.TemplateResponse(request=request, name="404.html", context={"message": "Không tìm thấy dự án"})
    stats = get_project_statistics(db, project_id)
    return templates.TemplateResponse(request=request, name="export.html", context={"project": project, "stats": stats})
