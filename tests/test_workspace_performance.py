"""Large workspace regressions, bounded DOM, batched reads and real browser timings."""
import json
import socket
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, insert
from sqlalchemy.orm import sessionmaker

from Web.app.db import Base, get_db
from Web.app.main import app
from Web.app.models import Project, Task, Document, Segment, Alignment, AlignmentMember


@pytest.fixture
def workspace(tmp_path):
    engine = create_engine(f'sqlite:///{(tmp_path / "workspace.db").as_posix()}',
                           connect_args={'check_same_thread': False})
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, record): connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    def override():
        with factory() as db: yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, factory, engine
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def seed_workspace(factory, han_count=1000, viet_count=5000, pair_count=50):
    with factory() as db:
        db.execute(insert(Project), [dict(id='perf', name='Kiểm thử dữ liệu lớn')])
        db.execute(insert(Task), [dict(id='task', project_id='perf', target_count=2000)])
        db.execute(insert(Document), [dict(id=side, project_id='perf', language=side,
            raw_sha256='a' * 64, clean_sha256='b' * 64, raw_bytes=b'snapshot') for side in ('han', 'viet')])
        for side, count in [('han', han_count), ('viet', viet_count)]:
            db.execute(insert(Segment), [dict(id=f'{side}_{i}', document_id=side, project_id='perf',
                language=side, order_index=i, raw_text=f'Raw {i}',
                clean_text=f'古籍漢字第{i}段。' if side == 'han' else f'Tiếng Việt: Nguyễn, Trường, dòng {i}.',
                page_ref=str(i // 50 + 1)) for i in range(count)])
        if pair_count:
            db.execute(insert(Alignment), [dict(id=f'pair_{i}', project_id='perf', status='confirmed',
                alignment_type='1-1', task_id='task') for i in range(pair_count)])
            db.execute(insert(AlignmentMember), [dict(alignment_id=f'pair_{i}', segment_id=f'{side}_{i}',
                side=side, position=0) for i in range(pair_count) for side in ('han', 'viet')])
        db.commit()


@pytest.fixture
def browser_workspace(workspace):
    import uvicorn
    from playwright.sync_api import sync_playwright
    client, factory, engine = workspace
    sock = socket.socket(); sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started: break
            time.sleep(.05)
        assert server.started
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='chrome', headless=True)
            yield browser, f'http://127.0.0.1:{port}', client, factory
            browser.close()
    finally:
        server.should_exit = True; thread.join(timeout=5); sock.close()


def test_workspace_and_alignment_lists_use_constant_query_counts(workspace):
    client, factory, engine = workspace
    seed_workspace(factory, pair_count=500)
    queries = []
    def count(*args): queries.append(args[2])
    event.listen(engine, 'before_cursor_execute', count)
    try:
        response = client.get('/api/workspace/perf')
        assert response.status_code == 200
        assert len(queries) <= 4, len(queries)
        snapshot = response.json()
        assert len(snapshot['segments']) == 6000 and len(snapshot['alignments']) == 500
        assert all('raw_text' not in seg for seg in snapshot['segments'])
        assert snapshot['segments'][0]['alignment_status'] == 'confirmed'
        queries.clear()
        pairs = client.get('/api/alignments', params={'project_id': 'perf'})
        assert pairs.status_code == 200 and len(pairs.json()) == 500
        assert len(queries) <= 2, len(queries)
        assert pairs.json()[0]['han_segments'][0]['raw_text']
        assert client.get('/api/workspace/missing').status_code == 404
    finally:
        event.remove(engine, 'before_cursor_execute', count)


def test_compact_snapshot_preserves_status_precedence_and_active_rows(workspace):
    client, factory, _ = workspace
    seed_workspace(factory, han_count=12, viet_count=12, pair_count=1)
    with factory() as db:
        for index, status in enumerate(['draft', 'suggested', 'needs_review', 'rejected']):
            key = f'status_{index}'
            db.add(Alignment(id=key, project_id='perf', alignment_type='1-1', status=status))
            db.flush()
            for side in ('han', 'viet'):
                db.add(AlignmentMember(alignment_id=key, segment_id=f'{side}_{index+1}', side=side, position=0))
        db.get(Segment, 'han_11').active = False
        db.commit()
    expected = {s['id']: s for s in client.get('/api/segments', params={'project_id': 'perf'}).json()}
    actual = client.get('/api/workspace/perf').json()['segments']
    assert len(actual) == 23 and 'han_11' not in {s['id'] for s in actual}
    for segment in actual:
        assert segment == {key: expected[segment['id']][key] for key in segment}


def test_paging_search_qa_and_fast_confirmation(browser_workspace):
    from playwright.sync_api import expect
    browser, base, client, factory = browser_workspace
    seed_workspace(factory)
    with factory() as db:
        db.add(Alignment(id='fallback', project_id='perf', alignment_type='1-1', status='suggested'))
        db.flush()
        for side in ('han', 'viet'):
            db.add(AlignmentMember(alignment_id='fallback', segment_id=f'{side}_0', side=side, position=0))
        db.commit()
    page = browser.new_page(viewport=dict(width=1366, height=900))
    page.emulate_media(reduced_motion='reduce')
    reads, writes = [], []
    page.on('request', lambda request: (reads.append(request.url) if '/api/workspace/' in request.url else None,
        writes.append(request.url) if request.method == 'POST' and request.url.endswith('/api/alignments') else None))
    page.goto(base + '/workspace/perf')
    expect(page.locator('#saveStatus')).to_have_text('Đã lưu DB')
    artifacts = Path('artifacts/workspace-performance')
    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts / 'workspace-1366.png'))
    expect(page.locator('.segment-card')).to_have_count(200)
    expect(page.locator('#alignProgressText')).to_have_text('Đã xác nhận: 50 cặp')
    page.once('dialog', lambda dialog: dialog.accept())
    page.locator('#card_han_0 button[title="Hủy xác nhận dóng hàng của ô này"]').click()
    expect(page.locator('#alignProgressText')).to_have_text('Đã xác nhận: 49 cặp')
    expect(page.locator('#card_han_0')).to_contain_text('Gợi ý AI')
    page.locator('#card_han_99').click()
    page.locator('#card_viet_99').click()
    page.locator('#vietPager').get_by_role('button', name='Sau', exact=True).click()
    page.locator('#card_viet_100').click()
    expect(page.locator('#cardinalityBadge')).to_have_text('1–n')
    # The first POST is pending when the next selection is made and a second
    # confirmation is attempted. Only the first may be sent.
    page.evaluate("""() => {
      confirmAlignment();
      handleSegmentClick('han', segmentById.get('han_101'), false);
      handleSegmentClick('viet', segmentById.get('viet_101'), false);
      confirmAlignment();
    }""")
    expect(page.locator('#saveStatus')).to_have_text('Đã lưu DB')
    expect(page.locator('#alignProgressText')).to_have_text('Đã xác nhận: 50 cặp')
    assert len(writes) == 1 and len(reads) == 1
    assert page.evaluate('[...selectedHan]') == ['han_101']
    assert page.evaluate('[...selectedViet]') == ['viet_101']
    rows = client.get('/api/alignments', params={'project_id': 'perf'}).json()
    created = next(p for p in rows if p['alignment_type'] == '1-n')
    assert [s['id'] for s in created['viet_segments']] == ['viet_99', 'viet_100']
    page.locator("button:has-text('Hoàn tác')").click()
    expect(page.locator('#alignProgressText')).to_have_text('Đã xác nhận: 49 cặp')
    assert len(reads) == 1
    page.locator('#vietPager input').fill('4321')
    page.locator('#vietPager').get_by_role('button', name='Đến', exact=True).click()
    expect(page.locator('#card_viet_4321')).to_be_focused()
    page.locator('#card_viet_4321 .segment-text').dblclick()
    expect(page.locator('#edit_seg_text')).to_have_value('Tiếng Việt: Nguyễn, Trường, dòng 4321.')
    page.keyboard.press('Escape')
    page.locator('#searchInput').fill('dòng 4999.')
    expect(page.locator('#card_viet_4999')).to_be_visible()
    expect(page.locator('#vietColumn .segment-card')).to_have_count(1)
    page.goto(base + '/workspace/perf?segment=viet_4200')
    expect(page.locator('#card_viet_4200')).to_have_class(__import__('re').compile('qa-target'))
    expect(page.locator('#card_viet_4200')).to_be_focused()
    page.set_viewport_size(dict(width=390, height=844))
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    for button in page.locator('.workspace-selection-actions > button').all():
        box = button.bounding_box()
        if box:
            assert box['x'] >= 0 and box['x'] + box['width'] <= 390
    page.screenshot(path=str(artifacts / 'workspace-390.png'))
    page.close()


def test_browser_render_and_selection_benchmark(browser_workspace):
    from playwright.sync_api import expect
    browser, base, client, factory = browser_workspace
    seed_workspace(factory)
    results = {'segments': 6000}
    baseline = Path('artifacts/workspace-performance/baseline.js')
    for index, mode in enumerate(['before', 'after'] if baseline.exists() else ['after']):
        page = browser.new_page(viewport=dict(width=1366, height=900))
        page.emulate_media(reduced_motion='reduce')
        if mode == 'before':
            page.route('**/static/workspace.js', lambda route: route.fulfill(
                body=baseline.read_text(encoding='utf-8-sig'), content_type='application/javascript'))
        page.goto(base + '/workspace/perf')
        expect(page.locator('#saveStatus')).to_have_text('Đã lưu DB', timeout=60000)
        page.evaluate('document.fonts.ready')
        results[mode] = page.evaluate("""async () => {
          const start = performance.now(); renderColumns();
          void document.getElementById('hanColumn').scrollHeight;
          const renderMs = performance.now() - start;
          const samples = [];
          for(let i=0;i<3;i++) {
            const t = performance.now(); handleSegmentClick('han',hanSegments[0],false);
            await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
            samples.push(performance.now()-t);
          }
          return {render_ms:renderMs, selection_ms:Math.min(...samples),
                  cards:document.querySelectorAll('.segment-card').length};
        }""")
        results[mode]['confirm_ms'] = page.evaluate("""async index => {
          clearSelection();
          handleSegmentClick('han',hanSegments[index],false);
          handleSegmentClick('viet',vietSegments[index],false);
          const start = performance.now(); await confirmAlignment();
          if(hanSegments[index].alignment_status !== 'confirmed') throw new Error('Confirmation failed');
          return performance.now()-start;
        }""", 100 + index)
        page.close()
    assert results['after']['cards'] <= 200
    if 'before' in results:
        assert results['after']['render_ms'] < results['before']['render_ms']
    destination = Path('artifacts/workspace-performance/timings.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(results, indent=2), encoding='utf-8')


def test_25000_segments_keep_dom_bounded(browser_workspace):
    from playwright.sync_api import expect
    browser, base, client, factory = browser_workspace
    seed_workspace(factory, han_count=2213, viet_count=23479)
    page = browser.new_page(viewport=dict(width=1366, height=900))
    page.goto(base + '/workspace/perf')
    expect(page.locator('#saveStatus')).to_have_text('Đã lưu DB', timeout=30000)
    expect(page.locator('.segment-card')).to_have_count(200)
    expect(page.locator('#vietPager')).to_contain_text('/ 23479 ô')
    page.locator('#vietPager input').fill('23478')
    page.locator('#vietPager').get_by_role('button', name='Đến', exact=True).click()
    expect(page.locator('#card_viet_23478')).to_be_focused()
    assert page.locator('.segment-card').count() <= 200
    page.close()


def test_native_click_feedback_with_normal_motion(browser_workspace):
    from playwright.sync_api import expect
    browser, base, client, factory = browser_workspace
    seed_workspace(factory, han_count=2213, viet_count=23479)
    page = browser.new_page(viewport=dict(width=1366, height=900), reduced_motion='no-preference')
    page.goto(base + '/workspace/perf')
    expect(page.locator('#saveStatus')).to_have_text('Đã lưu DB', timeout=30000)
    page.evaluate("""() => {
      window.clickFeedback = [];
      window.originalCard = document.getElementById('card_han_0');
      document.addEventListener('click', event => {
        const card = event.target.closest('.segment-card');
        if (!card) return;
        const start = performance.now();
        const sample = {id:card.id};
        clickFeedback.push(sample);
        requestAnimationFrame(() => {
          sample.frame_ms = performance.now() - start;
          sample.selected = card.dataset.selected;
          sample.duration = getComputedStyle(card).transitionDuration;
          sample.animations = card.getAnimations().map(a => ({
            property:a.transitionProperty, duration:a.effect.getTiming().duration}));
        });
      }, true);
    }""")
    page.locator('#card_han_0 .segment-text').click()
    expect(page.locator('#card_han_0')).to_have_attribute('data-selected', 'true')
    page.wait_for_function('clickFeedback.length && clickFeedback[0].duration !== undefined')
    sample = page.evaluate('clickFeedback[0]')
    destination = Path('artifacts/workspace-performance/native-click.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(sample, indent=2), encoding='utf-8')
    assert sample['selected'] == 'true'
    assert sample['duration'] == '0s'
    assert sample['animations'] == []
    assert page.evaluate("originalCard === document.getElementById('card_han_0')")
    # Choosing another card must not rewrite the previously selected card.
    page.evaluate("""() => {
      window.previousCardChanges = [];
      window.selectionObserver = new MutationObserver(changes => previousCardChanges.push(...changes));
      selectionObserver.observe(originalCard, {attributes:true});
    }""")
    page.locator('#card_viet_0 .segment-text').click()
    expect(page.locator('#cardinalityBadge')).to_have_text('1–1')
    assert page.evaluate('previousCardChanges.length') == 0
    page.evaluate('selectionObserver.disconnect()')
    # Native double click still restores the selection that preceded editing.
    page.locator('#card_han_1 .segment-text').dblclick()
    expect(page.locator('#editSegmentModal')).to_be_visible()
    assert page.evaluate('[...selectedHan]') == ['han_0']
    page.keyboard.press('Escape')
    expect(page.locator('#editSegmentModal')).to_be_hidden()
    page.locator('#card_han_0 .segment-text').click()
    expect(page.locator('#card_han_0')).to_have_attribute('data-selected', 'false')
    assert page.evaluate('selectedViet.has("viet_0")')
    page.close()
