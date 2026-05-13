# CONTEXT.md — PKT Extensions 304

## Mục đích
Tool tự động tìm và block Facebook page theo từ khóa trong `Anti.txt`.

## Kiến trúc lọc (block_tool.py)

### Pipeline lọc mỗi profile
```
extract_profiles(search_kw, Anti.txt)
  → F1: name match (required trong name, optional trong name HOẶC card)
       HOẶC is_gambling(name) via _GAMBLING_BLACKLIST + _BLACKLIST_REGEXES
       HOẶC _slug_has(url, keyword)
  → F2 (nếu F1 fail): _bio_match(card, bio_signals, threshold=2)
  → BLOCK nếu F1 hoặc F2 pass
  → LOG [SKIP] với lý do F1/F2 nếu cả hai fail
```

### Hàm chính
| Hàm | Mô tả |
|-----|-------|
| `_term_in(term, text)` | word-boundary: "5" khớp "5.0" nhưng không khớp "500" |
| `_compact(s)` | strip diacritics + non-alphanum + lower → "ok-vip" → "okvip" |
| `_to_searchable(s)` | Lookalike + Math-alpha → NFC lower |
| `_bio_match(card, signals, threshold=2)` | ≥2 signals OR bất kỳ signal nào có space |
| `_gambling_signals(name)` | check cả `_normalize_detect(name)` và `_compact(name)` vs blacklist |
| `name_matches(name, pattern)` | parse_keyword → required+optional với _term_in |
| `parse_keyword(line)` | required (double-quoted), optional (single-quoted), fallback (≥3 chars) |
| `split_line(line)` | `&&` → required+optional; `&@` → all required; plain → fallback |

### Anti.txt format
```
# macro = && 'term1' 'term2'     ← định nghĩa macro bio-signal
## SECTION                        ← section header (implicit macro @@ section_name)
Keyword                           ← plain match
Keyword && 'guard1' 'guard2'      ← với optional bio guards
Keyword &@ "word1" "word2"        ← tất cả words bắt buộc
Keyword @@ macro_name             ← dùng macro thay bio signals
```

### Sections trong Anti.txt
- `## CASINO` — gambling: tên nhà cái, game bài, unicode variants
- `## AFFILIATE` — spam link tiếp thị/hoa hồng, coupon giả
- `## VAY` — vay nặng lãi, tín dụng đen
- `## BACSI` — lang băm y tế
- `## VIECLAM` — job scam
- `## OTHER` — tên page cụ thể + unicode variants

### _GAMBLING_BLACKLIST (tên domain nhà cái)
Checked against cả `_normalize_detect(name)` và `_compact(name)`:
`new88, bet88, thabet, kubet, okvip, rikvip, 789bet, jun88, hi88, shbet, 188bet, m88, w88, fun88, fb88, bk88, v9bet, fi88, f8bet, st666, loto188, lode88, vnloto`

## Files chính
- `facebook-block-tool/block_tool.py` — core tool
- `facebook-block-tool/ad_library.py` — scraper FB Ad Library
- `Anti.txt` — danh sách từ khóa block
- `reaction-collector/` — thu thập reaction FB

## Môi trường
- Python 3.x, Playwright (async), undetected-chromedriver
- SSH debug production: `ssh tuyenpkt@180.93.1.235` (SSH key only)
