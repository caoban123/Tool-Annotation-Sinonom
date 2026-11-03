"""
Work Catalog & Data Source Resolver.
Manages the standardized catalog of Classical Sino-Vietnamese works,
locates local files in data/source_materials, and handles auto-pull from GitHub CV01 repository.
"""

import os
import sys
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CV01_REPO = "https://github.com/caoban123/CV01.git"
DEFAULT_GDRIVE_FILE_ID = "1buDy5j8bNtFLUzh1yvTSOPX5dAyE_ShG"
DEFAULT_GDRIVE_URL = f"https://drive.google.com/uc?id={DEFAULT_GDRIVE_FILE_ID}"

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

def is_lfs_pointer_file(file_path: Path) -> bool:
    """Checks if a file is a Git LFS pointer text file (~130 bytes starting with version https://)."""
    if not file_path.exists():
        return False
    try:
        if file_path.stat().st_size > 4096:
            return False
        with open(file_path, "rb") as f:
            header = f.read(20)
            return header.startswith(b"version https://") or header.startswith(b"versi")
    except Exception:
        return False

def is_valid_pdf_file(file_path: Path) -> bool:
    """Checks if a file exists, has realistic binary size (>2KB), and starts with %PDF- header."""
    if not file_path.exists():
        return False
    try:
        if file_path.stat().st_size < 2048:
            return False
        with open(file_path, "rb") as f:
            header = f.read(5)
            return header.startswith(b"%PDF-")
    except Exception:
        return False

def get_works_catalog() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of all registered works."""
    return WORKS_CATALOG

def download_from_gdrive(
    gdrive_id: str = DEFAULT_GDRIVE_FILE_ID,
    target_dir: Path = Path("data/source_materials")
) -> bool:
    """
    Tự động kéo toàn bộ dữ liệu 660MB PDF gốc từ link Google Drive công khai qua gdown.
    Giải nén và sắp xếp đúng cấu trúc thư mục data/source_materials.
    """
    try:
        import gdown
    except ImportError:
        print("[DataLoader] Đang cài đặt thư viện gdown để kéo dữ liệu từ Google Drive...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdown"], check=False)
        try:
            import gdown
        except Exception:
            print("[DataLoader] Không thể cài đặt gdown.")
            return False

    temp_zip = target_dir.parent / "_source_materials_download.zip"
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"[DataLoader] 🚀 Đang tự động kéo toàn bộ 660MB PDF gốc từ Google Drive (ID: {gdrive_id})...")

    try:
        downloaded = gdown.download(id=gdrive_id, output=str(temp_zip), quiet=False)
        if not downloaded or not temp_zip.exists() or temp_zip.stat().st_size < 100000:
            print("[DataLoader] Tải file từ Google Drive không thành công hoặc file rỗng.")
            if temp_zip.exists():
                temp_zip.unlink(missing_ok=True)
            return False

        print(f"[DataLoader] 📦 Đang giải nén bộ tài liệu vào: {target_dir}...")
        with zipfile.ZipFile(str(temp_zip), "r") as zf:
            zf.extractall(str(target_dir))
        temp_zip.unlink(missing_ok=True)

        # Xử lý nếu giải nén tạo thư mục lồng nhau: target_dir/source_materials/...
        nested = target_dir / "source_materials"
        if nested.exists() and nested.is_dir():
            for sub in nested.iterdir():
                dest = target_dir / sub.name
                if not dest.exists():
                    sub.rename(dest)
            import shutil
            shutil.rmtree(nested, ignore_errors=True)

        print("[DataLoader] ✓ Tải và giải nén toàn bộ 660MB PDF gốc thành công!")
        return True
    except Exception as e:
        print(f"[DataLoader] Lỗi trong quá trình kéo Google Drive: {e}")
        if temp_zip.exists():
            temp_zip.unlink(missing_ok=True)
        return False

def ensure_data_source(
    base_dir: str = "data/source_materials",
    git_repo_url: str = DEFAULT_CV01_REPO,
    gdrive_id: str = DEFAULT_GDRIVE_FILE_ID
) -> Path:
    """
    Đảm bảo dữ liệu tư liệu nguồn có sẵn:
    1. Kiểm tra nếu đã có file PDF dung lượng thực tế.
    2. Nếu đang chạy trên Colab và đã mount Google Drive, tự động nhận diện.
    3. Tự động kéo 660MB từ link Google Drive của người dùng (băng thông không giới hạn).
    4. Fallback: Nếu không có kết nối Google Drive, thử kéo CV01 git.
    """
    target = Path(base_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    # 1. Kiểm tra nếu đã có file PDF nhị phân thật (>2KB)
    existing_pdfs = [p for p in target.rglob("*.pdf") if is_valid_pdf_file(p)]
    if existing_pdfs:
        print(f"[DataLoader] ✓ Tìm thấy {len(existing_pdfs)} file PDF dung lượng thực tế trong: {target}")
        return target

    # 2. Kiểm tra nếu chạy Colab đã mount Drive
    colab_drive_paths = [
        Path("/content/drive/MyDrive/source_materials"),
        Path("/content/drive/MyDrive/CV01"),
        Path("/content/drive/MyDrive/data/source_materials")
    ]
    for drive_p in colab_drive_paths:
        if drive_p.exists() and [p for p in drive_p.rglob("*.pdf") if is_valid_pdf_file(p)]:
            print(f"[DataLoader] ✓ Đã phát hiện tài liệu trong Google Drive: {drive_p}")
            for item in drive_p.iterdir():
                dest = target / item.name
                if not dest.exists():
                    try:
                        dest.symlink_to(item)
                    except Exception:
                        pass
            return target

    # 3. Tự động kéo từ Google Drive công khai qua gdown
    print(f"[DataLoader] Chưa có file PDF nhị phân trong {target}.")
    success = download_from_gdrive(gdrive_id=gdrive_id, target_dir=target)
    if success:
        return target

    # 4. Fallback kéo CV01 repo
    print(f"[DataLoader] Đang thử kéo bổ trợ từ GitHub {git_repo_url}...")
    try:
        temp_dir = target / "_cv01_temp"
        subprocess.run(
            ["git", "clone", "--depth", "1", git_repo_url, str(temp_dir)],
            check=True
        )
        for item in temp_dir.iterdir():
            if item.name.startswith(".git"):
                continue
            dest_item = target / item.name
            if not dest_item.exists():
                item.rename(dest_item)
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        print(f"[DataLoader] Cảnh báo khi tải từ git: {e}")

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
