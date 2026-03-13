"""
Folder watcher: auto-ingests files dropped into the uploads directory.
Also provides _process_file for manual ingestion with tags/collection support.
"""
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional, List

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .extractor import extract_text, SUPPORTED_EXTENSIONS
from .vector_store import ingest_document, delete_document

logger = logging.getLogger(__name__)

UPLOADS_DIR = str(Path(__file__).parent.parent.parent / "uploads")

# Track processing state: filename -> status string
processing_status: Dict[str, str] = {}


def _process_file(
    file_path: str,
    tags: Optional[List[str]] = None,
    collection: Optional[str] = None,
    source_url: Optional[str] = None,
):
    name = Path(file_path).name
    ext = Path(file_path).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        logger.info(f"Skipping unsupported file: {name}")
        return

    processing_status[name] = "processing"
    logger.info(f"Ingesting: {name}")

    try:
        time.sleep(0.5)
        text = extract_text(file_path)
        if not text:
            processing_status[name] = "error: no text extracted"
            return

        chunks = ingest_document(
            file_path, text,
            tags=tags,
            collection=collection,
            source_url=source_url,
        )
        processing_status[name] = f"done ({chunks} chunks)"
        logger.info(f"Ingested {name}: {chunks} chunks")
    except Exception as e:
        processing_status[name] = f"error: {e}"
        logger.error(f"Failed to ingest {name}: {e}")


class UploadHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            _process_file(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            _process_file(event.dest_path)

    def on_deleted(self, event):
        if not event.is_directory:
            name = Path(event.src_path).name
            deleted = delete_document(name)
            processing_status.pop(name, None)
            if deleted:
                logger.info(f"Removed {name} from knowledge base ({deleted} chunks)")


def start_watcher():
    """Start the folder watcher in a background thread."""
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    # Ingest any files already in the folder at startup
    for f in Path(UPLOADS_DIR).iterdir():
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            name = f.name
            if processing_status.get(name, "").startswith("done"):
                continue
            _process_file(str(f))

    observer = Observer()
    observer.schedule(UploadHandler(), UPLOADS_DIR, recursive=False)
    observer.start()
    logger.info(f"Watching uploads folder: {UPLOADS_DIR}")
    return observer
