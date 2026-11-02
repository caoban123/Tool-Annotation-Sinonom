import pytest
from pathlib import Path
from Web.app.services.export import generate_tsv, generate_xlsx, verify_export_parity

def test_export_parity_matching(tmp_path):
    pairs = [
        ("id1", "古南交，周號越裳。", "Đất Nam Giao xưa, nhà Chu gọi là Việt Thường."),
        ("id2", "秦始皇置象郡。", "Nhà Tần đặt quận Tượng. Lại chia đặt các quan cai trị."),
        ("id3", "漢武帝平南越。 置交趾九郡。", "Vua Hán Vũ Đế bình định Nam Việt và đặt ra chín quận Giao Chỉ."),
        ("id4", "其地山川秀麗。 氣候溫和。", "Núi sông vùng ấy tốt tươi đẹp đẽ. Thời tiết bốn mùa ấm áp ôn hòa."),
        ("id5", "=SUM(1+1) 𠀀 𡨸喃 đặc biệt", "=1+1 Ký tự đặc biệt 𠀀 𡨸喃")
    ]

    tsv_file = tmp_path / "match.tsv"
    xlsx_file = tmp_path / "match.xlsx"

    generate_tsv(pairs, tsv_file)
    generate_xlsx(pairs, xlsx_file)

    assert verify_export_parity(tsv_file, xlsx_file) == True

def test_export_parity_mismatch_detected(tmp_path):
    pairs1 = [("id1", "古南交", "Đất Nam Giao")]
    pairs2 = [("id1", "古南交", "Đất Nam Giao Khác")]

    tsv_file = tmp_path / "mismatch.tsv"
    xlsx_file = tmp_path / "mismatch.xlsx"

    generate_tsv(pairs1, tsv_file)
    generate_xlsx(pairs2, xlsx_file)

    with pytest.raises(ValueError, match="Sai khác"):
        verify_export_parity(tsv_file, xlsx_file)
