#!/usr/bin/env python3
"""
PKT Facebook Block Tool
Đọc file từ khoá → tìm người → chặn tự động
Usage: python block_tool.py keywords.txt [delay_giây]
"""

import asyncio
import sys
import unicodedata
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

PROFILE_DIR = Path(__file__).parent / 'fb_profile'
SKIP_PATHS = {
    'search', 'login', 'checkpoint', 'events', 'groups', 'marketplace',
    'gaming', 'watch', 'help', 'policies', 'ads', 'hashtag', 'stories',
    'reels', 'photos', 'videos', 'home', 'notifications', 'messages',
    'pages', 'privacy', 'settings', 'friends', 'saved', 'feed',
    'about', 'people', 'posts', 'reel',
}


def log(entries: list, kind: str, text: str):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f'{ts} [{kind:7}] {text}'
    print(line)
    entries.append({'time': datetime.now().isoformat(), 'type': kind, 'text': text})


def nfc(s: str) -> str:
    return unicodedata.normalize('NFC', s)


def keyword_words(kw: str) -> set[str]:
    return {w.lower() for w in nfc(kw).split() if len(w) >= 3}


def name_matches(name: str, kw: str, min_matches: int = 2) -> bool:
    words = keyword_words(kw)
    name_l = nfc(name).lower()
    return sum(1 for w in words if w in name_l) >= min_matches


async def extract_profiles(page, kw: str) -> list[str]:
    """Lấy profile URL từ trang search results đã render, lọc theo keyword."""
    try:
        await page.wait_for_selector('[role="feed"]', timeout=15000)
    except Exception:
        await page.wait_for_selector('[role="main"]', timeout=10000)
    await asyncio.sleep(3)

    # Scroll để load thêm kết quả
    for _ in range(3):
        await page.keyboard.press('End')
        await asyncio.sleep(1)

    pairs = await page.evaluate('''() => {
        const seen = new Map(); // url → best name
        const skip = ''' + str(list(SKIP_PATHS)).replace("'", '"') + ''';

        const main = document.querySelector('[role="main"]');
        if (!main) return [];

        for (const a of main.querySelectorAll('a[href]')) {
            try {
                const url = new URL(a.href);
                if (url.hostname !== 'www.facebook.com') continue;
                const path = url.pathname.replace(/\\/$/, '');
                if (!path || path === '/') continue;
                const seg = path.split('/').filter(Boolean);
                if (seg.length === 0) continue;
                const name = (a.textContent || '').trim();
                let cleanUrl = null;
                // profile.php?id=xxx
                if (path === '/profile.php' && url.searchParams.has('id')) {
                    cleanUrl = 'https://www.facebook.com/profile.php?id=' + url.searchParams.get('id');
                // /people/Name/NUM
                } else if (seg.length === 3 && seg[0].toLowerCase() === 'people' && /^\d+$/.test(seg[2])) {
                    cleanUrl = 'https://www.facebook.com/profile.php?id=' + seg[2];
                } else if (seg.length === 1 && !skip.includes(seg[0].toLowerCase())) {
                    cleanUrl = 'https://www.facebook.com/' + seg[0];
                }
                if (cleanUrl) {
                    const prev = seen.get(cleanUrl);
                    if (!prev || name.length > prev.length) {
                        seen.set(cleanUrl, name);
                    }
                }
            } catch (_) {}
        }
        return [...seen.entries()].map(([url, name]) => ({url, name}));
    }''')

    print(f'  [extract] raw: {len(pairs)} links')
    for p in pairs:
        print(f'    "{p["name"][:50]}" → {p["url"][:70]}')

    filtered = [p['url'] for p in pairs if name_matches(p['name'], kw)]
    return filtered


