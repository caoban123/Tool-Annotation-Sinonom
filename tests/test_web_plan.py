import hashlib
import io
import json
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from Web.app.db import Base, get_db
from Web.app.main import app
from Web.app.models import Project, Document, Segment, Alignment, QAIssue, QualityReview
from Web.app.migrations import migrate_database
from Web.app.services.quality import save_review, get_project_statistics
from Web.app.services.alignment import create_alignment


@pytest.fixture
def web(tmp_path):
    engine = create_engine(f'sqlite:///{(tmp_path / "web.sqlite").as_posix()}', connect_args={'check_same_thread': False})
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    def override():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def seed(client):
    project = client.post('/api/projects', json={'name': 'Plan regression', 'target_count': 1}).json()['id']
    raw_han = '𠀀甲。乙。'.encode()
    raw_viet = b'\xef\xbb\xbf' + 'Một.\r\nHai.'.encode()
    response = client.post(f'/api/projects/{project}/import', files={
        'han_file': ('han.txt', raw_han), 'viet_file': ('viet.txt', raw_viet)})
    assert response.status_code == 200, response.text
    segments = client.get('/api/segments', params={'project_id': project}).json()
    han = [s for s in segments if s['language'] == 'han']
    viet = [s for s in segments if s['language'] == 'viet']
    return project, han, viet, raw_han, raw_viet


def manifest(client, project, han, viet, pairs=1):
    source = client.get('/api/suggestions/export-segments', params={'project_id': project}).json()
    return dict(schema_version='1.0', project_id=project, task_id=source['task_id'],
        source_revision=source['revision'], source_sha256_han=source['source_sha256_han'],
        source_sha256_viet=source['source_sha256_viet'], model_name='test', model_version='1', created_at='2026-11-05',
        suggestions=[dict(han_ids=[han[0]['id']], viet_ids=[viet[0]['id']], alignment_type='1-1', score=.8)] * pairs)


def import_suggestions(client, project, payload):
    return client.post('/api/suggestions/import', params={'project_id': project}, files={'file': ('suggestions.json', json.dumps(payload).encode())})


@pytest.mark.parametrize('field,value', [('schema_version', '2'), ('source_revision', 0), ('source_revision', 9999),
    ('project_id', 'foreign'), ('source_sha256_han', '0' * 64), ('source_sha256_viet', None)])
def test_ai_rejects_invalid_or_stale_manifest(web, field, value):
    client, factory = web
    project, han, viet, *_ = seed(client)
    payload = manifest(client, project, han, viet)
    if value is None:
        payload.pop(field)
    else:
        payload[field] = value
    assert import_suggestions(client, project, payload).status_code == 400
    with factory() as db:
        assert db.query(Alignment).count() == 0


def test_concurrent_accept_and_stale_edit(web):
    client, factory = web
    project, han, viet, *_ = seed(client)
    response = import_suggestions(client, project, manifest(client, project, han, viet, pairs=2))
    assert response.json()['imported_suggestions_count'] == 2, response.text
    ids = [a['id'] for a in client.get('/api/alignments', params={'project_id': project}).json()]
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda key: client.post(f'/api/suggestions/{key}/accept').status_code, ids))
    assert sorted(codes) == [200, 409]
    with factory() as db:
        assert db.query(Alignment).filter_by(status='confirmed').count() == 1
    # Editing a source invalidates the still-suggested snapshot even after edits elsewhere.
    assert client.put(f"/api/segments/{han[1]['id']}", params={'project_id': project}, json={'clean_text': '改。'}).status_code == 200
    remaining = next(a['id'] for a in client.get('/api/alignments', params={'project_id': project}).json() if a['status'] == 'suggested')
    assert client.post(f'/api/suggestions/{remaining}/accept').status_code == 409


def test_partial_ai_import_reports_errors_without_half_rows(web):
    client, factory = web
    project, han, viet, *_ = seed(client)
    payload = manifest(client, project, han, viet)
    payload['suggestions'].append(dict(han_ids=['missing'], viet_ids=[viet[1]['id']], alignment_type='1-1', score=.5))
    response = import_suggestions(client, project, payload)
    assert response.status_code == 200
    assert response.json()['rejected_suggestions_count'] == 1
    assert response.json()['rejected'][0]['reason']
    with factory() as db:
        assert db.query(Alignment).count() == 1


def confirm(client, project, han, viet):
    response = client.post('/api/alignments', json=dict(project_id=project, han_segment_ids=[han['id']], viet_segment_ids=[viet['id']]))
    assert response.status_code == 200, response.text
    return response.json()['id']


