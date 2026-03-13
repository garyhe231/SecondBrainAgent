# Second Brain Agent

A personal RAG (Retrieval-Augmented Generation) knowledge base powered by Claude and ChromaDB. Upload documents, paste URLs, write notes — then have a conversation with everything you know.

![Python](https://img.shields.io/badge/python-3.9+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green) ![Claude](https://img.shields.io/badge/Claude-Opus%204.6-purple) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Features

- **Multi-format ingestion** — PDF, DOCX, PPTX, TXT, Markdown, CSV, JSON, HTML, images (OCR via Tesseract), video/audio (transcription via Whisper)
- **Web URL ingestion** — paste any URL; the page is scraped, cleaned, and indexed automatically
- **In-app notes** — write and save markdown notes directly in the UI; they are indexed alongside your documents
- **Conversation history** — every chat is auto-saved and can be restored from the History sidebar tab
- **Semantic chunking** — paragraph-aware splitting preserves context better than fixed-size chunks
- **Tags & collections** — organise documents into named collections and tag them; scope Q&A answers to a subset of your knowledge base
- **Google Drive sync** — browse and import files from Google Drive via the `gws` CLI
- **Rich source display** — each answer shows the source filename, similarity score, a text excerpt, any tags, and a backlink for web-ingested pages
- **Streaming responses** — token-by-token streaming from Claude with a typing indicator
- **Dark-theme UI** — clean sidebar + chat layout, no external CSS framework

## Screenshots

```
┌─────────────────────┬──────────────────────────────────────────┐
│  Second Brain       │  New conversation          Scope: All    │
│  Docs | Notes | Hist│                                          │
│ ┌─────────────────┐ │  Brain                                   │
│ │ Drop files here │ │  ┌──────────────────────────────────────┐│
│ └─────────────────┘ │  │ Here's what I found across 3 sources ││
│ [Paste a URL...]    │  │ **report.pdf** mentions...           ││
│ [Google Drive]      │  └──────────────────────────────────────┘│
│                     │                                          │
│ Knowledge Base      │  Sources ▼                               │
│  report.pdf  ready  │  [report.pdf  0.91]  [note: meeting ...]│
│  meeting.md  ready  │                                          │
│  blog.url.txt ready │  ┌──────────────────────────────────────┐│
│                     │  │ Ask anything about your documents... ││
└─────────────────────┴──────────────────────────────────────────┘
```

## Requirements

- Python 3.9+
- An [Anthropic API key](https://console.anthropic.com/)
- Optional: `tesseract` (image OCR), `ffmpeg` + `openai-whisper` (audio/video transcription)
- Optional: `gws` CLI (Google Drive sync)

## Installation

```bash
git clone https://github.com/garyhe231/SecondBrainAgent.git
cd SecondBrainAgent

pip install fastapi uvicorn anthropic chromadb sentence-transformers \
            watchdog pdfplumber python-docx python-pptx \
            beautifulsoup4 requests

# Optional — image OCR
pip install pytesseract pillow
brew install tesseract          # macOS

# Optional — audio/video transcription
pip install openai-whisper
brew install ffmpeg             # macOS
```

## Configuration

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Or create a `.env` file (not committed):

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
python3 run.py
```

Open **http://localhost:8005** in your browser.

### Ingesting content

| Method | How |
|---|---|
| File upload | Drag and drop onto the upload zone, or click to browse |
| URL | Paste a URL in the URL bar and click **Add** |
| Note | Click **Notes** tab → **+ New note** |
| Google Drive | Click **Google Drive**, search, tick files, click **Sync selected** |
| Folder watch | Drop files directly into the `uploads/` directory |

### Organising content

- Assign a **collection** and **tags** when uploading or creating a note
- Use the **filter dropdowns** in the sidebar to view a subset of your knowledge base
- Use the **Scope dropdowns** in the chat header to restrict answers to a collection or tag

### Chat

- Type a question and press **Enter** (or **Shift+Enter** for a new line)
- Click **Sources ▼** below the chat to see which documents were retrieved
- Past conversations appear in the **History** tab and can be restored with a click

## Project structure

```
SecondBrainAgent/
├── run.py                      # Entry point (uvicorn, port 8005)
├── app/
│   ├── main.py                 # FastAPI routes
│   ├── templates/index.html    # Single-page UI
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js
│   └── services/
│       ├── brain.py            # Claude Q&A with RAG context
│       ├── vector_store.py     # ChromaDB wrapper + semantic chunking
│       ├── extractor.py        # Text extraction for all file types
│       ├── watcher.py          # Folder watcher (watchdog)
│       ├── url_ingester.py     # Web scraping + cleaning
│       ├── notes_store.py      # In-app notes (markdown files)
│       ├── history_store.py    # Conversation session persistence
│       └── drive_sync.py       # Google Drive sync via gws CLI
├── uploads/                    # Watched folder (gitignored)
└── data/
    ├── chroma/                 # ChromaDB vector store (gitignored)
    ├── notes/                  # Saved notes as .md files (gitignored)
    └── history/                # Saved chat sessions as .json (gitignored)
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/documents` | List indexed documents |
| POST | `/api/upload` | Upload a file |
| DELETE | `/api/documents/{filename}` | Remove a document |
| PATCH | `/api/documents/{filename}/tags` | Update tags/collection |
| POST | `/api/ingest/url` | Ingest a web URL |
| GET | `/api/notes` | List notes |
| POST | `/api/notes` | Create a note |
| PUT | `/api/notes/{id}` | Update a note |
| DELETE | `/api/notes/{id}` | Delete a note |
| GET | `/api/sessions` | List chat sessions |
| POST | `/api/sessions` | Save a session |
| GET | `/api/sessions/{id}` | Load a session |
| DELETE | `/api/sessions/{id}` | Delete a session |
| GET | `/api/drive/files` | List Google Drive files |
| POST | `/api/drive/sync` | Download and ingest Drive files |
| POST | `/api/chat/stream` | Streaming chat (SSE) |
| POST | `/api/sources` | Get source chunks for a query |
| GET | `/api/stats` | Knowledge base statistics |
| GET | `/api/collections` | List all collections |
| GET | `/api/tags` | List all tags |

## License

MIT
