import os
from pathlib import Path
import sys

import pytest

from OCR.utils.notebook_process import run_logged_process
from OCR.utils.notebook_process import NotebookProgress, PROGRESS_PREFIX
import json


def test_child_stdout_and_stderr_are_visible_and_saved(tmp_path, capsys):
    log = tmp_path / 'ocr.log'
    result = run_logged_process(
        [sys.executable, '-u', '-c',
         "import sys; print('model loading'); print('diagnostic on stderr', file=sys.stderr)"],
        cwd=tmp_path, env=dict(os.environ), log_path=log)
    assert result.returncode == 0
    visible = capsys.readouterr().out
    for message in ('model loading', 'diagnostic on stderr'):
        assert message in visible
        assert message in log.read_text(encoding='utf-8')


def test_failure_surfaces_original_traceback(tmp_path, capsys):
    log = tmp_path / 'ocr.log'
    with pytest.raises(RuntimeError) as error:
        run_logged_process([sys.executable, '-u', '-c',
                            "raise ValueError('original OCR failure')"],
                           cwd=tmp_path, env=dict(os.environ), log_path=log)
    assert 'ValueError: original OCR failure' in str(error.value)
    assert str(log.resolve()) in str(error.value)
    assert 'Traceback' in capsys.readouterr().out
    assert 'ValueError: original OCR failure' in log.read_text(encoding='utf-8')


def test_failure_before_runner_import_is_visible(tmp_path):
    with pytest.raises(RuntimeError, match='No module named'):
        run_logged_process([sys.executable, '-u', '-m', 'nonexistent_ocr_module_for_test'],
                           cwd=tmp_path, env=dict(os.environ), log_path=tmp_path / 'ocr.log')


def test_empty_failure_still_reports_exit_code(tmp_path):
    with pytest.raises(RuntimeError, match='23'):
        run_logged_process([sys.executable, '-c', 'import sys; sys.exit(23)'],
                           cwd=tmp_path, env=dict(os.environ), log_path=tmp_path / 'ocr.log')


def event(name, **values):
    return PROGRESS_PREFIX + json.dumps(dict(event=name, **values))


def test_dashboard_counts_selected_range_and_keeps_review_separate():
    frames = []
    dashboard = NotebookProgress(render=frames.append, clock=lambda: 0)
    dashboard.accept(event('start', total=3))
    dashboard.accept(event('page_done', page=21, total=3, processed=1, cached=1))
    markup = dashboard.as_html()
    assert '33.3%' in markup and '1/3 trang' in markup
    dashboard.accept(event('region_error', page=22, region=[0, 0, 20, 30]))
    dashboard.accept(event('region_error', page=22, region=[20, 0, 40, 30]))
    assert dashboard.state['review_pages'] == 1
    assert dashboard.state['error_regions'] == 2
    dashboard.accept(event('finish', total=3, processed=3, cached=1, complete=False))
    assert '100.0%' in frames[-1]
    assert 'còn vùng cần kiểm tra' in frames[-1]
    assert dashboard.state['outcome'] == 'needs_review'


def test_dashboard_failure_does_not_fake_completion_and_escapes_text():
    dashboard = NotebookProgress(render=lambda markup: None, clock=lambda: 0)
    dashboard.accept(event('start', total=10))
    dashboard.accept(event('region_start', page=1, region='<script>alert(1)</script>'))
    dashboard.finish('failed')
    markup = dashboard.as_html()
    assert '0.0%' in markup
    assert '<script>' not in markup and '&lt;script&gt;' in markup
    assert 'dừng vì lỗi' in markup
    assert not dashboard.accept(PROGRESS_PREFIX + 'invalid json')
    assert not dashboard.accept(event('start', total='not a number'))


def test_dashboard_heartbeat_and_partial_result_from_real_worker(tmp_path, monkeypatch, capsys):
    import OCR.utils.notebook_process as module
    frames = []
    dashboard = NotebookProgress(render=frames.append)
    monkeypatch.setattr(module, 'NotebookProgress', lambda: dashboard)
    script = "import time; print(" + repr(event('start', total=2)) + "); time.sleep(.8); print(" + repr(
        event('finish', total=2, processed=2, cached=0, review_pages=1, error_regions=1, complete=False)) + ")"
    run_logged_process([sys.executable, '-u', '-c', script], cwd=tmp_path,
                       env=dict(os.environ), log_path=tmp_path / 'ocr.log')
    assert len(frames) >= 3  # initial, heartbeat while quiet, final
    assert dashboard.state['outcome'] == 'needs_review'
    assert PROGRESS_PREFIX in (tmp_path / 'ocr.log').read_text(encoding='utf-8')
    assert PROGRESS_PREFIX not in capsys.readouterr().out


def test_display_failure_falls_back_without_killing_worker(tmp_path, monkeypatch):
    import OCR.utils.notebook_process as module
    def broken_display(markup):
        raise RuntimeError('display disconnected')
    dashboard = NotebookProgress(render=broken_display)
    monkeypatch.setattr(module, 'NotebookProgress', lambda: dashboard)
    result = run_logged_process([sys.executable, '-c', "print('OCR still runs')"],
                               cwd=tmp_path, env=dict(os.environ), log_path=tmp_path / 'ocr.log')
    assert result.returncode == 0


def test_real_notebook_receives_updated_dashboard(tmp_path):
    import nbformat
    from nbclient import NotebookClient
    worker = "print(" + repr(event('start', total=2)) + "); print(" + repr(
        event('finish', total=2, processed=2, cached=1, review_pages=1, error_regions=1, complete=False)) + ")"
    source = (
        "import sys, os\nfrom pathlib import Path\n"
        "from OCR.utils.notebook_process import run_logged_process\n"
        f"result = run_logged_process([sys.executable, '-u', '-c', {worker!r}], "
        f"cwd=Path.cwd(), env=dict(os.environ), log_path={str(tmp_path / 'notebook.log')!r})\n"
    )
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)])
    NotebookClient(notebook, timeout=30, kernel_name='python3').execute()
    markup = '\n'.join(output.get('data', {}).get('text/html', '') for output in notebook.cells[0].outputs)
    assert 'Tiến độ OCR' in markup
    assert '2/2 trang' in markup
    assert 'còn vùng cần kiểm tra' in markup
