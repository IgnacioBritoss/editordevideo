const API_BASE = 'http://localhost:8000';

let selectedFile = null;
let pollTimer = null;

// ── SCREENS ──────────────────────────────────────────────────────────────────

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function resetApp() {
  clearInterval(pollTimer);
  selectedFile = null;
  document.getElementById('file-input').value = '';
  document.getElementById('file-name').textContent = '';
  document.getElementById('file-name').classList.add('hidden');
  document.getElementById('btn-generate').disabled = true;
  showScreen('screen-upload');
}

// ── FILE SELECTION ────────────────────────────────────────────────────────────

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('dragging');
});

dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragging'));

dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragging');
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('audio/')) setFile(file);
});

function setFile(file) {
  selectedFile = file;
  const nameEl = document.getElementById('file-name');
  nameEl.textContent = `${file.name} (${formatSize(file.size)})`;
  nameEl.classList.remove('hidden');
  document.getElementById('btn-generate').disabled = false;
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// ── GENERATION ───────────────────────────────────────────────────────────────

async function startGeneration() {
  if (!selectedFile) return;

  showScreen('screen-progress');
  setProgress(0, 'Subiendo audio...');

  const formData = new FormData();
  formData.append('file', selectedFile);

  let jobId;
  try {
    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(`Error al subir: ${res.status}`);
    const data = await res.json();
    jobId = data.job_id;
  } catch (err) {
    showError(`No se pudo conectar al backend (${err.message}).\n¿Está corriendo el servidor? Ejecutá: uvicorn main:app`);
    return;
  }

  pollTimer = setInterval(() => pollStatus(jobId), 1500);
}

async function pollStatus(jobId) {
  try {
    const res = await fetch(`${API_BASE}/status/${jobId}`);
    const job = await res.json();

    setProgress(job.progress, job.message);

    if (job.status === 'done') {
      clearInterval(pollTimer);
      showResult(jobId);
    } else if (job.status === 'error') {
      clearInterval(pollTimer);
      showError(job.message);
    }
  } catch (err) {
    // Ignore transient network errors during polling
  }
}

function setProgress(pct, msg) {
  document.getElementById('progress-bar').style.width = `${pct}%`;
  document.getElementById('progress-pct').textContent = `${pct}%`;
  if (msg) document.getElementById('progress-message').textContent = msg;
}

function showResult(jobId) {
  const videoUrl = `${API_BASE}/download/${jobId}`;
  const player = document.getElementById('video-player');
  player.src = videoUrl;
  player.load();

  document.getElementById('btn-download').href = videoUrl;

  showScreen('screen-result');
  player.play().catch(() => {});
}

function showError(msg) {
  document.getElementById('error-message').textContent = msg;
  showScreen('screen-error');
}
