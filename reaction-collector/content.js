'use strict';

const STORAGE_KEY = 'pkt_reactions';

const TABS_GOOD  = ['Thích','Yêu thích','Yêu thương','Haha','Wow','Thương thương','Like','Love','Care'];
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
  const tabs = [...el.querySelectorAll('[role="tab"]')];
  if (!tabs.length) return false;
  // Ưu tiên match tên tab cụ thể
  if (tabs.some(t => [...TABS_GOOD, ...TABS_ANGRY].some(k => (t.getAttribute('aria-label') || '').includes(k)))) return true;
  // Fallback: dialog có tabs + chứa link profile → đây là reactions dialog
  return el.querySelectorAll('a[href*="facebook.com"], a[href^="/"]').length > 0;
}

function findReactionDialogInDOM() {
  return [...document.querySelectorAll('[role="dialog"]')].find(isReactionDialog) ?? null;
}

function waitForDialog(ms = 5000) {
  const found = findReactionDialogInDOM();
  if (found) { console.log('[PKT] dialog found:', found); return Promise.resolve(found); }
  return new Promise(resolve => {
    const obs = new MutationObserver(() => {
      const el = findReactionDialogInDOM();
      if (el) { console.log('[PKT] dialog appeared:', el); obs.disconnect(); resolve(el); }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => { obs.disconnect(); console.log('[PKT] waitForDialog timeout'); resolve(null); }, ms);
  });
}

function isVisible(el) {
  if (!el.offsetParent && el.tagName !== 'BODY') return false;
  for (let e = el; e && e !== document.body; e = e.parentElement) {
    if (e.hidden || e.getAttribute('aria-hidden') === 'true') return false;
    const s = getComputedStyle(e);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
  }
  return true;
}

function collectLinks(root) {
  const urls = new Set();
  for (const el of root.querySelectorAll('a[href], [role="link"]')) {
    if (!isVisible(el)) continue;
    const href = el.href ?? el.getAttribute('href')
      ?? el.querySelector('a[href]')?.href
      ?? null;
    const u = cleanUrl(href);
    if (u) urls.add(u);
  }
  return urls;
}

function getScrollContainer(root) {
  // Ưu tiên: walk up từ link đầu tiên → scrollable ancestor chứa link đó
  const firstLink = root.querySelector('a[href]');
  if (firstLink) {
    for (let el = firstLink.parentElement; el && el !== root && el !== document.body; el = el.parentElement) {
      const ov = getComputedStyle(el).overflowY;
      if (ov === 'scroll' || ov === 'auto') {
        console.log('[PKT] scrollContainer (from link):', el.scrollHeight, el.clientHeight, el);
        return el;
      }
    }
  }
  // Fallback: div đầu tiên có overflow
  for (const el of root.querySelectorAll('div')) {
    if (el.getAttribute('aria-hidden') === 'true') continue;
    const ov = getComputedStyle(el).overflowY;
    if ((ov === 'scroll' || ov === 'auto') && el.scrollHeight > el.clientHeight + 20) {
      console.log('[PKT] scrollContainer (overflow):', el.scrollHeight, el.clientHeight, el);
      return el;
    }
  }
  return root;
}

const rand = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

// Dispatch full mouse event — một số React component cần chuỗi đầy đủ
function fbClick(el) {
  ['mousedown','mouseup','click'].forEach(type =>
    el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }))
  );
}

// Tìm container chứa reaction list — trong dialog hoặc portal ngoài
async function findReactionList(dialog, ms = 5000) {
  for (let t = 0; t < ms; t += 300) {
    await sleep(300);
    // Trong dialog
    if (dialog.querySelectorAll('a[href]').length > 0) {
      const c = getScrollContainer(dialog);
      console.log('[PKT] reactionList inside dialog:', c.scrollHeight, c.clientHeight);
      return c;
    }
    // Portal ngoài dialog: [role="list"] hoặc overflow div có profile links
    for (const el of document.querySelectorAll('[role="list"], div')) {
      if (dialog.contains(el) || !isVisible(el)) continue;
      const ov = el.tagName === 'DIV' ? getComputedStyle(el).overflowY : 'auto';
      if (el.getAttribute('role') !== 'list' && ov !== 'scroll' && ov !== 'auto') continue;
      const links = el.querySelectorAll('a[href]');
      if (links.length > 0 && cleanUrl(links[0].href)) {
        console.log('[PKT] reactionList portal:', el.scrollHeight, el.clientHeight, el);
        return el;
      }
    }
  }
  console.log('[PKT] findReactionList timeout');
  return null;
}

