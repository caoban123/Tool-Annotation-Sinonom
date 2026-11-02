import os
import sys
import random
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Classical Han sentence templates
HAN_TEMPLATES = [
    "古南交，周號越裳。",
    "秦始皇二十六年，分天下為三十六郡，置象郡。",
    "漢武帝元鼎六年，平南越，置交趾九郡。",
    "交趾、九真、日南三郡，皆古南越地也。",
    "其地山川秀麗，物產豐饒。",
    "春暖花開，萬物生長。",
    "江漢朝宗于海，朝廷修德化民。",
    "自古帝王撫有萬方，莫不以德為本。",
    "歲次甲子，國泰民安，四海昇平。",
    "文德既洽，武功亦揚，天下太平。"
]

# Vietnamese corresponding translation templates
VIET_TEMPLATES = [
    "Đất Nam Giao xưa, nhà Chu gọi là Việt Thường.",
    "Năm thứ hai mươi sáu đời Tần Thủy Hoàng, chia thiên hạ làm ba mươi sáu quận, đặt quận Tượng.",
    "Năm Nguyên Đỉnh thứ sáu đời Hán Vũ Đế, bình định Nam Việt, đặt ra chín quận Giao Chỉ.",
    "Ba quận Giao Chỉ, Cửu Chân, Nhật Nam đều là đất Nam Việt xưa.",
    "Đất đai nơi ấy núi sông tươi đẹp, sản vật phì nhiêu dồi dào.",
    "Mùa xuân ấm áp hoa nở, muôn vật tốt tươi sinh trưởng.",
    "Sông biển chầu về biển lớn, triều đình lấy đức hóa giải lòng dân.",
    "Từ xưa các bậc đế vương vỗ về muôn phương, không ai là không lấy đức làm gốc.",
    "Năm ấy gặp khoa Giáp Tý, nước thái dân an, bốn biển thái bình thịnh trị.",
    "Văn đức đã nhuần thấm khắp nơi, võ công cũng rạng rỡ, thiên hạ thái bình."
]

def generate_synthetic_dataset(count: int = 2000, output_dir: str = "data/synthetic") -> None:
    """Generates synthetic paired han.txt and viet.txt with realistic length and distribution."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    han_lines = []
    viet_lines = []

    for i in range(count):
        idx = i % len(HAN_TEMPLATES)
        suffix = f" [Đoạn #{i+1:04d}]"
        han_lines.append(HAN_TEMPLATES[idx] + suffix)
        viet_lines.append(VIET_TEMPLATES[idx] + suffix)

    han_path = out / "han_synthetic_2000.txt"
    viet_path = out / "viet_synthetic_2000.txt"

    with open(han_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(han_lines) + "\n")

    with open(viet_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(viet_lines) + "\n")

    print(f"Đã tạo thành công bộ dữ liệu giả lập {count} cặp tại:")
    print(f" - {han_path} ({len(han_lines)} dòng)")
    print(f" - {viet_path} ({len(viet_lines)} dòng)")

def generate_four_tasks_dataset(pairs_per_task: int = 2000, output_dir: str = "data/team_tasks") -> None:
    """Generates 4 distinct tasks totaling 8,000 synthetic pairs for team consolidation testing."""
    base = Path(output_dir)
    tasks = ["SV1_NguyenVanA", "SV2_TranThiB", "SV3_LeVanC", "SV4_PhamThiD"]
    scopes = ["Quyển 1 - Địa lý chí", "Quyển 2 - Nhân vật chí", "Quyển 3 - Quan chế chí", "Quyển 4 - Binh chế chí"]

    for t_idx, (task_user, scope) in enumerate(zip(tasks, scopes)):
        t_dir = base / task_user
        t_dir.mkdir(parents=True, exist_ok=True)
        han_lines = []
        viet_lines = []
        start_offset = t_idx * pairs_per_task

        for i in range(pairs_per_task):
            g_idx = start_offset + i
            tpl_idx = g_idx % len(HAN_TEMPLATES)
            suffix = f" [Q{t_idx+1} Cặp #{i+1:04d}]"
            han_lines.append(HAN_TEMPLATES[tpl_idx] + suffix)
            viet_lines.append(VIET_TEMPLATES[tpl_idx] + suffix)

        with open(t_dir / "han.txt", "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(han_lines) + "\n")
        with open(t_dir / "viet.txt", "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(viet_lines) + "\n")

    print(f"Đã tạo 4 tác phẩm cho nhóm tổng cộng {len(tasks) * pairs_per_task} cặp tại: {base}")

if __name__ == "__main__":
    generate_synthetic_dataset(2000)
    generate_four_tasks_dataset(2000)
