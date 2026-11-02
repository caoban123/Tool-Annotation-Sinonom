import time
import threading
import socket
from pathlib import Path
import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from Web.app.main import app

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

@pytest.fixture(scope="module")
def live_server():
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", port))
            s.close()
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError(f"Server did not start on {base_url}")

    yield base_url
    server.should_exit = True
    thread.join(timeout=2)

def test_playwright_e2e_workflow(live_server, tmp_path):
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
    han_txt = fixtures_dir / "han.txt"
    viet_txt = fixtures_dir / "viet.txt"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        # 1. Homepage
        page.goto(live_server)
        assert "Han" in page.title()

        # 2. Open Create Project Modal
        page.locator("button:has-text('Tạo Dự Án Mới')").click()
        page.wait_for_selector("#newProjectModal:not(.hidden)")

        page.fill("input[name='ma_de_tai']", "HVB_01")
        page.fill("input[name='ma_tac_pham']", "TEST_PLAYWRIGHT")
        page.fill("input[name='name']", "Kiểm thử Browser E2E")
        page.fill("input[name='scope']", "Chương 1")

        # Set files
        page.set_input_files("#han_file_input", str(han_txt))
        page.set_input_files("#viet_file_input", str(viet_txt))

        # Submit
        page.locator("#btnSubmitCreate").click()

        # 3. Wait for navigation to workspace
        page.wait_for_url(f"{live_server}/workspace/*", timeout=10000)
        assert "/workspace/" in page.url

        # Wait for segments to render
        page.wait_for_selector("#hanColumn div[id^='card_seg_han_']", timeout=5000)
        page.wait_for_selector("#vietColumn div[id^='card_seg_viet_']", timeout=5000)

        han_locator = page.locator("#hanColumn div[id^='card_seg_han_']")
        viet_locator = page.locator("#vietColumn div[id^='card_seg_viet_']")

        assert han_locator.count() >= 5
        assert viet_locator.count() >= 5

        # 4. Select Han[0] and Viet[0] -> 1-1
        han_locator.nth(0).click()
        viet_locator.nth(0).click()

        # Check badge shows 1–1
        page.wait_for_selector("#cardinalityBadge:has-text('1–1')")
        btn_confirm = page.locator("#btnConfirm")
        assert btn_confirm.is_enabled()

        # 5. Confirm 1-1 alignment
        btn_confirm.click()
        page.wait_for_timeout(1000)

        # Verify badge changed to "Đã dóng"
        assert "Đã dóng" in han_locator.nth(0).inner_text()

        # 6. Test Undo
        page.locator("button:has-text('Hoàn tác')").click()
        page.wait_for_timeout(1000)
        assert "Chưa gán" in han_locator.nth(0).inner_text()

        # 7. Re-confirm 1-1
        han_locator.nth(0).click()
        viet_locator.nth(0).click()
        btn_confirm.click()
        page.wait_for_timeout(1000)

        # 8. Create 1-n alignment: Han[1] and Viet[1], Viet[2]
        han_locator.nth(1).click()
        viet_locator.nth(1).click()
        viet_locator.nth(2).click()

        page.wait_for_selector("#cardinalityBadge:has-text('1–n')")
        btn_confirm.click()
        page.wait_for_timeout(1000)

        # Save screenshot for evidence
        artifacts_dir = Path(__file__).resolve().parent.parent.parent / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = artifacts_dir / "workspace_e2e.png"
        page.screenshot(path=str(screenshot_path))
        assert screenshot_path.exists()

        # 9. Navigate to QA page
        page.locator("a:has-text('QA & Lỗi')").click()
        page.wait_for_url(f"{live_server}/qa/*")
        assert "Kiểm Định Chất Lượng" in page.content()

        # 10. Navigate to Export page
        page.locator("a:has-text('Xuất & Sao lưu')").click()
        page.wait_for_url(f"{live_server}/export/*")
        assert "Gói Kết Quả Dóng Hàng Nghiệm Thu" in page.content()
        assert page.locator("a:has-text('Tải TSV Song Ngữ')").is_visible()
        assert page.locator("a:has-text('Tải Excel XLSX')").is_visible()
        assert page.locator("a:has-text('Tải Gói Giao Nộp (ZIP)')").is_visible()

        browser.close()
