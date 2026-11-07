"""Translation uses private test databases and mocked Azure, never real credentials."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from sqlalchemy import delete
from Web.app.models import Segment, SegmentTranslation, Project
from Web.app.routers import translations as router
from Web.app.services import translation as service
from test_workspace_performance import workspace, browser_workspace, seed_workspace


def setup(workspace):
    client, factory, _ = workspace
    seed_workspace(factory, han_count=3, viet_count=3, pair_count=1)
    return client, factory


def test_cache_stale_edit_and_project_delete(workspace, monkeypatch):
    client, factory = setup(workspace)
    calls = []
    monkeypatch.setattr(router, 'translate_han', lambda text: calls.append(text) or 'Bản dịch tham khảo')
    url = '/api/translations/perf/han_0'
    first = client.post(url, json={'revision': 1})
    assert first.status_code == 200 and not first.json()['cached']
    assert first.json()['source_language'] == 'lzh'
    assert client.post(url, json={'revision': 1}).json()['cached']
    assert len(calls) == 1
    with factory() as db:
        segment = db.get(Segment, 'han_0')
        assert segment.clean_text == calls[0] and segment.revision == 1
        segment.clean_text = '新文字。'; segment.revision = 2; db.commit()
    assert client.post(url, json={'revision': 1}).status_code == 409
    assert not client.post(url, json={'revision': 2}).json()['cached']
    assert len(calls) == 2
    assert client.get('/api/alignments', params={'project_id':'perf'}).json()[0]['status'] == 'confirmed'
    with factory() as db:
        assert db.query(SegmentTranslation).count() == 2
        db.execute(delete(Project).where(Project.id == 'perf')); db.commit()
        assert db.query(SegmentTranslation).count() == 0


def test_reject_wrong_side_scope_inactive_and_large_text(workspace, monkeypatch):
    client, factory = setup(workspace)
    def unexpected(_): pytest.fail('Must not call Azure')
    monkeypatch.setattr(router, 'translate_han', unexpected)
    for path, status in [('perf/viet_0',400), ('other/han_0',404), ('perf/missing',404)]:
        assert client.post('/api/translations/' + path, json={'revision':1}).status_code == status
    with factory() as db:
        db.get(Segment, 'han_0').active = False
        db.get(Segment, 'han_1').clean_text = '漢' * 5001
        db.get(Segment, 'han_2').clean_text = '  '
        db.commit()
    for index, status in [(0,404), (1,400), (2,400)]:
        assert client.post(f'/api/translations/perf/han_{index}', json={'revision':1}).status_code == status
    assert client.post('/api/translations/perf/han_1', json={'revision':1},
                       headers={'Origin':'https://other.example'}).status_code == 403


def test_edit_during_translation_is_not_cached(workspace, monkeypatch):
    client, factory = setup(workspace)
    def change_during_call(text):
        with factory() as db:
            segment = db.get(Segment, 'han_0'); segment.revision = 2
            segment.clean_text = '已修改。'; db.commit()
        return 'Old translation'
    monkeypatch.setattr(router, 'translate_han', change_during_call)
    assert client.post('/api/translations/perf/han_0', json={'revision':1}).status_code == 409
    with factory() as db:
        assert db.query(SegmentTranslation).count() == 0


def test_duplicate_requests_share_cached_result(workspace, monkeypatch):
    client, factory = setup(workspace)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def translate(text):
        calls.append(text); entered.set(); assert release.wait(10)
        return 'Dịch'
    monkeypatch.setattr(router, 'translate_han', translate)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, '/api/translations/perf/han_0', json={'revision':1})
        assert entered.wait(10)
        second = pool.submit(client.post, '/api/translations/perf/han_0', json={'revision':1})
        release.set()
        responses = [first.result(), second.result()]
    assert [r.status_code for r in responses] == [200,200]
    assert sorted(r.json()['cached'] for r in responses) == [False,True]
    assert len(calls) == 1


def azure_transport(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr(service.httpx, 'Client', lambda **kwargs:
        real_client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setenv('AZURE_TRANSLATOR_KEY', 'test-secret-key')
    monkeypatch.setenv('AZURE_TRANSLATOR_REGION', 'eastasia')
    monkeypatch.setenv('AZURE_TRANSLATOR_ENDPOINT', service.ENDPOINT)


def test_azure_request_contract(workspace, monkeypatch):
    client, factory = setup(workspace)
    def handler(request):
        assert request.url.host == 'api.cognitive.microsofttranslator.com'
        assert dict(request.url.params) == {'api-version':'3.0', 'from':'lzh', 'to':'vi', 'textType':'plain'}
        assert request.headers['Ocp-Apim-Subscription-Region'] == 'eastasia'
        assert request.headers['Ocp-Apim-Subscription-Key'] == 'test-secret-key'
        assert json.loads(request.content) == [{'Text':'古籍漢字第0段。'}]
        return httpx.Response(200, json=[{'translations':[{'to':'vi','text':'Văn bản Việt'}]}])
    azure_transport(monkeypatch, handler)
    response = client.post('/api/translations/perf/han_0', json={'revision':1})
    assert response.status_code == 200 and response.json()['translated_text'] == 'Văn bản Việt'
    assert 'test-secret-key' not in response.text


@pytest.mark.parametrize('status,body,expected', [(401,{},502),(403,{},502),(429,{},429),
    (500,{},502),(200,[],502),(200,[{'translations':[{'to':'vi','text':''}]}],502)])
def test_provider_errors_not_cached_or_leaked(workspace, monkeypatch, status, body, expected):
    client, factory = setup(workspace)
    azure_transport(monkeypatch, lambda request: httpx.Response(status, json=body))
    response = client.post('/api/translations/perf/han_0', json={'revision':1})
    assert response.status_code == expected and 'test-secret-key' not in response.text
    with factory() as db:
        assert db.query(SegmentTranslation).count() == 0


def test_missing_configuration_and_timeout(workspace, monkeypatch):
    client, factory = setup(workspace)
    monkeypatch.delenv('AZURE_TRANSLATOR_KEY', raising=False)
    assert client.post('/api/translations/perf/han_0', json={'revision':1}).status_code == 503
    def timeout(request): raise httpx.ReadTimeout('test-secret-key', request=request)
    azure_transport(monkeypatch, timeout)
    response = client.post('/api/translations/perf/han_0', json={'revision':1})
    assert response.status_code == 504 and 'test-secret-key' not in response.text
    monkeypatch.setenv('AZURE_TRANSLATOR_ENDPOINT', 'https://untrusted.example')
    assert client.post('/api/translations/perf/han_0', json={'revision':1}).status_code == 503


def test_translation_ui_cache_and_selection(browser_workspace, monkeypatch):
    from playwright.sync_api import expect
    browser, base, client, factory = browser_workspace
    seed_workspace(factory, han_count=110, viet_count=110, pair_count=0)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def translate(text):
        calls.append(text); entered.set(); assert release.wait(10)
        return '<img src=x onerror="window.translationXss=true"> Bản dịch Việt'
    monkeypatch.setattr(router, 'translate_han', translate)
    page = browser.new_page(viewport=dict(width=1366,height=900))
    page.goto(base + '/workspace/perf')
    expect(page.locator('#saveStatus')).to_have_text('Đã lưu DB')
    expect(page.locator('#vietColumn [data-translate-button]')).to_have_count(0)
    assert len(calls) == 0
    page.locator('#card_han_0 .segment-text').click()
    button = page.locator('#card_han_0 [data-translate-button]')
    panel = page.locator('#card_han_0 [data-translation-panel]')
    try:
        button.click()
        assert entered.wait(10)
        expect(button).to_be_disabled()
        expect(panel).to_contain_text('Đang gửi nội dung')
        # Other card selection stays responsive while the external call is pending.
        page.locator('#card_viet_0 .segment-text').click()
        expect(page.locator('#cardinalityBadge')).to_have_text('1–1')
    finally:
        release.set()
    expect(panel).to_contain_text('Bản dịch Việt')
    expect(panel.locator('img')).to_have_count(0)
    assert not page.evaluate('Boolean(window.translationXss)')
    assert page.evaluate('[...selectedHan]') == ['han_0']
    button.click(); expect(panel).to_be_hidden()
    button.click(); expect(panel).to_be_visible()
    page.locator('#hanPager').get_by_role('button', name='Sau', exact=True).click()
    page.locator('#hanPager').get_by_role('button', name='Trước', exact=True).click()
    expect(panel).to_contain_text('Bản dịch Việt')
    page.reload()
    expect(page.locator('#saveStatus')).to_have_text('Đã lưu DB')
    button.click(); expect(panel).to_contain_text('Đã lấy từ bản lưu')
    assert len(calls) == 1
    page.set_viewport_size(dict(width=390,height=844))
    expect(button).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    directory = Path('artifacts/translations'); directory.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(directory / 'mobile.png'))
    page.close()


def test_ui_retry_and_edit_discards_old_translation(browser_workspace, monkeypatch):
    from playwright.sync_api import expect
    from fastapi import HTTPException
    browser, base, client, factory = browser_workspace
    seed_workspace(factory, han_count=2, viet_count=2, pair_count=0)
    calls = []
    def translate(text):
        calls.append(text)
        if len(calls) == 1:
            raise HTTPException(429, 'Azure hết hạn mức thử nghiệm')
        return 'Bản dịch: ' + text
    monkeypatch.setattr(router, 'translate_han', translate)
    page = browser.new_page(viewport=dict(width=1366,height=900))
    page.goto(base + '/workspace/perf')
    expect(page.locator('#saveStatus')).to_have_text('Đã lưu DB')
    button = page.locator('#card_han_0 [data-translate-button]')
    panel = page.locator('#card_han_0 [data-translation-panel]')
    button.click()
    expect(panel).to_contain_text('Azure hết hạn mức')
    expect(button).to_have_text('Thử dịch lại')
    button.click()
    expect(panel).to_contain_text('Bản dịch: 古籍漢字第0段。')
    with factory() as db:
        seg = db.get(Segment, 'han_0'); seg.clean_text = '新文字。'; seg.revision = 2; db.commit()
    page.evaluate('loadWorkspaceData()')
    expect(page.locator('#card_han_0 .segment-text')).to_have_text('新文字。')
    expect(panel).to_be_hidden()
    expect(button).to_have_text('Dịch tham khảo')
    button.click()
    expect(panel).to_contain_text('Bản dịch: 新文字。')
    assert len(calls) == 3
    directory = Path('artifacts/translations'); directory.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(directory / 'desktop.png'))
    page.close()
