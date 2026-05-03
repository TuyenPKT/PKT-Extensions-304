#!/usr/bin/env python3
"""
PKT Facebook Block Tool
Đọc file từ khoá → tìm người → chặn tự động
Usage: python block_tool.py keywords.txt [delay_giây]
"""

import asyncio
import random
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

_LOOKALIKE = str.maketrans({
    # Cyrillic → Latin
    'А':'A','В':'B','С':'C','Е':'E','Н':'H','І':'I','К':'K','М':'M',
    'О':'O','Р':'P','Ѕ':'S','Т':'T','Х':'X','Ү':'Y','Ѡ':'W',
    'а':'a','с':'c','е':'e','о':'o','р':'p','х':'x','і':'i',
    'Ԁ':'D','ԁ':'d','п':'n','н':'h','һ':'h','ʜ':'H',
    # Latin small capitals / IPA
    'ᴀ':'a','ʙ':'b','ᴄ':'c','ᴅ':'d','ᴇ':'e','ꜰ':'f','ɢ':'g',
    'ɪ':'i','ᴊ':'j','ᴋ':'k','ʟ':'l','ᴍ':'m','ɴ':'n','ᴏ':'o',
    'ᴘ':'p','ʀ':'r','ꜱ':'s','ᴛ':'t','ᴜ':'u','ᴠ':'v','ᴡ':'w',
    'ʏ':'y','ᴢ':'z',
    # Greek
    'α':'a','β':'b','ε':'e','ι':'i','κ':'k','ο':'o',
    'ρ':'p','τ':'t','υ':'u','χ':'x','ω':'w',
    # Fullwidth digits
    '０':'0','１':'1','２':'2','３':'3','４':'4',
    '５':'5','６':'6','７':'7','８':'8','９':'9',
})


