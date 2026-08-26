# Advertisement Hash Cleaner

## Ad Cleaner

### Cách dùng

1. Tạo thư mục `ad_samples` ở đâu cũng được.
2. Bỏ tất cả ảnh quảng cáo mẫu vào đó.
3. Chạy:
   `python ad-cleaner.py`
4. Chọn `1` để thêm hash mới vào danh sách đã lưu.
5. Chọn thư mục để quét, nếu để ngang hàng với `ad-cleaner.py` thì gõ `Enter`.
6. Lần đầu nên chọn `1. DRY RUN` để kiểm tra.
7. Nếu kết quả đúng, chạy lại và chọn `2. DELETE`, sau đó gõ `DELETE`.

Danh sách SHA-256 được lưu trong `ad_hashes.json`.
Log được lưu trong thư mục `logs`.

Mỗi lần thêm ảnh mẫu mới, chỉ cần bỏ ảnh vào thư mục mẫu và chọn chế độ 1.
Chế độ 1 sẽ thêm hash mới, không xóa hash cũ.

Chế độ 3 thay thế toàn bộ danh sách hash bằng ảnh mẫu hiện tại.

### Cách lấy hash thủ công

1. Windows PowerShell:

```
Get-FileHash "001.png" -Algorithm SHA256
```

2. CMD:

```
certutil -hashfile "001.png" SHA256
```

## Auto rename folder/file

1. Rename
2. cbz pack
