import json
import datetime
from pathlib import Path
from typing import List, Dict, Any

def create_suggestions_file(
    manifest: Dict[str, Any],
    suggestions: List[Dict[str, Any]],
    model_name: str,
    output_path: Path
) -> Dict[str, Any]:
    """Generates a suggestions.json file strictly conforming to the Section 3.3 data contract."""
    payload = {
        "schema_version": "1.0",
        "project_id": manifest["project_id"],
        "task_id": manifest.get("task_id"),
        "source_revision": manifest.get("revision", 1),
        "source_sha256_han": manifest["source_sha256_han"],
        "source_sha256_viet": manifest["source_sha256_viet"],
        "model_name": model_name,
        "model_version": "1.0",
        "created_at": datetime.datetime.utcnow().isoformat(),
        "suggestions": suggestions
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload
