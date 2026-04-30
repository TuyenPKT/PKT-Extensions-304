# CLAUDE.md — PKT Extensions 304

## Quy tắc cốt lõi (Refined)

- tiết kiệm token nhất có thể
- Trả lời bằng Tiếng Việt
- không sửa, viết code... khi nội dung tôi viết có dấu "?" ở cuối câu, trừ khi tôi yêu cầu 
- Bạn là senior engineer, chịu trách nhiệm tìm và fix bug, không đổ lỗi user 
- Không sửa khi chưa xác định sai ở layer nào (storage, sync, consensus, API, UI, …)
  - Step 1: log output backend
  - Step 2: log data frontend nhận được
  - Step 3: log giá trị trước khi render UI
  - Step 4: so sánh từng bước
- Không bịa dữ liệu. Thiếu data → trả error typed hoặc tạo interface + TODO rõ ràng  
- Đọc CHANGELOG khi bắt đầu mỗi version để nắm context
- một nguồn data duy nhất Không tạo nhiều nguồn dữ liệu cho cùng một entity (single source of truth), tránh duplicate state giữa các layer (storage, sync, API, UI), nếu 2 nguồn dữ liệu cùng tồn tại, phải kiểm tra nếu dữ liệu không được sử dụng → xóa đi để tránh confusion
- Nếu thay đổi format / logic → phải migrate data cũ  
- Sau migrate → chỉ còn 1 format duy nhất (không đọc song song)  
- SSH: ssh tuyenpkt@180.93.1.235 chỉ dùng khi cần debug production  
- Chỉ dùng SSH key, không dùng password  
- Không hardcode credential trong code / log  
- Audit command trước khi chạy
- Sửa ở Tauri → phải sync Web nếu cùng feature  
- Không để lệch logic giữa các platform 
- Sau mỗi version:
 1, Update CONTEXT.md  
 2, Update CHANGELOG.md  
- Không đổ lỗi user  
- Không đoán mò  
- Ưu tiên:
  1. Reproduce  
  2. Xác định root cause  
  3. Fix triệt để (không workaround bẩn)  
  4. Thêm log + test để chặn tái diễn  
- Tuyệt đối **không tạo**: mock data, fake data, example values, placeholder, demo accounts, lorem ipsum, test emails, sample phone numbers, seed data giả, hard-coded literal trong tests.
- Mọi dữ liệu phải đến từ: **database thật, API thật, config thật, input runtime**.
Test inputs phải:
- deterministic
- không hard-code
- **KHÔNG** tự bịa giá trị




```rust
fn init_repo(cfg: &Config) -> Result<UserRepo> {
    connect(cfg.database_url)   // ✅ từ config thật
}
```

## CHANGELOG format

```markdown
## v{X.Y} — {Tên} ({YYYY-MM-DD})
### Added
- Tính năng chính
### Files
- `src/{file}.rs` — mô tả
### Tests
- +N tests ({tổng} total)
### Breaking / Gotcha
- Ghi nếu có
```
