import pytest
import json
from pathlib import Path

from Web.ai.prepare_segments import split_han_viet_segments
from Web.ai.candidate_generation import DeterministicSimAdapter
from Web.ai.monotonic_alignment import align_segments_monotonic
from Web.ai.export_suggestions import create_suggestions_file

def test_ai_suggestion_generation(tmp_path):
    manifest = {
        "schema_version": "1.0",
        "project_id": "proj_ai_test",
        "revision": 1,
        "source_sha256_han": "hash_han_123",
        "source_sha256_viet": "hash_viet_456",
        "segments": [
            {"segment_id": "h1", "language": "han", "order_index": 0, "text": "古南交，周號越裳。", "active": True},
            {"segment_id": "h2", "language": "han", "order_index": 1, "text": "秦始皇置象郡。", "active": True},
            {"segment_id": "v1", "language": "viet", "order_index": 0, "text": "Đất Nam Giao xưa, nhà Chu gọi là Việt Thường.", "active": True},
            {"segment_id": "v2", "language": "viet", "order_index": 1, "text": "Nhà Tần đặt quận Tượng.", "active": True},
            {"segment_id": "v3", "language": "viet", "order_index": 2, "text": "Lại chia đặt các quan cai trị.", "active": True}
        ]
    }

    han_segs, viet_segs = split_han_viet_segments(manifest)
    scorer = DeterministicSimAdapter()
    suggestions = align_segments_monotonic(han_segs, viet_segs, scorer)

    assert len(suggestions) >= 2
    types = [s["alignment_type"] for s in suggestions]
    assert "1-1" in types or "1-n" in types

    out_file = tmp_path / "suggestions.json"
    res = create_suggestions_file(manifest, suggestions, model_name="test_model", output_path=out_file)

    assert res["schema_version"] == "1.0"
    assert res["source_sha256_han"] == "hash_han_123"
    assert res["source_sha256_viet"] == "hash_viet_456"
    assert len(res["suggestions"]) == len(suggestions)
