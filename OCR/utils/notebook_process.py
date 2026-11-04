"""Run OCR workers with output visible in hosted notebook cells."""
from collections import deque
from pathlib import Path
import subprocess


def run_logged_process(command, *, cwd, env, log_path):
    """Stream merged stdout/stderr to the cell and retain the original failure.

    Inheriting the kernel's file descriptors does not reliably display child
    output in Colab. Explicitly forwarding the pipe makes Python tracebacks
    visible, including failures that occur before the runner can initialize.
    """
    log_path = Path(log_path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tail = deque(maxlen=60)
    print(f"Log OCR: {log_path}", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [str(part) for part in command], cwd=str(cwd), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        try:
            for line in process.stdout:
                log.write(line)
                log.flush()
                tail.append(line)
                print(line, end="", flush=True)
            returncode = process.wait()
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
    if returncode:
        detail = "".join(tail).strip()[-12000:]
        if not detail:
            detail = "Tiến trình không ghi log. Kiểm tra RAM/GPU và trạng thái runtime."
        raise RuntimeError(
            f"OCR dừng với mã {returncode}. Log đầy đủ: {log_path}\n"
            f"--- Lỗi gốc / cuối log OCR ---\n{detail}"
        )
    return subprocess.CompletedProcess(command, returncode)
