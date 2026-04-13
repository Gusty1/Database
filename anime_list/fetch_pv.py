"""
fetch_pv.py - 自動補全動漫 PV 網址的爬蟲腳本

功能：
  1. 從 ACGNTaiwan/Anime-List 下載原始 JSON（所有月份或指定月份）
  2. 比對 output/ 目錄，找出需要更新的項目（pv == null 的）
  3. 搜尋 MyAnimeList 取得 YouTube PV 網址
  4. 輸出帶 pv 欄位的 JSON 到 output/ 目錄

排程：每天台灣時間 10:00 由 GitHub Actions 觸發

用法：
  # 處理所有月份（預設）
  python fetch_pv.py

  # 只處理指定月份（格式 YYYY.MM）
  python fetch_pv.py --month 2026.04
  python fetch_pv.py --month 2025.01
"""

import argparse
import json
import random
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

# --- 常數設定 ---

# ACGNTaiwan 的 JSON 索引頁（列出所有可用的月份 JSON）
ANIME_LIST_INDEX_URL = "https://api.github.com/repos/ACGNTaiwan/Anime-List/contents/anime-data"
# 下載單一月份 JSON 的 Base URL
ANIME_JSON_BASE_URL = "https://acgntaiwan.github.io/Anime-List/anime-data/"

# MAL 搜尋 URL（cat= 代表分類，1 = 動畫）
MAL_SEARCH_URL = "https://myanimelist.net/search/all?q={query}&cat=anime"
MAL_ANIME_URL = "https://myanimelist.net"

# 輸出目錄（相對於此腳本的位置）
OUTPUT_DIR = Path(__file__).parent / "output"

# 模擬瀏覽器的 Headers，降低被 MAL 封鎖的機率
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,ja;q=0.8,en-US;q=0.7,en;q=0.6",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# 每次 MAL 請求之間的隨機延遲範圍（秒）
DELAY_MIN = 3.0
DELAY_MAX = 6.0


# --- 核心邏輯 ---

def random_delay() -> None:
    """在 MAL 請求之間加入隨機延遲，避免被封鎖。"""
    delay = random.uniform(DELAY_MIN, DELAY_MAX)
    print(f"  [延遲] 等待 {delay:.1f} 秒...")
    time.sleep(delay)


def get_available_json_files() -> list[str]:
    """
    從 GitHub API 取得 ACGNTaiwan/Anime-List 的 anime-data 目錄，
    回傳所有 anime{YYYY.MM}.json 的檔案名稱清單。
    """
    print("[Step 1] 取得可用的 JSON 檔案清單...")
    try:
        response = requests.get(ANIME_LIST_INDEX_URL, timeout=30)
        response.raise_for_status()
        files = response.json()
        # 只篩選 anime{YYYY.MM}.json 格式的檔案
        json_files = [
            f["name"] for f in files
            if re.match(r"^anime\d{4}\.\d{2}\.json$", f["name"])
        ]
        json_files.sort()
        print(f"  找到 {len(json_files)} 個 JSON 檔案：{json_files}")
        return json_files
    except Exception as e:
        print(f"  [錯誤] 無法取得 JSON 清單：{e}")
        return []


def download_source_json(filename: str) -> Optional[list[dict]]:
    """下載指定月份的原始 JSON 資料。"""
    url = ANIME_JSON_BASE_URL + filename
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  [錯誤] 下載 {filename} 失敗：{e}")
        return None



