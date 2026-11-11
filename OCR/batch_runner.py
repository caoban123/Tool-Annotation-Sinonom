"""Sequential multi-PDF jobs with independent outputs/cache and a resumable report."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import signal


def resolve_inputs(paths):
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) or not p.strip() for p in paths):
        raise ValueError('BATCH_MODE=True cần INPUT_PATHS là list đường dẫn PDF không rỗng')
    result = [Path(p).expanduser().resolve() for p in paths]
    if len(set(result)) != len(result):
        raise ValueError('INPUT_PATHS có đường dẫn PDF trùng nhau')
    for path in result:
        if path.suffix.lower() != '.pdf' or not path.is_file():
            raise ValueError(f'Không tìm thấy PDF: {path}')
    return result


def text_basename(config, default):
    name = config.get('text_basename', default)
    if not isinstance(name, str) or not name or Path(name).name != name or '/' in name or '\\' in name or name in ('.', '..'):
        raise ValueError('text_basename phải là tên file không chứa đường dẫn')
    return name


def build_jobs(config):
    root = Path(config['output_dir']).resolve()
    jobs = []
    for path in resolve_inputs(config['input_paths']):
        key = path.stem[:90] + '-' + hashlib.sha256(str(path).encode()).hexdigest()[:10]
        job = dict(config, input_path=str(path), output_dir=str(root / key), text_basename=path.stem)
        job.pop('input_paths', None)
        cache_root = config.get('checkpoint_dir')
        job['checkpoint_dir'] = str(Path(cache_root) / key) if cache_root else str(root / key / 'checkpoints')
        jobs.append((key, job))
    return jobs


def run_child(command):
    process = subprocess.Popen(command, env=dict(os.environ, PYTHONIOENCODING='utf-8'),
                               start_new_session=os.name != 'nt')
    try:
        code = process.wait()
        if code: raise subprocess.CalledProcessError(code, command)
    finally:
        if process.poll() is None:
            if os.name != 'nt':
                # Paddle's worker and its Torch reader inherit this process group.
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: pass
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            else:
                try:
                    import psutil
                except ImportError:
                    pass
                else:
                    try:
                        for child in reversed(psutil.Process(process.pid).children(recursive=True)):
                            try: child.kill()
                            except psutil.NoSuchProcess: pass
                    except psutil.NoSuchProcess: pass
                if process.poll() is None: process.kill()
            process.wait()


def run_batch(config, kind, execute=None):
    if kind not in ('han', 'viet'): raise ValueError('kind must be han or viet')
    jobs = build_jobs(config)
    output = Path(config['output_dir']).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config_dir = output / 'job_configs'; config_dir.mkdir(exist_ok=True)
    report = dict(kind=kind, complete=False, jobs=[])
    report_path = output / 'batch_report.json'
    def save():
        temporary = report_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(report_path)
    def default_execute(job, config_file):
        run_child([sys.executable, '-u', '-m', f'OCR.{kind}_runner', '--config', str(config_file)])
    execute = execute or default_execute
    save()
    for index, (key, job) in enumerate(jobs, 1):
        print(f'[BATCH] PDF {index}/{len(jobs)}: {job["input_path"]}', flush=True)
        item = dict(input_path=job['input_path'], output_dir=job['output_dir'], folder=key, status='failed')
        config_file = config_dir / (key + '.json')
        config_file.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
        try:
            execute(job, config_file)
            metadata = json.loads((Path(job['output_dir']) / f'{kind}_metadata.json').read_text(encoding='utf-8'))
            item.update(status='complete' if metadata['complete'] else 'partial',
                        text_file=metadata['text_file'], total_pages=metadata['total_pages'])
        except Exception as error:
            item['error'] = str(error)
            print(f'[BATCH] File lỗi, tiếp tục file kế: {error}', flush=True)
        report['jobs'].append(item)
        save()
    report['complete'] = all(j['status'] == 'complete' for j in report['jobs'])
    save()
    with zipfile.ZipFile(output / 'batch_ocr.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(report_path, 'batch_report.json')
        for item in report['jobs']:
            if item['status'] == 'failed': continue
            with zipfile.ZipFile(Path(item['output_dir']) / f'{kind}_ocr.zip') as single:
                for member in single.namelist():
                    archive.writestr(item['folder'] + '/' + member, single.read(member))
    print(f'[BATCH] Xong {len(jobs)} PDF. Báo cáo: {report_path}', flush=True)
    return report


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    def interrupted(signum, frame): raise KeyboardInterrupt('Batch stopped')
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=['han', 'viet'], required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    run_batch(json.loads(Path(args.config).read_text(encoding='utf-8')), args.kind)
