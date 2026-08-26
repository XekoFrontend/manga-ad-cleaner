#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Advertisement Hash Cleaner

- Put one or more known advertisement images into a sample folder.
- The tool calculates SHA-256 for every sample image.
- It scans a root folder RECURSIVELY (all subfolders, any name).
- If ANY file has a SHA-256 matching ANY sample hash, that file is deleted.
- Default mode is DRY RUN: nothing is deleted until you confirm.
- Saves hashes and an operation log next to this script.

Python 3.x, standard library only.
"""

import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
HASH_FILE = SCRIPT_DIR / "ad_hashes.json"
LOG_DIR = SCRIPT_DIR / "logs"

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp",
    ".avif", ".jfif", ".tif", ".tiff"
}

PROGRESS_EVERY = 50  # in báo tiến độ mỗi N file khi quét


def sha256_file(path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


def is_image(path):
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def choose_directory(prompt):
    while True:
        raw = input(prompt).strip().strip('"')
        if not raw:
            return None
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            return p
        print(f"Không tìm thấy thư mục: {p}")


def load_hashes():
    if not HASH_FILE.exists():
        return {}

    try:
        data = json.loads(HASH_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                str(k).lower(): str(v)
                for k, v in data.items()
                if isinstance(v, str)
            }
    except Exception as e:
        print(f"⚠ Không đọc được {HASH_FILE.name}: {e}")

    return {}


def save_hashes(hashes):
    HASH_FILE.write_text(
        json.dumps(dict(sorted(hashes.items())), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def build_hashes_from_samples(sample_dir):
    samples = [p for p in sample_dir.rglob("*") if is_image(p)]

    if not samples:
        print("⚠ Không tìm thấy ảnh mẫu.")
        return {}

    hashes = {}
    print("\nĐang tính SHA-256 ảnh mẫu...\n")

    for p in sorted(samples):
        try:
            digest = sha256_file(p)
            hashes[digest] = str(p)
            print(f"✓ {p.name}")
            print(f"  {digest}")
        except Exception as e:
            print(f"✗ {p}: {e}")

    return hashes


def collect_all_images(root):
    """Quét TOÀN BỘ file ảnh trong root, đệ quy qua mọi thư mục con, bất kể tên."""
    return sorted(p for p in root.rglob("*") if is_image(p))


def make_log_path():
    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return LOG_DIR / f"ad_cleaner_{stamp}.txt"


def main():
    print("=" * 70)
    print(" Advertisement Hash Cleaner")
    print("=" * 70)
    print()
    print("Tool sẽ xóa file nếu SHA-256 của file trùng với BẤT KỲ")
    print("SHA-256 nào trong danh sách ảnh mẫu.")
    print("Quét đệ quy TOÀN BỘ thư mục con, không phụ thuộc tên thư mục.")
    print()

    # Load existing hashes first.
    hashes = load_hashes()

    print("Chọn:")
    print("1. Quét thư mục ảnh mẫu và CẬP NHẬT hash")
    print("2. Dùng danh sách hash đã lưu")
    print("3. Quét ảnh mẫu và THAY THẾ danh sách hash cũ")

    mode = input("Chọn [1/2/3]: ").strip() or "1"

    if mode == "1":
        sample_dir = choose_directory(
            "\nĐường dẫn thư mục chứa ảnh quảng cáo mẫu: "
        )
        if not sample_dir:
            return

        new_hashes = build_hashes_from_samples(sample_dir)
        if not new_hashes:
            return

        hashes.update(new_hashes)  # giữ hash cũ, thêm hash mới
        save_hashes(hashes)

    elif mode == "3":
        sample_dir = choose_directory(
            "\nĐường dẫn thư mục chứa ảnh quảng cáo mẫu: "
        )
        if not sample_dir:
            return

        hashes = build_hashes_from_samples(sample_dir)
        if not hashes:
            return

        save_hashes(hashes)

    elif mode == "2":
        if not hashes:
            print(f"\n⚠ Chưa có hash nào trong {HASH_FILE.name}")
            print("Hãy chọn 1 hoặc 3 trước.")
            return

    else:
        print("Lựa chọn không hợp lệ.")
        return

    print("\n" + "-" * 70)
    print(f"Đang dùng {len(hashes)} hash mẫu.")
    print(f"Lưu tại: {HASH_FILE}")
    print("-" * 70)

    root = choose_directory(
        "\nĐường dẫn thư mục gốc cần quét (sẽ quét tất cả thư mục con): "
    )
    if not root:
        return

    print("\nĐang liệt kê toàn bộ file ảnh, có thể mất chút thời gian...")
    image_files = collect_all_images(root)

    if not image_files:
        print(f"\n⚠ Không tìm thấy file ảnh nào trong: {root}")
        return

    print(f"Tìm thấy {len(image_files)} file ảnh cần kiểm tra.")
    print("\nĐang quét (DRY RUN - chưa xóa gì cả)...")

    log_lines = [
        "Advertisement Hash Cleaner",
        f"Time: {datetime.now()}",
        f"Root: {root}",
        f"Hash count: {len(hashes)}",
        "",
    ]

    total_files_scanned = len(image_files)
    total_deleted = 0
    errors = 0
    dirs_with_match = set()
    matches = []  # list of (path, digest, rel_str)

    print()
    for idx, p in enumerate(image_files, 1):
        if idx % PROGRESS_EVERY == 0 or idx == total_files_scanned:
            print(f"  ...đã quét {idx}/{total_files_scanned} file", end="\r")

        try:
            digest = sha256_file(p)
        except Exception as e:
            errors += 1
            print(f"\n  ⚠ ERROR đọc file: {p} | {e}")
            log_lines.append(f"[READ ERROR] {p}: {e}")
            log_lines.append("")
            continue

        if digest not in hashes:
            continue

        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p

        matches.append((p, digest, str(rel)))
        dirs_with_match.add(p.parent)

        print(f"\n  MATCH: {rel}")
        print(f"         SHA256: {digest}")

        log_lines.append(f"[MATCH] {p}")
        log_lines.append(f"SHA256: {digest}")
        log_lines.append("")

    print()  # xuống dòng sau progress bar

    total_matches = len(matches)

    print("\n" + "-" * 70)
    print(f"Quét xong. File trùng hash: {total_matches} (trong {len(dirs_with_match)} thư mục).")
    print("-" * 70)

    delete_mode = False

    if total_matches > 0:
        print("\n⚠️ Bạn có muốn XÓA các file trùng hash ở trên ngay bây giờ?")
        confirm = input("Gõ DELETE để xác nhận (Enter để bỏ qua, không xóa gì): ").strip()
        delete_mode = confirm == "DELETE"

        if delete_mode:
            print()
            for p, digest, rel in matches:
                try:
                    p.unlink()
                    total_deleted += 1
                    print(f"  🗑 Đã xóa: {rel}")
                    log_lines.append(f"[DELETED] {p}")
                except Exception as e:
                    errors += 1
                    print(f"  ✗ Không xóa được: {rel} | {e}")
                    log_lines.append(f"[DELETE ERROR] {p}: {e}")
        else:
            print("Đã bỏ qua, không xóa gì cả.")

    log_lines.extend([
        "=" * 70,
        f"Files scanned      : {total_files_scanned}",
        f"Folders with match : {len(dirs_with_match)}",
        f"Files matched      : {total_matches}",
        f"Files deleted      : {total_deleted}",
        f"Errors             : {errors}",
        f"Mode               : {'DELETE' if delete_mode else 'DRY RUN ONLY'}",
        "=" * 70,
    ])

    log_path = make_log_path()
    log_path.write_text("\n".join(log_lines), encoding="utf-8")

    print("\n" + "=" * 70)
    print("HOÀN TẤT")
    print("=" * 70)
    print(f"File quét         : {total_files_scanned}")
    print(f"Thư mục có AD     : {len(dirs_with_match)}")
    print(f"File trùng        : {total_matches}")
    print(f"Đã xóa            : {total_deleted}")
    print(f"Lỗi               : {errors}")
    print(f"Log               : {log_path}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nĐã hủy bởi người dùng.")
    except Exception as e:
        print(f"\nLỖI: {e}")

    input("\nNhấn Enter để thoát...")