def save_output_json(filename: str, data: list[dict]) -> None:
    """將帶 pv 欄位的 JSON 儲存到 output/ 目錄。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [儲存] 已寫入 {output_path}")


def extract_youtube_id_from_html(soup: BeautifulSoup) -> Optional[str]:
    """
    從已解析的 BeautifulSoup 物件中取出 YouTube 影片 ID。

    MAL 動漫主頁的 PV 區塊結構：
      <a class="iframe js-fancybox-video video-unit promotion"
         href="https://www.youtube-nocookie.com/embed/VIDEO_ID?...">

    支援的 YouTube 網域：
    - youtube.com/embed/VIDEO_ID
    - youtube-nocookie.com/embed/VIDEO_ID

    方法優先順序（精確 → 廣泛）：
    1. <a class="video-unit promotion"> 的 href（MAL 主頁 PV 區塊，最精確）
    2. <iframe src> 或 <iframe data-src>
    3. 任何元素的 data-src 含 youtube(-nocookie).com/embed
    """
    # YouTube embed URL 的 regex（同時支援 youtube.com 和 youtube-nocookie.com）
    yt_embed_pattern = re.compile(r"youtube(?:-nocookie)?\.com/embed/([a-zA-Z0-9_-]+)")

    # 方法 1：MAL 主頁的 PV 連結 <a class="video-unit promotion" href="...">
    # 這是最精確的取法，只會拿到真正的 PV
    for a_tag in soup.find_all("a", class_="video-unit"):
        href = a_tag.get("href", "")
        match = yt_embed_pattern.search(href)
        if match:
            return match.group(1)

    # 方法 2：iframe src / data-src
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "") or iframe.get("data-src", "")
        match = yt_embed_pattern.search(src)
        if match:
            return match.group(1)

    # 方法 3：任何元素的 data-src（MAL 有時用延遲載入）
    for el in soup.find_all(attrs={"data-src": True}):
        match = yt_embed_pattern.search(el["data-src"])
        if match:
            return match.group(1)

    return None


def extract_youtube_url_from_mal_page(anime_url: str) -> Optional[str]:
    """
    從 MAL 動漫主頁取得 YouTube PV 網址。

    只抓主頁的 PV 區塊（class="video-unit promotion"）。
    若主頁找不到 YT 連結，直接回傳 None，不再嘗試 /video 子頁，
    以避免誤抓到其他不相關影片。
    """
    try:
        random_delay()
        response = requests.get(anime_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        video_id = extract_youtube_id_from_html(soup)
        if video_id:
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            print(f"  [PV] 找到 YouTube 網址：{youtube_url}")
            return youtube_url

        print(f"  [PV] 主頁找不到 YouTube 影片，設為 null：{anime_url}")
        return None

    except Exception as e:
        print(f"  [錯誤] 解析 MAL 頁面失敗 {anime_url}：{e}")
        return None


def search_mal_for_pv(original_name: str) -> Optional[str]:
    """
    搜尋 MyAnimeList，找到有 PV 的動漫頁面，回傳 YouTube 網址。

    MAL 搜尋結果的 HTML 結構：
      <h2 id="anime">Anime</h2>
      <article>...</article>   ← article 是 h2 的兄弟節點，不是子節點
      <article>...</article>

    每個 article 內部：
      - 主頁連結：<a class="hoverinfo_trigger fw-b fl-l" href="/anime/62001/...">
      - PV 圖示：<i class="malicon malicon-movie-pv"> 在 <a class="mal-icon"> 內

    搜尋邏輯：
    1. 找到 <h2 id="anime"> 標籤
    2. 用 find_next_siblings("article") 取得所有後續的 article 兄弟節點
    3. 找第一筆含有 malicon-movie-pv 圖示的 article
    4. 從該 article 取主頁連結（class="hoverinfo_trigger fw-b fl-l"）
    5. 進入主頁取出 YouTube embed URL
    """
    print(f"  [MAL 搜尋] '{original_name}'")

    try:
        encoded_name = quote(original_name)
        search_url = MAL_SEARCH_URL.format(query=encoded_name)

        random_delay()
        response = requests.get(search_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # 找 <h2 id="anime"> 標籤（注意：article 是它的兄弟節點，不是子節點）
        anime_heading = soup.find("h2", id="anime")
        if not anime_heading:
            print(f"  [MAL] 搜尋結果中找不到 <h2 id=\"anime\"> 標籤")
            return None

        # 取得所有緊接在 h2 後面的 article 兄弟節點
        articles = anime_heading.find_next_siblings("article")
        if not articles:
            print(f"  [MAL] 找不到任何 article 結果")
            return None

        print(f"  [MAL] 找到 {len(articles)} 筆搜尋結果，尋找有 PV 的項目...")

        for i, article in enumerate(articles):
            # 檢查是否有 malicon-movie-pv 圖示（代表有 PV）
            pv_icon = article.find("i", class_="malicon malicon-movie-pv")
            if not pv_icon:
                print(f"  [MAL] 第 {i + 1} 筆沒有 PV 標籤，跳過")
                continue

            # 取主頁連結（class 包含 hoverinfo_trigger fw-b fl-l 的 <a>）
            # 這個連結指向 /anime/ID/Name 格式，是動漫主頁
            main_link = article.find("a", class_="hoverinfo_trigger fw-b fl-l")
            if not main_link:
                # 備用：找任何 /anime/數字/ 格式的連結（排除 /video 結尾）
                main_link = article.find(
                    "a",
                    href=re.compile(r"/anime/\d+/[^/]+$"),
                )
            if not main_link:
                print(f"  [MAL] 第 {i + 1} 筆找不到主頁連結，跳過")
                continue

            href = main_link["href"]
            anime_url = href if href.startswith("http") else MAL_ANIME_URL + href
            print(f"  [MAL] 第 {i + 1} 筆有 PV，進入主頁：{anime_url}")

            # 進入動漫主頁取得 YouTube 網址
            youtube_url = extract_youtube_url_from_mal_page(anime_url)
            return youtube_url  # 無論是否找到都回傳（None 或 URL）

        print(f"  [MAL] 所有搜尋結果都沒有 PV")
        return None

    except Exception as e:
        print(f"  [錯誤] MAL 搜尋失敗 '{original_name}'：{e}")
        return None


def fill_missing_pvs(items: list[dict]) -> tuple[list[dict], int]:
    """
    對 pv == None 的項目進行 MAL 搜尋，補全 PV 網址。
    回傳更新後的列表和成功填入的數量。
    """
    updated_items = [dict(item) for item in items]  # 建立新列表，不修改原始資料
    filled_count = 0
    null_items = [item for item in updated_items if item.get("pv") is None]

    if not null_items:
        print("  所有項目都已有 pv 資料，跳過搜尋。")
        return updated_items, 0

    print(f"  需要補全 {len(null_items)} 筆 pv 資料...")

    for i, item in enumerate(updated_items):
        if item.get("pv") is not None:
            continue  # 已有 pv，跳過

        original_name = item.get("originalName")
        name = item.get("name", "未知")

        if not original_name:
            print(f"  [{i + 1}] '{name}' 沒有 originalName，跳過")
            continue

        print(f"  [{i + 1}] 處理：{name}（{original_name}）")
        youtube_url = search_mal_for_pv(original_name)
        # 即使找不到（None）也要明確設定，避免重複搜尋
        item["pv"] = youtube_url
        if youtube_url:
            filled_count += 1

    return updated_items, filled_count


def process_file(filename: str) -> None:
    """
    處理單一 JSON 檔案的完整流程。

    行為規則：
    - output/ 已存在同名檔案 → 直接跳過，不執行任何爬蟲，保護人工審查的結果
    - output/ 不存在同名檔案 → 下載原始 JSON，對所有項目跑 MAL 搜尋，寫入新檔
    """
    print(f"\n{'=' * 60}")
    print(f"處理檔案：{filename}")
    print(f"{'=' * 60}")

    # 已存在就跳過，完全不動（保護人工審查後的 pv 值）
    if (OUTPUT_DIR / filename).exists():
        print(f"  已存在，跳過。")
        return

    # 不存在 → 下載原始 JSON 並初始化
    source_items = download_source_json(filename)
    if source_items is None:
        print(f"  跳過 {filename}（下載失敗）")
        return

    print(f"  新檔案，執行全量初始化（第一次可能需要較長時間）")

    # 對每個項目加入 pv 欄位（初始為 None）後跑爬蟲
    init_items = [{**item, "pv": None} for item in source_items]
    updated_items, filled_count = fill_missing_pvs(init_items)

    # 儲存結果（每處理完一個月份立刻寫入，中斷也不丟失進度）
    save_output_json(filename, updated_items)

    null_remaining = sum(1 for item in updated_items if item.get("pv") is None)
    print(f"  完成：找到 {filled_count} 筆 PV，剩餘 {null_remaining} 筆設為 null")


def parse_args() -> argparse.Namespace:
    """解析命令列參數。"""
    parser = argparse.ArgumentParser(
        description="自動補全動漫 PV 網址的爬蟲腳本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  # 處理所有月份
  python fetch_pv.py

  # 只處理指定月份
  python fetch_pv.py --month 2026.04
  python fetch_pv.py --month 2025.01
        """,
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        metavar="YYYY.MM",
        help="只處理指定年月份（格式：YYYY.MM，例如 2026.04）。不傳此參數則處理所有月份。",
    )
    return parser.parse_args()


