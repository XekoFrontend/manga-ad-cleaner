#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CBZ Packager

- Tự động phát hiện "chapter unit": bất kỳ thư mục nào chứa ảnh TRỰC TIẾP
  bên trong (không cần biết trước cấu trúc, tùy site tải về đều nhận ra).
- Rename file ảnh trong mỗi chapter thành dạng 001.jpg, 002.jpg... theo
  đúng thứ tự đọc (sort tự nhiên: 2.jpg đứng trước 10.jpg).
- Rename tên thư mục chapter: chuẩn hóa số CUỐI CÙNG tìm thấy trong tên
  thành zero-pad, giữ nguyên phần chữ xung quanh (Chapter_5 -> Chapter_005).
- Đóng thành .cbz (zip ảnh trong từng chapter), xuất ra thư mục cbz_output/
  cạnh root, giữ nguyên cấu trúc con (không đụng ảnh gốc).
- Luôn preview trước, phải xác nhận mới thực thi.

Python 3.x, standard library only.
"""

import os
import re
import sys
import zipfile
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "logs"

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp",
    ".avif", ".jfif", ".tif", ".tiff"
}

# Các thư mục không bao giờ được coi là chapter / không đi vào khi quét.
EXCLUDED_DIR_NAMES = {"cbz_output", "logs", "ad_samples"}

DEFAULT_PAD_WIDTH = 3
CBZ_OUTPUT_DIRNAME = "cbz_output"

_NUM_RE = re.compile(r"(\d+)")  # có ngoặc () để re.split() GIỮ LẠI phần số khớp

# Pattern mặc định để tách SỐ CHAPTER từ tên thư mục: hỗ trợ cả số thập phân
# kiểu chapter lẻ (vd Ch.9.5, Ch.29.5). Không có group -> dùng cả match làm số.
DEFAULT_CHAPTER_NUM_PATTERN = r"\d+(?:\.\d+)?"


# --------------------------------------------------------------------------
# Helpers dùng chung
# --------------------------------------------------------------------------

def is_image(path):
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def natural_sort_key(name):
    """Sort tự nhiên: '2.jpg' đứng trước '10.jpg'."""
    return [
        int(tok) if tok.isdigit() else tok.lower()
        for tok in _NUM_RE.split(name)
    ]


def choose_directory(prompt, default=None):
    if default is not None:
        prompt = f"{prompt}\n(Enter để dùng: {default}) "

    while True:
        raw = input(prompt).strip().strip('"')
        if not raw:
            if default is not None:
                return default
            return None
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            return p
        print(f"Không tìm thấy thư mục: {p}")


def make_log_path():
    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return LOG_DIR / f"cbz_packager_{stamp}.txt"


# --------------------------------------------------------------------------
# Phát hiện chapter unit
# --------------------------------------------------------------------------

def find_chapter_units(root):
    """
    Trả về danh sách thư mục có chứa ảnh TRỰC TIẾP bên trong (không tính
    ảnh nằm trong thư mục con sâu hơn - thư mục con đó nếu có ảnh sẽ tự
    thành 1 unit riêng ở lượt walk của nó).
    """
    units = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)

        dirnames[:] = [d for d in dirnames if d.lower() not in EXCLUDED_DIR_NAMES]

        if current.name.lower() in EXCLUDED_DIR_NAMES:
            continue

        if any(is_image(current / f) for f in filenames):
            units.append(current)

    return sorted(units, key=lambda p: natural_sort_key(str(p)))


def list_images_sorted(folder, exclude_keywords=None):
    exclude_keywords = exclude_keywords or []
    files = [p for p in folder.iterdir() if is_image(p)]
    if exclude_keywords:
        files = [
            p for p in files
            if not any(kw in p.name.lower() for kw in exclude_keywords)
        ]
    return sorted(files, key=lambda p: natural_sort_key(p.name))


def ask_file_exclude_keywords():
    print("\nCó tên file nào cần LOẠI RA khỏi danh sách trang không?")
    print("(vd ảnh cover, ảnh quảng cáo còn sót lại trong mấy chapter)")
    print("Nhập từ khóa khớp một phần tên file, cách nhau dấu phẩy.")
    raw = input("VD: cover, thumbnail, ads (Enter nếu không cần loại gì): ").strip()
    if not raw:
        return []
    return [kw.strip().lower() for kw in raw.split(",") if kw.strip()]


# --------------------------------------------------------------------------
# Rename file ảnh trong 1 chapter
# --------------------------------------------------------------------------

def plan_file_renames(folder, exclude_keywords=None):
    """Trả về list (old_path, new_path). new_path đã zero-pad theo số lượng file."""
    files = list_images_sorted(folder, exclude_keywords)
    if not files:
        return []

    width = max(3, len(str(len(files))))
    plan = []
    for idx, p in enumerate(files, 1):
        new_name = f"{idx:0{width}d}{p.suffix.lower()}"
        new_path = p.parent / new_name
        plan.append((p, new_path))
    return plan


def apply_file_renames(plan):
    """Rename 2 pha qua tên tạm để không đè lẫn nhau khi tên chồng chéo."""
    if not plan:
        return

    tmp_pairs = []
    for i, (old, _new) in enumerate(plan):
        tmp = old.parent / f"__tmp_rename_{i}__{old.name}"
        old.rename(tmp)
        tmp_pairs.append(tmp)

    for tmp, (_old, new) in zip(tmp_pairs, plan):
        tmp.rename(new)


# --------------------------------------------------------------------------
# Rename tên thư mục chapter
# --------------------------------------------------------------------------

def get_number_span(m):
    """
    Lấy (start, end, text) của phần SỐ trong match.
    Nếu pattern có group bắt riêng (vd người dùng nhập 'Ch\\.(\\d+)') thì dùng
    group(1) để chỉ thay đúng phần số, giữ nguyên phần chữ xung quanh.
    Nếu không có group (pattern mặc định) thì dùng cả match.
    """
    if m.re.groups >= 1 and m.group(1) is not None:
        return m.start(1), m.end(1), m.group(1)
    return m.start(0), m.end(0), m.group(0)


def find_last_number_match(name, pattern):
    matches = list(pattern.finditer(name))
    return matches[-1] if matches else None


def compute_folder_pad_width(units, pattern):
    numbers = []
    for u in units:
        m = find_last_number_match(u.name, pattern)
        if m:
            _s, _e, text = get_number_span(m)
            int_part = text.split(".")[0]
            if int_part.isdigit():
                numbers.append(int(int_part))
    if not numbers:
        return DEFAULT_PAD_WIDTH
    return max(DEFAULT_PAD_WIDTH, len(str(max(numbers))))


def propose_folder_name(name, width, pattern):
    """None nếu không tìm thấy số nào trong tên -> không đổi được."""
    m = find_last_number_match(name, pattern)
    if not m:
        return None

    start, end, text = get_number_span(m)

    if "." in text:
        int_part, frac_part = text.split(".", 1)
        if not int_part.isdigit():
            return None
        new_num_str = f"{int(int_part):0{width}d}.{frac_part}"
    else:
        if not text.isdigit():
            return None
        new_num_str = f"{int(text):0{width}d}"

    return name[:start] + new_num_str + name[end:]


def compile_pattern(raw, fallback):
    """Biên dịch regex người dùng nhập; nếu lỗi thì báo và dùng fallback."""
    try:
        return re.compile(raw)
    except re.error as e:
        print(f"  ⚠ Regex không hợp lệ ({e}), dùng mặc định thay thế.")
        return fallback


def ask_folder_number_pattern():
    print("\nCách tách số chapter từ tên thư mục:")
    print("  Enter = mặc định (tự tìm số cuối cùng trong tên, hỗ trợ số")
    print("  thập phân như 9.5). Chỉ cần nhập regex nếu tên thư mục quá dị")
    print(r"  và mặc định đoán sai (vd: 'Ch\.(\d+(?:\.\d+)?)' để chỉ khớp sau 'Ch.').")
    raw = input("Regex tùy chỉnh (Enter để dùng mặc định): ").strip()
    default_pattern = re.compile(DEFAULT_CHAPTER_NUM_PATTERN)
    if not raw:
        return default_pattern
    return compile_pattern(raw, default_pattern)


def parse_folder_overrides(raw, units):
    """
    Parse chuỗi kiểu '3:Chapter_009.5, 7:SKIP, 12:' thành dict
    unit(Path) -> tên mới (str) hoặc None (nghĩa là ép giữ nguyên, không đổi).
    Số dòng (index) tính từ 1, theo đúng thứ tự đã in ra cho user xem.
    """
    overrides = {}
    if not raw.strip():
        return overrides

    for part in [p.strip() for p in raw.split(",") if p.strip()]:
        if ":" not in part:
            print(f"  ⚠ Bỏ qua override sai định dạng (thiếu ':'): {part}")
            continue
        idx_str, value = part.split(":", 1)
        idx_str = idx_str.strip()
        value = value.strip()

        if not idx_str.isdigit():
            print(f"  ⚠ Bỏ qua override sai định dạng (số dòng không hợp lệ): {part}")
            continue
        idx = int(idx_str)
        if idx < 1 or idx > len(units):
            print(f"  ⚠ Bỏ qua override: dòng {idx} không tồn tại")
            continue

        unit = units[idx - 1]
        if value == "" or value.upper() == "SKIP":
            overrides[unit] = unit.name  # ép giữ nguyên tên cũ
        elif "/" in value or "\\" in value:
            print(f"  ⚠ Bỏ qua override dòng {idx}: tên thư mục không được chứa / hoặc \\")
        else:
            overrides[unit] = value

    return overrides


# --------------------------------------------------------------------------
# Đóng .cbz
# --------------------------------------------------------------------------

def compute_cbz_output_path(unit_folder, root, output_root, display_name):
    rel_parent = unit_folder.parent.relative_to(root)
    if str(rel_parent) == ".":
        return output_root / f"{display_name}.cbz"
    return output_root / rel_parent / f"{display_name}.cbz"


def build_cbz(folder, output_path, exclude_keywords=None):
    files = list_images_sorted(folder, exclude_keywords)
    if not files:
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, arcname=p.name)
    return len(files)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    print("=" * 70)
    print(" CBZ Packager")
    print("=" * 70)
    print()
    print("Tự động nhận diện chapter = thư mục có chứa ảnh trực tiếp bên")
    print("trong, không cần biết trước cấu trúc thư mục.")
    print()

    print("Tool nên làm tới đâu?")
    print("1. Chỉ rename file ảnh (001.jpg, 002.jpg... theo đúng thứ tự)")
    print("2. Chỉ rename tên thư mục chapter (chuẩn hóa số, zero-pad)")
    print("3. Rename cả file lẫn thư mục (1 + 2)")
    print("4. Chỉ đóng .cbz (không đổi tên gì, dùng khi đã đặt tên chuẩn sẵn)")
    print("5. Rename (file + folder) rồi đóng .cbz luôn  [khuyên dùng]")

    mode = input("Chọn [1-5]: ").strip()
    if mode not in {"1", "2", "3", "4", "5"}:
        print("Lựa chọn không hợp lệ.")
        return

    do_rename_files = mode in {"1", "3", "5"}
    do_rename_folders = mode in {"2", "3", "5"}
    do_zip = mode in {"4", "5"}

    root = choose_directory(
        "\nĐường dẫn thư mục gốc cần xử lý (sẽ quét tất cả thư mục con):",
        default=SCRIPT_DIR,
    )
    if not root:
        return

    print("\nĐang quét để tìm các chapter (thư mục chứa ảnh)...")
    units = find_chapter_units(root)

    if not units:
        print(f"\n⚠ Không tìm thấy chapter nào (thư mục chứa ảnh) trong: {root}")
        return

    print(f"Tìm thấy {len(units)} chapter.")

    # ---- File cần loại trừ (cover, ads sót lại...) ----
    exclude_keywords = []
    if do_rename_files or do_zip:
        exclude_keywords = ask_file_exclude_keywords()

    # ---- Chuẩn bị plan cho rename folder (nếu cần) ----
    folder_plan = {}       # unit(Path gốc) -> new_name hoặc None
    pad_width = None
    number_pattern = None
    if do_rename_folders:
        number_pattern = ask_folder_number_pattern()
        pad_width = compute_folder_pad_width(units, number_pattern)
        for u in units:
            folder_plan[u] = propose_folder_name(u.name, pad_width, number_pattern)

        # In đầy đủ danh sách có đánh số để user xem trước và sửa tay nếu cần
        print(f"\nĐề xuất đổi tên thư mục (pad width = {pad_width}):")
        for i, u in enumerate(units, 1):
            proposed = folder_plan[u]
            if proposed is None:
                print(f"  {i:>3}. {u.name}  ->  (không tìm thấy số - GIỮ NGUYÊN)")
            elif proposed == u.name:
                print(f"  {i:>3}. {u.name}  ->  (đã đúng chuẩn)")
            else:
                print(f"  {i:>3}. {u.name}  ->  {proposed}")

        print("\nCó dòng nào cần SỬA TAY không? Nhập '<số dòng>:<tên mới>',")
        print("nhiều dòng cách nhau dấu phẩy. Gõ '<số dòng>:' hoặc '<số dòng>:SKIP'")
        print("để ép GIỮ NGUYÊN dòng đó.")
        override_raw = input("VD: 3:Ch.009.5, 15:SKIP (Enter nếu không sửa gì): ").strip()
        overrides = parse_folder_overrides(override_raw, units)
        if overrides:
            folder_plan.update(overrides)
            print(f"\nĐã áp dụng {len(overrides)} chỗ sửa tay:")
            for u, name in overrides.items():
                print(f"    {u.name}  ->  {name}")

    # ---- Preview tổng quan ----
    print("\n" + "-" * 70)
    print("XEM TRƯỚC")
    print("-" * 70)

    if do_rename_files:
        total_files = sum(len(list_images_sorted(u, exclude_keywords)) for u in units)
        print(f"• Sẽ rename tổng cộng {total_files} file ảnh trong {len(units)} chapter.")
        sample = units[0]
        sample_plan = plan_file_renames(sample, exclude_keywords)[:3]
        if sample_plan:
            print(f"  Ví dụ ({sample.name}):")
            for old, new in sample_plan:
                print(f"    {old.name}  ->  {new.name}")

    if do_rename_folders:
        skipped = [u for u in units if folder_plan[u] is None]
        renamed = [u for u in units if folder_plan[u] not in (None, u.name)]
        print(f"\n• Sẽ rename {len(renamed)}/{len(units)} tên thư mục.")
        if skipped:
            print(f"  ⚠ {len(skipped)} thư mục vẫn không tìm thấy số, sẽ giữ nguyên.")

    output_root = None
    if do_zip:
        output_root = choose_directory(
            "\nThư mục xuất file .cbz:",
            default=root / CBZ_OUTPUT_DIRNAME,
        )
        if not output_root:
            return
        print(f"\n• Sẽ đóng {len(units)} file .cbz vào: {output_root}")
        print("  (giữ nguyên cấu trúc thư mục con, không đụng ảnh gốc)")

    print("-" * 70)
    confirm = input("\nGõ OK để thực thi (Enter để hủy): ").strip()
    if confirm.upper() != "OK":
        print("Đã hủy, không có gì thay đổi.")
        return

    # ---- Thực thi ----
    log_lines = [
        "CBZ Packager",
        f"Time: {datetime.now()}",
        f"Root: {root}",
        f"Mode: {mode}",
        f"Exclude keywords: {exclude_keywords or 'none'}",
        f"Folder number pattern: {number_pattern.pattern if number_pattern else 'n/a'}",
        "",
    ]

    files_renamed_total = 0
    folders_renamed_total = 0
    folders_skipped_no_number = 0
    folders_conflict = 0
    cbz_created = 0
    cbz_pages_total = 0
    errors = 0

    print()
    for idx, unit in enumerate(units, 1):
        current_folder = unit  # sẽ cập nhật nếu folder bị rename
        print(f"[{idx}/{len(units)}] {unit.name}")

        # 1) rename file ảnh trước, dùng path folder hiện tại (chưa đổi)
        if do_rename_files:
            try:
                plan = plan_file_renames(current_folder, exclude_keywords)
                apply_file_renames(plan)
                files_renamed_total += len(plan)
                print(f"    ✓ Đã rename {len(plan)} file")
                log_lines.append(f"[FILES] {current_folder} -> {len(plan)} file renamed")
            except Exception as e:
                errors += 1
                print(f"    ✗ Lỗi rename file: {e}")
                log_lines.append(f"[FILE ERROR] {current_folder}: {e}")

        # 2) rename thư mục (nếu có số trong tên, không đụng hàng)
        display_name = current_folder.name
        if do_rename_folders:
            new_name = folder_plan.get(unit)
            if new_name is None:
                folders_skipped_no_number += 1
            elif new_name == current_folder.name:
                pass  # đã đúng chuẩn rồi, không cần đổi
            else:
                new_path = current_folder.parent / new_name
                if new_path.exists():
                    folders_conflict += 1
                    print(f"    ⚠ Bỏ qua đổi tên thư mục: đã tồn tại {new_path.name}")
                    log_lines.append(f"[FOLDER CONFLICT] {current_folder} -> {new_path} (đã tồn tại)")
                else:
                    try:
                        current_folder.rename(new_path)
                        folders_renamed_total += 1
                        print(f"    ✓ Đổi tên thư mục -> {new_name}")
                        log_lines.append(f"[FOLDER] {current_folder} -> {new_path}")
                        current_folder = new_path
                        display_name = new_name
                    except Exception as e:
                        errors += 1
                        print(f"    ✗ Lỗi đổi tên thư mục: {e}")
                        log_lines.append(f"[FOLDER ERROR] {current_folder}: {e}")

        # 3) đóng .cbz (dùng tên/đường dẫn hiện tại, sau khi đã rename nếu có)
        if do_zip:
            out_path = compute_cbz_output_path(current_folder, root, output_root, display_name)
            try:
                page_count = build_cbz(current_folder, out_path, exclude_keywords)
                cbz_created += 1
                cbz_pages_total += page_count
                print(f"    ✓ Đã đóng .cbz ({page_count} trang) -> {out_path}")
                log_lines.append(f"[CBZ] {current_folder} -> {out_path} ({page_count} trang)")
            except Exception as e:
                errors += 1
                print(f"    ✗ Lỗi đóng .cbz: {e}")
                log_lines.append(f"[CBZ ERROR] {current_folder}: {e}")

    log_lines.extend([
        "",
        "=" * 70,
        f"Chapters processed      : {len(units)}",
        f"Files renamed           : {files_renamed_total}",
        f"Folders renamed         : {folders_renamed_total}",
        f"Folders skipped (no #)  : {folders_skipped_no_number}",
        f"Folder rename conflicts : {folders_conflict}",
        f"CBZ created             : {cbz_created}",
        f"CBZ total pages         : {cbz_pages_total}",
        f"Errors                  : {errors}",
        "=" * 70,
    ])

    log_path = make_log_path()
    log_path.write_text("\n".join(log_lines), encoding="utf-8")

    print("\n" + "=" * 70)
    print("HOÀN TẤT")
    print("=" * 70)
    print(f"Chapter xử lý       : {len(units)}")
    if do_rename_files:
        print(f"File đã rename      : {files_renamed_total}")
    if do_rename_folders:
        print(f"Thư mục đã rename   : {folders_renamed_total}")
        print(f"Thư mục bỏ qua      : {folders_skipped_no_number} (không có số) "
              f"+ {folders_conflict} (trùng tên)")
    if do_zip:
        print(f"File .cbz đã tạo    : {cbz_created} ({cbz_pages_total} trang)")
        print(f"Xuất tại            : {output_root}")
    print(f"Lỗi                 : {errors}")
    print(f"Log                 : {log_path}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nĐã hủy bởi người dùng.")
    except Exception as e:
        print(f"\nLỖI: {e}")

    input("\nNhấn Enter để thoát...")
