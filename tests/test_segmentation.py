import pytest
from Web.app.services.segmentation import split_sentences_han, split_sentences_viet

def test_split_sentences_han():
    text = "古南交，周號越裳。秦始皇置象郡！漢武帝平南越；置交趾九郡。"
    parts = split_sentences_han(text)
    assert len(parts) == 4
    assert parts[0] == "古南交，周號越裳。"
    assert parts[1] == "秦始皇置象郡！"
    assert parts[2] == "漢武帝平南越；"
    assert parts[3] == "置交趾九郡。"

def test_split_sentences_viet():
    text = "Đất Nam Giao xưa, nhà Chu gọi là Việt Thường. Nhà Tần đặt quận Tượng! Lại chia đặt các quan; Vua Hán bình định."
    parts = split_sentences_viet(text)
    assert len(parts) == 4
    assert "Việt Thường." in parts[0]
    assert "quận Tượng!" in parts[1]
    assert "các quan;" in parts[2]
    assert "bình định." in parts[3]

def test_split_preserves_rare_characters():
    text = "天地玄黃 𠀀 𡨸喃。「宇宙洪荒。」"
    parts = split_sentences_han(text)
    assert any("𠀀" in p for p in parts)
    assert any("𡨸喃" in p for p in parts)
