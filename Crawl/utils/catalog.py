"""
Work Catalog & Data Source Resolver.
Manages the standardized catalog of Classical Sino-Vietnamese works,
locates local files in data/source_materials, and handles auto-pull from GitHub CV01 repository.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CV01_REPO = "https://github.com/caoban123/CV01.git"

WORKS_CATALOG: Dict[str, Dict[str, Any]] = {
    "HVNTDDC": {
        "key": "HVNTDDC",
        "name": "Hoàng Việt Nhất Thống Địa Dư Chí",
        "author": "Lê Quang Định",
        "ma_de_tai": "HVB_01",
        "ma_tac_pham": "HVNTDDC",
        "scope": "Quyển 1",
        "han_relpath": os.path.join("Hoàng_Việt_Nhất_Thống_Địa_Dư_Chí", "han", "Hoàng Việt Nhất Thống Dư Địa Chí.pdf"),
        "viet_relpath": os.path.join("Hoàng_Việt_Nhất_Thống_Địa_Dư_Chí", "vi", "Hoàng Việt Nhất Thống Dư Địa Chí.pdf"),
        "description": "Địa chí đầu thời Nguyễn ghi chép đầy đủ về cương giới, phong tục, núi sông toàn bờ cõi nước Việt."
    },
    "LTHCLC_Q20_25": {
        "key": "LTHCLC_Q20_25",
        "name": "Lịch Triều Hiến Chương Loại Chí (Quyển 20–25: Lễ Nghi Chí)",
        "author": "Phan Huy Chú",
        "ma_de_tai": "HVB_01",
        "ma_tac_pham": "LTHCLC_Q20_25",
        "scope": "Quyển 20 - Lễ Nghi",
        "han_relpath": os.path.join("Lịch_triều_hiến_chương_loại_chí_Quyển_20-25_Lễ_nghi_chí", "han", "Lịch triều hiến chương loại chí Quyển 20-25 Lễ nghi chí.pdf"),
        "viet_relpath": os.path.join("Lịch_triều_hiến_chương_loại_chí_Quyển_20-25_Lễ_nghi_chí", "vi", "Lịch Triều Hiến Chương Loại Chí - Phan Huy Chú - Tập 1_ocr.pdf"),
        "description": "Bộ bách khoa toàn thư cổ điển của Việt Nam; phần Lễ Nghi ghi chép điển chế, triều nghi, lễ tế."
    },
    "LTHCLC_Q46_49": {
        "key": "LTHCLC_Q46_49",
        "name": "Lịch Triều Hiến Chương Loại Chí (Quyển 46–49: Bang Giao Chí)",
        "author": "Phan Huy Chú",
        "ma_de_tai": "HVB_01",
        "ma_tac_pham": "LTHCLC_Q46_49",
        "scope": "Quyển 46 - Bang Giao",
        "han_relpath": os.path.join("Lịch_triều_hiến_chương_loại_chí_Quyển_46-49_Lễ_nghi_chí", "han", "Lịch triều hiến chương loại chí Quyển 46-49 Bang giao chí.pdf"),
        "viet_relpath": os.path.join("Lịch_triều_hiến_chương_loại_chí_Quyển_46-49_Lễ_nghi_chí", "vi", "Lịch Triều Hiến Chương Loại Chí - Phan Huy Chú - Tập 2_ocr.pdf"),
        "description": "Phần Bang Giao ghi chép thư tịch ngoại giao, nghi thức tiếp sứ và quan hệ quốc tế thời phong kiến."
    },
    "VIET_SU_YEU": {
        "key": "VIET_SU_YEU",
        "name": "Việt Sử Yếu",
        "author": "Hoàng Cao Khải",
        "ma_de_tai": "HVB_01",
        "ma_tac_pham": "VIET_SU_YEU",
        "scope": "Quyển 1",
        "han_relpath": os.path.join("Việt_Sử_Yếu", "Việt Sử Yếu.pdf"),
        "viet_relpath": None,
        "description": "Bộ sử yếu chữ Hán tóm lược diễn trình lịch sử nước Việt."
    },
    "DVDDTB": {
        "key": "DVDDTB",
        "name": "Đại Việt Địa Dư Toàn Biên",
        "author": "Nguyễn Văn Siêu",
        "ma_de_tai": "HVB_01",
        "ma_tac_pham": "DVDDTB",
        "scope": "Quyển 1",
        "han_relpath": os.path.join("Đại_Việt_địa_dư_toàn_biên", "han", "Đại việt địa dư toàn biên.pdf"),
        "viet_relpath": os.path.join("Đại_Việt_địa_dư_toàn_biên", "vi", "Đại Việt Địa Dư Toàn Biên.pdf"),
        "description": "Tác phẩm địa lý lịch sử quan trọng khảo cứu kỹ lưỡng cương thổ và phân định hành chính các thời kỳ."
    }
}

def get_works_catalog() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of all registered works."""
    return WORKS_CATALOG

def ensure_data_source(
    base_dir: str = "data/source_materials",
    git_repo_url: str = DEFAULT_CV01_REPO
) -> Path:
    """
    Ensures that source materials exist locally.
    If the directory is empty or missing (e.g. running on Google Colab or a fresh clone),
    automatically pulls the dataset from the remote GitHub CV01 repository.
    """
    target = Path(base_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    # Check if any PDF files exist inside target
    existing_pdfs = list(target.rglob("*.pdf"))
    if existing_pdfs:
        print(f"[DataLoader] Tìm thấy {len(existing_pdfs)} file PDF sẵn có trong: {target}")
        return target

    print(f"[DataLoader] Chưa thấy file PDF nào trong {target}.")
    print(f"[DataLoader] Đang tự động kéo dữ liệu từ {git_repo_url}...")

    try:
        # Clone with depth=1
        subprocess.run(
            ["git", "clone", "--depth", "1", git_repo_url, str(target / "_cv01_temp")],
            check=True
        )
        # Move items into target
        temp_dir = target / "_cv01_temp"
        for item in temp_dir.iterdir():
            if item.name.startswith(".git"):
                continue
            dest_item = target / item.name
            if not dest_item.exists():
                item.rename(dest_item)
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"[DataLoader] Kéo dữ liệu hoàn tất vào: {target}")
    except Exception as e:
        print(f"[DataLoader] Cảnh báo khi tải dữ liệu từ git: {e}")
        print("[DataLoader] Nếu chạy trên Colab, hãy đảm bảo kết nối mạng hoặc upload file vào data/source_materials/")

    return target

def resolve_work(work_key: str, base_dir: str = "data/source_materials") -> Dict[str, Any]:
    """
    Resolves full absolute paths and existence status for a given work.
    """
    if work_key not in WORKS_CATALOG:
        raise KeyError(f"Không tìm thấy tác phẩm '{work_key}' trong danh mục. Lựa chọn hợp lệ: {list(WORKS_CATALOG.keys())}")

    entry = dict(WORKS_CATALOG[work_key])
    base = Path(base_dir).resolve()

    han_path = (base / entry["han_relpath"]) if entry.get("han_relpath") else None
    viet_path = (base / entry["viet_relpath"]) if entry.get("viet_relpath") else None

    entry["han_abs_path"] = str(han_path) if han_path else None
    entry["viet_abs_path"] = str(viet_path) if viet_path else None
    entry["han_exists"] = han_path.exists() if han_path else False
    entry["viet_exists"] = viet_path.exists() if viet_path else False

    return entry
