import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from PIL import Image
from OCR.batch_runner import build_jobs, resolve_inputs, run_batch
from OCR.han_runner import run as run_han
from OCR.viet_runner import run as run_viet
from test_han_portable import RecordingEngine, configuration


@pytest.mark.parametrize('kind', ['han', 'viet'])
def test_batch_pdf_names_collisions_failure_and_resume(tmp_path, kind):
    paths = []
    for folder in ('first','last'):
        destination = tmp_path / folder / 'Quyển 1.pdf'
        destination.parent.mkdir()
        destination.write_bytes(Path('tests/fixtures/sample_text.pdf').read_bytes())
        paths.append(str(destination))
    broken = tmp_path / 'broken.pdf'; broken.write_bytes(b'not a PDF')
    paths.insert(1,str(broken))
    settings = configuration(tmp_path, Path(paths[0]))
    settings.update(input_paths=paths, input_mode='text', device='cpu')
    engine = RecordingEngine()
    def execute(job, config_file):
        assert json.loads(config_file.read_text(encoding='utf-8')) == job
        (run_han(job, engine) if kind == 'han' else run_viet(job))
    report = run_batch(settings, kind, execute)
    assert not report['complete']
    assert [j['status'] for j in report['jobs']] == ['complete','failed','complete']
    assert report['jobs'][0]['folder'] != report['jobs'][2]['folder']
    for item in (report['jobs'][0],report['jobs'][2]):
        assert item['text_file'] == 'Quyển 1.txt'
        assert (Path(item['output_dir']) / item['text_file']).exists()
    with zipfile.ZipFile(Path(settings['output_dir']) / 'batch_ocr.zip') as archive:
        assert 'batch_report.json' in archive.namelist()
        assert sum(n.endswith('/Quyển 1.txt') for n in archive.namelist()) == 2
    calls = engine.calls
    resumed = run_batch(settings, kind, execute)
    assert engine.calls == calls
    assert [j['folder'] for j in resumed['jobs']] == [j['folder'] for j in report['jobs']]
    for _, job in build_jobs(settings):
        assert job['checkpoint_dir'].startswith(job['output_dir'])


def test_batch_cli_text_pdf_needs_no_ocr_model(tmp_path):
    settings = dict(input_paths=[str(Path('tests/fixtures/sample_text.pdf').resolve())],
                    output_dir=str(tmp_path / 'out'), input_mode='text', device='cpu')
    config = tmp_path / 'config.json'; config.write_text(json.dumps(settings),encoding='utf-8')
    result = subprocess.run([sys.executable,'-m','OCR.batch_runner','--kind','viet','--config',str(config)],
                            capture_output=True,encoding='utf-8',errors='replace',timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((tmp_path / 'out/batch_report.json').read_text(encoding='utf-8'))
    assert report['complete'] and report['jobs'][0]['text_file'] == 'sample_text.txt'


@pytest.mark.parametrize('value', [[], '', ['missing.pdf'], ['a.png']])
def test_invalid_batch_inputs_fail_before_processing(value):
    with pytest.raises(ValueError): resolve_inputs(value)


def test_duplicate_paths_and_custom_checkpoint_root(tmp_path):
    path = tmp_path / 'a.pdf'; path.write_bytes(b'placeholder')
    with pytest.raises(ValueError): resolve_inputs([str(path),str(path)])
    settings = dict(input_paths=[str(path)],output_dir=str(tmp_path/'out'),checkpoint_dir=str(tmp_path/'cache'))
    assert Path(build_jobs(settings)[0][1]['checkpoint_dir']).parent == tmp_path/'cache'


def test_partial_line_keeps_text_image_and_never_caches(tmp_path):
    path = tmp_path / 'scan.png'; Image.new('RGB',(80,40),'white').save(path)
    output = tmp_path/'output'
    class Engine:
        info = dict(engine_type='contract', is_mock=False)
        def recognize_image(self, image):
            saved = output/'needs_review/line.png'; saved.parent.mkdir(parents=True,exist_ok=True)
            image.save(saved)
            return dict(boxes=[dict(text='Dòng đã đọc được',confidence=.9,bbox=[0,0,40,20])],
                        errors=[dict(image='needs_review/line.png',line_index=1,
                                     failures=[dict(error='token_limit')])])
    settings = dict(input_path=str(path),output_dir=str(output),device='cpu',text_basename='Sách Việt')
    result = run_viet(settings, Engine())
    assert not result['complete'] and result['pages'][0]['status'] == 'partial'
    assert result['pages'][0]['needs_review'] and result['full_text'] == 'Dòng đã đọc được'
    assert result['text_file'] == 'Sách Việt.partial.txt'
    assert len(result['errors']) == 1
    assert not list((output/'checkpoints').glob('*.json'))
    assert not (output/'Sách Việt.txt').exists()
    with zipfile.ZipFile(output/'viet_ocr.zip') as archive:
        assert 'needs_review/line.png' in archive.namelist()
        assert archive.read(result['text_file']).decode() == result['full_text']


def test_partial_page_keeps_worker_alive_for_next_page(tmp_path, monkeypatch):
    import OCR.viet_runner as runner
    path = tmp_path/'pages.tiff'
    Image.new('RGB',(80,40),'white').save(path,save_all=True,
        append_images=[Image.new('RGB',(80,40),'black')])
    workers = []
    class Worker:
        info = dict(engine_type='contract',is_mock=False)
        def __init__(self, settings):
            self.calls = self.closed = 0; workers.append(self)
        def recognize_image(self, image):
            self.calls += 1
            boxes = [dict(text='Đọc được',confidence=.9)]
            return dict(boxes=boxes,errors=[dict(error='token_limit')]) if self.calls==1 else boxes
        def close(self): self.closed += 1
    monkeypatch.setattr(runner,'WorkerEngine',Worker)
    result = runner.run(dict(input_path=str(path),output_dir=str(tmp_path/'out'),device='cpu'))
    assert [p['status'] for p in result['pages']]==['partial','complete']
    assert len(workers)==1 and workers[0].calls==2 and workers[0].closed==1


def test_batch_interrupt_stops_worker_process_group(monkeypatch):
    import os
    import signal
    from types import SimpleNamespace
    import OCR.batch_runner as batch
    signals, options = [], []
    class Process:
        pid = 123456
        waits = 0
        def poll(self): return None
        def wait(self, **kwargs):
            self.waits += 1
            if self.waits == 1: raise KeyboardInterrupt()
            return 0
    process = Process()
    def popen(command, **kwargs): options.append(kwargs); return process
    monkeypatch.setattr(batch.subprocess,'Popen',popen)
    monkeypatch.setattr(batch,'os',SimpleNamespace(name='posix',environ=os.environ,
        killpg=lambda pid,sig: signals.append((pid,sig))))
    # SIGKILL is not defined on Windows; the fake OS still exercises POSIX cleanup.
    monkeypatch.setattr(batch.signal,'SIGKILL',9,raising=False)
    with pytest.raises(KeyboardInterrupt): batch.run_child(['worker'])
    assert options[0]['start_new_session'] is True
    assert signals == [(process.pid,signal.SIGTERM),(process.pid,9)]
