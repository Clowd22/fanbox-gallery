import asyncio
import os
import json
from playwright.async_api import async_playwright

COOKIE_FILE = "cookies.json"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        login_url = "https://accounts.pixiv.net/login?prompt=select_account&return_to=https%3A%2F%2Fwww.fanbox.cc%2Fauth%2Fstart&source=fanbox"
        
        is_logged_in = False
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, "r") as f:
                cookies = json.load(f)
                await context.add_cookies(cookies)
            print("保存されたCookieを読み込みました。アクセスをテストします...")
            await page.goto("https://zrcy5345.fanbox.cc/posts?page=1&sort=newest")
            
            if "accounts.pixiv.net/login" not in page.url:
                print("ログインセッションの復元に成功しました。")
                is_logged_in = True

        if not is_logged_in:
            print("=" * 50)
            print("ブラウザでログインとCAPTCHAの突破を行ってください。")
            print("ログインが完全に完了したら、このコンソールに戻り [Enter] キーを押してください。")
            print("=" * 50)
            
            await page.goto(login_url)
            await asyncio.to_thread(input, ">> ログイン完了後、Enterを押してください: ")
            
            cookies = await context.cookies()
            with open(COOKIE_FILE, "w") as f:
                json.dump(cookies, f)
            print("Cookieを保存しました。")

        base_output_dir = os.path.abspath("fanbox_images_zrcy5345")
        os.makedirs(base_output_dir, exist_ok=True)
        print(f"ベース保存先ディレクトリ: {base_output_dir}")

        processed_post_ids = set()

        # 1〜10ページを巡回してすべての投稿IDを収集
        all_post_ids = []
        for page_num in range(11, 21):  # ページ番号を11から20に変更
            list_url = f"https://zrcy5345.fanbox.cc/posts?page={page_num}&sort=newest"
            print(f"リンク収集中: page {page_num}")
            
            await page.goto(list_url)
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1500)

            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await page.wait_for_timeout(1000)

            post_cards = await page.locator("a[href*='/posts/']").all()
            for card in post_cards:
                href = await card.get_attribute("href")
                if href and "/posts/" in href:
                    post_id = href.split("/posts/")[-1].split("?")[0]
                    if post_id.isdigit() and post_id not in processed_post_ids:
                        processed_post_ids.add(post_id)
                        all_post_ids.append(post_id)

        print(f"\n合計 {len(all_post_ids)} 件の投稿IDを取得しました。画像のダウンロードを開始します。")

        for post_id in all_post_ids:
            try:
                post_url = f"https://zrcy5345.fanbox.cc/posts/{post_id}"
                print(f"\n--- 投稿ID: {post_id} の処理 ---")
                
                await page.goto(post_url)
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(2000)

                # ページをスクロールしてすべての遅延画像を強制描画
                for _ in range(6):
                    await page.evaluate("window.scrollBy(0, 800);")
                    await page.wait_for_timeout(800)

                # 【改善】記事本文のラッパー（article）内の h1 を最優先で取得し、余計なUIテキストを排除する
                raw_title = await page.evaluate("""() => {
                    // 1. 記事コンテナ（article）内のh1を探す
                    const articleH1 = document.querySelector('article h1');
                    if (articleH1 && articleH1.innerText.trim()) {
                        return articleH1.innerText.trim();
                    }
                    
                    // 2. なければメインエリアの最初のh1を探す
                    const mainH1 = document.querySelector('main h1');
                    if (mainH1 && mainH1.innerText.trim()) {
                        return mainH1.innerText.trim();
                    }

                    // 3. それでもダメならページ内のh1を総当たりし、クリエイター名やUIを除外する
                    const h1s = document.querySelectorAll('h1');
                    for (let h1 of h1s) {
                        const text = h1.innerText.trim();
                        if (text && !text.includes('支援者') && !text.includes('プラン')) {
                            return text;
                        }
                    }
                    return "untitled";
                }""")
                
                title = "".join(c for c in raw_title if c.isalnum() or c in (' ', '_', '-')).strip()
                if not title:
                    title = "untitled"
                
                safe_title = title[:50] if len(title) > 50 else title
                print(f"  タイトル: {safe_title}")

                # 投稿ごとに専用のフォルダを作成
                folder_name = f"{post_id}_{safe_title}"
                post_output_dir = os.path.join(base_output_dir, folder_name)
                os.makedirs(post_output_dir, exist_ok=True)

                # 画像URLの抽出
                image_urls = await page.evaluate(f"""() => {{
                    const urls = new Set();
                    
                    document.querySelectorAll('img').forEach(img => {{
                        const src = img.src || img.getAttribute('data-src');
                        if (src && src.includes('/images/post/{post_id}/')) {{
                            urls.add(src);
                        }}
                    }});

                    document.querySelectorAll('a').forEach(a => {{
                        const href = a.href;
                        if (href && href.includes('/images/post/{post_id}/')) {{
                            urls.add(href);
                        }}
                    }});

                    return Array.from(urls);
                }}""")

                # サムネイルパスを高解像度版（1200）に変換
                normalized_urls = []
                for url in image_urls:
                    if "/w/" in url:
                        parts = url.split('/')
                        if "w" in parts:
                            idx = parts.index("w")
                            if idx + 1 < len(parts):
                                parts[idx + 1] = "1200"
                                url = '/'.join(parts)
                    normalized_urls.append(url)

                normalized_urls = list(dict.fromkeys(normalized_urls))
                print(f"  抽出された本文画像数: {len(normalized_urls)} 件")

                if len(normalized_urls) == 0:
                    print("  -> 画像がありません（スキップします）")
                    continue

                for img_count, img_url in enumerate(normalized_urls):
                    print(f"  ダウンロード中: {img_url}")
                    
                    try:
                        response = await context.request.get(img_url)
                        if response.ok:
                            binary_data = await response.body()
                            
                            ext = "jpg"
                            if ".png" in img_url:
                                ext = "png"
                            elif ".jpeg" in img_url:
                                ext = "jpeg"
                            elif ".webp" in img_url:
                                ext = "webp"
                            
                            file_name = f"{img_count}.{ext}"
                            file_path = os.path.join(post_output_dir, file_name)
                            
                            with open(file_path, "wb") as f:
                                f.write(binary_data)
                            print(f"    [保存成功] -> {file_path}")
                        else:
                            print(f"    [保存失敗] HTTPステータス: {response.status}")
                    except Exception as e:
                        print(f"    [保存エラー]: {e}")

                await asyncio.sleep(1)

            except Exception as e:
                print(f"エラー発生 (投稿ID {post_id}): {e}")

        await browser.close()
        print("\nすべての処理が完了しました。")

asyncio.run(main())