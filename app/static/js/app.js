// ── State ──────────────────────────────────────────────────────────────────────
let messages = [];
let streaming = false;
let currentSessionId = null;
let editingNoteId = null;

// ── DOM refs ───────────────────────────────────────────────────────────────────
const messagesEl    = document.getElementById('messages');
const userInput     = document.getElementById('userInput');
const sendBtn       = document.getElementById('sendBtn');
const docList       = document.getElementById('docList');
const statDocs      = document.getElementById('statDocs');
const statChunks    = document.getElementById('statChunks');
const folderPath    = document.getElementById('folderPath');
const sourcesPanel  = document.getElementById('sourcesPanel');
const sourcesToggle = document.getElementById('sourcesToggle');
const sourcesBody   = document.getElementById('sourcesBody');
const uploadZone    = document.getElementById('uploadZone');
const fileInput     = document.getElementById('fileInput');
const urlInput      = document.getElementById('urlInput');
const urlBtn        = document.getElementById('urlBtn');
const collFilter    = document.getElementById('collectionFilter');
const tagFilter     = document.getElementById('tagFilter');
const chatCollFilter= document.getElementById('chatCollectionFilter');
const chatTagFilter = document.getElementById('chatTagFilter');
const chatTitle     = document.getElementById('chatTitle');
const notesList     = document.getElementById('notesList');
const sessionsList  = document.getElementById('sessionsList');
const noteModal     = document.getElementById('noteModal');
const noteTitle     = document.getElementById('noteTitle');
const noteContent   = document.getElementById('noteContent');
const noteTags      = document.getElementById('noteTags');
const noteCollection= document.getElementById('noteCollection');
const saveNoteBtn   = document.getElementById('saveNoteBtn');
const deleteNoteBtn = document.getElementById('deleteNoteBtn');
const driveModal    = document.getElementById('driveModal');
const driveFileList = document.getElementById('driveFileList');


