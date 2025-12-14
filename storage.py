import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DATA_DIR = "data"
SESSIONS_PATH = os.path.join(DATA_DIR, "sessions.jsonl")


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_session(record: Dict[str, Any]) -> None:
    _ensure_data_dir()
    with open(SESSIONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_sessions(limit: int = 30) -> List[Dict[str, Any]]:
    if not os.path.exists(SESSIONS_PATH):
        return []
    rows: List[Dict[str, Any]] = []
    with open(SESSIONS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def make_vocab_csv_rows(
    vocab: List[Dict[str, Any]],
    level: str,
    topic: str,
    date_iso: Optional[str] = None,
) -> str:
    date_iso = date_iso or utc_now_iso()
    # Simple CSV without extra dependencies
    header = ["word", "translation", "example", "topic", "level", "date"]
    lines = [",".join(header)]
    for item in vocab or []:
        word = (item.get("word") or "").replace('"', '""')
        tr = (item.get("translation") or "").replace('"', '""')
        ex = (item.get("example") or "").replace('"', '""')
        t = topic.replace('"', '""')
        lv = level.replace('"', '""')
        dt = date_iso.replace('"', '""')
        # quote each field to be safe
        lines.append(f'"{word}","{tr}","{ex}","{t}","{lv}","{dt}"')
    return "\n".join(lines)
