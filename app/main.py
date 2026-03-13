import json
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel

from .services.watcher import start_watcher, processing_status, UPLOADS_DIR, _process_file
from .services.vector_store import (
    list_documents, get_stats, delete_document, list_collections, list_tags,
    update_document_tags,
)
from .services.brain import chat_stream, get_sources_for_query
from .services.extractor import SUPPORTED_EXTENSIONS
from .services.notes_store import (
    create_note, update_note, delete_note, get_note, list_notes,
    note_filename_for_vector, NOTES_DIR,
)
from .services.history_store import (
    save_session, load_session, delete_session, list_sessions,
    new_session_id, rename_session,
)
from .services.url_ingester import fetch_url, url_to_filename
from .services.drive_sync import list_drive_files, sync_drive_files

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Second Brain Agent")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_watcher_observer = None


@app.on_event("startup")
async def startup():
    global _watcher_observer
    os.makedirs(NOTES_DIR, exist_ok=True)
    _watcher_observer = start_watcher()


@app.on_event("shutdown")
async def shutdown():
    if _watcher_observer:
        _watcher_observer.stop()
        _watcher_observer.join()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Documents ──────────────────────────────────────────────────────────────────

@app.get("/api/documents")
async def get_documents(collection: Optional[str] = None):
    docs = list_documents(collection_filter=collection)
    for doc in docs:
        doc["status"] = processing_status.get(doc["name"], "done")
    for name, status in processing_status.items():
        if not any(d["name"] == name for d in docs):
            docs.append({"name": name, "chunks": 0, "tags": [], "collection": "default", "source_url": "", "status": status})
    return {"documents": docs}


@app.get("/api/stats")
async def get_brain_stats():
    stats = get_stats()
    stats["uploads_dir"] = UPLOADS_DIR
    stats["supported_types"] = sorted(SUPPORTED_EXTENSIONS)
    return stats


@app.get("/api/collections")
async def get_collections():
    return {"collections": list_collections()}


@app.get("/api/tags")
async def get_tags():
    return {"tags": list_tags()}


class UploadMeta(BaseModel):
    tags: Optional[List[str]] = None
    collection: Optional[str] = None


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    tags: Optional[str] = None,
    collection: Optional[str] = None,
):
    dest = Path(UPLOADS_DIR) / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    processing_status[file.filename] = "queued"
    threading.Thread(
        target=_process_file,
        args=(str(dest),),
        kwargs={"tags": tag_list, "collection": collection or "default"},
        daemon=True,
    ).start()
    return {"message": f"Uploaded {file.filename}", "status": "queued"}


@app.delete("/api/documents/{filename}")
async def remove_document(filename: str):
    deleted = delete_document(filename)
    file_path = Path(UPLOADS_DIR) / filename
    if file_path.exists():
        file_path.unlink()
    processing_status.pop(filename, None)
    return {"message": f"Removed {filename}", "chunks_deleted": deleted}


class TagUpdateRequest(BaseModel):
    tags: List[str]
    collection: Optional[str] = None


@app.patch("/api/documents/{filename}/tags")
async def patch_document_tags(filename: str, req: TagUpdateRequest):
    update_document_tags(filename, req.tags, req.collection)
    return {"message": "Tags updated"}


# ── URL Ingestion ──────────────────────────────────────────────────────────────

class URLIngestRequest(BaseModel):
    url: str
    tags: Optional[List[str]] = None
    collection: Optional[str] = None


@app.post("/api/ingest/url")
async def ingest_url(req: URLIngestRequest):
    try:
        result = fetch_url(req.url)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result:
        raise HTTPException(status_code=422, detail="Could not extract content from URL")

    filename = url_to_filename(req.url)
    dest = Path(UPLOADS_DIR) / filename
    with open(dest, "w", encoding="utf-8") as f:
        f.write(f"Title: {result['title']}\nURL: {result['url']}\n\n{result['text']}")

    processing_status[filename] = "queued"
    threading.Thread(
        target=_process_file,
        args=(str(dest),),
        kwargs={
            "tags": req.tags or [],
            "collection": req.collection or "default",
            "source_url": req.url,
        },
        daemon=True,
    ).start()
    return {"message": f"Ingesting {result['title']}", "filename": filename, "status": "queued"}