// ── Markdown renderer ──────────────────────────────────────────────────────────
function renderMarkdown(text) {
  // Escape HTML first
  let s = text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

  // Fenced code blocks
  s = s.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code>${code.trimEnd()}</code></pre>`
  );
  // Inline code
  s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  // Bold + italic
  s = s.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // Headers
  s = s.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  s = s.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  s = s.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  // Blockquote
  s = s.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
  // Horizontal rule
  s = s.replace(/^---+$/gm, '<hr>');
  // Unordered lists
  s = s.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  // Ordered lists
  s = s.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  // Wrap consecutive <li> in <ul>
  s = s.replace(/(<li>[\s\S]*?<\/li>)(\s*<li>)/g, '$1$2');
  s = s.replace(/((?:<li>[\s\S]*?<\/li>\s*)+)/g, '<ul>$1</ul>');
  // Links
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // Paragraphs (double newline)
  s = s.split(/\n\n+/).map(block => {
    block = block.trim();
    if (!block) return '';
    if (/^<(h[1-6]|ul|ol|li|pre|blockquote|hr)/.test(block)) return block;
    return `<p>${block.replace(/\n/g, '<br>')}</p>`;
  }).join('');

  return s;
}


// ── Sidebar tabs ───────────────────────────────────────────────────────────────
document.querySelectorAll('.stab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.stab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.stab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});


// ── Messages ───────────────────────────────────────────────────────────────────
function clearWelcome() {
  const el = messagesEl.querySelector('.welcome');
  if (el) el.remove();
}

function appendMessage(role, content) {
  clearWelcome();
  const wrap = document.createElement('div');
  wrap.className = `msg ${role}`;
  wrap.innerHTML = `
    <div class="msg-label">${role === 'user' ? 'You' : 'Brain'}</div>
    <div class="bubble">${renderMarkdown(content)}</div>
  `;
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrap;
}

function appendStreamingMessage() {
  clearWelcome();
  const wrap = document.createElement('div');
  wrap.className = 'msg assistant';
  wrap.innerHTML = `
    <div class="msg-label">Brain</div>
    <div class="bubble"><div class="typing-indicator"><span></span><span></span><span></span></div></div>
  `;
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrap.querySelector('.bubble');
}


// ── Chat ───────────────────────────────────────────────────────────────────────
async function sendMessage() {
  const text = userInput.value.trim();
  if (!text || streaming) return;

  streaming = true;
  sendBtn.disabled = true;
  userInput.value = '';
  userInput.style.height = 'auto';

  messages.push({ role: 'user', content: text });
  appendMessage('user', text);

  const bubble = appendStreamingMessage();
  let fullText = '';

  const collection = chatCollFilter.value || null;
  const tag = chatTagFilter.value || null;

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, collection, tag }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      fullText += decoder.decode(value, { stream: true });
      bubble.innerHTML = renderMarkdown(fullText);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    messages.push({ role: 'assistant', content: fullText });
    fetchSources(messages);

    // Auto-save session
    autoSaveSession();

  } catch (e) {
    bubble.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
  }

  streaming = false;
  sendBtn.disabled = false;
  userInput.focus();
}

async function fetchSources(msgs) {
  try {
    const collection = chatCollFilter.value || null;
    const tag = chatTagFilter.value || null;
    const res = await fetch('/api/sources', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: msgs, collection, tag }),
    });
    const data = await res.json();
    if (data.sources && data.sources.length > 0) showSources(data.sources);
  } catch (_) {}
}

function showSources(sources) {
  // Dedupe by source name
  const seen = new Set();
  const unique = sources.filter(s => {
    if (seen.has(s.source)) return false;
    seen.add(s.source); return true;
  });

  sourcesPanel.style.display = '';
  sourcesBody.innerHTML = unique.map(s => {
    const tagsHtml = s.tags && s.tags.length
      ? `<div class="sc-tags">${s.tags.map(t => `<span class="sc-tag">${t}</span>`).join('')}</div>`
      : '';
    const urlHtml = s.source_url
      ? `<a class="sc-url" href="${s.source_url}" target="_blank" rel="noopener">${s.source_url}</a>`
      : '';
    return `
      <div class="source-chip">
        <span class="sc-name">${s.source}</span>
        ${s.score !== undefined ? `<span class="sc-score">similarity: ${s.score}</span>` : ''}
        ${s.excerpt ? `<span class="sc-excerpt">${s.excerpt}</span>` : ''}
        ${urlHtml}
        ${tagsHtml}
      </div>`;
  }).join('');
}

sourcesToggle.addEventListener('click', () => {
  sourcesPanel.classList.toggle('open');
});


// ── Input auto-resize + send ───────────────────────────────────────────────────
userInput.addEventListener('input', () => {
  userInput.style.height = 'auto';
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
});
userInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
sendBtn.addEventListener('click', sendMessage);


// ── File upload ────────────────────────────────────────────────────────────────
uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault(); uploadZone.classList.remove('drag-over');
  uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', () => uploadFiles(fileInput.files));

async function uploadFiles(files) {
  const collection = collFilter.value !== 'all' ? collFilter.value : 'default';
  const tags = tagFilter.value ? tagFilter.value : '';
  for (const file of files) {
    const fd = new FormData();
    fd.append('file', file);
    if (tags) fd.append('tags', tags);
    if (collection) fd.append('collection', collection);
    try {
      await fetch('/api/upload', { method: 'POST', body: fd });
    } catch (e) { console.error('Upload failed:', e); }
  }
  setTimeout(loadDocs, 600);
}


// ── URL ingestion ──────────────────────────────────────────────────────────────
urlBtn.addEventListener('click', ingestURL);
urlInput.addEventListener('keydown', e => { if (e.key === 'Enter') ingestURL(); });

async function ingestURL() {
  const url = urlInput.value.trim();
  if (!url) return;
  urlBtn.disabled = true;
  urlBtn.textContent = '...';
  try {
    const collection = collFilter.value !== 'all' ? collFilter.value : 'default';
    const res = await fetch('/api/ingest/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, collection }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`URL ingestion failed: ${err.detail}`);
    } else {
      urlInput.value = '';
      setTimeout(loadDocs, 800);
    }
  } catch (e) { alert('Error: ' + e.message); }
  urlBtn.disabled = false;
  urlBtn.textContent = 'Add';
}


// ── Document list ──────────────────────────────────────────────────────────────
function fileIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  const map = {
    pdf: '', docx: '', doc: '', pptx: '', ppt: '',
    txt: '', md: '', csv: '',
    png: '', jpg: '', jpeg: '', gif: '', bmp: '', tiff: '', webp: '',
    mp4: '', mov: '', avi: '', mkv: '', webm: '',
    mp3: '', wav: '', m4a: '',
    json: '', xml: '', html: '', htm: '',
  };
  return map[ext] || '';
}

function statusClass(status) {
  if (!status || status.startsWith('done')) return 'status-done';
  if (status.startsWith('error')) return 'status-error';
  return 'status-processing';
}
function statusLabel(status) {
  if (!status || status.startsWith('done')) return 'ready';
  if (status === 'queued' || status.startsWith('processing')) return 'processing...';
  if (status.startsWith('error')) return 'error';
  return status;
}

async function loadDocs() {
  const cfVal = collFilter.value;
  const collection = cfVal !== 'all' ? cfVal : undefined;
  const [docsRes, statsRes] = await Promise.all([
    fetch('/api/documents' + (collection ? `?collection=${encodeURIComponent(collection)}` : '')).then(r => r.json()),
    fetch('/api/stats').then(r => r.json()),
  ]);

  const docs = docsRes.documents || [];
  statDocs.textContent = `${statsRes.total_documents} docs`;
  statChunks.textContent = `${statsRes.total_chunks} chunks`;
  folderPath.textContent = `Watch: ${statsRes.uploads_dir}`;

  // Populate filter dropdowns
  populateSelect(collFilter, statsRes.collections || [], 'all', 'All collections');
  populateSelect(tagFilter, statsRes.tags || [], '', 'All tags');
  populateSelect(chatCollFilter, statsRes.collections || [], '', 'All collections');
  populateSelect(chatTagFilter, statsRes.tags || [], '', 'All tags');
  populateSelectAppend(document.getElementById('noteCollection'), statsRes.collections || []);
  populateSelectAppend(document.getElementById('driveSyncCollection'), statsRes.collections || []);

  if (docs.length === 0) {
    docList.innerHTML = '<div class="doc-empty">No documents yet</div>';
    return;
  }

  docList.innerHTML = docs.map(doc => {
    const tagsHtml = doc.tags && doc.tags.length
      ? doc.tags.map(t => `<span class="doc-tag">${t}</span>`).join('')
      : '';
    const collHtml = doc.collection && doc.collection !== 'default'
      ? `<span class="doc-coll">${doc.collection}</span>` : '';
    return `
      <div class="doc-item" data-name="${doc.name}">
        <span class="doc-icon">${fileIcon(doc.name)}</span>
        <div class="doc-info">
          <div class="doc-name" title="${doc.name}">${doc.name}</div>
          <div class="doc-meta">${doc.chunks} chunks ${collHtml} ${tagsHtml}</div>
        </div>
        <span class="doc-status ${statusClass(doc.status)}">${statusLabel(doc.status)}</span>
        <button class="doc-delete" title="Remove" data-name="${doc.name}">×</button>
      </div>`;
  }).join('');

  docList.querySelectorAll('.doc-delete').forEach(btn => {
    btn.addEventListener('click', async () => {
      const name = btn.dataset.name;
      if (!confirm(`Remove "${name}" from your knowledge base?`)) return;
      await fetch(`/api/documents/${encodeURIComponent(name)}`, { method: 'DELETE' });
      loadDocs();
    });
  });

  if (docs.some(d => d.status && !d.status.startsWith('done') && !d.status.startsWith('error'))) {
    setTimeout(loadDocs, 2500);
  }
}

function populateSelect(sel, items, blankVal, blankLabel) {
  const cur = sel.value;
  sel.innerHTML = `<option value="${blankVal}">${blankLabel}</option>` +
    items.map(i => `<option value="${i}">${i}</option>`).join('');
  if (items.includes(cur) || cur === blankVal) sel.value = cur;
}

function populateSelectAppend(sel, items) {
  const existing = Array.from(sel.options).map(o => o.value);
  items.forEach(i => {
    if (!existing.includes(i)) {
      const opt = document.createElement('option');
      opt.value = i; opt.textContent = i;
      sel.appendChild(opt);
    }
  });
}

collFilter.addEventListener('change', loadDocs);
tagFilter.addEventListener('change', loadDocs);


// ── Notes ──────────────────────────────────────────────────────────────────────
document.getElementById('newNoteBtn').addEventListener('click', openNewNote);
document.getElementById('closeNoteModal').addEventListener('click', () => { noteModal.style.display = 'none'; });
noteModal.addEventListener('click', e => { if (e.target === noteModal) noteModal.style.display = 'none'; });
saveNoteBtn.addEventListener('click', saveNote);
deleteNoteBtn.addEventListener('click', deleteNoteConfirm);

function openNewNote() {
  editingNoteId = null;
  noteTitle.value = '';
  noteContent.value = '';
  noteTags.value = '';
  noteCollection.value = 'notes';
  deleteNoteBtn.style.display = 'none';
  noteModal.style.display = 'flex';
  noteTitle.focus();
}

function openEditNote(note) {
  editingNoteId = note.id;
  noteTitle.value = note.title;
  noteContent.value = note.content;
  noteTags.value = (note.tags || []).join(', ');
  deleteNoteBtn.style.display = '';
  noteModal.style.display = 'flex';
  noteContent.focus();
}

async function saveNote() {
  const title = noteTitle.value.trim() || 'Untitled';
  const content = noteContent.value.trim();
  const tags = noteTags.value.split(',').map(t => t.trim()).filter(Boolean);
  const collection = noteCollection.value || 'notes';

  if (editingNoteId) {
    await fetch(`/api/notes/${editingNoteId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content, tags, collection }),
    });
  } else {
    await fetch('/api/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content, tags, collection }),
    });
  }
  noteModal.style.display = 'none';
  loadNotes();
  loadDocs();
}

