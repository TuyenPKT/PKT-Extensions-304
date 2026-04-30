let keywords = [];
let cachedResults = [];

const $ = id => document.getElementById(id);

const fileInput    = $('fileInput');
const btnFile      = $('btnFile');
const fileInfo     = $('fileInfo');
const btnStart     = $('btnStart');
const btnPause     = $('btnPause');
const btnStop      = $('btnStop');
const btnDownload  = $('btnDownload');
const btnResume    = $('btnResume');
const loginWarning = $('loginWarning');
const progressSection = $('progressSection');
const progressFill = $('progressFill');
const progressText = $('progressText');
const statsSection = $('statsSection');
const foundCount   = $('foundCount');
const missCount    = $('missCount');
const logList      = $('logList');
const delayInput   = $('delayInput');

// --- File ---
btnFile.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    keywords = ev.target.result
      .split('\n')
      .map(l => l.trim())
      .filter(l => l.length > 0);
    fileInfo.textContent = `📋 ${file.name} — ${keywords.length} từ khóa`;
    btnStart.disabled = keywords.length === 0;
  };
  reader.readAsText(file, 'UTF-8');
});

// --- Controls ---
btnStart.addEventListener('click', () => {
  cachedResults = [];
  logList.innerHTML = '';
  chrome.runtime.sendMessage({
    type: 'START',
    keywords,
    delay: Math.max(1, parseInt(delayInput.value) || 3) * 1000
  });
});

btnPause.addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'PAUSE' });
});

btnStop.addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'STOP' });
});

btnResume.addEventListener('click', () => {
  loginWarning.style.display = 'none';
  chrome.runtime.sendMessage({ type: 'RESUME' });
});

btnDownload.addEventListener('click', downloadLog);

// --- Lắng nghe thay đổi state từ background (qua session storage) ---
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'session' || !changes.searchState) return;
  applyState(changes.searchState.newValue);
});

// Restore khi popup mở lại
chrome.storage.session.get('searchState', ({ searchState }) => {
  if (searchState) applyState(searchState);
});

function applyState(s) {
  if (!s) return;

  // Sync UI controls
  const active = s.running && !s.paused;
  btnStart.disabled    = s.running || keywords.length === 0;
  btnPause.disabled    = !s.running || s.paused;
  btnStop.disabled     = !s.running;
  btnDownload.disabled = (s.results?.length ?? 0) === 0;

  // Login warning
  loginWarning.style.display = s.loginRequired && s.paused ? 'flex' : 'none';

  // Progress
  const total = s.keywords?.length ?? 0;
  const idx   = s.index ?? 0;
  if (total > 0) {
    progressSection.style.display = 'block';
    statsSection.style.display    = 'flex';
    const pct = Math.round((idx / total) * 100);
    progressFill.style.width = pct + '%';
    progressText.textContent = `${idx} / ${total}  (${pct}%)`;
  } else {
    progressSection.style.display = 'none';
    statsSection.style.display    = 'none';
  }

  // Stats + log (chỉ append item mới)
  const results = s.results ?? [];
  const found   = results.filter(r => r.found).length;
  foundCount.textContent = found;
  missCount.textContent  = results.length - found;

  const existing = logList.children.length;
  for (let i = existing; i < results.length; i++) {
    appendLogItem(results[i]);
  }

  cachedResults = results;
}

function appendLogItem(r) {
  const div = document.createElement('div');
  div.className = `log-item ${r.found ? 'found' : 'not-found'}`;
  const icon  = r.found ? '✅' : '❌';
  const label = r.found ? `(${r.count} kết quả)` : 'không tìm thấy';
  div.textContent = `${icon} ${r.keyword}  ${label}`;
  logList.appendChild(div);
  logList.scrollTop = logList.scrollHeight;
}

function downloadLog() {
  if (cachedResults.length === 0) return;

  const now   = new Date().toLocaleString('vi-VN');
  const found = cachedResults.filter(r => r.found).length;
  const miss  = cachedResults.length - found;

  const header = [
    'PKT Facebook Keyword Search - Log',
    `Thời gian xuất: ${now}`,
    `Tổng: ${cachedResults.length}  |  Tìm thấy: ${found}  |  Không thấy: ${miss}`,
    '',
    'STT\tTừ khóa\tKết quả\tSố lượng\tThời gian'
  ];

  const rows = cachedResults.map((r, i) => {
    const t = new Date(r.time).toLocaleString('vi-VN');
    const status = r.found ? 'TÌM THẤY' : 'KHÔNG THẤY';
    return `${i + 1}\t${r.keyword}\t${status}\t${r.count}\t${t}`;
  });

  const content = [...header, ...rows].join('\n');
  const blob    = new Blob(['﻿' + content], { type: 'text/plain;charset=utf-8' });
  const url     = URL.createObjectURL(blob);
  const a       = document.createElement('a');
  a.href        = url;
  a.download    = `fb-search-${Date.now()}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}
