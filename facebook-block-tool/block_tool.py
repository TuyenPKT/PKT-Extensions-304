#!/usr/bin/env python3
"""
PKT Facebook Block Tool
Đọc file từ khoá → tìm người → chặn tự động
Usage: python block_tool.py keywords.txt [pages|people] [delay_giây]
"""

import asyncio
import csv
import platform
import random
import re as _re
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path
from datetime import datetime
from urllib.parse import quote


def _prompt_install(label: str, cmd: list[str]) -> None:
    print(f'  Lệnh cài: {" ".join(cmd)}')
    ans = input('  Tự động cài ngay? [y/N]: ').strip().lower()
    if ans == 'y':
        subprocess.check_call(cmd)
        print(f'[setup] {label} đã cài xong.')
    else:
        sys.exit(f'Chạy thủ công rồi thử lại: {" ".join(cmd)}')


def check_deps() -> None:
    """Kiểm tra môi trường (Python, pip, playwright, chromium). Gợi ý cài nếu thiếu."""
    if sys.version_info < (3, 9):
        sys.exit(f'Cần Python ≥ 3.9 (hiện tại {sys.version_info.major}.{sys.version_info.minor})')

    pip_ok = subprocess.run([sys.executable, '-m', 'pip', '--version'],
                            capture_output=True).returncode == 0
    if not pip_ok:
        sys.exit('pip không khả dụng. Xem: https://pip.pypa.io/en/stable/installation/')

    try:
        import playwright  # noqa: F401
    except ImportError:
        print('[setup] Thiếu thư viện playwright.')
        _prompt_install('playwright', [sys.executable, '-m', 'pip', 'install', 'playwright'])
        print('[setup] Cần cài trình duyệt — chạy lại lệnh gốc để tiếp tục.')
        sys.exit(0)

    # Kiểm tra Chromium binary đã được playwright install chưa
    system = platform.system()
    if system == 'Darwin':
        base = Path.home() / 'Library' / 'Caches' / 'ms-playwright'
    elif system == 'Windows':
        import os
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ms-playwright'
    else:
        base = Path.home() / '.cache' / 'ms-playwright'

    if not any(base.glob('chromium-*')):
        print('[setup] Chromium chưa được cài cho Playwright (~170 MB).')
        _prompt_install('chromium', [sys.executable, '-m', 'playwright', 'install', 'chromium'])


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
    """Tach search_kw va match_pattern.
    &@  -> AND: tat ca cum double-quote phai co.
    &&  -> AND+OR: search_kw phai co + it nhat 1 cum single-quote phai co.
    """
    if '&&' in line and '&@' not in line:
        left, right = line.split('&&', 1)
        kw = left.strip()
        # Tự ghép search_kw vào match làm required term
        return kw, f'"{kw}" {right.strip()}'
    if '&@' in line:
        left, right = line.split('&@', 1)
        return left.strip(), right.strip()
    return line.strip(), line.strip()


def parse_keyword(match_pattern: str):
    """required: cụm "" — ALL phải có.
    optional: cụm '' — ít nhất 1 phải có.
    fallback: từ ≥3 ký tự — cần ≥2 khớp."""
    p = (match_pattern
         .replace('\u201c', '"').replace('\u201d', '"')
         .replace('\u2018', "'").replace('\u2019', "'"))
    required = [_to_searchable(m) for m in _re.findall(r'"([^"]+)"', p)]
    optional = [_to_searchable(m) for m in _re.findall(r"'([^']+)'", p)]
    if required or optional:
        return required, optional, set()
    words = {w for w in _to_searchable(match_pattern).split() if len(w) >= 3}
    return [], [], words


def name_matches(name: str, match_pattern: str) -> bool:
    required, optional, fallback = parse_keyword(match_pattern)
    name_l = _to_searchable(name)
    if required or optional:
        if required and not all(t in name_l for t in required):
            return False
        if optional and not any(t in name_l for t in optional):
            return False
        return True
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


