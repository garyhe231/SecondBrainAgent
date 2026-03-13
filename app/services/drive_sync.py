"""
Google Drive sync via the `gws` CLI.
Lists files, downloads them to uploads/, triggers ingestion.
"""
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

UPLOADS_DIR = str(Path(__file__).parent.parent.parent / "uploads")

# Mime types we can handle
SUPPORTED_MIME_EXPORT = {
    "application/vnd.google-apps.document": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "application/vnd.google-apps.presentation": ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    "application/vnd.google-apps.spreadsheet": ("csv", "text/csv"),
}
SUPPORTED_MIME_DOWNLOAD = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _run_gws(args: List[str], timeout: int = 30) -> Optional[str]:
    try:
        result = subprocess.run(
            ["gws"] + args,
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            logger.error(f"gws error: {result.stderr}")
            return None
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError("gws CLI not found. Please ensure it is installed.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("gws command timed out")


def list_drive_files(query: str = "", max_results: int = 50) -> List[Dict[str, Any]]:
    """List files from Google Drive."""
    args = ["drive", "list", "--format", "json", "--limit", str(max_results)]
    if query:
        args += ["--query", query]
    out = _run_gws(args)
    if not out:
        return []
    try:
        data = json.loads(out)
        # Normalise to list
        if isinstance(data, dict):
            files = data.get("files", data.get("items", []))
        else:
            files = data
        return [
            {
                "id": f.get("id", ""),
                "name": f.get("name", f.get("title", "")),
                "mime": f.get("mimeType", ""),
                "modified": f.get("modifiedTime", f.get("modifiedDate", "")),
                "size": f.get("size", ""),
            }
            for f in files
        ]
    except json.JSONDecodeError:
        logger.error(f"Could not parse gws output: {out[:200]}")
        return []


def download_file(file_id: str, file_name: str, mime_type: str) -> Optional[str]:
    """
    Download a Drive file to uploads/.
    Returns the local path or None on failure.
    """
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    if mime_type in SUPPORTED_MIME_EXPORT:
        ext, export_mime = SUPPORTED_MIME_EXPORT[mime_type]
        safe_name = Path(file_name).stem[:60] + f".{ext}"
        dest = os.path.join(UPLOADS_DIR, safe_name)
        args = ["drive", "export", file_id, "--mime-type", export_mime, "--output", dest]
    elif mime_type in SUPPORTED_MIME_DOWNLOAD:
        safe_name = Path(file_name).name[:80]
        dest = os.path.join(UPLOADS_DIR, safe_name)
        args = ["drive", "download", file_id, "--output", dest]
    else:
        logger.info(f"Unsupported mime type for download: {mime_type}")
        return None

    out = _run_gws(args, timeout=60)
    if out is not None and os.path.exists(dest):
        return dest
    return None


def sync_drive_files(file_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Download a list of Drive file IDs.
    Returns list of {id, name, status, local_path}.
    """
    # First list all to get metadata
    all_files = list_drive_files(max_results=200)
    file_map = {f["id"]: f for f in all_files}

    results = []
    for fid in file_ids:
        meta = file_map.get(fid)
        if not meta:
            results.append({"id": fid, "name": fid, "status": "error: not found"})
            continue

        try:
            local = download_file(fid, meta["name"], meta["mime"])
            if local:
                results.append({"id": fid, "name": meta["name"], "status": "downloaded", "local_path": local})
            else:
                results.append({"id": fid, "name": meta["name"], "status": "error: unsupported type"})
        except Exception as e:
            results.append({"id": fid, "name": meta["name"], "status": f"error: {e}"})

    return results