async def block_profile(page, url: str) -> str:
    """Vào profile → click ... → Block → Confirm. Trả về 'blocked' hoặc lý do skip."""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)

        # Chờ profile render — đợi button xuất hiện trong main content
        try:
            await page.wait_for_selector('[role="main"] [role="button"]', timeout=15000)
            await asyncio.sleep(1)
        except Exception:
            await asyncio.sleep(5)

        # Nếu bị redirect về login
        if 'login' in page.url:
            return 'session_expired'

        # Click nút "..." trên profile header — dùng JS để tránh click nhầm vào post
        clicked = await page.evaluate('''() => {
            // Match trực tiếp theo aria-label đã biết
            const direct = document.querySelector(
                '[aria-label*="lựa chọn"][aria-haspopup="menu"],' +
                '[aria-label="More"][aria-haspopup="menu"],' +
                '[aria-label="Thêm"][aria-haspopup="menu"]'
            );
            if (direct) { direct.click(); return true; }
            // Ưu tiên tìm trong ProfileActions
            const pa = document.querySelector('[data-pagelet="ProfileActions"]');
            if (pa) {
                const btn = pa.querySelector('[aria-haspopup="menu"]');
                if (btn) { btn.click(); return true; }
            }
            // Fallback: haspopup KHÔNG nằm trong article/feed
            const all = [...document.querySelectorAll('[role="main"] [aria-haspopup="menu"]')];
            const profileBtn = all.find(b =>
                !b.closest('[role="article"]') && !b.closest('[role="feed"]')
            );
            if (profileBtn) { profileBtn.click(); return true; }
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

        # Tìm tuỳ chọn Block trong menu
        import re as _re
        block_item = page.locator('[role="menuitem"]').filter(
            has_text=_re.compile(r'chặn|block', _re.IGNORECASE)
        ).first

        if not await block_item.count():
            # Log tất cả menuitem để debug
            items = await page.locator('[role="menuitem"]').all_text_contents()
            await page.keyboard.press('Escape')
            return f'no_block_option | menu: {items}'

        await block_item.click()
        await asyncio.sleep(1)

        # Nút xác nhận — Facebook dùng div[role="button"], không phải <button>
        import re as _re
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
    keywords = [
        l.strip()
        for l in Path(keyword_file).read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]
    if not keywords:
        print('File từ khoá rỗng.')
        return

    log_path = Path(__file__).parent / f'log-{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    entries: list = []

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={'width': 1280, 'height': 800},
            args=['--disable-blink-features=AutomationControlled'],
        )

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Kiểm tra login
        await page.goto('https://www.facebook.com', wait_until='domcontentloaded')
        await asyncio.sleep(2)
        if 'login' in page.url or await page.locator('[name="email"]').count():
            log(entries, 'info', 'Chưa đăng nhập — hãy đăng nhập trong cửa sổ browser, sau đó nhấn Enter ở terminal.')
            input()

        log(entries, 'info', f'Bắt đầu: {len(keywords)} từ khoá | delay={delay}s')

        blocked_total = 0
        skipped_total = 0

        for ki, kw in enumerate(keywords):
            log(entries, 'info', f'[{ki+1}/{len(keywords)}] Tìm kiếm: "{kw}"')

            try:
                await page.goto(
                    f'https://www.facebook.com/search/top/?q={kw}',
                    wait_until='domcontentloaded',
                    timeout=20000,
                )
                profiles = await extract_profiles(page, kw)
            except Exception as e:
                log(entries, 'error', f'Lỗi search "{kw}": {e}')
                continue

            log(entries, 'info', f'Tìm thấy {len(profiles)} profile')

            for url in profiles:
                result = await block_profile(page, url)
                if result == 'blocked':
                    blocked_total += 1
                    log(entries, 'blocked', f'Đã chặn [{kw}] {url}')
                else:
                    skipped_total += 1
                    log(entries, 'skip', f'Bỏ qua [{kw}] {url} — {result}')
                await asyncio.sleep(delay)

            # Quay lại search cho kw tiếp theo
            await page.goto('https://www.facebook.com', wait_until='domcontentloaded')
            await asyncio.sleep(1)

        log(entries, 'info', f'Hoàn thành | Đã chặn: {blocked_total} | Bỏ qua: {skipped_total}')
        await ctx.close()

    # Lưu log
    lines = [f'{e["time"]}\t{e["type"]}\t{e["text"]}' for e in entries]
    header = [
        'PKT Facebook Block Tool',
        f'Xuất lúc: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'Đã chặn: {sum(1 for e in entries if e["type"] == "blocked")} | Bỏ qua: {sum(1 for e in entries if e["type"] == "skip")}',
        '',
        'Thời gian\tLoại\tNội dung',
    ] + lines
    log_path.write_text('\n'.join(header), encoding='utf-8-sig')
    print(f'\nLog đã lưu: {log_path}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python block_tool.py keywords.txt [delay_giây]')
        sys.exit(1)
    asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3))
