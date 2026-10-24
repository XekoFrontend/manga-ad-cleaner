# 1. Cách dùng `re:` (regex)

Mặc định, pattern tên là **glob**, kiểu đơn giản: `*` là bất kỳ chuỗi nào, `?` là đúng 1 ký tự. Ví dụ `*credit*` hoặc `00?.jpg`.

Gõ `re:` ở đầu thì phần phía sau được hiểu là **regex**, mạnh hơn nhưng khó viết hơn. Dùng khi glob không diễn đạt được.

Một số quy tắc của tool:

- Regex chỉ so với **tên file** (gồm cả đuôi, vd `001.jpg`), không so với đường dẫn.
- Tool dùng kiểu "tìm thấy ở đâu cũng tính", nên muốn khớp chính xác đầu/cuối tên thì phải thêm `^` và `$`.
- Không phân biệt hoa thường.
- Không để dấu cách sau `re:`.

Các ký tự hay dùng:

| Ký tự   | Nghĩa                                                |
| ------- | ---------------------------------------------------- |
| `^`     | bắt đầu tên file                                     |
| `$`     | kết thúc tên file                                    |
| `\.`    | dấu chấm thật (dấu `.` trần nghĩa là "ký tự bất kỳ") |
| `\d`    | một chữ số                                           |
| `[1-3]` | một ký tự trong khoảng 1 đến 3                       |
| `a\|b`  | `a` hoặc `b`                                         |
| `+`     | lặp 1 lần trở lên                                    |

Ví dụ:

| Muốn xóa                                | Gõ                         |
| --------------------------------------- | -------------------------- |
| file tên bắt đầu bằng `001`             | `re:^001\.`                |
| file `001`, `002`, `003`                | `re:^00[1-3]\.`            |
| file chứa credit hoặc intro hoặc thanks | `re:credit\|intro\|thanks` |
| mọi file đuôi `.png`                    | `re:\.png$`                |
| file tên chỉ gồm 1-2 chữ số             | `re:^\d{1,2}\.`            |

Chỗ hay sai: `re:*credit*` là **sai**, vì trong regex `*` không đứng một mình được. Viết `re:credit` là đủ, vì tool đã "tìm thấy ở đâu cũng tính". Nếu regex lỗi, tool báo ngay và không thêm rule đó. Dù sao có bước xem trước, mày nhìn danh sách file sẽ xóa là biết pattern đúng chưa.

[Back](README.md)
