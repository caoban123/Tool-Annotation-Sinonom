import time
import threading
import socket
import json
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


def test_offline_responsive_review_and_focus(live_server):
    """Exercise the actual local assets and UI at desktop and phone widths."""
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':1366,'height':768})
        forbidden=[]
        def local_only(route):
            if route.request.url.startswith(live_server):
                route.continue_()
            else:
                forbidden.append(route.request.url);route.abort()
        context.route('**/*',local_only)
        page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        project=page.request.post(live_server+'/api/projects',data={'name':'Offline UI QA','target_count':1}).json()['id']
        upload=page.request.post(f'{live_server}/api/projects/{project}/import',multipart={
            'han_file':{'name':'han.txt','mimeType':'text/plain','buffer':'甲。乙。'.encode()},
            'viet_file':{'name':'viet.txt','mimeType':'text/plain','buffer':'Một. Hai.'.encode()}})
        assert upload.ok,upload.text()
        source=page.request.get(f'{live_server}/api/suggestions/export-segments?project_id={project}').json()
        han=next(s for s in source['segments'] if s['language']=='han')
        viet=next(s for s in source['segments'] if s['language']=='viet')
        payload=dict(schema_version='1.0',project_id=project,task_id=source['task_id'],source_revision=source['revision'],
            source_sha256_han=source['source_sha256_han'],source_sha256_viet=source['source_sha256_viet'],
            model_name='browser-test',model_version='1',created_at='2026-11-05',
            suggestions=[dict(han_ids=[han['segment_id']],viet_ids=[viet['segment_id']],alignment_type='1-1',score=.9)]*2)
        response=page.request.post(f'{live_server}/api/suggestions/import?project_id={project}',multipart={
            'file':{'name':'suggestions.json','mimeType':'application/json','buffer':json.dumps(payload).encode()}})
        assert response.ok,response.text()
        page.goto(f'{live_server}/qa/{project}');page.wait_for_selector('#pendingPairs .sample-row')
        assert page.locator('#pendingPairs .sample-row').count()==2
        page.locator('#pendingPairs .sample-row').first.get_by_role('button',name='Duyệt cặp').click()
        page.wait_for_function("document.querySelectorAll('#pendingPairs .sample-row').length===1")
        page.locator('#pendingPairs .sample-row').get_by_role('button',name='Duyệt cặp').click()
        page.wait_for_selector('#toastContainer [role=alert]')
        page.locator('#pendingPairs .sample-row').get_by_role('button',name='Từ chối gợi ý').click()
        page.wait_for_function("document.querySelectorAll('#pendingPairs .sample-row').length===0")
        page.goto(f'{live_server}/workspace/{project}')
        page.wait_for_selector('#hanColumn .segment-card')
        page.wait_for_function("document.querySelector('#alignProgressText').textContent.includes('1')")
        # Focus stays in a modal and returns to the invoking edit button.
        edit=page.locator('#hanColumn .segment-card').first.get_by_role('button',name='Sửa',exact=True)
        edit.click();page.wait_for_selector('#editSegmentModal:not(.hidden)')
        assert page.locator('#edit_seg_text').evaluate('(element)=>element===document.activeElement')
        page.keyboard.press('Escape');page.wait_for_selector('#editSegmentModal.hidden',state='attached')
        assert edit.evaluate('(element)=>element===document.activeElement')
        page.locator('#compactView').check();page.locator('#readingSize').fill('21')
        page.locator('#readingSize').dispatch_event('input')
        assert page.locator('#hanColumn .segment-text').first.evaluate('(e)=>getComputedStyle(e).fontSize')=='21px'
        artifacts=Path('artifacts/web-plan-ui');artifacts.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(artifacts/'workspace-desktop.png'))
        # Save a manual error, rescan, and navigate from the retained issue.
        page.goto(f'{live_server}/qa/{project}');page.wait_for_selector('#sampleRows .sample-row')
        row=page.locator('#sampleRows .sample-row').first
        row.locator('select[name=outcome]').select_option('error')
        row.locator('input[value=OMISSION]').check();row.locator('button').click()
        page.wait_for_function("document.querySelector('#qaSummary').textContent.includes('100%')")
        page.locator('#scanQa').click()
        page.wait_for_selector('#issuesTableBody tr:has-text("manual_review")')
        page.locator('#issuesTableBody tr:has-text("manual_review") a').click()
        page.wait_for_selector('.qa-target')
        assert page.locator('header nav [aria-current=page]').inner_text()=='Dóng Hàng'
        for width,height in [(1366,768),(390,844)]:
            page.set_viewport_size({'width':width,'height':height})
            for path in [f'/workspace/{project}',f'/clean/{project}',f'/qa/{project}',f'/sources/{project}',f'/export/{project}']:
                response=page.goto(live_server+path);assert response.ok
                page.wait_for_timeout(200)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(width,path,page.evaluate('document.documentElement.scrollWidth'))
                assert page.locator('header nav [aria-current=page]').count()==1
            page.goto(f'{live_server}/workspace/{project}');page.wait_for_selector('.segment-card')
            page.screenshot(path=str(artifacts/f'workspace-{width}.png'))
        page.goto(f'{live_server}/export/{project}')
        page.wait_for_selector('#deliveryChecklist .checklist-row')
        assert 'còn điều kiện' in page.locator('#deliveryChecklist').inner_text()
        assert not forbidden,forbidden
        assert not errors,errors
        browser.close()
