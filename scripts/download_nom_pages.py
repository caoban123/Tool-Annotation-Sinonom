import os
import sys
import time
from pathlib import Path
import requests

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def download_volume_pages(
    volume_code: str = "nlvnpf-0103-01",
    total_pages: int = 82,
    output_dir: str = "data/nom_scans/dai_viet_dia_du_q1",
    start_page: int = 1,
    end_page: int = 82
):
    """
    Tải tự động các trang ảnh scan từ thư viện Viện Nghiên Cứu Hán Nôm (Nom Foundation).
    URL dạng: https://lib.nomfoundation.org/site_media/nom/{volume_code}/jpeg/{volume_code}-{page:03d}.jpg
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HanVietNomDownloader/1.0"}

    print(f"Bắt đầu tải các trang từ {start_page} đến {end_page} cho tác phẩm: {volume_code}")
    success_count = 0

    for p in range(start_page, min(total_pages, end_page) + 1):
        filename = f"{volume_code}-{p:03d}.jpg"
        img_url = f"https://lib.nomfoundation.org/site_media/nom/{volume_code}/jpeg/{filename}"
        dest_path = out / filename

        if dest_path.exists() and dest_path.stat().st_size > 1000:
            print(f"[{p}/{end_page}] Đã có sẵn: {filename}")
            success_count += 1
            continue

        try:
            resp = requests.get(img_url, headers=headers, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
                print(f"[{p}/{end_page}] Đã tải thành công: {filename} ({len(resp.content)//1024} KB)")
                success_count += 1
                time.sleep(0.5) # Crawl delay văn minh tôn trọng server
            else:
                print(f"[{p}/{end_page}] Lỗi tải trang {p}: HTTP {resp.status_code}")
        except Exception as e:
            print(f"[{p}/{end_page}] Lỗi kết nối trang {p}: {str(e)}")

    print(f"\nHoàn tất! Đã tải thành công {success_count}/{end_page - start_page + 1} trang tại: {out.resolve()}")

if __name__ == "__main__":
    # Mặc định tải thử 3 trang đầu làm mẫu
    download_volume_pages(start_page=1, end_page=3)