def resolve_target_files(month: Optional[str]) -> list[str]:
    """
    根據參數決定要處理的 JSON 檔案清單。

    - month 為 None：從 GitHub API 取得所有月份
    - month 有值：直接組出單一檔名（不需呼叫 GitHub API）
    """
    if month is not None:
        # 驗證格式 YYYY.MM
        if not re.match(r"^\d{4}\.\d{2}$", month):
            print(f"[錯誤] --month 格式不正確：'{month}'，應為 YYYY.MM（例如 2026.04）")
            return []
        filename = f"anime{month}.json"
        print(f"[模式] 指定月份：{filename}")
        return [filename]

    print("[模式] 全部月份")
    return get_available_json_files()


def main() -> None:
    """主程式入口。"""
    print("=" * 60)
    print("fetch_pv.py - 動漫 PV 網址自動補全腳本")
    print("=" * 60)

    args = parse_args()

    # 根據參數決定要處理哪些檔案
    json_files = resolve_target_files(args.month)
    if not json_files:
        print("[錯誤] 無可處理的 JSON 檔案，結束程式。")
        return

    # 逐一處理每個月份的 JSON
    for filename in json_files:
        process_file(filename)

    print("\n" + "=" * 60)
    print("所有檔案處理完畢。")
    print("=" * 60)


if __name__ == "__main__":
    main()
