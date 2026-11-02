import uvicorn
import sys
from pathlib import Path

# Add project root to sys.path so imports work properly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def main():
    print("=" * 60)
    print("  Han–Viet Alignment Studio — Local Web Server")
    print("  Địa chỉ: http://127.0.0.1:8000")
    print("  Host: 127.0.0.1 (Localhost only, không mở LAN)")
    print("=" * 60)
    uvicorn.run("Web.app.main:app", host="127.0.0.1", port=8000, reload=False)

if __name__ == "__main__":
    main()
