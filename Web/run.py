import uvicorn
import sys
import os
import socket
import argparse
from pathlib import Path

# Add project root to sys.path so imports work properly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

def find_available_port(start_port: int = 8000, host: str = "127.0.0.1") -> int:
    port = start_port
    while is_port_in_use(port, host):
        port += 1
    return port

def main():
    parser = argparse.ArgumentParser(description="Chạy Han–Viet Alignment Studio Web Server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)), help="Cổng chạy server (mặc định 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host (mặc định 127.0.0.1)")
    args = parser.parse_args()

    host = args.host
    target_port = args.port

    if is_port_in_use(target_port, host):
        fallback_port = find_available_port(target_port + 1, host)
        print("!" * 60)
        print(f"  CẢNH BÁO: Cổng {target_port} đang bị chiếm bởi tiến trình khác.")
        print(f"  Tự động chuyển sang cổng khả dụng: http://{host}:{fallback_port}")
        print("!" * 60)
        target_port = fallback_port

    print("=" * 60)
    print("  Han–Viet Alignment Studio — Local Web Server")
    print(f"  Địa chỉ: http://{host}:{target_port}")
    print(f"  Host: {host} (Localhost only, an toàn)")
    print("=" * 60)
    uvicorn.run("Web.app.main:app", host=host, port=target_port, reload=False)

if __name__ == "__main__":
    main()
