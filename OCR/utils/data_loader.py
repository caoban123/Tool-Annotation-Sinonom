"""
Data loading and catalog helper utilities for OCR pipeline.
Handles auto-pulling 660MB historical scanned PDFs from public Google Drive via gdown.
"""
import os
import sys
import json
import zipfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from .pdf_detector import inspect_pdf

DEFAULT_GDRIVE_FILE_ID = "1buDy5j8bNtFLUzh1yvTSOPX5dAyE_ShG"

def download_from_gdrive(
    gdrive_id: str = DEFAULT_GDRIVE_FILE_ID,
    target_dir: Path = Path("data/source_materials")
) -> bool:
    """
    Tự động kéo toàn bộ 660MB PDF gốc từ Google Drive công khai qua gdown và giải nén.
    """
    try:
        import gdown
    except ImportError:
        print("[DataLoader] Đang cài đặt thư viện gdown để kéo dữ liệu từ Google Drive...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdown"], check=False)
        try:
            import gdown
        except Exception:
            print("[DataLoader] ❌ Không thể cài đặt gdown.")
            return False

    target_dir = Path(target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    temp_zip = target_dir.parent / "_source_materials_download.zip"

    print(f"[DataLoader] 🚀 Đang tự động kéo toàn bộ 660MB PDF gốc từ Google Drive (ID: {gdrive_id})...")
    try:
        url = f"https://drive.google.com/uc?id={gdrive_id}"
        downloaded = gdown.download(url=url, output=str(temp_zip), quiet=False)
        if not downloaded or not temp_zip.exists() or temp_zip.stat().st_size < 100000:
            downloaded = gdown.download(id=gdrive_id, output=str(temp_zip), quiet=False)

        if not downloaded or not temp_zip.exists() or temp_zip.stat().st_size < 100000:
            print("[DataLoader] ⚠️ Tải file từ Google Drive không thành công hoặc file bị giới hạn.")
            if temp_zip.exists():
                temp_zip.unlink(missing_ok=True)
            return False

        print(f"[DataLoader] 📦 Đang giải nén bộ tài liệu 660MB vào: {target_dir.parent}...")
        with zipfile.ZipFile(str(temp_zip), "r") as zf:
            zf.extractall(str(target_dir.parent))

        # Dọn dẹp file zip tạm
        temp_zip.unlink(missing_ok=True)

        # Xử lý nếu giải nén tạo thư mục lồng nhau
        nested = target_dir / "source_materials"
        if nested.exists() and nested.is_dir():
            for sub in nested.iterdir():
                dest = target_dir / sub.name
                if not dest.exists():
                    sub.rename(dest)
            import shutil
            shutil.rmtree(nested, ignore_errors=True)

        print("[DataLoader] ✓ Tải và giải nén toàn bộ 660MB PDF gốc từ Google Drive thành công!")
        return True
    except Exception as e:
        print(f"[DataLoader] Lỗi trong quá trình kéo Google Drive: {e}")
        if temp_zip.exists():
            temp_zip.unlink(missing_ok=True)
        return False

def ensure_data_source(
    base_dir: str = "data/source_materials",
    gdrive_id: str = DEFAULT_GDRIVE_FILE_ID
) -> Path:
    """
    Đảm bảo dữ liệu tư liệu nguồn có sẵn:
    - Nếu đã có file PDF nhị phân thật (> 100KB), bỏ qua.
    - Nếu chưa có, tự động kéo 660MB từ Google Drive và giải nén.
    """
    target = Path(base_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    existing_pdfs = [p for p in target.rglob("*.pdf") if p.stat().st_size > 100000]
    if existing_pdfs:
        print(f"[DataLoader] ✓ Đã có {len(existing_pdfs)} file PDF dung lượng thực tế trong: {target}")
        return target

    # Tự động kéo từ Google Drive
    download_from_gdrive(gdrive_id=gdrive_id, target_dir=target)
    return target

def get_works_catalog() -> Dict[str, Dict[str, Any]]:
    cat_file = Path("data/works_catalog.json")
    if cat_file.exists():
        try:
            with open(cat_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        from Crawl.utils.catalog import get_works_catalog as _gwc
        return _gwc()
    except Exception:
        return {}

def resolve_work(work_key: str, base_dir: str = "data/source_materials") -> Dict[str, Any]:
    catalog = get_works_catalog()
    entry = dict(catalog.get(work_key, {
        "key": work_key,
        "name": work_key,
        "ma_tac_pham": work_key
    }))
    base = Path(base_dir).resolve()

    han_rel = entry.get("han_relpath", "")
    target_path = (base / han_rel) if han_rel else None

    # 1. Trực tiếp khớp đường dẫn
    if target_path and target_path.exists() and target_path.stat().st_size > 10000:
        entry["han_abs_path"] = str(target_path)
        entry["han_exists"] = True
        return entry

    # 2. Tìm kiếm thông minh theo thư mục tác phẩm (chống lệch Unicode NFC/NFD)
    candidate_pdfs = [p for p in base.rglob("*.pdf") if p.stat().st_size > 100000]
    
    # Tìm file nằm trong thư mục 'han' phù hợp tên tác phẩm
    for p in candidate_pdfs:
        p_str = str(p).lower()
        if "han" in p_str:
            if work_key.lower() in p_str or any(k in p_str for k in ["dia_du", "dia du", "hien chuong", "hien_chuong", "nhat thong", "viet su"]):
                entry["han_abs_path"] = str(p)
                entry["han_exists"] = True
                return entry

    # 3. Lấy file PDF chữ Hán đầu tiên tìm thấy
    for p in candidate_pdfs:
        if "han" in str(p).lower():
            entry["han_abs_path"] = str(p)
            entry["han_exists"] = True
            return entry

    # 4. Lấy bất kỳ file PDF nào có dung lượng thực tế
    if candidate_pdfs:
        entry["han_abs_path"] = str(candidate_pdfs[0])
        entry["han_exists"] = True
        return entry

    entry["han_abs_path"] = str(target_path) if target_path else None
    entry["han_exists"] = False
    return entry

__all__ = [
    "inspect_pdf",
    "get_works_catalog",
    "resolve_work",
    "ensure_data_source",
    "download_from_gdrive",
    "DEFAULT_GDRIVE_FILE_ID"
]
