import re
from typing import List, Dict, Any, Optional

class BaseEmbeddingAdapter:
    def score_pair(self, han_text: str, viet_text: str) -> float:
        raise NotImplementedError

class DeterministicSimAdapter(BaseEmbeddingAdapter):
    """
    Deterministic rule-based similarity adapter for contract tests and CPU fallback.
    Uses Sino-Vietnamese syllable mapping, character correspondence and length heuristics.
    """
    def __init__(self):
        # Sample Sino-Vietnamese phonetic correspondences for demonstration/deterministic mode
        self.char_map = {
            "古": "cổ", "南": "nam", "交": "giao", "周": "chu", "號": "hiệu", "越": "việt", "裳": "thường",
            "秦": "tần", "始": "thủy", "皇": "hoàng", "置": "đặt", "象": "tượng", "郡": "quận",
            "漢": "hán", "武": "vũ", "帝": "đế", "平": "bình", "地": "đất", "山": "núi", "川": "sông",
            "秀": "tươi", "麗": "đẹp", "氣": "khí", "候": "hậu", "溫": "ấm", "和": "hòa",
            "天": "trời", "黃": "vàng", "宇": "vũ", "宙": "trụ"
        }

    def score_pair(self, han_text: str, viet_text: str) -> float:
        viet_lower = viet_text.lower()
        matches = 0
        total_han_chars = 0
        for char in han_text:
            if re.match(r'[\u4e00-\u9fff]', char):
                total_han_chars += 1
                meaning = self.char_map.get(char)
                if meaning and meaning in viet_lower:
                    matches += 1

        if total_han_chars == 0:
            return 0.5
        sim = matches / total_han_chars
        # Base similarity floor for adjacent candidates
        return min(1.0, max(0.1, sim * 0.8 + 0.2))

class RealModelAdapter(BaseEmbeddingAdapter):
    """Adapter for sentence_transformers / LaBSE / Qwen3-Embedding when installed."""
    def __init__(self, model_name: str = "sentence-transformers/LaBSE"):
        self.model_name = model_name
        try:
            from sentence_transformers import SentenceTransformer, util
            self.model = SentenceTransformer(model_name)
            self.util = util
            self.available = True
        except Exception:
            self.available = False
            self.fallback = DeterministicSimAdapter()

    def score_pair(self, han_text: str, viet_text: str) -> float:
        if not self.available:
            return self.fallback.score_pair(han_text, viet_text)
        emb1 = self.model.encode(han_text, convert_to_tensor=True)
        emb2 = self.model.encode(viet_text, convert_to_tensor=True)
        cos_sim = float(self.util.cos_sim(emb1, emb2)[0][0])
        return max(0.0, min(1.0, (cos_sim + 1.0) / 2.0))