async function scrollAndCollect(container) {
  console.log('[PKT] scrollAndCollect:', container.scrollHeight, container.clientHeight, container.scrollTop);
  const collected = new Set();
  let noNewCount = 0;
  let lastCount = -1;

  while (noNewCount < 3) {
    const steps = rand(3, 6);
    for (let s = 0; s < steps; s++) {
      container.scrollTop += rand(60, 160);
      await sleep(rand(80, 200));
    }
    await sleep(rand(800, 1500));

    const rawCount = container.querySelectorAll('a[href], [role="link"]').length;
    const cur = collectLinks(container);
    console.log(`[PKT] scrollTop=${container.scrollTop} raw=${rawCount} links=${cur.size}`);

    if (rawCount === lastCount) {
      noNewCount++;
    } else {
      noNewCount = 0;
      lastCount = rawCount;
      cur.forEach(u => collected.add(u));
    }
  }
  console.log('[PKT] scroll done, total:', collected.size);
  return collected;
}

function findSeeMore(dialog) {
  return [...dialog.querySelectorAll('[role="tab"],[role="button"]')]
    .find(el => /xem thêm|see more/i.test(el.textContent || ''));
}

async function scrapeDialog(dialog, tabNames, useFallback = true) {
  const collected = new Set();

  // Lấy labels của regular tabs (không có seeMore)
  const regularTabLabels = [...dialog.querySelectorAll('[role="tab"]')]
    .filter(t => !/xem thêm|see more/i.test(t.textContent || ''))
    .map(t => t.getAttribute('aria-label') || t.textContent || '');

  // Tìm target labels khớp với tabNames
  let targetLabels = tabNames.filter(k => regularTabLabels.some(l => l.includes(k)));
  const needsDropdown = tabNames.filter(k => !targetLabels.includes(k));

  console.log('[PKT] regularTabLabels:', regularTabLabels.map(l => l.slice(0, 40)));

  async function doCollect(clickFn, label) {
    if (!document.contains(dialog)) return;
    clickFn();
    // Đợi old content clear trước (tab switch làm dialog reload content)
    await sleep(800);
    console.log('[PKT] waiting for content after:', label?.slice(0, 50));
    const container = await findReactionList(dialog);
    if (!container) { console.log('[PKT] no content for:', label); return; }
    container.scrollTop = 0;
    await sleep(300);
    const urls = await scrollAndCollect(container);
    urls.forEach(u => collected.add(u));
  }

  const seeMore = findSeeMore(dialog);

  if (seeMore) {
    // Mở dropdown 1 lần để lấy labels
    seeMore.click();
    await sleep(700);
    const dropdownTargets = [...document.querySelectorAll('[role="menuitemradio"]')]
      .filter(el => tabNames.some(k => (el.getAttribute('aria-label') || '').includes(k)))
      .map(el => el.getAttribute('aria-label')).filter(Boolean);
    console.log('[PKT] dropdownTargets:', dropdownTargets.map(l => l.slice(0,50)));
    // Đóng
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await sleep(400);

    for (const label of dropdownTargets) {
      if (!document.contains(dialog)) break;
      const sm = findSeeMore(dialog);
      if (!sm) { console.log('[PKT] seeMore gone'); break; }
      sm.click();
      await sleep(700);
      const item = [...document.querySelectorAll('[role="menuitemradio"]')]
        .find(el => el.getAttribute('aria-label') === label);
      if (!item) { console.log('[PKT] item not found:', label); continue; }
      await doCollect(() => item.click(), label);
    }

    // Regular tabs không có trong dropdown
    const dropdownSet = new Set(dropdownTargets);
    for (const tab of dialog.querySelectorAll('[role="tab"]')) {
      const label = tab.getAttribute('aria-label') || '';
      if (!tabNames.some(k => label.includes(k))) continue;
      if (dropdownSet.has(label)) continue;
      await doCollect(() => fbClick(tab), label);
    }
  } else {
    // Không có seeMore → click regular tabs
    for (const tab of dialog.querySelectorAll('[role="tab"]')) {
      const label = tab.getAttribute('aria-label') || tab.textContent || '';
      if (!tabNames.some(k => label.includes(k))) continue;
      await doCollect(() => fbClick(tab), label);
    }
    // Fallback nếu không tìm được tab nào
    if (!collected.size && useFallback) {
      console.log('[PKT] fallback direct');
      const container = await findReactionList(dialog, 3000);
      if (container) {
        const urls = await scrollAndCollect(container);
        urls.forEach(u => collected.add(u));
      }
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
  const allBtns = [...scope.querySelectorAll('[role="button"]')];
  console.log('[PKT] scope:', scope, '| buttons:', allBtns.length);
  allBtns.forEach((el, i) => {
    const label = el.getAttribute('aria-label') || '';
    const txt = (el.textContent || '').trim().slice(0, 80);
    if (label || /\d/.test(txt)) console.log(`[PKT] btn[${i}] label=${JSON.stringify(label)} txt=${JSON.stringify(txt)}`);
  });

  // Strategy 0: textContent chứa "cảm xúc" + số → "Tất cả cảm xúc:607"
  for (const el of scope.querySelectorAll('[role="button"]')) {
    const txt = (el.textContent || '').trim();
    if (/cảm xúc/i.test(txt) && /\d/.test(txt)) {
      console.log('[PKT] S0 matched:', JSON.stringify(txt.slice(0, 40))); return el;
    }
  }
  // Strategy 1: aria-label chứa số + "cảm xúc/reaction"
  for (const el of scope.querySelectorAll('[role="button"],[aria-label]')) {
    const label = el.getAttribute('aria-label') || '';
    if (/\d/.test(label) && /cảm xúc|reaction/i.test(label)) {
      console.log('[PKT] S1 matched:', JSON.stringify(label)); return el;
    }
  }
  // Strategy 2: emoji reaction + số trong textContent
  for (const el of scope.querySelectorAll('[role="button"]')) {
    const txt = el.textContent || '';
    if (/[\u{1F44D}\u{2764}\u{1F602}\u{1F62E}\u{1F622}\u{1F621}\u{1F97A}\u{1F615}]/u.test(txt) && /\d/.test(txt)) {
      console.log('[PKT] S2 matched:', JSON.stringify(txt.slice(0, 40))); return el;
    }
  }
  // Strategy 3: aria-label chỉ là số thuần
  for (const el of scope.querySelectorAll('[role="button"][aria-label]')) {
    const label = el.getAttribute('aria-label') || '';
    if (/^[\d.,\s]+$/.test(label.trim())) {
      console.log('[PKT] S3 matched:', JSON.stringify(label)); return el;
    }
  }
  console.warn('[PKT] không tìm thấy nút reaction count');
  return null;
}

// ── Lấy URL post thực từ article (timestamp link) ────────────────────────────

function getPostUrl(scope) {
  for (const a of scope.querySelectorAll('a[href]')) {
    const h = a.href;
    if (/facebook\.com\/.+\/posts\/\d+/.test(h)) return h.split('?')[0];
    if (/facebook\.com\/permalink\.php/.test(h)) return h.split('&')[0];
    if (/facebook\.com\/.+\/videos\/\d+/.test(h)) return h.split('?')[0];
    if (/facebook\.com\/photo(s)?\?/.test(h)) return h;
    if (/facebook\.com\/reel\/\d+/.test(h)) return h.split('?')[0];
  }
  return location.href;
}

// ── Core handler ──────────────────────────────────────────────────────────────

let _collecting = false;

async function handleCollect(scope, type, btn) {
  if (_collecting) { toast('⏳ Đang thu thập bài khác, vui lòng đợi...'); return; }
  _collecting = true;
  btn.dataset.orig = btn.textContent;
  btn.textContent  = '⏳';
  btn.disabled     = true;
  try {
    const rcBtn = findReactionCount(scope);
    if (!rcBtn) {
      toast('⚠️ Không tìm thấy nút đếm reaction — hãy click thủ công vào số reaction.');
      return;
    }
    console.log('[PKT] clicking rcBtn:', rcBtn);
    rcBtn.click();
    await sleep(600);
    console.log('[PKT] after click — dialogs:', document.querySelectorAll('[role="dialog"]').length);
    const dialog = await waitForDialog(6000);
    if (!dialog) { toast('⚠️ Popup reaction chưa xuất hiện — thử lại hoặc click số reaction thủ công.'); return; }

    const urls  = await scrapeDialog(dialog, type === 'good' ? TABS_GOOD : TABS_ANGRY, type === 'good');

    const added = await persist(urls, type, getPostUrl(scope));
    toast(`${type === 'good' ? '👍' : '😤'} +${added} mới (${urls.length} link tìm thấy)`);
  } finally {
    _collecting = false;
    btn.textContent = btn.dataset.orig;
    btn.disabled    = false;
  }
}

// ── Inject ────────────────────────────────────────────────────────────────────

const BTN_STYLE = 'font:11px sans-serif;padding:2px 6px;cursor:pointer;border:1px solid #ddd;border-radius:3px;background:#f0f2f5;white-space:nowrap;line-height:1.6;';

// Walk up DOM để tìm container đủ rộng (có chứa links = khu vực reaction/profile)
function getPostScope(likeBtn) {
  const article = likeBtn.closest('[role="article"]');
  if (article) return article;
  // Walk up tối đa 12 cấp đến khi tìm container có chứa <a href>
  let el = likeBtn.parentElement;
  for (let i = 0; i < 12 && el && el !== document.body; i++) {
    if (el.querySelector('a[href]')) return el;
    el = el.parentElement;
  }
  return likeBtn.parentElement;
}

// Inject cạnh bất kỳ nút "Thích/Like" nào — post, comment, video đều dùng chung
function injectNearLike(likeBtn) {
  const container = likeBtn.parentElement;
  if (!container || container.dataset.pktDone) return;
  container.dataset.pktDone = '1';

  const scope = getPostScope(likeBtn);

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
