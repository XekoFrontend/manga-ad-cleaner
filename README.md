# Manga Toolkit: Ad Cleaner / Rename

| Tool            | Việc làm                                                          |
| --------------- | ----------------------------------------------------------------- |
| `ad_cleaner.py` | Xóa ảnh quảng cáo / trang thừa khỏi các chapter                   |
| `rename.py`     | Đổi tên file, thư mục cho chuẩn và đóng từng chapter thành `.cbz` |

## Công nghệ Ad Cleaner

- **Python 3.x**, chỉ dùng thư viện chuẩn, không cần `pip install`.
- Chạy trên terminal hoặc double-click file `.py` (Windows).
- Nhận diện ảnh: `.jpg .jpeg .png .webp .gif .bmp .avif .jfif .tif .tiff`.
- So khớp quảng cáo bằng **SHA-256**, sắp xếp file/thư mục bằng **natural sort** (`2.jpg` đứng trước `10.jpg`).

## Quy trình khuyên dùng

```
1. ad_cleaner  chế độ 1 (hash) → xóa files quảng cáo để lộn xộn
2. ad_cleaner  chế độ 2 (vị trí) → xóa files có vị trí tương đồng ở mọi chapters
3. cbz_packager chế độ 5         → đổi tên + đóng .cbz hoặc rename trước nếu cần.
```

Cả hai tool đều xem trước (dry run) trước, xác nhận mới thực thi, và ghi log vào logs/.

## ad-cleaner.py

```
python ad_cleaner.py
```

### Chế độ 1: Xóa theo hash

Dùng khi quảng cáo là **cùng một ảnh** lặp lại ở nhiều chapter.

1. Tạo thư mục `ad_samples` ở đâu cũng được. Bỏ ảnh mẫu quảng cáo vào.
2. Chạy: `python ad-cleaner.py` hoặc đường dẫn tới file `ad-cleaner.py`
3. Chọn `1` (cập nhật hash) hoặc `3` (thay hash cũ). Chọn `2` nếu đã có hash lưu sẵn.
4. Nhập thư mục gốc cần quét (Enter = thư mục hiện tại).
5. Tool liệt kê file trùng hash. Gõ `DELETE` để xóa, Enter để bỏ qua.

Chỉ file trùng **từng byte** với ảnh mẫu mới bị xóa. Nếu quảng cáo bị nén lại hoặc đổi kích thước thì hash khác, cần thêm bản đó vào `ad_samples`.

Mỗi lần thêm ảnh mẫu mới, chỉ cần bỏ ảnh vào thư mục mẫu và chọn chế độ 1.

- Chế độ 1 sẽ thêm hash mới, không xóa hash cũ.
- Chế độ 3 thay thế toàn bộ danh sách hash bằng ảnh mẫu hiện tại.

### Chế độ 2: Xóa theo vị trí / tên

Dùng khi trang thừa nằm ở **vị trí cố định** (trang đầu, trang cuối) hoặc có **tên đặc trưng**.

Thêm nhiều rule một lượt, kết quả là hợp của các rule:

| Rule      | Nhập              | Ý nghĩa                                       |
| --------- | ----------------- | --------------------------------------------- |
| File đầu  | `1` / `3` / `2-5` | file đầu tiên / 3 file đầu / file thứ 2 đến 5 |
| File cuối | `1` / `2`         | file cuối cùng / 2 file cuối                  |
| Theo tên  | `*credit*`        | glob (mặc định)                               |
| Theo tên  | `re:^00[12]\.`    | gõ `re:` ở đầu để dùng regex                  |

Ngoài ra:

- **Phạm vi:** Enter = tất cả thư mục; `10-20` = thư mục thứ 10 đến 20; hoặc gõ từ khóa tên thư mục.
- **Lưu rule:** rule được lưu vào `ad_rules.json`. Lần sau tool hiển thị rule cũ và hỏi `Y` dùng lại, `A` thêm rule mới, `N` tạo lại từ đầu.
- **An toàn:** thư mục mà rule sẽ xóa trắng bị bỏ qua và cảnh báo. Tool cũng cảnh báo khi xóa quá 30% tổng số file.

---

## rename.py

```
python cbz_packager.py
```

### Menu

| Chọn | Làm gì                                                              |
| ---- | ------------------------------------------------------------------- |
| 1    | Chỉ đổi tên file ảnh thành `001.jpg`, `002.jpg`... theo đúng thứ tự |
| 2    | Chỉ đổi tên thư mục chapter (chuẩn hóa số, thêm số 0 phía trước)    |
| 3    | Đổi tên cả file và thư mục                                          |
| 4    | Chỉ đóng `.cbz`, không đổi tên gì                                   |
| 5    | Đổi tên file + thư mục rồi đóng `.cbz` (khuyên dùng)                |

### Cách tool xử lý

- **Tên file:** sắp theo thứ tự đọc rồi đánh số lại `001`, `002`...
- **Tên thư mục:** tìm **số cuối cùng** trong tên và thêm số 0 phía trước, giữ nguyên phần chữ. `Ch.5` → `Ch.005`, `Ch.9.5` → `Ch.009.5` (hỗ trợ chapter lẻ).
- **Đóng gói:** mỗi chapter thành một `.cbz` trong `cbz_output/`, giữ nguyên cấu trúc thư mục con. **Ảnh gốc không bị đụng tới.**

### Khi auto đoán sai

Tool in toàn bộ danh sách đổi tên có đánh số dòng trước khi làm, và cho can thiệp:

- **Sửa tay:** gõ `3:Ch.009.5, 15:SKIP` để đặt tên riêng cho dòng 3 và giữ nguyên dòng 15.
- **Regex tùy chỉnh:** khi tên có số gây nhiễu (vd `Ch.15 [Team2]` sẽ bị nhầm số 2). Nhập `Ch\.(\d+(?:\.\d+)?)` để chỉ lấy số sau `Ch.`.
- **Loại file:** gõ từ khóa như `cover, ads` để file có tên chứa từ đó không bị đổi tên và không vào `.cbz`.
- Thư mục không có số trong tên được giữ nguyên (trừ khi sửa tay).

---

## Lưu ý

- Cách lấy hash thủ công trên Window
  1.  Windows PowerShell: `Get-FileHash "001.png" -Algorithm SHA256SHA256`
  2.  CMD: `certutil -hashfile "001.png" SHA256`

- Xóa file là **không thể hoàn tác**. Luôn xem kỹ phần xem trước, nên thử trên 1-2 chapter trước.
- Nên chạy `cbz_packager` **sau khi** đã dọn quảng cáo bằng `ad_cleaner`.
- `ad_samples`, `logs`, `cbz_output` luôn bị bỏ qua khi quét, nên có thể để chung với các chapter.
- Mỗi lần chạy có log chi tiết trong `logs/` để tra lại file nào đã xóa hoặc đổi tên.