def test_reviews_persist_ignore_notes_and_become_stale(web):
    client, factory = web
    project, han, viet, *_ = seed(client)
    alignment = confirm(client, project, han[0], viet[0])
    assert client.post(f'/api/qa/reviews/{alignment}', json=dict(outcome='error', error_codes=['OMISSION', 'ADDITION'], note='Manual finding')).status_code == 200
    with factory() as db:
        db.get(Alignment, alignment).notes = '[CHECKED_SOMETHING] [CHECKED_ERROR]'
        db.commit()
    client.post('/api/qa/scan', params={'project_id': project})
    stats = client.get(f'/api/projects/{project}/stats').json()
    assert (stats['checked_sample_size'], stats['checked_error_count'], stats['error_rate_pct']) == (1, 1, 100)
    issues = client.get('/api/qa', params={'project_id': project}).json()
    assert len([i for i in issues if i['origin'] == 'manual_review' and i['status'] == 'open']) == 2
    client.put(f"/api/segments/{han[0]['id']}", params={'project_id': project}, json={'clean_text': '修正。'})
    assert client.get(f'/api/projects/{project}/stats').json()['checked_sample_size'] == 0
    assert client.post(f'/api/alignments/{alignment}/confirm').status_code == 200
    assert client.get(f'/api/projects/{project}/stats').json()['checked_sample_size'] == 0
    assert not client.get('/api/qa/reviews', params={'project_id': project}).json()[0]['current']
    assert client.post(f'/api/qa/reviews/{alignment}', json=dict(outcome='correct', error_codes=[])).status_code == 200
    assert client.get(f'/api/projects/{project}/stats').json()['error_rate_pct'] == 0


def test_notes_alone_and_rejected_pairs_never_count_as_review(web):
    client, factory = web
    project, han, viet, *_ = seed(client)
    for index,status in enumerate(['confirmed','rejected']):
        response=client.post('/api/alignments',json=dict(project_id=project,
            han_segment_ids=[han[index]['id']],viet_segment_ids=[viet[index]['id']],
            status=status,notes='[CHECKED_SOMETHING] [CHECKED_ERROR] [CHECKED_VALID]'))
        assert response.status_code==200
    stats=client.get(f'/api/projects/{project}/stats').json()
    assert stats['checked_sample_size']==0 and stats['error_rate_pct'] is None


@pytest.mark.parametrize('errors,total,rate', [(0, 0, None), (2, 10, 20), (3, 10, 30), (4, 10, 40)])
def test_review_rates_use_valid_pairs_once(tmp_path, errors, total, rate):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        db.add(Project(id='p', name='Rates'))
        for i in range(total):
            db.add_all([Segment(id=f'h{i}',document_id='h',project_id='p',language='han',order_index=i,raw_text='甲',clean_text='甲'),
                        Segment(id=f'v{i}',document_id='v',project_id='p',language='viet',order_index=i,raw_text='Một',clean_text='Một')])
        db.flush()
        for i in range(total):
            alignment = create_alignment(db, 'p', [f'h{i}'], [f'v{i}'])
            save_review(db, alignment.id, 'error' if i < errors else 'correct', ['OMISSION', 'ADDITION'] if i < errors else [])
        db.commit()
        stats=get_project_statistics(db,'p')
        assert stats['checked_sample_size']==total and stats['checked_error_count']==errors
        assert stats['error_rate_pct']==rate
    engine.dispose()


def test_raw_snapshot_zip_metadata_and_merged_page_refs(web):
    client, factory = web
    project, han, viet, raw_han, raw_viet = seed(client)
    metadata = dict(complete=True, full_text=raw_han.decode(), pages=[dict(page_number=10,text='𠀀甲。'),dict(page_number=11,text='乙。')])
    response = client.post(f'/api/projects/{project}/metadata/han', files={'file': ('han_metadata.json',json.dumps(metadata).encode())})
    assert response.status_code==200, response.text
    assert client.get('/api/segments',params={'project_id':project,'language':'han'}).json()[0]['page_ref']=='10'
    merged=client.post('/api/segments/merge',params={'project_id':project},json={'segment_ids':[s['id'] for s in han]}).json()
    assert merged['page_ref']=='10,11'
    client.put(f"/api/segments/{merged['id']}",params={'project_id':project},json={'clean_text':'已修改。'})
    split=client.post('/api/segments/split',params={'project_id':project},json={'segment_id':merged['id'],'split_texts':['已。','修改。']})
    assert split.status_code==200,split.text
    assert client.delete(f"/api/segments/{split.json()[0]['id']}",params={'project_id':project}).status_code==200
    assert client.get('/api/exports/raw-text',params={'project_id':project,'language':'han'}).content==raw_han
    response=client.get('/api/exports/zip',params={'project_id':project})
    assert response.status_code==200,response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        raw=next(n for n in archive.namelist() if n.endswith('/02_ocr_tho/han/han_tho.txt'))
        assert archive.read(raw)==raw_han
        assert hashlib.sha256(archive.read(raw)).hexdigest()==hashlib.sha256(raw_han).hexdigest()
        manifest=json.loads(archive.read(next(n for n in archive.namelist() if n.endswith('task_manifest.json'))))
        assert set(manifest['exported_files'])==set(archive.namelist())
        assert not manifest['delivery_ready']
    assert client.get('/api/exports/zip',params={'project_id':project,'delivery':True}).status_code==400
    # Removing snapshots must never export the edited working version as raw.
    with factory() as db:
        doc=db.query(Document).filter_by(project_id=project,language='han',active=True).one();doc.raw_bytes=None;db.commit()
    assert client.get('/api/exports/raw-text',params={'project_id':project,'language':'han'}).status_code==404


