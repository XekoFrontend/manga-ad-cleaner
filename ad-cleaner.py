#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Advertisement Cleaner

Chế độ 1 - Xóa quảng cáo theo HASH:
- Đặt ảnh quảng cáo mẫu vào thư mục ad_samples, tool tính SHA-256.
- Quét đệ quy; file nào trùng hash mẫu sẽ bị xóa (sau khi xác nhận).

Chế độ 2 - Xóa file theo VỊ TRÍ / TÊN:
- Áp dụng cho từng thư mục chứa ảnh (chapter), thứ tự theo sort tự nhiên.
- Nhiều rule một lượt, kết quả là HỢP của các rule:
    + N file đầu, hoặc range A-B
    + N file cuối
    + tên file theo glob (*credit*) hoặc regex (gõ "re:" ở đầu)
- Rule được lưu vào ad_rules.json; lần sau tool hỏi có dùng lại không.
- Không bao giờ xóa trắng một thư mục (chapter bị bỏ qua + cảnh báo).

Luôn xem trước, gõ DELETE mới xóa thật. Log lưu trong thư mục logs.
Python 3.x, standard library only.
"""

import fnmatch
import hashlib
import json
import os
import re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
HASH_FILE = SCRIPT_DIR / "ad_hashes.json"
RULES_FILE = SCRIPT_DIR / "ad_rules.json"
LOG_DIR = SCRIPT_DIR / "logs"

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp",
    ".avif", ".jfif", ".tif", ".tiff"
}

# Các thư mục luôn bị loại khỏi vòng quét/xóa (không phân biệt hoa thường).
EXCLUDED_DIR_NAMES = {"ad_samples", "logs", "cbz_output"}

DEFAULT_SAMPLE_DIR_NAME = "ad_samples"
PROGRESS_EVERY = 50
BIG_DELETE_RATIO = 0.30  # cảnh báo nếu xóa quá 30% tổng số file

_NUM_RE = re.compile(r"(\d+)")


# --------------------------------------------------------------------------
# Helpers dùng chung
# --------------------------------------------------------------------------

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


def natural_sort_key(name):
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


def make_log_path(prefix):
    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return LOG_DIR / f"{prefix}_{stamp}.txt"


def collect_all_images(root, exclude_dirs=None):
    """Mọi file ảnh dưới root (đệ quy), bỏ qua thư mục bị loại."""
    exclude_resolved = {d.resolve() for d in (exclude_dirs or [])}
    images = []

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)

        kept = []
        for d in dirnames:
            if d.lower() in EXCLUDED_DIR_NAMES:
                continue
            if (current / d).resolve() in exclude_resolved:
                continue
            kept.append(d)
        dirnames[:] = kept

        for name in filenames:
            fp = current / name
            if is_image(fp):
                images.append(fp)

    return sorted(images)


def find_image_folders(root):
    """
    Trả về list (folder, [ảnh đã sort tự nhiên]) cho mọi thư mục chứa ảnh
    TRỰC TIẾP bên trong, đã sort tự nhiên theo đường dẫn.
    """
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d.lower() not in EXCLUDED_DIR_NAMES]
        if current.name.lower() in EXCLUDED_DIR_NAMES:
            continue

        imgs = [current / f for f in filenames if is_image(current / f)]
        if imgs:
            imgs.sort(key=lambda p: natural_sort_key(p.name))
            result.append((current, imgs))

    result.sort(key=lambda t: natural_sort_key(str(t[0])))
    return result


# --------------------------------------------------------------------------
# CHẾ ĐỘ 1: xóa theo hash
# --------------------------------------------------------------------------

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


def run_hash_mode():
    print("\n" + "-" * 70)
    print(" CHẾ ĐỘ 1: Xóa quảng cáo theo HASH")
    print("-" * 70)

    hashes = load_hashes()

    print("👇 Chọn:")
    print("1. Quét thư mục ảnh mẫu (ad_samples) và CẬP NHẬT hash")
    print("2. Dùng danh sách hash đã lưu")
    print("3. Quét ảnh mẫu và THAY THẾ danh sách hash cũ")

    mode = input("Chọn [1/2/3]: ").strip() or "1"

    default_sample_dir = SCRIPT_DIR / DEFAULT_SAMPLE_DIR_NAME
    if not default_sample_dir.is_dir():
        default_sample_dir = None

    sample_dir = None

    if mode == "1":
        sample_dir = choose_directory(
            "\nĐường dẫn thư mục chứa ảnh quảng cáo mẫu:",
            default=default_sample_dir,
        )
        if not sample_dir:
            return

        new_hashes = build_hashes_from_samples(sample_dir)
        if not new_hashes:
            return

        hashes.update(new_hashes)
        save_hashes(hashes)

    elif mode == "3":
        sample_dir = choose_directory(
            "\nĐường dẫn thư mục chứa ảnh quảng cáo mẫu:",
            default=default_sample_dir,
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
        "\nĐường dẫn thư mục gốc cần quét (sẽ quét tất cả thư mục con):",
        default=SCRIPT_DIR,
    )
    if not root:
        return

    exclude_dirs = [sample_dir] if sample_dir else []
    names = ", ".join(sorted(EXCLUDED_DIR_NAMES))
    print(f"\n(Sẽ bỏ qua các thư mục tên: {names}"
          + (f" và {sample_dir}" if sample_dir else "") + ")")

    print("Đang liệt kê toàn bộ file ảnh, có thể mất chút thời gian...")
    image_files = collect_all_images(root, exclude_dirs=exclude_dirs)

    if not image_files:
        print(f"\n⚠ Không tìm thấy file ảnh nào trong: {root}")
        return

    print(f"Tìm thấy {len(image_files)} file ảnh cần kiểm tra.")
    print("\nĐang quét (DRY RUN - chưa xóa gì cả)...")

    log_lines = [
        "Advertisement Cleaner - HASH MODE",
        f"Time: {datetime.now()}",
        f"Root: {root}",
        f"Hash count: {len(hashes)}",
        f"Excluded dir names: {', '.join(sorted(EXCLUDED_DIR_NAMES))}"
        + (f" (+ {sample_dir})" if sample_dir else ""),
        "",
    ]

    total_files_scanned = len(image_files)
    total_deleted = 0
    errors = 0
    dirs_with_match = set()
    matches = []

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

    print()

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
                    print(f"  🗑️ Đã xóa: {rel}")
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

    log_path = make_log_path("ad_cleaner_hash")
    log_path.write_text("\n".join(log_lines), encoding="utf-8")

    print("\n" + "=" * 70)
    print("✅ HOÀN TẤT")
    print("=" * 70)
    print(f"File quét         : {total_files_scanned}")
    print(f"Thư mục có AD     : {len(dirs_with_match)}")
    print(f"File trùng        : {total_matches}")
    print(f"Đã xóa            : {total_deleted}")
    print(f"Lỗi               : {errors}")
    print(f"Log               : {log_path}")
    print("=" * 70)


# --------------------------------------------------------------------------
# CHẾ ĐỘ 2: xóa theo vị trí / tên
# --------------------------------------------------------------------------
# Rule dạng dict:
#   {"type": "first", "start": 1, "end": 3}     file thứ start..end (1-based)
#   {"type": "last",  "count": 2}               count file cuối
#   {"type": "name",  "pattern": "*credit*"}    glob, hoặc "re:..." là regex

def describe_rule(r):
    t = r.get("type")
    if t == "first":
        if r["start"] == 1:
            return f"Xóa {r['end']} file ĐẦU (file 1 → {r['end']})"
        return f"Xóa file ĐẦU từ vị trí {r['start']} → {r['end']}"
    if t == "last":
        return f"Xóa {r['count']} file CUỐI"
    if t == "name":
        pat = r["pattern"]
        if pat.lower().startswith("re:"):
            return f"Xóa file có tên khớp REGEX: {pat[3:]}"
        return f"Xóa file có tên khớp GLOB: {pat}"
    return f"(rule không hiểu: {r})"


def valid_rule(r):
    try:
        t = r["type"]
        if t == "first":
            return 1 <= int(r["start"]) <= int(r["end"])
        if t == "last":
            return int(r["count"]) >= 1
        if t == "name":
            return isinstance(r["pattern"], str) and r["pattern"] != ""
    except Exception:
        pass
    return False


def load_rules():
    if not RULES_FILE.exists():
        return []
    try:
        data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict) and valid_rule(r)]
    except Exception as e:
        print(f"⚠ Không đọc được {RULES_FILE.name}: {e}")
    return []


def save_rules(rules):
    RULES_FILE.write_text(
        json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def print_rules(rules):
    for i, r in enumerate(rules, 1):
        print(f"   {i}. {describe_rule(r)}")


def parse_first_input(raw):
    """'3' = 3 file đầu (1..3); '2-5' = file thứ 2 đến 5."""
    raw = raw.strip()
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", raw)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
    elif raw.isdigit():
        a, b = 1, int(raw)
    else:
        return None
    if a < 1 or b < a:
        return None
    return {"type": "first", "start": a, "end": b}


def ask_new_rules():
    rules = []
    while True:
        print("\nThêm rule (kết quả là HỢP của tất cả rule):")
        print("  a. Xóa file ĐẦU     (vd: 1 = file đầu tiên, 3 = 3 file đầu, 2-5 = file thứ 2 đến 5)")
        print("  b. Xóa file CUỐI    (vd: 1 = file cuối cùng, 2 = 2 file cuối)")
        print("  c. Xóa theo TÊN     (glob như *credit*, 00?.jpg; gõ 're:' ở đầu để dùng regex)")
        print("  d. Xong, qua bước xem trước")
        if rules:
            print(f"  (đang có {len(rules)} rule)")
        choice = input("Chọn [a/b/c/d]: ").strip().lower()

        if choice == "a":
            r = parse_first_input(input("Nhập (vd 1, 3, 2-5): "))
            if r:
                rules.append(r)
                print(f"  ✓ {describe_rule(r)}")
            else:
                print("  ⚠ Giá trị không hợp lệ.")

        elif choice == "b":
            raw = input("Số file cuối cần xóa (vd 1, 2, 3): ").strip()
            if raw.isdigit() and int(raw) >= 1:
                r = {"type": "last", "count": int(raw)}
                rules.append(r)
                print(f"  ✓ {describe_rule(r)}")
            else:
                print("  ⚠ Giá trị không hợp lệ.")

        elif choice == "c":
            pat = input("Pattern tên file: ").strip()
            if not pat:
                print("  ⚠ Pattern rỗng.")
                continue
            if pat.lower().startswith("re:"):
                try:
                    re.compile(pat[3:])
                except re.error as e:
                    print(f"  ⚠ Regex không hợp lệ: {e}")
                    continue
            r = {"type": "name", "pattern": pat}
            rules.append(r)
            print(f"  ✓ {describe_rule(r)}")

        elif choice == "d":
            if not rules:
                print("  ⚠ Chưa có rule nào.")
                continue
            return rules

        else:
            print("  ⚠ Lựa chọn không hợp lệ.")


def choose_rules():
    """Hỏi dùng lại rule cũ hay tạo mới; lưu lại kết quả cuối cùng."""
    saved = load_rules()

    if saved:
        print(f"\n📋 Đã có {len(saved)} rule lưu từ lần trước ({RULES_FILE.name}):")
        print_rules(saved)
        print("\nBạn muốn:")
        print("  Enter / Y = DÙNG LẠI các rule này")
        print("  A         = giữ rule cũ và THÊM rule mới")
        print("  N         = bỏ rule cũ, TẠO MỚI hoàn toàn")
        ans = input("Chọn [Y/A/N]: ").strip().lower() or "y"

        if ans == "y":
            return saved
        if ans == "a":
            rules = saved + ask_new_rules()
        elif ans == "n":
            rules = ask_new_rules()
        else:
            print("Lựa chọn không hợp lệ.")
            return None
    else:
        rules = ask_new_rules()

    save_rules(rules)
    print(f"\n💾 Đã lưu {len(rules)} rule vào {RULES_FILE.name}")
    return rules


def match_name(name, pattern):
    if pattern.lower().startswith("re:"):
        return re.search(pattern[3:], name, re.IGNORECASE) is not None
    return fnmatch.fnmatch(name.lower(), pattern.lower())


def compute_deletions(images, rules):
    """
    images: list Path đã sort tự nhiên.
    Trả về dict {index (0-based): [lý do, ...]}.
    """
    n = len(images)
    dels = {}

    def mark(i, why):
        dels.setdefault(i, []).append(why)

    for r in rules:
        t = r["type"]
        if t == "first":
            for pos in range(r["start"], min(r["end"], n) + 1):
                mark(pos - 1, "đầu")
        elif t == "last":
            for pos in range(max(1, n - r["count"] + 1), n + 1):
                mark(pos - 1, "cuối")
        elif t == "name":
            for i, p in enumerate(images):
                if match_name(p.name, r["pattern"]):
                    mark(i, f"tên:{r['pattern']}")

    return dels


def ask_scope(folders):
    """Lọc chapter: Enter = tất cả; 'A-B' = thư mục thứ A..B; còn lại = từ khóa tên."""
    print("\nPhạm vi áp dụng:")
    print("  Enter      = tất cả thư mục")
    print("  vd 10-20   = chỉ thư mục thứ 10 đến 20 trong danh sách đã sort")
    print("  vd ch.5,ch.6 = chỉ thư mục có tên chứa từ khóa (cách nhau dấu phẩy)")
    raw = input("Phạm vi: ").strip()

    if not raw:
        return folders

    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", raw)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a < 1 or b < a:
            print("⚠ Range không hợp lệ, dùng tất cả.")
            return folders
        return folders[a - 1:b]

    kws = [k.strip().lower() for k in raw.split(",") if k.strip()]
    return [t for t in folders if any(k in t[0].name.lower() for k in kws)]


def run_rule_mode():
    print("\n" + "-" * 70)
    print(" CHẾ ĐỘ 2: Xóa file theo VỊ TRÍ / TÊN")
    print("-" * 70)
    print("Áp dụng cho từng thư mục chứa ảnh (chapter), thứ tự file theo sort tự nhiên.")

    root = choose_directory(
        "\nĐường dẫn thư mục gốc cần quét (sẽ quét tất cả thư mục con):",
        default=SCRIPT_DIR,
    )
    if not root:
        return

    print("Đang quét thư mục chứa ảnh...")
    folders = find_image_folders(root)
    if not folders:
        print(f"\n⚠ Không tìm thấy thư mục nào chứa ảnh trong: {root}")
        return
    print(f"Tìm thấy {len(folders)} thư mục chứa ảnh.")

    folders = ask_scope(folders)
    if not folders:
        print("\n⚠ Không có thư mục nào khớp phạm vi.")
        return
    print(f"→ Áp dụng cho {len(folders)} thư mục.")

    rules = choose_rules()
    if not rules:
        return

    print("\nRule đang dùng:")
    print_rules(rules)

    # ---- Tính kế hoạch xóa (DRY RUN) ----
    plan = []          # (folder, images, dels)
    skipped_all = []   # thư mục bị bỏ qua vì sẽ xóa trắng
    total_files = 0
    total_del = 0

    for folder, imgs in folders:
        total_files += len(imgs)
        dels = compute_deletions(imgs, rules)
        if not dels:
            continue
        if len(dels) >= len(imgs):
            skipped_all.append((folder, len(imgs)))
            continue
        plan.append((folder, imgs, dels))
        total_del += len(dels)

    print("\n" + "-" * 70)
    print("XEM TRƯỚC (DRY RUN - chưa xóa gì)")
    print("-" * 70)

    log_lines = [
        "Advertisement Cleaner - RULE MODE",
        f"Time: {datetime.now()}",
        f"Root: {root}",
        "Rules:",
    ]
    log_lines += [f"  {i}. {describe_rule(r)}" for i, r in enumerate(rules, 1)]
    log_lines.append("")

    def rel_of(p):
        try:
            return p.relative_to(root)
        except ValueError:
            return p

    for folder, imgs, dels in plan:
        print(f"\n{rel_of(folder)}  ({len(imgs)} file → xóa {len(dels)})")
        log_lines.append(f"[FOLDER] {folder} ({len(imgs)} file → xóa {len(dels)})")

        items = sorted(dels.items())
        for k, (i, why) in enumerate(items):
            log_lines.append(f"   ✗ {imgs[i].name}  (rule: {', '.join(why)})")
            if k < 6:
                print(f"   ✗ {imgs[i].name}  ({', '.join(why)})")
        if len(items) > 6:
            print(f"   ... và {len(items) - 6} file khác (xem đầy đủ trong log)")

    for folder, n in skipped_all:
        print(f"\n⚠ BỎ QUA {rel_of(folder)}: rule sẽ xóa TRẮNG cả {n} file")
        log_lines.append(f"[SKIPPED - would delete all] {folder} ({n} file)")

    untouched = len(folders) - len(plan) - len(skipped_all)

    print("\n" + "-" * 70)
    print(f"Tổng: {len(folders)} thư mục, {total_files} file.")
    print(f"Sẽ xóa {total_del} file trong {len(plan)} thư mục.")
    print(f"Không bị ảnh hưởng: {untouched} thư mục"
          + (f"; bỏ qua vì xóa trắng: {len(skipped_all)}" if skipped_all else ""))
    print("-" * 70)

    ratio = total_del / total_files if total_files else 0
    if ratio > BIG_DELETE_RATIO:
        print(f"⚠️ CẢNH BÁO: sẽ xóa {ratio:.0%} tổng số file. Kiểm tra kỹ rule trước khi xóa!")

    deleted = 0
    errors = 0
    delete_mode = False

    if total_del > 0:
        confirm = input("\nGõ DELETE để xác nhận xóa (Enter để bỏ qua, không xóa gì): ").strip()
        delete_mode = confirm == "DELETE"

        if delete_mode:
            print()
            for folder, imgs, dels in plan:
                for i in sorted(dels):
                    p = imgs[i]
                    try:
                        p.unlink()
                        deleted += 1
                        print(f"  🗑️ Đã xóa: {rel_of(p)}")
                        log_lines.append(f"[DELETED] {p}")
                    except Exception as e:
                        errors += 1
                        print(f"  ✗ Không xóa được: {rel_of(p)} | {e}")
                        log_lines.append(f"[DELETE ERROR] {p}: {e}")
        else:
            print("Đã bỏ qua, không xóa gì cả.")
    else:
        print("\nKhông có file nào khớp rule.")

    log_lines.extend([
        "",
        "=" * 70,
        f"Folders scanned    : {len(folders)}",
        f"Folders affected   : {len(plan)}",
        f"Folders skipped    : {len(skipped_all)} (would delete all)",
        f"Files planned      : {total_del}",
        f"Files deleted      : {deleted}",
        f"Errors             : {errors}",
        f"Mode               : {'DELETE' if delete_mode else 'DRY RUN ONLY'}",
        "=" * 70,
    ])

    log_path = make_log_path("ad_cleaner_rules")
    log_path.write_text("\n".join(log_lines), encoding="utf-8")

    print("\n" + "=" * 70)
    print("✅ HOÀN TẤT")
    print("=" * 70)
    print(f"Đã xóa            : {deleted}")
    print(f"Lỗi               : {errors}")
    print(f"Log               : {log_path}")
    print("=" * 70)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    print("=" * 70)
    print(" Advertisement Cleaner")
    print("=" * 70)
    print()
    print("Chọn chế độ:")
    print("1. Xóa quảng cáo theo HASH (so khớp ảnh mẫu trong ad_samples)")
    print("2. Xóa file theo VỊ TRÍ / TÊN (file đầu, file cuối, pattern tên)")

    mode = input("Chọn [1/2]: ").strip() or "1"

    if mode == "1":
        run_hash_mode()
    elif mode == "2":
        run_rule_mode()
    else:
        print("Lựa chọn không hợp lệ.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nĐã hủy bởi người dùng.")
    except Exception as e:
        print(f"\nLỖI: {e}")

    input("\nNhấn Enter để thoát...")