async function deleteNoteConfirm() {
  if (!editingNoteId) return;
  if (!confirm('Delete this note?')) return;
  await fetch(`/api/notes/${editingNoteId}`, { method: 'DELETE' });
  noteModal.style.display = 'none';
  loadNotes();
  loadDocs();
}

async function loadNotes() {
  const res = await fetch('/api/notes').then(r => r.json());
  const notes = res.notes || [];
  if (!notes.length) {
    notesList.innerHTML = '<div class="doc-empty">No notes yet</div>';
    return;
  }
  notesList.innerHTML = notes.map(n => `
    <div class="note-item" data-id="${n.id}">
      <div class="note-name">${n.title}</div>
      <div class="note-meta">${n.modified || ''}</div>
      <div class="note-preview">${n.content.slice(0, 80)}</div>
    </div>`).join('');

  notesList.querySelectorAll('.note-item').forEach(item => {
    item.addEventListener('click', async () => {
      const id = item.dataset.id;
      const res = await fetch(`/api/notes/${id}`).then(r => r.json());
      openEditNote(res.note);
    });
  });
}


// ── Conversation history ───────────────────────────────────────────────────────
document.getElementById('newChatBtn').addEventListener('click', newChat);

function newChat() {
  messages = [];
  currentSessionId = null;
  chatTitle.textContent = 'New conversation';
  messagesEl.innerHTML = `
    <div class="welcome">
      <h2>Ask your second brain anything</h2>
      <p>Upload documents, paste URLs, write notes — then ask questions about them.</p>
    </div>`;
  sourcesPanel.style.display = 'none';
  sourcesBody.innerHTML = '';
  document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
}

