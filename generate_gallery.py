import os
import json
import re

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTHOR_FOLDERS = [
    {"id": "hiiragihiiro", "name": "@hiiragihiiro", "path": "fanbox_images_@hiiragihiiro"},
    {"id": "zrcy5345", "name": "zrcy5345", "path": "fanbox_images_zrcy5345"}
]

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

def natural_sort_key(s):
    """文字列内の数字を数値として比較する自然ソートキー"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def scan_folders():
    gallery_data = []

    for author in AUTHOR_FOLDERS:
        author_dir = os.path.join(WORKSPACE_DIR, author["path"])
        if not os.path.exists(author_dir):
            continue

        author_data = {
            "id": author["id"],
            "name": author["name"],
            "folder": author["path"],
            "works": []
        }

        # 作品フォルダ一覧を取得
        work_folders = [f for f in os.listdir(author_dir) if os.path.isdir(os.path.join(author_dir, f))]
        # フォルダ名の自然ソート（通常はID昇順/降順）
        work_folders.sort(key=natural_sort_key, reverse=True)

        for work_dir in work_folders:
            work_path = os.path.join(author_dir, work_dir)
            files = os.listdir(work_path)
            
            # 画像ファイル抽出
            images = [f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]
            if not images:
                continue

            images.sort(key=natural_sort_key)

            # タイトルとIDの分離
            match = re.match(r"^(\d+)_(.+)$", work_dir)
            if match:
                work_id = match.group(1)
                title = match.group(2)
            else:
                work_id = ""
                title = work_dir

            # 相対パスを作成
            rel_work_path = os.path.join(author["path"], work_dir).replace("\\", "/")
            
            author_data["works"].append({
                "folderName": work_dir,
                "id": work_id,
                "title": title,
                "path": rel_work_path,
                "images": images,
                "thumbnail": f"{rel_work_path}/{images[0]}"
            })

        gallery_data.append(author_data)

    # JSファイルとして書き出し
    js_content = f"const GALLERY_DATA = {json.dumps(gallery_data, ensure_ascii=False, indent=2)};"
    with open(os.path.join(WORKSPACE_DIR, "gallery_data.js"), "w", encoding="utf-8") as f:
        f.write(js_content)

    print("gallery_data.js successfully generated!")

if __name__ == "__main__":
    scan_folders()
