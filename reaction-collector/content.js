'use strict';

const STORAGE_KEY = 'pkt_reactions';

const TABS_GOOD  = ['Yêu thích','Yêu thương','Haha','Wow','Thương thương','Like','Love','Care'];
const TABS_ANGRY = ['Buồn','Phẫn nộ','Sad','Angry'];

const SKIP = new Set([
  'search','login','checkpoint','events','groups','marketplace','gaming',
  'watch','help','policies','ads','hashtag','stories','reels','photos',
  'videos','home','notifications','messages','pages','privacy','settings',
  'friends','saved','feed','about','people','posts','reel','photo','video',
]);

// ── Utils ─────────────────────────────────────────────────────────────────────

const sleep = ms => new Promise(r => setTimeout(r, ms));

function cleanUrl(href) {
  try {
    if (!href) return null;
    if (href.includes('l.facebook.com')) {
      const u = new URL(href);
      const t = u.searchParams.get('u');
      if (t) href = decodeURIComponent(t);
    }
    const u = new URL(href, 'https://www.facebook.com');
    if (!['www.facebook.com','facebook.com'].includes(u.hostname)) return null;
    const path = u.pathname.replace(/\/$/, '');
    const segs  = path.split('/').filter(Boolean);
    if (path === '/profile.php') {
      const id = u.searchParams.get('id');
      return id ? `https://www.facebook.com/profile.php?id=${id}` : null;
    }
    if (segs.length === 3 && segs[0] === 'people' && /^\d+$/.test(segs[2]))
      return `https://www.facebook.com/profile.php?id=${segs[2]}`;
    if (segs.length === 1 && !SKIP.has(segs[0].toLowerCase()))
      return `https://www.facebook.com/${segs[0]}`;
    return null;
  } catch { return null; }
}

function toast(msg) {
  const el = Object.assign(document.createElement('div'), { textContent: msg });
  Object.assign(el.style, {
    position:'fixed', bottom:'24px', right:'24px', zIndex:'99999',
    background:'#1877f2', color:'#fff', padding:'10px 16px',
    borderRadius:'8px', font:'14px/1.4 sans-serif',
    boxShadow:'0 2px 8px rgba(0,0,0,.3)', transition:'opacity .3s',
  });
  document.body.appendChild(el);
  setTimeout(() => { el.style.opacity='0'; setTimeout(() => el.remove(), 300); }, 3000);
}

// ── Reaction dialog ───────────────────────────────────────────────────────────

function isReactionDialog(el) {
  return [...el.querySelectorAll('[role="tab"]')].some(t =>
    [...TABS_GOOD, ...TABS_ANGRY].some(k => (t.getAttribute('aria-label') || '').includes(k))
  );
}

function waitForDialog(ms = 5000) {
  const found = document.querySelector('[role="dialog"]');
  if (found && isReactionDialog(found)) return Promise.resolve(found);
  return new Promise(resolve => {
    const obs = new MutationObserver(() => {
      const el = document.querySelector('[role="dialog"]');
      if (el && isReactionDialog(el)) { obs.disconnect(); resolve(el); }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => { obs.disconnect(); resolve(null); }, ms);
  });
}

async function scrapeDialog(dialog, tabNames) {
  const collected = new Set();
  for (const tab of dialog.querySelectorAll('[role="tab"]')) {
    const label = tab.getAttribute('aria-label') || '';
    if (!tabNames.some(k => label.includes(k))) continue;
    tab.click();
    await sleep(700);
    const panel = dialog.querySelector('[role="tabpanel"]');
    if (panel) { panel.scrollTop += 500; await sleep(500); panel.scrollTop += 500; await sleep(500); }
    for (const a of (panel ?? dialog).querySelectorAll('a[href]')) {
      const u = cleanUrl(a.href);
      if (u) collected.add(u);
    }
  }
  return [...collected];
}

async function persist(urls, type, source) {
  const { [STORAGE_KEY]: list = [] } = await chrome.storage.local.get(STORAGE_KEY);
  const seen  = new Set(list.map(e => e.url));
  const added = urls.filter(u => !seen.has(u)).map(u => ({ url: u, type, source, ts: Date.now() }));
  await chrome.storage.local.set({ [STORAGE_KEY]: [...list, ...added] });
  return added.length;
}

// ── Reaction count → click để mở dialog ──────────────────────────────────────

// Tìm nút hiển thị tổng reaction gần likeBtn nhất (trong cùng scope)
function findReactionCount(scope) {
  for (const el of scope.querySelectorAll('[role="button"],[aria-label]')) {
    const label = el.getAttribute('aria-label') || '';
    if (/\d/.test(label) && /thích|cảm xúc|reaction|yêu|like/i.test(label)) return el;
  }
  return null;
}

// ── Core handler ──────────────────────────────────────────────────────────────

async function handleCollect(scope, type, btn) {
  btn.dataset.orig = btn.textContent;
  btn.textContent  = '⏳';
  btn.disabled     = true;
  try {
    findReactionCount(scope)?.click();
    await sleep(400);
    const dialog = await waitForDialog(5000);
    if (!dialog) { toast('⚠️ Không mở được popup reaction — thử click số reaction trước.'); return; }

    const urls  = await scrapeDialog(dialog, type === 'good' ? TABS_GOOD : TABS_ANGRY);
    dialog.querySelector('[aria-label*="Đóng"],[aria-label*="Close"]')?.click();

    const added = await persist(urls, type, location.href);
    toast(`${type === 'good' ? '👍' : '😤'} +${added} mới (${urls.length} link tìm thấy)`);
  } finally {
    btn.textContent = btn.dataset.orig;
    btn.disabled    = false;
  }
}

// ── Inject ────────────────────────────────────────────────────────────────────

const BTN_STYLE = 'font:11px sans-serif;padding:2px 6px;cursor:pointer;border:1px solid #ddd;border-radius:3px;background:#f0f2f5;white-space:nowrap;line-height:1.6;';

// Inject cạnh bất kỳ nút "Thích/Like" nào — post, comment, video đều dùng chung
function injectNearLike(likeBtn) {
  const container = likeBtn.parentElement;
  if (!container || container.dataset.pktDone) return;
  container.dataset.pktDone = '1';

  // Scope để tìm reaction count: article gần nhất hoặc chính container
  const scope = likeBtn.closest('[role="article"]') ?? container;

  const wrap = document.createElement('span');
  wrap.style.cssText = 'display:inline-flex;gap:3px;margin-left:6px;vertical-align:middle;';

  for (const [type, label] of [['good','Block 👍'],['angry','Block 😤']]) {
    const btn = document.createElement('button');
    btn.textContent  = label;
    btn.style.cssText = BTN_STYLE;
    btn.addEventListener('click', e => { e.stopPropagation(); handleCollect(scope, type, btn); });
    wrap.appendChild(btn);
  }
  container.appendChild(wrap);
}

// ── Observer ──────────────────────────────────────────────────────────────────

function scan() {
  document.querySelectorAll('[aria-label="Thích"],[aria-label="Like"]').forEach(injectNearLike);
}

new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
scan();
