"""Run OCR workers with output visible in hosted notebook cells."""
from collections import deque
from pathlib import Path
import subprocess
import json
import time
import html
import queue
import threading

PROGRESS_PREFIX = '[OCR_PROGRESS] '


def emit_progress(event, **values):
    print(PROGRESS_PREFIX + json.dumps(dict(event=event, **values), ensure_ascii=False), flush=True)


class NotebookProgress:
    """A single notebook display updated in place, independent of the log stream."""
    def __init__(self, render=None, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.ended = None
        self.last_render = -1
        self.review_page_numbers = set()
        self.state = dict(total=0, processed=0, cached=0, review_pages=0,
                          error_regions=0, page=None, region=None,
                          status='Đang khởi động OCR…', outcome='running')
        self.render = render
        if render is None:
            try:
                from IPython import get_ipython
                from IPython.display import HTML, display
                if get_ipython() is not None:
                    handle = display(HTML(self.as_html()), display_id=True)
                    if handle is not None:
                        self.render = lambda markup: handle.update(HTML(markup))
            except ImportError:
                pass
        self.refresh(force=True)

    def accept(self, line):
        if not line.startswith(PROGRESS_PREFIX):
            return False
        try:
            event = json.loads(line[len(PROGRESS_PREFIX):])
            name = event['event']
            if not isinstance(name, str):
                return False
            for key in ('total', 'processed', 'cached', 'review_pages', 'error_regions', 'page'):
                if key in event and not (key == 'page' and event[key] is None):
                    if type(event[key]) is not int or event[key] < 0:
                        return False
        except (ValueError, KeyError, TypeError):
            return False
        for key in ('total', 'processed', 'cached', 'review_pages', 'error_regions', 'page', 'region'):
            if key in event:
                self.state[key] = event[key]
        labels = {'start': 'Đang chuẩn bị tài liệu', 'model_loading': 'Đang nạp mô hình — vui lòng chờ',
                  'page_start': 'Đang OCR', 'region_start': 'Đang nhận dạng vùng ảnh',
                  'region_done': 'Đã xử lý vùng ảnh', 'region_cached': 'Đã nạp vùng từ cache',
                  'region_retry': 'Đang chia nhỏ vùng khó', 'region_error': 'Vùng cần kiểm tra — tiếp tục xử lý',
                  'page_done': 'Đã xử lý trang', 'export': 'Đang đóng gói kết quả'}
        if name == 'region_error':
            self.state['error_regions'] += 1
            self.review_page_numbers.add(self.state['page'])
            self.state['review_pages'] = len(self.review_page_numbers)
        if name == 'finish':
            self.finish('complete' if event.get('complete') else 'needs_review')
        else:
            self.state['status'] = labels.get(name, self.state['status'])
            self.refresh()
        return True

    def finish(self, outcome):
        self.state['outcome'] = outcome
        self.state['status'] = {
            'complete': 'Hoàn tất xử lý — vẫn cần đối chiếu chất lượng OCR',
            'needs_review': 'Xử lý xong — còn vùng cần kiểm tra',
            'failed': 'OCR đã dừng vì lỗi — xem log bên dưới',
            'interrupted': 'Đã dừng theo yêu cầu',
        }[outcome]
        self.ended = self.clock()
        self.refresh(force=True)

    def as_html(self):
        state = self.state
        total = max(0, int(state['total'] or 0))
        processed = max(0, int(state['processed'] or 0))
        percent = min(100, processed / total * 100) if total else 0
        elapsed = max(0, int((self.ended if self.ended is not None else self.clock()) - self.started))
        duration = f'{elapsed // 3600:02d}:{elapsed // 60 % 60:02d}:{elapsed % 60:02d}'
        color = '#fbbf24' if state['outcome'] in ('needs_review', 'interrupted') else '#f87171' if state['outcome'] == 'failed' else '#34d399'
        esc = lambda value: html.escape(str(value))
        location = f"Trang {state['page']}" if state['page'] is not None else 'Chưa bắt đầu trang'
        if state['region'] is not None:
            location += ' · Vùng ' + str(state['region'])
        return f'''<section aria-label="Tiến độ OCR" style="font:14px/1.5 system-ui,sans-serif;background:#111827;color:#e5e7eb;border:1px solid #475569;border-radius:12px;padding:18px;margin:8px 0 16px;max-width:1000px;box-sizing:border-box">
<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap"><strong style="font-size:17px">Tiến độ OCR</strong><strong style="color:{color}">{percent:.1f}%</strong></div>
<div role="progressbar" aria-label="Trang đã xử lý" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{percent:.1f}" style="height:12px;background:#334155;border-radius:8px;overflow:hidden;margin:12px 0"><div style="height:100%;width:{percent:.1f}%;background:{color}"></div></div>
<div style="display:flex;gap:24px;flex-wrap:wrap"><span>Đã xử lý: <b>{processed}/{total or '—'} trang</b></span><span>Từ cache: <b>{esc(state['cached'])}</b></span><span>Thời gian: <b>{duration}</b></span></div>
<div style="margin-top:10px;color:#cbd5e1">{esc(location)}</div>
<div style="margin-top:6px;color:{color}">{esc(state['status'])}</div>
<div style="margin-top:8px;color:#fbbf24">Cần kiểm tra: {esc(state['review_pages'])} trang · {esc(state['error_regions'])} vùng lỗi</div>
<small style="display:block;color:#94a3b8;margin-top:10px">Phần trăm là tiến độ xử lý trang, gồm cả trang cần kiểm tra; không phải độ chính xác nhận dạng. Log chi tiết ở bên dưới.</small></section>'''

    def refresh(self, force=False):
        now = self.clock()
        if self.render and (force or now - self.last_render >= .25):
            try:
                self.render(self.as_html())
            except Exception:
                # Losing the notebook display must not kill the OCR worker.
                self.render = None
            self.last_render = now


def run_logged_process(command, *, cwd, env, log_path, show_progress=True):
    """Stream merged stdout/stderr to the cell and retain the original failure.

    Inheriting the kernel's file descriptors does not reliably display child
    output in Colab. Explicitly forwarding the pipe makes Python tracebacks
    visible, including failures that occur before the runner can initialize.
    """
    log_path = Path(log_path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tail = deque(maxlen=60)
    dashboard = NotebookProgress() if show_progress else None
    print(f"Log OCR: {log_path}", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        try:
            process = subprocess.Popen(
                [str(part) for part in command], cwd=str(cwd), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        except Exception:
            if dashboard:
                dashboard.finish('failed')
            raise
        messages = queue.Queue()
        def read_output():
            try:
                for line in process.stdout:
                    messages.put(line)
            finally:
                messages.put(None)
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            while True:
                try:
                    line = messages.get(timeout=.5)
                except queue.Empty:
                    if dashboard:
                        dashboard.refresh()
                    continue
                if line is None:
                    break
                log.write(line)
                log.flush()
                tail.append(line)
                if not dashboard or not dashboard.accept(line):
                    print(line, end="", flush=True)
            returncode = process.wait()
            if dashboard:
                if returncode:
                    dashboard.finish('failed')
                elif dashboard.state['outcome'] == 'running':
                    dashboard.state['status'] = 'Tiến trình kết thúc; không có thông tin tổng kết OCR'
                    dashboard.ended = dashboard.clock()
                    dashboard.refresh(force=True)
        except KeyboardInterrupt:
            if dashboard:
                dashboard.finish('interrupted')
            raise
        except BaseException:
            if dashboard:
                dashboard.finish('failed')
            raise
        finally:
            # Stop the worker as well when the user interrupts the cell.
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdout.close()
            reader.join(timeout=1)
    if returncode:
        detail = "".join(tail).strip()[-12000:]
        if not detail:
            detail = "Tiến trình không ghi log. Kiểm tra RAM/GPU và trạng thái runtime."
        raise RuntimeError(
            f"OCR dừng với mã {returncode}. Log đầy đủ: {log_path}\n"
            f"--- Lỗi gốc / cuối log OCR ---\n{detail}"
        )
    return subprocess.CompletedProcess(command, returncode)