def test_complete_delivery_and_source_file_roundtrip(web):
    client, factory = web
    project, han, viet, *_ = seed(client)
    for h,v in zip(han,viet):
        alignment=confirm(client,project,h,v)
        client.post(f'/api/qa/reviews/{alignment}',json={'outcome':'correct'})
    for language in ('han','viet'):
        assert client.put(f'/api/projects/{project}/sources/{language}',json=dict(title='Nguồn',filename='source.pdf',format='PDF',page_count=2,scope='Trang 1-2',tools='PaddleOCR')).status_code==200
    source=b'%PDF-source-example'
    assert client.post(f'/api/projects/{project}/sources/han/file',files={'file':('source.pdf',source)}).status_code==200
    checklist=client.get('/api/qa/checklist',params={'project_id':project}).json()
    assert checklist['ready'],checklist
    response=client.get('/api/exports/zip',params={'project_id':project,'delivery':True})
    assert response.status_code==200,response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.read(next(n for n in archive.namelist() if n.endswith('/01_nguon/han/source.pdf')))==source
        assert json.loads(archive.read(next(n for n in archive.namelist() if n.endswith('/reports/checklist.json'))))['ready']


def test_additive_migration_preserves_legacy_database(tmp_path):
    path=tmp_path/'old.sqlite'; engine=create_engine(f'sqlite:///{path.as_posix()}')
    Base.metadata.create_all(engine)
    raw=b'Original\r\ninput'; snapshot=tmp_path/'old_raw.txt';snapshot.write_bytes(raw)
    with sessionmaker(bind=engine)() as db:
        db.add(Project(id='legacy',name='Legacy'));db.flush()
        db.add(Document(id='doc',project_id='legacy',language='han',raw_sha256=hashlib.sha256(raw).hexdigest(),clean_sha256='x',provenance=json.dumps({'raw_storage_path':str(snapshot)})))
        db.flush();db.add(Segment(id='seg',document_id='doc',project_id='legacy',language='han',order_index=0,raw_text='Original',clean_text='Edited',page_ref='1'))
        db.add(QAIssue(id='issue',project_id='legacy',code='OMISSION',comment='Human finding'));db.commit()
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE quality_reviews'))
        for table, columns in {'documents':['raw_bytes','active','source_bytes','source_sha256'],'alignments':['suggestion_context'],'qa_issues':['origin']}.items():
            for column in columns:conn.execute(text(f'ALTER TABLE {table} DROP COLUMN {column}'))
    migrate_database(engine);migrate_database(engine)
    with sessionmaker(bind=engine)() as db:
        assert db.get(Document,'doc').raw_bytes==raw
        assert db.get(Segment,'seg').clean_text=='Edited' and db.get(Segment,'seg').page_ref==''
        assert db.get(QAIssue,'issue').origin=='legacy'
        assert db.query(QualityReview).count()==0
    backup=path.with_name(path.name+'.before-web-v2.bak')
    assert backup.exists()
    with sqlite3.connect(backup) as connection:
        assert 'raw_bytes' not in [row[1] for row in connection.execute('PRAGMA table_info(documents)')]
    engine.dispose()


def test_reimport_preserves_versions_and_rejects_bad_encoding_atomically(web):
    client,factory=web
    project,han,viet,raw_han,raw_viet=seed(client)
    confirm(client,project,han[0],viet[0])
    bad=client.post(f'/api/projects/{project}/import',files={'han_file':('han.txt',b'\xff'), 'viet_file':('viet.txt',b'Valid')})
    assert bad.status_code==400
    assert client.get('/api/exports/raw-text',params={'project_id':project,'language':'han'}).content==raw_han
    new_han='新。'.encode();new_viet='Mới.'.encode()
    response=client.post(f'/api/projects/{project}/import',files={'han_file':('han.txt',new_han),'viet_file':('viet.txt',new_viet)})
    assert response.status_code==200
    with factory() as db:
        assert db.query(Document).filter_by(project_id=project).count()==4
        assert db.query(Document).filter_by(project_id=project,active=False,language='han').one().raw_bytes==raw_han
    assert client.get('/api/exports/raw-text',params={'project_id':project,'language':'han'}).content==new_han
    assert client.get(f'/api/projects/{project}/stats').json()['confirmed_alignments']==0


def test_checklist_requires_each_task_target_not_just_total(web):
    client,factory=web
    project,han,viet,*_=seed(client)
    response=client.post(f'/api/projects/{project}/tasks',json=dict(assigned_to='Người B',scope='Phần B',target_count=1))
    assert response.status_code==200,response.text
    for h,v in zip(han,viet):
        confirm(client,project,h,v)  # Both assigned to the original task, second task is empty.
    checklist=client.get('/api/qa/checklist',params={'project_id':project}).json()
    conditions={c['code']:c['passed'] for c in checklist['conditions']}
    assert conditions['target'] and not conditions['task_targets']
