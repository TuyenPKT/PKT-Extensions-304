// State lưu trong session storage để survive service worker restart
const INIT_STATE = {
  keywords: [],
  index: 0,
  results: [],
  running: false,
  paused: false,
  tabId: null,
  delay: 2000
};

async function getState() {
  const { searchState } = await chrome.storage.session.get('searchState');
  return searchState ?? { ...INIT_STATE };
}

async function setState(patch) {
  const cur = await getState();
  const next = { ...cur, ...patch };
  await chrome.storage.session.set({ searchState: next });
  return next;
}

// --- Message handler từ popup ---
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  handleMessage(msg).then(sendResponse).catch(e => sendResponse({ error: e.message }));
  return true;
});

async function handleMessage(msg) {
  switch (msg.type) {
    case 'START': {
      await setState({
        ...INIT_STATE,
        keywords: msg.keywords,
        delay: msg.delay ?? 2000,
        running: true
      });
      processNext();
      return { ok: true };
    }
    case 'PAUSE':
      await setState({ paused: true });
      return { ok: true };

    case 'RESUME': {
      await setState({ paused: false });
      processNext();
      return { ok: true };
    }
    case 'STOP': {
      const s = await getState();
      if (s.tabId) {
        try { await chrome.tabs.remove(s.tabId); } catch {}
      }
      await setState({ ...INIT_STATE });
      return { ok: true };
    }
    default:
      return { error: 'unknown' };
  }
}

// --- Lắng nghe tab load xong ---
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== 'complete') return;

  const s = await getState();
  if (tabId !== s.tabId || !s.running || s.paused) return;

  const url = tab.url ?? '';

  // Facebook yêu cầu đăng nhập
  if (url.includes('facebook.com/login') || url.includes('facebook.com/checkpoint')) {
    await setState({ paused: true, loginRequired: true });
    return;
  }

  if (!url.includes('facebook.com/search')) return;

  // SW sống ít nhất 30s sau event — 4.5s wait an toàn
  setTimeout(() => checkResults(tabId), 4500);
});

async function processNext() {
  const s = await getState();
  if (!s.running || s.paused) return;

  if (s.index >= s.keywords.length) {
    await setState({ running: false });
    return;
  }

  const keyword = s.keywords[s.index];
  const url = `https://www.facebook.com/search/top/?q=${encodeURIComponent(keyword)}`;

  let { tabId } = s;
  if (!tabId) {
    const tab = await chrome.tabs.create({ url, active: false });
    tabId = tab.id;
    await setState({ tabId });
  } else {
    try {
      await chrome.tabs.get(tabId);
      chrome.tabs.update(tabId, { url });
    } catch {
      const tab = await chrome.tabs.create({ url, active: false });
      tabId = tab.id;
      await setState({ tabId });
    }
  }
}

async function checkResults(tabId) {
  const s = await getState();
  if (!s.running || s.paused || tabId !== s.tabId) return;

  let found = false;
  let count = 0;

  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId },
      func: detectResults
    });
    found = res.result.found;
    count = res.result.count;
  } catch {
    // Tab đóng hoặc lỗi → ghi not found
  }

  const keyword = s.keywords[s.index];
  const entry = { keyword, found, count, time: Date.now() };
  const results = [...s.results, entry];

  await setState({ index: s.index + 1, results });

  setTimeout(() => processNext(), s.delay);
}

// Chạy trong context của trang Facebook
function detectResults() {
  const articles = document.querySelectorAll('[role="article"]');

  const NO_RESULT_TEXTS = [
    'No results found',
    'Không có kết quả',
    'Không tìm thấy kết quả',
    'Try different keywords',
    'Try different search terms'
  ];
  const bodyText = document.body?.innerText ?? '';
  const hasNoResult = NO_RESULT_TEXTS.some(t => bodyText.includes(t));

  const count = articles.length;
  const found = count > 0 && !hasNoResult;

  return { found, count };
}