def _strip_diacritics(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def _normalize_detect(s: str) -> str:
    s = s.translate(_LOOKALIKE)
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

# Build ASCII → {unicode variants} từ _LOOKALIKE (đảo ngược map)
def _build_char_classes():
    from collections import defaultdict
    inv = defaultdict(set)
    for codepoint, asc in _LOOKALIKE.items():
        inv[asc.lower()].add(chr(codepoint))
    return dict(inv)

_CHAR_VARIANTS = _build_char_classes()


def keyword_to_variant_regex(kw: str) -> _re.Pattern:
    """'SHBET' → [ЅS][НʜH][ВB][ЕE][ТT] — match mọi biến thể Unicode."""
    def char_class(ch):
        ch_l = ch.lower()
        variants = _CHAR_VARIANTS.get(ch_l, set()) | {ch_l, ch_l.upper()}
        if len(variants) == 1:
            return _re.escape(ch_l)
        def esc(c):
            return ('\\' + c) if c in r']\^-' else c
        return '[' + ''.join(esc(c) for c in sorted(variants)) + ']'
    return _re.compile(''.join(char_class(c) for c in kw), _re.IGNORECASE)


# Pre-build variant regex cho mỗi blacklist term
_BLACKLIST_REGEXES = [keyword_to_variant_regex(t) for t in _GAMBLING_BLACKLIST]


def is_gambling(name: str) -> bool:
    # 1. Normalize rồi check blacklist + patterns
    n = _normalize_detect(name)
    if any(term in n for term in _GAMBLING_BLACKLIST):
        return True
    if any(pat.search(n) for pat in _GAMBLING_PATTERNS):
        return True
    # 2. Check raw name bằng variant regex (bắt obfuscation chưa có trong _LOOKALIKE)
    return any(rx.search(name) for rx in _BLACKLIST_REGEXES)


def should_block(name: str, match_pattern: str) -> bool:
    return name_matches(name, match_pattern) or is_gambling(name)


# ── Auto-expand Anti.txt với Unicode variants ──────────────────────────────────

# Ký tự lookalike "chuẩn" hay dùng nhất — ưu tiên dạng này khi generate variant
_PREFERRED_LOOKALIKE: dict[str, str] = {
    's': 'Ѕ', 'h': 'ʜ', 'b': 'в', 'e': 'е', 't': 'т',
    'a': 'а', 'c': 'с', 'o': 'о', 'p': 'р', 'i': 'і',
    'n': 'п', 'x': 'х', 'm': 'ᴍ', 'w': 'ᴡ', 'v': 'ᴠ',
    'k': 'κ', 'u': 'υ',
}


def _primary_lookalike_char(ch: str) -> str:
    preferred = _PREFERRED_LOOKALIKE.get(ch.lower())
    if preferred:
        return preferred.upper() if ch.isupper() and preferred.upper() != preferred else preferred
    variants = _CHAR_VARIANTS.get(ch.lower(), set())
    if not variants:
        return ch
    return sorted(variants)[0]


def generate_variants(kw: str) -> list[str]:
    """Tạo các biến thể Unicode + không dấu cho keyword 1-2 từ."""
    words = nfc(kw).split()
    if len(words) > 2:
        return []

    result = []

    # 1. Bỏ dấu tiếng Việt
    plain = _strip_diacritics(kw)
    if plain.lower() != kw.lower():
        result.append(plain)

    # 2. Thay mỗi ký tự bằng Unicode lookalike chính
    lookalike = ''.join(
        _primary_lookalike_char(c) if c.isalpha() else c
        for c in kw
    )
    if lookalike.lower() != kw.lower():
        result.append(lookalike)

    # 3. Bỏ dấu rồi thay lookalike (bắt dạng "mien phi" + Cyrillic)
    lk_plain = ''.join(
        _primary_lookalike_char(c) if c.isalpha() else c
        for c in plain
    )
    seen = {r.lower() for r in result} | {kw.lower()}
    if lk_plain.lower() not in seen:
        result.append(lk_plain)

    return result


def expand_keyword_file(kw_path: Path) -> list[str]:
    """Đọc file, bổ sung variant còn thiếu cho keyword 1-2 từ, ghi lại."""
    lines = [l.strip() for l in kw_path.read_text(encoding='utf-8').splitlines() if l.strip()]
    existing_lower = {l.lower() for l in lines}

    new_lines: list[str] = []
    for line in lines:
        search_kw, _ = split_line(line)
        for variant in generate_variants(search_kw):
            if variant.lower() not in existing_lower:
                new_lines.append(variant)
                existing_lower.add(variant.lower())
                print(f'  [expand] +"{variant}"  ←  "{search_kw}"')

    if new_lines:
        kw_path.write_text('\n'.join(lines + new_lines) + '\n', encoding='utf-8')
        print(f'  [expand] Đã thêm {len(new_lines)} variant vào {kw_path.name}')

    return lines + new_lines


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

    keywords = expand_keyword_file(kw_path)
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
        consecutive_errors = 0
        BATCH_SIZE = 25
        actions_in_batch = 0

        async def check_rate_limited() -> bool:
            content = await page.content()
            return 'đã xảy ra lỗi' in content.lower() or 'checkpoint' in page.url

        async def cooldown(minutes: int):
            log(entries, 'info', f'Nghỉ cooldown {minutes} phút...')
            await asyncio.sleep(minutes * 60)

        async def human_pause():
            # #4: delay sau mỗi navigation, không chỉ sau block
            await asyncio.sleep(random.uniform(1.5, 4.0))

        for ki, line in enumerate(keywords):
            search_kw, match_pattern = split_line(line)
            log(entries, 'info', f'[{ki+1}/{len(keywords)}] Tìm: "{search_kw}" | lọc: "{match_pattern}"')

            # #4: delay trước khi search
            await human_pause()

            try:
                await page.goto(
                    f'https://www.facebook.com/search/pages/?q={quote(search_kw)}',
                    wait_until='domcontentloaded', timeout=20000,
                )
                await human_pause()
                profiles = await extract_profiles(page, match_pattern)
            except Exception as e:
                log(entries, 'error', f'Lỗi search "{search_kw}": {e}')
                continue

            log(entries, 'info', f'Tìm thấy {len(profiles)} profile')

            for url in profiles:
                # #5: quá nhiều lỗi liên tiếp → dừng
                if consecutive_errors >= 5:
                    log(entries, 'error', 'Quá nhiều lỗi liên tiếp — dừng.')
                    break

                result = await block_profile(page, url)

                if result == 'blocked':
                    blocked_total += 1
                    consecutive_errors = 0
                    actions_in_batch += 1
                    log(entries, 'blocked', f'Đã chặn [{search_kw}] {url}')
                else:
                    skipped_total += 1
                    # #1: chỉ check rate-limit khi thất bại
                    if result in ('session_expired', 'no_more_btn') and await check_rate_limited():
                        log(entries, 'info', 'Phát hiện rate-limit — cooldown 25 phút.')
                        await cooldown(random.randint(20, 30))
                    if result in ('session_expired', 'no_more_btn'):
                        consecutive_errors += 1
                    log(entries, 'skip', f'Bỏ qua [{search_kw}] {url} — {result}')

                # #2: batch rest sau mỗi BATCH_SIZE lần block
                if actions_in_batch >= BATCH_SIZE:
                    rest = random.randint(5, 10)
                    log(entries, 'info', f'Batch {BATCH_SIZE} xong — nghỉ {rest} phút.')
                    await cooldown(rest)
                    actions_in_batch = 0

                # #4: delay đầy đủ giữa các profile
                await asyncio.sleep(random.uniform(delay, delay + 10))

            # #3: về home giữa các keyword, scroll nhẹ
            await page.goto('https://www.facebook.com', wait_until='domcontentloaded')
            await human_pause()
            for _ in range(random.randint(1, 3)):
                await page.keyboard.press('End')
                await asyncio.sleep(random.uniform(0.8, 2.0))

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
