import json
import os
from typing import Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECEIPT_DATA_PATH = os.path.join(BASE_DIR, "receipt_data.json")


def load_templates() -> list[dict[str, Any]]:
    with open(RECEIPT_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["receipts"]


def template_display_names() -> list[str]:
    return [t["receipt_id"].replace("_", " ") for t in load_templates()]


def template_by_index(index: int) -> dict[str, Any]:
    return load_templates()[index]