async function autoSaveSession() {
  if (messages.length < 2) return;
  const res = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSessionId, messages }),
  });
  const data = await res.json();
  currentSessionId = data.session.id;
  chatTitle.textContent = data.session.title;
  loadSessions();
}

async function loadSession(sid) {
  const res = await fetch(`/api/sessions/${sid}`).then(r => r.json());
  const session = res.session;
  messages = session.messages || [];
  currentSessionId = sid;
  chatTitle.textContent = session.title;

  messagesEl.innerHTML = '';
  messages.forEach(m => appendMessage(m.role, m.content));
  sourcesPanel.style.display = 'none';

  document.querySelectorAll('.session-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === sid);
  });
}

async function loadSessions() {
  const res = await fetch('/api/sessions').then(r => r.json());
  const sessions = res.sessions || [];
  if (!sessions.length) {
    sessionsList.innerHTML = '<div class="doc-empty">No saved chats</div>';
    return;
  }
  sessionsList.innerHTML = sessions.map(s => {
    const date = s.updated ? s.updated.slice(0, 16).replace('T', ' ') : '';
    return `
      <div class="session-item${s.id === currentSessionId ? ' active' : ''}" data-id="${s.id}">
        <span class="session-title" title="${s.title}">${s.title}</span>
        <span class="session-meta">${s.message_count} msgs</span>
        <button class="session-del" title="Delete" data-id="${s.id}">×</button>
      </div>`;
  }).join('');

  sessionsList.querySelectorAll('.session-item').forEach(item => {
    item.addEventListener('click', e => {
      if (e.target.classList.contains('session-del')) return;
      loadSession(item.dataset.id);
    });
  });

  sessionsList.querySelectorAll('.session-del').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Delete this conversation?')) return;
      await fetch(`/api/sessions/${btn.dataset.id}`, { method: 'DELETE' });
      if (btn.dataset.id === currentSessionId) newChat();
      loadSessions();
    });
  });
}


