"""Pinned Paddle install with an official wheel fallback for hosted Linux notebooks."""
import argparse
import os
import platform
import sys
from pathlib import Path

from OCR.utils.notebook_process import run_logged_process

VERSION = '3.2.2'
PYPI = 'https://pypi.org/simple'


def install_commands(cuda, *, python=None, system=None, machine=None, python_version=None):
    if cuda not in ('cpu', 'cu118', 'cu126'):
        raise ValueError('Paddle runtime must be cpu, cu118 or cu126')
    python = str(python or sys.executable)
    runtime = 'paddlepaddle' if cuda == 'cpu' else 'paddlepaddle-gpu'
    base = [python, '-m', 'pip', 'install', '--disable-pip-version-check']
    commands = [base + ['--timeout', '30', '--retries', '2', runtime + '==' + VERSION,
                '--index-url', f'https://www.paddlepaddle.org.cn/packages/stable/{cuda}/']]
    system = system or platform.system()
    machine = machine or platform.machine()
    python_version = python_version or sys.version_info[:2]
    if system == 'Linux' and machine.lower() in ('x86_64', 'amd64') and tuple(python_version) == (3, 11):
        filename = f'{runtime.replace("-", "_")}-{VERSION}-cp311-cp311-linux_x86_64.whl'
        wheel = f'https://paddle-whl.bj.bcebos.com/stable/{cuda}/{runtime}/{filename}'
        # Only the runtime bypasses the index; its dependencies still come from PyPI.
        commands.append(base + ['--timeout', '120', '--retries', '5', wheel, '--index-url', PYPI])
    return commands


def install_paddle(cuda, log_dir, runner=run_logged_process):
    log_dir = Path(log_dir).resolve()
    commands = install_commands(cuda)
    failures = []
    for index, command in enumerate(commands):
        label = 'index' if index == 0 else 'official-wheel'
        print(f'[Paddle] {VERSION} / {cuda}: {label}', flush=True)
        if index:
            print('[Paddle] Kho index chưa cài được. Thử wheel cùng phiên bản/CUDA từ máy chủ Paddle; '
                  'wheel GPU cu126 khoảng 1,9 GB, cần chờ tải.', flush=True)
        try:
            runner(command, cwd=Path.cwd(), env=dict(os.environ),
                   log_path=log_dir / f'paddle_install.{label}.log', show_progress=False)
            return
        except RuntimeError as error:
            failures.append(str(error))
    raise RuntimeError('Không cài được Paddle. Chưa chạy OCR. Xem log paddle_install.*.log tại '
                       f'{log_dir}. Không tự đổi phiên bản, CUDA hay chuyển CPU.\n' + '\n'.join(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cuda', required=True, choices=['cpu', 'cu118', 'cu126'])
    parser.add_argument('--log-dir', required=True)
    args = parser.parse_args()
    install_paddle(args.cuda, args.log_dir)
