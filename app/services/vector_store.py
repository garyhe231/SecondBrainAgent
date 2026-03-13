"""
ChromaDB-backed vector store with semantic chunking, collections/tags, and excerpt retrieval.
"""
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.utils import embedding_functions

DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "chroma")
COLLECTION_NAME = "second_brain"

# Chunking parameters
CHUNK_TARGET = 600       # target chars per chunk
CHUNK_MAX = 900          # hard max before force-split
CHUNK_OVERLAP = 120      # overlap between consecutive chunks

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=DB_PATH)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# ── Semantic chunking ─────────────────────────────────────────────────────────

def _split_paragraphs(text: str) -> List[str]:
    """Split on blank lines (markdown / prose paragraph boundaries)."""
    blocks = re.split(r"\n\s*\n", text)
    return [b.strip() for b in blocks if b.strip()]


def chunk_text(text: str) -> List[str]:
    """
    Semantic paragraph-aware chunking.
    Tries to keep paragraphs together up to CHUNK_TARGET, then overlaps by CHUNK_OVERLAP chars.
    Falls back to hard splits for very long paragraphs.
    """
    paragraphs = _split_paragraphs(text)
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for para in paragraphs:
        # If single paragraph exceeds max, force-split it
        if len(para) > CHUNK_MAX:
            # Flush current accumulation first
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            # Hard split with overlap
            start = 0
            while start < len(para):
                end = start + CHUNK_MAX
                chunks.append(para[start:end].strip())
                start += CHUNK_MAX - CHUNK_OVERLAP
            continue

        if current_len + len(para) > CHUNK_TARGET and current:
            chunks.append("\n\n".join(current))
            # Overlap: carry last paragraph into next chunk
            overlap_para = current[-1] if current else ""
            current = [overlap_para, para] if overlap_para else [para]
            current_len = len(overlap_para) + len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        chunks.append("\n\n".join(current))

    return [c for c in chunks if c.strip()]


# ── Ingest / delete ───────────────────────────────────────────────────────────

def ingest_document(
    file_path: str,
    text: str,
    tags: Optional[List[str]] = None,
    collection: Optional[str] = None,
    source_url: Optional[str] = None,
) -> int:
    """Chunk and upsert a document. Returns number of chunks added."""
    col = _get_collection()
    file_name = Path(file_path).name

    # Remove existing chunks for this file
    existing = col.get(where={"source": file_name})
    if existing["ids"]:
        col.delete(ids=existing["ids"])

    chunks = chunk_text(text)
    if not chunks:
        return 0

    ids, documents, metadatas = [], [], []
    tags_str = ",".join(tags) if tags else ""
    collection_str = collection or "default"

    for i, chunk in enumerate(chunks):
        chunk_id = hashlib.md5(f"{file_path}::{i}".encode()).hexdigest()
        ids.append(chunk_id)
        documents.append(chunk)
        meta = {
            "source": file_name,
            "chunk": i,
            "file_path": file_path,
            "tags": tags_str,
            "collection": collection_str,
        }
        if source_url:
            meta["source_url"] = source_url
        metadatas.append(meta)

    col.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(chunks)


def delete_document(file_name: str) -> int:
    """Remove all chunks for a file. Returns count deleted."""
    col = _get_collection()
    existing = col.get(where={"source": file_name})
    if existing["ids"]:
        col.delete(ids=existing["ids"])
        return len(existing["ids"])
    return 0


def update_document_tags(file_name: str, tags: List[str], collection: Optional[str] = None):
    """Re-tag all chunks for a file without re-ingesting."""
    col = _get_collection()
    existing = col.get(where={"source": file_name})
    if not existing["ids"]:
        return
    tags_str = ",".join(tags)
    new_metadatas = []
    for meta in existing["metadatas"]:
        m = dict(meta)
        m["tags"] = tags_str
        if collection is not None:
            m["collection"] = collection
        new_metadatas.append(m)
    col.update(ids=existing["ids"], metadatas=new_metadatas)


# ── Search ────────────────────────────────────────────────────────────────────

def search(
    query: str,
    n_results: int = 8,
    collection_filter: Optional[str] = None,
    tag_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic search. Returns list of {text, source, chunk, tags, collection, source_url, excerpt}.
    Optional collection_filter and tag_filter narrow results.
    """
    col = _get_collection()
    count = col.count()
    if count == 0:
        return []

    n = min(n_results, count)

    where = None
    if collection_filter and collection_filter != "all":
        where = {"collection": collection_filter}

    results = col.query(
        query_texts=[query],
        n_results=n,
        where=where,
    )

    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        tags_raw = meta.get("tags", "")
        tags = [t for t in tags_raw.split(",") if t] if tags_raw else []

        # Tag filter (client-side, since Chroma where on substring is limited)
        if tag_filter and tag_filter not in tags:
            continue

        # Build a short excerpt (first 200 chars, clean whitespace)
        excerpt = re.sub(r"\s+", " ", doc[:200]).strip()
        if len(doc) > 200:
            excerpt += "…"

        output.append({
            "text": doc,
            "excerpt": excerpt,
            "source": meta.get("source", "unknown"),
            "chunk": meta.get("chunk", 0),
            "tags": tags,
            "collection": meta.get("collection", "default"),
            "source_url": meta.get("source_url", ""),
            "score": round(1 - dist, 3),  # cosine similarity
        })

    return output


# ── Listing / stats ───────────────────────────────────────────────────────────

def list_documents(collection_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return list of ingested documents with chunk counts, tags, collections."""
    col = _get_collection()
    all_items = col.get()
    doc_map: Dict[str, Dict[str, Any]] = {}

    for meta in all_items["metadatas"]:
        src = meta.get("source", "unknown")
        if src not in doc_map:
            doc_map[src] = {
                "name": src,
                "chunks": 0,
                "tags": set(),
                "collection": meta.get("collection", "default"),
                "source_url": meta.get("source_url", ""),
            }
        doc_map[src]["chunks"] += 1
        tags_raw = meta.get("tags", "")
        if tags_raw:
            for t in tags_raw.split(","):
                if t:
                    doc_map[src]["tags"].add(t)

    result = []
    for name, info in sorted(doc_map.items()):
        if collection_filter and collection_filter != "all" and info["collection"] != collection_filter:
            continue
        result.append({
            "name": info["name"],
            "chunks": info["chunks"],
            "tags": sorted(info["tags"]),
            "collection": info["collection"],
            "source_url": info["source_url"],
        })
    return result


def list_collections() -> List[str]:
    """Return all distinct collection names."""
    col = _get_collection()
    all_items = col.get()
    colls = set()
    for meta in all_items["metadatas"]:
        c = meta.get("collection", "default")
        if c:
            colls.add(c)
    return sorted(colls)


def list_tags() -> List[str]:
    """Return all distinct tags."""
    col = _get_collection()
    all_items = col.get()
    tags = set()
    for meta in all_items["metadatas"]:
        raw = meta.get("tags", "")
        if raw:
            for t in raw.split(","):
                if t:
                    tags.add(t)
    return sorted(tags)


def get_stats() -> Dict[str, Any]:
    col = _get_collection()
    total_chunks = col.count()
    docs = list_documents()
    return {
        "total_chunks": total_chunks,
        "total_documents": len(docs),
        "collections": list_collections(),
        "tags": list_tags(),
    }