// ── Google Drive ───────────────────────────────────────────────────────────────
document.getElementById('driveBtn').addEventListener('click', () => {
  driveModal.style.display = 'flex';
});
document.getElementById('closeDriveModal').addEventListener('click', () => {
  driveModal.style.display = 'none';
});
driveModal.addEventListener('click', e => { if (e.target === driveModal) driveModal.style.display = 'none'; });

document.getElementById('driveSearchBtn').addEventListener('click', searchDrive);
document.getElementById('driveSearch').addEventListener('keydown', e => {
  if (e.key === 'Enter') searchDrive();
});

async function searchDrive() {
  const q = document.getElementById('driveSearch').value.trim();
  driveFileList.innerHTML = '<div class="doc-empty">Loading...</div>';
  try {
    const res = await fetch(`/api/drive/files?q=${encodeURIComponent(q)}`).then(r => r.json());
    const files = res.files || [];
    if (!files.length) {
      driveFileList.innerHTML = '<div class="doc-empty">No files found</div>';
      return;
    }
    driveFileList.innerHTML = files.map(f => `
      <div class="drive-item">
        <input type="checkbox" value="${f.id}" data-name="${f.name}">
        <span class="di-name" title="${f.name}">${f.name}</span>
        <span class="di-meta">${f.mime.split('.').pop().split('/').pop()}</span>
      </div>`).join('');
  } catch (e) {
    driveFileList.innerHTML = `<div class="doc-empty" style="color:var(--danger)">${e.message}</div>`;
  }
}

document.getElementById('driveSyncBtn').addEventListener('click', async () => {
  const checked = Array.from(driveFileList.querySelectorAll('input[type=checkbox]:checked'));
  if (!checked.length) { alert('Select at least one file.'); return; }
  const file_ids = checked.map(c => c.value);
  const tags = document.getElementById('driveSyncTags').value.split(',').map(t => t.trim()).filter(Boolean);
  const collection = document.getElementById('driveSyncCollection').value || 'default';

  document.getElementById('driveSyncBtn').disabled = true;
  document.getElementById('driveSyncBtn').textContent = 'Syncing...';

  try {
    const res = await fetch('/api/drive/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_ids, tags, collection }),
    });
    const data = await res.json();
    const ok = data.results.filter(r => r.status === 'downloaded').length;
    alert(`Synced ${ok} of ${file_ids.length} file(s). They will appear in the knowledge base shortly.`);
    driveModal.style.display = 'none';
    setTimeout(loadDocs, 1000);
  } catch (e) {
    alert('Sync error: ' + e.message);
  }

  document.getElementById('driveSyncBtn').disabled = false;
  document.getElementById('driveSyncBtn').textContent = 'Sync selected';
});


// ── Init ───────────────────────────────────────────────────────────────────────
loadDocs();
loadNotes();
loadSessions();
setInterval(loadDocs, 10000);
setInterval(loadSessions, 15000);
