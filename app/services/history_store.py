"""
Persistent conversation history: save, load, list, delete chat sessions.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

HISTORY_DIR = str(Path(__file__).parent.parent.parent / "data" / "history")


def _ensure_dir():
    os.makedirs(HISTORY_DIR, exist_ok=True)


def _session_path(session_id: str) -> str:
    return os.path.join(HISTORY_DIR, f"{session_id}.json")


def new_session_id() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")


def save_session(session_id: str, messages: List[Dict[str, str]], title: Optional[str] = None) -> Dict[str, Any]:
    _ensure_dir()
    if not title:
        # Auto-title from first user message
        for m in messages:
            if m.get("role") == "user":
                title = m["content"][:60].strip()
                break
        title = title or "Untitled"

    data = {
        "id": session_id,
        "title": title,
        "messages": messages,
        "updated": datetime.utcnow().isoformat(),
    }
    with open(_session_path(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def load_session(session_id: str) -> Optional[Dict[str, Any]]:
    path = _session_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_session(session_id: str) -> bool:
    path = _session_path(session_id)
    if os.path.exists(path):
        os.unlink(path)
        return True
    return False


def list_sessions() -> List[Dict[str, Any]]:
    _ensure_dir()
    sessions = []
    for fname in sorted(os.listdir(HISTORY_DIR), reverse=True):
        if fname.endswith(".json"):
            sid = fname[:-5]
            path = _session_path(sid)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append({
                    "id": data["id"],
                    "title": data.get("title", sid),
                    "updated": data.get("updated", ""),
                    "message_count": len(data.get("messages", [])),
                })
            except Exception:
                pass
    return sessions


def rename_session(session_id: str, title: str) -> bool:
    data = load_session(session_id)
    if not data:
        return False
    data["title"] = title
    with open(_session_path(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True
