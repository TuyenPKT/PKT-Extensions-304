#!/usr/bin/env python3
"""
PKT Facebook Block Tool
Đọc file từ khoá → tìm người → chặn tự động
Usage: python block_tool.py keywords.txt [delay_giây]
"""

import asyncio
import re as _re
import sys
import unicodedata
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from playwright.async_api import async_playwright

PROFILE_DIR = Path(__file__).parent / 'fb_profile'
SKIP_PATHS = {
    'search', 'login', 'checkpoint', 'events', 'groups', 'marketplace',
    'gaming', 'watch', 'help', 'policies', 'ads', 'hashtag', 'stories',
    'reels', 'photos', 'videos', 'home', 'notifications', 'messages',
    'pages', 'privacy', 'settings', 'friends', 'saved', 'feed',
    'about', 'people', 'posts', 'reel', 'photo', 'video', 'watch',
}


def log(entries: list, kind: str, text: str):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'{ts} [{kind:7}] {text}')
    entries.append({'time': datetime.now().isoformat(), 'type': kind, 'text': text})


def nfc(s: str) -> str:
    t = unicodedata.normalize('NFC', s)
    return _re.sub(r'[\xa0​‌‍﻿\s]+', ' ', t).strip()


def split_line(line: str) -> tuple[str, str]:
    """'search_kw &@ match_pattern' → (search_kw, match_pattern). Không có &@ thì cả hai bằng nhau."""
    if '&@' in line:
        left, right = line.split('&@', 1)
        return left.strip(), right.strip()
    return line.strip(), line.strip()


def parse_keyword(match_pattern: str):
    """required: list cụm trong "" — ALL phải có trong tên.
    fallback: set từ ≥3 ký tự — cần ≥2 khớp."""
    p = match_pattern.replace('“', '"').replace('”', '"')
    quoted = [nfc(m).lower() for m in _re.findall(r'"([^"]+)"', p)]
    if quoted:
        return quoted, set()
    words = {w.lower() for w in nfc(match_pattern).split() if len(w) >= 3}
    return [], words


def name_matches(name: str, match_pattern: str) -> bool:
    required, fallback = parse_keyword(match_pattern)
    name_l = nfc(name).lower()
    if required:
        return all(term in name_l for term in required)
    return sum(1 for w in fallback if w in name_l) >= 2


# ── Auto-detect gambling/scam ──────────────────────────────────────────────────

def _strip_diacritics(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def _normalize_detect(s: str) -> str:
    s = _strip_diacritics(s).lower()
    s = _re.sub(r'[^a-z0-9\s]', ' ', s)
    return _re.sub(r'\s+', ' ', s).strip()


_GAMBLING_BLACKLIST = {
    'fun88', 'jun88', 'shbet', 'hi88', 'mb66', 'au88', 'tk88', '78win',
    'gk88', '88vin', 'm88', '188bet', 'w88', 'fb88', '789bet', 'pbv88',
    'open88', 'nohu52', 'sunwin', 'go88', 'web88', 'vi68',
}

_GAMBLING_PATTERNS = [
    _re.compile(r'\b[a-z]{2,4}\d{2,3}\b'),
    _re.compile(r'(bet|win|tai\s*xiu|nohu|casino|slot|game\s*bai)'),
    _re.compile(r'(b[e3]t|w[i1]n|t[a4]i\s*x[i1]u|n[o0]h[u4])'),
    _re.compile(r'\b\w{2,10}\d{2,3}\.(com|net|vip|cc|io)\b'),
]


def is_gambling(name: str) -> bool:
    n = _normalize_detect(name)
    if any(term in n for term in _GAMBLING_BLACKLIST):
        return True
    return any(pat.search(n) for pat in _GAMBLING_PATTERNS)


def should_block(name: str, match_pattern: str) -> bool:
    return name_matches(name, match_pattern) or is_gambling(name)


def _clean_profile_url(href: str):
    from urllib.parse import urlparse, parse_qs, urljoin
    try:
        href = urljoin('https://www.facebook.com', href)
        u = urlparse(href)
        if u.hostname not in ('www.facebook.com', 'facebook.com'):
            return None
        path = u.path.rstrip('/')
        seg = [s for s in path.split('/') if s]
        if path == '/profile.php':
            uid = parse_qs(u.query).get('id', [None])[0]
            return f'https://www.facebook.com/profile.php?id={uid}' if uid else None
        if len(seg) == 3 and seg[0].lower() == 'people' and seg[2].isdigit():
            return f'https://www.facebook.com/profile.php?id={seg[2]}'
        if len(seg) == 1 and seg[0].lower() not in SKIP_PATHS:
            return f'https://www.facebook.com/{seg[0]}'
        return None
    except Exception:
        return None


async def extract_profiles(page, match_pattern: str) -> list[str]:
    try:
        await page.wait_for_selector('[role="feed"]', timeout=15000)
    except Exception:
        await page.wait_for_selector('[role="main"]', timeout=10000)
    await asyncio.sleep(3)

    for _ in range(5):
        await page.keyboard.press('End')
        await asyncio.sleep(1.5)

    elements = await page.query_selector_all('[role="main"] a[href]')
    print(f'  [extract] anchors: {len(elements)}')

    seen: dict[str, str] = {}  # url → best name
    for el in elements:
        try:
            href = await el.get_attribute('href') or ''
            clean_url = _clean_profile_url(href)
            if not clean_url:
                continue
            name = ' '.join((await el.inner_text()).split())
            prev = seen.get(clean_url, '')
            if len(name) > len(prev):
                seen[clean_url] = name
        except Exception:
            continue

    pairs = [{'url': u, 'name': n} for u, n in seen.items()]

    print(f'  [extract] raw: {len(pairs)} links')
    for p in pairs:
        print(f'    "{p["name"][:60]}" → {p["url"][:70]}')

    return [p['url'] for p in pairs if should_block(p['name'], match_pattern)]


async def block_profile(page, url: str) -> str:
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)

        try:
            await page.wait_for_selector('[role="main"] [role="button"]', timeout=15000)
            await asyncio.sleep(1)
        except Exception:
            await asyncio.sleep(5)

        if 'login' in page.url:
            return 'session_expired'

        clicked = await page.evaluate('''() => {
            const direct = document.querySelector(
                '[aria-haspopup="menu"][aria-label*="lựa chọn"],' +
                '[aria-haspopup="menu"][aria-label="More"],' +
                '[aria-haspopup="menu"][aria-label="Thêm"]'
            );
            if (direct) { direct.click(); return true; }
            const pa = document.querySelector('[data-pagelet="ProfileActions"]');
            if (pa) {
                const btn = pa.querySelector('[aria-haspopup="menu"]');
                if (btn) { btn.click(); return true; }
            }
            const all = [...document.querySelectorAll('[role="main"] [aria-haspopup="menu"]')];
            const btn = all.find(b => !b.closest('[role="article"]') && !b.closest('[role="feed"]'));
            if (btn) { btn.click(); return true; }
            return false;
        }''')

        if not clicked:
            labels = await page.evaluate('''() =>
                [...document.querySelectorAll('[aria-label]')]
                .map(e => e.getAttribute('aria-label'))
                .filter(l => l && l.length < 60)
            ''')
            return f'no_more_btn | labels: {labels[:15]}'

        await asyncio.sleep(0.8)

        block_item = page.locator('[role="menuitem"]').filter(
            has_text=_re.compile(r'chặn|block', _re.IGNORECASE)
        ).first

        if not await block_item.count():
            items = await page.locator('[role="menuitem"]').all_text_contents()
            await page.keyboard.press('Escape')
            return f'no_block_option | menu: {items}'

        await block_item.click()
        await asyncio.sleep(1)

        confirm = page.locator('[role="button"]').filter(
            has_text=_re.compile(r'xác nhận|confirm|^chặn$|^block$', _re.IGNORECASE)
        ).last

        if not await confirm.count():
            await page.keyboard.press('Escape')
            return 'no_confirm_btn'

        await confirm.click()
        await asyncio.sleep(10)
        return 'blocked'

    except Exception as e:
        return str(e)[:80]


