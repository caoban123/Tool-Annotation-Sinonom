import os
import re
import html
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

def extract_from_html(
    source_url_or_path: str,
    css_selector: Optional[str] = None,
    timeout: int = 15
) -> Dict[str, Any]:
    """
    Extracts clean article text from an HTML file path or Web URL.
    Strips boilerplate (nav, header, footer, script, style, ads).
    Preserves paragraph structure and reading order.
    """
    is_url = source_url_or_path.startswith(("http://", "https://"))
    provenance = {
        "source": source_url_or_path,
        "is_url": is_url,
        "extracted_at": datetime.datetime.utcnow().isoformat(),
    }

    if is_url:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HanVietCrawler/1.0"}
        try:
            resp = requests.get(source_url_or_path, headers=headers, timeout=timeout)
            if resp.status_code == 403:
                raise PermissionError("Truy cập bị từ chối (HTTP 403 Forbidden). Cần kiểm tra quyền hoặc chính sách robots/paywall.")
            if resp.status_code == 429:
                raise ConnectionRefusedError("Bị giới hạn tốc độ yêu cầu (HTTP 429 Too Many Requests). Cần tăng crawl delay.")
            resp.raise_for_status()
            html_content = resp.text
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Lỗi kết nối tới URL: {str(e)}")
    else:
        path = Path(source_url_or_path)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file HTML: {source_url_or_path}")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            html_content = f.read()

    soup = BeautifulSoup(html_content, "html.parser")

    # Extract page title
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    provenance["title"] = title

    # Remove unwanted tags
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "menu", "noscript", "iframe"]):
        tag.decompose()

    # Target specific container if provided, else main or body
    container = None
    if css_selector:
        container = soup.select_one(css_selector)

    if not container:
        container = soup.find("main") or soup.find("article") or soup.find("body") or soup

    # Extract paragraphs and headings
    text_blocks = []
    for el in container.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "li"]):
        # Only take leaf text or elements without block children
        if not el.find(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
            raw = el.get_text()
            cleaned = html.unescape(raw).strip()
            # Collapse internal whitespace
            cleaned = re.sub(r'[ \t]+', ' ', cleaned)
            if cleaned and cleaned not in text_blocks:
                text_blocks.append(cleaned)

    full_text = "\n".join(text_blocks)
    if not full_text.strip():
        raise ValueError("Nội dung HTML trích xuất rỗng hoặc không tìm thấy văn bản phù hợp.")

    provenance["block_count"] = len(text_blocks)
    provenance["char_count"] = len(full_text)

    return {
        "text": full_text,
        "blocks": text_blocks,
        "provenance": provenance
    }
