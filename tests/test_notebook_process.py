import os
from pathlib import Path
import sys

import pytest

from OCR.utils.notebook_process import run_logged_process


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
