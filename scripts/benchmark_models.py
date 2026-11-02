import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Web.ai.candidate_generation import DeterministicSimAdapter, RealModelAdapter
from Web.ai.monotonic_alignment import align_segments_monotonic
from Web.ai.prepare_segments import split_han_viet_segments

def run_benchmark(gold_path: str = "tests/fixtures/expected_pairs.json") -> Dict[str, Any]:
    print("=" * 60)
    print("  HanViet-Alignment — Mô Hình Hóa & Benchmark")
    print("=" * 60)

    # Check GPU availability
    has_gpu = False
    gpu_name = "None (CPU Execution)"
    try:
        import torch
        if torch.cuda.is_available():
            has_gpu = True
            gpu_name = torch.cuda.get_device_name(0)
    except Exception:
        pass

    print(f"Phần cứng phát hiện: {gpu_name}")

    # Load gold fixture
    p = Path(gold_path)
    with open(p, "r", encoding="utf-8") as f:
        gold = json.load(f)

    # Test Deterministic Sim Adapter
    det_scorer = DeterministicSimAdapter()
    t0 = time.time()
    correct = 0
    total = len(gold["test_cases"])

    for tc in gold["test_cases"]:
        score = det_scorer.score_pair(tc["han_expected"], tc["viet_expected"])
        if score > 0.4:
            correct += 1

    dur = time.time() - t0
    acc = (correct / total) * 100 if total > 0 else 0.0

    print(f"Mô hình: Deterministic Sim Adapter (Baseline Local)")
    print(f" - Độ chính xác trên fixture chuẩn ({total} mẫu): {acc:.1f}%")
    print(f" - Thời gian thực thi: {dur*1000:.2f} ms")

    # Real Model (LaBSE / Qwen3) availability check
    real_adapter = RealModelAdapter("sentence-transformers/LaBSE")
    real_status = "Available" if real_adapter.available else "Pending GPU/Download (Not Installed Locally)"

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hardware": {
            "has_gpu": has_gpu,
            "device": gpu_name
        },
        "baseline_model": {
            "name": "DeterministicSimAdapter",
            "accuracy_pct": acc,
            "test_sample_size": total,
            "latency_ms": round(dur * 1000, 2)
        },
        "neural_models": {
            "LaBSE": real_status,
            "Qwen3-Embedding-0.6B": "Colab / High-Memory Target",
            "Qwen3-Embedding-4B": "Colab GPU (16GB+ VRAM) Target"
        },
        "real_data_benchmark_status": "gold fixture evaluated; large ancient Chinese benchmark pending full corpus annotation"
    }

    out_file = Path("docs/model-benchmark.md")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("# Báo Cáo Benchmark & Đánh Giá Mô Hình AI\n\n")
        f.write(f"- **Thời gian chạy**: {report['timestamp']}\n")
        f.write(f"- **Phần cứng**: {gpu_name}\n\n")
        f.write("## 1. Kết Quả Đo Lường Trên Fixture Chuẩn\n\n")
        f.write(f"| Mô hình | Trạng thái | Độ chính xác ({total} cặp mẫu) | Độ trễ |\n")
        f.write("|---|---|---|---|\n")
        f.write(f"| `DeterministicSimAdapter` | Sẵn sàng (Local/CPU) | {acc:.1f}% | {dur*1000:.2f} ms |\n")
        f.write(f"| `LaBSE` | {real_status} | Phụ thuộc weights | - |\n")
        f.write(f"| `Qwen3-Embedding-0.6B` | Hỗ trợ Colab | Khuyến nghị chạy trên Colab T4 | - |\n")
        f.write(f"| `Qwen3-Embedding-4B` | Hỗ trợ Colab A100 | Khuyến nghị GPU 16GB+ | - |\n\n")
        f.write("## 2. Ghi Chú Trung Thực Về Môi Trường\n\n")
        f.write("> **Lưu ý nghiệp vụ:** Độ chính xác trên Hán văn cổ đòi hỏi đối chứng thực tế với bản dịch của chuyên gia. ")
        f.write("Mô hình AI trong đồ án đóng vai trò **gợi ý (suggestions)**, không thay thế người duyệt và không tự động xác nhận vào file giao nộp TSV/XLSX.\n")

    print(f"Đã cập nhật tài liệu benchmark: {out_file}")
    return report

if __name__ == "__main__":
    run_benchmark()