def _build_math_alpha_map() -> dict:
    """U+1D400–U+1D7FF: Mathematical Bold/Italic/Fraktur/Script/... → ASCII."""
    _dw = {'ZERO':'0','ONE':'1','TWO':'2','THREE':'3','FOUR':'4',
           'FIVE':'5','SIX':'6','SEVEN':'7','EIGHT':'8','NINE':'9'}
    m = {}
    for cp in range(0x1D400, 0x1D800):
        name = unicodedata.name(chr(cp), '')
        if not name.startswith('MATHEMATICAL'):
            continue
        parts = name.split()
        last = parts[-1]
        if len(last) == 1 and last.isalpha():
            m[chr(cp)] = last.lower() if 'SMALL' in name else last.upper()
        elif last in _dw:
            m[chr(cp)] = _dw[last]
    return m

_MATH_ALPHA = str.maketrans(_build_math_alpha_map())


def _to_searchable(s: str) -> str:
    """Lookalike + Math-alpha → NFC lower. Giữ nguyên dấu tiếng Việt."""
    return nfc(s.translate(_LOOKALIKE).translate(_MATH_ALPHA)).lower()


def _strip_diacritics(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def _normalize_detect(s: str) -> str:
    s = s.translate(_LOOKALIKE).translate(_MATH_ALPHA)
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


def _gambling_signals(name: str) -> int:
    """Đếm số signal gambling độc lập: blacklist-hit + pattern-hit (max 2)."""
    n = _normalize_detect(name)
    blacklist_hit = (
        any(term in n for term in _GAMBLING_BLACKLIST) or
        any(rx.search(name) for rx in _BLACKLIST_REGEXES)
    )
    pattern_hit = any(pat.search(n) for pat in _GAMBLING_PATTERNS)
    return int(blacklist_hit) + int(pattern_hit)


def is_gambling(name: str) -> bool:
    return _gambling_signals(name) >= 1


def should_block(name: str, match_pattern: str, mode: str = 'pages') -> bool:
    if mode == 'people':
        required, optional, fallback = parse_keyword(match_pattern)
        name_l = _to_searchable(name)
        if required or optional:
            req_ok = all(t in name_l for t in required) if required else True
            opt_ok = any(t in name_l for t in optional) if optional else True
            keyword_ok = req_ok and opt_ok and (len(required) + len(optional) >= 2)
        else:
            keyword_ok = sum(1 for w in fallback if w in name_l) >= 2
        return keyword_ok or _gambling_signals(name) >= 2
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


async def extract_profiles(page, match_pattern: str, mode: str = 'pages') -> list[str]:
    try:
        await page.wait_for_selector('[role="feed"]', timeout=15000)
    except Exception:
        await page.wait_for_selector('[role="main"]', timeout=10000)
    await asyncio.sleep(random.uniform(2.5, 4.5))

    for _ in range(random.randint(4, 7)):
        dy = random.randint(280, 680)
        await page.evaluate(f'window.scrollBy({{top:{dy},behavior:"smooth"}})')
        await asyncio.sleep(random.uniform(0.9, 2.8))
        if random.random() < 0.25:
            await page.evaluate(f'window.scrollBy({{top:-{random.randint(60,200)},behavior:"smooth"}})')
            await asyncio.sleep(random.uniform(0.5, 1.2))

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

    return [p['url'] for p in pairs if should_block(p['name'], match_pattern, mode)]


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

        # Chờ dialog confirm xuất hiện
        try:
            await page.wait_for_selector('[role="dialog"],[role="alertdialog"]', timeout=5000)
        except Exception:
            pass

        # Tìm trong dialog trước, fallback toàn trang
        _pat = _re.compile(r'xác nhận|confirm|chặn|block', _re.IGNORECASE)
        confirm = page.locator('[role="dialog"] [role="button"],[role="alertdialog"] [role="button"]').filter(has_text=_pat).last
        if not await confirm.count():
            confirm = page.locator('[role="button"]').filter(has_text=_pat).last

        if not await confirm.count():
            dlg_btns = []
            try:
                dlg_btns = await page.locator('[role="dialog"] [role="button"],[role="alertdialog"] [role="button"]').all_text_contents()
            except Exception:
                pass
            await page.keyboard.press('Escape')
            return f'no_confirm_btn | btns: {dlg_btns[:6]}'

        await confirm.click()
        await asyncio.sleep(10)
        return 'blocked'

    except Exception as e:
        return str(e)[:80]


_SEARCH_URL = {
    'pages':  'https://www.facebook.com/search/pages/?q={}',
    'people': 'https://www.facebook.com/search/people/?q={}',
}


def _read_csv(path: Path) -> tuple[list[dict], list[str]]:
    """Đọc CSV, trả về (rows, fieldnames). Bỏ qua dòng thiếu url."""
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r.get('url', '').strip()]
        return rows, list(reader.fieldnames or ['url', 'type', 'source', 'timestamp'])


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