# ── Notes ──────────────────────────────────────────────────────────────────────

class NoteRequest(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = None
    collection: Optional[str] = None


@app.get("/api/notes")
async def get_notes():
    return {"notes": list_notes()}


@app.post("/api/notes")
async def post_note(req: NoteRequest):
    note = create_note(req.title, req.content)
    # Index in vector store
    note_file = note["path"]
    note_fname = note_filename_for_vector(note["id"])
    processing_status[note_fname] = "queued"
    threading.Thread(
        target=_process_file,
        args=(note_file,),
        kwargs={"tags": req.tags or [], "collection": req.collection or "notes"},
        daemon=True,
    ).start()
    return {"note": note}


@app.get("/api/notes/{note_id}")
async def get_note_endpoint(note_id: str):
    note = get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"note": note}


@app.put("/api/notes/{note_id}")
async def put_note(note_id: str, req: NoteRequest):
    try:
        note = update_note(note_id, req.title, req.content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
    # Re-index
    note_fname = note_filename_for_vector(note_id)
    processing_status[note_fname] = "queued"
    threading.Thread(
        target=_process_file,
        args=(note["path"],),
        kwargs={"tags": req.tags or [], "collection": req.collection or "notes"},
        daemon=True,
    ).start()
    return {"note": note}


@app.delete("/api/notes/{note_id}")
async def delete_note_endpoint(note_id: str):
    note_fname = note_filename_for_vector(note_id)
    delete_document(note_fname)
    ok = delete_note(note_id)
    processing_status.pop(note_fname, None)
    return {"deleted": ok}


# ── Conversation History ───────────────────────────────────────────────────────

class SaveSessionRequest(BaseModel):
    session_id: Optional[str] = None
    messages: List[dict]
    title: Optional[str] = None


class RenameSessionRequest(BaseModel):
    title: str


@app.get("/api/sessions")
async def get_sessions():
    return {"sessions": list_sessions()}


@app.post("/api/sessions")
async def post_session(req: SaveSessionRequest):
    sid = req.session_id or new_session_id()
    data = save_session(sid, req.messages, req.title)
    return {"session": data}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    data = load_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": data}


@app.delete("/api/sessions/{session_id}")
async def del_session(session_id: str):
    ok = delete_session(session_id)
    return {"deleted": ok}


@app.patch("/api/sessions/{session_id}")
async def patch_session(session_id: str, req: RenameSessionRequest):
    ok = rename_session(session_id, req.title)
    return {"renamed": ok}


# ── Google Drive ───────────────────────────────────────────────────────────────

@app.get("/api/drive/files")
async def get_drive_files(q: Optional[str] = ""):
    try:
        files = list_drive_files(query=q, max_results=100)
        return {"files": files}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


class DriveSyncRequest(BaseModel):
    file_ids: List[str]
    tags: Optional[List[str]] = None
    collection: Optional[str] = None


@app.post("/api/drive/sync")
async def post_drive_sync(req: DriveSyncRequest):
    try:
        results = sync_drive_files(req.file_ids)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Trigger ingestion for successfully downloaded files
    for r in results:
        if r.get("status") == "downloaded" and r.get("local_path"):
            name = Path(r["local_path"]).name
            processing_status[name] = "queued"
            threading.Thread(
                target=_process_file,
                args=(r["local_path"],),
                kwargs={"tags": req.tags or [], "collection": req.collection or "default"},
                daemon=True,
            ).start()

    return {"results": results}


# ── Chat ───────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: List[dict]
    collection: Optional[str] = None
    tag: Optional[str] = None


@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    async def generator():
        async for token in chat_stream(req.messages, req.collection, req.tag):
            yield token

    return StreamingResponse(generator(), media_type="text/plain")


@app.post("/api/sources")
async def get_sources(req: ChatRequest):
    query = ""
    for msg in reversed(req.messages):
        if msg["role"] == "user":
            query = msg["content"]
            break
    sources = get_sources_for_query(query, req.collection, req.tag)
    return {"sources": sources}