async def main(keyword_file: str, delay: int):
    kw_path = Path(keyword_file)
    if not kw_path.exists():
        kw_path = Path(__file__).parent.parent / keyword_file
    if not kw_path.exists():
        print(f'Không tìm thấy file: {keyword_file}')
        return

    keywords = [l.strip() for l in kw_path.read_text(encoding='utf-8').splitlines() if l.strip()]
    if not keywords:
        print('File từ khoá rỗng.')
        return

    logs_dir = Path(__file__).parent / 'logs'
    logs_dir.mkdir(exist_ok=True)
    log_path = logs_dir / f'log-{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    entries: list = []

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={'width': 1280, 'height': 800},
            args=['--disable-blink-features=AutomationControlled'],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        await page.goto('https://www.facebook.com', wait_until='domcontentloaded')
        await asyncio.sleep(2)
        if 'login' in page.url or await page.locator('[name="email"]').count():
            log(entries, 'info', 'Chưa đăng nhập — đăng nhập xong nhấn Enter.')
            input()

        log(entries, 'info', f'Bắt đầu: {len(keywords)} từ khoá | delay={delay}s')
        blocked_total = skipped_total = 0

        for ki, line in enumerate(keywords):
            search_kw, match_pattern = split_line(line)
            log(entries, 'info', f'[{ki+1}/{len(keywords)}] Tìm: "{search_kw}" | lọc: "{match_pattern}"')

            try:
                await page.goto(
                    f'https://www.facebook.com/search/pages/?q={quote(search_kw)}',
                    wait_until='domcontentloaded', timeout=20000,
                )
                profiles = await extract_profiles(page, match_pattern)
            except Exception as e:
                log(entries, 'error', f'Lỗi search "{search_kw}": {e}')
                continue

            log(entries, 'info', f'Tìm thấy {len(profiles)} profile')

            for url in profiles:
                result = await block_profile(page, url)
                if result == 'blocked':
                    blocked_total += 1
                    log(entries, 'blocked', f'Đã chặn [{search_kw}] {url}')
                else:
                    skipped_total += 1
                    log(entries, 'skip', f'Bỏ qua [{search_kw}] {url} — {result}')
                await asyncio.sleep(delay)

            await page.goto('https://www.facebook.com', wait_until='domcontentloaded')
            await asyncio.sleep(1)

        log(entries, 'info', f'Hoàn thành | Đã chặn: {blocked_total} | Bỏ qua: {skipped_total}')
        await ctx.close()

    lines = [f'{e["time"]}\t{e["type"]}\t{e["text"]}' for e in entries]
    header = [
        'PKT Facebook Block Tool',
        f'Xuất lúc: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'Đã chặn: {sum(1 for e in entries if e["type"] == "blocked")} | Bỏ qua: {sum(1 for e in entries if e["type"] == "skip")}',
        '', 'Thời gian\tLoại\tNội dung',
    ] + lines
    log_path.write_text('\n'.join(header), encoding='utf-8-sig')
    print(f'\nLog đã lưu: {log_path}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python block_tool.py keywords.txt [delay_giây]')
        sys.exit(1)
    asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3))