async def main(keyword_file: str, mode: str, delay: int):
    kw_path = Path(keyword_file)
    if not kw_path.exists():
        kw_path = Path(__file__).parent.parent / keyword_file
    if not kw_path.exists():
        print(f'Không tìm thấy file: {keyword_file}')
        return

    if mode != 'direct':
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
            viewport={'width': random.choice([1280, 1366, 1440, 1536]), 'height': random.choice([768, 800, 864, 900])},
            user_agent=(
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            locale='vi-VN',
            timezone_id='Asia/Ho_Chi_Minh',
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
            ],
            ignore_default_args=['--enable-automation'],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        await page.goto('https://www.facebook.com', wait_until='domcontentloaded')
        await asyncio.sleep(2)
        if 'login' in page.url or await page.locator('[name="email"]').count():
            log(entries, 'info', 'Chưa đăng nhập — đăng nhập xong nhấn Enter.')
            input()

        # ── Pause/resume bằng phím 'p' ───────────────────────────────────────
        _resume = asyncio.Event()
        _resume.set()  # bắt đầu ở trạng thái running

        def _stdin_watcher():
            while True:
                try:
                    line = sys.stdin.readline()
                except Exception:
                    break
                if not line:
                    break
                if line.strip().lower() == 'p':
                    if _resume.is_set():
                        _resume.clear()
                        print('\n[pause] Đã tạm dừng — nhấn p + Enter để tiếp tục.')
                    else:
                        _resume.set()
                        print('[resume] Tiếp tục...')

        threading.Thread(target=_stdin_watcher, daemon=True).start()
        print('[info] Nhấn p + Enter bất cứ lúc nào để pause/resume.')

        async def check_pause():
            if not _resume.is_set():
                t = datetime.now().strftime('%H:%M:%S')
                print(f'{t} [pause ] Đang tạm dừng...')
                await _resume.wait()

        if mode == 'direct':
            log(entries, 'info', f'Direct mode: {kw_path.name}')
        else:
            log(entries, 'info', f'Bắt đầu: {len(keywords)} từ khoá | mode={mode} | delay={delay}s')
        blocked_total = skipped_total = 0
        consecutive_errors = 0
        actions_in_batch = 0
        batch_count = 0
        profile_counter = 0  # đếm toàn bộ để xen scroll

        # Recovery state
        recovery_mode  = False
        recovery_start = 0.0
        recovery_hits  = 0
        _cooldown_min  = 15   # phút hiện tại (15→30→60→120→240)
        RECOVERY_HOURS = 24

        def _batch_size() -> int:
            return random.randint(10, 15) if recovery_mode else random.randint(15, 20)

        def _action_delay() -> float:
            return random.uniform(5, 10) if recovery_mode else random.uniform(4, 8)

        batch_size = _batch_size()

        # LOW=0 MEDIUM=1 HIGH=2 CRITICAL=3
        async def risk_level() -> int:
            url = page.url
            # CRITICAL: UI captcha thật
            if await page.locator('[name="captcha"], iframe[src*="recaptcha"], [data-testid="captcha"]').count():
                return 3
            # HIGH: redirect vào checkpoint/challenge/login device
            if any(k in url for k in ('/checkpoint/', '/challenge/', '/login/device', '/login/identify')):
                return 2
            # MEDIUM: redirect về login bất thường (không phải khởi động)
            if 'login' in url and 'facebook.com' in url:
                return 1
            return 0

        async def cooldown(minutes: int):
            end = time.time() + minutes * 60
            log(entries, 'info', f'Nghỉ {minutes} phút (đến {datetime.fromtimestamp(end).strftime("%H:%M:%S")})...')
            try:
                while True:
                    left = end - time.time()
                    if left <= 0:
                        break
                    await asyncio.sleep(min(60, left))
                    left2 = end - time.time()
                    if left2 > 0:
                        log(entries, 'info', f'  còn {int(left2 // 60)}p{int(left2 % 60):02d}s...')
            except asyncio.CancelledError:
                raise

        async def human_pause():
            await asyncio.sleep(random.uniform(1.5, 3.5))

        async def human_scroll():
            try:
                await page.goto('https://www.facebook.com', wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(random.uniform(1.8, 3.5))
                for _ in range(random.randint(4, 9)):
                    dy = random.randint(220, 720)
                    await page.evaluate(f'window.scrollBy({{top:{dy},behavior:"smooth"}})')
                    await asyncio.sleep(random.uniform(0.8, 3.2))
                    if random.random() < 0.3:
                        await page.evaluate(f'window.scrollBy({{top:-{random.randint(80,250)},behavior:"smooth"}})')
                        await asyncio.sleep(random.uniform(0.6, 1.5))
                await asyncio.sleep(random.uniform(1.5, 4.0))
            except Exception:
                pass

        async def handle_risk(level: int) -> bool:
            """level: 0=LOW 1=MEDIUM 2=HIGH 3=CRITICAL. Trả True = tiếp tục."""
            nonlocal recovery_mode, recovery_start, recovery_hits, batch_size, _cooldown_min

            if level == 0:
                return True

            if level == 1:  # MEDIUM: chậm lại, không cooldown dài
                log(entries, 'warn', 'MEDIUM risk — redirect login bất thường, nghỉ 2–4 phút.')
                await cooldown(random.randint(2, 4))
                recovery_mode = True
                batch_size = _batch_size()
                return True

            # HIGH hoặc CRITICAL — cooldown có cấp bậc
            label = 'CRITICAL (captcha UI)' if level == 3 else 'HIGH (checkpoint/challenge)'

            # Reset exponent nếu session trước đủ dài
            if recovery_start > 0:
                ran_minutes = (time.time() - recovery_start) / 60
                if ran_minutes >= _cooldown_min:
                    _cooldown_min = 15
                    recovery_hits = 0

            recovery_hits += 1
            rest = _cooldown_min
            _cooldown_min = min(_cooldown_min * 2, 240)

            log(entries, 'warn',
                f'{label} lần {recovery_hits} — cooldown {rest} phút '
                f'(tiếp theo nếu bị nhanh: {_cooldown_min}p).')

            await cooldown(rest)
            recovery_mode = True
            recovery_start = time.time()
            batch_size = _batch_size()
            return True

        # ── Direct mode ───────────────────────────────────────────────────────
        if mode == 'direct':
            csv_rows, csv_fields = _read_csv(kw_path)

            # Dedup theo url, giữ bản cuối cùng; đảo ngược để process từ dưới lên
            seen_urls: dict[str, dict] = {}
            for row in csv_rows:
                seen_urls[row['url'].strip()] = row
            queue = list(reversed(list(seen_urls.values())))
            log(entries, 'info', f'{len(queue)} URL (từ dưới lên, đã dedup)')

            stop_all = False
            for row in queue:
                if stop_all:
                    break

                await check_pause()
                rl = await risk_level()
                if rl >= 1:
                    await handle_risk(rl)
                    if rl >= 2:
                        break  # HIGH/CRITICAL: thoát vòng profile, resume sau cooldown

                if consecutive_errors >= 5:
                    log(entries, 'error', 'Quá nhiều lỗi liên tiếp — dừng.')
                    break

                url = row['url'].strip()
                result = await block_profile(page, url)
                profile_counter += 1

                if result == 'blocked':
                    blocked_total += 1
                    consecutive_errors = 0
                    actions_in_batch += 1
                    log(entries, 'blocked', f'[direct] {url}')
                    csv_rows = [r for r in csv_rows if r['url'].strip() != url]
                    _write_csv(kw_path, csv_rows, csv_fields)
                else:
                    skipped_total += 1
                    if result == 'session_expired':
                        rl2 = await risk_level()
                        if rl2 >= 2:
                            await handle_risk(rl2)
                            break
                    if result in ('session_expired', 'no_more_btn'):
                        consecutive_errors += 1
                    log(entries, 'skip', f'[direct] {url} — {result}')

                if actions_in_batch >= batch_size:
                    batch_count += 1
                    actions_in_batch = 0
                    batch_size = _batch_size()
                    if not recovery_mode and batch_count % random.randint(2, 3) == 0:
                        rest = random.randint(15, 20)
                        log(entries, 'info', f'Batch {batch_count} — nghỉ dài {rest} phút.')
                    else:
                        rest = random.randint(5, 10)
                        log(entries, 'info', f'Batch {batch_count} xong — nghỉ {rest} phút.')
                    await cooldown(rest)

                scroll_every = 5 if recovery_mode else 10
                if profile_counter % scroll_every == 0:
                    await human_scroll()

                await asyncio.sleep(_action_delay())

        # ── Keyword search mode ───────────────────────────────────────────────
        for ki, line in enumerate(keywords if mode != 'direct' else []):
            # Kiểm tra hết window recovery (24h) → về nhịp bình thường
            if recovery_mode and (time.time() - recovery_start) >= RECOVERY_HOURS * 3600:
                recovery_mode = False
                batch_size = _batch_size()
                log(entries, 'info', 'Hết 24h recovery — về nhịp bình thường.')

            search_kw, match_pattern = split_line(line)
            log(entries, 'info', f'[{ki+1}/{len(keywords)}] Tìm: "{search_kw}" | lọc: "{match_pattern}"')

            await human_pause()

            try:
                await page.goto(
                    _SEARCH_URL[mode].format(quote(_to_searchable(search_kw))),
                    wait_until='domcontentloaded', timeout=20000,
                )
                await human_pause()
                profiles = await extract_profiles(page, match_pattern, mode)
            except Exception as e:
                log(entries, 'error', f'Lỗi search "{search_kw}": {e}')
                continue

            log(entries, 'info', f'Tìm thấy {len(profiles)} profile')

            stop_all = False
            for url in profiles:
                await check_pause()
                rl = await risk_level()
                if rl >= 1:
                    await handle_risk(rl)
                    if rl >= 2:
                        break

                if consecutive_errors >= 5:
                    log(entries, 'error', 'Quá nhiều lỗi liên tiếp — dừng.')
                    stop_all = True
                    break

                result = await block_profile(page, url)
                profile_counter += 1

                if result == 'blocked':
                    blocked_total += 1
                    consecutive_errors = 0
                    actions_in_batch += 1
                    log(entries, 'blocked', f'Đã chặn [{search_kw}] {url}')
                else:
                    skipped_total += 1
                    if result == 'session_expired':
                        rl2 = await risk_level()
                        if rl2 >= 2:
                            await handle_risk(rl2)
                            break
                    if result in ('session_expired', 'no_more_btn'):
                        consecutive_errors += 1
                    log(entries, 'skip', f'Bỏ qua [{search_kw}] {url} — {result}')

                if actions_in_batch >= batch_size:
                    batch_count += 1
                    actions_in_batch = 0
                    batch_size = _batch_size()
                    if not recovery_mode and batch_count % random.randint(2, 3) == 0:
                        rest = random.randint(15, 20)
                        log(entries, 'info', f'Batch {batch_count} — nghỉ dài {rest} phút.')
                    else:
                        rest = random.randint(5, 10)
                        log(entries, 'info', f'Batch {batch_count} xong — nghỉ {rest} phút.')
                    await cooldown(rest)

                # Xen scroll sau mỗi ~5 profile khi recovery, ~10 khi bình thường
                scroll_every = 5 if recovery_mode else 10
                if profile_counter % scroll_every == 0:
                    await human_scroll()

                await asyncio.sleep(_action_delay())

            if stop_all:
                break

            # Về home giữa các keyword, scroll nhẹ
            await page.goto('https://www.facebook.com', wait_until='domcontentloaded')
            await human_pause()
            for _ in range(random.randint(2, 5)):
                dy = random.randint(200, 600)
                await page.evaluate(f'window.scrollBy({{top:{dy},behavior:"smooth"}})')
                await asyncio.sleep(random.uniform(0.7, 2.2))
                if random.random() < 0.2:
                    await page.evaluate(f'window.scrollBy({{top:-{random.randint(50,180)},behavior:"smooth"}})')
                    await asyncio.sleep(random.uniform(0.4, 1.0))

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
    check_deps()
    from playwright.async_api import async_playwright
    if len(sys.argv) < 2:
        print('Usage: python block_tool.py keywords.txt [pages|people] [delay_giây]')
        sys.exit(1)

    _mode = 'pages'
    _delay = 3
    for _a in sys.argv[2:]:
        if _a in ('pages', 'people', 'direct'):
            _mode = _a
        elif _a.isdigit():
            _delay = int(_a)

    try:
        asyncio.run(main(sys.argv[1], _mode, _delay))
    except KeyboardInterrupt:
        print('\n[dừng] Ctrl+C — đã thoát.')
