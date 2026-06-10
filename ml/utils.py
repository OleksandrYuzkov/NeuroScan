import json
from pathlib import Path
from typing import List


def save_class_names(path: Path, class_names: List[str]) -> None:
    path.write_text(json.dumps(class_names, ensure_ascii=False, indent=2), encoding="utf-8")


def load_class_names(path: Path) -> List[str]:
    return json.loads(path.read_text(encoding="utf-8"))
