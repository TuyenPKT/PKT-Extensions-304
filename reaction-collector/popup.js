'use strict';

const KEY = 'pkt_reactions';

// ── IndexedDB — lưu FileSystemDirectoryHandle qua session ────────────────────

const DB = (() => {
  let _db;
  function open() {
    if (_db) return Promise.resolve(_db);
    return new Promise((res, rej) => {
      const r = indexedDB.open('pkt_db', 1);
      r.onupgradeneeded = e => e.target.result.createObjectStore('kv');
      r.onsuccess       = e => { _db = e.target.result; res(_db); };
      r.onerror         = rej;
    });
  }
  return {
    async get(key) {
      const d = await open();
      return new Promise(res => {
        d.transaction('kv').objectStore('kv').get(key).onsuccess = e => res(e.target.result);
      });
    },
    async set(key, val) {
      const d = await open();
      return new Promise(res => {
        d.transaction('kv', 'readwrite').objectStore('kv').put(val, key).onsuccess = res;
      });
    },
  };
})();

async function getDirHandle() { return DB.get('dirHandle'); }
async function setDirHandle(h) { return DB.set('dirHandle', h); }

async function verifyPermission(handle) {
  const opts = { mode: 'readwrite' };
  if (await handle.queryPermission(opts) === 'granted') return true;
  return await handle.requestPermission(opts) === 'granted';
}

// ── Render ────────────────────────────────────────────────────────────────────

async function render() {
  const { [KEY]: list = [] } = await chrome.storage.local.get(KEY);
  document.getElementById('n-good').textContent  = list.filter(e => e.type === 'good').length;
  document.getElementById('n-angry').textContent = list.filter(e => e.type === 'angry').length;
  document.getElementById('n-total').textContent = list.length;
  document.getElementById('empty-msg').style.display = list.length ? 'none' : 'block';

  const handle = await getDirHandle();
  document.getElementById('dir-path').textContent =
    handle ? `📁 ${handle.name}` : 'Chưa chọn (tải về Downloads)';
}

// ── Export ────────────────────────────────────────────────────────────────────

async function exportJSON() {
  const { [KEY]: list = [] } = await chrome.storage.local.get(KEY);
  if (!list.length) { alert('Chưa có dữ liệu.'); return; }

  const content  = JSON.stringify(list, null, 2);
  const filename = `pkt-reactions-${Date.now()}.json`;
  const handle   = await getDirHandle();

  if (handle) {
    try {
      if (!await verifyPermission(handle)) throw new Error('no-perm');
      const fh = await handle.getFileHandle(filename, { create: true });
      const w  = await fh.createWritable();
      await w.write(content);
      await w.close();
      alert(`Đã lưu: ${handle.name}/${filename}`);
      return;
    } catch {
      // Quyền bị thu hồi hoặc lỗi ghi → fallback download
    }
  }

  // Fallback: trình duyệt tải về Downloads
  Object.assign(document.createElement('a'), {
    href:     URL.createObjectURL(new Blob([content], { type: 'application/json' })),
    download: filename,
  }).click();
}

async function exportCSV() {
  const { [KEY]: list = [] } = await chrome.storage.local.get(KEY);
  if (!list.length) { alert('Chưa có dữ liệu.'); return; }

  const rows = [
    'url,type,source,timestamp',
    ...list.map(e =>
      [e.url, e.type, `"${(e.source || '').replace(/"/g, '""')}"`,
       new Date(e.ts).toISOString()].join(',')
    ),
  ];
  Object.assign(document.createElement('a'), {
    href:     URL.createObjectURL(new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' })),
    download: `pkt-reactions-${Date.now()}.csv`,
  }).click();
}

// ── Events ────────────────────────────────────────────────────────────────────

document.getElementById('choose-dir').addEventListener('click', async () => {
  try {
    const handle = await window.showDirectoryPicker({ mode: 'readwrite' });
    await setDirHandle(handle);
    render();
  } catch { /* user huỷ */ }
});

document.getElementById('export-json').addEventListener('click', exportJSON);
document.getElementById('export-csv').addEventListener('click', exportCSV);

document.getElementById('clear').addEventListener('click', async () => {
  if (!confirm('Xoá toàn bộ dữ liệu đã thu?')) return;
  await chrome.storage.local.remove(KEY);
  render();
});

render();
