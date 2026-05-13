# CHANGELOG — PKT Extensions 304

## v1.5 — Filter Overhaul (2026-05-12)
### Added
- `_term_in(term, text)`: word-boundary match — "5" khớp "5.0" nhưng không khớp "500", "51"
- F1 giờ kiểm tra optional terms trong **card description** (không chỉ name) — fix "Công nghệ 5.0" bị skip
- `_gambling_signals` giờ check cả `_compact(name)` — fix "Ok-Vip" → detect "okvip" trong blacklist
- `_bio_match`: multi-word signal = 1 match là đủ để block (thay vì cần threshold=2)
- `[SKIP]` log chi tiết: F1 why (thiếu required/optional) + F2 why (N/M signals) + card preview
- `## AFFILIATE` section mới trong Anti.txt: spam link tiếp thị, coupon giả, deal khuyến mãi
- Keywords mới: Thợ săn siêu cấp, Okvip, Rikvip, Ok bóng đá, Thuật toán, Fan Club VN, Tool Al Vip, Topone, Mechanical Spider Escape, Tự tin xây tương lai, Thu nhập online
- `_prompt_install` thêm `--break-system-packages` cho pip trên Python 3.14+

### Fixed
- Lines 628-635 Anti.txt: xóa macro body inlined cũ, thay bằng `@@ casino` / `&& 'tay' 'nhanh' 'gấp'`
- Casino macro stripped: xóa token quá generic để tránh false positive trong F1 card-check
- `need_card` giờ bật khi có `optional_terms` (không chỉ `bio_signals`) — đảm bảo card được extract

### Removed
- "World Cup VIP" — 38 kết quả quốc tế không liên quan, 0 block. Gambling World Cup đã cover bởi 'soi kèo', 'kèo bóng đá', 'cá độ bóng đá'

### Files
- `facebook-block-tool/block_tool.py` — _term_in, F1 card-check, compact blacklist, skip log, bio_match
- `Anti.txt` — AFFILIATE section, casino cleanup, unicode fix, World Cup VIP removed

---

## v1.4 — Gambling Domains & Bio Match (commit f66d986)
### Added
- `_GAMBLING_BLACKLIST` với domain nhà cái phổ biến
- `_BLACKLIST_REGEXES` cho pattern số-chữ
- Multi-word bio signal: 1 match là đủ

---

## v1.3 — Compact & Pip (commit 044c273 / 611435e)
### Added
- `_compact(s)`: strip diacritics + non-alphanum + lower
- Pip prompt với `--break-system-packages`

---

## v1.2 — Macro System & Bio Filter (commit 91b972b)
### Added
- `## SECTION` implicit macro
- `@@ macro_name` syntax
- Bio-signal filter (F2)
- Compact match

---

## v1.1 — FB Ad Library Scraper (commit af844e1)
### Added
- `ad_library.py` scraper

---

## v1.0 — Base (commit 7a7a2f2 / 48e7c2f)
### Added
- Core block tool
- Math/lookalike normalization
- Reaction collector
