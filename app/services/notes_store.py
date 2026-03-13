"""
In-app notes: create, update, delete markdown notes stored as files and indexed in the vector store.
"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

NOTES_DIR = str(Path(__file__).parent.parent.parent / "data" / "notes")


def _ensure_dir():
    os.makedirs(NOTES_DIR, exist_ok=True)


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9 ]", "", title).strip()
    slug = re.sub(r"\s+", "_", slug)[:60]
    return slug or "note"


def _note_filename(note_id: str) -> str:
    return os.path.join(NOTES_DIR, f"{note_id}.md")


def create_note(title: str, content: str) -> Dict[str, Any]:
    _ensure_dir()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    note_id = f"{ts}_{_slug(title)}"
    path = _note_filename(note_id)
    body = f"# {title}\n\n{content}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return {"id": note_id, "title": title, "content": content, "path": path}


def update_note(note_id: str, title: str, content: str) -> Dict[str, Any]:
    path = _note_filename(note_id)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Note {note_id} not found")
    body = f"# {title}\n\n{content}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return {"id": note_id, "title": title, "content": content, "path": path}


def delete_note(note_id: str) -> bool:
    path = _note_filename(note_id)
    if os.path.exists(path):
        os.unlink(path)
        return True
    return False


def get_note(note_id: str) -> Optional[Dict[str, Any]]:
    path = _note_filename(note_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        body = f.read()
    lines = body.splitlines()
    title = lines[0].lstrip("# ").strip() if lines else note_id
    content = "\n".join(lines[2:]).strip() if len(lines) > 2 else ""
    stat = os.stat(path)
    return {
        "id": note_id,
        "title": title,
        "content": content,
        "path": path,
        "modified": datetime.utcfromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
    }


def list_notes() -> List[Dict[str, Any]]:
    _ensure_dir()
    notes = []
    for fname in sorted(os.listdir(NOTES_DIR), reverse=True):
        if fname.endswith(".md"):
            note_id = fname[:-3]
            note = get_note(note_id)
            if note:
                notes.append(note)
    return notes


def note_filename_for_vector(note_id: str) -> str:
    """Return the .md filename as it appears in the vector store (basename)."""
    return f"{note_id}.md"
