#!/usr/bin/env python3
"""
PKT Ad Library Scraper
Tìm Page đang / đã chạy quảng cáo theo từ khóa Anti.txt → xuất CSV cho block_tool.py
Usage:
  export PKT_TOKEN=EAABx...
  python ad_library.py [keyword_file] ADS [output_csv]
Mặc định: Anti.txt → ad_library_results.csv
Sau đó chặn: python block_tool.py ad_library_results.csv direct
"""

import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).parent))
from block_tool import split_line, _to_searchable  # reuse parse logic

API = 'https://graph.facebook.com/v19.0/ads_archive'
FIELDS = 'page_id,page_name,ad_creative_bodies,funding_entity,ad_delivery_start_time,ad_delivery_stop_time'
LIMIT = 100   # max items/page theo API


def _get(url: str) -> dict:
    req = Request(url, headers={'User-Agent': 'PKT-AdLib/1.0'})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def query(keyword: str, token: str, active_only: bool) -> list[dict]:
    params = {
        'search_terms': keyword,
        'ad_reached_countries': '["VN"]',
        'ad_type': 'ALL',
        'fields': FIELDS,
        'limit': LIMIT,
        'access_token': token,
    }
    if active_only:
        params['ad_active_status'] = 'ACTIVE'

    url: str | None = f'{API}?{urlencode(params)}'
    results: list[dict] = []

    while url:
        try:
            data = _get(url)
        except HTTPError as e:
            body = e.read().decode()
            print(f'\n  [api-error] HTTP {e.code}: {body[:200]}')
            break
        except Exception as e:
            print(f'\n  [error] {e}')
            break

        results.extend(data.get('data', []))
        url = data.get('paging', {}).get('next')
        if url:
            time.sleep(0.4)

    return results


def load_existing(path: Path) -> tuple[list[dict], set[str]]:
    if not path.exists():
        return [], set()
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    return rows, {r['page_id'] for r in rows if r.get('page_id')}


FIELDNAMES = ['url', 'page_id', 'page_name', 'keyword', 'funding_entity',
              'started', 'stopped', 'timestamp']


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    token = os.environ.get('PKT_TOKEN', '').strip()
    if not token:
        sys.exit(
            'Thiếu access token.\n'
            '1. Tạo app tại developers.facebook.com\n'
            '2. Lấy User Access Token với permission ads_read\n'
            '3. export PKT_TOKEN=EAABx...\n'
        )

    kw_arg  = sys.argv[1] if len(sys.argv) > 1 else 'Anti.txt'
    _mode   = sys.argv[2].upper() if len(sys.argv) > 2 else 'ADS'
    if _mode != 'ADS':
        sys.exit(f'Mode không hợp lệ: {_mode!r}. Dùng: python ad_library.py <keyword_file> ADS')
    out_arg = sys.argv[3] if len(sys.argv) > 3 else 'ad_library_results.csv'

    # Tìm keyword file
    kw_path = Path(kw_arg)
    if not kw_path.exists():
        kw_path = Path(__file__).parent.parent / kw_arg
    if not kw_path.exists():
        sys.exit(f'Không tìm thấy keyword file: {kw_arg}')

    out_path = Path(__file__).parent / out_arg

    # Đọc keywords — chỉ lấy search_kw duy nhất (bỏ qua duplicate sau normalize)
    raw_lines = [l.strip() for l in kw_path.read_text(encoding='utf-8').splitlines() if l.strip()]
    seen_kw: set[str] = set()
    keywords: list[str] = []
    for line in raw_lines:
        kw, _ = split_line(line)
        norm = _to_searchable(kw)
        if norm and norm not in seen_kw:
            seen_kw.add(norm)
            keywords.append(norm)

    rows, existing_ids = load_existing(out_path)
    print(f'[init] {len(keywords)} keyword duy nhất | {len(rows)} page đã có trong {out_path.name}')

    # Hỏi active_only
    active_only = input('Chỉ lấy quảng cáo đang chạy? [y/N]: ').strip().lower() == 'y'

    new_total = 0
    for ki, kw in enumerate(keywords):
        print(f'[{ki+1:>4}/{len(keywords)}] "{kw}" ...', end=' ', flush=True)
        ads = query(kw, token, active_only)

        added = 0
        for ad in ads:
            pid = str(ad.get('page_id') or '')
            if not pid or pid in existing_ids:
                continue
            existing_ids.add(pid)
            rows.append({
                'url':            f'https://www.facebook.com/{pid}',
                'page_id':        pid,
                'page_name':      ad.get('page_name', ''),
                'keyword':        kw,
                'funding_entity': ad.get('funding_entity', ''),
                'started':        ad.get('ad_delivery_start_time', ''),
                'stopped':        ad.get('ad_delivery_stop_time', ''),
                'timestamp':      datetime.now().isoformat(),
            })
            added += 1

        new_total += added
        print(f'{len(ads)} ads → +{added} page mới')

        write_csv(out_path, rows)  # ghi sau mỗi keyword để không mất data nếu interrupt
        time.sleep(1.2)

    print(f'\n[done] Tổng {len(rows)} page ({new_total} mới) → {out_path}')
    if new_total:
        print(f'[next] python block_tool.py {out_path.name} direct')


if __name__ == '__main__':
    main()
