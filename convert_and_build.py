import os
import shutil
import json
import re
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(WORKSPACE_DIR, "dist")

AUTHOR_FOLDERS = [
    {"id": "hiiragihiiro", "name": "@hiiragihiiro", "path": "fanbox_images_@hiiragihiiro"},
    {"id": "zrcy5345", "name": "zrcy5345", "path": "fanbox_images_zrcy5345"}
]

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_DIMENSION = 2048  # 画像の最大長辺ピクセル数
WEBP_QUALITY = 78     # WebP圧縮クオリティ (高画質かつ軽量)

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def process_single_image(args):
    src_path, dst_path = args
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    
    # 既に変換済みでDstが存在すればスキップ（再実行時の高速化）
    if os.path.exists(dst_path):
        return

    try:
        with Image.open(src_path) as img:
            # EXIF回転補正
            img = ImageOps.exif_transpose(img)
            
            # RGB変換
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

            # リサイズ
            width, height = img.size
            if max(width, height) > MAX_DIMENSION:
                if width > height:
                    new_w = MAX_DIMENSION
                    new_h = int(height * (MAX_DIMENSION / width))
                else:
                    new_h = MAX_DIMENSION
                    new_w = int(width * (MAX_DIMENSION / height))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # WebPとして保存
            img.save(dst_path, "WEBP", quality=WEBP_QUALITY, method=4)
    except Exception as e:
        print(f"Error processing {src_path}: {e}")
        # エラー時はそのままコピー
        try:
            shutil.copy2(src_path, dst_path)
        except Exception:
            pass

def convert_and_build():
    print("=== デプロイ用WebP変換およびサイトビルドを開始します ===")
    
    if os.path.exists(DIST_DIR):
        print(f"既存の dist フォルダを整理中...")

    os.makedirs(DIST_DIR, exist_ok=True)

    gallery_data = []
    conversion_tasks = []

    for author in AUTHOR_FOLDERS:
        src_author_dir = os.path.join(WORKSPACE_DIR, author["path"])
        if not os.path.exists(src_author_dir):
            continue

        author_data = {
            "id": author["id"],
            "name": author["name"],
            "folder": author["path"],
            "works": []
        }

        work_folders = [f for f in os.listdir(src_author_dir) if os.path.isdir(os.path.join(src_author_dir, f))]
        work_folders.sort(key=natural_sort_key, reverse=True)

        for work_dir in work_folders:
            src_work_path = os.path.join(src_author_dir, work_dir)
            files = os.listdir(src_work_path)
            
            orig_images = [f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]
            if not orig_images:
                continue

            orig_images.sort(key=natural_sort_key)

            match = re.match(r"^(\d+)_(.+)$", work_dir)
            if match:
                work_id = match.group(1)
                title = match.group(2)
            else:
                work_id = ""
                title = work_dir

            rel_work_path = f"{author['path']}/{work_dir}"
            converted_images = []

            for img_name in orig_images:
                base_name = os.path.splitext(img_name)[0]
                webp_name = f"{base_name}.webp"
                
                src_file = os.path.join(src_work_path, img_name)
                dst_file = os.path.join(DIST_DIR, author["path"], work_dir, webp_name)
                
                conversion_tasks.append((src_file, dst_file))
                converted_images.append(webp_name)

            author_data["works"].append({
                "folderName": work_dir,
                "id": work_id,
                "title": title,
                "path": rel_work_path,
                "images": converted_images,
                "thumbnail": f"{rel_work_path}/{converted_images[0]}"
            })

        gallery_data.append(author_data)

    print(f"合計 {len(conversion_tasks)} 枚の画像を高速変換中 (マルチスレッド)...")
    
    # 並列変換処理 (CPUコア数に合わせて最適化)
    max_workers = min(16, (os.cpu_count() or 4) * 2)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(process_single_image, conversion_tasks))

    print("画像のWebP変換が完了しました。")

    # gallery_data.js を dist 内に作成
    js_content = f"const GALLERY_DATA = {json.dumps(gallery_data, ensure_ascii=False, indent=2)};"
    with open(os.path.join(DIST_DIR, "gallery_data.js"), "w", encoding="utf-8") as f:
        f.write(js_content)

    # index.html を dist にコピー
    shutil.copy2(os.path.join(WORKSPACE_DIR, "index.html"), os.path.join(DIST_DIR, "index.html"))

    print(f"=== ビルド完了! 出力先: {DIST_DIR} ===")

if __name__ == "__main__":
    convert_and_build()
