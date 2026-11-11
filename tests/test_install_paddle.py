from pathlib import Path
import pytest
from OCR.utils.install_paddle import install_commands, install_paddle, VERSION


@pytest.mark.parametrize('cuda,runtime', [('cpu','paddlepaddle'), ('cu118','paddlepaddle-gpu'), ('cu126','paddlepaddle-gpu')])
def test_official_fallback_matches_runtime_python_and_cuda(cuda, runtime):
    commands = install_commands(cuda, python='/env/bin/python', system='Linux', machine='x86_64', python_version=(3,11))
    assert len(commands) == 2
    first, fallback = commands
    assert runtime + '==' + VERSION in first
    assert f'https://www.paddlepaddle.org.cn/packages/stable/{cuda}/' in first
    assert f'https://paddle-whl.bj.bcebos.com/stable/{cuda}/{runtime}/{runtime.replace("-","_")}-{VERSION}-cp311-cp311-linux_x86_64.whl' in fallback
    assert fallback[:4] == ['/env/bin/python','-m','pip','install']
    assert fallback[-2:] == ['--index-url','https://pypi.org/simple']
    assert '--retries' in first and '--retries' in fallback


@pytest.mark.parametrize('system,machine,version', [('Windows','AMD64',(3,11)), ('Linux','aarch64',(3,11)), ('Linux','x86_64',(3,13))])
def test_no_incompatible_wheel_fallback(system, machine, version):
    assert len(install_commands('cu126', system=system, machine=machine, python_version=version)) == 1


def test_invalid_cuda_is_rejected():
    with pytest.raises(ValueError): install_commands('cu130')


@pytest.mark.parametrize('failures,expected', [(0,1),(1,2),(2,2)])
def test_retries_keep_original_diagnostics_and_never_switch_device(tmp_path, monkeypatch, failures, expected):
    import OCR.utils.install_paddle as module
    commands = install_commands('cu126', system='Linux', machine='x86_64', python_version=(3,11))
    monkeypatch.setattr(module, 'install_commands', lambda cuda: commands)
    calls = []
    def runner(command, **kwargs):
        calls.append((command, kwargs))
        if len(calls) <= failures:
            raise RuntimeError('original pip error ' + str(len(calls)))
    if failures == 2:
        with pytest.raises(RuntimeError, match='original pip error 1') as error:
            install_paddle('cu126', tmp_path, runner=runner)
        assert 'original pip error 2' in str(error.value)
    else:
        install_paddle('cu126', tmp_path, runner=runner)
    assert len(calls) == expected
    assert calls[0][1]['log_path'] == Path(tmp_path) / 'paddle_install.index.log'
    if expected == 2:
        assert calls[1][1]['log_path'] == Path(tmp_path) / 'paddle_install.official-wheel.log'


def test_interrupt_does_not_start_another_download(tmp_path, monkeypatch):
    import OCR.utils.install_paddle as module
    monkeypatch.setattr(module, 'install_commands', lambda cuda: [['first'], ['fallback']])
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt): install_paddle('cu126', tmp_path, runner=runner)
    assert calls == [['first']]
